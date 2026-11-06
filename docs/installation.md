# 安装与维护

## 安装

最简单的方式见 [README](../README.md)。需要自定义目录或指定游戏时：

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/dy0000/pvz-scared-ai-bridge/main/bootstrap.ps1))) -InstallDir "D:\AI-Games\pvz-scared-ai-bridge" -GamePath "D:\Games\PVZ-Scared" -NonInteractive
```

已下载源码时，在项目目录运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -NonInteractive
```

| 可选参数 | 用途 |
| --- | --- |
| `-GamePath` | 游戏目录或 EXE；省略时复用已有路径、查找项目 game 目录或已运行的游戏。找不到也能安装 |
| `-Client Auto` | 默认，检测到 Codex CLI 就自动注册，否则生成通用 MCP 配置 |
| `-Client Generic` | 只生成配置，不注册 Codex |
| `-PythonPath` | 指定已有的 Python 3.12 x64；只用于本地 install.ps1 |
| `-InstallDir` | 自定义项目安装目录；只用于 bootstrap.ps1 |
| `-NonInteractive` | 兼容 AI 自动安装调用；默认流程也不询问游戏路径 |

找不到 Python 时通过 winget 为当前用户安装。没有 winget 则手动安装 [Python 3.12 x64](https://www.python.org/downloads/windows/) 后重试。玩家不需要 Git、Node.js 或编译器。

## 启动与 MCP

先打开一个恐怖版游戏，再运行 `start.cmd`，启动器会自动发现并关联它。也可以显式指定：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\launch.ps1 -GamePath "D:\Games\PVZ-Scared"
# 多开游戏时必须选定一个实际 PID。
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\launch.ps1 -PidToAttach 12345
```

安装器生成 `generated/mcp.json`、`generated/codex.toml` 和 `generated/START_HERE.txt`。通用客户端添加本地 stdio 服务时，命令和参数取 generated 中的实际绝对路径。Codex 注册格式依据 [OpenAI MCP 文档](https://learn.chatgpt.com/docs/extend/mcp)。

安装只检查已提供的游戏目录是否完整，不比较版本哈希。原生连接仍使用已适配的地址表并核对兼容性；允许安装新版不代表保证新版游戏可玩。

## 更新与卸载

先让 AI `release_control`。停止宿主可在项目根目录创建 `runtime/stop.request`，待其正常退出后覆盖新版本源码、重新运行安装器。保留 runtime 中的购买收据，避免未知扣款被重复提交。下载入口发现已有安装时只复用，不会自动覆盖运行中的源码。

卸载时先交还并停止宿主，再移除 MCP 服务 `pvz_scared`，最后删除项目目录。Codex CLI 可用 `codex mcp remove pvz_scared`。游戏与存档不会被自动删除。

## 常见问题

| 问题 | 处理 |
| --- | --- |
| AI 看不到工具 | 重新加载客户端；检查 generated 配置是否合并成功，工具前缀是 pvzh_ |
| 找不到游戏 | 先打开游戏再启动；或通过 -GamePath 指定完整解压目录 |
| 下载失败 | 检查 GitHub、Python/PyPI 网络，按自己的网络环境设置代理或镜像 |
| `Unsupported game file` | 安装已完成，但当前原生地址表尚不兼容该构建，需适配后才能游玩 |
| 端口占用/控制冲突 | 沿用原控制器，先正常交还，不同时运行第二个宿主 |
| `release_blocked` | 等待恢复或正常关闭游戏，不强杀宿主、不清锁 |
| 动作超时 | 观察现场，不自动重放；购买先查收据 |

`doctor.cmd` 只检查本地环境和 MCP 定义，不接管游戏。反馈错误时不要公开 runtime/connection.json 或 token。
