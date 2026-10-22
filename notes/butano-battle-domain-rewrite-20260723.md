# Butano 战斗领域与组件渲染纠错记录（2026-07-23）

## 纠错原因

用户复核指出，旧 scenario 41 以预制整屏画面和固定菜单路线拼出战斗外观，不能视为战斗架构。
本轮以此为失败基线：交互阶段的地图、单位、游标、HP、菜单、目标和结果必须来自同一份领域状态，
表现层不得写入坐标、HP、资源、行动账本或胜负。

## 已替换的运行链

- `battle_action_system.h` 将成本、效果、目标、范围、升级和表现绑定拆成正交策略；预览无写入，
  最终解析使用 session 副本原子提交，并支持逐 hit、命中 RNG、伤害、治疗、召唤、忍具槽消耗、
  写轮眼一次性反应和明确的 unsupported handler 错误；
- `battle_action_loadout.h` 从 63 条角色模板的 15 个主动槽按初始状态和等级生成实际动作列表，
  再与 87 条主动动作定义表做引用校验和实体化。鸣人等级 1 的通用列表是 `[2,5,7]`；
  scenario 41 的教程规则显式限制为动作 5，而敌方角色 30 的 AI 消费完整 `[1..6]`；
- AI 对每个可达落点和每个装备动作调用与玩家相同的 `battle_action_resolver::preview_units`，
  只提交合法且评分最高的候选；不再接收唯一的硬编码攻击，也不再按回合号移动到固定坐标；
- 该轮曾让 resolver 的动作提交显式携带面向；这一做法已在 2026-07-24 的两阶段行动尾部
  纠错中取代。现在玩家与 AI 都只在效果和 condition 之后选择面向。任务保护单位缺失会返回
  `invalid_objective`，不会继续生成候选；
- `scenario_41_scene.cpp` 不再引用 `scenario_41_combat_layers.h`。活动战斗阶段统一保持一张清理后的
  `scenario_41_clean_map`，鸣人、敌人和游标分别由 sprite 按领域坐标移动，HP 和菜单由
  `present_scenario_41` + `render_battle_overlay` 实时生成；敌方 HP 归零且 `active=false` 后 sprite 消失；
- `generate_butano_battle_runtime_assets.py` 从哈希绑定的旧参考图机械派生无单位地图和独立敌方 sprite。
  生成只改变原图两个 32×32 区域，测试逐像素证明其他位置不变。一次内置生成式去物体尝试会改变
  整张像素图和尺寸，已判为不合格且没有进入工作区或 ROM。

## TDD 与验证

本轮新增或扩展的红绿测试覆盖：

- 当时的 resolver 动作提交面向测试（现已由独立 action-tail 测试取代）；
- AI 保护目标配置错误；
- 多动作 AI 严格择优；
- 角色动作列表、等级解锁、关卡过滤和定义引用；
- 地图/敌方 sprite 的确定性生成和像素改动边界；
- 活动场景禁止重新引用整屏 combat layer；
- 实时 presenter 的行动菜单和术菜单。

验证结果：

- 宿主 C++：20 个测试程序全部通过；
- Python 相关生成器、构建、素材和研究文档测试：50 项通过，1 项环境开关构建测试跳过；
- `py_compile` 与 `git diff --check` 通过；
- Butano/ARM 构建经 `tools/run_guarded.py` 完成，峰值 RSS `64.75390625 MiB`，无降级；
- ROM：`butano-sequel/butano-sequel.gba`，大小 `7,605,664`，SHA-256
  `aefce90b11fcf9f41a7442ed73b36e69b3c5986be2a00a98cb8b6ecfd5c91b0d`；
- ELF SHA-256：`e80e2ca8a5cd476181edc0586e69d618fa5b0c2781f111ec32d5e8a84bb4c045`；
- mGBA 完整路线：`build/butano-component-runtime-20260723-01/`，2580 帧成功标记、最终 savestate、
  交互阶段和战后截图齐全；守卫摘要
  `build/resource-guard/butano-component-runtime-20260723-01.json`，峰值 RSS `53.56640625 MiB`，
  `completion_trigger=success-marker`。本次自动验收静音运行，因此不作为音频质量证据。

## 当前边界

这次已经修复“交互战斗由整屏截图和固定伤害驱动”的错误，但不能宣称完整功能等价：

- 教程对白、胜利和战后结算仍暂时消费参考帧；它们只读领域结果，
  但后续仍应从原始 tile/sprite/timeline 重建；
- 87 条主动动作和 94 条忍具已经有完整模板，仍有 resolver handler 尚未实现，未实现项会被明确拒绝；
- 多目标范围、完整属性状态 reducer、递归反击/联动、完整七槽 AI utility、47 场 condition 数据、
  多角色/多敌/召唤/护送的通用运行场景仍需接入；
- scenario 41 facade 仍含关卡演出兼容状态，不能拿单关成功代替跨关卡架构验收。

## 2026-07-24：状态链、联动解析与组件攻击演出

用户再次复核后确认，旧攻击阶段虽然已把交互战场拆成组件，仍通过
`scenario_41_attack_animation_frames.h` 连续播放整屏录屏帧。这条路径已经移除，不能再把
录屏画面计入战斗实现。

本轮补齐的领域闭环：

- `battle_attribute_system` 从单位基础快照按 16 个状态槽顺序重算攻击、防御、敏捷、移动和
  最大 HP；预览、命中与伤害共享同一属性视图。`0x26` 原子建立四个 modifier，容量不足时
  session 保持不变；
- 状态 duration 统一按原 ROM `(raw_duration & 0x7F) × 2` 写入，每个 side end 递减；
- effect `0x03` 在事务副本中移动 source，并把新位置同步到 action draft 后再统一提交；
- effect `0x05` 只覆盖 `character_id`，状态 `+4` 保存 linked unit；HP、资源、位置、
  行动账本和状态库不复制。自然到期、cleanup 和战败均恢复 original identity，原始 ID
  8/15 的变体条件映射也保留；
- 状态 `0x0E` 在每个有效 hit 内先以同一 amount 递归结算 linked target，再结算主目标；
  guard 禁止二次递归。`action_result.damage_steps` 保留 hit、目标、联动标记、实际伤害和
  击倒顺序，不再复制“总伤害”；
- 状态 `0x0D` 的 source/target 消费、六种 reaction event 排除和 target raw bit
  `0x100` 清理进入共享 resolver policy；
- 动作 43–49 通过同一 `0x13` record 完成阶段生产、替换、资格原因码 9–20 和
  effect `0x14` hit count；模板 base hit 为 0 的表/里莲华由阶段低字节产生真实 hit 数。

攻击表现改为 `battle_action_animation` 的 96 帧只读姿态流：蓄力、接近、三次 impact、
受击闪烁/抖动、返回和稳定帧都只修改 sprite 的临时显示偏移，不写 HP、坐标、状态或结果。
`scenario_41_scene.cpp` 在整个演出中保留 `scenario_41_clean_map`，运行源码已无任何
`scenario_41_attack_frame_*` / attack-alpha 引用。未引用的旧参考资产仍保留在本地作为
历史取证材料，不参与 ROM 运行链。

验证结果：

- 红灯分别复现缺少位移结果、身份覆盖字段、战败不恢复身份、联动事件树、八门资格服务、
  `0x14` 零基础 hit 和组件动画系统；最小实现后全部转绿；
- 26 个宿主 C++ 测试程序全部通过；
- `python3 -m unittest tests/test_analyze_battle_*.py`：97 项通过，13 项按既有环境条件跳过；
- 排除三个依赖已清理历史 `build/` 捕获源的归档导出器后，Butano 相关 Python 回归
  94 项通过、1 项显式构建开关测试跳过；三个归档模块分别缺少
  `scenario-41-attack-trace-20260722-01`、`scenario-41-attack-trace-20260722-04` 和
  `macos-prebattle-frame80-step2-20260715` 输入，未伪报为通过；
- ARM/Butano 构建守卫：
  `build/resource-guard/butano-domain-animation-20260724-01.json`，
  exit 0、`degraded=false`、峰值 74.96484375 MiB；
- ROM：`butano-sequel/butano-sequel.gba`，5,268,584 字节，
  SHA-256 `56c77c2d6b1340fcee7b9771f40a8b419120b4655f23b94aae1140b442b91621`；
  ELF SHA-256 `d23770a0fdd6d0aedb1e4ed7f0fccdb687a7413d95c7966871cfb7291277a911`。
  与上一版 7,605,664 字节 ROM 相比减少 2,337,080 字节，且 ELF 字符串表不再含攻击整屏
  frame/alpha 符号；
- mGBA 0.10.5 script-backport 经同一 heavy guard 冷启动完成 2580 帧路线，生成 44 张截图、
  final savestate 与成功标记。证据目录
  `build/butano-domain-animation-runtime-20260724-01/`，守卫摘要
  `build/resource-guard/butano-domain-animation-runtime-20260724-01.json`，
  `completion_trigger=success-marker`、`degraded=false`、峰值 88.8984375 MiB。
  本次静音运行只证明流程与图形，不签发音频听感。

剩余边界没有变化：未闭合的 resolver handler 不得猜测实现；七槽 AI utility、完整 condition
内容、多单位/多敌/召唤/护送的跨关卡运行验收仍需继续。

## 2026-07-24：跨关卡 AI 目标索引与标准效用主链

旧 `battle_ai` 仍要求 scenario 预先指定唯一 `target_unit`，然后只在这个目标和可达落点之间
比较 `1000 + damage × 100`。这不符合原 ROM 已闭合的“全候选生成 → 状态过滤 → 七槽目标
评分 → 严格择优”，也无法支撑多敌与支援动作。本轮按
`notes/battle-ai-utility-policy-bindings-20260723.json`、
`notes/battle-ai-status-policy-bindings-20260723.json` 和
`notes/battle-ai-planner-static-20260723.json` 替换这条简化链。

实现边界如下：

- `battle_ai_target_index` 按活动单位槽顺序，为同阵营和异阵营分别维护最低 HP 比例、最大 HP、
  攻击、防御、敏捷、移动和地图距离七个目标槽；指标相等时不替换，因此保留首次扫描单位。
  `battle_unit_instance` 新增中性的 `ai_role`/`ai_linked_unit` 字段，role 2 指向 role 0 时
  按原证据覆盖异阵营七槽；
- `battle_ai_utility_scorer` 消费模拟 actor、七槽索引和固定容量 queued event。异阵营权重
  `[1700,800,800,1300,1000,800,3600]`、同阵营权重
  `[4200,2000,1000,1000,1000,800,0]` 按 effect low 3 门控到独立 bank；每个 selector
  对重复 event 最多加一次。damage family `0x01/0x14/0x15` 先按目标聚合，再把截顶伤害、
  最大成功率、覆盖率和相对范围求和成一个组件。配置组件保留零值进入整数平均；
- 状态感知评分实现两组 target status-any 门、`0x1E/0x20/0x22/0x24/0x26` 同族门，
  以及 actor `0x12/0x12`、`0x0D/0x0D` 首次匹配时在整数除法前一次性减去
  `weight[0x84]+weight[0x1C]`。event `0x11` 在投影 HP/查克拉都高于一半，或投影位置
  位于既有 `battle_ai_candidate_field` 的敌方伤害威胁区时复用同一减分，且不增加分母。
  第一条 event 为 effect `0x07`、无 active typed scenario rule 且其选择位置安全时，
  则向分子加入固定 8000，同样不增加分母；event raw position mode 保留 actor/target
  两种位置来源。
  普通评分最后只消费
  15-bit RNG 的 0–9 项；actor action-state 低位为 2 时走独立 0–99 随机分；
- 通用 planner 现在枚举“每个可达落点 × 每个动作 × 每个符合 target policy 的活动单位”，
  每个候选仍调用玩家共用的 `battle_action_resolver::preview_units`。关卡显式
  `target_unit` 只作为可选约束；留空时 AI 能自行选择敌方目标或受伤友军。候选仍只在
  `score > best.score` 时替换，无合法动作安全结束；
- scenario 41 的首个敌方回合回归仍移动到 `(4,6)` 并造成 `80→75` 的真实 HP 变化，
  证明标准效用接入没有退化成无伤害的截图/演出分支。

TDD 与验证：

- 红灯先证明目标索引头文件不存在、无预设 `target_unit` 时旧 planner 直接结束行动；
  绿灯覆盖七槽、严格 tie、role override、两组状态门、五组同族门、伤害聚合、资源/生存、
  0–9/0–99 RNG、自动敌方选择和友军治疗选择；
- 28 个宿主 C++ 测试程序全部通过，守卫摘要
  `build/resource-guard/butano-ai-host-tests-20260724-03.json`，exit 0、
  `degraded=false`、峰值 40.015625 MiB；
- battle 分析测试 97 项通过、13 项按既有证据条件跳过；Butano 构建/文档/音频/运行脚本
  61 项通过、1 项显式集成开关跳过；
- Docker 内 ARM/Butano 构建经守卫
  `build/resource-guard/butano-ai-runtime-build-20260724-05.json` 完成；
- ROM 为 5,271,832 字节，SHA-256
  `e7fa2ba26421d9d04e190b7e9c54a92e6388e6a5275c2f784a13c84037f17fd2`；
  ELF SHA-256 `2c8a6ea291ce71e674806125e55f37e25f651304fce607d13476141154378dd4`；
- mGBA 冷启动完成 2580 帧、44 张截图、最终 save-state 与成功标记。证据目录
  `build/butano-ai-runtime-20260724-04/`，守卫摘要
  `build/resource-guard/butano-ai-runtime-20260724-04.json`，
  `completion_trigger=success-marker`、`degraded=false`、峰值 88.9296875 MiB。
  本次仍为静音自动验收，不签发音频听感。

本轮还记录一项宿主环境异常：启动 LLDB 后，未签名的 Homebrew Python 和自编译 mGBA
在 macOS AMFI/taskgated 边界进入 `U` 状态，均发生在用户代码/ROM 第一帧之前；原始 mGBA
运行 `butano-ai-runtime-20260724-01` 因而是 protection failure 且输出目录为空，不能作为
游戏失败证据。验证使用 `build/` 内 ad-hoc 签名的测试二进制和 mGBA 副本恢复，未修改用户
原始工具。若遗留的 `U` 状态进程在内核层拒绝信号，只能在本轮证据保存后通过宿主重启清理。

剩余边界：四槽 typed `AiScenarioRule` kind 1–5 尚未接入 planner；empty-tile、范围多目标、
召唤槽与复合 queued event 的候选生成仍待实现。完整 condition 数据、多单位/多敌/召唤/
护送跨关卡运行时也未完成，因此不能把本轮称为完整战斗系统或功能等价完成。

## 2026-07-24：47×3 有序 condition 与战场对象表

旧 `objective_engine` 使用任意规则列表和数值 priority，无法表达原 ROM 每个 variant 固定
四个胜利槽、四个失败槽及“同槽返回结果 5”的规则。本轮新增
`battle_condition_interpreter` 并把 scenario 41 的结果判定迁移到原 ROM 内容表：

- `battle_condition_variant` 固定保存 4 字节头、四胜和四负；两组分别按槽位顺序找首个命中。
  只有胜方命中返回 1，只有负方命中返回 2；双方都命中时较小槽位抢占，相同槽位返回 5。
  结果 1/2/5 分别映射 presentation ID 1/2/3，三者都标记结束战斗；
- 解释器实现记录实际使用的 type 1/2/3/6/7/8/9：阵营无有效单位、完整回合上限、
  指定阵营/角色缺席、`arg0+1` 对象槽失活，以及到限时双方 HP、有效单位数和 behavior 9
  对象结算计数比较。未被 47 场记录引用的 type 4/5 明确返回 unsupported；
- `battlefield_object_table` 保留 32 个 16 字节槽，槽 0 不分配；allocate 从槽 1 开始，
  free 只清 type。behavior 9 解析先释放对象，再按 resolving unit 阵营累加独立计数；
- `tools/generate_butano_battle_condition_content.py` 对完整记录区 SHA-256
  `0d6e137011aa4e97c5b5d165f1939b7fb0b33235b9b20fceb1566b485dc35bf4`
  做门禁，生成 `generated_battle_condition_content.h` 的 47 场 × 3 variant；
- scenario 41 现在消费生成表 `battle_condition_variants[9][0]`，不再调用
  `objective_engine::evaluate`。该 variant 的胜负首槽分别是敌方无有效单位和我方无有效单位。

验证结果：

- 29 个宿主 C++ 测试程序通过；新增测试覆盖单方命中、不同首槽抢占、同槽结果 5、
  完整回合门、对象分配/释放/计数、HP/人数/对象计数比较和 unsupported type；
- 宿主测试守卫摘要
  `build/resource-guard/butano-condition-host-tests-20260724-01.json`，exit 0、
  `degraded=false`、峰值 51.1953125 MiB；
- battle 分析 97 项通过、13 项按证据条件跳过；condition 生成与 Butano 相关回归
  64 项通过、1 项显式集成开关跳过；
- ARM 构建守卫
  `build/resource-guard/butano-condition-runtime-build-20260724-01.json` 完成；
  ROM 5,272,420 字节，SHA-256
  `99c0d6a23bb64a7a7c3ee473c9e4d93c24147017ffa47b97fbd9875c42c9bb7f`；
  ELF SHA-256 `e48f8cc4687e272ef0bfa68b88c041dcbd459c8c403404277c7854888e34f990`；
- mGBA 2580 帧路线生成 44 张截图、save-state 和 success marker。证据目录
  `build/butano-condition-runtime-20260724-01/`，守卫摘要
  `build/resource-guard/butano-condition-runtime-20260724-01.json`，
  `completion_trigger=success-marker`、`degraded=false`、峰值 88.92578125 MiB。

这一里程碑闭合的是 condition 数据与解释器，不等于 47 场已经都可游玩：关卡单位部署、
地图/对象实例、脚本触发点和多单位回合仍需生成并接入；result 5 的可见名称也继续保持中性。

## 2026-07-24：多目标事务、召唤图、多单位调度与效果处理器闭环

本轮直接针对“把截图和选项拼成假战斗”的问题继续收紧领域边界。表现层仍可读取
`BattleSession`，但目标集合、资源扣除、效果队列、召唤关系、回合推进、战场对象和胜负条件
都必须由同一会话产生。

ROM 绑定证据：

- `0x0806A4AC..0x0806A774` 的面积构造器确认动作运行记录 `+8` 的低 7 位是含中心格的
  size；高位 0 是曼哈顿菱形，高位 1 是四条轴线。三处分支均回调同一目标策略函数
  `0x0806A2F4`。分析器与清单位于 `tools/analyze_battle_range_shape.py` 和
  `notes/battle-range-shape-bindings-20260724.json`；
- `0x08077040..0x0807764E` 的效果分派区 SHA-256 为
  `2e80b66092e3dd94ecdc20afdfb93e9cd41b6e549ab04e92c33c1cf6fc2282c0`。
  单复制、身份变体复制、成对分身分别调用 `0x0806ADD0`、`0x0806AEE8`、
  `0x0806B030`；战场对象统一调用 `0x08081024`；普通/特殊伤害共用
  `0x08076A30`；反应状态交给 `0x0806A8C0`。可复核清单位于
  `notes/battle-effect-handler-bindings-20260724.json`；
