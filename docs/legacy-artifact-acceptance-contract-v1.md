# 历史 ROM artifact 的固定身份验收合同 v1

**包已独立验真、逐字节重建并晋升；两阶段本地提交待执行。**
此前candidate-v3因真实selector错误被拒绝，修复后的candidate-v4已通过新formal关联检查。
正式目录为`artifacts/rom-legacy-acceptance-20260905-v1/`；完整三成员身份和64根分母
固定在`tools/legacy_artifact_acceptance_contract.py`，不能由未提交包授权自身。

本合同解决旧目录不能原样通过现代 promotion schema 的问题。它保留所有旧 manifest
及成员字节，使用一次已完成的 coverage/formal 收据建立历史身份关联。它不重新执行
旧 ROM verifier，不增加 classified bytes，不代替下一次 canonical coverage/formal audit。

## 固定输入与分母

本轮为 64 个历史目录、160 个 regular Git blob。原始候选清单漏入四份 gzip 与四份
framebuffer bin/PNG；这些成员全部由原 manifest 和 verifier 的实际读取域确定。
目录之外还保存 coverage、proof、formal report、formal guard 和相关 verifier 源码，
合计 282 个输入。完整路径、Git mode、size、SHA-256 位于 catalog 的 `input_files`；
原始字节以 base64 JSON/gzip 保存，不能依赖另一工作树或 ignored build 目录复验。

- 32 个 `direct_proof_verifier`：proof 命令的精确 artifact 参数、脚本哈希、明确成功
  断言及 formal 成功执行记录关联；命令只规范化 Python 解释器位置，保留 `-I -S`
  及所有脚本参数。
- 21 个 `aggregate_coverage_verifier`：完整对应 coverage claim ID、原 manifest/payload
  身份、存在的 selector、独立 verifier 源码身份和原有 report 哈希关联。历史 claim
  未记录 report 哈希时保持 null，不能制造一个新哈希。aggregate 的原始源码、输入和
  formal 成功收据整体冻结；此桥梁不声称从源码文本重新证明执行行为。
- 11 个 `immutable_precoverage_binding`：逐个验证 gzip 和解压原始 bytes 的摘要、大小；
  `per_root_semantic_verifier=false`，只能证明历史输入身份。

本轮固定 coverage 为 6,203,707 classified / 87,749 unknown；formal 为106个成功结构合同、
ROM gate96个合同，完整报告仍 `complete=false` /175 blockers。外部 trust anchor 仍未验证。

catalog SHA：`e687009c79e4ee3b6e584f61e710bbfaea1fd2bb75a5f52758ee79df237b342c`；
snapshot SHA：`184f34a1871e7d451b429ecab0c6e1b9502080665e96db5290ac108d25fa0b93`；
manifest SHA：`5527ed5acaccc560aa54b0c468ae95b6df3f6f577de7aa10836e0109f21e057c`。
snapshot重建使用Python3.14.3/zlib1.2.12；连续两次独立报告摘要相同，均为
`42e1d5628834efdf871a175d20feeba66d915b63daae66d669ac710f9821577c`。

## 独立验证与信任边界

`tools/verify_legacy_artifact_acceptance.py` 不导入 producer 或旧 ROM verifier。它从
归档重建成员分母和三种证据桥梁，核对 formal 的 `trust_anchor.spec_sha256` 指向
归档 proof，proof evidence 指向归档 coverage，formal coverage summary 与归档逐字段
一致，并逐项检查 aggregate 的正式 assertions。失败收据、缺失命令、参数变更、重复
JSON key、危险路径、非 regular mode、错误 base64/gzip、成员或 selector 缺失均失败关闭。

`inspect_snapshot` / `verify_archive` 是可用于隐藏同构测试的结构一致性检查，返回
candidate 状态；它们本身不是提交授权。只有 `verify_bundle_members` 先匹配代码中固定的
**整个包**成员/mode/size/SHA（包括 catalog、snapshot 和 manifest），再通过独立检查，
才能返回 accepted。因此不能删除整根后重算 catalog，也不能同时换掉 formal auditor、
输出路径、proof 和 report 后伪造自洽输入。CLI 只提供这个固定包验收入口。

