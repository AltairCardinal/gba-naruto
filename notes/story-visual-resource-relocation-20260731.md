# 剧情透明 BG3 图层可变长迁移（2026-07-31）

## 结论

`0x0854229C` 的24条剧情透明 BG3 descriptor 已从静态 PNG 导出推进到可变长
资源迁移和统一构建闭环：

- 24 graphics、24 tilemap和24个物理palette流共72个LZ77载荷；
- 按`(类型, 解压SHA-256)`去重后为49份内容：24 graphics、1 palette、
  24 tilemap；
- 72个源指针在全 ROM 四字节对齐扫描中各只有descriptor内一条精确引用，
  未知额外引用为0；
- 49份原始二进制由批量脚本固化在
  `artifacts/story-visual-resource-sources-v1/`；
- 全量原样迁移生成49个分配补丁和72个指针补丁，合计121项。

专属区域为`0xB50000..0xB71000`。原样重编码存储56,551 bytes，包含四字节
对齐后的占用末端为`0xB5DD2D`，剩余78,547 bytes。后续图像区域从
`0xB71000`开始，迁移器不得越界借用。

## 可编辑契约

每层继续服从 consumer `0x08087C9C` 已证明的 BG3 ABI：

- graphics：4bpp完整tile，1–192个；最大6144 bytes；
- palette：固定16色/32 bytes；
- tilemap：固定32×32 u16，即2048 bytes；
- palette bank：全部entry固定为15；
- tile ID：必须恰好覆盖从`0x140`开始的连续graphics tile集合；
- 共享palette可按catalog内的`target_pointer_offsets`拆分；
- 49份编辑的总LZ77结果必须落入专属区域，容量不足时原子失败。

允许graphics tile数变化时必须同步提交同层tilemap。单层最大192 tile的正例已
进入测试；24层同时最大化会超过当前区域，容量门会拒绝，不会侵占后续图像或
`0xC00000..0xFFFFFF`音频/文字/配置分区。

## 与 tile-assets 的联合关系

descriptor `+0x0C` 的`config_id`仍按零基索引`0x085A320C`的79项
tile-assets表。本迁移只改`+0/+4/+8`三条LZ77指针，不重复迁移或复制
tile-assets descriptor。

联合集成测试把完整tile-assets迁移和本迁移放入同一个
`PatchSafetyGate`：共1,153个补丁全部应用，分配区域只出现
`tile-assets`和`story-visual-layers`，24个`config_id`仍落在0–78并索引已经
重写资源指针的原descriptor行。

## 证据和边界

- 源文件导出器：`tools/export_story_visual_resource_sources.py`
- 迁移器：`tools/import_story_visual_resource_relocations.py`
- 审计导出器：`tools/export_story_visual_resource_relocation_audit.py`
- 独立重建验证器：
  `tools/verify_story_visual_resource_relocation_audit.py`
- 审计：`artifacts/story-visual-resource-relocation-v1/`
- 定向测试：
  `tests/test_export_story_visual_resource_sources.py`、
  `tests/test_import_story_visual_resource_relocations.py`、
  `tests/test_story_visual_resource_relocation_audit.py`

独立验证器不调用迁移器或审计导出器；它重新解析24条ROM descriptor、解压72个
源载荷、重做全ROM精确引用扫描、验证49份源文件、重建16 MiB输出并比较资源账本、
摘要和输出哈希。

本闭环证明静态资源的编辑、变长重编码、分配和指针改写，不证明修改后剧情路线的
滚动、window/blend时序或最终屏幕像素等价，也不改变`butano-sequel/`。
