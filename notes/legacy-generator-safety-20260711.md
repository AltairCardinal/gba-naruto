# Legacy 生成器安全封堵（2026-07-11）

当前 editor.db 实际包含：重复/越界式 chapters、多个 unit_id=0 的 skills、折叠到
少量 chapter_id 的 54 个 story beats、以及 rom_offset 为 NULL 的 audio rows。
旧生成器分别使用固定模板、占位指针或合成指针写真实 ROM，PatchSafetyGate 对内容
相同的重复写会视为幂等，不能替代记录身份验证。

按 TDD 新增 `tests/test_unsafe_legacy_patches.py`：四个生成器最初均返回 `bytes`，
测试按正确原因失败；最小修正后改为：

- chapters → `db_chapter_unmapped`；
- skills → `db_skill_unmapped`；
- story beats → `db_story_beat_unmapped`；
- audio → `db_audio_unmapped`。

诊断不含 `offset/after_hex`，因此不会修改 ROM。已经有 `_idx + _rom_offset` 身份和
base-ROM 前置校验的 `rom_*` lossless mirror 不受影响。

仍需同样处理当前库尚未创建、但一旦出现就会危险写 ROM 的 maps、levels、
character_stats、battle_config_data、encounter_zones 和 items legacy 表。
