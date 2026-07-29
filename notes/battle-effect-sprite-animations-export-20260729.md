# 战斗特效子动画全量导出（2026-07-29）

## 结论

原 ROM 的 18 个非零 battle-effect resource group 已从静态像素继续闭合到
definition、component、animation timeline 和父 callback spawn plan：

- group→definition/animation 指针对表：`0x085991B4..0x0859924C`，19×8 字节，
  group 0 为空，SHA-256
  `c7025f5ca83b63b21ff3bf3e3183602447d157cf6cd1e63395b918a318e74392`；
- 18/18 非零 group，178 个 frame definition，437 个 0x14-byte component；
- 23 条 child animation、193 个 keyframe，全部保留 ROM hold；
- 178 张 indexed PNG 源空间预览；每组解压图块均至少被一个 component 精确覆盖；
- 22/22 sequence 的 callback spawn policy、child variant、spawn tick、child hold
  和最后 child 静态完成 tick；
- 22/22 sequence 的 child task 原点公式，包括父对象静态偏移、对战侧水平镜像、
  角色锚点跟随和 sequence 1 的 RNG/Q8.8 运动状态转移。

成果位于 `artifacts/battle-effect-sprite-animations-v1/`。它复用
`battle-effect-resource-pairs-v1` 的图形/调色板和
`battle-effect-sequence-bindings-v1` 的 sequence→group/callback 映射，没有建立
第三套平行身份表。

## Component 与 timeline schema

definition table 是按 frame ID 索引的 component-list 指针表。每个 component 为：

| Offset | Type | 语义 |
|---:|---|---|
| `+0x00` | `u16` | group 图块中的 tile index |
| `+0x02` | `u16` | tile flags；bit 0 水平翻转，bit 1 垂直翻转 |
| `+0x04/+0x06` | `s16` | component-local x/y |
| `+0x08/+0x0A` | `u16` | width/height |
| `+0x0C/+0x0E` | `u16` | scale x/y |
| `+0x10` | `u8` | control |
| `+0x11` | `u8` | affine mode |
| `+0x12` | `u16` | reserved；当前全零 |

component list 以 `FF FF 00 00` 终止。animation table 是 variant→timeline
指针表；timeline 单项为 `<u16 frame_id,u16 hold_frames>`，以
`<0xFFFF,0>` 终止。ROM 中每个 component 区和 timeline 区都与下一结构精确相邻，
导出器与独立 verifier 都拒绝空洞、越界、零 hold 或缺少 terminator。

## 全量 group 统计

| Group | Frames | Components | Variants | Variant durations |
|---:|---:|---:|---:|---|
| 1 | 8 | 8 | 1 | 59 |
| 2 | 26 | 26 | 3 | 87, 52, 45 |
| 3 | 26 | 26 | 3 | 87, 52, 45 |
| 4 | 4 | 4 | 1 | 7 |
| 5 | 8 | 36 | 1 | 16 |
| 6 | 11 | 47 | 1 | 25 |
| 7 | 11 | 32 | 1 | 44 |
| 8 | 11 | 28 | 1 | 79 |
| 9 | 13 | 72 | 1 | 41 |
| 10 | 7 | 40 | 1 | 40 |
| 11 | 6 | 6 | 1 | 11 |
| 12 | 6 | 8 | 1 | 13 |
| 13 | 4 | 13 | 2 | 8, 9 |
| 14 | 8 | 23 | 1 | 30 |
| 15 | 9 | 21 | 1 | 25 |
| 16 | 5 | 5 | 1 | 80 |
| 17 | 7 | 35 | 1 | 90 |
| 18 | 8 | 7 | 1 | 52 |

Group 18 的 frame 7 是合法空 component list。每组 tile coverage 都是完整
`0..tile_count-1`；因此先前已导出的全部特效像素都已连接到至少一个帧定义。

## Callback spawn plan

共享 motion 表 `0x0853EE98..0x0853EF2E` 是 15×10 字节
`<s16 effect_id,x,y,render_attributes,delay_ticks>`，末项为
`(-1,0,0,0,0)`。14 个 child 的 spawn tick 为：

```text
0,4,4,8,8,8,12,12,16,16,16,20,20,24
```

其 effect/variant ID 为：

```text
1,0,2,1,1,2,0,1,1,0,2,0,0,0
```

- sequence 2 在 `0x080806DC..0x080806E4` 将表中 `render_attributes`
  左移 8 位后再 OR `0x400`；sequence 3 在 `0x0808079E..0x080807A2`
  只执行左移 8 位。manifest 保存的是这个传给 child 构造器的最终参数，而不是
  表中的原始 `s16`；
- sequence 2/group 2 与 sequence 3/group 3 使用表中 variant，最后 child 在
  tick 111 静态结束；
- sequence 18/group 18 强制所有 child 使用 variant 0，最后 child 在 tick 76
  静态结束；
- sequence 1 在 tick 0 创建三个 group-1 variant-0 child，寿命均为 59 tick；
  三者初始角度/位置含 RNG 和 parent `+0x8C` mode，不能静态生成唯一屏幕坐标；
