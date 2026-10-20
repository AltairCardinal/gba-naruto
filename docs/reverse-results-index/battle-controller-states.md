# 原版战斗主控制器 38 态：命名、38↔24 映射与状态转移表

> 里程碑 **M2**（roadmap §2 `docs/butano-reverse-gap-roadmap.md`）。
> 逆向工作树只读；本文件与 `sequel/content/battle_controller_states.json`、
> `sequel/content/battle_controller_transitions.json` 是重制侧的唯一新增产物。
> 门禁：`tests/test_battle_controller_states.py`。

## 0. 结论摘要

| 项 | 数字 |
| --- | --- |
| 原版顶层分派器非默认状态 | **38**（65,536 输入分母穷尽） |
| 已命名 | **26** |
| `unknown`（显式拒绝定名） | **12** |
| 重制自造 `battle_scene_phase` | **24** |
| 一一对应 / 子相 / 候选 | 11 / 8 / 1 |
| 重制新增、原版无对应 | **4**（`level_up`、`error`、`script_blocked`、`training`） |
| 原版有、重制无对应 | **17** |
| 状态转移表条目 | **24**（8 条静态控制流 + 16 条运行时收据） |

**这份表不是「已实现」。** 重制侧目前仍跑自己的 24 值 `battle_scene_phase` 枚举；
把枚举换成原版状态码是 `butano-sequel/game/` 泳道的事，见 §7。

## 1. 范围与边界（先声明，再看结论）

- **只做战斗场景这一层**：原版战斗主控制器 `0x080732B4..0x0807509C` 内部的
  16-bit 顶层分派器。
- **不外推到嵌套链**：`0x0809xxxx`（演出／消息／事件）那一层有独立 dispatcher
  （`rom-boot-state-dispatcher-cfg-v1`、`rom-story-state-callback-cfg-v1`、
  `rom-event-handler-cfg-v1`），本轮**不覆盖**。表内任何一条都不得向上当成嵌套层的结论，
  嵌套层的任何结果也不得回填进这一层。
- **原版一个顶层态可以盖多个可见子流程**（例如 `0x4100` 同时是目标选择与攻击确认，
  `0x8000` 同时是对白、结果弹窗与胜利演出）。因此「一状态一截图」是错的读法。
- 转移表只收**顶层**转移；发生在嵌套控制器内部的步骤（例如 `0x4100` 里的目标预览）
  不是顶层转移，不进表。

## 2. 证据来源（全部 hash 固定）

| 用途 | 文件（逆向工作树） | SHA-256 |
| --- | --- | --- |
| 已签成果族 manifest | `artifacts/rom-battle-controller-cfg-v1/manifest.json` | `282b4323bf965676a68b5326f2edbbdee35606b987412d351de137b82d50fe63` |
| 成果族 payload | `artifacts/rom-battle-controller-cfg-v1/rom-battle-controller-cfg.json` | `c8b1d1c2068d85912ede1fd35be31f0cf9cb43943beb10f1058d43c65c00449a` |
| 38 项逐项断言 | `tests/test_export_rom_battle_controller_cfg.py` | `412ae14c68d0ccd0a402f199fcaf9fbf1333ab75369fbd6212c4494b2aadf1a7` |
| 命名来源 | `notes/battle-controller-states-20260723.json` | `e0157597e6d7fddb94d036ddfa7a0d2e74fa232450ad08534cd868d6c6fe1336` |
| checkpoint 绑定 | `notes/battle-controller-checkpoint-bindings-20260723.json` | `b12acafd034a842cbe135eb8c057305fba082466ffa4d80a21669f0274e98646` |

