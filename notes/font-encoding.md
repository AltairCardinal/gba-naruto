# 游戏文本编码：自定义双字节字形码（不是 Shift-JIS）

**日期**: 2026-10-20
**工具**: `tools/konoha_font.py`、`tools/font_roundtrip.py`
**状态**: ✅ 已静态验证 + 字节级往返验证
**关联**: `notes/why-external-editor-shipped-20261020.md`（方法论复盘）、
`notes/external-konoha-workshop-gap-20261020.md`（差集清单）、
`notes/story-script-vm.md`（剧情脚本 VM）、
`notes/text-writeback-migration-20261020.md`（写回路径迁移，**已落地**）

---

## 0. 结论

**本仓库此前对游戏文本编码的判断是错的。**

`notes/dialogue-format.md` 原先写"Encoding: cp932 (Shift-JIS with extensions)"，
并据此产出了乱码样例：

```
著畔愃榔撒誼「吶責」米候扮坦級？
```

实际编码是**游戏自带的双字节字形码**：首字节落在 `0x80..0x9F` 时，
`code = 首字节 * 256 + 次字节`，该 code 对应 ROM 内置字库里的一个字形。
把这类字节当 cp932 解，必然得到乱码。

**直接影响**：`tools/extract_dialogue_full.py`（cp932+gbk 双解）、
`tools/extract_text_block.py`（shift_jis）、`tools/find_sjis_blocks.py`、
`tools/patch_sjis.py`（用 shift_jis **写回**）、`tools/import_dialogue.py`
与 `import_dialogue_var.py`（默认 encoding="cp932" 写回）、
`tools/import_rom_to_editor.py`（注释断言 "GBA's native text encoding is SJIS"）
全部建立在错误前提上。**其中写回类工具会用错误编码改写 ROM，需要按本文修正。**

> **2026-10-20 更新**：写回类工具已全部改为字形码（见 §7 与
> `notes/text-writeback-migration-20261020.md`）。
> 附带查明：**此前所有对白补丁写进 ROM 的都是玩家读不懂的乱码**，
> 因为作者写的日文被按 cp932 编码进了中文字形 ROM；
> 而且历次验收只检查"字节落位"，从未检查"渲染成什么"。
> 现在 `tools/verify_text_writeback.py` 直接回读渲染结果作为门禁。

---

## 1. 字形段表（0x53D644）

| 项 | 值 |
|---|---|
| ROM 地址 | `0x0853D644`（file `0x53D644`） |
| 槽位 | 31 × 8 字节 |
| 段格式 | u16 起始码 / u8 字数 / u32 字形偏移（ROM 指针） |
| 每字形 | 32 字节 4bpp 索引 |
| 本 ROM 非空段 | 26 |

本 ROM 实测段表（`tools/konoha_font.py` 输出）：

```
seg 0 start=0x8140 count=109   seg13 start=0x9140 count=189
seg 1 start=0x8240 count=178   seg14 start=0x9240 count=189
seg 2 start=0x8340 count=151   seg15 start=0x9340 count=189
seg 3 start=0x8740 count=32    seg16 start=0x9440 count=189
seg 4 start=0x889F count=94    seg17 start=0x9540 count=189
seg 5 start=0x8940 count=189   seg18 start=0x9640 count=189
seg 6 start=0x8A40 count=189   seg19 start=0x9740 count=189
seg 7 start=0x8B40 count=189   seg20 start=0x9840 count=51
seg 8 start=0x8C40 count=189   seg21 start=0x9873 count=138
seg 9 start=0x8D40 count=189   seg22 start=0x9940 count=189
seg10 start=0x8E40 count=189   seg23 start=0x9A40 count=189
seg11 start=0x8F40 count=189   seg24 start=0x9B40 count=189
seg12 start=0x9040 count=189   seg25 start=0x9C40 count=255
```

全码位空间为 `0x8140..0x9D3F`，共 4261 个有效码位。

### 1.1 这张表只对应 8×8 字形（2026-10-20 修正）

用无头 mGBA 探针把场景 54 的对白**真的画出来**之后（画面见
`notes/evidence/story-scene-l3.png`，证据见
`notes/evidence/story-scene-l3-20261020.md`），实测：

- 对白框里的**汉字是 16×16**（而这张段表的字形是 8×8 4bpp / 32 字节）；
- 字距实测约 12 px = 汉字 16 px + ASCII 标点 8 px，即**两种宽度并存**；
- 渲染器 `0x08065EB8` 取字形时是 `lsls r0, r0, #5`（×32），
  证实这张表只服务 8×8 的小字（任务文字、名牌一类）；
