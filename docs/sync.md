# 自动备份进度（可选，仅 Mac）

先把本仓库的 `tools/` 复制到你的项目根目录。然后在项目根目录创建 `.ai-hub/remote-continuity.json`，可复制 `tools/examples/remote-continuity.example.json`，核对 `managed`、远端名和分支。目标分支须已有初始提交，且当前检出该分支。先按[身份守卫](identity-guard.md)配置白名单并安装钩子。命令均在项目根目录运行：

```sh
python3 tools/identity_guard.py install
python3 tools/identity_guard.py check
tools/bin/sync --root . status
tools/bin/sync --root . run
```

`run` 只自动提交清单匹配的文件并推送；先查隐私和 Git 远端授权。删除进度文件、清单外未推送提交、身份不符、敏感内容或同一文件的并发改动会阻止同步。失败会保留本地状态，`status` 显示上次结果和未同步文件；`status` 本身不联网。状态与日志放在仓库的 `.git` 内。

仅 macOS 可运行 `tools/bin/sync --root . install-watch` 安装 launchd 自动监视与定时重试；`tools/bin/sync --root . uninstall-watch` 卸载。标签由项目目录名生成，因此不同目录名的项目互不共用；同名目录仍可能冲突，安装前应检查。监视器只观察已存在的清单文件；新增文件可能等到定时重试，或需重装监视器。其他系统可以手动运行 `run`，自动监视未实测。配置与白名单应按项目分别维护；不要把私人身份、密钥或绝对私人路径放进同步文件。
