# 世界地图背景资源可变长迁移（2026-07-31）

## 结论

`0x085A8014` 的三条世界地图背景记录已从只读导出推进到可变长迁移。严格分母是：

- 3 个 graphics、3 个物理 tilemap、3 个 palette，共 9 个物理载荷；
- 三个 tilemap 解压内容相同，按“资源类型 + 解压 SHA-256”去重后为 7 份内容；
- 9 个 descriptor 指针字段；全 ROM 四字节对齐精确扫描没有额外引用。

新构建类型 `world_map_background_relocation` 把选中的内容写入图像资源注册表中的
`world-map-backgrounds` 区域，并原子重写对应 descriptor 指针。相同 tilemap 的
三个物理别名可以保持联动，也可以通过 `target_pointer_offsets` 选择子集后分裂。

## 格式与容量门

loader 把 graphics 解压到 `0x06004000`，而已验证的世界地图合成会同时启用从
`0x0600C000` 开始的 BG3 文字层。因此 BG0 graphics 只能占用两者之间的 32 KiB，
即最多 512 个 8bpp tile；513–768 tiles 虽未越过 BG VRAM 总上界，却会覆盖 BG3。
每页 graphics 因此支持 1–512 个完整 tile，所有像素索引必须小于 160。tilemap
固定为 30×20 个 u16 entry（1,200 bytes），palette 固定为160色 BGR555
（320 bytes）。迁移计划生成前会联合检查：

- graphics 为 64-byte tile 的整数倍，且不越过 512-tile BG0/BG3 边界；
- tilemap 的 tile ID 均小于该页 graphics tile 数，8bpp palette-bank 位为零；
- palette 恰好 320 bytes；
- catalog、基准 ROM、原内容、9 个旧指针和完整别名集合均未漂移；
- 每个指针只被一个 edit 认领，所有新分配均落在注册区域。

独立审查发现早期实现错误地按 BG VRAM 总上界允许 768 tiles；新增红测证明
513-tile 输入此前会被接受，随后把上限收紧到 512。注册区域保持
`0xB71000..0xB90000`（126,976 bytes），足以容纳三页512-tile最坏编码；
未来图像区域从 `0xB90000` 开始。

## 原样迁移结果

全量 preservation 规格生成 7 个新分配和 9 个指针补丁：

- 存储载荷合计 90,082 bytes；
- 占用跨度 90,084 bytes；
- 末端 `0xB86FE4`；
- 区域剩余 36,892 bytes。

独立 verifier 不导入迁移器或审计导出器；它重新读取当前基准 ROM、当前静态
catalog、9 个真实指针、7 份源内容和当前区域注册表，自行实现确定性 GBA LZ77
编码并重建完整 16 MiB 输出。重签后篡改分母、authoring spec、文件集合、区域或
实现哈希都会被拒绝。

## 成果与边界

- 迁移器：`tools/import_world_map_background_relocations.py`
- 审计导出器：`tools/export_world_map_background_relocation_audit.py`
- 独立 verifier：`tools/verify_world_map_background_relocation_audit.py`
- 产物：`artifacts/world-map-background-relocation-v1/`
- 测试：`tests/test_import_world_map_background_relocations.py`、
  `tests/test_world_map_background_relocation_audit.py`

本里程碑允许修改三页背景的 tile 图形、tilemap 和 palette，并生成扩展 ROM。
它不修改三条地点标签、解锁规则或选择光标，也不证明修改后 page 1/2 的自然选择、
转场时序和最终合成像素等价。运行时复验应从已有世界地图快照继续，不重新导航主线。
