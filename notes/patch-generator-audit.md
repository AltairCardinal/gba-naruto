# DB 补丁生成器审计（2026-07-10）

## 范围与判定标准

本次逐一审计 `tools/build_db_patches.py` 中全部 36 个 `generate_*_patches()`，并核对 `tools/build_mod.py` 的导入、调用、去重和写 ROM 路径。本文只判定生成器**实际写到哪里**，不把函数名、docstring 中的 “real” 或构建变量名 `db_real_patches` 当作有效性证据。

- **real ROM**：生成的 `bytes` 补丁直接指向游戏已知表/代码/资源偏移（`< 0x5E0000`），理论上可被游戏读取。此分类只证明写入目标不是审计区，**不证明字段语义、索引和运行时效果已经验证**。
- **audit-only**：只写 `0x5E0000..0x5FFFFF` 保留区；游戏没有已证实的消费路径。
- **混合**：同一生成器同时产生 real ROM 与 audit-only 字节补丁。
- **未集成**：定义存在，但 `build_mod.py` 未调用。

源码总述已经明确通用 DB 补丁是审计轨迹而非游戏有效补丁：`build_db_patches.py:2-7,19-20,30-35`。通用生成器逐表打包并线性写入保留区：`build_db_patches.py:115-169`。

## 总结

| 类别 | 数量 | 结论 |
|---|---:|---|
| real ROM | 14 | 写入真实 ROM 表，但多处使用固定模板、占位指针或未经动态验证的索引公式，不能据此宣称可编辑闭环完成 |
| audit-only | 22 | 包含通用 `generate_db_patches` 和 21 个专用生成器；不改变游戏实际行为 |
| 混合 | 0 | 当前没有生成器同时写真实表和审计区 |
| 未集成 | 0 | 36 个生成器全部被构建调用；“已集成”不等于“游戏有效” |

## 逐函数审计

### Real ROM（14）

| 函数 | DB 结构 | 实际目标偏移/公式 | 代码证据 | 风险 | 建议优先级 |
|---|---|---|---|---|---|
| `generate_battle_config_patches` | `battle_configs` | 单位 ID `0x53F298`；场景 `0x53D914 + scenario_id*32` | `172-183,193,212-239` | 所有行可能覆盖同一单位表起点；场景仅写 20 字节固定模板而非完整 32 字节；玩家/敌人语义被合并 | **P0** |
| `generate_chapter_patches` | `chapters` | `0x53D914 + chapter_number*32` | `254-260,268,274-288` | 同样只写固定 20 字节模板；标题字段被查询但完全未编码；与 battle config 可互相覆盖 | **P0** |
| `generate_unit_patches` | `units` | `0x53F298 + ((id-1)%64)*2` | `301-305,312-338` | modulo 会让非法/重复 ID 静默覆盖；只回写 `char_id`，`name/hp` 未生效 | **P1** |
| `generate_skill_patches` | `skills` | `0x546100 + unit_id*16` | `351-375,376-387` | 用 `unit_id` 作为技能索引未证实；除 damage 外大量字段为硬编码常量，多个技能可覆盖 | **P0** |
| `generate_story_beat_patches` | `story_beats` | `0x53636C + chapter_id*4` | `400-426` | 每项都写固定占位指针 `0x08535CFC`，beat 内容和 `beat_index` 未生效，可能把所有章节指向章节 1 | **P0** |
| `generate_audio_patches` | `audio_files` | `0x53F138 + (rom_offset+2)*4`，值 `0x0812F5B0 + rom_offset*16` | `447-470,471-482` | 把名为 ROM offset 的值当表索引；基址/步长为推导公式，无边界和指针验证，极易越界破坏数据 | **P0** |
| `generate_map_patches` | `maps` | `0x53D910 + id*32` | `554-588` | `id` 是否零基未证实；只保留宽高和两个指针，其余 20 字节清零；默认指针可能伪造有效数据 | **P0** |
| `generate_level_patches` | `levels` | `0x5459D4 + id*12` | `608-640` | `id`/`level` 双索引关系未证实；后 4 字节强制清零 | **P1** |
| `generate_character_stat_patches` | `character_stats` | `0x54507A + id*16` | `660-693` | 基址非对齐且索引语义未证实；中间 6 字节清零；名称未生效 | **P0** |
| `generate_battle_config_data_patches` | `battle_config_data` | `0x545458 + id*16` | `713-745` | 多个未知字段清零，`name` 不生效，id 是否表索引未证实 | **P1** |
| `generate_encounter_zone_patches` | `encounter_zones` | `0x53D910 + map_id*32 + 16` | `765-798` | 假设 map header `+16` 为 zone u32；会与 map generator 的整条 32 字节写入冲突，结果依赖调用顺序 | **P0** |
| `generate_item_patches` | `items` | `0x546100 + item_id*16` | `819-862` | 与技能共用表且后调用，会按偏移覆盖 skill；effect 字符串未编码，结构中存在硬编码常量 | **P0** |
| `generate_character_stats_b_patches` | `character_stats_b` | `0x545200 + char_index*16` | `1097-1125` | 虽完整写 8×u16，但字段语义及表边界未做运行时验证 | **P1** |
| `generate_font_patches` | `fonts` | `0x53E5B4 + char_index` | `1293-1318` | 只写像素宽度；索引边界、字形映射和渲染效果仍需验证 | **P1** |

