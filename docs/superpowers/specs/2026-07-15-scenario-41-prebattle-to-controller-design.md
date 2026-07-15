# Scenario 41 prebattle → controller 分段设计

## 背景与已批准方向

`docs/reverse-engineering-macos-intel-handoff-20260715.md` 已明确要求：先接纳
`scenario-41-prebattle-menu-candidate.ss9`，再把旧的 “Down+A” 假设拆成独立候选；
任一步不清楚就停止。Task 4.6 已完成前半段，证明该快照在严格 mGBA 0.10.5 上零输入
80 帧稳定，当前活动 unwind 为
`0x080885C1 → 0x08088F9F → 0x0808F92D`，不含 controller return
`0x0808F957`。

旧 Task 5 已在提交 `2bd9760`、`ce67a8a`、`4949a86` 中实际执行并以
`not-proven` 收尾。它接纳了 start-row，但单 A 只到 pre-controller lineup；后续栈复核
没有否定 start-row 的 UI 稳定性，只否定了 controller/player-control 正证据。旧 raw
`build/task5-*` 文件不随仓库分发，guard 当时也不是可复核 PASS，因此不得重跑或改写成
新的成功证据。

## 方案比较

1. **分段原生 mGBA 输入（采用）**：复用现有严格 replay runner 的路径、哈希、guard、
   staged ROM、fresh output 与 PGID 清理，只新增固定 single-input Lua 和显式输入模式。
   Down、A 各自独立运行，每个候选先做零输入复验。优点是内存约 52 MiB、无需浏览器、
   输入审计可精确到帧；代价是需要 TDD 加固新的输入模式。
2. **复用浏览器 runtime probe**：已有按键审计，但历史运行约 540–620 MiB，旧 raw 证据
   已缺失，且 screen classifier 曾把 pre-controller 误当 controller。资源和误判风险更高。
3. **一次发送 Down+A**：最快，但无法判断哪一步改变菜单结果，也无法在失败时复用中间
   快照，违反交接文档和当前停止门。

## 组件与复用边界

### 固定 single-input Lua

新增 `tools/mgba_single_input_replay.lua`。它只接受 `Down` 或 `A`，只调用一次
`emu:addKey` 和一次 `emu:clearKey`，down/up frame 必须为正整数且
`down < up < capture`。capture frame 保存 state/PNG，并写出包含唯一显式事件的
audit/sentinel 后退出。现有 `tools/mgba_checkpoint_replay.lua` 与
`tools/run_macos_mgba_replay.py` 保持零输入字节、SHA 与行为不变。

### Runner 模式

新增独立 `tools/run_macos_mgba_single_input.py`，从现有 zero-input runner 直接复用
`ReplayError`、`canonical_input`、output alias/symlink 防护、manifest/binary/ROM/state
SHA、`emulator_command`、`guarded_command`、`validate_guard_summary`、post-run drift 与 exact
PGID 清理。依赖方向保持为 single-input runner → 通用的现有 replay helper，不让
zero-input runner 依赖输入逻辑。

zero-input runner 继续禁止所有 pre-script/input 参数，原有测试与 replay Lua SHA 不变。
single-input runner 只能装载仓库固定 single-input Lua；禁止任意 pre-script、多个键、重复键、
恢复键、自适应输入或 capture 后输入。最终 audit 包含一个且仅一个事件，并固定
`evidence_mode=single-input`、`zero_input_verified=false`、`automatic_inputs=[]`、
`recovery_inputs=[]`。

### 候选与验收

每个输入段使用 fresh build 目录，并保留 state、PNG、audit、sentinel、guard summary：

1. 从 accepted prebattle menu 发送单 Down，frame 80 捕获 Down candidate；
2. 离线检查画面、task 2、显式栈槽、`[0x0202680C]` 与输入/来源；
3. 从 Down candidate 用现有 zero-input 模式再跑 80 帧；只有画面、task/unwind、WRAM
   稳定才把 Down checkpoint 固化到 `artifacts/runtime-checkpoints/`；
4. 仅从 accepted Down checkpoint 发送单 A，再做同样的 zero-input 复验；
5. controller entry 只接受活动 unwind 包含 raw return `0x0808F957`，并静态解码
   `0x0808F952 → 0x080732B4`，或 fresh entry observer。screen/battle/map classifier 只能
   作补充，不能单独接纳。

任一步画面未变化、意外变化、输入数不为 1、hash/guard/PGID/监听失败，或无法给出受约束
的活动 unwind，都保持 candidate/not-proven 并停止后续按键。

## 快照、资源与失败处理

- 原始 ROM 旁不得出现 `rom/base.sav`；staged `.sav` 仅在 fresh build 目录。
- 每轮都经同一 heavy lock、`MIN_AVAILABLE_MIB=4096`、`MAX_TREE_RSS_MIB=1536`、
  wall/idle timeout 与 POSIX process group；记录 peak RSS，清理仅限 owned PGID。
- 有意义的 Down 中间点优先固化为 tracked snapshot，后续 A 从该快照加载，不重复序章或
  start-row 路线。
- build 原始证据可忽略，但 compact JSON、调查 note、checkpoint ledger 与 roadmap 必须在
  同一工作周期更新。

## 测试与验收

TDD 覆盖：零输入模式不回归；错误键/多键/帧序/任意脚本/错误 input audit/自动输入/hash
漂移/guard failure/PGID 残留全部 fail closed；single-input audit 与 Lua 静态契约；真实 Down
smoke 的输入、state/PNG、guard 与资源证据；候选的零输入稳定性；controller raw return 的
显式栈槽与 Thumb BL 静态验证。最终独立 reviewer 必须确认没有用画面分类替代 controller
门槛，也没有把 not-proven 升级为 player control。
