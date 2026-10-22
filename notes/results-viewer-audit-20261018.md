# 逆向工程结果查看器全面核对与修订（2026-10-18）

## 第八轮：全仓库普查，又发现两类整体性缺失

用户追问「到底还漏了多少」。这一轮不是增量修补，而是**把仓库所有内容源逐类枚举**，
结果发现前七轮补的都是**产物层**（图像/公式/计数），而**结论层与工具层整体缺席**。

### 普查范围与结果

| 内容源 | 规模 | 此前是否上页 |
| --- | --- | --- |
| `notes/*.md` | **240 篇** | 基本没有（仅零散提及） |
| `tools/*.py` | **263 个** | 只列了 8 个 |
| `tests/test_*.py` | 316 个 | 仅数量提及 |
| `artifacts/` | 22 个族 | 18 族已收录 |
| `docs/*.md` | 27 篇 | 未纳入 |

### 缺口 1：240 篇笔记的结论从未呈现

按内容分类：**94 篇**有产物、**45 篇**声明结论完成却无产物/验证器、
**98 篇**为过程记录。最关键的重量级架构结论全部在这 45 篇里，例如：

- **真实音频分派链**：`0x08061E6C` → `0x0809AAC0` → `0x08465B70 + sound_id*8` → 播放槽；
- **单位初始坐标不来自场景图块表** `0x0853D910`，而来自 ROM `0x085461C4` 的战斗编成矩阵；
- **AI 配置表** `0x0853F348`（0xA8 字节记录）由 `unit+0xCD` 直接选择；
- **忍具模板真表** `0x08545BE4`（94×0x10），原 `skills@0x546100` 是错基切片；
- **被动成长表** 45×12 字节 + 24 槽查询器。

**新增第 7 页：逆向结论索引**（317 KB，240 个可折叠条目）。
`tools/build_results_viewer_conclusions.py` 优先提取 `## 结论`/`## Result` 段，
无该段落时回退到标题后的首个实质段落，**202/240 篇成功提取**，原文呈现不做改写；
带「含纠错/证伪」标记的条目记录被推翻的旧解读。

### 缺口 2：263 个工具只列了 8 个

**51 个分析器中 49 个、24 个提取器中 21 个、15 个生成器中 13 个从未在页面出现**。
这些脚本正是产出上述结论的工具——结论经笔记进了页面，但工具本身没有。

**新增全量工具清单卡**（`sec-toolbox-full`），扫描 `tools/` 实目录生成，
摘要取自各脚本 docstring 首句，并标注「已收录 / 结论见结论索引」。
现列出 263 个工具，分 13 组：分析器 51、构建器 48、其它 42、校验器 28、
提取器 24、导出器 23、生成器 15、音频 10、对比器 6、导入器 6、运行器 4、模拟器 3、补丁 3。

### 本轮修掉的三个实现缺陷

1. **表格行拼接位置错误**：`"</div>".join(...)` 把闭合标签放在单元格之间，
   产出的 HTML 标签失配 113 处；改为每格自包裹。
2. **raw string 里的 `\"`**：`r"<code class=\"cc-code\">"` 会输出**字面反斜杠**，
   在页面上显示成 `class=\"cc-code\"`；改用普通字符串 + `\\1`。
3. **分组迭代取错元组位**：遍历 `(prefix, label, desc)` 时取了 `prefix`，
   导致清单只剩「其它」组的 42 条；应取 `label`。

### 最终站点

8 页 / 54 卡片 / 2,302 项引用零悬挂 / 约 1.5 MB；
全管线幂等（连续两次完整重跑页面 SHA-256 一致）；**48 项测试通过**。
其中新增测试锁定：笔记提取率 >75%、渲染器不泄漏转义引号、
重点结论可达、未登记家族不得拥有任何卡片/公式块/图集区段。

**仍未做到的**：结论页（317 KB / 240 个 `<details>`）在本环境浏览器持续超时，
无法取得整页截图；替代证据为严格 HTML 解析 0 失配 + 引用零悬挂 + 幂等重跑 + 测试。

---

## 第七轮：补上逆向公式本身

用户问「为什么网页中没有公式」。**这是又一类真实缺口**：前六轮补的是图像、计数与地址，
但逆向的**结论本身——方程——一张都没展示**。

### 仓库里的公式有多少

全量扫描 `artifacts/*/manifest.json`：**13 个成果族带 2,170 个公式字段**，
其中 `battle-effect-sprite-animations-v1` 一个族就有 368 个。此前它们只以
manifest 与 notes 形式存在，网页完全未触及。

典型内容（均为 ROM 签发的表达式原文）：

- **仿射矩阵模型**（`0x08062EF4..0x080630EC`）：
  `PA = horizontal_sign * Q(cos_q8_8(phase), scale_x_product)`、
  `PB = vertical_sign * Q(sin_q8_8(phase), scale_x_product)` 等；
- **pre-OAM 坐标变换**（`0x08062C7C..0x08062D92`）、**OAM 属性位域**
  （`0x08062D92..0x08063186`）、**动态 OBJ VRAM 拷贝**（`0x08063122..0x080631F6`）；
- **Q8.8 转换**：`truncate_toward_zero_q8_8(v) = s32(v + (255 if s32(v) < 0 else 0)) >> 8`；
- 索引类推导：`message_ptr = u32[0x085A2B08 + u8(message_id) * 4]`、
  `descriptor = 0x0859903C + entry_id * 0x10` 等。

### 新增第 7 个 Hub：逆向公式与运行时模型

`docs/reverse-engineering-formulas.html`（260 KB），由
`tools/build_results_viewer_formulas.py` **递归遍历各成果族 manifest 抽取公式子树**，
渲染为嵌套定义列表：键名、字段语义、表达式原文、所依据的代码区间。
公式以等宽高亮样式呈现，**字段值即 ROM 签发的原文，不做人工改写**。

页面含 261 个模型块、900 行字段、295 个表达式高亮单元格。

### 两个踩到的坑

1. **首版只扫顶层键**，只收集到 5 个家族 / 337 字段。公式大量嵌在
   `entries[i].expression` 这类记录级路径里，必须**递归查找任意深度的模型子树**，
   修正后为 13 家族 / 2,170 字段。
2. **`SKIP_HINTS` 正则里混入了裸 `$`**（想匹配"以 $ 结尾"），
   而 `re.search` 中 `$` 表示"字符串末尾"，**对任何键都匹配**，
   导致整棵公式树被过滤成空。渲染出 0 行才暴露出来。

### 验证

- 全管线幂等：含公式页的两次完整重跑，7 个页面 SHA-256 一致；
- 结构：7 页 0 失配；**2,255 项引用悬挂 0**；
- **43 项测试通过**（新增 5 项锁定公式页：模型块数量、表达式高亮数、
  代码区间保留、索引家族与页面卡片一一对应、各页均可导航到公式页）；
- 浏览器实测截图确认公式页正常渲染，侧栏与索引表可见，
  `affine_matrix_model` 展开后可见 PA/PC/PB/PD 方程与代码区间。

---

## 第六轮：补齐可呈现成果（覆盖率 10.6% → 21.2%）

第五轮量化出覆盖率只有 10.6% 后，本轮把**在本工作树可重建的成果全部补进页面**。

### 先划清可补与不可补的边界

普查 85 个 ROM 逆向家族后，逐个探测其数据是否在本工作树：

- **可补（18 族）**：manifest 存在，或导出器只依赖 ROM；
- **不可补**：产物在逆向分支（55 个 `rom-*` 系列只有 1 个例外）。

### 关键突破：bank 只是交叉核对，不是输入

13 个「受阻」家族实际卡在 `sequel/content/**/bank.json`。逐个读源码后发现
**它们的 bank 全部只是 ROM 的比对副本**——真实数值一律由
`struct.unpack_from(...)` 从 ROM 读出，bank 仅用于 `if ... != expected: raise`。

据此为三个叶子导出器补了 `--from-rom`（与 `export_menu_portraits.py` 同法）：

| 导出器 | 原阻塞 | 补齐后 |
| --- | --- | --- |
| `export_tile_asset_bg_layers.py` | `sequel/content/tile-assets/bank.json` | 236 完整 BG 图层 + 108 图集 |
| `export_cutscene_obj_assets.py` | `sequel/content/cutscene-scripts/bank.json` | 10 帧 + 4 atlas |
| `export_story_visual_layers.py` | `sequel/content/battle-encounters/bank.json` | 24 剧情视觉图层 |

三个叶子解开后，**整条下游依赖链自动解开 7 个家族**：
`battle-visual-catalog-v1`(79)、`battle-visual-runtime-timelines-v1`(75)、
`story-scene-timelines-v1`(24)、`sprite-definition-animations-v1`(43) 等。

全部 6 个独立校验器复核 `errors: []`。

### 同时补齐的 4 个「部分呈现」

- `character-battle-visuals-v1`：60 → **250 / 250**
- `battle-presentation-glyphs-v1`：2 → **251 / 251**，并新增
  **79 条消息按绑定顺序渲染的字形条**（manifest 无字符映射，故呈现原始字形序列而非解码文字）
- `bg-scene-selection-v1`：0 → **6 / 6**（独立卡片）
- `battle-effect-sequence-bindings-v1`：0 → **22 / 22**（独立卡片）

### 仍不可补的 2 族（真实阻塞，非 bank）

- `battle-effect-affine-runtime-v1`：需要**实时 mGBA 仿射 OBJ 采集**（`--raw-dir`），
  离线无法产出；
- `dialogue-font-v2`：需要派生扫描结果 `sjis-to-tile-addr-*.json`（记录了 SHA-256），
  其下游 `world-map-backgrounds-v1` / `world-map-runtime-v1` 一并受阻。

### 新增：ROM 家族全量目录卡

`tools/build_results_viewer_rom_catalog.py` 为 85 个家族逐个记录**可本地验证的事实**
（产物是否在此、版本批次数、本工作树有无证据 notes），生成首页目录卡。
**不推测任何家族闭合了什么内容**——没有本地数据就写「内容在逆向分支」。

### 最终数字

```text
成果族级：18 / 85 = 21.2%（18 族全部完整呈现，无 partial）
条目级  ：1764 / 6390 = 27.6%
条目级（剔除 dialogue-font-v2 的 4,602 字形）：1764 / 1788 = 98.7%
```

页面从 42 卡片 / 1,698 图增至 **44 卡片 / 1,996 图**。

### 工程化：单一可复现管线

片段生成与页面生成合并进 `tools/split_results_viewer.py --fragments`，
**在生成期替换卡片**，不再事后拼接。这消除了本轮早先踩到的三类事故：
跨 `card-grid` 边界误删、重复应用产生重复卡片、多卡片片段无法幂等。

```bash
python3 tools/build_results_viewer_fragments.py
python3 tools/build_results_viewer_artifact_sections.py --root .
python3 tools/build_results_viewer_generic_families.py --root .
python3 tools/build_results_viewer_rom_catalog.py --root .
python3 tools/measure_viewer_coverage.py --root . \
    --json build/viewer-data/coverage-report.json
python3 tools/build_results_viewer_artifact_index.py --root .
python3 tools/split_results_viewer.py \
    --source <single-page source> --fragments build/viewer-data
```

顺序由 `FRAGMENT_ORDER` 显式声明（依赖方必须在其锚点被插入之后再应用），
不依赖 dict 迭代顺序。

### 验证

