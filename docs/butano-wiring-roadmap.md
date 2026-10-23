# Butano 复刻接线补全路线图

> 2026-10-22 立。此文档是**执行路线图**：按「能换多少像素 / 能防多少回归 / 结构成本」排序，
> 每个里程碑带**验收分母**与**门禁**。
> 读数来源：`notes/butano-wiring-coverage-20261022.md`（接线点全量枚举）、
> `notes/butano-usable-backlog-20261022.md`（存量分诊）、
> `docs/butano-reverse-gap-roadmap.md`（差异清单与 M0–M7）。
> **读数必须来自当轮收据，不得写死。**

## 目标

把「逆向侧已闭合、复刻侧还没接线」的部分补完，使 **S49 一关的像素差分收敛到 0**，
并让后续每铺一关的接线成本从「重新发明」降到「填表 + 跑审计」。

**明确不在本路线图范围内**：铺关卡数量、补功能面（技能／忍具／宝箱／胜负分支／音频）。
它们由 `docs/sequel-roadmap.md` 负责；本图只保证**接线的机制与存量**。

## 起点读数（2026-10-22 当轮实测；W1 闭合后已刷新）

| 项 | W1 前 | **当前** | 出处 |
| --- | ---: | ---: | --- |
| 逆向成果族 | 264 | 264 | 索引 |
| 带声明的接线（全部有门禁） | **66** | **109** | 109 导入器载体 + 12 provenance 载体（族去重后）；**审计器可见 − 矩阵数出 = 0** ✅ |
| 本地产物缺失（有 exporter，产物不在树里） | **26** | **0** ✅ | W1 补回，26 族逐字节相同 |
| └ 其中复刻侧 producer **自己复现**的 | — | **16** | `rederived`：含解码器的强结论 |
| └ 其中从逆向树**导入**的 | — | **9** | `imported`：抓取／verifier 证据／schema 已迭代 |
| 已闭合带 payload、**无人接** | **71** | **0** ✅ | 55 族接进导入器载体（3 个像素 A/B + 52 个逐文件哈希族）；**15 族因逆向侧自己的 manifest 与文件不一致**被标成 `local-derivation-missing`（不导入 = 不掩盖逆向侧的晋升缺陷）；2 族已被 verifier 读作证据 |
| 其中 `scope` 全部闭合 | 3 | 3 | 逆向 manifest 的 `scope` 块 |
| 其中 `scope` 有未闭合声明 | 69 | 69 | 多为 `runtime_reachability_complete` |
| sink 侧未登记面 | 110 手写头 / 34 内容库 / 1819 图形资产 / 4 运行时源码 | 同左 | 无声明载体 |
| notes `needs_guard`（未转门禁） | 333（314 连测试都没引用） | 332（313） | notes 索引五桶 |
| 差异清单 `local_artifact` | 3 | **0** | 逆向成果的本地副本不再被当成消费 |
| 逆向侧完成度审计 | 失败探针 4 / 阻塞缺口 3 | 失败探针 **4** / 阻塞缺口 **3** | `completion_audit.py --check` **退出码 1**（见 §边界声明） |
| S49 覆盖层残差 | **2,917 @ step-20** | **2,917 @ step-20** | `measure_s49_movegrid_baseline.py --walk artifacts/s49-remake-walk-20261021-v1`（**基线录像目录必须钉住**，见 W2） |
| 复刻关卡数 | 3 / 47 | 3 / 47 | 场景 41/43/49 vs map header 表 47 条 |

## 里程碑

### W0 · 接线点全量枚举（✅ 已完成，2026-10-22）

| 项 | 内容 |
| --- | --- |
| 产出 | `tools/measure_butano_usable_backlog.py`、`tools/measure_butano_wiring_coverage.py` |
| 收据 | `artifacts/butano-usable-backlog-v1/`、`artifacts/butano-wiring-coverage-v1/` |
| 门禁 | 20 + 9 项，全绿 |
| 验收 | 264 族**九态全覆盖**，每族有可审计的判定证据；连跑读数逐字节一致 |

**本里程碑的产出是后续所有 W 的分母来源。**

---

### W1 · 补回 26 族缺失的本地产物（✅ 已完成，2026-10-22）

**为什么先做**：这 26 族的 exporter 还在复刻树里，**产物却不在**。
它们不是「没接线」，是**线断在工作树里**。补回来比新接 26 个族便宜一个数量级。

