# Butano ↔ 逆向成果差异的二次核验（2026-10-20）

本文记录对会话 `mvs_c578650a3b6a4437907dc84f66aa5212` 执行
`docs/butano-reverse-gap-roadmap.md` 的**独立二次核验**。核验方法是不采信对方
自述，全部指标由本机脚本重跑得到。

工具：`tools/measure_butano_reverse_gap.py`（10 项测试全绿）
核验输出：`build/butano-reverse-gap-check-20261020/gap.{json,md}`

---

## 1. 核验方法

1. 不接受"文档说改好了"作为通过；每个里程碑都要求**可复跑的验收命令**。
2. 测量**同口径**：固定索引（`artifacts/reverse-results-index-v1/index.json`，
   SHA-256 `8c59f3520edd55e7…`），只让工作树变化。
3. **排除自指**（本轮发现并修复，见 §3）：报告与 roadmap 会提到所有缺口族，
   若把它们算作引用，写报告本身就会"改善"测量。
4. 导入类里程碑要求**跑独立 verify**，而不是看脚本存在。

---

## 2. 核验结论：roadmap 执行是真实的

### 2.1 量化对比（同口径，去自指）

| 指标 | 基线 02:24 | 核验 02:58 | 判定 |
| --- | ---: | ---: | --- |
| 索引条目 | 2,186 | 2,190 | +4（逆向树新增 2 工具 + 2 测试：`extract_battle_controller_states`） |
| 成果族 `build` | 33（12.6%） | **88（33.6%）** | ✅ 真实 |
| 成果族 `doc` | 211 | 161 | 随 55 族转入 `build` |
| 成果族 `none` | 15 | **10** | ✅ 真实（10 个全是 `precoverage` 中间产物） |
| 真正未触及的最终成果 | **5** | **0** | ✅ 真实 |
| 台账 `missing` | 5 | **0** | ✅ 真实 |
| notes `none` | 213 | 213 | ❌ M5 未做 |
| 成果类总缺口 | 232 | 227 | 部分收窄 |

### 2.2 逐里程碑核验

| 里程碑 | 核验方式 | 结果 |
| --- | --- | --- |
| **M1** 消除自造行为 | 源码检索 + 门禁方向 | ✅ 青色选中描边已移除：`battle_unit_selected_palette_color` 与 `selected_palette` 在 `battle_runtime_scene.cpp` 中均已不存在；门禁 `tests/test_butano_battle_unit_animation_runtime_wiring.py` 已**反转为 `assertNotIn`**（原为 `assertIn`，即原门禁把错误行为钉死了） |
| **M2** 原版状态机 | 跑 `tests/test_battle_controller_states` | ✅ 22 项测试全绿；产出 `sequel/content/battle_controller_states.json`（93 KB，38 态 + 38↔24 映射）与 `sequel/content/battle_controller_transitions.json`。**但**该表自带 `implemented: false` 声明：重制仍跑自己的 24 值 `battle_scene_phase` 枚举，**枚举替换尚未做** |
| **M3** 接入 pixel-A/B + relocation | 跑两个导入器的 `verify` 子命令 | ✅ `import_rom_pixel_ab_baselines.py verify` → `checked_families: 32, problems: []`；`import_rom_relocation_specs.py verify` → `checked_families: 22, problems: []`。两者都按**逐族 manifest SHA-256 钉死**、校验 `accepted` 状态、manifest 变动即硬失败，并提供 `compare` 复跑入口 |
| **M4** 5 个未触及成果 | 查台账 | ✅ 5 族全部记为 `not-applicable` 并附**可核验理由**：如 `rom-chapter-script-unbound-tail-v1` 的 `artifact_status` 是 `candidate`（导入规则只接受 `accepted`）、`rom-fast-audit-four-packet-baseline-v1` 的 `scope.historical_baseline_only=true`、`rom-sprite-component-source-v1` 描述的是重制未使用的通用精灵系统 |
| **M5** 结论消化 | 查 notes `none` | ❌ **未做**（213 条未被读的结论一条未动） |
| **M6** 台账收口 | 查台账 | ✅ 17 条目，`missing` 归零，状态分布 `reconstructed: 9 / not-applicable: 5 / reused: 2 / derived: 1` |
| **M7** 持续门禁 | 查收据 | ✅ 底账于 02:52 用同一工具重跑生成 |
| **M0** 来源声明 | 查 `tools/audit_butano_reverse_provenance.py` | ⚠️ **该工具不存在**。但 M3 的两个导入器用**逐族 manifest 哈希钉死 + 导入收据**实现了同等强度的来源绑定，且可 `verify` 复跑。⇒ M0 的目标在 M3 覆盖的范围内已达成，**全局 provenance 扫描器仍缺** |

### 2.3 55 个新 `build` 族的命中来源（排除自指后仍成立）

| 来源 | 族数 |
| --- | ---: |
| `tools/butano/import_rom_pixel_ab_baselines.py` | 32 |
| `tools/butano/import_rom_relocation_specs.py` | 22 |
| 其他既有 `tools/export_*.py` | 1 |

⇒ 新增消费**集中在 M3 的两条导入链**上，与 roadmap 的设计一致，不是靠文档命中凑出来的。

---

## 3. 本轮发现并修复的测量缺陷：自指偏差

**现象**：首轮核验（02:52 底账）显示成果族 `none` 从 15 降到 0、真正未触及成果
5 → 0，看起来 M4 已完美收口。但逐族查命中位置时发现，**这 15 族的唯一命中是
`docs/butano-reverse-gap-roadmap.md`**——也就是我自己写的、专门列出"从未被触及"
的那张表。

**根因**：测量把"本树提到某成果族"当作"本树消费了某成果族"。写报告这件事本身
就会让报告里的所有缺口族变成"已提及"。

**修复**：`tools/measure_butano_reverse_gap.py` 的排除清单新增
`docs/butano-reverse-gap-roadmap.md` 与
`notes/full-customization-and-fidelity-theory-20261020.md`（会话此前已排除底账目录
`artifacts/butano-reverse-gap-v1/`），并在收据的 `excluded_prefixes` 中公开。
新增守卫测试 `test_the_roadmap_and_theory_note_are_not_references`。

**修复后的真实数字**：`none` = 10（全是 `precoverage` 中间产物），
真正未触及的最终成果 = 0，`build` = 88。

**方法论教训（写进 AGENTS.md 任务模式登记表）**：
> 任何"清单型产物"（差异报告、roadmap、覆盖表、索引）都会枚举被测对象；
> 若测量口径是"名字出现即算引用"，则**写清单本身会提高清单的分数**。
> 测量工具必须把自身产物与引用清单排除在外，且排除项必须在收据里公开。

