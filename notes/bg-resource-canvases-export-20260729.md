# BG 场景资源表完整导出（2026-07-29）

## 结论

ROM `0x0859903C..0x0859911C` 是由硬件 BG loader 直接消费的 14×16 字节场景资源
选择表，不是角色矩阵末尾的 padding。ID 0、8 是全零哨兵；其余 12 项均为：

```text
u32 graphics_lz77
u32 palette_lz77
u32 tilemap_lz77
u32 color_mode_8bpp
```

ID 1–7 是 4bpp，ID 9–13 是 8bpp。完整成果位于
`artifacts/bg-resource-canvases-v1/`，每项保存三份 ROM 原始 LZ77 记录、三份解压
二进制、256×80 原始 strip 和按 consumer 规则生成的 256×160 可见画布。

## 边界和哈希

| 范围（右端不含） | 大小 | SHA-256 |
|---|---:|---|
| 表 `0x0859903C..0x0859911C` | `0xE0` | `57e9b8b6b7c3003615c39539f80934f142efeb1e6674114fbaca98bc629f7da2` |
| loader `0x08088348..0x0808842A` | `0xE2` | `1d581ddbdfb89f17de5b5e52fd1b34d9952fcaddf8e4f24f1f86982facf6db27` |
| 基准 ROM | `0x600000` | `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b` |

下一张表从 `0x0859911C` 开始，是已经闭合的 19×8 战斗特效 graphics/palette
资源表。因此当前边界两侧都已有独立表结构和 verifier 证明。

## Loader 语义

`0x08088348` 的静态原型可记为：

```text
(u8 entry_id, u8 bg, u8 charblock, u8 screenblock, u8 bgcnt_extra)
```

它按 `0x0859903C + entry_id * 0x10` 读取 descriptor：

- graphics 解压到 `0x06000000 + charblock * 0x4000`；
- palette 解压到 BG palette RAM `0x05000000`；
- 32×10 u16 tilemap 解压到
  `0x06000000 + screenblock * 0x0800`；
- mode 非零时设置 `BGxCNT` bit 7，即 GBA 8bpp text BG；
- 从 tilemap 目标 `+0x280` 继续填满 32×32 screenblock：4bpp 使用
  `0x0000`，8bpp 使用 `0x001E`。

所以 ROM 原始 tilemap 只有 256×80；GBA 可见的 256×160 层由原始 10 行加上
consumer 填充的 10 行构成。artifact 同时保留这两个层级，没有把填充行冒充 ROM
原始数据。

## 选择链

loader 的四个直接调用点是 `0x0807AAA6`、`0x0808F522`、`0x08091716` 和
`0x080930D6`：

- 前两条路径读取
  `u8[0x0853D910 + battle_id * 0x20 + 0x1C]`；47 个 battle header
  只选择 ID 1–7，分布为 `23/3/5/4/1/1/10`；
- `0x0808F522` 对输入 50–54 还使用 `entry_id = input_id - 41`，连接 ID 9–13；
- `0x08091716` 固定选择 ID 9；
- `0x080930D6` 固定选择 ID 1。

这证明 ID 1–7 是 battle-map 关联的 4bpp 决斗/场景背景，ID 9–13 是特殊场景使用
的 8bpp 背景。但目前没有给所有 12 项赋予自然语言场景名；loader 本身也没有 entry
ID 上界检查。章节脚本解释器的 opcode `0x1E` 也会把脚本操作数送入这条加载链；
现有脚本分析器尚未枚举全部 `0x1E` 操作数，因此 manifest 明确保留
`runtime_entry_selection_complete=false`。

## 导出统计

- 12/12 有效项；
- 7 张 4bpp、5 张 8bpp；
- 11 份唯一 graphics、12 份唯一 palette、8 份唯一 tilemap；
- 36 个 LZ77 指针均有效；
- graphics、palette、tilemap 解压大小分别满足 GBA tile、`0x180` 和
  `0x280` 约束；
- 4bpp tilemap 的 tile/palette bank/flip 全部在界；
- 8bpp tilemap 的最大 tile 精确落在各自 graphics 范围内，实际像素索引均小于
  192 色 palette。

ID 1 与 7 的 graphics、tilemap 和 indexed pixels 完全相同，仅 palette 不同，
是明确的 palette swap 复用。

## 验证与边界

```sh
python3 -m unittest tests.test_export_bg_resource_canvases -v
python3 tools/verify_bg_resource_canvases.py \
  --root . \
  --artifact-dir artifacts/bg-resource-canvases-v1
```

独立 verifier 不导入 exporter 或其他 `tools` 模块；它重新读取 ROM、独立解压
LZ77、解释 4bpp/8bpp tilemap、重建 consumer 填充、核对 indexed pixels、RGB
palette、压缩/解压二进制、manifest 和精确文件集合。

本里程碑闭合静态 BG 表、原始资源和 loader 可见画布，但不声称已闭合所有运行时
scene 名称、滚动偏移或与其他 BG/OBJ 层的最终合成。