| 项 | 内容 |
| --- | --- |
| 动作 | 逐族跑复刻侧对应 exporter，重生成 `artifacts/<family>/`；或从逆向树导入 |
| 验收分母 | 26 族本地 manifest 存在，且与逆向树原始**逐字节相同**（分叉即失败关闭） |
| 门禁 | `measure_butano_wiring_coverage.py` 的 `local-derivation-missing` 计数 **= 0** |
| 依赖 | 无 |
| 风险 | 本地 exporter 用的解码器与逆向树不同 ⇒ 会分叉。**分叉必须报错，不许「就近取一个」** |

**本轮结果（`notes/butano-local-derivations-20261022.md`）**：

| 模式 | 族数 | 含义 |
| --- | ---: | --- |
| `rederived` | **16** | 复刻侧 producer 复现了逆向树字节（**含解码器**）——强结论 |
| `imported` | **9** | 复刻侧无 producer 能复现（抓取／verifier 证据／schema 已迭代），按 reverse commit + 逐文件摘要导入——弱结论 |
| `already-identical` | **1** | 还原前已存在且逐字节一致 |
| `diverged` | **0** | 无分叉 |

> **产物**：`tools/restore_butano_local_derivations.py`（还原器）+ `tools/verify_butano_local_derivations.py`（独立复核，**不 import** 还原器）
> **收据**：`artifacts/butano-local-derivations-v1/{local.json,local.md,provenance.json}`
> **门禁**：`tests/test_restore_butano_local_derivations.py`（13 项，全绿）

**本轮顺带收紧了两处旧判定**（不是新功能，是旧判定不够严）：

1. **接线审计器从「只比 manifest」改成「比整棵目录树」**——manifest 只证明描述一致，
   不证明载荷一致；4 个两侧都没有 manifest 的抓取族此前永远判不出「一致」。
2. **差异清单按内容排除「逆向成果的本地副本」**——副本内部的引用不是消费
   （与 `artifacts/butano-reverse-m3-import-v1/` 同理由），本轮命中 30 个目录。
   规则是量出来的：本地摘要**等于**逆向树摘要才排除，一旦分叉立刻重新参与扫描。

> ⚠️ 这 26 族本地产物在 2026-10-19 的 artifacts 清理里被带走
> （`notes/s49-fidelity-handover-20261019.md` §1 记录了 8,124 个被跟踪文件整体缺失）。
> **它们大概率可以重跑出来**——工具还在。
> ⇒ **已证实**：16 族确实重跑出来了，9 族确实没有能重跑的工具。

---

### W2 · S49 覆盖层 1:1 接线（唯一直接换像素的当前项）

**为什么现在做**：S49 残差 2,917 像素的**原版那一侧早就闭合了**——
闭合在**本树的原版运行期收据** `artifacts/s49-original-movegrid-tilemap-v1/`
（BG2、palette 12、32 块、四个状态）。
⚠️ **2026-10-22 更正**：本节原先写的是「`overview-gradient-overlay-v1` 里就有原版覆盖层的
tiles/tilemap/调色板」——**那是另一个覆盖层**（BG0 的**角色总览渐变**层，
palette 13、11 块、checkpoint `alternate-character-overview.ss9`）。
逐项比对见 `notes/s49-overlay-preconditions-20261022.md` §4。
**逆向侧不需要再补分析**（原版逐帧算法已代码验证），但**「接线」这条路本身被下面的
施工尝试否证了**——原版覆盖层是逐帧算的，且重制侧元胞形状与原版不同。

