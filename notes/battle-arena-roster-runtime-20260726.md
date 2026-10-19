# 竞技场双方阵容到统一战斗运行时（2026-07-26）

## 结论

原 ROM 的 battle 31 variant 1 与 battle 32–38 不是“战役三人队伍加三名 NPC”，而是竞技场
双方各自选择至多三名角色的六席模板。Butano 现在用显式的
`battle_arena_match_roster` 表达玩家队与对手队，并把双方角色、等级、技能 progression
和九格忍具接入已有的部署、scenario loader、controller、AI、resolver 和回合循环。

这项实现不创建第二套“竞技场战斗规则”，也不以截图或固定角色数组冒充战斗。竞技场只负责
构造同一战斗域的初始参与者；进入战斗以后，双方与战役关卡共用同一个
`battle_encounter_runtime`。

## 原 ROM 证据

基准 ROM：

- SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 编队表：file `0x5461C4`，每条 `0xB8` 字节。

battle 32–38 的活动记录均为六个动态 selector：

| 席位 | selector | affiliation | 所有者 |
|---|---:|---:|---|
| 0 | `0xFF` | 0 | 玩家队 1 |
| 1 | `0xFE` | 0 | 玩家队 2 |
| 2 | `0xFD` | 0 | 玩家队 3 |
| 3 | `0xFC` | 1 | 对手队 1 |
| 4 | `0xFB` | 1 | 对手队 2 |
| 5 | `0xFA` | 1 | 对手队 3 |

精确活动记录范围：

| battle | file range |
|---:|---|
| 32 | `0x57B748..0x57BAE0` |
| 33 | `0x57D1F4..0x57D58C` |
| 34 | `0x57ECA0..0x57F038` |
| 35 | `0x58074C..0x580AE4` |
| 36 | `0x5821F8..0x582590` |
| 37 | `0x583CA4..0x58403C` |
| 38 | `0x585750..0x585AE8` |

battle 31 variant 1 也使用同一 3v3 模式；variant 0/2 则是剧情固定单位与动态席位混合，
不能整体归类为竞技场模板。

攻略只用于交叉验证入口语义，不取代 ROM 字节证据：

- GameFAQs 指南描述通关后开放 Arena/Link，Arena 先选区域，再选择至多三名角色；
- Wave Gamer 的流程记录为“选择场景 → 选择对手（可留空）→ 选择己方角色 → 开战”，
  多人 Link 是另一入口。

来源：

- <https://gamefaqs.gamespot.com/gba/918717-naruto-konoha-senki/faqs/29486>
- <https://wavegamer.wordpress.com/2012/11/22/review-naruto-konoha-senki/>

## 领域模型与所有权

```text
Arena 场景/选择 UI（模式所有者）
        │
        ├── player[3]: progression + equipped_tools[9]
        └── opponent[3]: progression + equipped_tools[9]
                        │
                        ▼
             apply_battle_arena_scene_policy
                        │
                        ▼
        BattleDeploymentFlow ──► 可见六席部署
                        │
                        ▼
        BattleScenarioLoader ──► BattleUnitInstance
                        │
                        ▼
 BattleEncounterRuntime / Controller / AI / Resolver / TurnFlow
```

关键约束：

- 每方容量固定为三，至少各有一名活动角色；
- inactive combatant 会显式关闭对应席位，不会制造虚假角色；
- 角色 ID、角色 active 标记、等级 `1..50`、progression 初始化和九格忍具均在写入前校验；
- 整份 policy 以草稿构造，任一校验失败时调用者保持零写；
- 玩家与对手可以选择相同角色；两边的等级、技能状态和装备来自各自 combatant，互不共享；
- scenario policy 保存的是指向 roster 内记录的非拥有指针，因此 roster 必须由模式层持有到
  deployment 和 session load 完成；生产 fixture 将 roster 与 request/config 放在 EWRAM，
  每次进入时原地重建；
- `arena_roster` 与 `campaign` 不能同时提供，避免两个模式争用同一动态 selector。

## TDD

红阶段：