- 全 ROM 扫描**没有**找到第二张同构的段表（31 项、start 递增、count>0、
  glyph offset 合法），所以 16×16 对话字形的来源**尚未定位**。

### 1.2 再修正一次：对话汉字的位图在**第三处**（2026-10-20 晚）

把屏幕像素反查成调色板索引后逐字节比对给出更强的结论：

| 结论 | 证据 |
|---|---|
| 对话汉字是 **16×16**、ASCII 标点是 **8×8** | 屏幕字距实测；两者都不是 `0x53D644` 的 8×8 4bpp 位图 |
| `0x53D644` 这张表的 32 字节字形**无法**复现屏幕上的汉字 | 试遍 8×8 4bpp / 8×16 2bpp / 16×8 2bpp / 16×16 1bpp / 2 倍放大各向，最佳平均差异 27/128 像素（真正匹配应为 0） |
| **「屏幕 → 调色板索引 → ROM 字节」的反推链在密集汉字上不成立** | 16×16 单元重测：**所有**文字格都匹配不上。文字带抗锯齿/半透明混合，屏幕颜色不是字形索引的直接投影 |

> **一次被推翻的断言（留档）**：本轮曾据上述反推链声称「屏幕上一个 8×16 单元与
> ROM `0x0813E209` 的 32 字节逐字节相同」。**该断言是错的** ——
> 那个格子只有 2 个墨迹像素，匹配到的是 ROM 里的**零填充区**。

**候选表（均未证实）**：`0x0813E040`（u16 字形偏移表）、
`0x0813E120`（字形数据）、`0x0596D60`（u32 指针表）、
`0x0142A70`（24 字节步进指针表）、`0x0142AC0`（(u16 code, u16 count) 对表）。
清单与留档见 `notes/resource-locations.md`。

**因此本文件的适用范围要写清楚**：

- `0x53D644` 描述的是**字形码的编码**（码位 → 汉字）以及它自己那套 8×8 4bpp 位图。
  码位空间 `0x8140..0x9D3F`（4261 个）**在全 ROM 通用** ——
  剧本解码出的中文与屏幕显示逐字一致（`notes/evidence/text-encoding-l3-20261020.md`）。
- **对话汉字的位图数据**属于另一处 ROM 数据，本轮只列出**候选**，
  **既没有证实**哪一张是它，**也没有**解出「码位 → 字形偏移」的索引规则。

> 待办：先用**渲染器**（而非屏幕反推）确定对话字体的位图格式 ——
> 即在宿主里加一条「把 VRAM 里的 tile 反汇编成位图」的能力，
> 或直接读出文本层 tile 的原始 4bpp 数据；
> 然后把屏幕像素与 ROM 字形逐位对上。

## 2. 文本扫描规则

| 首字节 | 含义 | 占用 |
|---|---|---|
| `0x00` | 字符串结束 | 1 字节 |
| `0x01` | 控制码 | 2 字节 |
| `0x02` | 控制码 | 3 字节 |
| `0x0A` | 换行 | 1 字节（码位 10） |
| `0x20..0x7E` | ASCII | 1 字节 |
| `0x80..0x9F` | **双字节字形码** | 2 字节 |
| 其它 | 单字节码位 | 1 字节 |

特殊：`0x8140` = 全角空格「　」。

### 2.1 控制码必须保留（写回时的关键点）

原版文本里夹着 `01 xx` / `02 xx yy` 控制码，**解码成字符串时会丢失**，
所以**改写已有文本不能用纯字符串编码**，否则会破坏排版。

正确做法是按 **token 流**处理：

```python
tokens = konoha_font.scan_tokens(rom, offset)          # [('text', code), ('ctrl', b'..'), ...]
text   = konoha_font.tokens_to_string(tokens, mapping) # 给人看的文本
raw    = konoha_font.encode_tokens(tokens, mapping)     # 原样写回，字节级一致
```

实测 5 个真实文本样本的 token 级往返：

```
story/dialogue text bank entry 0: bytes_equal=True  ctrl_codes=0
mission title, stage 1            : bytes_equal=True  ctrl_codes=0
character name, id 1              : bytes_equal=True  ctrl_codes=0
mission description, stage 1      : bytes_equal=True  ctrl_codes=4
story script text, scene 1        : bytes_equal=True  ctrl_codes=0
```

**写新内容**（全新字符串）可以用 `encode_text()`；
**改写已有内容**必须用 token 流。

### 2.2 少数字符有多个码位

