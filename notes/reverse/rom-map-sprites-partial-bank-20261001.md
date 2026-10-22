# Map-sprites 部分 bank 合同 canary

## 结果和入口

旧像素 A/B 的 ID 1 / definition_ptr 已形成结构化、可重放的部分 bank 合同。
43 条记录 × 2 字段共 86 个验收单元，覆盖 1 个，显式未覆盖 85 个。
底层 archive、savestate、ROM 重建、OAM 和图片归因仍由既有独立 verifier 验证；
本次输出 213 个变化像素，bbox=[178,64,215,71]。

从逆向工作树执行：

```sh
python3 tools/verify_map_sprites_partial_bank.py --root .
```

成功输出一个 JSON，verified=true、cells_total=86、cells_covered 长度 1、
exhaustive=false。缺文件、symlink 或身份漂移时输出 verified=false/errors 并 exit1。
没有游戏 UI、加载画面或新增资源编辑入口；这是开发者验收工具，执行中等待 JSON。
自然 loader 重入、animation_ptr、其余 42 条记录和实体 GBA 均未验证。
controlled materialization 不升级成自然路径，verified=true 只表示这个固定样本通过。

## 固定输入和复用判断

冻结合同为 tools/data/map-sprites-partial-bank-contract-v1.json，19 项输入，SHA
`ed5482dce37d3baa7bdf69410839d8cab65dc5a01c34fa05c0a2ad5036cc2db2`。
包括 ROM、bank、旧 artifact 全部五个成员和旧 manifest 的 13 个实现输入；
wrapper 的源码和本次测试另外由 receipt 固定，proposal 中 script_sha256 固定实际 CLI。
bank SHA 为 52fae253049983323951b5c29b21e6960c6975c0348238947a8ec38efe474064。

直接复用 verify_map_sprites_definition_pixel_ab.verify_artifact，不重写截图或内存验证。
wrapper 只补 ID、字段、单元、bank/evidence/input 哈希及边界，另从 ROM 原始 pair
重建 43 条记录。现有 auditor 的 _check_bank 和 _execute_contract 直接复用，无需修改。
当前只有一个迁移 canary，不抽取通用 framework；其他 bank 消费者和控制路径不同，
后续确有共同合同需求时再抽取共享单元模型。该合同追加到既有验收链，不新增 runtime 链。

## TDD 与真实集成

8 项初始测试在未实现 stub 上因正确原因失败，再最小实现转绿。重构后新增两项
边界保护，最终 10 项新测试 + 9 项旧 artifact 测试 = 19/19 通过。
涵盖真实证据、source/bank/evidence/合同漂移、missing/symlink、错 ID 声明、
真实 CLI 成功/JSON 错误、真实 auditor 接线及伪造全量覆盖拒绝。
两个稳定结果逐字段相等；auditor 实际启动 CLI，合同断言全部通过。
partial bank 检查仍 complete=false、保留 5 个局部 blockers；仅将 coverage 标签和
数量改成 exhaustive，也会因 verifier 未绑定全量 ID/字段而拒绝。

同 heavy lock 下所有成功阶段非降级，最终峰值约 116MiB；RED exit1 是预期功能失败。
语法、空白、scoped git diff 与永久 receipt 全部成员哈希另行复核。
未重跑 formal/coverage，没有新的 mGBA 或硬件样本。

## 提案阶段和持久证据

[永久 receipt](evidence/rom-map-sprites-partial-bank-20261001-v1/)保存唯一 run 的日志、
guard、稳定 JSON、proposal、真实 auditor 集成结果及本次实现/测试/合同副本。
受管源 run 为 build/experiments/active/map-sprites-typed-contract/tier1-20261001-v1。
proposal.json 是后续里程碑的精确替换候选，没有写入 live sequel/bank-proofs.json。
所以正式矩阵仍 22 有效 bank / 2,954 条 / 23 声明覆盖 / 0 typed 合同；候选另有 1。
不能把合同迁移计为新增覆盖记录或未知字节收益，也不算第四个同类 byte packet。
旧 manifest、canonical、proof 均原样保持，unknown=87,631B、175 blockers 是旧正式事实。
未提交或 push。下一步复验 cutscene 的两类资源种子，并以真实控制路径决定批量矩阵。

## 几分钟验收

- [ ] 执行上述 CLI → verified=true，1/86 单元、213 像素，exhaustive=false。
- [ ] 查看 receipt 的 result.json → 85 个未覆盖单元，包含 ID 1 / animation_ptr。
- [ ] 查看 auditor-integration.json → CLI contract_ok=true，partial bank complete=false。
- [ ] 查看 proposal.json → 仅 ID 1 / definition_ptr，无自然 loader 或全量覆盖声明。
