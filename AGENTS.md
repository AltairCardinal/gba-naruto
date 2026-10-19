# 项目协作规则

## 持久记忆

本仓库是 ROM 逆向与续作规划的长期记忆，重要信息不得只留在对话中。

- 有意义的发现和有效工作必须形成仓库内的持久产物。
- 调查记录、内存映射和实验结果放入 `notes/`；稳定方案和流程放入 `docs/`；可复现实验放入 `tools/`。
- 有效调试方法必须同时记录方法、结果及关键文件或地址范围。
- 逆向结论变化时更新原记录；路线图进度变化时同步更新 `docs/sequel-roadmap.md`。

## 逆向任务成本节约

- 每个逆向工程任务开始前必须先归类为一个可复用的“任务模式”；模式应描述输入、主要操作和可验证产出，不得仅使用当次文件名或地址命名。
- 执行前必须先在本节的“任务模式登记表”中查找相同或足够相近的模式，并按其记载的执行方式处理；不得在已有低成本方式可复用时直接升级到更高成本方式。
- 执行方式按预期成本从低到高固定为：
  1. 编写可复现脚本执行。
  2. 使用 GPT-5.6 Luna max 生成子代理执行。
  3. 使用 GPT-5.6 Terra 生成子代理执行。
  4. 由 Codex 本体直接执行。
- 登记表中找不到对应模式时，必须按上述顺序从最低成本方式开始小范围尝试；只有当当前方式不可用、无法产出可验证结果，或在明确的时间或资源上限内失败时，才可升级到下一种方式。
- 子代理模型只能在当前工具 schema 明确支持时使用；若 Luna 或 Terra 不可用，必须记录“当前环境不可用”后继续尝试下一种方式，不得声称已调用未提供的模型。
- 新模式确定有效执行方式后，必须在任务结束前回填登记表，记录任务模式、选定方式、适用边界和支撑证据；后续结果证明该方式不再合适时，更新原条目并保留变更原因。

### 任务模式登记表