---

## 4. 仍未闭合的项

| 项 | 状态 | 说明 |
| --- | --- | --- |
| M0 全局 provenance 扫描器 | 缺 | `tools/audit_butano_reverse_provenance.py` 不存在。M3 覆盖范围内有等价机制，但生成产物（`generated_*.h`、`butano-sequel/graphics/*`）仍不声明来源 ⇒ §0.1 的"下界"问题未解决 |
| M2 枚举替换 | 未做 | 状态表已产出并自带 `implemented: false`；重制仍用 24 值自造枚举 |
| M5 结论消化 | 未做 | 213 条 notes 仍 `none` |
| 原版 step-16 移动范围预览 | 对方在做 | 对方已用三条独立证据（逐帧画面 / 38 态映射 / 实跑实验）把 S49 缺口收敛到"一屏"，并**回退**了 `open_command_before_move = false`（该实验证伪了 4.3.79 的解释） |

## 5. 对本仓库自身结论的更正

`notes/full-customization-and-fidelity-theory-20261020.md` §8.2.3 把
`open_command_before_move` 列为"重写侧自造抽象导致流程顺序错"。对方的实测证伪了这
一半：**菜单与目的地网格的相对顺序两侧本来就一致**；4.3.79 观察到的"命令菜单被整个
跳过"实际是"移动被消耗"（`confirm_move_consumes_movement = true` 使 `移動` 项隐藏），
不是流程顺序缺陷。原版真正多出的一屏是**命令菜单之前的移动范围预览**。

⇒ §8 的主结论（"1:1 迟滞主因是逆向成果没接到 Butano 侧"）**依然成立且已被本次
核验证实**（`build` 33→88 之后，S49 缺口从"多屏 + 流程错"收敛为"一屏"）；
但 §8.2.3 的具体归因需要按上述更正。

## 6. 本轮未做的事

未修改 `butano-sequel/game/`；未修改会话产出的任何文件（状态表、转移表、导入器、
台账、M1 门禁）；未启动 mGBA；未 commit / push。
本轮只改了两个自己拥有的文件：`tools/measure_butano_reverse_gap.py`（排除自指）
与 `tests/test_measure_butano_reverse_gap.py`（新增守卫测试）。

---

## 7. 第三轮核验（2026-10-20 03:40）

会话在上一轮之后完成了 **M5（notes 分类索引）** 并转回 S49 像素工作（回合横幅面板
像素级精修 → 重建 → 重录）。本轮重跑测量，发现并处理了**第二个自指来源**。

### 7.1 观测到的现象

首跑时 `notes none` 从 213 掉到 **10**，`result gap` 从 227 掉到 **24**，
看起来像 M5 一次消化了 200 条结论。逐条查命中位置后发现，命中全部来自
`docs/reverse-results-index/notes-index.md`——**该文件逐条列出了全部 427 条 note**。

⇒ 与 roadmap 自指偏差**同类**：批量枚举被测对象的清单型产物，其命中是"分类"，
不是"消费"。

### 7.2 会话独立发现了同一问题

`docs/reverse-results-index/notes-index.md` 的开头**自己写明了这一点**：

> 本索引把每条 note 都写进了本树，因此差异测量里这些 note 的状态会从 `none` 变成
> `doc`/`local_artifact`。**那不是消费。** 下面是写入本索引之前它们在本树的真实状态。

其机读收据 `artifacts/reverse-notes-index-v1/notes-index.json` 的
`summary.by_pre_index_status` 保留写入前快照：
`build 19 / local_artifact 3 / test 15 / doc 177 / none 213`——
**与本仓库 02:24 的独立基线逐项吻合**。⇒ 双方独立测得同一真值。

### 7.3 本轮处置

- 测量工具排除清单新增 `docs/reverse-results-index/notes-index.md`；
  新增守卫测试 `test_the_notes_index_is_not_a_reference`（工具现 **11 项测试全绿**）。
- **保留**（非枚举器，是真引用）：
  `docs/reverse-results-index/battle-controller-states.md`（命中 6 条，含
  `rom-battle-controller-cfg-v1` 等 4 个成果族）、
  `docs/reverse-results-index/ledger.json`（命中 7 条）、
  `sequel/content/battle_controller_states.json`（命中 4 条，带来源指针）。

### 7.4 三轮同口径对比

| 指标 | 基线 02:24 | 核验 02:58 | 本次 03:40 |
| --- | ---: | ---: | ---: |
| 索引条目 | 2,186 | 2,190 | 2,190 |
| 成果族 `build` | 33 | 88 | **88** |
| 成果族 `build` 占比 | 12.6% | 33.6% | **33.6%** |
| 成果族 `doc` | 211 | 161 | 161 |
| 成果族 `none` | 15 | 10 | 10（全为 `precoverage`） |
| 真正未触及的最终成果 | 5 | 0 | **0** |
| 台账 `missing` | 5 | 0 | **0** |
| notes `none` | 213 | 213 | **213** |
| 成果类总缺口 | 232 | 227 | 227 |

### 7.5 M5 的实际形态

M5 的交付物是**分类**而非**消费**，5 桶覆盖全部 427 条 note：

| 桶 | 条数 | 含义 |
| --- | ---: | --- |
| `implemented_in_code` | 19 | 本树构建链已引用，附消费文件与行号 |
| `not_applicable` | 43 | 与本复刻无关，附理由 |
| `missing_evidence` | 19 | 证据未闭合，回逆向侧补齐 |
| `needs_guard` | 333 | 已给出原版结论，尚未转成门禁（M1/M2 的原料） |
| `needs_human_review` | 13 | 自动判读不了，附原因 |

⇒ **M5 按其自身定义达成**（每条 note 落在 1/2/3/4 之一，计数由脚本统计）；
但 `needs_guard` 的 333 条**尚未转成门禁**，那才是 M1/M2 的真实工作量。
`notes none = 213` 不变是正确的——分类不等于消费。

### 7.6 仍未闭合

| 项 | 状态 |
| --- | --- |
| M0 全局 provenance 扫描器 | 缺（`tools/audit_butano_reverse_provenance.py` 不存在）；M3 范围内有逐族哈希钉死 |
| M2 枚举替换 | 未做：状态表自带 `implemented: false`，重制仍用 24 值自造枚举 |
| `needs_guard` 333 条 → 门禁 | 未做，这是 M1/M2 的真实剩余量 |
| 原版 step-16 移动范围预览 | 对方在做（回合横幅资产已做到像素级，重建重录中） |

---

## 8. 第四轮核验（2026-10-20 04:15）

会话已交付 roadmap 报告并转回 S49 复刻线。本轮独立重跑全部验收命令。

