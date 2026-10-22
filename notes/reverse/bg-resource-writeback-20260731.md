# Regular BG 资源安全原位回编（2026-07-31）

## 结论

`0x0859903C` regular BG 表的12个有效 descriptor 已从只读画布导出推进到
受守卫原位回编。每项 descriptor 按 ROM 真实顺序保存
`graphics/palette/tilemap/mode_flag`；ID 1–7 为4bpp，ID 9–13 为8bpp。

新 `bg_resource` 构建类型以“资源类型 + 原始解压 SHA-256”标识资源：

- 12个场景的36条逻辑引用对应36个互不重叠的物理 LZ77 槽；
- 按类型和内容去重后形成31份编辑资源；
- 默认把同内容写回全部物理槽，也允许用 catalog 约束的
  `target_physical_offsets` 子集分别编辑；
- 真正的 descriptor 指针不改写，任一目标槽超限时整项原子失败；
- 写补丁前以修改后全视图重新验证 graphics、384-byte palette 与
  32×10 u16 tilemap 的索引关系。

## 完整分母与容量

`artifacts/bg-resource-writeback-v1/` 的独立容量审计结果：

| 口径 | 数量 |
|---|---:|
| 内容资源 | 31 |
| 物理 LZ77 槽 | 36 |
| 逻辑 descriptor 引用 | 36 |
| 原样确定性回编 | 31/31 内容、36/36 槽 |
| 固定低位变异可写回 | 20/31 内容、21/36 槽 |
| 固定低位变异溢出 | 11/31 内容、15/36 槽 |
| 原样最小容量余量 | 0 byte |
| 变异最小容量余量 | -3 bytes |

固定低位变异只是一种可复现容量见证，不代表任意编辑都能装入原槽。超限资源会
明确失败；当前不迁移资源、不扩 ROM、不改 descriptor 指针。

## 构建规格

构建清单：

```json
{
  "id": "bg-resource-import",
  "type": "bg_resource",
  "spec": "sequel/content/bg-resources/resource-edits.json"
}
```

规格使用 `bg-resource-import-v1`：

```json
{
  "schema": "bg-resource-import-v1",
  "source_catalog": "artifacts/bg-resource-canvases-v1/manifest.json",
  "edits": [
    {
      "id": "entry-2-graphics",
      "resource_type": "graphics",
      "resource_sha256": "37b3ac4f45cd4bd3ac06101b1612eef4ca7ccf5236109a80670c202a74f4fc25",
      "source_file": "sequel/content/bg-resources/entry-02-graphics.bin",
      "expected": {
        "decompressed_size": 3072,
        "physical_offsets": [3320324]
      }
    }
  ]
}
```

`expected` 必须来自 catalog/审计，不得手工猜测。graphics 输入必须保持原解压
长度并按对应 mode 组成完整32-byte 4bpp 或64-byte 8bpp tile；palette 必须恰好
384 bytes；tilemap 必须恰好640 bytes。

## 联动安全门禁

导入器在生成补丁前对12个场景重新组成修改后资源视图：

- tilemap 的低10位 tile index 必须落在 graphics tile 数量内；
- 4bpp palette bank 的完整16色范围必须落在192色 palette 内；
- 8bpp graphics 的所有像素索引必须小于192；
- catalog、表哈希、模式、指针、原始压缩/解压哈希和物理区间必须一致；
- 同一物理槽不能被两个编辑争用，目标子集必须排序、去重且属于 catalog；
- 所有目标槽都能容纳新 LZ77 后才返回任何补丁。

## 边界

本成果只签发三类原始二进制资源的受限原位回编，不证明：

- 256×160 canvas PNG 可无损逆编译；底部10行是 consumer 运行时填充；
- 任意修改都能放入旧 LZ77 槽；
- 资源迁移、扩容或 descriptor 指针改写；
- 所有运行时 entry 选择、scroll、图层组合、OBJ/window/blend 或最终像素等价；
- 全 ROM 通用背景/图像回编完成。

## 验证

- TDD 红灯：no-op 测试因 `tools.import_bg_resources` 不存在而失败。
- 10项测试覆盖 `31→36→36` 分母、全量 no-op、同内容默认联动与显式拆分、
  非规范目标、陈旧 provenance、格式、跨资源索引、原子溢出、统一构建和
  独立 verifier。
- 独立 verifier 不导入 importer/exporter，从 ROM、descriptor 表和 catalog
  自行重建 LZ77 编解码、31份资源和36个槽，并拒绝重签后的语义篡改。
- artifact verifier 返回
  `31 content / 36 physical / 36 logical / errors=[]`。
- 本里程碑只做离线静态处理，没有启动 mGBA，也没有写入 Butano 工作树。
