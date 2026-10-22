# Butano 战斗表现事务纠错与原 ROM 组件证据（2026-07-26）

## 结论

本轮确认并修复了一个会把“数据驱动战斗”退化成“所有选项套同一段演出”的架构错误：

- 原 ROM 动作模板 `+1` 是 `presentation_binding`，不是“近战标志”；
- 旧 Butano 代码把 `presentation_binding == 1` 直接解释为 `actor_lunges`，所以动作 5
  与火遁 16 都会突进；
- 旧 `battle_combat_presentation` 又按手写动作 ID 表把部分动作归为 `direct`，其余动作
  默认塞入决斗舞台，导致瞬身、召唤和增益也走伪造的决斗链；
- 该手写表已经删除。87 个主动动作和 94 个忍具现在逐项消费生成的
  `action_definition.presentation`、`target` 和 `range`。

新的生产分流为：

```text
BattleSession / resolver
        │ 生成真实 affected units、hit count、前后 HP
        ▼
battle_scene_presentation_event
        │ action id、ninja-tool、presentation binding、目标策略
        ▼
battle_combat_presentation_definition
        ├─ binding 1 + opponent target ──► duel transaction
        │     transition → duel → prep → title/movie → N impacts → result → return
        ├─ binding 5 + self target ──────► self-technique transaction
        │     transition → single actor → prep → title/movie → result → return
        └─ 其他动作 ─────────────────────► map transaction
              map prep/effect/result；不创建 duel/HUD/title
```

这不是截图选择器。`PresentationStep` 每步独立声明 track、resource、固定/逐 hit 时长；
resolver 生成的 `impact_count` 决定 impact 重复次数。玩家和 AI 共享同一
`battle_scene_presentation_event` 与同一表现事务，renderer 不参与伤害、命中、成本或
回合决定。

## 绑定语义与用户可见行为

### 决斗动作

同时满足下列条件才进入决斗：

1. 动作模板 `presentation.animation_family == 1`；
2. 动作模板目标为 `opponent_unit`。

动作 5 与火遁 16 都属于对敌决斗动作，因此两者共享“决斗事务”的结构，但并不共享伤害、
命中次数或资源。动作 5 的原 ROM 运行帧证明它也显示术名栏，不能再作为无标题
`direct` 特例。

突进条件另行计算：非忍具、对敌 binding 1 且模板最大射程不超过 1。动作 5 可突进；
火遁 16 的模板射程为 2，所以保持施术位。该判断不再使用动作名称或手写动作 ID 列表。

### 地图动作

瞬身、召唤、放置物和目前没有独立舞台证据的非攻击忍具留在战场地图。表现事务仍锁住输入
并等待自动步骤完成，但所有步骤都保留 map track，不创建决斗背景、双方 HP 面板或术名
切入。早期把所有“增益”一概归入地图动作的结论已被 2026-07-27 的逐帧证据推翻：
动作 38“白眼”和动作 43“第一　开门　开”都是 `animation_family == 5`、
`self_or_implicit_actor`，并进入只有施术者的独立忍术舞台。修正证据与实现边界见
`notes/battle-self-technique-presentation-evidence-20260727.md`。

`build/butano-combat-binding-runtime-20260726-20/naruto-teleport-result.png` 与
`sakura-clone-result.png` 分别证明动作 2 和动作 1 在真实 GBA 运行时留在同一地图；
最终 audit 在 frame 5775 完成 battle 9 第二回合，控制器继续推进。

## 原 ROM 动作 5 组件证据

输入：

- ROM：`rom/base.gba`
  SHA-256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- checkpoint：`artifacts/runtime-checkpoints/scenario-41-attack-confirmation.ss9`
  SHA-256 `544cffbaea182a55d1963447965d95750984a915cae9877d66d6bc3aebbd560f`
- 脚本：`tools/mgba_trace_action_presentation.lua`
- 组件追踪 run：`build/original-action-presentation-trace-20260726-05/`

