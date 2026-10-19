## Context

当前调查闭合为 32/32，但证据分布仍是 13 `runtime_verified`、10 `code_verified`、9 `disproved`。scenario 41 已有稳定 battle 41 表现和可操作目标网格快照，但该快照位于 `0x08073940/0x08073946` 玩家选择边界之后；从它加载新 ROM 时 scratch 为零只能证明检查点越过 hook，不能否定控制流。

本轮已验证 Windows mGBA 0.10.5 可加载项目 `.ss9`、通过 Qt GDB 端点读取寄存器/内存和设置断点；最小化窗口的定向 `PostMessage` 不能可靠改变 GBA KEYINPUT。浏览器模拟器的实例内 `buttonPress/buttonUnpress` 可可靠导航，但 Chrome 进程树更重。两条路径都必须受现有 Windows Job Object / POSIX process group、共享 heavy 锁和内存门禁约束。

## Goals / Non-Goals

**Goals:**

- 从真实存档逐阶段固化可复放快照，证明 scenario 41 进入玩家控制。
- 自然完成两回合教程，捕获 MOVEDONE、胜负检查、结果写入、battle 退出与 postbattle 状态。
- 形成 Windows 原生 mGBA 的有界 GDB 读取和断点工具，并与浏览器实例内输入互补。
- 为每个正结论保留紧凑 JSON、关键地址、输入路线、ROM/快照哈希和资源峰值。
- 以 TDD、集成测试、独立审查和范围明确的本地 commit 维持可持续调查链路。

**Non-Goals:**

- 不在本 change 内证明 level 2、训练点或 levels record A/B。
- 不升级其余 `code_verified` bank，不启动网页编辑器产品开发。
- 不用强制 WRAM 胜利位、作弊补丁或预载状态替代自然控制流证据。
- 不使用全局键盘注入或按进程名批量清理。

## Decisions

### 1. 以自然存档建立单向快照阶梯

从 `tutorial-ui-save.sav` 冷加载开始，在 PUSH START、Continue、木叶主界面、scenario 41 剧情、任务准备、开始任务、教学、玩家行动、victory 和 postbattle 边界分别保存 `.ss9`。每个快照记录来源、输入、SHA-256 和可见/内存分类；后续实验从最近的前置快照开始。

选择该方案而不是复用旧 actionable 快照，是因为旧快照已越过玩家选择 hook。选择逐屏快照而不是长固定延迟序列，是因为方向键和转场会丢失边沿。

### 2. 运行时结论采用双通道交叉证明

ROM observer 在已静态验证的直接 BL call site 发布 magic、hit count 和参数；原生 mGBA GDB 在相同或相邻 PC 设置断点并读取 scratch、battle control 和单位状态。正结论至少要求一个自然输入路径、一个精确地址证据以及与屏幕/状态一致的结果。

只观察屏幕、只观察预载 battle ID，或在已越过 hook 的 savestate 上得到零命中均不构成结论。

### 3. 输入与调试采用混合路径

Windows 与 macOS 原生 mGBA 负责 `.ss9` 快速复放、只读内存、断点和寄存器；Windows 用系统 TCP owner table，macOS 用 `lsof` 精确证明 GDB listener/connection 属于本次 child，二者都 fail closed。浏览器模拟器只负责 mGBA 窗口无法可靠接收的实例内输入。禁止 `SendInput`、焦点抢占和全局按键。mGBA 0.10.5 Qt-only `--script` backport 缺少脚本 breakpoint API，不能用空 Lua trace 替代 GDB 地址证据。

### 4. GDB 大区间读取固定分块

mGBA GDB 对大于 256 字节的单个 memory packet 返回 `E06`。逻辑读取必须按不超过 256 字节分块并按地址顺序拼接；任何子块错误都使整个读取失败并写出可操作诊断。

### 5. 自然胜利门禁按控制链逐级成立

玩家控制以 `0x08073940/0x08073946` 自然命中为首门禁；随后要求自然移动和行动提交命中 MOVEDONE，再命中 `0x0807444E → 0x080777FC → 0x08073068 → 0x08074FDA`，最终进入 `0xF400` postbattle。每一级都记录输入与前后状态，禁止用后一级状态倒推前一级已发生。

### 6. 所有重任务通过同一资源所有权边界

静态扫描、Chrome probe 和 mGBA probe 统一经 `tools/run_guarded.py` 与共享锁运行。只允许终止本次 Job Object/process group；每批前后检查可用内存并记录 owned-tree 峰值。失败摘要必须保留，不能因清理异常覆盖原始诊断。

## Risks / Trade-offs

- [快照捕获在按键或 DMA 中间态] → 每个候选快照先零输入重放并等待稳定，再作为前置状态；保留失败快照仅作导航线索。
- [固定 settle 帧与角色动画周期错位] → 不使用动画遮罩；在最多 600 帧的零输入采样中要求 frame `0/p/2p` 全屏 exact RGB 重现，再用两段独立 `p`-frame replay 复核 task/unwind/WRAM。无周期即保持 `not-proven`。
- [浏览器与原生 mGBA 时序不同] → 结论绑定 GBA 地址、WRAM 和 ROM bytes，不以宿主帧率作为验收条件。
- [observer 改变寄存器或返回链] → 对每个 wrapper 做精确机器码、literal、寄存器/SP/LR 保存和错误 ROM 测试，并由独立审查复核。
- [教程输入复杂导致重复成本] → 快照阶梯只向前扩展，成功边界提交到 `artifacts/runtime-checkpoints/`。
- [资源再次异常] → 共享锁、准入、树级 RSS、wall/idle timeout 和精确 owned-tree 清理保持强制；禁止无界全 ROM Capstone。
- [预览地图形成假阳性] → strict battle arrival 之外还要求玩家 hook 或可操作菜单/行动事件；预览状态明确记录为负证据。

## Migration Plan

1. 完成并审查 mGBA GDB 与玩家控制 observer 的测试和工具说明。
2. 从真实存档重建并验证最早必要快照，删除或忽略仅用于导航的临时 build 产物。
3. 从任务准备快照命中玩家控制，固化首个正证据与新前置快照。
4. 沿自然教程逐段扩展到 MOVEDONE、victory 和 postbattle，逐阶段创建范围明确的本地 commit。
5. 更新交接、路线图和 checkpoint README；将 levels 留给后续 change。

回滚仅删除本 change 新增的探针、测试和证据，不改动基础 ROM，也不回滚用户已有工作。

## Open Questions

- 任务准备菜单的方向键消抖状态位尚未完全命名；在正证据前需要用行为与内存双重判别第三项。
- 原生 mGBA 是否可通过官方脚本接口实现无焦点实例内输入仍待评估；当前不以此阻塞混合路线。