- ROM SHA-256：`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 控制器正文 SHA-256：`c9bdc220590a851fa331960bcb32be90eb9ac7248a5cd3dabb9f8afa0b674bc1`
- 分派区 SHA-256：`43fe396227bb6815aeedd5c48783effdb842194634360999d3e42f0ee316e2b1`
- 映射 canonical SHA-256：`ce5e8ea24e274c4456482611609ee90144d31e064fccf0d85bf8f4643f44ac15`

**证据根的约定**：数据文件里每条证据都带 `source_root` 字段。`reverse` = 取自逆向工作树
（本树只读）；`local` = 取自本树镜像的同一份逆向记录。两者只在
`notes/battle-system-restoration-evidence-20260723.md` 上不同——本树镜像那份比逆向工作树
那份多一节（AI 候选场），SHA-256 分别是 `c92a0a57…` 与 `e99ff1c2…`，而本表引用的两行
两边都在，所以引用钉在本树镜像这一份（`source_root: "local"`），其余全部钉在逆向工作树
（`source_root: "reverse"`）。

### 2.1 命名是怎么 join 上去的（重要）

2026-07-23 的状态库存只解出 **36** 态，而且它自己的 dispatcher 解码与已签的 38 态分母
**不一致**：

- 它的 `0x1020`、`0x3310`、`0x9200` 三个标签被逐项断言证明**根本不存在**；
- 它的 `0x1220` 标签指向的 handler，在已签分母里叫 `0x1210`。

所以本轮**一律按 handler 入口地址 join 名字，绝不按旧标签 join**；旧标签只作为
`legacy_label` 保留以便追溯。三条被纠正的对应关系：

| 旧标签 | 已签分母 | handler 入口 |
| --- | --- | --- |
| `0x1020` | `0x2010` | `0x080739D0` |
| `0x3310` | `0x3300` | `0x080740D4` |
| `0x9200` | `0x9110` | `0x08074834` |
| `0x1220` | `0x1210` | `0x080736F8` |

**每一个被命名的状态都必须能被一句逐字引用钉住**：名字的 `quote` 必须原样出现在
hash 固定的源文件里。引不出来 ⇒ `unknown`，不许用「看起来像」代替。

## 3. 38 态状态表

`语义状态` 沿用库存里的证据等级：`static` / `partial_static` /
`static_plus_runtime` / `static_plus_checkpoint_runtime` /
`checkpoint_runtime_transaction` / `static_control_flow`。

| 状态 | handler 入口 | 名字 | 语义状态 | 重制对应 phase | 证据形态 |
| --- | --- | --- | --- | --- | --- |
| `0x0000` | `0x080735CA` | battlefield_entry_sequence | static_plus_checkpoint_runtime | `preparation` | dispatcher_denominator、state_inventory_claim、runtime_checkpoint |
| `0x0010` | `0x08073638` | `unknown` | — | —（原版有，重制无） | dispatcher_denominator、state_inventory_unresolved |
| `0x1000` | `0x0807364A` | `unknown` | — | —（原版有，重制无） | dispatcher_denominator、state_inventory_unresolved |
| `0x1100` | `0x0807367C` | side_end_status_duration_tick | static_plus_runtime | —（原版有，重制无） | dispatcher_denominator、state_inventory_unresolved、static_status_tick_claim、handler_range |
| `0x1200` | `0x080736B0` | `unknown` | — | —（原版有，重制无） | dispatcher_denominator、state_inventory_unresolved |
| `0x1210` | `0x080736F8` | round_transition_script | static_plus_checkpoint_runtime | `turn_banner` | dispatcher_denominator、state_inventory_claim、runtime_checkpoint |
| `0x1220` | `0x080737E6` | `unknown` | — | —（原版有，重制无） | dispatcher_denominator、state_inventory_missing |
| `0x1300` | `0x080738C0` | side_scheduler | static_plus_runtime | `enemy_turn` | dispatcher_denominator、state_inventory_claim |
| `0x2000` | `0x08073940` | player_unit_selection | static_plus_runtime | `unit_selection` | dispatcher_denominator、state_inventory_claim |
| `0x2010` | `0x080739D0` | current_unit_activation | partial_static | `unit_selection` | dispatcher_denominator、state_inventory_claim |
| `0x3000` | `0x08073A04` | unit_action_menu | static_plus_checkpoint_runtime | `action_selection`、`chakra_selection`、`combination_decision`、`command_selection`、`end_confirmation` | dispatcher_denominator、state_inventory_claim、runtime_checkpoint |
| `0x3100` | `0x08073B84` | `unknown` | — | —（原版有，重制无） | dispatcher_denominator、state_inventory_unresolved |
| `0x3110` | `0x08073BA8` | player_move_selection | static_plus_checkpoint_runtime | `move_selection` | dispatcher_denominator、state_inventory_claim、runtime_checkpoint |
| `0x3200` | `0x08073E14` | `unknown` | — | —（原版有，重制无） | dispatcher_denominator、state_inventory_unresolved |
| `0x3210` | `0x08073EB0` | chakra_exchange_result | checkpoint_runtime_transaction | `chakra_selection` | dispatcher_denominator、state_inventory_claim |
| `0x3220` | `0x08074074` | `unknown` | — | —（原版有，重制无） | dispatcher_denominator、state_inventory_unresolved |
| `0x3300` | `0x080740D4` | rest_confirmation | checkpoint_runtime_transaction | `rest_confirmation` | dispatcher_denominator、state_inventory_claim |
| `0x4000` | `0x0807410C` | post_move_action_menu | static_plus_checkpoint_runtime | `command_selection` | dispatcher_denominator、state_inventory_claim、runtime_checkpoint |
| `0x4100` | `0x08074190` | technique_targeting | static_plus_checkpoint_runtime | `target_confirmation`、`target_preview`、`target_selection` | dispatcher_denominator、state_inventory_claim、runtime_checkpoint |
| `0x5000` | `0x08074200` | side_completion_scan | partial_static | —（原版有，重制无） | dispatcher_denominator、state_inventory_claim |
| `0x6000` | `0x080742A4` | player_action_confirmation | static_control_flow | —（原版有，重制无） | dispatcher_denominator、state_inventory_claim |
| `0x7000` | `0x080742E4` | enemy_action_preparation | static_plus_checkpoint_runtime | `enemy_turn` | dispatcher_denominator、state_inventory_claim、runtime_checkpoint |
| `0x8000` | `0x080743D4` | action_resolution_and_outcome | static_plus_checkpoint_runtime | `outcome` | dispatcher_denominator、state_inventory_claim、runtime_checkpoint |
| `0x8010` | `0x08074510` | `unknown` | — | —（原版有，重制无） | dispatcher_denominator、state_inventory_missing |
| `0x9000` | `0x08074550` | facing_selection | static_plus_checkpoint_runtime | `facing_selection` | dispatcher_denominator、state_inventory_claim、runtime_checkpoint |
| `0x9100` | `0x080747E0` | defense_preparation | static_plus_checkpoint_runtime | `defense_decision` | dispatcher_denominator、state_inventory_claim、runtime_checkpoint |
| `0x9110` | `0x08074834` | technique_menu | static_plus_checkpoint_runtime | `defense_selection` | dispatcher_denominator、state_inventory_claim、runtime_checkpoint |
| `0xA000` | `0x0807484E` | `unknown` | — | —（原版有，重制无） | dispatcher_denominator、state_inventory_unresolved |
| `0xB000` | `0x08074870` | `unknown` | — | —（原版有，重制无） | dispatcher_denominator、state_inventory_unresolved |
| `0xC000` | `0x080748AC` | `unknown` | — | —（原版有，重制无） | dispatcher_denominator、state_inventory_unresolved |
| `0xD000` | `0x08074918` | secondary_action_completion | static_plus_runtime | —（原版有，重制无） | dispatcher_denominator、state_inventory_claim |
| `0xE000` | `0x08074988` | `unknown` | — | —（原版有，重制无） | dispatcher_denominator、state_inventory_unresolved |
| `0xE010` | `0x080749CC` | victory_exit_check | partial_static | —（原版有，重制无） | dispatcher_denominator、state_inventory_claim |
| `0xF000` | `0x08074A98` | result_state_router | partial_static | `result` | dispatcher_denominator、state_inventory_claim |
| `0xF100` | `0x08074C2E` | result_page_setup | partial_static | `result` | dispatcher_denominator、state_inventory_claim |
| `0xF200` | `0x08074C7C` | result_unit_enumeration | partial_static | `result` | dispatcher_denominator、state_inventory_claim |
| `0xF300` | `0x08074E48` | result_transition | partial_static | `result` | dispatcher_denominator、state_inventory_claim |
| `0xF400` | `0x08074EE6` | postbattle | static_plus_runtime | `complete` | dispatcher_denominator、state_inventory_claim |

`0x1100` 的 handler 范围另有逆向侧哈希固定收据：
`[0x0807367C, 0x0807368C)`，SHA-256 `2a0c42d909bf81f19ce2246cc1ce386bc70e97bbcf95ab0842263770d4758622`
（`notes/battlefield-object-effect-chain-bindings-20260802.json`）。

## 4. 12 个 `unknown` 态：缺什么证据、怎么补

这 12 条**停止定名**。统一缺两样东西，缺一不可：

1. **handler 级静态断言**——说清这个 handler 读什么、写什么（例如它写哪个 RAM
   字段、它调用哪个已知函数、它在什么条件下写下一个状态码）；
2. **至少一个哈希绑定 checkpoint**，其 controller frame 落在该 handler 的 frame 区间里。

逆向侧补齐时，需要按已签 38 态分母产出，**不要沿用 2026-07-23 的旧标签**
（`0x1020`/`0x3310`/`0x9200` 不存在，`0x1220` 指的是 `0x1210` 的 handler）。

| 状态 | handler 入口 | frame 区间 | 缺什么 |
| --- | --- | --- | --- |
| `0x0010` | `0x08073638` | `0x08073638..0x0807364A` | handler 静态断言 + 落在该区间的哈希绑定 checkpoint |
| `0x1000` | `0x0807364A` | `0x0807364A..0x0807367C` | 同上 |
| `0x1200` | `0x080736B0` | `0x080736B0..0x080736F8` | 同上 |
| `0x1220` | `0x080737E6` | `0x080737E6..0x080738C0` | 同上；且旧库存根本没有这个 handler（只解出 36 态） |
| `0x3100` | `0x08073B84` | `0x08073B84..0x08073BA8` | 同上 |
| `0x3200` | `0x08073E14` | `0x08073E14..0x08073EB0` | 同上 |
| `0x3220` | `0x08074074` | `0x08074074..0x080740D4` | 同上；它与 `0x3300` 相邻，旧库存把两者编号搞混过 |
| `0x8010` | `0x08074510` | `0x08074510..0x08074550` | 同上；旧库存根本没有这个 handler |
| `0xA000` | `0x0807484E` | `0x0807484E..0x08074870` | 同上 |
| `0xB000` | `0x08074870` | `0x08074870..0x080748AC` | 同上 |
| `0xC000` | `0x080748AC` | `0x080748AC..0x08074918` | 同上 |
| `0xE000` | `0x08074988` | `0x08074988..0x080749CC` | 同上；已有一条运行时边（`0xE000 → 0xE010`），但状态本身的语义未闭合 |

## 5. 38 ↔ 24 映射表（重制 phase → 原版状态）

`status` 含义：`direct` = 一一对应；`sub_phase` = 原版顶层态内部的一个子步骤，
重制把它拆成了独立相；`candidate` = 候选对应但未闭合；`remake_only` = 重制新增、
原版没有对应状态。

| 重制 phase | 原版状态 | status | 说明 |
| --- | --- | --- | --- |
| `preparation` | `0x0000` | `direct` | 原版战场入口任务（resume 0x08073616）；重制用 preparation 表示加载完成后的起始相。 |
| `unit_selection` | `0x2000`、`0x2010` | `direct` | 原版先在 0x2000 浏览玩家单位 roster（A 确认后由 0x2010 激活当前单位）；重制合并成一个 unit_selection。 |
| `move_selection` | `0x3110` | `direct` | 原版 0x3110 打开可移动格选择，checkpoint 绑定 0x08073C88 -> 0x0806F718。 |
| `command_selection` | `0x3000`、`0x4000` | `sub_phase` | 原版只有一个按 unit+0xC0 行动类别位分派的菜单态（0x3000）与移动后的精简菜单（0x4000）；重制把同一菜单拆成 command_selection / action_selection / chakra_selection / combination_decision 四个相。 |
| `chakra_selection` | `0x3000`、`0x3210` | `sub_phase` | 查克拉数量在 0x3000 菜单内选择，0x3210 是提交后的查克拉资源交换结果态。 |
| `rest_confirmation` | `0x3300` | `direct` | 原版休息确认在 0x3300（旧库存标 0x3310），确认后跨到回合过渡脚本。 |
| `action_selection` | `0x3000` | `sub_phase` | 0x3000 内按 unit+0xC0 行动类别位选择具体行动；重制把它单独拆成一个相。 |
| `combination_decision` | `0x3000` | `sub_phase` | 连携决定同样落在 0x3000 的行动类别分派里；原版没有独立顶层态。 |
| `target_selection` | `0x4100` | `direct` | 原版 0x4100 同时承载目标选择与攻击确认，checkpoint 绑定 0x08074192 -> 0x08070DF8。 |
| `target_preview` | `0x4100` | `sub_phase` | 目标预览在原版共享的嵌套控制器内，没有独立顶层态。 |
| `target_confirmation` | `0x4100` | `sub_phase` | 目标确认在 0x4100 内；确认成功后原版会经过独立的 0x6000 提交门，重制没有对应相。 |
| `facing_selection` | `0x9000` | `direct` | 原版 0x9000 消费方向输入并写当前单位朝向，checkpoint 直接 resume 0x080745A4。 |
| `defense_decision` | `0x9100` | `direct` | 原版 0x9100 是防御准备提示（checkpoint 绑定 0x080747F4 -> 0x08067158）。 |
| `defense_selection` | `0x9110` | `sub_phase` | 原版防御准备复用通用动作浏览器 0x9110，并在该态的确认边界重新判定类别。 |
| `enemy_turn` | `0x1300`、`0x7000` | `direct` | 0x1300 阵营调度在当前阵营非玩家侧时直接转 0x7000；0x7000 是敌方行动准备。 |
| `outcome` | `0x8000` | `direct` | 原版 0x8000 是玩家与 AI 共用的解析/结果链（对白、结果弹窗、胜利演出都在此态内）。 |
| `result` | `0xF000`、`0xF100`、`0xF200`、`0xF300` | `direct` | 0xF000 是结果路由器，按 result substate 0..3 分派到 0xF100 / 0xF200 / 0xF300。 |
| `level_up` | — | `remake_only` | 原版 38 态里没有闭合的独立升级顶层态；0xD000 与 0xE010 的语义没有闭合到「升级」，不得凭印象对应。 |
| `complete` | `0xF400` | `direct` | 原版 0xF400 进入官方 postbattle/save 包装。 |
| `error` | — | `remake_only` | 原版 38 态没有错误态；未覆盖的输入走默认分支（default_target 479310）。 |
| `script_blocked` | — | `remake_only` | 重制的 script_blocked 是脚本失败/阻塞态；原版 0x1210 是回合过渡脚本（推进态，不是阻塞失败），两者语义不同，不能合并。 |
| `training` | — | `remake_only` | 原版 38 态里没有训练态；训练是重制侧自加的流程。 |
| `end_confirmation` | `0x3000` | `sub_phase` | 原版行动结束确认在 0x3000 菜单内（checkpoint 绑定 0x08073A82 -> 0x08067158）。 |
| `turn_banner` | `0x1210` | `candidate` | 原版 0x1210 已闭合的内容是回合边界对白/脚本，横幅本身没有独立状态；候选对应但未闭合，不作定论。 |

**原版有、重制无对应（17 项）**：`0x0010`、`0x1000`、`0x1100`、`0x1200`、`0x1220`、
`0x3100`、`0x3200`、`0x3220`、`0x5000`、`0x6000`、`0x8010`、`0xA000`、`0xB000`、
`0xC000`、`0xD000`、`0xE000`、`0xE010`。

其中两条是**重制真的缺了状态**（不是命名问题）：

- `0x6000`（玩家提交门）：原版在目标确认（`0x4100`）与共享解析（`0x8000`）之间有
  一道独立提交门，重制把它折进 `target_confirmation` 流程里了；
- `0xD000` / `0xE000` / `0xE010` 这条结果／胜负仲裁链：重制没有对应的顶层态。

## 6. 状态转移表（24 条）

形态定义：

- `static_control_flow` —— 某条被引用的指令直接写下下一个顶层状态；
- `runtime_checkpoint_crossing` —— 两个哈希绑定的原版 checkpoint 显示状态变化；
- `runtime_transaction` —— 哈希绑定的单输入重放，带领域资源差分；
- `runtime_checkpoint_sequence` —— 跨多个状态的哈希绑定 checkpoint 链；
- `runtime_checkpoint_matrix` —— 同一条边上的哈希绑定样本矩阵。

| from | to | 形态 | 输入 | 守卫条件 |
| --- | --- | --- | --- | --- |
| `0x1300` | `0x7000` | static_control_flow | none（帧边界） | 当前阵营（RAM 0x0202680E）不是玩家侧 |
| `0x7000` | `0x8000` | static_control_flow | none（帧边界） | 已选中 affiliation 1 单位且行动上下文已拷进共享缓冲 |
| `0x4100` | `0x6000` | static_control_flow | A（确认） | 目标确认成功 |
| `0x6000` | `0x8000` | static_control_flow | A（确认） | 玩家确认界面完成，行动交给共享 resolver |
| `0xF000` | `0xF100` | static_control_flow | none（帧边界） | result substate == 0 |
| `0xF000` | `0xF200` | static_control_flow | none（帧边界） | result substate == 1 |
| `0xF000` | `0xF300` | static_control_flow | none（帧边界） | result substate == 2 |
| `0xF000` | `0xF400` | static_control_flow | none（帧边界） | result substate == 3 |
| `0x2000` | `0x3000` | runtime_checkpoint_crossing | A（确认） | 选中玩家单位行动未用尽（unit+0xC0 低字节 0）且 affiliation 0 |
| `0x2000` | `0x2000` | runtime_checkpoint_crossing | A（确认） | 选中单位已用完行动（unit+0xC0 低字节 16），确认被拒 |
| `0x2000` | `0x2000` | runtime_checkpoint_crossing | A（确认） | 选中的是护送/目标单位（action flags 144、action state 2），确认被拒 |
| `0x3000` | `0x3210` | runtime_transaction | A（确认） | 查克拉命令提交：行动单位付 HP、获得查克拉（134→119 HP，4→5 查克拉） |
| `0x3300` | `0x1210`（备选 `0x1220`） | runtime_transaction | A（确认） | 休息确认提交：行动单位回血并完成本次行动（24→41 HP，查克拉不变，行动标记 0→32） |
| `0x4100` | `0x3000` | runtime_checkpoint_crossing | B（取消） | 玩家取消目标选择退回行动菜单 |
| `0x3000` | `0x3000` | runtime_checkpoint_crossing | B（取消） | 玩家取消移动/行动菜单 |
| `0x4100` | `0x4100` | runtime_checkpoint_crossing | B（取消） | 玩家在嵌套技能/目标控制器内取消 |
| `0x8000` | `0x9000` | runtime_checkpoint_crossing | A（确认演出） | 共享 resolver 提交瞬身：查克拉、落点、行动标记在同一边界写入 |
| `0x4100` | `0x8000` | runtime_checkpoint_sequence | A（确认） | 最终确认成功；此时预览阶段尚未提交任何资源 |
| `0x8000` | `0x9000` | runtime_checkpoint_matrix | A（确认演出）/ 零输入审计 | resolver 提交结果：伤害写目标 HP，替身写目标位移 |
| `0x4100` | `0x9000` | runtime_transaction | A（确认） | 手里剑确认：装备忍具槽被消耗、行动标记置位 |
| `0x9100` | `0x9100` | runtime_checkpoint_crossing | Up（选「是」） | 防御提示选「是」，只有嵌套菜单选择变化 |
| `0x9100` | `0x9110` | runtime_checkpoint_crossing | A（打开已习得动作列表） | 防御提示选「是」后打开通用动作浏览器 |
| `0x9110` | `0x9110` | runtime_checkpoint_crossing | A（确认动作） | 选中的动作不是防御/回避系，确认被拒 |
| `0xE000` | `0xE010` | runtime_checkpoint_crossing | none（帧边界） | 战斗目标达成：结果标志 0→1 |

**唯一带歧义标注的边**：`rest_confirmation_commit`（`0x3300 → 0x1210`）。
2026-07-23 的库存只解出 36 态，它的 `0x1220` 覆盖整个
`[0x080736F8, 0x080738C0)` 帧区间，而已签的 38 态分母把这一段拆成 `0x1210`
（入口 `0x080736F8`）和至今未命名的 `0x1220`（入口 `0x080737E6`）。表里记 `0x1210`
并把 `0x1220` 显式列为备选；**在回合教程 checkpoint 的 frame（`0x08073780`）按 38 态
分母重新绑定之前，这条边不能当成闭合结论**。

## 7. 交给 `butano-sequel/game/` 泳道（W2）的动作清单

本轮**没有**改 `butano-sequel/game/` 下任何文件。下面是应由 W2 接手、且能直接用本表
落地的常量替换建议（**不是**本轮的既成事实）：

1. **新增原版状态码常量**：在
   `butano-sequel/game/include/konoha/battle_scene_controller.h` 里加一组
   `constexpr std::uint16_t`（或 `enum class battle_original_state : std::uint16_t`），
   取值就是表里的 16-bit 状态码（`0x0000`…`0xF400`），并让
   `sequel/content/battle_controller_states.json` 成为唯一真源（生成头或
   `constexpr` 表）。**注意原版是 16-bit，重制现在是 `std::uint8_t` 24 值。**
2. **替换自造枚举**：把 `battle_scene_phase` 的 24 个自造值换成原版状态码；
   重制新增、原版无对应的 4 个（`level_up`、`error`、`script_blocked`、`training`）
   要么单列为「重制扩展态」并在名字上带前缀（例：`remake_only_level_up`），
   要么在 Butano 侧显式放弃——但**不能继续叫 `battle_scene_phase`**，否则门禁里的
   38↔24 映射会失去意义。
3. **补原版有的、重制缺的顶层态**：`0x6000`（玩家提交门）、
   `0xD000`/`0xE000`/`0xE010`（结果与胜负仲裁链）目前在重制里没有对应相；
   合并成现有 phase 是可以的，但要在代码里留注释说明它对应原版哪几个状态。
4. **顺序类语义不能改**：原版顺序是「横幅 → 移动选格 → 战场 → 命令菜单」
   （见 roadmap M1），而重制目前是反的；换成原版状态码时必须同时把顺序改回原版顺序。
5. **不要把本表当成已实现**：表里 12 个 `unknown` 态在重制侧目前没有行为定义；
   在逆向侧补齐证据前，重制侧对这些状态码只能空转（`default` 分支）。

## 8. 复跑

```bash
cd /Users/altair/github/gba-naruto
/usr/local/bin/python3 -m unittest tests.test_battle_controller_states -v
/usr/local/bin/python3 tools/measure_butano_reverse_gap.py
```

门禁**失败关闭**：逆向工作树缺 manifest、缺状态项，或 hash 固定的源文件对不上，
测试直接失败并指名缺哪一条。逆向工作树路径可用环境变量
`KONOHA_REVERSE_ROOT` 覆盖，默认 `/Users/altair/github/gba-naruto-reverse`。

## 9. 相关记录

- 逆向侧成果族：`rom-battle-controller-cfg-v1`（manifest + payload）
- 逆向侧逐项断言：`tests/test_export_rom_battle_controller_cfg.py`
- 逆向侧命名来源：`notes/battle-controller-states-20260723.json`
- 逆向侧 checkpoint 绑定：`notes/battle-controller-checkpoint-bindings-20260723.json`
- 逆向侧系统还原记录：`notes/battle-system-restoration-evidence-20260723.md`
- roadmap：`docs/butano-reverse-gap-roadmap.md`（§2 M2、§4 验收总表、§5 边界）
- 差异底账：`artifacts/butano-reverse-gap-v1/gap.{json,md}`
