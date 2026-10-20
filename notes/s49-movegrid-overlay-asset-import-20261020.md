# 原版移动网格覆盖层素材入库（2026-10-20）

## 0. 这一轮做了什么

**只落资产，不接线。** 原版《火影忍者 - 木叶战记》S49 的移动范围覆盖层（BG2）的
**图块与调色板**已经进入重制侧的资产管线，作为可复现、带出处声明的生成产物：

| 产物 | 字节数 | SHA-256 |
| --- | ---: | --- |
| `butano-sequel/graphics/battle_movegrid_overlay_tiles.bmp` | 1142 | `61b2e3b086ad34487eeae8889e24db5ac7e3ab3f952d2c4f8b0a323045e16ccf` |
| `butano-sequel/graphics/battle_movegrid_overlay_tiles.json` | 10456 | `3c72970a3be68932c528130e8a9751c8e666f656c90d043d5c85f6ecfa9c1b2c` |
| `butano-sequel/game/include/konoha/generated_battle_movegrid_overlay_content.h` | 15575 | `6d2cb614b0336c2c9b562909cac7b898d15f478c01b802da000719ac87bd87e6` |

生成器：`tools/generate_butano_movegrid_overlay_assets.py`
门禁：`tests/test_s49_movegrid_overlay_assets.py`（18 项，全绿）

**本轮没有改任何 C++ 代码**：重制侧覆盖层仍是「8bpp + 混合」的旧画法（见
`notes/s49-movegrid-overlay-implementation-spec-20261020.md` 第 5 节步骤 2–4）。

## 1. 证据：素材从哪来