| 任务模式 | 执行方式 | 适用边界 | 支撑证据 |
| --- | --- | --- | --- |
| 固定覆盖账本的只读缺口聚类与证据依赖规划 | 复用既有unknown-cluster分析脚本与formal收据；脚本足够时不启动代理 | 输入ROM、canonical和报告哈希固定，区分提交状态与候选；排名与局部实验不晋升语义，不以历史Goal/额度替代实时状态 | `notes/remaining-reverse-plan-20260930.md`、`notes/evidence/remaining-reverse-plan-20260930-v1/`；87,749B/1,773段重算，2项真实CLI及失败关闭测试通过 |
| 固定 CFG 分母的间接跳转表解析与单代闭包扩展 | 可复现脚本（TDD + `run_guarded.py`）；执行时 Luna schema 不可用；Terra 仅作只读 P0/P1 复核 | 已有哈希固定的基线 CFG，间接跳转可由原始指令、边界与 ROM 表项失败关闭地推导；不适用于需动态状态才能解出的目标 | 逆向分支 `artifacts/rom-cfg-inventory-v3/`、`tools/verify_rom_cfg_inventory_v3.py`、`tests/test_export_rom_cfg_inventory_v3.py`；29/677/290、189/101、4,698/891/9,902 与 16 frontier 独立复验通过 |
| 固定直接分支 producer 证明的新 CFG 根与冻结基线增量 | 可复现 exporter + 独立 raw-control-flow verifier（TDD + `run_guarded.py`）；Terra 仅作只读候选筛选与 P0/P1 复核 | 仅适用于 producer 指令、目标 root、目标限定的全 ROM producer 分母及基线 CFG 均可哈希固定的情况；命中基线有效入口必须 opaque stop，跳入基线指令中部失败关闭；只分类新闭包与 producer 自身，不外推全局代码/BL 分母、间接目标或自然执行 | 逆向分支 `artifacts/rom-cfg-proven-roots-v1/`、`tools/verify_rom_cfg_proven_roots.py`、`tests/test_export_rom_cfg_proven_roots.py`；3 producer/2 roots、6,166 指令、1,203 block、12,966 字节、259 cross-edge 与 28 frontier 独立复验通过 |
| 固定指针表的消费者／解释器绑定记录闭包 | 可复现 exporter + 独立 verifier（TDD）；执行时 Luna schema 不可用；Terra 仅作只读复核 | 仅适用于固定 slot 分母、真实 table-base/index 消费者及 parser 或命令解释器边界均可绑定的记录；只分类 parser 实际消费到的首个终止符，NUL 后零后缀仍保持未知；混合资源表的文本前缀缺少完整索引域时必须整段排除；间隙仅在逐字节验证固定填充值时单独分类，不外推自然可达、Unicode 或可编辑性 | 逆向分支 profile、fixed-consumer、training-text-script、value-range-text、selector-text 与 battle-message-text 六组 artifact/exporter/verifier/tests；fixed-consumer 累计闭合 9 表、575 槽（1 null）、570 条记录并排除 `0x5A7FCC` 混合表，battle-message-text 以 79 槽固定分母闭合 1,411 字节文本和 1,329 字节逐字节验证零填充 |
| 固定 interwork veneer 证明的异构指令集根闭包 | 可复现 exporter + 独立 raw-control-flow verifier（TDD）；执行时 Luna schema 不可用；Terra 仅作只读 P0/P1 复核 | 仅适用于 producer 的直接分支、模式切换、root 与 decoder 均可固定且 worklist 无 frontier 的最小闭包；只分类可达指令、实际消费 literal 与 producer 指令，不外推完整启动运行时路径、相邻 veneer、RAM 目标或包络区域 | 逆向分支 `artifacts/rom-boot-interwork-v1/`、`tools/verify_rom_boot_interwork.py`、`tests/test_export_rom_boot_interwork.py`；唯一 BL→BX pc→ARM B、92/368、8 block/10 edge/0 frontier、9 literal 与净增 414 字节独立复验通过 |
| 历史候选物理别名／子字段的批量负证据合同化 | 单一只读 verifier + 参数化 TDD；执行时 Luna schema 不可用；Terra 仅作只读分组规划与 P0/P1 复核 | 仅适用于候选固定范围能从规范表、artifact 或结构字段逐字节重建，并绑定 candidate、bank、evidence、全 ROM 指针出现分母和已知消费者窗口的 disproved tombstone；否证范围必须固定为“不是独立物理 ROM bank”，不得把未穷尽的 computed/逻辑消费者说成不存在，也不能由此推导有效 bank 已穷尽 | 逆向分支 `tools/verify_disproved_bank_candidates.py` 与参数化测试；10 个 disproved 候选按独立物理 bank 范围重建，输出显式声明未穷尽排除替代逻辑消费者，22 个有效 bank 不受影响 |
| 公开合同闭合的小型冻结逆向工作包（固定指针表、有限 ARM/Thumb 直接控制流、确定性解析／TDD／manifest） | 可复现脚本仍为首选；脚本不足且任务符合右侧边界时，使用 GPT-5.6 Luna max 原生单代理；必须由独立 verifier 在可见输入与隐藏同构输入上复现，失败或越界时升级到 Terra 或 Codex 本体 | 仅限输入、根／范围、输出 schema、失败关闭语义和验收分母均已冻结，能在单一隔离 packet 内完成的短任务：固定槽指针表与终止边界、有限直接分支及 ARM/Thumb 模式切换、CRC／顺序／stop 等确定性解析及其测试／manifest；不适用于完整 ROM、开放式探索、动态运行时状态、合同歧义、自然执行可达性证明、长期多阶段任务或没有独立 verifier 的结论 | `notes/reverse-model-benchmark-20260819.{md,json}` 与 `build/reverse-model-benchmark/report-native-v1.{json,md}`；Luna max 正式结果 3/3 均为 100/100、每格一次通过并完成隐藏同构复现；结论绑定本轮 plan、native receipt、provider contract 和 Codex 二进制，任一变化后必须重跑 compatibility gate 与 contract canary |
| 固定公开合同下的多模型逆向质量／耗时／成本横评 | 可复现 benchmark harness（TDD + `run_guarded.py` + 独立 verifier）；`codex-native` 单代理使用 Codex 内建 provider，Ultra 由 app-server 和冻结的 native HTTPS 子传输执行并累计全部代理线程；受测配置只在冻结 packet 内工作，Codex 本体复核公开合同、隔离证据与最终报告 | 仅适用于配置身份、provider contract、plan／种子、公开 `CONTRACT.json`、输入哈希和评分规则均冻结的小型同构任务；每格隔离写入并在原输入与隐藏同构输入复现，基础设施失败不计模型 0 分；Ultra 是多代理系统配置，不能与单代理解释为纯档位对照；不外推一般智能、完整 ROM 或长期工期，缺失逐请求边界的阶梯成本保持 unknown／partial-known | `docs/reverse-model-benchmark-protocol.md`、`tools/reverse_benchmark/`、`tests/test_reverse_benchmark_*.py` 与 `notes/reverse-model-benchmark-20260819.{md,json}`；冻结 native plan／receipt／manifest／report 哈希、公开合同 canary、独立 billing 重算和凭据扫描可复验 |
| 固定单关的资源引入、Butano 构建及原作差分验收 | 优先复用生成器、独立 verifier、宿主测试、受守卫构建和 mGBA 按键路线；当前原生协作 schema 未提供 Luna max / Terra，记为当前环境不可用；主代理唯一写入，只读代理复核 | 固定 ROM / 快照 / 源码哈希；区分已提交来源与既有候选、整屏与区域比较、宿主接线与真实音频；超时保留证据并停止扩张，不能以单关可玩推导任意新关卡 100% 还原 | `notes/butano-s49-reproduction-20261011.md`、`notes/butano-s49-interaction-fixes-20261011.md`、`notes/butano-s49-full-fidelity-20261013.md` 与对应 artifact manifest；2026-10-13 新增输入对齐全帧录制／全屏无排除比较和菜单、运动、范围图块的红绿及真实运行回归；第二轮补四方向/领取真实输入、实际 SRAM 素材和红绿回归，静态画面不得代替交互验收；首轮 56 项测试、3 个 C++ 宿主程序、地图 / 角色 verifier、整关运行与 9 整屏 / 4 组 UI 比较；短 SFX 回归被拒绝交付 |
| 录制基础设施随 `artifacts/` 与 `build/` 被清理后的原样重建 | 可复现脚本优先（重建脚本本身即固定契约，不手敲 cmake）；Gemini 调用用 `ask_antigravity_gemini.py` 封装的只读 sidecar；执行时 Luna schema 不可用，Terra 仅作只读复核 | 适用于「源码与工具脚本还在、但二进制产物和原始录制被清空」；重建必须钉住 commit + tag + 补丁 SHA-256 并写 sentinel 自证 `--script` 可用；**部分克隆（`--filter=blob:none`）无法再被 `git clone --no-local` 服务，必须浅克隆带完整 blob**；本机 Homebrew mGBA 0.10.5 不支持 `--script`，不能拿它顶替；外部模型只用于「看画面发生了什么」，**坐标／单位身份结论必须回到原始 PNG 复核**，模型给的网格坐标与单位名不可直接引用 | 逆向分支 `artifacts/macos-mgba-20261019-v1/manifest.json`（二进制 `2cc5c36d…`、sentinel `script_loaded=true`）、`tools/build_macos_mgba.py`、`tools/butano/ask_antigravity_gemini.py`（13 测试含一次真实 `gemini-3.8-flash-high` 调用）、`tools/butano/capture_s49_pair.py`、`tools/butano/mgba_boot_input_sequence.lua`；`docs/butano-antigravity-video-review.md` 记录 `--sandbox --dangerously-skip-permissions` 必须成对使用、`webm_encoder` 在 macOS 不可用、`-fps_mode passthrough` 必需；`notes/s49-fidelity-handover-20261019.md` 记录逐键探测与首轮差分：状态栏逐像素一致（鸣人）、单位分处东西两侧、P0 两条（原版 **A/B 切单位且方向键无效**，重制相反；原版循环含**蜜蜂**，重制四人）、名字字形错位（木叶丸渲染成「打木叶」，佐助前 3 字取错，数据表正确、运行时取值错）；**跨帧配对要先做「每帧最佳匹配」再判差异**，否则会把名单差异误读成渲染差异 |
| 按硬编码像素坐标从截图裁剪的字模图集的坐标纠错与局部重建 | 可复现脚本优先：先按列投影从源图反推真值坐标，再写**坐标真值测试**，最后用**局部重建工具**只重算源文件仍存在的字符并把其余格逐字节保留；执行时 Luna schema 不可用，Terra 仅作只读 P0/P1 复核 | 仅适用于「图集的字形是按硬编码 (left, top) 从截图裁出来的」场景：源截图仍可读时才能反推坐标；**坐标必须逐格从源图反推并写成测试**，不能靠「看起来像」推断；**局部重建只能用于源文件仍存在的那部分**，缺源的字符必须显式留档而不是猜；**GBA 存档与 ROM 强绑定**，重新构建后必须从上电重录，复用旧 `.ss9` 会得到黑屏加彩色噪块，极易误判成「构建炸了」；**图集是调色板索引图**，比对必须用参考图集的索引而不是原始 RGB | `tools/generate_butano_battle_identity_content.py`（坐标表）、`tools/butano/repatch_battle_ui_font_glyphs.py`、`tests/test_glyph_crop_coordinates.py`、`tests/test_battle_ui_font_contract.py`、`docs/konoha-senki/01-battle-s49.md` 4.3.52–4.3.53、`notes/s49-fidelity-handover-20261019.md` §6–7；标题行「使劲打木叶丸吧！」是精确 8 像素网格，声明坐标整行错开一格，使「木叶丸」渲染成「打木叶」；修 5 个坐标后局部重建 44 字符，**只有那 5 格变化、39 格逐字节不变**；新 ROM 上电重录与旧 ROM **33 帧中 32 帧逐字节相同**，仅 step-07（名字条 bbox `(4,121)-(28,136)`）不同；既有红测指标 **216 → 0 像素**；另发现 8 个字形源截图**从未进入 Git**，56/100 字符因此不可重建，已由红门禁钉死 |
| 固定输入契约的跨版本推进录制与逐区域配对差分 | 可复现脚本优先（`capture_s49_advance.py` + `compare_s49_regions.py`，TDD + `run_guarded.py`）；执行时 Luna schema 不可用，Terra 仅作只读 P0/P1 复核 | 仅适用于「两侧各有一条可哈希固定的起点 + 显式按键序列」的场景：ROM/快照/mGBA/脚本/SRAM 全部入 `inputs.json`，每步自存快照，截断即失败关闭；**同序号不等于同语义**（两侧推进路径长度可以不同，必须按画面内容选基线而不是按步号）；**底图不同时全屏同索引差分既不能当验收闸门也不能用来选基线**（最优/次优差 0–147/38,400 时排名是噪声），应改用区域差分且把区域写成显式输入；**像素差必须按通道取最大值再二值化**，`convert("L")` 会把单通道 1 级差压成 0 而静默少计；**判定某一帧内容必须单独打开那一帧**，禁止从接触表/网格缩略图反推文件序号；**「重制做不到 X」先确认输入路径**，历史证据可能全部来自中途快照续跑而非上电路径；**重录后若与旧序列逐字节相同，则旧对照表内容有效**，作废的是读取方式而非结论 | `tools/butano/{capture_s49_advance,s49_step_alignment,compare_s49_regions}.py`、`tests/test_{capture_s49_advance,compare_s49_regions}.py`、`docs/konoha-senki/01-battle-s49.md` 4.3.46–4.3.51、`notes/s49-fidelity-handover-20261019.md` §5；`artifacts/s49-fidelity-20261019-v1/{walk-original-a24,walk-remake-dd-a30,region-diff}`；原版 25 步 / 重制 33 步对照表逐帧单独渲染确认，重录与旧序列 21/21 逐字节一致；25×25 全配对 `matched_steps=0` 且最优/次优仅差 0–147 像素，据此**否定**全屏配对方法；5 组内容相同基线的区域差分（对白头像区 0、状态栏 0/31、结算 37）；35 项新测试全绿，含一条守住「无容差」语义的回归 |
| 固定截图上按精灵调色板做像素模板匹配、定位共用图块误用，并判定图集格子的「同字两字号」冲突 | 可复现脚本（TDD + `run_guarded.py` + devkitARM 容器构建 + 上电重录 + 区域差分收据）；执行时 Luna schema 不可用，Terra 仅作只读复核 | 仅适用于「两侧各有一条已哈希固定的同内容基线帧，且精灵共用少数几种调色板颜色」的场景：把精灵图块按其调色板映射成字母再做整块模板匹配，可直接读出**位置一致但图块不同**的误用；**收据的文件名与标签必须先与帧内容核对**，本轮有一份 `result-panel.json` 实为动作菜单，结论顺着错标签一路错到底；**改共享图集格子前必须逐帧回放所有步**，本轮把「查克拉」改成满高后目标区 489→0，但每一步状态栏各多 252 像素、整体更差，说明原版同一字符在不同界面用两套图集，共享格子结构上不可能同时正确；**解法是查清别的图集里有没有已经对的那一份**，本轮在 `battle_action_menu_font` 里找到那三格满高字形（逐索引等于原版），换用已有字体即**零 VRAM 开销**（每张字库 31 KB，场景已同时构造 9 个字体生成器）；**坐标仍须从源图逐格反推并写成测试**，本轮 `移/休/息` 左偏 4px 裁进面板竖边框，与 D3 同源 | `tests/test_s49_menu_row_marker_assets.py`、`tests/test_glyph_crop_coordinates.py`、`tests/test_s49_command_menu_chakra_glyphs.py`、`artifacts/s49-original-ui-reference-v1/`（含 README 记录 ROM 哈希与网格反推）、`tools/butano/{capture_s49_advance,compare_s49_regions}.py`、`docs/konoha-senki/01-battle-s49.md` 4.3.59–4.3.63；动作菜单 37→0、命令菜单 1740→1196、**文字区 489→0** 且状态栏全程保持 0 像素 |
| 从原版存档直接读 PRAM／VRAM／OAM 取证渲染机制（调色板、图块、VRAM 内容） | 可复现脚本（mGBA Lua 读 `emu.memory[<区域名>]:readRange` + Python 驱动 + TDD）；执行时 Luna schema 不可用，Terra 仅作只读复核 | 仅适用于「机制类问题需要硬件状态」的场景：调色板、图块索引、VRAM 内容、去色/变暗、半透明混合。区域名见 mGBA `src/gba/core.c` 的 `_GBAMemoryBlocks`；**路径是 `emu.memory[<区域名>]`，没有 `domains` 子表**——写错会让 Lua 中止、mGBA 继续空跑，最终表现为守卫的 `exit 124` idle 超时，看起来像「跑得慢」而不是「脚本早死了」；**凡能从渲染像素反推的机制，先确认能不能直接读硬件状态**——本轮连续三轮反推（映射是否多义、灰阶是否服从亮度公式）不如直接读一次 PRAM；**读出来的数值必须绑在探针收据上**，不允许退化成一对手抄常量 | `tools/butano/mgba_gpu_state_dump.lua`、`tools/butano/capture_s49_gpu_state.py`、`tools/butano/generate_unit_dimmed_palette.py`、`tests/test_s49_unit_dimmed_palette.py`（10 项全绿）、`artifacts/s49-original-gpu-20261020-v2/`（含 `inputs.json` 与调色板收据）；一次读出原版命令菜单帧 OAM 在用 bank `{1,2,3,14,15}`，**bank 3 = 16 项里 15 项灰阶**，与彩色组逐索引孪生，帧内 13 种灰阶色全部由它解释 |
| 既有成果展示页的全量事实核对与重建 | 可复现脚本优先：先用链接／引用扫描定位断链，再用 ROM 派生数据生成器替换手写数字，最后按生成片段逐行回填页面；单页膨胀到 749 图后按 section 边界拆成多页并共享 CSS/JS，拆分脚本须带「源已是拆分页则拒绝运行」的保护；覆盖率必须由脚本扫描页面实际引用的产物路径得出，禁止人工登记；已在 notes 中标注作废解读时必须保留折叠说明；执行时 Luna schema 不可用，Terra 仅作只读复核 | 仅适用于「已有静态 HTML 展示页 + 页面数字声称来自 ROM/manifest」的场景：所有断链可枚举、页面表格可与 manifest 逐列比对、被推翻的旧解读在 notes 中已有明确证伪记录时；发现页面建立在已证伪读法上必须改引已验证导出而非就地修补；无证据的名称／剧情绑定不得保留，也不得用推断性命名填补；场景名等未闭合语义改中性标注；**「未收录」只表示本工作树无法重建，必须逐族写明具体阻塞输入，不得让读者误解为工作未完成**；**「正文提到族名」不等于「已收录」，部分呈现必须记为 partial 并标出 x/y**；**覆盖率须先声明单位，条目单位差异过大时不得用条目总数当主口径** | `notes/results-viewer-audit-20261018.md`、`tools/{build_results_viewer_assets,build_results_viewer_fragments,build_results_viewer_artifact_index,build_results_viewer_artifact_sections,split_results_viewer,measure_viewer_coverage}.py`、`tests/test_results_viewer_{assets,artifact_index,site,coverage}.py`；立绘区由已证伪的 `0x5A4E14` 155×16 改回 `0x5A4DEC` 311 变体（表 SHA-256 `bfc9952…`），tileset 区由不存在的 `build/tilesets/` 改回真实 47 行 `build/tiles-palette/`；完成度盘点补 8 个成果族 9 张卡片（61 张成品战场画布、250 角色战斗视觉、79 条战斗消息字形等）并生成覆盖总表；再按 section 拆成 6 页共享 `docs/assets/viewer.{css,js}`，入口 URL 不变；958 项引用零悬挂；拆分期修复顶栏 `</button>` 残留致整页塌陷、`currentActiveHub` 重复声明致脚本失效、按 `card` 子串匹配命中 `card-head` 致表格被切开三个缺陷；量化期再纠正「11 族已收录」虚报为 9 族（2 族仅正文提及）并把 60/250 的部分呈现记为 partial，自查轮再发现**人工登记表遗漏 61 个家族**（真实 ROM 逆向家族 85 个主干，其中 55 个 `rom-*` 系列藏在 `notes/evidence/**/source-snapshots/` 递归层），37.5% 系虚报；**更正后覆盖为 9/85 = 10.6%**（完整 7 = 8.2%）。覆盖率分母必须由全仓库普查（递归 `os.walk` 抓 `artifacts/` 引用 + 合并 `v1..vN` 批次）得出，**禁止用手工登记表当分母**；条目单位不可比时必须同时给出含/剔除两个值。补齐轮确认 `sequel/content/**/bank.json` 多数只是 ROM 的比对副本而非输入，为叶子导出器补 `--from-rom` 后**整条下游链自动解开**（补齐 7 族，覆盖率 10.6%→21.2%）；**真正不可补的要写明是需实时 mGBA 采集还是需派生扫描结果**；**片段必须在页面生成期替换，不得事后拼接**（曾致跨 card-grid 误删、重复卡片、无法幂等），依赖顺序用显式 `FRAGMENT_ORDER` 声明；公式轮另发现网页只给图像/计数/地址、**完全没给逆向结论本身（方程）**：13 个成果族共 2,170 个公式字段藏在 manifest 里未展示，已补第 7 个 Hub 公式专页，**由脚本递归抽取任意深度的模型子树**，字段值保留 ROM 原文与代码区间。**正则里不要混入裸 `$`**（`re.search` 中它匹配任何键，会静默清空整棵树）；全仓库普查轮再发现**结论层与工具层整体缺席**：240 篇 notes 的结论从未呈现（含真实音频分派链、单位坐标真源、AI 配置表等重量级架构结论），263 个工具只列了 8 个（49/51 分析器、21/24 提取器从未出现）。已补第 7 页结论索引（202/240 篇提取到结论原文，不改写）与全量工具清单卡。**结论提取须回退到标题后首个实质段落**，且**笔记中引用 artifact 路径不等于已收录**，判定收录须看是否拥有卡片/公式块/图集区段。8 页 / 54 卡片 / 2,302 引用零悬挂、全管线幂等、48 项测试通过 |
| 晋升后回归套件失效的根因定位与「全局量派生 + 元守卫」修复 | 可复现脚本（AST 穷举 + 幂等改写器）+ 元守卫测试（TDD 先红后绿）；执行时 Luna schema 不可用，Terra 仅作只读复核 | 仅适用于「回归套件把会随晋升变化的累计量写成字面量」的场景：失败位置可由**用例名字母序**静态还原（unittest 类内按名排序），再用 **AST 穷举**补全到全部失败点；**只扫 int 字面量会漏掉 SHA 摘要型断言，多行 assertEqual 的尾随逗号会让正则漏匹配**；量的分类必须按「是否随晋升变化」而不是按名字（`consumer_code_slice_*` 名字里没有 `cfg_` 但同样是累计量）；**批次增量必须保持硬编码**（反向护栏），**历史收据的历史值可以硬编码但必须显式登记并反向断言仍钉旧值**（`87,631` 是池 3 晋升前的收据值，差值即 1,542 B）；**派生会让断言退化为「spec 与账本一致」**，这是可接受的，但必须另立元守卫在秒级发现漂移，否则要等 45 分钟套件末尾才见 F；**长跑测试必须 nohup 分离**，前台 bash 900 s 超时会杀掉它且无 summary | `notes/line-a-progress-20261019.md` §14、`notes/evidence/reverse-proof-update-20261019-v1/derive_live_coverage_assertions.py`（幂等，二次运行 0 替换）、`tests/test_audit_reverse_engineering_coverage_count_liveness.py`（6 项全绿，1.3 s）、`tests/test_audit_reverse_engineering_proof.py`（37 处字面量→派生，`LIVE_COVERAGE_SUMMARY` 引用 210→247）；AST+正则双路复扫全 `tests/` 目录陈旧字面量 0 处；12 个失败测试定向复跑 6/6 快速项已转绿（余 2 项含全 ROM 审计者并入全量套件） |
| 正式收据的解释器解析契约（`-I -S` 下的 purelib 漂移） | 可复现脚本优先（先复现单个验证器再改 runner）；执行时 Luna schema 不可用，Terra 仅作只读复核 | 仅适用于「正式 formal 收据里某个验证器 exit 1，但语义上它一直通过」的场景：**换解释器不只是换版本号，还会换 `sysconfig` 的路径解析**——`--system-site-packages` 的 venv 在正常启动时能看到 base 的包，但在 `-S`（跳过 `site.py`）下**看不到**；因此「venv 能 import」**不能**推出「venv `-I -S` 也能 import」；仓库里凡有 `sys.path.append(sysconfig.get_path("purelib"))` 这类 workaround 的验证器（如 `tools/{verify,export}_rom_sprite_loader_tail.py`），**正式 runner 的解释器解析必须与基线逐字节同构**——把 `.venv/bin` 前置到 `PATH` 会让 spec 里的 `python3` 解析到 venv 的空 purelib，workaround 静默失效，报 `ModuleNotFoundError: No module named 'PIL'`，表现为**多出一个假 blocker**而不是语义失败；**正式收据的 A/B 对比只允许有「一个变量」的差异**，否则墙钟数字不可比；改这类被 proof 钉住 SHA 的验证器必须同步 `script_sha256` 并重跑 formal，运行期间改它会让当轮直接失败 | 逆向树 `notes/evidence/reverse-proof-update-20261019-v1/first-run-venv-interpreter/README.md`（首轮 6,214 s / 176 blockers 的完整对照与 purelib 表）、`notes/evidence/reverse-proof-update-20261019-v1/run_formal_parallel.sh`（改用 `/usr/local/bin/python3`、`PATH` 不再前置 `.venv/bin`）、`notes/line-a-progress-20261019.md` §15；首轮 108 个验证器中仅 `verify_rom_sprite_loader_tail.py` 因 `ModuleNotFoundError: No module named 'PIL'` exit 1，其余全绿 |