### Audit-only（22）

下表“已知真实候选表”只来自函数注释/常量，当前函数**没有写入该候选表**。

| 函数 | DB 结构 | 实际写入 | 已知真实候选表 | 代码证据 | 风险 | 建议优先级 |
|---|---|---|---|---|---|---|
| `generate_db_patches` | `TABLE_LAYOUT` 全部结构 | `0x5E0000 + 全局行号*64` | 不适用 | `115-169` | 仅审计；容量 2048 行；会与专用 audit 生成器重叠 | **P0（基础设施）** |
| `generate_unit_position_patches` | `unit_positions` | `0x5E0000 + i*64` | 注释称 WRAM 战斗单位数组，尚无 ROM 入口 | `495-500,507-533` | 游戏不读取；所有专用 audit 共用起点 | **P0** |
| `generate_audio_event_patches` | `audio_events` | `0x5E8000 + id*64` | 索引表基址 `0x599634` | `882-911,920-927` | 明言无法安全修改索引表；与通用审计区范围重叠 | **P1** |
| `generate_battle_encounter_patches` | `battle_encounters` | `0x5E0000 + i*64` | `0x542384` | `995-1030` | 候选表完全未写 | **P0** |
| `generate_battle_handler_patches` | `battle_handlers` | `0x5E0000 + i*64` | `0x53E6D8` | `1046-1081` | 函数指针控制流高风险，需范围/Thumb 位校验后再回写 | **P0** |
| `generate_cutscene_script_patches` | `cutscene_scripts` | `0x5E0000 + i*64` | `0x53DF70` | `1142-1177` | 剧情主链未生效 | **P0** |
| `generate_data_table_a_patches` | `data_table_a` | `0x5E0000 + i*64` | `0x5A14A4` | `1193-1227` | 候选表未写，字段语义未知 | **P2** |
| `generate_data_table_b_patches` | `data_table_b` | `0x5E0000 + i*64` | `0x5A2120` | `1243-1277` | 候选表未写，字段语义未知 | **P2** |
| `generate_function_pointer_patches` | `function_pointers` | `0x5E0000 + i*64` | `0x53D5F4` | `1336-1371` | 控制流指针未生效；直接实现前必须验证 Thumb 位和目标范围 | **P1** |
| `generate_map_event_patches` | `map_events` | `0x5E0000 + i*64` | `0x53EB08` | `1387-1422` | 地图事件链未生效 | **P0** |
| `generate_map_sprite_patches` | `map_sprites` | `0x5E0000 + i*64` | `0x53F1DC` | `1438-1473` | 地图精灵配置未生效 | **P1** |
| `generate_menu_ui_patches` | `menu_ui` | `0x5E0000 + i*64` | `0x5A5774` | `1489-1524` | UI 指针未生效 | **P2** |
| `generate_palette_patches` | `palettes` | `0x5E0000 + i*64` | `0x53F138` | `1540-1575` | 候选基址与 audio generator 相同，表身份冲突需先澄清 | **P1** |
| `generate_resource_pointer_patches` | `resource_pointers` | `0x5E0000 + i*64` | `0x596F0C` | `1591-1626` | 资源替换链未生效 | **P1** |
| `generate_sappy_engine_patches` | `sappy_engine` | `0x5E0000 + i*64` | 记录值示例/注释涉及 `0x079668` | `1642-1675` | 即使 DB 标记 code_verified，本生成器仍只审计，不修改引擎 | **P1** |
| `generate_save_state_patches` | `save_state` | `0x5E0000 + i*64` | `0x53D848` | `1691-1727` | 存档格式没有编辑闭环；误写会破坏兼容性，需单独测试 ROM | **P1** |
| `generate_sprite_animation_patches` | `sprite_animations` | `0x5E0000 + i*64` | `0x53F200` | 动画指针未生效 | **P1** |
| `generate_story_b_patches` | `story_b` | `0x5E0000 + i*64` | `0x536BC8` | `1794-1829` | 章节指针链未生效 | **P0** |
| `generate_story_c_patches` | `story_c` | `0x5E0000 + i*64` | `0x538FF0` | `1845-1880` | 章节指针链未生效 | **P0** |
| `generate_story_d_patches` | `story_d` | `0x5E0000 + i*64` | `0x53AB78` | `1896-1931` | 章节指针链未生效 | **P0** |
| `generate_story_e_patches` | `story_e` | `0x5E0000 + i*64` | `0x53C3C0` | `1947-1982` | 章节指针链未生效 | **P0** |
| `generate_tile_asset_patches` | `tile_assets` | `0x5E0000 + i*64` | `0x5A3218` | `1998-2033` | tile 指针未生效 | **P1** |

