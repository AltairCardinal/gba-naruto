# 逆向模型横评记录（2026-08-19，native 正式终态）

## 正式结论

本轮唯一进入正式质量统计的是绑定 plan
`dd499658da079bf2dee301a95fe68077bd1a815a04e724bf7e8516ed9db6327c`
与 native compatibility receipt
`4bc23126f5429464c7f89e90313445450286bca2403741a266dc1551b4447a99`
的 `codex-native` campaign。它覆盖 4 个配置、3 个模型名、3 个挑战和 12 个逻辑格。

- 12/12 个逻辑格进入终态，11/12 个形成有效质量结果。
- 14 个物理尝试包括 12 个 primary 和 2 个预先授权的基础设施 retry。
- 11 个有效结果全部为 100/100；没有观察到有效的能力失败。
- Sol Ultra 的 ARM/Thumb 格在 primary 与唯一 retry 后仍缺少完整执行／usage 闭包，
  因而是 `infrastructure-failed`，不记模型 0 分，也不进入平均分。
- 本轮没有预先冻结综合排序或性价比 tie-break，因此不事后宣称单一“第一名”。
  可以确认的独立轴是：Sol medium 为三个完整配置中最快，Luna max 的 Codex
  credits 估算最低，Sol Ultra 的已知成本最高且只有 2/3 有效格。

权威机器结果见
`build/reverse-model-benchmark/report-native-v1.{json,md}`；本文不重新定义其分母。

| 配置 | 系统模式 | 指针表 | ARM/Thumb | TDD | 有效格 | 平均分 | 有效耗时(s) | 物理耗时(s) | API USD | Codex credits 估算 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Luna max | 单代理 | 100 | 100 | 100 | 3/3 | 100 | 1591.589010187 | 1591.589010187 | unknown | 3.880265（complete） |
| Terra max | 单代理 | 100 | 100 | 100 | 3/3 | 100 | 1565.173712186 | 1565.173712186 | unknown | 37.29279（complete） |
| Sol medium | 单代理 | 100 | 100 | 100 | 3/3 | 100 | 847.778592983 | 847.778592983 | unknown | 51.325625（complete） |
| Sol Ultra | 多代理 | 100 | — | 100 | 2/3 | 100（仅有效格） | 1432.895860453 | 2470.962739417 | ≥5.797344，另 3 次 unknown | ≥144.9336，另 3 次 unknown |

## 逐格结果与 token

token 为 `uncached_input + cached_input + cache_write_input + output`；reasoning token
已包含于 output，不能再次相加。`unknown` 表示 attempt 已产生工作，但没有完整 usage
闭包，不能写成 0。

| 配置 | 挑战 | 最终状态 | 分数 | 有效耗时(s) | 物理耗时(s) | 物理尝试 | 已知 token |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Luna max | 固定指针表 | verified-passed | 100 | 495.972872094 | 495.972872094 | 1 | 630,917 |
| Luna max | ARM/Thumb | verified-passed | 100 | 632.341991555 | 632.341991555 | 1 | 801,931 |
| Luna max | TDD/Manifest | verified-passed | 100 | 463.274146538 | 463.274146538 | 1 | 450,615 |
| Terra max | 固定指针表 | verified-passed | 100 | 410.512110536 | 410.512110536 | 1 | 641,828 |
| Terra max | ARM/Thumb | verified-passed | 100 | 650.746185511 | 650.746185511 | 1 | 686,259 |
| Terra max | TDD/Manifest | verified-passed | 100 | 503.915416139 | 503.915416139 | 1 | 628,577 |
| Sol medium | 固定指针表 | verified-passed | 100 | 338.367747538 | 338.367747538 | 1 | 507,984 |
| Sol medium | ARM/Thumb | verified-passed | 100 | 265.281337687 | 265.281337687 | 1 | 311,456 |
| Sol medium | TDD/Manifest | verified-passed | 100 | 244.129507758 | 244.129507758 | 1 | 313,159 |
| Sol Ultra | 固定指针表 | verified-passed | 100 | 449.380414172 | 449.380414172 | 1 | 836,742 |
| Sol Ultra | ARM/Thumb | infrastructure-failed | — | — | 901.247982439 | 2 | unknown（2 次） |
| Sol Ultra | TDD/Manifest | verified-passed | 100 | 983.515446281 | 1120.334342806 | 2 | ≥2,403,296，另 1 次 unknown |

