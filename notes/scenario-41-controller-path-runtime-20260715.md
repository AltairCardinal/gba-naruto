# Scenario 41 controller-path runtime（2026-07-15）

## 目的

Task 5 的 `scenario-41-start-row` 与 battle-entry 白框 checkpoint 都能稳定重放，但
`0x08073946/0x080739D8` 没有 fresh observer hit。本轮构建五点透明 observer，尝试先在
既有 `actionable-move-grid.ss9` 上证明 action-dispatch 运行时正对照，再决定是否测试
scenario 41。所有运行直接加载 savestate，没有重复从标题、木叶或准备菜单导航。

## 探针

诊断 ROM `build/scenario-41-controller-path.gba` 的 SHA-256 为
`253ab3a7b1fd28c5a70364422982e5032a03b951a2bb1e35c0c930f45ab6b93a`。
它复用 shared published-call ABI，观察：

- `0x08073946 → 0x0806F718`；
- `0x08073A16/2E/3E/4A → 0x08067158` 四个互斥 action-dispatch BL。

共享 counter 是 `0x0203F040`，五个 24-byte record 位于
`0x0203F060/80/A0/C0/E0`。每轮结束一次性 dump `0x0203F040` 起 192 bytes；单 dump 只
产生 `valid_records`，只有 baseline/final `compare` 才能产生 `fresh_records`。

## 尝试 0：配置失败

首次 guard 调用遗漏 Windows `PROBE_BROWSER`，在 Chrome 启动前以 child-exit/1 结束，
没有 result、截图或 dump，不能算浏览器实验。该 summary 路径随后被有效 baseline 覆盖，
所以这里只保留 `operator_recorded/raw_not_preserved`，不把峰值或后检冒充 raw 证据。

## 有效轮 1：actionable 零输入 baseline

从 `artifacts/runtime-checkpoints/actionable-move-grid.ss9`（SHA-256
`4821a3a6694d32871a23bbea6a93ba1724663cb4a3c6e5f691d4fd48a5635fac`）零输入重放：

- input audit `events=[]`；
- battle ID 41、map `242c0916`、foreground `battle-map`；
- 192-byte dump SHA-256
  `5d89f056865052bcb89c910d2d62872e029fb273c3db03f8968a52a41593c1b5`；
- event counter=0，五条 record 全无 valid value；
- guard raw `completed/0`，Windows Job Object，`degraded=false`，峰值
  `571.3671875 MiB`。

## 有效轮 2：actionable 短显式序列

从同一 checkpoint 发送交接中已有的显式序列
`KeyX,ArrowDown,ArrowDown,KeyZ,KeyZ`。五个事件的 down/up 全部完成，hold 125ms，
`automatic=0`。最终仍为 battle 41 / map `242c0916` / battle-map，但：

- final dump 与 baseline 的 SHA-256 完全相同；
- compare 明确 `freshness_evaluated=true`，`fresh_records=[]`；
- guard raw `completed/0`，Windows Job Object，`degraded=false`，峰值
  `550.484375 MiB`。

因此正对照本身为 `positive-control-not-proven`。按预设停止条件，本轮没有运行 scenario 41
零输入和单 A 两轮，也没有追加其他键。

## 结论与边界

本轮证明了 builder/decoder 可以被守卫运行并产生可比较 dump，但没有证明所选 actionable
后缀会经过四个 `0x08073A04` action-dispatch BL。不能据此推断这些 call-site 在所有教程
路径都不执行，更不能用零 hit 证明或否定玩家控制。

下一步必须先取得一个确实穿过 `0x08073A04` 的更早 savestate/输入边界，或静态上移到它的
checked upstream dispatcher。继续在 scenario 41 白框上猜 A/方向键没有信息增益。完整命令、
环境来源、raw hashes 与无法持久证明的 postcheck 字段见
`artifacts/runtime-checkpoints/scenario-41-controller-path-evidence.json`。
