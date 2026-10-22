# 战场对象运行时闭环（2026-07-26）

## 结论

本轮恢复的是原作战场对象领域链，不是按画面拼接的起爆符演示：

1. 忍具动作通过正式 `ActionDefinition` 与 effect `0x18` 创建 type 1 对象；
2. 对象进入 `BattleSession` 唯一状态表，按原 ROM 的 32×16 字节布局保存；
3. 每次阵营结束先递减对象持续时间；
4. type 1 到期后按忍具 payload、施放者和方形范围调用正式伤害/命中/反应/被动 resolver；
5. 结算结果写回单位 HP，再释放对象，最后才求值关卡 condition；
6. controller 只把 session 事件排入表现 FIFO，renderer 只读对象快照和表现事件。

因此，ROM 中可见的对象出现、跨阵营存活、到期、范围伤害与消失均来自同一领域状态，
不是截图、固定选项或表现层直接改 HP。

## 原 ROM 绑定

- 原 ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 对象表：`0x02026604`，32 槽、每槽 `0x10` 字节，slot 0 保留。
- 分配器：`0x08081024`；释放器：`0x08081084`。
- effect `0x0C` handler：`0x0807726E`，创建 type 2。
- effect `0x18` handler：`0x08077514`，创建 type 1，并保存 source unit。
- 阵营结束遍历：`0x08081B70`，调用点位于 `0x08073688` 的阵营翻转之前。
- type 1 到期调用忍具初始化器 `0x0806D910`；范围是以对象格为中心的
  Chebyshev/方形半径。
- type 2 到期并非静默释放：`0x08081BB0` 先建立坐标特效，
  `0x08081BD4` 以 tile 索引区间 `0x0300..0x037F` 和 palette bank
  `12..14` 建立资源，`0x08081BDA` 选择 sequence 7，等待状态 3 后才在
  `0x08081C14` 释放对象。
- sequence 7 的 24 字节表选择 resource group `0x12`；其资源对为 graphics
  `0x083478F4`、palette `0x083480C8`。LZ 解压后 graphics 是 3584 字节，
  恰好为 7 帧 32×32、4bpp OBJ 图块；graphics SHA-256 为
  `9162bda2e90536bbe5982e94b4d4de9b18111538b548137ca057701d36b7bc55`，
  palette SHA-256 为
  `d53a7a56bded0b6727002a3fb4ad69454dccee15e8f849ad3a16c3b5639244c1`。
- 忍具 67–72 属于 effect `0x18`；67–69 的 potency 为 20/26/32，
  70–72 另带 `0x40` flags。后续反汇编已闭合该 flag：有效命中后建立
  `0x1F/0x21/0x23` 三条 10% 攻/防/敏下降状态，持续三回合。

机读证据为
`notes/battlefield-object-runtime-20260726.json`，生成器为
`tools/analyze_battlefield_object_runtime.py`。

## 实现边界

- `battlefield_object_record` 以 `offsetof` 固定原作 16 字节 ABI；
  `+4` 是 payload/action ID，`+6` 是编码后的持续时间，不再误命名为威力。
- type 2 到期先排入无 actor 的位置表现事件，播放原作 sequence 7 的 7 帧烟尘后
  释放；type 1 到期解析范围效果并释放。
- 每个到期事件保留 slot、对象快照、受影响单位、impact count 与总伤害。
- 跨层返回只携带 16 字节 `battlefield_object_resolution_summary`；
  完整逐 hit 日志留在 resolver/session，不再复制进每层返回值。
- 对象分配器调用 `0x08080FC8`，只把 `(slot << 6)` 写进
  `0x02021E2C` 的地图格元数据；释放器以 `0xF83F` 清掉 `0x07C0` 槽位位域。
  这不是可见 OBJ sprite。Butano 已删除此前给每个存活对象绘制
  `scenario_41_cursor` 的伪标记，renderer 只在真实 type 2 到期事件期间创建专属
  sequence 7 精灵。

后一点同时修复了 GBA 栈风险。引入对象结算后，ARM 实测结构曾为：

| 类型 | 修复前 | 修复后 |
|---|---:|---:|
| `battle_turn_flow_result` | 660 B | 28 B |
| `battle_player_action_flow_result` | 684 B | 52 B |
| `battle_ai_turn_flow_result` | 776 B | 144 B |
| `battle_scene_control_result` | 1464 B | 200 B |
| 可见战斗场景栈帧 | 9940 B | 3636 B |

