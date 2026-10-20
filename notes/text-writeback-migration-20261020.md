# 文本写回路径迁移：cp932 → 字形码（2026-10-20）

**工具**: `tools/text_codec.py`、`tools/migrate_text_bank_to_font.py`、
`tools/verify_text_writeback.py`、`tests/test_text_writeback.py`
**状态**: ✅ 写回链路已切换并端到端验收
**关联**: `notes/font-encoding.md`（编码本体）、
`notes/external-konoha-workshop-gap-20261020.md`（差集清单）、
`notes/story-script-vm.md`（剧情 VM）

---

## 0. 一句话结论

**此前仓库里所有对白补丁写进 ROM 的是玩家读不懂的乱码。**
以前只验证过"字节落到了正确偏移"，从未验证过"这些字节渲染出来是什么"。

迁移后：5/5 对白槽位渲染结果与作者文本**逐字相同**。

---

## 1. 之前到底发生了什么

`sequel/content/text/dialogue-patches.json` 里存的是 **mojibake**：
把 ROM 的字形码字节按 cp932 解出来的乱码字符。
再按 cp932 编回去，能得到原始字节 —— 所以"写回"在**字节层面**是自洽的。

但这套自洽有两个致命缺陷：

1. **写不进新内容**。任何中文都会被编码成 Shift-JIS 字节，游戏随后按字形码
   解释这些字节，画出的是碰撞到的随机字形。
2. **没人检查过渲染结果**。历次 "E2E ROM verification" 验证的是字节落地，
   不是玩家看到的东西。

### 1.1 实测：旧补丁写进去的是什么

把旧 `dialogue-patches.json` 的文本按 cp932 编码后，再用字形码映射回读：

| 槽位 | 作者写的（旧） | 旧路径写入的字节 | 游戏实际渲染 |
|---|---|---|---|
| `proof.menu.same_length_00076d` | `試験` | `8e8e8cb1` | `伙复` |
| `group0.main` | `希ROMV_20260624_100950丸` | `8af3…8adb` | `傣ROMV_20260624_100950崔` |
| `group0.label1` | `第１話` | `91e682509862` | `麻１夏` |
| `group1.main` | `忍刀の残党が附近に潜伏警戒せよ。` | `9445…8142` | `千赔の慌胚が深垛に砾甥汾昌せよ。` |
| `group2.main` | `輸送巻物守るべし。敵の狙いは明白だ。` | `9741…8142` | `停柳喘诗缄るべし。农の亮いは塘求だ。` |

**没有一条是人能读的。** 内容本身也是日文 —— 作者照着原版日文写的，
但 ROM 是熊组汉化版（字形码 → 中文），日文按 cp932 编码进中文 ROM 必然错位。

### 1.2 ROM 原文其实是中文

按字形码解码，ROM 里的原文是：

```
0x459414  把九尾妖狐封印在鸣人体内的\n是第几代火影？
0x459464  第４代
0x459488  忍者在使用术的时候\n需要的能源叫什么名字？
0x459508  鸣人为恶作剧发明的\n有点色的术叫什么名字？
0x00076D  测试　\n村边的森林　\n入口之森　　\n波之国入口　　\n…（标题画面菜单）
```

即：**这套 ROM 的文本本来就是中文**，此前的"乱码"全部是解码方式错误造成的，
不是 ROM 数据限制。

---

## 2. 做了什么

### 2.1 新增统一编解码入口 `tools/text_codec.py`

| API | 作用 |
|---|---|
| `load_mapping(rom_path)` | 取指纹校验过的码位→汉字映射（带缓存） |
| `encode(text, encoding, mapping)` | `encoding="font"` 写字形码；legacy 编码发 `DeprecationWarning` |
| `decode(data, mapping)` | 字节 → 玩家看到的文字 |
| `decode_bounded(rom, offset, max_bytes, mapping)` | 按槽位字节预算截断解码 |
| `encode_tokens` / `decode_tokens` | 保留控制码的改写路径 |

ROM 定位顺序：显式参数 → `$KONOHA_ROM` → `rom/base.gba` → 仓库根 `*.gba`。