### 8.1 量化：四轮同口径对比（排除全部清单型自指）

| 指标 | 基线 02:24 | 轮2 02:58 | 轮3 03:40 | 轮4 04:15 |
| --- | ---: | ---: | ---: | ---: |
| 索引条目 | 2,186 | 2,190 | 2,190 | 2,190 |
| 成果族 `build` | 33 | 88 | 88 | **88** |
| 成果族 `build` 占比 | 12.6% | 33.6% | 33.6% | **33.6%** |
| 成果族 `doc` | 211 | 161 | 161 | 161 |
| 成果族 `none` | 15 | 10 | 10 | 10（全为 `precoverage`） |
| 真正未触及的最终成果 | 5 | 0 | 0 | **0** |
| 台账 `missing` | 5 | 0 | 0 | **0** |
| notes `none` | 213 | 213 | 213 | 213 |
| 成果类总缺口 | 232 | 227 | 227 | 227 |

+55 的构成经逐行核对：**M3 的 54 族导入 + M2 的 `rom-battle-controller-cfg-v1`**
（其 `build` 命中在 `sequel/content/battle_controller_states.json` 与
`battle_controller_transitions.json`，属真实消费）。其余 2,132 行零变动。

### 8.2 逐条验收命令（本机复跑，不采信自述）

| 里程碑 | 命令 | 结果 |
| --- | --- | --- |
| M1 / S49 门禁 | `unittest discover -s tests -p 'test_s49_*'` | **51 tests OK (skipped=3)** |
| M2 状态机 | `unittest tests.test_battle_controller_states` | **22 tests OK** |
| M3 导入 | `unittest discover -s tests -p 'test_rom_*_import.py'` | **27 tests OK** |
| M3 独立 verify | `import_rom_pixel_ab_baselines.py verify` | **32 族，`problems: []`** |
| M3 独立 verify | `import_rom_relocation_specs.py verify` | **22 族，`problems: []`** |
| M6 台账 | `unittest tests.test_reverse_results_ledger` | **14 tests OK** |
| M7 幂等 | 测量工具连跑两次 | **summary 与 rows 完全一致** |
| 全树回归 | `unittest discover -s tests` | **exit 0** |
| M0 | `tools/audit_butano_reverse_provenance.py` | **不存在**；生成产物无 `reverse-source` 声明 ⇒ **未交付**（与会话自述一致） |

### 8.3 S49 像素收据核验（读 `region-diff-banner6/summary.json`）

| 基线 | 全屏差 | 状态栏 | 菜单面板 | 左侧单位 |
| --- | ---: | ---: | ---: | ---: |
| dialogue1-sakura | **0** | 0 | 0 | 0 |
| dialogue2-naruto | **0** | 0 | 0 | 0 |
| dialogue3-sasuke | **0** | 0 | 0 | 0 |
| action-menu | **0** | 0 | 0 | 0 |
| turn-banner | 722 | 0 | 582 | 140 |
| field-unit-selection | 1,278 | 0 | 0 | 920 |
| command-menu | 655 | 0 | 0 | 655 |
| move-grid | 3,463 | 0 | 1,024 | 696 |
| command-menu-row2 | 1,183 | 0 | 0 | 1,183 |

跨轮次趋势：命令菜单 **715 → 655**（banner3 起）、回合横幅 **742 → 730 → 722**、
状态栏**全程 0**。

**「横幅本体 4000 像素 0 差异」的口径被逐字证实**：
`region-diff-banner6/turn-banner.json` 的 `banner-panel` 区域
`box=[72,40,152,90]`（80×50 = 4000 像素）`different_pixels = 0`。
但该基线**整屏仍差 722**，残差来自 `command-menu-panel` 582 与 `left-unit-sprite` 140
——横幅资产本身已像素级正确，残差属于相位配对与菜单/精灵区域。

### 8.4 仍未闭合（独立确认）

| 项 | 证据 |
| --- | --- |
| **M0 全局 provenance 扫描器** | 文件不存在；`generated_battle_unit_visual_content.h` 头部仍只有 `// Generated by tools/generate_butano_battle_unit_visual_content.py.`，**无来源声明** ⇒ `build = 88` 仍是名字引用口径的下界 |
| **M2 枚举替换** | 状态表与转移表已落地并被消费，但重制仍用 24 值自造 `battle_scene_phase`（`implemented: false`） |
| **`needs_guard` 333 条 → 门禁** | 未做 |
| **M7 CI 接线** | 本仓库无 CI，未做 |
| **原版 step-16 移动范围预览** | 未做；`move-grid` 仍差 3,463 |
| **「SELECT詳細」提示语** | 未做 |
| **单位待机动画 31 姿态** | 未做（重制模型 4 姿态） |
| **移动网格抖动遮罩染色** | 未做 |
| **动作菜单「隐」「年」字形** | 未做 |

### 8.5 本轮结论

**roadmap M1–M7 中，M1/M2/M3/M4/M5/M6 已由脚本证实，M7 部分（幂等已证，CI 未做），
M0 未交付。** 会话的自述与实测**逐项一致**，未发现虚报。

⇒ 「逆向成果没接到 Butano 侧」这个框架结论**已被证实并已被部分修复**：
消费面从 12.6% 升到 33.6%，且新增消费全部有可复跑的 verify 与逐族哈希钉死。
剩下的不是"逆向不够"，而是 **333 条 `needs_guard` 结论要转成门禁**，
以及 M0 要把 `build` 从下界变成血缘真值。

---

## 9. 第五轮核验（2026-10-20 04:45）：M0 已交付

会话自 04:03 结束回合后转入空闲，但其 W1 泳道**随后完成了 M0**（工具、测试、
12 个生成器改造、生成头文件重建全部落盘）。本轮独立核验通过。

### 9.1 M0 硬证据

| 项 | 结果 |
| --- | --- |
| 审计器 | `python3 tools/audit_butano_reverse_provenance.py` → **`problems: none`**，exit 0 |
| 测试 | `unittest tests.test_audit_butano_reverse_provenance` → **18 tests OK** |
| 血缘声明 | 生成头文件已带：`// provenance-carrier: c-header-comment`、`// reverse-source: character-battle-visuals-v1 @ a048eb6b…`、`// reverse-source-rom: 0x596D5C+8928 sha256 baa3f867…` |
| 审计器设计 | 声明是**唯一连接**（审计器自身不携带任何族名）；消费的 ROM 区段摘要必须由该族记录，且该偏移处的字节必须哈希到该摘要；缺 manifest / manifest 漂移 / `candidate`·`disproved`·被取代 ⇒ 硬失败，不静默跳过 |

