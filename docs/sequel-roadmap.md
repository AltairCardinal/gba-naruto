# 木叶战记续作 Roadmap

## 目标

把当前仓库从"已建立续作工作区和逆向基础"推进到"可以持续生产续作内容并稳定回写 ROM"的状态。

**执行策略：先完成逆向工程，再建网页编辑器。**

---

## 现状总览

> 2026-07-13 当前调查闭合审计为 32/32：23 个有效数据 bank 均通过元数据和
> 基准 ROM fidelity，另 9 个是带负证据、空 entries、禁写回的 `disproved`
> tombstone。分布为 runtime 13 / code 10 / static 0 / disproved 9。32/32 只表示
> bank 身份调查闭合，不等于所有字段语义、运行时路径与端到端写回均已完成；
> save-state 已由真实 UI save 与冷启动恢复升级为 runtime_verified。

### 2026-07-13 最新执行边界

- 2026-07-23 用户否决了 Butano scenario 41 的截图/固定选项拼接实现：它不产生真实战斗规则，不能称为战斗架构或功能等价实现。纠错后，63 条单位、87 条主动动作、94 条忍具已经生成到 Butano 固定内容表，活动战斗阶段改为地图、独立单位/游标和领域快照 UI 的组件渲染，玩家与敌方多动作 AI 共用事务式 resolver；单关 2580 帧路线已通过。该闭环只解除“截图伪战斗”阻塞，不代表完整等价；45 条被动、剩余 handler、完整回合/AI/目标规则以及召唤、多角色、复合目标和护送样本仍必须继续实现和验收。证据审计见 `notes/battle-system-restoration-evidence-20260723.md`，实现/运行记录见 `notes/butano-battle-domain-rewrite-20260723.md`。
- 2026-07-23 主动动作显示身份已从诊断截图中剥离为受 ROM 名称字节约束的 87 项 overlay：78 项逐字确认，9 项明确待二次校字；主控制器 `0x080732B4..0x08075082` 的 36 个分派状态完成结构库存，已命名的 ROM 锚点只限阵营扫描、玩家选择、行动类别、MOVEDONE、胜负/结果和 postbattle。其余状态不得强行套入候选 Butano 状态图。机读证据为 `sequel/content/battle-config/action-identities.json` 和 `notes/battle-controller-states-20260723.json`。
- 2026-07-23 进一步把 18 个 `.ss9` 边界绑定到协作任务栈中的真实控制器帧：14 个 scenario 41 样本覆盖 `0x3110` 移动、`0x3000/0x4000` 菜单、`0x9200` 术菜单、`0x4100` 目标/确认、`0x9000/0x9100` 面向/防御、`0x8000` 结果与 `0x1220` 回合脚本；4 个 scenario 45/50 样本又证明敌方 `0x7000` 行动准备与玩家 `0x6000` 提交门共同汇入 `0x8000` 解析。分析要求有效 Thumb BL、外层 controller caller、checkpoint 哈希及阵营/当前单位字段。证据见 `notes/battle-controller-checkpoint-bindings-20260723.json`。旧 implementation plan 的“已实现”状态已撤销并标记为不得继续执行。
- 2026-07-23 多单位选择新增四次连续单输入 L 与一次受守卫 R 的哈希绑定：六个 checkpoint 始终位于 `0x2000`；L 的本场完整环绕为鸣人→猫→小樱→佐助→鸣人，R 为鸣人→佐助。每次只在两个有效单位的 `unit+0xC1` 间转移选择标记，当前行动单位指针保持空、战斗控制区零差异。它证明 roster 游标是确认前状态，并证明猫这类目标代理也能进入 roster。R 运行峰值 tree RSS 50.77734375 MiB，owned PGID/listener 清理通过。证据为 `notes/battle-unit-selection-bindings-20260723.json`。
- 2026-07-23 单位资格新增五次受守卫单输入对照：L/R 可从唯一未行动的小樱浏览到已行动佐助和护送目标，说明 roster 不预过滤命令资格；A 只让小樱从 `0x2000→0x3000` 并绑定 actor，佐助/护送目标的 A 均保持 `0x2000`，且单位池、战斗控制区、菜单块零差异。资格层因此位于确认边界，死亡/失能/召唤物与跨关卡差异仍待闭合。最大峰值 tree RSS 50.79296875 MiB，owned PGID/listener 全部清理通过。证据为 `notes/battle-unit-eligibility-bindings-20260723.json`。
- 2026-07-23 AI 规划器新增三段函数哈希与直接调用库存：`0x080851F8` 枚举候选，在 `0x080855A2` 调用格评分，并只在 `candidate_score > best_score` 时复制 20 字节候选；`0x08085160` 的局部评分已闭合面向 +50、地形 +200/+100 和 `(rng*50)>>15` 扰动；`0x08085610` 证明网格候选有边界/占用/标志过滤和严格择优。目标优先级、伤害效用、任务目标权重及未命名 helper 仍未闭合，不能把局部常量冒充完整 AI。证据为 `notes/battle-ai-planner-static-20260723.json`。
- 2026-07-23 63 个单位模板新增受 ROM 名称字节约束的显示身份 overlay：55 项逐字确认，8 项 `[22,23,24,25,26,44,53,56]` 明确待二次校字；生成目录已把每个单位的显示身份、基础数值、15 个主动槽、24 个被动槽与 87 主动动作/45 被动项关联。该结果闭合模板成员关系，但不把模板槽误报为任意剧情/等级下的自然菜单资格。证据为 `sequel/content/units/unit-identities.json` 和 `notes/battle-content-catalog-20260723.json`。
- 2026-07-23 事务边界新增四组原 ROM 哈希绑定证据：scenario 45/50 的三个 B 取消路径对完整单位池、忍具库存和战斗控制区均为零差异；scenario 50 瞬身术只在 `0x8000→0x9000` 时把当前查克拉 `1→0`、坐标 `(5,6)→(3,5)` 和行动标记 `0→16` 一起提交。候选 `ActionDraft` 因而有了运行时依据，但其他成本类型、AI 与失败分支仍未闭合。证据为 `notes/battle-action-transaction-bindings-20260723.json`。
- 2026-07-23 资源事务新增三组哈希绑定：battle 15 查克拉命令在 `0x3000→0x3210` 把 HP `134→119`、查克拉 `4→5`；battle 13 休息在 `0x3310→0x1220` 把 HP `24→41`、保持查克拉并把行动标记 `0→32`；同一场的十字手里剑在 `0x4100→0x9000` 清除行动单位首个战斗内装备槽 `unit+0xB1`，但不改 HP、查克拉或持久忍具库存区。它证明忍具 loadout/背包与本场可用槽位必须分层建模，但仍不构成通用恢复公式或完整装备槽布局。证据为 `notes/battle-resource-transaction-bindings-20260723.json`。
- 2026-07-23 效果解析新增普通命中/替身两条 `0x4100→0x8000→0x9000` 哈希链：普通分支目标 HP `46→46→32` 且不位移；替身分支佐助查克拉 `2→2→0`、目标 HP `110→110→110`、坐标 `(4,6)→(4,6)→(3,5)`，目标 `unit+0x154` 为 `0→22→0`。替身反应在确认态先暂存，成本、行动账本和位移到解析边界才原子提交；这证明预览不能直接扣血、替身必须是 resolver 反应分支。通用公式、多段、防御/反击、联携和状态优先级仍待闭合。证据为 `notes/battle-effect-resolution-bindings-20260723.json`。
- 2026-07-23 替身暂存新增 29 个 `0x8000→0x9000` 哈希绑定解析边界交叉矩阵：18 次普通伤害在解析入口均为目标 `unit+0x154=0`，随后扣 HP、不位移；11 次替身均为 `unit+0x154=22`，随后 HP 不变、位移并清零。该结果排除单一槽位/单次样本巧合，但仅覆盖 battle 15 的 character 35，不证明全局反应枚举、触发公式、落点或防御/反击/多段优先级。证据为 `notes/battle-reaction-matrix-bindings-20260723.json`。
- 2026-07-23 防御准备新增 `Up→A→A` 单输入链：从 `0x9100` 选择“是”进入 `0x9200` 共用动作列表；火遁术虽可浏览，但确认时显示“只能选择防御系・回避系的术・忍具”，仍在 `0x9200`。三步 actor/行动标记不变，单位池和战斗控制区零差异，只改菜单状态；说明类别资格在确认边界而非列表生成时验证。最大峰值 tree RSS 50.875 MiB，owned PGID/listener 清理通过。证据为 `notes/battle-defense-preparation-bindings-20260723.json`。
- 2026-07-23 防御类别负例补充 scenario 43 鸣人 `Down→A`：影分身术在防御动作浏览器可见，但确认后同样显示类别拒绝并保持 `0x9200`，单位池与战斗控制区零差异。不能按动作名称推断防御/回避类别。两次守卫峰值为 50.87109375/50.8046875 MiB，owned PGID/listener 清理通过；最终状态 SHA-256 为 `fb3c96d6eac89402275d1404b7a354323a6baa86d8f385d5dae6be084a75ca51`。
- 2026-07-23 成功防御新增写轮眼受控 A/B 链：只把佐助 action 15 等级 `0xFF→1`、当前查克拉 `1→5`，完整 EWRAM 审计确认无第三处前置修改。确认预览保持 `0x9200` 且单位池零差异；提交进入 `0x1220` 时查克拉 `5→3`、`unit+0xD4=0x10` 与 `unit+0xD5=15` 原子写入。相邻 character 35 进入 `0x8000` 攻击时 `+0xD4` 清零，出现写轮眼演出，佐助 HP 始终 134、坐标始终 `(5,6)`。该样本证明一次性回避反应，不证明反击、多段或其他防御动作优先级。证据为 `notes/battle-defense-reaction-bindings-20260723.json`。
- 2026-07-23 基础伤害/命中公式新增静态与自然样本绑定：`0x080754A8` 在演出前按攻击力、攻击属性、`100-5×isqrt(防御)` 与 150% 会心生成普通/会心、计防御/无视防御四候选；`0x08076034` 以模板成功率加敏捷差一半（向零截断、上限 99），对每个 hit 独立比较 `(rng×100)>>15`。自然十字手里剑 power 6、hit count 3 生成 `[9,13,11,16]` 四候选，HP `49→31` 唯一对应两次普通 9 点命中和一次 miss；界面 `6×3` 不是最终伤害。状态/地形修正仍待分支闭合。证据为 `notes/battle-damage-hit-bindings-20260723.json`。
- 2026-07-23 会心/无视防御新增静态与两个单字节受控运行时闭环：基础命中后依次查询被动类型 `0x0C` 与 `0x19`；会心率为 `min(100, passive_value+10)` 并写 flag 2，无视防御率为 `passive_value` 并 OR 4。100% 会心样本得到 `[2,2,2]`、HP `49→10`（`13×3`），100% 无视防御样本得到 `[5,5,5]`、HP `49→16`（`11×3`）；证明 RNG 顺序为命中→会心→无视防御且按条件消耗。证据为 `notes/battle-hit-modifier-bindings-20260723.json`。
- 2026-07-23 反应优先级新增原 ROM 预处理器与两类运行时闭环：`0x080763E0` 先查 blocker、再查 reaction，且只在非零 hit 上触发；写轮眼 `0x10` 替换首个有效 hit 并把事件截断到该 hit，自然十字手里剑基线以队列 hit count 3 逐 hit 判定并得到“两次普通命中、一次 miss”。火弹受控前置仅装备战斗内忍具 46，原版 UI 提交后写入 `unit+0xD4=0x19/+0xD5=0xAE`；敌人攻击队列携带该反应，结算保持佐助 HP `134→134`、把原攻击者 HP `17→3`，并清除反应元数据。静态递归调用与 HP 结果共同证明反击是 source/target 反转的嵌套共享解析，不是表现层反伤。其他反应家族与自然到期仍待闭合。证据为 `notes/battle-reaction-priority-bindings-20260723.json`。
- 2026-07-23 通用状态持续时间新增 side-end 静态/运行时闭环：控制器状态 `0x1100` 在切换阵营前调用 `0x0806C308`，遍历单位槽 1–12 的 16 个、步长 8 的状态槽；同一 checkpoint 的两字节受控对照证明持续时间 `1→0` 时完整移除状态，`2→1` 时保留状态，随后 side 才从 `0→1`。一次性 reaction 消费仍属于攻击 resolver，不与通用 tick 合并；状态专属周期效果、属性修正和 duration-zero 语义仍待闭合。证据为 `notes/battle-status-expiry-bindings-20260723.json`。
- 2026-07-23 状态存储新增三函数静态哈希绑定：每个单位的 `+0xD4..+0x154` 是 16×8 活动状态区，`+0x154..+0x1D4` 是 16×8 已移除状态事件区；自然到期把完整记录移入后者再清活动码，一次性反应消费只清活动码。查询按 code 低 6 位首匹配，普通 code 替换同类旧记录，特殊 `0x3F` 只在旧 duration 非零且短于新 duration 时替换。参数字段和 code-specific 玩法仍待消费者链闭合。证据为 `notes/battle-status-storage-bindings-20260723.json`。
- 2026-07-23 状态消费者新增全 ROM 直接引用库存：查询函数共有 96 个 BL 引用、写入函数 21 个；95 个立即数查询覆盖 25 个 code，现有 blocker/reaction 各 6 个，只覆盖 12 个。剩余 13 个 code 已按稳定 ID 列出，仍需逐调用数据流和运行样本闭合，不能把完整状态架构缩减成防御反应表。证据为 `notes/battle-status-consumer-bindings-20260723.json`。
- 2026-07-23 状态 `0x0E` 新增共享 resolver 静态闭环：解析器从主目标活动状态记录 `+4` 读取联动单位，以相同 source/action type/amount 和防递归参数 `[0,0,0,1]` 先递归结算，再回到主目标 HP 分支；这是有序传播而非重定向，不能实现成复制总伤害。其可见玩法名称和自然演出仍保持 unresolved；原始 13 个非 blocker/reaction code 中还剩 12 个 code-specific 行为待闭合。证据为 `notes/battle-status-linked-resolution-bindings-20260723.json`。
- 2026-07-23 状态 `0x0D` 新增 resolver queue 静态闭环：非反应 event 在解析前依次从 source/target 直接消费该状态且不产生 removed event；target 消费还清 `unit+0xC0` 的 raw bit `0x100`。六个已知 reaction event 跳过此门。状态显示名与 bit 业务名保持 unresolved；连同 `0x0E`，原始 13 个非 blocker/reaction code 已闭合两条操作链，剩余 11 个。证据为 `notes/battle-status-participant-consumption-bindings-20260723.json`。
- 2026-07-23 AI 状态策略新增整段评分器哈希闭环：15 个查询形成两组 target status-any 门、五组同族 event/status 门和两组 actor 分值惩罚；命中 target 门是跳过对应 event 的分值贡献，不是表现层取消，actor `0x12/0x12` 与 `0x0D/0x0D` 则减配置权重。该矩阵证明 AI 必须共享领域状态，但仍不等于完整目标、伤害、生存或任务优先级。证据为 `notes/battle-ai-status-policy-bindings-20260723.json`。
- 2026-07-23 AI 目标与效用新增目标索引函数、全评分器和 8×0xA8 配置表哈希闭环：单位槽 1–12 为同/异阵营各建立最低 HP 比例、最大 HP、攻击、防御、敏捷、移动和地图距离七槽，严格更小替换并保留首次扫描 tie；标准异阵营权重为 `[1700,800,800,1300,1000,800,3600]`，同阵营为 `[4200,2000,1000,1000,1000,800,0]`。damage family 先按目标聚合多段预计伤害，再组合 6000/900/3000/100 的伤害、成功率、覆盖和距离效用；配置尾部四个 typed rule 槽实际覆盖 kind 1–5，普通评分最终只加 0–9 RNG。目标优先级、标准伤害效用、关卡规则和 tie-break 已可实现；规则可见名与完整路径 helper 保持中性。证据为 `notes/battle-ai-utility-policy-bindings-20260723.json`。
- 2026-07-23 动作模板语义新增两套初始化器、目标资格、事件构建、资源门与 63 项 resolver 跳转表的哈希闭环：87 条主动动作和 94 条忍具均生成同一运行时描述，`+0/+1/+2/+3` 分别是成本、显示/动画、效果代码+flags、目标策略+flags；成本已区分查克拉、HP、无标量特殊动作和战斗内忍具槽，目标已区分自己/友军/敌军/占用单位/空格。所有非空模板都能按低 6 位解析到 `0x08076F44` handler，Butano 必须生成独立 Cost/Effect/Target/Range/Upgrade 策略并使用共享 registry，不得按截图或动作名写分支。证据为 `notes/battle-action-template-semantics-bindings-20260723.json`。
- 2026-07-23 Butano 领域重写首个闭环已落地：`generate_butano_battle_action_content.py` 生成 87 条主动动作与 94 条忍具的正交定义，`generate_butano_battle_unit_content.py` 生成 63 个角色的基础数值及 15/24 个动作槽。scenario 41 已删除固定 80 伤害，改从角色 1/30 与动作 5 的 ROM 表实例化；玩家和 AI 共用 `battle_action_resolver`，敌方接近后会真实造成 5 HP 伤害。新状态库实现每单位 16 个活动槽+16 个 removed-event 槽、低 6 位替换/移除、side-end tick 与写轮眼首有效 hit 截断。宿主 19 个 C++ 测试程序全部通过；这仍是领域基础，不代表完整 handler、AI utility、复合目标与多关卡表现已完成。
- 2026-07-23 状态 `0x13` 新增数值与生命周期闭环：effect type `0x14` 读取 source 活动状态记录 `+6` 低字节，加入模板 hit count 后写入 event `+0x12`；配对 handler 先共享解析，再以 mode 1 移除状态并产生 removed event。原 ROM 未检查 lookup `0xFF`，新内容生成必须把所需状态路径作为构建期不变量，不能复刻越界。显示名和其余消费者仍 unresolved。证据为 `notes/battle-status-hit-count-modifier-bindings-20260723.json`。
- 2026-07-23 状态 `0x13` 的生产和全部直接查询消费者已闭合：动作跳转表把 ID 43–49 绑定到第一至第五门、表莲华和里莲华；第一门要求状态缺失，后四门要求阶段严格为 1–4，表/里莲华分别要求阶段 `<=2` 与 `>2`。动作 43–47 的模板以 effect type `0x13`、potency `1–5` 进入 resolver，在 `0x0807758A` 以普通同 code 替换写入 record `+6`；资格与防御详情读取完整 u16，hit-count 消费低字节。它们必须共享一个 `EightGatesStage` 实例。原因码 9–20 的可见文案和状态显示名仍 unresolved，但操作链已闭合；原始 13 个非 blocker/reaction code 剩余 10 个。证据为 `notes/battle-status-stage-policy-bindings-20260723.json`。
- 2026-07-23 状态 `0x05` 已闭合为限时身份覆盖而非贴图替换：动作 4“变化术”只把 source character ID 覆盖为 target character ID，不复制 HP/资源/位置/状态等完整单位记录；状态 `+4` 保留 linked target slot，并参与 `0x0200` tile 类的阵营、自指和 cleanup-event 资格例外。cleanup event `0x0B` 与通用 duration 到期都会调用同一原始身份恢复 helper；自然到期明确经过 removed-event bank 和 `0x0806C5A6`。Butano 必须实现 `IdentityOverrideStatus` 的领域生命周期并覆盖两条恢复路径。该 code 操作链闭合后，原始 13 个非 blocker/reaction code remaining 9；证据为 `notes/battle-status-transformation-bindings-20260723.json`。
- 2026-07-23 属性状态族已闭合为从原始角色身份重建后的有序 modifier 管线：`0x0806D1EC` 按 16 个活动槽顺序，以 record `+6` u16 对攻击、防御、敏捷、移动和最大 HP 应用百分比/绝对增减及 99/9/999 上限；effect `0x26` 原子建立 `0x1E/0x20/0x22/0x1B` 并按最大 HP 正差值同步当前 HP。side-end 在 tick/removed-event 后统一重算，duration 0 保留。主动动作与忍具生产 ID 已逐模板绑定。至此原始 13 个非 blocker/reaction 直接查询 code 的核心操作链 remaining 0，但显示名、removed-event 演出和其他间接状态仍 unresolved。证据为 `notes/battle-status-attribute-modifier-bindings-20260723.json`。
- 2026-07-23 目标结果新增两组跨关卡哈希绑定：battle 44 在目标敌人已清除、小樱位于 `(4,3)` 且面向值为 2 时从 `0xE000→0xE010` 写入胜利 `0→1`；battle 15 在护送代理已清除、三名玩家仍存活时保持同一 `0x8000`，只把结果字节 `0x02026807` 从 `0→2`。这证明复合目标和结果抢占不能退化为清敌/玩家全灭。证据为 `notes/battle-objective-transition-bindings-20260723.json`。
- 2026-07-23 condition 解释器新增全函数、跳转表和 47×3 条 variant 的静态哈希绑定：记录区从 `0x08594758` 精确结束于下一张数据表 `0x08596CCC`，地址为 `base + battle_id×0xCC + variant×0x44`，每条保留四个有序胜利槽和四个有序失败槽。解释器支持 type 1–9，记录实际使用 1、2、3、6、7、8、9；全部已用 type 的运算已经闭合，包括单位/角色缺席、回合上限、战场对象槽失活、到限时 HP 总和/有效单位数/behavior 9 对象结算计数比较。32 槽对象表的分配/释放链与 behavior 9 结算后按单位阵营累加 `0x02026BC0 + side` 的写入链也已闭合。两组同时成立时比较首个命中槽位，较小索引抢占，同索引返回结果 5；调用者把结果 1/2/5 分别送入 presentation ID 1/2/3，结果 5 也结束战斗。对象 behavior 的可见玩法名称、presentation ID 3 可见身份、未用 handler 4/5 和运行时同满足 A/B 仍未闭合。证据为 `notes/battle-condition-interpreter-bindings-20260723.json`。
- 2026-07-22 在线战斗录屏复核已撤销 Butano scenario 41 的“完整 1:1”验收：原作在
  “开始任务？是”后依次显示双方亮相、“开始”标题、可见战前对白和手里剑转场，随后才
  进入单位选择；当前 ROM 跳过了整段入口。当前状态机也仍是固定单角色四回合黄金路线，
  尚未实现多单位行动状态、L/R 切换、完整行动菜单和真实敌方攻击/防御循环。纠正证据见
  `notes/butano-battle-flow-video-review-20260722.md`。
