import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "docs" / "butano-local-reference.md"
COST_REPORT = ROOT / "docs" / "butano-konoha-systems-cost.md"
BATTLE_GUIDE = ROOT / "docs" / "butano-scenario-41-battle.md"
RUNTIME_NOTE = ROOT / "notes" / "butano-scenario-41-runtime-20260721.md"
ONE_TO_ONE_NOTE = ROOT / "notes" / "butano-scenario-41-one-to-one-runtime-20260722.md"
BATTLE_AUDIO_RUNTIME = (
    ROOT
    / "notes"
    / "butano-battle-audio-runtime-20260727.md"
)
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
DOMAIN_REWRITE = ROOT / "notes" / "butano-battle-domain-rewrite-20260723.md"
ROADMAP = ROOT / "docs" / "sequel-roadmap.md"
TOOLS_README = ROOT / "tools" / "README.md"
SHARED_RUNTIME_PLAN = (
    ROOT
    / "docs"
    / "superpowers"
    / "plans"
    / "2026-07-24-butano-shared-encounter-runtime.md"
)
GENERIC_SCENE_DESIGN = (
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-07-25-butano-generic-visible-battle-scene-design.md"
)
GENERIC_SCENE_PLAN = (
    ROOT
    / "docs"
    / "superpowers"
    / "plans"
    / "2026-07-25-butano-generic-visible-battle-scene.md"
)
CHARACTER_ACTION_DESIGN = (
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-07-25-butano-character-action-architecture-design.md"
)
CHARACTER_ACTION_PLAN = (
    ROOT
    / "docs"
    / "superpowers"
    / "plans"
    / "2026-07-25-butano-character-action-architecture.md"
)
UNIT_ANIMATION_DESIGN = (
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-07-25-butano-battle-unit-animation-design.md"
)
UNIT_ANIMATION_PLAN = (
    ROOT
    / "docs"
    / "superpowers"
    / "plans"
    / "2026-07-25-butano-battle-unit-animation.md"
)
ACTION_IDENTITY_PLAN = (
    ROOT
    / "docs"
    / "superpowers"
    / "plans"
    / "2026-07-25-butano-complete-action-identities.md"
)
AI_CANDIDATE_SCORE_PLAN = (
    ROOT
    / "docs"
    / "superpowers"
    / "plans"
    / "2026-07-25-butano-ai-candidate-score.md"
)
AI_CANDIDATE_FIELD_RUNTIME = (
    ROOT
    / "notes"
    / "battle-ai-candidate-field-runtime-20260725.json"
)


