# 字库映射往返：编辑器里所有对白变成 `{字XXXX}`（2026-10-23）

> 症状：编辑器「剧情与对白」页里**所有对白**都显示成 `{字8167}{字8DC0}…`，
> 每段下面挂一条红字「这段正文里有 16 个字库解不出来的字形码，改写会丢掉它们。」
> （用户截图：146 句全是这样）。
>
> 结论：**两个字库表（`code_to_char` / `char_to_code`）在两处被写成了十进制字符串**，
> 而 `FontCodec` 是拿 `parseInt(x, 16)` 读它们的 ⇒ **每一次查表都对不上**。
>
> 影响比红字说的**更严重**：红字只说「改写会丢掉它们」，实际上坏映射下
> **encode 会把整句写成乱码字节**（不是丢掉未知码，是**整句都错**）。
> 那条红字（`segment.problem` ⇒ 输入框 `disabled`）是唯一挡住数据损坏的东西。
>
> 门禁：`rom-editor/tools/verify_font_map.mjs`（42 条断言，含变异对照）
> 探针：`build/_fontmap_probe.mjs`（build/ 下，被 gitignore）
> 真浏览器实测：`build/_fontmap_live_check.html` / `build/_fontmap_live_check_broken.html`

---

## 1. 成因

### 1.1 字库表在内容包里的格式

`FontCodec`（`rom-editor/js/textcodec.js`）内部的两张 Map **键/值是数字**：

```js
this.codeToChar.set(parseInt(code, 16), ch);   // Map<数字, 字符>
this.charToCode.set(ch, parseInt(code, 16));   // Map<字符, 数字>
```

而**内容包里**同样的字形码写成**十六进制字符串**（无 `0x`、4 位大写）：

```jsonc
"code_to_char": { "8140": "　", … },   // 键 = 字形码
"char_to_code": { "　": "8140", … }    // 值 = 字形码
```

Python 侧 `tools/export_content_pack.py` 就是这么写的（`f"{code:04X}"`），
**格式是对的，不要动它**。实测 `rom-editor/content/pack.json` 里 4,261 个键与
4,253 个值**全部**是 4 位大写十六进制。

### 1.2 两处把 Map 直接塞回普通对象

| 位置 | 写法 |
|---|---|
| `rom-editor/js/parsepack.js:379-380`（旧） | `code_to_char: Object.fromEntries(template.font.codeToChar)`<br>`char_to_code: Object.fromEntries(template.font.charToCode)` |
| `rom-editor/js/pack.js:206-207`（旧） | 同上，但来源是 `this.font.*`（**导出**路径） |

`Object.fromEntries(map)` 把数字键/值变成**十进制字符串**：

```
0x8140 ⇒ "33088"    0x8167 ⇒ "33127"    0x8DC0 ⇒ "36288"
```

`FontCodec` 再 `parseInt("33088", 16)` ⇒ 得到 **`0x33088`**（不是 `0x8140`）
⇒ 查表**全部落空**。

### 1.3 为什么是「全部」而不是「部分」

`parseInt("33088", 16)` = 209,536 —— 一个**超出字形码范围**的大数。
所以坏映射下 `codeToChar` 的键**没有一个**等于任何真实字形码：
解码 ⇒ 每个字都变 `{字XXXX}`；`undecodedCount` ⇒ **每个**码都算「解不出来」
⇒ 每段都挂红字；`charToCode` 同理 ⇒ encode 把整句写成别的字节。

### 1.4 两条独立的受害路径

1. **解析路径**（编辑器的「从 ROM 中解析」按钮 → `app.js:406`）：
   `parsePackFromRom(state.pack, …)` ⇒ 坏的 `font` 块 ⇒ `ContentPack.fromJSON(pack)`
   ⇒ 整个内容包的字库是坏的。
2. **导出路径**（`ContentPack.toJSON()` ⇒ 「导出内容包」）：
   导出的 `pack.json` 里两张表是十进制 ⇒ **再导入回来也是坏的**
   （这一条即使不经过解析路径也会中招）。

---

## 2. 证据

### 2.1 坏映射复刻（`build/_fontmap_probe.mjs`）

