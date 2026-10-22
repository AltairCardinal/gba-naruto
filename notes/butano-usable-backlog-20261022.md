# 未被使用但可直接用于复刻的逆向成果：实测与分诊（2026-10-22）

日期：2026-10-22
工作树 `/Users/altair/github/gba-naruto`（分支 `codex/butano-foundation-research`）
逆向树 `/Users/altair/github/gba-naruto-reverse`，commit `821d0937e058245aa7e6d29f23f96c7fc78e7375`（工作树 dirty=False）
ROM SHA-256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`

## 0. 结论

**复刻侧没有「逆向成果不够用」的问题；缺的是接线。**

- 264 个成果族（artifact family）里，**134 个**同时满足「已 `accepted`」+「带 payload」+
  「没被构建链消费」——这是**还没被用掉的货架**。
- 货架里 **71 个**可以直接接进复刻：
  - **30 个 `asset-direct`**：payload 就是 remake 资产管线能读的字节（像素／图块／调色板／LZ77／音频）；
  - **41 个 `table-direct`**：payload 是内容表，接入只需一个生成器。
- 剩下 63 个不是「没用上」，而是**本来就不是可导入素材**：
  51 个 `analysis-only`（控制流／覆盖分母／审计证据）＋ 12 个 `unclassified`（要人读）。
- notes 侧已有现成分桶：**333 条 `needs_guard`**（原版结论已闭合、尚未转成门禁），
  其中 **314 条连测试都没引用过**。
- ⚠️ **但「可用」不等于「已闭合」**：货架里只有 **3 个** manifest 的 `scope` 全部为真；
  **69 个**明确写着未闭合声明（最常见是 `runtime_reachability_complete`、
  `global_caller_denominator_complete`）；**62 个**根本没写 `scope`。

⇒ **对复刻的直接结论：不要再去逆向侧「补分析」来解 S49 的像素差异。
已经闭合、可以立刻接线的成果有 71 个；S49 当前缺的那几样（覆盖层图块、状态栏、
对白表、调色板、场景合成）全都在这 71 个里面。**

## 1. 与既有测量的区别（不要混用两个数字）

| 测量 | 工具 | 回答的问题 | 本轮读数 |
| --- | --- | --- | --- |
| 差异清单 | `tools/measure_butano_reverse_gap.py` | 「有没有被引用」 | 成果族 `build` 93 / 264 = 35.2% |
| **本轮货架** | `tools/measure_butano_usable_backlog.py` | 「**能不能直接用**」 | 货架 134；可直接用 **71** |

两者的分母相同、口径不同。「被引用」既不等于「已使用」（文档提及不算），
也**不能**推出「没用上」——`build` 之外的 171 个族里，有 **134** 个是「已闭合且带
payload」的结果，其中 **71** 个可以直接接。

## 2. 口径（全部由脚本实测，无人工名单）

```
population : index entries with kind == "artifact"                    → 264
accepted   : manifest artifact_status == "accepted"                   → 201
has_payload: 至少一个非空文件，且不是 manifest.json / inputs.json / .gz 收据
consumed   : 差异清单 status == "build"                               →  93
shelf      : accepted and has_payload and not consumed                → 134
```

分层的判定：

| 层 | 判据 | 族数 |
| --- | --- | ---: |
| `asset-direct` | payload 含 `.png/.4bpp/.8bpp/.bgr555/.lz77/.s3m/.wav` | 30 |
| `table-direct` | JSON 顶层键命中**表词表**且不命中**结构词表** | 41 |
| `analysis-only` | 不命中表词表，且命中结构词表或覆盖词表 | 51 |
| `unclassified` | 同时命中表与结构，或都没命中 | 12 |

三套词表都写在 `tools/measure_butano_usable_backlog.py` 顶部，每个族的判定证据
（命中了哪些键、哪些文件）都写进 `artifacts/butano-usable-backlog-v1/backlog.json`，
可逐行复核。

> **为什么要把「覆盖分母类键」和「控制流结构类键」分开**：
> 几乎每个 ROM 侧结果都带 `coverage_baseline` / `literal_denominator` /
> `non_claims` 这些键——那是逆向项目**自己**的记账，不是 payload。若让它们参与
> 计数，一个内容表会被记账键投票投成「分析类」：`rom-battle-sound-selector-v1`
> （64 个音效 ID 的 256 字节表）就是这么被错投的。**记账键不得否决内容判定。**
> 反过来，`cfg` / `roots` / `code_ranges` / `literal_ranges` 这类描述 payload
> **自身控制流**的键必须否决——同时命中表与结构的判为 `unclassified`，不硬猜。

## 3. 抽查发现的三处错分（本轮已改口径，记录留档）

分诊不是「跑完脚本就算数」——本轮按 §6 的纪律**逐族打开 payload 复核**，
发现三处错分并已改口径：

1. **`archive` 被当成表键** → `battle-effect-group15-allocator-side-runtime-v1`
   被判成「内容表」。实际 `archive` 是该成果自己的文件清单（记账），
   该族实为**运行期证据**。⇒ `archive` 移出表词表。
2. **`gaps` 被当成分析键** → `rom-alternate-dialogue-table-v1`（80 条对白记录）
   的内容正好在 `gaps` 里，被投票投成「分析类」。⇒ `gaps` 移出分析词表。
3. **记账键参与计票** → `rom-battle-sound-selector-v1`（256 字节音效选择表）、
   `rom-directsound-pitch-lookup-v1`、`rom-psg-frequency-lookup-v1`、
   `rom-u8-indexed-u8-triplet-lookup-v1` 全被投成「分析类」。
   ⇒ 拆成结构词表（否决）与覆盖词表（不否决）两套。

复核样本：asset-direct 抽 6、table-direct 抽 6、analysis-only 抽 6，
逐个打开 payload 看内容。**6/6 + 6/6 命中，analysis-only 6/6 确为代码切片与覆盖投影**
（例：`rom-mp2k-note-allocator.bin` 562 B 是代码字节，不是素材）。

> **教训**：`keyword 词表探针` 只能给出**一审**结论。本轮三处错分全部出现在
> 「哪个键代表什么」这一层，而不在「键有没有命中」这一层。
> **词表必须能被 payload 反证**：改完词表要回到具体族上核对，
> 否则「样本抽得对」掩盖不了「词表是错的」。

## 4. 货架里可直接用的 71 个（按复刻子系统归位）

| 复刻子系统 | 成果族 | 说明 |
| --- | --- | --- |
| **移动网格覆盖层** | `overview-gradient-overlay-v1` | `generated-tiles.4bpp.bin` + `generated-tilemap-30x20.bin` + 调色板 —— **正是 S49 第 26 轮施工单 ①②③ 步要的东西** |
| 状态栏 | `battle-status-bars-v1` | 状态栏 PNG + `generated-family.4bpp.bin` + `runtime-palette-bank13.bgr555.bin` |
| 对白／文本 | `rom-alternate-dialogue-table-v1`（80 条对白文本 + 表）、`rom-dialogue-text-inventory-v1`、`rom-renderer-text-inventory-v1`（+22 KB 文本字节）、`rom-display-text-delta-v1` | 文本是重制侧「字模/文本」最缺的原料 |
| 调色板 | `rom-menu-portrait-palette-inventory-v1`（**70 个 128 B 物理调色板**）、`portrait-palette-producers-v1`、`lz77-palette-runtime-v1` | 调色板逐号同色是像素等价的必要条件 |
| 场景／地图 | `scene-visual-composites-v1`（10 张 240×160 合成图）、`runtime-bg-composites-v1`、`runtime-screen-composites-v1`、`map41-visual-resource-matrix-v1` | 背景合成与图层 |
| 战斗特效帧 | `battle-effect-frame-phase-group{1,2,3,4,5,14,16,17,18}-v1` + `battle-effect-frame-phase-v1`（10 族，各带 `capture.png` 240×160 + VRAM/OAM/PRAM dump + `.ss9`），另有 `battle-effect-group12-ai-observer-v1`、`group13-natural-runtime-v1`、`group18-natural-checkpoint-v1` | **像素基准 + 硬件状态**，可直接当 1:1 验收基准 |
| OAM／精灵绑定 | `character-runtime-oam-bindings-v1`（2.4 MB）、`battle-effect-runtime-oam-bindings-v1` 等 4 族 | 精灵/特效的运行时绑定关系 |
| 音频 | `rom-battle-sound-selector-v1`、`rom-directsound-pitch-lookup-v1`、`rom-psg-frequency-lookup-v1` | 音效 ID 与音高/频率表 |
| 像素基准（A/B） | `levels-status-per-level-ab-v1`、`cutscene-obj-id1-primary-ptr-ab-v1`、`sappy-engine-master-enable-ab-v1` | `baseline.png` + `candidate.png`，与已导入的 32 个 pixel-A/B 族同一形态 |

## 5. 与 S49 当前在飞工作的关系

S49 第 26 轮末的下一步是「读重制侧 VRAM，核对 ① 槽 77..100 图块字节 ② 可见窗口
30×20 tile index ③ 8bpp 上传长度/基址对齐」，而**原版那一侧的图块、tilemap、调色板
早就闭合了**：

- `overview-gradient-overlay-v1` 里就有原版覆盖层的 `generated-tiles.4bpp.bin`、
  `generated-tilemap-30x20.bin` 与调色板；
- `rom-pointer-lz77-graphics-v1` 里有按地址导出的 LZ77 图形 PNG；
- `battle-status-bars-v1` 里有状态栏的 4bpp 图块与 bank13 调色板。

⇒ **S49 的残差 2,917 像素不是「逆向不够」，是「接线没做」**。这条结论与
第 26 轮末的否证（接线越接越差 ⇒ 2,917 → 16,533）不冲突：那否证的是**接线方式**，
不是**成果可用性**。

## 6. 边界声明

- 分母 264 / 201 / 93 / 134 / 71 全部由脚本从当次索引与差异清单重算，
  **读数必须来自当次收据**，不得写死；逆向树一变，分母就变
  （上一次分母修正见 `docs/butano-reverse-gap-roadmap.md` §7.7：262 → 264）。
- 分层是**词表探针**的一审结论，不是逐族人工判定；每个族的判定证据都在收据里。
  `unclassified` 的 12 个族是**有意不做判定**的，要人读。
- 「可直接用」只描述**导入成本**（一次生成器 / 一次复制），
  **不代表结论已闭合**。`scope` 里的未闭合声明（多数是运行期可达性）单列在收据里。
- 本轮**没有**把任何成果接进复刻构建链；本轮只做**测量与分诊**。
  货架的清空是后续工作。

## 7. 复现

```bash
/usr/local/bin/python3 tools/build_reverse_results_index.py \
    --reverse-root /Users/altair/github/gba-naruto-reverse \
    --out-dir artifacts/reverse-results-index-v1
