# 更新记录（CHANGELOG）

写给 AI 和用户看：每一版改了什么，用大白话。版本号与根目录 `VERSION` 一致。AI 发现新版时，会把这里的说明转述给用户，用户同意后按 [UPGRADE.md](UPGRADE.md) 升级。

## 2026.10.14

- **新增：AI 自动写回进度。** 每做完一步、用户做了决定、要结束对话或额度快用完时，AI 自己把进度写进 HANDOFF.md / STATUS.md，不用用户提醒。
- **新增：接手先查漏。** 新接手的 AI 先对比提交记录和交接本，发现上一个 AI 没来得及记下的改动，先告诉用户并补记。
- **新增：规则自动更新。** AI 每天最多查一次模板有没有新版本；有就告诉用户改了什么，用户同意后只替换「规则区」，用户自己的配置和偏好不动。规则升级后，其他开着的窗口在下一次写回进度时会自动重新读规则。
- **调整：** `AGENTS.md` 加了版本号和「规则区」标记；「用户偏好」挪到规则区上方。

---

# Changelog (English)

## 2026.10.14

- **New: the AI writes progress back automatically** after every step, every user decision, before ending a session, or when the quota runs low; no reminder needed.
- **New: gap check on takeover.** The next AI compares the commit history with the handoff notebook and records anything the previous AI left out.
- **New: automatic rule updates.** At most once a day the AI checks for a newer template version, tells the user what changed, and on approval replaces only the rules section; the user's own setup and preferences stay untouched. Other open windows re-read the rules the next time they write progress back.
- **Changed:** `AGENTS.md` now carries a version number and rules-section markers; "User preferences" moved above the rules section.
