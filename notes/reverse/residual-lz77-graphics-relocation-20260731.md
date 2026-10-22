# 残余指针可达 LZ77 图形迁移

日期：2026-07-31

## 结论

严格 type-`0x10`、四字节对齐且有 ROM 指针消费者的 896 条 LZ77 记录中，十个
既有图像迁移域之外还剩 31 条。按静态 loader 目标和 payload 结构重新分类后：

- 20 条是完整 4bpp 图形，共 36,640 字节解压数据和 34 个精确根指针；
- 3 条是 LZ77 palette；
- 7 条是送入 WRAM 的 visual metadata；
- 1 条是 32×20 text-BG tilemap。

本里程碑只闭合 20 条真实图形，不把 palette、metadata 或 tilemap 错当成 4bpp
图块。二十条图形已经全部迁入 `residual-lz77-graphics`
`0xBB0000..0xBC0000`，形成 20 个 allocation 和 34 个根指针 patch，共 54 项
安全写入。完整 preservation 输出为 16 MiB，SHA-256：
`c7951f1878a1e8f660571fb81533d56cd7c8202daa265fccfe0cded46721cf35`。

## 可编辑边界

- 每项输入必须保持原解压长度，并由完整的 32-byte 4bpp tile 组成；
- 可以替换该项全部 tile 内容，重新编码后的 LZ77 可使用整个 64 KiB 专区，不再受
  原压缩槽长度限制；
- 目标 VRAM、动态 OBJ slot 和全部 consumer 保持原样；同一物理 payload 的多个
  根指针必须一起重定向；
- 20 项当前原压缩总量为 16,574 bytes，新编码存储 16,501 bytes，占用跨度
  16,530 bytes，末端 `0xBB4092`，区域剩余 49,006 bytes；
- 全 literal 最坏编码上界仍小于 64 KiB，区域溢出会在返回任何 patch 前失败。

`0x0812D2F0` 与 `0x083496F8` 仍只有合成索引预览，没有 OAM attr2 证明真实
palette bank。迁移器和 verifier 固定要求 `unresolved_palette_count == 2`，
不得用邻近 palette 或同帧 PRAM 驻留把它们伪装为已闭合颜色资源。

## 独立审计

- 导入器：`tools/import_residual_lz77_graphics_relocations.py`
- 审计导出：`tools/export_residual_lz77_graphics_relocation_audit.py`
- 独立验证：`tools/verify_residual_lz77_graphics_relocation_audit.py`
- 正式产物：`artifacts/residual-lz77-graphics-relocation-v1/`

独立 verifier 不导入生产导入器或审计导出器。它从基准 ROM、原 inventory 和
graphics catalog 重新：

1. 解码 20 条 LZ77 并验证 36,640-byte 分母；
2. 全 ROM 四字节扫描并验证 34 个根指针，未知引用为 0；
3. 独立编码 LZ77、分配 20 个 payload、改写 34 个 before-word；
4. 重建完整 16 MiB ROM；
5. 对 20 个资源分别修改首个 tile，再独立重建 capability fixture。

capability fixture 输出 SHA-256：
`9967bf4bccce8ac70f1c8e6599d36aba961eb9cec16e336847d7b55b35c0297b`。
测试还覆盖缺失、重复和未知资源、长度变化、区域溢出，以及重新签名后的
denominator、spec、raw payload、额外文件和全局区域重叠篡改。独立 verifier
自行验证 ROM layout、父分区及全部图像区域的唯一性、对齐、连续覆盖和无重叠，
不只核对 residual 自身的区域行。

正式导出经 `tools/run_guarded.py` 使用统一 heavy lock，峰值 owned-tree RSS
60.551 MiB，无超时、降级或残留进程。本里程碑没有运行 mGBA，因此不需要新快照。

## 未证明边界

本成果不证明改变解压 tile 数、改变 VRAM 目的地、编辑 palette、七条 metadata
ABI、text-BG tilemap 语义、自然语言业务名称，以及修改后最终屏幕合成像素和时序
等价。图像“压缩 payload 可编辑迁移”分母到此闭合，但颜色、组合和运行时视觉
等价仍需分别继续。