⇒ 这正是"**不得用名字命中冒充血缘**"要求的实现：**字节级**血缘，可回查 ROM。

### 9.2 量化：五轮同口径对比

| 指标 | 基线 02:24 | 轮4 04:15 | 轮5 04:45 |
| --- | ---: | ---: | ---: |
| 索引条目 | 2,186 | 2,190 | 2,190 |
| 成果族 `build` | 33 | 88 | **91** |
| 成果族 `build` 占比 | 12.6% | 33.6% | **34.7%** |
| 成果族 `doc` | 211 | 161 | 158 |
| 成果族 `none` | 15 | 10 | 10（全为 `precoverage`） |
| 真正未触及的最终成果 | 5 | 0 | **0** |
| 台账 `missing` | 5 | 0 | **0** |
| notes `none` | 213 | 213 | 213 |
| 成果类总缺口 | 232 | 227 | 227 |

本轮 +3 的族（`map-canvases-v1`、`dialogue-font-v2`、`menu-portraits-v1`、
`rom-battle-condition-records-v1`、`rom-chapter-script-inventory-v1`、
`rom-fixed-consumer-text-inventory-v1` 等）**改为经生成头文件的血缘声明命中**，
不再是名字匹配。

### 9.3 M0 的残留缺口（可执行）

审计器 `PRODUCT_GLOB = "generated_*.h"`，实测报出 **20 个生成产物在 carrier scope 之外**：

- 9 个 `butano-sequel/game/include/konoha/*_sprite_font.h`
  （由 `tools/generate_butano_battle_identity_content.py` 生成，但文件名不匹配 `generated_*.h`）
- 11 个 `generated_*.h` 标注为"not written by a tools/generate_butano_*.py generator"
  （`generated_battle_action_05_*`、`generated_battle_action_16_*`、
  `generated_battle_ninja_tool_bomb_*`）

⇒ 这些产物**没有血缘声明**，其数据来源在测量里仍不可证。
把 carrier scope 扩到全部生成产物，是 M0 的收尾，且会直接抬高 `build` 的可证性。

### 9.4 仍未闭合

| 侧 | 项 |
| --- | --- |
| roadmap | M0 carrier scope 扩到 20 个无声明产物；M2 的 24 值枚举替换；`needs_guard` 333 条转门禁；12 个 `unknown` 状态码的 handler 级静态断言；23 个 pixel-A/B 族缺 scenario-47/50/53 对照配方；10 个上游素材目录未被导入；M7 CI 接线（本仓库无 CI） |
| 复刻（S49） | 原版 step-16 移动范围预览（相机 (152,40)、无状态栏、多色网格）；「SELECT詳細」提示语；单位待机 31 姿态（重制 4 姿态）；移动网格抖动遮罩染色；动作菜单「隐」「年」字形 |

---

## 10. 第六轮核验（2026-10-20 05:30）

会话已按指令开工。本轮核验：M0 扩展已交付、P1 映射层已落地、S49 像素有真实进展；
**并发现一个当前为红的状态**（M5/M6 索引产物相对逆向树漂移）。

### 10.1 M0 扩展：交付且**没有靠放宽规则**

| 项 | 结果 |
| --- | --- |
| 审计器 | `python3 tools/audit_butano_reverse_provenance.py` → **`problems: none`**，exit 0 |
| 测试 | `unittest tests.test_audit_butano_reverse_provenance` → **34 tests OK**（上一轮 18） |
| 范围扩展方式 | 生成器用模块级 `GENERATED_PRODUCTS` 常量**显式登记**自己产出什么（`REGISTRY_CONSTANT = "GENERATED_PRODUCTS"`），审计器读注册表 ⇒ **不是靠 glob 猜，也不是靠放宽规则** |
| 残留 | 审计器已**不再报** "generated files outside the carrier scope"；逐文件检查 `generated_*.h` 与 `*_sprite_font.h`，**无声明产物为 0** |
| 放松检查 | 全文 grep `skip|allow|ignore|exempt|tolerat` 只命中文档里那句 "never a silent skip" ⇒ **无新增跳过逻辑** |

**变异测试（独立执行，最强证据）**：把 `generated_battle_unit_visual_content.h` 的
`reverse-source: character-battle-visuals-v1 @ a048eb6b…` 改成 `@ deadbeef…` 后重跑审计器：

```
exit = 2
problems: 1
  - character-battle-visuals-v1: manifest sha256 mismatch
    (declared deadbeef…, actual a048eb6b…)
```

还原后 `exit = 0 / problems: none`。⇒ 审计器**真的会拒绝伪造血缘声明**，
`problems: none` 不是放宽出来的。

### 10.2 P1：原版状态码已进入重制侧

`butano-sequel/game/include/konoha/battle_scene_controller.h` 现在
`#include "konoha/battle_original_states.h"`，并有 `battle_original_state` 枚举、
`battle_original_state_code(...)`、`result.original_state_code` 字段。
新门禁 `tests/test_battle_scene_phase_mapping.py` → **6 tests OK**。

**边界要说清**：24 值 `battle_scene_phase` 枚举**仍在**（保留可读名字），
新增的是**由状态表生成的原版状态码映射层**，行为尚未由原版状态驱动
（状态表仍 `implemented: false`，`named 26 / unknown 12 / state_count 38`）。
⇒ 这是"加了权威映射层"，不是"用原版枚举替换了自造枚举"。

### 10.3 P2：新增门禁（均通过）

`test_s49_select_prompt.py`（4 OK）、`test_s49_action_menu_glyphs.py`（15 OK）、
`test_s49_turn_banner_spec.py`（6 OK）、`test_battle_scene_phase_mapping.py`（6 OK）。

### 10.4 S49 像素：真实改善

| 基线 | 上一轮 banner6 | 本轮 prompt | 变化 |
| --- | ---: | ---: | ---: |
| field-unit-selection | 1,278 | **933** | −345 |
| move-grid | 3,463 | **2,917** | −546 |
| command-menu | 655 | 655 | — |
| turn-banner | 722 | 722 | — |
| command-menu-row2 | 1,183 | 1,183 | — |
| dialogue1/2/3、action-menu | 0 | 0 | — |
| 状态栏 | 0 | 0 | — |

### 10.5 ⚠️ 发现一个当前为红的状态：M5/M6 索引产物相对逆向树漂移

`unittest tests.test_reverse_notes_index` → **24 tests, 1 FAILED**：

```
test_shipped_artifact_matches_a_fresh_build
AssertionError: needs_guard 333 != 334
```

**根因**（已定位到时间戳）：逆向树在 **04:39** 新增了
`notes/evidence/reverse-proof-update-20261019-v1/first-run-venv-interpreter/README.md`，
而 M5 索引产物构建于 **03:52** ⇒ 逆向树在索引构建**之后**又动了。
新构建的 notes 数为 **428**（旧 427）。

