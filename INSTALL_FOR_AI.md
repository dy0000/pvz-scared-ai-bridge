# 给大肥鱼的安装指南

目标：在用户的 Windows 电脑上安装“PVZ 恐怖版 AI Bridge”，让用户的 AI 客户端通过本机 stdio MCP 读取并操作 PVZ-Scared 1.0.1。

## 安装流程

1. 确认运行环境是 Windows x64，且你具有本机文件与终端权限。下载/解压本项目到长期保留的目录；已有合适目录就复用。
2. 读取 `README.md` 和 `skills/pvz-horror-player/SKILL.md`。寻找用户已提供的游戏目录；不要扫描无关磁盘。缺游戏时告知用户从 README 的作者渠道准备完整 Windows 1.0.1 包。
3. 在项目根目录执行下面的命令，替换实际游戏路径：

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -GamePath "D:\Games\PVZ-Scared" -NonInteractive
   ```

   非 Codex 客户端加 `-Client Generic`。如果 Python 3.12 已安装在自定义位置，可加 `-PythonPath "实际路径\python.exe"`。使用安装器准备的 `.venv`，不改系统 Python 依赖。

4. 检查命令退出码。安装器已完成哈希校验与 MCP 握手，不必再重复同一检查。Codex CLI 已成功注册时告诉用户重新加载客户端；其他客户端把 `generated/mcp.json` 的单个 MCP 服务合并到它支持的配置位置，保留其他配置。客户端路径或产品不明时先说明生成文件在哪里。
5. 给用户 `generated/START_HERE.txt`。skill 由 AI 从当前项目读取，不需要覆盖全局技能。不要把本机配置或运行 token 放进仓库。
6. 用户要求开始游玩时，先判断是否已有游戏/宿主。没有宿主就运行 `start.cmd`；已有游戏但未接入时，用 `scripts/launch.ps1 -PidToAttach <实际PID>`，不启动重复游戏。已有活跃控制器则沿用它，不抢占。
7. 用当前客户端的 `pvzh_capabilities`、`pvzh_observe`、`pvzh_menu` 查看现场。此后作为唯一控制者 `pvzh_take_control`。根据当前解锁进度开始正常剧情，不改存档、不自动解锁、不凭历史说明获得购物/作弊授权。
8. 结束时 `pvzh_release_control`，用该回包核对释放凭据。报告安装、MCP 加载、宿主 ready、实机读写分别完成到哪一步，不把工具列表当作实机验收。

## 约束

- 游戏关键文件哈希不匹配就停止接入，不改 profile 绕过校验。
- 不输出 `runtime/connection.json` 的 token；诊断只提取非敏感字段。
- 正常游玩保留原生费用和冷却；`test_assist` 是显式作弊工具，只在用户明确授权后使用。
- 不自动购物，用户明确授权后才消费游戏金币。
- F8/F9 玩家停止锁只由玩家 F10 解除。
- 超时/断线后的动作结果未知，不自动重放；购买先查 `purchase_receipt`。
- `release_blocked` 时原宿主保留控制权；等恢复或正常关闭游戏，不强杀、不清锁、不启动另一控制器。
- 纯离线文档修改不停止健康宿主。更新代码/依赖必须在交还并停止本项目宿主后进行。

## 完成时告诉用户

项目安装目录、使用的游戏目录、MCP 服务名 `pvz_scared`、下一步双击 `start.cmd`，以及客户端是否需要用户重启。缺模型账号、游戏、客户端加载能力时说明具体缺项，不能假装安装后已经开始游玩。
