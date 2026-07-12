# 逆向工程 Bank 完成度审计

生成时间：`2026-07-12T07:01:27.072532+00:00`

范围：bank metadata/entries/verification/documentation and base-ROM byte fidelity; no runtime or write-back validation。因此本报告不能证明运行时语义或实际回写闭环。

## 汇总

- 发现 `32` / 预期 `32` 个 bank。
- 同时满足六项元数据与字节检查：`32` / `32`。
- 有效数据 bank：`27`；已证伪且保持空条目的安全 tombstone：`5`。
- `table_offset`：`32` / `32`。
- `format`：`32` / `32`。
- `entries`：`32` / `32`。
- `verification`：`32` / `32`。
- `documentation`：`32` / `32`。
- `rom_fidelity`：`32` / `32`。
- verification 分布：`code_verified`=4, `disproved`=5, `runtime_verified`=6, `static_verified`=17。

## 逐结构结果

| 结构 | table_offset | format | entries | verification | 文档覆盖 | ROM字节 | 完整 | 问题 |
|---|---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| `audio` | ✅ `0x465B70` | ✅ | ✅ (80) | ✅ `runtime_verified` | ✅ (20) | ✅ (240) | ✅ | — |
| `battle-config` | ✅ `0x545458` | ✅ | ✅ (32) | ✅ `runtime_verified` | ✅ (18) | ✅ (480) | ✅ | — |
| `battle-encounters` | ✅ `0x542384` | ✅ | ✅ (38) | ✅ `static_verified` | ✅ (11) | ✅ (38) | ✅ | — |
| `battle-handlers` | ✅ `0x53E6D8` | ✅ | ✅ (14) | ✅ `static_verified` | ✅ (10) | ✅ (14) | ✅ | — |
| `character-stats` | ✅ `0x545068` | ✅ | ✅ (63) | ✅ `runtime_verified` | ✅ (15) | ✅ (504) | ✅ | — |
| `character-stats-b` | ✅ `0x545200` | ✅ | ✅ (0) | ✅ `disproved` | ✅ (16) | ✅ (0) | ✅ | — |
| `cutscene-scripts` | ✅ `0x53DF70` | ✅ | ✅ (16) | ✅ `static_verified` | ✅ (10) | ✅ (16) | ✅ | — |
| `data-table-a` | ✅ `0x5A14A4` | ✅ | ✅ (20) | ✅ `static_verified` | ✅ (9) | ✅ (20) | ✅ | — |
| `data-table-b` | ✅ `0x5A2120` | ✅ | ✅ (20) | ✅ `static_verified` | ✅ (9) | ✅ (20) | ✅ | — |
| `encounter-zones` | ✅ `0x53D910` | ✅ | ✅ (47) | ✅ `static_verified` | ✅ (22) | ✅ (423) | ✅ | — |
| `fonts` | ✅ `0x53E5B4` | ✅ | ✅ (256) | ✅ `static_verified` | ✅ (8) | ✅ (256) | ✅ | — |
| `function-pointers` | ✅ `0x53D5F4` | ✅ | ✅ (11) | ✅ `static_verified` | ✅ (9) | ✅ (11) | ✅ | — |
| `items` | ✅ `0x546100` | ✅ | ✅ (0) | ✅ `disproved` | ✅ (16) | ✅ (0) | ✅ | — |
| `levels` | ✅ `0x5459D4` | ✅ | ✅ (47) | ✅ `static_verified` | ✅ (12) | ✅ (282) | ✅ | — |
| `map-events` | ✅ `0x53EB08` | ✅ | ✅ (47) | ✅ `static_verified` | ✅ (12) | ✅ (47) | ✅ | — |
| `map-sprites` | ✅ `0x53F1DC` | ✅ | ✅ (47) | ✅ `static_verified` | ✅ (9) | ✅ (47) | ✅ | — |
| `maps` | ✅ `0x53D910` | ✅ | ✅ (47) | ✅ `static_verified` | ✅ (31) | ✅ (423) | ✅ | — |
| `menu-ui` | ✅ `0x5A5774` | ✅ | ✅ (20) | ✅ `static_verified` | ✅ (9) | ✅ (20) | ✅ | — |
| `palettes` | ✅ `0x53F138` | ✅ | ✅ (88) | ✅ `static_verified` | ✅ (15) | ✅ (88) | ✅ | — |
| `positions` | ✅ `0x5461C4` | ✅ | ✅ (1728) | ✅ `runtime_verified` | ✅ (21) | ✅ (10368) | ✅ | — |
| `resource-pointers` | ✅ `0x596F0C` | ✅ | ✅ (20) | ✅ `static_verified` | ✅ (9) | ✅ (20) | ✅ | — |
| `sappy-engine` | ✅ `0x09AE3C` | ✅ | ✅ (1) | ✅ `code_verified` | ✅ (6) | ✅ (1) | ✅ | — |
| `save-state` | ✅ `0x53D848` | ✅ | ✅ (10) | ✅ `code_verified` | ✅ (13) | ✅ (20) | ✅ | — |
| `skills` | ✅ `0x545BE4` | ✅ | ✅ (94) | ✅ `code_verified` | ✅ (13) | ✅ (1504) | ✅ | — |
| `sprite-animations` | ✅ `0x53F200` | ✅ | ✅ (38) | ✅ `static_verified` | ✅ (9) | ✅ (38) | ✅ | — |
| `story` | ✅ `0x060C74` | ✅ | ✅ (56) | ✅ `runtime_verified` | ✅ (29) | ✅ (56) | ✅ | — |
| `story-b` | ✅ `0x060D54` | ✅ | ✅ (56) | ✅ `code_verified` | ✅ (11) | ✅ (56) | ✅ | — |
| `story-c` | ✅ `0x538FF0` | ✅ | ✅ (0) | ✅ `disproved` | ✅ (13) | ✅ (0) | ✅ | — |
| `story-d` | ✅ `0x53AB78` | ✅ | ✅ (0) | ✅ `disproved` | ✅ (11) | ✅ (0) | ✅ | — |
| `story-e` | ✅ `0x53C3C0` | ✅ | ✅ (0) | ✅ `disproved` | ✅ (11) | ✅ (0) | ✅ | — |
| `tile-assets` | ✅ `0x5A3218` | ✅ | ✅ (6) | ✅ `static_verified` | ✅ (9) | ✅ (6) | ✅ | — |
| `units` | ✅ `0x54241C` | ✅ | ✅ (63) | ✅ `runtime_verified` | ✅ (19) | ✅ (630) | ✅ | — |

## 判定规则

- `table_offset`：必须为非负整数；若有 `table_offset_hex`，两者必须一致。
- `format`：`format`、`entry_format` 或已知领域格式字段至少一个非空。
- `entries`：有效 bank 必须是非空数组；`disproved` tombstone 必须保持空数组；若声明 `entry_count`，必须与实际数量一致。
- `verification`：必须是 `static_verified`、`code_verified`、`runtime_verified` 或带方法与说明的 `disproved`。
- 文档覆盖：`docs/*.md` 或 `notes/*.md` 至少一处提到结构目录名、bank 路径或表偏移。
- `rom_fidelity`：有效 bank 已提取字段的 `*_hex` 必须与校验过的基准 ROM 对应字节一致；空的 `disproved` tombstone 记为不适用。