- effect `0x06/0x1A` 按目标最大 HP 百分比恢复，不是固定点数；`0x1C/0x1D`
  分别对查克拉做上限/下限钳制；`0x0C/0x18` 创建 type 2/type 1 战场对象；
  `0x11` 组合状态 2、HP 恢复和查克拉恢复；`0x15/0x3F` 还会更新独立的反应状态。

实现闭环：

- `battle_target_set` 按单位槽顺序收集范围内所有合法目标。`preview_area` 不写会话；
  `resolve_area_draft` 只提交一次成本，再对每个目标独立执行命中、状态、联动伤害和战败，
  最后原子替换会话。AI 为同一候选生成多条 queued event，覆盖率与效用评分不再只看中心目标；
- `BattleSession` 把“可浏览阵营单位”和“本阶段可下命令单位”分开。L/R 可以查看已行动单位和
  scripted 护送单位，但 scripted/死亡/已完成单位不能被玩家或 AI 选中。任一阵营会依单位槽
  顺序连续完成全部可行动单位，再切换阵营；敌方最后一人结束后才进入新完整回合；
- effect `0x02` 复制 source 全部战斗数据并建立双向 link，新单位出生阶段已完成；
  `0x07` 在角色 8/15 的身份变体映射后复制；`0x17` 同时建立 source、primary clone、
  auxiliary clone 的两级 link 图。稳定 slot id 不被复制覆盖，下一完整回合才恢复行动资格；
- `battlefield_object_table` 从条件上下文移入 `BattleSession`。动作创建、behavior 9 释放、
  分阵营完成计数和 type 6/9 条件读取同一份状态。条件上下文是只读会话快照，不再由场景手工
  添加两个单位；生成 variant 的 `header[0]` 直接提供回合上限，完整回合边界由 session 标记；
- `battle_condition_interpreter::evaluate_session` 使清敌、护送角色死亡、限回合比较和对象目标
  使用统一入口。跨系统集成测试在一个会话内组合两个玩家单位、scripted 护送、两个敌人、
  成对召唤和双目标范围击杀，并另行证明敌方真实伤害护送角色后立即得到 loss。

验证结果：

- 37 个宿主 C++ 测试程序经系统 Clang 编译、ad-hoc 签名并全部执行通过；守卫摘要
  `/tmp/gba-naruto-host-suite-final-summary.json`，exit 0、峰值 RSS `64.0703125 MiB`；
- 与本轮变更直接相关的 Python 逆向、生成、构建、文档、音频和运行脚本回归
  68 项通过、1 项按集成开关跳过；
- Docker/devkitARM 增量构建通过，守卫摘要
  `/tmp/gba-naruto-arm-build-final-summary.json`；ROM 为 5,283,892 字节，SHA-256
  `d706dae121a73437bfee998aa4dab90ba7a5f667a37668a09d170f025700ebcd`；
- 签名 mGBA 经同一 heavy guard 完成 2580 帧路线，产出目标选择、三次 impact、胜利、
  结算、44 张截图和 final save-state。证据目录
  `artifacts/butano-battle-runtime-20260724-1805/`；
  `completion_trigger=success-marker`、峰值 RSS `108.1484375 MiB`，final state SHA-256
  `3c406059e6f6b90f59d6e5ba2257e6659a11b69278144b0b0bc4e17375a97873`。

全仓 185 个 Python 模块的一次性 `unittest discover` 被资源守卫以
`protection-failure` 拒绝，不能记录为通过；守卫已确认本次测试/mGBA 进程树没有残留。
本轮改动范围采用上述 68 项定向回归、全部领域 C++ 程序、ARM 构建和 mGBA 路线验收。

当前边界：领域核心已经是可组合的真实战斗运行时，不再是截图状态机；但 47 场的地图部署、
关卡脚本触发和失败/特殊结算表现还没有全部接入 Butano 场景，因此仍不能宣称全游戏
“功能等价完成”。mGBA 本轮为静音自动验收，也不签发音频听感结论。

## 2026-07-24：47 场地图/编队生成与真实场景装载

本里程碑把逆向得到的地图尺寸和初始编队接到 `BattleSession`，不再由每个 Butano 场景
手工构造两个测试单位：

- `tools/generate_butano_battle_scenario_content.py` 严格读取 47 条 maps 记录和
  positions 的 47 组 × 3 variant × 12 record，生成
  `generated_battle_scenario_content.h`；生成器验证地图逻辑格、阵营、坐标、面向和
  角色引用，并在相同输入下生成字节稳定的头文件。全部固定槽中有 476 条启用记录：
  329 条固定角色记录和 147 条部署占位记录；
- 输入 `sequel/content/maps/bank.json` 的 SHA-256 为
  `a8e224f9ac3c243707e33706ef2cf2042cb2a13cd8607207622f55cc78d0f367`，
  `sequel/content/positions/bank.json` 的 SHA-256 为
  `1e9d2822e486c6e79c9ad4f1545915fa378505dd1b58e840f939fd1032fd55e9`；
- positions 的记录公式是
  `0x5461C4 + battle_id×0x1AAC + variant×0x08E4 + 4 + record×0xB8`。
  `0xFA..0xFF` 仍是动态部署占位符；加载时没有显式角色绑定就返回错误，绝不把未知值猜成角色；
- `battle_scenario_loader` 在临时 session 完整验证后才提交，容量不足、无效/未激活角色、
  未解析占位符或重复实例都保持原 session 不变；
- battle 15 variant 0 真实装载 9 个单位：三名玩家、位于 `(4,5)` 的角色 30 护送对象，
  以及五名角色 35 敌人。护送对象可由 L/R roster 浏览，但不可发出玩家命令；三名玩家依次
  完成行动后进入敌方阶段，敌方动作通过共享 `battle_action_resolver` 击倒护送对象，
  护送对象死亡后返回 loss，`battle_condition_variants[15][0]` 随即结束战斗；
- scenario 41 现在也从 `generated_battle_scenario_content.h` 的编队 41 装载角色 1 和
  角色 30，初始坐标仍为 `(4,10)` / `(4,4)`，既有入口、移动、AI、胜利和黄金路线测试不再
  依赖构造函数里的手写单位。

验证结果：

- 39 个宿主 C++ 测试程序经系统 Clang 编译、ad-hoc 签名并全部执行通过；守卫摘要
  `build/resource-guard/butano-scenario-host-tests-20260724-01.json`，exit 0、
  `degraded=false`、峰值 RSS `73.46484375 MiB`；
- 场景生成、condition 生成、Butano wiring、研究文档、音频和 mGBA 脚本定向回归
  68 项通过、1 项按集成开关跳过；
- Docker/devkitARM 构建经
  `build/resource-guard/butano-scenario-arm-build-20260724-02.json` 完成。ROM 为
  5,324,420 字节，SHA-256
  `07ea2e47d4b878078fa107cf1300dd77c12a52e9d9e0b7d9ad7852f669cc2f6a`；
  ELF SHA-256 `752f9bd32220a792264f0753186e99ccfb117efdc33226aa0544f295ae63229f`；
- 签名 mGBA 在同一 heavy guard 下完成 2580 帧场景 41 可见回归，生成 44 张截图、
  audit、success marker 和 final state。证据目录
  `artifacts/butano-scenario-runtime-20260724-1830/`，守卫摘要
  `build/resource-guard/butano-scenario-runtime-20260724-1830.json`，
  `completion_trigger=success-marker`、峰值 RSS `89.0234375 MiB`；final state SHA-256
  `3a6af7bfc98ca681fcbbf1a0702e9ecbe13bc2aa959b07507c7f6a573f38822c`。
  本轮 mGBA 仍为静音自动验收，只签发流程与图形回归，不签发声音听感。

本轮闭合的是“场景数据 → 单位实例 → 回合/动作/条件”的领域 wiring。它仍未实现 47 场的
地图 tile 渲染、章节入口/剧情触发、动态占位选择 UI、战场对象初始布置和全部结果演出；
因此 47 场地图与编队不等于 47 场可游玩，也不能据此签发全游戏功能等价。
# 两阶段行动尾部运行时（2026-07-24）

此前 `battle_action_resolver` 在扣除成本、移动和应用效果后直接调用
`commit_action(facing, no_ability)`。这会把 actor 立即标为完成并推进阵营，跳过原 ROM
已绑定的 `0x8000 → 0x9000 → 0x9100/0x9200 → 0xD000` 顺序；scenario 41 的致死
组合拳只因胜利立刻抢占而掩盖了这一错误。

本轮按红绿重构拆成两个事务边界：

1. resolver 成功后只提交移动、成本和效果，进入 `effects_resolved`；
   `ledger.completed` 仍为 `false`，draft actor、当前阵营和下一单位资格不变；
2. `battle_turn_flow::after_effects` 先解释关卡 condition。结果成立时保留
   `effects_resolved` 并结束战斗；否则打开朝向选择；
3. 朝向确认进入防御选择，`battle_turn_flow::complete_defense` 才在会话副本上写入防御、
   完成单位、执行 side-end 状态 tick，并推进同阵营下一单位、阵营或回合；condition
   解释失败不会污染真实会话。

玩家与 AI 现共用这条尾部。scenario 41 的“行动结束”逐屏驱动 session 的朝向与防御状态；
玩家技能和敌方能力都先走 `after_effects`，AI 只自动选择面向及 `no_ability`，没有直接完成
行动的旁路。battle 15 集成测试还验证三名玩家依次完成尾部后才切到敌方，敌方击倒护送角色
30 时 loss 在 `effects_resolved` 抢占，跳过敌方朝向/防御。

TDD 证据：

- 红：`test_battle_action_tail.cpp` 因缺少 `effects_resolved` 与三段尾部 API 编译失败；
- 红：`test_battle_turn_flow.cpp` 因缺少 `battle_turn_flow.h` 编译失败；
- 绿：41 个宿主 C++ 测试程序全部编译、签名并执行通过，资源守卫摘要为
  `build/resource-guard/butano-action-tail-host-20260724-05.json`，峰值 tree RSS
  66.6484375 MiB；
- source-wiring 回归要求 scenario 41 同时调用 `open_facing_selection`、
  `select_facing`、`battle_turn_flow::after_effects` 和
  `battle_turn_flow::complete_defense`，并禁止关卡 facade 出现 `commit_action(`。
- scenario/condition 生成、Butano wiring、研究文档、音频和路线脚本 70 项定向 Python
  回归通过，1 项按既有集成开关跳过；Python 3.9 的四项部署自检也通过；
- Docker/devkitARM 构建摘要为
  `build/resource-guard/butano-action-tail-arm-build-20260724-03.json`，exit 0、
  `degraded=false`、峰值 tree RSS 19.73828125 MiB。ROM 为 5,326,148 字节，
  SHA-256 `930fd83f4858c203142456cdb4368855a14f70d0ac3900e38a33a5ae487c786c`；
  ELF SHA-256 `9ccb33264678ea1b9be137f1aab6e88beaff36193fc8a3654f622f4634ddbea3`；
- mGBA 预检先发现 25 份 2026-07-22 及更早的历史 crash report，当前 ROM 尚未启动。
  这些报告经 `clear_crash_latch()` 写入 history 并建立基线后，签名 mGBA 0.10.5
  script-backport 在同一 heavy guard 完成 2580 帧路线。证据目录为
  `artifacts/butano-action-tail-runtime-20260724-1907/`，含 44 张截图、audit、
  success marker 和 final state；守卫摘要
  `build/resource-guard/butano-action-tail-runtime-20260724-1907.json` 为
  `completion_trigger=success-marker`、峰值 tree RSS 89.15625 MiB。44 张截图与上一
  scenario 数据里程碑逐文件完全一致，final state SHA-256 为
  `6b642428686e8e813b45f180ab5bc2ebdddbc4b76411c1b018e82281be60681a`。
  本轮自动验收静音运行，只签发流程与图形回归，不签发声音听感。

当时边界：`defense_ability` 只在单位完成时存入账本，尚未消费；这一缺口已由下一节的
防御准备与来袭反应运行时部分取代。补充查克拉、休息、地图 tile/对象、章节脚本和更多
可见关卡仍未因两阶段尾部通过而完成。

# 防御准备与来袭反应运行时（2026-07-24）

上一里程碑只把防御选择写进 `defense_ability`，没有证明资源提交、反应令牌和后续来袭使用
的是同一个领域事务。本轮以 `battle_defense_preparation` 补齐这个断点：

- 预览只读会话，并按 effect code 与动作来源共同验证类别；`0x10` 只允许主动术，
  `0x19` 只允许本场忍具。火遁、影分身、伪造来源和未闭合反应类别均明确拒绝；
- 提交在会话副本上复用动作资格和成本策略，原子完成查克拉/HP/忍具槽扣除、状态槽容量
  检查、一次性令牌建立和行动账本写入。成本不足、忍具 ID 与槽位不匹配、状态槽满或
  condition 解释失败都不会污染真实会话；
- 写轮眼：跳过 miss，在首个有效 hit 消费 `0x10`，该 hit 零伤害并截断剩余 hit；
  未命中时令牌保留，消费后的第二次攻击恢复正常伤害；
- 火弹：只在相邻有效命中消费 `0x19`，以防御者为 source、原攻击者为 target 走共享
  damage resolver；非相邻攻击正常伤害防御者且令牌保留；
- `reaction_resolution_event` 保存来源种类、规范化动作 ID、忍具槽、双方 UnitId、
  incoming hit、实际反击伤害和击倒结果。表现层不参与扣血，也不再靠高位动作 ID 猜
  主动术与忍具身份。

# 敌方第二指令与替身反应纠错（2026-07-25）

此前文档所称“玩家与 AI 共用尾部”只覆盖了状态机形状：AI 实际在 `select_facing` 后固定
提交 `no_ability`，没有执行原作敌方规划器的第二条指令。这正是“菜单/截图能走，但规则
没有闭环”的架构缺口。

静态控制流重新确认：

- `0x7000` 调用 `0x080851F8`，把规划工作区 `0x0202D228+0x10` 的 20 字节主候选复制到
  `0x02026A40` 并进入 `0x8000`；
- 玩家单位随后进入 `0x9000→0x9100`；敌方跳过这套玩家 UI，直接进入 `0xC000`；
- `0xC000` 把 `0x0202D228+0x24` 的第二个 20 字节候选复制到同一行动上下文，
  `0xD000` 再执行 secondary MOVEDONE；
- planner 在 `0x0808530C` 与 `0x080855A8` 分别用严格比较更新主/第二候选。

Butano 现增加 `battle_ai_secondary_command_planner`：主行动和 condition 未抢占战斗时，
先确认面向，再从同一个 `battle_defense_browser` 的可确认条目中按来袭威胁、反应效果和
资源成本选择第二指令，最后仍由 `battle_turn_flow::complete_defense` 原子提交。角色 35
具有 action 3 且资源足够时会实际扣除查克拉、把 action 3 写入行动账本并建立反应，而不是
把 UI 文本或演出截图当作结果。

替身的证据链使用 `notes/battle-effect-resolution-bindings-20260723.json` 与
`notes/battle-reaction-matrix-bindings-20260723.json`：11 个自然样本均在反应入口出现
`unit+0x154=0x16`，解析后 HP 不变、坐标改变、状态清零；11 个落点的曼哈顿距离均为 1–2。
实现因此把 action 3 的动作效果 `0x04` 映射为防御反应状态 `0x16`，首个有效 hit 消费并
截断整次多段攻击。战场拓扑从加载后的 `grid_map` 固化为 32×32 位图，候选必须在边界内、
可通行且未被活动单位占据；无合法格时反应不消费，避免半提交。

当前未闭合边界：12 个候选的精确 RNG 权重、战场对象是否排除落点、以及多个反应共存时的
完整 ROM 优先级。现有候选顺序只作为满足已观测约束的中性策略，不记为 ROM 精确公式。

本轮验收把领域测试、ARM 与运行时证据连接起来：

- 76 个宿主 C++ 测试程序以 `-Wall -Wextra -Werror` 编译并运行通过；替身测试覆盖预览
  零写、3 点查克拉成本、`0x16` 建立/一次消费、miss 保留、多段截断和只剩一个合法落点时
  的真实坐标变化。摘要为
  `build/resource-guard/butano-ai-secondary-host-final-20260725-05.json`；
- 定向 Python 76 项通过、2 项按既有条件跳过。全量 1061 项仍有三个历史图片/状态产物缺失
  error 和一个无关语义 fail，原始日志为
  `build/butano-ai-secondary-python-20260725-02/unittest.log`；
- devkitARM 构建通过，ROM 为 9,477,892 字节，ROM/ELF SHA-256 为
  `6ce6ccb48e8a0b00c1faf0fdc8344d98591788fe5e56746d5f94c9437a9bf4d2` /
  `02882a19879ec49db30e8e69892c38a4586d2a39d4a07bcb812cbe6f17d7a242`；
- 静音 mGBA battle 32 在真实 ARM ROM 中记录 AI 第二指令
  `planned=1, kind=1, action_id=3, score=31` 后正常进入第 2 回合，证据目录
  `artifacts/butano-ai-secondary-b32-20260725-05/`；battle 9 完整角色动作路线和
  scenario 41 组合拳/结算入口分别由
  `artifacts/butano-ai-secondary-b09-20260725-02/` 与
  `artifacts/butano-ai-secondary-s41-20260725-04/` 回归通过。

# 单一战斗规则源纠错（2026-07-25）

复核生产 include 后发现，真实 `battle_action_resolver` 之外仍保留两条早期原型路径：

- `ability_resolver` 接受手写 `ability_definition<MaxEffects>`，直接按 effect node
  加减 HP、坐标和状态；
- `apply_effect_chain` 操作另一份 `unit_state`，替身只用 `bool substitution_ready`
  跳过伤害。

主运行时虽然已经不使用它们，但旧 AI 重载、scenario include、宿主基础测试与 GBA 自检
仍让这套 API 可编译、可通过，后续关卡很容易误用并再次形成“演示规则”。本轮因此不再做
兼容适配：

- 删除两个旧规则头、旧 AI 重载、`BattleUnitInstance::substitution_ready` 和共享 resolver
  中的布尔降级分支；
- 将 `deterministic_rng` 拆到无领域行为的 `battle_random.h`；
- 旧 ability、production primitives、benchmark 和 ROM 自检全部改为直接构造
  `ActionDefinition`，在 `BattleSession` 上调用同一个 `battle_action_resolver`；
- `tests/test_butano_single_battle_domain.py` 扫描生产 include/src，禁止
  `ability_resolver`、`ability_definition<`、`apply_effect_chain` 与
  `substitution_ready` 回流，并要求 RNG 只有一个定义。

这项迁移不增加新技能公式；它移除的是绕过已绑定公式、状态库、成本、地图与事务边界的第二
规则源。后续关卡若需要新效果，只能先补 ROM 证据、生成内容与正式 handler，不能新建局部
effect chain。

ARM 集成暴露了两个宿主测试看不到的问题，均保留原始反证：

1. 首次构建命令只有 `set -o pipefail`，编译因 benchmark 的同名 `action_result` 冲突失败，
   但后续 `touch SUCCESS` 覆盖了 shell 返回值。摘要
   `build/resource-guard/butano-single-domain-arm-build-20260725-17.json` 的 exit 0
   因而不是构建成功证据；实际错误保存在同 run 的 build log。后续构建统一使用
   `set -euo pipefail`，marker 只会在编译成功后创建。
