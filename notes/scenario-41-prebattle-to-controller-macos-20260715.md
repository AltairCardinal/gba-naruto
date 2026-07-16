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