脚本不再只保存屏幕和 savestate。它在下列首个断点分别转储 I/O、VRAM、OAM 和 PRAM：

- `0x0806D85C` active action initializer；
- `0x080754A8` action event builder；
- `0x0807FDCC` effect resource builder；
- `0x0807FE2C` effect sequence selector；
- `0x0807C5E8` effect sequence binding；
- `0x0807B8B8` hit presentation；
- `0x08080108` visual object create。

run 05 除语义断点外继续记录四个 BIOS 传输包装器：
`CpuFastSet 0x0809C0DC`、`CpuSet 0x0809C0E0`、
`LZ77UnCompVram 0x0809C0E8` 和 `LZ77UnCompWram 0x0809C0EC`。
`presentation-trace.jsonl` SHA-256 为
`347a4227b81354384a1b03b85ab0c13596b4e74fd7e9364ef04225364ebdf040`。
`tools/analyze_original_action_components.py` 只接受 ROM-backed LZ77 和
PRAM/VRAM 目标，过滤 82 次 WRAM 中转，输出 11 个 GPU 组件；分析器不接受图像作为输入。

命中边界的硬件层解码结果为：

- display mode 0，1D OBJ mapping；
- BG0/BG1 是独立森林/草地战斗背景；
- BG3 是术名栏和双方 HUD；
- OAM 0 是 32×64 目标角色；
- OAM 1 从 32×64 攻击者切换为 64×64 动作对象；
- 背景、HUD、攻击者、目标和命中对象可以独立重建，不需要生产整屏截图。

命中边界区域哈希：

| 区域 | 大小 | SHA-256 |
|---|---:|---|
| I/O | 0x400 | `87fbc0c46de849aacc3d245527c672aba96c0f8145395d654430527134888597` |
| VRAM | 0x18000 | `c74f46fdddd7f4f178d5196220505a8d967f8a3d2cf3347a36d58df3a7d3144f` |
| OAM | 0x400 | `5c446f19aacf6e91024c9b4abf740a0035025ddb9b57ccc7c70f0fc8f1102946` |
| PRAM | 0x400 | `9477fcde50219b29a3e5b408e82e7221cd21856d2a2485b7093e73ed511cbadc` |

静态 `sequel/content/tile-assets/bank.json` 的 79 项接触表显示为角色肖像/术名切入资源族，
不是火焰资源。该 bank 可以支撑 title/cut-in 组件，但不能作为火遁电影证据。

### 原作组件指针与生产接入

动作 5 的实机调用把资源来源和硬件目标闭合为：

| 帧 | ROM 来源 | 硬件目标 | 解压大小 | 组件 |
|---:|---|---|---:|---|
| 51 | `0x0809C614` | `VRAM+0x3800` | 2048 | BG 字形/界面 tiles |
| 51 | `0x085B64E0` | `OBJ+0x7A00` | 1536 | 战斗 HUD OBJ |
| 51 | `0x08329C34` | `BG VRAM+0x4000` | 3072 | 森林决斗 BG tiles |
| 52 | `0x0832A854` | `PRAM+0x000` | 384 | 森林决斗 BG palette |
| 52 | `0x0832A8F8` | `BG VRAM+0x0000` | 640 | 森林决斗 BG tilemap |
| 52 | `0x0812F298` | `OBJ+0x73E0` | 1568 | 数字/标点 OBJ |
| 52 | `0x0812F584` | `OBJ PRAM+0x1C0` | 32 | 数字/标点 palette |
| 69 | `0x083406F0` | `OBJ+0x2000` | 1024 | 动作 5 扬尘序列 |
| 69 | `0x083409D0` | `OBJ PRAM+0x080` | 32 | 扬尘 palette |
| 145 | `0x08342938` | `OBJ+0x2400` | 3840 | 动作 5 命中闪光序列 |
| 145 | `0x08342DC8` | `OBJ PRAM+0x0A0` | 32 | 命中闪光 palette |