- 2026-07-22 已完成中文流程前 20 分钟 36,001 帧与日文原版全片 12,330 帧的逐帧清单、
  状态边界复核及 scenario 41–50 原 ROM 证据交叉验证。战斗系统后续采用“分层状态机 +
  事务式行动草案 + 数据驱动能力/目标 + 阻塞演出队列”的通用架构；scenario 41 仅作为首个
  验收切片，不再作为架构模板。本项仍处于设计审阅阶段，尚未据此改写 ROM。证据见
  `notes/butano-battle-video-frame-analysis-20260722.md`，设计见
  `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`。
- 2026-07-22 Butano scenario 41 的旧纵切片已从战前任务菜单贯通到战后世界地图：
  38 个稳定边界在真实 mGBA 中保持零像素差，264 帧组合拳为 264/264 normalized RGB
  一致。Maxmod 已按原版 player 状态接入战前 cue 5、战斗 cue 14、组合拳 cue 15、
  战后对白 cue 8、世界地图 cue 2，以及 UI、攻击、弹窗、胜利、结果和升级音效；五个
  路线采样点的主开关、DMA1/2、Timer0 均为 active。Goal 全量回归前墙钟记录为
  28,753 秒（7.9869 小时）。这些证据只对已经截取的画面、动画和音频边界有效，不再证明
  入口或通用战斗流程正确；本关也不代表通用部署、多技能、失败结算、存档和其他章节已完成。证据见
  `notes/butano-scenario-41-one-to-one-runtime-20260722.md`。

