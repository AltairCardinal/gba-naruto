## Why

`levels` 目前只有静态代码证据，尚未证明 scenario 41 自然胜利后会产生 Naruto level 2、EXP、非零训练点并实际消费对应等级记录。必须以 `close-scenario-41-battle-runtime` 固化的胜利/postbattle checkpoint 为前置，从自然运行时链和单因素 A/B 两侧闭合证据，才能避免把“可达代码”误写为 `runtime_verified`。

## What Changes

- 以 `close-scenario-41-battle-runtime` 产出的真实 victory/postbattle checkpoint 为唯一入口；依赖未满足时不得启动 levels 结论升级。
- 捕获并固化 Naruto level 2、EXP、template `+0xBA > 0` 与 `A880 == 3` 的同一自然运行时边界。
- 证明运行时命中 `0x0808E16E → 0x08093698 → 0x08093070 → 0x080932CA`，并把地址命中、输入 checkpoint 与状态快照关联为可复验制品。
- 对自然命中的 levels record `+6` 进行仅改变该字段的 control/variant A/B，证明可见或可观测结果差异来自该字段，而非 checkpoint、输入或其他 ROM 字节。
- 仅在全部验收门槛通过后，把 `levels` 从 `code_verified` 更新为 `runtime_verified`，同步逆向笔记、交接文档和路线图；任一门槛失败时保留原状态并记录负结果。

## Capabilities

### New Capabilities

- `levels-runtime-verification`: 规定 scenario 41 战后等级状态、levels consumer 调用链、record `+6` 单因素 A/B 以及证据状态升级的运行时验收契约。

### Modified Capabilities

- 无。

## Impact

- 依赖 `close-scenario-41-battle-runtime` 的胜利/postbattle checkpoint 与证据清单。
- 后续实现会涉及受资源守卫的运行时 probe、对应构建器与回归测试，以及 `artifacts/runtime-checkpoints/`、`notes/`、`docs/reverse-engineering-handoff-20260711.md`、`docs/sequel-roadmap.md` 和 `sequel/content/levels/bank.json`。
- 不改变其他 bank 的验证状态，不完成剩余逆向工程，也不引入产品 API 或破坏性格式变更。