正式 campaign 的 14 个物理尝试中，11 个 usage 完整，已知 token 合计
8,212,764（输入 7,958,615、输出 254,149），另有 3 个 Ultra 失败 attempt 为
unknown。ARM/Thumb retry 的候选产物在隔离 verifier 中得到 100，但 app-server turn
最终为 `interrupted`、进程退出 1，且没有 all-agent usage 闭包；协议因此仍将该格
判为基础设施不可用，不能把内部 verifier 分数提升为正式质量结果。

## 正式耗时与成本

| 统计域 | 物理尝试 | 物理耗时 | API 等价 USD | Codex credits 估算 | 已知 token |
| --- | ---: | ---: | --- | --- | ---: |
| native campaign | 14 | 6475.504054773s | ≥$5.797344，12 次金额 unknown/partial | ≥237.43228，3 次 unknown | ≥8,212,764 |
| native v22 gate | 4 | 97.040918918s | $0.189403（complete） | 4.735075（complete） | 75,086 |
| 正式 processing total | 18 | 6572.544973691s | ≥$5.986747，仍为 partial-known | ≥242.167355，仍为 partial-known | ≥8,287,850 |

API USD 是冻结官方价表的等价成本，不是账户账单；credits 是 token 推算，不是套餐
ledger。9 个单代理格只提供 turn aggregate，且输入超过 272K，缺少逐请求边界，故
正式 API 金额必须保持 unknown。仅作敏感度分析、不能替代正式金额的数学包络为：

| 配置 | 全部按标准档下界 | 全部按长上下文档上界 |
| --- | ---: | ---: |
| Luna max | $0.15521060 | $0.26981920 |
| Terra max | $1.4917116 | $2.5886772 |
| Sol medium | $2.053025 | $3.655840 |

Ultra 的两个成功 attempt 具有逐请求边界，已知金额分别为 $1.693275 和 $4.104069；
三个失败 attempt 的 usage 不完整，因此无法为 Ultra 或 processing total 给出有限
上界。

## 历史 token、搭建开销与“浪费”边界

以下历史数据从现存 receipt／manifest 归一化；不同货币不得相加。所有带 `≥` 的值
只是已知下界，缺失 usage 的 attempt 仍可能产生实际消耗。

| 互斥分类 | 尝试/usage 完整 | 已知 token | 物理时间 | USD 下界 | credits 下界 | CNY 下界 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 当前有效 native v22 gate | 4/4 | 75,086 | 97.041s | $0.189403 | 4.735075 | — |
| 当前正式 native campaign | 14/11 | ≥8,212,764 | 6475.504s | ≥$5.797344 | ≥237.43228 | — |
| 旧无效 campaign（`runs/`、v3–v6） | 72/51 | ≥26,067,418 | 16,279.957s | ≥$18.77780708 | ≥763.493175 | ≥¥4.35826356 |
| 被取代 gate／contract canary | 61/41 | ≥3,526,688 | 2,031.211s | ≥$0.82562728 | ≥21.458960 | ≥¥2.56652382 |
| v13–v21 等无标准 receipt 的诊断 | unknown | unknown | unknown | unknown | unknown | unknown |

搭建／兼容性门／contract canary（当前 v22 加全部被取代项）共有 65 次有记录尝试，
已知至少 3,601,774 token、2,128.252 秒、$1.01503028、26.194035 credits 和
¥2.56652382。它不包含本次 Codex 编排对话本身，也不包含无标准 receipt 的诊断，
所以“搭建总成本”仍是 unknown。

若把“浪费”严格定义为已经判定不能进入当前排名的旧无效 campaign，则已知下界是
26,067,418 token，占全部有记录已知 token 37,881,956 的 68.81%。若把被取代但用于
发现合同、评分器和 provider 问题的 gate/canary 也算作广义沉没开销，则为
29,594,106 token、5.086 小时，占已知 token 的 78.12%。后一个比例不应解释为
“毫无价值的纯浪费”，因为它包含形成当前公开合同和 native 兼容性边界的研发证据。

Goal 编排器在 campaign 与首轮报告完成后的独立快照为 945,566 token；这是 Codex
对话／工具编排的总量，不是上述模型 API attempt token，系统没有提供把它可靠拆分为
“搭建／单格／浪费”的逐调用 ledger。当时剩余工作仅为文档、扫描和复验，估计约为
已消耗量的 0.03–0.06 倍。最终验收前的最新快照为 1,060,423 token，剩余只含终检、
Goal 收口和交付，估计约为已消耗量的 0.01–0.02 倍；这些估计都不是账单数据。

## 执行身份与 transport

- Luna max、Terra max 和 Sol medium 通过 Codex 内建 `openai` provider、本机 Codex
  session 认证执行单代理 turn；没有 endpoint override，也没有读取或中继用户提供的
  代理 API key。