### 2.2 写回链路改造

| 文件 | 改动 |
|---|---|
| `tools/import_dialogue.py` | 支持 `encoding="font"`；新增 `--rom` |
| `tools/import_dialogue_var.py` | 同上（变长 redirect 路径） |
| `tools/patch_sjis.py` | 默认改为 `font`，新增 `--encoding` / `--rom`；打印渲染结果 |
| `tools/automated_test.py` | 编码套件改走字形码，并新增 3 条断言型用例 |

### 2.3 内容库迁移

`sequel/content/text/dialogue-bank.json`：
- 7 个条目 `encoding` 全部 `cp932` → `font`
- `notes` 里的 mojibake 换成真实中文原文
- `expected_hex` **未改动**（仍是原始字节，作为补丁安全门禁的锚）

`sequel/content/text/dialogue-patches.json`：
- 文本从 mojibake 日文换成**真实中文**，对齐 `sequel/content/story/episode-01.json`
  的剧情草案（边境异动 → 山道遭遇 → 保护运输卷轴）
- 每条都受槽位字节预算约束（见 §4）

| 槽位 | 字节预算 | 新内容 |
|---|---|---|
| `proof.menu.same_length_00076d` | 4 | `开始` |
| `group0.main` | 41 | `边境情报异常\n小队被派往警戒线 V20261020` |
| `group0.label1` | 6 | `第一章` |
| `group1.main` | 41 | `山道遭遇不明忍者\n敌方企图夺取运输卷轴！` |
| `group2.main` | 41 | `保护运输卷轴！\n击退来袭的忍者部队！` |

### 2.4 读侧同步修复（否则编辑器里看到的还是乱码）

| 文件 | 改动 |
|---|---|
| `tools/extract_dialogue_full.py` | cp932/gbk 双解 → 字形码解码；显式 UTF-8 写文件（Windows 默认 gbk 编码会崩） |
| `tools/extract_text_block.py` | shift_jis → 字形码 |
| `tools/import_rom_to_editor.py` | 删掉"SJIS / 乱码是 ROM 限制"的错误注释 |

`dialogue-bank-full.json` 现在存的是**真实中文**，`text_ja` 与 `text_zh` 同值
（本 ROM 是汉化版，原日文已被替换、不可恢复；`text_ja` 是编辑器编辑的列，
必须可读）。

---

## 3. 验证证据

### 3.1 映射表自证（独立于第三方推断表）

ROM 自己的原文重新编码后，与 ROM 里的字节**逐字节一致**（7/7 条 bank 条目）：

```
bank 条目 expected_hex == ROM 实际字节        : 7/7
ROM 原文 --字形码编码--> 与 ROM 原字节逐字节相同 : 7/7
```

这不是循环论证：映射表来自第三方推断 + 姓名表自证，这里验证的是
**"解码出的文字能无损地编回原来的字节"**，任何码位错位都会立刻破坏它。

### 3.2 写回端到端验收 `tools/verify_text_writeback.py`

```
python tools/verify_text_writeback.py
python tools/verify_text_writeback.py --verify-rom build/naruto-sequel-dev.gba
```

两种模式都 **PASS**，5/5 槽位渲染结果 == 作者文本：

```
[OK  ] group0.main @ 0x459414 (41 bytes, encoding=font)
        authored : '边境情报异常\n小队被派往警戒线 V20261020'
        rendered : '边境情报异常\n小队被派往警戒线 V20261020'
...
RESULT: PASS - every patched slot renders the authored text
```

验收走的是**真实构建代码路径**（`import_dialogue` → `build_mod.apply_bytes_patch`），
`before_hex` 不匹配会直接抛错，所以过期 bank 无法蒙混过关。

### 3.3 产物三方对照（`build/text-writeback-artifact-evidence.json`）

同一批槽位在三个 ROM 里的渲染结果：