**主索引同样漂移**：`build_reverse_results_index.py` 新构建 **2192** 条，
已发布 **2190** 条，新增 `test_audit_reverse_engineering_coverage_count_liveness`。
两边 `ledger_problems` 都是 `[]`。

**对测量口径的影响：无。** 成果族分母在新构建里仍是 **262**（`artifact 262 /
note 428 / doc 65 / tool 816 / test 621`），新增条目一个是 test、一个是 note，
**不改变成果族分母**，故 §9.2 的 `build 91 / none 10` 等结论成立。

**性质**：这**不是**门禁误报，而是门禁**正确地检出漂移**（fail-closed 生效）。
处置是**重建 M5/M6 两个索引产物**（`tools/build_reverse_notes_index.py` 与
`tools/build_reverse_results_index.py`），而不是放宽门禁。

### 10.6 六轮同口径对比

| 指标 | 基线 02:24 | 轮5 04:45 | 轮6 05:30 |
| --- | ---: | ---: | ---: |
| 索引条目 | 2,186 | 2,190 | 2,190（新构建 2,192，成果族分母不变） |
| 成果族 `build` | 33 | 91 | **91（34.7%）** |
| 成果族 `doc` | 211 | 158 | 158 |
| 成果族 `none` | 15 | 10 | 10（全为 `precoverage`） |
| 真正未触及的最终成果 | 5 | 0 | **0** |
| 台账 `missing` | 5 | 0 | **0** |
| notes `none` | 213 | 213 | 213 |
| 成果类总缺口 | 232 | 227 | 227 |

经生成产物血缘声明命中的 build 族：8 → **10**。

### 10.7 我已修复该红状态（会话此刻处于网络错误停机）

会话在 04:39 之后因 `net::ERR_NETWORK_CHANGED` 停在 error 状态，红门禁会留在树上。
漂移是**确定性重建**即可消除的，故由我处理：

| 动作 | 结果 |
| --- | --- |
| `python3 tools/build_reverse_notes_index.py` | 重建 `artifacts/reverse-notes-index-v1/` 与 `docs/reverse-results-index/notes-index.md`；notes 427 → **428**，`needs_guard` 334，`pre-index none` 214 |
| `python3 tools/build_reverse_results_index.py` | 重建 `artifacts/reverse-results-index-v1/`；`indexed 2192 entries`，`ledger_problems` 仍 `[]` |
| **手工维护的 `docs/reverse-results-index/ledger.json`** | **未被改写**（重建前后哈希同为 `7e96c13093d820bd52c9…`）⇒ builder 只审计、不覆盖台账，符合约定 |
| `unittest tests.test_reverse_notes_index` | **24 tests OK**（修复前 1 FAILED） |
| `unittest tests.test_reverse_results_ledger` | 14 OK |
| `unittest tests.test_measure_butano_reverse_gap` | 11 OK |

**修复后同口径数字**（索引 2192 条）：

| 指标 | 基线 02:24 | 轮6 05:30 | 修复后 |
| --- | ---: | ---: | ---: |
| 索引条目 | 2,186 | 2,190 | 2,192 |
| **成果族分母** | 262 | 262 | **262（不变）** |
| 成果族 `build` | 33 | 91 | **91（34.7%）** |
| 成果族 `doc` | 211 | 158 | 158 |
| 成果族 `none` | 15 | 10 | 10（全为 `precoverage`） |
| 真正未触及的最终成果 | 5 | 0 | **0** |
| 台账 `missing` | 5 | 0 | **0** |
| notes `none` | 213 | 213 | 214（新增的逆向 note 尚未被消费，正确） |
| 成果类总缺口 | 232 | 227 | 228（同上，新增 1 条逆向 note） |

**新增条目的性质**：1 个 test + 1 个 note，**不改变成果族分母** ⇒ §10.6 的
`build 91 / none 10 / 真·最终成果 0` 等结论全部成立。

### 10.8 本轮新增的操作教训

> **逆向树在索引产物构建之后又动了 ⇒ 索引产物立刻过期 ⇒ 门禁转红。**
> 这不是门禁误报，而是 fail-closed 生效。正确处置是**重建索引产物**，
> 绝不能放宽门禁。
> ⇒ 流程上，**索引产物必须在逆向树稳定之后、作为最后一步重建**；
> 否则任何在逆向侧继续推进的并行泳道都会让 M5/M6 的门禁变红。

---

## 11. 第七轮核验（2026-10-20 13:47）：当前未消费份额

### 11.1 ⚠️ 更正本文件 §8.2 的一处测量错误

§8.2 写的"全树回归 `unittest discover -s tests` → **exit 0**"是**错的**。
当时的命令是 `unittest discover -s tests 2>&1 | tail -4; echo "exit=$?"`，
`$?` 取到的是管道**最后一个命令 `tail`** 的退出码，不是 unittest 的。
会话在 06:17 报告的实数是 `Ran 1902 tests ⇒ failures=24, errors=115`。
⇒ **我在 04:15 报的"exit 0"不成立**，此处更正并保留痕迹。

### 11.2 当前实数（13:47，同口径）

| 指标 | 值 |
| --- | ---: |
| 索引条目 | 2,197（逆向树仍在增长） |
| **成果族分母** | **262** |
| 成果族 `build` | **92（35.1%）** |
| 成果族 `doc` | 157 |
| 成果族 `test` | 3 |
| 成果族 `none` | 10（全为 `precoverage` 中间产物） |
| **真正未被消费的最终成果族** | **170（64.9%）** = doc 157 + test 3 |
| 台账 `missing` | 0 |
| notes 428 | build 21 / doc 174 / test 19 / **none 215（50.2%）** |
| docs 65 | build 0 / doc 55 / test 6 / none 4 |

### 11.3 未消费成果按类别（`rom` 类是最大未消费块）

| 类别 | 合计 | build | 未消费 | 占比 |
| --- | ---: | ---: | ---: | ---: |
| rom | 124 | **4** | 120 | 96.8% |
| visual | 70 | 46 | 24 | 34.3% |
| residual | 13 | 5 | 8 | 61.5% |
| map | 15 | 12 | 3 | 20.0% |
| presentation | 14 | 11 | 3 | 21.4% |
| other | 9 | 5 | 4 | 44.4% |
| scenario | 6 | 5 | 1 | 16.7% |
| runtime | 5 | 1 | 4 | 80.0% |
| battle | 3 | 2 | 1 | 33.3% |
| audio | 1 | 0 | 1 | 100% |
| overview | 2 | 1 | 1 | 50.0% |