```
  0x8167 好: "“"  坏: undefined  修: "“"
  0x8DC0 好: "好"  坏: undefined  修: "好"
  codeToChar size: 好 4261  坏 4261  修 4261      ← 数量一样，内容全错
encode：
   "好"      好 -> 8D C0   坏 -> 62 88    修 -> 8D C0
   "鸣人"    好 -> 92 98 94 C8  坏 -> 75 28 80 88  修 -> 92 98 94 C8
decode（ROM 0x8009F3D 那句）：
   好 -> "“好～～！！　　\n出发啦～～～～！！”　　　　"
   坏 -> "{字8167}{字8DC0}{字8160}{字8160}{字8149}{字8149}{字8140}{字8140}\n{字8A95}…"
```

⇒ **坏映射下 encode 写出的字节是完全错误的另一句话**（不只是丢未知码）。

### 2.2 真浏览器实测（headless Chrome）

`node rom-editor/tools/serve.mjs 8123` 起服务，然后：

```
chrome --headless=new --dump-dom --virtual-time-budget=25000 http://localhost:8123/build/_fontmap_live_check_broken.html
```

**旧写法（变异体 `build/_mut_parsepack.js`）**：

```
解析出来的字库：4261 键，示例 33088,33089,33090
键是十六进制字符串：false
页面里的红色提示（class=bad）：147 条
  例：这段正文里有 16 个字库解不出来的字形码，改写会丢掉它们。
  第 2 句的红字：这段正文里有 26 个字库解不出来的字形码，改写会丢掉它们。
正文输入框：147 个
  第 1 句：{字8167}{字8DC0}{字8160}{字8160}{字8149}{字8149}　　↵{字8A95}{字8C40}{字90AF}…
正文里有 {字 占位符：true
输入框里有 disabled 的：147
```

⇒ **与用户截图逐字一致**（占位符格式、红字文案、每段一条、输入框全被禁）。

**修好之后（`build/_fontmap_live_check.html`）**：

```
解析出来的字库：4261 键，示例 8140,8141,8142
键是十六进制字符串：true
页面里的红色提示（class=bad）：0 条
正文输入框：147 个
  第 1 句：“好～～！！　　↵出发啦～～～～！！”　　　　
  第 2 句：“你兴奋个什么劲啊，　　　　　　　↵去波之国的准备已经做好了吗！？”　　　　
正文里有 {字 占位符：false
输入框里有 disabled 的：0
构建错误数：0
重建的 ROM 与原版逐字节相同：true（首个差异 -1）
再解析回来的字库键集合与 pack.json 相同：true
```

---

## 3. 改法

### 3.1 `rom-editor/js/pack.js`（新增一个共用转换）

```js
function fontCodeHex(code) {
  return code.toString(16).toUpperCase().padStart(4, '0');
}

export function fontTablesToJson(font) {
  const codeToChar = (font && font.codeToChar) || new Map();
  const charToCode = (font && font.charToCode) || new Map();
  return {
    code_to_char: Object.fromEntries(
      [...codeToChar].map(([code, ch]) => [fontCodeHex(code), ch])),
    char_to_code: Object.fromEntries(
      [...charToCode].map(([ch, code]) => [ch, fontCodeHex(code)])),
  };
}
```

`toJSON()` 改成 `font: fontTablesToJson(this.font)`。

### 3.2 `rom-editor/js/parsepack.js`

`font` 块改成 `...fontTablesToJson(template.font)`（`fontTablesToJson` 从
`./pack.js` 导入 —— `parsepack.js` 本来就 import 那个文件，没有循环依赖）。

**两张表都要转**：`code_to_char` 的**键**、`char_to_code` 的**值**。
只转一张 ⇒ 另一半仍然是坏的。

### 3.3 为什么不动 `textcodec.js`

`FontCodec` 的构造器**行为是对的**（它只认十六进制字符串，这也正是
`pack.json` 的格式）。问题在**调用方**把 Map 直接倒回普通对象。
把 `FontCodec` 改成也吃数字键，只会把「包里的表是十六进制字符串」这条
契约搅乱（Python 侧导出的包就是十六进制字符串）。⇒ `textcodec.js` **零改动**。