字库里有 8 个字符对应两个码位（多为最后一段补字）：

```
'鸣' -> 0x9298 / 0x9876      '吵' -> 0x8A51 / 0x987B
'吨' -> 0x8BD3 / 0x9CF3      '嘎' -> 0x8CBF / 0x9880
'哼' -> 0x8DDC / 0x989E      '摸' -> 0x929D / 0x9875
'嘻' -> 0x97F8 / 0x9CCE      '吱' -> 0x9BD0 / 0x9CD3
```

反向映射取**最小码位**，因此新写入的文本显示正确，但**不保证与原 ROM 字节相同**
（这 8 个字除外，其余完全一致）。对同长度替换无影响。

## 3. 码位 → 汉字映射的来源

两条独立来源，互相印证：

### 3.1 ROM 姓名表自证（61 个码位）
`0x599280 + id*4` 是角色姓名指针。用姓名表里的已知姓名逐字比对码位，
可无歧义确定 61 个码位（`tools/konoha_font.py: seed_from_name_table`）。
**这是完全独立于任何外部资料的锚点。**

### 3.2 第三方推断表 + 字形指纹校验（4200 个码位）
`third_party/konoha-workshop/editor/text_catalog.js` 提供推断出的
"段起始码 / 字数 / FNV-1a 指纹" 与 "码位→汉字" 对照。

**关键安全机制**：映射只在**字形段指纹匹配**时才应用——
对段内 `count*32` 字节算 FNV-1a，与推断表里的指纹比对。
换一份字库不同的 ROM，指纹不匹配，映射自动不生效（而不是给出错误汉字）。

本 ROM 实测：**26/26 段指纹全部匹配**，映射覆盖 4261 码位，**0 个未解析**。

## 4. 验证证据

### 4.1 指纹校验通过
```
font segs  : 26 non-empty of 31
catalog    : matched 26/26 segments
mapping    : 4261 codes total
unresolved : 0
```

### 4.2 字节级往返一致
```
story/dialogue text bank entry 0: '把九尾妖狐封印在鸣人体内的\n是第几代火影？'
    bytes_equal=True  decode_stable=True
mission title, stage 1            : '保护达兹纳先生不被鬼兄弟攻击！'
    bytes_equal=True  decode_stable=True
character name, id 1              : '漩涡鸣人'
    bytes_equal=True  decode_stable=True
```
即 `encode(decode(bytes)) == bytes`，**写回路径可用**。
（token 级往返见 §2.1，5/5 样本字节级一致。）

### 4.3 语义自洽
- `0x461CE8` 指针表首条解出 "把九尾妖狐封印在鸣人体内的/是第几代火影？"，
  其后三条指针解出 "第４代" "第３代" "第１代" —— 是一道**四选一问答**，完全自洽。
- 剧情第 1 场解出鸣人喊"出发啦～～～～！！"、小樱"去波之国的准备已经做好了吗！？"、
  达兹纳（波之国委托人）登场 —— 与原作剧情一致。
- 角色 31 解出"达兹纳"，其对白"漩涡鸣人！给我记住了！！"确为委托人对鸣人的说话。

### 4.4 姓名表 62 条全部解出
```
  1 漩涡鸣人   2 宇智波佐助   3 春野樱      4 山中井野    5 奈良鹿丸
  6 秋道丁次   7 旗木卡卡西   8 犬冢牙      9 油女志乃   10 日向雏田
 11 日向宁次  12 李洛克     13 天天       14 我爱罗     15 勘九郎
 16 手鞠     17 萨克      18 多斯       19 金        20 桃地再不斩
 21 白       22 篝        23 胧         24 梦火      25 业头
 26 冥头     27 草鞋      28 草覆       29 大蛇丸     30 木叶丸
 31 达兹纳    32 卡多的手下   33 不明忍者    34 不明忍者   35 傀儡人偶
 36 熊       37 老虎      38 蜈蚣      39 大蛇　头   40 大蛇　尾
 41 猫       42 旗本卡卡西  43 第三代火影  44 伊鲁卡     45 猿飞阿斯玛
 46 夕日红    47 阿凯      48 惠比斯     49 伊那里     50 卡多
 51 御手洗红豆 52 森乃伊比喜  53 手内      54 志治美     55 蜜蜂
 56 津美     57 犬冢牙    58 勘九郎     59 秋道丁次   60 李洛克
 61 药师兜    62 岸本齐史
```
（62 号"岸本齐史"是原作作者彩蛋。）
**这 62 个名字用到的所有字符 100% 可编码**（0 个缺失），
说明这份映射对该 ROM 的汉字覆盖是完整的。

