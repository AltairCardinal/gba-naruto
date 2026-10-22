# Battle-distance 七路 dispatcher CFG

## 结论

`rom-battle-distance-dispatcher-cfg-v1` 精确晋升 1,162 bytes / 14 claims：28-byte
dispatcher table、1,110-byte reachable Thumb code 与 24-byte PC-relative literal。
两个 2-byte 零洞保持 unknown。本结论不声明自然运行时、距离算法业务含义、opaque
target 语义、padding/free space 或编辑/重定位安全。

## 证据链

- ROM SHA-256：`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- upstream code artifact 固定 `0x083B3C..0x083B4E`：`LDRB` selector，unsigned
  `CMP #6/BLS`，越界跳 `0x083FEA`，合法值乘四后由 `0x083B58` literal 取得
  `0x08083B5C` 并 `MOV pc`。
- table `[0x083B5C,0x083B78)` SHA-256
  `0186fb9894e0c12d8d8b2b9e0c5191f47dbe16041427105fde3edfbb04a0cfde`，七个 root 为
  `0x083B78/0x083BAC/0x083C8A/0x083D20/0x083DAE/0x083E38/0x083F0E`。
- bounded worklist：555 instructions、126 blocks、25 opaque accepted exits、0 frontier；
  packed code/literal SHA-256 为 `6bf6a49a...31950` / `aed4c39e...1a8de`。

## 验收

- packet tests：7/7。
- Tier-1 quick projection：3/3，projected classified/unknown =
  6,194,084 / 97,372（包含本批前两个 packet）。
- Tier-2 registry 回归：1/1；reachable code kind 已登记为 `thumb_only`，正式 aggregate
  不会把它视为未授权 future code kind。
- standalone verifier：`verified=true`、`promotion_bytes=1162`、`frontier_count=0`。
- artifact manifest/payload/verifier SHA-256：`ce7844f6...5fa2` /
  `2b8efd1f...c718` / `8f6f3ce4...5716`。

## 后续边界

只有进入 `0x083FEA` / `0x083FFA` 的 owner 已由 upstream artifact 固定；本包把它们当作
opaque stop。两个零洞不能因相邻代码和 literal 自动解释。full coverage/proof/formal
必须等本批达到第四包或其他 tier-2 阈值后统一运行。