除背景 palette 的 color 0 外，11 个 GPU 组件中所有仍应保留到 hit 边界的目标切片均与
命中 VRAM/PRAM 逐字节一致。color 0 在运行时由 `0x7CC3` 改为黑色，符合 BG 透明色/
backdrop 行为，不是资源指针错误。机读生产清单在
`notes/evidence/battle_duel_forest_component_manifest.json`。

`tools/butano/generate_battle_duel_components.py` 直接解压前三个森林组件，按 GBA text BG
tile entry、水平/垂直翻转和 palette bank 重建 256×256 Butano regular BG。
它没有读取任何 PNG 或截图。应用原作 BG0 的 `VOFS=0x1E0` 后，生成图和
`hit-boundary/bg0.png` 的 240×160 可见区域差异像素为 **0**。

生产 renderer 已删除 `_write_backdrop_tiles`、棋盘格和 action-movie 条纹生成器。进入
duel transaction 时，它把现有地图 BG 的 item 原位切换为
`battle_duel_forest`、移除地图 camera 并设置原作滚动；退出事务时恢复当前战场 chunk、
origin 和 camera。这样只占用一个 8bpp BG palette，也不会以整屏 OBJ 拼图占满
32 KiB OBJ VRAM。`naruto-teleport-result.png` 与 `sakura-clone-result.png` 证明地图动作
不切换 BG；火遁四阶段证明决斗 BG、标题、角色、效果和 HUD 仍由独立 track 控制。

### 动作 5 特效序列：从硬件组件到生产运行时

`tools/analyze_original_effect_sequence.py` 对 run 05 的逐帧 OAM dump 做通用解码，只保留
OBJ tile base `0x06012400`、palette bank 5 的对象，并逐帧复核 VRAM/PRAM 内容与 ROM
LZ77 资源一致。结果不是 16 张像素截图，而是 16 个结构化帧：

- 原作帧 148–163，共 16 帧；
- 每帧 1–8 个组件，保留 X/Y、OBJ shape/size、tile offset、水平/垂直翻转和 priority 2；
- 共 14 个唯一 `(tile offset, width, height)` 资产；
- tiles SHA-256
  `6628fdc3365f8d6f16b134797be5f9a1c7cb48662ffeeea634ace058c659bb32`；
- palette SHA-256
  `c00b7ea1d6748f60c387c12d2083da584a65a7e654e61a95bdfe25d1a803dc61`。

`tools/butano/generate_battle_effect_sequence.py` 直接从 `rom/base.gba` 解码 4bpp OBJ
tiles/palette，生成 14 个独立 Butano sprite item 和
`battle_effect_sequence`。16 个原作帧会按连续相同构型压缩成 11 个 keyframe，每个
keyframe 显式保存 hold 时长，总时长仍为 16 帧。机读清单
`notes/evidence/battle_action_05_hit_sequence_manifest.json` SHA-256 为
`231f7a51f2ef95c8462b21d828d28e742ad7bf6131fedfb08b3b9bb7456a6203`。
生成器与运行时均不读取屏幕截图。

参数化追踪 run `build/original-action-presentation-trace-20260726-42-dust/` 又闭合了
命中前扬尘：

- 原作帧 77–135，共 59 帧、最多 3 个独立 OAM 组件；
- tiles `0x083406F0 → 0x06012000`，1024 字节，SHA-256
  `d2bdbe77b17e8ab4031f0a100851dffbbe5a8acf3a8b245ce1b6349d758221d3`；
- palette `0x083409D0 → 0x05000280`，32 字节，SHA-256
  `baf6d16005215ced81fbddd5597f08cbc12441e468e737be9a3fb9a89ac04b67`；
- 59 个原作帧压缩为 26 个带 hold 的 keyframe，总时长保持 59 帧；
- 生成 8 个独立 sprite item，源证据和生产清单 SHA-256 分别为
  `08ed713d32298cda854abcc9aa2f60a2175078deebec597ed5d7575f0d6a3718`、
  `9e0664e01ea7dc851b233233c23465723e1fbeb42f95f2ac1bd5bba68c124f71`。

