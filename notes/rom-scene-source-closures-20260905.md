# Scene source closures（2026-09-05）

## 结论

`rom-scene-source-closures-v1` 已正式发布并由独立 verifier 复验。它只晋升
`[0x46401C,0x464534)` 包络中有固定消费者或 parser 边界的 current-unknown 字节：

- 71 段 parser-bounded text/fixed source roots：655 bytes；
- 2 个 Cutscene OBJ source closures：360 bytes；
- 合计 73 claims / 1,015 bytes。

包络总长 1,304 bytes。46 段 / 90 bytes 的 alignment gaps 独立排队，不混入主合同；
另有 23 段 / 199 bytes 缺少可靠 owner，继续保持 unknown。候选 roots `0x464298` 与
`0x4642AC` 没有闭合消费者，已失败关闭排除。早期 1,029-byte 草案含 12 bytes
unknown-only roots 和 2 bytes parser overrun，已被正式 1,015-byte 分母取代。

## 验证边界

- exporter 从固定 source/record 分母、parser 终点和 Cutscene OBJ 上游 artifact 重建
  promotion，不按连续包络或填充值扩张。
- 独立 verifier 不导入 exporter，重新读取 raw ROM、上游 artifact 和 immutable
  precoverage，重建 73 个 ranges、bytes、顺序、哈希与保留洞。
- 12/12 packet tests、正式 artifact verifier、Tier-1 current-unknown projection 和 Sol
  P0/P1 复核通过；Luna 只读复核 23 个 residual holes，未发现可可靠晋升项。
- 不声明全部 scene source、自然运行时可达、最终像素等价、padding/free space、编辑、
  写回或重定位安全。

## 正式证据

- artifact：`artifacts/rom-scene-source-closures-v1/`
- manifest SHA-256：
  `df3616f985564cd4e04850c8f1e7f6ae8be9b51bd2d50b425317ea33c1698467`
- payload SHA-256：
  `0013db71a7e83af7e7eb86b784e01f07a80931bebdd8d790c7e055d2545f4929`
- verifier SHA-256：
  `8a5ed29f61f20d5ef8f027a7509f58aad59310cf903bb38aab84bb77e672393a`

## 四包 Tier-2 接入

本包与 `rom-v17-v18-helper-cfg-v1`、`rom-fixed-pair-tables-v1`、
`rom-prebattle-menu-controller-cfg-v1` 合计 4,231 bytes / 141 claims，达到四包门槛并
真实接入 canonical：6,198,347 classified / 93,109 unknown / 16,793 claims /
18,552 segments，即 98.52007230122885%。coverage / proof SHA-256 为
`b14d1778bc9961356cca7f319c9d2ae85a07a6811276f9ee0cd1bc2070e96b82` /
`e50417ea10a2f485c3462812fe8aa74d518bb551fcac79f526ad75aad8c4a8e9`。

依赖旧 coverage 的三个 packet verifier 已改为读取
`rom-scene-source-four-packet-precoverage-v1`。该 gzip 解压后精确等于接入前 canonical
`ae7c6933...90024`，避免 live canonical 前进后 verifier 自失效。正式非降级 formal
执行 106/106 contracts，ROM gate 96/96、coverage errors=0；report / guard SHA-256 为
`b2afd536ecc4437851664bda55874fa277fb8425085b75f07c7153498fb088da` /
`f09deffdcc4fff545f003eb293b8cafe1632a13918686be170b3b66469afb30d`。

下一优先项是 story callback 六条固定 BL 边驱动的 direct-callee 依赖闭包；只读预核定
净增 1,460 unknown bytes，必须按精确 worklist/range 晋升，不能吞并相邻洞。