## Butano 复用逆向成果

- Butano 开发前按 `docs/butano-reverse-results-guide.md` 查找、验真和引入逆向成果。
- 只复用逆向分支中已提交且有证据链的成果；不得依赖另一工作树的
  `build/experiments/`、未跟踪文件或绝对路径。
- 引入时保留来源 commit、manifest、verifier 和适用边界；跨分支写入必须限定路径，
  不得复制整个脏工作树。

## Goal 直接执行

- 自动续跑或继续既有 `/goal` 开发前必须检查 Goal 状态；非 `active` 时不得继续该 Goal 的写操作。用户当前消息明确要求的独立操作仅按其授权范围执行。
- 后续任务不使用 Comet 编排；Goal 直接按仓库交接、路线图、测试和运行时证据规划与执行。
- 规划按可验收里程碑拆分，不做过细实验切片、重复审查或微步骤编排；相邻的低风险输入和验证应合并为一个闭环。
- 恢复任务时重新读取 Goal 状态、交接/路线图、目标证据文件和 Git 状态，以文件事实为准修正过期状态。
- 本地 commit 仅按 Goal 或用户授权执行；push 始终需要单独授权。
- 收到新用户指令后，继续写入前必须重新检查 Goal、存活代理和 Git 状态；重新确认前产生的写入或提交视为未审计结果。