## 5. 对旧手工映射表的判定

`sequel/content/text/sjis-to-tile-mapping.json` 是手工做的 20 字符表，
注释称取自 `0x459414` 的字节。实测：

| | 解出的内容 |
|---|---|
| ROM 指纹校验映射 | `把九尾妖狐封印在鸣人体内的 / 是第几代火影？` |
| 旧表（值再修复一层 mojibake） | `ʲô！？……真拿你û办法 / 最后һ次Ŷ！！` |
| 旧表与 ROM 一致的条目 | **0 / 20** |

旧表的**值本身是双重编码的乱码**（`"浠€"` 实为 `"什"`），
且它描述的句子根本不在该偏移处。**旧表应停用**，
改用 `tools/konoha_font.py` 的指纹校验映射。

## 6. 使用方式

```powershell
# 查看映射覆盖率与段指纹
python tools/konoha_font.py

# 往返验证 + 旧表判定
python tools/font_roundtrip.py

# 导出完整码位表（替代手工表）
python tools/font_roundtrip.py --emit-mapping sequel/content/text/font-code-map.json
```

API（`tools/konoha_font.py`）：

```python
mapping, report = konoha_font.build_mapping(rom)   # 指纹校验后的码位→汉字
text, nxt = konoha_font.decode_at(rom, offset, mapping)
raw   = konoha_font.encode_text("漩涡鸣人", mapping)  # 写回用
names = konoha_font.read_character_names(rom, mapping)
```

## 7. 对既有工具的影响与待办

> **2026-10-20 更新**：写回路径已迁移到字形码，见
> `notes/text-writeback-migration-20261020.md`。
> 统一编解码入口为 `tools/text_codec.py`（`encode` / `decode` /
> `decode_bounded` / `encode_tokens`）。
> 下表的"建议"列已落实；**遗留项**见该笔记 §5。

| 工具 | 状态 | 现状 |
|---|---|---|
| `tools/text_codec.py` | ✅ 新增 | 统一入口。`encoding="font"` 写字形码；legacy 编码发 `DeprecationWarning` |
| `tools/import_dialogue.py` | ✅ 已改 | 支持 `encoding="font"`（新增 `--rom`） |
| `tools/import_dialogue_var.py` | ✅ 已改 | 同上（变长 redirect 路径） |
| `tools/patch_sjis.py` | ✅ 已改 | 默认 `font`，新增 `--encoding` / `--rom`，打印渲染结果 |
| `tools/automated_test.py` | ✅ 已改 | 编码套件走字形码，并新增 3 条断言型用例 |
| `tools/extract_dialogue_full.py` | ✅ 已改 | 字形码解码；写文件显式 UTF-8（Windows 默认 gbk 会崩） |
| `tools/extract_text_block.py` | ✅ 已改 | 字形码解码 |
| `tools/import_rom_to_editor.py` | ✅ 已改 | 删除"SJIS / 乱码是 ROM 限制"的错误注释 |
| `tools/verify_text_writeback.py` | ✅ 新增 | 打补丁后回读渲染文字，断言 == 作者文本 |
| `tools/find_sjis_blocks.py` | ⚠️ 遗留 | 仍按 SJIS 首字节范围扫描，块列表不可信 |
| `tools/decode_dialogue_record.py` | ⚠️ 遗留 | 仍依赖手工表 `sjis-to-tile-mapping.json` |
| `tools/translate_sjis_to_chinese.py` | ⚠️ 已被取代 | 手工建映射的旧路子，现由 `text_codec` 承担 |
| `sequel/content/text/sjis-to-tile-*.json` | ⚠️ 已废止 | 旧手工表，值本身是双重编码乱码 |

**验收标准已升级**：以前的"原字节校验"只能挡位置错位，挡不住编码错；
现在 `tools/verify_text_writeback.py` 直接回读**渲染结果**，
`tools/automated_test.py` 也新增了"patched dialogue renders as the authored text"。

## 8. 复现

```powershell
python tools/konoha_font.py
python tools/font_roundtrip.py
python tools/decode_story_script.py --scene 1
python tools/dump_story_text.py --all --out build/story_text.txt
```

---

## 9. 反向映射的规范化（2026-10-20 补，取代 §2.2 的实现描述）

> §2.2 记录的"反向映射取最小码位"是**实现细节**，不是**判据**。
> 本节给出判据本身，并说明为什么"取最小"在 8 个重复字上**结果恰好正确**。

### 9.1 码位空间不是一整段