| 槽位 | 基准 ROM（原版） | **仓库已提交的构建 ROM** | 修复后重建 |
|---|---|---|---|
| `proof.…00076d` | `测试` | `伙复` ❌ | `开始` ✅ |
| `group0.main` | `把九尾妖狐封印在鸣人体内的\n是第几代火影？` | `傣ROMV_20260624_100950崔` ❌ | `边境情报异常\n小队被派往警戒线 V20261020` ✅ |
| `group0.label1` | `第４代` | `麻１夏` ❌ | `第一章` ✅ |
| `group1.main` | `忍者在使用术的时候\n需要的能源叫什么名字？` | `【T8涪聚-31482】` ❌ | `山道遭遇不明忍者\n敌方企图夺取运输卷轴！` ✅ |
| `group2.main` | `鸣人为恶作剧发明的\n有点色的术叫什么名字？` | `停柳喘诗缄るべし。农の亮いは塘求だ。` ❌ | `保护运输卷轴！\n击退来袭的忍者部队！` ✅ |

**已提交的 `build/naruto-sequel-dev.gba` 里就是乱码** —— 这是此前所有"已验证"
产物在玩家视角下的真实样貌。

### 3.4 构建与测试

```
python tools/build_mod.py --project sequel/project.json   → exit 0
    patch_class_counts: {game_effective: 5, audit: 0, diagnostic: 0}
    5 条补丁全部 encoding=font

python -m unittest discover -s tests -p 'test_text_writeback.py'  → Ran 11 tests, OK
python tools/automated_test.py                                 → 23/24
```

`automated_test.py` 唯一失败项 `db_integrity`（`sequel/editor.db` 缺失）
**是改动前就存在的环境问题**（已用 `git stash` 对比基线确认：
基线 31 tests / 7 failures / 1 error，其中 7 个 u32 失败 + 1 个 db 错误
在本次改动后依然存在且数量不变）。

### 3.5 变长 redirect 路径也打通

`tools/import_dialogue_var.py` 的"写空闲区 + 改指针表"分支此前**从未跑过**
（`dialogue_var` 未在 manifest 里启用），一跑就暴露 `ROM_BASE` 未定义的 `NameError`。
已修复，并补了回归测试：
`tests/test_text_writeback.py::test_variable_length_redirect_renders_the_authored_text`
—— 文本写入 `0x5DFBEC` 起的空闲区、指针表重定向后，沿指针读回仍是作者原文。

### 3.6 已提交的构建产物**未被覆盖**（有意为之）

仓库里那份 `build/naruto-sequel-dev.gba` + 构建报告是用
`sequel/editor.db` 生成的（`game_effective` 2443 / `audit` 471，
其中 `db_real` 2438、`db_audit` 471）。
该 DB 被 `.gitignore` 的 `*.db` 排除、本机不存在，**无法从 ROM 完整重建**
（`import_rom_to_editor.py` 只能填充已有 DB，不能建表造数据）。

直接重新构建会让这 2438 条 db 补丁消失 —— 等于拿"少一半内容"的产物
去覆盖"内容全但对白是乱码"的产物。因此**已提交产物保持原样**，
本次修复的验收改在隔离输出目录进行：

```powershell
$env:BUILD_OUTPUT_DIR='build/verify-writeback'
python tools/build_mod.py --project sequel/project.json
python tools/verify_text_writeback.py --verify-rom build/verify-writeback/naruto-sequel-dev.gba
# → PASS, 5/5
```

**待办**：要把产物本身也修好，需要先把 `sequel/editor.db` 纳入版本管理
（或提供一份可重建的种子），否则构建产物无法复现。

顺带把 `tools/automated_test.py` 的构建用例改成**隔离输出**
（`BUILD_OUTPUT_DIR=build/automated-test-build`）：此前该用例会直接跑
`build_mod.py` 覆盖 `build/naruto-sequel-dev.gba` 与构建报告，
等于每次跑测试就把已跟踪产物换成"少了 2438 条 db 补丁"的版本。

---

## 4. 现在重要的地址与约束