| 项 | 内容 |
| --- | --- |
| 动作 | 按第 26 轮施工单（`artifacts/s49-overlay-plan-20261021-v1/patch-plan.md` §5）三步：① 块预算 77→101 ② 把原版 32 个 4bpp 图块装进 77..100 ③ 移动相位按滚动公式装原版 30×20 烘焙窗口 |
| **前置** | **先读重制侧 VRAM** 核对三件事：槽 77..100 的图块字节 / 可见窗口 30×20 的 tile index / 8bpp 上传长度与基址对齐。**不先改代码**（第 26 轮否证就败在没核对这三处） |
| **前置核对** | ✅ **已完成**（2026-10-22）：`tools/butano/verify_s49_overlay_preconditions.py` 读收据核对，**四项全过**——图块字节 32 块逐块反解一致；四个状态的可见窗口都等于各自的滚动公式算出的窗口（`grid16` 滚的是 152/40，不是 240/24）；来源身份已分清；上传 77 → 52 块、**净省 1,600 B**。收据 `artifacts/s49-overlay-preconditions-v1/`，门禁 `tests/test_s49_overlay_preconditions.py`（8 项，含 4 条变异测试） |
| ⚠️ **施工尝试已失败并回滚** | ❌ 按动作 ③「装原版烘焙窗口」施工 → step-20 残差 **2,917 → 19,213**，已回滚代码并重建基线 ROM（`02bf3573…`），收据保留（`artifacts/s49-remake-walk-20261022-overlay-v1/status.json`、`build/w2-overlay-compare.png`） |
| ⚠️ **第二处前提更正** | **原版的战斗覆盖层不是烘焙出来的静态窗口，是按游戏状态逐帧算的**（移动透镜跟着光标与移动范围走）。装某一刻捕获的窗口，**按构造就是另一个时刻**——对比图里透镜在左上角，而 S49 这一刻在角色周围。⇒ **动作 ③ 整条不成立**，施工单需要重写 |
| ⚠️ **第三处前提更正：残差的主体不是接线** | 逐单元同口径比对（`tools/butano/compare_s49_overlay_layers.py`，收据 `artifacts/s49-overlay-layer-compare-v1/`）：两侧都在 **15×10 个 16×16 px 单元**上说话，但**原版把 46 个单元画成移动透镜、重制侧只画 15 个**（85/150 单元的族不同）。按单元切残差：**2,304 px（79%）是整单元的覆盖差异（= 重制侧游戏逻辑：移动范围/受阻集合）**，**613 px（21%）才是单元内的画法/描边差异（= 接线能碰的）**。⇒ **「残差 ≤ 2,917」若指清零，靠接线达不到**；接线侧的真实可做量是 **613 px** |
| ✅ **地面真相 + 棘轮门禁已就位** | 原版 BG2 转储**独立给出**了可见窗口 15×10 个 16 px 单元各属哪一族（网格网／透镜／光标／目标／受阻／透明）⇒ 落成 `artifacts/s49-overlay-layer-compare-v1/expected_units.json`（**只由原版导出，与重制侧无关**）⇒ 「重制侧的移动范围规则要改成和原版一样」从此是**可判定的**：当前 **85/150 单元族不同（匹配率 43.3%）**，`tests/test_s49_overlay_ground_truth.py` 做成**棘轮**——缺口只许变小，变大即回归 |
| ⇒ **W2 的重新定界** | ① **接线侧**（本图内）：把覆盖层改到原版的 16 px 单元粒度，回收 613 px 的画法/描边差；② **逻辑侧**（本图外，按边界声明归 sequel-roadmap）：重制侧的移动范围/受阻集合要与原版一致（原版的逐单元答案**已经在本树**：`artifacts/s49-original-movegrid-tilemap-v1/*.bg2-layer.png` 就是原版覆盖层单独渲染的图，可直接当门禁期望值） |
| ✅ **根因已锁定：两件事，一件属内一件属外** | 重制侧覆盖层的 tilemap **画了 899 / 1024 格**（31×29 的**实心矩形**，用了 88% 的地图），而**它自己的状态只标了 232 格**是移动透镜（原版是 192 格）⇒ 多画的 667 格 = 232×4 ⇒ **根因是渲染把每个 8×8 px 的状态格扩成了 4×2 块（32×16 px），面积放大 8 倍** ⇒ 这就是「原版透镜是十字、重制是实心矩形」的原因 ⇒ **是渲染 bug ⇒ 属 W2 范围**；但把 8× 展开除掉后，**状态本身**仍是原版透镜的 **2.33 倍**（重制 112 个 32×16 px 游戏格 vs 原版 48 个 16×16 px 单元）⇒ **修好展开后透镜仍是错的形状**，主体仍要动重制侧移动范围规则（本图外）施工单：① 每状态格画 **1** 个 8×8 块（不再 4×2）；② 载入原版 6 族 × 4 变体的 8bpp 展开块（已生成好）；③ 变体按邻居状态选（内部无边 / 右 / 下 / 两边）；④ 块预算 = 原版 24 + 菜单 28 + 重制自己的 4×2（目标相位仍需要）。**验收 = 「单元内画法差异 = 0」**（现 613 px）；整单元覆盖差异（现 2,304 px）只能随**重制侧规则**一起收敛，不在接线侧 |
| 验收分母 | step-20 残差 **≤ 2,917**，且**任何一帧都不得变差**；⚠️ **按 §7 的分解，接线侧的可回收量是 613 px**——接线侧验收应写成「**单元内画法差异 = 0**」，而「整单元覆盖差异」交给逻辑侧 |
| 验收命令 | `/usr/local/bin/python3 tools/butano/measure_s49_movegrid_baseline.py --walk artifacts/s49-remake-walk-20261021-v1` |
| ⚠️ **录像目录必须钉住** | `s49-remake-walk-20261021-v1` = **基线**（最小差分 2,917 @ step-20）；`s49-remake-walk-20261021-v2` = **第 26 轮失败实验**（16,533）。两者都用同一个工具、同一张原版对照帧，**只差 9,302**——不钉目录就会把失败实验读成基线 |
| 失败处置 | 一旦变差立即回滚（照第 26 轮处置），收据保留 |
| 依赖 | 无。**原版数据已在本树**（`artifacts/s49-original-movegrid-tilemap-v1/`）；`overview-gradient-overlay-v1` 是**另一个**覆盖层（角色总览渐变），别当成本项的依赖 |
| 风险 | Butano 的 8bpp tile index 语义与块基址对齐**从未验证过** |