| 项 | 值 |
| --- | --- |
| ROM | `rom/base.gba`，SHA-256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b` |
| 图块记录 | LZ77 @ ROM `0x080B9E94`（文件偏移 `0x0B9E94`），压缩 198 B → 解压 **1024 B**，SHA-256 `0f86c8032129ef1b92fb1464c516a03b1c0ca71672ac5de4d37e8b302cf6ce40` |
| 调色板记录 | LZ77 @ ROM `0x080B9F5C`（文件偏移 `0x0B9F5C`），压缩 36 B → 解压 **32 B**，SHA-256 `d198ec85eff147b157978bb44d1948db5b9893edb5f8f63d4d9b96b5ca7e7e84` |

**解码器不重写**：教科书式 GBA LZ77 解不开这两个 blob；生成器直接
`from tools.butano.export_s49_movegrid_overlay import lz77_decompress`，复用逆向树
已验证的 `_parse_lz77` 布局（`length = (first >> 4) + 3`、
`distance = (((first & 0x0F) << 8) | second) + 1`）。

**布局**：32 个 4bpp 图块按 VRAM 顺序摊成 8 列 × 4 行的 **64×32 索引图**，图块 256 在
左上角（`x = (blob % 8) * 8`，`y = (blob // 8) * 8`）。BMP 用仓库既有的
`tools/butano/indexed_bmp.py::write_4bpp_bmp` 写（未压缩 4bpp 索引 BMP），
调色板用 `8bit = (c << 3) | (c >> 2)` 展开。

**独立佐证**：生成的 BMP 索引图与逆向树已导出的
`artifacts/s49-original-movegrid-overlay-v1/movegrid-tiles-index.png` **逐字节相同**
（64×32、单通道 L），即图块顺序与摊放方式与既有导出物一致。

**调色板不失真**：5bit→8bit 展开满足 `rgb8 >> 3 == rgb5`，因此 BMP 里的 8bit 颜色被
GRIT 之类的工具按 `>>3` 折回 5bit 时**逐通道精确还原**原版的 bank 12（16 色）。

## 2. 实际执行的命令与真实输出

生成（幂等，两次运行产物逐字节相同）：

```
$ export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
$ python3 tools/generate_butano_movegrid_overlay_assets.py
rom        rom/base.gba  sha256=1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b
tiles      0x080B9E94 -> 1024 B  sha256=0f86c8032129ef1b92fb1464c516a03b1c0ca71672ac5de4d37e8b302cf6ce40
palette    0x080B9F5C -> 32 B  sha256=d198ec85eff147b157978bb44d1948db5b9893edb5f8f63d4d9b96b5ca7e7e84
bmp        butano-sequel/graphics/battle_movegrid_overlay_tiles.bmp  1142 B
sidecar    butano-sequel/graphics/battle_movegrid_overlay_tiles.json  10456 B
header     butano-sequel/game/include/konoha/generated_battle_movegrid_overlay_content.h  15575 B
```

门禁：

```
$ python3 -m unittest tests.test_s49_movegrid_overlay_assets -v
... (18 项)
Ran 18 tests in 3.596s

OK
```

M0 出处审计（本轮新增的生成器已被登记，审计仍然通过）：

```
$ python3 tools/audit_butano_reverse_provenance.py
...
generators in the registry: 17
generated products: 36
  declared:     36
  with family:  24
...
  tools/generate_butano_movegrid_overlay_assets.py: 1 product(s)
...
  butano-sequel/game/include/konoha/generated_battle_movegrid_overlay_content.h -> rom-pointer-lz77-inventory-v1
...
problems: none
$ echo $?
0
```

**出处绑定**：头文件声明的反向成果族是 `rom-pointer-lz77-inventory-v1`（manifest
SHA-256 `d4afca9d19c3b764ce40f460d9c73d7c19f908bf25c197d4b082bd6bc5c4bb33`，
`artifact_status: accepted`），并记录两段实际消费的 ROM 字节
（`0x0B9E94+198` 与 `0x0B9F5C+36`）；审计器把两段摘要回查 ROM 字节与该族的
inventory 记录，两边对上。

**失败关闭**：ROM 错一个字节就拒绝，**不落任何文件**（不建输出目录）；输出目录也不会
被创建。实测退出码 2，stderr 含 `ROM SHA-256 mismatch ... refusing to generate`。

## 3. 产物怎么用（下一轮的接线接口）

### 3.1 生成头 `generated_battle_movegrid_overlay_content.h`

| 符号 | 内容 |
| --- | --- |
| `battle_movegrid_overlay_palette_rgb5[16]` | bank 12 的 5bit 颜色，可直接喂 `bn::color(r, g, b)` |
| `battle_movegrid_overlay_palette_rgb8[16]` | 同一批颜色的 8bit 展开（BMP 里用的值） |
| `battle_movegrid_overlay_palette_bgr555[16]` | 原始 16 个 BGR555 |
| `battle_movegrid_overlay_tile_indices[32]` | 覆盖层占用的图块号 256..287（VRAM 顺序） |
| `battle_movegrid_overlay_tile_data[1024]` | 4bpp 图块字节（`alignas(4)`），与 ROM 解压结果逐字节相同 |
| `battle_movegrid_overlay_tile_words[256]` | 同一批字节的小端 32bit 视图，正好是 `bn::tile`（`uint32_t data[8]`）的排布 |
| `battle_movegrid_overlay_tile_views_agree()` | `static_assert` 已在头里钉住：两个视图必须一致 |

接线写法（`bn::tile` 32 字节，正好一块 4bpp 图块）：

```cpp
const bn::regular_bg_tiles_item tiles_item(
        bn::span<const bn::tile>(
                reinterpret_cast<const bn::tile*>(
                        konoha::battle_movegrid_overlay_tile_words.data()),
                32),
        bn::bpp_mode::BPP_4);
```

头文件已用宿主 `clang++ -std=c++20` 实际编译并运行过（`bn::tile` 尺寸 32、
`static_assert` 通过、调色板与首字节读数正确）。

### 3.2 位图与 sidecar

`battle_movegrid_overlay_tiles.json` 的 `type` 是 Butano 图形工具的
**`regular_bg_tiles`**（只出图块、不出 tilemap），`bpp_mode: bpp_4`，
`generate_palette: true` ⇒ 构建时除了 `bn::regular_bg_tiles_items::…` 还会生成一份
`bn::bg_palette_item`（正是覆盖层要的自有 16 色调色板）。
sidecar 里另外记了 ROM 出处（地址、压缩/解压字节数、各级 SHA-256）与 32 条图块布局
（`blob_index → tile_index / sheet_col / sheet_row / x / y`）。

> ⚠️ 本机没有 `grit`（devkitPro 图形工具未安装），所以 **Butano 的图形工具没有真的跑过**
> 这一对文件；sidecar 的字段是照着
> `third_party/butano/butano/tools/butano_graphics_tool.py` 的 `RegularBgTilesItem`
> 逐字段对齐写的。下一轮构建时才会真正验证。

## 4. 未确立（不归本轮）

| 项 | 说明 |
| --- | --- |
| **覆盖层的图块选择规则** | 「每个格子该用哪一块图块」**不是本轮推导的**，归并行代理所有（产物 `artifacts/s49-original-movegrid-overlay-rule-v1/`）。本轮只提供图块与调色板本身，规则覆盖不到的邻域组合仍应标 `unknown`。 |
| 覆盖语义 | 「可达高亮」还是「不可达压暗」仍未确立。 |
| 自然执行可达性 | 现有收据是脚本化行走，不是覆盖证明。 |
| bank 12 的 index 6–11 用途 | 非零，但含义未定。 |
| Butano 构建期验证 | 见 3.2 的警告：`grit` 不在本机。 |

## 5. 引用

- 逆向侧机制：`notes/s49-dispcnt-bit10-layer-20261020.md`、
  `notes/s49-movegrid-overlay-assets-20261020.md`、`notes/s49-movegrid-overlay-tilemap-20261020.md`
- 实施规格：`notes/s49-movegrid-overlay-implementation-spec-20261020.md`（第 5 节步骤 1 = 本轮）
- 既有导出物：`artifacts/s49-original-movegrid-overlay-v1/`
- 本轮代码：`tools/generate_butano_movegrid_overlay_assets.py`、
  `tests/test_s49_movegrid_overlay_assets.py`
- 复用而非重写的解码器：`tools/butano/export_s49_movegrid_overlay.py::lz77_decompress`
