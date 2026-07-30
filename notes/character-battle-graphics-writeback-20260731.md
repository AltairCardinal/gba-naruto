# 角色战斗 Graphics 固定长度安全回编（2026-07-31）

## 结论

角色战斗视觉矩阵的250套 raw 4bpp graphics 已从无损导出推进到固定长度安全回编。
每套 graphics 都是独立 ROM byte slice，不使用 LZ77：

- 250个资源对应250个唯一物理指针和250份唯一内容；
- 总计60,430个32-byte tile，即1,933,760 bytes；
- 单资源长度1,600–26,624 bytes，共21种长度；
- 250个 graphics 区间彼此不重叠，也不与 palette、component region、
  frame pointer table、timeline 或 animation pointer table 交叉；
- 342个逻辑 slot 对应250个资源，资源32–36分别被15/24/24/18/16个 slot 共享。

新 `character_battle_graphics` 构建类型只覆盖目标 graphics 区间。同一资源的全部
逻辑 slot 会在报告中原子披露；descriptor、component、frame、timeline 和
animation pointer table 均保持不变。

## Tile 边界证明

完整分母包含2,004帧、2,190个 component。每个 component 使用
`tile_offset = tile_index_raw & 0x03FF`，`tile_end` 由宽高换算。

对250/250资源逐项成立：

```text
max(component.tile_end) == graphics.tile_count
graphics.size == graphics.tile_count * 32
graphics_pointer + graphics.size == first_frame_pointer
```

因此，只要 replacement 长度严格不变，所有既有 component 的 tile 引用继续落在
同一个 graphics 区间内。任意同长度 raw 4bpp 字节都可以改写像素，但不能新增
tile、改变 component 或扩展资源。

## 完整分母

`artifacts/character-battle-graphics-writeback-v1/` 的独立审计结果：

| 口径 | 数量 |
|---|---:|
| 物理 graphics | 250 |
| 唯一 graphics 内容 | 250 |
| descriptor 资源 | 250 |
| 逻辑 slot 引用 | 342 |
| 帧 | 2,004 |
| component | 2,190 |
| 4bpp tile | 60,430 |
| graphics 总字节 | 1,933,760 |
| 原样固定长度往返 | 250/250 |
| 首字节低位修改写回 | 250/250 |

首字节低位修改只用于证明每个槽都有真实修改路径。同长度写回不涉及压缩，因此没有
“新编码超过旧槽”的容量风险。

## 构建规格

构建清单：

```json
{
  "id": "character-battle-graphics-import",
  "type": "character_battle_graphics",
  "spec": "sequel/content/character-battle-graphics/graphics-edits.json"
}
```

规格使用 `character-battle-graphics-import-v1`：

```json
{
  "schema": "character-battle-graphics-import-v1",
  "source_catalog": "artifacts/character-battle-visuals-v1/manifest.json",
  "edits": [
    {
      "id": "resource-0-new-pixels",
      "graphics_pointer": "0x0813E090",
      "graphics_sha256": "00604b6d454b23f73413ec7d65cebead033c7a6177f3e8da9861fb32f44db3ec",
      "source_file": "sequel/content/character-battle-graphics/resource-000.bin",
      "expected": {
        "file_offset": 1302672,
        "size": 18432,
        "tile_count": 576,
        "maximum_component_tile_end": 576,
        "resource_id": 0,
        "slot_rows": [0]
      }
    }
  ]
}
```

`expected` 必须从 catalog/审计复制。replacement 必须非空、长度与原 graphics
完全相同并按32 bytes对齐；错误指针、SHA、resource ID、slot rows 或 component
边界均失败关闭。

## 边界

本成果只签发固定长度 raw 4bpp 像素写回，不证明：

- 可增加 tile 或改变 graphics 长度；
- frame/component/animation/keyframe 结构已可编辑；
- 资源迁移、descriptor 指针改写或扩 ROM；
- 运行时 slot 选择、屏幕坐标、相机、priority、affine、blend 或 palette
  transform；
- 修改后在全部战斗场景中的最终屏幕像素等价；
- 全 ROM 通用图像回编完成。

## 验证

- TDD 红灯：no-op 测试因
  `tools.import_character_battle_graphics` 不存在而失败。
- 8项测试覆盖完整分母、250资源 no-op、逻辑 slot 别名、错误长度、陈旧
  provenance、重复/未知目标、基准 ROM、统一构建和独立 verifier。
- 独立 verifier 不导入 importer/exporter，从 ROM、558项 descriptor、catalog
  与全部结构 span 重建250个 graphics 和2,190个 component，并拒绝重签语义篡改。
- verifier 返回
  `250 graphics / 250 resources / 342 slots / 2190 components / errors=[]`。
- 本里程碑只做离线静态处理，没有启动 mGBA，也没有写入 Butano 工作树。