2. 把完整 `resolve_draft` 事务放进 ROM 启动自检后，battle 32 在 AI 入口
   `scene_frame=270` 停留超过 11 万 emulator frame。反证目录
   `artifacts/butano-single-domain-b32-20260725-06/` 与守卫摘要
   `build/resource-guard/butano-single-domain-b32-mgba-20260725-20.json` 保留
   12,922 条遥测样本。原因是嵌入式自检在 GBA 启动栈执行了带 session 副本的大事务；
   宿主 benchmark 可承受，但不适合作为 ROM 启动 smoke。

新增红测要求嵌入式自检只能调用正式 resolver 的 `preview_units` 只读入口，禁止
`resolve_draft`；宿主 benchmark 仍保留真实提交与失败零写。修正后的 ROM 在同一 battle 32
路线恢复到 frame 1194 完成，AI action 3 的四个连续遥测样本仍为
`planned=1/kind=1/action=3/score=31`。最终验证证据：

- ARM 摘要 `build/resource-guard/butano-single-domain-arm-build-20260725-21.json`，
  exit 0、无代码 warning；ROM/ELF SHA-256 为
  `baa27f0bba2dbc013fd7d10d41add26229359239133f1db1065e7019428d6bf2` /
  `bf3e134caabca0ae7bb44c82cbbc5ece091e1d4a7039bd021cdd8d6749bfa350`；
- mGBA battle 32、battle 9、scenario 41 证据分别在
  `artifacts/butano-single-domain-b32-20260725-07/`、
  `artifacts/butano-single-domain-b09-20260725-03/`、
  `artifacts/butano-single-domain-s41-20260725-05/`。
- 76 个宿主 C++ 测试程序、5 个 benchmark 与 77 项定向 Python（1 skip）通过；
  全量 Python 共运行 1063 项，仍只有既有的 1 fail、3 error、18 skip：三个 error
  都是历史截图/快照产物缺失，fail 是未纳入本轮的
  `distance_and_line_flags` / `distance_and_line_shape` 语义不一致。完整日志在
  `build/butano-single-domain-python-full-20260725-12/unittest.log`，本轮未引入新失败。

# 来袭反应唯一仲裁与失败 RNG 原子性（2026-07-25）

原版 `0x080763E0` 已静态绑定的 reaction lookup 顺序是
`0x04 → 0x0A → 0x09 → 0x10 → 0x16 → 0x19`。此前 Butano 只按
`0x10 → 0x16 → 0x19` 逐分支查找：目标若同时持有未实现的高优先 `0x04` 与写轮眼，
会错误忽略前者；替身存在但找不到落点时，还会继续降级触发低优先火弹。公开
`resolve_draft` / `resolve_area_draft` 虽复制 session，失败时却仍推进调用者 RNG。

本轮先用领域红测复现这些差异，再增加唯一只读 `_select_incoming_reaction`：

- 按六项 ROM 顺序只返回第一个状态槽，同一 hit 只执行一个反应；
- `0x10/0x16/0x19` 继续复用既有写轮眼、替身、火弹 handler；
- 尚未闭合效果的 `0x04/0x0A/0x09` 返回 `unsupported_effect`，完整 session/RNG
  零提交，不允许静默绕到后续已实现反应；
- `0x16` 无合法落点时保留令牌并走普通来袭，不再 fallthrough 到 `0x19`；
- 单体与面积公开 resolve 都在 RNG 副本上计算，只有成功时与 session 一起提交。

结构测试固定完整顺序及唯一 selector。该实现闭合的是静态可证的仲裁规则，不声称已经知道
`0x04/0x0A/0x09` 的效果、替身 12 候选精确 RNG 权重或战场对象是否排除落点；原版自然
多令牌共存样本也仍缺失。

RED 先在 `test_battle_substitution_reaction` 因 `0x04` 被跳过而失败；面积动作的第二个
RED 又证明失败后调用者 RNG 确实已前进。GREEN 后的验证为：

- 76 个宿主 C++ 程序和 5 个 benchmark 全部通过，日志分别在
  `build/butano-reaction-priority-host-20260725-03/game.log` 与
  `benchmark.log`，守卫 exit 0、`degraded=false`；
- 构建、研究文档和三条运行脚本共 78 项定向 Python 通过，1 项按集成开关跳过；
- devkitARM 摘要
  `build/resource-guard/butano-reaction-priority-arm-build-20260725-04.json`
  为 exit 0、无代码 warning。ROM 为 9,478,140 字节，ROM/ELF SHA-256 为
  `cb9a6e157ec31ebe581dbd878d20a955a5adbe9a5ec3559f7cd473d2b384593c` /
  `43ab745a296450e3614065059ecae46576b9e1667bfda091f70ebaf0aac858be`，
  本次 ELF 解析出的遥测地址仍为 `0x020151C8`；
- battle 32 在 frame 1194 进入第 2 回合，并在第 1 回合留下四个
  `kind=1/action=3/score=31` 的 AI 第二指令样本；battle 9 在 frame 3003 以 9 个
  活动单位完成三名角色动作路线并进入第 2 回合；scenario 41 在 frame 439 以
  action 5、零控制错误进入第 2 回合。证据目录分别为
  `artifacts/butano-reaction-priority-b32-20260725-06/`、
  `artifacts/butano-reaction-priority-b09-20260725-07/` 和
  `artifacts/butano-reaction-priority-s41-20260725-08/`。

为追查战场对象排除，曾对原版
`scenario-50-battle-15-round3-frontline-assembled.ss9` 的 slot 5 坐标
`0x02024AA8` 设置写监视点。两次受守卫 run
`battle-substitution-position-watch-20260725-01/02` 都因该 checkpoint 停在玩家
`0x1220` 尾部、零输入无法进入下一次攻击而超时，没有产生坐标写命中；这两次是无效反证，
不能用于判断对象是否阻挡落点。后续必须从可自动进入 `0x8000` 的攻击前 checkpoint 或
带单输入的可复现路线继续，不能把“未命中 watchpoint”解释成对象不参与。

红绿证据包括：缺少防御事务头文件的编译红灯、缺少 reaction 子事件的编译红灯、伪造
忍具写轮眼被错误放行的断言红灯；聚焦绿测覆盖零写预览、原子失败、状态容量、写轮眼多段/
miss/一次消费、火弹相邻反击/击倒、非相邻保留和忍具槽身份。

验证结果：

- 43 个宿主 C++ 测试程序经系统 Clang 编译、ad-hoc 签名并全部执行通过；资源守卫摘要
  `build/resource-guard/butano-defense-runtime-host-20260724-13.json`，exit 0、
  `degraded=false`、峰值 tree RSS 73.28515625 MiB；
- setup、condition/scenario 生成、Butano wiring、研究文档、音频与 mGBA 脚本共
  75 项定向 Python 回归通过，1 项按既有集成开关跳过。最初两次音频测试因测试内部硬编码
  `"python3"` 命中本机 Homebrew Python 并进入不可中断 `U` 状态；测试改为继承
  `sys.executable` 后由 `/usr/bin/python3` 在 0.321 秒内完成，未把环境卡死记为产品失败；
- Docker/devkitARM 构建摘要
  `build/resource-guard/butano-defense-runtime-arm-build-20260724-14.json` 为 exit 0、
  `degraded=false`、峰值 tree RSS 19.76953125 MiB。ROM 为 5,326,300 字节，
  SHA-256 `dc9ecc36c033904502a78e73b5143e4b1eba752f2246923e74260ca83593d992`；
  ELF SHA-256 `7ba8e2297532b769bf0d31568f92662e69c8ae171b6be48798d950111acb39a9`；
- 签名 mGBA 0.10.5 script-backport 在同一 heavy guard 完成 2580 帧场景 41 无防御路线。
  证据目录 `artifacts/butano-defense-runtime-20260724-1932/` 含 44 张截图、audit、
  success marker 与 final state；守卫摘要
  `build/resource-guard/butano-defense-runtime-mgba-20260724-1932.json`，
  `completion_trigger=success-marker`、峰值 tree RSS 89.20703125 MiB。44 张截图与上一
  action-tail 里程碑逐文件完全一致，final state SHA-256
  `434ecb24fecb2fe66d6752fe58d25c5725c580b5952c32afbc486fe5ecbbc82b`。
  自动路线静音，只签发流程与图形回归，不签发音频听感。

# 通用玩家行动 Flow 与 scenario 适配（2026-07-24）

共享动作目录与 resolver 已存在后，`scenario_41_battle` 仍直接编排玩家伤害提交、condition、
朝向和防御；这会让后续关卡复制同一组 modal switch。新增
`battle_player_action_flow` 后，应用层只保存阶段、列表游标、目标 preview 和最近结果，
领域数据继续只有 `BattleSession` 一份。

TDD 先以 scenario 43 固定单位池建立完整玩家流程：

- 鸣人的完整目录仍有 3 项 action 2、5、7；测试 action access policy 后，教学列表只有 action 7，
  证明关卡限制是只读投影而不是篡改角色技能；
- 敌人占用格 preview 返回拒绝，flow 保持 target selection，session 零写；取消可逐层回到
  action selection 和 command selection；
- 合法空地确认在 session 副本中同时执行影分身 resolver 和 condition 尾部，成功后才提交，
  随后进入 facing、defense decision，并在明确无防御后完成单位、切到敌方；
- 佐助等级 14 的防御流程验证进攻术确认被拒绝且 session 不变、B 返回防御决定、再次进入后
  选择 action 15 才扣成本并建立写轮眼状态。

scenario 41 的玩家侧 resolver 直连随后被移除。选择教学组合拳时 flow 从完整角色目录按
显式 action 5 policy 产生单项列表；目标 preview、最终确认、结束行动、朝向、防御浏览与
单位完成都委托同一 flow。scenario snapshot 只复制所选 action/defense 身份和错误供
presenter 读取，不能写 HP 或胜负。

当前边界：scenario 41 的敌方仍在 adapter 内组合 AI planner、共享 resolver 和回合尾；
补充查克拉、休息的精确公式尚未闭合，未伪造常量接入；scenario 43 也仍没有地图/动态 sprite/
剧情的可见适配。因此该里程碑证明玩家应用流程可复用，不等于全部关卡已可玩。

验证证据：

- 47 个宿主 C++ 测试通过，守卫摘要
  `build/resource-guard/butano-player-flow-host-final-20260724-49.json`，峰值 tree RSS
  75.4375 MiB；
- 78 项定向 Python 测试通过、1 项跳过，守卫摘要
  `build/resource-guard/butano-player-flow-python-final-20260724-44.json`；
- 首次 devkitARM 构建因结果成员命名触发 `-Wchanges-meaning` 而失败，保留红测证据
  `build/resource-guard/butano-player-flow-arm-build-20260724-45.json`；重命名后由
  `build/resource-guard/butano-player-flow-arm-build-final-20260724-47.json` 签发
  无 warning/error 构建。ROM 大小 5,340,816 bytes，ROM SHA-256
  `73399f83f7271f6fa5cf5523c65a4ed2e2769d6ff40a62a64d0ac20eb594dbde`，ELF SHA-256
  `2accf6860892f779d1291827de197dcf663318b95528a1718f0846c65107492d`；
- mGBA 0.10.5 script-backport 在 heavy guard 下完成 scenario 41 的 2580 帧路线，
  证据目录 `artifacts/butano-player-flow-runtime-20260724-2023/`，守卫摘要
  `build/resource-guard/butano-player-flow-mgba-20260724-48.json`，峰值 tree RSS
  89.1171875 MiB。44 张截图与前一动作目录里程碑逐文件一致，final state SHA-256
  `241f25526c3c8d2e6ff91011dc505c6a700ea7e557c864d934abc1c3da98ac72`。
  自动路线静音，只验证流程、图形和状态，不能签发音频听感。

# 通用动作目录、固定单位池与影分身执行（2026-07-24）

防御浏览器完成后，进攻菜单与防御菜单仍可能各自复制一遍“等级 → 技能/忍具”映射，而且
场景加载器会丢弃未部署记录，使召唤 resolver 没有原 ROM 固定单位池中的空闲槽。该问题
不能靠显示一个“影分身”选项解决。本轮以三个先失败的测试固定共享运行边界：

- `battle_action_catalog` 是角色动作内容的唯一只读投影。等级 1 的鸣人得到 action
  2、5、7，装备 tool 1 时追加并保存实际槽位；无效角色或忍具引用使整个目录失败；
- `battle_action_browser` 在目录之上执行动作资格、查克拉/HP 和本场忍具成本校验；
  `battle_defense_browser` 改为消费同一目录，再追加防御类别 preview，不再各自扫描
  15+4 个槽；
- loader 的显式固定池策略按编队记录保留 UnitId 1–12。scenario 43 variant 0 有鸣人和
  三名敌人四个有效记录，后续八个空记录成为 inactive reserve；默认策略仍只装载有效单位，
  容量小于 12 时固定池装载在临时 session 原子失败；
- `battle_action_execution` 根据 target policy、effect handler、目标格和空闲 reserve
  统一调用共享 preview/resolve。scenario 43 的 action 7 在 `(4,16)` 预览时 session
  字节级相等；提交后查克拉 5→2，槽 5 原子变为角色 1 的可追踪影分身，保存 summoner、
  位置和本回合已完成账本。占用格与没有 reserve 的对照均返回明确错误且零写。

scenario 41 的教学组合拳也不再从固定动作数组取第一个元素，而是从当前鸣人实例的共享目录
按显式教学 action 5 规则查找；关卡限制仍留在 scenario definition，角色学习和成本规则
不复制进 facade。

这一闭环证明“角色内容 → 动作目录 → 目标/召唤预览 → 原子效果提交”可以跨 scenario
运行，但 scenario 43 目前只有宿主领域集成测试，不是可见关卡验收。地图 tile、动态单位
sprite、剧情入口、玩家全命令控制器和敌方完整演出尚未接到 scenario 43，不能把一次影分身
领域测试冒充关卡已经可玩。

验证结果：

- 46 个宿主 C++ 测试程序以 `-Wall -Wextra -Werror` 编译、ad-hoc 签名并全部执行通过；
  资源守卫摘要
  `build/resource-guard/butano-action-catalog-host-final-20260724-35.json`，exit 0、
  `degraded=false`、峰值 tree RSS 65.296875 MiB；
- setup、condition/scenario 生成、Butano wiring、研究文档、音频与 mGBA 脚本共
  77 项定向 Python 回归通过，1 项按既有集成开关跳过；守卫摘要
  `build/resource-guard/butano-action-catalog-python-20260724-33.json`；
- Docker/devkitARM 最终构建摘要
  `build/resource-guard/butano-action-catalog-arm-build-final-20260724-36.json` 为 exit 0、
  `degraded=false`、峰值 tree RSS 63.6015625 MiB，编译日志无 warning/error。ROM 为
  5,335,560 字节，SHA-256
  `3d0ccc916c147ca69077b3c5365e4e3a2e249765423a3bce5cce1ba5a030c209`；
  ELF SHA-256 `9a9b138bb1c8a7b9e9ab1b75c118f4fc1ed761de0aebbbae5d086ce0dbeb7bd8`；
- 签名 mGBA 0.10.5 script-backport 完成 2580 帧 scenario 41 回归。证据目录
  `artifacts/butano-action-catalog-runtime-20260724-2007/` 含 44 张截图、audit、
  success marker 与 final state；守卫摘要
  `build/resource-guard/butano-action-catalog-mgba-20260724-37.json`，
  `completion_trigger=success-marker`、峰值 tree RSS 69.65234375 MiB。44 张截图与上一
  防御浏览器里程碑逐文件一致；final state SHA-256
  `411ac73a60f161b71f573e88be3bc6e5c10438e0c76c72349579946171c85bfd`。
  自动路线静音，只签发流程与图形回归，不签发音频听感。

当前边界：`0x04/0x09/0x0A/0x16/0x22` 等其余 reaction family 仍保持 unsupported；
scenario 41 当前可见菜单没有暴露写轮眼/火弹选择，因此其 mGBA 黄金路线只能证明既有
无防御分支没有回归，不能冒充这两个防御动作的可见验收。

# 数据驱动防御动作浏览器与可见接线（2026-07-24）

此前 scenario 41 的防御确认页只有固定的 `DEFENSE PREP / A:CONFIRM`，按 A 总是提交
`no_ability`。这仍是 facade 伪造流程，无法证明角色技能、等级、忍具和防御事务真正接通。
本轮先以失败测试固定以下领域边界，再做最小实现：

- `UnitInstance` 保存由剧情/部署提供的等级；场景策略没有证据时以 1 为明确基线，不从
  positions 未知字节猜等级；
- `battle_defense_browser` 从角色定义的 15 个主动动作槽按实例等级筛选已学技能，再追加
  4 个本场忍具槽。列表中的每一项都执行零写 `preview`，因此进攻术和普通忍具可以浏览，
  但不会绕过类别、成本、槽位或状态容量校验；
- 领域测试以等级 14 的角色 2 验证 10 个可见条目：八个已学主动术加两个装备忍具；
  action 15 写轮眼和 tool 46 火弹可确认，进攻 action 2 与普通 tool 1 明确不可确认；
- scenario 41 的鸣人等级 1 列表来自同一服务，显示 action 2、5、7。确认这些进攻术会
  保持菜单和领域状态不变，B 返回确认页；默认“不使用”保留原黄金路线，不要求黑屏中再按 A。

这次接线并不等于全部显示层已经组件化。活动战场、单位、游标、HP 和动作/防御菜单由领域
snapshot 与事件生成；入口、教程、胜利、结果、升级和战后仍有全帧或预制三层 BG 资源。
这些 BG 现阶段只承担参考画面和过场表现，不再拥有 HP、命中、成本或胜负的写权限；后续
仍要逐场替换为数据驱动的演出队列。scenario 41 也仍是首个两单位可见 facade，不能用它
冒充 47 场地图、完整部署、全部防御 family 或完整战斗系统已经功能等价。

TDD 红灯包括：缺少实例等级与浏览器头文件导致编译失败，以及 scenario 41 缺少浏览阶段、
事件和 snapshot 字段导致黄金路线测试无法编译。最小实现后，领域测试、场景输入测试、
presenter 文案测试和 source-wiring 测试均转绿。

验证结果：

- 44 个宿主 C++ 测试程序以 `-Wall -Wextra -Werror` 编译、ad-hoc 签名并全部执行通过；
  资源守卫摘要为
  `build/resource-guard/butano-defense-browser-host-20260724-22.json`，exit 0、
  `degraded=false`、峰值 tree RSS 70.46875 MiB；
- setup、condition/scenario 生成、Butano wiring、研究文档、音频与 mGBA 脚本共
  76 项定向 Python 回归通过，1 项按既有集成开关跳过；守卫摘要
  `build/resource-guard/butano-defense-browser-python-20260724-23.json`；
