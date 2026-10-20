# DB 写回面与生成器的基址更正（2026-10-20 晚）

> 本文记录本轮在 `tools/build_db_patches.py` / `tools/import_*.py` / `tools/automated_test.py`
> 上发现并修掉的一批缺陷：**方法**和**结果**都记在这里，便于以后复核。

## 0. 触发点

完成度审计（`tools/completion_audit.py`）在接上**可执行写回探针**之后，
`writeback_usable` 仍然是 9/46。把 12 条往返自检真正跑起来之后，
`tools/writeback_paths.py` 一口气交出 11 条可写回路径（后来补到 12 条），
但审计仍把「写回路径可用」判给旧的 `grep` 型探针 ——
于是暴露出两类问题：

1. **生成器写到的地址和裁决结论对不上**；
2. **编辑器→构建的 override 链实际上是断的**。

## 1. 方法：先看 ROM 里那里到底有什么

裁决结论说「`0x53F200` 没有原生读者」，这**只**说明游戏没有把这个地址
当成基址用，**不等于**那一片是死空间。判断「往那里写会不会踩到活数据」，
光看读者数不够，要看**那片地址的原生内容**。

做法：把每个 DB 生成器会写的目标地址连同长度取出来，dump 该区间的原生
u32 字，再按取值分类（`romptr` = 合法 ROM 指针 / `wram` / `small` / `zero` /
`other`）：

```python
# 片段：tools/ 下一次性脚本，结论已并入下面的表
words = [struct.unpack_from("<I", rom, target + i * 4)[0] for i in range(count)]
```

结果（摘要）：

| 地址 | 原生内容 | 判定 |
|---|---|---|
| `0x53F138` / `0x53F1DC` / `0x53F200` | 全是 ROM 指针 | **同一张活表 `0x53F140` 的不同窗口** |
| `0x596F0C` | 全是 ROM 指针 | 精灵动作表 `0x596CCC + 0x240` 的窗口 |
| `0x5A14A4` / `0x5A2120` / `0x5A5774` / `0x5A3218` | 全是 ROM 指针 | 真实指针表，基址只是没被字面量点名 |
| `0x53E6D8` / `0x53EB08` / `0x53D5F4` / `0x536BC8` … | 全是 Thumb 代码指针 | 真实函数指针表 |

**结论**：这些地址都不是死空间，都有活数据。所以问题不是「写了会不会坏」，
而是**「写进去的东西有没有意义」** —— 一个生成器按错误的条目形态往一张
结构化的表里写，就会破坏结构。

## 2. 修掉的 5 个基址/框架缺陷

| # | 生成器 | 原来 | 现在 | 依据 |
|---|---|---|---|---|
| 1 | `generate_sprite_animation_patches` | 写 `0x53F200`，38 项 × u32 | 写 **`0x596CCC`**，576 项 × 16 字节（4 个 u32 指针） | `CONFLICTS['0x53f200']`；`0x596CCC` 有 18 个原生读者、`muls` 按 id 索引 |
| 2 | `generate_map_sprite_patches` | 写 `0x53F1DC`，47 项 | 写 **`0x53F140`**，86 项 | `CONFLICTS['0x53f1dc']`：`0x53F1DC = 0x53F140 + 0x9C`（第 39 项窗口）；bank.json 本来就写的是 `0x53F140`/86 |
| 3 | `generate_palette_patches` | 写 `0x53F138`，88 项 | **拒绝写**，指向精灵动作表的第 4 个指针（palette_ptr） | `CONFLICTS['0x53f138']`：`0x53F138` 零读者，是 `0x53F140` 数组头部 2 个代码指针的窗口；精灵调色板是 32 字节 BGR555，挂在动作条目第 4 个指针上 |
| 4 | `generate_resource_pointer_patches` | 写 `0x596F0C`，20 项 × u32 | **拒绝写**，指向 `rom_sprite_animations` | `CONFLICTS['0x596f0c']`：`0x596F0C = 0x596CCC + 0x240` = 第 36 项（id 4 / action 0）；20 个 u32 其实是 5 个条目的 4 类指针，单列 `resource_ptr` 表达不了是哪一类 |
| 5 | `generate_save_state_patches` | 第二个 u32 叫 `sram_offset`、描述写「存档描述符」 | 叫 **`alloc_size`**（分配大小），描述写「WRAM 分配」 | `0x53D848` 是 **WRAM 分配表**（10 组 `{u32 wram_addr, u32 size}`，4 个原生读者 `0x0806869A/0x08068954/0x08068CC0/0x08068D98`）；存档数据在 SRAM，不在 ROM |

另外 `generate_cutscene_script_patches` 的 docstring 写「17 entries」，
实际是 **16**（`0x53DF70 + 16*4 = 0x53DFB0` 就是下一张表的起点）。

> 拒绝语义沿用仓库里已有的先例：`generate_unit_patches` 早就因为
> 「`0x53F298` 的 char_id 没有已证明的映射」而拒绝写。返回的记录类型是
> `db_palette_unmapped` / `db_resource_pointer_unmapped`，
> 带 `error` 与 `description`，**不是**静默返回空列表。

