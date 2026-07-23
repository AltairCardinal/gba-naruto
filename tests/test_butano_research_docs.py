import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "docs" / "butano-local-reference.md"
COST_REPORT = ROOT / "docs" / "butano-konoha-systems-cost.md"
BATTLE_GUIDE = ROOT / "docs" / "butano-scenario-41-battle.md"
RUNTIME_NOTE = ROOT / "notes" / "butano-scenario-41-runtime-20260721.md"
ONE_TO_ONE_NOTE = ROOT / "notes" / "butano-scenario-41-one-to-one-runtime-20260722.md"
REJECTED_BATTLE_PLAN = (
    ROOT
    / "docs"
    / "superpowers"
    / "plans"
    / "2026-07-22-butano-battle-system-implementation.md"
)
RESTORATION_EVIDENCE = ROOT / "notes" / "battle-system-restoration-evidence-20260723.md"
BATTLE_ARCHITECTURE = (
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-07-22-butano-battle-system-architecture-design.md"
)


class ButanoResearchDocsTest(unittest.TestCase):
    def test_local_reference_is_reproducible_and_offline(self):
        self.assertTrue(REFERENCE.is_file(), "Butano 本地参考手册缺失")
        text = REFERENCE.read_text(encoding="utf-8")
        for required in (
            "21.7.1",
            "112a1827c9c6d9e6041a7e93e66f04c4561a6415",
            "third_party/butano/docs/index.html",
            "tools/butano/toolchain.lock",
            "tools/butano/build.sh",
            "离线",
            "升级流程",
            "故障处理",
            "100/50/0=150",
            "38 个稳定边界",
            "264/264",
            "third_party/gba-wav-to-s3m-converter",
            "ec956fc951cc637153139cb968721f427c802e51",
            "tools/butano/mgba_scenario_41_golden_route.lua",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_scenario_41_runtime_note_records_cold_start_evidence(self):
        self.assertTrue(RUNTIME_NOTE.is_file(), "scenario 41 运行证据缺失")
        text = RUNTIME_NOTE.read_text(encoding="utf-8")
        for required in (
            "butano-s41-runtime-20260721-02",
            "c55a440da95401f1ec965dfb73c4293b5d0a9724eb8c686be3369434e50232fd",
            "af6ab51a2ff63d6067908938aa74181fe2bbad0c441e231f3c4dbc80e7d6fe5d",
            "completion_trigger",
            "success-marker",
            "95.6875 MiB",
            "victory.png",
            "result.png",
            "restart.png",
            "逐格执行 198 次寻路",
            "已修复",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_cost_report_covers_every_foundation_system_and_boundaries(self):
        self.assertTrue(COST_REPORT.is_file(), "Butano 成本预研报告缺失")
        text = COST_REPORT.read_text(encoding="utf-8")
        systems = (
            "核心循环与场景",
            "外围流程与部署",
            "章节脚本与对白",
            "地图、碰撞与寻路",
            "单位与战斗实例",
            "回合与行动状态机",
            "技能、伤害与效果",
            "AI 与任务目标",
            "成长、训练与奖励",
            "存档与恢复",
            "UI、文本与图形演出",
            "音频转换与播放",
            "内容转换、调试与验收",
        )
        for system in systems:
            with self.subTest(system=system):
                self.assertIn(system, text)
        for required in (
            "80.9–121.3–191.2 Codex 连续墙钟小时",
            "人周估算已取代",
            "B1",
            "B2",
            "B3",
            "B4",
            "B5",
            "B6",
            "900 个逻辑单元",
            "160 个集成单元",
            "8 小时/日",
            "16 小时/日",
            "24 小时/日",
            "不计逆向补证",
            "旧存档兼容",
            "功能边界",
            "入口",
            "加载",
            "空状态",
            "错误",
            "Goal 实测",
            "功能等价压力样本",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_scenario_41_guide_has_playable_acceptance_contract(self):
        self.assertTrue(BATTLE_GUIDE.is_file(), "scenario 41 用户手册缺失")
        text = BATTLE_GUIDE.read_text(encoding="utf-8")
        for required in (
            "scenario 41",
            "9×22",
            "(4,10)",
            "(4,4)",
            "忍者组合拳",
            "行动结束",
            "胜利",
            "100 / 50 / 0 = 150",
            "B 取消",
            "START",
            "非法目标",
            "加载",
            "空状态",
            "错误",
            "功能边界",
            "notes/butano-scenario-41-one-to-one-runtime-20260722.md",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_one_to_one_note_records_final_visual_and_audio_evidence(self):
        text = ONE_TO_ONE_NOTE.read_text(encoding="utf-8")
        for required in (
            "38 个稳定边界",
            "264/264",
            "cue 5",
            "cue 14",
            "cue 15",
            "cue 8",
            "cue 2",
            "sound 116",
            "sound 138",
            "Maxmod",
            "Goal 实测",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_rejected_battle_plan_cannot_claim_architecture_is_implemented(self):
        text = REJECTED_BATTLE_PLAN.read_text(encoding="utf-8")
        self.assertIn("状态：**已否决", text)
        self.assertIn("截图驱动", text)
        self.assertIn("不得继续执行", text)
        self.assertNotIn("Tasks 1–7 and the Task 8 source wiring/build/runtime slice are implemented and verified", text)

    def test_transaction_rule_is_bound_to_original_rom_evidence(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-action-transaction-bindings-20260723.json",
            "三个取消路径",
            "0x8000 → 0x9000",
            "unit+0x07",
            "资源、位置和行动标记",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("四组哈希绑定", architecture)
        self.assertIn("取消样本", architecture)
        self.assertIn("提交样本", architecture)

    def test_enemy_actions_converge_on_the_shared_resolver(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "18 个 checkpoint",
            "0x6000",
            "0x7000",
            "scenario 45",
            "scenario 50",
            "共同汇入 `0x8000`",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("玩家与 AI 不应拥有两套结算器", architecture)
        self.assertIn("0x6000/0x7000", architecture)

    def test_objective_interrupts_are_bound_to_cross_scenario_evidence(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-objective-transition-bindings-20260723.json",
            "battle 44",
            "(4,3)",
            "0xE000 → 0xE010",
            "battle 15",
            "0x02026807",
            "0→2",
            "同一 `0x8000`",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("目标结果可以抢占普通行动尾部", architecture)
        self.assertIn("不能把所有任务退化为清敌", architecture)
        self.assertIn("尚未证明全局胜负优先级", architecture)

    def test_chakra_and_rest_transactions_are_runtime_bound(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-resource-transaction-bindings-20260723.json",
            "0x3000 → 0x3210",
            "134→119",
            "4→5",
            "0x3310 → 0x1220",
            "24→41",
            "行动标记 `0→32`",
            "不证明通用恢复公式",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("查克拉命令是 HP 与查克拉之间的领域事务", architecture)
        self.assertIn("休息会结束当前单位行动", architecture)

    def test_ninja_tool_runtime_state_is_separate_from_persistent_inventory(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "忍具战斗内消耗事务",
            "0x4100 → 0x9000",
            "unit+0xB1",
            "`1→0`",
            "持久忍具库存区保持零差异",
            "不能把持久背包直接当作战斗内可用次数",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("持久装备/背包与战斗内可用槽位分层建模", architecture)
        self.assertIn("首个装备槽 `unit+0xB1`", architecture)

    def test_multi_unit_l_selection_is_bound_as_a_precommit_roster_cursor(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-unit-selection-bindings-20260723.json",
            "鸣人 → 猫 → 小樱",
            "鸣人 → 猫 → 小樱 → 佐助 → 鸣人",
            "两次连续单输入 `L`",
            "unit+0xC1",
            "当前行动单位指针保持 `0x00000000`",
            "单输入 `R` 从鸣人切到佐助",
            "峰值 tree RSS 50.77734375 MiB",
            "空槽残留标记",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("roster 游标与已确认行动单位分离", architecture)
        self.assertIn("目标代理也可以进入可选 roster", architecture)
        self.assertIn("L/R 的方向均已有运行时绑定", architecture)
        self.assertIn("本场 L 的完整环绕顺序", architecture)

    def test_roster_browsing_and_command_eligibility_are_separate_layers(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-unit-eligibility-bindings-20260723.json",
            "可行动小樱、已行动佐助、护送目标",
            "0x2000 → 0x3000",
            "已行动佐助和护送目标都保持 `0x2000`",
            "单位池、战斗控制区和菜单状态块均为零差异",
            "峰值 tree RSS 50.79296875 MiB",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("浏览 roster 与命令资格分离", architecture)
        self.assertIn("资格检查发生在 A 确认边界", architecture)
        self.assertIn("已行动单位仍能被 L/R 浏览", architecture)

    def test_damage_and_substitution_are_bound_as_resolution_branches(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-effect-resolution-bindings-20260723.json",
            "`0x4100 → 0x8000 → 0x9000`",
            "HP `46→46→32`",
            "HP `110→110→110`",
            "查克拉 `2→2→0`",
            "坐标 `(4,6)→(4,6)→(3,5)`",
            "`unit+0x154`",
            "`0→22→0`",
            "预览值不能直接扣血",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("替身是共享 resolver 内的反应分支", architecture)
        self.assertIn("反应判定先暂存", architecture)
        self.assertIn("不能把预计伤害直接写入目标 HP", architecture)
        self.assertIn("先处理 blocker，再按固定顺序选择 reaction", architecture)

    def test_defense_preparation_browses_actions_then_revalidates_category(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-defense-preparation-bindings-20260723.json",
            "`Up → A → A`",
            "`0x9100 → 0x9100 → 0x9200 → 0x9200`",
            "只能选择防御系・回避系的术・忍具",
            "影分身术同样被拒绝",
            "fb3c96d6eac89402275d1404b7a354323a6baa86d8f385d5dae6be084a75ca51",
            "单位池和战斗控制区始终零差异",
            "峰值 tree RSS 50.875 MiB",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("防御准备复用动作浏览器", architecture)
        self.assertIn("确认时重新验证防御/回避类别", architecture)
        self.assertIn("不能把列表项等同为可准备动作", architecture)
        self.assertIn("不能按名称推断防御类别", architecture)

    def test_successful_defense_is_bound_as_one_shot_reaction(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-defense-reaction-bindings-20260723.json",
            "受控 A/B",
            "查克拉 `5→3`",
            "`unit+0xD4` 从 `0→16→0`",
            "`unit+0xD5=15`",
            "HP 始终为 134",
            "坐标始终为 `(5,6)`",
            "写轮眼专属演出",
            "不是常驻减伤数值",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("确认预览不写领域状态", architecture)
        self.assertIn("一次性反应令牌", architecture)
        self.assertIn("准备、消费和演出必须由共享 resolver 串联", architecture)
        self.assertIn("其他反应家族和自然到期仍需独立运行时样本", architecture)

    def test_reaction_priority_multihit_and_counter_are_runtime_bound(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-reaction-priority-bindings-20260723.json",
            "`0x080763E0`",
            "只对非零命中结果",
            "首个有效 hit",
            "后续 hit",
            "`unit+0xD4=0x19`",
            "`unit+0xD5=0xAE`",
            "HP 从 `17→3`",
            "佐助 HP 保持 `134→134`",
            "递归反转 source/target",
            "不是动画层反伤",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("ReactionPreprocessor", architecture)
        self.assertIn("首个有效 hit 替换并截断后续 hit", architecture)
        self.assertIn("嵌套反向 `ActionResolution`", architecture)
        self.assertIn("反击不是额外 UI 分支", architecture)

    def test_base_damage_and_per_hit_success_formula_are_bound(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-damage-hit-bindings-20260723.json",
            "`0x080754A8`",
            "`0x08076034`",
            "`floor(power × floor(attack × attack_percent / 100) / 10)`",
            "`100 - 5 × isqrt(defense)`",
            "`(rng × 100) >> 15`",
            "两次普通命中和一次 miss",
            "候选值 `[9,13,11,16]`",
            "“6×3”不是最终伤害",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("四个伤害候选", architecture)
        self.assertIn("每个 hit 独立抽取一次 RNG", architecture)
        self.assertIn("UI 的攻击力与 hit 数不能相乘后直接扣 HP", architecture)
        self.assertNotIn("三次各 6 点", architecture)

    def test_status_duration_ticks_at_side_end_before_side_toggle(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-status-expiry-bindings-20260723.json",
            "`0x1100`",
            "`0x0806C308`",
            "单位槽 1–12",
            "16 个状态槽",
            "步长 8",
            "`unit+0xD4`",
            "`unit+0xD6`",
            "阵营交接前",
            "`1→0` 并移除",
            "`2→1` 且保留",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("状态持续时间 tick 属于 scheduler 的 side-end 边界", architecture)
        self.assertIn("先递减状态，再切换阵营", architecture)
        self.assertIn("一次性 reaction 消费与通用持续时间递减是两条独立规则", architecture)

    def test_status_storage_separates_active_state_from_removed_events(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-status-storage-bindings-20260723.json",
            "`unit+0xD4..+0x154` 的活动状态区",
            "`unit+0x154..+0x1D4` 的已移除状态事件区",
            "两区各含 16 条、步长 8 的完整记录",
            "只比较状态码低 6 位",
            "自然到期会在有空位时把完整记录复制到首个空闲已移除事件槽",
            "事件区已满时仍清活动码",
            "一次性反应消费会直接清除活动状态码",
            "状态码 `0x3F`",
            "只在旧 duration 非零且小于新 duration 时替换",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("ActiveStatusBank", architecture)
        self.assertIn("RemovedStatusEventBank", architecture)
        self.assertIn("表现层不得通过扫描活动状态自行推断到期动画", architecture)

    def test_status_consumer_inventory_prevents_reaction_only_model(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-status-consumer-bindings-20260723.json",
            "96 个直接状态查询引用",
            "21 个直接状态写入引用",
            "95 个立即数查询",
            "25 个不同状态 code",
            "blocker/reaction 只覆盖其中 12 个",
            "剩余 13 个",
            "`0x05/0x0D/0x0E/0x12/0x13/0x1B/0x1E/0x1F/0x20/0x21/0x22/0x23/0x24`",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("StatusBehaviorRegistry", architecture)
        self.assertIn("不能把状态系统缩减为 blocker/reaction 两张表", architecture)
        self.assertIn("13 个尚未分类 code", architecture)

    def test_status_0x0e_is_ordered_linked_resolution_not_redirection(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-status-linked-resolution-bindings-20260723.json",
            "状态 code `0x0E`",
            "状态记录 `+4`",
            "`0x08076B6C`",
            "相同 source、action type 和 amount",
            "附加参数 `[0,0,0,1]`",
            "先递归，再继续主目标 HP 分支",
            "传播而不是重定向",
            "可见玩法名称仍未闭合",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("LinkedResolution", architecture)
        self.assertIn("不得复制总伤害", architecture)
        self.assertIn("防递归 guard", architecture)

    def test_status_0x0d_consumption_is_a_resolver_queue_policy(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-status-participant-consumption-bindings-20260723.json",
            "状态 code `0x0D`",
            "event type 的低 6 位",
            "`0x04/0x09/0x0A/0x10/0x16/0x19`",
            "source 与 target",
            "mode 0",
            "target 的 `unit+0xC0`",
            "`0x00000100`",
            "可见玩法名称和该 bit 的业务名称仍未闭合",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("StatusConsumptionPolicy", architecture)
        self.assertIn("不得产生 removed-status event", architecture)
        self.assertIn("不能放到 side-end scheduler", architecture)

    def test_ai_event_scoring_has_a_status_policy_matrix(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-ai-status-policy-bindings-20260723.json",
            "`0x08084274..0x08085154`",
            "15 个状态查询",
            "`0x3F/0x3E/0x3D/0x0F/0x11`",
            "`0x1F/0x21/0x23`",
            "event `0x1E/0x20/0x22/0x24/0x26`",
            "同族状态",
            "event/status `0x12/0x12` 与 `0x0D/0x0D`",
            "不能据此声称完整目标优先级已经闭合",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("StatusAwareScorePolicy", architecture)
        self.assertIn("跳过该事件的分值贡献", architecture)
        self.assertIn("不能把状态过滤放到表现层", architecture)

    def test_status_0x13_modifies_hit_count_and_is_removed_after_resolution(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-status-hit-count-modifier-bindings-20260723.json",
            "effect type `0x14`",
            "状态 `0x13` 记录 `+6` 的低字节",
            "event `+0x12`",
            "模板 hit count 与共享 modifier accumulator 相加",
            "`0x08077470`",
            "mode 1",
            "产生 removed-status event",
            "没有检查 `0xFF`",
            "可见玩法名称仍未闭合",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("StatusDrivenHitCountModifier", architecture)
        self.assertIn("先解析、后移除", architecture)
        self.assertIn("构建期失败", architecture)

    def test_status_0x13_stage_is_shared_by_eight_gates_eligibility_and_ui(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-status-stage-policy-bindings-20260723.json",
            "动作 ID `43–49`",
            "第一　开门　开",
            "第五　杜门　开",
            "表莲华",
            "里莲华",
            "完整 `u16`",
            "状态不存在时才可选",
            "阶段严格等于 `1/2/3/4`",
            "阶段不高于 2",
            "阶段大于 2",
            "`0x08071152`",
            "同一个状态实例",
            "模板 byte `+4`",
            "阶段 `1–5`",
            "`0x08077532`",
            "`0x0807758A`",
            "替换旧的 `0x13`",
            "剩余 10 个",
            "原因码 `9–20` 的可见文案仍未闭合",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("EightGatesStage", architecture)
        self.assertIn("不得复制成 UI 阶段与战斗 buff 两份状态", architecture)
        self.assertIn("`ActionEligibilityPolicy`", architecture)
        self.assertIn("动作 43–47 的模板", architecture)
        self.assertIn("stage 1–5", architecture)

    def test_status_0x05_is_a_timed_identity_override_with_two_restore_paths(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        roadmap = (ROOT / "docs/sequel-roadmap.md").read_text(encoding="utf-8")
        readme = (ROOT / "tools/README.md").read_text(encoding="utf-8")
        for required in (
            "battle-status-transformation-bindings-20260723.json",
            "动作 ID `4`“变化术”",
            "只覆盖 source 的 character ID",
            "不会复制完整单位记录",
            "状态记录 `+4`",
            "target unit slot",
            "原始角色 ID `unit+0xBC`",
            "refresh mode 8",
            "refresh mode 0",
            "cleanup event type `0x0B`",
            "`0x0806C5A6`",
            "先复制到 removed-event bank，再恢复原始身份",
            "剩余 9 个",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("IdentityOverrideStatus", architecture)
        self.assertIn("不是表现层临时换 sprite", architecture)
        self.assertIn("必须同时覆盖 cleanup 与自然到期", architecture)
        self.assertIn("battle-status-transformation-bindings-20260723.json", roadmap)
        self.assertIn("remaining 9", readme)

    def test_attribute_status_family_is_an_ordered_recompute_pipeline(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        roadmap = (ROOT / "docs/sequel-roadmap.md").read_text(encoding="utf-8")
        readme = (ROOT / "tools/README.md").read_text(encoding="utf-8")
        for required in (
            "battle-status-attribute-modifier-bindings-20260723.json",
            "`0x0806D1EC`",
            "原始角色 ID `unit+0xBC`",
            "16 个活动状态槽",
            "记录 `+6` 的完整 `u16`",
            "按槽位 0→15 顺序",
            "`0x12/0x1E` 增加攻击",
            "`0x1F` 降低攻击",
            "`0x20/0x21` 增减防御",
            "`0x22/0x23` 增减敏捷",
            "`0x24/0x25` 增减移动",
            "`0x1B` 增加最大 HP",
            "攻击/防御/敏捷上限 99",
            "移动上限 9",
            "最大 HP 上限 999",
            "effect `0x26`",
            "`0x1E/0x20/0x22/0x1B`",
            "当前 HP 增加正的最大 HP 差值",
            "`0x0807367C → 0x08073680 → 0x08073684`",
            "duration 0 不递减",
            "剩余 0 个 code-specific 操作链",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("OrderedAttributeModifier", architecture)
        self.assertIn("不能在应用时永久改写基础属性", architecture)
        self.assertIn("按活动状态槽顺序重算", architecture)
        self.assertIn("battle-status-attribute-modifier-bindings-20260723.json", roadmap)
        self.assertIn("remaining 0 operational codes", readme)

    def test_critical_and_ignore_defense_probability_gates_are_runtime_bound(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-hit-modifier-bindings-20260723.json",
            "被动类型 `0x0C`",
            "`min(100, passive_value + 10)`",
            "被动类型 `0x19`",
            "命中 → 会心 → 无视防御",
            "`[2,2,2]`",
            "HP `49→10`",
            "`[5,5,5]`",
            "HP `49→16`",
            "只改一个被动等级字节",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("每个 hit 的 RNG 顺序固定为基础命中、可选会心、可选无视防御", architecture)
        self.assertIn("flag 2 选择会心候选", architecture)
        self.assertIn("OR 4 选择无视防御候选", architecture)

    def test_reaction_staging_is_cross_checked_across_resolution_samples(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-reaction-matrix-bindings-20260723.json",
            "29 个",
            "18 次普通伤害",
            "11 次替身",
            "`unit+0x154=0`",
            "`unit+0x154=22`",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("29 个哈希绑定解析边界", architecture)
        self.assertIn("不是全局反应枚举", architecture)

    def test_ai_planner_static_score_shape_is_hash_bound_without_overclaiming(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-ai-planner-static-20260723.json",
            "0x080851F8..0x080855FE",
            "candidate_score > best_score",
            "面向相同加 50",
            "地形标记分支加 200 或 100",
            "(rng_value * 50) >> 15",
            "仍未闭合目标优先级、伤害效用和任务目标权重",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("AI 不是脚本坐标播放器", architecture)
        self.assertIn("候选生成 → 合法性过滤 → 评分 → 严格择优", architecture)

    def test_ai_target_and_utility_policy_is_data_driven_and_hash_bound(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        roadmap = (ROOT / "docs/sequel-roadmap.md").read_text(encoding="utf-8")
        readme = (ROOT / "tools/README.md").read_text(encoding="utf-8")
        for required in (
            "battle-ai-utility-policy-bindings-20260723.json",
            "`0x0808400C..0x08084266`",
            "同阵营和异阵营各 7 个目标槽",
            "当前 HP 比例、最大 HP、攻击、防御、敏捷、移动、地图距离",
            "单位槽 1→12",
            "严格更小",
            "首次扫描到的单位",
            "`[1700,800,800,1300,1000,800,3600]`",
            "`[4200,2000,1000,1000,1000,800,0]`",
            "event `0x01/0x14/0x15`",
            "先按目标聚合多段预计伤害",
            "6000/900/3000/100",
            "`0x0853F348`",
            "8×0xA8",
            "4 个、步长 8",
            "kind 1–5",
            "`(rng_value×10)>>15`",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("AiTargetIndex", architecture)
        self.assertIn("AiUtilityScorer", architecture)
        self.assertIn("AiScenarioRule", architecture)
        self.assertIn("不能压缩成“最近敌人”", architecture)
        self.assertIn("battle-ai-utility-policy-bindings-20260723.json", roadmap)
        self.assertIn("seven target selectors", readme)

    def test_action_templates_bind_cost_target_effect_and_dispatch_as_orthogonal_policies(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        roadmap = (ROOT / "docs/sequel-roadmap.md").read_text(encoding="utf-8")
        readme = (ROOT / "tools/README.md").read_text(encoding="utf-8")
        for required in (
            "battle-action-template-semantics-bindings-20260723.json",
            "`+0` 是成本通道",
            "`+1` 是显示/动画族",
            "`+2` 低 6 位是效果代码",
            "`+3` 低 3 位是目标策略",
            "当前查克拉、当前 HP、无标量资源特殊动作、战斗内忍具槽",
            "自己/隐式行动者、友军、敌军、任意占用单位、空格",
            "`0x08076F44`",
            "63 项",
            "87 条主动动作",
            "94 条忍具",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        for required in (
            "CostPolicy",
            "EffectDescriptor",
            "TargetPolicy",
            "RangeShape",
            "UpgradeRule",
            "三个正交策略",
            "数据驱动 resolver registry",
        ):
            with self.subTest(required=required):
                self.assertIn(required, architecture)
        self.assertIn("battle-action-template-semantics-bindings-20260723.json", roadmap)
        self.assertIn("analyze_battle_action_template_semantics.py", readme)

    def test_butano_battle_now_consumes_generated_domain_content_not_fixed_damage(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        roadmap = (ROOT / "docs/sequel-roadmap.md").read_text(encoding="utf-8")
        readme = (ROOT / "tools/README.md").read_text(encoding="utf-8")
        for required in (
            "固定 80 伤害已移除",
            "角色 1",
            "角色 30",
            "HP 10",
            "同一个 `battle_action_resolver`",
            "敌方接近后会实际扣除鸣人 HP",
            "16+16",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("领域实现状态", architecture)
        self.assertIn("87+94", architecture)
        self.assertIn("63×(15+24)", architecture)
        self.assertIn("generate_butano_battle_action_content.py", roadmap)
        self.assertIn("generate_butano_battle_unit_content.py", roadmap)
        self.assertIn("generate_butano_battle_action_content.py", readme)
        self.assertIn("generate_butano_battle_unit_content.py", readme)

    def test_condition_interpreter_preserves_ordered_predicate_slots(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "battle-condition-interpreter-bindings-20260723.json",
            "0x080777FC",
            "47 场",
            "battle_id×0xCC + variant×0x44",
            "4 条胜利谓词和 4 条失败谓词，每条 8 字节",
            "跳转表支持 type 1–9",
            "实际条件表使用 type 1、2、3、6、7、8、9",
            "battle 9",
            "type 1/affiliation 1",
            "battle 15",
            "character 30",
            "较小的首个命中槽位",
            "相同槽位返回结果 5",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("保留四个有序胜利槽和四个有序失败槽", architecture)
        self.assertIn("相同首个命中槽位必须产生独立结果 5", architecture)
        self.assertNotIn("失败优先级和胜利优先级由关卡定义明确", architecture)

    def test_condition_interpreter_closes_every_record_used_handler_operationally(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "type 2 在完整回合边界检查非零回合上限",
            "`0x0202680A == 0x0202680C`",
            "32 个、步长 `0x10` 的战场对象槽",
            "type 6 检查 `arg0 + 1` 对象槽的 type 字节是否为零",
            "`0x08081024` 分配、由 `0x08081084` 释放",
            "type 7 比较双方当前 HP 总和",
            "type 8 比较双方有效单位数",
            "对象 behavior 9",
            "按结算单位 affiliation",
            "`0x02026BC0 + side`",
            "对象 behavior 的可见玩法名称仍未闭合",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("回合上限到达时按 type 2/7/8/9 的原始运算求值", architecture)
        self.assertIn("BattlefieldObjectTable", architecture)
        self.assertIn("不能把 behavior 9 擅自命名为击杀分或占点分", architecture)

    def test_equal_slot_result_has_a_distinct_ending_presentation(self):
        evidence = RESTORATION_EVIDENCE.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        for required in (
            "`0x0807305C..0x080731D0`",
            "结果 1/2/5 分别调用 `0x08072EDC(1/2/3)`",
            "结果 5 仍结束战斗",
            "没有把 presentation ID 3 猜成“平局”",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)
        self.assertIn("结果 5 进入独立的 presentation ID 3 并结束战斗", architecture)


if __name__ == "__main__":
    unittest.main()
