# Legacy 生成器安全封堵（2026-07-11）

当前 editor.db 实际包含：重复/越界式 chapters、多个 unit_id=0 的 skills、折叠到
少量 chapter_id 的 54 个 story beats、以及 rom_offset 为 NULL 的 audio rows。
旧生成器分别使用固定模板、占位指针或合成指针写真实 ROM，PatchSafetyGate 对内容
相同的重复写会视为幂等，不能替代记录身份验证。

按 TDD 新增并扩展 `tests/test_unsafe_legacy_patches.py`：legacy 生成器最初会返回
`bytes` 或存在返回 `bytes` 的风险，测试按正确原因失败；修正后改为：

- chapters → `db_chapter_unmapped`；
- skills → `db_skill_unmapped`；
- story beats → `db_story_beat_unmapped`；
- audio → `db_audio_unmapped`；
- maps → `db_map_unmapped`；
- levels → `db_level_unmapped`；
- character_stats → `db_character_stat_unmapped`；
- battle_config_data → `db_battle_config_data_unmapped`；
- encounter_zones → `db_encounter_zone_unmapped`；
- items → `db_item_unmapped`。

诊断不含 `offset/after_hex`，因此不会修改 ROM。已经有 `_idx + _rom_offset` 身份和
base-ROM 前置校验的 `rom_*` lossless mirror 不受影响。

这些 legacy 表后续只能在建立明确 ROM 身份、完整 raw/base 校验和字段级序列化证据后
逐项恢复真实写回；在此之前只能保留诊断。
