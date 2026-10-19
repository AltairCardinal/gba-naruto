# 逆向模型横向测评协议

## 目的与适用边界

本协议用于比较多个模型配置在固定、隔离、可复验的 ROM 逆向任务上的质量、
耗时和成本。它回答的是“在同一套小型逆向工作包上，哪个配置的能力／成本比更
合适”，不证明模型的一般智能、完整 ROM 逆向能力或真实长期项目工期。

测评工作包不得包含隐藏答案。每格只能看到自己的 `AGENTS.md`、`TASK.md`、
`CONTRACT.json`、`INPUTS.json` 和 `input/`；网络、外部搜索、插件、技能、父目录和
既有会话均被禁止。`CONTRACT.json` 不仅公开 JSON 形状，还必须公开所有影响精确
评分的语义。所有提交写入该格的 `submission/`，verifier 在任务结束后隔离评分。

## 冻结矩阵

工具保留 19 个配置的能力目录，供历史计划复验；每次正式计划必须从目录中显式
冻结本轮子集。2026-08-19 收敛计划只比较 4 个配置、3 个挑战，共 12 个逻辑格：

| 模型 | 推理档位 | 系统模式 |
| --- | --- | --- |
| GPT-5.6 Luna | max | 单代理 |
| GPT-5.6 Terra | max | 单代理 |
| GPT-5.6 Sol | medium | 单代理 |
| GPT-5.6 Sol | ultra | 多代理 |

`none`、其余 OpenAI 档位和 MiniMax 不进入本轮最终排名。历史 v3–v6、兼容性
canary 和 MiniMax 结果必须保留作审计，但不得与本轮 12 格混算。Sol Ultra 与其他
配置一起统计，但其多代理系统模式必须保留在配置身份和成本边界中。

本轮四个配置都冻结为 `codex-native`，但执行机制并不完全相同。Luna max、Terra
max 和 Sol medium 使用 Codex 内建 `openai` provider、本机 Codex session 认证，
不覆盖 endpoint，也不做第三方凭据中继。Sol Ultra 由 app-server 调度多代理 turn，
使用冻结的官方 HTTPS native 子传输并禁用 WebSocket，usage 必须覆盖 root 与全部
child agent threads。Ultra 因而是系统配置对照，不是与前三项之间的纯模型或纯
reasoning-effort 对照。仅当 root 尚未产生工作或 usage 时，瞬时 transport restart
才允许在同一物理 attempt 内恢复；产生工作后的失败只能进入 campaign 的一次
基础设施 retry 规则。

能力目录实现以 `tools/reverse_benchmark/matrix.py` 为准，正式子集以 plan 的
`configurations` 为准。计划生成后会冻结选中配置、provider contract、兼容性回执、
主种子、挑战种子、顺序和 primary/retry run ID；修改上述任一内容都必须生成新的
plan，不能复用旧 run ID。新子集必须使用新 seed、plan 路径和 runs 目录；旧计划仍
按其自身完整目录验证。

## 三类固定挑战

| 挑战 | 主要能力 | 必须失败关闭的边界 |
| --- | --- | --- |
| 固定指针表 | 小端指针、空槽、重复槽、首个 NUL 消费边界、可复现导出 | NUL 后字节不得分类 |
| ARM/Thumb 控制流 | Thumb BL/B、`BX pc` 模式切换、ARM B、`BX lr` 终止 | 随机填充和声明范围外字节不得分类 |
| TDD/Manifest 合同 | 顺序、CRC32、首个 stop、红绿重构、输入哈希和运行清单 | stop 后记录不得解释；CRC 或顺序错误必须拒绝 |

每个挑战由固定种子生成可见输入；隐藏 verifier 还会生成不同种子的同构输入，
用于排除硬编码答案。

## 公开合同与隔离复现

- plan 必须冻结 packet contract schema、公开 `CONTRACT.json`、输入哈希和评分权重。
- `CONTRACT.json` 必须使冻结期望能由公开材料唯一推出；例如 stop 是否进入
  `accepted_sequences`、stop 后非空物理行的计数方式，以及 BL continuation 只参与
  traversal 而不输出隐式边，都不得留作隐藏约定。
- 候选测试路径、运行命令、复制集合、工作目录、超时、输出上限和隐藏同构输入的
  隔离方式必须公开。隐藏复现只复制公开声明的 solution、测试和冻结输入。
