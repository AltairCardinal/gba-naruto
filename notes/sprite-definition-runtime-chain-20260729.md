# `0x53F140` 通用 Sprite 定义与运行时 OBJ 资产链

日期：2026-07-29

## 结论

`0x53F140` 是 43 组 definition/animation 指针对；它不直接保存像素或调色板
指针。静态定义已完整提取为 43 条 entry、45 个 component，并已追到运行时
OBJ tile base、palette bank、OAM attr2、OBJ VRAM 和 OBJ palette 地址。

这关闭了“表结构和初始 component 几何”的静态缺口，但**没有**把运行时
OBJ VRAM 内容冒充成 ROM 内静态图像。实际像素和最终 palette 仍需在对应
Sprite 被创建后做受控运行时捕获。

可复现产物：

- `tools/export_sprite_definition_runtime_chain.py`
- `tools/verify_sprite_definition_runtime_chain.py`
- `artifacts/sprite-definition-runtime-v1/manifest.json`
- `tests/test_export_sprite_definition_runtime_chain.py`

## ROM 身份

| 对象 | 文件偏移 | 大小 | SHA-256 |
|---|---:|---:|---|
| definition/animation 指针对 | `0x53F140` | `43×8 = 344` | `5873ae022e9b6290f876aab367b6dbe95b7a97b9b7a2f15d0861dc747196f3f8` |
| 每 ID 的 tile-base offset | `0x53F298` | `43×2 = 86` | `86d57e438c3b3e9a877ebea8d910e2782c30b5bcbf8ca4f305df1deee6d231d6` |
| `concat ROM[D_i[0]:D_i[0]+0x28]` | 间接寻址 | `43×0x28` | `439eb69f5ee2eadefe6fbd66b88ba27fb53c6552ac184267a803917fe8e98248` |

ROM 为 `rom/base.gba`，SHA-256：
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。

`0x53F298` 的 43 个值依次为：

```text
0,1,2,3,4,5,6,7,8,9,25,26,27,28,29,30,31,32,33,34,
37,38,39,40,41,42,43,44,45,46,10,11,35,36,47,48,12,13,
18,21,22,23,24
```

它们是当前 43 个 Sprite ID 对应的 tile-base offset；历史上把更长的后续字节
一并解释为 64 项角色 ID 表是错误的，相关写回必须继续禁用。

## Component list 结构

每个 `definition_ptr` 的首个 `u32`（即 `D_i[0]`）指向 component list：

```text
component[0]  component[1] ...  FFFF0000 terminator
0x14 bytes    0x14 bytes         4 bytes
```

渲染器在 `0x080629FC` 把 component `+0x00` 读为有符号半字，`-1`
终止；`0x080631F6..0x08063210` 每次前进 `0x14` 并重复检查。

代码可证字段：

| 偏移 | 类型 | 当前最强语义 |
|---:|---|---|
| `+0x00` | `u16/s16` | 非终止时为 OBJ tile offset；`-1` 终止 |
| `+0x02` | `u8` | OAM 控制计算 flag，位名未知 |
| `+0x03` | `u8` | 坐标/变换路径 flag，位名未知 |
| `+0x04` | `s16` | 水平定位输入，业务名未定 |
| `+0x06` | `s16` | 垂直定位输入，业务名未定 |
| `+0x08` | `s16` | 宽度，只接受 `8/16/32/64` |
| `+0x0A` | `s16` | 高度，只接受 `8/16/32/64` |
| `+0x0C` | `s16` | affine 相关变换乘数，轴名未定 |
| `+0x0E` | `s16` | 第二个 affine 相关变换乘数，轴名未定 |
| `+0x10` | `u8` | 未见 renderer 消费；现有样本均 `0xFF` |
| `+0x11` | `u8` | 并入 OAM 控制字的 attribute byte |
| `+0x12` | `u16` | 未见独立消费；现有样本均 `0` |

41 条 entry 各含一个 `8×8` component。ID 37、38 各含两个：

- ID 37：`tile +0, 8×8` 与 `tile +1, 32×8`
- ID 38：`tile +0, 8×8` 与 `tile +1, 16×8`

因此全表共 45 个 component。

## 运行时地址链

`0x08080B08` 读取 `0x0853F140` 与 `0x0853F298`，并通过
`0x08063494 → 0x080625A4` 创建 Sprite task：

```text
task.tile_base = u16[0x0202CA24] + tile_base_offset[id]
task.palette_bank = u8[0x0202CA26]

attr2.tile = task.tile_base + component.tile_offset
attr2.palette = task.palette_bank << 12

OBJ tile bytes = 0x06010000 + attr2.tile * 32
OBJ palette bytes = 0x05000200 + task.palette_bank * 32
```

关键代码点：

- `0x08062668`：按 `id×8` 安装 definition/animation 指针；
- `0x0806298C`：从当前 frame 选择 component list；
- `0x08063108`：把 task tile base 与 component tile offset 合成 attr2；
- `0x08063134`：必要时把 component tile 数据复制到 OBJ VRAM；
- `0x080631F6..0x08063210`：步进到下一个 component/terminator。

## 被撤回的错误哈希

`49b3609e0ae207c8d277f58677305bbe96e4448626e3b05f79f69fbe3614e970`
来自错误的 `concat ROM[D_i-0x18:D_i+0x10]` 假设，不是规范 descriptor
哈希。该假设只对普通一 component entry 碰巧成立；ID 37、38 的
`D_i[0] = D_i-0x2C` 会立即暴露错误。规范证据只能使用实际解引用
`D_i[0]` 后的范围。

## 下一步运行时捕获边界

后续捕获应经 `tools/run_guarded.py` 启动 mGBA，并从已验证的最近快照开始：

1. 在 `0x08080B08` 记录自然命中的 Sprite ID；
2. 在 task 创建后记录 tile base、palette bank 与 definition/animation 指针；
3. 在首帧和每个新 frame 稳定后，按 component 的 tile offset、宽、高精确导出
   OBJ VRAM tile 与对应 32-byte palette；
4. 保存 run ID、ROM/快照哈希、task 地址、frame/component 索引及原始 dump；
5. 同一 ID/帧已有同哈希捕获时直接复用，不重复走长导航。

本里程碑仅离线读取 ROM，没有启动 mGBA。生产导出耗时约 0.11 秒，最大 RSS
约 23.5 MB，无 page fault 或 swap。
