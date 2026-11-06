# 架构与扩展

```text
AI 客户端（模型/账号由客户端管理）
  ↓ stdio JSON-RPC / MCP，工具名 pvzh_*
scripts/run_mcp.py
  ↓ 持久 HorrorClient，本机 TCP + 每次宿主随机令牌
scripts/run_bridge.py（单宿主锁，127.0.0.1:47633）
  ↓ Frida attach，校验精确路径和构建
src/bridge.js + src/story.js
  ↓ GameAPP.Update 游戏线程上的原生调用
PVZ-Scared 1.0.1
```

## 配置与生命周期

安装器使用 Python 3.12，检查 `profile.json` 的 4 个文件 SHA256，创建 `.venv` 并安装固定版 Frida。游戏目录写入 `config.local.json`；不复制、不修改游戏。宿主未配置时仍支持 `game/PVZ-Scared.exe` 默认路径。

`start.cmd` 使用 `.venv/Scripts/python.exe` 启动宿主。已有连接时，启动器核对本机地址、端口所有者、宿主 PID、游戏路径和状态后复用；`release_blocked` 不允许替换。宿主启动前再核对文件哈希及 PID 对应的 EXE 路径，拿到本项目 `controller.lock` 和独占 TCP 端口才接入。

宿主将 token 等连接信息写入 `runtime/connection.json`，MCP 通过客户端模块读取，不把 token 放进 MCP 配置。MCP `initialize` 和 `tools/list` 不依赖游戏，因此安装可以在不启动游戏的情况下自检；实际工具调用才建立游戏宿主连接。

单机只保留一个输入控制者。别同时用 MCP、示例 runner 和 Python 直连操作目标。查询 `doctor.cmd` 只检查本机与 MCP 定义，不会创建游戏连接。

## 给非 MCP Agent 接入

优先使用现有 stdio MCP。若 Agent 框架只支持 Python，可在独立控制会话中复用客户端：

```python
import sys
from pathlib import Path

root = Path(r"D:\AI-Games\pvz-scared-ai-bridge")  # 换成本机项目目录
sys.path.insert(0, str(root / "scripts"))
from client import HorrorClient

with HorrorClient() as game:
    print(game.request("capabilities"))
    print(game.request("observe"))
    try:
        game.request("attach")
        # 用当前 battle_id / card_id / entity_id 规划和执行。
    finally:
        released = game.request("detach")
        print(released)  # 核对释放凭据；失败时保留宿主并按文档恢复。
```

这里的 `print` 只输出工具回包，不读取或输出连接配置。`HorrorClient.close()` 仅关闭连接，显式原生交还仍使用 `detach`。连接中断时动作结果未知，不能原样重试写操作。

## 动作语义

外层 `ok=true` 仅表示接口调用成功。`result.status=Committed` 才代表相应动作已提交；`navigation_requested`、`interaction_requested`、`collection_requested` 要在自然后继观察中看结果，不能当作进入页面、击杀或入账的证明。

使用当前会话的字符串 ID，行列从 1 开始。不要构造内存地址或复用过关前的 ID。特殊卡来源包含 bank/conveyor/falling；友军和 Boss 部位有各自数据字段。

`test_assist` 是历史验收用的显式作弊，不应混入普通代玩策略。基础 runner 不等同完整战术 Agent，处理新机制时参照技能与实际能力数据。