- scenario 41 任务准备菜单已确认：`A` 为队伍/装备，`Down,A` 为查看战场，
  `Down,Down,A` 为“开始任务？”，`Down,Down,Down,A` 为保存；
- 确认“开始任务？”后，battle ID 41、map 36×44、Naruto `(4,10)`、Iruka
  `(4,4)` 和白框画面连续六次采样保持稳定；但 2026-07-15 离线任务栈复核证明其保存时的活动链位于
  `0x0808F928 → 0x08088F10 → 0x0807509C → 0x0806F718` 的 pre-controller
  lineup/deployment，且不含 controller caller return；旧 strict arrival 对“该 state 证明 battle controller entry”产生了语义假阳性；
- 该边界尚未证明真实战斗入口、玩家接管、胜利、EXP 或升级：Naruto 仍为 level 1 / EXP 100，
  训练点 `+BA=0`、`A880=0`，因此 `levels` 继续保持 `code_verified`；
- 2026-07-15 五点 controller-path probe 已完成 builder/decoder 与 guarded A/B，但
  `actionable-move-grid.ss9` 的零输入 baseline 和显式 `B,Down,Down,A,A` final dump
  逐字节相同，`0x08073946` 与四个 `0x08073A04` 分支均无 fresh record。正对照未成立，
  因此没有运行 scenario 41 白框两轮，也没有提升玩家控制状态；
- 2026-07-15 macOS Intel 已复用严格 mGBA 0.10.5 frame-80 零输入结果验收战前菜单：
  candidate 与输出的 240×160 RGB8 normalized pixels 逐哈希相同，task 2 resume PC
  为 `0x08067D02`，三个显式栈槽经 base ROM Thumb BL 静态校验后得到活动 unwind
  `0x080885C1 → 0x08088F9F → 0x0808F92D`，`[0x0202680C]=0`，仍不含 controller
  return `0x0808F957`。strict audit/ROM/state/emulator/patch 全部通过哈希校验，guard
  为非降级 `completed/0`，最终 PGID 与 mGBA listener 均无残留；该 state 现已作为
  `scenario-41-prebattle-menu` accepted，可直接重载用于后续分段调试；
- 下一 P0 从 accepted prebattle menu 继续完成 lineup/deployment，并以 task 栈含
  `0x0808F957` 或 fresh entry observer 命中 `0x0808F952 → 0x080732B4` 证明真实
  controller entry；随后依次命中玩家单位选择 `0x08073940`、
  MOVEDONE `0x080722A8`、胜负谓词 `0x080777FC`、结果写入 `0x02026807` 和
  postbattle `0x08074EE6`，再对自然命中的 levels record `+6` 做单因素 A/B；
- 当前证据分布仍为 13 `runtime_verified` / 10 `code_verified` / 9 `disproved`；
  本次纠正的是 scenario 41 功能边界，不改变 bank 状态。
- 2026-07-16 成本/耗时审计确认，mGBA 证据链的实现后加固占本轮约 45% 有效
  token 和 50% 墙钟，根因与强制门禁记录在
  `docs/codex-mgba-cost-time-audit-20260716.md`。用户转向统计后，未被取消的写代理提交了
  `f252dbd` single-input runner；该提交尚未 review，未运行 ROM、未发送按键，也未提升
  controller 进度。后续只能先做一次限定 review，再从 accepted prebattle menu 执行单次
  Down，禁止继续扩展已批准的 evidence 框架。
- 2026-07-16 在限定 review 后，从 accepted prebattle menu 仅发送一次 Down，并以独立
  fresh 80-frame zero-input 重放固化 `scenario-41-prebattle-down.ss9`。四路 normalized RGB、
  task 2、显式 Thumb BL unwind、`[0x0202680C]`、guard 和资源门均稳定；该 rung 仍不证明
  controller entry/player control，也不单独授权 A。Step 4 仍须独立门禁，当前未发送 A。
- 2026-07-16 cycle diagnostic 选择最小 exact period `p=19` 后，从唯一 A candidate
  连续执行两段独立 fresh 19-frame zero-input replay。candidate/p/2p 的完整 RGB8 画面、
  task 2、三个显式 static-BL-valid unwind slots 与 `[0x0202680C]` 全部相同，已固化
  `scenario-41-pre-controller-after-a.ss9`。lineage 为 accepted Down → 唯一 A → zero
  settle 19，`allowed_evidence=[]`；活动 unwind 仍无 `0x0808F957`，所以这只证明稳定
  pre-controller 状态，不证明 controller entry 或 player control，后续仍须独立通过门槛。
- 2026-07-16 从该稳定 pre-controller state 分段执行 B → zero → B → zero；两个 B
  边界均稳定。后续唯一 Down 在 80-frame capture 与同 input state 的唯一 160-frame
  延长重试中，都没有改变 task 2、活动 stack、`[0x0202680C]` 或 normalized full-screen
  RGB，因此 selection/result 未被证明改变并触发停止门。未发送 final A，未运行 entry
  observer，未捕获 raw `0x0808F957`，没有 controller checkpoint；controller entry 与
  player control 继续为 `not-proven`，不进入下一阶段。
- 2026-07-17 上述 B/B/Down 分支已作为 superseded 历史保留：`0x08088628` 是
  message-box yield，Down 不会选择列表项。纠正后的分段输入 B → B → A → Down → Down →
  A → inner B → outer A → inner A 捕获 static-BL-valid raw `0x0808F957`；两次独立
  224-frame zero-input replay 保持 exact RGB、task-2 resume/SP/LR、三条 raw return 与
  A880/A882/2680C，p1 已固化为 `scenario-41-controller-entry.ss9`。controller entry
  现为 runtime-proven 且 stable；player control、first turn、MOVEDONE、victory 与
  postbattle 仍未证明。bank 验证数量和 13/10/9 分布不变。
- 2026-07-18 已从 accepted controller checkpoint 自然闭合玩家接管、第一回合
  secondary MOVEDONE、后续回合、技能击杀、`0x02026807=1` 胜利结果、升级页、战后
  对白和木叶世界地图。immutable base ROM 的决定性 A 与 observer 运行画面及 WRAM
  完全一致；`scenario-41-victory.ss9` 和 `scenario-41-postbattle.ss9` 均已在 base ROM
  下零输入重放并固化。完整边界见 `notes/scenario-41-completion-runtime-20260718.md`。
- `0x08074F2C` natural-save observer 在现有固定帧样本仍未命中，因此本轮不把瞬态
  `0xF400` 或自然保存写成已证明。下一 P0 不再重复战斗导航，直接从 accepted postbattle
  checkpoint 验证升级前后 levels record `+6` 的运行时消费；若最终审计仍要求保存命中，
  应使用“命中即落盘”observer，而不是继续增加固定帧切片。bank 分布暂仍为
  13 `runtime_verified` / 10 `code_verified` / 9 `disproved`。
- 2026-07-18 已从场景 41 战后 checkpoint 自然完成下一段演习场剧情与教程战斗；结果页
  令 Naruto 保持 LV2、EXP `0→110`、训练点保持 1。base ROM 零输入稳定 checkpoint
  `scenario-42-postbattle-world-map.ss9` 已固化，后续主线不再重放场景 42。
- levels probe 已捕获训练确认完整参数并定位第一个 type 4 row：index 8、levels ID 1、
  secondary slot 0。该 row 需要角色 LV8，当前 LV2 UI 明确拒绝，consumer `0x080932CA`
  未命中；因此 levels 保持 `code_verified`，下一步继续自然升级而非强制写入状态。
- 2026-07-18 已自然完成后续三敌人任务，结果页给出 155 EXP，Naruto `LV2→LV3`、训练点
  变为 2；`scenario-43-postbattle-next-task-prompt.ss9` 已经 base ROM 零输入复验。影分身可
  留下可控 unit，“休息”恢复 18 HP，可作为后续战斗的稳定生存循环。levels 仍未到 LV8，
  下一步从该 checkpoint 直接开始下一任务。
