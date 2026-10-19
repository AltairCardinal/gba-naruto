# Story callback 直接依赖闭包（2026-09-05）

## 结论

`rom-story-callback-dependency-closures-v1` 已作为 Tier-1 packet 发布并由独立 raw
Thumb verifier 复验。它从 `rom-story-state-callback-cfg-v1` 中六条固定 opaque BL
边出发，并递归纳入三条唯一直接依赖，冻结 9 个 root 的最小闭包：

- 762 条 Thumb 指令、156 个 basic block；
- 18 段 code，1,656 bytes；
- 71 个 LDR 引用、69 个唯一 literal word，合并为 14 段、276 bytes；
- 合计 32 claims / 1,932 bytes，0 unresolved frontier；
- 63 个 opaque call exits 落入 37 个既有非 unknown owner；
- 8 个 indirect return 由逐 root 的 prologue/epilogue 合同关闭；
- 唯一 `0x0863FC -> 0x0863FE` continuation 落入既有 CFG owner；
- 6 个内部 2-byte hole，共 12 bytes，明确保持 unknown。

本包只证明固定直接 producer 所绑定的有限 Thumb CFG 与实际 LDR literal，不声称自然
执行可达、所有 callback dependency、computed/indirect producer、ABI/业务含义、相邻
填充、可编辑、重定位或可分配空间。

## 失败关闭与独立性

全 ROM 半字对齐 direct-branch 扫描确认 9 个 root 各只有一个固定 BL producer。独立
verifier 不导入 exporter，使用 raw Thumb 位域解码重建 762-node closure、producer、
literal、exit、boundary 与 structured-return 分母。producer、closure、literal、hole、
boundary source/owner 任一代表性单字节变化均失败关闭；artifact 路径拒绝 symlink，正式
发布使用内核原子 no-replace。

Sol medium 复核发现初版把可变的 live coverage 当永久历史基线，会在后续 promotion 后
自失效。已先发布
`artifacts/rom-story-callback-dependency-closures-precoverage-v1`，其中 gzip 解压后精确
等于接入前 canonical：31,201,261 bytes，SHA-256
`b14d1778bc9961356cca7f319c9d2ae85a07a6811276f9ee0cd1bc2070e96b82`。
exporter/verifier 只读该 immutable artifact；测试显式禁止 verifier 读取 live coverage，
仍能复验通过。

## 身份与验收

- precoverage manifest / gzip SHA-256：
  `fbdc769feb0c7d23752f73cf1caf7578a06a8c7df866cfaf0c64c738e1b0f423` /
  `af9fd00d9e5bc5bf10b1d7f63b5e44325498982efe2c9b8b46aada34faa21c00`；
- packet manifest / payload / verifier SHA-256：
  `0c0209dcf0bb5081f83ec7d0c01816e9b40d318bf69b7a2bf9892716e10385ea` /
  `62d3ad4455afac0c66d629097d2e50603e6c4dcff17b3c4fea5a72f28de0a18b` /
  `3338abdaeeca3e8187aad6484f7bfeba5b6b5e2a6affe16ca0613405df902364`；
- precoverage + packet tests：9/9 通过；coverage quick projection：3/3 通过；
- candidate 与正式 artifact 逐字节相同；正式 verifier `verified=true`、
  `contract_ok=true`、`root_count=9`、`promotion_bytes=1932`、`frontier_count=0`；
- guard receipts：
  `build/experiments/active/story-callback-dependency-closures-20260905/`。

## 进度口径

authoritative canonical 暂不改写，仍是 6,198,347 classified / 93,109 unknown /
98.52007230122885%。Tier-1 current-unknown 投影为 6,200,279 classified / 91,177
unknown / 98.55078061421713%，提升 0.03070831298828125 个百分点。当前批次只有 1 个
packet / 1,932 bytes，未达到 4 packets、10 KiB 或 0.15pp 的 Tier-2 门槛，因此不运行
full coverage、proof 或 formal。
