"""Commit Identity Guard acceptance (Privacy Regression Phase 2 — future leak prevention).

Every case runs in an isolated temporary repo with global / system git config disabled,
so nothing here reads or writes the real repository or the user's global identity.

SAFE   Approved identity -> PASS (raw author/committer metadata verified)
FAIL   missing identity · macOS fallback · real-name identity · hostname-derived email ·
       unknown name · unknown email · unsafe GIT_AUTHOR_* · unsafe GIT_COMMITTER_* ·
       allowlist email unset · manual checkpoint (pre-commit) · push path (pre-push) ·
       annotated tag tagger · automatic sync · sync with manual guard not installed ·
       install-watch refusal. Reports never echo rejected values.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import identity_guard
from tools.identity_guard import IdentityBlocked
from tools.remote_sync import BLOCKED_IDENTITY, RemoteProgressSync, install_watch

APPROVED = {"version": 1, "name": "Example Contributor", "email": "you@example.com"}
GUARD = str(ROOT / "tools" / "identity_guard.py")


def isolated_env(home, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(HOME=str(home), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, LC_ALL="C")
    env.update(extra)
    return env


class IdentityGuardCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(dir=ROOT))
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = isolated_env(self.home)
        self.remote = self.tmp / "remote.git"
        self.git(self.tmp, "init", "--quiet", "--bare", "-b", "main", str(self.remote))
        self.repo = self.tmp / "repo"
        self.git(self.tmp, "clone", "--quiet", str(self.remote), str(self.repo))
        (self.repo / ".ai-hub" ).mkdir()
        shutil.copy(ROOT / "tools" / "examples" / "remote-continuity.example.json", self.repo / ".ai-hub" / "remote-continuity.json")
        (self.repo / ".ai-hub" / "commit-identity.json").write_text(json.dumps(APPROVED))
        (self.repo / "AGENTS.md").write_text("# Hub\n")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    # helpers ---------------------------------------------------------------------

    def git(self, cwd, *args, env=None, check=True):
        proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env or self.env)
        if check and proc.returncode != 0:
            raise AssertionError("git %s failed: %s" % (args[0], proc.stderr))
        return proc

    def configure(self, name=APPROVED["name"], email=APPROVED["email"], guard=True):
        if name is not None:
            self.git(self.repo, "config", "user.name", name)
        if email is not None:
            self.git(self.repo, "config", "user.email", email)
        if guard:
            self.git(self.repo, "config", "core.hooksPath", str(identity_guard.HOOKS_DIR))
            self.git(self.repo, "config", "user.useConfigOnly", "true")

    def effective(self, env=None):
        return identity_guard.check_effective(self.repo, env=env or self.env)

    def assert_blocked(self, env=None):
        with self.assertRaises(IdentityBlocked) as ctx:
            self.effective(env)
        return ctx.exception

    def commit(self, *extra, env=None):
        self.git(self.repo, "add", "-A", env=env)
        return self.git(self.repo, "commit", "--quiet", "-m", "checkpoint", *extra, env=env, check=False)

    def raw(self, rev="HEAD"):
        out = self.git(self.repo, "cat-file", "-p", rev).stdout
        return {line.split(" ", 1)[0]: line.split(" ", 1)[1] for line in out.splitlines()
                if line.startswith(("author ", "committer "))}

    def head(self):
        return self.git(self.repo, "rev-parse", "--verify", "--quiet", "HEAD", check=False).stdout.strip()

    # SAFE ------------------------------------------------------------------------

    def test_safe_identity_passes_and_raw_metadata_is_exact(self):
        self.configure()
        self.effective()
        proc = self.commit()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        raw = self.raw()
        for field in ("author", "committer"):
            self.assertTrue(raw[field].startswith("Example Contributor <%s> " % APPROVED["email"]), field)
        metadata = " ".join(raw.values())
        self.assertNotIn(".local>", metadata)
        push = self.git(self.repo, "push", "--quiet", "origin", "main", check=False)
        self.assertEqual(push.returncode, 0, push.stderr)

    # FAIL: effective identity ------------------------------------------------------

    def test_missing_repo_identity_blocked(self):
        self.configure(name=None, email=None)
        blocked = self.assert_blocked()
        self.assertIn("cannot resolve", blocked.problems[0]["reason"])
        proc = self.commit("--no-verify")
        self.assertNotEqual(proc.returncode, 0, "useConfigOnly must stop git itself, even with --no-verify")

    def test_macos_fallback_identity_blocked(self):
        # Unguarded repo, no identity anywhere: git falls back to the OS account + hostname email.
        self.configure(name=None, email=None, guard=False)
        fallback = self.git(self.repo, "var", "GIT_AUTHOR_IDENT", check=False)
        if fallback.returncode != 0:
            self.skipTest("this git build does not fall back to an OS identity")
        blocked = self.assert_blocked()
        reasons = {p["field"]: p["reason"] for p in blocked.problems}
        self.assertEqual(reasons.get("author.email"), "hostname-derived email")
        self.assertIn("author.name", reasons)

    def test_real_name_identity_blocked(self):
        self.configure(name="Other Name", email=APPROVED["email"])
        blocked = self.assert_blocked()
        self.assertEqual({p["field"] for p in blocked.problems}, {"author.name", "committer.name"})

    def test_hostname_derived_email_blocked(self):
        self.configure(email="someone@host.local")
        blocked = self.assert_blocked()
        self.assertTrue(all(p["reason"] == "hostname-derived email" for p in blocked.problems))

    def test_unknown_name_blocked(self):
        self.configure(name="Other Name")
        self.assert_blocked()

    def test_unknown_email_blocked(self):
        self.configure(email="other@example.com")
        blocked = self.assert_blocked()
        self.assertTrue(all(p["reason"] == "email not on allowlist" for p in blocked.problems))

    def test_unsafe_git_author_override_blocked(self):
        self.configure()
        env = isolated_env(self.home, GIT_AUTHOR_NAME="Other Name", GIT_AUTHOR_EMAIL="other@example.com")
        blocked = self.assert_blocked(env)
        self.assertEqual({p["field"].split(".")[0] for p in blocked.problems}, {"author"})
        proc = self.commit(env=env)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.head(), "")

    def test_unsafe_git_committer_override_blocked(self):
        self.configure()
        env = isolated_env(self.home, GIT_COMMITTER_NAME="Example Contributor", GIT_COMMITTER_EMAIL="x@host.local")
        blocked = self.assert_blocked(env)
        self.assertEqual({p["field"] for p in blocked.problems}, {"committer.email"})
        self.assertNotEqual(self.commit(env=env).returncode, 0)

    def test_unset_allowlist_email_blocks_everything(self):
        (self.repo / ".ai-hub" / "commit-identity.json").write_text(json.dumps(dict(APPROVED, email=None)))
        self.configure()
        blocked = self.assert_blocked()
        self.assertIn("no approved identity", blocked.problems[0]["reason"])

    # FAIL: manual checkpoint + push paths --------------------------------------------

    def test_manual_checkpoint_unsafe_identity_blocked_by_hook(self):
        self.configure(email="other@example.com")
        proc = self.commit()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(BLOCKED_IDENTITY, proc.stderr)
        self.assertNotIn("other@example.com", proc.stderr, "report must not echo the rejected value")
        self.assertEqual(self.head(), "")

    def test_manual_checkpoint_author_flag_blocked(self):
        self.configure()
        proc = self.commit("--author=Other Name <other@example.com>")
        self.assertNotEqual(proc.returncode, 0, "pre-commit hook must see --author")
        self.assertNotIn("Other Name", proc.stderr)

    def test_push_blocks_unsafe_commit_made_with_no_verify(self):
        self.configure()
        bypass = isolated_env(self.home, GIT_AUTHOR_NAME="Other Name", GIT_AUTHOR_EMAIL="other@example.com")
        self.assertEqual(self.commit("--no-verify", env=bypass).returncode, 0)
        push = self.git(self.repo, "push", "origin", "main", check=False)
        self.assertNotEqual(push.returncode, 0)
        self.assertIn(BLOCKED_IDENTITY, push.stderr)
        self.assertEqual(self.git(self.remote, "rev-parse", "--verify", "--quiet", "main", check=False).stdout, "")

    def test_unknown_noreply_blocked(self):
        # A syntactically valid GitHub noreply that is not the approved account (e.g. a third-party org).
        self.configure(email="other@example.com")
        blocked = self.assert_blocked()
        self.assertTrue(all(p["reason"] == "email not on allowlist" for p in blocked.problems))

    def test_pre_push_blocks_historical_unsafe_commit(self):
        # Commit made before the guard existed (unguarded fallback-style identity), pushed later.
        self.configure(name="Other Name", email="someone@host.local", guard=False)
        self.assertEqual(self.commit().returncode, 0)
        self.configure()  # now install the guard with the approved identity
        push = self.git(self.repo, "push", "origin", "main", check=False)
        self.assertNotEqual(push.returncode, 0)
        self.assertIn(BLOCKED_IDENTITY, push.stderr)
        self.assertNotIn("someone@host.local", push.stderr)
        self.assertNotIn("Other Name", push.stderr)
        self.assertEqual(self.git(self.remote, "rev-parse", "--verify", "--quiet", "main", check=False).stdout, "")

    def test_push_blocks_annotated_tag_with_unsafe_tagger(self):
        self.configure()
        self.assertEqual(self.commit().returncode, 0)
        self.git(self.repo, "push", "--quiet", "origin", "main")
        tag_env = isolated_env(self.home, GIT_COMMITTER_NAME="Other Name", GIT_COMMITTER_EMAIL="other@example.com")
        self.git(self.repo, "tag", "-a", "backup", "-m", "backup", env=tag_env)
        push = self.git(self.repo, "push", "origin", "backup", check=False)
        self.assertNotEqual(push.returncode, 0)
        self.assertIn("tagger", push.stderr)

    # FAIL: automatic sync path ----------------------------------------------------

    def _initial_commit(self):
        self.configure()
        self.assertEqual(self.commit().returncode, 0)
        self.git(self.repo, "push", "--quiet", "origin", "main")

    def test_automatic_sync_unsafe_identity_blocked(self):
        self._initial_commit()
        remote_before = self.git(self.remote, "rev-parse", "main").stdout.strip()
        local_before = self.head()
        self.git(self.repo, "config", "user.email", "someone@host.local")
        (self.repo / "AGENTS.md").write_text("# Hub\nprogress\n")
        old = os.environ.copy()
        os.environ.clear()
        os.environ.update(self.env)
        try:
            result = RemoteProgressSync(self.repo).run("test")
        finally:
            os.environ.clear()
            os.environ.update(old)
        self.assertEqual(result["state"], BLOCKED_IDENTITY)
        self.assertFalse(result["synced"])
        self.assertEqual(self.head(), local_before, "no commit")
        self.assertEqual(self.git(self.remote, "rev-parse", "main").stdout.strip(), remote_before, "no push")
        self.assertNotIn("someone@host.local", json.dumps(result))

    def test_automatic_sync_blocked_when_manual_guard_not_installed(self):
        self._initial_commit()
        self.git(self.repo, "config", "--unset", "core.hooksPath")
        (self.repo / "AGENTS.md").write_text("# Hub\nprogress\n")
        old = os.environ.copy()
        os.environ.clear()
        os.environ.update(self.env)
        try:
            sync = RemoteProgressSync(self.repo)
            result = sync.run("test")
            refused = install_watch(sync)
        finally:
            os.environ.clear()
            os.environ.update(old)
        self.assertEqual(result["state"], BLOCKED_IDENTITY)
        self.assertFalse(refused["installed"])
        self.assertEqual(refused["state"], BLOCKED_IDENTITY)

    def test_automatic_sync_safe_identity_syncs(self):
        self._initial_commit()
        (self.repo / "AGENTS.md").write_text("# Hub\nprogress\n")
        old = os.environ.copy()
        os.environ.clear()
        os.environ.update(self.env)
        try:
            result = RemoteProgressSync(self.repo).run("test")
        finally:
            os.environ.clear()
            os.environ.update(old)
        self.assertEqual(result["state"], "SYNCED", result)
        raw = self.raw("main")
        self.assertTrue(raw["author"].startswith("Example Contributor <%s> " % APPROVED["email"]))
        self.assertTrue(raw["committer"].startswith("Example Contributor <%s> " % APPROVED["email"]))


if __name__ == "__main__":
    unittest.main()
