# 角色战斗视觉矩阵全量导出（2026-07-29）

## 结论

ROM `0x08596D5C..0x0859903C` 是 62 个角色×9 个视觉槽的稀疏战斗 OBJ
矩阵，不是旧笔记所称的 312 行地图 tile 表。558 个 16-byte descriptor 中：

- 342 个槽四指针完整，216 个槽全零，没有部分填充；
- 槽 0–4 各有 62 项，槽 5–8 各有 8 项；
- 342 个逻辑槽去重为 250 套 definition/animation/graphics/palette 资源；
- 逻辑视图共 2674 帧、2860 个 component、1045 条动画、4246 个 keyframe；
- 去重资源共 2004 帧、2190 个 component、784 条动画、3187 个 keyframe；
- 250 段 graphics 共 60,430 个 4bpp tile，全部由 component 精确引用；
- palette 有 48 个 ROM 指针、40 份不同的 32-byte 内容。

完整成果位于 `artifacts/character-battle-visuals-v1/`：每套资源保存 component
区、frame 指针表、timeline 区、animation 指针表、原始 4bpp 图块、BGR555 palette
和逐帧 indexed PNG；`manifest.json` 保留 558 个逻辑槽到 250 套物理资源的映射。

这使地图/战斗角色编辑器可以直接消费 2004 个完整去重源空间帧、全部组件原始字节和
原始 hold，而不必依赖 Butano 生成目录或重新运行 mGBA。唯一 `FBFF` 原始字节仍被
无损保存，但其运行语义已由 2026-07-30 的同快照一字节 A/B 闭合为 ROM 数据异常；
导出时只对该已知地址采用显式 `FFFF` 终止修复。最终屏幕坐标、相机、priority、
运行时槽选择、blend 和 palette transform 不在本源空间成果的完成边界内。

## 表身份

| 对象 | 文件范围 | 大小 | SHA-256 |
|---|---:|---:|---|
| 62×9 descriptor 矩阵 | `0x596D5C..0x59903C` | `558×16 = 0x22E0` | `baa3f86793e15d0d4abd44fcf10518da15ba0d76588b918838c3660e042e01dc` |
| ROM | `rom/base.gba` | `0x600000` | `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b` |

行索引为：

```text
row = (character_id - 1) * 9 + visual_slot
character_id = 1..62
visual_slot = 0..8
```

每行四个 `u32` 依次指向 frame pointer table、animation pointer table、raw
4bpp graphics 和 16 色 raw BGR555 palette。矩阵在 `0x59903C` 精确结束；
从该地址开始是独立的 14×16 regular BG 场景资源表，其首行是表内 ID 0 全零
哨兵。旧扫描把该行计入角色矩阵后得到的 217 个空行结论不成立。

当前槽名沿用已有 consumer/Butano 视觉目录：

```text
0 field_idle_and_movement
1 cast_facing_right
2 throw_facing_right
3 melee_facing_right
4 hit_facing_right
5 cast_facing_left
6 throw_facing_left
7 melee_facing_left
8 hit_facing_left
```

manifest 把这些名称与 raw slot ID 同时保存；自然场景中的每条上层业务选择仍需单独
验收，不能仅凭名称推断某一运行帧必然选择哪个槽。

selector `0x0807AE04..0x0807B284` 的 SHA-256 为
`5a0d06474ee94f5d3fd68cfe6c90224ce5a4cc8ffbb8ceeb6c4529c67ecd1b0b`。
代码使用预偏基址 `0x08596CCC = table - 0x90`：

```text
descriptor = 0x08596CCC + character_id * 0x90 + visual_slot * 0x10
```

op 0/1/2 选择槽 0，并分别使用角色 facing 派生的 animation variant；op 3/4/5
选择右向槽 1/2/3 或左向槽 5/6/7；op 6/7 选择右向槽 4 或左向槽 8。左向槽
5–8 的首指针为空时，代码回退对应的 1–4 并设置 H-flip `0x8000`。allocator
`0x080625A4..0x080626B0` 按 slot×16 把四个指针安装进 sprite task，SHA-256 为
`e238cd1ee159265fb8b718766f336f8d5462596954f93c7805d1bf33dd6b3c54`。

## Definition、component 与 timeline

animation table 的第一个指针也是第一条 timeline：

```text
frame_count = (first_timeline - frame_pointer_table) / 4
```

frame pointer 严格递增；一帧的右边界是下一帧指针，最后一帧右边界是 frame pointer
table。component 为 20 bytes：

