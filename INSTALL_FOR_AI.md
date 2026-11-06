# AI 自动安装

在用户的 Windows 电脑执行：

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/dy0000/pvz-scared-ai-bridge/main/bootstrap.ps1))) -NonInteractive
```

默认目录 `%LOCALAPPDATA%\PVZScaredAIBridge`。已有本项目源码时直接运行 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -NonInteractive`，无需再次下载。游戏路径可省略；发现正在运行的游戏时自动关联，未发现也正常完成安装。

安装器自动准备 Python 3.12 和独立依赖，检查 MCP 握手，检测到 Codex CLI 就注册 `pvz_scared`。其他客户端使用生成的 `generated/mcp.json`，合并单个服务，保留其他配置。安装不要求游戏版本哈希匹配。

安装后告诉用户打开游戏，再运行安装目录的 `start.cmd`；客户端需要重新加载 MCP 时说明这一点。开始游玩前读 `skills/pvz-horror-player/SKILL.md`，先查看现场，再作为唯一控制者接管。安装完成不等于已经验证实机游玩。

不要输出连接 token，不抢占已有控制器。正常游玩不购物、不作弊；结束时交还。新版游戏的原生接口若不兼容，说明具体限制，不能靠改哈希强行接入。
