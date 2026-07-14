# Brainstorm Summary

- Change: close-scenario-41-battle-runtime
- Date: 2026-07-15
- Confirmation: 用户已授权所有确认事项由执行者依据证据自行判定；本设计按该授权确认。

## 确认的技术方案

采用“快照阶梯 + 分阶段透明 observer + 原生 mGBA 严格只读调试”的混合方案：

1. 浏览器模拟器只负责实例内按钮输入和 `.ss9` 生产，不使用全局键盘注入、焦点抢占或 Windows `PostMessage` 作为证据输入。
2. 从自然 scenario 41 准备菜单链中，以 `build/natural-s41-menu-index2.ss9` 作为当前最可靠的 pre-hook 候选；先验证其零输入稳定性、前台画面、WRAM 不变量和来源哈希，再迁入 `artifacts/runtime-checkpoints/`。文件名与真实 UI 不一致的 `natural-s41-start-prompt.ss9` 不得作为 canonical prompt。
3. 每个目标边界只使用最近的前置快照，并把玩家选择、MOVEDONE、胜负链和 postbattle 分成多个小型 observer ROM；每个 ROM 只覆盖已校验的直接调用点/安全 cave，避免一个 ROM 堆叠过多 hook。
4. 玩家控制首先从 canonical “开始任务”行检查点执行单一 A 输入；只接受 checkpoint 加载后新鲜的 `0x08073946`/`PCO1` 命中，并同时要求 scenario 41、前台战斗画面与当前玩家单位一致。strict battle arrival、旧 scratch 或已越过 hook 的零命中都不构成结论。
5. 原生 Windows mGBA 只承担 savestate 复放、GDB breakpoint、寄存器和分块内存读取。探针必须在连接前确认端口未被占用，验证会话对应本次 ROM/进程，严格解析 stop packet 并校验 PC/地址；清理时不发送可能影响其他 endpoint 的 `k`，只终止本次拥有的进程树。
6. 玩家控制通过后，依次固化 player-turn、turn-1-complete、victory 和 postbattle 检查点；每一级必须由自然输入和本级地址证据成立，不能用后级状态倒推前级。

比较过的方案：

- 原生 mGBA-only：资源较轻、断点精确，但官方 Windows 0.10.5 的定向输入未建立，`PostMessage` 已有失败证据，不采用。
- 浏览器-only：实例内输入可靠，但缺少独立 PC/寄存器检查且 Chrome 树更重，不作为唯一证据通道。
- 混合方案（采用）：输入、快照与调试各自使用已证明最可靠的通道，代价是需要严格维护快照谱系和 ROM/状态哈希。

## 关键取舍与风险

- 快照可以显著减少重复导航，但只允许从目标调用之前的已验证边界继续；文件名、屏幕分类或残留 battle/map 内存不能代替来源证明。
- observer 必须保存调用约定并使用 publish-last magic；运行时证据还需记录 checkpoint 后 baseline、递增命中和事件顺序，排除 savestate 携带旧样本。
- mGBA 固定 GDB 端口存在误连风险；使用“启动前端口空闲 + 子进程存活 + ROM 指纹校验 + 不发送远端 kill”缩小所有权边界。
- `mgba_gdb_probe.py` 的 Windows 键盘注入能力将移除或明确隔离为失败实验，不进入正式证据链。
- 现有 screen classifier 会把转场残片判成 battle-map；前台截图、稳定帧、formation/battle/map 与精确 hook 必须共同判定。
- 所有重任务必须通过共享 heavy lock 和 owned-process-tree guard，运行前后记录系统可用内存；只清理本项目本次任务创建的树。

## 测试策略

- GDB 客户端：先写失败测试覆盖端口占用、错误会话、stop packet/PC 不匹配、NACK/checksum、256-byte 分块、子块错误、日志排水和 owned-process 清理，再做最小实现。
- Observer builder：补齐第二 hook/cave 篡改、hook/cave/scratch 不重叠、完整机器码和执行级寄存器/SP/LR 等价测试；胜负链只在静态确认调用约定后新增 wrapper。
- Runtime decoder/evaluator：用注入式 memory reader 验证 plan/settle 两循环地址与长度，覆盖 baseline 后新鲜命中、陈旧 magic、乱序、错误 scenario/map/unit 和假 battle-map。
- 快照清单：验证父状态、ROM/状态 SHA-256、单一输入、零输入稳定性、允许用途和“已越过 hook”拒绝。
- 集成：fake RSP 服务验证协议；已知可达 PC 做一次受守卫 native mGBA smoke；每个自然阶段都运行 base ROM control 与 observer ROM，比较用户可见行为和关键 WRAM。
- 完成验收：Python/Node/集成测试、OpenSpec strict validate、`git diff --check`、资源摘要和独立子代理证据审查全部通过后才提交对应阶段。

## Spec Patch

1. 为 `bounded-native-mgba-probing` 补充 GDB 会话必须属于本次启动进程、端口占用时 fail closed、stop packet/PC 必须匹配目标以及禁止向不明 endpoint 发送 kill 的场景。
2. 为 `scenario-41-battle-runtime` 补充 checkpoint 后 baseline、新鲜命中/事件顺序和单一显式输入约束，防止自动 settle/recovery 输入或 savestate 旧 scratch 形成假阳性。
