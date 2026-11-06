# 参与贡献

欢迎改进安装体验、增加构建适配、修复原生操作或完善文档。提交问题时附系统、游戏版本、复现步骤、期望/实际行为和去敏错误片段；不要上传游戏文件、存档、连接 token 或整份 runtime。

## 本地开发

运行 `install.cmd` 准备环境。编辑 Python 和 Frida JS 即可，不需要编译游戏。Node.js 只用于运行隔离 JS 测试，玩家无需安装。

回归范围以变更边界为准，例如：

```powershell
# 安装配置、打包边界、启动器：不启动真实游戏。
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p test_install.py -v
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p test_bootstrap.py -v
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p test_launcher.py -v

# 宿主或 MCP 改动时才运行对应文件。
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p test_host.py -v
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p test_mcp.py -v

# 原生动作逻辑的隔离回归。
node tests/test_bridge.cjs
node tests/test_story.cjs
node tests/test_sun_hazards.cjs
```

隔离测试不证明真实游戏动作成功；涉及新原生绑定、场景切换或释放逻辑时，在明确授权的测试存档上验证对应操作，并区分自然游玩与 assisted 结果。不要把历史测试购物或作弊授权延续到他人的存档。

## 必须保留的边界

- 精确游戏路径、四个关键文件哈希、单宿主锁和独占端口。
- 原生游戏线程执行；正常操作保留原生规则。
- F8/F9 停止锁与玩家 F10 恢复；控制交还与输入释放凭据。
- 结果未知不重放，购买收据跨宿主重启保留。
- 不接管活跃控制器、不热替换运行中的桥接、不公开运行 token。

新增游戏版本请提供独立构建证据并调整精确适配，不能只把新文件哈希塞进旧地址表。PR 描述写清触发场景、改变后的行为、定向验证及剩余限制。

运行 `scripts/package_release.py` 生成不含本机数据的发行 ZIP。贡献以本项目 MIT 许可提交，第三方来源保留原许可说明。
