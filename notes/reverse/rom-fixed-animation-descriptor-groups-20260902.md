# 固定动画描述器组（2026-09-02）

## 结论

`rom-fixed-animation-descriptor-groups-v1` 精确分类 ROM
`[0x12D574,0x12D9E4)` 的 1,136 bytes：12 个 `0x54` 描述器、12 槽描述器指针表、
4 组各 3 项加 sentinel 的序列，以及 4 槽组指针表。

## 可复验证据

- caller `0x071EA8..0x071EBE` 穷尽产生 group `0..3`；`0x071EC0/0x071EC2` 装入两张表。
- allocator `0x0626B4` 把 group、slot、descriptor/group bases 写入对象，并把 slot 置 0。
- renderer 只在 next group entry 不是 `0xFFFF` 时增加 slot，故每组访问恰好 3 records。
- renderer `0x0631F6..0x063208` 以 `0x14` 前进并在 next head 为 `-1` 时停止；12 个描述器
  都是 4 entries + `0x0000FFFF` terminator，恰为 `0x54`。
- artifact：`artifacts/rom-fixed-animation-descriptor-groups-v1/`；独立 verifier：
  `tools/verify_rom_fixed_animation_descriptor_groups.py`；TDD：
  `tests/test_export_rom_fixed_animation_descriptor_groups.py`。
- manifest/payload/verifier SHA-256：`83e526c51214bc0e42f31f8906b7633e4b94a0762a630c643f0134fad974ff05` /
  `8afa72be44e60892c85a16c037052ea6a02dd078b0864227ebef436ba3ae5e3b` /
  `9555d5bf37c1b19fdb1b5e8dada5fad5aaa32eabbcaa9c803e96b6037896e529`。

## 边界

只声明固定 consumer 合同覆盖的物理描述器字节；不声明自然运行时覆盖全部组、其他 caller
均使用同一输入、renderer opaque 副作用、字段业务名、编辑/写回/重定位安全或 free space。
canonical coverage 尚未改写；本包必须排在 boot-state dispatcher queued claims 后做
current-unknown projection。
