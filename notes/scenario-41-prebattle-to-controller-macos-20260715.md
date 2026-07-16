# Scenario 41 prebattle 到 controller 的 macOS 证据记录（2026-07-15）

## Task 4.7 Step 3：Down candidate zero-input 复验并固化

2026-07-16 从 Step 2 candidate
`build/scenario-41-prebattle-down-20260715/after-down.ss9`（SHA-256
`c1a16fa3fd505c5a4aeb3e593f639c26342c5048d5d506771aa9a6ad6418e449`）执行了唯一一次
受 heavy guard 的 fresh、80-frame、zero-input 重放。run ID 为
`7d378580de56bea13a3d0e09b8bea185`；没有发送 A，也没有进入 Step 4。

重放以 exit 0 完成；guard 为 `completed/0`、非降级 POSIX process group、PGID 41717、
peak RSS `52.09375 MiB`。运行前可用内存 `4991.793 MiB`，运行后
`5083.738 MiB`；前后均无 mGBA/QEMU 进程或监听，heavy lock 可取，
`rom/base.sav` 不存在。

画面与离线状态稳定：candidate embedded image、Step 2 PNG、zero output embedded image、
zero PNG 的 normalized RGB 均为 240×160、115200 bytes、SHA-256
`1e68324b6496cda1dc4cff6821a1c6b86dbfc422ac15fdfd1bcdfd0a9246352d`，人工检查无变化。
task 2 resume PC 同为 `0x08067D02`；显式 active-unwind slots
`0x03001220/0x03001240/0x03001278` 的 raw returns 同为
`0x080885C1/0x08088F9F/0x0808F92D`，静态 Thumb BL 分别解码到
`0x08067158/0x080884DC/0x08088F10`；`[0x0202680C]=0`。

final audit 与 sentinel JSON 相同，并满足既有 zero-input schema：`inputs=[]`、
`pre_scripts=[]`、`zero_input_verified=true`。该旧 schema 不要求 single-input runner 后增的
`automatic_inputs` 和 `recovery_inputs` 字段；本轮未修改 zero-input runner 或 Lua。

所有 acceptance gate 通过后，candidate 已按原 SHA-256 固化为
`artifacts/runtime-checkpoints/scenario-41-prebattle-down.ss9`，并登记到 checkpoint ledger；
compact 证据为 `artifacts/runtime-checkpoints/scenario-41-prebattle-down-evidence.json`。
接受边界仍仅是“一次 Down 后的 prebattle row 可被 fresh zero-input 稳定重放”：不证明
controller entry 或 player control，也不授权绕过 Step 4 的 A 规则。

完整运行命令、四路 fingerprint 命令、两条离线 inspector 命令、所有来源哈希和接受边界见
`.superpowers/sdd/task-4.7-step3-report.md`。

## Task 4.7 Step 4：单 A candidate 未通过 exact-pixel 稳定门

2026-07-16 从 tracked accepted Down snapshot 只发送一次 A（frame 5→13，hold 8），
得到 candidate `build/scenario-41-controller-a-20260715/after-a.ss9`（SHA-256
`43f19bf7b80f900be6d34bd4da3bdfc4daf206bd78da1e6e68754071bb40f6e8`），再只执行一次独立
80-frame zero-input replay（run IDs `189eeecb14a44e5998c8699812c6ffc2`、
`8f5fa1b2e3cc7a9ae72c4238dbc2d2ed`）。两次 input/guard/resource 门均通过；candidate 与 zero
output 的 task 2、三个显式 static-BL-valid unwind slots 和 `[0x0202680C]` 相同。

但是 candidate 与 zero output 的 normalized RGB8 pixel SHA-256 分别为
`29ad62a2e213ccb1db042fa73cc23d1c3d157c55e9755298e3daed8de8c1e005` 与
`56dd1650f49080a733376a92658ba718ab4876a1c69aa225449521f6b633e80f`；人工画面肉眼一致也不能
覆盖精确 hash 差异。因此 Step 4 结论为 `not-proven`，未执行 Step 5、未接受/复制 checkpoint、
未更新 ledger，也不声称 controller 或 player control。完整命令与证据见
`.superpowers/sdd/task-4.7-step4-report.md`。

## Task 4.7 Step 4C：以周期 19 的双段 zero-input 接受 A 后快照

