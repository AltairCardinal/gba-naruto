# Cutscene secondary_ptr：自然胜利加载的 1/16 单元合同

## 当前结论与范围

第一表 record 1 的 secondary_ptr 已完成独立构建复验、五份正确共享锁的真实捕获、
运行时因果归因、受管 Tier-1 发布及真实 bank auditor CLI 接线。固定 bank 是 8 条记录
× primary_ptr/secondary_ptr 两字段，共 16 单元；本包只认领 1 单元，其余 15 单元显式
未覆盖。旧 primary_ptr 的自然胜利证据另存，不自动合并为整个 bank 已完成。

只有 PRAM 0x05000382 的一个字节 FF→E0，IO/VRAM/OAM/IWRAM/EWRAM 五域完全相同。
进入胜利画面后，文字的白色描边变青色，变化 778 像素，inclusive bbox=[42,49,195,110]。
输入基准的六域 SHA 和 RGB 与旧 primary_ptr 的自然胜利基准一致。三份零输入样本
的六域与 RGB 完全相同，排除了尚未输入时的变体差异。

这证明冻结快照、固定 A 输入、当前 c16 模拟器下的第一表 palette 加载，不证明任意
导航、其他 ID、第二表 definition/animation、完整 relocation 安全或实体硬件。没有新增
游戏菜单或编辑器入口；这是开发者可执行的验证工具。正式 coverage、bank-proofs 与
全局 proof 没有写入，unknown 87,631B / 175 blockers 仍是既有正式事实。

## 输入、方法与可复用链路

任务模式为“冻结资源指针单字段 A/B 与可恢复快照自然路径合同”，沿用登记表的脚本
优先方案，没有启动子代理。复用旧 build_pair、codec/layout/region/PatchSafetyGate、
独立 _lz77、savestate reader、renderer、auditor 及原子 NO_REPLACE 发布 primitives。
新 verifier 是独立语义边界：不能把第一表 palette 与第二表 animation 或旧纯观测
manifest 混用，因此保留独立工具，而不是修改已绑定身份的旧 verifier。

- 源 ROM SHA：1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b。
- 合同 `tools/data/cutscene-secondary-ptr-contract-v1.json`：45 个固定输入，SHA
  86886cace99036319a4b3ccfda5be7ac67b0cd96b5e5177d8d7962933e7010ba。
- 独立从旧父构建恢复完整 allocation ledger，重建两份 16MiB ROM，而非信任新 builder
  自报的结果。baseline=762ea679...fa5816，candidate=76974bcd...67c9d。
- 唯一字段位于 0x53DF7C：0x08BA0964→0x08BA12F0；两 ROM 仅 0x53DF7C/0x53DF7D
  不同。22B 新流在两份 ROM 中都位于 [0xBA12F0,0xBA1306)，独立解码为 32B palette；
  color1=0x7FFF→0x7FE0，其余颜色相同，透明 color0 不变。
- 输入快照 `artifacts/runtime-checkpoints/scenario-41-combat-popup.ss9`，SHA
  01f478cfafa2796cbe1652007c16e54480d2a289d1e6f54068ace8adc970300a，格式 0x01000007。
  c16 新捕获的五份输出均为 0x0100000B。输入和输出格式分别绑定，拒绝混用。
- c16 commit=c16c3ff55585e71bee83c95539c2ecde15d728c8，binary SHA=ef2386a5...d54b，
  同 commit 缓存库 SHA=0f84fde8...25b0b。仅进程内 DYLD_LIBRARY_PATH 选择经过 dlopen
  和 gitCommit 核对的库，不修改系统、旧 binary 或旧 manifest。
- 固定 Lua：zero 两份 baseline + 一份 candidate；single-input 各一份，A down5/up13，
  capture512。五个独立 run ID、case 文件夹、audit/sentinel/marker、guard 参数、残留
  检查与脚本身份逐项绑定。拒绝重复运行标识、额外按键或 --allow-degraded。
- 全部新捕获显式使用 `build/experiments/heavy.lock`，4096MiB 启动门槛、1536MiB
  owned-tree 上限，五个 guard completed/exit0/success-marker/非降级，峰值约 60MiB。
- baseline RGB SHA=051162ea4f830febd94823d2e87d75ad474223f352867e63fa0965912dbe7bc8；
  candidate RGB SHA=a279454f9ea1f124e9522cdcfa3e8372cd06977474751645d384b5713139f41c。

## 旧捕获已取代与文档更正

旧 `runtime-recovery-20261001-v1` 的五份捕获调用了 legacy guarded_command，它实际
选择 `build/resource-guard/heavy.lock`，与仓库统一锁不同。因此这五份捕获只保留为
历史观测，不进入本包；不能仅改收据中的锁字符串。本轮完整重跑五个 fresh run，
新源是 `runtime-shared-lock-20261001-v1`。错误锁的变异测试确保旧锁不能通过。
原 DYLD 崩溃、审计恢复、旧捕获和失败采集脚本全部原样保留在旧永久 receipt。

