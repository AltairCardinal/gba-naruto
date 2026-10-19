# 79 槽战斗消息文本与零填充闭包（2026-08-11）

## 结论

基准 ROM SHA-256 为
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
固定 79 槽表 `0x005A2034..0x005A2170` 指向 79 个唯一、严格递增的消息记录。
按真实 renderer grammar 解析后得到：

- 79 条 parser 消费记录：1,411 字节；
- 79 段记录结束至下一 target（末条至表首）的逐字节零填充：1,329 字节；
- 两者连续、无重叠地闭合 `0x005A1580..0x005A2034`：2,740 字节。

artifact 位于 `artifacts/rom-battle-message-text-inventory-v1/`。manifest SHA-256
为 `fff6410091d6165f338821b6400ecb5e0912a7221bad0c664bbce85d9daf5d54`，
payload SHA-256 为
`c5e270c79c5cf5f18e13c9d0c77162afef8c28b459f6e86eecabd5f232a4db7b`，
连续 byte bundle SHA-256 为
`e0be9ff986140ae489c88769e483d98eab06febcf9f26ebf5fc6395fb428e0b9`。

## 固定分母与消费者

`sequel/content/data-table-b/bank.json` 固定表首、79×4 分母及每个指针；表原始
字节 SHA-256 为
`c6dc43fda3044405fec144561fb76b3e684aa974a0c5633ec990ba5532b47ce3`。
全 ROM 中表地址 `0x085A2034` 只有两个 literal：

- `0x08098624`，消费者 `0x080985D8..0x080985EA`；
- `0x08099D58`，消费者 `0x08099D24..0x08099D38`。

两条路径均按 byte ID×4 取指针并调用 `0x08098290`；wrapper 在 `0x08098308`
恢复文本指针后调用 `0x08066758` bridge，bridge 再调用 `0x0806626C` parser。
parser 以 `0x00` 终止，并按控制字节与 SJIS range table 决定步长。

## 字节边界

79 条记录范围分母 SHA-256 为
`d397dcf693ddcfedccaeb56efba1eeb2e646adfdfcea116254b41ad6898110cf`，
记录内容 bundle SHA-256 为
`24f1684e150bed11571cfa2f35fbb77d4e44c952d58fbcd5ec15d3e70f8eb8af`。
79 段零填充范围分母 SHA-256 为
`2170a4fffa02b01884c4633470fae48d24594e0083dfeebfb7b1dc52d41bd6e5`，
填充内容 bundle SHA-256 为
`738f09bb312878c2a990ac9af0ef31be3d3935a34233802f11b8bf10d1a47479`。

316 字节指针表已由 `data-table-b` 的 `fixed_table` claim 拥有，本批不重复分类。
紧邻前方 `0x005A14F4..0x005A1580` 的 140 字节没有固定 producer/consumer，继续
保持 unknown。

## 限制与复核

自然 action-7 证据只绑定 ID 0。当前不声明运行时索引一定小于 79、其余 78 个 ID
自然可达、Unicode 文本、可安全写回、实体 GBA 行为，或零填充可作为分配空间。
exporter 与独立 verifier 固定 ROM、bank/evidence、两个 consumer、wrapper、bridge、
parser、79 指针、每条记录与间隙、范围分母及 bundle；输出拒绝根/祖先、foreign
目录和符号链接。

```bash
python3 tools/export_rom_battle_message_text_inventory.py --root .
python3 tools/verify_rom_battle_message_text_inventory.py \
  --root . \
  --artifact-dir artifacts/rom-battle-message-text-inventory-v1
python3 tools/audit_rom_byte_coverage.py --root .
```

本批接入后，保守语义分类为 5,984,285 / 6,291,456（95.1176%），unknown 为
307,171（4.8824%）。