Step 4B 的 600-frame diagnostic 找到最小 exact period `p=19` 后，2026-07-16
从原单 A candidate 独立运行 19 帧，再从第一段输出 state 独立运行 19 帧。两段
run ID 分别为 `dae5070e1b87e5d58dae0137888f9c57` 与
`b5fa01bd561aff630ebb88148ad12131`，均为现有 replay runner 的
`evidence_mode=zero-input`，没有 pre-script，audit/sentinel 均确认
`inputs=[]`、`pre_scripts=[]`、`zero_input_verified=true`。

原 candidate、19 帧与 38 帧 state 内嵌画面及两张输出 PNG 均严格解码为
240×160 RGB8，115200 bytes，normalized full-screen pixel SHA-256 同为
`29ad62a2e213ccb1db042fa73cc23d1c3d157c55e9755298e3daed8de8c1e005`。
三状态 task 2 均为 SP `0x030011FC`、resume PC `0x0806F996`；显式 active-unwind
slots `0x03001234/0x03001240/0x03001278` 的 raw returns 均为
`0x0807513F/0x08089029/0x0808F92D`，并分别由 base ROM 静态 Thumb BL 解码到
`0x0806F718/0x0807509C/0x08088F10`；`[0x0202680C]=0`。

两轮 guard 均为非降级 POSIX process group 的 `completed/0`，owned PGID
`24663/25620` 与 mGBA listener 均清洁；运行前/中/后可用内存分别为
`5526.672/5448.816/5535.855 MiB`，`rom/base.sav` 始终不存在。预先存在的用户
Chrome PGID `95724` 不属于项目 owned tree、不持有 heavy lock、没有相关 listener，
按父级审计结论排除且未终止。

全部门禁通过后，第一段输出已固化为
`artifacts/runtime-checkpoints/scenario-41-pre-controller-after-a.ss9`，SHA-256
`1fbfc94cd08a89a4fbf2d806c62cb2739407780c658fb48ab8fd82bf8ddbe646`。
lineage 为 accepted Down → 唯一 A → zero settle 19，compact evidence 为
`scenario-41-pre-controller-after-a-evidence.json`，ledger 明确
`allowed_evidence=[]`。活动 unwind 不含 `0x0808F957`；因此该结果仍不证明
controller entry 或 player control，且本步没有进入 Step 5。

## Task 4.7 Step 5：B/B 后 Down 无状态效果，controller entry 仍 not-proven

2026-07-16 从 accepted `scenario-41-pre-controller-after-a.ss9` 按已静态核对的
base-ROM 控制流分段执行 B → B → Down。第一 B run
`f49c95b60c74956e337ca99bfef895c6` 后，以 fresh zero-input run
`e2262b1d2b884aa0fbe7b93699068d86` 复核；第二 B run
`56cf8aea33052f3a2f8541255a451bc6` 后，以 fresh zero-input run
`d6b4f692b5bd34a6bca9dc140d9ee201` 复核。两个边界的全屏 RGB、task 2、显式
static-BL-valid unwind 和 `[0x0202680C]` 均分别稳定，第二 B 边界 task 2 resume PC 为
`0x08088628`。

从第二 B 的 zero-verified state 发送唯一 Down（run
`53a895bae7cd13282d9d8ea8bb5a1a23`，5/13/80）后，task 2、全部 task context、
`0x03001224..0x030012A3` task stack、`[0x0202680C]` 与 normalized RGB
`a2673d496209f1147145e3b16cf0edf31a4ddf4e58d09f59b0e53ad94b5310b0` 均未变化。
按计划仅允许从相同 input state 延长 capture 重试一次；160-frame run
`9203a9c0a12b04d2557f8162e8a0e1ce` 仍完全相同，因此不能证明 Down 改变 selection/result。

所有六个 run 均为 base ROM、独立 fresh 目录、guard `completed/0`、非降级 POSIX process
group；owned PGID/listener 清洁，`rom/base.sav` 前后不存在。peak RSS 为 51.785–52.0 MiB，
由于固定 runner 没有 guard sampling interval CLI，这些值明确只作为 1 秒粒度 coarse
sampled peak。base ROM `0x0808F952` 的字节 `e3f7affc` 静态解码到 `0x080732B4`，但
活动 unwind 没有 raw `0x0808F957`。

因此停止门已触发：未发送 final A、未创建或运行 entry observer、未创建
`scenario-41-controller-entry.ss9`，也未进入 Step 6。紧凑证据为
`artifacts/runtime-checkpoints/scenario-41-controller-entry-evidence.json`；它只证明本次受限
尝试为 `not-proven`，不证明 controller entry 或 player control。