- Docker/devkitARM 构建摘要
  `build/resource-guard/butano-defense-browser-arm-build-20260724-24.json` 为 exit 0、
  `degraded=false`、峰值 tree RSS 19.80859375 MiB。ROM 为 5,334,468 字节，
  SHA-256 `bd3d0437e6119ed1695241e53343b76bbf4f5f57f6bd46444a7ad82c3d89c782`；
  ELF SHA-256 `8c84eb37621b869bf457d2419b8e8d88b30e3ddfeb232b9d4003ffa4d49abe8b`；
- 签名 mGBA 0.10.5 script-backport 在同一 heavy guard 完成 2580 帧路线。证据目录
  `artifacts/butano-defense-browser-runtime-20260724-1949/` 含 44 张截图、audit、
  success marker 与 final state；守卫摘要
  `build/resource-guard/butano-defense-browser-mgba-20260724-25.json`，
  `completion_trigger=success-marker`、峰值 tree RSS 89.1015625 MiB。与上一里程碑相比
  只有 `defense-confirmation.png` 发生预期变化，其余 43 张逐文件相同；final state
  SHA-256 为 `e163e4f280aea91708e283df98e95bd2ca454a93998e0c148b381581c7aa4ac0`。
  自动路线静音，只签发流程与图形回归，不签发音频听感。

# 通用 AI 单位回合 Flow（2026-07-24）

上一里程碑虽然让玩家和 AI 共用 resolver，但 `scenario_41_battle` 仍自己选择敌方单位、
物化角色动作数组、调用 planner、区分单体/范围 resolver，并分别提交 condition、朝向与
回合尾。这会让每个后续关卡复制一套敌方控制器。

本轮先以失败测试固定两个缺口：

- 同一个 action ID 可以同时出现在主动技能和忍具目录，旧 `AiCandidate` 只保存 ID，无法
  唯一回查。现在候选同时保存主动技能/忍具来源与 tool slot；同 ID 的高伤害忍具被选中时，
  能准确记录并消耗忍具槽 2，不会误执行主动技能；
- 新 `battle_ai_turn_flow` 缺失时，跨关卡测试无法编译；scenario source-wiring 测试也明确
  捕获 facade 仍直接调用 planner、两个 resolver 和两个 turn-flow 入口。

绿灯实现把一个 AI 单位的完整行动放入 `BattleSession` 与 RNG 副本：验证当前阵营和 control，
选择单位，从角色等级、15 个主动技能槽和 4 个忍具槽生成浏览目录，只向 planner 提交合法
动作，然后在副本中执行移动、目标效果、condition、朝向和无防御回合尾。任一步失败都保持
session 和下一次 RNG 输出不变；效果后目标成立则停在 `EffectsResolved` 并立即返回 outcome。

scenario 43 的 variant 0 继续使用四个部署单位与八个 inactive reserve。玩家结束行动后，
unit 2 通过同一 AI flow 从真实角色目录规划并完成行动，12 个稳定槽保持不变。scenario 41
随后删除了敌方动作物化和所有直接 resolver/turn-flow 调用，只提供目标并把 flow 结果映射为
既有教程、玩家回合或胜负演出事件。

验证结果：

- 48 个宿主 C++ 测试程序以 `-Wall -Wextra -Werror` 编译、签名并全部执行通过；守卫摘要
  `build/resource-guard/butano-ai-turn-flow-host-20260724-50.json`，exit 0、
  `degraded=false`、峰值 tree RSS 73.61328125 MiB；
- 80 项定向 Python 回归通过，1 项按既有集成开关跳过；最终守卫摘要
  `build/resource-guard/butano-ai-turn-flow-python-final-20260724-56.json`；
- devkitARM 最终构建摘要
  `build/resource-guard/butano-ai-turn-flow-arm-build-final-20260724-53.json` 为 exit 0、
  `degraded=false`、峰值 tree RSS 18.76953125 MiB，编译日志无 warning/error。ROM 大小
  5,343,404 字节，SHA-256
  `40d848752d13dbc3c78ead6e571a2af94f6f2a84446e788e457f36b1c7aa1b1f`；ELF SHA-256
  `3d39f31892e88e932d1b0b8719264bfca6f1480511783b8eb1017c85d52530ed`；
- mGBA 0.10.5 script-backport 在 heavy guard 下完成 scenario 41 的 2580 帧路线，证据目录
  `artifacts/butano-ai-turn-flow-runtime-20260724-2043/`，守卫摘要
  `build/resource-guard/butano-ai-turn-flow-mgba-20260724-54.json`，
  `completion_trigger=success-marker`、峰值 tree RSS 89.0625 MiB。44 张截图与上一玩家 flow
  里程碑逐文件一致，final state SHA-256
  `684b5f67578a5b0de40a181f94a18079408becf24e91fb9cb682b630415f171b`。
  自动路线静音，只验证流程、图形和状态，不能签发音频听感。

当前边界：AI 防御动作选择、补充查克拉/休息命令、真实地图 tile/collision、章节脚本、
剧情打断和跨关卡结果表现仍未进入通用控制器；scenario 43 也仍不是可见可玩关卡。

# 通用玩家基础指令与资源事务（2026-07-24）

上一里程碑只统一了 action→target→facing→defense；移动仍由 scenario 41 直接调用
`BattleSession::preview_move`，补充查克拉和休息也没有进入玩家 flow。场景因此仍可能
绕过领域层，以菜单索引和直接状态写入重新制造“选项拼接”的假流程。

本轮先用原 ROM 静态范围与两个角色 checkpoint 闭合基础资源规则，并生成
`notes/battle-resource-command-rule-bindings-20260724.json`：每补充 1 点查克拉消耗
角色 `hand_seals` 点 HP，HP 至少保留 1；休息恢复 `floor(max_hp / 5)`。两者都遵循
预览无写入、确认原子提交，休息和补充查克拉随后进入单位完成与 condition 求值链。

实现新增 `battle_command_browser` 和 `battle_resource_commands`，并扩展既有
`battle_player_action_flow`，没有另建平行场景状态机：

- 固定命令目录按 move、ability、replenish、rest、end 的顺序查询，但每项的
  available/disabled/hidden/reason 由当前单位、账本、资源、草案和关卡只读 policy 动态产生；
- 移动选择调用通用 pathfinder，预览只写 `ActionDraft`，确认后回到动态命令目录；取消移动
  或取消整个单位行动会回滚草案，单位实例坐标不被 scenario 提前修改；
- 查克拉数量选择和休息确认共用资源事务。非法数量、HP 不足、资源已满或 session 阶段错误
  都保持会话逐字节不变；
- scenario 41 只把按键、命令 policy 和只读 snapshot 接到玩家 flow。源码门禁禁止它直接
  调用 `_session.preview_move`、`_session.cancel_action` 或自行写 HP/查克拉。

scenario 41 是教程关，移动后只开放 ability/end；补充查克拉与休息不会为了演示而被硬塞进
该场可见菜单。相同 command flow 已在宿主跨场景 fixture 中完成休息与多点查克拉交换，
后续关卡可直接提供 policy 与地图，不需要复制资源公式。

TDD 与验证：

- 红灯先后证明资源规则分析器、`battle_resource_commands`、`battle_command_browser`、
  command flow 方法和场景 wiring 均不存在；最后又用“UI 索引与领域命令故意不一致”的
  presenter 测试证明旧高亮仍依赖 UI 索引，并验证 ability/end 不能绕过当前选中命令直接
  执行。只读审查再暴露场景 `reachable()` 前置门、移动后空 policy 的半更新、资源 condition
  未验收和证据输入追溯不足；四项均先补失败测试再修复，复审结论无 Critical/Important；
- 50 个宿主 C++ 测试程序以 `-Wall -Wextra -Werror` 编译并全部执行通过；资源守卫摘要
  `build/resource-guard/butano-player-command-host-reviewed-20260724-69.json` 为 exit 0、
  `degraded=false`、峰值 tree RSS 63.95703125 MiB；
- 资源规则、Butano wiring、研究文档、scenario 41 运行脚本/音频和两组生成器共 79 项
  定向 Python 回归通过；守卫摘要
  `build/resource-guard/butano-player-command-python-reviewed-20260724-70.json` 为 exit 0、
  `degraded=false`。全量 discovery 共运行 966 项，因当前系统 `/usr/bin/python3` 3.9 与
  若干历史测试所需 API 不匹配、三个已清理的历史捕获目录缺失，以及一项既有技能字段语义
  断言不一致，结果为 1 failure、11 errors、18 skips；诊断见
  `build/test-results/butano-player-command-python-discovery-20260724-64.log`，本轮没有把它
  误报为通过，也没有为通过本功能而改写这些无关归档测试；
- devkitARM 构建摘要
  `build/resource-guard/butano-player-command-arm-build-reviewed-20260724-71.json` 为 exit 0、
  `degraded=false`、峰值 tree RSS 20.078125 MiB，构建日志无 warning/error。ROM 为
  5,346,324 字节，SHA-256
  `e40b0dab010af7ba777dfcb693e920cab4b0f841a2f6c60196ec5208ae31dbb2`；
  ELF SHA-256 `00980bedac9110038f586d4cad0e0ea3b82603fe39c212b2dc0b35c3628f167f`；
- mGBA 0.10.5 script-backport 在 heavy guard 下完成 scenario 41 的 2580 帧路线，证据目录
  `artifacts/butano-player-command-runtime-reviewed-20260724-2142/` 含 44 张截图、audit、
  success marker 和 final state；守卫摘要
  `build/resource-guard/butano-player-command-mgba-reviewed-20260724-72.json`，
  `completion_trigger=success-marker`、峰值 tree RSS 89.57421875 MiB。44 张图与上一
  AI-flow 里程碑逐文件一致，final state SHA-256 为
  `2d50331b0b39b6782701fe43e00150fe23ed500b38c6ed5fbc28b061733edac5`。

当前边界：这次闭合了玩家基础命令主链，不代表 47 场可见关卡已经接线。AI 选择资源命令、
真实地图 tile/collision、章节脚本、剧情打断、结果表现和 scenario 43 可见场景仍未完成；
自动 mGBA 路线为静音验证，不签发音频听感。

# ROM 地图内容、占用与组件背景运行时（2026-07-24）

旧 scenario 41 的活动背景虽然已把单位拆成 sprite，仍来自“含人物的运行截图 → 复制别处
草地覆盖人物/游标”的清图流程，移动层又额外手写六个障碍格。这两份数据既不是 ROM 地图
真值，也无法给 scenario 43 或后续 47 场复用。

本轮把地图链拆成三个只读/可变边界：

- `analyze_battle_map_collision.py` 用 ROM、函数和 opcode 哈希锁定 map table、碰撞消费者及
  occupancy 写入/清理；完整清单写入
  `notes/battle-map-collision-semantics-20260724.json`；
- `generate_butano_battle_map_content.py` 解压 47 个 collision stream，将 12151 个原始
  u16 word 平铺生成到 `generated_battle_map_content.h`。低四位保持原样，绝不把
  `1/3/7` 部分属性改写成 cost 0；
- `battle_map_loader` 原子物化地形，再从 `BattleSession` 的 active unit 集中生成占用层。
  地图定义不会因单位移动被修改；越界、完全封闭格和重复单位位置均拒绝且目标 map 不变。

本段记录的是 2026-07-24 的历史边界，已被 2026-07-26 的完整消费者数据流取代。旧分析
曾把 `1/2/4/8` 当成四方向 case，又因证据不足退回只拒绝 `0xF`；后续
`0x08069DB8 → 0x08069D1C → 0x080698B4` 已证明低四位是地形类别，`1/3/7` 分别消耗
被动 target `0x1A/0x1C/0x1B` 的逐路径预算。当前事实与运行时验收见
`notes/battle-terrain-passive-runtime-20260726.md`。

活动背景也不再从截图派生。`generate_butano_battle_runtime_assets.py` 直接解压原 ROM 的
tile graphics、palette、primary layout 和 metatile definitions，生成 288×352 active map
并透明填充到 512×512；因此旧清图误删的岩石与地面阴影重新可见。敌方 sprite 暂时仍从
参考帧提取，属于后续角色表现资产工作，不拥有领域写权限。

验证结果：

- 52 个宿主 C++ 测试全部通过，日志
  `build/test-results/butano-map-runtime-host-final-20260724-77.log`，守卫摘要
  `build/resource-guard/butano-map-runtime-host-final-20260724-77.json`；
- ARM 构建无 warning/error，ROM 5,370,740 字节，SHA-256
  `674fce2a9f51577c758ecb1720f6cdf5a7df92bcb83995f038e0df296b762709`；
  ELF SHA-256 `243f483a6cc97223a894fdad45d63bdfd78f1076b3c59c1a25bb84bd3c58fe5d`；
- mGBA 0.10.5 在 heavy guard 下完成 2,580 帧路线，生成 44 张关键截图、final state 和
  success marker。证据目录 `artifacts/butano-map-runtime-20260724-2216/`，守卫摘要
  `build/resource-guard/butano-map-runtime-mgba-20260724-79.json`，final state SHA-256
  `a4700e1b5bf92f6ec39b8e4ff69fcc2da85c29e6479b22b263a97a6cedd9a925`。

当前边界：scenario 43 已通过同一真实地图/占用加载器的宿主集成测试，但可见 renderer、
章节脚本、通用 BattleController 和动态召唤 sprite 尚未接入；自动路线静音，不签发音频听感。

# 共享 Encounter Runtime、场景控制器与 scenario 43 可见闭环（2026-07-24）

本轮纠正“每个场景各自拼装 session/菜单/AI”的剩余结构。`battle_encounter_runtime` 现在
统一拥有 `BattleSession`、不可变地形、玩家 flow、AI flow、condition 和 RNG；scenario 41
只保留教程/剧情 adapter。`battle_scene_controller` 把按键语义映射到运行时命令，并输出
固定容量 snapshot；`battle_scene_presentation` 消费控制器的一次性事件，把领域已提交的
移动、技能和目标转成插值、突进、命中震动/闪烁。表现层没有 HP、坐标、资源或召唤写入口。

scenario 43 的 SELECT 开发入口加载生成的 row 43 地图、1 名玩家、3 名敌人与 8 个 reserve。
可见路线完成 action 7 影分身：查克拉 `5→2`、槽 5 激活、`ACTIVE 4/12→5/12`；随后三名
敌人按 `AI DONE 0/3→1/3→2/3` 通过同一 planner/resolver/turn-flow，最终进入
`ROUND 2 PLAYER`。这证明 snapshot 不是预制截图索引：单位位置、资源、召唤和回合都来自
同一权威会话，renderer 只遍历活动槽。

ARM 调试先发现三个不同问题。大型 planner 工作数组落在同步调用栈时，SP 从
`0x03007F00` 降到 `0x030016EC` 并覆盖 IWRAM；把 reachable/unit projection/event queue
迁入 EWRAM workspace 后，SP 恢复到安全区。加入表现事件后又暴露 GCC 把 planner 完全内联
进 AI turn executor 的布局敏感错误：KEYINPUT 始终 `0x03FF`，但 PC/LR 从合法规划地址跳入
`0x03006xxx` 栈区并导致 ROM 复位。最终给 planner 建立非内联边界，符号尺寸从单一
`0x2CE4` executor 拆为 `0x2054` planner 与 `0x0AE8` executor；最终帧 SP 为
`0x030063C4`，没有再次复位。回归 scenario 41 时又发现 facade 仍是函数栈局部对象；
共享 runtime 增大后会停在战斗入口。源码失败测试固定 EWRAM wiring 后，facade 改为静态
EWRAM 对象并在每次进场原地重建，41 关随即恢复完整路线。

验证结果：

- 55 个宿主 C++ 程序以 `-Wall -Wextra -Werror` 编译并全部通过；
- Butano wiring、文档、内容生成和 scenario 43 脚本共 69 项定向 Python 回归通过，
  1 项按既有集成开关跳过；
- ARM 构建守卫
  `build/resource-guard/butano-shared-runtime-arm-build-s41-ewram-20260724-109.json`
  为 exit 0，日志无代码 warning/error；ROM SHA-256
  `8085dffcd7df4aeae0d6b07a31d27885f5f0f292ac4a67510596f95594e7aa5c`；section 审计为
  `.iwram` 8,840 字节、IWRAM `.bss` 2,168 字节、EWRAM `.sbss` 70,748 字节；
- mGBA 证据目录 `artifacts/butano-shared-runtime-scenario43-20260724-17/` 保存 formation、
  clone、敌方序列、第 2 回合截图、register samples、save-state 和 audit；守卫
  `build/resource-guard/butano-shared-runtime-scenario43-mgba-final-20260724-113.json`
  以 success marker 完成。scenario 41 证据
  `artifacts/butano-shared-runtime-scenario41-20260724-02/` 保存 44 张关键截图、final state
  和 2,580 帧 audit；守卫
  `build/resource-guard/butano-shared-runtime-scenario41-mgba-ewram-20260724-110.json`
  同样以 success marker 完成。

当时边界：scenario 43 的角色图仍为 side/slot 占位表现，章节脚本、部署 UI、失败/特殊结果
表现尚未接入；AI 资源命令与防御策略、`1/3/7` 地形语义也尚未闭合。后者现已由
`notes/battle-terrain-passive-runtime-20260726.md` 取代。自动 mGBA 路线静音，只签发
流程、图形和状态，不签发音频听感，更不代表 47 场全部完成。

# 通用可见场景与 row 9 3v5 压力样本（2026-07-25）

`scenario_43_scene.cpp` 已降为路由 wrapper；`battle_runtime_scene` 按 battle ID、地图尺寸、
condition variant、seed 和背景资源装载 row 43 与 row 9。renderer 只遍历
`battle_scene_controller` snapshot 并消费 `battle_scene_presentation_event`，没有
session、resolver、HP、坐标、查克拉或召唤写入口。row 9 使用原 ROM 生成的 16×32 地图，
实际装载 3 名玩家、5 名敌人和 12 个固定槽。

ARM 首次运行在确认移动后停住，PC 落入 `0x030016F0`。ELF 的 nm/objdump 证明该地址是
`__aeabi_memset4`，不是音频或 mGBA 故障。根因是 16×32 `find_path` 结果、距离/父节点/
访问数组、临时地图和 player/AI flow 同时压入 IWRAM 栈，覆盖返回地址。修复不是扩大栈，
而是新增 `pathfinder_workspace`：16×32 工作区固定为 8,704 字节，由
`battle_encounter_runtime` 与移动地图工作区一起常驻 EWRAM，玩家预览和 AI 规划复用
同一容量边界。最终 SP 在稳定帧为 `0x03006444`。

第二个 ARM 问题出现在第八个活动单位创建 sprite 时。GBA 只有 128 个 OAM entry，长 HUD
文本、12 个单位、单位标签和双 sprite 光标的最坏组合超限。`battle_runtime_scene_sprite_budget`
把 HUD 限为 78 个文本 sprite，并静态证明 12 单位场景适配 OAM；这不是隐藏单位或改用截图。

为避免固定帧脚本把“领域已推进、最后演出仍在播”误报为回合完成，场景在 EWRAM 导出
96 字节遥测，当前最终 ELF 符号为 `0x02012848`。字段包括 battle/phase/round、单位与完成
计数、光标、控制器错误、render stage、`presentation_busy`、选中角色/动作以及最后结算
动作。地址只用于本构建取证，
脚本必须通过 `arm-none-eabi-nm` 重新解析。row 9 在第 433 帧进入 round 2 但演出仍忙，
第 450 帧才空闲，第 453 帧签发完成；row 43 同理在第 1119 帧进入 round 2、第 1232 帧
演出空闲、第 1235 帧完成。

