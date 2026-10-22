# `0x53F140` 通用 Sprite 定义、像素与 OBJ 资产链

日期：2026-07-29

## 结论

`0x53F140` 是 43 组 definition/animation 指针对；它本身不直接保存像素或
调色板指针。`0x08080A48` 会把 ROM `0x0812F298` 的 49 个 4bpp tile 与
`0x0812F584` 的 16 色 palette 解压到 OBJ VRAM/PRAM。43 项 tile-base
offset 和 45 个 component 正好把 tile `0..48` 各引用一次，无缺口、无重叠。

因此规范像素、palette、每 ID component 几何和 OBJ 地址链已经完全静态闭合，
不再需要 mGBA 捕获才能导出资源。运行时捕获只在要证明某场景是否后续覆盖
这些规范资源时才是可选验证。

可复现产物：

- `tools/export_sprite_definition_runtime_chain.py`
- `tools/verify_sprite_definition_runtime_chain.py`
- `artifacts/sprite-definition-assets-v2/`（43 张 ID PNG、总图集、两个无损
  二进制和 manifest，共 47 个文件）
- `tests/test_export_sprite_definition_runtime_chain.py`

`artifacts/sprite-definition-runtime-v1/manifest.json` 保留为发现阶段历史证据；
其“必须运行时捕获像素”的边界已被 v2 取代。

## ROM 身份

| 对象 | 文件偏移 | 大小 | SHA-256 |
|---|---:|---:|---|
| definition/animation 指针对 | `0x53F140` | `43×8 = 344` | `5873ae022e9b6290f876aab367b6dbe95b7a97b9b7a2f15d0861dc747196f3f8` |
| 每 ID 的 tile-base offset | `0x53F298` | `43×2 = 86` | `86d57e438c3b3e9a877ebea8d910e2782c30b5bcbf8ca4f305df1deee6d231d6` |
| `concat ROM[D_i[0]:D_i[0]+0x28]` | 间接寻址 | `43×0x28` | `439eb69f5ee2eadefe6fbd66b88ba27fb53c6552ac184267a803917fe8e98248` |
| 压缩 OBJ graphics | `0x12F298` | `745 → 1568` | 解压后 `1472c4df7436428d41c668fd6ebb21f58c2a13b0876f372fe3f4b5d602aaa256` |
| 压缩 OBJ palette | `0x12F584` | `20 → 32` | 解压后 `043a3dbc0b648314d4289bea8eeca660c17085ddd1c2fb225e50ace435f95ab6` |

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

## 静态像素覆盖

规范资源为 49 个连续 4bpp tile。每项实际源 tile 为：

```text
source_tile = tile_base_offset[id] + component.tile_offset
tile_count = (component.width / 8) * (component.height / 8)
```

ID `0..9` 覆盖 tile `0..9`，ID `10..19` 覆盖 `25..34`，ID `20..29`
覆盖 `37..46`，ID `30..31` 覆盖 `10..11`，ID `32..33` 覆盖
`35..36`，ID `34..35` 覆盖 `47..48`，ID 36 覆盖 12，ID 37 覆盖
`13..17`，ID 38 覆盖 `18..20`，ID `39..42` 覆盖 `21..24`。

ID 37 按 component 位置重建为 `40×8`，ID 38 为 `24×8`；其余均为
`8×8`。PNG 保留 16 色索引，OBJ 透明索引为 0。

## 运行时地址链

`0x08080A48` 先写入 tile base/palette bank，并两次调用
`0x0809C0E8` 的 BIOS LZ77 VRAM 解压包装：

```text
0x0812F298 -> 0x06010000 + u16[0x0202CA24] * 32
0x0812F584 -> 0x05000200 + u8[0x0202CA26] * 32
```

`0x08080B08` 随后读取 `0x0853F140` 与 `0x0853F298`，并通过
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

- `0x08080A48`：规范 graphics/palette 的静态资源加载器；
- `0x08080A5C` / `0x08080A6A`：graphics / palette 解压调用；
- `0x08062668`：按 `id×8` 安装 definition/animation 指针；
- `0x0806298C`：从当前 frame 选择 component list；
- `0x08063108`：把 task tile base 与 component tile offset 合成 attr2；
- `0x08063134`：另一种 descriptor 的条件复制分支；通用 task flags `0x49`
  不进入该分支；
- `0x080631F6..0x08063210`：步进到下一个 component/terminator。

## 被撤回的错误哈希

`49b3609e0ae207c8d277f58677305bbe96e4448626e3b05f79f69fbe3614e970`
来自错误的 `concat ROM[D_i-0x18:D_i+0x10]` 假设，不是规范 descriptor
哈希。该假设只对普通一 component entry 碰巧成立；ID 37、38 的
`D_i[0] = D_i-0x2C` 会立即暴露错误。规范证据只能使用实际解引用
`D_i[0]` 后的范围。

## 剩余边界

- animation sequence 尚未完成业务语义命名；
- 尚未用自然场景证明加载后没有其他系统覆盖这 49 个规范 tile；这不影响静态
  资源导出，只有场景最终帧身份需要时才运行验证；
- 若确需运行时验证，必须经 `tools/run_guarded.py`，复用最近已验证快照，只记录
  `0x0202CA24/0x0202CA26` 与精确 VRAM/PRAM 区间哈希，不再重复导航做资源发现。

本里程碑仅离线读取 ROM，没有启动 mGBA。生产导出耗时约 0.11 秒，最大 RSS
约 22.8 MiB、peak footprint 约 17.5 MiB，无 page fault 或 swap。独立验证器
从 ROM 自行解压、重建 43 张 PNG 并核对 indexed pixels、palette、透明索引和
文件集合，结果为 43/43 entry、45/45 component、43/43 asset、49/49 tile，
`errors=[]`。
