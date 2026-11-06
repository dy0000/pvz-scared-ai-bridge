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

需要 **Windows x64** 和支持本机 stdio MCP 的 AI 客户端。游戏从[作者发布页](https://www.bilibili.com/video/BV1F2gj6GEMw/)另行获取。

### 1. 安装

在 PowerShell 粘贴：

```powershell
irm https://raw.githubusercontent.com/dy0000/pvz-scared-ai-bridge/main/bootstrap.ps1 | iex
```

也可[下载安装包](https://github.com/dy0000/pvz-scared-ai-bridge/releases/latest)，解压后双击 **`install.cmd`**。Python、依赖和 MCP 配置会自动准备；不必先填写游戏目录，安装不强制校验版本。

### 2. 启动

打开恐怖版游戏，再双击安装目录的 **`start.cmd`**，自动关联游戏。默认安装目录为 `%LOCALAPPDATA%\PVZScaredAIBridge`。

### 3. 让 AI 开始玩

重新加载 AI 客户端的 MCP，把 **`generated/START_HERE.txt`** 内容发给 AI。结束时让 AI 交还控制；随时可按 **F8/F9** 停止，玩家按 **F10** 重新允许。

## 交给大肥鱼安装

把这句话发给能操作你电脑的 AI：

> 帮我安装这个项目：https://github.com/dy0000/pvz-scared-ai-bridge ，按 INSTALL_FOR_AI.md 自动安装并接入 MCP。

AI 安装流程见 [INSTALL_FOR_AI.md](INSTALL_FOR_AI.md)。AI 需要有本机文件、终端和 MCP 能力。

## 命令行安装

已下载源码时，在项目根目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -NonInteractive
```

游戏路径可省略。自定义安装目录、指定游戏或使用其他客户端的参数见 [安装文档](docs/installation.md)。

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

直接运行 `start.cmd`，启动器会自动发现并关联唯一的目标游戏。多开游戏时可指定实际 PID：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\launch.ps1 -PidToAttach 12345
```

当前原生地址表已适配 **PVZ-Scared 1.0.1**。安装不因版本变化失败；连接时仍核对已适配构建，尚未适配的新版可能无法游玩。

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
| 安装后找不到游戏 | 先打开完整解压的恐怖版游戏，再运行 `start.cmd`；也可用 `-GamePath` 指定路径 |
| 启动时报 `Unsupported game file` | 安装不受影响，但原生地址表尚不兼容该构建，需要适配后才能游玩 |
| 没有 winget / Python 安装失败 | 手动安装 Python 3.12 x64，或通过 `-PythonPath` 指定它，再重试 |
| Frida 下载失败 | 检查到 PyPI 的网络；可按自己的网络环境设置 pip 镜像或代理，再重试安装 |
| AI 看不到工具 | 确认已导入 generated 配置并重启客户端；工具名以 `pvzh_` 开头 |
| `connection.json` 不存在 | 先运行 `start.cmd`；安装成功和游戏桥接启动是两个步骤 |
| 多个游戏进程无法自动选择 | 用 `-PidToAttach` 选定实际进程 |
| 47633 端口已占用 / 控制者冲突 | 查看原宿主/客户端，先正常交还；新旧项目不能同时控制同一个游戏 |
| `release_blocked` | 保留原宿主，等待恢复或正常关闭游戏；不要清锁、强杀再重开 |
| `playerLocked` / F8/F9 后 AI 不能动 | 玩家在游戏中按 F10；AI 不能自己解除玩家停止锁 |
| `rejected_by_game` | 游戏拒绝本次动作；读当前卡牌、费用、冷却和格子，选择合法操作 |
| 超时/断线后不知道是否成功 | 重连后观察；结果未知的动作不自动重放，购买先查收据 |
| 看得到状态但种得不好 / 不能通关 | 检查模型、skill 和策略；接口接通不等于模型具备通关水平 |
| Windows 安全软件阻止 Frida | Frida 的运行时注入可能触发检测；核对源码与来源后按自己的安全软件策略处理 |

本地自检：双击 **`doctor.cmd`**。它检查文件是否齐全、依赖和 MCP 握手，**不接管游戏，不输出 token**。反馈问题可附 Python/Frida 版本、错误消息和相关日志片段；不要公开 `runtime/connection.json`、存档或整份运行目录。

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

- [给 AI 的安装指南](INSTALL_FOR_AI.md) / [安装参数与维护](docs/installation.md)
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

感谢《植物大战僵尸恐怖版》作者；运行时研究参考了 [UnluckyManDev 的英文补丁项目](https://github.com/UnluckyManDev/pvz-scared-english-patch)。

▶ [大肥鱼通关视频](https://www.bilibili.com/video/BV1Cixp6MEEh/)

## 社区

本开源项目已链接并认可 [LINUX DO 社区](https://linux.do)。
