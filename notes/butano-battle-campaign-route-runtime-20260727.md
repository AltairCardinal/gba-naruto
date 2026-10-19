# Butano 战役战斗路由与运行时证据（2026-07-27）

## 结论

生产 ROM 已删除 `41 → 43 → 9 → 11 → 32` 开发夹具链。章节层现在用固定容量、
数据驱动的 `battle_campaign_route` 把持久 `scenario_id` 解析为通用
`battle_runtime_scene_request`；单场战斗仍完全由共享 controller、session、AI、
resolver、condition 和 presentation 执行，路由层不保存截图、按键序列或伪造结果。

当前只签发原 ROM 已有运行 checkpoint 支持的战斗切片：

| scenario | battle row | variant | 胜利后的 scenario | 队伍策略 |
|---:|---:|---:|---:|---|
| 41 | 41 | 0 | 42 | 鸣人 |
| 42 | 42 | 0 | 43 | 鸣人 |
| 43 | 43 | 0 | 44 | 鸣人 |
| 44 | 44 | 0 | 45 | 第七班 |
| 45 | 45 | 0 | 46 | 第七班 |
| 46 | 9 | 0 | 47 | 第七班 |
| 47 | 13 | 0 | 49 | 第七班 |
| 49 | 14 | 0 | 50 | 第七班 |
| 50 | 15 | 0 | 56 | 第七班 |

scenario 48 是纯剧情段，本里程碑没有伪造一场 battle 48，而是在 battle-only 路由中明确
跳到 scenario 49。scenario 56 是当前证据切片的终止哨兵，不会静默重放 battle 15。

## 原 ROM 证据边界

- scenario 41–45 的自然结果和后继可由
  `artifacts/runtime-checkpoints/scenario-41-postbattle.ss9`、
  `scenario-42-postbattle-world-map.ss9`、`scenario-43-postbattle-next-task-prompt.ss9`、
  `scenario-44-postbattle-world-map.ss9`、`scenario-45-postbattle-world-map.ss9` 复现；
  42/44/45 另有 progression evidence JSON。
- scenario 46 的自然入口、34+ 回合捕获路线、胜利奖励和战后地图 checkpoint 绑定
  battle row 9。
- scenario 47 的入口文件名和运行状态绑定 battle row 13；scenario 48 只有学院剧情与
  战后世界地图，没有战斗入口。
- scenario 49、50 的入口 checkpoint 分别绑定 battle row 14、15；其多敌、护送、占位、
  替身和失败条件证据仍由原 checkpoint 与
  `notes/butano-battle-video-frame-analysis-20260722.md` 约束。

该表只表达“章节选择哪场战斗”，不表示每一场的剧情演出、对象专属表现和技能音画已经完整。

## 架构与事务

`battle_campaign_state.chapter_id` 在生产中统一解释为 scenario ID。路由表产生
`battle_id + variant + party policy`，再由 `run_battle_campaign_stage` 调用唯一的
`run_battle_scene(request)`。

- 只有 `battle_runtime_scene_exit::victory` 推进 scenario。
- defeat、draw、aborted 不推进路由，也不提交场内 campaign 候选。
- scenario 44 首次启用第七班时只补建缺失的佐助/小樱 level-1 progression，不覆盖已有
  等级、经验、技能训练或装备。
- 路由推进发生在验证保存之前；失败时恢复战前 campaign checkpoint。
- SRAM telemetry 在既有字段尾部增加 `scenario_id` 和 `route_complete`，旧偏移不变。

## EWRAM / Maxmod 回归与修复

初版路由把 `battle_campaign_route_workspace` 作为第三份 `battle_campaign_state` 常驻
EWRAM，新增 `0x1234` 字节静态占用。ARM 构建虽然成功，mGBA 却稳定出现：