| 项 | 值 |
|---|---|
| 字形段表 | `0x53D644`（31 槽 × 8 字节），本 ROM 26 段非空 |
| 字形段指纹 | FNV-1a，26/26 与推断表匹配 |
| 码位空间 | `0x8140..0x9D3F`，4261 个码位，0 未解析 |
| 姓名表 | `0x599280`（62 条，映射自证锚点） |
| 对白指针表 | `0x461CE8` |
| 标题画面文本 | `0x00076D` |

**写回约束**：

1. 中文字符 = 2 字节，ASCII = 1 字节，`\n` = 1 字节。
2. 槽位预算 = `bank.max_bytes`；超出且无 `redirect_offset` 时构建必须失败。
3. 字库没有的字符 → `KeyError`，**不做替换**（错码会画出错字）。
4. 改写**已有**文本必须走 token 流（控制码 `0x01`/`0x02` 携带排版语义，
   纯字符串编码会丢）；写**全新**文本可用 `encode_text`。
5. 8 个字符有双码位（见 `notes/font-encoding.md` §2.2），反向映射取最小码位，
   同长度替换不受影响。

---

## 5. 遗留缺口

| 项 | 状态 | 说明 |
|---|---|---|
| `sequel/editor.db` 缺失 | 🔴 既有 | 被 `.gitignore` 的 `*.db` 排除，新检出里不存在 → 编辑器→构建的 override 链（`generate_editor_dialogue_overrides`）在纯净检出下是空转的；`tests/test_positions_integration.py` 也因此报错；**已提交的构建产物无法复现**（见 §3.6） |
| 已提交的 `build/naruto-sequel-dev.gba` | ⚠️ 仍含乱码 | 产物本身是对白乱码（§3.3 有证据）。修复在源码侧已就位并验收，重建产物被 `editor.db` 缺失阻塞 |
| `tools/find_sjis_blocks.py` | ⚠️ 未改 | 仍按 SJIS 首字节范围扫描，块列表不可信 |
| `tools/decode_dialogue_record.py` | ⚠️ 未改 | 仍依赖手工表 `sjis-to-tile-mapping.json`（已判定不可信） |
| `tools/translate_sjis_to_chinese.py` | ⚠️ 已被取代 | 手工建映射的旧路子，现由 `text_codec` 承担 |
| `sequel/content/text/sjis-to-tile-*.json` | ⚠️ 已废止 | 旧手工表，值本身是双重编码乱码；应停用（见 `notes/font-encoding.md` §5） |
| legacy `cp932` 编码 | ⚠️ 保留但告警 | `text_codec.encode` 对 legacy 编码发 `DeprecationWarning` |
| 游戏内实际观感 | ⬜ 未验 | 仍未做 mGBA 运行时截图/OCR 确认，只做了静态字节级+渲染级双重验收 |
---

## 6. 复现

```powershell
# 编码映射自检
python tools/text_codec.py

# 写回验收（对基准 ROM 应用补丁并回读渲染）
python tools/verify_text_writeback.py

# 验收已构建的 ROM
python tools/verify_text_writeback.py --verify-rom build/naruto-sequel-dev.gba

# 迁移工具（dry run / 应用）
python tools/migrate_text_bank_to_font.py --out build/migrate.json
python tools/migrate_text_bank_to_font.py --apply --bank-only

# 构建
python tools/build_mod.py --project sequel/project.json

# 测试
python -m unittest discover -s tests -p 'test_text_writeback.py'
```

---

## 7. 补：编辑器 → 构建 的 override 链在纯净检出下为什么是空的（2026-10-20 晚）

> §5 遗留表里"🔴 既有：编辑器→构建的 override 链在纯净检出下是空转的"这条，
> 本节给出**确切的链路**、**实测数据**与**用户该怎么做**。
> 结论比原记录更强：**这条链即使有 DB 也永远不生效**。

### 7.1 实际的链路（读三个工具得到）

