# 残余 WRAM tilemap 批量迁移（2026-07-31）

## 结论

ABI 已证明的三条 WRAM→status-3 GPU queue tilemap 现已作为一个批量域获得受保护的
可变存储迁移能力：

| 原 ROM 源 | 唯一根 offset | 几何 | palette bank | 新 offset |
|---|---:|---:|---:|---:|
| `0x0834928C` | `0x08AEE0` | 15×20 | 1 | `0xBC0C00` |
| `0x083F1C98` | `0x08BD38` | 24×12 | 8 | `0xBC0CDC` |
| `0x085B67E0` | `0x08BD48` | 23×3 | 9 | `0xBC0EA4` |

三条共 657 个 u16 entry、1,314 bytes。保持原内容时，821 bytes LZ77 数据连同
4-byte 对齐占用 `0x33A` bytes，末端 `0xBC0F3A`。注册表把
`0xBC0C00..0xBC1400` 切成独占的 `residual-wram-tilemaps` 区域，仍余
1,222 bytes；即使三个 payload 都退化为全 literal LZ77，含逐项对齐的最坏占用
也只有 1,492 bytes，不会越界。

## 编辑与失败边界

`tools/import_residual_wram_tilemap_relocations.py` 一次处理三条资源，生成三项分配和
三个精确根重定向。每条允许修改全部 screen entry、标准 H/V flip，并保持：

- 固定的 15×20、24×12、23×3 几何与 decoded 长度；
- 固定 palette bank 1、8、9；
- 各自已观察的 tile 范围 6–67、0–267、0–86；
- 固定的 WRAM 解压及逐行 VRAM 目标 ABI。

资源缺项、重复 source、ABI/ROM/registry 哈希漂移、尺寸或 palette 错误、tile 越界、
区域溢出及非 FF 目标都会在写 ROM 前失败。全 ROM 精确值扫描证明每个 source
只有上述一个对齐 literal 根，也没有指向压缩 span 内部的别名；这不把尚未完成的
全 ROM computed-pointer 符号执行冒充为已证明。

## TDD、成果与验证

红阶段的六项 importer 测试先因批量模块不存在而失败；实现后覆盖：

- 三条 source、三条唯一根和 queue ABI 的精确 catalog；
- 注册区域无缝切分；
- 16 MiB preservation build 的六项安全 patch；
- 三条同时编辑及尺寸/tile/palette 负例；
- literal 最坏容量和强制溢出；
- `automated_test.py` 与统一 `build_mod.py` 集成。

独立审计又先以“正式 artifact 不存在”为红测试，随后生成
`artifacts/residual-wram-tilemap-relocation-v1/`。verifier 不导入生产 importer
或 exporter，自行实现 LZ77、重建 ROM 根集合、全局 RomLayout/区域注册表、三项
分配、三项指针 patch、16 MiB 输出和三项同时 H-flip 的 capability fixture，并拒绝
重新签名后的 payload、spec、tilemap、区域和实现哈希篡改。

正式新成果导出和验证均经统一 heavy lock，峰值 tree RSS 分别为
58.75 MiB 与 0.921875 MiB，无降级。注册表哈希变化后，又批量重建并验证
12 个既有图像迁移 artifact；导出最大峰值 85.25390625 MiB，验证最大峰值
56.66796875 MiB，全部退出码 0。旧注册表哈希在 artifact JSON 中剩余 0 项。
提交前依赖审计又重建并验证了固定 `build_mod.py` 或 `automated_test.py` 的角色
bundle、角色palette/graphics/structure、BG、菜单立绘、地图及战斗特效原位回编
8个成果；峰值分别为100.76953125 MiB与53.875 MiB，全部退出码0。最终递归检查
artifact JSON中的197项实现文件哈希，当前不一致为0。

本轮完全离线，没有运行 mGBA，因此没有新增快照；Butano 工作树未被访问或修改。

## 未闭合边界

- 四条 `0x083F2108`、`0x084634B8`、`0x0846356C`、`0x084635D8` 的 ABI；
- computed-pointer 隐藏 consumer 的全 ROM 证明；
- status-3 queue 槽成功、自然 flush 和运行时可达性；
- BG/graphics/palette 所有权、业务名称；
- 修改后最终屏幕像素和跨帧时序等价。

下一图像主线继续追踪剩余四条 WRAM payload 的直接消费者；只有代码闭合 ABI 后
才允许扩充本批量迁移 schema。