---

### W3 · 让接线审计器覆盖两套载体，并给 sink 面补载体（🟡 动作 1 ✅、动作 2 的 ② ✅；③ 待逐条判定）

| 项 | 内容 |
| --- | --- |
| 动作 1 | provenance 审计器增读**导入器载体**（`import_rom_*` 的 `*_FAMILIES` 常量）；覆盖率断言从「只看头注释」改成「两套都要看」 |
| 动作 2 | 内容库 JSON 增加 `_provenance` 块（族 + manifest 哈希）；图形资产**按生成器**登记 sidecar（不逐文件） |
| 动作 2 的 ③ 的逆向来源 | 🟡 **3 / 16 个生成器已用 `provenance_block` 声明逆向族**（sidecar 直接读声明，不 grep 源码），**13 个未声明**在收据 `declaration_gap` 里逐个列出；门禁钉住「声明的族必须在索引里」与「缺口与已声明恰好互补」 |
| 动作 2 的 ③ | 🟡 **已建机制，余 11 个歧义待声明**（2026-10-22）：`tools/butano/annotate_graphic_asset_provenance.py` 用四条**可测量**规则（`literal` / `pattern` / `constant` / `prefix`，并按**特异度消歧**）把 **1818 个图形资产里的 1807 个（99.4%）**归到 **16 个生成器组**，每组一个 sidecar（逐条记归属规则）；**无归属 0 个**，11 个真歧义明列在开放清单里。三条靠猜的规则被实测否决（token 命中唯一 0 个、片段规则把 1621 降到 106、拼接两个 f-string 数学上重建不出名字）。门禁 `tests/test_graphic_asset_provenance.py`（5 项）。**收口办法**：让两个生成器各自声明产物（像 `GENERATED_PRODUCTS`） |
| 动作 2 的 ② | ✅ **已完成**（2026-10-22）：`tools/butano/annotate_content_bank_provenance.py` 给 **34/34** 个内容库写入 `_provenance` 块（ROM 偏移/长度/哈希 + 提取器 + 逆向族 + note + **无来源时的明写理由**），门禁 `tests/test_content_bank_provenance.py`（8 项，含幂等与 `--check` 模式） |
| 验收分母 | ① 审计器可见的带声明接线 = 实际带声明接线（差 = 0）；② 34 个内容库**全部**能回答「来自哪个族 / 哪条 note」；③ 图形资产按生成器归组后 100% 有 sidecar |
| 门禁 | `audit_butano_reverse_provenance.py` exit 0 且 `problems: none`；新增「没有族处于未登记态」的断言 |
| 依赖 | W1（W1 的产物会新增声明，必须先有载体） |
| 风险 | 载体加在 JSON 里会改内容库字节 ⇒ 要确认现有门禁不依赖内容库的精确字节 |

**这一步是「以后不再产生灰区」的结构性修复。** 每一铺一关都要重接一遍线，
先建机制比先接一关更省。

**动作 1 已完成**（`notes/butano-wiring-carriers-20261022.md`）：

