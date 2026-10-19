# Butano 战斗单位视觉目录设计

## 目标

通用 Butano 战斗场景必须按领域状态中的 `character_id` 显示 ROM 对应角色，
而不是按阵营把全部玩家画成鸣人、全部敌人画成同一个替代敌人。

本里程碑只恢复单位的地图待机视觉和 ROM 锚点。移动、朝向、受击、技能与胜利动画
仍由后续动画时间线里程碑恢复，不能把本里程碑描述为“完整角色动画”。

## 逆向依据

ROM SHA-256 固定为
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。

文件偏移 `0x596D5C` 开始的表并非旧文档所称的 312 行地图 tile 表，而是：

- 62 个角色；
- 每个角色固定 9 个视觉槽；
- 每行 16 字节，依次为帧描述表、动画描述表、4bpp OBJ tile 数据和
  BGR555 OBJ palette 指针；
- 总计 558 行，其中 342 行有效、216 行为保留空槽；
- 角色 `N` 的视觉槽 `S` 位于行 `(N - 1) * 9 + S`。

每个角色的槽 0 均有效。其帧描述表首指针指向 24 字节 OBJ 帧记录：

| 偏移 | 字段 | 语义 |
|---|---|---|
| `+0x00` | `u32 tile_index` | 以 32 字节 OBJ tile 为单位的起始索引 |
| `+0x04` | `s16 x` | 相对单位地图锚点的左上角 X |
| `+0x06` | `s16 y` | 相对单位地图锚点的左上角 Y |
| `+0x08` | `u16 width` | OBJ 宽度 |
| `+0x0A` | `u16 height` | OBJ 高度 |
| `+0x0C` | `u16 scale_x` | 原始比例为 `0x100` |
| `+0x0E` | `u16 scale_y` | 原始比例为 `0x100` |
| `+0x10..0x17` | 控制/保留字段 | 原样记录，尚不赋予未验证语义 |

待机帧并非全部 32×64、中心偏移 `(0,-24)`。已确认的例外包括：

- 角色 36、37：中心 Y 偏移 `-16`；
- 角色 39、40：32×32，中心 Y 偏移 `-8`；
- 角色 42、59：64×64，中心偏移 `(8,-24)`；
- 角色 55：32×32，中心 Y 偏移 `-38`。

因此运行时位置必须使用描述符的
`(x + width / 2, y + height / 2)`，不能继续使用玩家/敌方两个常量。

## 复用决策

1. 角色身份、属性和技能继续复用现有 `battle_unit_instance`、
   `battle_scene_unit_view` 和 `generated_battle_unit_content.h`。
2. 4bpp BMP 写入逻辑从 scenario 41 资产生成器抽为公共 helper，旧生成器与新目录
   共用，避免产生第二套 BMP 编码。
3. 新能力追加到 `battle_runtime_scene.cpp` 的部署和战斗渲染链；不新建平行战斗场景。
4. scenario 41 的逐帧参考场景暂不切换。它承担原关卡逐帧对照，通用场景承担后续关卡
   数据驱动运行，两者用户体验和验收目的不同。

## 生成物

- `tools/generate_butano_battle_unit_visual_content.py`
- `butano-sequel/graphics/battle_unit_01_idle.bmp` 到
  `battle_unit_62_idle.bmp`
- 对应 62 个 Butano sprite JSON
- `butano-sequel/graphics/battle_unit_visual_catalog.json`
- `butano-sequel/game/include/konoha/generated_battle_unit_visual_content.h`

目录保存 ROM 指针、角色/槽映射、帧尺寸、锚点、像素哈希和源 ROM 哈希。C++ 头只负责
把 `character_id` 映射到 Butano sprite item 和中心偏移。

## 运行时行为

- 部署确认页按 `battle_deployment_entry.character_id` 创建正确角色；
- 正式战斗按 `battle_scene_unit_view.character_id` 创建正确角色；
- 变身或身份覆盖导致 `character_id` 改变时，已有 sprite 在同一槽位切换 item，
  不重建领域状态；
- 非 1..62 的活动角色视为内容错误并触发断言，不以鸣人或通用敌人静默代替；
- 活跃单位数量仍受现有 12 单位和 OAM 预算约束。

## 测试与验收

RED 必须先证明：

- 旧 312 行/首空行终止模型不能覆盖 62 个角色；
- 新生成器、62 个资源和 `character_id` 渲染 wiring 尚不存在。

GREEN 后验证：

- 558 行结构、342/216 稀疏计数、62 个槽 0；
- 鸣人、佐助、角色 42、55、62 的尺寸、锚点与像素哈希；
- 两次生成逐字节一致；
- 通用部署和战斗渲染不再引用 `scenario_41_naruto/enemy`；
- ARM ROM 构建成功；
- battle 32 动态部署画面同时显示角色 1、2、3、35 的不同 ROM sprite；
- battle 9、11、scenario 43、scenario 41 路线回归。

