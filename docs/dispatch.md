# 派活与后台调用

负责人先看 `git status`，用首行 `【负责人派活】` 的任务写清目标、目录、权限和成功标准。执行者回报文件与证据。负责人再看 `git status`，逐项核对并写 `DISPATCH-LOG.md`。

| 执行者 | 非交互调用 | 状态 |
| --- | --- | --- |
| Codex CLI | `codex exec -C <dir> --sandbox read-only "<任务>"` | 已实测 |
| Claude Code | `claude -p "<任务>"` | 据官方文档，未实测 |
| CodeBuddy / WorkBuddy | `codebuddy -p "<任务>"` | 据官方文档，未实测 |
| 其他 | 查对应 CLI 文档 | 未实测 |

命令格式可能随版本变化，以各自官方文档和本机 `--help` 为准。上表不是调用成功或权限边界的保证；先做只读试跑。调用可能消耗额度或产生费用，先遵守项目规则。