### 混合与未集成

- **混合：无。** `generate_audio_event_patches` 虽计算/记录真实候选表信息，但实际只返回 `0x5E8000+` 审计补丁（`882-927`），所以仍是 audit-only。
- **未集成：无。** `build_mod.py:181-218` 导入全部 36 个生成器；`219-253` 调用 35 个专用生成器，`254` 调用通用审计生成器。

## 构建链关键缺陷

### P0：专用 audit 数据互相覆盖/被去重丢弃

`build_mod.py:219-253` 把 real ROM 和 audit-only 专用生成器全部追加到同一个 `db_real_patches`。随后 `308-322` **只按 offset 去重且保留最后一项**。除 audio event 外，21 个专用 audit 生成器都从 `0x5E0000 + i*64` 开始，因此同一行号的补丁互相冲突；调用顺序靠后的 `tile_assets`、`story_e` 等会淘汰前面的结构。也就是说，专用 audit 生成器即使返回了记录，多数也不会进入 ROM。

### P0：通用 audit 再次覆盖专用 audit

专用集合在 `build_mod.py:327-340` 先写入；通用 `generate_db_patches()` 产生的 `db_audit_patches` 在 `342-364` 后写入，同样从 `0x5E0000` 开始。因此后者会再次覆盖相同区域。`audio_events` 的专用 `0x5E8000 + id*64` 也落在通用审计区 `0x5E0000..0x5FFFFF` 内，没有分区保证。

### P0：所谓 before-check 实际不是基准 ROM 校验

构建在写每个 DB 专用补丁前，直接从**当前已被前序补丁修改的内存**取字节并注入 `before_hex`（`build_mod.py:331-338`）。这只会让 `apply_bytes_patch` 验证“刚读到的值等于刚读到的值”，无法检测错误偏移或不同生成器间覆盖；注释 `324-326` 所称的防止静默覆盖并未成立。

### P0：真实生成器间也存在确定的偏移冲突

- `battle_configs` 与 `chapters` 都写 `0x53D914 + n*32`；后调用的 chapter 胜出。
- `maps` 整条写 `0x53D910 + id*32`，`encounter_zones` 后写同条目的 `+16`；这是顺序依赖的隐式合并。
- `skills` 与 `items` 都写 `0x546100 + index*16`；索引相同则后调用的 item 胜出。
- `audio_files` 使用 `0x53F138` 作为表基址，而 palettes 注释也把 `0x53F138` 当候选表；基础语义存在冲突。

## 建议执行顺序

1. **P0，先修构建真实性边界**：把 real 与 audit 生成器拆成不同集合；audit 按结构分配不重叠区间或只保留一个规范化通用审计流；报告明确标记 `game_effective=false`。
2. **P0，建立基准校验**：每个真实表生成器必须用已校验 base ROM 的预期字节/表边界，而不是运行时读取当前值生成 `before_hex`；检测并拒绝跨生成器重叠，只有显式声明的字段级合并可放行。
3. **P0，优先打通章节闭环**：battle/chapter/story beat/cutscene/map event/story B-E；移除固定模板和占位指针，依据真实结构序列化，并用 mGBA 验证开场→事件→战斗→胜败→下一章。
4. **P0，验证高破坏性公式**：audio、skill/item、map、character stat。对每个索引做范围检查、基址反向引用验证和单字段 A/B 运行时实验。
5. **P1，转换剩余 audit-only 候选表**：每次只转换一个结构，补充提取→修改→构建→ROM diff→运行时消费证据；函数指针必须检查 ROM 地址范围和 Thumb 位。
6. **P1/P2，完善测试门槛**：测试不仅检查“补丁字节出现”，还要检查真实目标偏移、无未声明重叠、模拟器运行效果和存档兼容性。

## 当前结论

全部生成器确实“接入了构建”，但只有 14 个指向真实游戏区域，其中多项仍是固定模板/占位推导；另外 22 个完全是 audit-only。现有构建还会把专用审计记录按偏移去重丢弃并被通用审计流覆盖。因此，生成器数量、构建成功或 ROM 中出现 DB 字节都不能作为“逆向完成”或“编辑闭环完成”的证据。
