# 项目协作规则

## 持久记忆

本仓库是 ROM 逆向与续作规划的长期记忆，重要信息不得只留在对话中。

- 有意义的发现和有效工作必须形成仓库内的持久产物。
- 调查记录、内存映射和实验结果放入 `notes/`；稳定方案和流程放入 `docs/`；可复现实验放入 `tools/`。
- 有效调试方法必须同时记录方法、结果及关键文件或地址范围。
- 逆向结论变化时更新原记录；路线图进度变化时同步更新 `docs/sequel-roadmap.md`。

## 分支与工作树边界

- Butano 实现使用 `/Users/altair/github/gba-naruto` 的
  `codex/butano-foundation-research`；逆向工程使用
  `/Users/altair/github/gba-naruto-reverse` 的 `codex/reverse-engineering`。
- 两边需要复用成果时通过已提交 commit 精确 cherry-pick；不得直接复制整个脏工作树。
- 跨分支共享文档由当前集成人单点修改，避免两边同时写入。

## Goal 直接执行

- 自动续跑或继续既有 `/goal` 开发前必须检查 Goal 状态；非 `active` 时不得继续该 Goal 的写操作。用户当前消息明确要求的独立操作仅按其授权范围执行。
- 后续任务不使用 Comet 编排；Goal 直接按仓库交接、路线图、测试和运行时证据规划与执行。
- 规划按可验收里程碑拆分，不做过细实验切片、重复审查或微步骤编排；相邻的低风险输入和验证应合并为一个闭环。
- 恢复任务时重新读取 Goal 状态、交接/路线图、目标证据文件和 Git 状态，以文件事实为准修正过期状态。
- 本地 commit 仅按 Goal 或用户授权执行；push 始终需要单独授权。
- 收到新用户指令后，继续写入前必须重新检查 Goal、存活代理和 Git 状态；重新确认前产生的写入或提交视为未审计结果。

## 并发与子代理

- 共享工作区同时最多一个 writer；reviewer、日志分析和资料研究代理默认只读。
- 外派任务必须独立、非关键路径阻塞、上下文精简且结果可验证；否则由 Codex 本体处理。
- 原生子代理使用 `fork_turns: none` 并在提示词中写明目标、允许路径、禁区、验证命令、停止条件和提交权限。提示词约束不是权限隔离，关键写入仍由父代理复核。
- 当前工具 schema 未提供的模型、权限、路径或预算能力，不得声称已经应用。外部模型只做只读 sidecar，输出均由 Codex 用本地证据复核。
- 子代理报告完成不等于任务完成；父代理必须核对 TDD 红绿证据、集成测试、改动范围和 review 结论后，才能勾选 Comet task。

### 已验收的模式化分工

