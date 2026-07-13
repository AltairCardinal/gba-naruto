# 逆向工程 Bank 完成度审计

生成时间：`2026-07-13T03:29:16.630566+00:00`

范围：bank metadata/entries/verification/documentation and base-ROM byte fidelity; no runtime or write-back validation。因此本报告不能证明运行时语义或实际回写闭环。

## 汇总

- 发现 `32` / 预期 `32` 个 bank。
- 同时满足六项元数据与字节检查：`32` / `32`。
- 有效数据 bank：`23`；已证伪且保持空条目的安全 tombstone：`9`。
- `table_offset`：`32` / `32`。
- `format`：`32` / `32`。
- `entries`：`32` / `32`。
- `verification`：`32` / `32`。
- `documentation`：`32` / `32`。
- `rom_fidelity`：`32` / `32`。
- verification 分布：`code_verified`=10, `disproved`=9, `runtime_verified`=13。

## 逐结构结果

| 结构 | table_offset | format | entries | verification | 文档覆盖 | ROM字节 | 完整 | 问题 |
|---|---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| `audio` | ✅ `0x465B70` | ✅ | ✅ (80) | ✅ `runtime_verified` | ✅ (29) | ✅ (240) | ✅ | — |
| `battle-config` | ✅ `0x545458` | ✅ | ✅ (32) | ✅ `runtime_verified` | ✅ (18) | ✅ (480) | ✅ | — |
| `battle-encounters` | ✅ `0x54229C` | ✅ | ✅ (24) | ✅ `code_verified` | ✅ (12) | ✅ (96) | ✅ | — |
| `battle-handlers` | ✅ `0x53E6D8` | ✅ | ✅ (0) | ✅ `disproved` | ✅ (12) | ✅ (0) | ✅ | — |
| `character-stats` | ✅ `0x545068` | ✅ | ✅ (63) | ✅ `runtime_verified` | ✅ (15) | ✅ (504) | ✅ | — |
| `character-stats-b` | ✅ `0x545200` | ✅ | ✅ (0) | ✅ `disproved` | ✅ (16) | ✅ (0) | ✅ | — |
| `cutscene-scripts` | ✅ `0x53DF70` | ✅ | ✅ (8) | ✅ `code_verified` | ✅ (12) | ✅ (16) | ✅ | — |
| `data-table-a` | ✅ `0x5A143C` | ✅ | ✅ (46) | ✅ `runtime_verified` | ✅ (7) | ✅ (46) | ✅ | — |
| `data-table-b` | ✅ `0x5A2034` | ✅ | ✅ (79) | ✅ `code_verified` | ✅ (7) | ✅ (79) | ✅ | — |
| `encounter-zones` | ✅ `0x53D910` | ✅ | ✅ (0) | ✅ `disproved` | ✅ (22) | ✅ (0) | ✅ | — |
| `fonts` | ✅ `0x53E5B4` | ✅ | ✅ (0) | ✅ `disproved` | ✅ (10) | ✅ (0) | ✅ | — |
| `function-pointers` | ✅ `0x53D5F4` | ✅ | ✅ (11) | ✅ `runtime_verified` | ✅ (11) | ✅ (11) | ✅ | — |
| `items` | ✅ `0x546100` | ✅ | ✅ (0) | ✅ `disproved` | ✅ (16) | ✅ (0) | ✅ | — |
| `levels` | ✅ `0x5459C8` | ✅ | ✅ (45) | ✅ `code_verified` | ✅ (14) | ✅ (315) | ✅ | — |
| `map-events` | ✅ `0x53E698` | ✅ | ✅ (256) | ✅ `code_verified` | ✅ (13) | ✅ (512) | ✅ | — |
| `map-sprites` | ✅ `0x53F140` | ✅ | ✅ (43) | ✅ `code_verified` | ✅ (8) | ✅ (86) | ✅ | — |
| `maps` | ✅ `0x53D910` | ✅ | ✅ (47) | ✅ `runtime_verified` | ✅ (35) | ✅ (423) | ✅ | — |
| `menu-ui` | ✅ `0x5A4DEC` | ✅ | ✅ (63) | ✅ `runtime_verified` | ✅ (9) | ✅ (630) | ✅ | — |
| `palettes` | ✅ `0x53EE98` | ✅ | ✅ (15) | ✅ `code_verified` | ✅ (14) | ✅ (75) | ✅ | — |
| `positions` | ✅ `0x5461C4` | ✅ | ✅ (1728) | ✅ `runtime_verified` | ✅ (22) | ✅ (10368) | ✅ | — |
| `resource-pointers` | ✅ `0x596F0C` | ✅ | ✅ (5) | ✅ `code_verified` | ✅ (12) | ✅ (20) | ✅ | — |
| `sappy-engine` | ✅ `0x09AE3C` | ✅ | ✅ (1) | ✅ `code_verified` | ✅ (6) | ✅ (1) | ✅ | — |
| `save-state` | ✅ `0x53D848` | ✅ | ✅ (10) | ✅ `runtime_verified` | ✅ (16) | ✅ (20) | ✅ | — |
| `skills` | ✅ `0x545BE4` | ✅ | ✅ (94) | ✅ `runtime_verified` | ✅ (19) | ✅ (1504) | ✅ | — |
| `sprite-animations` | ✅ `0x53F200` | ✅ | ✅ (0) | ✅ `disproved` | ✅ (11) | ✅ (0) | ✅ | — |
| `story` | ✅ `0x060C74` | ✅ | ✅ (56) | ✅ `runtime_verified` | ✅ (38) | ✅ (56) | ✅ | — |
| `story-b` | ✅ `0x060D54` | ✅ | ✅ (56) | ✅ `runtime_verified` | ✅ (17) | ✅ (56) | ✅ | — |
| `story-c` | ✅ `0x538FF0` | ✅ | ✅ (0) | ✅ `disproved` | ✅ (13) | ✅ (0) | ✅ | — |
| `story-d` | ✅ `0x53AB78` | ✅ | ✅ (0) | ✅ `disproved` | ✅ (11) | ✅ (0) | ✅ | — |
| `story-e` | ✅ `0x53C3C0` | ✅ | ✅ (0) | ✅ `disproved` | ✅ (11) | ✅ (0) | ✅ | — |
| `tile-assets` | ✅ `0x5A320C` | ✅ | ✅ (79) | ✅ `code_verified` | ✅ (6) | ✅ (1343) | ✅ | — |
| `units` | ✅ `0x54241C` | ✅ | ✅ (63) | ✅ `runtime_verified` | ✅ (21) | ✅ (630) | ✅ | — |

## 判定规则

- `table_offset`：必须为非负整数；若有 `table_offset_hex`，两者必须一致。
- `format`：`format`、`entry_format` 或已知领域格式字段至少一个非空。
- `entries`：有效 bank 必须是非空数组；`disproved` tombstone 必须保持空数组；若声明 `entry_count`，必须与实际数量一致。
- `verification`：必须是 `static_verified`、`code_verified`、`runtime_verified` 或带方法与说明的 `disproved`。
- 文档覆盖：`docs/*.md` 或 `notes/*.md` 至少一处提到结构目录名、bank 路径或表偏移。
- `rom_fidelity`：有效 bank 已提取字段的 `*_hex` 必须与校验过的基准 ROM 对应字节一致；空的 `disproved` tombstone 记为不适用。
