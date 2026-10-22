# ROM CFG proven-roots v20

## 结论

- 唯一可接受 producer 为 `0x06108E BL -> 0x062924`，它位于已接受的 boot
  continuation instruction owner `[0x06108A,0x0610D4)`。
- 全 ROM、2-byte stride 的 Thumb BL/B/Bcond target-limited 分母另有
  `0x061320 BL -> 0x062924`；其 owner 是 `consumer_code_slice`，因此只保留为
  shape match，不作为 root proof。
- 从 `0x062924` 重新解码得到 1,405 instructions / 249 blocks / 2,866 code bytes，
  39 个 PC-relative LDR 绑定 39 个唯一 literal words / 156 bytes；17 条出边只进入
  5 个精确 accepted owner。
- `0x062918 BX r0`、`0x063336 BX r0`、`0x063602 BX r1` 是三个未解析 frontier；
  不声明 structured return、动态目标或自然运行时可达。

## 字节晋升

- 当前 unknown 中精确晋升 11 段 Thumb code / 1,070 bytes 与 7 段 consumed
  literals / 80 bytes，共 18 claims / 10 union ranges / 1,150 bytes。
- 与 `rom-story-callback-dependency-closures-v1` 的 1,932-byte overlay 重叠为 0。
  两包累计投影为 6,201,429 classified / 90,027 unknown，即
  98.56905937194824%。authoritative canonical 仍保持 6,198,347 / 93,109。

## 证据与边界

- 正式 artifact：`artifacts/rom-cfg-proven-roots-v20/`。
- manifest / payload / verifier SHA-256：
  `7f5ed6e408b834afc91e622898f0eabb7278b7906098dbfff39fa87283975f2d` /
  `5d3186a688973b1733b0117aedee7c689a5270497c83f8726d4d2540bcfe1543` /
  `0f185e030fda6461d5652d67d34850c872f45836ba580ef6a3074883736fde66`。
- exporter suite 9/9、Tier-1 projection 3/3、独立 official verifier 均通过；
  guard 峰值分别不高于 201.7 MiB，非降级。
- 不声明全局 caller/code/indirect/computed/RAM producer、rejected producer
  有效性、literal 业务语义、holes/alignment/padding/free、ABI/compiler、编辑、写回、
  重定位或 gameplay。