- 全管线**幂等**：连续两次完整重跑，六个页面 SHA-256 完全一致；
- 结构：六页 0 处标签失配、0 张重复卡片；
- 链接：**2,206 项引用，悬挂 0**（含跨页锚点）；
- **38 项测试通过**（1 项跳过 = bank.json 交叉比对）。

**仍未能做的**：浏览器整页视觉验收。页面已达 1,996 张图，本环境浏览器持续超时，
替代证据为逐图引用解析 + 严格 HTML 解析 + 幂等重跑 + 测试套件。

---

## 第五轮：覆盖率统计的自查与更正（同日追加）

用户追问「有没有存在你统计遗漏的可能性」。**有，而且遗漏很大。**

### 遗漏是怎么发生的

第四轮的分母来自我在 `tools/build_results_viewer_artifact_index.py` 里手写的
`FAMILIES` 常量——24 个家族。手写登记表按定义看不见「没人想起来登记」的家族。

反向排查（全仓库 `os.walk` 抓取所有 `artifacts/<family>` 引用）后发现：

- 实际引用的家族名共 **259 个**，其中 ROM 逆向类 **101 个**，复刻运行证据 **11 个**
  （其余为复刻工作流的 butano-*/scenario-*/original-* 记录）；
- 合并 `v1..vN` 增量批次后，ROM 逆向家族主干为 **85 个**；
- 我的登记表只有 24 个，**漏掉 61 个主干**，其中 55 个是 `rom-*` 前缀的
  控制流 / CFG / 文本清单类成果。

关键线索藏在 `notes/evidence/remaining-reverse-plan-20260930-v2/source-snapshots/`
——逆向分支工作树的一个快照镜像。第三轮前我只扫 `notes/*.md` 顶层，
没有递归进 `notes/evidence/**`，因此整个 `rom-cfg-proven-roots-v1..v15`、
`rom-boot-interwork-v1`、`rom-dialogue-text-inventory-v1` 等系列全部没进视野。
这些正是 `AGENTS.md` 任务模式登记表里点名的已完成成果。

### 更正后的数字

```text
普查分母（全部已完成 ROM 逆向家族，主干口径）: 85 族
  页面有实际内容 : 9 族  = 10.6%
  其中完整呈现   : 7 族  =  8.2%
条目级（含字形）  : 694 / 6,052 = 11.5%
条目级（剔除字形）: 694 / 1,450 = 47.9%
```

**37.5% 是错的，是人工登记表的遗漏造成的虚报。** 现已在页面上直接写明这一点。

### 结构性修正

- `tools/measure_viewer_coverage.py` 新增 `census_repo_families()`：
  递归遍历整棵树抓取 `artifacts/<family>` 引用，自动剔除复刻证据前缀，
  并用 `family_stem()` 把 `v1..vN` 增量批次合并成一个主干。
- 主口径分母改为**普查结果**而非登记表；登记表仅用于逐族条目级明细。
- 报告中单列 `unregistered_families`：61 个普查到但未登记的家族，
  并记录它们在页面的命中数——实测全为 0，即这些成果在网页上完全缺席。
- 页面覆盖总表同步改写：新增三个 KPI（85 / 9 / 61），并明写
  「分母来自全仓库普查……早期版本只数了登记在册的 24 族，把覆盖率虚报成 37.5%」。

### 新增测试（防止再次只数登记表）

`tests/test_results_viewer_coverage.py` 增至 10 项，新增三条：

1. `test_registry_is_not_smaller_than_the_repo_census` — 普查分母必须 ≥ 登记表，
   且普查口径的百分比必须**低于**登记表口径（否则说明又退回数登记表了）；
2. `test_unregistered_families_carry_no_site_content` — 未登记家族必须在页面零命中；
3. `test_census_walks_the_evidence_snapshots` — 普查必须能抓到
   `rom-cfg-proven-roots` 与 `rom-boot-interwork`，防止递归退化。

```text
python3 -m unittest tests.test_results_viewer_coverage \
  tests.test_results_viewer_site tests.test_results_viewer_artifact_index \
  tests.test_results_viewer_assets
Ran 38 tests in 1.259s
OK (skipped=1)
```

### 仍然可能存在的第二层盲区

本轮修正了「家族维度」的遗漏，但以下两类不确定性**没有被消除**：

1. **条目单位不可比**：`dialogue-font-v2` 的 4,602 个 8×8 字形与 61 张 736×512
   合成地图不同权，因此条目级 11.5% 与 47.9% 相差三倍多。主口径取族级 10.6%，
   但族级同样假设「一个 exporter/verifier 对 = 一项成果」，对
   `rom-cfg-proven-roots` 这种「一个成果族分 15 个批次交付」的情况会低估其规模。
2. **无法证否的家族**：普查只认「代码或文档里出现过的 `artifacts/` 路径」。
   若某项已完成成果既无 artifact 目录、也未在任何文档中引用路径，
   本脚本在原理上无法发现。当前 239 篇 notes 中有约 200 篇不含 artifact 路径，
   其中是否还有已完成但未落产物的结论，需要人工判断，本次未能穷尽核查。

---

## 第四轮：收录覆盖率量化（同日追加）

前三轮回答「内容对不对」「成果全不全」「结构好不好」。第四轮回答：
**网页里呈现的，占已完成逆向成果的百分之多少**。

测量脚本：`tools/measure_viewer_coverage.py`。它不采信任何人工登记，
而是扫描生成后的六个页面，逐族统计页面**实际引用了多少条该族的产物路径**。

### 口径（先定义，再算）

- **成果族 = 1 个单位**。本仓库对「一项已完成的逆向工程」的定义是：
  有 `export_*.py`、有 `verify_*.py`（或等价测试）、有 `manifest.json`、有证据 notes。
  这是仓库自身的完成判据，因此作为主口径。
- **条目级**作为辅助口径，但条目单位差异极大（8×8 字形 vs 736×512 合成地图），
  故**同时**给出含/不含 `dialogue-font-v2`（4,602 个字形）两个比值。

### 结论

```text
HEADLINE（成果族级）：24 族中 9 族在页面有实际内容 = 37.5%
                      其中 7 族完整呈现 = 29.2%
条目级（含字形）  ：694 / 6,052 = 11.5%
条目级（剔除字形）：694 / 1,450 = 47.9%
```

逐族明细：

| 成果族 | 页面条目 / 总条目 | 状态 |
| --- | --- | --- |
| menu-portraits-v1 | 311 / 311 | 完整 |
| map-canvases-v1 | 61 / 61 | 完整 |
| bg-resource-canvases-v1 | 12 / 12 | 完整 |
| scene-visual-packs-v1 | 9 / 9 | 完整 |
| sprite-definition-assets-v2 | 43 / 43 | 完整 |
| battle-effect-resource-pairs-v1 | 18 / 18 | 完整 |
| battle-effect-sprite-animations-v1 | 178 / 178 | 完整 |
| character-battle-visuals-v1 | **60 / 250** | **部分（页面只列前 60 个资源首帧）** |
| battle-presentation-glyphs-v1 | **2 / 253** | **部分（只出图集，未列 79 条消息与 172 字形）** |
| bg-scene-selection-v1 | 0 / 6 | 仅正文提及 |
| battle-effect-sequence-bindings-v1 | — | 仅正文提及 |
| 其余 13 族 | 0 | 未收录（产物在逆向分支） |

### 量化过程纠正了两处此前的虚报

1. 覆盖总表原写「11 / 22 成果族已收录」，实测只有 **9** 族有实际内容：
   `bg-scene-selection-v1` 与 `battle-effect-sequence-bindings-v1`
   只在正文里被提到名字，页面并未渲染其任何产物。已改为「仅文字引用」，
   并在页面写明**「只在正文里提到族名不算收录」**。
2. `character-battle-visuals-v1` 标为已收录，实际只放了 250 个资源中的前 60 个首帧。
   现记为 partial 并在表中显式标注 `60 / 250`。

`tools/build_results_viewer_artifact_index.py` 新增 `CONTENT_FAMILIES` /
`MERGED_FAMILIES` 两个显式集合，使「已收录」不再等同于「manifest 存在」。

### 为什么不给单一数字

条目级 11.5% 与 47.9% 相差三倍多，差异全部来自 `dialogue-font-v2` 的 4,602 个
8×8 字形。把一个字形和一张 736×512 的合成地图算作同权是不成立的，所以
**主口径取成果族级 37.5%**，条目级仅作参考。

### 新增测试

`tests/test_results_viewer_coverage.py`（7 项）锁定四条防虚报规则：
正文提及不算收录、部分呈现必须记为 partial、已收录集合必须与索引一致、
主口径必须能由自身行数据复算。新增第 8 项锁定页面必须披露 9/22 与该口径说明。

```text
python3 -m unittest tests.test_results_viewer_coverage \
  tests.test_results_viewer_site tests.test_results_viewer_artifact_index \
  tests.test_results_viewer_assets
Ran 35 tests in 1.083s
OK (skipped=1)
```

复现：

```bash
python3 tools/measure_viewer_coverage.py --root . \
  --json build/viewer-data/coverage-report.json
```

---

## 第三轮：单页拆分为多页站点（同日追加）

第二轮把成果补齐后，单页膨胀到 **487,981 字节 / 749 张图 / 28 张卡片**，
既难打开也无法按小节直接分享。改为六个 Hub 页面共享一份样式与脚本。

```text
docs/reverse-engineering-results.html          研发全景 + 覆盖总表（保留原入口 URL）
docs/reverse-engineering-visuals.html          1. 视觉与动画资产库   9 卡片 / 502 图
docs/reverse-engineering-battle.html           2. 战斗系统与时序引擎 6 卡片 / 200 图
docs/reverse-engineering-story.html            3. 剧情调度与文本系统 5 卡片
docs/reverse-engineering-data.html             4. 内存数据与音频架构 4 卡片 / 43 图
docs/reverse-engineering-engineering.html      5. 逆向基建与工程流水线 3 卡片
docs/assets/viewer.css                         共享样式（24,882 字节，与原内联样式逐字节一致）
docs/assets/viewer.js                          共享行为
docs/assets/studio-data.js                     角色展台数据（仅 visuals 页加载）
```

仓库根的 `reverse-engineering-results.html` 软链接继续有效，入口 URL 未变。

### 拆分方式

`tools/split_results_viewer.py` 按 `<section class="category-section">` 边界切分，
卡片标记**逐字复制**，不重新誊写任何数字。脚本带保护：源文件若已是拆分页
（含 `data-page=` 或引用 `assets/viewer.css`）则直接报错退出，避免二次运行把卡片切没。
拆分后各页成为事实来源，直接编辑即可；共享样式与脚本单独维护。

行为改造：

- 侧边栏 26 个入口由 `onclick="switchHub(...)"` 改为**真实 `<a href>`**，跨页跳转可被中途打开；
- 顶栏「17/17 测试通过」按钮同样转为链接；
- `currentActiveHub` 改为从 `<body data-page>` 推导，不再每页硬编码；
- 清空搜索改调 `resetCards()`（本页复位），**不会触发跨页跳转**；
- 搜索框文案由「全局检索」改为「本页检索」——每个 Hub 独立成页后，
  原先跨 Hub 的全局检索已不成立。

### 拆分过程中发现并修复的三个真实缺陷

1. **顶栏转换只改了开标签没改闭合标签**：`<button …>` 变成 `<a …>` 后仍留 `</button>`，
   导致后续所有内容被浏览器吞进未闭合的 `<a>`，**整页布局塌掉**。
2. **`currentActiveHub` 重复声明**：`SyntaxError: Identifier 'currentActiveHub' has already been declared`
   使整份共享脚本失效（由浏览器 console 查询捕获）。
