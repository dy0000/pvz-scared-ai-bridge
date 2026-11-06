# PVZ 恐怖版 AI Bridge

让你的大肥鱼来玩《植物大战僵尸恐怖版》。提供 32 个 MCP 工具，支持读战场、选卡布阵、铲子手套、领奖续关。

## 让 AI 一键安装

把这句话发给能操作你电脑的 AI：

> 帮我安装这个项目：https://github.com/dy0000/pvz-scared-ai-bridge ，按 INSTALL_FOR_AI.md 自动安装并接入 MCP。

AI 会自动下载项目、准备 Python 和依赖、配置 MCP。**不必先填写游戏目录，安装不强制校验游戏版本。**

## 自己安装

在 Windows PowerShell 粘贴：

```powershell
irm https://raw.githubusercontent.com/dy0000/pvz-scared-ai-bridge/main/bootstrap.ps1 | iex
```

或者[下载安装包](https://github.com/dy0000/pvz-scared-ai-bridge/releases/latest)，解压后双击 **`install.cmd`**。

## 开始玩

1. 打开恐怖版游戏，再双击项目中的 **`start.cmd`**，自动关联游戏。
2. 重新加载 AI 客户端的 MCP，把 **`generated/START_HERE.txt`** 内容发给 AI。
3. 想停止时在游戏内按 **F8/F9**，按 **F10** 重新允许 AI。

需要 Windows x64 和支持本机 stdio MCP 的 AI 客户端。检测到 Codex CLI 时自动注册；其他客户端导入 `generated/mcp.json`。游戏请从[作者发布页](https://www.bilibili.com/video/BV1F2gj6GEMw/)另行获取。

## 兼容性

当前原生接口已适配 **PVZ-Scared 1.0.1**。安装不因版本变化而失败；连接游戏时仍会核对地址表兼容性，尚未适配的新版可能无法游玩。支持剧情模式，暂不支持生存、娱乐模式。

## 文档

- [安装参数、更新与常见问题](docs/installation.md)
- [AI 安装指南](INSTALL_FOR_AI.md) / [游玩技能](skills/pvz-horror-player/SKILL.md)
- [工具接口](skills/pvz-horror-player/references/api.md) / [验证范围](docs/verification.md)

桥接采用 [MIT 许可](LICENSE)，游戏本体及素材归原作者所有。

▶ [大肥鱼通关视频](https://www.bilibili.com/video/BV1Cixp6MEEh/)
