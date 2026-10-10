"""Commit Identity Guard — allowlist validation for every commit and push path.

Git silently falls back to the
OS account's full name and a hostname-derived email when no identity is configured;
a content-only scan cannot see that. This guard is an allowlist, not a denylist:
author and committer name and email must exactly equal the approved identity in
``.ai-hub/commit-identity.json``, otherwise the result is BLOCKED_IDENTITY.

It is the single validator shared by:
* Remote Progress Sync (before its commits, merge commits, and pushes), and
* the manual checkpoint workflow, via ``tools/githooks/pre-commit`` and ``tools/githooks/pre-push``
  (installed through repo-local ``core.hooksPath``; never the global config).

Reports never echo the rejected values — only which field failed and why.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BLOCKED_IDENTITY = "BLOCKED_IDENTITY"
IDENTITY_FILE = ".ai-hub/commit-identity.json"
CODE_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = CODE_ROOT / "tools" / "githooks"
FIELDS = ("author", "committer")
_IDENT = re.compile(r"^(?P<name>.*) <(?P<email>[^<>]*)> \d+ [+-]\d{4}$")


class IdentityBlocked(Exception):
    def __init__(self, reason, problems=None):
        super().__init__(reason)
        self.state = BLOCKED_IDENTITY
        self.reason = reason
        self.problems = problems or []


def _git(root, *args, env=None):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          env=env if env is not None else os.environ.copy())


def repo_root(cwd="."):
    proc = _git(cwd, "rev-parse", "--show-toplevel")
    return Path(proc.stdout.strip()) if proc.returncode == 0 else Path(cwd).resolve()


def load_approved(root=None):
    """Approved identity from the target repository only."""
    for base in ([Path(root)] if root else []):
        path = base / IDENTITY_FILE
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return {"name": data.get("name") or None, "email": data.get("email") or None, "source": str(path)}
    return {"name": None, "email": None, "source": None}


def _hint(value):
    """Category of a rejected value, for diagnostics only (never the value itself)."""
    if not value:
        return "empty"
    if "@" in value:
        domain = value.rsplit("@", 1)[1].lower()
        if domain.endswith(".local") or "." not in domain:
            return "hostname-derived email"
        return "email not on allowlist"
    return "name not on allowlist"


def check_values(name, email, approved, field):
    problems = []
    if not approved.get("name") or not approved.get("email"):
        problems.append({"field": field, "reason": "no approved identity configured (allowlist email is unset)"})
        return problems
    if name != approved["name"]:
        problems.append({"field": field + ".name", "reason": _hint(name) if name else "empty"})
    if email != approved["email"]:
        problems.append({"field": field + ".email", "reason": _hint(email)})
    return problems


def effective_identity(root, env=None):
    """What `git commit` would record right now (config, env overrides, fallback)."""
    result = {}
    for field, var in (("author", "GIT_AUTHOR_IDENT"), ("committer", "GIT_COMMITTER_IDENT")):
        proc = _git(root, "var", var, env=env)
        match = _IDENT.match(proc.stdout.strip()) if proc.returncode == 0 else None
        result[field] = (match.group("name"), match.group("email")) if match else (None, None)
    return result


def check_effective(root, env=None, approved=None):
    approved = approved or load_approved(root)
    problems = []
    for field, (name, email) in effective_identity(root, env).items():
        if name is None:
            problems.append({"field": field, "reason": "git cannot resolve an identity (missing / useConfigOnly)"})
        else:
            problems += check_values(name, email, approved, field)
    if problems:
        raise IdentityBlocked("effective git identity is not the approved identity", problems)
    return approved


def check_commits(root, revs, approved=None):
    """Validate raw author/committer metadata of commits (e.g. everything about to be pushed)."""
    approved = approved or load_approved(root)
    problems = []
    for rev in revs:
        proc = _git(root, "log", "-1", "--format=%an%x00%ae%x00%cn%x00%ce", rev)
        an, ae, cn, ce = (proc.stdout.rstrip("\n").split("\0") + ["", "", "", ""])[:4]
        for field, name, email in (("author", an, ae), ("committer", cn, ce)):
            for p in check_values(name, email, approved, field):
                problems.append(dict(p, commit=rev[:12]))
    if problems:
        raise IdentityBlocked("outgoing commits carry a non-approved identity", problems)
    return approved


def check_tag(root, ref, approved=None):
    approved = approved or load_approved(root)
    proc = _git(root, "cat-file", "-p", ref)
    for line in proc.stdout.splitlines():
        if line.startswith("tagger "):
            match = _IDENT.match(line[len("tagger "):])
            name, email = (match.group("name"), match.group("email")) if match else (None, None)
            problems = check_values(name, email, approved, "tagger")
            if problems:
                raise IdentityBlocked("annotated tag carries a non-approved tagger identity", problems)
    return approved


def outgoing_commits(root, local_sha, remote_name):
    proc = _git(root, "rev-list", local_sha, "--not", "--remotes=%s" % remote_name)
    return [line for line in proc.stdout.split() if line]


def manual_guard_installed(root):
    """The manual path is guarded only if hooks + useConfigOnly are active in repo-local config."""
    hooks = _git(root, "config", "--get", "core.hooksPath").stdout.strip()
    strict = _git(root, "config", "--get", "user.useConfigOnly").stdout.strip().lower()
    ok_hooks = bool(hooks) and Path(hooks).resolve() == HOOKS_DIR.resolve()
    return ok_hooks and strict == "true", {"hooks_path_ok": ok_hooks, "use_config_only": strict == "true"}


def install(root):
    """Repo-local only: hooks path, useConfigOnly, and the approved identity if one is set."""
    approved = load_approved(root)
    for key, value in (("core.hooksPath", str(HOOKS_DIR)), ("user.useConfigOnly", "true")):
        _git(root, "config", "--local", key, value)
    if approved["name"]:
        _git(root, "config", "--local", "user.name", approved["name"])
    if approved["email"]:
        _git(root, "config", "--local", "user.email", approved["email"])
    return {"installed": True, "approved_email_set": bool(approved["email"])}


# ---- hook / CLI entry points -------------------------------------------------------

def _report(blocked):
    print("%s: %s" % (blocked.state, blocked.reason), file=sys.stderr)
    for p in blocked.problems:
        print("  - %s%s: %s" % (p.get("commit", "") + " " if p.get("commit") else "", p["field"], p["reason"]),
              file=sys.stderr)
    print("  NO COMMIT / NO PUSH. Fix the repo-local identity; see .ai-hub/commit-identity.json.", file=sys.stderr)


def hook_pre_commit():
    try:
        check_effective(repo_root())
    except IdentityBlocked as blocked:
        _report(blocked)
        return 1
    return 0


def hook_pre_push(remote_name, stdin):
    root = repo_root()
    try:
        approved = load_approved(root)
        check_effective(root, approved=approved)
        for line in stdin:
            parts = line.split()
            if len(parts) != 4 or set(parts[1]) == {"0"}:
                continue
            local_ref, local_sha = parts[0], parts[1]
            if local_ref.startswith("refs/tags/") and _git(root, "cat-file", "-t", local_sha).stdout.strip() == "tag":
                check_tag(root, local_sha, approved)
            check_commits(root, outgoing_commits(root, local_sha, remote_name), approved)
    except IdentityBlocked as blocked:
        _report(blocked)
        return 1
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv[0] if argv else "check"
    if command == "pre-commit":
        return hook_pre_commit()
    if command == "pre-push":
        return hook_pre_push(argv[1] if len(argv) > 1 else "origin", sys.stdin)
    root = repo_root()
    if command == "install":
        print(json.dumps(install(root), indent=2))
        return 0
    if command == "check":
        installed, detail = manual_guard_installed(root)
        try:
            check_effective(root)
            print(json.dumps({"state": "PASS", "approved_identity_configured": True, "manual_guard_installed": installed, **detail}, indent=2))
            return 0 if installed else 1
        except IdentityBlocked as blocked:
            _report(blocked)
            print(json.dumps({"state": BLOCKED_IDENTITY, "manual_guard_installed": installed, **detail}, indent=2))
            return 1
    print("usage: identity_guard.py [check|install|pre-commit|pre-push <remote>]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
