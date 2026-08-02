# Group 2 自然入口停止证据（2026-08-02）

> 后续状态：本文记录的 supplemental/tool 49 路线仍被否决，但停止条件已由
> action 7“影分身术”的硬编码 handler 自然入口解决。完整 production A/B 见
> `notes/battle-effect-group2-pixel-ab-20260802.md`；当前 Group 2 不再是路线 blocker。
>
> 后续静态上游补充：`notes/battle-effect-hardcoded-selector-producers-20260802.md`
> 已把 8 个硬编码 handler 与 13 个主动动作关联。本文否决 tool 49 和 supplemental
> state 冒充自然入口的结论仍有效；“没有 action binding”只限动态
> action→sequence 表，不再表示没有 handler-pair 上游。

## 结论

`artifacts/battle-effect-affine-runtime-v1/raw/state-0154.ss9` 仍是有效的 Group 2
affine supplemental 运行时输入，但它不能升级为 production 自然入口。历史来源目录名
包含 `tool49-component-trace`，不能证明 tool 49 到 Group 2 的数据流；当前静态绑定反而
明确证明 tool 49（encoded action `0xB1`）在 `0x0853E647` 选择 sequence 6。sequence 2
才绑定 Group 2，但它的 `runtime_state_values`、`active_action_ids` 和
`ninja_tool_ids` 均为空，只剩 11 个 `MOVS r0,#2` 的硬编码 selector callsite 候选。

因此，后续 Group 2 production 像素 A/B 必须从这些硬编码 caller 的真实游戏上游重新
建立自然输入链；不得把 tool 49、历史目录名、受控 WRAM 前提或 supplemental phase
capture 冒充自然入口。该要求现已由 action 7 handler `0x0807E1C8` 的自然确认页链满足。

## 受守卫零输入续跑

新增 `tools/run_macos_mgba_replay_current.py` 后，从上述输入在 accepted current desktop
mGBA profile 下零输入运行 600 帧：

- 输入 SHA-256：`60028c26e1a529c9542b1e9644dcd35d341cfcfe593cde1b3359c1e2817e3c93`；
- 输出 state SHA-256：`e9eab9bd2ccf64225f0143c2d4b15937e63c7c3e2300f1850dbe23c9fc3fe85c`；
- 输出 PNG SHA-256：`0bba919d21f7327ccdda72ac2b5212a932c87a8da689ed51d9b94033cf6031d5`；
- guard 为 `completed/0`、non-degraded，峰值 tree RSS `65.46484375 MiB`；
- owned PGID 和 mGBA listener 均无残留；
- mGBA 正常生成的 32 KiB staged `.sav` 被记录为
  `2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc`
  后删除，源 ROM `.sav` 始终不存在；
- audit/sentinel SHA 均为
  `cd5a1d6cd53e93b2b6a038e42ff2233d5fa5200c6d33d8a75a0158b178b57bb5`，
  最终化 marker 再绑定两者。

输入时 unit slot 1 为 `+0xB0=1/+0xB1=49`，Group 2 task 位于 slots
`[123,124,126]`；输出已回到战斗“请选择人物面对的方向”提示，battle control 仍为
`000f0000000000000300000194420202`，但 `+0xB1` 已变为 0，Group 2 task 为 0 个。
这证明该输入可以稳定结束动画，却不能在结束边界原样重触发 Group 2。

## 可复用快照与归档

完整运行、frame-600 快照、PNG、guard、audit/sentinel、最终化 marker 和机器可读
`route-audit.json` 已由实验生命周期完整归档：

- `build/experiments/archive/battle-effect-group2-route/2026-08/20260802-02.tar.gz`
- archive SHA-256：`2e8dc1ed6d4424ed98e87139b62880aa82e84e62c46d8f3ea81ecee08d1b1d32`
- sidecar SHA-256：`d16a5ac665a8a7ced2ac2ed17e80fa66227cd96115f18d2da51d31b35fa2fddf`

需要继续诊断时应从该归档提取 `frame-0600.ss9`，无需重放 600 帧；它只允许作为
supplemental 战斗面对方向边界，不允许成为 Group 2 自然生产证据。

## Runner 安全边界

current runner 固定 accepted profile 与仓库零输入 Lua，不提供 legacy manifest、
pre-script、自定义 script 或 evidence-mode 参数。TDD 还覆盖：

- legacy runner SHA 保持不变；
- source `.sav` 前后均 fail-closed；
- staged `.sav` 哈希、记录和删除；
- audit/sentinel 先写临时文件，第二次替换失败时两者回滚为 raw payload；
- `<audit>.finalized.json` 最后提交两份最终哈希；
- profile、binary、ROM、state、staged ROM 与 Lua 在最终化前重新哈希；
- guard、PGID 和 listener residue 必须全部通过。

相关 43 项 runner/guard/residue 回归测试通过；其中失败注入还证明第二个临时
payload 在 staging 阶段失败时不会遗留 `.tmp` 文件。
