# Battle Config 不安全模板回写修正（2026-07-10）

## 尝试内容

在将 positions 编成矩阵 `0x5461C4+` 接入真实 ROM 回写后，新的补丁
重叠门禁拒绝了默认构建：

```text
conflicting patch overlap at 0x547934..0x547948:
db_real_battle_configs_4 vs db_real_rom_positions_31
```

反查 `generate_battle_config_patches()` 发现，旧逻辑把编辑器中的
`battle_configs.scenario_id` 直接当成从 0 开始的 ROM 表索引，按
`0x53D914 + scenario_id*32` 写入固定 20 字节模板。

## 学到的结论

- 数据库中的 `scenario_id` 包含 `0x0101`/`0x0301`/`0x0501` 等游戏值，
  不是连续 ROM 表索引。
- 乘 32 后会跨越多个无关区域，已确认会覆盖 positions 矩阵。
- 固定模板没有保留原记录其他字段，不能视为无损回写。
- 安全门禁的冲突不是新回归，而是暴露了以前被 last-write-wins
  掩盖的错误偏移。

## 修正结果与边界

- 旧 `battle_configs` CRUD 行现在返回 `db_battle_config_unmapped` 诊断项，
  不再产生任何 ROM 字节补丁。
- 只有拥有明确 `_idx`/`_rom_offset` 并保留完整原字节的 `rom_*`
  镜像可进入无损构建链。
- 这是防止 ROM 损坏的修复，不表示编辑器战斗配置 CRUD 已完成真实
  语义映射；后续需为可编辑行加入明确 ROM record key 和完整序列化。

## 重要地址

- 地图描述表：`0x53D910`
- 旧逻辑的错误基址：`0x53D914`
- positions 编成矩阵：`0x5461C4+`
- 首个实际冲突范围：`0x547934..0x547948`