- 2026-07-18 已自然完成场景 `0x2C`：胜利条件是“击倒卡卡西 + 在铃铛宝箱上方 `(4,3)`
  朝下结束行动”，不是敌方清零或占据宝箱格。三人各得 125 EXP，Sasuke 升至 LV2；
  `scenario-44-postbattle-world-map.ss9` 已经 base ROM 零输入复验。下一步从该世界地图继续
  自然任务，直到 Naruto 达到 LV8 或首次出现 secondary level 激活。

Windows 前台 runtime 到此停止，后续转移到 macOS Intel。迁移、mGBA 0.10.5、Lua
8-frame 输入、candidate 零输入验收和进程守卫要求见
`docs/reverse-engineering-macos-intel-handoff-20260715.md`。

资源约束：全 ROM Capstone 对象扫描曾单进程膨胀到 3 GiB 以上并触发 OOM、swap
thrashing 和 I/O pressure；该路径现已替换为恒定内存 Thumb 编码扫描。静态重任务与
Chromium probe 必须统一经 `tools/run_guarded.py` 的共享 `heavy` 锁、内存准入、树级 RSS、
wall/idle timeout 和精确 owned-tree 清理；runtime 的实际入口是
`play/_scripts` 下的 `npm run probe:guarded`。禁止按进程名清理。当前 bank 分布仍为
13 runtime / 10 code / 9 disproved；资源安全实现不改变逆向证据等级。完整门槛、退出码和
命令见 `docs/reverse-engineering-handoff-20260711.md` 第 0.5 节。

### ✅ 已打通
- 对白 → ROM 写入闭环（dialogue patch pipeline）
- 5 段对话已验证写入 ROM
- 变长对白现已使用独占 `0x5F0000..0x5F7FFF` allocator，校验基准指针、FF
  空间、编码/NUL、对齐和容量；`group0.label2` 已从 6-byte slot 重定位到
  `0x5F0000`，构建 ROM 的 `0x461CF0` 指针和目标文本逐字节验证通过；该 ROM
  已在 WASM 路线 step 306 通过完整 strict battle arrival，变长重定位的构建→启动→
  文本流程→首战 no-crash E2E 已闭环
- 构建流水线支持 7 种 patch 类型（bytes/dialogue/pointer_redirect/map/battle_config/
  dialogue_var/chapter_script）
- mGBA headless 调试环境稳定（`tools/mgba-headless-snapshot.py`）
- mGBA PC/读取探针已加入：断点真实命中后可在同一上下文抓取 ROM 与 WRAM；
  复位 PC smoke test 已通过；maps width/height 与六类资源流均已由 WASM/mGBA
  同边界 A/B 闭合
- 网页 WASM 首战导航与编成探针已可复现：单位槽 1 坐标 `(4,4)` 唯一对应
  positions group 40 / variant 0 / record 0（ROM `0x588CA8`），positions 已完成
  runtime 验证
- WASM 探针现会记录 `0x02026804` 的 8 字节控制区、`0x02026805` 标识和
  `0x0201BE28..2B` map runtime；baseline 得到 `[36,44,9,22]`
- WASM 到达判据仍要求唯一完整编成、非零 battle ID、派生一致 map runtime 和
  真实地图截图，但旧颜色分类已纠正：旧 step 306 实际是角色详情面板假阳性；
  真正地图在 tail 阶段，菱形黑角 `darkRatio=0.200625`，面板仅 `0.003125`。
  分类器现用黑角比例区分，必须以新 live run 重新签发 strict-arrival 结果；详见
  `notes/strict-battle-arrival-gate-20260712.md`
- 纠正后两次重跑分别停在“队伍・装备”和“特别宝箱”教程说明页，均被正确拒绝且
  save hook 为 0；菜单已确认包含“开始任务”，START 不能关闭教程。静态追踪现已
  确认队伍页只是 normalized selector 2 的嵌套页；真实路径必须退回外层选 selector 4，
  经 `0x08086A54` 成功后由 `0x080871BE..C4` 建立 battle control，再以黑角与下一 A
  打开真实行动菜单的双门禁确认战场
- 独立 A/B 仅把 maps 第 40 行 `0x53DE10` 的 width 36→32，同路线得到
  `[32,44,8,22]`，因此 maps width/height 字段链已升级为 runtime；
  资源指针字段仍保持 code 验证。47 行已有持久 `rom_map_headers` 镜像和
  immutable-base、精确 offset、尺寸、ROM 对齐、LZ header/解压长度门禁的
  32-byte 安全写回
- units 旧结论已撤销：`0x0806E654` 实为读取单位 x/y，`0x53F298` 唯一消费者
  将其作为 u16 偏移查找；legacy units 回写已安全禁用，真实角色记录已迁移到
  `0x54241C`；loader-derived base destinations、两组槽数组和过滤 ID 区已命名，
  完整记录安全写回已建立；玩家界面属性名称仍待 UI correlation
- 真实角色定义表已定位并迁移到 units bank：`0x54241C`，63×`0xB4`；
  `tools/extract_character_definitions.py` 可重复提取；formation character ID 经
  `0x02022E34` 模板池复制到 `0x1D4` 战斗槽；WASM 首战样本已证明
  template slot 1 → battle slot 1 的前 `0xBC` 字节复制，但 template payload 与
  ROM raw record `0x5424D0` 仅前 7 字节一致，raw record 字段转换仍待 PC/LR 或
  受控 A/B 证明；后续 `0x5424D1` byte `0x0e→0x0f` A/B 已证明 raw record byte `+1`
  进入 runtime template 和 battle slot，units 结构身份达到 runtime 证据；
  后续静态闭合 7 个 base value、15×4 主槽、24×4 次槽和 9 个候选 ID，
  `rom_character_definitions` 镜像支持带 immutable-base、精确 offset/length、
  sentinel/active flag 门禁的整条 `0xB4` 写回
- character-stats 旧两表结论已撤销：真实成长表为 `0x545068`，63×`0x10`，
  `0x0806D964` 按角色 ID 读取并以 `growth*(level-1)/100` 写入模板；受控首战
  两因素 A/B 已证明 record 1 `+4` 进入 template/battle slot `+2`。
  `0x54507A` 和 `0x545200` 都是错位切片，后者 legacy 回写已禁用
- `battle-config@0x545458` 的旧 u16 场景配置解释已撤销；2026-07-23 又撤销了把连续表截成 32 行的边界：真实结构是
  87×16-byte 主动动作数值模板，与动作文本及单位 primary 槽 ID 一一对应；`0x0806D85C` 按 action ID 复制记录，并用
  byte `+0x0C` 与 u16 `+0x0E` 应用等级成长；effect 2 的 level-2 A/B 已证明
  growth `1→2` 只令 type-4 输出 `+7:4→5`，升级 runtime；地图场景表仍是 `0x53D910`
- items 与 skills 的 `0x546100` 冲突已拆分：两者 entries 原本逐字节相同，且无
  独立 item consumer；items 已改为 disproved tombstone，legacy item 写回保持
  diagnostic-only；legacy `skills` 路径的真表已纠正为 `0x545BE4` 的 94×16-byte 忍具/强化道具模板，
  `0x0806D910` 按 ninja-tool ID 复制前 10 字节，旧 `0x546100` 是 record 81 起的尾部切片
- 五个旧 late-ROM `story*` 候选其实是 `0x465B70` 音频主表所指 song descriptor
  的 `+4` 切片；m4a SongHeader byte 0 是 track count，`+4` 是 voicegroup，
  `+8` 是 track sequence pointers。`story-c/d/e` 保持 tombstone；`story/story-b` 已迁移为真实章节表
  `0x60C74/0x60D54`，并有独立安全写回
- maps width/height 消费链已定位到 `0x0201BE28..2B`，并通过 width 36→32
  A/B 从 `[36,44,9,22]` 变为 `[32,44,8,22]`
- maps 资源字段静态语义已纠正：`+8` 是 BG palette（旧 extractor 错用 `+14`），
  `+0C/+10` 是主/可选 coarse layout，`+14` 是 metatile attributes，`+18` 是
  collision grid；47 行长度公式全部通过测试。row 41 的同边界 EWRAM/PRAM/VRAM
  比对已令六项全部通过，maps 升为 runtime_verified
- battle configs、units、chapters、skills、story beats、legacy audio、maps、levels、
  character_stats、battle_config_data、encounter_zones、items 等无 ROM 身份的
  legacy 危险回写已禁用，只输出 unmapped 诊断；lossless `rom_*` mirror 继续作为
  安全写回入口
- audio/palette/message 身份已拆分：`0x53F138` 的旧 palette 身份已撤销，
  `palettes` slug 实为 `0x53EE98` motion/effect 参数表；`0x599634` /
  `0x08079668` 是消息表/分发器。真实 sound-ID 主表为 `0x465B70`，域 0..158，
  80 个非空 descriptor；dispatcher `0x0809AAC0`、track initializer
  `0x0809B1F4`、FIFO/DMA initializer `0x0809AE3C` 已闭合。运行时 hook 命中
  230 次并证明 ID 118→`0x0853D06C`，audio 升级 runtime；真实指针可达提取器
  已导出 217 条 track blob、23 个 voicegroup、387 个 tone 和 79 个合法 WAV；
  track opcode/控制流已结构化解码并生成单循环 MIDI；player 级 mixer、同-slot
  硬替换和跨-player 共享池已有运行时差分，每个 cue 的可听名称仍待完成。
  sound-ID 主表已有持久
  `rom_audio_sound_ids` 镜像和 immutable-base、精确 offset、ROM 范围/对齐、
  descriptor track-count 门禁的 8-byte 安全写回
- save descriptor 第二字段已纠正为 payload length/累计 stride，而非独立 SRAM
  offset；group 3..9 累计起点为 `0x2548..0x55B0`。WASM 已改用 `getSave()`
  导出真实 32KiB `.sav`。裸 group 均返回1并改变七处，但 wrapper 在战斗初始化
  上下文仍返回0且记录校验不成立；自然 caller 已归属 postbattle controller
  `0x080732B4` 的 state `0xF400`。首战开始自然命中为0，强制 state/gate 会卡在
  更早的结果 UI 阶段，不能代替真实胜利转换；下一有效路线是自动完成首战或取得
  genuine post-victory state 后命中 `0x08074F2C`