本次新查明（详见 `notes/evidence/font-reverse-mapping-20261020.md`）：

```
0x8140..0x889E   符号 / 假名 / 拉丁 块          418 个有标签
0x889F..0x9CC3   基准段：GB2312 一级字表拼音序   3754 个有标签
0x9873..0x989E   扩展段 A（插在基准段中间）      44 槽 / 39 个有标签
0x9CC4..0x9D3E   扩展段 B（接在基准段后面）     283 槽 / 50 个有标签 + 73 填充
```

* 基准段里 **GB2312 一级字表 3755 个字中有 3754 个按拼音序原样出现**，
  只缺 **编**（它被挪到扩展段 B 的 `0x9CC4`）；另有 **旋** 的槽位放着 **漩**。
* 扩展段 A/B 的 89 个字，**除"编"以外全部不在 GB2312 一级字表里**
  —— 它们本来就是给生僻字补的。

### 9.2 规范规则

> **一个字符用它在基准段里的码位编码。**
> 扩展段那一份是**冗余重复拼写**（基准段已经按 GB2312 标准槽位带着这个字），
> 因此不是规范码位。

8 个重复字（吵/吨/嘎/哼/鸣/摸/嘻/吱）**每一个**都是
"一个基准段码位 + 一个扩展段码位"，且**基准段码位都更小**。
所以旧实现取最小码位**结果上是对的**，但那是碰巧对的；
新实现把理由固定下来，并让 `tools/font_roundtrip.py` 每次运行都复核。

### 9.3 实现

* `tools/text_codec.py`
  * `EXTENSION_BLOCK_RANGES` —— 两个扩展段的码位区间；
  * `build_canonical_reverse_mapping()` —— 规则实现 + 逐字证据报告；
  * `canonical_mapping()` —— 只保留规范码位的 code→char 表，
    `encode()` 改走它，公开 API 不变；
  * `roundtrip_report()` —— 4261 个码位逐个往返自检。
* `tools/font_roundtrip.py` —— 24 项机器断言（失败即 exit 1）：
  (a) 4261/4261 往返；(b) 反向映射无歧义；
  (c) 每个重复字恰好一基准段 + 一扩展段码位，且"取最小"与规范规则逐字一致；
  (5) 从 ROM 重新推导扩展段，必须与 `text_codec` 的常量推出的 89 个码位**完全相同**。

### 9.4 边界：字节级一致性不是 100%

8 个字里有 5 个（吵/哼/鸣/嘻/吱）**游戏自身两种拼写都在用**，
所以"字符 → 码位"这种单值映射**在原理上无法**让
`encode(decode(bytes)) == bytes` 对它们成立。
**改写已有文本必须走 token 流**（`text_codec.encode_tokens()`，原样保留码位）；
纯字符串编码只适用于**全新文本**。

### 9.5 附带发现

ROM 里除字形码文本外，**还有 GB2312 编码的中文数据**
（例 `0x4DDB00`、`0x4C0C90`）。
这解释了为什么"按字节对全 ROM 扫"会产生大量假命中 ——
扫描器必须带"≥3 个字形码 + 全部可查 + CJK 占比 ≥70%"的判据。

### 9.6 复现

```powershell
python tools/font_roundtrip.py     # 24 项断言，失败即 exit 1
python tools/text_codec.py --self-test   # 4261/4261
```

### 9.7 两个遗留工具已退役（2026-10-20 晚）

§7 的工具表里这两行仍写着"⚠️ 遗留"，现已处理：

| 工具 | 处置 | 说明 |
|---|---|---|
| `tools/find_sjis_blocks.py` | ✅ 已重写 | 不再按 SJIS 首字节扫，改按**字形码**规则扫 ROM 的文本段并用 `text_codec` 解码。文件名的 "sjis" 已是历史遗留（`notes/completion-audit.py` 仍引用它，故保留文件名）。实测本 ROM 找到 9119 个文本块。 |
| `tools/decode_dialogue_record.py` | ✅ 已重写 | 不再依赖手工表 `sjis-to-tile-mapping.json`，改走 `text_codec`；并纠正了"0x8B62 是换行分隔符"的错误 —— `0x8B62` 其实是字形码 U+7684「的」。原表里的 30 个偏移是 **IWRAM 地址**（旧 RAM dump 的状态表），当成 ROM 文件偏移读只会得到乱码，工具现在会明确提示这一点。 |

两者都**不再使用 cp932/Shift-JIS**，也不再读已废止的手工表；
可用 `python tools/find_sjis_blocks.py` 与 `python tools/decode_dialogue_record.py` 直接复现。