验证：

- 57 个宿主 C++ 程序以 `-Wall -Wextra -Werror -pedantic` 编译并执行通过，守卫摘要
  `build/resource-guard/butano-generic-scene-host-final-20260725-188.json`；
- ARM 构建守卫 `build/resource-guard/butano-generic-scene-presentation-busy-build-20260725-180.json`
  通过；section 审计为 `.iwram` 8,840、IWRAM `.bss` 2,172、EWRAM `.ewram` 224、
  `.sbss` 122,732 字节；
- row 9 状态驱动证据
  `artifacts/butano-generic-scene-battle09-state-final-20260725-03/`；
- row 43 状态驱动证据 `artifacts/butano-generic-scene-s43-final-20260725-05/`；
- scenario 41 2,580 帧金路径
  `artifacts/butano-generic-scene-scenario41-final-20260725-01/`。

当前边界：单位仍使用阵营/槽位占位 sprite；AI 主动资源/防御策略、部分碰撞属性、章节
部署/对白、特殊目标可见表现、胜负/结算通用 renderer 与其余关卡未完成。自动 mGBA 静音，
本证据不签发音频听感。

# 角色与技能可观察架构（2026-07-25）

本轮针对“场景里拼截图和选项不能算战斗系统”的问题，把角色/技能事实到实际效果的链路
接入现有领域层，而没有建立第二套 scene 私有规则：

- `generate_butano_battle_identity_content.py` 从哈希约束的身份 JSON 生成 63 个角色身份、
  87 个主动技能身份和中文 sprite font。55/78 条 exact 与 8/9 条 ambiguous 置信度原样
  保留；原 ROM 名称字节只作 provenance，不能被误当作全局 Unicode 编码。
- `battle_action_loadout → battle_action_catalog → battle_action_browser →
  battle_player_action_flow` 继续决定实际目录和资格；scene 不按角色 ID 重建菜单。
  player-flow snapshot 使用 10 字节动作视图，固定投影 19 项动作 ID、来源、成本、目标、
  效果和稳定错误码。角色等级、攻防敏捷移动则从真实 unit instance 投影到 scene snapshot。
- UI、遥测和测试都只消费 snapshot。Butano 画面已显示漩涡鸣人、宇智波佐助、春野樱以及
  各自等级 1 的完整技能列表；未验证忍具名仍明确显示 `TOOL #ID`。

首个 ARM 路线在鸣人目标确认后停滞。PC/SP 和宿主/ARM 对照证明不是 mGBA 或音频故障，
而是 30 字节动作定义扩大 player snapshot 后，controller 与 player flow 又按值嵌套复制，
导致 `_confirm_target` 约 2.7 KiB、下层 target confirm 约 10.6 KiB 栈帧共同触发
IWRAM 栈溢出。修复把动作投影压为 10 字节、snapshot 返回 const 引用，并只跨确认边界
保存 `ability_id`；player snapshot 从 696 降到 316 字节，12 槽 scene snapshot 从
1,416 降到 1,032 字节。没有增加 battle ID、角色 ID 或截图分支。

96 字节遥测保留旧前 72 字节偏移，并追加
`selected_character_id/action_count/action_index/selected_action_id/
selected_action_error/last_resolved_action_id`。最终 ELF 符号为 `0x02012848`，ROM SHA-256
为 `42e0f29ad4ab05a9205e2d890ea34dd5575fc5c25f2278cdcc8616f2e7a79f64`，ELF SHA-256
为 `ffeec790ac2b494942689f15c2fc91e6bb48ebc07b3fca9aa6410f5975ea03d0`。section 审计为
`.iwram` 8,840、IWRAM `.bss` 2,172、EWRAM `.ewram` 224、`.sbss` 123,332 字节。

受守卫 `artifacts/butano-character-actions-b09-20260725-03/` 在第 994 帧完成：

- 鸣人动作 2 从 `(11,15)` 瞬移到 `(11,14)` 并消耗 1 查克拉；
- 樱动作 1 激活角色 3 的 reserve 分身，活动单位从 8 增至 9；
- 佐助目录实际遍历 `[2,5,16]`；
- 五名敌人完成后返回 round 2，分身和九个活动单位仍存在。

既有 battle 09 多单位、scenario 43 分身和 scenario 41 的 2,580 帧黄金路线也各自通过
success marker 回归。自动 mGBA 全程静音，因此不签发音频；单位仍是通用占位 sprite，
63 名角色逐人美术、87 个技能逐项演出、AI 资源/防御策略、章节部署和其余关卡仍是 Goal
后续边界。

# 被动运行时与 IWRAM 事务边界（2026-07-25）

本轮没有增加 scene 私有选项或截图分支。`generate_butano_battle_passive_content.py` 把
ROM 表中的 45 条 12 字节被动成长记录生成到固定内容表；每个单位实例持有 24 个紧凑
`id/level` 槽。查询严格遵循 ROM 规则：ID 0、level 0、level `0xFF` 无效，同 target type
返回首个活动槽，数值为 `base + per_level * (level - 1)`。当前只有已有原 ROM 动态证据的
type `0x0C` 与 `0x19` 进入逐 hit resolver，分别产生会心 flag 2 和无视防御 flag 4；
其他类型不根据名称字节猜效果。

加入 48 字节被动状态后，ARM 运行先后暴露两层历史栈问题：

1. battle 9 加载时黑屏，`execution-trap.ss9` 显示 Butano
   `Pool does not contain this value`；Maxmod `mp_mix_seg` 从正常 `00/FF` 变为 `2C/D3`，
   随后混音输出覆盖音频队列。`load_battle_scenario<12>` 入口后的 SP 为 `0x030029B8`，
   已落入 Maxmod IWRAM BSS，而非 mGBA 模拟器故障。
2. 把加载候选迁到 EWRAM 后，移动确认和技能解析仍分别触发大对象嵌套副本。写监视抓到
   `memcpy` 在 SP `0x030027F8`、`memset` 在 SP `0x030025B4` 以 4 字节宽度覆盖
   `mp_mix_seg=0x03002970`。调用链中的 `preview_move` 栈帧为 `0x21FC`，动作层又在
   player-flow、resolver、turn-flow 重复复制整份 session。

修复后的内存规则是：`battle_encounter_runtime` 常驻 EWRAM，并统一拥有 load workspace
和 transaction workspace；外层只复制一次 session/player-flow，内层
`confirm_target_in_place → resolve_in_place → resolve_*_draft_in_place →
after_effects_in_place` 操作同一候选。错误仍不提交正式 session/RNG，成功才一次性提交；
这保留了原作和现有宿主测试要求的事务语义。

最终运行证据：

- battle 9 完整角色动作路线：
  `artifacts/butano-action-workspace-runtime-b09-full-20260725-26/`，第 996 帧返回 round 2，
  活动单位 9，鸣人 action 2、樱 action 1、佐助 `[2,5,16]` 均由遥测确认；
- 音频状态写监视：
  `artifacts/butano-action-workspace-runtime-b09-audio-watch-20260725-27/`，frame 100–119
  共 20 次写入全部来自 `PC=0x03000DFC`，宽度 1，仅 `00↔FF`，最低 SP
  `0x03006BB4`；
- scenario 43、battle 9 多单位基线、scenario 41 回归分别在
  `artifacts/butano-action-workspace-regression-s43-20260725-28/`、
  `artifacts/butano-action-workspace-regression-b09-multi-20260725-30/`、
  `artifacts/butano-action-workspace-regression-s41-20260725-29/` 完成；
- ROM SHA-256 `02cd264c7fa3b9c4efd86559cfebb56bafe99da4a9a18dec7750166faf6d7080`，
  ELF SHA-256 `91cb32ac39acb713e84940883561484db170209532085d58b3ff7d472c36e140`；
  `.iwram` 8,840、IWRAM `.bss` 2,172、EWRAM `.ewram` 224、
  `.sbss` 169,960 字节。

自动 mGBA 全程静音，因此这些证据确认音频内存不再被战斗栈覆盖，但不签发主观音频听感。
45 条被动并不等于 45 条效果全部实现；角色专属 sprite、87 项技能逐项演出、剩余被动
消费者、AI 资源/防御策略、章节部署和其余关卡仍是 Goal 后续边界。

# 全战斗内容目录契约（2026-07-25）

本里程碑没有把更多关卡包装成可见演示，而是在现有 session/controller/runtime 前增加
`battle_content_catalog`。它直接绑定生成内容，并把 scenario、map 和 conditions 作为同一个
`battle_content_entry` 返回；`battle_runtime_scene` 不再按相同整数分别索引三张表。

生产目录审计结果为：

- 47 场、141 个变体，其中 85 个非空，41 个含部署占位符，56 个为空；
- 329 条固定单位编队、147 条部署占位记录；
- 62 个有效角色定义、82 个带有效 effect 的主动术、93 个带有效 effect 的忍具、44 个非零被动；
- condition 实际使用 type 0/1/2/3/6/7/8/9，均已有消费者；
- 编队不存在越界、阻塞格或重复位置。

验证器还用可注入 fixture 固定了错误边界：错误 battle id、地图切片越界、阻塞格、重复位置、
无效角色、无效主动术、无效被动和 unsupported condition 都必须在控制器创建前失败。生产表
同时受编译期 `static_assert` 与 foundation self-test bit 5 约束。

TDD 证据：

- 缺少目录头文件的 RED：
  `build/resource-guard/butano-all-scenario-catalog-red-20260725-02.json`；
- 目录实现 GREEN：
  `build/resource-guard/butano-all-scenario-catalog-run-20260725-04.json`；
- 缺少嵌入式自检接线的 RED：
  `build/resource-guard/butano-all-scenario-catalog-selftest-red-20260725-05.json`，
  GREEN 为 `butano-all-scenario-catalog-selftest-green-20260725-06.json`；
- 生产入口仍分别索引三张表的 RED：
  `build/resource-guard/butano-all-scenario-catalog-entry-red-20260725-07.json`，
  GREEN 为 `butano-all-scenario-catalog-entry-green-20260725-08.json`。

61 个宿主 C++ 测试、14 项 Butano 构建接线测试（另 1 项因集成环境跳过）和 Docker ARM
构建通过。ARM 占用保持 `.iwram` 8,840、IWRAM `.bss` 2,172、EWRAM `.ewram` 224、
`.sbss` 169,960 字节。当前 ROM SHA-256 为
`43bf8c18bdfe492b066d35b09593a7e7567ccc110b1b51583bdd9b2f5c98809f`，ELF SHA-256 为
`be96776c775523cab1ef783cb07b6cb0942a94e6614a16692277d81686aa46d5`。

静音 mGBA 代表路线均通过：battle 9 在第 996 帧回到 round 2（9 个活动单位），scenario 43
在第 1375 帧回到 round 2（5 个活动单位），scenario 41 完整路线于第 2580 帧结束。证据分别为
`artifacts/butano-content-catalog-runtime-b09-20260725-31/`、
`artifacts/butano-content-catalog-runtime-s43-20260725-32/` 和
`artifacts/butano-content-catalog-runtime-s41-20260725-33/`。

边界：这一契约证明 47 场内容可以一致地校验和查询，不等于 47 场都可游玩。动态尺寸的通用
地图表现、41 个部署变体的部署 UI、角色专属 sprite、87 项技能逐项演出、其余被动消费者、
AI 资源/休息/防御策略、章节脚本和特殊目标表现仍需继续实现。

# 通用部署确认与输入释放门（2026-07-25）

原作 battle 9 与 battle 13 运行证据都显示：战斗开始前会依次确认每条活动编队记录，第八条
确认后才显示“开始”，之后才进入战前事件和玩家控制。Butano 通用场景此前在 loader 后直接
调用 controller `start()`，这条可见阶段缺失。

本轮新增无 Butano 依赖的 `battle_deployment_flow`：

- 固定编队和 `0xFA..0xFF` 动态占位编队都读取 `battle_scenario_definition`；
- 角色解析从 `battle_scenario_loader` 抽成共享入口，部署预览和最终装载不再各算一次
  `0xFF - selector`；
- A 逐条确认，全部记录后进入独立 START；B 退回上一条，首条 B 取消；
- 未绑定占位符、非法 variant、无效或 inactive 角色在 controller 创建前失败；
- START 确认后等待 A/B 完全释放并运行一个中性帧，避免该 A 串入玩家单位确认。

TDD 的领域 RED 为
`build/resource-guard/butano-deployment-flow-red-20260725-19.json`（缺少
`battle_deployment_flow.h`）；随后 battle 9 的 8 条记录、START/B 回退、battle 32 未绑定
失败及六槽绑定均转为 GREEN。可见 wiring 和两条 Lua 路线也先因缺少部署阶段断言进入 RED，
再接入遥测 phase `0xFFFFFFFE/0xFFFFFFFD`。

运行时第一次 scenario 43 复跑
`build/resource-guard/butano-deployment-s43-mgba-20260725-23.json` 暴露脚本连续 A 没有释放
空帧；修正后又在 battle 9 的
`build/resource-guard/butano-deployment-b09-mgba-20260725-27.json` 暴露生产 START
释放等待未推进遥测，脚本与运行时互相等待。两次均由 heavy guard idle timeout 清理并保留为
失败证据。最终释放门在等待期间持续推进 scene frame，且进入 controller 前额外保留一个
中性帧。

最终静音 mGBA 证据：

- battle 9：`artifacts/butano-deployment-runtime-b09-20260725-39/`，依次观测 8 条部署记录
  和 START，第 1323 帧回到 round 2，活动单位 9；
- scenario 43：`artifacts/butano-deployment-runtime-s43-20260725-40/`，依次观测 4 条部署
  记录和 START，第 1374 帧回到 round 2，活动单位 5；
- scenario 41：`artifacts/butano-deployment-runtime-s41-20260725-41/`，第 2580 帧完成。

62 个宿主 C++ 程序、39 项定向 Python（1 skip）和最终 Docker ARM 构建通过；ARM 段为
`.iwram` 8,840、IWRAM `.bss` 2,172、EWRAM `.ewram` 224、`.sbss` 169,960 字节。ROM
SHA-256 为 `6b0fd4aa24848117e774d096074581f2cea2979a1c9b730152b2fb800239087c`，
ELF SHA-256 为 `a8560acba869167fb67de52161d8f2d58c4bb52874d028acd9b921e1740d8cee`。

边界：当前可见入口仍只提供 battle 9/43 的固定 roster。领域层已经能解析 battle 32 的六个
动态占位符，但章节队伍数据、玩家选人/换装 UI 和 41 个动态部署变体的入口尚未接入；不能把
逐记录确认等同于完整编队系统。

# 全地图运行时活动边界（2026-07-25）

生成目录的 47 张地图共有 22 种逻辑尺寸，最大为 23×32。此前 `grid_map<Width, Height>`
把模板容量当作实际边界，map loader 又要求定义宽高完全相等，导致可见运行时分别保留
9×22 和 16×32 两个 controller；继续接关卡会扩张为 22 套模板实例。

现实现采用一个 23×32 固定容量：

- `grid_map` 保存活动宽高，默认等于容量以兼容已有小地图类型；
- materializer 按地图定义宽度读取内容、按容量宽度存储，并保持无效尺寸/切片事务失败；
- 活动区外始终不可访问，cursor、寻路和 AI tile bounds 统一遵守 `contains()`；
- 同一 `battle_runtime_controller` 已依次装载 47 张地图和全部 85 个非空变体；
- 动态部署变体必须通过 load policy 显式绑定占位角色，空变体继续拒绝伪造。

TDD 证据：

- 首个 RED `build/resource-guard/butano-runtime-grid-red-20260725-42.json` 因缺少
  `battle_runtime_grid.h` 失败；
- AI RED `build/resource-guard/butano-runtime-grid-ai-red-20260725-44.json` 证明旧
  candidate bounds 仍会扩到容量边界；
- 领域 GREEN 为
  `build/resource-guard/butano-runtime-grid-domain-green-20260725-45.json`；
- 63 个宿主程序全量 GREEN 为
  `build/resource-guard/butano-runtime-grid-host-all-20260725-46.json`，峰值
  84.40 MiB；
- Python wiring 先因场景仍引用尺寸模板失败，迁移后 23 项通过、1 项按集成环境跳过。

ARM 构建证据为
`build/resource-guard/butano-runtime-grid-arm-build-20260725-47.json`，无代码
warning/error。section 为 `.iwram` 8,840、IWRAM `.bss` 2,168、EWRAM `.ewram` 224、
`.sbss` 129,612 字节，总计 14,814,713；统一实例使 `.sbss` 比部署里程碑的 169,960
减少 40,348 字节。ROM SHA-256 为
`b80e76599d70b655afaadcca75859ca67d862bac252072e5b4672aaf58bac068`，ELF SHA-256 为
`0fa5748a75e6bf893a0b8ca7a3c21be83ea7ea9faed829d1e9916e5ff3e8c683`，本构建遥测符号为
`0x020124CC`。

静音 mGBA 证据：

- battle 9：`artifacts/butano-runtime-grid-b09-20260725-43/`，第 1329 帧以 9 个活动
  单位进入 round 2；
- scenario 43：`artifacts/butano-runtime-grid-s43-20260725-44/`，第 1379 帧以 5 个
  活动单位进入 round 2；
- scenario 41：`artifacts/butano-runtime-grid-s41-20260725-45/`，第 2580 帧完成。

`artifacts/butano-runtime-grid-b09-20260725-42/` 的内容虽然完成，但调用资源守卫时漏传
success marker，守卫无法形成完成 manifest，已被 `...-43/` 的完整证据取代，不用于验收。

边界：全部逻辑地图可装载不代表全部关卡已经可见。最大 23 格宽对应 736px，超过 GBA
regular background 512px 上限；下一阶段必须实现逐关 ROM 视觉资源生成与分块流送。章节
脚本、动态选人/换装 UI、角色专属 sprite、逐技能演出、剩余规则消费者和 AI 策略仍在 Goal
范围内，不能宣称全战斗功能等价。

# battle 11 大地图背景分块流送（2026-07-25）

47 张逻辑地图中 battle 0 虽为 23×32，但三个 variant 均为空；battle 11 是唯一非空且超过
16 格宽的运行样本。其 ROM row 重建结果为 544×480，variant 0 是角色 1/2/3 对角色 34/35。

生成与运行规则：

- `generate_map_chunks()` 从同一 indexed 全图生成 512×512 分块；
- battle 11 origins 为 `[0,32]`，两块的全图重叠区逐像素一致；
- manifest 保存 tile graphics、palette、primary layout、metatile attributes 四类
  SHA-256；
- `battle_background_stream` 校验 origin、viewport 覆盖与最终地图覆盖，重叠区提供
  hysteresis；
- 部署 camera 和战斗 camera 共用 stream helper；`regular_bg_ptr::set_item()` 先释放旧
  BG 资源再载入新块，背景 origin 对齐既有全图世界坐标；
- battle 11 没有新 controller/FSM，通过 battle 43 → battle 9 → battle 11 的 SELECT
  开发链进入同一通用运行时。

TDD 与失败证据：