- Sol Ultra 通过 app-server 执行多代理 turn，使用冻结的官方 HTTPS native 子传输，
  禁用 WebSocket；成功 attempt 的 usage 必须覆盖 root 与全部 child agent threads。
- Ultra 的两次 primary 在已产生工具工作后进入 `systemError`；TDD retry 成功，
  ARM/Thumb retry 最终 `interrupted`。这些不是模型 0 分，但属于本协议负载下的真实
  系统配置可靠性和物理成本。
- compatibility gate 的 4 个 canary 全部通过；gate 自身只作为执行前提和处理开销，
  不进入正式质量分数。

## 公开合同与隔离复现

每格只能看到自己的 `AGENTS.md`、`TASK.md`、`CONTRACT.json`、`INPUTS.json` 和
`input/`。`CONTRACT.json` 公开所有影响 exact score 的 JSON 形状与语义；隐藏复现只
复制声明的 solution、tests 和冻结输入，并使用同构不同 seed。v3–v5 暴露的隐藏输出
约定、stop 计数和测试强度问题均已在新 contract、verifier-owned behavior cases 与
新 plan/run ID 中修正；旧结果保留但不混入本轮。

独立 verifier 还会从每个 manifest 的 request telemetry 重算 billing，核对 aggregate
usage、请求序号和 Ultra all-agent scope，再从同一 plan、native receipt 和 manifests
逐字节重生成 JSON/Markdown。最终不可用格只有物理耗时，不携带正式分数或有效耗时。

## 冻结证据

- campaign 窗口：`2026-08-19T08:50:33.409718Z` 至
  `2026-08-19T10:39:04.484152Z`。
- Codex：`codex-cli 0.148.0-alpha.9`；二进制 SHA-256
  `c4932031a3d98539bb355fd8c39f4dd40402e18186a3c16c1dd0d58553d618c7`。
- Git HEAD：`765f4547c32b285d5630018b452d858644b36188`；工作树在任务前后均有大量
  与本轮无关的既有未提交改动，本轮未回滚、未提交、未 push。
- plan：`build/reverse-model-benchmark/plan-native-v1.json`；SHA-256
  `44c202c8f560f1f9428ca00fac3aa23c5635824c6ca6b74f62369290d0a98e09`。
- native receipt：
  `build/reverse-model-benchmark/openai-native-compatibility-v22/receipt.json`；SHA-256
  `e7bf64969cefbe15d8aef09b0402af409f56b5bc29bf19749f74553350d93b49`。
- report JSON：`build/reverse-model-benchmark/report-native-v1.json`；SHA-256
  `9fab2ef902fe991b610dadd6ee36506ec3731c1a7ca3163b2301f893631dafac`。
- report Markdown：`build/reverse-model-benchmark/report-native-v1.md`；SHA-256
  `c49baa0b72658979800696fafaca7c85e16a0370487d23dad2adfdec7d22cf99`。
- 14 个 manifest 的逐文件 SHA-256、run ID、attempt/token/cost 明细写入同名 JSON note。
- 独立 report verifier 验证 12/12 terminal，扫描 plan、receipt、两份 report 和 14 个
  manifest，共 18 个文件，凭据形状命中 0。
- 扩展扫描覆盖 formal plan、完整 native gate、14 个 run 目录及两份 report，共
  211 个文件，命中 0；发布文档集合（AGENTS、协议、路线图和两份 note）5 个文件，
  命中 0。该结论不泛化为整个脏工作树无凭据。
- `python3 -B -m unittest discover -s tests -p 'test_reverse_benchmark_*.py' -v`：
  117/117 通过。

## 历史隔离

`runs-v3` 的隐藏输出合同、`runs-v4` 的 stop 语义、`runs-v5` 的残余语义／配额／
基础设施问题以及 `runs-v6` 的旧 57 格计划均已被本轮取代。旧 proxy gate、MiniMax
结果、contract canary 和 native transport 诊断只作方法与成本审计：
`included_in_formal_quality=false` 且
`included_in_formal_processing_total=false`。历史证据不删除、不覆盖，也不用于补齐
Ultra 的不可用格。

## 证明与不证明

本轮最多证明四个指定配置在三类小型、冻结、同构逆向任务上的质量、耗时、成本和
有限隐藏同构泛化。它不证明一般智能、完整 ROM 逆向能力、自然执行可达性、长期项目
工期，亦不外推未测档位、provider、未来 Codex 二进制或不同 transport。Sol Ultra
是多代理系统配置，不能把其效果、成本或故障率解释成纯模型／纯推理档位差异。