大型场景快照、对象快照、控制结果与 sprite 状态已迁入 EWRAM。失败运行
`artifacts/butano-battlefield-object-runtime-20260726-10/` 在结束防御后停止产帧，
已由上述紧凑契约取代，不得再作为通过证据。

## ROM 运行证据

最终静音自动化：

- 目录：`artifacts/butano-battlefield-object-runtime-20260726-12/`
- 路径：部署 → 教程页 → 角色 1 → 忍具 67 → 空格放置 → 面向 →
  防御结束 → 敌方回合 → 对象到期。
- frame 147：slot 1 对象存在；
- frame 223：进入敌方回合，对象仍存在；
- frame 279：round 2，对象已释放，等待既有 AI 表现完成；
- frame 363：type 1 事件被表现 FIFO 取出且 `presentation_busy=1`；
- 领域结果：`object_damage=23`，控制错误与玩家错误均为 0。
- guard：`reason=completed`、`completion_trigger=success-marker`。

构建产物：

- ROM SHA-256：
  `f3d0b6d7cde4981f8b05ef62f285e4d545ac7284ead67ad408c57b17757a4e96`
- ELF SHA-256：
  `b7c66f08fb79d01d057740215041adc843fab4f5eaad0847c9bb7b535614f87c`
- 原始存档仍为：
  `2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc`

自动化使用 `mute=1`，只能证明领域与画面流程，不证明音频撕裂已修复。

## type 2 表现闭环

- `BattleSession` 产生 `type_2_expired` 权威事件；
- `battle_scene_controller` 不再丢弃该事件，而是把 actorless 事件写入既有表现 FIFO；
- `battle_scene_presentation` 保留 tile/palette/sequence 原始参数，并以 7 帧生命周期
  驱动 renderer；
- `tools/generate_butano_battlefield_object_effect_content.py` 对基准 ROM 哈希、
  graphics/palette 指针和解压数据哈希做 fail-closed 校验，再生成
  `butano-sequel/graphics/battlefield_object_type_2_expiry.{bmp,json}`；
- renderer 在对象坐标播放精灵；领域对象快照只用于逻辑与遥测，不再伪装为可见游标。

生成清单为 `notes/battlefield-object-effect-content-20260726.json`。ARM 零缓存构建
已通过，证明资源转换、精灵帧索引与链接成立。当前 4 帧/图形帧的 hold 值是明确的
暂定表现参数；在取得原版自然路线逐帧捕获前，不宣称时间节奏等价。

Butano 静音自然路线：

- 目录：`artifacts/butano-battlefield-object-type2-runtime-20260726-03/`
- 新档 campaign 的鸣人第三忍具槽装备真实忍具 37；动作目录实际显示 6 项，
  action index 5 为忍具 37。
- frame 165：动作 37 结算完成，slot 1 对象存在；
- frame 296：round 2 玩家重新取得行动权，对象仍存在；
- frame 391：进入 round 3 前对象已释放；
- frame 410：controller 的 FIFO 正在消费 type 2 事件，
  `presentation_object_kind=2`、`damage=0`、`object_count=0`、
  `presentation_busy=1`，控制与玩家错误均为 0。
- 截图 `type-2-expiry.png` 只在上述领域/表现条件同时成立后生成；
  `trace.log` 保留完整 phase/round/object/action 轨迹。

最终 ROM/ELF SHA-256 为
`f496da7f4f9e415e5ffdc61b6ff132034995b1c2651b3e92b0854e224c041db1` /
`2db7059fd95460f83a4af37b8b9186baad40ec4a0e1522f88de734caa455c9f8`。
基准存档及 mGBA 同名存档均保持
`2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc`。

## 尚未闭合

- 忍具 70–72 的 `0x40` 已由
  `notes/battle-effect-flag-followups-20260726.json` 闭合，并已接入对象到期统一
  resolver；本文件此前“只保留 flag、不实现状态”的结论已被取代。
- type 2 的精确资源、事件、Butano 自然路线和消失演出已闭合；原版自然路线的逐帧
  时长与音效仍未闭合。
- type 1 的 `object-explosion.png` 只证明通用表现事务消费了真实 23 点领域伤害，
  不代表起爆符专属视觉已经功能等价。
- 本里程碑只闭合战场对象这一条基础系统链，完整角色技能、全部特殊效果、
  关卡脚本、专属表现和非静音音频仍阻止“完整战斗系统已完成”的结论。