> **口径标注**：本表是 **13:47 的快照**（分母 262、`rom` 124），与 §11.2 是同一份索引。
> 13:55 重建后的索引分母为 **264**、`rom` 变 **126**（新增两族都归 `rom`，且都落在 `doc`），
> 其余类别计数一字不变 —— 见 §11.10。

`rom` 类 124 族里进入构建链的只有 4 个：
`rom-battle-condition-records-v1`、`rom-battle-controller-cfg-v1`、
`rom-chapter-script-inventory-v1`、`rom-fixed-consumer-text-inventory-v1`。
未消费的 120 个里：**47 个是 CFG 闭包**（battle-distance-dispatcher、
boot-register-init-dependency、boot-state-dispatcher、story-state-callback、
event-handler 等），64 个是 ROM 结构族，9 个是 provenance/audit 基线。

### 11.4 这 170 个里，哪些是真的"漏了"、哪些是"用不上"

**不是漏、是用不上（占绝大多数）**：boot 链与 interwork、audit/基线类、
`precoverage` 中间产物、47 个 CFG 闭包（当前复刻不走原版启动路径、
不需要完整 CFG 覆盖）、`docs` 类（文档本就不是构建输入，build 0 正常）。

**真·卡住 1:1 的少数几项**（都能对上具体的像素残差）：

| 残差 | 像素 | 缺的是什么 |
| --- | ---: | --- |
| move-grid | 2,917 | 不可达区暗化：覆盖色两侧已完全一致（18 种公共色），缺**不可达区域的冷色暗化罩**（1,024 px）；用 14 组 (底色→蒙罩色) 反解单一 (T, alpha) **无解** ⇒ 两层叠加或暗化图块副本 |
| field-unit-selection | 933 | 原版 32 帧周期内 **30/32 幅互不相同**（191 次帧间变化 183 次变了），而 ROM 的 field slot 是「32 帧/每姿态 hold 8/三姿态」**解释不了** ⇒ 缺的是**哪条运行期路径逐帧推进单位视觉帧** |
| command-menu / command-menu-row2 | 655 / 1,183 | 同上 + 缺陷语义 |
| turn-banner | 722 | 原版 step-16 那一屏的相位语义（相机 (152,40)、`DISPCNT` 与移动网格同一位、无状态栏） |

⇒ 结论：**未被消费的逆向成果有 170 个，但真正卡住 1:1 的是 3～4 项**，
且它们卡住的原因**不是"逆向没做"**（台账 `missing` = 0，所需的东西都有出处），
而是**缺运行期路径级证据**（逐帧推进路径、叠层合成规则），
以及**原版相位语义尚未在逆向侧判定**。

### 11.5 全树套件的真实状态（更正 §8.2 的口径）

`unittest discover -s tests` 正确捕获退出码（`> log 2>&1; echo $?`）：

| 时刻 | 读数 |
| --- | --- |
| 会话 06:17 报告 | `Ran 1902 tests ⇒ failures=24, errors=115, skipped=27, expected failures=4` |
| 13:55（我复跑） | `Ran 1936 tests in 381.473s ⇒ failures=25, errors=115, skipped=27, expected failures=6`，**REAL_EXIT = 1** |

⇒ §8.2 的"exit 0"是**我的管道退出码错误**（`$?` 取的是 `tail`），此处已更正。

**失败归因（140 条失败条目）**：139 条是**既有红**，集中在
`test_butano_scenario_41_assets`（缺 `artifacts/` 源截图）、
`test_butano_battle_result_original_ui`、`test_mgba_manual_battle_observer_script`、
`test_analyze_original_effect_sequence`、`test_audio_sound_id_writeback` 等——
根因是 `artifacts/` 源被清理、`build/` 录制轨迹被清空、以及一条 D7 时期就过期的切片断言。

**唯一的新增红项**：`test_reverse_notes_index.ShippedIndexTest.test_shipped_artifact_matches_a_fresh_build`
——**又是索引漂移**（逆向树在 05:45 之后又新增了 note：428 → 435；索引条目 2192 → 2204）。
这是**第二次**因同一原因转红，证实 §10.8 的流程教训：索引产物必须在逆向树稳定后**最后重建**。

### 11.6 已重建（逆向树此时已提交且干净：HEAD `f054f4c1`、dirty=0）

| 动作 | 结果 |
| --- | --- |
| `build_reverse_notes_index.py` | notes **435**；`pre-index status: build 21 / local_artifact 3 / test 19 / doc 174 / none 218` |
| `build_reverse_results_index.py` | `indexed 2204 entries`，`ledger_problems: []` |
| 手工 `docs/reverse-results-index/ledger.json` | 哈希 `d5f1bbd0664f8e172f4c…` **重建前后未变** ⇒ builder 只审计不覆盖 |
| `tests.test_reverse_notes_index` | **25 OK**（原 1 FAILED） |
| `tests.test_reverse_results_ledger` | 14 OK |
| `tests.test_measure_butano_reverse_gap` | 11 OK |
| `tests.test_audit_butano_reverse_provenance` | 34 OK |

### 11.7 最终差异基线（13:55，重建后）

| 指标 | 基线 02:24 | 现在 |
| --- | ---: | ---: |
| 索引条目 | 2,186 | 2,204 |
| 成果族分母 | 262 | **264**（§11.10 更正：原写 262） |
| 成果族 `build` | 33（12.6%） | **92（34.8%）** |
| 成果族 `doc` | 211 | 159 |
| 成果族 `test` | 3 | 3 |
| 成果族 `none` | 15 | 10（全为 `precoverage`） |
| **真正未被消费的最终成果族** | 229 | **162（61.4%）** |
| 台账 `missing` | 5 | **0** |
| notes | 427（none 213） | 435（build 21 / doc 174 / test 19 / **none 218**） |
| 成果类总缺口 | 232 | 232 |
| 经字节级血缘命中的 build 族 | 0 | **10** |

### 11.8 重建后全树套件复跑（确认漂移红已清除）

| 时刻 | 读数 |
| --- | --- |
| 13:55（重建前） | `Ran 1936 tests ⇒ failures=25, errors=115`（含 1 条索引漂移） |
| **14:15（重建后）** | `Ran 1936 tests in 378.750s ⇒ failures=24, errors=115, skipped=27, expected failures=6`，**REAL_EXIT = 1** |