| Offset | Type | 已验证语义 |
|---:|---|---|
| `+00` | `u16` | graphics 中的 tile offset |
| `+02` | `u8` | bit0 H flip、bit1 V flip |
| `+03` | `u8` | affine angle offset；本表全零 |
| `+04/+06` | `s16` | component-local x/y |
| `+08/+0A` | `u16` | width/height |
| `+0C/+0E` | `u16` | X/Y 8.8 scale；本表全 `0x100` |
| `+10` | `u8` | control；本表全 `0xFF` |
| `+11` | `u8` | OBJ attribute byte；本表全零 |
| `+12` | `u16` | reserved；本表全零 |

timeline 单项为 `<u16 frame_id,u16 hold_frames>`，以 `<0xFFFF,0>` 结束。
1045 条逻辑动画均有终止符，hold 为 1–16，总时长为 4–72 帧。

## 唯一异常尾标及运行时闭环

2674 个逻辑 frame 中，2673 个尾部是 `ffff0000`。唯一例外是 row 227
（character 26、slot 2、frame 2）在 `0x0825A8E4` 的 `fffb0000`：

- 低 10 位仍是 OBJ tile sentinel `0x3FF`；
- 该帧由 timeline 实际引用；
- 按 frame pointer 边界解析时，前面恰有一个完整 20-byte component；
- 通用 renderer 的 `0x080629FC/0x080631FE` 读取完整 signed halfword，只接受
  `-1 / 0xFFFF`；`0xFBFF` 的 signed 值是 `-1025`，不是合法终止符。

2026-07-30 从已验证的 `state-0154.ss9` 生成完全相同的注入 task，仅对 ROM
`0x0825A8E5` 做 `FB→FF` 一字节 A/B。受守卫 mGBA 的断点证据为：

- 原 ROM 在循环条件处依次读取
  `0x0825A8E4=FBFF → 0x0825A8F8=00FF → 0x0825A90C=0100 →
  0x0825A920=A8D0`，每次严格前进一个 20-byte component，证明 renderer 越过
  指针边界继续解释后续数据；
- FFFF 对照在两帧中都于 `0x0825A8E4` 读取 `FFFF/-1` 并立即停止；frame 2
  产生唯一合法对象 `attr0/1/2=8438/C068/E340`，没有伪 component；
- 两条路线输入 task 逐字节相同，guard 都由 success marker 正常结束，峰值进程树
  RSS 分别为 47.46/47.40 MiB，没有遗留 mGBA；
- 原 ROM SHA-256 保持
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`，
  一字节对照 ROM SHA-256 为
  `3f55e607829db4497a1f49200514777c89df01f3624fd849005b96247502507a`。

因此 `FBFF` 已闭合为唯一的单字节损坏终止符，而不是新格式。导出器继续保存
`frame_trailer_raw_hex=fffb0000` 和 `renderer_terminator=false`，同时以
`runtime_verified_single_byte_corrupt_terminator` 标记该帧，明确关联
`artifacts/character-fbff-runtime-v1/manifest.json`；2004/2004 个去重源空间帧现在
均为 `render_complete=true`。这项修复只决定 component 边界，不扩大为屏幕坐标、
相机、priority、blend 或 palette transform 的运行时签发。

早期两次 idle timeout 都实际启动了 `rom/base.gba`，没有运行已经生成的
`control.gba`；这属于实验命令错误，不是 FFFF 对照失败。新探针直接在 renderer
循环设置有界断点，FBFF 路径观察四次步进后即由成功标记结束，不再把超时当主要证据。

## 可复现性

```sh
python3 tools/export_character_battle_visuals.py \
  --root . \
  --output-dir artifacts/character-battle-visuals-v1
python3 tools/verify_character_battle_visuals.py \
  --root . \
  --artifact-dir artifacts/character-battle-visuals-v1
python3 tools/verify_character_fbff_runtime.py \
  --root . \
  --artifact-dir artifacts/character-fbff-runtime-v1
python3 -m unittest \
  tests.test_export_character_battle_visuals \
  tests.test_build_character_fbff_control_rom \
  tests.test_mgba_character_fbff_probe_script \
  tests.test_verify_character_fbff_runtime
```

导出器约 3.2 秒，最大 RSS 45,621,248 bytes；独立 verifier 约 4.0 秒，最大
RSS 46,964,736 bytes。二者均无 swap。结构 verifier 不导入 exporter 或任何
`tools.*`，会从 ROM 独立解析、手写解码 4bpp/BGR555，并通过 Pillow 核对每张 PNG
的索引像素、palette 和透明色；测试覆盖 PNG、slot alias、raw binary、timeline
和额外文件篡改。FBFF verifier 另行从 ROM 重建一字节对照、核对 renderer 指令窗口、
两条运行 trace、OAM、截图、输入 task 和全部文件哈希，并含篡改反例。槽名称属于项目
约定；本闭环只签发源空间 component 终止和该帧像素，不冒充场景业务选择或屏幕合成。

初始矩阵导出完全离线；FBFF 运行闭环启动了两次受守卫静音 mGBA。全过程没有读取或
修改 `butano-sequel`。
