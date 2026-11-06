# PVZ-Scared 0.2.2 独立接口

以当前 capabilities 的实际版本为准。响应为 `{id,ok,result}` 或 `{id,ok:false,error}`；result.status 才表示游戏动作结果。32 个工具使用前缀 `pvzh_`；下表工具名省略此前缀。写操作要求 take_control，查询可直接读取。

| 工具 | 原生 op | 参数 |
|---|---|---|
| capabilities / observe / menu | 同名 | 无 |
| take_control / release_control | attach / detach | 无 |
| stop | stop | 无 |
| menu_action | 同名 | menu_id, action_id；新建玩家可加 name |
| choose_card | 同名 | battle_id, card_id；selected 默认 true |
| start_battle | 同名 | battle_id |
| plant | 同名 | battle_id, card_id, row, column |
| collect | 同名 | battle_id, sun_ids 字符串数组 |
| auto_collect | 同名 | battle_id, enabled 布尔 |
| game_info | 同名 | 可选 level，读取指定剧情关配置，不改变当前关；inspect_class 为只读原生元数据诊断 |
| shovel | 同名 | battle_id, entity_id |
| move_plant | 同名 | battle_id, entity_id, row, column |
| interact | 同名 | battle_id；entity_id、row/column 或 x/y 世界坐标 |
| set_slow | 同名 | battle_id, enabled 布尔 |
| set_speed | 同名 | speed 倍率，原生预设 0.5 / 1 / 1.5 / 2 / 3 |
| set_paused | 同名 | battle_id, paused 布尔 |
| set_difficulty | 同名 | preset: easy / normal / hard / nightmare，先打开原生难度菜单 |
| rewards | 同名 | 无 |
| collect_reward | 同名 | battle_id, reward_id |
| choose_event | 同名 | event_id；battle_id 可选，通过卡片原生按钮推进翻面/查看/选择 |
| next_level | 同名 | 无，每次推进一个原生导航步骤 |
| almanac | 同名 | 无，先进入图鉴 |
| almanac_select | 同名 | entry_id, kind: plant / zombie |
| store | 同名 | 无，先进入商店 |
| buy | 同名 | product_id，直接原生购买 |
| purchase_receipt | 同名 | 可选 purchase_id；省略则最近 20 条 |
| test_assist | 同名 | battle_id；scope: mobs / all（默认 all），advance_waves 可选布尔；显式验收作弊 |
| ui_controls | 同名 | 无 |
| set_ui_value | 同名 | control_id, kind: slider / toggle / input / dropdown, value |

menu_id/action_id 来自最近 menu，使用后失效。关卡按钮附带 level，章节按钮附带 chapter，AI 可直接选择当前已解锁的目标。battle_id 随场景生命周期变化；卡牌、实体、收集物、商品、UI 控件 ID 均使用当前观察到的字符串，不自行构造地址。plant 的 card_id 可来自普通卡槽，也可为 observe 中 conveyor/falling 卡的完整 ID。

observe.phase：menu、moving、diary、selection、selection_paused、running、paused、victory、defeat、unknown。选卡与开始要求 selection，种植与收集要求 running。rewards 独立读取，最后波无敌人时 phase 仍为 running 也应查询。领奖后等待动画，事件卡带 native_state、revealed、animating；动画后通过卡片原生按钮推进选择。next_level 可以从主菜单、章节地图、关卡确认或原生继续入口推进。

game_info 包含 progress（当前关、最高已解锁关、金币、卡槽）、settings（难度、速度、噩梦解锁）、level（名称、描述、组件）。observe 还包含：

