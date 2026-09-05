# 历史 artifact 提交验收迁移（2026-09-05，进行中）

最新状态：**包已独立验真、重建、promote并完成授权提交A，历史目录待B提交**。
A为`47d9a60e668a5c3fe6e1123524864d21a2c93545`，91个精确文件，通过显式启用的
`.githooks`门禁。完整三成员包身份和64根分母已填入contract；干净A检出48项测试和
bundle verifier也通过。主index为空；下面“pins为空”等描述均保留为此前失败关闭状态。

修复后的formal106/106、ROM96/96通过，globalfalse/175；candidate-v4独立验真成功，
282inputs/72,618,549raw bytes、64roots/160members、32/21/11桥梁。新private tree为
`f7cac66c107a9ec129608188235117f5379a3c70`，816变化，只供候选读取，不是已提交证据。
正式包`artifacts/rom-legacy-acceptance-20260905-v1/`三成员摘要见合同文档；重建输出
与原snapshot逐字节一致，连续两次verifier报告SHA均为
`42e1d5628834efdf871a175d20feeba66d915b63daae66d669ac710f9821577c`。
迁移实验已随promote完成。两阶段提交和clean checkout验证的新run为
`build/experiments/active/committed-artifact-acceptance/post-selector-repair-20260905/`。
本次promotion前余额used26，可验证余量74%；未用reset credit、未push。

## 方法与已验证结果

复用不可变 Git tree、既有 coverage/formal 收据和独立 verifier 模式，保持旧 manifest
原字节。Sol medium 只读查提交闭包及 P0/P1；Luna max 在公开冻结的11份 gzip/raw
小包上流式复核，11/11成功、只声明输入身份。本体负责全部写入与TDD。

旧清单遗漏8件必需成员：CGB/M4A/MP2K三类4份precoverage gzip，以及2份启动framebuffer
bin和2份PNG。原 manifest 分别通过 `coverage.archive.file` 与 `source_bin/preview_png`
关联，独立 verifier 实际读取并要求完整文件集合；不是可省略的附件。

修正后64个历史目录共有160个成员/36,034,696 bytes，桥梁32 direct、21 aggregate、
11 immutable baseline。新 private tree `3592d3f6adeec5ddf67d30d169526fcae5fc73c5`
还补入 formal 完成后新增的三个永久收据和迁移代码，共772个候选变化。
`commit-closure-candidate-v4.json`扩展到了完整已跟踪目录库存（大量clean依赖），
不能把8,691个总路径当成实际变化；stage时始终只选真实变化。

候选包 `candidate-v3/`有282个冻结输入/72,617,940 raw bytes：
- catalog SHA `80a3e2af30833f8d9628b3c91f298959d34fad3eb4bdd23ae6c79a253c772358`
- snapshot SHA `cfd36f7fca049f4e576265f5622d4dbfb4accc6ccbe35346fdf131d869bc06b5`

它只是失败候选。后续coverage修复会使这些输入失效，不能把它晋升或消费为授权。

## TDD 与失败证据

实验根：`build/experiments/active/legacy-artifact-acceptance/post-story-v1-20260905/`。
所有编号日志/guard保留；没有覆盖旧失败。

- verifier初始RED→9项GREEN，随后隔离Python flags、明确success、完整包固定身份
  分别RED→GREEN。输入哈希链、重复键、path/mode/base64/gzip、selector、失败formal命令
  及coherent重写都覆盖。
- staged policy RED复现既有schema拒绝与authority变更未检查；GREEN使用冻结baseline/index
  及实际运行模块身份。后续RED复现部分旧根提交与无关现代目录受阻两个P1，已补完整批次
  和仅固定legacy根触发规则。
- 首次真实检查重复解析同一payload，120秒idle-timeout；并发测试被heavy lock拒绝且没有
  子进程。这两份guard均保留。新增失败测试复现重复解析后缓存单次snapshot内的JSON/摘要；
  相同输入重试仅4秒即给出真实元数据错误，peak约295MiB。
- 最新测试与状态以 `batch-scope-green.log`/guard为准。源码compile及改动diff whitespace
  检查通过。当前未运行本次修复后的新的full coverage/formal。

## 阻止验收的真实问题

独立迁移检查发现sprite-component selector `/packet_records/0` 无法在原payload中解析。
追溯 `_fast_audit_four_packet_claims` 后确认，四个fast-audit包116条claim都使用了不存在的
虚拟键。全量只读扫描又发现V10的7条代码claim使用基本块序号索引只有两项的合并区间；
其中5条越界，前2条虽能解析也不对应claim范围。

本体选择修正原生成器与canonical证据，而不增加兼容例外。目标仅修复123个selector，
classified/unknown/claim/segment数、ROM范围和全部旧artifact成员都应保持一致。
迁移暂缓直到修正后的coverage/proof/formal重新验收。当前106/96成功是旧合同执行事实，
不覆盖本次新增的selector独立检查；仍不得宣称100%。

修复实验：`build/experiments/active/evidence-selector-repair/fast-audit-20260905/`。
里面保存canonical、proof、auditor与原测试完整before副本，以及selector-scan-v1。
指向verifier源码的168个selector属于输出报告域，不能当JSON artifact错误修掉。

## 恢复

### 正式验收运行期间的收据域修正

迁移 verifier 现只消费 `notes/evidence/rom-evidence-selector-repair-20260905/`
下的正式收据；新增RED确认旧实现仍查旧域，随后GREEN确认修复后的域被接受、旧域被拒绝。
`selector-receipt-domain-*.{log,json}` 保留本次红绿证据。17项轻量合成测试与58次包含
既有Git门禁回归的测试执行通过（后者包含重复加载的基类测试）；没有运行ROM verifier，
也没有修改正在formal执行的coverage/proof/auditor输入。contract pins仍为空。
正式新收据尚未完成，实际迁移包依然未接受。

另由本体TDD和Sol medium只读复核关闭重建CLI输出未绑定漏洞：旧实现仅绑定catalog，
压缩结果SHA/size不符时仍成功；最小补丁又由`None`和mode变异测试抓住缺失pin旁路。
最终在创建输出前要求完整snapshot pin与最终字节身份。`rebuild-output-pin-red.log`、
`rebuild-null-pin-red.log`、`rebuild-pin-schema-red.log`及最终
`rebuild-pin-schema-green.{log,json}`保留全部红绿过程；最终18项相关合成测试通过。
这是归档构造合同修复，不是新增ROM语义证明。

先重新检查Goal、账户、存活代理、Git和heavy lock。2026-09-05 08:16Z主额度used24，
可验证余量76%；没有使用reset credit，没有push授权。先完成selector TDD与新canonical
证据链，再重建迁移候选，复核后执行合同文档中的A/B精确本地提交。
