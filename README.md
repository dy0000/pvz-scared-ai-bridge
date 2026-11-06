<div align="center">

# PVZ 恐怖版 AI Bridge

**让你的大肥鱼，亲自去打恐怖版僵尸。**

植物大战僵尸恐怖版 · Windows 一键安装 · 32 个 MCP 工具 · 原生状态与操作

![Windows x64](https://img.shields.io/badge/Windows-x64-0078D4)
![PVZ Scared](https://img.shields.io/badge/PVZ--Scared-1.0.1-7437B8)
![Bridge](https://img.shields.io/badge/Bridge-0.2.2-2E8B57)
![License](https://img.shields.io/badge/License-MIT-blue)

[快速开始](#快速开始) · [交给大肥鱼安装](#交给大肥鱼安装) · [MCP 接入](#接入你的-ai) · [常见问题](#常见问题) · [接口文档](skills/pvz-horror-player/references/api.md)

</div>

这是 **《植物大战僵尸恐怖版》PVZ-Scared 1.0.1 的 AI 接入 Mod**。把它接到支持本机 MCP 工具的 AI 助手后，AI 就能读取战场、选卡布阵、使用手套和铲子、领奖续关。

玩家准备游戏，桥接负责提供工具，AI 负责思考怎么玩。项目使用 Frida 在运行时接入游戏，不修改磁盘上的游戏 EXE/DLL；正常种植和操作遵守原生费用、冷却与放置规则。

## 能做什么

| 能力 | 支持内容 |
| --- | --- |
| 看懂战场 | 阳光、波次、卡牌、费用/冷却、植物与僵尸血量、地形和障碍 |
| 自主操作 | 选卡、开战、种植、拾取、铲除、手套搬运、主动能力 |
| 剧情流程 | 菜单导航、章节/关卡、日记正文、失败重试、领奖续关和结局档案 |
| 特殊机制 | 传送带/掉落卡、友军、Boss 部位与攻击范围、部分特殊植物状态 |
| 原生功能 | 图鉴、游戏设置、难度、速度、暂停、商店与购买收据 |
| 玩家接管 | F8/F9 停止并锁定 AI；玩家按 F10 重新允许 |

当前范围是**剧情及其相关界面**；生存、娱乐模式尚未接入。AI 的实际水平取决于模型和策略，项目不承诺自然通关。自带的 `play_story.py` 是基础示例，不是完整通关 AI。

## 快速开始

**一行安装：**打开 PowerShell，粘贴下面这行命令；按提示输入已经解压的游戏目录即可。默认安装到 `%LOCALAPPDATA%\PVZScaredAIBridge`，不需要先装 Git。

```powershell
irm https://raw.githubusercontent.com/dy0000/pvz-scared-ai-bridge/main/bootstrap.ps1 | iex
```

更喜欢双击安装，可以按下面三步下载项目。网络无法访问 GitHub 时也可使用手动下载方式。

### 1. 准备游戏和项目

- 系统：**Windows 10/11 x64**，PowerShell 5.1 或更高版本。
- 游戏：**Windows PVZ-Scared 1.0.1** 完整解压目录，里面应有 `PVZ-Scared.exe`、`GameAssembly.dll`、`UnityPlayer.dll` 和 `PVZ-Scared_Data`。
- AI：能运行本机 **stdio MCP** 工具的客户端。桥接本身不需要模型 API Key；AI 客户端的账号、模型或 API 由你自己配置。
- 首次安装需要联网下载 Python/Frida。日常桥接只监听本机 `127.0.0.1:47633`。

从本仓库的 **[Releases](https://github.com/dy0000/pvz-scared-ai-bridge/releases)** 下载项目 ZIP 并解压，或者点 **Code → Download ZIP**。解压到准备长期保留的目录，例如 `D:\AI-Games\pvz-scared-ai-bridge`。

游戏请从[作者发布视频](https://www.bilibili.com/video/BV1F2gj6GEMw/)中的渠道获取。本项目不附带游戏。安装器会校验 4 个关键文件的 SHA256；同为 1.0.1 的其他构建也可能不兼容，具体以 [profile.json](profile.json) 为准。

### 2. 双击安装

双击 **`install.cmd`**，按提示粘贴游戏目录，回车等待完成。目录可以包含中文和空格，游戏不必搬进项目。

安装器会：

1. 查找本机 Python 3.12 x64；找不到时，通过 winget 安装到当前用户。
2. 只读校验游戏文件，版本不匹配就停止。
3. 创建项目专用 `.venv`，安装固定版本 Frida。
4. 生成本机绝对路径配置，检查 MCP 握手和工具列表。
5. 找到 Codex CLI 时自动注册 `pvz_scared` MCP；否则生成可导入的通用配置。

看到 **Setup complete** 即表示安装完成。安装过程不启动游戏、不操作存档。没有 winget 时，先手动安装 [Python 3.12 x64](https://www.python.org/downloads/windows/)，再双击安装。

### 3. 启动并让 AI 开始玩

双击 **`start.cmd`**。它会启动游戏和桥接；如果本项目已有可核对的健康宿主，会复用它。

重启或重新加载 AI 客户端，使 MCP 配置生效。把安装生成的 **`generated\START_HERE.txt`** 内容交给 AI；里面已经填好这台电脑的路径。也可以说：

> 先读项目里的 `skills/pvz-horror-player/SKILL.md` 和接口参考，再通过 `pvz_scared` 的 `pvzh_*` 工具帮我玩恐怖版剧情。正常游玩，不购物、不作弊。结束时交还控制。

AI 应先读取能力、当前状态和菜单，再接管控制。`start.cmd` 显示 ready 只说明宿主就绪；**AI 成功读取当前现场、提交原生动作后，才说明完成了实机接入**。

## 交给大肥鱼安装

不想自己敲命令，可以把以下文字连同**仓库链接或已解压目录**发给有本机终端权限的大肥鱼：

```text
请帮我安装“PVZ 恐怖版 AI Bridge”。
仓库：https://github.com/dy0000/pvz-scared-ai-bridge
先读仓库 README.md、INSTALL_FOR_AI.md 和 skills/pvz-horror-player/SKILL.md。
把项目放到长期保留的本机目录，找到我提供的 PVZ-Scared 1.0.1 游戏目录。
使用 install.ps1 -GamePath "实际游戏目录" -NonInteractive 安装。
能用 Codex CLI 就自动注册；其他客户端使用 generated/mcp.json。
不要覆盖我的其他 MCP 配置，不要输出 runtime/connection.json 中的 token。
安装完成后按文档启动并读取当前游戏状态；正常游玩，不购物、不作弊。
若缺游戏或客户端需要我手动重启，请准确告诉我还差哪一步。
```

完整的代理安装流程见 **[INSTALL_FOR_AI.md](INSTALL_FOR_AI.md)**。大肥鱼需要有本机文件、终端和 MCP 能力；只支持网页聊天的模型无法仅凭一段提示词操作你的本机游戏。

## 命令行安装

直接从 GitHub 安装，并指定游戏路径：

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/dy0000/pvz-scared-ai-bridge/main/bootstrap.ps1))) -GamePath "D:\Games\PVZ-Scared" -NonInteractive
```

下载入口的 `-InstallDir` 可指定项目安装位置；重复运行时复用已有源码，更新方法见下方“停止、更新与卸载”。

在解压后的项目根目录运行：

```powershell
# 自动识别 Codex CLI；游戏目录也可以换成完整 EXE 路径。
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -GamePath "D:\Games\PVZ-Scared" -NonInteractive

# 其他 MCP 客户端：只生成配置，不注册 Codex。
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -GamePath "D:\Games\PVZ-Scared" -Client Generic -NonInteractive
```

| 参数 | 作用 |
| --- | --- |
| `-GamePath` | 游戏目录或 `PVZ-Scared.exe` 完整路径；交互安装时可以现场输入 |
| `-Client Auto` | 默认。检测到 Codex CLI 就注册，否则生成通用 MCP JSON |
| `-Client Codex` | 要求注册 Codex；找不到 CLI 就明确报错 |
| `-Client Generic` | 只生成本机配置，适合其他 stdio MCP 客户端 |
| `-PythonPath` | 可选，指定已有的 Python 3.12 x64 可执行文件 |
| `-NonInteractive` | 不等待输入；必须提供游戏路径，或已将完整游戏放到 `game/` |

脚本不需要修改系统级执行策略。首次安装或修复可能由 Windows/winget 显示系统提示。

## 接入你的 AI

### Codex

自动注册等价于执行以下命令，安装器会代入真实绝对路径：

```powershell
codex mcp add pvz_scared -- "D:\AI-Games\pvz-scared-ai-bridge\.venv\Scripts\python.exe" -X utf8 "D:\AI-Games\pvz-scared-ai-bridge\scripts\run_mcp.py"
```

没有 CLI 时，可把 `generated\codex.toml` 中的单个服务配置合并到 Codex MCP 配置，或者在客户端设置中添加对应 stdio 服务。请保留其他服务条目。命令与格式依据 [OpenAI MCP 文档](https://learn.chatgpt.com/docs/extend/mcp)。

本项目的游玩 skill 随仓库提供；默认由 AI 读取本地文件，不覆盖你已有的全局 skill。

### 其他 MCP 客户端

导入安装生成的 **`generated\mcp.json`**，或添加：

- 类型：**stdio / 本地命令**。
- 命令：项目 `.venv\Scripts\python.exe` 的绝对路径。
- 参数：`-X`、`utf8`、`scripts\run_mcp.py` 的绝对路径，分别作为数组项。
- 服务名：`pvz_scared`；工具前缀：`pvzh_`。

`mcp.example.json` 只展示结构；**实际使用 generated 中带本机路径的文件**。不同客户端的配置文件位置各异，请合并 `mcpServers.pvz_scared`，不要用整个文件覆盖已有配置。

### 已经打开了游戏

在任务管理器“详细信息”页找到目标 `PVZ-Scared.exe` 的 PID，再运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\launch.ps1 -PidToAttach 12345
```

用实际 PID 替换 `12345`。宿主核对完整可执行文件路径和文件哈希，不会仅凭进程名字随便注入。

## 停止、更新与卸载

**暂时停止 AI：**在游戏里按 F8/F9。它会停止并锁定 AI；只有玩家按 F10 才重新允许。正常结束也应让 AI 调用 `pvzh_release_control`，确认 `controlled=false`、`auto_collect=false`、`selection_released=true` 和 `held_os_inputs=0`。

**停止宿主：**先让 AI 交还，然后在项目根目录运行：

```powershell
New-Item -ItemType File -Path .\runtime\stop.request -Force
```

宿主在确认释放后退出。若显示 `release_blocked`，等待释放或正常关闭游戏；不要强杀宿主，也不要启动第二控制器。

**更新：**交还并停止旧宿主后，将新版本解压到原目录覆盖源码，再运行 `install.cmd`。保留 `runtime/`，其中有防止重复扣款的购买收据。不要在运行中覆盖代码或依赖；安装器会使用宿主锁阻止活跃项目的环境更新。安装目录变动后，重新运行安装以更新 MCP 绝对路径。

**卸载：**交还并停掉宿主，移除客户端的 `pvz_scared` MCP 条目，再删除项目目录。Codex CLI 可用 `codex mcp remove pvz_scared`。游戏和游戏存档位于各自原目录；本项目不自动删除它们。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| 双击安装提示找不到游戏 | 先完整解压游戏；粘贴包含 EXE 和 `PVZ-Scared_Data` 的目录，不能直接指向 ZIP |
| `Unsupported game file` / 哈希不一致 | 此构建不匹配；使用支持的 Windows 1.0.1 包，别修改 profile 的哈希来绕过校验 |
| 没有 winget / Python 安装失败 | 手动安装 Python 3.12 x64，或通过 `-PythonPath` 指定它，再重试 |
| Frida 下载失败 | 检查到 PyPI 的网络；可按自己的网络环境设置 pip 镜像或代理，再重试安装 |
| AI 看不到工具 | 确认已导入 generated 配置并重启客户端；工具名以 `pvzh_` 开头 |
| `connection.json` 不存在 | 先运行 `start.cmd`；安装成功和游戏桥接启动是两个步骤 |
| 游戏已打开但启动器拒绝再开 | 用 `-PidToAttach` 连接实际进程，不再启动一个游戏 |
| 47633 端口已占用 / 控制者冲突 | 查看原宿主/客户端，先正常交还；新旧项目不能同时控制同一个游戏 |
| `release_blocked` | 保留原宿主，等待恢复或正常关闭游戏；不要清锁、强杀再重开 |
| `playerLocked` / F8/F9 后 AI 不能动 | 玩家在游戏中按 F10；AI 不能自己解除玩家停止锁 |
| `rejected_by_game` | 游戏拒绝本次动作；读当前卡牌、费用、冷却和格子，选择合法操作 |
| 超时/断线后不知道是否成功 | 重连后观察；结果未知的动作不自动重放，购买先查收据 |
| 看得到状态但种得不好 / 不能通关 | 检查模型、skill 和策略；接口接通不等于模型具备通关水平 |
| Windows 安全软件阻止 Frida | Frida 的运行时注入可能触发检测；核对源码与来源后按自己的安全软件策略处理 |

本地自检：双击 **`doctor.cmd`**。它检查游戏版本、依赖和 MCP 握手，**不接管游戏，不输出 token**。反馈问题可附 Python/Frida 版本、错误消息和相关日志片段；不要公开 `runtime/connection.json`、存档或整份运行目录。

## 开发与文档

```text
pvz-scared-ai-bridge/
├─ install.cmd / install.ps1     # 双击/终端安装
├─ start.cmd / doctor.cmd        # 启动/只读自检
├─ src/                         # 游戏内 Frida Bridge
├─ scripts/                     # 宿主、MCP、客户端与维护脚本
├─ skills/pvz-horror-player/     # AI 游玩技能、接口与战术
├─ tests/                       # 隔离测试，不驱动真实游戏
├─ docs/                        # 架构、兼容性和验证说明
└─ profile.json                 # 支持构建的哈希与原生元数据
```

- [给 AI 的安装指南](INSTALL_FOR_AI.md)
- [32 个工具与参数](skills/pvz-horror-player/references/api.md)
- [图鉴机制与战术](skills/pvz-horror-player/references/almanac-tactics.md)
- [架构与接入示例](docs/architecture.md)
- [兼容性与验证范围](docs/compatibility.md)
- [贡献指南](CONTRIBUTING.md) / [更新记录](CHANGELOG.md)

只修改安装流程时，运行对应的安装/启动器测试；修改原生动作时验证对应原生行为边界。打包命令：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\package_release.py
```

产物在 `dist/`，附逐文件 SHA256 清单和 ZIP 校验文件。打包脚本只收录公开源码目录，不包含游戏、存档、虚拟环境、运行日志、token 或本机配置。

## 许可与致谢

桥接代码与项目文档采用 [MIT License](LICENSE)。游戏本体、美术、音乐和剧情归各自权利人所有，不属于本项目的 MIT 授权范围。

感谢《植物大战僵尸恐怖版》作者；运行时研究参考了 [UnluckyManDev 的英文补丁项目](https://github.com/UnluckyManDev/pvz-scared-english-patch)。第三方说明与许可见 [NOTICE.md](NOTICE.md)。README 的信息组织参考 [uv](https://github.com/astral-sh/uv#readme) 与 [FastAPI](https://github.com/fastapi/fastapi#readme)，按“用途 → 安装 → 可运行示例 → 文档 → 贡献与许可”编排。
