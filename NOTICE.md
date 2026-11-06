# 来源与第三方许可

本项目从本地 PVZ-Scared AI Bridge 0.2.2 独立拆分。公开范围为桥接源码、元数据配置、隔离测试、安装工具与文档；不含游戏本体、资源、存档或运行令牌。

| 项目 | 用途 | 许可/归属 |
| --- | --- | --- |
| PVZ-Scared / 植物大战僵尸恐怖版 | 被接入的游戏，需玩家另行准备 | 作者及相关权利人所有；不随本项目分发 |
| [Frida](https://github.com/frida/frida) | 安装时从 PyPI 获取的运行时依赖 | Frida 项目许可，详见上游；依赖不包含在源码 ZIP 中 |
| [Python](https://www.python.org/) | 安装时检测/通过 winget 获取的运行环境 | PSF License；不包含在源码 ZIP 中 |
| [pvz-scared-english-patch](https://github.com/UnluckyManDev/pvz-scared-english-patch) | 原始研究参考了运行时字符串布局与分配函数位置 | MIT，Copyright (c) 2026 UnluckyManDev，保留[上游许可](third-party/pvz-scared-english-patch-MIT.txt) |

`profile.json` 是与受支持构建绑定的原生类、方法与字段元数据及文件哈希，不是游戏安装包。固定 RVA 仅对该构建适用。项目不安装英文补丁，也不附带其翻译资源。