- 分块生成器最初因既有 `generate_map()` 拒绝 544px 宽进入 RED；
- `build/resource-guard/butano-background-stream-red-20260725-55.json` 因缺少流送状态机
  进入 RED，GREEN 为 `...-green-20260725-56.json`；
- wiring 测试先因没有 battle 11 items、telemetry 和入口失败；
- 首个 runtime `build/resource-guard/butano-background-stream-b11-mgba-20260725-58.json`
  在 scenario 43 部署第 1 帧后 idle timeout。既有 scenario 43 路线随即通过，证明 ROM
  没有挂死；根因是新 Lua 误用不存在的 `emu:removeKey`，第 36 帧回调异常。脚本改用
  `emu:clearKey`，并由 Python 测试明确禁止错误 API；
- `...b11-debug-mgba-20260725-60.json` 是同一脚本错误的短超时复现，不用于验收。

最终 battle 11 证据为
`artifacts/butano-background-stream-b11-20260725-49/`：第 377 帧、5 个活动单位、
round 1 move phase、cursor `(4,4)`，遥测确认 `[0,1,0]`，三张截图分别保存首块、右块和
返回首块。回归证据：

- scenario 43：`artifacts/butano-background-stream-regression-s43-20260725-47/`，
  第 1380 帧、5 个活动单位、round 2；
- battle 9：`artifacts/butano-background-stream-regression-b09-20260725-50/`，
  第 1332 帧、9 个活动单位、round 2；
- scenario 41：`artifacts/butano-background-stream-regression-s41-20260725-51/`，
  第 2580 帧完成。

64 个宿主 C++ 程序和 28 项定向 Python（1 skip）通过。ARM section 为 `.iwram` 8,840、
IWRAM `.bss` 2,168、EWRAM `.ewram` 224、`.sbss` 129,620 字节，总计 14,886,908；
ROM SHA-256 为 `065acbc9dccd452a5b9d1ae6e22560fcd08f3709c2de64c5a7ae8f1f41ab129b`，
ELF SHA-256 为 `cf76684bda74c8d4f93842225ff6c9673271fa9092d6de7026d00c75e6003648`，
遥测地址仍为 `0x020124CC`。自动路线全部静音，不签发音频听感。

边界：该里程碑闭合“大地图视觉如何进入通用 renderer”，不是 47 张背景的全部打包。下一步
应由同一生成协议批量产出剩余 ROM 地图并建立 battle ID → background manifest 查询；角色
专属 sprite/逐技能演出、章节脚本、动态选人换装、AI 资源/防御和剩余碰撞/被动消费者仍未完成。

# 全战斗背景内容目录（2026-07-25）

上一节的 battle 11 适配器已扩展为全量内容层，而不是继续向 renderer 添加关卡特例。
`generate_all_map_chunks()` 遍历 battle 0..46，并为每个 ROM row 生成：

- 一份 `battle_XX_map_chunks.json`，保存 active size、origin、分块文件和四类 ROM source
  SHA-256；
- 一或两个 `battle_XX_map_chunk_N.bmp/.json`；
- 总目录 `battle_background_catalog.json`；
- 生产 C++ 表 `generated_battle_background_content.h`。

审计结果是 47 entries、49 chunks、6,221,312 个原始 indexed 像素。battle 0 的
736×512 地图使用 origins `[0,224]`，battle 11 的 544×480 地图使用 `[0,32]`；其余
45 张地图均为单块。所有高度不超过 512px。

通用 `battle_runtime_scene` 的基础 config 现在只含 battle ID、variant、seed、标题和流程
flags。它先查询一个同时持有 scenario/map/conditions 的 `battle_content_entry`，再独立
查询同 battle ID 的 `battle_background_content_entry`，并验证：

- 两边 battle ID 一致；
- `pixel_width == grid_width × 32`；
- `pixel_height == grid_height × 16`；
- 分块数量、item 指针和 viewport coverage 可被 `battle_background_stream` 接受。

任何失败都在部署前返回；wrapper 和 renderer 不再直接 include 或引用
`battle_XX_map_chunk_N`。这是内容/表现适配器，cursor、碰撞、寻路、单位、回合和 resolver
仍由共享 controller/session 拥有。

TDD 和构建证据：

- 全量生成器测试先因缺少 `generate_all_map_chunks()` 进入 RED；
- 生产审计：
  `build/resource-guard/butano-all-backgrounds-audit-20260725-65.json`；
- 生成 GREEN：
  `build/resource-guard/butano-all-backgrounds-generator-green-20260725-66.json`；
- 生产生成：
  `build/resource-guard/butano-all-backgrounds-generate-production-20260725-67.json`；
- ARM 首次 RED：
  `build/resource-guard/butano-all-backgrounds-arm-build-20260725-68.json`，编译器发现
  background content pointer 与 stream 状态同名；重命名后
  `build/resource-guard/butano-all-backgrounds-arm-build-20260725-69.json` GREEN；
- 64 个宿主 C++：
  `build/resource-guard/butano-all-backgrounds-host-all-20260725-74.json`；
- 106 项相关 Python（1 skip）：
  `build/resource-guard/butano-all-backgrounds-python-focused-final-20260725-78.json`。

ARM 最终 section 为 `.iwram` 8,840、IWRAM `.bss` 2,168、EWRAM `.ewram` 224、
`.sbss` 129,620，总计 16,233,173 字节。ROM 为 6,921,928 字节，SHA-256
`f5c79ffe8616bbeaea87ba36519abf8f9dcfff84fef5ca398daf62b7e9b127cc`；ELF SHA-256
`cef0f451d03e80b05ab53021ab4948e767bd4c02f4aa250e2e60124c53710ee1`。遥测地址仍为
`0x020124CC`，但后续构建必须重新从 ELF 解析。

静音 mGBA 运行证据：

- battle 11：`artifacts/butano-all-backgrounds-b11-20260725-52/`，第 377 帧，
  5 个活动单位，分块 `[0,1,0]`；
- battle 9：`artifacts/butano-all-backgrounds-b09-20260725-53/`，第 1332 帧，
  9 个活动单位，round 2；
- scenario 43：`artifacts/butano-all-backgrounds-s43-20260725-54/`，第 1380 帧，
  5 个活动单位，round 2；
- scenario 41：`artifacts/butano-all-backgrounds-s41-20260725-55/`，第 2580 帧完成。

全库 Python discovery 另运行 1,012 项，保留了 3 个缺少历史 PNG/ss9 原始证据的错误和
1 个既有技能字段语义文案失败；归因日志为
`build/test-results/butano-all-backgrounds-python-all-20260725-76.log`，不把这些既有失败
伪装为通过。

边界：47 张背景都可按 ID 查询，不代表 47 个 variant 都可玩。空 variant 仍为空，41 个
动态部署入口仍需章节队伍/换装输入；对象行为、章节脚本、角色专属 sprite、逐技能演出、
结算表现和剩余规则消费者仍需后续里程碑。

# 动态部署请求与 empty-tile 地图门禁（2026-07-25）

领域层此前已经能用 `battle_scenario_load_policy` 解析 `0xFF..0xFA`，但可见 renderer 额外
要求 `battle_content_entry_kind::fixed_roster`，并在内部构造空 policy。因此 41 个
`deployment_required` 非空变体虽然宿主 controller 可加载，GBA 可见入口仍必然失败。

现已公开 `battle_runtime_scene_request`。章节入口负责提供 battle ID、variant、seed、
标题/流程 flag 和完整 load policy；通用 scene 只拒绝 empty content，并把同一 policy 传入
`battle_deployment_flow::prepare()` 与 `battle_runtime_controller::load()`。固定和动态
编队不再分裂 loader 或 FSM。

battle 32 variant 0 是明确命名的 integration fixture：

```text
placeholder 0xFF..0xFA
        -> [1,2,3,35,35,35]
        -> deployment preview
        -> 12-slot session (6 active)
        -> shared player/AI round
```

该映射只验证注入协议，不是原作章节队伍证据。正式入口必须由章节状态或选人 UI 构造，不能
复制 fixture。

首个运行
`artifacts/butano-dynamic-deployment-b32-20260725-56/` 确认六条部署身份和三名玩家行动，
但敌方完成数永久停在 2/3。遥测 `last_control_error=5`，宿主复现进一步绑定：

- 第二个 AI 选择 action 2 empty-tile move；
- planner destination 为 `(11,11)`，target 为 `(12,13)`；
- 动作后 unit 5 实际位于 `(12,13)`；
- ROM map 32 的该格 `cost=0`、directional mask `15`；
- 第三个 AI 进入前 `apply_battle_occupancy()` 因单位在 blocked cell 失败，scene 只见
  `ai_flow_failed` 并反复重试。

根因是 empty-tile planner 只调用 `_occupied()`，没有验证地图 cost/mask；玩家
`_confirm_target()` 也只调用领域范围预览。修复后：

- AI empty-tile candidate 必须 cost 非零、mask 非 `grid_fully_closed` 且无活动单位；
- 玩家 empty-tile 确认应用同一三项门禁；
- battle 32 宿主测试还直接验证角色 1 的 action 2 不能确认到 blocked `(2,5)`。

最终证据：

- wiring RED：
  `build/resource-guard/butano-dynamic-deployment-wiring-red-20260725-79.json`；
- ARM：
  `build/resource-guard/butano-dynamic-deployment-arm-build-20260725-82.json`；
- 动态 mGBA：
  `artifacts/butano-dynamic-deployment-b32-20260725-57/`，第 1392 帧、deployment
  `[1,2,3,35,35,35]`、6 active、round 2、control/player error 均为 0；
- 固定路线：
  `artifacts/butano-dynamic-deployment-regression-b11-20260725-58/`、
  `artifacts/butano-dynamic-deployment-regression-b09-20260725-59/`、
  `artifacts/butano-dynamic-deployment-regression-s43-20260725-60/`、
  `artifacts/butano-dynamic-deployment-regression-s41-20260725-61/`；
- 65 个宿主 C++：
  `build/resource-guard/butano-dynamic-deployment-host-all-final-20260725-90.json`；
- 109 项相关 Python（1 skip）：
  `build/resource-guard/butano-dynamic-deployment-python-focused-final-20260725-92.json`。

最终 `.iwram` 8,840、IWRAM `.bss` 2,168、EWRAM `.ewram` 224、`.sbss` 129,620，
总计 16,237,096 字节。ROM 为 6,923,076 字节，SHA-256
`209c095031df613576a2c066f71b32ead5e60be72513ec6ea8b158ad0bcfefea`；ELF SHA-256
`2258f62beb36c1d4b84c85d01388a8092a967e04d3266caf54f343e757cc8065`，遥测地址
`0x020124CC`。

边界：动态输入契约已完成，但 41 个变体尚未逐个绑定真实章节 party/level/scripted 状态；
也尚未实现选人换装 UI。对象行为、章节脚本、角色专属 sprite、逐技能演出和结算表现继续
留在 Goal。

# 62 角色战斗待机视觉目录（2026-07-25）

## 逆向纠正

`0x596D5C` 的旧 312-row 地图 tile 解释已撤销。表的真实固定边界是 62 个角色 × 9 个
视觉槽，共 558 行 × 16 字节；342 行有效、216 行为空。每行四个指针依次进入帧描述表、
动画描述表、4bpp OBJ tile 和 BGR555 palette。角色 `N` 的槽 `S` 为
`(N - 1) * 9 + S`，62 个角色的槽 0 全部有效。

槽 0 首帧的 24 字节记录给出 tile index、相对锚点、宽高和 `0x100/0x100` 比例。
生成器按 GBA 1D OBJ tile 顺序解码并保存像素哈希。角色 36/37、39/40、42、55、59
证实不能统一使用 32×64、`(0,-24)`：其中角色 42/59 是 64×64，角色 39/40/55 是
32×32，角色 55 的中心 Y 为 -38。

`tools/generate_butano_battle_unit_visual_content.py` 现确定性生成 62 个待机 BMP/JSON、
`battle_unit_visual_catalog.json` 和
`generated_battle_unit_visual_content.h`。通用部署与战斗 renderer 都按
`character_id` 查目录；身份改变会切换 item，inactive 空槽不再创建替代人物。

## 运行故障与修复

首次 ARM 版本在 scenario 43 成功，但切换 battle 9 后停留在上一遥测。根因不是资源数量，
而是 snapshot 保留 12 个脚本槽：battle 9 的空槽为 inactive 且 character ID 255。
旧 renderer 给每个空槽也创建通用敌人，掩盖了错误；新目录正确拒绝 255，但初版仍提前
为 inactive 槽查资源并触发断言。

最终实现以每个领域槽一个 optional sprite 建模：

- inactive 空槽不分配 OBJ tile/palette；
- 召唤把空槽激活时即时创建对应角色 sprite；
- 单位死亡/移除后释放 sprite；
- 身份覆盖变化时在原槽调用 `set_item()`；
- OAM 预算仍按最多 12 个活动单位计算。

## 验证

- 生成器 3 项测试和 CLI 入口通过，固定 342/558 稀疏结构与代表像素哈希；
- Docker ARM 构建：
  `build/resource-guard/butano-unit-visual-arm-build-final-20260725-99.json`；
- battle 32：
  `artifacts/butano-unit-visual-b32-final-20260725-66/`，部署
  `[1,2,3,35,35,35]`，第 1393 帧到 round 2，control/player error 为 0；
  部署截图分别显示鸣人、佐助、小樱和角色 35，而非阵营替代图；
- scenario 43：
  `artifacts/butano-unit-visual-regression-s43-20260725-67/`，5 active、round 2；
- battle 9：
  `artifacts/butano-unit-visual-regression-b09-20260725-68/`，召唤后 9 active、
  round 2；
- battle 11：
  `artifacts/butano-unit-visual-regression-b11-20260725-69/`，chunk `[0,1,0]`；
- scenario 41：
  `artifacts/butano-unit-visual-regression-s41-20260725-70/`，第 2580 帧完成；
- 65 个宿主 C++ 程序：
  `build/resource-guard/butano-unit-visual-host-all-20260725-106.json`。

最终 ROM 为 6,995,284 字节，SHA-256
`97677fab0c5afc860286db3db95a469917e82a7b5c03d1626eed5b388435a899`；
ELF SHA-256
`ee2977079040560b27d78a6933dcae0dc235b1a717aa369d7d0b35e0838974ed`。
自动路线继续静音，只验玩法与资源，不签发音频听感。

边界：本里程碑只恢复 62 个角色的 ROM 待机帧、尺寸与锚点。9 槽中的移动、朝向、受击、
技能和胜利动画尚未进入运行时 animation timeline；不能据此宣称角色专属表现或完整战斗
视觉已经完成。

# 完整角色逐帧动画与默认共享 scenario 41（2026-07-25）

上节“只恢复待机帧”的边界已被本里程碑取代。`0x596D5C` 的 62×9 表已完整解码
342 个有效槽、全部帧、最多 5 段复合 OAM 和 ROM duration，生成 534 个 shape-specialized
sprite 资产。槽 0 提供四向待机/离场/到达，槽 1–4 提供右向
结印/投掷/近战/受击，槽 5–8 是部分角色的显式左向版本；没有左向槽时由运行时镜像。

表现事务不再只保存目标格。`action_result` 的 `affected_unit_ids` 经过玩家/AI flow 和
controller 进入 presentation，范围行动和致死目标都按实体 ID 保留并播放。动作族同时
区分近战突进与结印/忍具原地表现。

默认 `main.cpp` 已直接调用 `run_battle_41_scene()`，scenario 41 与 battle 9/32 使用同一
`battle_runtime_scene`。旧 264 帧整屏攻击资产已从生产 `graphics/` 移到
`references/scenario-41-attack-animation/`，ROM 构建不再生成对应 gfx 对象。

最终验证：

- ARM：`build/resource-guard/butano-final-unit-animation-arm-build-20260725-155.json`；
- scenario 41：`artifacts/butano-shared-s41-runtime-20260725-84/`，round 2、action 5、
  control/player error 0；
- battle 9：`artifacts/butano-unit-animation-b09-20260725-86/`，3v5、不同角色动作、
  召唤后 9 active、round 2；
- battle 32：`artifacts/butano-dynamic-deployment-b32-20260725-87/`，动态六单位部署、
  round 2。

最终 ROM 为 9,106,684 字节，SHA-256
`b18135d9128773fd0ab4b3acad6f9ef67db1f69d77a394a503ce3b98a968cec1`。自动路线均静音，
不签发音频听感。仍未闭合的是招式特效/镜头/章节演出和所有动作族的原作逐帧电影脚本。

# 命中次数驱动表现时长（2026-07-25）

旧共享表现层无论 resolver 生成多少 hit，都固定播放三次 impact 和 96 帧动作。这会让
分身/状态等零伤害动作凭空受击，也会把单击与多段术画成同一种节奏。

现在 `action_result.generated_hits` 经过玩家和 AI flow 进入 presentation 的
`impact_count`。表现层以领域已提交的实际 hit 数调用
`total_frame_count(impact_count)`，其实现是
`battle_action_animation::total_frame_count(impact_count)`，生成 0–32 段 impact；返回、
收势、角色槽切换和输入锁都使用同一动态边界。表现层仍然
没有 HP、命中或回合写入口。

运行时发现 outcome 已提交后，旧 HUD 会在角色仍处于 impact 时提前显示
`BATTLE COMPLETE`。renderer 现在只在表现事务忙碌时显示 `RESOLVING`，待返回和收势完成
再显示领域结果；这只遮罩可见阶段，不延迟或回滚领域提交。最终 ARM 证据为
`build/resource-guard/butano-resolved-impact-outcome-mask-arm-build-20260725-188.json`，
scenario 41 为 `artifacts/butano-resolved-impact-s41-20260725-93/`，battle 9 为
`artifacts/butano-resolved-impact-b09-20260725-94/`。ROM 为 9,106,908 字节，
SHA-256 `23ec3ecfec4b50c14605318983fa86823aeda85baf87e80d7ace48411cad6a02`。

# 完整动作身份与场景装备加载（2026-07-25）

动作身份已从“主动术有名字、忍具仍显示编号”收敛为统一表现投影。
`ninja-tool-identities.json` 覆盖连续 ID 0–93，生成器同时产出 87 条主动术与 94 条忍具身份
及共享中文 sprite font。攻击与防御列表按来源查询身份；名称不进入 resolver、成本、目标或
AI。仅由攻略地址关联的忍具使用 `guide_address_correlated` 并显示 `?`，保留证据边界。

运行验收暴露并修复了另一条真实断链：旧 `battle_scenario_loader` 从未给
`UnitInstance.equipped_tools` 赋值，因而生产关卡不可能自然出现忍具。现在 load policy
提供每角色四槽装备，loader 在候选 session 中验证全部忍具 ID 后再原子提交；非法 ID
返回 `invalid_ninja_tool` 且不会改变已有会话。battle 9 为接线验收给鸣人槽 0 装入 ID 1
十字手里剑；这是夹具，不是已确认的原作章节装备。

静音 mGBA 路线
`artifacts/butano-complete-action-identities-b09-20260725-01/` 在第 1109 帧完成首轮并返回
round 2。第 483 帧遥测明确记录 4 项动作中的索引 3 为
`kind=1`、`tool_slot=0`、`id=1`，`naruto-tool.png` 同时显示十字手里剑身份；最终
control/player error 均为 0。验证清单：