/usr/local/bin/python3 tools/measure_butano_reverse_gap.py \
    --root . --index artifacts/reverse-results-index-v1/index.json \
    --out-dir artifacts/butano-reverse-gap-v1
/usr/local/bin/python3 tools/measure_butano_usable_backlog.py \
    --root . --index artifacts/reverse-results-index-v1/index.json \
    --gap artifacts/butano-reverse-gap-v1/gap.json \
    --out-dir artifacts/butano-usable-backlog-v1
```

收据：`artifacts/butano-usable-backlog-v1/{backlog.json,backlog.md}`
门禁：`tests/test_measure_butano_usable_backlog.py`（20 项全绿）

### 7.1 ⚠️ 本轮踩到并修掉的一个自指坑（重要）

新写的货架收据 `artifacts/butano-usable-backlog-v1/backlog.json` **在每行里点名了
全部 264 个族**。它落在 `artifacts/` 扫描根下，于是 `measure_butano_reverse_gap.py`
下一次运行会把它当成**引用** ⇒ 读数从 `build 373 / doc 512 / local_artifact 3`
漂到 `build 373 / doc 355 / local_artifact 174`（**174 个族被凭空抬成
`local_artifact`**）。

**症状不是「数字变了」，是「连跑两次读数不一样」**——只跑一次根本发现不了。

⇒ 已把 `artifacts/butano-usable-backlog-v1/` 加进 `measure_butano_reverse_gap.py`
的 `EXCLUDED_PREFIXES`，并补了一条红测
（`tests/test_measure_butano_reverse_gap.py::test_the_usable_backlog_receipt_is_not_a_reference`）。
修复后**连跑三次读数逐字节一致**（`sha=4760c2ab1738…`）。

> **教训**：任何新写的**逐族枚举**收据都会污染全树引用测量。
> 判定标准很简单：**这份文件是不是把被测总体列了一遍？** 是 ⇒ 必须进排除表。
> 差分清单工具的 docstring 早就写了这���，但**新收据会不断长出来**，
> 排除表必须跟着更新，否则测量会静默漂移。

> 附带发现：仓库里已提交的 `gap.json` 是 **2026-10-20T18:11** 生成的，
> 2026-10-21 的合并笔记（`notes/master-merge-20261021.md` 等）落盘后
> 它就**过期了**。本轮重算把读数拉回当轮事实（`build` 372 → 373）。
> 这正是「分母随上游树变 ⇒ 读数必须由当次收据重算」那条规则的又一个实例。

### 7.2 回归核验

全量套件 `build/full-suite-r27c.log`：**Ran 2130，failures=23 / errors=116 /
skipped=27 / expected failures=5**（基线 `build/full-suite-r26b.log` 为 2109/23/116/27/5；
+21 = 本轮新增的 20 项货架门禁 + 1 项自指红测）。
**失败 ID 集合与基线逐行相同 ⇒ 无回归、无新失败。**

> ⚠️ **工具坑**：`tools/run_guarded.py` 用 `subprocess.PIPE` 收子进程输出，
> **不转发到继承的 stdout** ⇒ 把重定向写在外面
> （`run_guarded.py ... > log 2>&1`）会得到**只有守卫收据、没有测试输出**的空日志。
> 重定向必须挂在**被守卫的命令**上，或直接跑（实测守卫峰值 RSS 590 MiB，
> 远低于上限，套件本身不需要重活守卫）。

## 8. 建议的下一步顺序

1. **先接 `overview-gradient-overlay-v1`**（26 KB，manifest **没有写 `scope`**，即没有自报的
   未闭合项）：用原版已闭合的 4bpp 图块 + 30×20 tilemap + 调色板替换重制侧的程序化网格网，
   对着 S49 step-20 的 2,917 像素残差验收——门槛仍是「≤ 2,917 且任何一帧不得变差」。
2. **再接 `battle-status-bars-v1`** 与 `rom-menu-portrait-palette-inventory-v1`：
   状态栏与调色板是「像素等价」的必要条件，且这两族都有可复制的字节。
3. **然后是文本族**（`rom-alternate-dialogue-table-v1` / `rom-renderer-text-inventory-v1`）：
   重制侧的对白/文本还原是当前最大的内容缺口。
4. **10 个 `battle-effect-frame-phase-group*` 族**当作像素验收基准导入
   （与已导入的 32 个 pixel-A/B 族同一形态，导入器现成）。
5. **notes 侧**：333 条 `needs_guard` 里挑与上面 4 类子系统相关的转成门禁；
   剩下 314 条无测试引用的按 M5 分批消化。

## 9. 相关

- `docs/butano-reverse-gap-roadmap.md`（差异清单与 M0–M7 路线图）
- `docs/reverse-results-index/notes-index.md`（notes 五桶分类，436 个 note 文件）
- `docs/reverse-results-index/ledger.json`（复刻台账，29 条，`missing` = 0）
- `notes/s49-fidelity-handover-20261019.md`（S49 工作交接，§26 轮末的下一步）
- **`docs/butano-wiring-roadmap.md`**（接线补全执行路线图 W0–W5）
- `tools/measure_butano_reverse_gap.py`、`tools/measure_butano_usable_backlog.py`