- 准备页已经显示、campaign telemetry 为 scenario 41；
- GBA `KEYINPUT` 能看到 B=`0x03FD`、A=`0x03FE`；
- Butano keypad manager 的 held/pressed 缓冲始终为 0；
- 每个 VBlank 的 IRQ 返回点都落在 Maxmod `__mmAllocChannel_from_thumb`；
- 主线程没有走到 `bn::core::update()` 尾部的 keypad 更新，因此所有输入看起来失效。

旧稳定 ROM 的同一探针会更新 keypad 缓冲并在 frame 240 进入 battle 41。修复后，SRAM
序列化和 route 事务不会同时使用各自工作区，二者复用同一个 0x2000 EWRAM raw storage；
事务语义不变，`.sbss` 从 162,648 降到 157,988 字节。相同探针随后恢复为
B held=`2`、A held=`1`，frame 240 进入 battle 41 部署。

诊断证据：

- 失败：`artifacts/butano-battle-preparation-input-diagnostic-20260727-02/diagnostic.json`
- 旧 ROM 对照：
  `artifacts/butano-battle-preparation-input-control-old-rom-20260727-01/diagnostic.json`
- 修复后：
  `artifacts/butano-battle-preparation-input-diagnostic-20260727-03/diagnostic.json`
- ARM guard：
  `build/resource-guard/20260727-battle-campaign-route-arm-build-shared-workspace.json`

这证明本次卡死不是 mGBA 没送键，也不是截图菜单等待第二次 A，而是 GBA 端音频提交阻塞
使主线程无法完成一帧。后续新增大型事务工作区必须先检查可复用生命周期，再做 ARM section
和非禁音音频路径验收。

## 非零音频回归已闭合

工作区复用先修复了输入/战斗冻结，但当时仍不能据此签发音频：该版 ROM 的 mGBA core
冷启动 600 帧录音为 657,416 个全零采样；同一录音器运行旧稳定 ROM 得到 540,872 个
非零采样、RMS 888.8785、峰值 6528，排除了录音器和 mGBA 前端本身。

进一步的运行内存证据位于
`artifacts/butano-audio-mixer-current-prep-20260727-01/diagnostic.json`：

- Maxmod 已初始化，`sound_005` 的歌曲地址为 `0x088908AC`，落在
  `bn_audio_soundbank_bin` 范围内；
- pattern 已推进到 row 26，global/layer volume 为 128/1024；
- 20 个 mixer channel 中激活数为 0，wave buffer 非零字节数为 0；
- 当前与旧稳定 ROM 的 soundbank 主体及该歌曲数据逐字节一致。

继续在 Maxmod 的 `NewNote`、`AllocChannel` 和 IWRAM veneer 处追踪后，根因闭合为
SRAM decode 大栈覆盖：按值返回的 `decode_battle_campaign_slot` 在 ARM 上建立约
`0x123c` 字节栈帧，嵌套 `memset` 越过栈底，把
`__mpp_Channel_NewNote_from_arm` 的目标从 `0x03000B05` 改写为 campaign buffer
内容。生产现使用调用方持有的 EWRAM decoded slots 原位解析，核心 decode 栈帧降到
`0x6c`。

修复后 100 帧追踪得到 88 次 `mmFrame`、1 次 `NewNote`、1 次成功声道分配和 0 次
veneer 改写；600 帧录音有 539,784 个非零采样、RMS 887.7133、峰值 6528，
`>=8192`/`>=16384` 相邻突跳均为 0。scenario 41 又在 frame 978 完成 verified save，
冷启动在 frame 134 进入 battle 42。完整调用链、WAV 与运行证据见
`notes/butano-battle-audio-runtime-20260727.md`。

## TDD 与运行时验收

红灯依次捕获：

1. 路由头文件不存在，九段映射、胜利推进、终止哨兵与第七班激活均无实现；
2. `main.cpp` 仍拥有硬编码夹具链，且没有结果回滚/保存顺序；
3. campaign telemetry 没有 scenario，无法证明保存后的后继；
4. ARM 上第三份 campaign 工作区造成运行时冻结；
5. 两个 Lua 驱动过早发送首键，未显式完成准备页的“松开后解锁”握手。