## 并发与子代理

- 共享工作区同时最多一个 writer；reviewer、日志分析和资料研究代理默认只读。
- 外派任务必须独立、非关键路径阻塞、上下文精简且结果可验证；否则由 Codex 本体处理。
- 原生子代理使用 `fork_turns: none` 并在提示词中写明目标、允许路径、禁区、验证命令、停止条件和提交权限。提示词约束不是权限隔离，关键写入仍由父代理复核。
- 当前工具 schema 未提供的模型、权限、路径或预算能力，不得声称已经应用。外部模型只做只读 sidecar，输出均由 Codex 用本地证据复核。
- 子代理报告完成不等于任务完成；父代理必须核对 TDD 红绿证据、集成测试、改动范围和 review 结论后，才能勾选 Comet task。

## ROM 与资源安全

- mGBA、Chromium 和高开销静态任务必须经 `tools/run_guarded.py` 使用同一 heavy lock；只清理本次拥有的进程树。
- 启动前检查可用内存，运行中监控 owned-tree RSS；资源守卫拒绝、超时或内存异常时先保存证据并停止扩张实验。
- 冗长导航前及关键输入前后建立可复用快照，并先验证快照可恢复；后续实验优先从最近已验证快照继续。
- 单次实验只改变一个输入，并保留零输入重放作对照；CPU 暂时为零不能单独证明进程挂死。

## 证据与验收

- 每次实验使用唯一 run ID，不覆盖原始产物；派生分析写入临时或新目录。
- 结论必须关联输入、工具/ROM/快照哈希、关键地址和结果 manifest；失效结论标记为已取代，不删除历史证据。
- 完成前运行与改动匹配的格式、单元、集成和必要的运行时验证；无法执行的检查必须明确说明。
- `AGENTS.md` 只承担稳定行为约束；状态、权限、锁、预算和写入拦截必须由 Goal、Comet guard、hooks 或脚本实现，不得把文字规则当作硬隔离。
