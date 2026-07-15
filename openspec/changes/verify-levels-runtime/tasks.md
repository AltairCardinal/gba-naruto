## 1. 前置依赖与基线

- [ ] 1.1 校验 `close-scenario-41-battle-runtime` 的 victory/postbattle 证据已验收，并记录 checkpoint、基础 ROM 和紧凑证据文件哈希；依赖未闭合时停止本 change 的运行时工作
- [ ] 1.2 运行现有 bank audit，记录 `levels=code_verified`、当前 verification 分布及相关测试基线，确认工作树中的其他 bank 不在本 change 修改范围

## 2. 自然升级状态证据

- [ ] 2.1 先编写失败测试，覆盖 Naruto level/EXP、template `+0xBA`、`0x0200A880` 的解码、同一快照约束、依赖哈希不匹配和任一门槛失败时拒绝升级
- [ ] 2.2 最小实现状态采样与证据判定，记录战前/战后 level 和 EXP 原始值，并验证 level 2、`+0xBA>0`、`A880==3`
- [ ] 2.3 在共享资源 guard/lock 下从依赖 checkpoint 运行到训练分配前稳定边界，固化 checkpoint、截图、资源摘要和紧凑状态证据
- [ ] 2.4 重构状态解码与判定逻辑，重跑相关单元及 runtime wiring 集成测试，确认未使用内存写入制造 level、EXP、训练点或 A880

## 3. Levels consumer 透明观察

- [ ] 3.1 先编写失败测试，覆盖四个 hook 的原指令/cave 校验、Thumb wrapper 机器码、寄存器与 SP/LR 返回链、独立 scratch、publish-last magic 和 savestate 旧值拒绝
- [ ] 3.2 最小实现 `0x0808E16E`、`0x08093698`、`0x08093070`、`0x080932CA` 透明 observer builder，并保证调用原函数后的用户可见行为与 control 一致
- [ ] 3.3 先编写失败测试，覆盖 runtime decoder 的新鲜命中计数、调用顺序、row type 4、有效 levels ID、record 地址/12-byte 原值以及训练点和次槽等级 before/after wiring
- [ ] 3.4 最小实现 runtime 采样与证据序列化，并接入所有实际 plan/settle 采样循环；无效 magic、陈旧计数、顺序缺口、type 或 ID 错误必须产生明确失败原因
- [ ] 3.5 在 guard 下加载训练分配前 checkpoint，执行自然确认输入，捕获四段调用链、自然 ID、`0x085459C8+ID*12`、`+6` 原值、训练点恰减 1 和对应次槽等级恰加 1
- [ ] 3.6 重构 builder/decoder 的公共能力并重跑聚焦单元、集成和 control 行为回归，确认诊断 ROM 只改 checked hook/cave 且未提交 build 产物

## 4. Record 加六字段单因素 A/B

- [ ] 4.1 先编写失败测试，要求 control/variant 仅允许自然命中 record 的 `+6` u16 从 `n` 改为 `n+1`，并拒绝错误 ID、错误基础值、越界、附加 ROM 差异或非同源 observer patch
- [ ] 4.2 最小实现 A/B builder 与逐字节 diff 清单，输出基础 ROM、control、variant、checkpoint、输入计划和目标 record 的哈希及元数据
- [ ] 4.3 先编写失败测试，覆盖同 checkpoint/输入/row/ID/采样窗口约束，以及 `base_a + per_level_a * (stored_level - 1)` 的预期差异判定和非目标条件一致性
- [ ] 4.4 在共享 guard/lock 下依次运行 control 与 variant，禁止并发重任务，保存两组命中链、状态快照、资源摘要和运行结果
- [ ] 4.5 比较实际输出与公式预测；只有目标差异成立且训练点消耗、row、ID、次槽选择等非目标条件一致时，生成 A/B 通过结论，否则持久化负结果并保持 `code_verified`

## 5. 收尾验证与状态同步

- [ ] 5.1 运行格式检查、相关 Python/Node 单元测试、runtime wiring 集成测试和 bank audit，并检查资源摘要及项目自有进程无残留；记录无法运行的验证及原因
- [ ] 5.2 生成可复验的紧凑 JSON 与调查笔记，写明尝试、结论、checkpoint/ROM 哈希、重要地址、自然 ID/record、失败处理和功能边界
- [ ] 5.3 仅在依赖、自然升级状态、完整 consumer 链和 A/B 全通过后，把 `sequel/content/levels/bank.json` 更新为 `runtime_verified`；否则保留 `code_verified`
- [ ] 5.4 同步 `docs/reverse-engineering-handoff-20260711.md` 与 `docs/sequel-roadmap.md`，从实际 bank audit 重新计算分布，并确认其他 bank 的内容和验证状态未改变
- [ ] 5.5 完成独立代码/证据审查并处理发现，最后重新运行 strict OpenSpec 验证与本 change 的全部验收命令