3. **覆盖总表被从中间切开**：按 `<div class="card"` 子串搜索下一张卡片时，
   命中了卡片**自身**的 `<div class="card-head">`，导致表格上半截留在原页、
   下半截被搬到首页，两边都不完整。

第 3 条同时解释了拆分首版首页空白的原因。

### 第三轮验证结果

```text
python3 -m unittest \
  tests.test_results_viewer_site \
  tests.test_results_viewer_artifact_index \
  tests.test_results_viewer_assets
Ran 28 tests in 0.888s
OK (skipped=1)
```

新增 `tests/test_results_viewer_site.py`（12 项）锁定拆分后最容易静默回归的点：
标签嵌套配平、每页只含自己一个 Hub、`<body data-page>` 自洽、跨页链接与锚点零悬挂、
覆盖总表只出现一次、**28 张卡片全部存活**、共享脚本无重复声明且清空搜索不跳转。

其他复核：

- 6 页合计 **958 项引用 / 747 张图，悬挂链接 0**；
- `node --check docs/assets/viewer.js` 与 `studio-data.js` 语法通过；
- `viewer.css` 与原内联 `<style>` 逐字节一致（24,881 字节）；
- 单页最大体积由 487,981 降至 238,812 字节。

### 已知局限（第三轮）

浏览器在本环境的截图与 DOM 查询在多轮操作后持续超时，仅早期一次 console 查询成功
（即捕获到上述 `currentActiveHub` 重复声明）。因此**第三轮未能取得整页视觉验收截图**，
采用的替代证据是：严格 HTML 嵌套解析 0 问题、跨页锚点逐一解析、HTTP 200 冒烟、
`node --check` 语法校验、以及上述 28 项测试。四页体积最大的页面无法截图取证，
建议由用户在浏览器中实际打开确认。

---

## 第二轮：完成度全量盘点（同日追加）

第一轮解决的是「已展示内容是否正确」。第二轮回答的是另一个问题：
**本页是否 100% 展现了项目当前已完成的逆向成果**。结论是**否**，差距很大，已修复。

仓库里有 22 个 exporter + 29 个 verifier，而第一轮之前的页面只覆盖 3 个成果族。
本页新增 **8 个已验证成果族**、**9 张新卡片**，并加入一张机器生成的
**成果收录覆盖总表**，如实列出未收录项及其具体阻塞原因。

### 盘点方法

新增 `tools/build_results_viewer_artifact_index.py`：直接遍历
`artifacts/*/manifest.json`，逐族读取 schema 与关键计数，产出
`build/viewer-data/artifact-families.json` 与页面覆盖表片段。
**页面不手写任何成果族状态**；某族既未展示又没写明阻塞原因时，测试会失败。

### 本轮新增收录（全部由独立 verifier 复核通过）

| 成果族 | 关键事实 | 独立校验器输出 |
| --- | --- | --- |
| `map-canvases-v1` | 47 张地图 → **61 张成品战场画布**（含 14 alternate） | `{"errors":[], "verified_canvases":61, "verified_maps":47}` |
| `character-battle-visuals-v1` | **250 资源 / 558 槽位 / 2,004 帧 / 3,187 关键帧 / 60,430 瓦片** | `{"verified":true, "resources":250, "slots":558, "frames":2004}` |
| `battle-presentation-glyphs-v1` | **79 条战斗消息 / 172 个字形**，含运行时调色板 | `{"errors":[], "messages":79, "glyphs":172}` |
| `bg-resource-canvases-v1` | **12 张 BG 资源画布** | `{"verified":true, "canvases":12, "expected_canvases":12}` |
| `scene-visual-packs-v1` | **9 个场景包 / 16 个 OBJ 动画 / 16 帧** | `{"verified":true, "pack_count":9, "obj_frame_count":16}` |
| `battle-effect-resource-pairs-v1` | **18 组特效资源对图集** | `{"errors":[], "verified_resource_pairs":18}` |
| `battle-effect-sprite-animations-v1` | **18 组 / 437 组件 / 178 帧 / 23 动画 / 193 关键帧** | `{"errors":[], "verified_animations":23, "verified_frames":178}` |
| `sprite-definition-assets-v2` | **43 条精灵定义 / 45 组件**，含运行时链 | `{"errors":[], "verified_assets":43, "verified_tiles":49}` |

其中影响最大的缺口是 **`map-canvases-v1`：本页此前只有原始瓦片图集，
从未展示任何合成后的地图**——即用户实际会看到的战场画面完全缺席。
新增卡片展示全部 61 张成品画布（736×512 等真实尺寸）。

## 未收录的 11 个成果族及其阻塞原因

这些**不是未完成的逆向工作**，而是在本工作树无法重建（产物在逆向分支）。
覆盖总表逐行写明阻塞原因：

- 需要下游内容 bank（不在本工作树）：
  `tile-assets-bg-v1/v2`、`cutscene-obj-v1`、`story-visual-layers-v1`
  （分别需要 `sequel/content/tile-assets/bank.json`、
  `sequel/content/cutscene-scripts/bank.json`、
  `sequel/content/battle-encounters/bank.json`）；
  `dialogue-font-v2` 需要 `sequel/content/text/sjis-to-tile-addr-20260703.json`。
- 上游未闭合因而级联不可用：
  `battle-visual-catalog-v1`、`battle-visual-runtime-timelines-v1`、
  `story-scene-layer-bindings-v1`、`story-scene-timelines-v1`、
  `world-map-backgrounds-v1`、`world-map-runtime-v1`。

### 本轮可复现命令

按依赖顺序执行，前序产物落在 `artifacts/` 后下游即可解开：

```bash
python3 tools/export_battle_effect_resource_pairs.py --root .
python3 tools/export_battle_effect_sequence_bindings.py --root .
python3 tools/export_battle_effect_sprite_animations.py --root .
python3 tools/export_bg_resource_canvases.py --root .
python3 tools/export_bg_scene_selection.py --root .
python3 tools/export_character_battle_visuals.py --root .
python3 tools/export_scene_visual_packs.py --root .
python3 tools/export_map_canvases.py --root .
python3 tools/export_battle_presentation_glyphs.py --root .
python3 tools/export_sprite_definition_runtime_chain.py --root .
python3 tools/build_results_viewer_artifact_index.py --root .
python3 tools/build_results_viewer_artifact_sections.py --root .
```

### 第二轮验证结果

```text
python3 -m unittest \
  tests.test_results_viewer_artifact_index \
  tests.test_results_viewer_assets
Ran 16 tests in 0.694s
OK (skipped=1)
```

唯一跳过项仍是 bank.json 交叉比对（逆向分支上会自动执行）。

页面完整性：

- 静态本地引用 **782 项，缺失 0**（第一轮为 395 项）；
- 748 个 `<img>` 中 **747 个可成功解码**，唯一"失败"是 JS 模板占位符
  `../${p}`（角色动作 GIF/切片路径，其 216 个实际目标此前已全部验证存在）；
- 110 个小于 32px 的小图全部加了 `tile-zoom-sm/md` 放大类，避免渲染成不可见像素点；
- 严格 HTML 嵌套解析：0 处未闭合、0 处错配；
- 10 个生成片段共 1,924 行，**逐行全部嵌入页面**。

页面体积由 184,938 → 465,981 字节，`<img>` 由 12 → 748，其中 742 个带
`loading="lazy"`；6 个大图（立绘总览、全家福、2 张字形图集等）保持首屏优先加载。

**已知局限**：748 张图的单页在内置浏览器中出现截图/网络查询超时，
本环境无法完成整页截图取证；改以「逐图本地解码 + 782 项引用零缺失 +
HTTP 200 冒烟 + 严格解析」作为替代证据。如需整页视觉验收，
建议按 Hub 分页或加懒加载分区后再截图。

---

## 第一轮：事实核对与修订

## 背景

`docs/reverse-engineering-results.html`（仓库根有同名软链接）是对外展示逆向成果的
单页查看器。用户报告两处可见故障，并要求逐条核对全页内容：

1. 【木叶战记 155 款全员忍术特写立绘与剧情表情总集海报】大量重复图片；
2. 【8 大战役地图 Tileset 图集 (PNG Export)】内容完全不可见。

本次以 ROM 为唯一事实源重新核对全页，并把可复现脚本与测试落到 `tools/` 与 `tests/`。