- 66 个宿主 C++：
  `build/resource-guard/butano-complete-action-identities-host-all-final-20260725-219.json`；
- 无 warning/error 的干净 ARM 构建：
  `build/resource-guard/butano-complete-action-identities-arm-build-final-20260725-220.json`；
- 遥测符号地址 `0x02012534`，大小 112 字节，新增动作来源和忍具槽字段；
- ROM 9,119,800 字节，SHA-256
  `a08eb07626563df9a1506afd0bcfcd60fa0d0ec3ef815d2b00fa50cbab04f6fc`；
  ELF SHA-256
  `2a137da0f6cad671ed80cf9890b044a4c6d1a13a982a42a22484413786376750`。

自动 mGBA 保持静音，不签发主观音频听感。该里程碑闭合的是动作身份与本场装备装载链，
不是完整战斗系统：真实章节装备来源、换装/补充 UI、AI 资源与防御策略、章节脚本、结果演出
和其余动作专属特效仍在 Goal 范围。

# 反应族闭合与旧 facade 退役（2026-07-25）

原 ROM scenario 41 攻击确认快照分别注入 `0x04/0x09/0x0A` 八字节状态记录，并以每次
仅一个 A 输入继续到结算。结果与 `0x080763E0` 预处理器、
`0x08076A30` 共享 resolver 一致：

- `0x04` 相邻时消费、取消整次来袭、不移动；
- `0x09` 按状态 `+3` 距离门反向伤害攻击者并取消来袭；
- `0x0A` 按同一距离门先反向伤害攻击者，再继续原来袭；
- `0x16` 补齐原 ROM 的相邻门；
- `0x09/0x0A/0x19` 统一走 counter handler。

状态机不再用 `bool` 混合表达“未触发”和“反击后继续”，而是返回
`not_triggered / continue_incoming_damage / cancel_remaining_hits`。完整运行哈希、
输入和边界见 `notes/battle-reaction-family-runtime-20260725.{md,json}`。

同时完成了生产树复核。正式入口此前虽已使用 `battle_scene_controller`，旧
`scenario_41_battle`、`scenario_41_scene` 及其整屏/分层状态资产仍在 `SOURCES`/`GRAPHICS`
目录中参与构建。它们现连同 10 个旧 facade 测试和 194 个图片/配置文件移至
`references/legacy-butano-scenario-41-screenshot-prototype/`。生产树结构测试要求：

- 不存在旧 facade 源文件；
- 不存在 `class scenario_41_battle` 或 `run_scenario_41_scene`；
- `scenario_41_*` 生产图形仅保留共享运行时使用的 cursor/cursor shadow 四个文件。

这次退役关闭了“旧截图原型仍能被重新接回 ROM”的入口。正式战斗仍由
`battle_scene_controller → battle_encounter_runtime → BattleSession/ActionDefinition`
生成状态，表现层只消费 snapshot。角色专属特效、准确声音链、精确替身落点 RNG 与对象
落点排除仍未闭合，完整 Goal 不得标记完成。

最终验证：

- 全量宿主 C++ 通过，guard：
  `build/resource-guard/butano-reaction-facade-host-all-20260725-01.json`；
- 53 项定向 Python 通过、2 项按集成开关跳过，guard：
  `build/resource-guard/butano-reaction-facade-python-targeted-20260725-05.json`；
- 清理生成目录后的 devkitARM 构建通过，且 build 中只有 cursor/cursor shadow 四个
  scenario 41 图形生成物，guard：
  `build/resource-guard/butano-reaction-facade-arm-clean-build-20260725-04.json`；
- scenario 41 实机进入 round 2 并以 action 5 胜利，control/player error 均为 0：
  `artifacts/butano-reaction-facade-s41-20260725-06/`；
- battle 32 动态部署六单位并进入 round 2：
  `artifacts/butano-reaction-facade-b32-20260725-07/`；
- battle 9 载入 3v5、浏览鸣人/小樱/佐助不同动作、召唤后 9 active 并进入 round 2：
  `artifacts/butano-reaction-facade-b09-20260725-08/`。

ROM 为 9,478,580 字节，SHA-256
`0a1a17a1a420ab2e92abf1bf75085fe34e8c948c0de91f069a81cc7a253c58dc`；
ELF SHA-256
`71a6259591349bfd6893483123918842ded6b6c44a4b5b040a17c5ee1b9f239f`。
三条 Butano mGBA 路线仍为静音验证，不证明音频听感已修复。

# 被动消费者库存与恢复/经验接线（2026-07-25）

新增 `tools/analyze_battle_passive_consumers.py` 对 ROM 全地址空间扫描 Thumb BL，不以
被动名称猜语义。`0x0806DDA4` 只有 15 个直接调用点，请求类型为
`0x0C、0x14–0x20`；其中 `0x1F` 有两个调用点。查询表存在 32 种 target type 不表示 32 种
都会由战斗运行时直接消费，`0x01–0x0B、0x0D–0x13` 当前没有直接调用。确定性结果与
ROM/函数哈希保存在 `notes/battle-passive-consumer-bindings-20260725.json`。

本里程碑只接入两个有完整算术数据流的消费者：

- `0x08077C1C..0x08077C53`：`floor(max_hp / 5) + type 0x14 value_a`，进入
  `restore_hp_and_chakra` 的共享 resolver；缺少被动时仍保持五分之一恢复。
- `0x08089064..0x080890EF`：先汇总同角色全部有效战斗实例的 carried battle EXP，再应用
  `floor(sum * type 0x15 value_a / 100)`。结果域不再只读取第一个角色实例，因此分身或
  召唤实例取得的经验不会丢失；任务经验和回合奖励不受该被动放大。

TDD 红阶段分别观测到恢复结果仍为 20（期望 50）以及只返回首实例 50（期望同角色
`50+10` 再加 5% 得 63）；最小实现后聚焦测试转绿。本段当时仍把 `0x1A–0x1C` 记为
视觉配置，该结论已被后续地形消费者里程碑纠正；它们现在是类别 `1/3/7` 的逐路径预算。
这仍不能把当前进度误报为全部被动效果完成。

验证结果：

- 67 个 game 宿主 C++ 程序全量通过：
  `build/resource-guard/butano-passive-consumers-host-all-20260725-01.json`；
- 被动分析、生成、生产树结构与构建接线定向 Python 通过：
  `build/resource-guard/butano-passive-consumers-python-20260725-02.json`；
- 固定 devkitARM 镜像清理与清洁构建通过：
  `build/resource-guard/butano-passive-consumers-docker-clean-20260725-04.json`、
  `build/resource-guard/butano-passive-consumers-arm-clean-build-20260725-05.json`；
- 静音 mGBA scenario 41 走完领域结算到 phase 15，动态结果仍为
  `100 + 50 + 25 = 175`、`LV1 → LV2`、剩余 EXP 25、HP 成长 14，控制器/玩家错误为 0：
  `artifacts/butano-passive-consumers-s41-results-20260725-06/`。

最终 ROM 为 9,478,900 字节，SHA-256
`161507b510d0b5e5ab63b4ba7e75cdad7d87a31c1c4d244b86b137a13d53d7f8`；
ELF SHA-256
`784e6987c48b78d2aae0b464dd126876842739839c6c39f2dd87e213ef837283`。mGBA 路线静音，
不证明用户报告的音频撕裂已修复。

# 连续攻击被动进入统一命中事务（2026-07-25）

`tools/analyze_battle_continuation_hits.py` 同时锁定原 ROM 静态控制流和 scenario 41
单变量运行样本。`0x08076208` 先筛选 effect code `0x01/0x14/0x15`，再按 runtime kind
查询：

- `2/current_hp → target 0x16 / passive ID 17`；
- `1/current_chakra → target 0x17 / passive ID 18`；
- `5/ninja_tool → target 0x18 / passive ID 19`。

一次唯一 action ID 只消费一次概率 RNG；成功标记由同 action ID 的所有排队事件复用。
`0x08076360` 随后把这些事件 `+0x12` 的基础 hit count 增 1，`0x08076034` 才逐 hit
生成普通命中、暴击和无视防御标志。它不是“额外伤害百分比”，也不是在每个面积目标上各
掷一次。

运行对照源为
`artifacts/runtime-checkpoints/scenario-41-attack-confirmation.ss9`。只把鸣人单位记录中
passive ID 17 的 level byte `0x02024325: FF → 13`（十六进制 0x13，即 stored level 19），
概率由 `10 + 5*(19-1)` 变为 100%。相同 A 输入到 frame 180 后：

- baseline：event hit count 1、continuation mark 0、hit flags `[1]`；
- control：event hit count 2、continuation mark 1、hit flags `[1,1]`。

完整 checkpoint/audit/ROM/函数哈希在
`notes/battle-continuation-hit-observations-20260725.json` 与
`notes/battle-continuation-hit-bindings-20260725.json`。2003 GameFAQs Skill List 的
被动名称和每级 +5% 仅作文本交叉验证：
`https://gamefaqs.gamespot.com/gba/918717-naruto-konoha-senki/faqs/25752`。

Butano 的单体与面积 resolve 现都在动作事务入口调用同一个 continuation roll。面积目标
共享结果；新增 hit 继续复用现有 per-hit resolver，所以 miss、critical、ignore-defense、
替身和反击的顺序没有另起一套。红测先在 melee 100% 样本得到 generated hits 1（期望
2），随后覆盖三类动作、错误类别不触发、完整 RNG 顺序和两目标共享一次掷骰。当前边界是
原 ROM `event+0x16 != 0` 的排除语义尚未命名；不得据此宣称被动系统或完整战斗 Goal 已
完成。

# 回合开始被动进入阵营调度与表现 FIFO（2026-07-25）

原 ROM `0x0806DF88..0x0806E1AF` 及其唯一调用点 `0x080736DE` 已闭合为阵营开始
消费者。控制器先完成 side-end、翻转阵营位，再调用该函数；单位内查询优先级固定为
`0x1D→0x1E→0x1F→0x20`，四组共用 `unit+0xBE` 锁存。确定性 ROM/函数/调用点与
被动表绑定保存在 `notes/battle-side-start-passive-bindings-20260725.json`。

Butano 新增 `battle_side_start_passive_system` 并在 `BattleSession::start_round()`、
玩家转敌方、敌方结束进入新回合三处同一阵营开始边界调用。已实现的 `0x1D–0x1F`
分别覆盖低 HP 回血并补满查克拉、低 HP 回血并获得 5 回合攻击增益、四分之一 HP 门下
获得 3 回合攻击增益。数值直接来自现有 `BattlePassiveState`，状态继续进入共享
`battle_status_store → battle_attribute_system`，没有另建角色特例。

每次阵营开始生成 sequence 和固定容量领域事件。controller 只消费新 sequence，并把
多单位事件放入表现 FIFO；敌方最后动作、新回合脚本和被动同一边界相遇时，动作先显示，
再逐个显示被动，脚本 snapshot 最后继续。HUD 会显示被动名、HP/查克拉差值、攻击增益，
状态槽已满时显示 `STATUS FULL`。遥测新增被动 ID、家族、资源差、状态码/强度/持续时间和
写入结果，后续 mGBA 路线无需靠截图猜触发。

TDD 红阶段先得到缺失 side-start 头文件/分析器、缺失表现映射/FIFO、遥测仍为 248 字节，
实现后新领域、表现、遥测和控制器聚焦测试转绿；全量宿主 C++ 通过
`build/resource-guard/butano-side-start-host-all-20260725-01.json`。本节当时保留的
type `0x20` 已在 2026-07-26 由
`notes/battle-passive-coverage-and-battle11-runtime-20260726.md` 的后续里程碑取代：
机械契约已实现，可见名称与专属动画仍未闭合。这仍不是完整被动系统或完整战斗 Goal。

最终验证从 `make clean` 后重新构建 ARM ROM，通过摘要为
`build/resource-guard/butano-side-start-arm-clean-build-rerun-20260725-09.json`；
定向 Python 为 88 pass、1 条件 skip。静音 mGBA scenario 41 在 frame 476 依次完成部署、
两轮行动、组合拳表现、结果与升级，`last_control_error=0`、
`last_player_error=0`，审计为
`artifacts/butano-side-start-s41-results-20260725-01/audit.json`。该场景的默认满 HP
编队不会自然触发 `0x1D–0x1F`，所以这条实机路线只能证明回合调度/FIFO 接入没有破坏
既有流程；低 HP 触发、共享锁存、状态槽满和多单位 FIFO 仍以领域及 controller 集成测试
验收，不把未出现的实机效果写成已观察事实。

# 85 个非空变体首轮换边矩阵（2026-07-25）

新增 `test_battle_all_scenario_runtime.cpp`，不再只以 battle 9/11/32/41/43 证明通用性。
测试对 47×3 目录中的 85 个非空变体使用同一 12 槽、23×32 controller，逐页推进战前
脚本，玩家逐单位原地移动并结束行动，再让全部敌方 AI 执行，直到第 2 回合或合法结果。
这条 **85 个非空变体首轮换边矩阵**最初在 **battle 10 variant 2** 红失败。

失败候选为敌方角色 8：从 `(1,4)` 规划到 `(1,5)` 后，以 action 4 变化术对
“**移动后的自己**”施术。planner 已把 actor 投影到目的格，`battle_action_execution`
仍通过旧 session 坐标查询 `(1,5)`，得到空目标；即使显式 actor ID 被传入，resolver 的
**只读 preview**也曾引用移动前实例，最终返回 `invalid_target`。最小修复把 draft
`preview_position` 上的非 empty-tile 目标解析为 actor ID，并让 self target preview
读取已经投影坐标的 actor 副本。没有增加 battle ID、角色 ID 或技能 ID 特判。

聚焦测试先稳定复现移动后 self target 的 preview 失败，修复后同时验证 preview 零写、
resolve 成功、身份链接仍为 actor 且位置提交到 `(2,1)`；全矩阵随后转绿。该结果证明第一
回合共享脚本/玩家/AI/condition 链可以承接所有非空内容变体，但仍不等于每场完整胜负路线、
章节队伍输入或技能专属表现均已验收。

最终全量宿主 guard 为
`build/resource-guard/butano-all-scenario-round-host-all-20260725-11.json`；89 项定向
Python 通过、1 项按既有条件跳过。零缓存 ARM guard 为
`build/resource-guard/butano-all-scenario-round-arm-clean-build-20260725-14.json`。
静音 mGBA scenario 41 完整结算回归见
`artifacts/butano-all-scenario-round-s41-results-20260725-01/audit.json`，控制/玩家错误
均为 0。ROM/ELF SHA-256 为
`4350b8ba73e00b251463ab2f343fc531909d38b797edefe1581048b5a7f57848` /
`628003fa52d1d8f5bd469397627ddc28b87fe526080cf4bd8f68e2b148a6a0b1`。

# 有序两组件动作替换截图式“组合技”（2026-07-25）

用户复核指出此前版本仍把截图和选项拼成“战斗”。本轮回到原版 ROM 的真实菜单与动作构建
函数，确认连续攻击是一条由玩家输入驱动的领域事务，不是场景动画分支。

`tools/analyze_battle_action_combinations.py` 哈希绑定 `0x08075B58` 和
`0x0853DFB0`：只有输入组件数为 2 时扫描五条有序配方；命中时把两个组件替换成动作
10/11/13/17/18，未命中时保留原组件数并分别调用两个动作初始化器。确定性结果写入
`notes/battle-action-combination-bindings-20260725.json`。原版运行时又补齐两个菜单边界：

- 多重影分身确认后强制返回术列表，显示“请选择要使用连续攻击的攻击术・忍具”；动作 9
  暂存后查克拉显示 `20→15`，再选忍者组合拳才进入目标选择；
- 火遁术查克拉不足时先失败；只把临时 savestate 的佐助查克拉改为 `9/9` 后，会显示
  “继续使用连续攻击进行攻击吗？”。默认继续后返回术列表，火遁成为第一组件，查克拉显示
  `9→7`。

完整输入、checkpoint、ROM/emulator 哈希和单变量边界在
`notes/battle-action-combination-player-flow-20260725.md`。临时 savestate 修改没有进入
仓库 ROM，也没有改写 `rom/base.sav`。

Butano 新增正式 `CombinationDecision` 和第一组件草稿阶段。选择“否”按单动作进入目标；
选择“是”或使用不能单独执行的多重影分身时，只在 `battle_player_action_flow` 保存组件、
资源预留和上下文动作资格，真实 `BattleSession` 零写。B 撤销保持在术列表。第二组件确认
后：

- 五个 ROM 配方使用派生 `ActionDefinition`，表现事件也携带派生动作 ID，而不再把第二个
  菜单项当组合结果；
- 多重影分身与普通攻击/攻击忍具的未匹配组合，把 effect `0x08` potency 加到后续动作的
  hit 数；
- 其他合法未匹配配对按顺序执行两个共享 resolver 效果，合并一个 `ActionResult`；
- 两项资格、合计查克拉/HP、忍具槽、目标和 RNG 都在 session 副本中验证，任一步失败时
  session/RNG 原子回滚。

场景控制器此前在第一组件后无条件跳 `TargetSelection`，现改为读取 player flow 的真实
phase；组合确认、取消、暂存和目标阶段都有 controller 集成测试。运行时 HUD 显示
`COMBO?`、是/否、`COMBO 1/2`、预留查克拉和 A/B 操作反馈。上下文投影会把不能作为第二
组件的非攻击动作标为不可选，而不会删除角色真实目录。

同时修正 `RangeShape::maximum_distance()`：原 ROM 距离字段只有低 5 位，先前 `&0x7F`
会把 `0x20/0x40` 标志误算成几十格距离；现为 `&0x1F` 并有红绿测试。新增/扩展测试覆盖
五个派生配方成功结算、工具 wildcard、普通双效果、多重影分身增段、组合确认是/否/取消、
场景 phase wiring、派生动作表现身份和 EWRAM snapshot 预算。76 个 game 宿主程序全量
通过；85 个非空 scenario 变体随后各推进到第 101 回合边界或合法结算。宿主全量、scenario
压力、定向 Python、清洁 devkitARM 构建的 guard 分别为：

- `build/resource-guard/butano-action-combinations-host-all-20260725-02.json`；
- `build/resource-guard/butano-action-combinations-host-stress-20260725-01.json`；
- `build/resource-guard/butano-action-combinations-python-20260725-03.json`；
- `build/resource-guard/butano-action-combinations-arm-clean-build-20260725-05.json`。

最终 ROM/ELF SHA-256 为
`65232ffc6c45c18bf8968184d1da575940ef61676b34dc09a46038e5377a3c7c` /
`0e4f1b9560f7ff855c43adc7cfc493138f6d9fb166c3d7f4282d8143fdc40ac0`。
静音 mGBA 首次回归发现新增 `CombinationDecision` 后 Lua 仍持有旧 phase 编号：
controller 的 `script_blocked` 已从 17 移到 18，自动驾驶因而停在战前脚本。运行遥测
`artifacts/butano-action-combinations-s41-trace-20260725-03/trace.json` 明确记录
`phase=18`，没有黑屏或崩溃。所有受影响脚本统一改为当前枚举值，并新增
`test_butano_battle_phase_contract.py` 从 C++ 枚举反查每个 Lua 常量，防止再次漂移。