---

## 4. 门禁：`rom-editor/tools/verify_font_map.mjs`（42 条断言）

| 节 | 断什么 |
|---|---|
| 1 | 基准：`pack.json` 两张表本身是 4 位大写十六进制（4,261 / 4,253） |
| 2 | **从 ROM 解析出来的**两张表与 `pack.json` **逐格相同** |
| 3 | **能解出真对白**：ROM `0x08009F3D` 那句解出 `“ 好 ～ ！ 出发啦`，**没有 `{字`** |
| 4 | **encode 往返**：decode → encode 与 ROM 那段**逐字节相同**；单字「好」= `8D C0` |
| 5 | **导出路径**：`ContentPack.fromJSON(pack.toJSON())` 之后字库完全一致，且仍能解码/编码 |
| 6 | **编辑器层面**：`textSegments()` 的 `problem` 为空（红字的来源）；**全剧 7,488 段**没有一条「字库解不出来」 |
| 7 | **无头渲染真实 UI 模块** `renderScriptView`：`class="bad"` **0 个**、147 个输入框全是中文、**0 个 disabled** |
| 8 | **端到端**：解析 → 构建 → 再解析，ROM 逐字节相同、字库逐格相同、13 张文本表逐表相同 |
| 9 | **变异对照**（见下） |

### 4.1 变异对照：门禁真的有牙吗

第 9 节把 `parsepack.js` / `pack.js` 的输出**改回数字键**，但**改的是
`build/font-map-mutation/` 下的临时副本**（相对 import 被改写成绝对
`file://` URL 才能 import 进来）—— **仓库文件零改动**。然后把**同一批**
断言跑在变异体上，要求它们**必须红**：

```
变异点命中：parsepack.js 里确实有那一行 — fontTablesToJson(template.font)
变异体：code_to_char 与 pack.json **不同**（第 2 节会红） — 4261 个键，示例 33088,33089,33090
变异体：char_to_code 与 pack.json **不同**（第 2 节会红） — 4253 个值，示例 33176,33102,33163
变异体：键不是十六进制字符串（是十进制）
变异体：解不出真对白（第 3 节会红） — {字8167}{字8DC0}{字8160}{字8160}{字8149}{字81
变异体：decode → encode 不再逐字节相同（第 4 节会红） — 「好」编成 62 88
变异体：「好」编成乱码字节（数据损坏） — 62 88
变异点命中：pack.js 的 toJSON 里确实有那一行 — font: fontTablesToJson(this.font),
变异体：导出的 code_to_char 与 pack.json **不同**（第 5 节会红）
变异体：导出的键不是十六进制字符串（是十进制）
```

⇒ 断言与变异体**同源**（同一个 `auditFontTables` / `auditCodec`），
所以「会红」不是猜的，是跑出来的。

---

## 5. 同类写法扫描（全仓库）

`grep 'Object.fromEntries'` 全仓命中 3 处：

| 位置 | 判定 |
|---|---|
| `rom-editor/js/pack.js:206-207` | **就是本 bug**，已修 |
| `rom-editor/js/parsepack.js:379-380` | **就是本 bug**，已修 |
| `third_party/konoha-workshop/…/check_editor_core_suite.js:10` | 无关（算文件 sha256 用），不动 |

「期望十六进制字符串键、却收到数字键」的反向情况：

| 位置 | 判定 |
|---|---|
| `rom-editor/tools/verify_free_space.mjs:52` | `font: { code_to_char: {}, char_to_code: {} }` —— 空表，无所谓 |
| `tools/probe_orphan_bytes.mjs:32` | 直接读 `pack.json`，键本来就是十六进制字符串 |
| `tools/build_reloc_test_rom.mjs:58` | 用的是 `pack.font.charToCode.get(ch)`（Map），不是普通对象 |
| `rom-editor/tools/verify_*.mjs` 里的 `font.charToCode` | 都是 Map 用法（`.get` / `.keys()`），正确 |

⇒ **除上面两处，没有第三处同类写法。**

---

## 6. 顺手记下、但**没有**修的三件事（不在本次范围内）