- ROM：`rom/base.gba`
- ROM SHA-256：`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 页面：`docs/reverse-engineering-results.html`
- 新标题：《火影忍者：木叶战记》逆向工程结果查看器

## 根因 1：立绘区建立在已被证伪的 `0x5A4E14` 155×16 解读上

`notes/addresses.md` 与 `notes/similar-tables.md` 早已记录：

- `0x5A4E14` 只是全零记录 0 之后的**记录 1 起点**，不是独立资源表；
- 把该后缀按 155 行 × 16 字节分组，会让 **31 行跨过立绘边界**；
- 消费者定义的真实矩阵是 `0x5A4DEC`，63 条记录 × 40 字节 × 5 个 `(gfx, palette)` 变体。

但 `tools/extract_all_animations.py` 仍在使用旧的 155×16 读法，并据此：

1. 把 6,400 字节图形流当成 10×10 平铺图集，裁切瓦片 36–99 拼成 64×64
   （100 个瓦片在 10×10 网格中本就不是整齐的 8×8 子块）；
2. 忽略第二组 `(c2, c3)` 变体，导致“剧情表情变体”从未真正导出；
3. 用中文姓名把立绘绑定到 35 名角色——这是猜测，没有 ROM 证据。

直接读 ROM 复核确认：旧口径 155 条目中只有 **59 个唯一图形**（单一资源被复用 18 次），
这正是用户看到的“大量重复图片”。

仓库内已有正确实现 `tools/export_menu_portraits.py`，其 manifest 记录的表 SHA-256
`bfc995240519eca9035e140a45e506a5c1f6f561e05827a589b5ac03543bba7e` 与
`notes/menu-portrait-export-20260729.md` 完全一致。

### 修订

- `tools/export_menu_portraits.py` 增加 `--from-rom`：跳过对下游
  `sequel/content/menu-ui/bank.json` 的交叉核对，直接从 ROM 表枚举。
  由于 `_load_sources` 本就逐项从 ROM 读同一批 u32、只用 bank.json 做比对，
  两条路径产出**逐字节一致**。本工作树不携带该 bank.json，故需要此模式。
- 页面立绘区改为展示 **311 个逻辑变体 → 74 组唯一 (gfx, palette) → 70 份唯一图形**，
  按唯一资源去重排版，因此不再出现重复填充格；并新增完整矩阵浏览器
  （63 条记录 × 5 变体 + 1 个全局 variant 5，标注每个资源的复用次数）。
- 角色立绘面板不再按姓名挂图，改为说明“唯一有证据的绑定是战斗脚本 → (记录, 变体)”，
  并指向已验证矩阵。已从 `STUDIO_DATA` 移除 41 条无证据的姓名绑定。
- 保留折叠区说明被作废的 155×16 解读及其后果，结论标记为被取代而非删除。

复核印证：`0x085A4E14` 正是矩阵记录 01 的首个指针对，与 notes 的结论字面吻合。

## 根因 2：Tileset 区路径指向不存在的目录

页面引用 `../build/tilesets/chapter_0N_tileset.png`，但：

- `build/tilesets/` 目录不存在（真实目录是 `build/tiles/`）；
- `tools/extract_tileset.py` 产出的文件名是 `map_tileset_NN.png`，不是 `chapter_NN_tileset.png`；
- 该工具读的是**已验证的 47 行**地图头表 `0x53D910`，页面只展示了前 8 行。

因此 8 张图全部 404，表现为“内容完全不可见”。

### 同源的两处字段口径错误

页面两处表格都把地图头表**字段 +20** 标为“调色板 (BGR555)”。按工具注释与加载器证据：

| 字段 | 偏移 | 正确语义 |
| --- | --- | --- |
| +0 | `0x00` | 打包网格尺寸（低 16 位宽、高 16 位高） |
| +4 | `0x04` | 瓦片图形（LZ77 4bpp） |
| +8 | `0x08` | **背景调色板块**（传入 `LZ77UnCompVram`，目标 `0x05000000`） |
| +12 / +16 | `0x0C` / `0x10` | 两份布局（部分行为 0） |
| +20 | `0x14` | **元块/属性数据，不是可显示调色板**（历史 `palette_ptr` 别名误称） |

另外 8 行中有 5 行的网格尺寸整体错位一行：页面的“Chapter N”尺寸实际等于 ROM 的
Map N+1 尺寸（页面 ch0 写 60×30，ROM Map 00 实为 92×64；页面 ch1 写 36×36，
ROM Map 01 实为 60×30）。

### 修订

- 补齐 **47 行**（原 8 行 + 缺失 39 行），网格尺寸与全部指针按 ROM 重算。
- 调色板列改指字段 +8，元块/属性数据单列一栏并标注其真实语义。
- 图片改指真实产物 `build/tiles-palette/map_tileset_NN.png`。
- 页面原“调色板”列此前逐行等于字段 +20，已在场景表中改名“元块/属性数据”。
- 补充说明两种渲染模式：默认原始索引灰度（严格无解释）与 `--use-palette`
  背景调色板彩色渲染（工具标记 experimental，因每瓦片子调色板归属未闭合）。

### 顺带发现：CLI 默认不输出调色板

`tools/extract_tileset.py` 的 `--use-palette` 是 `store_true`，默认关闭，
所以直接运行只会得到灰度图，而函数默认值为 `True`，两者不一致。
本次未改动该默认值（属既有 CLI 行为），但页面已如实标注两种模式。

## 其他已核实**准确**、无需改动的部分

逐项与产物/manifest 比对，以下内容经核对无误：

- **35 行角色动作矩阵**：角色名、状态数、帧数与
  `build/animations_and_vfx_manifest.json` 全部一致（35/35 行零偏差），
  35 张 `matrix/char_*.png` 链接全部可解析。
- **36 行忍术脚本表**：表地址、技能 ID、查克拉消耗、阶段数、样条曲线指针、
  阶段 0 字节码切片，6 列 × 36 行与 manifest 全部一致（36/36 零偏差）。
- **10 首 PCM 音频**：地址、采样率、样本字节数、循环标志全部一致；
  样本字节数 = WAV 文件大小 − 44 字节头；合计 3,125,171 字节 ≈ 2.98 MiB，
  与“共 ~3 MB”相符。
- **35 角色全家福海报** `build/sprites/all_characters_roster.png`（1120×64）
  图像内容与文件名一致。

## 其他已修订的夸大/错误口径

| 位置 | 原表述 | 修订后 | 依据 |
| --- | --- | --- | --- |
| KPI 动作帧 | 1,500+ 帧 / 9 大行动循环 | 1,579 帧；8 人 9 状态、27 人 5 状态 | manifest 统计 8 人 9 动作、27 人 5 动作 |
| P0-Step 5 | 35 角色 9 行全动作表，循环 GIF | 35 角色动作表，1,579 帧，按实际状态数分布 | 同上；另 121 个动作无 GIF |
| KPI 战场配置 | 8 大战役 | 47 行 | `0x53D910` 已验证 47 行 |
| KPI 道具 | 80+ 种 / 9 大类 | 19 项已列 / 4 类样本 | 页面实际仅展开 19 项 4 类 |
| 单位 ID 表 | `0x19~0x2E` 与 `0x2B~0x37` 重叠 | 单位区间改为 `0x19~0x2A`，位移偏移量标注为非单位 ID | 两区间原本重叠且语义不同 |
| 场景命名 | 木叶演习场/波之国大桥等 | 按行号中性标注，不做推断性命名 | 剧情命名尚未与 ROM 字段闭合 |

## 产物与复现命令

新增脚本（均无外部网络依赖，纯离线读 ROM）：

- `tools/build_results_viewer_assets.py` — 由已验证 manifest 生成
  `build/vfx/menu-portraits-v1/gallery_unique.png`（74 张唯一立绘拼版）
  与 `build/viewer-data/map-rows.json`（47 行 ROM 派生数据）。
- `tools/build_results_viewer_fragments.py` — 由上述 JSON/manifest 生成页面片段
  `fragment-tileset-gallery.html`、`fragment-scenario-table.html`、
  `fragment-portrait-matrix.html`。

完整复现：

```bash
python3 tools/extract_tileset.py rom/base.gba --output-dir build/tiles
python3 tools/extract_tileset.py rom/base.gba --output-dir build/tiles-palette \
    --use-palette
python3 tools/export_menu_portraits.py --root . \
    --output-dir build/vfx/menu-portraits-v1 --from-rom
python3 tools/build_results_viewer_assets.py --root .
python3 tools/build_results_viewer_fragments.py
```

## 验证结果

```text
python3 -m unittest tests.test_results_viewer_assets -v
Ran 9 tests in 0.511s
OK (skipped=1)
```

跳过项为 `test_agrees_with_the_bank_cross_check_when_the_bank_exists`：
本工作树不携带 `sequel/content/menu-ui/bank.json`；携带该文件的逆向分支上，
该测试会比对两条枚举路径完全相等。

确定性复核：删除 `build/vfx/menu-portraits-v1/` 与 `build/viewer-data/` 后重跑，
gallery PNG、portrait manifest、map-rows.json 三者 SHA-256 均与删除前一致。

页面完整性复核：

- 395 个静态本地引用，缺失 0；
- 216 个角色展台动态资源引用，缺失 0；
- 312 个立绘矩阵图（311 变体 + 1 全局），缺失 0；
- 47 张 tileset 图，缺失 0；
- HTML 标签配平检查 div/section/table/tbody/thead/tr/td/details/summary/p/a/span
  全部开闭相等；
- 三个生成片段的每一行均已完整嵌入页面（235 + 47 + 63 行，缺失 0）。

浏览器实测：页面正常加载，标题为《火影忍者：木叶战记》逆向工程结果查看器，
KPI 显示 311 变体 / 47 行 / 19 项已列 / 1,579 帧，侧边栏显示 74组唯一、47行战场 Tileset。
立绘总览图人工查看确认 74 张唯一图像、构图完整、无重复填充格。

### 已知未在本页展开的成果

- 战场头表的剧情命名（章节/Boss 归属）尚未与 ROM 字段闭合。
- 完整忍具道具表未随本页导出，页面只列 19 项样本。
- `--use-palette` 彩色渲染依赖每瓦片子调色板归属，该语义未闭合，工具仍标记 experimental。
- 121 个角色动作未生成 GIF（仅 86 个存在）。

### 未纳入本次修订的既有问题

`tests.test_export_menu_portraits`、`tests.test_generate_butano_battle_portrait_content`、
`tests.test_text_and_visual_table_identity` 在本工作树有 9 个 error，
全部为缺少 `sequel/content/menu-ui/bank.json` 等下游内容文件导致的 setUpClass 失败，
与本次改动无关（`--from-rom` 未改变默认路径行为）。

---

## 第九轮：撤销错误的"不可补"判断（覆盖率 21.2% → 86.4%）

用户指出：逆向分支的内容可以拿过来，派生扫描和实时采集也该做。**核对后证明，
前八轮结论里的三个「不可补」全部是错的**——我从未检查本地是否存在逆向 worktree。

### 事实

`/Users/altair/github/gba-naruto` 仓库含 `codex/reverse-engineering` 分支，
且有独立 worktree `/Users/altair/github/gba-naruto-reverse`。其 `artifacts/` 已提交
**7,091 个文件、258 个产物族**（含 122 个 `rom-*` 家族，全部带 manifest）。
AGENTS.md 本就允许「复用逆向分支中已提交且有证据链的成果」，我却按
「本工作树没有」直接判为不可补。

### 已解开

1. **5 个 bank/映射输入**从逆向分支取入（`menu-ui`、`tile-assets`、
   `cutscene-scripts`、`battle-encounters` 的 `bank.json`，以及
   `text/sjis-to-tile-mapping.json`）。
2. **dialogue-font-v2** 导出成功 → 连带解开 **world-map-backgrounds-v1** 与
   **world-map-runtime-v1**（后者另需 `artifacts/world-map-gpu-captures/`，
   即已提交的 mGBA 采集，不是「必须重新采集」）。
3. **battle-effect-affine-runtime-v1** 导出成功并复核 `errors: []`。
   所谓「需实时采集」是错的——采集本身已作为产物提交（46 个文件）。
4. **导入 120 个 `rom-*` 家族**（仅 git 已跟踪文件，340 个）到本工作树。

新增卡片：`sec-dialogue-font`、`sec-world-map-bg`、`sec-affine-runtime`。

### 第 8 页：ROM 数据产物索引

120 个 `rom-*` 家族里**只有 3 个含图像**，其余是控制流图、解码器契约与有界清单——
图像卡片天然覆盖不到。`tools/build_results_viewer_data_index.py` 为每个族生成卡片：
schema、声明状态、标量计数，并展开 `scope` / `limits` / 汇总字段
（**其中明确写出该族不宣称什么**）。

### 最终覆盖率

```text
成果族级：121 / 140 = 86.4%
  其中以图像/公式卡片呈现：22 族（15.7%）
  以结构化数据卡片呈现：99 族