表现定义把“动作电影资源”和“命中资源”拆成两个字段：动作 5 的 movie 绑定
`action_05_dust_sequence`，impact 绑定 `action_05_hit_sequence`；动作 16 分别绑定
自己的 cut-in、movie 和 hit resource。通用 renderer 每帧按 elapsed time 查找
keyframe，从同一个 sequence
取 0–8 个组件，按原坐标、翻转和 priority 更新固定 8 个 optional sprite，资产变化时
只切换 sprite item。玩家与 AI 仍消费同一个
`battle_scene_presentation_event`；命中序列不拥有 HP、目标、回合或结算写入口。

### 动作 5 施术者动作轨

特效序列不负责移动角色。原作逐帧 OAM/CPUSet 证明动作 5 还有独立施术者轨：

- 原作帧 77–82：攻击者使用 visual slot 0 的动作帧，在屏幕锚点
  `x=52→56` 起步；
- 原作帧 83–135：攻击者隐藏，只保留扬尘对象；
- 原作帧 136–143：攻击者在目标侧以 visual slot 3 frame 0、锚点 `x=134`
  重新入场；
- 原作帧 144–147：切换 slot 3 frame 1、锚点 `x=132`；
- 原作帧 148–155：slot 3 frame 2 与命中效果并行；
- 原作帧 156–163：slot 3 frame 3/4，锚点依次向左移动
  `136→128→120→112→104→100→97`；
- result 段继续使用 slot 3 frame 4，在领域事务完成前保持攻击后姿态。

生产 `battle_actor_choreography` 把上述 87 帧压成 14 个数据步骤，只保存
`stage/frame range + visual slot/frame + visible + screen anchor`。它不保存角色像素、
伤害或目标；renderer 从现有 63 角色 ROM 派生 visual catalog 解析实际 actor 的帧。
因此 battle 9 中执行同一动作的佐助使用佐助自己的角色资产，而不是复用原作抓取中的
鸣人整屏画面。未声明 choreography 的动作继续走通用 pose，不会误套动作 5。

领域集成测试不依赖截图：battle 9 中佐助依次移动
`(9,15)→(7,14)→(7,11)→(7,10)`，第三回合从正式角色目录选择动作 5，锁定
`(7,9)` 敌人，正式 resolver 产生一次 impact、目标 HP 下降并提交单位移动。随后
静音 ARM ROM 自然路线完成同一流程，击倒目标后活动单位 `9→8`，再返回
`unit_selection`；这证明视觉帧挂在真实回合事务之后，而不是由截图选项直接跳转。

### 动作 16 火遁：完整组件纵向切片

动作 16 不再使用程序化火球。原 ROM 自然路线的 cut-in、标题、movie 和命中分别被拆成
独立资源与 renderer track：

- cut-in：决斗背景之上的 dialogue BG、512 像素宽肖像 BG、三个标题 OBJ；
- cut-in fade：原作 frame 300 的 WIN0/BLDCNT/BLDY 契约，窗口只覆盖
  `x=0..240, y=32..112`；
- movie：actor、fire、streak、dialogue 四个 BG，以及独立 title OBJ；
- impact：30 帧、12 keyframe、最多 4 组件、10 个唯一 OBJ 资产；
- result/transition：只等待表现结束并把控制权交回已经提交的领域事务。

`PresentationDefinition` 用有序阶段和 resource ID 绑定上述组件；玩家和 AI 仍经过同一
resolver、`battle_scene_presentation_event` 和 renderer。表现资源不携带 HP、命中次数、
行动资格或回合写入口。生成器直接消费 ROM/GPU 结构化证据，不读取 240×160 合成截图。

