# 逆向工程 Bank 完成度审计

生成时间：`2026-07-11T14:28:11.294496+00:00`

范围：bank metadata/entries/verification/documentation and base-ROM byte fidelity; no runtime or write-back validation。因此本报告不能证明运行时语义或实际回写闭环。

## 汇总

- 发现 `32` / 预期 `32` 个 bank。
- 同时满足六项元数据与字节检查：`32` / `32`。
- `table_offset`：`32` / `32`。
- `format`：`32` / `32`。
- `entries`：`32` / `32`。
- `verification`：`32` / `32`。
- `documentation`：`32` / `32`。
- `rom_fidelity`：`32` / `32`。
- verification 分布：`code_verified`=1, `runtime_verified`=2, `static_verified`=29。

## 逐结构结果

| 结构 | table_offset | format | entries | verification | 文档覆盖 | ROM字节 | 完整 | 问题 |
|---|---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| `audio` | ✅ `0x53F138` | ✅ | ✅ (88) | ✅ `static_verified` | ✅ (16) | ✅ (88) | ✅ | — |
| `battle-config` | ✅ `0x545458` | ✅ | ✅ (32) | ✅ `static_verified` | ✅ (15) | ✅ (256) | ✅ | — |
| `battle-encounters` | ✅ `0x542384` | ✅ | ✅ (38) | ✅ `static_verified` | ✅ (11) | ✅ (38) | ✅ | — |
| `battle-handlers` | ✅ `0x53E6D8` | ✅ | ✅ (14) | ✅ `static_verified` | ✅ (10) | ✅ (14) | ✅ | — |
| `character-stats` | ✅ `0x54507A` | ✅ | ✅ (20) | ✅ `static_verified` | ✅ (13) | ✅ (160) | ✅ | — |
| `character-stats-b` | ✅ `0x545200` | ✅ | ✅ (18) | ✅ `static_verified` | ✅ (12) | ✅ (144) | ✅ | — |
| `cutscene-scripts` | ✅ `0x53DF70` | ✅ | ✅ (16) | ✅ `static_verified` | ✅ (10) | ✅ (16) | ✅ | — |
| `data-table-a` | ✅ `0x5A14A4` | ✅ | ✅ (20) | ✅ `static_verified` | ✅ (9) | ✅ (20) | ✅ | — |
| `data-table-b` | ✅ `0x5A2120` | ✅ | ✅ (20) | ✅ `static_verified` | ✅ (9) | ✅ (20) | ✅ | — |
| `encounter-zones` | ✅ `0x53D910` | ✅ | ✅ (47) | ✅ `static_verified` | ✅ (19) | ✅ (423) | ✅ | — |
| `fonts` | ✅ `0x53E5B4` | ✅ | ✅ (256) | ✅ `static_verified` | ✅ (8) | ✅ (256) | ✅ | — |
| `function-pointers` | ✅ `0x53D5F4` | ✅ | ✅ (11) | ✅ `static_verified` | ✅ (9) | ✅ (11) | ✅ | — |
| `items` | ✅ `0x546100` | ✅ | ✅ (12) | ✅ `static_verified` | ✅ (14) | ✅ (84) | ✅ | — |
| `levels` | ✅ `0x5459D4` | ✅ | ✅ (47) | ✅ `static_verified` | ✅ (12) | ✅ (282) | ✅ | — |
| `map-events` | ✅ `0x53EB08` | ✅ | ✅ (47) | ✅ `static_verified` | ✅ (12) | ✅ (47) | ✅ | — |
| `map-sprites` | ✅ `0x53F1DC` | ✅ | ✅ (47) | ✅ `static_verified` | ✅ (9) | ✅ (47) | ✅ | — |
| `maps` | ✅ `0x53D910` | ✅ | ✅ (47) | ✅ `static_verified` | ✅ (28) | ✅ (423) | ✅ | — |
| `menu-ui` | ✅ `0x5A5774` | ✅ | ✅ (20) | ✅ `static_verified` | ✅ (9) | ✅ (20) | ✅ | — |
| `palettes` | ✅ `0x53F138` | ✅ | ✅ (88) | ✅ `static_verified` | ✅ (12) | ✅ (88) | ✅ | — |
| `positions` | ✅ `0x5461C4` | ✅ | ✅ (1728) | ✅ `runtime_verified` | ✅ (19) | ✅ (10368) | ✅ | — |
| `resource-pointers` | ✅ `0x596F0C` | ✅ | ✅ (20) | ✅ `static_verified` | ✅ (9) | ✅ (20) | ✅ | — |
| `sappy-engine` | ✅ `0x079668` | ✅ | ✅ (1) | ✅ `code_verified` | ✅ (8) | ✅ (1) | ✅ | — |
| `save-state` | ✅ `0x053D848` | ✅ | ✅ (10) | ✅ `static_verified` | ✅ (11) | ✅ (20) | ✅ | — |
| `skills` | ✅ `0x546100` | ✅ | ✅ (12) | ✅ `static_verified` | ✅ (14) | ✅ (84) | ✅ | — |
| `sprite-animations` | ✅ `0x53F200` | ✅ | ✅ (38) | ✅ `static_verified` | ✅ (9) | ✅ (38) | ✅ | — |
| `story` | ✅ `0x53636C` | ✅ | ✅ (9) | ✅ `static_verified` | ✅ (25) | ✅ (9) | ✅ | — |
| `story-b` | ✅ `0x536BC8` | ✅ | ✅ (11) | ✅ `static_verified` | ✅ (11) | ✅ (11) | ✅ | — |
| `story-c` | ✅ `0x538FF0` | ✅ | ✅ (10) | ✅ `static_verified` | ✅ (10) | ✅ (10) | ✅ | — |
| `story-d` | ✅ `0x53AB78` | ✅ | ✅ (11) | ✅ `static_verified` | ✅ (10) | ✅ (11) | ✅ | — |
| `story-e` | ✅ `0x53C3C0` | ✅ | ✅ (9) | ✅ `static_verified` | ✅ (10) | ✅ (9) | ✅ | — |
| `tile-assets` | ✅ `0x5A3218` | ✅ | ✅ (6) | ✅ `static_verified` | ✅ (9) | ✅ (6) | ✅ | — |
| `units` | ✅ `0x54241C` | ✅ | ✅ (63) | ✅ `runtime_verified` | ✅ (18) | ✅ (252) | ✅ | — |

## 判定规则

- `table_offset`：必须为非负整数；若有 `table_offset_hex`，两者必须一致。
- `format`：`format`、`entry_format` 或已知领域格式字段至少一个非空。
- `entries`：必须是非空数组；若声明 `entry_count`，必须与实际数量一致。
- `verification`：必须是 `static_verified`、`code_verified` 或 `runtime_verified`。
- 文档覆盖：`docs/*.md` 或 `notes/*.md` 至少一处提到结构目录名、bank 路径或表偏移。
- `rom_fidelity`：已提取字段的 `*_hex` 必须与校验过的基准 ROM 对应字节一致。
