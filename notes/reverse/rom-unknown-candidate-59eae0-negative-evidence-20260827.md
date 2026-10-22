# `0x59EAE0` unknown 候选的负证据（2026-08-27）

## 结论

不要把 `[0x0059EAE0,0x0059F5F0)` 冻结成 `118×24` 表，也不要把
`[0x0059EAE0,0x0059F560)` 冻结成已证明安全索引的 `112×24` 表。

静态代码能证明两个消费者都计算：

```text
index = byte[0x08348DAC + state[0x16]] + state[0x19]
record = 0x0859EAE0 + index * 24
```

但进入消费者的两条直接 CFG 链都继承 RAM 值，没有局部 guard。固定 chapter-script
root 还给出具体反例 `(state[0x16], state[0x19]) = (31, 30)`；ROM lookup 的第 31
项为 90，因此组合 index 为 120，而不是 `0..111`。这否证了“仅凭本地代码即可证明
112 条索引上界”的命题。

这不是自然玩法 OOB 的证明：当前仍缺 scheduler callback 首入/续入生命周期，以及
所有 script-root 到 callback 的支配关系。没有这两项证据时，范围必须保持 unknown。

## 固定身份

- 基准 ROM：`rom/base.gba`，SHA-256
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- 调查时 canonical coverage：`sequel/rom-byte-coverage.json`，SHA-256
  `4ea0496a0754d0391ae4f48e16f941d9a2241c9cc730bdf38799abde85181cbd`，
  `unknown_bytes=172150`。
- 原候选 `[0x0059EAE0,0x0059F5F0)`：2,832 字节，SHA-256
  `36dc1d051cfd58034571449b63ed80407fc91d13b6bb7b4ca9445ef19e81db8b`。
- 24-byte 候选前段 `[0x0059EAE0,0x0059F560)`：2,688 字节，SHA-256
  `05cefb7a73e68d196dd4349c3eb553703d497a438468b1e8e52069d86a7096b3`。
- 独立后段 `[0x0059F560,0x0059F5F0)`：144 字节，SHA-256
  `36799e6ed48b1bb9dfb3b6ed607e114ef6477174ce57f57ad352b8cab0441f60`。

`0x0859F560` 有三个独立 ROM pointer literal/PC-relative consumer，因此它是物理
边界证据，不能把后 144 字节冒充第 112–117 条 24-byte record：

- literal `0x08078094`，consumer `0x08077F34`；
- literal `0x080898D8`，consumer `0x08089868`；
- literal `0x08093C6C`，consumer `0x08093A26`。

这三个 consumer 本身尚未给出后段的完整索引分母，所以本记录也不把 144 字节整体
分类为另一张完整表。

## 已闭合的直接 CFG 分母

`0x0808A0F0` 的全 ROM target-limited Thumb BL 分母恰为两条：

- `0x0808F644`，raw `fa f7 54 fd`；
- `0x0808F9C0`，raw `fa f7 96 fb`。

`0x0808A0F0` 固定按 `0 → 0x10 → 0x20 → 0x30` 推进，并各调用一次：

- `0x0808A146 → 0x08089310`，raw `ff f7 e3 f8`；
- `0x0808A172 → 0x08089E84`，raw `ff f7 87 fe`。

两个 target 的全 ROM直接 callsite 分母均为 1。`0x0808A0F0` 没有写入或检查
`0x020311EA`（state `+0x16`）与 `0x020311ED`（state `+0x19`）。

入口 `0x0808F618` 的 `beq 0x0808F644` 路径直接继承原 RAM；另一分支只把两字节
复制到 battle-control RAM，也不修改原值。入口 `0x0808F9C0` 所在 callback 状态机
在状态 `0x120` 的分派路径同样没有支配性的范围检查。

## 固定反例

primary scenario 50 的固定脚本路径包含：

```text
0x0803EE81: 0f 1e       ; state[0x19] = 30
0x0803EFEE: 1a 1f 00    ; state[0x16] = 31
0x0803EFF3: 00          ; terminal
```

`rom[0x00348DAC + 31] = 0x5A = 90`，所以 `90 + 30 = 120`。opcode `0x0F`
handler `0x08097C3C` 与 opcode `0x1A` handler `0x08097C6C` 都直接写 u8，未 clamp。

