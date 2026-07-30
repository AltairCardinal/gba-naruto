# 角色战斗视觉调色板安全原位回编（2026-07-31）

## 结论

角色战斗视觉矩阵的342个有效逻辑槽、250套去重 descriptor 资源最终引用48个
互不重叠的物理调色板槽。每槽都是未压缩的32-byte、16色 BGR555 数据，因此现在
具备不迁移资源、不修改指针的完整固定长度回编链：

- `character_battle_palette` 构建类型从
  `artifacts/character-battle-visuals-v1/manifest.json` 重建全部别名；
- 每项编辑用物理 palette 指针和原始 SHA-256 标识；
- 32-byte 输入会先核对基准 ROM、catalog、descriptor 表指针、全部
  resource ID 和逻辑 slot row；
- 真正共用同一 palette 指针的全部 resource/slot 自动联动；
- 内容相同但物理指针不同的8组重复内容保持独立，不按内容哈希误合并；
- 补丁仍经过统一 immutable-base 和重叠冲突门禁，失败时不会产生部分 ROM。

## 完整分母

`artifacts/character-battle-palette-writeback-v1/` 从基准 ROM 和
`62×9` descriptor 矩阵独立重建：

| 口径 | 数量 |
|---|---:|
| 物理 palette 槽 | 48 |
| 唯一 palette 内容 | 40 |
| descriptor 资源引用 | 250 |
| 有效逻辑 slot 引用 | 342 |
| 原始32-byte往返 | 48/48 |
| 固定低位修改可写回 | 48/48 |

调色板没有 LZ77 槽容量问题；任意合法32-byte BGR555 内容都能原位替换。审计中的
固定变异把首个非透明色的低位翻转，只用于证明所有48个物理槽都存在真实修改路径。

## 构建规格

构建清单：

```json
{
  "id": "character-battle-palette-import",
  "type": "character_battle_palette",
  "spec": "sequel/content/character-battle-palettes/palette-edits.json"
}
```

规格使用 `character-battle-palette-import-v1`。以下示例修改角色1全部九个视觉槽
共享的 palette；`expected` 数组必须从审计产物复制，不能手工猜测：

```json
{
  "schema": "character-battle-palette-import-v1",
  "source_catalog": "artifacts/character-battle-visuals-v1/manifest.json",
  "edits": [
    {
      "id": "character-1-new-colors",
      "palette_pointer": "0x0813E070",
      "palette_sha256": "5ed6559b7dbaee0832ff46c3961fd0e60ed89c6c9db5dd945d1135aa2dc52916",
      "source_file": "sequel/content/character-battle-palettes/character-1.bin",
      "expected": {
        "file_offset": 1302640,
        "resource_ids": [0, 1, 2, 3, 4, 5, 6, 7, 8],
        "slot_rows": [0, 1, 2, 3, 4, 5, 6, 7, 8]
      }
    }
  ]
}
```

## 边界

本成果只签发48个物理角色战斗 palette 的固定长度写回，不证明：

- 250套 raw 4bpp graphics 已可编辑；
- frame/component/animation/keyframe 等变长结构已可回编；
- 资源迁移或 descriptor 指针改写；
- palette transform、blend、相机、priority 或最终屏幕像素等价；
- 全 ROM 通用图像回编完成。

graphics 的250个物理区间虽已无损导出，但长度由现有 component 最大 tile 引用
推导；帧和时间线又包含指针表与终止符。它们必须另建结构联合验证后才能开放。

## 验证

- TDD 红灯：首个 no-op 测试因
  `tools.import_character_battle_palettes` 不存在而失败。
- 定向测试覆盖完整 `48→250→342` 分母、共享指针联动、同内容不同指针隔离、
  错误长度、陈旧 provenance、重复编辑、未知指针、统一构建及独立 verifier。
- 独立 verifier 不导入 importer/exporter；它从 ROM、558项 descriptor 和
  250项资源重新建立48个物理槽，并拒绝即使重新签哈希的语义篡改。
- 新增7项测试全部通过；角色视觉导出、角色 palette 与既有立绘/地图/战斗特效
  回编联合回归在资源守卫下 `completed/0`，峰值 tree RSS `80.94921875 MiB`。
- `tools/automated_test.py` 为25/25，独立 verifier 返回
  `48 palettes / 250 resources / 342 slots / errors=[]`。
- 本里程碑只做离线静态处理，没有启动 mGBA，也没有写入 Butano 工作树。
