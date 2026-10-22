# 战斗地图资源安全原位回编（2026-07-30）

## 结论

`map-canvases-v1` 的47个地图 header共有249条非空资源引用，按 ROM 起点落到
217个物理 type-`0x10` LZ77 槽，按“资源类型 + 解压内容 SHA-256”去重后是166份
编辑资源：

| 类型 | 逻辑引用 | 物理槽 | 内容资源 |
|---|---:|---:|---:|
| tile graphics | 47 | 41 | 34 |
| BG palette | 47 | 41 | 15 |
| primary layout | 47 | 41 | 35 |
| alternate layout | 14 | 12 | 12 |
| metatile definitions | 47 | 41 | 35 |
| collision grid | 47 | 41 | 35 |
| 合计 | 249 | 217 | 166 |

`tools/import_map_resources.py` 现以内容资源为编辑身份。一项修改会先解析它的全部
map-header 逻辑别名和物理槽，验证基准 ROM、catalog、解压长度、内容 SHA、资源
结构与调用方声明的物理偏移，再以“全部替换内容 + 未修改 ROM 内容”的联合视图
检查每张受影响地图：layout 的两个 metatile 索引必须存在，每个 metatile 的 tile
索引和 palette bank 也必须落在对应资源范围内。随后才用共享的确定性 GBA LZ77
编码器重压缩。只有编码结果能装入每一个物理槽时才返回全部固定长度 `bytes`
补丁；任一索引越界或任一槽超限都会在生成补丁前拒绝整项修改。

`tools/build_mod.py` 已接入 `map_resource` 类型。构建报告为每个物理补丁保留资源
类型、原内容 SHA、新内容 SHA、编码长度、槽长度、受影响地图和完整逻辑别名。header
指针不会被修改。

## 容量审计

`artifacts/map-resource-writeback-v1/` 对完整 `166/217/249` 分母进行审计：

- 166/166份原始内容均能确定性重编码并装入其全部别名槽；
- 217/217个物理槽均通过原始内容往返；
- 对每份资源执行一个按类型固定的低位变异后，135/166份内容仍能装入全部别名槽；
- 31/166份内容至少有一个别名槽溢出，回编器必须拒绝；
- 物理槽口径为163/217可装入、54/217溢出。

这个变异只用于建立受限容量见证。它不证明任意地图编辑都能装入原槽，也不能把
135/166写成“地图资源编辑完成率”。

## 验证边界

独立 verifier 不导入 importer、artifact exporter或共享 LZ77 原语。它从基准 ROM
和47个 map header重新建立 `249 → 217 → 166` 映射，独立编解码每份资源并重算
原始/变异容量、实现文件哈希和 promotion manifest。测试覆盖重签后的 slot-size
语义篡改，不能仅靠更新 manifest 哈希绕过。审计 scope 同时绑定 importer 已具备
跨资源索引验证；回归测试分别覆盖 layout→metatile、metatile→tile 和
metatile→palette 越界拒绝。

明确未完成：

- 超槽资源迁移和 map-header 指针改写；
- 任意大小或任意内容编辑均可容纳；
- 把完整画布 PNG 自动反编译为 tiles/layout/metatile；
- alternate layout 的运行时选择、滚动/分块和动态占用层；
- 修改后在全部47张地图上的 mGBA或实体 GBA像素等价。

因此本成果提升的是地图资源的安全回编能力，而不是通用图像回编完成。
