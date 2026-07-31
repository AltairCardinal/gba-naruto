# 通用 Sprite bundle 可变长迁移

日期：2026-07-31

## 结论

`0x0853F140` 的 43 个固定 Sprite ID 已从只读导出推进为统一扩展 ROM
迁移。源分母为 43 个 definition、43 个 animation table、43 个 component
list、43 个 animation-0 sequence，以及各一份 graphics/palette，共有 174
条精确源指针引用；全 ROM 四字节对齐扫描未发现未知外部引用。

迁移器将共享 4bpp graphics、16 色 palette 和 43 个 entry bundle 写入
`generic-sprite-bundle` 区域 `0xB90000..0xBA0000`，重写 88 个原 ROM
指针字段及 43 个 tile-base 值。entry bundle 内部同时重建 component-list、
definition、固定 animation-0 sequence 和 animation table 的 86 条内部指针。

完整保持迁移形成：

- 45 个 allocation；
- 88 个外部 pointer patch；
- 43 个 tile-base patch；
- 合计 176 个安全门禁写入。

## 可编辑边界

- ID 集合固定为 `0..42`，不能新增或删除；
- graphics 为 `1..97` 个完整 4bpp tile；
- palette 固定为 16 色/32 bytes；
- 每个 ID 可有 `1..2` 个合法 GBA OBJ component；2是源资源已证明的最大值，
  更高数量需要另行证明运行时OAM容量；
- component 可修改 tile offset、两个 flag、坐标、12 种硬件尺寸、两个变换量和
  保留字段；
- animation 0 固定为 frame 0、hold 1 tick、随后 `-1` 停止。

97-tile 上限不是任意预算。对 `0x08080A48` 的 12 个自然调用点复核表明，
graphics 会被加载到 OBJ tile base `0x34E` 或 `0x39F`；最高基址 927，
因此 GBA OBJ 的 1024-tile 地址空间只剩 `1024-927=97` tile。98 tile
会越过 OBJ VRAM，迁移器在生成任何 patch 前拒绝。

## 证据

- 实现：`tools/import_generic_sprite_bundle_relocations.py`
- 审计导出：`tools/export_generic_sprite_bundle_relocation_audit.py`
- 独立验证：`tools/verify_generic_sprite_bundle_relocation_audit.py`
- 产物：`artifacts/generic-sprite-bundle-relocation-v1/`

独立 verifier 不导入迁移器或审计导出器；它从 ROM 和两个源 catalog 重建
43/45/174 分母、确定性 LZ77、全部 bundle 内外指针及 16 MiB 输出，并拒绝
重签后的分母、spec 和文件集合篡改。

## 未证明边界

本成果不证明新增 Sprite ID、新增 animation/frame、场景专用资源覆盖、43 个
ID 的全部自然选择，以及修改后的最终屏幕合成像素/时序等价。运行时验证需要时
必须通过资源守卫并复用已验证快照；本里程碑本身只做离线重建，未启动 mGBA。
