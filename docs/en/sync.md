# Automatic progress backup (optional, Mac only)

First copy this repository's `tools/` directory to your project root. At the project root, create `.ai-hub/remote-continuity.json`; you can copy `tools/examples/remote-continuity.example.json`, then check `managed`, the remote name, and the branch. The target branch must already have an initial commit and be checked out. Configure the allowlist and install the hooks using the [identity guard](identity-guard.md) first. Run these commands at the project root:

```sh
python3 tools/identity_guard.py install
python3 tools/identity_guard.py check
tools/bin/sync --root . status
tools/bin/sync --root . run
```

`run` automatically commits and pushes only files matched by the manifest; check privacy and authorization for the Git remote first. Deleted progress files, unpushed commits outside the manifest, identity mismatches, sensitive content, or concurrent changes to the same file block sync. On failure, local state is kept. `status` shows the last result and unsynced files; `status` itself does not access the network. State and logs live under the repository's `.git` directory.

On macOS only, `tools/bin/sync --root . install-watch` installs launchd monitoring and timed retries; `tools/bin/sync --root . uninstall-watch` removes it. The label comes from the project directory name, so projects with different directory names do not share a label; matching names can still collide, so check before installing. The watcher monitors only manifest files that already exist. New files may wait for a timed retry, or the watcher may need reinstalling. On other systems, you can run `run` manually; automatic monitoring has not been tested. Keep configuration and allowlists separate for each project. Do not put private identities, keys, or absolute personal paths into synced files.
