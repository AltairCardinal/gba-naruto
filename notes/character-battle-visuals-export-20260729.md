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

这使地图/战斗角色编辑器可以直接消费 2003 个完整去重源空间帧、1 个明确标为
provisional 的指针边界预览、全部组件原始字节和原始 hold，而不必依赖 Butano
生成目录或重新运行 mGBA。最终屏幕坐标、相机、priority、运行时槽选择、blend 和
palette transform 不在本静态成果的完成边界内。

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
4bpp graphics 和 16 色 raw BGR555 palette。矩阵右端 `0x59903C..0x59904C`
还有一行表外零 padding；旧扫描把它计入后得到的 217 个空行结论不成立。

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

## 唯一异常尾标

2674 个逻辑 frame 中，2673 个尾部是 `ffff0000`。唯一例外是 row 227
（character 26、slot 2、frame 2）在 `0x0825A8E4` 的 `fffb0000`：

- 低 10 位仍是 OBJ tile sentinel `0x3FF`；
- 该帧由 timeline 实际引用；
- 按 frame pointer 边界解析时，前面恰有一个完整 20-byte component；
- 通用 renderer 的 `0x080629FC/0x080631FE` 又表现为比较完整 signed halfword
  `-1`，因此目前不能把 `0xFBFF` 的运行语义宣称为完全闭合。

导出器保存 `frame_trailer_raw_hex`，并把该帧标记为
`render_complete=false / provisional_pointer_bounded_preview`；它只预览尾标前的
一个完整 component，不声称等价于 renderer 最终输出。manifest 明确设置
`static_source_space_frames=false` 和
`all_component_termination_semantics_complete=false`。结构独立 verifier 锁定
“2003 个去重资源帧使用 `FFFF`、1 个使用 `FBFF`”，不会静默归一化异常字节。

## 可复现性

```sh
python3 tools/export_character_battle_visuals.py \
  --root . \
  --output-dir artifacts/character-battle-visuals-v1
python3 tools/verify_character_battle_visuals.py \
  --root . \
  --artifact-dir artifacts/character-battle-visuals-v1
python3 -m unittest tests.test_export_character_battle_visuals
```

导出器约 3.2 秒，最大 RSS 45,621,248 bytes；独立 verifier 约 4.0 秒，最大
RSS 46,964,736 bytes。二者均无 swap。结构 verifier 不导入 exporter 或任何
`tools.*`，会从 ROM 独立解析、手写解码 4bpp/BGR555，并通过 Pillow 核对每张 PNG
的索引像素、palette 和透明色；测试覆盖 PNG、slot alias、raw binary、timeline
和额外文件篡改。槽名称属于项目约定，`FBFF` 运行解释仍是显式未决项，不由结构
verifier 冒充业务语义证明。

本里程碑完全离线，没有启动 mGBA，也没有读取或修改 `butano-sequel`。