最终静音 mGBA 自然路线位于
`build/butano-action16-layer-fade-runtime-20260726-04/`：frame 6145 完成 battle 9、
round 2、`last_resolved_action_id=16`、active units `9→8` 并返回 unit selection。
ROM/ELF SHA-256 为
`a035eeffd4a6e3f25562b92259604e6f03e2919fce5eb1dd4a507122f989f507` /
`343eb2067017cadafdd71f7d2f0969e79eacbd3e5193bc27a447bcb0d6c06a69`。
标题 frame 250、窗口白场 frame 300 和 movie frame 360 三个 240×160 锚点均为
**0/38400 差异像素**。完整证据、地址、哈希、阶段边界和失败处理见
`notes/original-fire-presentation-runtime-20260726.md`。

### 对敌控制术事务

`presentation_binding` 已进一步解除“资源 family 等于场景类型”的错误耦合。
日本版连续录像 950–975 秒证明鹿丸 `影真似の術` 从地图进入双角色森林舞台，显示双方
HUD，播放独立术名/肖像，再回到双角色舞台完成命中判定；本次自然结果为 MISS，最后才
返回地图。生产分类现在同时消费 binding、目标策略和 resolver effect：

```text
family 5 + opponent + effect 14/15/63
  → control_technique
```

动作 23/24/80 因此共用八阶段战斗事务。family 5 的 linked-cleanup effect 11、自己、
友军、占用单位和空格动作不被误分类。场景集成测试证明术名、双角色舞台、impact 与地图
恢复来自同一 `battle_scene_presentation_event`；表现层仍不写 HP、状态或回合。
逐帧产物、哈希、TDD 与未闭合边界见
`notes/battle-opponent-control-presentation-evidence-20260727.md`。

### 对敌爆弹忍具事务

原先所有非投掷忍具都降级为地图效果，其中 family 5、目标为敌方单位的 tool 49–66
缺少场景事务。先前用已缓存 tool 39 状态只改装备字节的 tool 49 实验无效，现已撤回；
从 battle 15 未缓存目录自然构造 tool 49 后，原作明确执行
“转场 → 双角色森林舞台/双方 HUD/忍具标题 → 命中与烟雾 → 返回地图”。第二个状态样本
tool 55 同样进入双角色舞台并显示 `-25%`，证明外层事务不依赖伤害 effect。

生产分类现为：

```text
ninja tool + family 5 + opponent target
  → bomb_tool eight-stage combat transaction
```

分类不读取动作、角色、关卡 ID 或截图；tool 49 的伤害和 tool 55–66 的状态仍分别由正式
resolver 结算。完整原作 trace、缓存陷阱、哈希、TDD 和未闭合的专属组件边界见
`notes/battle-opponent-bomb-tool-presentation-evidence-20260727.md`。

tool 49 已进一步从原 ROM OAM/VRAM/PRAM 生成 7 帧投射物与 111 帧爆炸烟雾组件序列，
而非导入合成截图。正式 battle 9 路线从部署、移动、命令、忍具目录、目标和防御进入该
事务，领域结算使 active units `9→8`，演出结束自动回到 round 3 unit selection。
过程中还发现并修复主动技/忍具裸 ID 碰撞：主动技 43–49 的八门资格现在只应用于
`active_action` 来源，不再错误阻断同 ID 忍具；resolver、browser 和 AI 都以
`(source_kind, id)` 解释动作身份。

## Butano 运行时验收

生产 ROM SHA-256：
`52330dbfa239e420873c41a381261fe875641324a03ed513a7c3fae4038ea63c`；
ELF SHA-256：
`fe68de1cb5bcd47f65ecd29947ac57f04c684f69aea1cac3982fca82bf0b46ac`。

验证：

- 91 个宿主 C++ 程序通过：
  `build/resource-guard/butano-action05-full-host-20260726-40.json`；
- 加入扬尘 hold 与施术者动作轨后，当前 92 个宿主 C++ 程序再次全部通过：
  `build/resource-guard/butano-action05-choreography-full-host-20260726-52.json`，
  guard peak 152.44921875 MiB；
- devkitARM 构建通过，峰值 20.367 MiB：
  `build/resource-guard/butano-action05-effect-arm-build-20260726-34.json`；
