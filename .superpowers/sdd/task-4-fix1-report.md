# Task 4 第 1 轮修复报告

## 状态

DONE_WITH_CONCERNS

## 修复范围

- Observer baseline 与后续采样改为一次读取 `0x0203F040..0x0203F097` 的 88-byte 同步快照；同一快照包含共享事件计数器、`PCU1` 和 `PCO1`。evaluator 要求 player/current sequence 都严格晚于 baseline 的共享 sequence boundary，拒绝采样过程中已经发生的 player hit。
- 玩家正证据不再从 observer 参数回退。单位诊断从已确认的 unit `+0xC0` 标志提取 affiliation 和 active 状态，仅当存在唯一 active affiliation-0 单位时提供独立 slot/character/affiliation；缺失、类型非法、歧义或任一 observer 参数不一致均 fail closed。
- 输入审计改为追加式事件：记录 phase/step、logical key、GBA button、holdMs、classification、down/up completion。按下或释放状态只在对应调用成功后置为 true；释放失败会保留 `downCompleted=true/upCompleted=false`。
- player-control evaluator 接收深度冻结的 expected plan，并要求实际事件完整、全部 explicit、数量和字段逐项严格匹配。正式 driver 的 Task 5 边界固定为一次 `tail step 1 / KeyZ / A / configured holdMs`，任何 automatic、任意键或额外键都拒绝。
- legacy evidence stop 条件及非 player-control 成功路径未改变；三处 live `pressGbaKey` 仍全部显式分类并补充 phase/step。

## TDD RED

命令：

`node --test play/_scripts/scenario-41-runtime-evidence.test.js play/_scripts/runtime-formation-probe.test.js`

- 53 tests：44 passed / 9 failed。
- 正确失败原因：生产代码仍做两次独立 24-byte 读取，无法接收单次 88-byte 快照；audit 仍写字符串数组，无法记录 down/up；unit summary 未暴露 affiliation/active；evaluator 未实现 shared boundary、独立 controlled diagnostics 和严格单 A 计划。
- RED 覆盖了审查列出的三类反例：baseline 两 slot 之间发生 player hit、缺失或不一致的 slot/character/affiliation 与 tracker 实际接线、release 失败/任意键/额外键/正确单 A。

## GREEN 与重构

- 第一次 GREEN：53 tests，52 passed / 1 failed；唯一失败为测试投影遗漏新 affiliation/active 字段，不是生产逻辑失败。
- 修正测试投影后最终 GREEN：53 passed / 0 failed。
- 快照 decoder 仍复用既有 `decodePublishedCall`，没有另建第二套 ABI parser。
- uint32 freshness/order 继续复用既有 bounded modulo-forward 算法，包括 `0xFFFFFFFF -> 0` 回绕覆盖。

## 验证

- `node --test play/_scripts/scenario-41-runtime-evidence.test.js play/_scripts/runtime-formation-probe.test.js`：PASS，53/53。
- `node --check play/_scripts/scenario-41-runtime-evidence.js`：PASS。
- `node --check play/_scripts/runtime-formation-probe.js`：PASS。
- `git diff --check`：PASS；仅有既有 Windows `core.autocrlf` advisory。
- 静态核对三处 live `pressGbaKey`：plan/tail primary=`explicit`，adaptive-back=`automatic`，settle recovery=`automatic`；均带 phase/step。
- 按任务边界未运行 mGBA/Chromium，也未触碰 Task 5 或大量 `build/` 证据。

## 自审

- 单次 `readGbaBytes(page, 0x0203F040, 0x58)` 对默认浏览器 reader 来说只触发一次 `page.evaluate`，两个 observer slot 不再跨 JS 异步边界。
- baseline 记录共享计数器；player/current 除各自 hit-count/sequence freshness 外还必须分别晚于该共同边界，因此 current-only 后续命中不能复用 baseline 采集期间的 player hit。
- tracker 的 controlled unit 由 unit `+0xC0` 诊断独立决定，不读取 player/current observer 参数来选择单位；多个或零个候选会返回空诊断并拒绝正结论。
- input snapshot 对每个事件复制并冻结；后续按键不会回写较早 diagnostic。
- expected plan 数组及每个条目必须冻结；实际 down/up 未完整、automatic 非空、键/按钮/hold/phase/step/数量任一不一致都会拒绝。

## 残余顾虑

- 本轮只加固证据层，没有运行 scenario 41，因此仍未证明玩家控制。Task 5 需要用真实 checkpoint 验证 scenario 41 确实只有一个 active affiliation-0 可控单位；若诊断出现零个或多个候选，当前实现会保守返回 not-proven，而不会猜测。
- 输入释放调用抛错时审计会正确保留未完成事件并让上层失败；驱动没有在该异常路径尝试额外释放，因为这会形成未列入计划的补偿输入。
