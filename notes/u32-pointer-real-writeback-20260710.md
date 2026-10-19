# u32 指针表真实回写（2026-07-10）

## 尝试内容

- 核对 `tools/build_db_patches.py` 中 battle handler、cutscene、map event、map
  sprite、story B–E 的 audit-only 生成器。
- 交叉检查 `sequel/content/*/bank.json`、`sequel/editor.db` 的 `rom_*`
  schema、基准 ROM 指针范围和低位语义。
- 新增通用 `_generate_u32_pointer_table_patches()`，将纯指针表接到真实表槽位；
  混合值 `battle_encounters` 使用同样的索引/偏移安全检查但不强制指针语义。

## 学到的内容

1. 编辑器实际 schema 使用 `rom_battle_handlers`、`rom_map_events` 等名称，旧生成器
   查询无前缀表名，因此过去会静默返回空列表。
2. `battle_encounters@0x542384` 后续已证实是从真实视觉资源描述符中间开始的错位切片，旧行必须 diagnostic-only。
3. `cutscene_scripts@0x53DF70` 的第 17 个候选值是 `0x090A0809`，超出 48 Mbit
   ROM 地址空间。边界复核确认真实指针表是 16 项；`0x53DFB0` 是独立 byte
   table。两者分别在 ROM `0x072F3C`、`0x075C0C` 出现独立地址引用。
4. `battle_handlers@0x53E6D8` 是 Thumb 代码指针表；`map_events@0x53EB08`
   后续已证实是 256-pair 表的错位切片，旧真实回写已撤销。
5. `map_sprites@0x53F1DC` 是数据指针表，bit 0 必须为 0。story B–E 指向无对齐
   保证的字节流，奇数地址可以是实际数据地址，故只检查 ROM 范围。
6. 首次审计发现 `rom_battle_handlers` 和 `rom_map_sprites` 共 61 行的
   `_rom_offset` 来自错误 bank 偏移；helper 按预期全部拒绝。修正 bank 后已从
   SHA-1 校验过的基准 ROM 重新提取并重建 `rom_*` 镜像，现为 61/61 通过。

## 已形成的真实回写

| 表 | 重要范围 | 当前 DB 结果 |
|---|---:|---:|
| `rom_map_events` | legacy `0x53EB08..0x53EBC3` | 已撤销；diagnostic-only |
| `rom_story_b` | `0x536BC8..0x536BF3` | 11/11 真实补丁 |
| `rom_story_c` | `0x538FF0..0x539017` | 10/10 真实补丁 |
| `rom_story_d` | `0x53AB78..0x53ABA3` | 11/11 真实补丁 |
| `rom_story_e` | `0x53C3C0..0x53C3E3` | 9/9 真实补丁 |
| `rom_battle_handlers` | `0x53E6D8..0x53E70F` | 14/14 真实补丁 |
| `rom_map_sprites` | `0x53F1DC..0x53F297` | 47/47 真实补丁 |

第一批合计 149 个真实 ROM 字节补丁。

### 第二批纯指针表

| 表 | 重要范围 | `pointer_kind` | 真实补丁 |
|---|---:|---|---:|
| `rom_data_table_a` | `0x5A14A4..0x5A14F0` | data | 20 |
| `rom_data_table_b` | `0x5A2120..0x5A216C` | data | 20 |
| `rom_function_pointers` | `0x53D5F4..0x53D61C` | Thumb | 11 |
| `rom_menu_ui` | `0x5A5774..0x5A57C0` | data | 20 |
| `rom_resource_pointers` | `0x596F0C..0x596F58` | data | 20 |
| `rom_sprite_animations` | `0x53F200..0x53F294` | data | 38 |
| `rom_tile_assets` | `0x5A3218..0x5A322C` | data | 6 |

第二批的 bank 偏移、`rom_*._rom_offset` 和基准 ROM 值一致；135/135 行通过
范围、低位和索引检查。七个生成器已删除旧 audit-only 不可达实现。第一批七个
wrapper 后的旧不可达实现也在同一工作周期清理。

## 验证方法与结果

- `python3 -m unittest tests.test_u32_pointer_patches -v`：7/7 PASS；新增第二批七表
  的条目数、首尾槽位和全量 bytes patch 检查。
- 覆盖索引上下界、48 Mbit ROM 范围、Thumb bit、数据指针 bit、陈旧
  `_rom_offset`，以及 story 字节流奇数地址。
- `python3 -m py_compile tools/build_db_patches.py tests/test_u32_pointer_patches.py`：PASS。

下一步是 mGBA 消费路径验证；不能仅因为回写字节与基准 ROM 一致就
把结构升级为 `runtime_verified`。