| 项 | 之前 | 现在 |
| --- | ---: | ---: |
| 审计器可见的带声明接线 | **12**（只读头注释载体） | **66**（头注释 12 + 导入器 54） |
| **覆盖率断言 `difference`** | 不可比 | **0** ✅ |
| 导入器载体读取器 | 测量器私有副本 | **审计器持有**，测量器 import 它 |

> **载体规则只能有一份实现。** 上一轮是「测量器自己补一份读取」，登记表本身没动，
> 于是同一棵树有两个不一致的登记表（12 vs 66）——**那不是修好了，是把灰区从一处搬到另一处**。

**动作 2 的两个分母实测下来不可脚本化**（不是判断，是试过的；**但 ② 换了问法后闭合了**）：

| 尝试 | 结果 |
| --- | --- |
| 用内容库 `table_offset` 反查逆向树 259 份 family manifest 的同址/近址 | 32 个有地址的内容库**只中 2 个** ⇒ **地址不是可用的连接键** |
| 用内容库自带的 `extraction`/`discovered_by`/`notes` 反查来源 | 这些字段记的是「逆向侧当时怎么提取的」，**不是**「哪一族闭合了它」 |
| 扫 37 个生成器源码里字面出现的图形资产名 | 1819 个图形资产里**只 174 个**被点名，其余由循环/模板生成 |

⇒ 动作 2 与 **W5 同类**：**逐条判定**，先给分母与缺口清单，再逐族/逐生成器落地。

**但 ② 已用「换问法」闭合**（2026-10-22）：不再问「这库来自哪个族」，
而是让每个库**如实回答「它的字节从哪来」**——
ROM 偏移/长度/哈希（实测）+ 库自带的提取器（实测）+ **声明了同一表地址**的逆向族（严格匹配）
+ 库自带的 note 指针（实测）+ **都没有时明写理由**。
⇒ 34/34 个内容库现在都能回答（2 个有族、13 个有 note、15 个有提取器、
19 个只认 ROM 偏移并写明「无族/无 note/无工具」）。
**判据从「猜来源」换成「记录来源」，灰区因此消失。**

---

### W4 · 71 个「已闭合带 payload、无人接」的族按子系统接线

**这是唯一「换像素」的批量项，但每一族都是设计判断，脚本做不了。**

建议顺序（按复刻子系统归位，详见 `notes/butano-usable-backlog-20261022.md` §4）：

> ⚠️ **2026-10-22 更正**：序 6 之外的「移动网格覆盖层」一行原写
> `overview-gradient-overlay-v1` 是 S49 覆盖层的来源——**不是**。
> 那是 BG0 的**角色总览渐变**层（palette 13、11 块）。
> S49 战斗覆盖层的原版侧闭合在**本树**的运行期收据里，不在货架上。
> 证据：`notes/s49-overlay-preconditions-20261022.md` §4。

| 序 | 子系统 | 族 | 备注 |
| --- | --- | --- | --- |
| 1 | 状态栏 / 调色板 | `battle-status-bars-v1`、`rom-menu-portrait-palette-inventory-v1`（70 个 128 B 物理调色板）、`portrait-palette-producers-v1` | 调色板逐号同色是像素等价的必要条件 |
| 2 | 文本 / 对白 | `rom-alternate-dialogue-table-v1`（80 条对白文本）、`rom-dialogue-text-inventory-v1`、`rom-renderer-text-inventory-v1`、`rom-display-text-delta-v1` | 复刻侧对白/文本还原是当前最大内容缺口 |
| 3 | 场景 / 地图 | `scene-visual-composites-v1`（10 张 240×160 合成图）、`runtime-bg-composites-v1`、`runtime-screen-composites-v1`、`map41-visual-resource-matrix-v1` | 背景合成与图层 |
| 4 | 战斗特效基准 | 13 个 `battle-effect-*` 族（带 `capture.png` 240×160 + VRAM/OAM/PRAM dump） | 可直接当 1:1 验收基准，导入器现成 |
| 5 | 音频表 | `rom-battle-sound-selector-v1`、`rom-directsound-pitch-lookup-v1`、`rom-psg-frequency-lookup-v1` | 只给音频运行时，**不换像素** |
| 6 | 文字 / 其它 | `rom-pointer-lz77-graphics-v1`、`rom-renderer-script-pointer-pool-records-v1` 等 | 杂项 |