绿灯后的关键运行证据：

- 场景 41 完整路线：
  `artifacts/butano-battle-campaign-route-20260727-05/audit.json`
  - frame 978、battle 41、round 4、phase complete；
  - 150 EXP，鸣人 level 1→2；
  - 动作 8 训练 0→1，训练点 1→0；
  - SRAM generation 1 / slot 1 / verified 1；
  - scenario 41→42，控制错误和玩家错误均为 0。
- 同一 ROM/SRAM 冷启动后继：
  `artifacts/butano-battle-campaign-route-battle42-20260727-01/audit.json`
  - load generation 1、`load_used_default=0`；
  - scenario 42 解析为 battle 42；
  - frame 134 进入部署，错误均为 0。
- ARM ROM SHA-256：
  `8f19053a827ee15c4d1a0c0b7b43550aec7f2b74e2be2cd5468bb7bbf1493bad`
- ELF SHA-256：
  `570867daf9717e2ec3bbc3b8fe8fe10a243fd69effb95f4607daafb087abf479`
- 最终 telemetry：
  campaign `0x02008108`，battle `0x020221E4`。

## Scenario 42 完整战役纵切（后续验收）

早期路由验收只证明 scenario 41 胜利后能进入 battle 42 部署，不能证明 battle 42 本身
是可运行的战斗，更不能证明结果能进入后续关卡。本轮把验收扩展为三个独立、顺序衔接的
生产 ROM 进程：

```text
scenario 41
  └─ 共享 controller：真实四回合胜利
       └─ 结果 / 升级 / 跳过修炼
            └─ verified SRAM：scenario 42, LV2, EXP0, TP1
                 └─ scenario 42 共享 controller
                      ├─ 地图碰撞与逐回合可达格选择
                      ├─ 敌方 AI
                      ├─ 动作 5 + resolver + presentation
                      ├─ condition interpreter → victory
                      └─ 结果 100 + 10 + 0 = 110
                           └─ verified SRAM：scenario 43
                                └─ 新 mGBA 进程冷启动 battle 43
```

自动化只发送 GBA 按键并读取 telemetry；脚本测试明确拒绝 `emu:write`。移动驱动也不再
假定敌人静止或指定格必定合法，而是按与宿主集成测试相同的距离顺序枚举候选，让生产
controller 的地图、占位和移动预算决定哪个格可提交。只有已提交格与敌人距离为 1 时才
打开技能目录，否则正常结束行动并继续追击。

### 标准 scenario 42 输入存档

原作 scenario 42 自然证据要求鸣人保持 LV2、EXP 从 0 增至 110、修炼点保持 1。先前
`MGBA_S41_SHARED_CONTINUE_RESULTS=1` 路线主动消费修炼点把动作 8 从 0 练到 1，虽然是
合法玩家选择，但不适合作为该自然路线的前置存档。新增可选的真实按键分支在训练页按 B：

- 证据：
  `artifacts/butano-battle-campaign-route-s41-preserve-training-20260727-01/audit.json`
- frame 897，battle 41，round 4；
- 结果 150 EXP，鸣人 LV2 / EXP0；
- 修炼点 1，动作 8 等级 0；
- scenario 42，save generation 1 / verified 1；
- SAV SHA-256：
  `77e00322b7d055fc1b4c1f1035b7a9268c358c62c10df3fbc3cf069b56a7afd7`。

这没有修改训练规则；玩家仍可选择修炼并消费一点。它只纠正验收输入分支，使其与原作
scenario 42 checkpoint 对齐。

### Battle 42 完整胜利与保存

- 证据：
  `artifacts/butano-battle-campaign-route-s42-complete-20260727-05/audit.json`