- cards：plant_name、source、cost、cooldown、available、disabled、on_bank、selected；特殊卡不一定有费用字段。
- plants/zombies：entity_id、kind、row、column、health/max_health、x/y、dying。植物另有 is_gray、ability；牧师蒜 ability 为 kind=pastor、crosses、spent、recharge、restore。interact 返回 ability_before/ability_after，crosses/spent 的变化是主动能力效果证据。僵尸 column 为当前位置估算，可能在棋盘外。
- allies 独立列出 PaladinGargantuar，不能当作敌人处理。
- suns扩展提供世界x/y；红光另有threatened_plant_ids，来自原生CoinSun.$tO伤害筛选，不是猜测半径。无爆炸倒计时；旧桥接缺字段时邻近未知。第40关当前用户明确授权例外用collect的当前sun_ids及red_sun_policy="level40-near-plant"，原生在游戏线程复核关卡和邻近条件，失效项在skipped_sun_ids，不把collection_requested当动画入账。调用方由唯一控制器附策略标记。
- tools、slow_enabled、time_scale、mechanics（传送带/掉落卡）、terrain.row_types、obstacles、grid_items、bosses、wave_state。
- bosses 同时包括第一形态和第二形态 arena/parts：部位 entity_id、part_name（LeftHand/RightHand）、health/max_health、position、dying、splash_rows，以及 head_attack_countdown。splash_rows 来自原生伤害范围查询，不按屏幕外观猜测可攻击行。需要点击部位时可用 interact 的世界坐标。
- native_pointer_reads 是原生鼠标位置覆盖累计计数，用于接入诊断，不需要在普通游玩中逐步校验。

cards.plant_name 是枚举名，plants/zombies/allies.kind 是类名，两者可能与图鉴本地化键不同，例如LinCornpult/Lin_Cornpult、TallZombie/Taller、PaladinGargantuar/Paladin_Zombie_Gargantuar；查机制用 [名称对照](almanac-tactics.md#现场类名与图鉴键对照)，执行仍使用当前实体或卡牌ID。

interact 当前返回 `interaction_requested`，不是统一的Committed回执；主动能力看ability变化及后继现场。乞讨付款也走交互，没有商店购买收据，按正常下一轮可见余额和对应实体/植物变化判断，未知结果不重放。

购物用 store 当前 product_id 直接 buy。返回 purchase_id、money_before/after、spent 与 status。宿主在原生扣款前持久保存收据；回包丢失或重启后用 purchase_receipt 查询，pending/unknown 不自动重放。历史测试授权不适用于其他用户；消费须取得当前会话明确授权。

set_ui_value 走真实控件事件；数值范围由原生 UI 处理。难度页面有多个滑条，按控件 path/name 决定目标。速度工具自行使用速度预设滑条，不把序号当倍率。主菜单、图鉴和商店的打开/返回用 menu_action。

Python 备用入口（已有 MCP 会话时不另开输入控制器）：

```python
import sys
sys.path.insert(0, "D:/AI-Games/pvz-scared-ai-bridge/scripts")
from client import HorrorClient

with HorrorClient() as game:
    game.request("attach")
    state = game.request("observe")["result"]
    # 使用当前状态进行操作。
    released = game.request("detach")
```

配置示例 `D:/AI-Games/pvz-scared-ai-bridge/mcp.example.json`，启动器 `scripts/launch.ps1`，维护 runner `scripts/play_story.py`。runner 的 state.json/actions.jsonl 位于独立 evidence/story-* 目录；写入该目录的 stop.request 可安全停止。存档和运行令牌不随桥接发布。

## 验收辅助与结局

历史接口验收曾允许开挂触发场景；只有当前任务已有相应明确授权时才使用 test_assist，并标记 assisted，普通代玩不由历史验收记录获得作弊授权。辅助验收不要求基础 runner 自然通关。工具只处理当前敌人：临时压低血量后调用目标真实伤害/死亡回调；mobs 保留 Dave/Boss，all 包含 Boss 部位；advance_waves 可加快普通波次。它明确跳过PaladinGargantuar，但代码并未统一核验所有可转友军种类，不把它当作通用敌我安全过滤器。响应含 cheat=true、damage（目标、类型、前后血量）、wave_accelerated。

终关 collect_reward 后用 menu 读取“Z公司档案”的 Title/PageCounter、NextButton/FinishButton，3 页读完后可能回到章节地图，关闭 LevelChooseCloseButton 后才是含 StoryMode 的主菜单。主菜单 Event 在该原版是固定占位弹窗，事件卡提交不适用；若未来原生卡片现场存在，可继续调用 choose_event。

需要复查数据时：`verify_expansion.py --scenario battle --level 41 --seconds 180 --transport mcp --cheat`，mcp-wire.jsonl 保存 AI 实际收到的原始请求/回包，mcp-tools.json 保存 32 个工具定义。已领奖而只需继续结局导航时，用 `--resume-result <先前summary.json>`，避免重打与重复领奖。证据目录每次新建；不要把脚本战术表现作为数据接入验收条件。
