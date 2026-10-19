# Pre-battle menu controller CFG packet（2026-09-05）

## 结论

`rom-prebattle-menu-controller-cfg-v1` 已冻结、正式发布并由独立 verifier 复验。它从
authoritative coverage 的 current-unknown 集合中精确晋升 1,920 bytes：

- 27 段 reachable Thumb code，1,564 bytes；
- 24 段 PC-relative consumed literal words，332 bytes；
- `[0x08F39C,0x08F3B4)` 六项固定 jump table，24 bytes。

该包入队时与前两个待接入包形成的历史 Tier-1 overlay 为 6,197,332 classified /
94,124 unknown / 98.50393931070963%。随后 scene source 成为第四包，四包已统一通过
Tier-2 接入；当前 authoritative canonical 为 6,198,347 / 93,109 /
98.52007230122885%，不再使用上述 overlay 判断当前进度。

## 固定 denominator

- root：`0x08F190`；全 ROM target-limited direct denominator 唯一命中为
  `0x08F894 BL -> 0x08F190`。
- producer owner：上游 accepted `rom-story-state-callback-cfg-v1` 的
  `[0x08F872,0x08F8EE)` claim；上游 manifest、payload、verifier、canonical JSON、
  accepted 状态、702-byte promotion 和精确 claim 均失败关闭绑定。
- selector：`0x08F380..0x08F394` 证明 `0..5`，`0x08F392` 通过
  `[0x08F39C,0x08F3B4)` 六项表解析，不再是 frontier。
- raw closure：786 instructions / 1,752 bytes / 200 blocks；其中 699 instructions /
  1,564 bytes 为 current unknown，87 instructions / 188 bytes 是两个既有 owner 的
  decode-through dependency。
- opaque calls：83 edges / 35 targets，均要求当前 coverage 中恰有一个 code/CFG owner；
  保留 7 个 fixed indirect-PC frontiers。
- literal denominator：84 references / 83 unique words，其中 current-unknown 为
  24 ranges / 332 bytes。

不声明自然运行时可达、全局函数入口穷尽、七个间接目标已解析、opaque callee 内部语义、
编辑/重定位安全或 free space。

## 审计分层修改

最初把上游完整 verifier 放在 `_producer()` 内，导致每个 ROM/合同 mutation 都重复进行
上游全量重建。TDD 新增 release-layer RED 后改为：

1. 普通 `build_payload()` / `_rebuild()` 只做冻结文件身份、canonical JSON、manifest、
   payload owner claim、ROM bytes 与当前 coverage owner 的轻量失败关闭校验；
2. 正式 `export_artifact()` 与独立 `verify_artifact()` 入口各自执行完整上游 verifier；
3. Tier-1 coverage 使用线性 current-unknown 交叠门，不重建 canonical ledger。

内层 release-gate 测试由 14.3 秒失败变为 4.2 秒通过；完整 packet suite 12/12 在
68.8 秒内通过。该修改只减少重复计算，没有删除正式发布门。

## 证据

- artifact：`artifacts/rom-prebattle-menu-controller-cfg-v1/`
- manifest SHA-256：
  `e94a01e3ef814e4d98e99e74aeb6575a49ec8c80e474a5ed8f70d40cbf991f6c`
- payload SHA-256：
  `ed05a078db7d94e0ca27f53593ec504b2152bc63c53c73bbf01e045eda03ae13`
- verifier SHA-256：
  `387c1b00a1c38b424e6f30d567374329493c1d3309c32a29fd905b77a65b3d2f`
- exporter / contract / packet-test SHA-256：
  `61e8fbc7...e7f6` / `6f0bc5de...3362` / `87ae5bff...d5c`
- candidate 和 official exporter/verifier guard 均 `reason=completed`、
  `degraded=false`；峰值 tree RSS 分别约 147/110 MiB。
- 预加固 candidate 已保留到
  `build/experiments/superseded/prebattle-menu-controller-cfg-sol-pre-parent-hardening-20260905/`，
  不得作为正式证据引用。

## 模型与失败记录

最初 994-byte 合同漏掉 current-unknown callees `0x08CD40` 和 `0x08768C`，Luna max
因此正确阻塞；父代理递归扩张并冻结最终闭包。Luna 随后只留下 RED/contract 而无 blocker
地停滞，升级到 Sol medium 完成实现。Sol reviewer 找到 promotion union 未从组件派生、
producer owner 为合同回显两个 P1；父代理用 mutation RED/GREEN 关闭，并完成正式验收。

## 下一步

原计划的 scene packet 已按严格分母完成：两个 OBJ closures 360 bytes + 71 段
text/fixed source 655 bytes，共 1,015 bytes；46 段 / 90 bytes alignment gaps 独立排队，
23 段 / 199 bytes residual 继续 unknown。四包现已正式接入，详情见
`notes/rom-scene-source-closures-20260905.md`。
