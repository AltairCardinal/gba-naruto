# Cutscene OBJ 静态资源全量导出（2026-07-29）

## 结论

历史名为 `cutscene-scripts` 的 `0x53DF70/0x53DF90` 两张四记录表，现已转化为
可直接使用和独立复核的静态图像成果：

- 4/4 个 LZ gfx/palette bundle 全部解压并导出；
- 4 个无损 indexed OBJ atlas；
- 相邻 definition/animation 指针结构证明 10 个静态 frame，并全部导出为
  原生尺寸 indexed PNG；
- ID 0–2 各有两个 `64×64` frame，tile offset 为 `0, 64`；
- ID 3 有四个 `32×32` frame，tile offset 为 `0, 16, 32, 48`；
- 四组 palette 解压结果相同，均为 32 字节、16 色 BGR555；
- 共 14 个 PNG 和 1 个 ROM-bound manifest，约 `76 KiB`。

这批资源是 OBJ 视觉资源，不是剧情 opcode、对白或 cutscene 脚本。

## ROM、表与消费者

- ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- gfx/palette 表：`0x53DF70`，`4×8`，SHA-256：
  `16b13c432f37ba159697cd9d9d6d5d5147adc41c44c8cc0cc44ce7f2935f1401`
- definition/animation 表：`0x53DF90`，`4×8`，SHA-256：
  `1c76f2100b2067e78abd713e312bd845d7c874b030f51ef08f968961862e198a`
- 两表连续 64 字节 SHA-256：
  `1e6d5016b58d0e565c5a40791a7f2684d6129e0a1c4e85e79317af4d2b1a7f62`

`0x08072F0C` 用 `id << 3` 索引第一张表，经 `0x0809C0E8` 将 gfx 和 palette
分别解压至 `0x06016000`、`0x05000380`。同一链把第二张表交给
`0x080625A4`；`0x08062668` 的路径按相同 ID 安装 definition 与 animation
指针。所有直接调用只传 ID `0..3`；`0x53DFB0` 是独立对象，不得扩展成第五条记录。

## 资源摘要

| ID | gfx pointer | 压缩/解压 bytes | gfx 解压 SHA-256 | definition / animation | frames |
|---:|---|---:|---|---|---:|
| 0 | `0x0812D9E4` | `1112 / 4096` | `ff3e1b090a18378eb51b2c25ad7e9115ea33d6c9afe11ceeb09cbd392a5496c5` | `0x0812DF2C / 0x0812DF44` | 2 |
| 1 | `0x0812DF4C` | `1187 / 4096` | `1494d4db49423aaf026f3a1d45df4a63c70db9a0c6c7bae72621f7f7688bae0d` | `0x0812E474 / 0x0812E48C` | 2 |
| 2 | `0x0812E494` | `1113 / 4096` | `ff180630c246cf7c9e161576b33c0e734157a2a927c07be6bc90a80619654079` | `0x0812E990 / 0x0812E9A8` | 2 |
| 3 | `0x0812E9B0` | `935 / 2048` | `d2b44e9c68dc23771249bedfb7397de35f19e6769f99a91f86512b7604b43ec1` | `0x0812EDD0 / 0x0812EE00` | 4 |

palette LZ 记录均为 22 字节，解压 SHA-256 均为
`99d45ddc5929d60c150146f1292cd55f56d89afbff70ffd0f377128fe75352af`。

## Definition 与 animation 边界

每组 frame 数由相邻指针直接推导：

```text
(animation_table_pointer - definition_table_pointer) / 12
```

其中每个 frame 占 4 字节 definition pointer 加 8 字节相邻 animation record。
definition pointer 指向 24 字节单组件记录；manifest 保存完整原始字节、哈希、
tile offset、原点、宽高和未解释 tail words。animation pointer 必须精确指向相邻的
8 字节记录；manifest 保存四个原始 `u16`。

首条记录为 `(frame=0, value=1, 0xFFFF, 0)`，后续记录的第二个值为 0。
静态结构和 frame 选择可以确定，但 0 的运行期时序含义没有自然运行时捕获，因此产物
明确标记 `animation_timing_interpreted: false`，不伪造播放时长或最终序列。

## 可重复成果与验证

- 导出器：`tools/export_cutscene_obj_assets.py`
- 独立验证器：`tools/verify_cutscene_obj_export.py`
- 测试：`tests/test_export_cutscene_obj_assets.py`
- 产物：`artifacts/cutscene-obj-v1/`
- schema：`cutscene-obj-export-v1`

```bash
python3 tools/export_cutscene_obj_assets.py \
  --root . \
  --output-dir artifacts/cutscene-obj-v1

python3 tools/verify_cutscene_obj_export.py \
  --root . \
  --artifact-dir artifacts/cutscene-obj-v1
```

独立验证器不调用导出器、共享 renderer 或 PNG encoder；它从 ROM 重算两张表、
LZ 边界、消费者 literal、definition/animation 记录、4bpp 像素和 palette，并逐像素
比较全部 14 张 PNG：

```text
verified_resources: 4
verified_frames: 10
verified_atlases: 4
errors: []
```

定向测试 9 项通过；与共享图像底座、旧表身份测试、tile-assets、story layer 和
menu portrait 一起回归共 48 项，`20.490s` 全部通过。生产导出耗时约 `0.15s`，
最大 RSS `23,625,728` 字节，peak memory footprint `18,075,648` 字节，
page fault 与 swap 均为 0。
视觉抽查 `resource_0_frame_00.png`、`resource_0_atlas.png` 与
`resource_3_atlas.png` 均呈现边界完整的透明 OBJ 字形。

本里程碑完全离线读取 ROM，没有启动 mGBA，也没有写入 `butano-sequel/`。

## 剩余边界

1. 这 10 个 frame 的静态像素与 frame 选择已闭合；第二字段为 0 的运行期 timing
   含义仍待需要播放等价性时做最小运行时 trace。
2. `0x53F140` 的 43 条通用 sprite definition/animation pair 仍需追踪其实际
   gfx/palette 分配链，不能套用本表资源。
3. `0x53D644` 的原 ROM 日文字形可静态导出 atlas，但不代表中文替换字体或
   group-0 字体来源已经定位。
