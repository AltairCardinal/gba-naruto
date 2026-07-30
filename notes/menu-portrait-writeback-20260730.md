# 菜单/剧情立绘安全原位回编（2026-07-30）

## 结论

`artifacts/menu-portraits-v1/` 中311个逻辑菜单/剧情立绘对应的74套唯一
`(gfx, palette)` 资源，现在具备可进入统一 ROM 构建的安全原位回编链：

- 输入为80×80、模式 `P`、透明索引0、最多64色的 PNG；
- 画布按已证明的六段硬件 OBJ 矩形逆变换为6400-byte 1D OBJ流；
- 图形使用确定性的 BIOS type-`0x10` GBA LZ77 编码；
- 编码后不超过原压缩槽才允许写回，尾部保留原槽字节以维持 ROM 长度；
- 调色板固定写回128-byte、64色 BGR555；
- PNG 不承载的 BGR555 未使用 bit15 逐色继承原 ROM，74/74导出 PNG
  无修改再导入均产生零补丁；
- 每项编辑绑定 `resource_id`、gfx/palette 指针及原字节 SHA-256；
- 修改共享资源时，构建报告列出全部受影响的逻辑立绘别名；
- `build_mod.py` 的统一 immutable-base 与重叠冲突门禁继续生效。

这使74套已知立绘资源具备真实的“导出 PNG → 修改 → 构建 ROM”能力，不再只是
可视化导出。

## 容量分母

正式审计 `artifacts/menu-portrait-writeback-v1/` 从基准 ROM 重读全部74套资源：

| 项目 | 结果 |
|---|---:|
| 唯一资源 | 74 |
| 逻辑立绘别名 | 311 |
| 原图确定性重编码可装回原槽 | 74/74 |
| 解压流 offset 0 单像素索引修改可装回原槽 | 74/74 |
| 128-byte 调色板固定长度写回 | 74/74 |
| 原图重编码最小余量 | 4 bytes |
| 单像素修改最小余量 | 4 bytes |

单像素修改是固定、可复现的容量见证：把解压流第0字节改为
`(before + 1) mod 64`，重新压缩、补齐原槽并再次解压验证。它证明所有74套资源
至少存在真实像素修改的安全原位路径，但不证明任意复杂 PNG 都能压入原槽。

## 作者规格

构建清单：

```json
{
  "id": "portrait_import",
  "type": "menu_portrait",
  "spec": "sequel/content/menu-portraits/portrait-edits.json"
}
```

规格示例：

```json
{
  "schema": "menu-portrait-import-v1",
  "source_catalog": "artifacts/menu-portraits-v1/manifest.json",
  "edits": [
    {
      "id": "new-expression",
      "resource_id": 0,
      "png": "sequel/content/menu-portraits/new-expression.png",
      "expected": {
        "gfx_pointer": "0x08408BD8",
        "palette_pointer": "0x084098C4",
        "compressed_sha256": "28d82e56b5c72c3d6eed4d59a224ebdbae3722310cefb0bc14f1d1e385bf48f1",
        "palette_sha256": "cb61b78fb80795ed2f2fc59ed7ceb8f2fd70bde7af7827c0b1a8b9232a01d48c"
      }
    }
  ]
}
```

指针和哈希必须从当前 accepted catalog 复制，不能手工猜测。一个 `resource_id`
只能在同一规格中编辑一次，避免两个 PNG 对同一共享槽产生顺序依赖。

## 独立验证

```bash
python3 tools/export_menu_portrait_writeback_audit.py \
  --root . --output artifacts/menu-portrait-writeback-v1

python3 tools/verify_menu_portrait_writeback_audit.py \
  --root . --artifact artifacts/menu-portrait-writeback-v1

python3 -m unittest tests.test_import_menu_portraits -v
```

独立 verifier 不导入 importer、exporter 或仓库 LZ77 helper；它自行实现严格
type-`0x10` 解码和同一确定性编码，从 ROM/catalog 重建74条容量记录、实现哈希、
summary、scope 和 promotion manifest。修改容量数字后即使重新签 payload 哈希，
仍会得到 `resource records mismatch`。

## 明确边界

本成果没有证明：

- 任意 PNG 都能压入对应原槽；
- 超槽资源的空闲区分配、迁移或指针改写；
- 新立绘在所有菜单、剧情和调色变换路径上的运行时像素等价；
- 其他图像类别可以复用该布局或回编器；
- 全 ROM 的通用图像回编已经完成。

超槽输入会在生成补丁前失败，不产生部分 ROM。后续若确实需要更复杂的新立绘，
应单独建立带占用图、对齐、容量、指针引用全集和运行时验证的资源迁移器，不能放宽
本原位导入器的门禁。