| 项 | 内容 |
| --- | --- |
| 验收分母 | 逐族：① 接线声明登记 ② 像素差分或内容等价验收 ③ 门禁 |
| 门禁 | 每族一条；总门禁 = `measure_butano_wiring_coverage.py` 的 `on-shelf` 计数逐族归零 |
| 依赖 | W3（声明载体要先在） |
| 风险 | **`scope` 未闭合的 69 族**：多数是「自然运行期可达性未证明」。接进去可以，但**不能声称原版一定会走到那里** |

**第 1 片（✅ 2026-10-22）：3 个 `-ab-v1` 族接进像素 A/B 导入器载体**

| 项 | 值 |
| --- | --- |
| 接进的族 | `cutscene-obj-id1-primary-ptr-ab-v1`（**真像素族**，4032 像素差）、`levels-status-per-level-ab-v1`（ROM **数据字节**编辑）、`sappy-engine-master-enable-ab-v1`（ROM **代码半字**编辑） |
| 声明载体 | `tools/butano/import_rom_pixel_ab_baselines.py` 的 `PIXEL_AB_FAMILIES`（族 + manifest 哈希钉死） |
| 验收 | 前者像素差分；后两者**内容等价**——本树 base ROM 在记录偏移处仍等于记录的基线值 |
| 读数 | 带声明接线 **66 → 69**；`on-shelf` **71 → 69**（含 2 族 verifier-only ⇒ 矩阵里是 `verified-against`）；覆盖率断言差 **= 0** |
| **第 2 片（✅ 2026-10-22）** | **52 族逐文件哈希族接进新载体** `tools/butano/import_rom_shelf_families.py`（族 + manifest 哈希钉死 + **逐文件哈希复核** ⇒ 内容等价验收）：**794 文件、0 问题**。⇒ 带声明接线 **→ 109**，`on-shelf` **→ 0**。**15 族不导入**：它们自己的 manifest 与自己的文件不一致（逆向侧晋升的缺陷）⇒ 如实标成 `local-derivation-missing`，**不导入＝不掩盖** |

> ⚠️ **货架笔记的「同一形态」判断只对了一族**：
> `notes/butano-usable-backlog-20261022.md` §4 把这三族写成「与已导入的 32 族同一形态」。
> **文件布局一样，但「编辑的是什么」不一样**——后两族改的是 ROM 数据/代码，
> **没有像素期望**。⇒ 导入器新增 `rom_anchor` + `check_rom_anchor()`，
> 门禁对无像素期望的族改用内容等价验收，并配**变异测试**（改锚点字节必须被拒）。
> **载体是按验收方式分的，不是按文件清单分的。** 详见 `docs/butano-reverse-gap-roadmap.md` §8.6。

---

### W5 · notes 侧：333 条 `needs_guard` 转门禁

| 项 | 内容 |
| --- | --- |
| 动作 | 按 W4 的子系统挑相关 note，逐条转成行为门禁；剩下的按 M5 分批消化 |
| 第一步（已完成） | ✅ **字节级批量钉点**（2026-10-22）：`tools/butano/snapshot_note_rom_claims.py` 把 332 条 `needs_guard` note 引用的 **2405 处地址**里**可钉的 1434 处**（卡带窗口内）钉成 base ROM 的 4 字节断言；**971 处 EWRAM/PRAM/IO 地址只列不钉**（base ROM 里没有这些字节）。门禁 `tests/test_note_rom_claims.py`（5 项）。**边界**：字节级只保证「note 指的字节没变」，**不保证解读仍成立** ⇒ 语义门禁仍逐条写 |
| 验收分母 | `needs_guard` 从 333 降下来；**314 条「连测试都没引用」的优先** |
| 门禁 | `docs/reverse-results-index/notes-index.md` 重新生成后的桶分布 |
| 依赖 | 无（可与 W1–W4 并行） |
| 风险 | 「被测试引用」≠「行为门禁」——文档类测试也算引用。**逐条判定仍需人看** |

---

## 依赖与推进顺序

```
W0（已完成，分母来源）
 ├─► W1（补回 26 族本地产物）──► W3（审计器覆盖两套载体 + sink 载体）
 ├─► W2（S49 覆盖层 1:1 接线）        │
 └─► W5（notes 转门禁，可全程并行）    ▼
                                  W4（71 族按子系统接线）
                                       │
                                       ▼
                            （交棒给 sequel-roadmap：铺关卡 + 补功能面）
```

