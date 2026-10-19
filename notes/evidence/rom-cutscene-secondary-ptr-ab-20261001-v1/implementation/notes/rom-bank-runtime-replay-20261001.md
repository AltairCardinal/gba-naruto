# 固定 bank runtime 验证器批量重放

## 结果

按 live bank-proofs.json 中 11 条原命令逐条离线执行，10 条 exit0 且 verified=true，
menu-ui exit1/verified=false。这是已有证据重放，不是新的 11 份运行时样本，也不能
推导 bank 的全记录/字段覆盖。正式 catalog 和 proof 没有修改。

| bank | 实际结果 | 原 verifier 的可观察输出 |
| --- | --- | --- |
| battle-encounters | 通过 | 1,603 像素变化，内存差异归因 |
| cutscene-scripts | 通过 | errors=[]，ID 1 primary_ptr 自然胜利旧证据 |
| data-table-b | 通过 | message0，928 像素变化 |
| levels | 通过 | baseline output_a=18，candidate=2 |
| map-events | 通过 | entry228，37,436 像素变化 |
| map-sprites | 通过 | entry1，213 像素变化 |
| maps | 通过 | map41 自然入口，204 像素变化 |
| menu-ui | 拒绝 | portrait independent implementation hash mismatch |
| palettes | 通过 | record0/y_offset，自然路径，286 像素变化 |
| sappy-engine | 通过 | errors=[]，旧 master-enable 证据 |
| tile-assets | 通过 | descriptor2，38,400 像素变化 |

表中只是原 verifier 的固定样本输出；palettes slug 实际验证 motion-effect 参数，
不能由其名字推导调色板所有颜色或字段已验证。没有把 exit0 单独作为成功依据。

## 漂移定位与下一动作

menu-ui 旧 manifest 的 implementation_sha256 仅一项漂移：
tools/render_mode0_checkpoint.py 期待
`dbd6e5e179c43218e7f97f3e496ac808908422ed6d08f472b3e0d0968eda53e0`，
当前为 `80a7d188d93418ba3796b597deb62a0584acfd1270dce633cfd8f1b18794c369`。
旧 archive/manifest 和 renderer 均不改写、不回退。本轮没有绕过 hash gate 来宣称
旧头像证据通过；后续以相同 raw 输入和当前 renderer 生成独立新收据，再做篡改与
语义复验。该失效与之前 battle-effect 的测试文件 SHA 漂移是不同债务。

cutscene 两表可复用种子已确认，下一动作从第一表 ID 1 secondary_ptr 单字段
A/B 开始；第二表 definition/animation 仍独立。地图精灵 canary 已有 typed proposal，
其余通过的旧 verifier 可以按原始覆盖边界迁移，不能直接增加 23/2,954 的覆盖数字。

## 方法和证据

模式：固定有效 bank 旧 runtime verifier 分母重放与身份漂移定位，脚本优先。
run 为 build/experiments/active/bank-runtime-replay/existing-11-20261001-v1。
plan 固定 bank-proofs SHA、原命令、bank/evidence/artifact 全部成员及脚本身份；每项
执行前后重验输入身份。脚本先检查 verifier 不直接 subprocess 启动模拟器；每项
180s 上限，在同 heavy lock 下顺序执行。本轮总 guard 非降级，峰值约 111MiB，
没有启动 mGBA，三条绝对 binary 参数按原样保留，没有伪装可移植。

[永久 receipt](evidence/rom-bank-runtime-replay-20261001-v1/)含 plan、可复现 replay.py、
每项 stdout/stderr/result、report、semantic-summary 与 guard。脚本属于调查产物，
没有新增生产行为，不声称功能 TDD；语法、清单 SHA、文档和身份检查另行通过。
canonical unknown87,631B、175 blockers、正式 typed 合同0保持，未提交或 push。

## 验收

- [ ] 查看 report.json → 11 条真实执行，10 条 exit0；menu-ui 为 exit1。
- [ ] 查看 semantic-summary.json → 10 个 verified=true，头像仅 renderer 身份漂移。
- [ ] 查看 cases/cutscene-scripts/stdout.txt → verified=true/errors=[]，范围仍仅旧样本。