- 首战已建立可恢复的 WASM slot-9 checkpoint 闭环：稳定真地图重载仍得到 battle
  ID 40、map `[36,44,9,22]`、唯一 slot 1 `(4,4)`；新增 EWRAM dump 证明光标是
  `0x02026A78/79`，与单位记录 `+0xC4/+0xC5` 不同。地图/面板门禁改以纹理
  `edgeRatio` 为主，稳定地图约 `0.3435`、角色面板约 `0.1263`。当前 A→单步 Down
  只令光标到 `(4,8)`，单位未移动、natural-save hook 仍为0，故不得升级 SRAM
  结论；下一步必须闭合教程的真实 unit-action 子状态后再验证保存与冷加载。详见
  `notes/first-battle-savestate-checkpoints-20260712.md`
- 上述 checkpoint 后续确认是战前“查看战场”，不是可行动战斗；此假阳性已撤销。
  正确选择“开始任务”后，首战以真实两回合 `(4,4)→(4,7)→(4,10)` 完成，
  在宝箱 `(4,11)` 相邻格行动结束并进入胜利转场。木叶界面 UI Save 写出 32KiB
  存档；descriptor 0/2 的 19-byte `Naruto-KONOHASENKI\0` header、payload 和
  NOT-sum checksum 均有效，未使用记录保持全 FF。冷启动 Continue 识别 slot 1
  并恢复相同木叶状态，因此 save-state bank 已升为 runtime_verified。旧 verifier
  把 payload/checksum 起点提前19字节，旧“冷加载必须命中 0x08068AF0”也混淆了
  optional battle restore caller，均已纠正。详见
  `notes/tutorial-victory-save-load-runtime-20260712.md`
- `0x60D54` 受控运行时探针已从无效的 `0x1A` 专用 hook 改为 selector + 通用
  dispatch 追踪。scenario 39 运行时选中 `0x08031281`，共执行 25 次 dispatch，
  最终在 `0x0803142E` 的 opcode `00` 正常返回；live bytes 与 ROM 一致。该脚本
  不产生 battle state 是已解码的预期行为，story-b 已升为 runtime_verified。
- 备用章节实验的 checkpoint 导出已修正：旧实现可能复制同槽旧文件，现保存前
  清理 `.ss9` 候选并要求唯一新文件，加载后也显式释放全部 GBA 键。新的
  `木叶里 / 对战` 任务选择 checkpoint 已通过独立零输入重放；下一段从该页 A
  进入卡卡西对白，继续追到 selector hook。
- 浏览器键盘映射修正后，`PROBE_TAIL_REPEAT` 可复现重复选择。后续通用 dispatch
  探针证明该分支本身就是备用章节对白消费链，而不是必须进入战斗才算成功；runner
  现在会在终止证据出现时立即固化，避免后续输入覆盖最后 cursor。
- Phase 1/2/6 框架级完成

### 🔴 核心瓶颈（P0 — 逆向工程阶段）

| 目标 | 状态 | 备注 |
|------|------|------|
| tilemap 布局数据 | ✅ 已定位 | 32x32 grid at 0x14D000+ |
| 战斗配置表 | ✅ 已定位 | ROM 表(0x53D910, 0x53F298) + WRAM 地址均已确认，patch 生成可用 |
| 章节流程入口 | ✅ 两链已闭合 | `0x60C74/0x60D54` 两张 56 项脚本表；primary scenario 39→`0x31020`→三字节 `SetBattle(40,2)` 后接独立 `End`；alternate scenario 39→`0x31281`→25 次 dispatch→`0x3142E` opcode `00` 正常终止，均有 runtime 证据 |
| 资源提取（图片/音频） | ⚠️ 部分 | 47/47 tileset atlas、217 条音频 track blob、79 个 pointer-reachable WAV 和 80/80 整曲 PCM 已导出；track opcode、mixer/player 并发已闭合，cue 语义命名仍未完成 |

### 🟡 续作内容创作（逆向完成后）
- episode-01 剧情源稿细化
- 多章节内容模板

### 🟢 网页编辑器（逆向工程 100% 完成后启动）
- 技术方案：FastAPI 后端 + Vue 前端，部署于本服务器（14.103.49.74）
- 功能：地图编辑器、角色编辑器、技能编辑器、剧情编辑器、道具编辑器等
- 架构：多用户 WebSocket 协作编辑，ROM 在服务端操作

---

## 逆向工程路线图

### P0-Step 1｜稳定 mGBA 调试环境
**状态：✅ 已完成**

- `tools/mgba-headless-snapshot.py`：snapshot / watch / diff 三种模式可用
- `docs/next-action-plan.md`：方案 A 执行结果已记录
- 验证：watchpoint 命中 PC=0x08060FD2，cycle=182801696

---

### P0-Step 2｜定位 tilemap 布局数据（Phase 4 收尾）

**状态：✅ 已完成**

**现状：**
- Tile 描述表 `0x596D5C` 已完整分析（312行×16字节，每行含 tile data/attribute/layout/palette 4 个指针）
- tilemap 布局数据（2D 瓦片 ID 网格）已定位！

**发现：**
- 多个 tilemap 数据区位于 ROM: 0x14D000, 0x195000, 0x1CB000 等
- 格式：2字节/条目，32×32 网格 (1024条目，2048字节)
- 编码：低10位为 tile ID (0-311)， bits 10-15 为 flip/调色板属性

**方法：**
1. 用静态分析扫描 ROM 寻找 tile ID 有效范围内的 2D 网格模式
2. 通过对比验证找到多个有效的 tilemap 数据区

**交付物：**
- `notes/map-format.md`（完整版）✓
- `notes/map-addresses.md`（完整版）✓
- `tools/import_map.py`（完整 patch 生成逻辑）✓

---

### P0-Step 3｜定位战斗配置与角色定义

**状态：⚠️ 部分完成**（positions、maps 全资源、角色定义及成长表已有运行时闭环；units 已有结构字段和安全 lossless 写回，剩余玩家属性命名仍未完成）

**已确认 ROM 数据表：**
- ❌ 旧 `0x0853F298` 单位 ID 映射结论已撤销；唯一消费者把它作为 u16
  对象/渲染偏移查找，legacy 回写已禁用
- ✅ 真实角色定义表：`0x0854241C` / file `0x54241C`，63×`0xB4`；
  `tools/extract_character_definitions.py` 已建立，`sequel/content/units/bank.json`
  已迁移；runtime 样本已把战斗槽 character ID 和模板槽闭合到 ID 1 / ROM
  `0x5424D0`；`0x5424D1` 单字节 A/B 已动态闭合 raw record byte `+1` 到模板字段；
  两组槽数组及过滤候选区已按 loader 命名，整条记录可受保护写回
- ✅ 战斗场景配置表：`0x0853D910` / file `0x53D910`，8 个有效条目 × 16 字节
  - 条目格式：u16 tiles_x, u16 tiles_y, u32 ptr1, u32 ptr2, u16 flag, u16 extra
  - ptr1：12 字节头 + 原始 tile 数据（u16/tile）
  - ptr2：LZ77 压缩数据（解压后 384 字节，调色板/属性数据）
- ✅ 状态机函数指针表：`0x0853F1C0` / file `0x53F1C0`，u32[60]，指向 0x0812Fxxx
- ✅ WRAM 分配表：`0x0853D848` / file `0x53D848`

**已确认 WRAM 战斗数据地址：**
| WRAM 地址 | 大小 | 说明 |
|---|---|---|
| `0x0201BE28` | 4 字节 | map width/height 及 `>>2/>>1` 派生尺寸 |
| `0x02021E2C` | 网格相关 | 单位坐标查找表基址 |
| `0x020240C0` | `0x17C4` 总区间；`0x1D4*N` | 主战斗数据/单位数组物理基址（单位 stride 468 字节） |
| `0x02024294` | `0x1D4` | 第一个可分配/常用单位槽（slot 1） |
| `0x02022E34` | 24×`0xBC` | 角色模板池；模板 `+0` 为 character ID |
| `0x02022EF0` | `0xBC` | 角色模板池 slot 1；旧 character-stats WRAM 假设已撤销 |
| `0x02026804` | 8 字节 | 战斗控制标志 |

**交付物：**
- ✅ `notes/battle-config-format.md` — 完整版（ROM 表、WRAM 布局、LZ77 格式、代码引用）
- ✅ `notes/unit-skill-addresses.md` — 完整版（单位 ID 表、场景配置、状态机函数）
- ✅ `notes/unit-id-mapping-analysis.md` — 完整版
- ✅ `notes/battle-scenario-config.md` — 完整版（8 个场景条目解析）
- ✅ `tools/import_battle_config.py` — 可生成 ROM patches + WRAM cheat patches
- ✅ `tools/extract_positions.py` — 从 ROM `0x5461C4` 编成矩阵可复现提取 48×3×12 条记录；记录 `+2/+3` 已静态确认为初始 x/y
- ✅ positions ROM→WRAM 静态链路：`0x0806E41E/0x0806E71E → 0x0806AC70 → 0x0806AA64`；单位 stride 已纠正为 `0x1D4`
- ✅ positions 编辑/回写链：通用 ROM mirror 导入 `rom_positions` 1728 行并保留完整 `0xB8` 原始记录；构建器验证 index、ROM offset 与长度后写回真实矩阵
- ⚠️ 旧 `unit_positions` CRUD 仅是运行时编辑概念，没有一行一 ROM 地址证据，不计入真实回写完成度
- ✅ runtime WRAM dump 已通过网页 WASM 探针取得并与 ROM 编成记录唯一关联；CLI
  headless 仍无按键注入与 PC/LR 联合采集能力

---

### P0-Step 4｜定位章节流程入口（Phase 3 收尾）

**状态：✅ 主流程入口已完成；脚本 opcode 全语义仍属后续字段工作**

**2026-07-12 纠正：**
- `0x0808F544` 根据状态 `+0x18` 在 `0x60C74` / `0x60D54` 两张
  56-entry script pointer table 之间选择，并按 scenario ID 索引；
- WASM hook 捕获 primary scenario 39 → `0x08031020`，脚本游标
  `0x08031070` 的 `1A 28 02 | 00`（三字节 SetBattle + 一字节 End）将 battle ID 40 写入状态并最终到
  `0x02026805`；
- `story` bank 已迁移为 primary/runtime，`story-b` 为 alternate/runtime；
  旧 late-ROM `story*` 资源切片结论已撤销。

**已完成：**
- 静态分析：遍历 38 个 late-ROM 表候选，全部为视觉/资源描述表
- 代码引用分析：定位到 9 处对战斗配置表（0x0853D910, 0x0853F298）的引用
- 章节 ID 序列搜索：在 0xBD713, 0xC1717 等处发现 u16(1,2,3...) 模式，但未找到明确配置表

**Runtime 验证尝试：**
- 尝试 1：加载 savestate - 失败（所有 save 文件为 0xFF，未初始化）
- 尝试 2：设断点 0x080894DE - 未命中（游戏卡在 UI 循环 0x085CCDxx）
- 尝试 3：设断点 0x0806E654 - 未命中（无用户输入无法到达战斗）
- 尝试 4：frame advance + breakpoint - 停留在 video/UI 子系统，无法进入主游戏逻辑

