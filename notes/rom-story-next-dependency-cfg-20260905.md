# ROM story-next dependency CFG

## 结论

- root `0x088F10` 的全 ROM、2-byte stride Thumb BL/B/Bcond target-limited
  producer 分母恰有两项：接受 story callback code owner 内的
  `0x08F928 BL -> 0x088F10`，拒绝仍为 current unknown 的
  `0x08F61A BL -> 0x088F10`。
- 从 root 重新解码得到 338 instructions / 96 blocks / 770 code bytes；21 个
  PC-relative LDR 绑定 21 个唯一 literal words / 84 bytes。43 条 direct call
  出边绑定 26 个既有 code targets，其中 `0x065404`、`0x08CBF4`、`0x08CC18`
  额外绑定独立验证的 CFG-inventory v2 精确 instruction entries。
- `0x0884CA BX r0`、`0x088648 BX r1`、`0x089062 BX r1` 保守保留为三个
  unresolved indirect-PC frontiers，不把返回形态外推成动态目标或自然可达证明。

## 字节晋升

- 精确晋升 10 段 Thumb code / 770 bytes 与 9 段 consumed literals / 84 bytes，
  共 19 claims / 7 union ranges / 854 bytes。
- 五段 2-byte holes `[0x08859A,0x08859C)`、`[0x08860E,0x088610)`、
  `[0x08864A,0x08864C)`、`[0x088F52,0x088F54)`、`[0x089036,0x089038)`
  继续 unknown。
- 与 story callback 1,932 bytes、CFG v20 1,150 bytes 顺序 overlay 后累计净增
  3,936 bytes；Tier-1 投影为 6,202,283 classified / 89,173 unknown，即
  98.5826333363851%。authoritative canonical 仍为 6,198,347 / 93,109。

## 证据与边界

- 正式 artifact：`artifacts/rom-story-next-dependency-cfg-v1/`。
- manifest / payload / verifier SHA-256：
  `a5429f89ecfb60da5ce6950063ee5d9df2996eead6ad60d221474429d49e4669` /
  `d12f4b28c68ba94bc122fc284cd3bbb8fd4fd59426c0bc46ab4b9dcf377a5e6b` /
  `ed5b35817e06320089bb74914a60ec8765129a4e0c49013cdc6ee9959a1ecfa8`。
- packet suite 10/10、Tier-1 projection 3/3、candidate/official 独立 verifier
  均通过；两次 guard 峰值分别 244.3 MiB 与 260.6 MiB，均为非降级完成。
- 不声明全局 caller/code/indirect/computed/RAM producer、rejected producer
  有效性、三个 BX 的 target/structured-return、literal 业务语义、holes/alignment/
  padding/free、ABI/compiler、编辑、写回、重定位或 gameplay。
- 本包按简化审计策略只进入 Tier-1 队列，不改 canonical/proof，不运行 formal；达到
  4 packets、10 KiB 或 0.15pp 任一门槛后再统一执行 Tier-2。
