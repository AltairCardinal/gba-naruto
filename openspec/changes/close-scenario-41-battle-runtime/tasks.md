## 1. 固化调查基线

- [ ] 1.1 审计当前未提交 probe、测试和 build 产物，区分可持久证据、临时导航文件与用户既有修改
- [ ] 1.2 记录 Windows mGBA 0.10.5 来源、版本、SHA-256、源码 commit 和可复现安装位置
- [x] 1.3 运行资源与内存基线检查，确认所有后续 mGBA/Chrome 命令使用共享 heavy 锁和 owned-tree guard
- [x] 1.4 在 macOS Intel 上以 TDD 验收 Darwin 内存/RSS 守卫，记录可脚本化 mGBA 0.10.5 x86_64 来源、哈希与构建资源摘要
- [x] 1.5 回移上游 Qt `--script` 到严格 mGBA 0.10.5，在 heavy guard 下零输入复放并验收 prebattle menu candidate

## 2. 完成原生 mGBA 与玩家控制探针

- [x] 2.1 以红绿重构完成 GDB RSP 寄存器、严格断点、错误输出和 256 字节分块读取测试
- [x] 2.2 以红绿重构完成玩家单位选择与当前单位双 observer 的精确机器码、literal、call-site/cave 和错误 ROM 测试
- [x] 2.3 让浏览器 runtime decoder 在 plan 与 settle 循环读取两个 observer，并补齐 wiring 回归测试
- [ ] 2.4 更新工具 README，说明原生 mGBA、混合输入、快照和资源守卫使用方法与失败边界

## 3. 建立 scenario 41 前置快照阶梯

- [ ] 3.1 从 `tutorial-ui-save.sav` 冷加载并零输入复验 PUSH START、Continue 与木叶主界面快照
- [ ] 3.2 自然进入 scenario 41，捕获 opcode `0x08031D5F` 终止并固化任务准备菜单快照
- [x] 3.3 行为、内存与离线 task 栈共同确认“查看战场”和“开始任务”边界，保留 pre-controller 白框为负证据
- [ ] 3.4 固化位于玩家选择 hook 之前的“开始任务”或开场教学快照，并记录输入、ROM/状态哈希
- [x] 3.5 从 accepted prebattle menu 将 Down/A 拆成独立原生 mGBA 单键运行，每段先零输入复验并固化快照；仅以活动 unwind `0x0808F957` 或 fresh entry observer 接纳 controller entry

## 4. 证明玩家控制边界

- [ ] 4.1 从 hook 前快照运行双 observer，证明 `0x08073940/0x08073946` 自然命中且参数与玩家单位一致
- [x] 4.2 用原生 mGBA breakpoint 或相邻 PC 独立复核命中，并记录寄存器、scratch、battle control 与资源峰值
- [x] 4.3 在基础 ROM 或无 observer 对照上复放相同输入，确认探针未改变玩家可见行为
- [ ] 4.4 固化首个玩家控制检查点与紧凑 JSON 证据

## 5. 闭合自然行动、胜利与 postbattle

- [ ] 5.1 从玩家控制快照完成第一回合 `(4,4)→(4,7)`，捕获 MOVEDONE 与回合状态变化
- [ ] 5.2 固化回合边界快照并完成教程中断、朝向和防御选择
- [ ] 5.3 完成第二回合到 `(4,10)` 的自然行动，捕获胜负谓词与 result 写入链
- [ ] 5.4 证明 battle controller 经 `0x08074FDA` 退出并进入 `0xF400` postbattle
- [ ] 5.5 固化 victory/postbattle 快照，在基础 ROM 上零输入复放并生成紧凑证据

## 6. 同步证据与功能边界

- [x] 6.1 新增调查记录，写明尝试、结果、关键地址、快照来源和被否定的假设
- [x] 6.2 更新 checkpoint ledger、逆向交接和路线图，明确真实 controller entry、玩家控制、胜利与 levels 均尚未证明
- [x] 6.3 更新并运行完成度审计；证据门禁未成立，不改变任何 bank 的 verification 状态

## 7. 验证、审查与阶段交付

- [ ] 7.1 运行相关 Python、Node、集成、格式与 `git diff --check` 验证，并保存资源守卫摘要
- [ ] 7.2 对 probe ABI、快照来源、正负证据和资源清理做独立子代理审查并处理结论
- [ ] 7.3 清理仅由本轮创建的临时 build 诊断文件，保留已选定的持久快照和证据
- [ ] 7.4 检查 `git status`，按阶段创建聚焦的本地 commit，并记录 commit hash