- frame 4810，battle 42，round 11，phase complete；
- 最后解析动作 5，最终活动单位 1；
- 任务经验 100、战斗经验 10、回合奖励 0、总经验 110；
- 鸣人 LV2 / EXP110 / TP1 / 动作 8 等级 0；
- scenario 43，save generation 2 / verified 1；
- controller/player error 均为 0；
- SAV SHA-256：
  `61b76f53017f80592844c280fe0c35a2dec98bb5d4bc93b5745d6e2bff43d8f7`。

对应宿主集成测试
`butano-sequel/game/tests/test_battle_campaign_scenario_42.cpp` 从同一内容目录装载 battle 42，
只调用 controller 公共语义输入，贯通移动、敌方回合、技能、胜负、结果、训练取消、
campaign merge 和 route advance。它没有 scenario 42 专用 HP 写入、固定胜负 API 或第二套
战斗状态机。

### Scenario 43 独立冷启动与黑帧采样纠正

第一次冷启动探针在 `PHASE_DEPLOY_UNIT` 出现时立即截图，虽然 telemetry 已证明
scenario/battle 43，但得到部署 renderer 首帧之前的黑图；该图不作为可见验收。脚本随后
按 TDD 改为完成部署和开场脚本，等待 `unit_selection` 稳定两帧才截图：

- 证据：
  `artifacts/butano-battle-campaign-route-s43-cold-20260727-02/audit.json`
- frame 223，scenario 43 / battle 43 / round 1 / phase unit selection；
- load generation 2，`load_used_default=0`；
- controller/player error 均为 0；
- `battle-entry.png` 可见地图、敌我单位、游标和 `SELECT UNIT`，不是黑帧，也不需要用户
  再按一次 A 才显示战场。

最终验证为 99/99 个 game host C++ 测试、32/32 个相关 Python wiring/脚本测试、
`git diff --check`、Lua 语法检查和固定 devkitARM 构建通过。资源守卫记录：

- `build/resource-guard/20260727-battle-campaign-s42-full-host.json`
- `build/resource-guard/20260727-battle-campaign-s42-final-arm-build.json`
- `build/resource-guard/20260727-battle-campaign-route-s41-preserve-training-01.json`
- `build/resource-guard/20260727-battle-campaign-route-s42-complete-05.json`
- `build/resource-guard/20260727-battle-campaign-route-s43-cold-02.json`

## Scenario 43 多单位完整战役纵切

scenario 42 纵切仍然只有一名玩家和一名敌人，不能单独证明共享运行时能处理召唤单位、
同阵营多单位调度、三个敌方 AI、跨等级结算和后继队伍扩充。scenario 43 现作为第二个
完整关卡样本，验收规格直接来自原 ROM 内容和既有自然推进证据：

- Naruto 初始 `(4,17)`，三名敌人初始 `(2,11)`、`(4,10)`、`(6,11)`；
- 槽 5..12 是预留槽，动作 7 在 `(4,16)` 创建槽 5 Naruto 分身并消耗 3 chakra；
- 胜利条件是 `no_valid_unit_for_side(enemy)`；
- 三敌各携带 10 EXP；任务 125 EXP，5 回合内奖励 25 EXP；
- 原作自然路线超过 5 回合，得到 `125 + 30 + 0 = 155`，Naruto
  `LV2/EXP110/TP1 → LV3/EXP0/TP2`。

新增宿主纵切
`butano-sequel/game/tests/test_battle_campaign_scenario_43.cpp` 只使用 controller 的公开
语义输入。它真实生成分身，让三个敌方单位分别走 AI 回合，让 Naruto 与分身经过共享
pathfinder 接敌和执行动作 5，最后由 condition interpreter 判胜；随后完成结果、升级、
训练取消、campaign merge、43→44 路由和 Team 7 party policy。测试不写 HP、坐标、胜负
或 campaign 内存，也没有 scenario 43 专用生产 FSM。

### mGBA 完整胜利与保存