- `test_battle_arena_roster.cpp` 先因缺少 `battle_arena_roster.h` 编译失败；
- wiring 测试先因 request 没有 arena roster、battle 32 仍使用原始六角色夹具而失败；
- 生命周期测试先发现 `battle_runtime_scene_config` 和竞技场 roster 留在 GBA 函数栈；
- 资源生命周期测试先发现脚本立绘分配前没有提交单位 OBJ tile 的延迟回收。

绿阶段覆盖：

- 双方 2v2、其余两席禁用，部署预览和最终 loader 得到相同四活动单位；
- 玩家 Naruto LV10/tool 1 与对手 Naruto LV25/tool 93 同时存在且状态独立；
- 无对手、非法等级、非法忍具均返回明确错误且 policy 零写；
- battle 32 fixture 的真实阵容为玩家 `1/2/3`、对手 `12/35/1`，不再使用
  `{1,2,3,35,35,35}` 截图夹具；
- 全六单位完成第 1 回合，AI 的第二指令选择 action 3 替身术，并进入第 2 回合。

## mGBA 故障与修复

最初实现把六份完整 progression 复制进 policy/request/config，battle 32 在玩家第三人结束
行动后的脚本边界停住。把大对象改为 EWRAM 持有和非拥有指针后，SP 从 `0x03004C94`
恢复到 `0x030054EC`，但不同角色/等级的最终阵容仍停在：

- phase 10；
- scene frame 218；
- `render_stage=1`；
- `IE=1, IF=1, IME=1`。

这排除了“模拟器默认音频设置”“IRQ 被关闭”和等级/被动计算。根因是脚本边界在同一帧：

1. reset 六名单位的 sprite/tile handle；
2. 立即为对话 portraits 分配 OBJ tile；
3. Butano 要到下一次 `bn::core::update()` 才真正回收已释放的 OBJ VRAM block。

旧夹具只有四种视觉身份，未越过容量边界；真实双方阵容有五种视觉身份，因此稳定触发资源
不足。修复是在确实释放过单位 component 时，先执行一次 `bn::core::update()`，再分配
portrait。它是表现资源生命周期修复，不修改战斗阶段、伤害、AI 或回合结果。

被取代的失败证据保留在：

- `artifacts/butano-arena-roster-b32-runtime-20260726-01/`
- `artifacts/butano-arena-roster-player-l1-b32-runtime-20260726-02/`
- `artifacts/butano-arena-roster-all-l1-b32-runtime-20260726-03/`
- `artifacts/butano-arena-roster-final-b32-runtime-20260726-04/`
- `artifacts/butano-arena-roster-irq-diagnostic-b32-runtime-20260726-05/`

最终成功证据：

- `artifacts/butano-arena-roster-portrait-reclaim-final-b32-runtime-20260726-06/`
- `audit.json`：deployment `[1,2,3,12,35,1]`、active 6、round 2、phase 1、
  `ai_substitution=true`、controller/player error 均为 0；
- `register-samples.jsonl`：第 896 帧观测 AI secondary
  `kind=1/action=3/score=1`，第 1150 帧进入 round 2；
- 最终 SP `0x030057CC`，不再停在 portrait allocation 边界。

## 最终验证

- 全量宿主 C++：83/83；
- 清洁 devkitARM：exit 0，无代码 warning/error，peak 114.598 MiB；
- 静音 mGBA：exit 0，guard peak 101.402 MiB，第 1162 帧完成审计；
- ROM SHA-256：
  `70953261605c15feabd3d356598bddb3dd4bf6ee8d2fcc5aded101624a434833`
- ELF SHA-256：
  `96c5b2e17373bddc8f2e7723dc2d65c4f4ba659b78fcb5dff21fa6cc94902861`
- `rom/base.sav` 保持：
  `2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc`

## 边界

- 已闭合的是竞技场“双方阵容 → 同一战斗域”的架构与 battle 32 运行夹具；
- 竞技场场景选择、角色选择 UI、通关解锁、胜负结算入口尚未实现；
- Link 的远端输入、同步和断线处理是独立网络/通信层，本项未实现；
- 完整背包库存与战斗内忍具消耗回写、逐技能专属表现、非静音音频和完整章节脚本仍未闭合；
- 因此本里程碑不能宣称整个战斗 Goal 或全游戏功能等价已经完成。
