# 剧情与对白域的两个统一视图：场景 与 字库（2026-10-22）

日期：2026-10-22
范围：`rom-editor/js/modules/scene.js`（新）、`rom-editor/css/scene.css`（新）、
`rom-editor/js/modules/story.js`（加分发入口 + 两行 groups）、
`rom-editor/js/routing.js`（只加 `scene` / `font` 两个标签）、
`rom-editor/tools/verify_scene_view.mjs`（新）。

## 1. 目标

用户反馈：「应当按统一的任务编辑来呈现，然后按索引表列出，将其他表的内容都作为字段呈现。
其他模块也要做同样思路的修改。」

任务域已经这么做了（`rom-editor/js/modules/mission.js`）。剧情与对白域里有两组
「同一个主对象的侧面」被拆成了六张表：

| 主对象 | 被拆开的表 |
|---|---|
| 场景 | `story_before_root` / `story_after_root` / `story_logic_root` / `story_events_root` |
| 字库 | `font_segments` / `font_width_table` |

## 2. 走过的路与结论

### 2.1 槽号就是场景号，0 号槽不是场景

四张根表各有 56（before / after）或 47（logic / events）个槽，**槽号 = 场景号**。
实测：每张表的 0 号槽指针都是 0（没有剧本），1..55（logic / events 是 1..46）
全部有剧本指针。所以：

- 场景列表 = 四张根表槽号的并集，去掉 0 号槽 ⇒ **55 个场景**；
- 0 号槽「不算一场戏」这条是**从数据里看出来的**（四张表的第一格都没指针），
  不是写死的常量。

`pack.scripts` 里的 202 条剧本（before 55 / after 55 / logic 46 / events 46）
与根表槽号一一对应（`pointer_slot` = 根表基址 + 槽号 × 4）。

### 2.2 四张根表在内容包里分属两个 module

`story_before_root` / `story_after_root` / `font_segments` / `font_width_table` /
`background_table` 的 `module` 是 `story`；但 `story_logic_root` / `story_events_root`
的 `module` 是 **battle**。所以剧情域首页以前是**显式白名单**才列得出这两张表的 ——
`renderDomainIndex` 的 `structures` 参数里必须点名它们。

合组之后这层白名单不再影响可达性：组行的脚注「由 … 合成」会把四张根表的名字
都列出来，`verify_views.mjs` 里「字宽表现在在剧情与对白域首页」那条断言仍然通过。

### 2.3 字宽表与字形段的对应关系：**仓库没有证明**

- `font_width_table`（`0x53E596`，256 字节 × 1）：**按单字节字符码索引**。
  唯一原生读者 `fn 0x0807F064` 用 `ldrb` 取字符码后加到表基址取宽度
  （`notes/evidence/fonts-spriteframe-l3-20261022.md` §3）。
- `font_segments`（`0x53D644`，31 段 × 8 字节）：`start_code` 是**双字节字形码**
  （0x8140 起，lead 0x80–0x9F + trail）。

两者**不是同一个码空间**：字宽表的 256 个码位与双字节字形码之间，
仓库没有给出证明过的映射（字宽表的唯一读者是「关卡文字标签渲染器」，
不是剧情正文的排版器）。

⇒ 界面上**只作标记，不作断言**：字宽表里属于当前字形段的行按
「字形码的低字节」标出来（`width-hit`），并在说明里写明这个对应关系**尚未证明**。
字宽表本身按字符码 0–255 整张列出、每格可直接改，另给一个
「按字符码查字宽」的入口，让段表没覆盖到的码位也能单独打开改。

### 2.4 字形段的空段

31 段里后 5 段（#26..#30）是空段：`start_code = 0`、`count = 0`、`glyph_offset = 0`。
列表里显示成「空段」，避免作者以为字库丢了 5 段字形。
（`pack.font.coverage` 的 `segments_total = 26` = 31 − 5，与此吻合。）

## 3. 界面

### 3.1 场景视图（`#story/scene`）