第一轮多敌 ROM 驱动在
`artifacts/butano-battle-campaign-route-s43-complete-20260727-01/` 到达 round 7，
但按“离敌距离”枚举整张地图，累计尝试 78 个当前单位不可达格，Lua 在 frame 20000 停止。
此失败已由
`build/resource-guard/20260727-battle-campaign-route-s43-complete-01.json` 保留，标记为
被后续运行取代；当时 controller/player error 均为 0，不能解释为战斗状态机挂死。

驱动随后先按当前单位 3 格移动预算裁剪候选，再按离敌距离排序。成功证据：

- `artifacts/butano-battle-campaign-route-s43-complete-20260727-02/audit.json`
- frame 12429，battle 43，round 27，phase complete；
- `shadow_clone_verified=1`，完成时仍有两名活动玩家单位；
- 三敌战斗 EXP 30，任务 125，回合奖励 0，总计 155；
- Naruto LV3 / EXP0 / TP2 / action 8 LV0；
- scenario 44，save generation 3 / verified 1；
- controller/player error 均为 0；
- ROM SHA-256：
  `8f19053a827ee15c4d1a0c0b7b43550aec7f2b74e2be2cd5468bb7bbf1493bad`；
- SAV SHA-256：
  `ed3f1ad83e61219f538a84b4d44aeb860ef7a3116d057c42f1bd041c33e6a78e`。

Lua 只读取 telemetry 并发送 GBA 按键，静态测试继续拒绝 `emu:write`。分身验证来自动作 7
已解析且活动单位数由 4 增至至少 5，不是审计脚本自行写入的标志。

### Scenario 44 独立冷启动

第二个 mGBA 进程复制上述 verified SAV 后独立启动：

- `artifacts/butano-battle-campaign-route-s44-cold-20260727-02/audit.json`
- frame 251，scenario 44 / battle 44 / round 1 / phase unit selection；
- active units 4，当前角色 Naruto；画面可见 Naruto、Sasuke、Sakura 和敌方单位；
- load generation 3，`load_used_default=0`，controller/player error 均为 0；
- `battle-entry.png` 的 YMIN/YAVG/YMAX 为 `16 / 149.077 / 235`，不是黑帧。

最终验证为 100/100 个 game host C++ 测试、22/22 个相关 Python 集成测试、
`git diff --check`、Lua 语法和固定 devkitARM 构建通过。ROM/ELF hash 与前一纵切一致。
资源守卫记录：

- `build/resource-guard/20260727-battle-campaign-s43-full-host.json`
- `build/resource-guard/20260727-battle-campaign-s43-final-arm-build.json`
- `build/resource-guard/20260727-battle-campaign-route-s43-complete-02.json`
- `build/resource-guard/20260727-battle-campaign-route-s44-cold-02.json`

## Scenario 44 两阶段目标完整纵切

scenario 44 不再在第一次行动后因“对象槽 1 从未初始化”而误胜。生产 encounter 现在从
mission rules 把 `(4,4)` 的 type 3 铃铛对象放入固定槽 1；击败 Kakashi 后对象仍活动，
战斗继续。任一玩家角色只有在 `(4,3)` 面向下完成行动且 enemy side 已清空时才会在事务
副本中释放该槽，随后原有 `object_slot_inactive(0)` 生成条件判胜。

宿主完整纵切只使用 controller 公共操作，真实执行 Team 7 多角色回合、Kakashi AI、
移动/攻击/击倒、取铃铛、三人结果、成长、campaign merge 和 44→45 路由。原版成长前置
同步为 Sasuke 首次加入时 100 EXP；结果策略按原版训练任务给三人各 125 mission EXP，
不计 Kakashi 的 100 battle EXP。

mGBA 成功证据：

- `artifacts/butano-battle-campaign-route-s44-complete-20260727-02/audit.json`
- frame 5793 / round 12 / phase complete；
- `objective_verified=1`，对象数 0，活动单位 3；
- `125 + 0 + 0 = 125`，Naruto LV3/EXP125/TP2；
- scenario 45，SRAM generation 4 verified；
- controller/player error 为 0。

第二个独立进程从该 SAV 冷启动：