class ButanoResearchDocsTest(unittest.TestCase):
    def test_battle_audio_is_event_driven_and_non_muted_verified(self):
        self.assertTrue(
            BATTLE_AUDIO_RUNTIME.is_file(),
            "战斗音频运行证据缺失",
        )
        text = BATTLE_AUDIO_RUNTIME.read_text(encoding="utf-8")
        for required in (
            "battle_audio_director",
            "battle_audio_event",
            "6500",
            "518/518",
            "0x0201FBC4",
            "b969b6eaa2cce74909d43a6fbd5d965d077d432b3803eb141e788afe27bbc87f",
            "c6cc5a62493933d818fd64ad6889fe99c817b76f3eaed96670b1f90284befd25",
            "0.001234%",
            "不是 mGBA 前端",
            "功能边界",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

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
            "96 帧组件姿态流",
            "运行时不再链接",
            "44 张关键截图",
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
            "condition 进入结果态",
            "不是四回合黄金路线",
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

    def test_rom_map_runtime_replaces_screenshot_obstacles_with_shared_content(self):
        guide = BATTLE_GUIDE.read_text(encoding="utf-8")
        domain = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")
        tools = TOOLS_README.read_text(encoding="utf-8")

        for required in (
            "generated_battle_map_content.h",
            "0xF",
            "1/3/7",
            "ROM tile",
            "scenario 43",
        ):
            with self.subTest(document="guide", required=required):
                self.assertIn(required, guide)
        for required in (
            "battle_map_loader",
            "12151",
            "不再从截图",
            "部分属性",
        ):
            with self.subTest(document="domain", required=required):
                self.assertIn(required, domain)
        for required in (
            "52 个宿主 C++",
            "674fce2a9f51577c758ecb1720f6cdf5a7df92bcb83995f038e0df296b762709",
            "butano-map-runtime-20260724-2216",
        ):
            with self.subTest(document="roadmap", required=required):
                self.assertIn(required, roadmap)
        for required in (
            "analyze_battle_map_collision.py",
            "generate_butano_battle_map_content.py",
        ):
            with self.subTest(document="tools", required=required):
                self.assertIn(required, tools)

    def test_shared_encounter_runtime_and_visible_scenario_43_are_durable(self):
        plan = SHARED_RUNTIME_PLAN.read_text(encoding="utf-8")
        guide = BATTLE_GUIDE.read_text(encoding="utf-8")
        domain = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")

        for required in (
            "battle_encounter_runtime",
            "battle_scene_controller",
            "battle_scene_presentation",
            "- [x] Add a failing host test loading scenario 41 and 43",
            "- [x] Run guarded mGBA acceptance",
        ):
            with self.subTest(document="plan", required=required):
                self.assertIn(required, plan)
        for required in (
            "scenario 41 共享战场按 SELECT",
            "影分身",
            "AI DONE",
            "ROUND 2 PLAYER",
            "动态单位 sprite",
        ):
            with self.subTest(document="guide", required=required):
                self.assertIn(required, guide)
        for required in (
            "artifacts/butano-shared-runtime-scenario43-20260724-17/",
            "artifacts/butano-shared-runtime-scenario41-20260724-02/",
            "0x2CE4",
            "0x0AE8",
            "0x030063C4",
            "EWRAM",
            "55 个宿主 C++",
        ):
            with self.subTest(document="domain", required=required):
                self.assertIn(required, domain)
        for required in (
            "8085dffcd7df4aeae0d6b07a31d27885f5f0f292ac4a67510596f95594e7aa5c",
            "scenario 43 可见运行闭环",
            "自动路线静音",
        ):
            with self.subTest(document="roadmap", required=required):
                self.assertIn(required, roadmap)

    def test_generic_visible_scene_and_multi_unit_runtime_are_durable(self):
        design = GENERIC_SCENE_DESIGN.read_text(encoding="utf-8")
        plan = GENERIC_SCENE_PLAN.read_text(encoding="utf-8")
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        guide = BATTLE_GUIDE.read_text(encoding="utf-8")
        domain = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")
        tools = TOOLS_README.read_text(encoding="utf-8")

        for required in (
            "battle row 9",
            "3v5",
            "`pathfinder_workspace`",
            "8,704 字节",
            "128 个 OAM sprite",
            "96 字节",
            "presentation_busy",
        ):
            with self.subTest(document="design", required=required):
                self.assertIn(required, design)
        self.assertNotIn("- [ ]", plan)
        self.assertIn("- [x] **Step 5: Persist evidence and run final suites**", plan)
        for required in (
            "`battle_runtime_scene`",
            "row 41、43、9",
            "状态驱动遥测",
        ):
            with self.subTest(document="architecture", required=required):
                self.assertIn(required, architecture)
        for required in (
            "SELECT: BATTLE 9",
            "3 名玩家",
            "5 名敌人",
            "artifacts/butano-unit-animation-b09-20260725-86/",
            "artifacts/butano-shared-s41-runtime-20260725-84/",
        ):
            with self.subTest(document="guide", required=required):
                self.assertIn(required, guide)
        for required in (
            "`__aeabi_memset4`",
            "8,704 字节",
            "OAM",
            "0x02012848",
        ):
            with self.subTest(document="domain", required=required):
                self.assertIn(required, domain)
        for required in (
            "57 个宿主 C++",
            "f207a593eed29633b46368ea5792c3085e8bbc737d86c87ab73cb49f726ffb2c",
            "butano-generic-scene-battle09-state-final-20260725-03",
            "butano-generic-scene-s43-final-20260725-05",
        ):
            with self.subTest(document="roadmap", required=required):
                self.assertIn(required, roadmap)
        for required in (
            "MGBA_B09_TELEMETRY_ADDRESS",
            "MGBA_S43_TELEMETRY_ADDRESS",
            "arm-none-eabi-nm",
            "presentation_busy",
        ):
            with self.subTest(document="tools", required=required):
                self.assertIn(required, tools)

    def test_character_identity_and_action_architecture_is_durable(self):
        design = CHARACTER_ACTION_DESIGN.read_text(encoding="utf-8")
        plan = CHARACTER_ACTION_PLAN.read_text(encoding="utf-8")
        domain = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")
        tools = TOOLS_README.read_text(encoding="utf-8")

        for required in (
            "63 个角色身份",
            "87 个主动技能身份",
            "`battle_action_menu_view`",
            "UI、遥测和测试都只消费 snapshot",
        ):
            with self.subTest(document="design", required=required):
                self.assertIn(required, design)
        self.assertNotIn("- [ ]", plan)
        for required in (
            "10 字节动作视图",
            "96 字节遥测",
            "IWRAM 栈溢出",
            "artifacts/butano-character-actions-b09-20260725-03/",
        ):
            with self.subTest(document="domain", required=required):
                self.assertIn(required, domain)
        for required in (
            "角色与技能可观察架构",
            "鸣人动作 2",
            "樱动作 1",
            "佐助 `[2,5,16]`",
            "42e0f29ad4ab05a9205e2d890ea34dd5575fc5c25f2278cdcc8616f2e7a79f64",
        ):
            with self.subTest(document="roadmap", required=required):
                self.assertIn(required, roadmap)
        for required in (
            "mgba_battle_09_character_actions.lua",
            "MGBA_B09_ACTION_TELEMETRY_ADDRESS",
            "last_resolved_action_id",
        ):
            with self.subTest(document="tools", required=required):
                self.assertIn(required, tools)

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

    def test_action_tail_runtime_records_real_transaction_boundaries(self):
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        domain = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")

        for required in (
            "Resolver 永不完成单位行动",
            "`EffectsResolved`",
            "目标判定抢占",
            "`FacingSelection`",
            "`DefenseSelection`",
        ):
            with self.subTest(document="architecture", required=required):
                self.assertIn(required, architecture)

        for required in (
            "`battle_turn_flow::after_effects`",
            "`battle_turn_flow::complete_defense`",
            "`ledger.completed` 仍为 `false`",
            "41 个宿主 C++",
        ):
            with self.subTest(document="domain", required=required):
                self.assertIn(required, domain)

        for required in (
            "两阶段行动提交",
            "防御准备只完成选择存储",
            "防御动作对后续来袭的完整反应消费仍未完成",
        ):
            with self.subTest(document="roadmap", required=required):
                self.assertIn(required, roadmap)

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
        for required in (
            "battle-resource-command-rule-bindings-20260724.json",
            "`unit+0x0A`（结印）",
            "HP 至少保留 1",
            "`floor(max_hp / 5)`",
            "预览无写入",
        ):
            with self.subTest(required=required):
                self.assertIn(required, architecture)

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

    def test_defense_preparation_runtime_is_a_domain_transaction(self):
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        implementation = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")
        for required in (
            "`battle_defense_preparation`",
            "主动术与忍具来源类型",
            "预览零写入",
            "状态槽容量",
            "0x10 只接受主动术",
            "0x19 只接受忍具",
            "`reaction_resolution_event`",
            "非相邻时不触发且不消费",
        ):
            with self.subTest(required=required):
                self.assertIn(required, architecture)
        for required in (
            "# 防御准备与来袭反应运行时（2026-07-24）",
            "写轮眼：跳过 miss",
            "火弹：只在相邻有效命中",
            "第二次攻击恢复正常伤害",
            "表现层不参与扣血",
        ):
            with self.subTest(required=required):
                self.assertIn(required, implementation)
        self.assertIn("防御准备已从账本占位升级为领域事务", roadmap)
        self.assertIn("0x04/0x09/0x0A/0x16/0x22", roadmap)

    def test_defense_browser_is_generated_from_unit_runtime_content(self):
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        implementation = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")
        for required in (
            "`battle_defense_browser`",
            "角色实例等级",
            "15 个主动动作槽",
            "9 个本场忍具槽",
            "进攻术仍可浏览",
            "场景 facade 只保存菜单游标",
        ):
            with self.subTest(required=required):
                self.assertIn(required, architecture)
        for required in (
            "# 数据驱动防御动作浏览器与可见接线（2026-07-24）",
            "等级 14 的角色 2",
            "默认“不使用”",
            "预制三层 BG",
            "不再拥有 HP、命中、成本或胜负的写权限",
        ):
            with self.subTest(required=required):
                self.assertIn(required, implementation)
        self.assertIn("防御浏览器已改为内容驱动", roadmap)

    def test_action_catalog_execution_and_fixed_unit_pool_are_documented(self):
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        implementation = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")
        for required in (
            "`battle_action_catalog`",
            "`battle_action_execution`",
            "固定 12 个单位槽",
            "inactive reserve",
            "preview 零写",
            "scenario 43",
        ):
            with self.subTest(required=required):
                self.assertIn(required, architecture)
        for required in (
            "# 通用动作目录、固定单位池与影分身执行（2026-07-24）",
            "八个空记录",
            "槽 5",
            "查克拉 5→2",
            "不是可见关卡验收",
        ):
            with self.subTest(required=required):
                self.assertIn(required, implementation)
        self.assertIn(
            "动作目录与防御目录不再各自重建技能列表",
            roadmap,
        )

    def test_player_action_flow_replaces_scenario_side_player_submission(self):
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        implementation = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")
        for required in (
            "`battle_player_action_flow`",
            "action access policy",
            "modal phase",
            "目标 preview",
            "session 副本",
            "scenario facade 不再",
        ):
            with self.subTest(required=required):
                self.assertIn(required, architecture)
        for required in (
            "# 通用玩家行动 Flow 与 scenario 适配（2026-07-24）",
            "完整目录仍有 3 项",
            "教学列表只有 action 7",
            "scenario 41",
            "玩家侧 resolver",
        ):
            with self.subTest(required=required):
                self.assertIn(required, implementation)
        self.assertIn(
            "玩家侧 action→target→facing→defense",
            roadmap,
        )

    def test_ai_turn_flow_replaces_scenario_side_enemy_submission(self):
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        implementation = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")
        for required in (
            "`battle_ai_turn_flow`",
            "`BattleSession` 和 RNG 副本",
            "主动技能/忍具来源",
            "scenario facade 不再",
            "AI 防御",
        ):
            with self.subTest(required=required):
                self.assertIn(required, architecture)
        for required in (
            "# 通用 AI 单位回合 Flow（2026-07-24）",
            "scenario 43",
            "忍具槽 2",
            "48 个宿主 C++",
            "80 项定向 Python",
            "684b5f67578a5b0de40a181f94a18079408becf24e91fb9cb682b630415f171b",
        ):
            with self.subTest(required=required):
                self.assertIn(required, implementation)
        for required in (
            "敌方单位 action→target→facing→complete",
            "`battle_ai_turn_flow`",
            "40d848752d13dbc3c78ead6e571a2af94f6f2a84446e788e457f36b1c7aa1b1f",
        ):
            with self.subTest(required=required):
                self.assertIn(required, roadmap)

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
            "0x080833A8..0x08083AEA",
            "0x080851F8..0x080855FE",
            "candidate_score > best_score",
            "面向相同加 50",
            "动态候选场 `0x02002880`",
            "无威胁加 200",
            "当前面向方向没有来源加 100",
            "(rng_value * 50) >> 15",
            "helper mode `0/2/4/6` 的全部差异",
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

    def test_battle_scenario_content_is_generated_from_all_47_map_formations(self):
        architecture = BATTLE_ARCHITECTURE.read_text(encoding="utf-8")
        rewrite = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")
        readme = TOOLS_README.read_text(encoding="utf-8")

        for required in (
            "BattleScenarioDefinition",
            "47 场 × 3 variant × 12 槽",
            "0x5461C4 + battle_id×0x1AAC + variant×0x08E4 + 4 + record×0xB8",
            "`0xFA..0xFF`",
            "场景、编队与条件 ID 不得假定恒等",
        ):
            with self.subTest(required=required):
                self.assertIn(required, architecture)

        for required in (
            "battle 15",
            "9 个单位",
            "角色 30",
            "`(4,5)`",
            "不可发出玩家命令",
            "护送对象死亡后返回 loss",
            "scenario 41",
            "generated_battle_scenario_content.h",
            "476 条启用记录",
            "329 条固定角色记录",
            "147 条部署占位记录",
            "a8e224f9ac3c243707e33706ef2cf2042cb2a13cd8607207622f55cc78d0f367",
            "1e9d2822e486c6e79c9ad4f1545915fa378505dd1b58e840f939fd1032fd55e9",
            "39 个宿主 C++ 测试程序",
            "68 项通过、1 项按集成开关跳过",
            "07ea2e47d4b878078fa107cf1300dd77c12a52e9d9e0b7d9ad7852f669cc2f6a",
            "artifacts/butano-scenario-runtime-20260724-1830/",
            "3a6af7bfc98ca681fcbbf1a0702e9ecbe13bc2aa959b07507c7f6a573f38822c",
        ):
            with self.subTest(required=required):
                self.assertIn(required, rewrite)

        self.assertIn("generate_butano_battle_scenario_content.py", roadmap)
        self.assertIn("47 场地图与编队不等于 47 场可游玩", roadmap)
        self.assertIn("generate_butano_battle_scenario_content.py", readme)
        self.assertIn("部署占位符必须由关卡策略显式绑定", readme)

    def test_dynamic_deployment_and_empty_tile_map_gate_are_durable(
        self,
    ):
        architecture = BATTLE_ARCHITECTURE.read_text(
            encoding="utf-8"
        )
        rewrite = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")
        readme = TOOLS_README.read_text(encoding="utf-8")

        for required in (
            "battle_runtime_scene_request",
            "deployment_required",
            "不得自行给 `0xFA..0xFF` 填默认角色",
            "empty-tile",
            "grid_fully_closed",
        ):
            with self.subTest(required=required):
                self.assertIn(required, architecture)
        for required in (
            "artifacts/butano-dynamic-deployment-b32-20260725-57/",
            "`(12,13)`",
            "occupancy",
            "[1,2,3,35,35,35]",
            "fixture",
        ):
            with self.subTest(required=required):
                self.assertIn(required, rewrite)
        self.assertIn("battle_runtime_scene_request", roadmap)
        self.assertIn(
            "mgba_battle_32_dynamic_deployment.lua",
            readme,
        )

    def test_battle_unit_visual_catalog_is_durable(self):
        architecture = BATTLE_ARCHITECTURE.read_text(
            encoding="utf-8"
        )
        rewrite = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")
        readme = TOOLS_README.read_text(encoding="utf-8")
        resource_locations = (
            ROOT / "notes" / "resource-locations.md"
        ).read_text(encoding="utf-8")

        for required in (
            "`0x596D5C`",
            "62 个角色 × 9 个视觉槽",
            "342 个有效槽",
            "216 个空槽",
            "character_id",
            "inactive",
            "optional sprite",
        ):
            with self.subTest(required=required):
                self.assertIn(required, architecture)
        for required in (
            "generated_battle_unit_visual_content.h",
            "artifacts/butano-unit-visual-b32-final-20260725-66/",
            "鸣人、佐助、小樱和角色 35",
            "空槽",
            "召唤",
        ):
            with self.subTest(required=required):
                self.assertIn(required, rewrite)
        self.assertIn(
            "generate_butano_battle_unit_visual_content.py",
            roadmap,
        )
        self.assertIn(
            "generate_butano_battle_unit_visual_content.py",
            readme,
        )
        self.assertIn(
            "558 rows",
            resource_locations,
        )
        self.assertIn(
            "旧 312-row 地图 tile 解释已撤销",
            resource_locations,
        )

    def test_full_unit_animation_and_shared_s41_runtime_are_durable(self):
        design = UNIT_ANIMATION_DESIGN.read_text(
            encoding="utf-8"
        )
        plan = UNIT_ANIMATION_PLAN.read_text(
            encoding="utf-8"
        )
        guide = BATTLE_GUIDE.read_text(encoding="utf-8")
        rewrite = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")
        readme = TOOLS_README.read_text(encoding="utf-8")

        for required in (
            "534 个 shape-specialized sprite 资产",
            "最多 8 个资源项",
            "所有受影响单位 ID",
            "近战突进",
            "结印/忍具原地",
        ):
            with self.subTest(document="design", required=required):
                self.assertIn(required, design)
        self.assertNotIn("- [ ]", plan)
        for required in (
            "`run_battle_41_scene()`",
            "`battle_runtime_scene`",
            "不是四回合黄金路线",
            "artifacts/butano-shared-s41-runtime-20260725-84/",
        ):
            with self.subTest(document="guide", required=required):
                self.assertIn(required, guide)
        for required in (
            "534 个 shape-specialized",
            "`affected_unit_ids`",
            "butano-shared-s41-runtime-20260725-84",
        ):
            with self.subTest(document="rewrite", required=required):
                self.assertIn(required, rewrite)
        self.assertIn("完整角色逐帧动画目录", roadmap)
        self.assertIn(
            "mgba_battle_41_shared_runtime.lua",
            readme,
        )

    def test_resolved_hit_count_drives_presentation_timing(self):
        design = UNIT_ANIMATION_DESIGN.read_text(
            encoding="utf-8"
        )
        architecture = BATTLE_ARCHITECTURE.read_text(
            encoding="utf-8"
        )
        rewrite = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")

        for required in (
            "`resolved.generated_hits`",
            "`impact_count`",
            "0、1、2 或更多次",
        ):
            with self.subTest(document="design", required=required):
                self.assertIn(required, design)
        for required in (
            "表现层不得固定伪造三次命中",
            "`impact_count`",
        ):
            with self.subTest(
                    document="architecture",
                    required=required):
                self.assertIn(required, architecture)
        for required in (
            "领域已提交的实际 hit 数",
            "`total_frame_count(impact_count)`",
        ):
            with self.subTest(document="rewrite", required=required):
                self.assertIn(required, rewrite)
        self.assertIn("命中次数驱动表现时长", roadmap)
        self.assertIn(
            "butano-resolved-impact-s41-20260725-93",
            rewrite,
        )
        self.assertIn(
            "butano-resolved-impact-b09-20260725-94",
            design,
        )
        self.assertIn(
            "23ec3ecfec4b50c14605318983fa86823aeda85baf87e80d7ace48411cad6a02",
            roadmap,
        )

    def test_complete_action_identity_and_equipment_flow_are_durable(self):
        architecture = BATTLE_ARCHITECTURE.read_text(
            encoding="utf-8"
        )
        rewrite = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")
        plan = ACTION_IDENTITY_PLAN.read_text(encoding="utf-8")

        for required in (
            "动作身份与本场装备边界",
            "94 条忍具身份",
            "`character_equipped_tools`",
            "身份不参与 resolver",
            "`guide_address_correlated`",
            "章节背包数量",
            "消费回写",
            "battle-campaign-tool-writeback-runtime-20260726.md",
        ):
            with self.subTest(document="architecture", required=required):
                self.assertIn(required, architecture)
        for required in (
            "butano-complete-action-identities-b09-20260725-01",
            "`kind=1`、`tool_slot=0`、`id=1`",
            "十字手里剑",
            "a08eb07626563df9a1506afd0bcfcd60fa0d0ec3ef815d2b00fa50cbab04f6fc",
        ):
            with self.subTest(document="rewrite", required=required):
                self.assertIn(required, rewrite)
        self.assertIn("94 条忍具身份目录", roadmap)
        self.assertIn(
            "butano-complete-action-identities-b09-20260725-01",
            roadmap,
        )
        self.assertNotIn("\n- [ ] **", plan)

    def test_ai_candidate_facing_and_tile_score_are_durable(self):
        architecture = BATTLE_ARCHITECTURE.read_text(
            encoding="utf-8"
        )
        evidence = RESTORATION_EVIDENCE.read_text(
            encoding="utf-8"
        )
        roadmap = ROADMAP.read_text(encoding="utf-8")
        plan = AI_CANDIDATE_SCORE_PLAN.read_text(
            encoding="utf-8"
        )
        runtime = json.loads(
            AI_CANDIDATE_FIELD_RUNTIME.read_text(
                encoding="utf-8"
            )
        )

        for required in (
            "`AiCandidate` 保存候选朝向",
            "站位内动作择优",
            "站位间候选场择优",
            "`score_tile`",
            "`plan.facing`",
            "`battle_ai_candidate_field_builder`",
            "不是 `grid_map::flags`",
        ):
            with self.subTest(
                document="architecture",
                required=required,
            ):
                self.assertIn(required, architecture)
        for required in (
            "butano-ai-candidate-score-host-all-20260725-241",
            "butano-ai-candidate-score-b09-20260725-01",
            "battle-ai-candidate-field-runtime-20260725-264",
            "`0x08085590`",
            "`0x11/0x81/0xF1/0x21/0x41`",
            "严格更高",
            "0–49",
            "两层候选择优",
        ):
            with self.subTest(
                document="evidence",
                required=required,
            ):
                self.assertIn(required, evidence)
        self.assertIn(
            "AI 动态候选场与朝向评分",
            roadmap,
        )
        self.assertNotIn("`0x0201BE2A` 地形标记", evidence)
        self.assertEqual(runtime["breakpoint"], "0x08085590")
        self.assertEqual(runtime["map"], {"width": 9, "height": 22})
        self.assertEqual(
            runtime["key_cells"],
            {
                "4,6": "0x11",
                "1,10": "0x81",
                "4,10": "0xF1",
                "7,10": "0x21",
                "4,14": "0x41",
            },
        )
        self.assertNotIn("\n- [ ] **", plan)

    def test_side_start_passive_architecture_and_boundary_are_durable(self):
        architecture = BATTLE_ARCHITECTURE.read_text(
            encoding="utf-8"
        )
        rewrite = DOMAIN_REWRITE.read_text(
            encoding="utf-8"
        )
        roadmap = ROADMAP.read_text(encoding="utf-8")
        tools = TOOLS_README.read_text(encoding="utf-8")
        manifest = json.loads(
            (
                ROOT
                / "notes/battle-side-start-passive-bindings-20260725.json"
            ).read_text(encoding="utf-8")
        )

        for required in (
            "SideStartPassiveSystem",
            "阵营开始领域事件",
            "共享锁存",
            "0x1D → 0x1E → 0x1F → 0x20",
            "`0x20` / passive 35 现按已闭合的机械契约实现",
            "表现 FIFO",
        ):
            with self.subTest(
                document="architecture",
                required=required,
            ):
                self.assertIn(required, architecture)
        for document in (rewrite, roadmap):
            self.assertIn(
                "battle-side-start-passive-bindings-20260725.json",
                document,
            )
            self.assertIn("0x1D–0x1F", document)
        self.assertIn(
            "analyze_battle_side_start_passives.py",
            tools,
        )
        self.assertEqual(
            manifest["families"]["0x20"][
                "implementation_status"
            ],
            "withheld_pending_semantics",
        )

    def test_all_scenario_first_round_matrix_and_projected_actor_fix_are_durable(
        self,
    ):
        architecture = BATTLE_ARCHITECTURE.read_text(
            encoding="utf-8"
        )
        rewrite = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")

        for document in (architecture, rewrite, roadmap):
            self.assertIn("85 个非空变体首轮换边矩阵", document)
            self.assertIn("battle 10 variant 2", document)
            self.assertIn("移动后的自己", document)
            self.assertIn("invalid_target", document)
        self.assertIn(
            "test_battle_all_scenario_runtime.cpp",
            rewrite,
        )
        self.assertIn("只读 preview", architecture)

    def test_two_component_action_architecture_and_original_ui_flow_are_durable(
        self,
    ):
        architecture = BATTLE_ARCHITECTURE.read_text(
            encoding="utf-8"
        )
        rewrite = DOMAIN_REWRITE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")
        tools = TOOLS_README.read_text(encoding="utf-8")
        player_flow = (
            ROOT
            / "notes/battle-action-combination-player-flow-20260725.md"
        ).read_text(encoding="utf-8")
        manifest = json.loads(
            (
                ROOT
                / "notes/battle-action-combination-bindings-20260725.json"
            ).read_text(encoding="utf-8")
        )

        for required in (
            "0x0853DFB0",
            "组合确认",
            "第一组件",
            "未命中配方",
            "BattleSession",
            "battle-action-combination-bindings-20260725.json",
        ):
            with self.subTest(required=required):
                self.assertIn(required, architecture)
        for document in (rewrite, roadmap, player_flow):
            self.assertIn("多重影分身", document)
            self.assertIn("火遁术", document)
            self.assertIn(
                "battle-action-combination-bindings-20260725.json",
                document,
            )
        self.assertIn(
            "analyze_battle_action_combinations.py",
            tools,
        )
        self.assertEqual(manifest["component_count_gate"], 2)
        self.assertEqual(
            manifest["unmatched_pair_behavior"],
            "preserve both selected components and initialize both action events",
        )

    def test_status_action_compliance_scope_and_boundaries_are_durable(
        self,
    ):
        architecture = BATTLE_ARCHITECTURE.read_text(
            encoding="utf-8"
        )
        roadmap = ROADMAP.read_text(encoding="utf-8")
        note = (
            ROOT
            / "notes/battle-status-action-compliance-20260726.md"
        ).read_text(encoding="utf-8")
        compliance_test = (
            ROOT
            / "butano-sequel/game/tests"
            / "test_battle_status_action_compliance.cpp"
        ).read_text(encoding="utf-8")

        for document in (architecture, roadmap, note):
            self.assertIn("33", document)
            self.assertIn("`0x26`", document)
        for document in (architecture, roadmap):
            self.assertIn(
                "battle-status-action-compliance-20260726.md",
                document,
            )
        self.assertIn(
            "std::array<status_action_expectation, 33>",
            compliance_test,
        )
        self.assertIn(
            "assert_expiry(",
            compliance_test,
        )
        self.assertIn(
            "动作 20、39、40、52",
            note,
        )
        self.assertIn(
            "不能为了达到 87/87 数字给全零模板捏造效果",
            note,
        )


if __name__ == "__main__":
    unittest.main()
