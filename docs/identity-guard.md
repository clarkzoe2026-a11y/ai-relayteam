# 防泄露守门员（可选）

先把本仓库的 `tools/` 复制到你的项目根目录。然后在项目根目录创建 `.ai-hub/commit-identity.json`，可从 `tools/examples/commit-identity.example.json` 复制后填入你批准的 Git 作者名和邮箱。不要直接使用示例值。运行 `python3 tools/identity_guard.py install`，它只改当前仓库的 Git 配置：安装 `tools/githooks`、开启 `user.useConfigOnly`，并设置批准的身份。用 `python3 tools/identity_guard.py check` 查看状态；通过时 `manual_guard_installed` 为 true。

守卫在提交前核对当前作者与提交者，在推送前核对待推送提交和带注释标签的身份；不回显被拒绝的身份。它不能检查所有敏感内容，也不能阻止主动绕过钩子。请自己审阅待公开文件。

卸载：在项目里运行 `git config --local --unset core.hooksPath`；若不再需要，运行 `git config --local --unset user.useConfigOnly`。这不会删除白名单或恢复旧身份；按需手动处理当前仓库配置。若还在使用同步工具，卸载守卫会使同步进入 `BLOCKED_IDENTITY`。
