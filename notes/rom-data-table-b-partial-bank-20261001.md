# data-table-b 消息 0 部分字段合同与可移植重放

## 可用入口与结果

在逆向工作树执行：

```sh
python3 tools/verify_data_table_b_partial_bank.py --root .
```

成功输出 JSON：verified=true、cells_total=79、cells_covered 只有
record_id="0" / field_id="text_ptr"，其余 78 个单元显式列入 cells_uncovered；
changed_pixel_count=928、exhaustive=false。等待执行完成即可，缺文件、输入身份漂移
或原始证据不一致时输出 verified=false/errors 并 exit1。没有游戏页面或编辑器入口变化。

这是历史两次采集的离线重放，不是新的 mGBA 运行。旧样本从 action7 影分身确认快照
按 A，selector hook=0x080985E2、renderer=0x08098290，观测各一次消息 0 消费。
0x5A2034 的 text_ptr 从 0x085A1580 换为记录 1 的 0x085A1598；两 probe ROM
只差 0x5A2034 的一个字节。ROM 重建、实际存档 scratch、16 字节文本前缀、
PNG 与存档内嵌画面及 928 个差异像素均重新计算。

zero_input_control_verified=false、historical_shared_lock_verified=false：archive
只有 baseline/candidate 两次采集，没有零输入对照，也没有外层共享锁命令收据。
两旧 guard 的完成、posix-process-group、非降级和约 109MiB RSS 身份通过，但不能
补称它们遵守了当前锁合同。尚未验证其余 78 条自然路径、完整语言解码、编辑安全
或实体 GBA。旧 natural_route 声明保持历史样本范围，不提升为现行完整运行时验收。

## 输入、复用与可移植身份

任务模式为登记表的“冻结 runtime archive 样本的部分 record×field 合同迁移”。
使用可复现脚本，无子代理。冻结合同 tools/data/data-table-b-partial-bank-contract-v1.json
SHA=`c8f736cd52ff52bea19625304a47fb06f31f7e97baf0e233835e803811374fab`，22 项输入：
ROM、bank、旧 artifact 五成员、原实现十文件、checkpoint、probe 依赖与安全文件读取工具。
bank SHA=`5b8bf5e464c52dac97cd5522c079dea6e31527beb51ed4c0f8b07f934e2a7059`；
旧 manifest SHA=`fc0310e3f40d493ac0502d27bf2490817659999e32fa5bcade639f0699a50e9b`，未修改。

复用既有 build_probe、extract_raw、scratch/savestate 解析、PNG 比较、read_regular
及 auditor 的 _check_bank/_execute_contract。原 collector 同时要求当前 checkout
和 Qt binary 都在历史绝对路径，无法直接支持目录迁移；新 adapter 只替换这层
provenance 处理，并逐字段重建旧 evidence/launch JSON 与之精确比较。旧绝对路径
仍是固定采集来源，绝不将其改写为当前目录或打开它们。binary SHA 和 commit 只绑定
历史记录；离线重放没有“当前 binary 已执行”或外部密码学证明声明。

能力追加到现有 bank 验收链，不新增截图解析器、运行时框架或资源编辑 UI。
记录 ID、字段、ROM/bank/evidence/input 身份与 79 个单元分母由新 wrapper 补齐。
map-sprites 的受控物化路径与本包历史自然采集限制不同，不改其冻结 wrapper。

## TDD、集成与失败记录

先建立失败测试和 API stub，再运行红阶段，guard exit1。首次 guard 捕获了退出码但
没有保留子进程测试输出；该不完整记录保留，另以相同初始 stub 的隔离重放补齐日志，
13 项初始测试因未实现合同失败。最小实现后，macOS /var 临时目录 symlink 与严格
文件读取不兼容的两轮失败保留；仅对自建临时目录先 resolve，再对每个输入使用
read_regular，最终转绿。重构复用已加载合同，避免一轮读取两遍冻结输入。

最终 14 项新测试 + 6 项旧 artifact 测试 + 3 项 probe 测试 = 23/23 通过。
覆盖全分母、旧 verifier 对照、目录迁移/真实 CLI、输入和合同漂移、缺文件/symlink、
原始 audit/输入/guard 篡改、存档 selector 与画面重算、launch/checkpoint 身份、
真实 auditor 接线、错误 ID 与伪造 exhaustive 标签拒绝。

额外将 22 输入、合同和新 CLI 复制到不同目录，子进程 audit hook 禁止读取源工作树、
历史采集工作树和旧 Qt binary 路径，并禁止启动子进程；结果 JSON 与原目录逐字段相等。
这验证的是 portable_offline_archive_replay，而非重新采集同样的游戏行为。

真实 auditor 的 CLI contract_ok=true，但 partial bank complete=false，保留 4 个局部
blockers。proposal.json 仅作候选，没有写入 sequel/bank-proofs.json。
成功阶段使用同 heavy lock，非降级，峰值约 126MiB。语法、空白和限定路径 diff 检查通过。
本包不新增 byte 分类，不触发 Tier-2，未重跑完整 formal、编辑器、硬件或 mGBA 运行。

## 持久证据与后续

[永久 receipt](evidence/rom-data-table-b-partial-bank-20261001-v1/)保存完整阶段日志、guard、
初始 stub、重放脚本、result/proposal、auditor、可移植结果及实现/测试/合同副本。
受管源 run 为 data-table-b-typed-contract/partial-20261001-v1。
永久脚本随后在独立 run 复验，result、proposal 与原 JSON 精确一致；4.14s、
124.43MiB、非降级。[独立重放收据](evidence/rom-data-table-b-partial-bank-portability-20261001-v1/)
绑定第一包 manifest SHA=eaa60ae4ddb01d98869c3748359c8a187bb8729b0a425c0ad79ff9eef261de68。
canonical/proof/bank-proofs 哈希均保持：unknown=87,631B，175 blockers 仍是历史正式结果，
有效 bank 正式 typed 合同数仍为 0。合同迁移不计新增自然覆盖或 ROM 分类收益。
未提交或 push，也未改 Butano 工作树。

下一包将已形成的 map-sprites、cutscene、menu-ui、data-table-b 部分合同集中重放为
统一 record×field 矩阵，检查共有依赖和全量门拒绝的原因，再决定小 bank 矩阵与资源
round-trip 的具体入口。避免继续逐像素拆包；四类样本的自然/物化/旧对照限制必须分别保留。

## 几分钟验收

- [ ] 执行上述 CLI → 1/79 单元、928 像素、exhaustive=false，78 个未覆盖单元。
- [ ] 查看 receipt/result.json → 零输入与历史共享锁均 false，当前 emulator 未执行。
- [ ] 查看 receipt/portability.json → 24 个文件移植，禁止源工作树读取与进程启动仍通过。
- [ ] 查看 receipt/auditor-integration.json → CLI contract_ok=true，完整 bank gate 仍 false。
