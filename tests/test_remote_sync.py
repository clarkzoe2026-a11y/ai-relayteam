"""Remote Progress Sync v0.1 acceptance — real git repos, a local bare repo as the Remote.

CASE 1  local authoritative transition -> automatic sync -> Remote has the same state
CASE 2  fresh restore from Remote -> same Goal / Progress / Decision Rationale / Next
CASE 3  remote-ahead / concurrent edit of the same doc -> SYNC_CONFLICT, nothing overwritten
CASE 4  secret / private-path fixture -> BLOCKED_SECRET, Remote unchanged, nothing committed
CASE 5  unavailable remote -> local preserved, not "synced", recoverable status; retry succeeds
CASE 6  unrelated source / binary / staged changes -> never committed or pushed by the sync
Plus: safe remote-ahead fast-forward, disjoint divergence merge, unpushed code commits blocked.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import identity_guard
from tools.remote_sync import (BLOCKED_SECRET, BLOCKED_UNSAFE, FAILED_RETRYABLE, SYNC_CONFLICT, SYNCED,
                                UP_TO_DATE, RemoteProgressSync)

# Clearly fake approved identity for isolated test repos (never a real address).
TEST_IDENTITY = {"version": 1, "name": "Example Contributor", "email": "you@example.com"}

HANDOFF = """# Project Handoff

## Decision Rationale
v1.2 = USER_CONFIRMED PUBLISHABLE BASE VIDEO -> visual gap -> Rules v1.0 frozen.