- `artifacts/butano-battle-campaign-route-s45-cold-20260727-02/audit.json`
- scenario 45 / battle 45 / round 1 / unit selection；
- active units 4，load generation 4，default 0；
- 可见战场，不是黑帧。

全量 102/102 game host、相关 Python、Lua、格式与 devkitARM 构建通过。ROM/ELF
SHA-256 为
`f76c36ba28728e8fe05071e0812b315492d735d2022377a1a4fc09c64b6abab5` /
`9179dab6d7066759706256fda3902aab1e0986f50627baed72600492266e9683`。
完整根因、设计、失败边界和产物见
`notes/butano-battle-scenario-44-objective-runtime-20260727.md`。

## Scenario 45 三角色动作与实际击倒者经验纵切

新增宿主纵切从 generation 4 等价 campaign 状态加载鸣人、佐助、小樱和卡卡西，只用
controller 公共输入完成选人、移动、十字手里剑、豪火球、卡卡西 AI、小樱最后击倒、
generated victory、结果、双角色升级、忍具回写和 45→46 路由。它不写 HP、坐标、胜负
或结果字段，也没有 scenario 45 专用 FSM。

奖励证据已纠正：result 108 给三人各 150 mission EXP，卡卡西携带的 100 battle EXP
只归实际击倒者小樱。最终状态为鸣人 LV3/275/TP2、佐助 LV3/0/TP2、小樱
LV3/60/TP2；这与原版 checkpoint 和 150/165 升级阈值精确闭合。全量 game host
103/103 通过，记录在
`build/resource-guard/20260727-battle-campaign-s45-full-host-01.json`。

前三次 mGBA 运行在 frame 5339/round 11 到达结果页后触发内存上限；诊断证明通用驱动
让鸣人击倒卡卡西，实际首名结果为 250，却仍断言原版小樱击倒路线中鸣人的 150，Lua
先退出后 mGBA 才空转到内存上限。修复后的路线经真实战前 UI 装备忍具 1，验证十字
手里剑、佐助动作 16 的单独施术并由小樱收尾，在 frame 5402 完成：

- `cross_shuriken_verified=1`、`sasuke_fire_verified=1`、
  `sakura_finisher_verified=1`；
- 鸣人结果 `150 + 0 + 0 = 150`，LV3/EXP275/TP2；
- 忍具 1 的装备与库存均清空；
- scenario 46，SRAM generation 6 verified；
- controller/player error 均为 0。

独立进程从该 SAV 冷启动到 scenario 46 / battle 9 / round 1 / unit selection，
active units 8 且战场可见。完整记录见
`notes/butano-battle-scenario-45-domain-runtime-20260727.md`。

## Scenario 46 捕获规则纵切

scenario 46 不再沿用早期 battle 9 的普通击倒解释。共享 mission rules 现在声明猫的
捕获身份、允许的技能/忍具来源、禁止的直接攻击来源，以及动作 7 在本任务中的伤害目标
投影。resolver 先产生真实击倒 damage step，capture system 再清空猫槽当前角色 ID，
最后由 generated condition interpreter 判定是否胜利。

宿主完整纵切通过公开 controller 输入完成佐助 2 次、鸣人 2 次、小樱 1 次捕获，并验证
第五次捕获直接进入 outcome、三人 `125 + 60/60/30`、升级和 46→47。独立 mGBA 进程从
上一纵切的 generation 6 SAV 冷启动，真实确认直接攻击被任务拒绝，动作 7 的运行目录为
effect 1 / opponent target 2；脚本不含 `emu:write`。

证据：

- `artifacts/butano-battle-scenario-46-rule-probe-20260727-02/audit.json`
- `build/resource-guard/butano-s46-capture-final-full-host-20260727-01.json`
- `build/resource-guard/butano-s46-capture-final-arm-build-20260727-01.json`
- `notes/butano-battle-scenario-46-capture-runtime-20260727.md`