修复后 scenario 41 在 frame 464 完成部署、两轮行动、动作 5 表现、结果和升级：
总经验 175、等级 `1→2`、剩余经验 25、HP 成长 14，控制器/玩家错误均为 0。guard 与
审计分别为
`build/resource-guard/butano-action-combinations-s41-mgba-20260725-10.json`、
`artifacts/butano-action-combinations-s41-results-20260725-04/audit.json`。这条 ARM
路线是共享单动作/结算回归，不冒充两组件菜单的实机覆盖；两组件 flow/controller 由宿主
集成测试验收。角色专属组合动画、所有红圈术的自然菜单样本和非静音音频仍未闭合，完整
战斗 Goal 保持未完成。

# AI 强制与可选连续攻击候选（2026-07-26）

编队运行时配置审计暴露了一个后续关卡风险：动作 9 的 effect `0x08` 在单动作 resolver
中没有独立效果，玩家流程会强制选择第二组件，但 AI 此前直接把目录每项作为单动作评分。
一旦敌方鸣人通过角色模板或未来脚本获得动作 9，就会消耗查克拉并结束行动，却不产生任何
战斗效果。

本轮没有用“过滤动作 9”掩盖缺口。扩展后的
`tools/analyze_battle_action_combinations.py` 对原 ROM 证明：

- `0x080851F8` 总规划器调用 `0x08083040` 候选枚举器；
- 候选枚举器调用 `0x08082354` 共享组件枚举器并保存返回组件数；
- 共享枚举器以 `0x1800` 识别连续攻击；`0x0800` 可选第二组件，先返回单动作再在后续
  调用枚举组合；`0x1000` 强制第二组件，直接循环而不返回单动作；
- 全 87 项模板扫描得到可选动作 `[12,16]`，强制动作 `[9,14,25,29]`。动作 9 的
  `0x1008` 只是 effect `0x08` 加强制位的一个实例。

Butano 的 AI 目录现按同一标志生成普通与组合候选：动作 12/16 同时保留单动作与组合，
动作 9/14/25/29 只生成组合。派生动作、影分身增段、增益后攻击和普通双攻击各自建立
规划投影；公共目标射程只在两个组件作用于同类目标时取交集，自我增益不会把后续对敌攻击
错误压成 0 射程。胜出候选通过同一组合事务逐组件结算，结果保留第一/第二/派生身份。
红测依次证明动作 14 不被识别、可选组合未生成、48 容量截断 54 项满载佐助，以及自我
增益被错误当成 0 射程；绿测覆盖 `9+5→11`、`9+忍具18`、`12+12→13`、`14+5` 的
状态+伤害原子事务和玩家强制暂存。

1,728 条当前编队记录中，主槽动作 25 出现 5 次、动作 29 出现 2 次；其中 4 条
`affiliation=1` 的动作 25 属于固定敌方内容，所以这次纠错会影响现有关卡，不只是未来
模板。动作 9 仍没有敌方主槽样本。原作候选枚举顺序已由 opcode 闭合；最终 utility 的
逐整数权重尚未全部命名，当前使用共享通用 AI utility，不宣称权重逐值相同。

验证分为三层。77 个宿主 C++ 测试全部通过，其中 AI flow 集成测试精确证明
`9+5→11` 与 `9+忍具18` 的组合身份、段数、HP/查克拉/忍具槽事务和回合推进；10 个
相关 Python/文档测试模块共 67 项通过；固定 devkitARM 构建通过，ROM/ELF SHA-256 为
`b8ad10c09ca23235f57f258537b2bea03f98112f6e7cb3236b8225a295771934` /
`ff6815dc40cc597cee7ea9ae9e8e391003746fb1a64ce245b6b8b02eb57638a1`。
最终宿主和 ARM 守卫分别为
`build/resource-guard/butano-ai-forced-combination-final-host-20260726-21.json` 与
`build/resource-guard/butano-ai-forced-combination-final-arm-20260726-22.json`。

第一次静音 mGBA 回归误用了上一构建的遥测地址 `0x0201A3E0`，60 秒 idle timeout 后
五个遥测/输入文件仍为 0 字节；失败证据保留在
`artifacts/butano-ai-forced-combination-runtime-20260726-04/guard.json`，不能解释为
ROM 黑屏或回合停滞。随后用 exact ELF 的 `arm-none-eabi-nm` 解析到
`konoha_battle_runtime_telemetry=0x0201A684`，重跑在 frame 2791 完成 battle 9：
9 个活动单位、鸣人动作 2/忍具、樱动作 1、佐助动作 2/5/16、五敌行动与 round 2 均由
遥测确认，控制器/玩家错误为 0。证据及哈希清单在
`artifacts/butano-ai-forced-combination-runtime-20260726-05/manifest.json`。该路线静音，
不验证音质；也因当前编队无敌方主动作 9，只作为 ARM/session 回归，不替代组合集成测试。

随后扩展到完整 `0x0800/0x1000` 策略后的最终验证仍为 77/77 宿主 C++ 和 10 个
Python/文档模块共 67 项通过；满载佐助的 54 个选项、动作 12 可选组合、动作 14 强制组合
与 85 个非空场景矩阵都在该轮宿主范围。固定 devkitARM 构建 guard 为
`build/resource-guard/butano-ai-combination-policy-arm-20260726-29.json`，仅保留既有
`battle_runtime_scene.cpp:693..694` null-dereference 编译器告警。ROM/ELF SHA-256 为
`5be556eca9087c1d5dfca714f9a5c2943af0dd0281608edcb77abd874946da32` /
`9ddc1d75398e966d2f96c9908aecb5cf7e240618a046678440a6bbcd28573386`。
exact ELF 遥测地址 `0x0201A824` 的静音 mGBA 回归在 frame 2791 完成 battle 9、9 个
活动单位、五敌行动和 round 2，控制器/玩家错误为 0；完整哈希清单在
`artifacts/butano-ai-combination-policy-runtime-20260726-06/manifest.json`。
这仍不签发非静音音质或未自然出现的专属组合演出。

# 战后主技能修炼阶段（2026-07-26）

战斗结果控制器现按原 ROM 的升级后训练链进入独立 `TRAINING` phase。完整非空主技能槽、
修炼点、锁定/未习得/LV1–3 均来自 progression 唯一事实源；A 只调用
`train_primary_action`，表现层不扣点也不改等级。battle 41 的 ARM/mGBA 路线实测
action 8 `0→1`、TP `1→0`，随后退出到 complete。训练快照独立于 1,120 字节 battle
scene snapshot，旧遥测偏移保持不变。证据为
`notes/battle-primary-training-runtime-20260726.md`。

同时纠正旧审计用语：`0x0806A8C0 → 0x0806A790` 写的是原 ROM `unit+0xC0` 的
`0x70` 反应/表现位域，不是一个等待补齐的禁行资格字段。状态 `0x3F` 自身保留持续时间；
不得把 reaction value `0x30` 直接接到行动资格。

# 63 角色战役档案与 SRAM 冷启动恢复（2026-07-26）

此前 scene 只持有三条临时 progression，真实结算和修炼仍会在退出时丢失。本轮新增
63 角色 `battle_campaign_state`，三人队伍按 ID 投影到通用 controller，退出后再按 ID
合并；无关 62 名角色、队伍变化和失败路径均有零写测试。

存储不是 raw struct dump：初始里程碑的两个 4096 字节槽使用 `KBCS` version 1、显式
little-endian payload、generation 和 CRC32，保存 63 名角色的等级、经验、修炼点、
15+24 技能状态和九个忍具 ID。当前 version 2 又加入 94 个忍具数量和 18 个素材数量；
写入后仍必须从 SRAM 读回并完整解码，单槽损坏回退、双槽默认和 32 位 generation 回绕
均由宿主测试覆盖。

该初始里程碑的 80 个宿主 C++、71 项相关 Python 和 devkitARM 构建通过。其 ELF 证明双槽工作区
`0x020010AC..0x020030AB`、两个 campaign 存储
`0x020030AC..0x02005433` 和 48 字节遥测 `0x02005434` 位于 EWRAM。两个独立静音
mGBA 进程先保存 generation 1，再零输入冷启动读回
`Naruto LV2 / EXP25 / TP0 / action8 LV1`；SAV 哈希保持不变。完整证据、ROM/ELF/SAV
哈希和未完成边界见 `notes/battle-campaign-persistence-runtime-20260726.md`。本项不包含
世界地图、手动存档、原作存档兼容、背包/装备 UI、副技能修炼或非静音音频，完整战斗 Goal
保持未完成。

# 主动技/被动技统一训练领域（2026-07-26）

原先的 `battle_primary_training_flow` 只投影 15 个主技能槽，与 ROM
`0x08093070` 的双写入分支不符。生产控制器现使用 `battle_training_flow`：先按模板顺序
列出全部非空 primary 槽，再列出全部非空 secondary 槽，每项带显式 kind、slot、定义 ID、
等级与解锁等级。

训练点和等级仍只有领域命令可以写。主动项调用 `train_primary_action`；被动项调用
`train_secondary_passive`，后者以 45 项 ROM 成长定义校验后原子执行
`TP-1 / secondary level+1`。renderer 只显示 snapshot，未校字被动名称使用
`PASSIVE #ID`。controller 测试证明可从 battle 41 的 action 8 行继续走到 secondary
条目，锁定确认零写；角色 3 / passive 15 的宿主集成证明训练结果进入下一场单位
`passives`，`0x14` 查询值为 30。

最终全量宿主、ARM 和静音 mGBA 证据见
`notes/battle-unified-training-runtime-20260726.md`。mGBA 自然路线只到鸣人 LV2，
因此只验收 secondary 条目可达，没有伪造一次自然解锁后的被动训练。45 项被动完整
consumer、名称二次校字、专属训练表现和非静音音频仍未闭合。

# 忍具库存与实时战前强化（2026-07-26）

campaign 不再把九格装备误当成完整库存。新增 94 项忍具数量、18 项素材数量和由原 ROM
94 条模板生成的强化配方；`ninja_tool_upgrade_service` 在 campaign draft 上统一校验并
原子提交父忍具 `-1`、素材 `-1`、产物 `+1` 和首个已装备父项替换。所有错误路径保持
campaign 不变。

`battle_preparation_flow` 和实时 Butano renderer 已接入主循环，显示装备、配方和数量，
但不拥有业务规则；A 最终调用同一强化服务。save version 2 把两个数量数组纳入双槽
CRC/generation 存档。86/86 宿主、清洁 ARM 和两进程静音 mGBA 已通过：第一进程完成
`67→68 / material6 1→0` 后继续显示 battle 41 地图部署，第二进程零输入读回同一状态。
完整地址、哈希、失败路线与未完成边界见
`notes/ninja-tool-inventory-upgrade-evidence-20260726.md`。这闭合库存/强化底座，不代表
商店、掉落、补给、手动换装或全部章节已经完成。

# 忍具副本分配、手工换装与消费持有量回写（2026-07-26）

战前页现有开始、装备、卸下、强化四个实时入口。装备领域不把“卸下”误写成“新增一件”：
章节持有量是总拥有副本，所有角色装备槽是分配；可用量始终由
`owned - equipped_across_all_characters` 派生。装备事务同时验证角色白名单、等级容量、
可用副本与首个空槽，卸下只释放分配。存档复用同一 validator，CRC 正确但超额分配的状态
仍被拒绝。

战前 flow 现从 campaign party 投影当前索引，根菜单 L/R 可循环切换全部非空队员。切换
只改变投影视角，不复制库存或角色档案；三人集成已证明角色 2 的换装跨 SRAM 和真实
scenario loader 后只进入角色 2 的战斗单位。默认单人教学阵容保持不变。

全量测试同时发现并修复了旧提交边界：战斗 resolver 消耗忍具后只清装备槽，campaign
持有量未扣减。scene progression 现在保存初始装备多重集，以最终差值原子扣减持有量；
新增工具、数量不足或其他合并失败时，成长、装备和库存全部不写。

运行路线不是菜单截图验收。mGBA 先把 `67/11/37` 换为 `1/11/37`，完成 SRAM 写后读，
再在 battle 41 正式 action catalog 观察忍具 1、source kind `ninja_tool`、slot 0；
独立零输入进程恢复同一装备与 `owned1=1/owned67=1`。证据及未完成边界见
`notes/ninja-tool-equipment-allocation-evidence-20260726.md`。商店、掉落和补给仍未闭合，
完整战斗 Goal 保持未完成。

# 地形类别被动与共享路径规划（2026-07-26）

旧实现只把 `0xF` 当墙，并把 `1/3/7` 保存在名为 `directional_mask` 的字段里等待解释；
这会让没有任何训练的角色穿过森林类地形，也会让玩家与 AI 各自形成错误的可达域。本轮
哈希绑定 `0x080698B4..0x08069E43`，确认三类地形分别由 target
`0x1A/0x1C/0x1B` 提供逐路径预算，且起点也消耗一份。生产 API 也已统一重命名为
`terrain_class`，不再暴露会诱导四方向解释的常量和方法。

Butano 现在从每个行动单位的正式被动状态计算 `grid_terrain_traversal_limits`。同一个
pathfinder 同时服务可达域、具体路径、玩家移动预览、AI 规划和 AI 威胁场；渲染器没有
覆盖合法性的入口。零位移只作为避免初始部署锁死的显式玩家例外，不让角色进入相邻未训练
类别。

TDD 从缺失领域头文件、旧碰撞语义和原地误拒绝三个红灯开始；最终 89/89 宿主程序、
ARM 构建和受守卫 mGBA battle 41 路线通过。mGBA 实际拒绝未训练鸣人从 `(4,10)` 进入
类别 7 的 `(3,9)`，再允许其留在原地进入命令阶段。完整 ROM 函数哈希、manifest、截图、
ROM/ELF/SAV 哈希和未完成边界见 `notes/battle-terrain-passive-runtime-20260726.md`。

# 金缚术与命令阻断领域（2026-07-27）

此前 action 80 虽经过正式 resolver，却只写 `reaction_state=0x30`；该 byte 没有持续时间，
也没有行动调度消费者，因此仍是“演出像束缚、规则并未束缚”的空实现。

本轮重新绑定原 ROM：动作模板 `0x08545958` 是 effect `0x3F`、85% 成功率、raw duration
2；handler `0x0807755C` 同时调用 reaction setter `0x0806A8C0` 与 status upsert
`0x0806C204`。阵营翻转后，controller `0x080736E4` 调用 `0x08075350`，按
`3F/3E/3D/0F/11/15` 查询状态并跳过命中单位的激活。哈希锁定和调用目标见
`notes/battle-command-blocker-bindings-20260727.json`。

Butano 现让 action 80 写入 duration 4 的 `0x3F` 活动状态；六个 blocker code 由共享
`battle_commands_blocked` 谓词进入 `battle_session` 的唯一资格门。玩家选人、L/R
轮换和 `battle_ai_turn_flow` 因而消费同一状态事实；reaction byte 只保留给 renderer。
TDD 红灯分别固定“命中后 applied status 为 0”和“阻断单位仍可选择”，绿测覆盖六 code、
同侧其他单位继续行动、AI 零写拒绝、两次 side-end 后恢复资格，以及 miss 不写状态。

全场景回归进一步暴露 battle 20 在玩家整侧受阻后仍尝试打开选择页。现新增事务式
`advance_empty_side`：它执行同一 status/object side-end、边界脚本和 condition，再翻转
阵营；不会伪造“等待”动作，也不会跳过一份 duration tick。battle 20 原失败点和全部
47×3 场景推进到 round 101 的宿主压力测试均已通过。金缚术专属图标、逐帧演出和非静音
音频仍未闭合。最终 92/92 宿主、16/16 相关 Python、devkitARM 和静音 mGBA battle 9
3v5 路线通过；完整哈希和证据目录见
`notes/battle-command-blocker-runtime-20260727.md`。

# 持久被动属性重算链（2026-07-27）

旧覆盖分析只统计 `0x0806DDA4` 的通用查询调用，把 targets `1–11` 的 18 条定义误报成
无 ROM 消费者。重新解码 `0x0806D964` 后确认，角色等级成长完成后会直接遍历 24 个
副技能槽：先完整执行 HP/防御/敏捷百分比和结印成本减免，再执行 HP、查克拉、攻防敏、
移动与忍具容量固定加值。target 10 最终上限为 99，不是纯等级阶段的 9。

Butano 现复用 progression 的 24 槽状态，在 scenario loader 中建立被动修正后的
`hp/max/base_*` 与结印成本；campaign 整备也从同一函数取得忍具容量，不再出现“训练已
保存但战斗/装备不生效”。临时状态 reducer 仍保持独立生命周期，并以新 `base_*` 为
到期基线。覆盖矩阵由 `17/28` 修正为 35 条已有生产消费者、10 条未闭合。

最终 93/93 宿主、121/121 相关 Python、`git diff --check`、固定 devkitARM 和受守护
静音 mGBA battle 9 均通过；frame 2804 进入 round 2，9 个活动单位，控制器/玩家错误
为 0，两类 trap 为空。ROM/ELF SHA-256 为
`be4201732a3a9dcf7ddfdb73fe107db75b7dc842fed8c99b6f5fbf85a31ef6d7` /
`46e9f9c9de1d83db2f8bdb1f8cccb910f2b9c4f0296ff5805eea1e51de072ab9`。
证据见 `notes/battle-persistent-passive-stat-runtime-20260727.md`。targets
`0x0D–0x13`、忍具逐件容量规则、专属表现和非静音音频仍未闭合，完整 Goal 保持未完成。

# 持久被动动作修正链（2026-07-27）

旧覆盖继续漏掉 targets `0x0D–0x13`：原 ROM `0x0806D6B8` 不调用通用查询器，而是在
主动技等级成长后、忍具槽成本物化后直接遍历 24 个副技能槽。它先执行 target 14/16 的
potency 百分比 pass，再执行 targets 13/15/17/18 的 potency 固定加值和 target 19 的
成功率加值。

Butano 现只在 `BattleActionCatalog` 调用共享纯函数修正动作副本；玩家 browser、AI、
preview、resolver 和表现事件因而消费同一事实源。宿主集成不仅断言字段变化，也把动作
16 的 catalog 定义送进正式 resolver，证明伤害没有在后续链路丢失。覆盖矩阵更新为
`17 direct query + 18 inline stat + 9 inline action modifier = 44` 条生产消费者，
剩余 1 条是 ID 0 哨兵。

最终 94/94 宿主、30/30 相关 Python、固定 devkitARM 与静音 mGBA battle 9 round 2
通过；ROM/ELF SHA-256 为
`30719ed9750b832d6136967deeefad200101138d107fff186b1eb577c613aecd` /
`2a67a2367d09d8c6763efbe57a790a14e8986827fd1006f56bd5f061fffbc0d4`。
完整证据见 `notes/battle-passive-action-modifier-runtime-20260727.md`。自然路线没有已
训练的 targets 13–19，mGBA 因此只签结构回归。后续复核 `0x08090004` 已确认忍具容量
是装备数量上限而非逐件重量；下一步是穷举生产可达容量是否始终不超过九格。专属表现、
剩余战役可达性和非静音音频仍未闭合，完整 Goal 保持未完成。