旧笔记曾把十进制地址手工转为 0xBA1FF0/0xBA2006、0x08BA1664，均已更正；机器
build manifest 的数值一直正确，原历史 receipt 不重写。输入/输出版本差异曾使新
verifier 误拒绝真实输出，现已修复；负测试仍明确拒绝把旧输入版本冒充新输出。

## 发布、失败处理与实际使用

受管 final：
`build/experiments/active/cutscene-secondary-ptr-contract/tier1-20261001-v1/final/`。
永久 receipt：`notes/evidence/rom-cutscene-secondary-ptr-shared-lock-20261001-v1/`。
工作包五个文件为 raw.tar（43 个原始成员）、evidence.json、两份 PNG、manifest.json。
不存两份可重建的 16MiB ROM。tar 只接受固定名字、普通文件、无重复/路径穿越的
canonical USTAR；先验完分母与字节再写入本次临时目录，不执行历史收据内的命令。

入口为 `tools/export_cutscene_obj_secondary_ptr_ab.py` 和
`tools/verify_cutscene_obj_secondary_ptr_ab.py`。exporter 仅向 init 且 active 的受管 run
写入新目录，显示结果以 final/ 和 accepted manifest 为准；等待期间是同步运行，没有
游戏 UI。缺数据、身份漂移、损坏截图、错误内存域、非法路径或非 active run 都失败
关闭；已有目录不覆盖，失败 stage 保留以便诊断。verifier 输出 JSON 和 exit code，
只有 verified=true/exit0 共同成立才成功，否则 errors 给出原因，不能当成空结果。

复验时先 init 独立受管 run，把下面的 `<active-run>` 替换为该路径：

```sh
python3 tools/run_guarded.py --summary <active-run>/verify-guard.json \
  --lock-file build/experiments/heavy.lock --cwd . \
  --min-available-mib 4096 --max-tree-rss-mib 1536 \
  --wall-timeout-s 240 --idle-timeout-s 120 -- \
  python3 tools/verify_cutscene_obj_secondary_ptr_ab.py --root . \
  --artifact-dir build/experiments/active/cutscene-secondary-ptr-contract/tier1-20261001-v1/final \
  --bank-contract
```

`--bank-contract` 将实际 artifact manifest SHA 纳入 JSON assertions。普通 artifact
report 保持位置无关，可复制后离线重放。partial-bank-proposal.json 只是一份离线
proposal；真实 auditor 接受结构化合同，完整 bank gate 仍因记录/字段非穷尽拒绝。
不以样本合同替换正式目录，也不提前增加正式 contracted-bank 数量。

## TDD 与验收状态

原始 source 先有 9 个 stub 红测试；纠正输入/输出版本后转绿。随后 3 个 hardening
反例先确认失败（额外 guard 参数、改 plan、重复 run ID），最小实现后 source 共
13 项通过。发布与审计 7 项在未实现 stub 上全部失败，再实现转绿；证据 manifest
绑定断言先红再绿。相关 31 项最终全部通过，含新 source 13、新发布 7、三个 builder
共 8、旧 primary artifact 3，最终 guard 非降级、峰值约 238MiB。

publication-red 至 red3 中的前几次属于测试基础设施错误（根路径缺失和测试类属性
遮蔽 unittest.run），不是有效功能红证据；全部保留。有效发布红证据是 red4。
完整 stdout/stderr 由 owned run_tests.py 直接落盘，避免 guard 的管道输出不转发。

已做四个新增 Python 文件的语法与尾随空白检查；没有配置专用 formatter，未声称
运行不存在的格式器。新五份 runtime、独立双重重建、真实 exporter/verifier CLI、
auditor 接线、NO_REPLACE、symlink/extra file、resigned evidence/pixels、恶意 tar 等
已验证。实体 GBA 和完整 formal 未运行；前者仍 external，后者没有新的正式晋升触发。
未 commit/push，未向 Butano 分支复制任何未提交成果。

## 后续顺序

先修复 menu-ui 因 renderer 身份漂移失效的旧样本，建立新冻结 receipt；再把仍有效的
旧 primary_ptr 证据迁移为独立的部分单元合同，明确与本包的交集和联合范围。
第二表的 definition/animation 必须沿自身消费者与 lifecycle 冻结，不能凭本包外推。
458 混合池的 flags/slot 生命周期仍是下一段字节分类主线。两个异构文本包仍只作
Tier-1 库存，未触发 Tier-2，不重复运行全量审计消耗额度。

## 几分钟验收

- [ ] 打开 final/baseline.png 与 candidate.png → 只有胜利文字描边变青色。
- [ ] 查看 verification.json → verified=true、778 像素、PRAM offsets=[898]（0x382）。
- [ ] 查看 partial-bank-proposal.json → 8 条记录、2 字段、1/16 覆盖、15 未覆盖。
- [ ] 查看 auditor-integration.json → contract_ok=true，完整 bank complete=false。
- [ ] 查看五个新 guard/launch → 统一 heavy.lock、非降级，三份 zero 无按键。
- [ ] 查看 canonical-identity.json → 三个正式身份未变；不把本包算作全局完成。