- 正式 campaign 前先逐挑战运行 contract canary；任何公开合同歧义都必须修复并用
  新 schema/seed/run ID 重启，已有结果标记为被取代而不删除。
- verifier 必须先校验公开 JSON Schema，再按公开语义比较冻结期望；schema 错误、
  语义值错误、复现失败和基础设施失败要使用不同诊断。

## 百分制质量

每格独立按 100 分计：

| 项目 | 分值 |
| --- | ---: |
| 可见输入和 `INPUTS.json` 哈希未改变 | 15 |
| `result.json` 按公开合同精确匹配冻结期望 | 40 |
| `run_manifest.json` 合同完整 | 10 |
| `solution.py` 在原输入和隐藏同构输入上均可复现 | 20 |
| 候选测试可隔离运行，并能杀死公开约束对应的行为 mutant | 15 |

只有无错误且满 100 分才是 `verified-passed`。`verified-failed` 仍是有效模型质量
结果，应保留实际分数；`infrastructure-failed` 不得记作 0 分，也不得进入模型
质量均值。最终 manifest 必须验证分数在 0–100 之间，并与 `passed` 和状态一致。

## 耗时与重试

- `effective_wall_time_ms`：逻辑格最终有效 attempt 的墙钟时间，用于能力／耗时比较。
- `physical_wall_time_ms`：primary 与所有授权 retry 的墙钟总和，用于真实处理成本。
- `physical_attempt_count`：该逻辑格实际启动的物理尝试数。

每格最多一次 retry，只允许基础设施故障，并在全部 primary 之后按 tail-FIFO 执行。
只有调度锁、资源准入、已登记的瞬时传输或空 Ultra 通知等基础设施故障可以 retry；
普通模型答案错误、质量未满分、持续认证失败和凭据材料检测不得作为模型质量重试。
资源守卫、统一 heavy lock、wall
timeout、idle timeout 和 owned process tree 清理由 harness 内部调用
`tools/run_guarded.py` 完成，外层不得重复嵌套资源守卫。

## 成本口径

成本必须按物理 attempt 累计，质量只取逻辑格最终有效 attempt。各单位不能互换：

