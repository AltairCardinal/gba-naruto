# Bounded-index u16-pair table

## 结论

`rom-bounded-index-u16-pair-table-v1` 只分类基准 ROM 的
`[0x53F2EE,0x53F30E)`：8 条、每条 4 字节的 two-u16 lookup，共 32 字节。
ROM 身份为 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`，
候选字节 SHA-256 为
`a123b14474752d4827e3e9b0e93d58b85ccc69fac06d6eae63470b7b77004246`。

consumer `[0x08080AA8,0x08080B08)` 的固定合同为：

- `0x08080AAC` 从 `unit+0x30` 读取 index；
- `0x08080AAE CMP #7` 与 `0x08080AB0 BHI 0x08080AFC` 以 unsigned 关系限制
  `index <= 7`，并支配后续两个 halfword load；
- `0x08080AE0` 读取唯一 table-base literal，`0x08080AE4` 做 `index << 2`；
- `0x08080AE8`、`0x08080AF0` 分别读取 record `+0`、`+2`，写入目标 `+8`、`+10`；
- `0x08080AF4/AF6` 自增并回写 index，完整 writer 分母只有 `0x08080AF6`。

八条记录第一列按 s16 为 `[-4,-6,-7,-8,-6,-4,-2,0]`，第二列按 u16 为
`[0,4,7,9,9,7,4,0]`。业务字段含义与目标端 signedness 均不声明。

## 独立性与失败关闭

exporter 使用 raw Thumb 位域重建 43-node CFG、支配关系、literal、stride、双 `LDRH`
数据流与 index writer；verifier 使用 vendored Capstone 独立重建同一合同，二者不共享
解释函数。对 CMP、BHI、literal、stride、increment、两个 LDRH 和 writer 的单点变异均
失败关闭。正式 artifact 仅允许 manifest 与 payload 两个 canonical JSON 文件，发布使用
原子 no-replace；8/8 packet tests 与 standalone verifier 通过，Sol 最终复核无 P0/P1。

artifact / 实现身份：

- manifest：`d909fed886e1779ae8db16a04dbcce7471d74a9a808ad17f6afd7372a0cb8d04`；
- payload：`d95ab9f397511a88550301bed432315e66e75899e15073b74c19a643fff85af2`；
- exporter：`e5340c70ff95e6dfc227b3739220bfe7ac050b77272229767d182b8f1f1735a2`；
- verifier：`077037c6924ba2e184f98bf84ef8f1598035ee7ad4d11698d79c7370fee7de7a`；
- packet tests：`ca4a074f911a6342226eb0a4f1a1e82c2861a89e890d552f435d8f7b0c440de6`。

## 边界

`[0x53F30E,0x53F310)` 两字节和更右侧动态索引结构保持 unknown。artifact 不声明所有
index 的自然运行时命中、字段业务语义、目标 signedness、相邻 gap 性质、编辑、写回、
重定位或 free/allocatable space。

本包与 boot-state、fixed-animation、battle-distance 三包统一完成 Tier-2 后，canonical
为 6,194,116 classified / 97,340 unknown / 16,652 claims / 18,332 segments，
98.45282236735026%。正式 non-degraded formal 106/106 contract 通过；详见
`build/experiments/active/four-packet-tier2-20260904/`。
