# Choosing a mode

| Mode | When to use it | What to put under "Current setup" |
| --- | --- | --- |
| One AI | Getting started or using only one AI | Set mode to One AI, lead to the current AI, and workers to none |
| One lead + one worker | Give another AI a bounded task | Name both AIs and the directories and permissions the worker has; the lead checks the result |
| Several workers | Independent tasks can run in parallel | List each AI, directory, permissions, and file ownership; give each file only one writer |

## Tested combination

| Lead → worker | Status |
| --- | --- |
| Claude Code → Codex CLI `codex exec` | Tested |
| Other combinations | Not tested |

"Tested" only means the reference materials recorded this combination. Check your own versions, sign-in state, and environment.
