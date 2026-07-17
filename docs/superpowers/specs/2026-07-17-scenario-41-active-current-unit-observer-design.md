---
change: close-scenario-41-battle-runtime
status: approved-by-executor-under-standing-autonomy
---

# Scenario 41 活动 current-unit observer 修正设计

## 问题与证据

Task 5B 已自然命中 `0x08073946`：PCO1 sequence 1、参数 `(9,0,1)`。随后唯一 A
进入 `0x08073A4A -> 0x08067158` action-menu handler，但 `0x080739D8` 的 PCU1
始终为零。活动栈的 `0x03001220 = 0x08073A4F` 已由 ROM 中的 Thumb BL 静态验证。
handler 返回 `0x08073A4E` 后只会重派 action menu 或继续动作，不会回到已经越过的
`0x080739D8`。因此继续按键无法补出 PCU1 命中。

原验收语义也不正确：`0x08073940` 明确把 `(9,0,1)` 传给选择器
`0x0806F718`，这三个值是 accept mask、mode 和 flags，不是玩家 slot、character 或
affiliation。活动路径在 `0x08073BAA` 从 unit object `0x0202680C + 3` 读取 slot，并以该
slot 作为 `r0` 调用 `0x08069DB8`；后者按
`0x020240C0 + (r0 & 0xff) * 0x1D4` 定位 WRAM unit record。character id 位于该 record
的 `+0`，不是 call argument；`record+3=13` 是另一字段，不得解释为角色 ID。callee 会覆盖
入口 `r1/r2`，因此包装器记录的 `r1/r2` 不能作为单位属性。

## 方案比较与决定

1. **保留旧 site，并增加活动 site（采用）**：继续覆盖 `0x080739D8`，新增
   `0x08073BAC -> 0x08069DB8`。两处使用独立 scratch、magic 和 event code，运行时选择
   PCO1 之后实际 fresh 的 current-unit 事件。
2. hook 共同 callee `0x08069DB8`：能覆盖所有调用，但会混入其他场景，且需要额外识别
   callsite/phase，扩大误报面。
3. 用 `0x08073BAC` 替换 `0x080739D8`：实现最小，但丢失原设计路径覆盖，无法解释不同
   battle state 的差异。

采用方案 1。它只增加一个 checked call 和一个零填充 cave，不改变已有 observer 行为。

## Patch 与 ABI

现有 site 保持不变：

- PCO1：hook `0x08073946`，original `0x0806F718`，stub `0x0809E800`，scratch
  `0x0203F080`，event `1`。
- PCU1：hook `0x080739D8`，original `0x08069DB8`，stub `0x0809E880`，scratch
  `0x0203F060`，event `2`。

新增活动 site：

- 名称 `active-current-unit`。
- hook `0x08073BAC`，原始字节 `f6 f7 04 f9`，目标 `0x08069DB8`。
- stub `0x0809E900`，96-byte cave 已确认全零。
- scratch `0x0203F0A0`，24 bytes。
- magic `PCA1`，event code `3`。
- 共享 counter 仍为 `0x0203F040`。

三个 wrapper 都必须完整保存并恢复 `r0-r4`，发布完整 record 后 tail-call 原目标；尤其不能
依赖会被 callee 覆盖的入口 `r1/r2`。site、scratch、stub 之间必须通过既有 overlap guard。

## 正确的验收数据流

1. load 后 baseline 要求 counter、PCO1、PCU1、PCA1 全零。
2. PCO1 fresh 只证明进入选择器；其参数必须精确为协议 `(9,0,1)`，不得解释为单位身份。
3. current-unit 候选为 PCU1 或 PCA1 中 PCO1 之后第一个 fresh record；两者同时 fresh 时按
   sequence 选择最早者并保留 source hook。
4. current-unit `argument0` 必须等于独立 WRAM unit diagnostic 的 slot；该 slot 必须按
   `0x020240C0 + slot * 0x1D4` 映射到同一 WRAM unit record。
5. character id 必须从该 record `+0` 读取，affiliation 必须按既有 runtime unit 解析约定从
   同一 record 的 `+0xC0` 低位读取。canonical 数据为 `controlledSlot=1`、
   `controlledCharacterId=1`、`controlledAffiliation=0`；同一 record 的 `record+3=13` 是另一字段，
   不得解释为角色 ID。character/affiliation 都必须通过既有 validity/from-WRAM gate，并与
   battle 41 当前玩家单位一致。不得使用 current wrapper 的 `argument1/argument2` 或 PCO1
   参数替代。
6. accepted evidence 必须记录 current source hook、magic、event、sequence、character id、
   unit-object slot/affiliation 和显式输入清单。

## 测试与失败边界

TDD RED 必须先证明：

- builder 尚未 patch `0x08073BAC`，或缺少独立 cave/scratch/magic/event。
- confined-diff 仍只允许三个 checked calls 与三个 96-byte caves。
- evaluator 拒绝把 PCO1 `(9,0,1)` 当 slot/affiliation。
- evaluator 接受 PCU1/event2 或 PCA1/event3 的 source-mapped fresh record，但只以
  `argument0` 绑定 WRAM unit slot，再由该 slot 映射的 record 提供 character/affiliation。
- source hook、event、magic 不匹配，或 unit-object slot/affiliation 不一致时拒绝。

GREEN 后重建 observer ROM并从已接受的 canonical controller checkpoint 重放既有唯一输入
链。新增 ROM 不能从旧 PCA1 非零状态起步；必须确认四个 baseline 区域全零。若 PCA1 仍不
fresh，停止并做 GDB 只读 breakpoint 核查，不追加盲输入。

## 范围

本修正只闭合 OpenSpec 4.1/Task 5B 的 current-unit 证据，不验收 MOVEDONE、动作提交、
胜利或 postbattle。既有运行产物保留为 observer-site mismatch 的负证据，不覆盖历史。