- sequence 4..17、19..21 的非 motion 分支各创建一个 variant-0 child，其完整
  duration 已写入 manifest；
- sequence 0 不创建 child。

父任务在 terminator 后等待全部 32 个 child 指针清空。父/子 task slot 在同一用户帧
内的调度顺序不是局部静态代码可固定，因此 parent visible release 只声明为
`last_child_tick..last_child_tick+1`，不伪造唯一帧号。

## Child task 原点模型

`0x08080218..0x08080554` 证明 child task 的位置字段及四种 sequence 模型：

| 字段 | 语义 |
|---:|---|
| `task+0x04/+0x06` | `s16` anchor x/y |
| `task+0x08/+0x0A` | `s16` actor-follow delta x/y |
| `task+0x2C/+0x30` | sequence 1 的 `s32` Q8.8 x/y |
| `task+0x34` | sequence 1 写入 `s32` angle；callback 读取低 `s16` |
| `task+0x38` | sequence 1 的 `s32` speed |

- sequence 2/3/18 使用 `parent + motion-table offset`；对战侧与角色朝向满足 ROM
  分支时，x offset 取 `s16(-x)` 并切换 `0x8000` 水平翻转位；
- sequence 8/9/11/16 在生成时保存
  `delta = initial_origin - actor_anchor(spawn)`，之后逐 tick 使用
  `origin(t) = actor_anchor(t) + delta`；actor x 为 Q8.8 截断值或
  `240 - 截断值`，取决于 `actor.orientation == side_id`，y 为 Q8.8 截断值；
- 其余单 child sequence 保持 parent 原点；sequence 0 无 child；
- sequence 1 的三个 child 从 `parent<<8` 开始。ROM 以两次 RNG 结果分别计算 angle
  jitter 和 speed，逐 tick 调用 ROM sin/cos 更新 Q8.8 x/y，随后
  `speed=max(0,speed-24)`。负 Q8.8 值先加 255 再算术右移 8 位，即向零截断。

manifest 保存了逐项公式、32 位 wrap/逻辑右移边界和每个 sequence 的 model ID。
renderer `0x08062C58..0x08062C7C` 又直接证明 component 坐标会与
`task+0x04/+0x08`、`task+0x06/+0x0A` 相加；该 36 字节切片 SHA-256 为
`dc022a30c9ef95ab0bcb78e1a00e9cfa5c3bc4793e9c8352dd664086323e8313`。
父坐标、对战 mode、actor Q8.8 坐标、RNG dispatch 目标/状态及每个 child 的 RNG
结果仍是运行时输入，所以公式闭合不等于产生唯一绝对坐标。

## 运行证据交叉检查

已有自然 OAM trace 的四个总时长与静态 timeline 完全一致：

| 证据 | Group | 静态/运行总帧 |
|---|---:|---:|
| action 5 dust | 1 | 59 |
| bomb projectile | 4 | 7 |
| action 5 hit | 5 | 16 |
| action 16 fire hit | 14 | 30 |

Action 5 hit 的静态 group-5 component tile、顺序和水平翻转也与16帧 OAM
运行清单逐项一致。此交叉检查不替代全量静态 verifier，也不把未提交的临时 trace
作为 artifact 的运行依赖。

## 可复现性

```sh
python3 tools/export_battle_effect_sprite_animations.py \
  --root . \
  --output-dir artifacts/battle-effect-sprite-animations-v1
python3 tools/verify_battle_effect_sprite_animations.py \
  --root . \
  --artifact-dir artifacts/battle-effect-sprite-animations-v1
python3 -m unittest tests.test_export_battle_effect_sprite_animations
```

生产导出耗时 0.24 秒，最大 RSS 26,890,240 字节，无 swap。独立 verifier
不导入领域 exporter，自行从 ROM 重建全部 definition、component、timeline、
callback plan 和 PNG，结果为 18/18 groups、178/178 frames、437/437 components、
23/23 animations、`errors=[]`。verifier 也独立保存预期位置模型并拒绝公式或
sequence model ID 篡改；位置公式的语义依据仍是人工审计且由精确 Thumb 切片哈希
约束，不把两份同结论实现冒充第二个指令级解释器。

## 尚未闭合

- 源空间预览应用 component tile 顺序与 H/V flip，但不应用 screen-space base
  position、priority、affine rasterization 或 callback 动态位移；child task 原点和
  对战侧镜像公式已经闭合，但 component-local → OAM → viewport 仍未合成；
- sequence 1 的公式已经闭合，唯一具体轨迹仍需确定性 RNG dispatch 状态与父对象状态；
- parent 最终释放存在上述 0/1 scheduler tick 边界；
- blend、palette transform 与音频绑定仍未全量闭合。

因此本成果已闭合静态 child OAM 结构、帧选择、hold、callback spawn 状态机和 task
原点公式，但不把源空间 frame PNG 或符号原点冒充最终屏幕帧。