- 静音 mGBA battle 9 路线通过，峰值 119.01171875 MiB：
  `build/butano-duel-component-runtime-20260726-28/guard.json`；
- mGBA audit SHA-256：
  `3fe82e6b711f38255db56c2de725a9faaef040bf884be07753044f979a4b8d8d`；
- execution trap 与 memory-write trap 都是 0 字节；
- 火遁 impact 在第 8 帧抓取，受击姿态与目标 `HP 1→0` 同帧可见；
- `sasuke-fire-duel/title/movie/impact` 四个边界均显示 ROM 派生森林组件；
  `naruto-teleport-result` 与 `sakura-clone-result` 均恢复原战场地图。
- 动作 5 的正式 mGBA 路线在 frame 3701、round 3、unit selection 完成：
  `build/butano-action05-effect-runtime-20260726-41/`；audit SHA-256 为
  `db3fe85b583d92a28ff8275d1972d9d48c1cacf5cfc3984c3dd61fabfe3a3db4`，
  guard peak 119.99609375 MiB，control/player error 均为 0，execution/memory-write
  trap 均为 0 字节。
- `impact-00/04/08/12/15` 显示从单点星芒到放射、收束的不同组件构型和
  `HP 1→0`；首帧抓取特意等待 impact telemetry 从 0 进入 1，使 mGBA 截到 renderer
  已提交的首个组件，而不是阶段切换前的术名帧。精确 0–15 帧内容仍由 OAM/VRAM/PRAM
  结构化证据与 host sequence 测试签发。
- 加入扬尘与施术者动作轨后的最终静音路线在 frame 3726、round 3、
  `unit_selection` 完成：`build/butano-action05-choreography-runtime-20260726-51/`；
  audit SHA-256 为
  `c973f7cfd725bca9e3a854ecf45f92ae017aaa5ef2bfca67bc5fe7a31fc3f001`，
  guard peak 119.82421875 MiB。`dust-01/20/58` 分别显示起步、施术者隐藏后的烟尘和
  尾帧 hold；`reentry-60` 显示佐助从目标侧重新入场；`impact-00/08/15` 显示攻击姿态、
  命中组件与目标 `HP 1→0`；`map-restored` 回到同一 battle 9。control/player error
  均为 0，execution/memory-write trap 均为 0 字节。

本次 mGBA 使用 `mute=1`，只验证战斗事务、地图/决斗分流、HP 提交、回合推进和资源安全，
不签发音质。

## 尚未闭合

- 决斗森林、动作 5 已取证组件以及动作 16 的 cut-in/title/movie/hit 已进入 production；
  通用决斗角色动作和 HUD chrome 仍未逐像素闭合。
- 动作 5 的 59 帧扬尘、16 帧命中闪光、逐帧 hold 和施术者
  “起步→隐藏→目标侧再入场→攻击/结果”动作轨已分别进入 production；该闭环只覆盖
  已取证的视觉组件和 battle 9 佐助自然路线。术名字形/HUD chrome 的逐像素差异、音效、
  不同体型角色的动作 5 可用性和其他动作族仍需独立验收，不能扩写成全战斗视觉等价。
- 动作 16 已有自然路线的 I/O/VRAM/OAM/PRAM 组件证据和三个零像素差锚点；动作 17、18
  仍没有各自同级证据，不能因同属 fire family 就复用动作 16 并宣称等价。
- 全 87 动作、94 忍具的专属资源、镜头、音效和 sequence ID 仍需按动作族继续闭合。
- family 5 对敌忍具 49–66 已进入真实双角色事务，但当前仍使用通用舞台；tool 49 的
  投射/爆炸/烟雾组件已从结构化证据生成 production resource；tool 50–66 的逐项资源
  和 tool 55–66 的状态视觉仍未闭合。
- 本轮全部运行时路线均静音；音频撕裂没有被修复或验收。
- 本轮只修正领域结果到表现事务的投影和一条 GBA 路线，不代表完整战斗 Goal 或全关卡
  视觉等价完成。