**环境限制：**
- mgba-sdl 0.10.1 缺少 `--script` 参数支持
- CLI 调试器无法注入按键输入
- 无有效 savestate 文件

**交付物：**
- `notes/chapter-entry-points.md` - 运行时验证尝试记录 + 静态分析
- `notes/chapter-flow-format.md` - 格式分析（待 runtime 验证）

---

### P0-Step 5｜资源提取链路（图片/音频）

**状态：⚠️ 字节提取、整曲渲染及 player 运行时完成，cue 语义部分完成**

**现状：**
- 47/47 tileset atlas 已由真实 descriptor 指针导出
- m4a SongHeader 已纠正：`+4` voicegroup，`+8` track sequences
- 已导出 217 条 track blob、23 个 voicegroup、387 个 tone、79 个 WAV
- 217 条 track 已结构化解码为 18,090 条命令和 6,750 个 note/tie；1,287 个
  控制流目标全部落在已知 track 范围
- PATT/PEND/GOTO 已按单循环策略执行；80/80 sound ID 已生成标准 MIDI，
  217 条 track 共发出 17,202 个时间线事件
- 16,180/16,180 note 已解析 terminal tone：16,169 个 DirectSound note 覆盖
  79/79 waves，其中 5,340 个经 drum table；剩余 11 个明确为 0x0C PSG/noise
- TIE 生命周期已纠正为 90 条：25 条由 EOT 释放、19 条由 FINE 进入 release、
  46 条在单循环 GOTO 边界仍活跃；只保留后 46 条为 open tie，不伪造释放
- DirectSound nominal pitch-step 已按 `0x0809A998` 的 ROM 两表与 UMULL high32
  精确整数公式闭合；16169/16169 DirectSound note、79/79 waves 均产生正 step，
  23-bit mixer phase 与本 ROM 15768 Hz / divFreq 532 也已代码锁定
- KEYSH/BEND/BENDR/TUNE 与当前 MODT=0 LFO 状态已接入 16169 条 DirectSound
  note，971 条 noncenter，零无效 step
- MP2K triangle LFO/LFODL/MOD 的逐 tick pitch automation 已闭合；对活跃 note 共
  产生 30937 次有效 step 更新（BEND 323、LFO 30413、MOD 201），零无效；open TIE
  只追踪到单循环边界
- `TrkVolPitSet→ChnVolSetAsm` 的两级 volume/pan 整数链已闭合；16169/16169
  DirectSound note 均得到有效双声道系数，活跃 note 内 39 次 VOL 更新全部有效；
  MODT=1/2 由合成向量锁定，但实际 track 中 MODT/LFODL 均为 0 次。timeline 现为
  38979 events（21328 pitch-state、449 mix-state）
- DirectSound ADSR/release/pseudo-echo 与 master gain 状态机已按
  `0x08099EC8..0x08099F82` 代码锁定；16169/16169 note 共 4 种有效 tuple，零非法。
  状态按 SoundMain mixer invocation 而非 MP2K tick 推进
- 11/11 PSG note 已闭合至 CGB channel-4 寄存器向量、NR43 时钟和 15/7-bit
  LFSR；实际语料均为 sound ID 144、NR43=`0x14`，三档 NR42 向量已代码锁定
- DirectSound 16169/16169 note 的 forward-linear 插值、跨 sample/loop、非循环
  停止、reverb seed、signed-byte modulo-256（非饱和）累加和 stereo WAV 写入已锁定；
  8442 条非循环、7727 条循环语料全部走此路径
- MP2K tempo threshold=150、同一 SoundMain 内 0/1/多 tick、linked-player 递归顺序、
  每次 264-frame mix 与 6×264 DMA/reverb ring 已代码锁定；多 tick 间不得插入混音
- 持久 WAIT/GOTO/PATT/REPT command VM 已让 217/217 track 各运行 2048 ticks：累计
  39825 commands、163 次真实 GOTO，79 条 FINE 终止、138 条在时长边界继续运行
- 10 DirectSound pool + 4 fixed CGB 的 free/released/active 选择、priority/track-address
  tie-break、steal、newest-first track chain 与 same-key EOT 已代码锁定
- persistent TEMPO/PRIO/VOICE/VOL/PAN/pitch/LFO registers 已让全部 track 在 2048 ticks
  产生 17546 NoteRequest、21 EOT、79 FINE stop，复用现有 decoded commands/整数公式
- request→terminal tone→allocated channel 已闭合：全库 17546 请求全部到达解析/分配
  路径；真实 sound 1 DirectSound 与 sound 144 CGB noise 向量、drum-root pitch、
  mid-note pitch/mix dirty 传播、自然停止后的 track unlink 和首个 264-frame PCM hash
  均已测试。bounded allocator rejection 不能冒充真实 SoundMain 丢音统计
- player 级整曲 SoundMain 与 DirectSound+CGB 联合 PCM 已闭合：80/80 sound ID
  均生成非静音 WAV，62 个 one-shot 自然结束，18 个 loop song 的全部 138 条
  GOTO track 均跨过首次 GOTO；首次 GOTO 上 21 个 active TIE 保持跨边界
- 独立 mGBA 差分已闭合：sound 101 的 79/79 个 Direct FIFO 块逐字节一致，sound 144
  的 68/68 组可读 CGB register/channel-4 status 一致；两条路径均自然结束
- player-slot 差分已闭合：活跃同-slot sound 101→102 硬替换 27/27、slot 1/2
  linked-player DirectSound 共享池 25/25、跨-player 固定 CGB channel 竞争 68/68；
  equal-priority active owner 稳定为低地址 `0x03006178`
- 播放 wrapper 共 290 个 callsite：278 个立即数调用覆盖 38 个有效 ID，12 个动态
  来源；仅四个 A 级与四个 B 级语义候选有当前证据，72 个仍保持 `unknown`，尚无
  官方名称来源

**方法：**
1. 从 `0x596D5C` descriptor 链提取 tileset PNG（已完成）
2. 从 `0x465B70` sound-ID → SongHeader → voicegroup/track/wave（已完成）
3. 闭合同 player hard replacement、linked-player 并发和全局 CGB pool 竞争（已完成）
4. 动态对照显式 `MPlayStop` 与 FINE release，并为 80 个 cue 建立有来源语义名称（下一步）

**交付物：**
- `tools/extract_tileset.py`
- `tools/extract_audio_assets.py`
- `tools/build_controlled_audio_runtime_probe.py`
- `tools/compare_mgba_audio_capture.py`
- `tools/compare_mgba_cgb_capture.py`
- `tools/build_delayed_audio_retrigger_probe.py`
- `tools/compare_mgba_retrigger_capture.py`
- `tools/compare_mgba_linked_audio_capture.py`
- `tools/build_cross_player_cgb_probe.py`
- `tools/compare_mgba_cross_player_cgb_capture.py`
- `tools/extract_audio_cue_calls.py`
- `artifacts/audio/mgba-sound101-full-differential.json`
- `artifacts/audio/mgba-sound144-cgb-differential.json`
- `artifacts/audio/mgba-same-player-101-102-differential.json`
- `artifacts/audio/mgba-active-retrigger-101-102-differential.json`
- `artifacts/audio/mgba-linked-player-101-106-differential.json`
- `artifacts/audio/mgba-cross-player-cgb-143-144-differential.json`
- `notes/m4a-emulator-differential-20260713.md`
- `notes/m4a-player-slot-runtime-differential-20260713.md`
- `notes/audio-cue-semantics-20260713.md`
- `notes/resource-locations.md`

---

### P0-Step 6｜可变长对话（Phase 2 收尾）

**现状：**
- 同长替换可行，变长 redirect 需要已验证的空闲 ROM 区域

**方法：**
1. 用 mGBA 在游戏运行时检测 ROM 空闲区域（写入后读回为 0xFF 且不被读的地址）
2. 验证后实现 pointer_redirect 策略

**交付物：**
- 空闲 ROM 区域验证文档
- `import_dialogue_var.py`（变长 redirect patch 生成）

---

### P0-Step 7｜全面测试闭环

**现状：**
- `docs/testing-checklist.md` 已建立
- 离线无 OCR 子闭环已完成：`tools/run_offline_e2e.py` 执行正式 build checks，核对
  输出 SHA-1，并用原生 mGBA + tracked checkpoint 断言 battle 41、map 36×44、
  Naruto `(4,10)`、Iruka `(4,4)`；持久报告在
  `artifacts/e2e/offline-smoke-20260713/`
- 编辑器 DB 隔离正式构建已闭合：完整 mirror DB 中只改 map 40 width 36→32，正式
  build 后 reserved region 之前仅 `0x53DE10:0x24→0x20`；测试同时修复了旧
  cutscene 16×pointer generator 与 8×pair schema 不一致、以及未编辑 chapter mirror
  与 scenario 39 semantic relocation 冲突
- 私有 build-ID HTTP 所有权已闭合：owner 可查状态/下载，其他登录用户得到 403；
  “最新 build”改按创建插入顺序而非随机 UUID 字典序。公开 UUID ROM endpoint 保持
  显式 capability URL；浏览器下载现通过带 Bearer 的 fetch/blob 并显示下载中/错误；
  WebSocket 改为首帧 JWT+显式 build ID，拒绝跨用户订阅且不再泄露服务器 ROM 路径
- build-ID 子进程隔离已闭合：`DB_PATH` 贯穿 dialogue 与全部 generator，外部
  `BUILD_OUTPUT_DIR` 的 ROM/build report/automated report 三件套均被当前请求验证，
  全局 build 哈希不变；backend 支持注入 BUILD_CWD/PROJECT_ROOT，并在 trigger 时用
  SQLite backup 固化 build-ID 专属 DB snapshot
- 浏览器 UI/API 鉴权下载已闭合；玩家可见 OCR 与剧情→战斗→存档长程回归仍未完成

**方法：**
1. 在现有离线 runtime smoke 与 editor DB 隔离 build 上追加浏览器 API 与跨平台 OCR
2. 每完成一个格式的 patch 生成，都要跑一遍 checklist

**交付物：**
- `tools/run_offline_e2e.py`（当前无 OCR runtime smoke）
- `tests/test_editor_build_integration.py`（临时 DB 与临时 build ROOT）
- 后续跨平台 mGBA + OCR 验证
- 所有格式的验证报告

---

## 当前推荐顺序

### 2026-07-10 Positions 与构建安全更新

- positions 真实 ROM 来源已更正为 `0x5461C4` 编成矩阵，记录 `+2/+3`
  为初始 x/y；旧 `0x53D914` 结论已撤销。