后续 topology-aware BFS 已在不写内存的前提下自动跑完原版 16×32 地图：第 92 回合
完成五次捕获、三人 `125 + 60/60/30`、generation 7 verified 并推进 scenario 47。
最终证据位于
`artifacts/butano-battle-scenario-46-exact-map-20260727-10/` 和
`notes/evidence/butano-scenario-46-exact-map-runtime-20260727.json`。三种旧贪心追逐
策略分别停在 round 57/45/77；它们没有黑屏或领域错误，但不能形成桥位夹击，现作为
已取代的反证保留在
`artifacts/butano-battle-scenario-46-complete-20260727-01..03/`。

## Scenario 47 真实 3v5 战役纵切

scenario 47 现加载 generated battle 13 的 13×21 地图、Team 7 原始站位与五名
character 33 / LV3 / HP80 敌人。宿主完整纵切只用 controller 公共输入，真实执行
移动、休息、影分身、五次击倒、敌方 AI、condition、三人结果、成长和 47→49；合计
battle EXP 375，三人各得 mission EXP 125，并全部升至 LV5。

GBA campaign adapter 的确定性 seed 已从 battle ID 13 纠正为 scenario ID 47，与宿主
纵切一致。早期 ARM 路线在战斗对白退出后看似“黑屏/不响应”，GDB 实际命中
`bn_sprite_tiles_manager.cpp:921`：脚本 cohort 释放的 400 个 OBJ tiles 仍在延迟回收，
地图 HUD 又在同一 core update 前申请 8 tiles。可见场景现在先释放脚本肖像、文字、单位
和 HUD sprite，执行一次 `bn::core::update()`，再分配地图 cohort；脚本 A 也拥有高于
地图输入的优先级并使用 latch，不能穿透到下一 UI。

清理诊断采样后的最终 mGBA 路线：

- artifact：
  `artifacts/butano-battle-scenario-47-real-map-20260727-22/`
- frame 24898 / round 31 / 五敌全灭；
- `shadow_clone_verified=1`，完成时 4 个活动玩家单位；
- 首名参与者 `125 + 75 + 0 = 200`，Naruto LV5 / EXP85 / TP4；
- scenario 49，SRAM generation 8 / verified 1；
- controller/player error 均为 0；
- ROM / ELF SHA-256：
  `36497840f4c636b39f9495ae5a2429ccda45e2ff1eb5e2c6fc0ae21202216a1a` /
  `aefaa2d3786a1d42e88cb83d2c43254348ddfdff61d165494eb61c036b7c0869`。

只读复审又发现脚本优先分支判断前会提前 `take_presentation_event()`，使对白等待期间的
FIFO 事件被弹出后丢弃。新增失败测试锁定该行为，生产循环现仅在非脚本等待、非活动演出
时取事件；ARM 重建和上述最终 mGBA 路线均在修复后重跑。

本条 mGBA 路线没有受伤到需要休息，故审计保持 `rest_verified=0`；休息恢复由宿主完整
纵切明确覆盖，不能为了标志位而提交无效行动。详细设计、GDB 根因和机读 manifest 见
`notes/butano-battle-scenario-47-runtime-20260727.md` 与
`notes/evidence/butano-scenario-47-real-map-runtime-20260727.json`。

## 未完成边界

- scenario 48 剧情、各战斗前后对白和世界地图串联尚未实现。
- scenario 50 之后的 scenario/battle 映射尚未进入生产路由。
- 47 场内容目录可装载不等于 47 场都已走自然胜负路线。
- 逐技能专属特效、镜头、对象表现和专属 cue 仍未全部验收。
- 导入 WAV SFX 仍因既有重复提交冻结风险保持禁用；S3M BGM 已恢复活动声道和非零录音，
  但这不等于所有逐技能 sound cue 已签发。
- 商店、掉落、补给、Arena 完整 UI/解锁/结算和 Link 通信仍不在此里程碑。

因此，本轮完成的是“真实共享战斗领域的生产章节路由”，不是全游戏功能等价完成。