其他固定脚本终止组合还包括 primary 51/53 的 `(50,30)`、alternate 3 的
`(51,60)`、alternate 50 的 `(31,30)`、alternate 52 的 `(24,30)` 和 alternate 53
的 `(50,30)`。它们继续作为入口状态反例，不自动等于自然 callback 可达性。

## 未闭合 frontier 与恢复条件

以下 callback 入口没有完整直接 caller 分母：

- `0x0808F654`：未解析 computed/indirect callback 入口；
- `0x0808F73C`：由 scheduler 通过精确 Thumb pointer 注册；
- `0x0808EF2C`：由 scheduler 通过精确 Thumb pointer 注册。

只有同时满足下列条件，才允许重新评估 112×24 packet：

1. 对上述 callback 的首入和全部续入状态建立冻结生命周期闭包；
2. 证明到达 `0x0808F644` 或 callback state `0x120` 时，最近一次支配性 writer 将
   `(state[0x16], state[0x19])` 限制为安全组合；
3. 显式排除 scenario 50 等固定脚本终止状态直接继承到这些入口；
4. 独立 verifier 从 ROM 重建 BL/literal/writer/script 分母，不能依赖本笔记的结论；
5. coverage 仍按 live current-unknown 交集投影，既有 primary owner 不重分类。

单一路线 runtime watch 只证明被测路径，不能替代全场景 callback 生命周期分母。

## 2026-08-27 scheduler lifecycle gate 复验

新增可复现 verifier：
`tools/verify_rom_scheduler_callback_lifecycle_gate.py`，定向测试为
`tests/test_verify_rom_scheduler_callback_lifecycle_gate.py`。它不创建 artifact 或
coverage claim，而是从 raw ROM 重建本候选进入下一阶段前必须满足的结构门禁。

已经闭合的窄事实为：

- `0x08061D7C` 的全 ROM raw Thumb 直接 callsite 分母恰为 8 个；
- slot 1 的直接注册历史是两次 `0x0808F73D`，slot 2 的直接注册历史是
  `0x0806E959`、`0x0808C175`、`0x0808EF2D`；
- 11 个固定 wrapper 都进入 `0x08061C58`，后者从固定 callback/context 数组取值，
  经 `0x0809C114` 的 `BX r1` 调用，并在 callback 返回后进入 `0x08061E00` 清理；
- 因此 `0x0808F73C` 与 `0x0808EF2C` 只在
  “literal registration → scheduler dispatch → return cleanup”结构上闭合；
- `0x0808F654` 的全 ROM raw direct branch 分母和精确 Thumb pointer
  `0x0808F655` occurrence 分母都为空，但这只留下 computed/RAM/indirect producer
  frontier，不能反向证明入口不存在；
- `0x0808F668 → 0x0808F618`、`0x0808F7CE → 0x0808F9C0` 与
  `0x0808F644/0x0808F9C0 → 0x0808A0F0` 的 target-limited direct denominator 保持
  固定，scenario 50 的 `90+30=120` 反例也重新从 ROM 验证。

最终 report 为
`build/experiments/active/scheduler-callback-lifecycle-gate/codex-r2-20260827/report.json`，
SHA-256
`1638ab9dab45800256fd921e950ef53600f6f592a05f39842b26bfbd7a983ec2`；
`verified=true`、`errors=[]`、`lifecycle_closed=false`、
`promotion_eligible=false`、`bytes_promoted=0`、`coverage_action=keep_unknown`。
定向 4/4 测试通过，Sol medium 只读 P0/P1 复核为 ACCEPT。

所以原三阶段计划在 Task 1 结束：Task 2 的全 writer/copy/clear/inherit 分母和 Task 3
的抽象索引证明都不启动。只有先用新证据闭合 `0x0808F654` 的 producer frontier，
才允许恢复后续阶段；否则继续投入只会重复已知阻塞。

## 非声明

- 不声明自然玩法一定触发 OOB；
- 不声明 112 条或 118 条是完整物理表；
- 不声明 `[0x0059F560,0x0059F5F0)` 是一张完整表；
- 不声明 computed/RAM/indirect writer 或 consumer 已穷尽；
- 不声明字段业务名称、编辑、写回、重定位、padding、free/allocatable space。
