# 38 槽值域选择文本闭包（2026-08-11）

## 结论

旧候选 92 的 `0x599F5C..0x599FEC` 36 槽范围不是完整表，也不是 code-handler
表。真实固定分母为 `0x599F5C..0x599FF4` 的 38 槽文本指针表；同一消费者以
`0x542204..0x54229C` 的 38 对连续 u16 包含范围选择槽位，并把目标交给
`0x08066758 -> 0x0806626C` renderer/parser。

38 条记录由各自真实 `0x00` 终止路径界定，连续覆盖
`0x00542E..0x00578C`，准确大小为 862 字节。早期只读报告中的 864 字节是算术
错误，未进入 artifact 或 coverage。

## 固定证据

- 基准 ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 指针表：`0x599F5C..0x599FF4`，38×4，SHA-256
  `70e722a0521ed49bf2ac43cbbee960295332d4b857115b595163da29f7731110`
- 值域表：`0x542204..0x54229C`，38×`{u16 lower,u16 upper}`，连续覆盖
  `0x0000..0x017B`，SHA-256
  `d5fc38cb718478c33f58d2175f2b6d35d360e08c83dfcde2a082a3f5852e39c9`
- 记录并集：38 条，`0x00542E..0x00578C`，862 字节；记录范围分母 SHA-256
  `90be672576fa1ecba130596da7304d92283f5f77e7b89ee8a42ac41e46f42ef0`
- consumer：`0x08087484..0x080874E0`；从 `0x02003AD0` 读取值域输入，查找
  38 对范围并按 `index*4` 读取指针。
- renderer 桥接：`0x08066758`；parser：`0x0806626C`。

## Artifact 与覆盖边界

规范产物位于 `artifacts/rom-value-range-text-inventory-v1/`：

- manifest SHA-256：
  `7bea3bcecd28d86a6bdbcd5bba58cbb4413dced0008691e219262de8f1a0faca`
- payload SHA-256：
  `2095c3e719f203de4e819a5c1e2a1af95320849860fb463f65b1c8ff4fda4b42`
- bundle SHA-256：
  `88f201f21194087ff7643f1822d0b89c309feff497fbef6155ff5ae6ce6bc3d0`

Coverage 只认领 152 字节值域表与 862 字节 renderer 记录，共 1,014 字节。
指针表由 similar-table candidate overlay 唯一拥有；候选 92 从 accepted 改为完整表的
strict-subrange alias，并把最后 2 槽的 8 字节从 unknown 纳入。因此本批净减少
unknown `1,014 + 8 = 1,022` 字节，canonical coverage 更新为
`5,980,729 classified / 310,727 unknown`。

不声明：`0x02003AD0` 的运行时上界、自然玩法覆盖全部 38 个范围、Unicode 文本
解码、字段含义或安全写回。

## 复核

```bash
python3 tools/export_rom_value_range_text_inventory.py --root .
python3 tools/verify_rom_value_range_text_inventory.py \
  --root . \
  --artifact-dir artifacts/rom-value-range-text-inventory-v1
python3 tools/verify_similar_table_candidates.py --root .
python3 tools/audit_rom_byte_coverage.py --root .
```

候选 verifier 的实现哈希变化会级联到 CFG seed 的证据实现哈希。2026-08-11 已按
seed → v2 → v3 顺序重建；263 个 roots、40,872 条 v2 指令、4,698 条 v3 扩展
指令及其 ROM 覆盖范围均未变化，只有哈希绑定链随修正版 verifier 更新。
