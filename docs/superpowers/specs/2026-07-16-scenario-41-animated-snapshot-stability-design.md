# Scenario 41 动画快照稳定性设计

## 背景与结论

Task 4.7 Step 4 已从 accepted Down snapshot 只发送一次 A，并完成一次独立 80-frame
zero-input replay。两轮的 task 2、静态 BL-valid unwind 和 `[0x0202680C]` 一致，但全屏
normalized RGB8 相差 140 个像素，差异只位于 Naruto 动画区域。固定 80 帧没有对齐角色动画
周期，因此它不能证明候选不稳定，也不能被 task/WRAM 相等直接覆盖。

本设计采用**有界 exact-pixel 周期复验**：保持全屏像素门槛，不引入动画遮罩，也不绕过
稳定快照直接追 controller observer。用户已把该技术路径的选择与结果责任明确委托给逆向
执行者。

## 方案边界

### 采用：有界零输入周期搜索

从 Step 4 的单 A candidate 重新加载，连续 600 帧不发送任何输入，并在每帧保存 PNG。
离线归一化为 240×160 RGB8 后，寻找最小 `p`，满足：

- `1 <= p <= 300`；
- frame `0`、`p`、`2p` 的全屏 RGB8 像素 SHA-256 完全一致；
- frame `0` 使用 candidate savestate 内嵌屏幕与 Step 4 PNG 的一致指纹；
- 搜索只产生诊断结论，不接纳 checkpoint，也不证明 controller/player control。

600 帧上限提供两个完整候选周期窗口；找不到满足条件的 `p` 时，本轮继续保持
`not-proven`，不得进入 controller gate。

### 不采用：动画区域遮罩

遮罩方案允许已知角色区域变化，但会把“差异是否仍属动画”的分类器引入正证据门槛，存在
边界扩张和假阳性风险。当前无需承担该复杂度。

### 不采用：跳过快照直接追 observer

fresh observer 可以证明一次运行中的 controller entry，却不能提供后续教程、胜利和
postbattle 调试所需的可复用前置快照。它继续保留为 controller acceptance 的地址证据，
不能替代快照稳定性。

## 组件与数据流

### 固定 zero-input frame sampler

新增固定 Lua sampler 和 macOS runner。Lua 只加载 caller-known savestate，在 frame 1..600
逐帧调用 `emu:screenshot`，每 30 帧输出一次进度，frame 600 写出 audit/sentinel 后退出。
脚本不得出现 `emu:addKey`、`emu:clearKey`、`emu:setKeys`、pre-script、adaptive、recovery 或
settle 输入。audit 固定记录 `inputs=[]`、`pre_scripts=[]`、`zero_input_verified=true`、
`evidence_mode=zero-input-cycle-sample` 和 `max_frame=600`。

Python runner 复用现有 replay 的 caller-known binary/manifest/patch/ROM/state SHA、fresh
output、staged save 隔离、heavy lock、4096 MiB admission、1536 MiB owned-tree RSS、
wall/idle timeout、guard summary 与 exact PGID/listener 清理。600 张 PNG 只保存在忽略的
fresh build 目录；任何缺帧、重复路径、hash drift、非零 child、guard 失败或资源残留均使采样
失败。

### 周期分析器

runner 使用现有 strict PNG decode 与 normalized RGB8 fingerprint 逻辑，对 candidate 的
frame 0 和 600 张采样图建立 hash 序列，选择第一个满足 `H[0] == H[p] == H[2p]` 的 `p`。
分析 JSON 记录 caller-known 来源、600 帧完整性、每帧 hash、所选周期和三个匹配点；没有周期
时显式输出 `not-proven`，不得选择近似匹配或局部像素匹配。

### 两段独立 acceptance replay

周期搜索只决定候选 `p`。真正接纳必须继续使用未修改的
`tools/run_macos_mgba_replay.py --evidence-mode zero-input`：

1. 从单 A candidate 零输入运行 `p` 帧，得到 `state-p` 与 `png-p`；
2. 从 `state-p` 再零输入运行 `p` 帧，得到 `state-2p` 与 `png-2p`；
3. 验证 candidate、`png-p`、`png-2p` 的 normalized RGB8 全屏像素完全一致；
4. 验证三个边界的 task 2 resume PC、显式 static-BL-valid unwind slots 和
   `[0x0202680C]` 完全一致；
5. 验证两次 replay 都是 empty input/pre-script、caller-known hash、guard
   `completed/0`、non-degraded POSIX process group、PGID/listener/base.sav clean。

全部成立后，`state-p` 才可作为 `scenario-41-controller-entry-candidate` 的稳定快照写入
checkpoint ledger。其 lineage 是 accepted Down → 唯一 A → 零输入 settle `p` 帧。该接纳只
证明稳定的 A 后边界；controller entry 仍必须在下一步由 raw return `0x0808F957` 的静态有效
active unwind 或 fresh observer 命中 `0x0808F952 → 0x080732B4` 单独证明。

## 失败与资源处理

- 单次采样最多 600 帧、约 13–20 MiB PNG；不得扩大为无界运行。
- 启动前检查可用内存，所有 mGBA 调用继续持有共享 heavy lock。
- 任何 run 被 guard 拒绝、超时、超过 RSS 或产生残留时，保存已有 audit/guard 证据并停止。
- 周期搜索、两个 replay 或离线 inspector 任一失败，都保留 raw build 证据并记录
  `not-proven`；不复制 checkpoint、不进入 Step 5、不发送新按键。
- 只清理本轮 owned PGID；不得按进程名终止 mGBA，也不得修改或删除用户已有 dirty 文件。

## TDD 与验收

TDD 必须先覆盖：固定 600 帧、禁止任何输入 API、600 张唯一文件名、每 30 帧进度、缺帧与
多帧拒绝、normalized RGB8 精确周期选择、无周期、只出现一次匹配、`p > 300`、caller-known
hash drift、guard/resource/base.sav failure。实现后运行 focused runner/analyzer tests、既有
zero-input/single-input/guard 回归、真实 ROM sampler，再运行两段 acceptance replay。

thorough reviewer 必须独立检查：RED/GREEN 证据、无输入 Lua contract、600 帧完整性、周期
算法、三个 exact RGB 指纹、task/unwind/WRAM、来源 hash、guard/资源清理，以及没有提前声称
controller/player control。