## 3. 编辑器 → 构建的 override 链：根因是**键集交集为空**

`tools/build_db_patches.py::generate_editor_dialogue_overrides` 的逻辑是
「editor.db 的 `dialogues.key` 等于 bank 的 `entry.id` 就当 override」。
实际两个键空间是：

| 来源 | 键 | 例 |
|---|---|---|
| editor.db `dialogues.key`（由 `dialogue-bank-full.json` 的 `slot` 灌入） | 槽序号 | `group0`、`group1`、`group10` |
| `dialogue-bank.json` / `dialogue-patches.json` 的 `id` | 语义名 | `group0.main`、`group0.label1`、`group1.main` |

**交集为空**，所以即使数据库里塞满 298 行，override 也是 **0 条**。

修法不是改名，而是**按 ROM 偏移连接**：

```
dialogue-bank-full.json : slot --text_offset--> ROM 偏移
dialogue-bank.json      : id  --text_rom_offset--> ROM 偏移
                              ⇒ slot --offset--> id
```

实测 7 条 curated entry 里 6 条能接上（`proof.menu.same_length_00076d`
没有 `text_rom_offset`，接不上也不需要接）。

**第二个坑**：full bank 是从 `build/naruto-sequel-dev.gba` 抽的，
它的解码文本和 `rom/base.gba` 对不上（例：槽 `group0` 在 dev ROM 里是
版本标记 `ROMV_20260624_100950`，在 base ROM 里是「把九尾妖狐封印在鸣人
体内的…）。如果把种子文本当 override 推回 base ROM，会**静默覆盖真对白**。

所以现在只有**作者真的改过**的行才算 override：DB 里的文本与
`dialogue-bank-full.json` 的种子文本相同 ⇒ 视为未改，交给内容 JSON 说了算。

回归：`tests/test_editor_dialogue_overrides.py`（3 条，全绿）覆盖
「未改 ⇒ 无 override」「改过 ⇒ override 且键是 `group0.main`」「未知槽忽略」。

## 4. 新的奖励表写回路径

`tools/reward_rules_semantics.py`（本轮由子代理从原生代码证明）给出了
24 字节奖励记录的完整布局，于是补了 `tools/import_reward.py`：

```
+0x00 u16 gold            +0x02 u16 upgrade_points    +0x04 u16 tier
+0x06      8 个 2 字节尾槽：低字节 = 类别标签(0..3)，高字节 = 物品 id（0 表示结束）
+0x16 u8  恒为 0、无人读  +0x17 u8  恒为 0、无人读
```

写回时用 ROM 自带的 **类别→名字表指针表 `0x59F5E0`**（`0x0808A02A` 载入、
用尾字节做下标）算出该类别的名字表容量，**越界的 id 直接拒绝**，
而不是靠手写的上界。`tools/writeback_paths.py` 新增 `reward-table` case，
12 条路径全部 PASS。

## 4.5 网页编辑器里两条**活的**破坏路径（2026-10-21）

`web-editor/backend/routers/battle_configs.py::export_battle_config_rom`
在导出补丁时有两条会**实际写坏 ROM**的路径，都是绕过仓库守卫的：

### (a) 把编辑器 `char_id` 写进 `0x53F298`

```python
unit_data = struct.pack(f"<{len(all_units)}H", *[u.get("char_id", 0) for u in all_units][:64])
patches.append({"type": "bytes", "offset": 0x53F298, ...})
```

`tools/build_db_patches.py::generate_unit_patches` **早就拒绝**这个写
（"legacy char_id has no proven ROM character-record mapping"），
但网页编辑器自己又写了一遍。本轮证明了 `0x53F298` 是什么：
**43 项的 u16 重映射表**，值被加上 WRAM `0x0202CA24` 的运行时 u16 后
掩到 16 位（见 `notes/evidence/units-offset-table-20261020.md`）。
写 `char_id` 进去 = 毁掉重映射 + 可能把游戏指向 64 KB 窗口里的任意位置；
而且旧的 64 项框架还会越过表尾写进 `0x53F2EE` 的邻表。

**修法**：不再写 `0x53F298`，改成在返回值里报一条 `skipped` 诊断，
并指出规范路径（编成矩阵 `0x5461C4`）。

### (b) 地图描述符用了**已证伪的基址**，还把三个指针清零

```python
scenario_offset = 0x53D914 + scenario_id * 32          # 旧基址
scenario_data  = bytes.fromhex("0100000000000000000000000000000002000000")
```

两处错：

1. `0x53D914` 是**旧逻辑的错误基址**；真正的基址是 **`0x53D910`**
   （原生 loader `0x08069040` 直接以 `0x0853D910 + id*32` 定位，
   `0x53D914` 是第 0 项的 `+0x04` 字段即 tile gfx 指针）。
   见 `tools/table_registry.py::CONFLICTS['0x53d910']` 与
   `notes/battle-config-unsafe-template-fix-20260710.md`。