- 新增可重复提取器 `tools/extract_positions.py`，共提取 `48×3×12=1728`
  条完整 `0xB8` 记录，并通过 `rom_positions` 无损回写。
- 单位物理数组基址是 WRAM `0x020240C0`，stride `0x1D4`；
  `0x02024294` 是 slot 1。
- 补丁冲突门禁发现旧 battle-config 模板会覆盖 `0x547934+`；
  已停止将未映射的 `scenario_id` 当 ROM 索引。
- 32/32 bank 已通过基准 ROM 字节一致性门禁；动态消费路径验证仍在进行。
- 新增只读 WASM 导航/WRAM 轮询探针 `play/_scripts/runtime-formation-probe.js`：
  可按 START → 新游戏 → 连续 A 计划导航，读取 `0x020240C0` 单位数组，并将
  `+0xC4/+0xC5` 坐标与 positions bank 匹配；已验证 core 就绪门禁与真实 WRAM
  读取。后续真实部署运行已进入首战，两次观察到 slot 1 `(4,4)` 并唯一匹配
  group 40 / variant 0 / record 0，因此 positions 已升级为 `runtime_verified`。
  当前导航已闭合 maps width/height A/B，并继续用于闭合真实角色定义的运行时证据。

### 2026-07-10 Bank 元数据审计基线

- 新增 `tools/audit_re_completion.py`，可重复检查 32 个 `sequel/content/*/bank.json` 的表偏移、格式字段、条目、验证标签和 Markdown 文档覆盖。
- 审计产物为 `notes/re-completion-audit.json` 与 `notes/re-completion-audit.md`。
- 首次审计结果为 23/32；随后已纠正错误偏移并从基准 ROM 重新提取。审计现采用双轨规则：23 个有效 bank 必须有非空 entries 和 ROM fidelity；9 个 `disproved` tombstone 必须为空、记录负证据并禁写回。调查闭合为 32/32，但这仍不代表动态语义或真实回写完成。
- 最新严格审计分布为 0 个 `static_verified`、10 个 `code_verified`、13 个
  `runtime_verified`、9 个 `disproved`；仍不能作为“100% 完成”的单独证据。

### 2026-07-11 Character growth 消费链修正

- 从精确地址零引用改为扫描 `0x545000..0x545458` 邻域，找到
  `0x0806D998 -> 0x08545068`，并反汇编闭合 `0x0806D964` 消费者。
- 真实表为 63×`0x10`，地址公式 `0x545068 + character_id*0x10`；ID 57/58
  分别复用 physical record 8/15。
- 七个 u16 成长字段写入模板 `+0x0E/+0x08/+0x02..+0x06`；首战 level 1
  会令正常增量为零，因此使用严格两因素插桩 A/B 避免伪阴性。
- character 1 record `+4` 从 100→200 后，template 与 battle slot 唯一变化为
  `+2: 15→16`，结构升级为 runtime_verified。
- 人物信息页与同边界 EWRAM 已把 template `+2/+3/+4/+5/+0A/+0C/+0E/+10`
  分别关联为攻击/防御/敏捷/移动/印/当前体力/体力上限/经验；growth 的体力、
  攻击、防御、敏捷、移动字段可同步命名。随后以 `0x08089AE0` 的标签行和数值读取
  行直接闭合 `template +8 = 查克拉容量`、`template +6 = 忍具数上限`，对应 growth
  `+2/+C`；两个运行值同为 5 不再构成歧义，也不再需要 UI A/B
- 章节最小语义创作链新增严格 codec；在 `End(00)` 与三字节
  `SetBattle(1A,id,mode)` 基础上，进一步沿 handler 闭合并开放
  `ShowPortrait(02,slot,portrait,expression)`、`UpdatePortrait(04,...)`、
  `SetSpeakerLabel(08,label_id)`、`AudioCue(1B,cue_id,mode)` 与
  `RenderText(01,encoded_text_hex)`。portrait 参数复用
  已闭合的 63×5 visual matrix 与 variant 5 特殊 pair，并限制真实 slot/记录边界。
  受控 primary
  scenario 39 探针选择 codec 输出
  `0x0809E800: 1A 28 02 | 00`，恰好 dispatch 两次并将章节/战斗状态 39→40。
  这证明 authoring bytes 的运行时因果，但生产 allocator、pointer+payload 原子回写和
  对话 opcode 子集仍未完成，短路线也未冒充 strict battle-map arrival
- alternate scenario 39 已由 control-aware text walker 完整拆成 25 条 command，边界与
  runtime 分布 `1B×1/02×5/08×8/01×8/04×2/00×1` 一致，末端精确落在
  `0x0803142E`。`1B` 已由 `0x08097C9C→0x08097140` 闭合为播放/等待/停止音频，
  `08` 已由 `0x080979E8` 与 12-byte 表 `0x085A57C4` 闭合为说话人标签选择；`02`
  按需创建 portrait slot 并等待转场，`04` 更新既有 slot，二者均通过
  `0x08096138` 选择 portrait/expression 资源。`01` 复用 `0x0806626C` 的控制感知
  token walker，并只承诺已编码字节的无损创作，不把汉化字形误当作 Unicode 同一。
  scenario 39 完整 25-command/`0x1AE` 字节现可 byte-exact codec 往返；analyzer 仍负责
  地址/raw 调查证据。生产 importer 已在独立 `0x5F8000..0x5FFFFF` 分区完成四字节
  对齐 allocator、immutable-base 指针校验与 payload+pointer 原子计划；真实构建将
  scenario 39 的 430 字节语义往返 payload 写到 `0x5F8000` 并重定向到 `0x085F8000`。
  旧 DB pointer-only 写回已禁用，避免绕过 codec。随后 runtime trace 捕获 selector
  实际选择 `0x085F8000`、25 次 dispatch，并在 `0x085F81AD` 的 `00` 正常终止，
  allocator→pointer→payload→interpreter 因果链已闭合
- skills initializer 字段链已纠正为 source `+0→runtime+1`、`+1` skip、`+2..+9`
  原位复制，`+A/+B` 另有 consumer。自然“术列表”控制器把 skill ID 1 与 `0x80`
  合并并命中 initializer；只改 row 1 `+4:6→7` 后，runtime `+4` 与可见攻击力
  `6×3→7×3` 同步改变，因此 skills 升级 runtime_verified
- skills 的非详情字段进一步闭合：`+0` 是战斗显示/动画族；`+A/+B` 构建前置技能到
  可联动候选的映射；`+C/+D` 是最多两个 ID 的资格白名单。它们均有明确消费者与
  错误反馈路径。自然详情另闭合 `+4` 攻击力、`+5` 距离、`+6` 成功率、packed
  `+7` 次数/直线和 `+8` 范围；`+2/+3/+9` 继续保持未知
- 战斗动作详情渲染器已锁定为 `0x080708BC`：action ID 高位清零时调用 effect
  initializer `0x0806D85C`，置位时才在 `0x08070906` 调 skills initializer
  `0x0806D910`。教程“忍者组合拳”是低位 effect 2，解释了旧 skills 探针零命中。
  旧强制 high-bit 诊断只作为负边界保留；现已由自然术列表 skill 1 的稳定可见 A/B
  取代，不能再用旧诊断的零可见差异否定新证据
- function-pointers 已从“11个看似有效 Thumb 指针”推进到真实 dispatcher 消费链：
  `0x08061D8C` 从 sentinel base `0x53D5F0` 按一基 ID 取表项并写入 task callback，
  11个 wrapper 均把对应 ID 传给 `0x08061C58`。自然标题人物图鉴路线两次命中
  ID 2 / entry `0x0853D5F8` / pointer `0x08061C99`；只把该四字节槽替换为相邻
  wrapper 3 后，同一输入提前分叉并留下未完成资料面板，因此升级 runtime_verified。
  variant 在再次 dispatch ID 2 前已分叉，其专用 scratch 为零，证据不把它误写成
  第二次 pointer hit
- `encounter-zones` 已证伪：其47行完整重复 maps，所谓 `zone_id` 实为已运行时
  追踪的 map `flags`/渲染配置字段；旧 bank 现为空且禁写。
- 历史 `cutscene-scripts@0x53DF70` 已修正为两个相邻的四记录视觉资源表：
  `0x08072EDC` 按 ID 0..3 解压 gfx/palette，并把第二组 pair 交给 sprite task，
  因此升级为 code_verified，但不再作为剧情脚本证据。
- 历史 `battle-encounters@0x542384` 已纠正为从真实 `0x54229C` 视觉资源表
  第14条 `+8` 处开始的错位切片；真实24条记录由剧情 opcode loader 消费，
  每条三条 LZ77 流，因此升级 code_verified，旧 editor 行禁写。
- 历史 `map-events@0x53EB08` 已纠正为完整 `0x53E698` 256×8-byte handler
  pair 表的 index 142 起始切片；消费者按 runtime state byte 同时选择 primary /
  secondary callback，因此升级 code_verified，旧47行 editor view 禁写。
- `battle-handlers@0x53E6D8` 又被证明是同一 handler-pair 表的 records 8..14
  重复视图，现为空、禁写的 disproved tombstone。
- `palettes` / `map-sprites` / `sprite-animations` 三个重叠目录已拆清：前两者
  分别修正为15条 motion/effect 参数与43条 sprite pair 并 code-verified；后者
  是 pair 24..42 的重复视图，已 tombstone。三个 legacy editor shape 均禁写。
- `fonts` 旧表跨入 handler pairs，已证伪；`levels` 修正为 `0x5459C8`
  45×12 effect/stat progression records；`resource-pointers` 修正为5×16嵌套
  descriptor。后两者均由消费者升级 code_verified。
- levels 的真正 Continue 已复现：Naruto level 1、经验100/250、训练点`+BA=0`；
  自然 selector 证明“移动→对战→木叶丸对白”消费 primary scenario 41 脚本
  `0x08031A12..0x08031D5F`，44 次 dispatch 后 opcode 00 正常终止、无 SetBattle，
  随后 UI 是 story 后任务准备而非标题图鉴。`A→B→Down×2→A` 曾产生瞬时 battle41，
  但完整 settle 回到 battle/map=0 的队伍页，已作为控制器假阳性撤销；真正入口必须
  settle 后仍可操作。目标仍是 A880=3 / level2 / 分配前训练点1
- scenario 41 开始任务控制流已纠正：`0x08097C78` 是 opcode `0x1A` handler 的
  中间指令而非 SetBattle 函数入口；story-only script 已留下 battle ID，正常开战由
  selector 4 → `0x08086A54 return 1` → `0x080871BE..C4` 复制到 battle control，
  不要求新增 selector/opcode hit。下一运行探针按该三段链路签发，详见
  `notes/battle-start-control-flow-20260713.md`