- OpenAI API USD：按冻结的 [OpenAI 官方 API 价表](https://developers.openai.com/api/docs/pricing)
  逐请求计算，是官方标准价等价成本，不是代理实际账单。
- Codex credits：按冻结的 [Codex 官方 credit 价表](https://learn.chatgpt.com/docs/pricing)
  从 token 推算；cache write 因公开表没有单独档位，按 uncached input rate 估算。
  该值不是账户 ledger，也不等于套餐界面实际扣减。
- MiniMax API CNY：按冻结的 [MiniMax 官方 API 价表](https://platform.minimaxi.com/docs/guides/pricing-paygo)
  逐请求计算。
- MiniMax Token Plan：同时记录输入和输出 token；它是套餐消耗量，不是人民币金额。
- USD 与 CNY 不做汇率换算或相加。

OpenAI 聚合输入超过 272K、MiniMax-M3 聚合输入超过 512K 时，如果遥测缺少逐请求
边界，对应 API 金额必须为 `unknown` 或 `partial-known`，不得把聚合 token 套用
单一阶梯，也不得把未知值写成 0。Codex credits 和 Token Plan token 若仍可精确
推导，应分别保留其已知值和独立状态。报告必须传播每项未知的原因。

本机 Codex session 下的 API USD 仍只是冻结官方价表的等价成本，Codex credits
仍只是 token 推算，不得写成账户真实账单或 ledger。Ultra 必须累计全部代理线程；
缺少闭包标记时，usage 和成本都要失败关闭。独立 verifier 必须从 request telemetry
重算 billing 并核对 aggregate usage，不能只用同一 manifest 重排既有金额。

## 凭据与传输

- 凭据只能由受控凭据加载器从系统安全存储或授权环境读取，不得写入仓库、plan、
  argv、prompt、事件、manifest、报告或文档。
- 每个实际 transport 必须通过对应的动态 compatibility gate；gate 回执的 provider
  contract、Codex 二进制哈希、认证来源和计量能力必须绑定到 plan 和每个 attempt。
- `codex-native` 使用本机 Codex session 认证，不读取本项目或用户提供的代理 API
  key。内建单代理 provider 不允许 endpoint override；Ultra 的 native HTTPS 子传输
  地址、WebSocket 策略与 all-agent usage 范围进入冻结 provider contract。
- 明文认证中继默认拒绝。只有用户对本次目标明确授权、静态安全门通过且 CLI
  显式提供 `--allow-plaintext-auth-relay` 时才可执行；持久文档只记录无密钥合同
  哈希，不记录认证值或用户专用端点。
- 每次 canary、campaign 和报告完成后，都要对新增产物执行凭据材料扫描；命中时
  立即停止，不生成可发布结论。

## 标准执行顺序

先检查工作树、存活代理、资源锁和可用内存。以下命令中的路径应替换为本次全新
目录，命令行不得包含凭据：

```bash
python3 -B -m tools.reverse_benchmark matrix

python3 -B -m tools.reverse_benchmark compat-openai-native \
  --repo-root /absolute/path/to/repo \
  --output build/reverse-model-benchmark/openai-native-compatibility-v22 \
  --execute

python3 -B -m tools.reverse_benchmark plan \
  --seed 20260820 \
  --output build/reverse-model-benchmark/plan-native-v1.json \
  --openai-native-compatibility-receipt build/reverse-model-benchmark/openai-native-compatibility-v22/receipt.json \
  --configuration-id openai-gpt-5.6-luna-max \
  --configuration-id openai-gpt-5.6-terra-max \
  --configuration-id openai-gpt-5.6-sol-medium \
  --configuration-id openai-gpt-5.6-sol-ultra

python3 -B -m tools.reverse_benchmark run \
  --repo-root /absolute/path/to/repo \
  --plan build/reverse-model-benchmark/plan-native-v1.json \
  --runs build/reverse-model-benchmark/runs-native-v1 \
  --openai-native-compatibility-receipt build/reverse-model-benchmark/openai-native-compatibility-v22/receipt.json \
  --wall-timeout-s 1800 \
  --idle-timeout-s 600 \
  --execute

python3 -B -m tools.reverse_benchmark report \
  --plan build/reverse-model-benchmark/plan-native-v1.json \
  --runs build/reverse-model-benchmark/runs-native-v1 \
  --openai-native-compatibility-receipt build/reverse-model-benchmark/openai-native-compatibility-v22/receipt.json \
  --json build/reverse-model-benchmark/report-native-v1.json \
  --markdown build/reverse-model-benchmark/report-native-v1.md

python3 -B tools/verify_reverse_benchmark_report.py \
  --plan build/reverse-model-benchmark/plan-native-v1.json \
  --runs build/reverse-model-benchmark/runs-native-v1 \
  --openai-native-compatibility-receipt build/reverse-model-benchmark/openai-native-compatibility-v22/receipt.json \
  --report-json build/reverse-model-benchmark/report-native-v1.json \
  --report-markdown build/reverse-model-benchmark/report-native-v1.md \
  --configuration-id openai-gpt-5.6-luna-max \
  --configuration-id openai-gpt-5.6-terra-max \
  --configuration-id openai-gpt-5.6-sol-medium \
  --configuration-id openai-gpt-5.6-sol-ultra
```

若中断，使用同一 plan、回执和 runs 目录恢复；固定 run ID 会跳过精确绑定的已完成
格。任何绑定冲突、被篡改 manifest 或未经授权的 retry 都必须在启动新格前失败。

## 验收与持久化

完成后至少执行：

```bash
python3 -B -m unittest discover -s tests -p 'test_reverse_benchmark_*.py' -v
git diff --check
```

并验证：plan 恰含上述 4 个配置和 12 个逻辑格，且每格均有最终状态；有效分数均在
0–100；状态与分数
一致；逐挑战耗时存在；每项成本状态与 known/unknown attempt 数一致；独立入口能从
同一 plan、回执和 manifests 逐字节重生成 JSON/Markdown，且新增证据凭据扫描为零。

`build/reverse-model-benchmark/` 保存本次运行中的原始证据，不作为长期唯一来源。
任务完成前应把归一化 JSON 摘要、Markdown 结果、plan/receipt/manifest 哈希、实际
命令、运行窗口、Git 状态、结论和“证明／不证明”边界写入 `notes/`；只把稳定流程
留在本文件。原始事件不入库，持久摘要不得包含凭据或未脱敏远端输出。

正式报告的 `processing_total` 只包含当前 plan 的 campaign 与其绑定的 native
compatibility gate。旧 proxy gate、v3–v6 campaign、contract canary 和被取代诊断
只进入历史成本审计，不得并入当前质量、成本或处理总计。