2. 那 16 字节把 `+0x04`（tile gfx）、`+0x08`（palette）、`+0x0C`（layer0）
   **三个指针全清零** —— 导出的地图会什么都没有。

**修法**：按仓库统一的写回模型，**复制原生条目**再只改编辑器真正拥有的字段
（`+0x1C` background_id）；原生条目读不到就**跳过**并在返回值里报告。
改完的效果（实测）：scenario 0 的 `+0x04` 仍是 `0x080B9F80`，
scenario 40 的是 `0x08118620` —— 不再被清零。

> 这两条**都不在**完成度审计的 47 个结构里（它们是**代码路径**，
> 不是数据表），所以审计查不出来。审计能抓的是「表写错了」，
> 抓不到「有人绕过守卫直接写」。**这类路径只能靠人读代码**。

## 5. 顺带修掉的两个测试缺陷
| 测试 | 症状 | 根因 | 修法 |
|---|---|---|---|
| `tests/test_u32_pointer_patches.py::test_second_batch_wrappers_cover_declared_real_tables` | 7 个子测试全红 | 断言用的是**已证伪**的 `0x53F200`；而且读的是被 gitignore 的 `sequel/editor.db`，纯净检出下什么都没测 | 改成用**合成**数据库（表名/列名/行数/`_rom_offset` 都按真实契约造），断言改成裁决后的真实基址；另加两条：精灵动作表必须写 `0x596CCC`、被证伪的两个别名必须**拒绝**而不是写字节 |
| `tests/test_positions_integration.py::test_build_syncs_rom_mirror_before_generating_patches` | 1 个 error：`sqlite3.OperationalError: unable to open database file` | `tempfile.NamedTemporaryFile` 在 Windows 上**持有句柄**，sqlite 打不开同一个路径 | 先 `temp.close()` 再让 sqlite 打开（其它测试本来就是这么写的） |
| `tools/automated_test.py::db_integrity` | 27/28 | 依赖被 gitignore 的 `sequel/editor.db` | 没有真库时改用**合成**库（`build_synthetic_editor_db`），并新增断言：被证伪的两个表必须拒绝写、且必须**显式**拒绝（不能静默返回空） |

## 6. 回归结果

| 命令 | 改动前 | 改动后 |
|---|---|---|
| `python -m unittest discover -s tests -p 'test_*.py'` | 74 tests / 7 failures + 1 error | **79 tests / OK** |
| `python tools/automated_test.py` | 27/28 | **28/28** |
| `python tools/completion_audit.py --check` | 退出 0 | 退出 0（阻塞缺口 31 → 1） |
| `python tools/writeback_paths.py rom/base.gba` | — | 12/12 PASS |

## 7. 留下的开放问题

1. `cutscene-scripts`（`0x53DF70`）的块格式**已裁决**（见
   `notes/evidence/cutscene-block-format-20261020.md`）：它**不是**剧情 VM
   脚本表，而是**关卡数据块表** —— 4 项 × 8 字节，每项一对指针
   （LZ77 4bpp 图块、LZ77 16 色调色板）。由此又带出两处更正：
   - 旧结构库「16 项 × u32」把**两张表并成了一张**（`0x53DF90` 起是同一函数
     另读的对象描述符表，`0x53DFB0` 起是第三张字节表）。写回路径的条目数
     收到 **8 个 u32 槽（4 项）**，`build_db_patches.py` 的 `entry_count`
     同步收紧 —— 旧的 16 槽模型允许下标写进隔壁那张表。
   - 块格式既然是 LZ77，**图形/调色板的内容级改写**在机械上已经可行
     （原地改载荷且解压长度不变）。这属于**新结构**（关卡图形资源），
     不应混在 `cutscene-scripts` 名下，**尚未单独立项**。
2. `0x53D848` 的「存档语义」仍未证伪到「ROM 里根本没有存档描述符表」这一步 ——
   已知的只有：它是 WRAM 分配表，存档数据在 SRAM。
3. 其余 legacy 基址（`0x5A14A4` / `0x5A2120` / `0x5A5774` / `0x5A3218` …）
   仍然**没有原生读者**，但原生内容是实打实的指针表 —— 说明游戏是通过
   别的字面量（指针表 / 基址+偏移）到达它们的，基址**未证**。
   要放开写回，得先像 `0x53F140` 那样把「谁读它」钉死。
4. `tools/populate_bank_json.py` 里另有几个旧基址（`0x53F1DC` / `0x53F138` /
   `0x596F0C` / `0x53F200`）仍写在那里，但它们已被**裁决守卫**跳过，
   不会覆盖裁决结果；`0x53DF70` 的那一处已按新几何更正。

## 8. 复现命令

```powershell
python tools\writeback_paths.py rom\base.gba
python tools\completion_audit.py --check
python -m unittest discover -s tests -p 'test_*.py'
python tools\automated_test.py
python tools\import_reward.py rom\base.gba --index 0 --set gold=500 \
    --set slots='[{"category":0,"item_id":3}]'
```
