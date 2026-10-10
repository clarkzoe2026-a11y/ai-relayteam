"""Remote Progress Sync v0.1 — authoritative state transition sync.

When the secret-free authoritative continuity docs (the Remote Continuity
Package, ``.ai-hub/remote-continuity.json``) change locally, converge them to the
Remote Continuity Source so a fresh Chat / Agent restores the latest truth without
anyone remembering to commit / push.

The authoritative docs stay the only Source of Truth; there is no second state
store. The first backend is the existing git remote, behind ``GitBackend``; the
product semantics (states, guards, allowlist) do not depend on GitHub.

Hard rules (asserted in tests/test_remote_sync.py):
* Only allowlisted package files are ever committed or pushed. Other working-tree
  changes (source code, binaries, staged files) are left exactly as they are, and
  unpushed local commits that touch non-package files block the sync.
* New content is scanned before any commit. A secret or private absolute path
  is BLOCKED_SECRET: nothing is committed and the Remote is untouched.
* Remote ahead is integrated only when provably safe (disjoint files, fast-forward
  or clean tree-level merge). Concurrent edits to the same package file are
  SYNC_CONFLICT; there is no last-write-wins, no force push, no overwrite.
* Network / auth / push failures keep the local state, never report "synced",
  and leave a recoverable status. A later run retries.
* The sync propagates already-written authoritative state; it never creates or
  edits facts, so it cannot widen any Agent's write authority or bypass a Gate.
"""

import argparse
import datetime
import fcntl
import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import identity_guard

MANIFEST = ".ai-hub/remote-continuity.json"

SYNCED = "SYNCED"
UP_TO_DATE = "UP_TO_DATE"
PENDING = "PENDING"
SYNC_CONFLICT = "SYNC_CONFLICT"
BLOCKED_SECRET = "BLOCKED_SECRET"
BLOCKED_UNSAFE = "BLOCKED_UNSAFE"
FAILED_RETRYABLE = "FAILED_RETRYABLE"
ALREADY_RUNNING = "ALREADY_RUNNING"
BLOCKED_IDENTITY = "BLOCKED_IDENTITY"
BLOCKED_STATES = (SYNC_CONFLICT, BLOCKED_SECRET, BLOCKED_UNSAFE, BLOCKED_IDENTITY)