逐条核对失败清单（139 条）：
- **索引漂移红项已不在其中**（`test_shipped_artifact_matches_a_fresh_build` 消失）
- **会话新写的门禁零失败**：`test_audit_butano_reverse_provenance`、
  `test_battle_scene_phase_mapping`、`test_s49_select_prompt`、
  `test_s49_action_menu_glyphs`、`test_s49_turn_banner_spec`、
  `test_reverse_notes_index`、`test_reverse_results_ledger`、
  `test_measure_butano_reverse_gap`、`test_s49_rule_*` **全部不在失败清单中**
- 剩余 139 条是**既有红**（`artifacts/` 源被清理、`build/` 录制轨迹被清空、
  一条 D7 时期就过期的切片断言、sqlite），与会话 06:17 基线（24+115）**逐条一致**

⇒ 会话 06:17 的"全部是既有红、相对基线减少 18 条且没有新增"这一说法**基本成立**，
但**当时少算了一条**：它自己在 06:17 重建索引后，逆向树又继续推进
（notes 428 → 435、索引 2192 → 2204），那条漂移红在 13:55 复现。
⇒ **漂移是重复事件（已两次），必须固化为流程约束，不能靠"收尾时记得重建"。**

### 11.9 建议固化的流程约束（供写进 AGENTS.md / roadmap）

1. **索引产物（`artifacts/reverse-results-index-v1/`、`artifacts/reverse-notes-index-v1/`、
   `docs/reverse-results-index/notes-index.md`）必须在逆向树稳定后最后重建**；
   逆向树任何新增 note/tool/test 都会让 `test_reverse_notes_index` 与
   `test_reverse_results_ledger` 转红。
2. **重建前先确认逆向树状态**：`git -C <reverse-root> status --short` 为空、
   HEAD 已提交。dirty 时重建出的索引会立刻再次过期。
3. **不通过放宽门禁来消除漂移**——漂移红是 fail-closed 正常工作的证据。
4. 长期解法：让索引收据记录逆向树的**内容摘要**（而不只是 commit），使漂移能被
   *识别为漂移*而非*无解释的计数不符*。

### 11.10.9 第 15 轮当次读数（当次收据，两次连跑一致）

索引条目 **2204**；成果族分母 **264**；成果族 `build` **96/264 = 36.4%**、`doc` 157、
`test` 4、`none` 10；条目口径 `build` **365**、`doc` **507**、`local_artifact` **3**、
`none` **1081**、`test` **248**；台账 **29** 条，`ledger_problems` `[]`，`missing` **0**。

⇒ `build` 由 **92** 升到 **93** 的原因：第 15 轮新增的覆盖层生成器
`tools/generate_butano_movegrid_overlay_assets.py` 进了 `build:` 命中；
**分母仍是 264**（本轮没有新成果族被晋升）。

### 11.10 成果族分母 262 → 264 的更正（第八轮核验，2026-10-20 15:00）

**结论先行**：成果族分母的真值是 **264**（不是 262）。我在 13:47 之后写的
"262"、会话 06:17 / 14:52 报告里的 "262 / 35.1%"，**都是沿用标签或硬编码除数**，
**机器产物一直是对的**。

#### 11.10.1 证据链（全部只读、可复跑）

| # | 证据 | 结果 |
| --- | --- | --- |
| 1 | `git -C <reverse> ls-tree -d --name-only a2d3082a^ artifacts/ \| wc -l` | **262** |
| 2 | `git -C <reverse> ls-tree -d --name-only a2d3082a artifacts/ \| wc -l` | **264** |
| 3 | 同上，`grep -E 'rom-(display-text\|renderer-records)-delta'` | 两族在 `a2d3082a` 中 |
| 4 | `git -C <reverse> reflog --date=format:'%m-%d %H:%M'` | `a2d3082a` 于 **12:27** 落地，下一次提交 **12:51** ⇒ **12:27 之后任何索引重建都看到 264** |
| 5 | `a2d3082a` 提交信息 | `feat: Tier-2 门槛例外 —— 三包晋升入账（3,361 B）+ 四道裁决落档` |
| 6 | `artifacts/reverse-results-index-v1/index.json` 的 `kind` 计数 | `artifact 264 / note 435 / tool 817 / test 623 / doc 65`，共 **2204** |
| 7 | `artifacts/butano-reverse-gap-v1/gap.json` 的 `rows` 按 kind 计数 | 同上 **264** |
| 8 | 我在 **14:49** 独立重跑 `measure_butano_reverse_gap.py`（`build/butano-reverse-gap-check-20261020/`） | `artifact 264`，`index.sha256` 与收据一致 |

⇒ **262 只在 12:27 之前成立**。`a2d3082a` 是分母翻牌的那一次提交，
新增的两族是 `rom-display-text-delta-v1` 与 `rom-renderer-records-delta-v1`。

#### 11.10.2 两族对结论的影响：分母变、结论不变

两族都是 `rom` 类、当前状态都是 **`doc`**（各 1 次命中），因此：

| 指标 | 262 时代 | **264（现值）** |
| --- | ---: | ---: |
| 成果族分母 | 262 | **264** |
| 成果族 `build` | 92 | **92（不变）** |
| 成果族 `doc` | 159 | **159（不变）** |
| 成果族 `test` / `none` | 3 / 10 | **3 / 10（不变）** |
| `build` 占比 | 35.1%（错） | **34.8%**（build 92、分母 264，**旧值**） |
| 未消费最终成果族 | 162 | **162（绝对数不变）= 61.4%** |
| `rom` 类合计 / 未消费 | 124 / 120 | **126 / 122** |

⇒ **「92 族已进入构建链」「162 族仍未消费」「台账 missing = 0」三条结论不受影响**，
受影响的只有**分母**和**由分母推出的百分比**。

#### 11.10.3 错在哪：不是测量错，是标签错

会话 14:52 报告的原始命令（我从其 transcript 读出）：

```python
fam=[r for r in d['rows'] if r['kind']=='artifact']
c=collections.Counter(r['status'] for r in fam)
print('families 262:', dict(c), 'build%%=%.1f%%' % (100*c['build']/262), ...)
```

`262` 被**硬编码在打印串和除数里**，而 `dict(c)` 实际是
`{'build': 92, 'doc': 159, 'none': 10, 'test': 3}` —— **加起来正好 264**。
⇒ 分子、分项全部正确，**只有除数是抄来的旧值**。

我在 13:47/13:55 两处也是同一类错误：把 **11:06 提交的基线分母（262）**抄进
"当前实数"表，而没有用 `len(fam)` 重算。**我自己上一轮口头回复里"成果族 262
+ 34.8%"也是同一个错**（34.8% 是「build 92 ÷ 分母 264」算的，标签却是 262）。

**判定依据（为什么 §11.2 的 262 是对的、§11.7 的 262 是错的）**：