- `data-table-a/b` 已从20条尾片恢复为46条人物资料文本和79条战斗消息文本；
  `tile-assets` 已恢复为79×0x44战斗视觉 descriptor，三者均 code-verified。
  `menu-ui` 随后由 `0x08096138` 纠正为63×5 visual variant matrix，加 special
  variant 5 pair；旧20项是records 61–62。record 7 / variant 0 的单因素 pair A/B
  又令同一步 `ShowPortrait(1,7,0)` 从卡卡西变为小樱，因此升级 runtime_verified。
  当前无 static bank。
- `data-table-a` 的 selected-pointer hook 已通过自然标题人物图鉴闭合。两边均在
  `0x0808B1A4` 命中一次 character 0 / entry
  `0x085A143C`；只替换该四字节指针为 entry 7 后，目标从 `0x0859F988` 变为
  `0x0859FDE8`，可见多行人物简介同步改变，因此升级 runtime_verified。旧 state
  `0x20` checkpoint 属于另一套三栏 UI，不再作为此 reader 的前置状态。
  后续复放确认原输入没有加载随附 save；该纠正不影响 reader A/B，但禁止把它当作
  存档进度或 levels 入口
- 已新增 base-ROM 可独立重放的真实 battle 41 actionable checkpoint：Naruto
  `(4,10)`、Iruka `(4,4)`、map 36×44，strict arrival 全过。基于该边界的三条
  专属探针进一步排除了入场期 `resource-pointers`、普通忍术下的组合关系 reader、
  以及无效目标提示属于 `data-table-b` 的假设；三项严格保持 code_verified，下一步
  从有效攻击/技能事件捕获真实运行 ID。详见
  `notes/remaining-runtime-bank-probes-20260713.md`。
- battle 41 的最小编成诊断又把伊鲁卡移到相邻 `(5,10)`：敌对时可被范围光标选中，
  但教程拒绝直接攻击；同阵营时提交移动直接进入教程对白，skill-relation 专属 scratch
  仍为零。该路线是剧情假阳性，不再作为组合技能入口继续扩展
- `character-stats-b@0x545200` 被证明是 record 25 `+8` 的错位别名，保留
  disproved tombstone；错误 bytes 写回已改为 diagnostic。
- 交付：`tools/extract_character_growth.py`、
  `tools/build_character_growth_probe.py`、验证器和回归测试；完整证据见
  `notes/character-growth-runtime-chain-20260711.md`。

### 2026-07-11 Save-state 首战 SRAM 负结果

- WASM 探针现会在导航前后读取七个已知 SRAM 记录并验证 19+1 checksum；
- 标题→新游戏→首战路线成功，但七条记录均保持 `FF×20`，证明该路线不自动保存；
- save-state 仍为 code 证据，下一步必须定位并执行显式保存菜单，或在
  `0x08068684` 捕获真实写处理器调用；
- 结果与哈希见 `notes/save-state-wasm-probe-20260711.md`。

### 2026-07-10 u32 指针表回写进展

- 新增带索引边界、48 Mbit ROM 地址范围、Thumb bit 和数据指针对齐检查的通用
  u32 指针表真实回写 helper，并补充 6 项单元测试。
- `map_events` 与 story B–E 当前可生成 88 个真实表补丁，不再写 audit 保留区。
- 安全检查发现 `rom_battle_handlers` 和 `rom_map_sprites` 共 61 行 DB 数据使用陈旧
  `_rom_offset`，现已拒绝回写；下一工作周期需从 `rom/base.gba` 重新导入并验证。
- `battle_encounters` 的旧混合值解释仍需纠正；`cutscene_scripts` 已确认是八个
  视觉资源 pointer pair，不是脚本表。详见
  `notes/cutscene-visual-resource-consumer-20260712.md`。
- 第二批已把 data table A/B、function pointers、menu UI、resource pointers、
  sprite animations、tile assets 共 135 行转换为带严格校验的真实 ROM 回写；旧
  audit-only 不可达代码已删除。palette 因表冲突证据不足仍保持隔离。

```
P0-Step 1（mGBA调试） ✅
       ↓
P0-Step 2（tilemap） ✅
       ↓
P0-Step 3（战斗配置） ✅（ROM 表已定位，patch 生成可用）
P0-Step 4（章节流程）
P0-Step 5（资源提取）
P0-Step 6（变长对话）
P0-Step 7（测试闭环）
       ↓
100% 逆向覆盖
       ↓
网页编辑器开发
```

---

## 不该现在做的事

1. 不要现在开始写大量剧情 —— 格式还没定，内容随时可能废弃
2. 不要现在开始建网页编辑器 —— 等逆向覆盖到 80%+ 再动手
3. 不要把手工十六进制修改当正式开发流程 —— 一切要走 pipeline

---

## 网页编辑器架构（逆向完成后）

**技术方案：** FastAPI + Vue + SQLite

**服务器：** 14.103.49.74:443（Debian 12，2核/4GB）

**架构图：**
```
用户浏览器 (Vue)
    │ HTTPS
[FastAPI 服务]
    │
 ┌──┼──┐
 │     │
SQLite  ROM文件
(队列)  (本地)
 │
WebSocket
(协作编辑)
```

**功能模块（逆向完成后按序开发）：**

| 模块 | 说明 |
|------|------|
| 对话编辑器 | 文本表单，调用 import_dialogue.py |
| 地图编辑器 | Canvas 瓦片地图，调用 import_map.py |
| 角色编辑器 | 数值表单，调用 import_battle_config.py |
| 技能编辑器 | 效果链配置 |
| 道具编辑器 | 表格编辑 |
| 剧情编辑器 | 分支对话树 |
| 构建验证 | build_mod.py 输出可下载 patch ROM |

**优先级：** 对话 > 地图 > 角色 > 技能 > 道具 > 剧情

---

### 2026-07-21 Butano 功能等价重建预研

- 已在 `codex/butano-foundation-research` 分支将 Butano 21.7.1 固定为 submodule，提交为 `112a1827c9c6d9e6041a7e93e66f04c4561a6415`；源码、离线 API 文档、示例和完整游戏样例均保存在 `third_party/butano/`。
- devkitARM Docker 工具链已按不可变 SHA-256 摘要锁定；最小木叶战记工程、官方 sprites 示例和 audio 示例均完成编译验证。
- 原 40/66/106 人周与 70–90 人周预算已取代，不再作为计划依据。当前估算以同一 Codex 模型实际完成的 B1–B6 六项任务为样本：总计 29.34 分钟，覆盖行动状态机、寻路、战斗效果、章节脚本、存档编解码与 Butano ROM 集成。
- 按 900 个逻辑单元与 160 个集成单元外推，全部基础系统功能等价重建为 80.9/121.3/191.2 Codex 连续墙钟小时；建议按 121.3–191.2 小时规划，并在首个真实纵切片后重校。该口径不计逆向补证、内容生产和旧存档兼容。
- 预研报告见 `docs/butano-konoha-systems-cost.md`，原始计时记录见 `notes/butano-agent-timing-benchmark-20260721.md`，本地使用手册见 `docs/butano-local-reference.md`。本阶段已实现可运行的五类基础微型纵切片及 ROM 内嵌自检，但尚未完成完整战棋、章节、AI、成长和内容系统。

### 2026-07-21 Butano scenario 41 战斗纵切片

- 选择运行证据最完整的 scenario 41“鸣人对伊鲁卡”作为首个功能等价关卡：9×22
  战棋格、初始坐标 `(4,10)` / `(4,4)`、移动暂存与取消、COMBO/WAIT 菜单、敌方
  确定性寻路、第 4 回合组合技胜利、结果页和重开均已进入 Butano 工程。
- 关卡领域核心与 Butano 显示层分离；新游戏测试覆盖初态、移动、取消、AI、非法目标
  不变性、自然胜利、结果/重开和页面文案，既有 benchmark 能力通过兼容头继续复用。
- 用户手册见 `docs/butano-scenario-41-battle.md`，构建及运行证据见
  `notes/butano-scenario-41-runtime-20260721.md`。资源守卫下的干净构建、17 次显式输入、
  胜利/结算/重开截图与最终 save-state 均已完成；移动范围原先逐格执行 198 次寻路导致
  输入丢失的问题也已修复并由同一冷启动路线复验。该单关卡纵切片当时被标记为验收完成，
  但这一结论已在 2026-07-22 在线录屏复核后撤销；入口演出和通用玩家/敌方行动循环补齐前，
  只能复用其局部资产、组合拳动画和已验证音频，不能作为完整功能等价关卡。

### 2026-07-22 Butano 通用战斗架构首个实现切片（2026-07-23 已否决）

- 当时新增了固定容量 `BattleSession`、行动资格、演出队列、能力/效果、目标表达式和确定性 AI 等类，并让 scenario 41 的固定路线调用它们；但这些类没有消费完整角色/动作数据，也没有生成原作完整回合，因此不能据此称为通用战斗架构已经实现。
- 入口现按“玩家亮相 → 敌方亮相 → 开始标题 → 30 帧自动黑场 → 可见对白等待 → 手里剑转场”推进；自动步骤不读取 A，L/R 已接入可行动单位轮换。确认开始后不再依赖黑屏中的额外 A。
- GBA 运行暴露了宿主测试未显示的性能问题：逐候选格重复 Dijkstra 会令敌方阶段长时间停帧。现改为单次可达代价场，受守卫 mGBA 在 frame 740 正确进入教程，并完成 2580 帧胜利/结果/战后路线。
- 当前 ROM SHA-256 为 `e04e218e9dbcede120f0b8544e44a47df68160258539d40eea303afd25fa44a6`；证据见 `notes/butano-battle-architecture-implementation-20260722.md`。
- 本节的旧“状态/规则架构已落地”结论已被 2026-07-23 用户验收推翻。入口和战斗主体使用截图/固定选项拼接，scenario 43–50 所需的多单位、召唤、护送、捕获、替身以及完整角色/技能内容均未实现；旧 ROM 只保留为反例和素材对照，不再作为新架构实现基线。
- 2026-07-23：纠正 Butano scenario 41 的截图拼接实现。活动战斗阶段已改为组件渲染，角色 1/30
  从生成内容实例化，玩家教程动作与敌方六动作 loadout 进入共享 resolver/AI；mGBA 完整 2580 帧
  路线通过。ROM SHA-256 `aefce90b11fcf9f41a7442ed73b36e69b3c5986be2a00a98cb8b6ecfd5c91b0d`。
  这只完成了领域基础与单关运行闭环，剩余 handler、多目标、完整 AI/condition 和跨关卡场景继续推进。