- **左边**：场景号列表（场景 1..55）。每行 = 场景号 + 有哪些剧本
  （战前 · 战后 · 逻辑 · 事件，无剧本则写「无剧本」）+ 已改几处。
- **右边**：这一场的**四个剧本指针**（战前 / 战后 / 战场事件逻辑 / 战场事件），
  每个都是 `fields.fieldControl` 的十六进制框，可直接改；每个指针旁边一条
  「看…的剧本 →」链接，跳到剧本查看器
  （`ctx.onJump({module:'story', kind:'script', id:'script', params:{root, scene}})`
  ⇒ `#story/script/<root>/<scene>`）。

### 3.2 字库视图（`#story/font`）

- **左边**：字形段表 31 行（段号 / 起始码 / 字数 / 字形在 ROM 里的位置 / 已改）。
- **右边**：这一段的字段（起始码 / 字数 / 填充 / 字形偏移指针，可改）
  + 字宽表（**256 行**，一行一个字符码，字宽可直接改）
  + 「按字符码查字宽」的入口（填 0–255 → 定位并高亮那一行，同时给出那一码的编辑框）。

两个视图都用 `rom-editor/js/split.js` 的 `splitPane`（可拖动分栏），
宽度分别记在 `editor.story.scene` / `editor.story.font`。

## 4. 写回

只走 `pack.setValue`（字段控件内部），没有新增写回路径。
探针实测：改一个字宽 ⇒ `pack.changedCount()` +1；改回原值 ⇒ 计数回落。

## 5. 验收

`rom-editor/tools/verify_scene_view.mjs`（无头，自带 DOM 桩）覆盖：

1. 场景视图能渲染，左边列表行数 = 场景数（按根表槽数算，不写死）；
2. 详情里有四个剧本指针的字段（都是十六进制框）+ 「看剧本」链接能跳到剧本查看器；
3. 字库视图能渲染，字宽表 256 行、每行都有可改的输入框；
4. 改一个字段 ⇒ `changedCount()` +1，改回原值 ⇒ 回落；
5. 域首页「本域可编辑内容」里四张根表合成一行、字形段表与字宽表合成一行，
   六张表不再单独占行；忍者问题表 / 说话人名表 / 剧情底图表仍是独立行；
6. 「打开场景」/「打开字库」按钮进的是新视图；
7. 交互：点场景行换详情、点字形段换段、按字符码查字宽。

其它门禁：`verify_syntax` / `verify_sources` / `verify_labels` / `python -m unittest`
全过。**`verify_views.mjs` 第 8 组有一项需要主代理改**（见下）。

## 6. 需要主代理配合

1. **`rom-editor/index.html` 加一行**
   `<link rel="stylesheet" href="css/scene.css">`（`css/scene.css` 是本轮新建的）。
2. **`rom-editor/tools/verify_views.mjs` 第 8 组的行数断言要改成「组感知」的**：
   现在它按「本域有多少张表 ⇒ 首页至少多少行」来判，而**组行一行就盖住 N 张表**。
   剧情域：6 张表合成 2 行 ⇒ 首页 7 个 `TR`（1 个表头 + 6 行），
   断言里的 `expected` 是 8（本域 5 张结构表 + 3 张文本表）⇒ 差 1，失败。
   建议把 `expected` 改成「未被任何组合并的表数 + 组行数」
   （剧情域 = 4 + 2 = 6 ⇒ 7 ≥ 6 通过）。
   **同一处对「剧情路线」域也只是勉强通过**（4 行 ≥ 4），再合组也会翻。

## 7. 没做的（边界）

- **字宽表码位 ↔ 双字节字形码的精确映射**：仓库没有证据，只作标记（§2.3）。
- **字形段表之外的字库数据**（`fn 0x0807EE50` 读的 `0x0853E328` 字形度量表
  6 字节/字形）：不在内容包里，本轮没进视图。
- **字形的位图本身**：字形偏移指针只显示地址，不预览图形。
