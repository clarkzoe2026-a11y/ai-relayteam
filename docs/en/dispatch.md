# Dispatching work and background calls

The lead checks `git status` first. A worker task starts with `[LEAD DISPATCH]` and states the goal, directory, permissions, and success criteria. The worker reports files and evidence. The lead checks `git status` again, reviews each result, and records it in `DISPATCH-LOG.md`.

| Worker | Non-interactive call | Status |
| --- | --- | --- |
| Codex CLI | `codex exec -C <dir> --sandbox read-only "<task>"` | Tested |

> If `codex` is not found: on macOS the Codex bundled with the ChatGPT desktop app is not on PATH; it is at `/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex` (found in a 2026-10-11 test where the lead could not dispatch). Once found, write it into "Current setup" in `AGENTS.md`.
| Claude Code | `claude -p "<task>"` | Per official docs; not tested |
| CodeBuddy / WorkBuddy | `codebuddy -p "<task>"` | Per official docs; not tested |
| Other | Check the corresponding CLI docs | Not tested |

Command syntax can change by version; check each tool's official docs and local `--help`. This table does not guarantee that a call will succeed or enforce a permission boundary. Try a read-only run first. Calls may use quota or cost money, so follow the project rules before making them.