| 位置 | 该表分项和 | 与标签是否自洽 | 判定 |
| --- | ---: | --- | --- |
| §11.2（13:47） | 92+157+3+10 = **262** | **自洽** | 该表用的是 12:27 之前建的索引（2197 条），**262 正确** |
| §11.7（13:55） | 92+159+3+10 = **264** | **矛盾** | 标签 262 错；且同表的 34.8% 与 61.4% 都是按 264 算的 ⇒ 只有标签是抄来的 |

#### 11.10.4 顺带复核的两件事（都是"假下降"嫌疑）

| 复核项 | 方法 | 结果 |
| --- | --- | --- |
| 是否有批量枚举型新产物把 `none` 假降 | 列出 `artifact` 的 10 个 `none` 族逐个看 | 10 个**全是 `precoverage` 中间产物**，无一个是清单/索引型枚举器 ⇒ **`none` 没有假降** |
| 是否有批量枚举型产物把 `build` 虚高 | 92 个 `build` 族逐个检查是否真有 `build:` 命中 | **92/92 全部有真 `build:` 命中**（`butano-sequel/`、`tools/`、`sequel/`）⇒ 没有虚高 |
| `notes/evidence/**/source-snapshots/` 里的逆向树工具副本是否在充数 | 按命中前缀复核 | 69 次命中**全部是 `doc:`**，从不贡献 `build` ⇒ 没有污染 |

#### 11.10.5 第八轮全树套件复核（独立复跑，非采信自述）

```bash
/usr/local/bin/python3 -m unittest discover -s tests > build/full-suite-r8.log 2>&1; echo "REAL_EXIT=$?"
```

| 项 | 第七轮（14:15） | **第八轮（14:54）** |
| --- | --- | --- |
| 用例数 | 1,936 | **1,936** |
| failures / errors | 24 / 115 | **24 / 115** |
| skipped / expected failures | 27 / 6 | **27 / 6** |
| 真实退出码 | 1 | **1** |
| 失败用例**集合** | 133 条 | **133 条** |
| **集合差（r7 △ r8）** | — | **0 行** |

⇒ 会话"失败集合与基线 diff = 0 行"的说法**由我独立复跑证实**（不是采信自述）：
两轮的失败用例 ID 集合**完全相同**，且**漂移红 `test_shipped_artifact_matches_a_fresh_build`
两轮都不在失败清单里**（索引产物与逆向树当前状态一致，逆向树 HEAD `f054f4c1` dirty=0，
索引 `source.commit` 同为 `f054f4c1`、`dirty: false`）。

**第九轮（我修掉会话遗留的悬空链接后复跑）**：
会话在 `docs/konoha-senki/01-battle-s49.md` 第 2946 行写了 `../notes/...`
（从 `docs/konoha-senki/` 出发应为 `../../notes/...`）⇒
`tests.test_konoha_senki_doc_set.test_every_relative_link_resolves` 变红，
那是 139 条既有红里的一条。修正后复跑：

| 项 | 第八轮 | **第九轮** | **第十轮（加入新闸门）** |
| --- | --- | --- | --- |
| 用例数 | 1,936 | **1,936** | **1,940**（+4 新闸门） |
| failures / errors | 24 / 115 | **23 / 115** | **23 / 115** |
| 失败行数 / 唯一失败用例 ID | 139 / 133 | **138 / 132** | **138 / 132** |
| 真实退出码 | 1 | **1** | **1** |
| 集合差 | — | **仅少 `test_konoha_senki_doc_set...test_every_relative_link_resolves`** | **与第九轮逐条相同，零新增红** |

> 注：`failures + errors` 是**失败行数**（`subTest` 会让同一个用例名出现多行），
> 与**唯一失败用例 ID 数**不是同一个数，第九轮起分别为 138 与 132。

⇒ 我改动的 4 处文档 + 1 处链接**没有引入任何新红**，净减 1 条；
第十轮加入的 4 项新闸门**全绿**（用例数 1936 → 1940，失败集合一字未变）。

#### 11.10.6 本轮新增的可复用规则（已并入 AGENTS.md 任务模式登记表）

1. **任何百分比都必须由当次读数的分项重算**，禁止沿用上一轮的除数：
   打印时用 `len(fam)` 而不是字面量。
2. **标签与分项必须自洽**：一行里若写"分母 X"和"分项 a/b/c"，
   `a+b+c` 必须等于 X；不自洽就是标签错，且要先判断**哪一侧**错
   （本次是 §11.7 的标签错、§11.2 的标签对）。
3. **区分"标签错"与"测量错"**：机器产物（`index.json` / `gap.json`）与
   叙述性标签冲突时，以机器产物为准，并按 §11.10.3 的表逐段判定历史记录该改哪一段。

#### 11.10.7 为这类错误加的闸门（`tests/test_gap_denominator_consistency.py`，4 项全绿）

测量工具本身从来没算错，错的是**从机器产物抄到叙述里的那个数**。所以闸门钉在
**两个「抄写缝」**上，而不是重复测一遍工具：

| 闸门 | 钉住什么 |
| --- | --- |
| `test_the_published_receipt_still_describes_the_published_index` | 已发布收据的 `index.sha256` 必须等于磁盘上索引的哈希，`reverse_commit` 必须等于索引的 `source.commit`，且收据不得建自 dirty 逆向树 ⇒ **陈旧收据不能冒充新收据** |
| `test_the_receipt_denominator_equals_the_index_denominator` | 收据里 `kind == artifact` 的行数、`summary.by_kind.artifact` 分项之和、索引里的成果族数三者必须相等 ⇒ **分母只有一个来源** |
| `test_the_current_documents_quote_the_live_denominator` | roadmap §7.7、核验笔记 §11.10、konoha-senki README 索引行、sequel-roadmap 指针四处「当前状态」必须同时写出实时的**分母**、**build 数**和**百分比** |
| `test_a_claim_against_a_foreign_denominator_must_be_marked_wrong` | 任何 `N/D = P%` 形式的断言：若 `D` 是实时分母，则 `N` 必须是实时 build 数、`P` 必须是实时百分比；若 `D` 不是实时分母，**该行必须带更正标记**（「是错的」「（错）」「更正」「原写」）⇒ **允许引用旧错误，但必须标出来** |

**变异测试（证明闸门真的会红）**：把三处当前状态分别改回 `92/262 = 35.1%`（**变异**用的就是旧的错值）
（roadmap §7.7 / sequel-roadmap 指针 / konoha-senki README 行），
**三处全部被捕获（exit ≠ 0）**，还原后 `exit 0 / OK`。

⚠️ **这条闸门在逆向树推进并重建收据后会主动转红**——那是**信号不是回归**：
文档必须跟着新的实时读数刷新（见 §11.10.6 第 1 条）。