## Unique Next
RESUME VISUAL ENHANCEMENT WITH RULES v1.0
"""


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.rstrip("\n")


class RemoteSyncCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(dir=ROOT))
        self.remote = self.tmp / "remote.git"
        git(self.tmp, "init", "--quiet", "--bare", "-b", "main", str(self.remote))
        self.local = self.clone("local")
        (self.local / ".ai-hub" ).mkdir()
        shutil.copy(ROOT / "tools" / "examples" / "remote-continuity.example.json", self.local / ".ai-hub" / "remote-continuity.json")
        (self.local / ".ai-hub" / "commit-identity.json").write_text(json.dumps(TEST_IDENTITY))
        
        (self.local / "AGENTS.md").write_text("# Hub\nGoal: continuity\n")
        (self.local / "HANDOFF.md").write_text(HANDOFF)
        (self.local / "src").mkdir()
        (self.local / "src" / "app.js").write_text("console.log(1)\n")
        git(self.local, "add", "-A")
        git(self.local, "commit", "--quiet", "-m", "init")
        git(self.local, "push", "--quiet", "origin", "main")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def clone(self, name):
        path = self.tmp / name
        git(self.tmp, "clone", "--quiet", str(self.remote), str(path))
        git(path, "config", "user.email", TEST_IDENTITY["email"])
        git(path, "config", "user.name", TEST_IDENTITY["name"])
        git(path, "config", "core.hooksPath", str(identity_guard.HOOKS_DIR))
        git(path, "config", "user.useConfigOnly", "true")
        return path

    def sync(self, repo=None):
        return RemoteProgressSync(repo or self.local).run("test")

    def remote_file(self, path):
        return git(self.remote, "show", "main:" + path)

    def remote_head(self):
        return git(self.remote, "rev-parse", "main")

    def test_case1_transition_reaches_remote(self):
        handoff = self.local / "HANDOFF.md"
        handoff.write_text(HANDOFF.replace("Rules v1.0 frozen.", "Rules v1.0 frozen.\nProgress: step 2 done."))
        result = self.sync()
        self.assertEqual(result["state"], SYNCED)
        self.assertTrue(result["synced"])
        self.assertEqual(self.remote_file("HANDOFF.md"), handoff.read_text().strip())
        self.assertEqual(result["evidence"]["remote_head"], self.remote_head())
        self.assertEqual(self.sync()["state"], UP_TO_DATE)

    def test_case2_fresh_restore_has_same_rationale_and_next(self):
        (self.local / "STATUS.md").write_text("# Status\nProgress: v1.2 accepted\n")
        self.assertEqual(self.sync()["state"], SYNCED)
        fresh = self.clone("fresh-agent")
        for path in ("AGENTS.md", "STATUS.md", "HANDOFF.md"):
            self.assertEqual((fresh / path).read_bytes(), (self.local / path).read_bytes(), path)
        restored = (fresh / "HANDOFF.md").read_text()
        self.assertIn("## Decision Rationale", restored)
        self.assertIn("RESUME VISUAL ENHANCEMENT WITH RULES v1.0", restored)

    def test_case3_concurrent_edit_is_conflict_not_overwrite(self):
        other = self.clone("other-agent")
        (other / "AGENTS.md").write_text("# Hub\nGoal: changed by other agent\n")
        git(other, "commit", "--quiet", "-am", "other agent")
        git(other, "push", "--quiet", "origin", "main")
        remote_before = self.remote_head()
        (self.local / "AGENTS.md").write_text("# Hub\nGoal: changed locally\n")
        result = self.sync()
        self.assertEqual(result["state"], SYNC_CONFLICT)
        self.assertFalse(result["synced"])
        self.assertEqual(result["evidence"]["files"], ["AGENTS.md"])
        self.assertEqual(self.remote_head(), remote_before)
        self.assertIn("changed by other agent", self.remote_file("AGENTS.md"))
        self.assertIn("changed locally", (self.local / "AGENTS.md").read_text())

    def test_remote_ahead_disjoint_fast_forwards_then_syncs(self):
        other = self.clone("other-agent")
        (other / "STATUS.md").write_text("# Status\nfrom other agent\n")
        git(other, "add", "STATUS.md")
        git(other, "commit", "--quiet", "-m", "other agent")
        git(other, "push", "--quiet", "origin", "main")
        (self.local / "AGENTS.md").write_text("# Hub\nGoal: local update\n")
        result = self.sync()
        self.assertEqual(result["state"], SYNCED)
        self.assertEqual(result["evidence"]["integration"], "fast_forwarded")
        self.assertIn("from other agent", self.remote_file("STATUS.md"))
        self.assertIn("local update", self.remote_file("AGENTS.md"))

    def test_case4_secret_and_private_path_blocked(self):
        for leak in ("api_key = '" + "AbCdEfGh" + "IjKlMnOpQrSt1234'", "see /" + "Users/example/clip.txt"):
            remote_before = self.remote_head()
            local_before = git(self.local, "rev-parse", "HEAD")
            (self.local / "AGENTS.md").write_text("# Hub\nGoal: continuity\n" + leak + "\n")
            result = self.sync()
            self.assertEqual(result["state"], BLOCKED_SECRET, leak)
            self.assertFalse(result["synced"])
            self.assertNotIn(leak.split()[-1], json.dumps(result))
            self.assertEqual(self.remote_head(), remote_before)
            self.assertEqual(git(self.local, "rev-parse", "HEAD"), local_before)

    def test_case5_unavailable_remote_preserves_local_and_recovers(self):
        (self.local / "AGENTS.md").write_text("# Hub\nGoal: offline edit\n")
        moved = self.tmp / "remote-offline.git"
        self.remote.rename(moved)
        result = self.sync()
        self.assertEqual(result["state"], FAILED_RETRYABLE)
        self.assertFalse(result["synced"])
        self.assertIn("offline edit", (self.local / "AGENTS.md").read_text())
        status = json.loads((self.local / ".git" / "ai-hub" / "remote-sync-status.json").read_text())
        self.assertEqual(status["state"], FAILED_RETRYABLE)
        self.assertIn("recovery", status)
        moved.rename(self.remote)
        self.assertEqual(self.sync()["state"], SYNCED)
        self.assertIn("offline edit", self.remote_file("AGENTS.md"))

    def test_push_failure_after_local_commit_is_retried(self):
        (self.local / "AGENTS.md").write_text("# Hub\nGoal: push fails\n")
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        result = self.sync()
        self.assertEqual(result["state"], FAILED_RETRYABLE)
        self.assertEqual(RemoteProgressSync(self.local).status()["local_commits_not_on_remote"], 1)
        hook.unlink()
        self.assertEqual(self.sync()["state"], SYNCED)
        self.assertIn("push fails", self.remote_file("AGENTS.md"))

    def test_case6_unrelated_changes_never_committed(self):
        (self.local / "src" / "app.js").write_text("console.log(2)\n")
        (self.local / "video.mp4").write_bytes(b"\x00\x01binary")
        (self.local / "notes.md").write_text("scratch\n")
        (self.local / "src" / "staged.js").write_text("staged\n")
        git(self.local, "add", "src/staged.js")
        (self.local / "AGENTS.md").write_text("# Hub\nGoal: with unrelated work\n")
        result = self.sync()
        self.assertEqual(result["state"], SYNCED)
        self.assertEqual(result["evidence"]["files"], ["AGENTS.md"])
        pushed = git(self.remote, "show", "--name-only", "--format=", "main").split()
        self.assertEqual(pushed, ["AGENTS.md"])
        self.assertEqual((self.local / "src" / "app.js").read_text(), "console.log(2)\n")
        status = git(self.local, "status", "--porcelain")
        self.assertIn(" M src/app.js", status)
        self.assertIn("A  src/staged.js", status)
        self.assertIn("?? video.mp4", status)

    def test_unpushed_code_commit_blocks_sync(self):
        (self.local / "src" / "app.js").write_text("console.log(3)\n")
        git(self.local, "commit", "--quiet", "-am", "code")
        (self.local / "AGENTS.md").write_text("# Hub\nGoal: x\n")
        remote_before = self.remote_head()
        result = self.sync()
        self.assertEqual(result["state"], BLOCKED_UNSAFE)
        self.assertEqual(self.remote_head(), remote_before)

    def test_diverged_disjoint_history_merges_without_overwrite(self):
        (self.local / "AGENTS.md").write_text("# Hub\nGoal: committed locally, push failed\n")
        git(self.local, "commit", "--quiet", "-am", "local doc commit")
        other = self.clone("other-agent")
        (other / "STATUS.md").write_text("# Status\nother\n")
        git(other, "add", "STATUS.md")
        git(other, "commit", "--quiet", "-m", "other")
        git(other, "push", "--quiet", "origin", "main")
        result = self.sync()
        self.assertEqual(result["state"], SYNCED)
        self.assertEqual(result["evidence"]["integration"], "merged_disjoint")
        self.assertIn("push failed", self.remote_file("AGENTS.md"))
        self.assertIn("other", self.remote_file("STATUS.md"))

    def test_deleting_authoritative_doc_is_blocked(self):
        (self.local / "AGENTS.md").unlink()
        self.assertEqual(self.sync()["state"], BLOCKED_UNSAFE)
        self.assertIn("Goal: continuity", self.remote_file("AGENTS.md"))


if __name__ == "__main__":
    unittest.main()