整体哈希固定的是历史快照及其来源记录，不是外部密码学信任锚，也不证明旧工具在任意
未来版本仍会通过。后续 canonical 晋升不会改写这个历史包；新版本必须重新验收。

## 两阶段本地提交

1. A 提交只包含现代验收包、checker/verifier/固定身份合同、重建工具、测试、文档和
   TDD 收据。验收包必须自身满足已有现代 promotion 规则，不能授权自身。
2. B 才提交固定的历史目录及当前 ROM 证据闭包。门禁一次冻结 HEAD tree 与 index tree，
   从 Git blobs 读取预先提交的包；逐根匹配完整 staged 成员/mode/size/SHA。
3. 消费授权时，包、checker、verifier、固定身份合同在 baseline 与 staged tree 中必须
   完全一致。由于 hook 执行工作树 Python，运行中的模块字节也必须与 baseline 相同。
   在同次提交修改授权代码或摘要再消费授权会失败；修改工作树数据不能使错误 staged
   数据通过。没有预先提交的包时，旧目录继续接受原现代 schema 检查。

这些校验不把 Python 提示词当沙箱，也不防止仓库所有者主动替换整个 hook。它们约束正常
提交路径中实际检查的对象和来源，不能用于声称抵御拥有本地代码执行权的攻击者。

本次发现共享仓库没有安装持久pre-commit hook，故A/B均使用
`git -c core.hooksPath=.githooks commit`显式启用现有检查入口，不改动共享Git配置。
这不是跳过hook；以后提交也须启用该入口或安装仓库已有hook。

## 复现与恢复

`tools/rebuild_legacy_artifact_acceptance.py` 从固定 catalog 指定的本地源文件读取原始
字节，核对 mode、size、SHA 后在新路径重建确定性 gzip；输入不符或输出已存在时失败。
初始 A 提交可独立验证包内快照；B 提交后可从已提交源文件再次重建并比对 archive SHA。

重建CLI同时固定catalog与最终snapshot身份：snapshot pin须完整包含普通非可执行mode、
size和SHA，不能缺失或为null。压缩完成后、创建输出前比较最终size/SHA；不符即失败且
不留下输出文件，符合后才exclusive create。Python/zlib版本差异也由这个最终字节比较
失败关闭，不能通过更新pin来掩盖。此CLI只重建归档字节，独立验收仍由bundle verifier负责。

在逆向仓库根目录运行下列复验；run-id每次须更换为未使用的值。A提交后可执行包验真，
B提交后才具备全部源文件进行重建。失败时保留该run的guard和输出，不覆盖旧实验。

```sh
python3 tools/experiment_workspace.py init --task legacy-acceptance-replay --run-id local-verify-20260905
python3 tools/run_guarded.py --lock-file build/experiments/heavy.lock --summary build/experiments/active/legacy-acceptance-replay/local-verify-20260905/verify-guard.json -- python3 tools/verify_legacy_artifact_acceptance.py --artifact artifacts/rom-legacy-acceptance-20260905-v1
python3 tools/run_guarded.py --lock-file build/experiments/heavy.lock --summary build/experiments/active/legacy-acceptance-replay/local-verify-20260905/rebuild-guard.json -- python3 tools/rebuild_legacy_artifact_acceptance.py --root . --catalog artifacts/rom-legacy-acceptance-20260905-v1/catalog.json --output build/experiments/active/legacy-acceptance-replay/local-verify-20260905/snapshot.json.gz
```

所有实验在 `build/experiments/active/legacy-artifact-acceptance/post-story-v1-20260905/`
使用不同编号保存；最终接受状态、哈希和 TDD 收据另存永久 notes。候选、失败或被替代的
清单不得直接复制到主 index。提交前必须重新读取账户余量；不高于5%时停止新写入。
