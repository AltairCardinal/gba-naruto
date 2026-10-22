# 角色战斗视觉结构同布局回编（2026-07-31）

## 结论

角色战斗视觉的 component 与 animation keyframe 已从只读解析推进到高层语义回编。
新 `character_battle_structure` 构建类型允许在不改变任何结构数量、指针或区域
长度的前提下编辑：

- component 的 graphics tile、水平/垂直翻转、局部 x/y 和已验证 OBJ 尺寸；
- keyframe 的 frame 引用和 hold 帧数。

构建器从基准 ROM 和 catalog 重建250个资源、2,004帧、2,190个 component、
784条 animation、3,187个 keyframe 和342个逻辑 slot。每项修改只生成一个
20-byte component 或4-byte keyframe 补丁；frame/animation pointer table、
terminator、graphics、palette 和 descriptor 均不改动。

## Component 编码

每个 component 固定20 bytes：

```text
u16 tile_index_raw
u8  orientation
u8  affine_angle_offset
s16 x
s16 y
u16 width
u16 height
u16 scale_x
u16 scale_y
u8  control
u8  attribute
u16 reserved
```

签发的编辑字段：

- `tile_offset`：只使用 `tile_index_raw` 的低10位；现有2,190项高6位均为0；
- `horizontal_flip` / `vertical_flip`：编码为 orientation bits 0/1；
- `x` / `y`：任意可编码 s16；
- `width` / `height`：仅限 exporter 已验证的12种 OBJ 形状；
- `tile_offset + width/8 × height/8 <= resource.tile_count`。

未签发字段必须保持
`angle=0, scale=0x100/0x100, control=0xFF, attribute=0, reserved=0`。

## Keyframe 编码

每条 animation 保持原 keyframe 数：

```text
<u16 frame_id, u16 hold_frames> × 原数量
<0xFFFF, 0> terminator
```

`frame_id` 必须小于本资源 frame 数，`hold_frames` 必须是非零 u16。不能新增或
删除 keyframe，也不能移动 timeline 或改 terminator。

## 完整分母

`artifacts/character-battle-structure-writeback-v1/` 的独立审计：

| 口径 | 数量 |
|---|---:|
| 资源 | 250 |
| 逻辑 slot 引用 | 342 |
| 帧 | 2,004 |
| component | 2,190 |
| animation | 784 |
| keyframe | 3,187 |
| component 原样语义重编码 | 2,190/2,190 |
| component 翻转真实变异 | 2,190/2,190 |
| keyframe 原样语义重编码 | 3,187/3,187 |
| keyframe hold 真实变异 | 3,187/3,187 |
| 已知异常 trailer | 1/1 |

共享资源32–36分别影响15/24/24/18/16个 slot。每个补丁报告完整
`affected_slot_rows` 和逻辑别名，不能把共享资源误当成单个角色专属结构。

## 异常 Trailer

2,003帧使用 `ffff0000` trailer；唯一
`0x0825A8E4` 为已由运行时证据解释的 `fffb0000`。importer 逐帧验证并原样保留
trailer，不把该字节规范化，也不允许补丁覆盖 terminator。

## 构建规格

```json
{
  "id": "character-battle-structure-import",
  "type": "character_battle_structure",
  "spec": "sequel/content/character-battle-structures/structure-edits.json"
}
```

规格使用 `character-battle-structure-import-v1`：

```json
{
  "schema": "character-battle-structure-import-v1",
  "source_catalog": "artifacts/character-battle-visuals-v1/manifest.json",
  "edits": [
    {
      "id": "resource-0-motion",
      "resource_id": 0,
      "expected": {
        "component_region_sha256": "4d1a3e45c840830f990706750f3fffa293cb6757d78a896ee06680b480558304",
        "timeline_region_sha256": "34514358ddecc359f595d14de8acf0062103d07719f6844ea0445b61e273e99f",
        "frame_count": 20,
        "component_count": 20,
        "animation_count": 12,
        "keyframe_count": 44,
        "tile_count": 576,
        "slot_rows": [0]
      },
      "component_edits": [
        {
          "frame_id": 0,
          "component_index": 0,
          "tile_offset": 1,
          "horizontal_flip": true,
          "x": -15
        }
      ],
      "keyframe_edits": [
        {
          "animation_id": 0,
          "keyframe_index": 0,
          "frame_id": 1,
          "hold_frames": 9
        }
      ]
    }
  ]
}
```

未列出的可编辑字段继承原值。`expected` 必须来自 catalog/审计；重复目标、陈旧
region SHA、错误数量、越界 tile/frame、零 hold 或未知字段都会使整个构建失败。

## 边界

本成果完成现有槽位的同布局语义编辑，但不证明：

- 可新增/删除 component、frame、animation 或 keyframe；
- 可改变 pointer table、region 长度、terminator 或资源地址；
- 可扩展 graphics tile 数；
- 运行时 slot 选择、相机、screen position、priority、affine、blend 或 palette
  transform 已闭合；
- 修改后在全部战斗入口的最终像素和时序等价；
- 全 ROM 通用角色编辑器已完成。

## 验证

- TDD 红灯：完整分母测试因
  `tools.import_character_battle_structures` 不存在而失败。
- 11项测试覆盖分母、component/keyframe 成功编辑、12种OBJ形状与边界、共享
  alias、所有主要非法域、
  重复目标、陈旧 provenance、基准 ROM、统一构建和独立 verifier。
- 独立 verifier 不导入 importer/exporter，从 ROM、pointer table、frame/
  timeline region 与 catalog 重建全部记录，并拒绝重签语义篡改。
- verifier 返回
  `250 resources / 342 slots / 2190 components / 3187 keyframes / errors=[]`。
- 本里程碑只做离线静态处理，没有启动 mGBA，也没有写入 Butano 工作树。