> 这三条都是真的、都能复现，但**与本 bug 无关**，别把它们混进来。
> 留给下一个会话按台账接着干。

| # | 现象 | 位置 | 判定方法 | 状态 |
|---|---|---|---|---|
| A | `parsepack.js` 里 `coverage` / `segments_total` / `duplicate_characters` 读的是 `template.font.coverage` —— **`FontCodec` 上没有这三个属性**（`'coverage' in font === false`）⇒ 解析出来的包里这三个字段恒为 `undefined`（JSON 序列化后直接消失）。`pack.json` 里原本是 `26 / 26 / 8` | `parsepack.js:381-383` | 解析后 `pack.font.coverage === undefined` | **已确认** |
| B | `ContentPack.toJSON()` **不导出** `derived` 与 `map_assets`（`'derived' in exported === false`）⇒ 导出内容包后再导入，「这个地址指向什么」的判定（`pointerTarget`）与地图资源描述全丢 —— 而 `fromJSON` 是收这两个字段的 | `pack.js::toJSON` | 导出前后 `derived` 是否为 `null` | **已确认** |
| C | `ContentPack.fromJSON(data)` 只做**浅拷贝** ⇒ 构建 ROM 时惰性写进记录的 `tokens` 缓存会**漏回调用方**手里的数据对象（门禁比较文本表时必须忽略 `tokens`） | `pack.js::fromJSON` | `JSON.stringify` 比较两次解析结果会差一个 `tokens` 字段 | **已确认**（本次踩到，已在门禁里忽略） |

---

## 7. 假设台账

| 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|
| H1：`code_to_char` 的键必须是十六进制字符串 | `parseInt(k, 16)` 能否还原出 ROM 里的字形码 | 能（`"8140"` → `0x8140`） | **已确认** |
| H2：坏映射下**每一次**查表都落空 | 坏 `FontCodec` 的键集合 ∩ 真实字形码集合 | 空集（`parseInt` 出来都是 5 位数） | **已确认** |
| H3：红字的唯一来源是 `undecodedCount > 0` | `scripttext.js:249` ⇒ `problem` ⇒ `scriptview.js:222` 渲染 `span.bad` | 确认，且 `problem` 还会让输入框 `disabled` | **已确认** |
| H4：修好之后**所有**段都不再报红（不只是那一句） | 全剧扫 `textSegments()` | 7,488 段，0 段有问题 | **已确认** |
| H5：真浏览器里也是这个症状（不是只在 Node 里） | headless Chrome 跑变异体 | 147 条红字 + 147 个 `{字…}` 输入框 | **已确认** |
| H6：一个字都不改 → 构建 → ROM 逐字节相同 | `buildRom` 后逐字节比 | 6,291,456 字节全等 | **已确认** |
| H7：`FontCodec` 本身没问题（问题在调用方） | `pack.json` 原样喂给 `FontCodec` | 解码 / 编码全对 | **已确认** |
| H8：Python 侧 `export_content_pack.py` 的格式不用动 | 看 `f"{code:04X}"` | 与 JS 侧修好后**逐格相同** | **已确认** |

---

## 8. 改了哪些文件

| 文件 | 改了什么 |
|---|---|
| `rom-editor/js/pack.js` | 新增 `fontCodeHex()` + `fontTablesToJson()`；`toJSON()` 改用后者 |
| `rom-editor/js/parsepack.js` | `font` 块改用 `fontTablesToJson(template.font)` |
| `rom-editor/tools/verify_font_map.mjs` | **新建**：42 条断言的门禁（含变异对照 + 无头渲染真实 UI 模块 + 端到端往返） |
| `build/_fontmap_probe.mjs` | 改成「修前 / 修后」对照探针，并吐出 `build/_mut_parsepack.js` 给真浏览器复现旧症状 |
| `notes/evidence/font-map-roundtrip-20261023.md` | **新建**：本文件 |

**没有动**：`rom-editor/content/pack.json`、`tools/export_content_pack.py`、
`rom-editor/js/textcodec.js`（理由见 §3.3）、其它任何仓库文件。
**没有 `git commit`。**