```
sequel/patches/manifest.json            5 条 type="dialogue" 清单项
        │  bank    = sequel/content/text/dialogue-bank.json    （7 个条目，id 命名空间）
        │  content = sequel/content/text/dialogue-patches.json （作者写的正文）
        │  entry_id = group0.main / group0.label1 / ...
        ▼
tools/build_mod.py
        │  overrides = generate_editor_dialogue_overrides(sequel/editor.db)
        │             （**仅当 sequel/editor.db 存在**；key 必须命中 bank 的 id 集合）
        ▼
tools/import_dialogue.py  import_dialogue(bank, content, overrides=overrides)
        │
        ▼
   ROM 字节

另一条平行支线（同样以 editor.db 存在为前提）：
tools/build_db_patches.py  generate_db_patches / generate_battle_config_patches /
                           generate_chapter_patches / generate_unit_patches / ...
        → db_real 补丁（真 ROM 数据）+ db_audit 补丁（审计哨兵记录）
```

DB 的**建库**脚本不是 `tools/import_rom_to_editor.py`（它只 INSERT，
DB 不存在时直接 `FATAL` 退出 2），而是
**`web-editor/backend/database.py` 的 `init_db()`**（`CREATE TABLE IF NOT EXISTS`）。

### 7.2 两处断裂（都实测过）

**断裂 A —— 纯净检出里 DB 不存在（已知，已量化）**

`.gitignore` 的 `*.db` 把 `sequel/editor.db` 排除，纯净检出里没有它。
`build_mod.py` 的两处 `if editor_db_path.exists():` 于是全部跳过：

```
# 纯净检出（无 sequel/editor.db），隔离输出目录
$env:BUILD_OUTPUT_DIR='build/verify-d4'
python tools/build_mod.py --project sequel/project.json
→ exit 0
→ patch_class_counts: {"game_effective": 5, "audit": 0, "diagnostic": 0}
```

**构建照样 exit 0**，但只剩清单里那 5 条对白补丁；
DB 派生的真 ROM 补丁与审计补丁**一条都没有**（已提交产物里是 2438 + 471）。
即：**内容静默减半，构建不报错。**

**断裂 B —— 就算有 DB，override 链依然是空的（新发现，更根本）**

`generate_editor_dialogue_overrides()` 的匹配条件是
`row["key"] in {entry["id"] for entry in dialogue-bank.json["entries"]}`。
但两个命名空间根本不相交：

| 来源 | 字段 | 取值样例 |
|---|---|---|
| `editor.db` 的 `dialogues` 表 | `key` | `group0` / `group1` / `group2` …（来自 `dialogue-bank-full.json` 的 `slot` 字段，该文件**根本没有 `id` 字段**） |
| `dialogue-bank.json` | `entries[].id` | `group0.main` / `group0.label1` / `proof.menu.same_length_00076d` … |

实测（沙箱里建库 + 灌数据后）：

```
DB dialogue keys      : 298
dialogue-bank.json ids: 7  ['group0.label1', 'group0.label2', 'group0.label3',
                            'group0.main', 'group1.main', 'group2.main',
                            'proof.menu.same_length_00076d']
INTERSECTION          : []          ← 空集
generate_editor_dialogue_overrides(db) -> {}   （0 条 override）
```

**即使 DB 存在且有 298 行对白，override 数仍然是 0。**
所以"编辑器 → 构建"这条链**在架构上就不可能生效**，
不是"缺 DB 所以空转"这么简单。

### 7.3 架构上能不能修？—— 不能靠改 build_mod.py 解决

要让 override 生效，必须让**编辑器的 key 命名空间**和**构建的 bank id 命名空间**
对上，可选：

1. 让 `import_rom_to_editor.py` 写入 `group0.main` 这样的 key
   （但 `dialogue-bank-full.json` 里只有 `slot`，没有 `id`，得先改抽取器）；
2. 让 `generate_editor_dialogue_overrides()` 改成"按 `slot` 归属 + 后缀匹配"；
3. 让 `dialogue-bank.json` 的 `id` 改成 `group0` 这种短名。

三条都**要改 `tools/import_*.py` / `tools/build_db_patches.py` 这类本次不得改动的文件**，
且 1 和 3 都会改动已发布的 `id` 契约（清单里 5 条 `entry_id` 全部引用它）。
**结论：本次不动架构，改为把它记录清楚。**

