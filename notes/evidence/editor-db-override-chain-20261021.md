# 编辑器 → 构建的 override 链：从「空转」到「可复现」（2026-10-21）

> 这份笔记记两件事：
> ① `sequel/editor.db` 不在版本库里，导致**纯净检出下整条 override 链空转**；
> ② 顺着这条链查出来的一批**活的 ROM 破坏路径**（生成器还写着旧基址和旧字段名）。

---

## 1. 问题：`editor.db` 被 gitignore ⇒ 链在纯净检出下空转

`sequel/editor.db` 是 SQLite 二进制库，`.gitignore` 里有 `*.db`，所以它不入库。
后果是：

* `tools/build_db_patches.py` 的每个生成器开头都是
  `if not db_path.exists(): return []` ——
  **没有数据库时，链安静地返回空列表**；
* 于是 `tools/build_mod.py` 构建出来的 ROM **一个 editor-db 派生的补丁都没有**，
  而「没有补丁」和「构建正确」长得一模一样，**没人会发现**；
* `tools/automated_test.py` 的 `db_integrity` 套件因此在纯净检出下
  只能用一个合成库顶替（`build_synthetic_editor_db`）。

## 2. 修法：把数据库变成**可推导**的，而不是「手提」的

新增 `tools/build_editor_db.py`：

1. 建编辑器自己的 schema（`web-editor/backend/database.py::init_db`）；
2. 建 + 填 `rom_*` 表（`web-editor/backend/rom_models.py`，从
   `sequel/content/*/bank.json` 读）；
3. 导入可编辑的行（units / dialogues / skills / story_beats / chapters /
   battle_configs / audio_files / unit_positions，源同样是那些 bank）；
4. **证明链不再空转**：把 `tools/build_db_patches.py` 里的**每一个**
   `generate_*` 跑一遍，要求至少产出一个补丁。

```powershell
$env:PYTHONIOENCODING='utf-8'
python tools\build_editor_db.py            # 重建 sequel/editor.db
python tools\build_editor_db.py --check    # 只验证链，并逐个生成器报 applied/rejected
```

实测（2026-10-21）：

```
editor.db tables:
  units 43   dialogues 298   skills 94   story_beats 55
  chapters 5 battle_configs 9   audio_files 0   unit_positions 0
override chain:  applied 5533  rejected 549
OK: the editor -> build override chain produces 5533 patch(es)
```

`--check` 会把**每一个**生成器的 applied / rejected 分开列出来 ——
「全部被拒」的生成器就是**基址或字段名已经过期**的信号。

## 3. 顺带查出来的活的 ROM 破坏路径（13 个生成器）

生成器写 ROM 时用的 `table_offset` / `pointer_column` 还是**旧基址与旧字段名**。
旧基址全是「真表里的错位窗口」，所以这些生成器会**往真实表的中间写**：

| 生成器 | 旧基址（旧字段） | 真基址（新字段） | 写到的位置 |
|---|---|---|---|
| `generate_battle_encounter_patches` | `0x542384`（`entry`） | `0x54229C`（`ptr_0`） | 记录 16 字节步长、+0 |
| `generate_battle_handler_patches` | `0x53E6D8`（`handler_ptr`） | `0x53E698`（`code_ptr_0`） | 记录 8 字节步长、+0 |
| `generate_data_table_a_patches` | `0x5A14A4`（`data_ptr`） | `0x5A143C`（`rom_ptr`） | 4 字节步长 |
| `generate_data_table_b_patches` | `0x5A2120`（`data_ptr`） | `0x5A2034`（`rom_ptr`） | 4 字节步长 |
| `generate_function_pointer_patches` | `0x53D5F4`（`func_ptr`） | `0x53D5F0`（`slot_value`） | 4 字节步长（槽 0/12 是哨兵） |
| `generate_map_event_patches` | `0x53EB08`（`handler_ptr`） | `0x53E698`（`code_ptr_0`） | 记录 8 字节步长、+0 |
| `generate_menu_ui_patches` | `0x5A5774`（`ui_ptr`） | `0x5A4DEC`（`expr0_ptr_0`） | 记录 40 字节步长、+0 |
| `generate_tile_asset_patches` | `0x5A3218`（`tile_ptr`） | `0x5A320C`（`tile_ptr_0`） | 记录 68 字节步长、**+12** |
| `generate_story_b/c/d_e_patches` | `0x536BC8` / `0x538FF0` / `0x53AB78` / `0x53C3C0`（`chapter_ptr`） | `0x536BC4` / `0x538FEC` / `0x53AB74` / `0x53C3BC`（`voicegroup_ptr`） | 头 + 4 |
| `generate_font_patches` | `0x53E5B4` | `0x53E596` | 1 字节步长 |
| `generate_character_stats_b_patches` | `0x545200`（`hp`/`padding1`/…） | `0x545068`（`field_0`…`field_7`） | 16 字节步长 × 63 |

**还有一处更隐蔽的 bug**：helper `_generate_u32_pointer_table_patches` 原来把
补丁偏移算成 `table_offset + index * 4`，而**记录步长并不是 4**
（遭遇记录 16、处理器记录 8、头像行 40、图块记录 68）。
即使把基址改对，补丁也会落在**记录中间**。
已给 helper 加了 `record_stride` 与 `field_offset` 两个参数，并把它们写进调用点。

**另外**：helper 的「陈旧导入」护栏拿**行首偏移**（`_rom_offset`）和
`table_offset + index*stride` 比，这个语义是对的；
补丁真正写入的地址是 `行首 + field_offset`。护栏没有被削弱。

## 4. 测试侧的修正

`tools/automated_test.py` 的 `patches` 套件原来拿**隔离构建的报告**去比对
**项目配置的输出 ROM**（`build/naruto-sequel-dev.gba`）——
这两者来自**不同的 editor.db**（提交的那份是开发者本机库做的），
所以一建库就必然对不上。已改成：报告与 ROM **取同一对**（隔离目录里的那份）。
`build/naruto-sequel-dev.gba` 与 `build/naruto-sequel-build-report.json` 未被改动。

`tests/test_u32_pointer_patches.py` 的合成库也更新成新基址与新字段名，
并补了「记录步长 ≠ 4」的用例。

## 5. 判死检验

| 检验 | 命令 | 失败意味着 |
|---|---|---|
| 链不再空转 | `python tools\build_editor_db.py --check` | 退出码 1 = 链没产出补丁 |
| 没有「全部被拒」的生成器 | 同上，逐行看 `rejects everything` 标记 | 某个生成器的基址/字段名又过期了 |
| 补丁真的落对了地址 | `python tools\automated_test.py`（`bytes patches correctly applied in output ROM`） | 报告里的偏移与 ROM 里的字节不一致 |
| 写回路径仍自洽 | `python tools\writeback_paths.py rom\base.gba` | 18 条往返自检有失败 |

## 6. 复现命令

```powershell
$env:PYTHONIOENCODING='utf-8'
python tools\build_editor_db.py
python tools\build_editor_db.py --check
python tools\automated_test.py
python tools\writeback_paths.py rom\base.gba
```