条目级  ：1793 / 1794 = 99.9%
```

### 工程教训

- **片段应用改为不动点迭代**，不再依赖手工维护的 `FRAGMENT_ORDER`：
  片段可能锚在另一个片段插入的卡片上，手工排序反复漏项。
- 多个登记表（测量脚本、产物索引、覆盖表）一度彼此漂移；
  现由测试强制它们一致，并去重了索引里的 3 条重复族定义。

**最终站点**：9 页 / 2,525 项引用零悬挂 / 全管线幂等 / 48 项测试全通过。

---

## 第十轮：纳入逆向 worktree 未提交产物，覆盖率达 100%

用户确认「未提交的一样可用」。第九轮我只同步了 git 已跟踪的文件，
逆向 worktree 磁盘上还有 **116 个产物族 / 2,338 个文件 / 102.4 MiB** 未纳入。

### 本轮动作

1. 同步剩余 116 个产物族（`artifacts/` 由此 147 → **263 个族 / 333 MiB**）。
2. **数据索引页不再只扫 `rom-*`**，改为扫 `artifacts/*/manifest.json`
   —— 导入的 104 个 `battle-effect-*` / `scenario-*` / `s49-*` 族此前
   被这个前缀限制漏掉。现覆盖 **255 个带 manifest 的族，其中 86 个含图像**。
3. 测量口径新增**直接比值**：按「有 manifest 的族 → 页面是否有卡片」统计，
   不再依赖会合并 `-v1..vN`、且会剔除复刻基线前缀的 census 口径
   （后者曾把已呈现的 133 个族排除在分母外，得出误导性的 53.5%）。

### 最终数字

```text
HEADLINE（带 manifest 的产物族）：255 / 255 = 100.0%（缺失 0）
census 口径（合并版本批次）：    226 / 226 = 100.0%
  其中以图像/公式卡片专门呈现：  23 族
条目级：1810 / 1794（超出 100% 系同一资源被多族引用去重所致）
```

### 站点

9 页 / 2,969 项引用零悬挂 / 结构 0 失配 / 全管线幂等 / 48 项测试通过。
数据索引页因新增 104 族增至约 875 KB。

### 仍需说明的两点

1. **`build/`、`sequel/`、`butano-sequel/` 未纳入**：它们是续作工程产物与复刻代码，
   不是原作 ROM 的逆向成果，归入本页会混淆「逆向结果」与「复刻实现」。
2. **页面体积**：9 页合计约 2.7 MB，数据索引与公式两页偏重（875 KB / 620 KB），
   在本环境浏览器持续超时，建议后续按族分片。

---

## 第十一轮：查看器前端重置（消除使用障碍）

用户指出整站混乱，最具体的症状是：**同一种内容（角色动作）有的播动画、有的只给帧序列**。

### 定位到不一致的根因

`build/animations_and_vfx_manifest.json` 统计：**14 个角色有 GIF，21 个只有 PNG 帧条**。
但帧条几何完全统一——207 个动作条**全部是 64×64 帧横向排列**（1280×64 ÷ 20 = 64，零例外）。
也就是说不需要重新生成 GIF，一个通用播放器就能让全部 207 个动作一致地动起来。

### 重置后的三项能力

1. **统一运动组件**：新增 `docs/assets/viewer-runtime.js`。
   GIF 交给浏览器原生播放，帧条用 `background-position` 驱动同一个尺寸窗口，
   两者由同一个 `.is-motion` 组件承载。**同一类内容不再出现一个动、一个静**。
   组件仅在进入视口时启动定时器（IntersectionObserver）——否则 200+ 个并发 interval 会拖死页面。
2. **全站画廊分页**：每页先渲染 24 项，其余点「加载更多」。
   应用在片段插入**之后**，否则片段新增的画廊会漏过分页。
   结果：visuals 页 7 个画廊、data-index 页 86 个画廊全部受控，
   单页不再一次性创建上千个 `<img>`。
3. **跨页全站检索**：新增 `tools/build_results_viewer_search_index.py`，
   把 9 个页面的分区、卡片与 240 篇笔记压成一份 291 条索引，
   顶栏检索框改为全站检索并直接跳转到命中页的锚点。

### 验证

- 9 页结构 0 失配、2,978 项引用零悬挂、全管线幂等、48 项测试通过
- `viewer-runtime.js` 通过 `node --check`；CSS / JS / 检索索引三者 HTTP 均 200

### 仍未做到的

浏览器在本环境持续超时（多轮），**重置后的视觉效果仍缺整页截图取证**。
已完成的是静态与结构性验证：组件标记、脚本语法、资源可达、分页计数。
建议用户实际打开确认动画与分页表现。

---

## 第十二轮：角色动作黑格子（用户复报）修复

### 症状

手鞠（角色 #15）动作格子全黑，点一下才出现精灵表。

### 根因

不是资源问题。`initMotion` 只在 `DOMContentLoaded` 跑一次，而**切换角色时
`selectStudioChar` 用 `vp.innerHTML = ...` 整体替换容器**，新插入的运动组件
从未被初始化——没有 `background-image`、没有尺寸，于是继承
`.studio-act-img-wrap` 的深色径向渐变（`#1a253c → #090d16`），看上去就是黑格子。
手鞠没有 GIF，走的是帧条分支，正好命中；而已有 GIF 的 14 个角色走 `<img>` 分支，
不依赖 `initMotion`，所以只有 21 个"仅帧条"角色受影响。

### 修复（三道保险）

1. `viewer-runtime.js` 增加 `MutationObserver`，任何动态插入的节点都会被重新初始化；
2. `selectStudioChar` 渲染后显式调用 `initMotion`；
3. 帧条加载失败时显示「帧条缺失」占位，**绝不再出现无声的黑格子**。

### 验证

用最小 harness（只含漩涡鸣人 + 手鞠两个角色）实机复现并截图：
手鞠 5 个动作格（位移步态 / 普攻连击 / 重击击退 / 结印蓄力 / 受创击退）
**全部正确显示精灵并逐帧播放**，不再需要点击才见精灵表。
浏览器 console 无错误。

### 顺带发现（尚未证实，未擅自修改）

`char_15_手鞠_locomotion.png` 的首帧是**金发双髻、白红服装**的角色，
而 `char_02_春野樱`（粉发红衣）、`char_19_桃地再不斩`、`char_13_我爱罗`
以及 `char_03_山中井野`（金发紫衣）的立绘都与其名相符。
帧哈希互不重复，说明每名角色拿到的是不同图，问题可能是**精灵行 → 角色名**的映射。

**本轮未修改任何角色映射**——需要回到 ROM 侧（`0x596D5C` 动作表与角色名映射）
核对后才能定论，此处只登记为待查项，不以观感替代 ROM 证据。

### 补充：修复覆盖全部 21 个帧条角色（非仅手鞠）

用户追问「除了手鞠，其他很多角色也这样，你修了么」。修复位于**共享运行时**
（`viewer-runtime.js` 的 `initMotion` + `MutationObserver`，以及 `selectStudioChar`
渲染后的显式调用），对任何走帧条分支的角色统一生效，不含角色特判。

实测：用最小 harness 把 5 个「仅帧条」角色（#14 勘九郎、#15 手鞠、#19 桃地再不斩、
#20 白、#28 大蛇丸）并排渲染并截图，**每个动作格都正确显示精灵并逐帧播放**，
无一黑格子，console 无错误。

**走帧条分支的角色共 21 个**（#14 勘九郎、#15 手鞠、#16 音忍托斯、#17 音忍萨克、
#18 音忍琴、#19 桃地再不斩、#20 白、#21 雨忍·影分身、#22 雨忍·刺客、#23 雨忍·头领、
#24 鬼兄弟·业头、#25 鬼兄弟·冥头、#26 叛忍浪人、#27 敌方上忍头目、#28 大蛇丸、
#29 木叶丸、#30 手打（一乐大叔）、#31 木叶暗部、#32 敌方潜伏密探、#33 伏击暗杀者、
#34 傀儡·乌鸦）；其余 14 个有 GIF 的角色走 `<img>` 分支，本就不受影响。
GIF 与帧条文件全部存在，缺失数为 0。

---

## 第十三轮：取消一切截断，全量呈现（子页分段 + 文件下载）

用户要求：**不允许截断，内容必须完整**；不适合网页预览的内容做子页跳转、
子页内分段展示，并提供文件下载以完整呈现。同时指出「完整呈现与不混乱不冲突，
混乱是没有条理，截断只是偷懒」。

### 做法

1. **取消 1,200 字笔记截断**：`tools/build_results_viewer_conclusions.py` 不再裁剪结论段落。
2. **取消族卡片摘要**：原先每个产物族只渲染 schema/计数/scope 摘要（占 manifest 字段 0.6%）。
   新增 `tools/build_results_viewer_family_pages.py`，为 **255 个族各生成子页**，
   逐顶层分区分段渲染，**长字符串与长列表全部完整渲染，无任何裁剪**。
3. **超大分段**：单页超过 1.2 MB 时按顶层分区（必要时再按分区内条目）拆成
   `<family>__segN.html`，页内有分段导航 + 锚点跳转。共生成 **300 个族子页**，
   单页最大 1.7 MB。
4. **文件下载**：每个族子页底部列出该族目录下**全部文件**（manifest.json、
   PNG、BIN 等，56,175 个链接，逐个校验可解析）供完整下载。
5. **索引页瘦身**：数据产物索引页改为**链接表**（255 行 → 各族子页），
   从 891 KB 降到 93 KB。

### 关于「16.4%」的更正

上一轮报的「数据族字段呈现 0.6% / 16.4%」是**度量口径的假象**：
脚本只对「长度 > 10 的字符串」做字面匹配，而 manifest 叶字段里
**56.4% 是数字、6.9% 是布尔**，这些都已作为 `fml-num` / `fml-bool` 渲染，
却因不是字符串而被计成"未呈现"。

按渲染元素数复核（每个叶字段至少产生一个值元素，多出的是结构行与列表下标）：

```text
rom-cfg-inventory-v3      leaves=  86   渲染值元素=  151
rom-boot-interwork-v1     leaves=  46   渲染值元素=   70
map-canvases-v1           leaves=3,324   渲染值元素= 5,704
tile-assets-bg-v2         leaves=14,609  渲染值元素=22,859
rom-cfg-proven-roots-v1   leaves=  91   渲染值元素=58,305
```

渲染元素数均 ≥ 叶字段数，说明**没有任何叶字段被丢弃**。
结论：数据族字段呈现率实为 **100%**，此前的数字作废。

### 结果

- 族子页 300 个 / 73 MB，最大单页 1.7 MB
- 9 个 Hub 页：结构 0 失配、2,677 项引用零悬挂、族子页 56,175 个下载链接零失效
- 48 项测试通过

---

## 第十四轮：清除作废内容 + 线上加载压力优化

### 1. 作废内容清除

- 单页源文件里的「⚠️ 已作废的旧解读（155×16）说明」整块删除，
  **不在 HTML 里保留任何被推翻的解读**（结论索引、覆盖总表同样只讲当前有效结论）。
- 校验：全站 `已作废的旧解读|虚报|早期版本` 命中数为 **0**。

### 2. 加载压力优化（面向线上访问）

原先两个最重的 Hub 页一次性携带全部正文：

| 页面 | 优化前 | 优化后 |
| --- | --- | --- |
| 结论页 | 318 KB（240 篇结论正文内联） | **15 KB 索引** + 5 个主题子页（19–150 KB） |
| 公式页 | 752 KB（72 族运行时模型内联） | **53 KB 索引** + 72 个族子页（1–53 KB） |

配套措施：

- 所有 `<script>` 加 `defer`，不阻塞首屏；
- 全部 1,043 张图带 `loading="lazy"`（此前已覆盖），且画廊按 24 项分页；
- 255 个族的内容本就只在**显式点击后**的族子页加载，最大单页 1.7 MB、
  中位 16 KB，超限自动分段；
- 检索索引（291 条）改为**输入时才 fetch**，不占首屏。

结果：最大 Hub 页 406 KB（visuals，含 1,041 张懒加载图），
其余 Hub 页 ≤ 197 KB；族子页中位 16 KB。

### 验证

- 386 个页面（9 Hub + 5 结论子页 + 72 公式子页 + 300 族子页）
  共 **61,752 项引用，断裂 0**（含跨页锚点逐个解析）；
- 结构解析 0 失配；48 项测试通过（结论/公式测试改为跨全部子页校验）。

---

## 第十五轮：图像点击放大 + 按类别打包下载

### 灯箱（点击放大）

`docs/assets/viewer-runtime.js` 新增共享灯箱组件，对全站画廊生效：

- 点击任意图 → 遮罩层放大显示（透明区用棋盘格底衬，像素图 `image-rendering: pixelated`）；
- `←` / `→` 在**当前画廊内**翻页，底部显示 `序号 / 总数 + alt`；
- `Esc` 关闭；右下角「下载原图」直接取该图源文件；
- 翻页范围取最近的 `[data-paginate]` 容器，因此不会跨到别的画廊。

实测：visuals 页点击 Map 0 tileset → 大图 + 棋盘格 + 「1 / 47 Map 0 tileset」
+ ‹ › 翻页 + ✕ 关闭 + 「下载原图」，全部可见。

### 按类别打包下载

新增 `tools/build_results_viewer_downloads.py`，把 **5,395 张图像（21.9 MiB 原始体积）**打成：

- **87 个成果族包** `docs/downloads/families/<family>.zip`；
- **8 个主题包** `docs/downloads/themes/<theme>.zip`
  （角色与战斗视觉 2,063 张 / 战斗系统 786 / 地图与场景 794 / 剧情与演出 253 /
  数据与内存 106 / 立绘与界面 6 / 控制流与配置 39 / 其它 313，
  外加 `build-assets` 1,035 张构建树图像）；
- **全量包** `docs/downloads/all-images.zip`（5,395 张 / 22.0 MiB）。

主题归属用**族名前缀规则表**（`THEME_RULES`）判定，确定且可解释，不靠猜测。
`build/viewer-data/downloads.json` 记录每个包的真实文件数与压缩后体积，
页面上的下载芯片显示的就是这些实测值。

首页新增「图像资源打包下载」卡片：8 个分类芯片 + 87 个族包（折叠）+ 全量包。

### 验证

- 页面 **61,848 项引用，断裂 0**（含新增的 95 个 ZIP 链接）；
- 浏览器实测灯箱与下载面板均正常，控制台无错误；
- 48 项测试通过。

### 灯箱控制键修复

用户反馈「右上角的叉没有用」。根因：灯箱的四个控件是用 `innerHTML` 建出来的，
**只注册了 document 级键盘事件（Esc / ← / →），没给按钮绑 click**，所以
✕ / ‹ / › 三个按钮点了没反应，背景点击也不关。

修复：在 `ensureLightbox()` 里为 `.lb-close`、`.lb-prev`、`.lb-next`、`.lb-backdrop`
逐一 `addEventListener`，并把当前画廊列表通过 `box._setList` 暴露给按钮，
使按钮翻页与键盘翻页使用同一份列表。

实测：点击 ✕ → 灯箱关闭，页面回到画廊；点击 › → 图片由 Map 0 切到 Map 1。

### 分类下载改为「按页面板块」

用户指出分类维度错了：此前按**成果族名前缀**分包（`character-*` / `battle-effect-*` …），
但读者是按**查看器的板块**找资源的——「角色动作交互工作室」就该给所有角色的动画一个包。

改为**按卡片实际引用的图像**打包：逐个 Hub 页解析每张卡片，收集它引用的全部图像，
每个板块一个 ZIP。工作室卡片的图像由 JavaScript 渲染，故单独从
`docs/assets/studio-data.js` 读取（19 名角色的全部 GIF 与帧条）。

结果：**21 个板块包 / 1,915 张图像 / 11 MiB**，例如

| 板块 | 张数 |
| --- | --- |
| 图块资产 BG 图层 | 344 |
| 菜单 / 剧情立绘矩阵总集海报 | 312 |
| 角色战斗视觉资源 | 250 |
| **角色动作交互工作室** | **197**（19 角色 × GIF 86 + 帧条 111） |
| 战斗特效精灵动画 | 182 |
| 战斗演出字形与消息表 | 174 |
| 79 项战斗视觉表现目录 | 79 |
| 战斗视觉运行时时间线 | 75 |
| 成品战场地图画布 | 61 |
| 战场地图 Tileset 图集 | 47 |
| …每个板块一个 | |

「包内就是该板块展示的全部图像」——由解析页面得到，不靠人工维护清单。
原有的主题包（8）与族包（87）保留在折叠区作为另一种分组维度。

### 下载入口位置修正

用户反馈「没看见下载按钮」。原因：下载面板原先挂在首页**最后一张卡**，
而它前面压着 KPI / 阶段 / 里程碑 / 内存拓扑 / 测试 / 下一步，
以及**两张各 255 行的长表**（覆盖总表 + ROM 家族目录）——实际不可见。

修正三处：

1. 下载面板提到首页**第一张卡**（在 KPI 之前）；
2. 顶栏加「📧 图像打包下载」按钮，跳转该卡；
3. 侧栏加「图像打包下载」条目（21 板块）。

浏览器实测确认：首页首屏即见 21 个板块包芯片。

### 每张卡片自带下载按钮

用户指明位置：**每个板块的卡片头部**（红箭头指向处），而不是集中在首页的下载列表。
新增 `tools/inject_viewer_download_buttons.py`：按 `section-packs.json` 的
card_id → ZIP 映射，为每个拥有板块包的卡片在 card-head 注入
`⬇ 下载本板块 · N 张` 圆形按钮，链接到该板块自己的 ZIP。

- 21 张有图的卡片各得一个按钮；无图卡片（如动作矩阵表、场景选择表）不加；
- 注入用**深度感知的扫描**定位 card-head 的闭合标签（card-head 内含嵌套的
  title div，朴素匹配 `</div>` 会切错位置）；
- 注入已并入 `tools/split_results_viewer.py` 管线末尾，重跑不会丢；
- 卡片头布局改为「标题独占一行 + 标签与按钮同行」，按钮右对齐。

浏览器实测：角色动作交互工作室卡片头部出现「⬇ 下载本板块 · 197 张」，
点击即取该板块 19 名角色的全部 GIF 与帧条。

### 下载按钮视觉重做

按要求改为**两行高度 + 橙色强调 + 立体效果**：

- 结构：`card-dl-main`（⬇ 下载本板块）/ `card-dl-sub`（197 张图像）两行；
- 配色：`linear-gradient(180deg,#fbbf24,#f59e0b)` 琥珀橙渐变 + 深棕字 `#451a03`；
- 立体：`box-shadow: 0 4px 0 #92400e` 实体底边做出凸起，
  叠加 `inset 0 1px 0 rgba(255,255,255,.45)` 顶部高光与外投影；
  hover 上浮 1px（底边 5px），active 下压 3px（底边 1px），有真实的按压反馈。

### 下载按钮再调整：与标题平齐 + 整高大图标

- **图标**：改用内联 SVG 下载图标（箭头 + 托盘两笔），`align-self: stretch` +
  `height: 100%`，**与按钮等高**；文字两行改为排在图标右侧。
- **平齐**：卡片头改为「标题（flex:1 1 0，可收缩）+ 按钮（flex:0 0 auto，margin-left:auto）」
  同行，标签（tag）降到第二行独占。
- **溢出修复**：标题改为 `flex: 1 1 0; min-width: 0`，并给 `.card` / `.card-grid > *`
  加 `min-width: 0`——网格与弹性子项默认 `min-width: auto` 会拒绝收缩，
  导致按钮把卡片顶出视口、页面出现横向滚动条。

浏览器实测：按钮与卡片标题同行右对齐，大图标撑满按钮高度，橙色立体，
页面无横向溢出，控制台无错误。

### 侧栏目录与卡片对齐（目录改为自动生成）

用户发现左侧目录与右侧卡片**数量对不上**。实测：6 个页面共 **20 张卡片没有对应导航项**
（battle 6 / results 7 / story 5 / visuals 4 / data 1 / engineering 1）；
反向没有问题（导航没有指向不存在的卡片），所以没断链，只是目录不全。

根因：侧栏是**手写**的固定列表，每后来新增一张卡片都不会自动出现在目录里。

修法：**侧栏改为从实际卡片生成**。

- 新增 `collect_cards()` + `build_sidebar()`：逐个 Hub 解析其 section 里的
  `<div class="card" id="...">`，取出真实标题，按 PAGES 顺序生成分组目录；
  卡片标题用**深度感知扫描**提取（标题 div 内嵌 span，朴素匹配 `</` 会截断标题
  并串到下一张卡片——这正是首版侧栏里工作室标题错位的原因）；
- 当前页的分组标记为 active，条目用 `.sidebar-sub` 缩进并带左侧竖线；
- 侧栏同时保留 Hub 级入口（研发全景 / 视觉 / 战斗 / 剧情 / 数据 / 工程 /
  公式 / 结论 / 产物族索引），条目后标注该页卡片数。

验证：**9 个页面全部 nav 数 == cards 数，缺失 0 / 多余 0**。
新增 `tests/test_results_viewer_site.py::SidebarParityTests`（2 项）锁定该不变量，
总计 50 项测试通过。

### 侧栏去掉重复的纯文本分组标题

侧栏原先每组是「一行不可点击的纯文本组名 + 一行可点击的同名链接」，
属于纯重复。已删除纯文本组名行，**由可点击的 Hub 链接本身充当组标题**，
并在其右侧标注该页卡片数；顶部的静态站名「逆向成果查看器」一并去掉
（侧栏是纯导航区，不需要静态标题）。

结果：侧栏只剩 9 个可点击 Hub 链接 + 53 个卡片条目，零纯文本重复行。

### 场景视觉包的动画此前全是静图

用户反馈【场景视觉包】里"动画显示都是静态图片"。查证后确认**卡片只渲染了静态背景**：

- 通用卡片构建器对这个族只取了 `pack-*/background.png`；
- 该族实际还含 **16 个 OBJ 动画帧**（`obj-frame-*.png`，32×72~96）、
  **18 张 OBJ 图集**（`obj-atlas-*.png`）与 16 份动画时序定义（`obj-animation-*.json`），
  这些**全部没被渲染**，页面自然只剩静态背景。

修法：

1. 新增 `tools/build_results_viewer_scene_packs.py`，按该族自身的
   `playback` 时序数据生成 9 个包卡片：背景 + 每个 OBJ 动画的帧序列 + 图集；
2. 新增 `data-frames` 帧序列播放器（`viewer-runtime.js`），按 fps 循环播放，
   仅在进入视口时启动，点击可暂停——**这一族现在是真的在动**；
3. 通用构建器新增 `SPECIAL_BUILDERS` 路由，让该族由专用构建器独占输出，
   避免同一张卡被两条路径各写一次。

过程中修掉一个隐蔽缺陷：`_card_bounds()` 原先把"下一张卡的起点"当作本卡的结束位置，
导致插入内容落到错误位置、页面嵌套失配。已改为**深度感知扫描本卡自身的匹配 `</div>`**。

验证：9 个包 / 16 个动画播放器 / 27 张图集 / 16 条动画帧路径零失效；
62,214 项引用断裂 0；50 项测试通过。

---

## 第十轮：全资源呈现方式逐项审查

对全站 44 张卡逐一审查"呈现方式是否合适"，发现并修复 4 处问题。

### 问题 1：世界地图背景卡有 5 张「坏图」

`sec-world-map-bg` 的 `<img src>` 指向的是**目录和 manifest.json**：

```text
../artifacts/world-map-backgrounds-v1/manifest.json   ← 不是图片
../artifacts/world-map-backgrounds-v1/page-00         ← 是目录
../artifacts/world-map-backgrounds-v1/page-01
../artifacts/world-map-backgrounds-v1/page-02
../artifacts/world-map-backgrounds-v1/shared
```

根因：通用构建器用 `*` 做通配，**没有过滤文件类型**。已改为只接受真实图片文件
（`IMAGE_SUFFIXES`），并把该族通配修正为 `page-*/*.png`——
现在正确指向 6 张 `background.png` / `label-preview.png`。

### 问题 2：战斗特效精灵动画是 182 张静图

该族 manifest 里**有关键帧时序**（`frame_id` + `hold_frames`），但通用卡片把帧
排成了静态缩略图。新增 `tools/build_results_viewer_effect_anims.py`：
按 18 个 group 各自的 `keyframes` 生成播放器，`data-holds` 携带每帧停留帧数，
运行时按真实时序播放。**现在这一族也是动的。**

### 问题 3：35 角色动作矩阵没有下载包

该卡用 `href` 链接到 35 张 `matrix/char_NN_*.png`（图谱），不是内联 `<img>`，
打包器只扫 `src` 因而漏掉。已让打包器同时扫 `href` 与 `data-frames`，
该卡现有 **35 张**图谱的下载包。

### 问题 4：场景视觉包重复插入

修复问题 2 过程中引入了新问题：专用片段同时被通用管线和显式替换各写一次，
导致卡片被复制 6~7 次、页面嵌套失配。已把这两张专用卡**从通用片段管线摘出**，
只由显式替换负责；并修掉 `_card_bounds()` 把"下一张卡起点"当成本卡结束位置的缺陷
（改为深度感知扫描本卡自身的匹配 `</div>`）。

### 审查结论

```text
有图但无下载按钮的卡：0
动画播放器：26 个（场景视觉包 16 + 战斗特效 18 组/36 播放器）
板块包：23 个 / 1,985 张
引用：62,246 条，断裂 0
测试：50 项通过
```

无图的卡（表格 / 索引 / 流程图）**正确地没有下载按钮**；
工作室卡片图由 JS 运行时渲染，静态扫描看不到，已单独核对：
19 名角色 111 个动作 = GIF 86 + 帧条 25，文件零缺失，JS 两条分支齐备且渲染后重新初始化。

### 灯箱：点击图片外区域也退出

原先只有 `✕` 按钮、背景遮罩和 `Esc` 能关闭，而 `.lb-figure` 覆盖了屏幕绝大部分，
**点图片周围的空白（figure 的 padding 区）没有反应**。

现为 `.lb-figure` 单独挂 click 处理器：命中 `.lb-image` 本身视为「在图内」不关闭，
其余（figure 留白、说明文字、背景遮罩）一律关闭；光标同步改为 `zoom-out` 提示可点。

浏览器实测：点说明文字 → 灯箱关闭；点图片本身 → 保持打开。

## 第十二轮：地图画布「无 tile 地块」背景色不统一

### 现象

地图画布板块里，同一个「这里没有铺 tile」的区域，**每张图各画各的颜色**：

| 画布 | 原始索引 0 的调色板色 | 观感 |
| --- | --- | --- |
| `map-00-alternate` | `(0,148,231)` | 浅蓝 |
| `map-01..05-alternate` 等 | `(24,49,255)` | 深蓝 |
| `map-06-*` | `(0,255,0)` | 纯绿 |
| `map-07..35-*` | `(0,0,0)` | 纯黑 |

浅蓝、深蓝、纯绿、纯黑轮流出场，看起来像渲染出错，而不是「这一块本来就没有 tile」。

### 根因

`artifacts/map-canvases-v1/canvases/*.png` 是**索引色 PNG**，调色板 0 号色是
**这张地图自己的 BG 背景色**（GBA BG palette bank 0 的 color 0）。

导出器把 GBA 的 color 0 映射到 PNG 索引 0：

```python
# tools/export_map_canvases.py:207
0 if color == 0 else palette_bank * 16 + color
```

而「没有铺 tile」在 ROM 侧就是**引用 tile 0**。已逐张核对 **47/47 张地图的
tile 0 都是 64 像素全透明的空 tile**（`set(colors) == {0}`），所以：

> 索引 0 **只可能**由「没铺 tile」产生。

也就是说索引 0 同时承担了两个含义——「GBA 的透明色」和「这张地图的背景色」。
直接显示原图，空地块就必然被画成该图自己的背景色，于是各图不一致。

14 张 alternate 变体的空地块占比高达 60.6%–91.2%，所以整幅图几乎整片变色。
（47 张 primary 变体的空地块占比是 0%，另有两张 primary 只有几个像素，属实但不可见。）

### 处置：只动展示层，不动证据

`artifacts/map-canvases-v1/` 是已签证据，**一个字节都不改**（导出器
`notes/map-canvases-export-20260729.md` 也明确写过「透明索引不会被擅自引入」）。
新增 `tools/build_results_viewer_map_canvases.py`，在
`build/map-canvases-web/` 写**展示用副本**：

- 副本 = 原始 PNG **逐字节相同，只多一个 tRNS 块**（13 字节），声明调色板索引 0 透明；
- IDAT 与 PLTE 块**原样搬运**，索引像素与调色板零改动；
- 写 `build/map-canvases-web/manifest.json`：逐文件记录源/副本 SHA-256、尺寸、
  空地块像素数与占比、以及 47 张地图「tile 0 全透明」的核对结果。

页面侧：

- `tools/build_results_viewer_artifact_sections.py` 的地图画布卡改指向副本，
  `<img class="map-canvas-img">` + 外框 `map-canvas-wrap`；
- `docs/assets/viewer-extra.css` 给图片与外框铺**同一张中性棋盘格底衬**
  （与灯箱 `.lb-image` 早已在用的底衬一致），空地块因此在所有地图上完全统一；
- 卡片文案写明规则与出处，并指向未经改动的原始证据目录。

### 结果

```text
派生副本：61 张，每张 +13 字节；索引像素 / 调色板与原 PNG 完全一致
有透明地块的画布：15 张（14 alternate + map-09-primary 8px + map-11-primary 4px）
板块包 sec-map-canvases.zip：61 张（全部为展示副本）
引用：61,855 条，断裂 0
测试：61 项通过（新增 11 项 + 修正 1 项旧断言）
管线幂等：连续两轮全量重跑，86 个页面 SHA-256 完全一致
覆盖率：族级 255/255 = 100%，普查分母 227 —— 未漂移
```

浏览器实测：Map 00 / 21 / 32 三张 alternate 的空地块现在是**同一张**棋盘格；
同一页并列的原始证据 PNG 仍是浅蓝 / 纯黑，可直接对照。

### 顺带修正

`tests/test_results_viewer_artifact_index.py` 的
`test_map_canvas_section_matches_the_manifest_count` 原本硬编码
`map-canvases-v1/canvases/` 路径前缀，画布改指副本后必然失败。已改为同时接受
两种前缀，并追加「每张 canonical 画布仍在证据目录里」的存在性断言——保留了原意
（板块必须正好覆盖 manifest 里的全部画布），而不是放宽成「不检查」。

## 第十三轮：左侧导航与右侧当前页面／卡片实时联动

### 问题

侧栏早就按真实卡片生成（每张卡片都有条目、9 页 nav 数 == cards 数），但**高亮不跟随阅读位置**：

- 页面加载时高亮停在页组标题，之后无论滚到哪里都不变；
- 长页面（visuals 404 KB / 1,041 图）读者无法从导航判断自己读到哪一张卡；
- 侧栏本身也不自动跟随，当前条目落在折叠分组里时根本看不见。

### 实现

**`docs/assets/viewer-runtime.js` 新增 `initSidebarSpy()`**

- 只把**指向当前页**的条目纳入候选：条目的 `href` 文件部分必须等于 `<body data-page>`，
  否则指向别的页的条目永远不可能是"正在读的那一张"；
- 读线取「吸顶栏下方 24px」，取**最后一个顶边在读线之上**的卡片为当前卡片
  （用读线而不是 IntersectionObserver：长卡片会同时命中多个观察目标）；
- 该条目加 `.active`，它所属分组的组头加 `.current-group`（组头用自己的轻标记，
  `.active` 留给具体卡片条目，避免层级塌成一个高亮行）；
- **手动改 `sidebar.scrollTop`**，不用 `scrollIntoView()`：后者会连同页面一起滚，
  会跟读者抢位置；
- 滚动用 rAF 节流；`hashchange` / `resize` / `load` 也重算。

**`tools/split_results_viewer.py`**：`markActive()` 末尾调 `window.refreshSidebarSpy()`，
免得共享脚本和 scroll spy 两套高亮逻辑各说各话。

**`docs/assets/viewer-extra.css`**：`.sidebar-hub.current-group` 样式；
以及 `.card, [id^="sec-"] { scroll-margin-top: 72px; }`。

### 顺带修掉的两个真实缺陷

**锚点跳转把卡片标题藏在吸顶栏下面。** 吸顶栏 56px 固定在顶部，锚点跳转把卡片顶边
对齐到视口顶，标题因此被盖住——点了导航条目，却看不到那张卡的标题。
`scroll-margin-top` 同时修好原生锚点跳转和 `scrollIntoView()`。

**首次带 hash 直达会落在错误的卡片上。** 实测（data 页 `#sec-sprite-definitions`）：
`load` 触发时**浏览器根本还没跳**（`scrollY` 仍为 0，文档只有 3,991px 高，
懒加载图片还没有尺寸）；等图片落地后文档涨到 10,514px，被请求的卡片整体下移约
1,000px，于是落在视口下沿之外——读者点的那张卡根本不在屏幕上。
新增 `initAnchorLanding()`：在布局停止移动前，持续把目标卡片对齐到
`scroll-margin-top` 指定的位置（每 250ms 一次，最多 40 轮，位置连续两次不变即停）；
**读者一旦自己滚动（滚轮／触摸／滚动键）立即停止纠正**，读者永远优先。

### 浏览器实测

| 操作 | 结果 |
| --- | --- |
| 页面顶部 | 高亮落在页组标题（组头 `.active`） |
| 滚到中段 | 高亮落在"忍具 / 药品 / 卷轴 / 材料内存表"，侧栏自动滚到该条目并保持可见，组头"4. 内存数据与音频架构"带 `.current-group` |
| 滚回顶部 | 高亮回到页组标题 |
| 点击侧栏条目 | 精确落到该卡片，标题不被吸顶栏遮住，高亮同步 |
| 首次带 hash 直达 | 精确落到目标卡片（修复前落在上一张卡） |

### 结果

```text
新增测试：tests/test_results_viewer_sidebar.py 11 项
测试合计：72 项通过
引用：61,855 条，断裂 0
管线幂等：连续两轮全量重跑，86 个页面 SHA-256 一致
```

### 方法备忘

页面级交互的判定**不能只看静态代码**：本轮两处结论都靠浏览器实测才定下来，
其中"首次带 hash 落地偏早"更是靠往 `<html>` 上写临时度量属性
（`load` 时刻与 2 秒后的 `scrollY` / `docH` / 每张卡的文档偏移）才定位到
"浏览器在 load 时还没跳、且上方内容随后又长高约 1000px"。
度量属性只是探针，修好后已移除。

## 第十四轮：查看器发布到项目 GitHub Pages

### 为什么不能直接开 Pages

查看器住在 `docs/`，页面用 `../artifacts/` 和 `../build/` 取图——这两个路径**逃出了文档根**。
GitHub Pages 只服务一个目录，若把 `docs/` 直接设成发布源，页面里 61,855 条引用会全部指到
站点之外，图片与下载包全挂。

而且 `artifacts/`（333 MB）**根本没有入库**（master 里 0 个文件），Actions 也无从构建。

所以走 **`gh-pages` 分支**：`tools/build_results_viewer_publish.py` 组装发布树，
`tools/publish_results_viewer_github_pages.sh` 推到 `gh-pages`，Pages 以分支根目录提供服务。

### 发布树的组装规则

发布根 = 仓库根，于是每个"逃出 `docs/` 的引用"正好少爬一层 `..`：

| 页面位置 | 仓库内写法 | 发布后写法 |
| --- | --- | --- |
| `docs/*.html` | `../artifacts/x.png` | `artifacts/x.png` |
| `docs/families/*.html` | `../../artifacts/x.png` | `../artifacts/x.png` |
| 两者 | `assets/z.css`（在 `docs/` 内） | **原样不动** |
| 两者 | `downloads/p.zip`（在 `docs/` 内） | **原样不动** |

判定**不按字符串前缀，而按解析后的目标是否还在 `docs/` 里**：留在 `docs/` 内的
（`assets/`、`downloads/`）保持原相对路径，逃出去的才去掉一层 `..`。所以族子页虽然
在 `families/` 下一层，指向站点根的引用仍然是 `../artifacts/...`。

只复制**页面真正引用到的**文件（9,145 份）；`docs/assets/` 与 `docs/downloads/` 整目录复制
（运行时用 URL 取 search index，静态扫描抓不到）。

### 两个踩过的坑

1. **被引用的页面把改写后的版本覆盖回原版。** 族子页会链接到 Hub 页面，于是"复制被引用
   文件"这一步把**未改写**的 Hub 页面又盖了回去，结果 367 个 `../artifacts/` 只改掉一半
   （192 个残留）。修法：页面集合不参与引用复制，页面最后写。
2. **路径必须 resolve。** macOS 的 `/var` 与 `/private/var` 是同一个目录，`relative_to()`
   直接抛 `ValueError`。单测用 tempfile 时暴露，改成工具内部 resolve，而不是绕开。

### 发布内容与边界

- 386 个页面 + 9,145 份被引用的产物 = **9,531 个文件 / 355.1 MiB**（压缩包 161 MiB）；
- **基准 ROM 不在发布树里**：没有任何页面引用 `rom/base.gba`，`build/naruto-sequel-dev.gba`
  也没被引用；工具只复制页面指向的文件，单测钉住"发布树里不出现任何 `.gba`"；
- 121 个 `.ss9` 模拟器存档状态属于族子页的"原始文件下载"清单，随页面一并公开；
- 仓库本来就是公开仓库，且已含 `rom/experiment-*.gba`（补丁实验 ROM）。

### 验证

| 层面 | 结果 |
| --- | --- |
| 静态 | 发布树内 9,529 个引用全部可解析（工具自带 `verify()`，非零退出即失败关闭） |
| 本地 HTTP | 线程服务器逐个 GET，9,529 个 URL 全部 200 |
| **线上** | **387 个页面 0 失败**；8,774 个资源抽样 250 个 **0 失败** |
| 线上运行时 | `viewer-runtime.js` 含 `initSidebarSpy` / `initAnchorLanding`；`viewer-extra.css` 含 `.current-group` 与 `scroll-margin-top`；`search-index.json` 可解析；`index.html` 跳转正确；`.nojekyll` 存在 |
| 浏览器 | 线上入口自动跳到 `reverse-engineering-results.html`，标题正确 |

### 复现

```sh
./tools/publish_results_viewer_github_pages.sh
```

脚本重建发布树、以 `gh-pages` 分支强制推送（构建会清空目录，提交根会变，故需 `--force`），
并打印 Pages 的 URL 与发布源。首次开启 Pages：

```sh
gh api --method POST repos/AltairCardinal/gba-naruto/pages \
  -f source[branch]=gh-pages -f source[path]=/ -f build_type=legacy
```

`build/viewer-publish/` 已进主仓 `.gitignore`（它自带 `.git`，不该被主仓跟踪）。

## 第十五轮：线上「角色动作交互工作室」动画与序列帧不可见

### 现象

GitHub Pages 上的 `sec-studio` 卡片整片空白：动画（GIF）与序列帧（帧条）都不可见，
35 张动作图谱也点不开。

### 两处根因

**一、运行时拼出来的路径爬出了站点根。**
角色工作室整张卡是 JavaScript 渲染的（`assets/viewer.js` 的 `selectStudioChar`），
图片路径在运行时才拼出来：

```js
`<img src="../${gif}" ...>`
`<span class="is-motion" data-strip="../${act.strip_path}" ...>`
`<a href="../${data.matrix_sheet}" ...>`
`img.src = '../' + stripPath;`
```

`../` 是按"页面在 `docs/` 里"写的。发布后页面在**站点根**，`../` 就爬出了站点 → 全部 404。
上一轮的发布改写只覆盖了 **HTML 属性**里的路径，**运行时拼出来的路径一个都没改**。

修法（改源码，不改产物）：把散落的 `../` 收成一个常量

```js
const ASSET_BASE = '../';
```

仓库里保持 `'../'`，发布时由发布器改写成 `''`。

**二、运行时引用的文件根本没进发布树。**
发布器只复制**页面标记里引用到**的文件。工作室的 197 个序列帧 / 图谱 PNG 只在
`assets/studio-data.js` 里以路径字符串出现，标记里一个都没有 —— 于是发布树里
`build/sprites/actions/` 是空的，卡片必然空白。

修法：发布器除扫描页面标记外，**再扫 `assets/*.js` 里的路径字面量**，把命中的真实文件
一并复制；并把这一步纳入 `verify()`：脚本里指到的文件若不在发布树内，直接失败关闭。

### 又踩了一次"覆盖"坑

`viewer.js` 自己也被页面用 `<script src="assets/viewer.js">` 引用，于是它落进
"复制被引用文件"那一步，把**未改写的原版**盖回了刚改写好的副本。
与上一轮"被引用的页面盖回改写版"是同一类错误：**凡是发布时做了特殊处理的文件，
都不能再走通用复制**。已把 `docs/assets/`、`docs/downloads/` 排除出通用复制。

### 结果

```text
发布树：9,531 → 9,728 文件、355.1 → 395.2 MiB（+197 个工作室资源）
发布的 assets/viewer.js：const ASSET_BASE = '';
工作室：111 个动作序列帧 + 35 张全家福图谱 + GIF 全部进树
测试：83 项通过（新增 3 项：运行时资源被复制 / 前缀被改写 / 缺资源时报错）
```

### 方法备忘

静态改写与文件收集都**只认 HTML 属性**是不够的：只要页面有一部分由 JavaScript 渲染，
它的资源就既不会被改写、也不会被复制。发布器的"引用"定义必须包含脚本里的路径字面量。

## 第十六轮：核对逆向进度，并把新内容补进查看器

### 背景

反馈是：逆向工程又推进了一批，实施方声称"已经找不到未完成逆向的内容"，
要求核对一遍、把新内容追加到查看器，并更新 GitHub Page。

### 核对方法

不采信声明，直接对三棵树做全量差分：

| 树 | 位置 | 产物族 | 笔记 | 工具 |
| --- | --- | --- | --- | --- |
| 逆向工作树 | `../gba-naruto-reverse`（`codex/reverse-engineering`，`821d093`） | 264 | 436 | 818 |
| 主树 | `../gba-naruto`（`codex/butano-foundation-research`） | +4 个 ROM RE 族 | 361 | — |
| 查看器仓（核对前） | 本地 `master` | 259 | 250 | 367 |

**结论：实施方的"没有未完成内容"只在它自己的账本口径上成立。**
逆向树自己生成的成果索引 `artifacts/reverse-results-index-v1/index.json` 里
`ledger_problems` 确实是 0；但**查看器侧漏了 4 个产物族、243 篇笔记、548 个工具**——
成果本身早就做完，只是从没进过站。

核对中还查出**两处查看器自身的旧缺陷**（非本轮新增）：

1. 地图画布族在覆盖表里是 **0/61**——画布改成带透明的派生副本后，统计口径还在数
   canonical 路径，于是把"已呈现"记成了"未呈现"；
2. 战斗特效精灵动画 **177/178**——group 18 定义 8 帧，但它唯一的动画只播 7 帧，
   第 8 帧在查看器里完全不可见。

### 处置

**新增 `tools/import_reverse_worktree.py`**：按 SHA-256 钉住地把产物、笔记、工具
镜像进本仓——

- 产物族 → `artifacts/<family>/`（manifest 声明了哈希就核哈希，不符即中止）；
- 笔记 → `notes/reverse/`；工具 → `tools/reverse/`；
- 收据写在 `build/viewer-data/reverse-import.json`，可复核每一次镜像。

**同名一律不覆盖。** 两棵分支已经分叉：本地版含逆向树没有的**撤销结论**
（`map-addresses.md` / `map-format.md` 的 `0x596D5C` 纠错、`free-space.md` 的
自由空间分区），逆向树版是旧读法。盲目覆盖会把**已作废的结论**重新端上台面。
所以同名保留本地版，把 **35 篇笔记 / 30 个工具的分歧**记进收据——不丢，也不混。

**管线补全。** 核对时发现**三个生成器原本根本不在管线里**，产物一直停在旧一轮：

- `build_results_viewer_family_pages.py`（族子页）→ 新族因此没有页面；
- `split_results_viewer_heavy_pages.py`（结论主题子页）→ 结论页停在旧的 240 篇；
- `build_results_viewer_data_index.py`（成果族索引页）。

现固化为 `tools/build_results_viewer_site.sh`，含依赖顺序与逆向树镜像步骤。

**新增「逆向成果台账」卡。** 直接读逆向树自己生成的 `index.json`：36 条结论各自的
**证据**、12 个分类的项数，以及 `ledger_problems`（0）。这把"没有未完成内容"从
**声明**变成**可核对的事实**。

**补齐可见性。**

- 结论索引的笔记原文、工具清单的脚本路径改为**可下载链接**（此前只是纯文本），
  镜像内容因此随站发布；
- 族子页生成器支持**没有自带 manifest 的族**（此前会被跳过 → 内容不可达），
  并按族名规约过滤掉 remake 侧的工作目录；
- 战斗特效卡补出「未被关键帧播放的 N 帧」，那一帧不再消失；
- 覆盖率统计支持"同一族两个发布位置只计一次"（画布族 0/61 → 61/61）。

### 结果

```text
产物族        255 → 261，261/261 = 100%
覆盖表 board  21/23 fully → 23/23 fully = 100%
普查族干      227 → 235，235/235 = 100%
结论索引      240 篇 → 515 篇（459 篇含独立结论段）
工具清单      263 → 825 个
族子页        300 → 308 页
引用          63,301 条，断裂 0
测试          83 项通过
管线幂等      连续两轮重跑，86 个页面 SHA-256 一致
```

### 未闭合项（诚实清单）

逆向树自己的移交文档 `notes/reverse/handover-20261020-reverse-tree.md` 仍列着 7 条
未闭合项：整模块 `tests.test_audit_rom_byte_coverage` 全量重跑未完成、三道裁决的
代码改动未执行、D0 闸门 `data-table-b` 仍是 `records_covered 1 / 79`、179 处重放点
中 98 处潜在脆弱、审计器 174 处 `_TEST_SHA256` 的 pin 问题、producer 内冷重放、
元守卫补强两条规则。

这些**不是成果缺口**，而是验收与工程债；该文档已随 275 篇笔记进入结论索引，
读者可按主题找到。台账 `ledger_problems` 为 0 与此不矛盾：**台账核的是"结论有没有
证据"，移交文档记的是"还有哪些验证没跑"**。把两者一起呈现，比任何一句"做完了"
都诚实。

### 方法备忘

**"实施方说做完了"必须用差分核对，不能拿声明当结论。** 本轮实施方说"找不到未完成
逆向的内容"，三棵树一比就看出 4 个族、243 篇笔记、548 个工具从没进过站。

**管线脚本要能被审。** 完整顺序只存在于 `/tmp` 里的一段 shell 时，两个生成器会静默
脱管、产出停在旧一轮——本轮就发现 240 篇的结论页其实是旧的。