SECRET_RULES = [
    ("github_token", r"\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    ("aws_access_key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("google_api_key", r"\bAIza[0-9A-Za-z_\-]{35}"),
    ("llm_api_key", r"\bsk-(ant-|proj-)?[A-Za-z0-9_\-]{20,}"),
    ("slack_token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    ("private_key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("jwt", r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ("bearer_credential", r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    ("oauth_client_secret", r"(?i)client[_-]?secret\s*[:=]\s*\S{8,}"),
    ("cookie_or_session", r"(?i)\b(set-cookie|cookie|session[_-]?(id|token|secret))\s*[:=]\s*\S{8,}"),
    ("credential_assignment", r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|"
                              r"secret[_-]?key|password|passwd)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-./+=]{12,}"),
    ("private_absolute_path", r"(/" + r"Users/(?!Shared/)[^/\s`'\"]+/|/home/[^/\s`'\"]+/|[A-Za-z]:\\Users\\)"),
]
SECRET_PATTERNS = [(name, re.compile(pattern)) for name, pattern in SECRET_RULES]


class SyncBlocked(Exception):
    def __init__(self, state, reason, **evidence):
        super().__init__(reason)
        self.state = state
        self.reason = reason
        self.evidence = evidence


class GitBackend:
    """The v0.1 Remote Continuity backend: a git remote branch. Replaceable."""

    def __init__(self, root, remote="origin", branch="main"):
        self.root = Path(root)
        self.remote = remote
        self.branch = branch
        self.tracking = "refs/remotes/%s/%s" % (remote, branch)

    def env(self):
        return dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C")

    def git(self, *args, check=True, timeout=120):
        env = self.env()
        try:
            proc = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True,
                                  timeout=timeout, env=env)
        except (OSError, subprocess.SubprocessError) as error:
            raise SyncBlocked(FAILED_RETRYABLE, "git %s could not run: %s" % (args[0], error))
        if check and proc.returncode != 0:
            raise GitError(args, proc)
        return proc

    def fetch(self):
        proc = self.git("fetch", "--quiet", self.remote, "+refs/heads/%s:%s" % (self.branch, self.tracking),
                        check=False)
        if proc.returncode != 0:
            raise SyncBlocked(FAILED_RETRYABLE, "remote unavailable: fetch failed", detail=_tail(proc.stderr))

    def push(self):
        proc = self.git("push", "--porcelain", self.remote, "HEAD:refs/heads/%s" % self.branch, check=False)
        if proc.returncode == 0:
            return "pushed"
        text = proc.stdout + proc.stderr
        if "[rejected]" in text or "non-fast-forward" in text or "fetch first" in text:
            return "rejected"
        raise SyncBlocked(FAILED_RETRYABLE, "push failed", detail=_tail(text))

    def remote_head(self):
        proc = self.git("ls-remote", self.remote, "refs/heads/%s" % self.branch, check=False, timeout=60)
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        return proc.stdout.split()[0]


class GitError(Exception):
    def __init__(self, args, proc):
        super().__init__("git %s failed: %s" % (" ".join(args[:2]), _tail(proc.stderr)))


def _tail(text, limit=400):
    text = (text or "").strip()
    return text[-limit:]


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def load_manifest(root):
    path = Path(root) / MANIFEST
    with open(path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest.get("managed"), list) or not manifest["managed"]:
        raise ValueError("%s has no managed allowlist" % MANIFEST)
    return manifest


def is_managed(path, patterns):
    parts = path.split("/")
    for pattern in patterns:
        pattern_parts = pattern.split("/")
        if len(parts) == len(pattern_parts) and all(fnmatch.fnmatchcase(p, q) for p, q in zip(parts, pattern_parts)):
            return True
    return False


def scan_text(lines):
    """Return redacted findings: (line_number, rule) — never the matched value."""
    findings = []
    for number, line in lines:
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append((number, name))
    return findings


class RemoteProgressSync:
    def __init__(self, root, backend=None, manifest=None, state_dir=None):
        self.root = Path(root).resolve()
        self.manifest = manifest or load_manifest(self.root)
        config = self.manifest.get("backend", {})
        self.backend = backend or GitBackend(self.root, config.get("remote", "origin"), config.get("branch", "main"))
        self.patterns = self.manifest["managed"]
        limits = self.manifest.get("limits", {})
        self.suffixes = tuple(limits.get("allowed_suffixes", [".md", ".json"]))
        self.max_bytes = int(limits.get("max_file_bytes", 1048576))
        git_dir = Path(self.backend.git("rev-parse", "--absolute-git-dir").stdout.strip())
        self.git_dir = git_dir
        self.state_dir = Path(state_dir) if state_dir else git_dir / "ai-hub"

    # ---- working-tree inspection -------------------------------------------------

    def _status(self):
        out = self.backend.git("status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
        entries, items, index = [], out.split("\0"), 0
        while index < len(items):
            item = items[index]
            index += 1
            if not item:
                continue
            code, path = item[:2], item[3:]
            if code[0] in "RC":
                index += 1  # skip the rename source
            entries.append((code, path))
        return entries

    def pending_changes(self):
        managed, other = [], []
        for code, path in self._status():
            (managed if is_managed(path, self.patterns) else other).append((code, path))
        return managed, other

    # ---- guards ------------------------------------------------------------------

    def _preflight(self):
        branch = self.backend.git("symbolic-ref", "--quiet", "--short", "HEAD", check=False).stdout.strip()
        if branch != self.backend.branch:
            raise SyncBlocked(BLOCKED_UNSAFE, "checkout is on %r, not the continuity branch %r"
                              % (branch or "detached HEAD", self.backend.branch))
        for marker in ("MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD"):
            if (self.git_dir / marker).exists():
                raise SyncBlocked(BLOCKED_UNSAFE, "a git %s is in progress" % marker)

    def _guard_identity(self):
        """Commit Identity Guard: allowlist check before any commit, merge commit or push.

        The same validator guards the manual checkpoint path (githooks/); the sync refuses
        to run at all while that path is unguarded, so neither path can leak an identity.
        """
        installed, detail = identity_guard.manual_guard_installed(self.root)
        if not installed:
            raise SyncBlocked(BLOCKED_IDENTITY, "manual-commit identity guard is not installed "
                              "(run: python3 tools/identity_guard.py install)", **detail)
        try:
            return identity_guard.check_effective(self.root, env=self.backend.env())
        except identity_guard.IdentityBlocked as blocked:
            raise SyncBlocked(BLOCKED_IDENTITY, blocked.reason, problems=blocked.problems)

    def _guard_outgoing(self, approved):
        outgoing = identity_guard.outgoing_commits(self.root, "HEAD", self.backend.remote)
        try:
            identity_guard.check_commits(self.root, outgoing, approved)
        except identity_guard.IdentityBlocked as blocked:
            raise SyncBlocked(BLOCKED_IDENTITY, blocked.reason, problems=blocked.problems)

    def _guard_files(self, managed):
        findings = []
        for code, path in managed:
            if "D" in code:
                raise SyncBlocked(BLOCKED_UNSAFE, "deleting an authoritative doc is never auto-synced", path=path)
            full = self.root / path
            if not path.endswith(self.suffixes):
                raise SyncBlocked(BLOCKED_UNSAFE, "file type not allowed in the continuity package", path=path)
            if full.stat().st_size > self.max_bytes:
                raise SyncBlocked(BLOCKED_UNSAFE, "file exceeds the package size limit", path=path)
            try:
                text = full.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                raise SyncBlocked(BLOCKED_UNSAFE, "not UTF-8 text", path=path)
            if code == "??":
                added = list(enumerate(text.splitlines(), 1))
            else:
                added = self._added_lines(["HEAD", "--", path])
            findings += [{"path": path, "line": n, "rule": rule} for n, rule in scan_text(added)]
        return findings

    def _added_lines(self, diff_args):
        out = self.backend.git("diff", "--no-color", "--no-ext-diff", "-U0", *diff_args).stdout
        lines, number = [], 0
        for line in out.splitlines():
            if line.startswith("@@"):
                match = re.search(r"\+(\d+)", line)
                number = int(match.group(1)) if match else 0
            elif line.startswith("+") and not line.startswith("+++"):
                lines.append((number, line[1:]))
                number += 1
        return lines

    def _changed(self, a, b):
        out = self.backend.git("diff", "--name-only", "-z", a, b).stdout
        return {p for p in out.split("\0") if p}

    # ---- remote integration --------------------------------------------------------

    def _integrate_remote(self, managed, other):
        remote = self.backend.tracking
        head = self.backend.git("rev-parse", "HEAD").stdout.strip()
        tip = self.backend.git("rev-parse", remote).stdout.strip()
        if head == tip or self._is_ancestor(tip, head):
            local_only = self._changed(tip, head) if head != tip else set()
            self._guard_unpushed(local_only, tip, head)
            return "remote_not_ahead"
        base = self.backend.git("merge-base", head, tip).stdout.strip()
        remote_changed = self._changed(base, tip)
        local_commits = self._changed(base, head) if base != head else set()
        dirty_managed = {p for _, p in managed}
        dirty_other = {p for _, p in other}
        overlap = sorted(remote_changed & (dirty_managed | local_commits))
        if overlap:
            raise SyncBlocked(SYNC_CONFLICT, "Local and Remote both changed the same authoritative state",
                              files=overlap, remote=tip[:12], local=head[:12])
        if remote_changed & dirty_other:
            raise SyncBlocked(BLOCKED_UNSAFE, "Remote changed files that have local uncommitted work",
                              files=sorted(remote_changed & dirty_other))
        self._guard_unpushed(local_commits, base, head)
        if base == head:
            self.backend.git("merge", "--ff-only", "--quiet", tip)
            return "fast_forwarded"
        merged = self.backend.git("merge-tree", "--write-tree", head, tip, check=False)
        if merged.returncode != 0:
            raise SyncBlocked(SYNC_CONFLICT, "Local and Remote histories do not merge cleanly",
                              remote=tip[:12], local=head[:12])
        tree = merged.stdout.split()[0]
        commit = self.backend.git("commit-tree", tree, "-p", head, "-p", tip, "-m",
                                  "continuity: merge Remote Continuity Source (disjoint changes)").stdout.strip()
        self.backend.git("merge", "--ff-only", "--quiet", commit)
        return "merged_disjoint"

    def _is_ancestor(self, a, b):
        return self.backend.git("merge-base", "--is-ancestor", a, b, check=False).returncode == 0

    def _guard_unpushed(self, paths, base, head):
        if base == head or not paths:
            return
        outside = sorted(p for p in paths if not is_managed(p, self.patterns))
        if outside:
            raise SyncBlocked(BLOCKED_UNSAFE, "unpushed local commits include non-continuity files; "
                              "push them under the project's own authorization", files=outside[:20])
        findings = scan_text(self._added_lines([base, head, "--"] + sorted(paths)))
        if findings:
            raise SyncBlocked(BLOCKED_SECRET, "unpushed local commits contain secret-like or private-path content",
                              findings=[{"line": n, "rule": r} for n, r in findings])

    # ---- main transition -----------------------------------------------------------

    def run(self, trigger="manual", quiet_seconds=0, max_wait_seconds=0):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        lock = open(self.state_dir / "remote-sync.lock", "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return self._record(ALREADY_RUNNING, trigger, "another sync is running", write=False)
        try:
            return self._run_locked(trigger, quiet_seconds, max_wait_seconds)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()

    def _run_locked(self, trigger, quiet_seconds, max_wait_seconds):
        evidence = {}
        try:
            self._preflight()
            approved = self._guard_identity()
            managed, other = self.pending_changes()
            if managed and quiet_seconds:
                managed, other = self._wait_quiet(managed, quiet_seconds, max_wait_seconds)
                if managed is None:
                    return self._record(PENDING, trigger, "authoritative docs still being edited; will retry")
            findings = self._guard_files(managed)
            if findings:
                raise SyncBlocked(BLOCKED_SECRET, "secret-like or private-path content in new authoritative text",
                                  findings=findings)
            self.backend.fetch()
            evidence["integration"] = self._integrate_remote(managed, other)
            if managed:
                paths = sorted(p for _, p in managed)
                self.backend.git("add", "--", *paths)
                message = "continuity: sync authoritative state (%d file%s)\n\n%s\n\nContinuity-Sync: v0.1\nTrigger: %s\n" % (
                    len(paths), "" if len(paths) == 1 else "s", "\n".join("- " + p for p in paths), trigger)
                self.backend.git("commit", "--quiet", "--only", "-m", message, "--", *paths)
                evidence["files"] = paths
            head = self.backend.git("rev-parse", "HEAD").stdout.strip()
            tip = self.backend.git("rev-parse", self.backend.tracking).stdout.strip()
            if head != tip:
                self._guard_outgoing(approved)
                if self.backend.push() == "rejected":
                    self.backend.fetch()
                    evidence["integration_retry"] = self._integrate_remote([], other)
                    self._guard_outgoing(approved)
                    if self.backend.push() == "rejected":
                        raise SyncBlocked(FAILED_RETRYABLE, "Remote kept moving; push rejected twice")
                head = self.backend.git("rev-parse", "HEAD").stdout.strip()
            remote_head = self.backend.remote_head()
            evidence.update(local_head=head, remote_head=remote_head)
            if remote_head != head:
                raise SyncBlocked(FAILED_RETRYABLE, "Remote does not show the local head after push", **evidence)
            state = SYNCED if evidence.get("files") or evidence["integration"] != "remote_not_ahead" or head != tip else UP_TO_DATE
            return self._record(state, trigger, "Remote Continuity Source equals local authoritative state", **evidence)
        except SyncBlocked as blocked:
            evidence.update(blocked.evidence)
            return self._record(blocked.state, trigger, blocked.reason, **evidence)
        except GitError as error:
            return self._record(FAILED_RETRYABLE, trigger, str(error), **evidence)

    def _wait_quiet(self, managed, quiet_seconds, max_wait_seconds):
        deadline = time.time() + max_wait_seconds
        while True:
            newest = max((self.root / p).stat().st_mtime for c, p in managed if "D" not in c)
            idle = time.time() - newest
            if idle >= quiet_seconds:
                return self.pending_changes()
            if time.time() + (quiet_seconds - idle) > deadline:
                return None, None
            time.sleep(quiet_seconds - idle + 0.5)
            managed, _ = self.pending_changes()
            if not managed:
                return self.pending_changes()

    # ---- status ------------------------------------------------------------------

    def _record(self, state, trigger, reason, write=True, **evidence):
        result = {"state": state, "synced": state in (SYNCED, UP_TO_DATE), "reason": reason,
                  "trigger": trigger, "at": _now(), "evidence": evidence}
        if state in BLOCKED_STATES:
            result["recovery"] = "resolve the cause, then run: tools/bin/sync run"
        elif state in (FAILED_RETRYABLE, PENDING):
            result["recovery"] = "local state kept; next trigger or retry interval re-runs the sync"
        if write:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.state_dir / "remote-sync-status.json.tmp"
            tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, self.state_dir / "remote-sync-status.json")
            with open(self.state_dir / "remote-sync.log.jsonl", "a", encoding="utf-8") as log:
                log.write(json.dumps(result, ensure_ascii=False) + "\n")
        return result

    def status(self):
        path = self.state_dir / "remote-sync-status.json"
        last = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        managed, _ = self.pending_changes()
        ahead = self.backend.git("rev-list", "--count", "%s..HEAD" % self.backend.tracking, check=False).stdout.strip()
        return {"last_run": last, "unsynced_managed_files": sorted(p for _, p in managed),
                "local_commits_not_on_remote": int(ahead or 0),
                "note": "no network check; last_run.synced is the last verified result"}

    # ---- automatic trigger (macOS launchd) ---------------------------------------

    def watch_paths(self):
        # Files only: a watched directory (e.g. the repo root, which holds .git) fires on
        # every git operation and makes the sync re-trigger itself. New package files
        # are picked up by the StartInterval retry until install-watch is re-run.
        paths = set()
        for pattern in self.patterns:
            paths.update(str(match) for match in self.root.glob(pattern) if match.is_file())
        return sorted(paths)


def label_for(root):
    name = re.sub(r"[^a-z0-9-]+", "-", Path(root).name.lower()).strip("-") or "project"
    return "io.github.ai-relayteam.sync.%s" % name


def launch_agent_path(root):
    return Path.home() / "Library" / "LaunchAgents" / (label_for(root) + ".plist")


def install_watch(sync):
    import plistlib
    try:
        sync._guard_identity()
    except SyncBlocked as blocked:
        return {"installed": False, "state": blocked.state, "reason": blocked.reason, **blocked.evidence}
    trigger = sync.manifest.get("trigger", {})
    program = str(Path(__file__).resolve().parent / "bin" / "sync")
    plist = {
        "Label": label_for(sync.root),
        "ProgramArguments": [program, "--root", str(sync.root), "run", "--trigger", "watch", "--wait-quiet"],
        "WatchPaths": sync.watch_paths(),
        "StartInterval": int(trigger.get("retry_interval_seconds", 600)),
        "ThrottleInterval": 20,
        "RunAtLoad": True,
        "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin:"
                                         + str(Path.home() / ".local" / "bin")},
        "StandardOutPath": str(sync.state_dir / "launchd.log"),
        "StandardErrorPath": str(sync.state_dir / "launchd.log"),
    }
    sync.state_dir.mkdir(parents=True, exist_ok=True)
    target = launch_agent_path(sync.root)
    target.parent.mkdir(parents=True, exist_ok=True)
    domain = "gui/%d" % os.getuid()
    subprocess.run(["launchctl", "bootout", "%s/%s" % (domain, label_for(sync.root))], capture_output=True)
    with open(target, "wb") as handle:
        plistlib.dump(plist, handle)
    proc = subprocess.run(["launchctl", "bootstrap", domain, str(target)], capture_output=True, text=True)
    return {"installed": proc.returncode == 0, "plist": str(target), "watch_paths": len(plist["WatchPaths"]),
            "detail": _tail(proc.stderr)}


def uninstall_watch(sync):
    target = launch_agent_path(sync.root)
    subprocess.run(["launchctl", "bootout", "gui/%d/%s" % (os.getuid(), label_for(sync.root))], capture_output=True)
    existed = target.exists()
    if existed:
        target.unlink()
    return {"uninstalled": existed, "plist": str(target)}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sync", description="Remote Progress Sync v0.1")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="sync the Remote Continuity Package now")
    run.add_argument("--trigger", default="manual")
    run.add_argument("--wait-quiet", action="store_true", help="wait until package files stop changing")
    sub.add_parser("status", help="show the last sync result and unsynced package files")
    sub.add_parser("install-watch", help="install the automatic macOS launchd trigger")
    sub.add_parser("uninstall-watch", help="remove the automatic trigger")
    args = parser.parse_args(argv)
    sync = RemoteProgressSync(args.root)
    if args.command == "run":
        trigger = sync.manifest.get("trigger", {})
        quiet = int(trigger.get("quiet_seconds", 45)) if args.wait_quiet else 0
        wait = int(trigger.get("max_wait_seconds", 900)) if args.wait_quiet else 0
        result = sync.run(args.trigger, quiet, wait)
    elif args.command == "status":
        result = sync.status()
    elif args.command == "install-watch":
        result = install_watch(sync)
    else:
        result = uninstall_watch(sync)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command == "run" and result["state"] in BLOCKED_STATES + (FAILED_RETRYABLE,):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