**W1 与 W2 的先后**：**两者无依赖**。W2 要用的 `overview-gradient-overlay-v1` 属于
`on-shelf`（payload 在逆向树，26,201 B），复刻侧直接读逆向树即可；
W1 处理的是**复刻树本地副本缺失**的那 26 族。两条线可以并行。

## 验收总表

| 里程碑 | 验收分母 | 门禁 | 状态 |
| --- | --- | --- | --- |
| W0 | 264 族九态全覆盖 | 29 项 | ✅ |
| W1 | 26 族本地产物齐全且与逆向树逐字节相同 | `local-derivation-missing` = 0 | ✅ |
| W2 | step-20 残差 ≤ 2,917 且无帧变差 | `measure_s49_movegrid_baseline.py` 逐帧报告 | 🟡 前置 + 分解 + 根因 + **地面真相/棘轮门禁**已闭合；**残差主体需重制侧规则**（棘轮缺口 85 单元），接线侧改动不足以达标 |
| W3 | 审计器可见接线 = 实际接线（差 = 0）；34 内容库 + 图形 sidecar 齐全 | provenance 审计 exit 0 | 🟡 动作 1 ✅ / ② ✅（34/34 内容库有来源登记）/ ③ 🟡（16 组 sidecar，1807/1818 已归组，11 待声明） |
| W4 | 71 族逐族接线 + 门禁 | `on-shelf` 计数归零 | ✅ **on-shelf = 0**（71 → 69 → 0；55 族接进导入器载体，15 族因逆向侧 manifest 自相矛盾改为 `local-derivation-missing`，1 族已被 verifier 读作证据） |
| W5 | `needs_guard` 333 → 逐条降 | notes 索引重新生成 | 🟡 第一步 ✅：332 条 note 的 **1434 个 ROM 字节钉点**已机器可检（971 个非卡带地址只列不钉）；**语义门禁仍逐条待写** |

## 边界声明

- 本路线图**只管接线**。像素差分驱动的是「改重制侧逻辑」（例如 AI 朝向 bug、
  状态栏判据），那类差异**逆向侧没有也不需要**对应成果，不在本图内。
- 「可用」≠「已闭合」：71 族里 `scope` 全闭合的只有 3 族。
  接进去可以，但**不能声称原版一定会走到那里**。
- 「有门禁」是**上界**：测试提到产物路径或导入其生成器模块都算，可能是文档类测试。
- 全部读数由脚本从当次三份收据重算，**逆向树一变就变**，不得写死。
- **每多一份逐族枚举的收据，就必须同步扩一次差异清单的 `EXCLUDED_PREFIXES`**——
  否则测量会静默漂移（已踩两次，见 `notes/butano-wiring-coverage-20261022.md` §5）。

## 不该现在做的事

1. **不要为「接线率」本身去刷数字**——接线是手段，S49 的像素残差才是判据。
2. **不要先接 `not-importable` 的 51 族**——它们是控制流／覆盖分母，
   约束行为但不是素材，接了也不会换像素。
3. **不要在 W3 的载体落地前逐族手写声明**——载体没建好，手写声明无处安放，
   且会被 W3 重新格式化成另一套。
4. **不要把「复刻侧本地重导出的副本」当成「接上了逆向成果」**——
   26 族那批就是教训：exporter 在，产物不在，两者都不是「接了」。

## 相关

- `notes/butano-local-derivations-20261022.md`（W1 还原：16 复现 / 9 导入 / 0 分叉）
- `notes/butano-wiring-coverage-20261022.md`（接线点枚举 + 两处自我更正）
- `notes/butano-usable-backlog-20261022.md`（存量分诊 + 词表探针的三处错分）
- `docs/butano-reverse-gap-roadmap.md`（差异清单与 M0–M7）
- `docs/sequel-roadmap.md`（铺关卡与功能面）
- `notes/s49-fidelity-handover-20261019.md`（S49 工作交接，第 26 轮末）
- `tools/restore_butano_local_derivations.py`、`tools/verify_butano_local_derivations.py`、
  `tools/measure_butano_usable_backlog.py`、`tools/measure_butano_wiring_coverage.py`、
  `tools/audit_butano_reverse_provenance.py`、`tools/measure_butano_reverse_gap.py`