- 从已验真快照、manifest 和资源表批量推导候选参数时，优先让 `gpt-5.6-terra` 只读初筛；禁止其写仓库或启动 mGBA。本体必须用本地解析、画面重放和编码器逐项复算后才能采用。
- 同类候选超过一组时，先扩展数据驱动的 build/run/export/verify 脚本，再串行运行受资源守卫保护的 mGBA A/B；不得复制多套组专用流程。
- bank 玩家可见闭环先让 `gpt-5.6-terra` 只读盘点已有 consumer、快照和 runner，本体复核后优先复用自然快照；路线已证实时固定 baseline/candidate 两次运行，不先增加命中探针。阶段截图尚未显示刚提交的 OAM 时，应从 ack savestate 重放 Mode 0，不得据 PNG 同哈希误判无可见差异。
- 视觉 descriptor 闭环可让 `gpt-5.6-terra` 只读提出候选路线和 A/B 字段，本体负责断点验真并采用能完成归因的最小字段修改；候选建议范围大于必要范围时不得照单采用。已验证模板是“自然控制器快照 → 零输入 selector/initializer 命中 → 单指针两字节变化 → 固定两次 A/B → 六内存域与像素独立复核”。
- 通用 task 表已在自然快照中物化、但 task 已 inactive 且没有短自然重建路线时，先让 `gpt-5.6-terra` 只读枚举直接/间接 caller；本体完成零输入对照和最多一个有静态依据的重入候选后仍不命中，就停止导航试错。允许在明确标注 controlled 的实验中只恢复 active bit，并从 baseline/candidate ROM 表物化目标字段；必须同时命中真实下游 consumer、等待完整提交帧、核对六内存域与最终像素，且不得声称自然 loader 重入。
- 自然 savestate 已位于上游事件构造之后时，不得强求恢复后重命中已经过去的 producer；用 hash-bound checkpoint/静态链约束上游，再以 handler 入口和 `lr` 诊断真实 consumer，A/B 只签发本轮实际命中的下游边界。需要等待自然调度的 Lua 注册 callback/breakpoint 后应返回 mGBA 事件循环，不得用 `while ... frameAdvance()` 冒充自然运行；Terra 的候选字段仍须由本体先反汇编验证空值和调用约定。
- mGBA 启动异常可先让 `gpt-5.6-terra` 只读对比成功/失败 run 的 ROM、快照、工具哈希、guard 摘要和配置；禁止其启动模拟器或据缺少 audit 猜测 ROM 行为。本体复核后只做一次有新可观测信息的重试；stdout/stderr 未持久化时不得把 `idle-timeout` 归因为脚本或 ROM。
- 可执行代码 bank 闭环先让 `gpt-5.6-terra` 只读盘点已有调用链、受控 runner 和下游证据；本体必须重新反汇编确认完整函数边界，再用 TDD 修正 extractor。运行时优先从初始化前 hash-bound 快照恢复，以单条安全 immediate 的最小 A/B 同时约束入口/返回 PC、直接硬件状态和下游输出；瞬时寄存器差异不得扩张为持续静音、可听 WAV 或真机结论。
- 被动数据 bank 的自然 producer 难以到达时，先让 `gpt-5.6-terra` 只读盘点同类型真实 caller、上游快照和历史实验，本体必须检查输入快照中的目标状态与 observer 命中计数，拒绝“producer 已在快照前执行”的过期路线。可接受的 call-local 物化必须使用 caller 原本请求的类型、非零等级、单字段 ROM A/B，并在返回后证明 live slot 恢复；若最终画面相同，只能升级实际查询公式，不得声称自然解锁、玩家可见差异或真机行为。
- 工具 schema 未列出的模型（包括当前不可用的 `luna`）不得调用或声称已使用；能力可用性变化后方可重新验收。

## ROM 与资源安全

- mGBA、Chromium 和高开销静态任务必须经 `tools/run_guarded.py` 使用同一 heavy lock；只清理本次拥有的进程树。
- 启动前检查可用内存，运行中监控 owned-tree RSS；资源守卫拒绝、超时或内存异常时先保存证据并停止扩张实验。
- 冗长导航前及关键输入前后建立可复用快照，并先验证快照可恢复；后续实验优先从最近已验证快照继续。
- 读取历史 `.ss9` 前先核对状态格式版本；版本 `0xB` 使用本地 mGBA commit `c16c3ff55585e71bee83c95539c2ecde15d728c8`（binary SHA-256 `ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b`），不得把新版 mGBA 的加载超时误判为路线失败。
- 原生函数若在内部同步等待多个 VBlank，普通 Lua frame callback 可能直到函数返回才恢复；要捕获中间可见态，应在循环内稳定 CPU 地址计数目标 VBlank 后保存，不得用回调恢复时的晚帧冒充中间帧。
- 单次实验只改变一个输入，并保留零输入重放作对照；CPU 暂时为零不能单独证明进程挂死。

## 证据与验收

- 每次实验使用唯一 run ID，不覆盖原始产物；派生分析写入临时或新目录。
- 实验必须由 `tools/experiment_workspace.py init` 建立在
  `build/experiments/active/`；禁止直接向 `artifacts/` 生成候选文件。
- 只有带文件哈希和 verifier 成功证据的 `final/` 才能 `promote` 到
  `artifacts/`；新成果目录受 pre-commit 检查。
- 任务完成后显式 `complete`；维护任务只归档已完成实验，不触碰 active 实验。
- 结论必须关联输入、工具/ROM/快照哈希、关键地址和结果 manifest；失效结论标记为已取代，不删除历史证据。
- 完成前运行与改动匹配的格式、单元、集成和必要的运行时验证；无法执行的检查必须明确说明。
- `AGENTS.md` 只承担稳定行为约束；状态、权限、锁、预算和写入拦截必须由 Goal、Comet guard、hooks 或脚本实现，不得把文字规则当作硬隔离。
