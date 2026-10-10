# Identity guard (optional)

First copy this repository's `tools/` directory to your project root. At your project root, create `.ai-hub/commit-identity.json`; you can copy `tools/examples/commit-identity.example.json` and fill in the Git author name and email you approve. Do not use the example values as your identity. Run `python3 tools/identity_guard.py install`. It changes Git configuration only in the current repository: it installs `tools/githooks`, enables `user.useConfigOnly`, and sets the approved identity. Check with `python3 tools/identity_guard.py check`; when it passes, `manual_guard_installed` is true.

The guard checks the current author and committer before a commit, and the identities in outgoing commits and annotated tags before a push. It does not echo rejected identities. It cannot inspect every kind of sensitive content or prevent someone from bypassing the hooks deliberately. Review files yourself before making them public.

To uninstall in the project, run `git config --local --unset core.hooksPath`; if no longer needed, run `git config --local --unset user.useConfigOnly`. This does not delete the allowlist or restore the old identity; adjust the current repository's settings manually as needed. If you still use the sync tool, uninstalling the guard puts sync into `BLOCKED_IDENTITY`.
