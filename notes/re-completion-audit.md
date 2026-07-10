# 逆向工程 Bank 完成度审计

生成时间：`2026-07-10T07:02:08.588122+00:00`

范围：bank metadata/entries/verification/documentation only; no runtime or write-back validation。因此本报告不能证明运行时语义或实际回写闭环。

## 汇总

- 发现 `32` / 预期 `32` 个 bank。
- 同时满足五项元数据检查：`32` / `32`。
- `table_offset`：`32` / `32`。
- `format`：`32` / `32`。
- `entries`：`32` / `32`。
- `verification`：`32` / `32`。
- `documentation`：`32` / `32`。
- verification 分布：`code_verified`=1, `static_verified`=31。

## 逐结构结果

| 结构 | table_offset | format | entries | verification | 文档覆盖 | 完整 | 问题 |
|---|---:|:---:|:---:|:---:|:---:|:---:|---|
| `audio` | ✅ `0x53F138` | ✅ | ✅ (88) | ✅ `static_verified` | ✅ (13) | ✅ | — |
| `battle-config` | ✅ `0x545458` | ✅ | ✅ (32) | ✅ `static_verified` | ✅ (13) | ✅ | — |
| `battle-encounters` | ✅ `0x542384` | ✅ | ✅ (38) | ✅ `static_verified` | ✅ (9) | ✅ | — |
| `battle-handlers` | ✅ `0x53E6D8` | ✅ | ✅ (14) | ✅ `static_verified` | ✅ (8) | ✅ | — |
| `character-stats` | ✅ `0x54507A` | ✅ | ✅ (20) | ✅ `static_verified` | ✅ (10) | ✅ | — |
| `character-stats-b` | ✅ `0x545200` | ✅ | ✅ (18) | ✅ `static_verified` | ✅ (10) | ✅ | — |
| `cutscene-scripts` | ✅ `0x53DF70` | ✅ | ✅ (17) | ✅ `static_verified` | ✅ (7) | ✅ | — |
| `data-table-a` | ✅ `0x5A14A4` | ✅ | ✅ (20) | ✅ `static_verified` | ✅ (7) | ✅ | — |
| `data-table-b` | ✅ `0x5A2120` | ✅ | ✅ (20) | ✅ `static_verified` | ✅ (7) | ✅ | — |
| `encounter-zones` | ✅ `0x53D910` | ✅ | ✅ (47) | ✅ `static_verified` | ✅ (15) | ✅ | — |
| `fonts` | ✅ `0x53E5B4` | ✅ | ✅ (256) | ✅ `static_verified` | ✅ (7) | ✅ | — |
| `function-pointers` | ✅ `0x53D5F4` | ✅ | ✅ (11) | ✅ `static_verified` | ✅ (7) | ✅ | — |
| `items` | ✅ `0x546100` | ✅ | ✅ (12) | ✅ `static_verified` | ✅ (10) | ✅ | — |
| `levels` | ✅ `0x5459D4` | ✅ | ✅ (47) | ✅ `static_verified` | ✅ (8) | ✅ | — |
| `map-events` | ✅ `0x53EB08` | ✅ | ✅ (47) | ✅ `static_verified` | ✅ (9) | ✅ | — |
| `map-sprites` | ✅ `0x53F1DC` | ✅ | ✅ (47) | ✅ `static_verified` | ✅ (7) | ✅ | — |
| `maps` | ✅ `0x53D910` | ✅ | ✅ (47) | ✅ `static_verified` | ✅ (20) | ✅ | — |
| `menu-ui` | ✅ `0x5A5774` | ✅ | ✅ (20) | ✅ `static_verified` | ✅ (7) | ✅ | — |
| `palettes` | ✅ `0x53F138` | ✅ | ✅ (88) | ✅ `static_verified` | ✅ (10) | ✅ | — |
| `positions` | ✅ `0x53D914` | ✅ | ✅ (8) | ✅ `static_verified` | ✅ (10) | ✅ | — |
| `resource-pointers` | ✅ `0x596F0C` | ✅ | ✅ (20) | ✅ `static_verified` | ✅ (7) | ✅ | — |
| `sappy-engine` | ✅ `0x079668` | ✅ | ✅ (1) | ✅ `code_verified` | ✅ (7) | ✅ | — |
| `save-state` | ✅ `0x053D848` | ✅ | ✅ (10) | ✅ `static_verified` | ✅ (9) | ✅ | — |
| `skills` | ✅ `0x546100` | ✅ | ✅ (12) | ✅ `static_verified` | ✅ (10) | ✅ | — |
| `sprite-animations` | ✅ `0x53F200` | ✅ | ✅ (38) | ✅ `static_verified` | ✅ (7) | ✅ | — |
| `story` | ✅ `0x53636C` | ✅ | ✅ (9) | ✅ `static_verified` | ✅ (18) | ✅ | — |
| `story-b` | ✅ `0x536BC8` | ✅ | ✅ (11) | ✅ `static_verified` | ✅ (9) | ✅ | — |
| `story-c` | ✅ `0x538FF0` | ✅ | ✅ (10) | ✅ `static_verified` | ✅ (8) | ✅ | — |
| `story-d` | ✅ `0x53AB78` | ✅ | ✅ (11) | ✅ `static_verified` | ✅ (8) | ✅ | — |
| `story-e` | ✅ `0x53C3C0` | ✅ | ✅ (9) | ✅ `static_verified` | ✅ (8) | ✅ | — |
| `tile-assets` | ✅ `0x5A3218` | ✅ | ✅ (6) | ✅ `static_verified` | ✅ (7) | ✅ | — |
| `units` | ✅ `0x53F298` | ✅ | ✅ (64) | ✅ `static_verified` | ✅ (14) | ✅ | — |

## 判定规则

- `table_offset`：必须为非负整数；若有 `table_offset_hex`，两者必须一致。
- `format`：`format`、`entry_format` 或已知领域格式字段至少一个非空。
- `entries`：必须是非空数组；若声明 `entry_count`，必须与实际数量一致。
- `verification`：必须是 `static_verified`、`code_verified` 或 `runtime_verified`。
- 文档覆盖：`docs/*.md` 或 `notes/*.md` 至少一处提到结构目录名、bank 路径或表偏移。