### 7.4 用户该做什么（受支持的作者路径）

**改对白 → 改 `sequel/content/text/dialogue-patches.json`。**
这是构建真正读的正文文件（清单项的 `content` 字段）。
编辑器 DB 只是**只读镜像**（`import_rom_to_editor.py` 从 bank.json 灌进去），
不是写回路径。5 条受管槽位与字节预算见 §2.3。

**想用编辑器改数据并让构建带上 → 走"建库 → 灌库 → 构建"三步：**

```powershell
# 1) 建库（这一步是 web-editor 的 init_db，不是 tools/import_*.py）
$env:PYTHONUTF8='1'
python web-editor/backend/database.py        # → sequel/editor.db（917 KB）

# 2) 灌库（把 bank.json 的内容灌进编辑器可编辑表）
python tools/import_rom_to_editor.py

# 3) 构建（此时 db_real / db_audit 补丁才会产生）
$env:BUILD_OUTPUT_DIR='build/verify-d4'      # 别覆盖已提交的 build/naruto-sequel-dev.gba
python tools/build_mod.py --project sequel/project.json
```

> **Windows 注意事项（实测）**：`tools/import_rom_to_editor.py` 有两处编码缺陷，
> 在默认 GBK 控制台下会直接失败：
> 1. `json.load(open(full_path))` 没指定 encoding → 读 UTF-8 的
>    `dialogue-bank-full.json` 抛 `UnicodeDecodeError: 'gbk' codec can't decode byte 0xa3`；
> 2. 最后一行打印 `✅` 抛 `UnicodeEncodeError: 'gbk' codec can't encode character '\u2705'`。
>
> **必须先设 `$env:PYTHONUTF8='1'`**（UTF-8 模式同时修掉这两处），
> 或者至少设 `$env:PYTHONIOENCODING='utf-8'` 修掉第 2 处。

### 7.5 复现命令（不污染仓库状态）

沙箱建库（`sequel/editor.db` 在仓库里，不要就地创建 —— 它会改变
`tests/test_positions_integration.py` 的基线）：

```powershell
$tmp = Join-Path $env:TEMP 'naruto-d4'
New-Item -ItemType Directory -Force -Path (Join-Path $tmp 'sequel') | Out-Null
New-Item -ItemType Junction -Path (Join-Path $tmp 'sequel\content') `
         -Target 'D:\Github\gba-naruto\sequel\content' | Out-Null

$env:DB_PATH = (Join-Path $tmp 'sequel\editor.db')
$env:PYTHONUTF8 = '1'
python web-editor/backend/database.py            # 建库
cd $tmp
python 'D:\Github\gba-naruto\tools\import_rom_to_editor.py'   # 灌库

# 验证 override 链
cd D:\Github\gba-naruto
python -c "import sys,pathlib; sys.path.insert(0,'tools'); \
from build_db_patches import generate_editor_dialogue_overrides, count_db_rows; \
db=pathlib.Path(r'$tmp\sequel\editor.db'); \
print('overrides:', len(generate_editor_dialogue_overrides(db))); \
print('rows:', count_db_rows(db))"
```

实测输出：

```
overrides: 0
rows: {'dialogues': 298, 'units': 43, 'skills': 6, 'story_beats': 50,
       'audio_files': 0, 'battle_configs': 9, 'unit_positions': 0,
       'chapters': 5, 'user_permissions': 0}
```

### 7.6 一句话给用户

> **改对白请改 `sequel/content/text/dialogue-patches.json`；
> 编辑器改的数据要进构建，必须先 `python web-editor/backend/database.py` 建库
> （Windows 上还要 `$env:PYTHONUTF8='1'`），再 `python tools/import_rom_to_editor.py` 灌库，
> 最后 `python tools/build_mod.py --project sequel/project.json` 构建。
> 但即便如此，**对白 override 仍然不会生效**（命名空间不相交），
> 而且纯净检出下 DB 不存在，DB 派生的 2438 条补丁会静默消失而构建仍报成功。**
