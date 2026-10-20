# 游戏文本编码：自定义双字节字形码（不是 Shift-JIS）

**日期**: 2026-10-20
**工具**: `tools/konoha_font.py`、`tools/font_roundtrip.py`
**状态**: ✅ 已静态验证 + 字节级往返验证

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

| 工具 | 问题 | 建议 |
|---|---|---|
| `tools/extract_dialogue_full.py` | 用 cp932/gbk 双解，必然乱码 | 改用 `konoha_font.decode_at` |
| `tools/extract_text_block.py` | shift_jis 解码 | 同上 |
| `tools/find_sjis_blocks.py` | 按 SJIS 首字节范围扫描 | 改为按字形段范围扫描 |
| `tools/patch_sjis.py` | **用 shift_jis 写回，会写坏 ROM** | 改用 `konoha_font.encode_text` |
| `tools/import_dialogue.py` | 默认 `encoding="cp932"` 写回 | 增加 `encoding="font"` 分支 |
| `tools/import_dialogue_var.py` | 同上 | 同上 |
| `tools/import_rom_to_editor.py` | 注释断言 SJIS | 改注释并改用字形码 |
| `tools/automated_test.py` | 默认 encoding "cp932" | 同步 |
| `tools/translate_sjis_to_chinese.py` | 手工建映射的旧路子 | 已被字形段映射取代 |
| `tools/decode_dialogue_record.py` | 依赖手工表 `sjis-to-tile-mapping.json` | 改用 `konoha_font` |

**写回类工具在改用字形码之前，应当视为高风险**：
用 cp932 编码中文写入 ROM 只会得到错误字节，且
`notes/patch-generator-audit.md` 已有的"原字节校验"只能挡住位置错位，
挡不住编码错。

## 8. 复现

```powershell
python tools/konoha_font.py
python tools/font_roundtrip.py
python tools/decode_story_script.py --scene 1
python tools/dump_story_text.py --all --out build/story_text.txt
```
