# ROM CFG proven-roots v14 验收记录

## 结论

CFG proven-roots v14 已完成独立 preflight、TDD、canonical artifact、dependency-first
immutable bundle、coverage、proof 与受守卫 formal-r2。该里程碑只把 160 个接入前为
`unknown` 的字节分类为 120-byte bounded Thumb code 与 40-byte
instruction-consumed literals；没有把全 ROM ARM/Thumb code map、自然运行时可达性、
间接目标、业务语义、编辑、写回、重定位或可分配空间声明为已完成。

接入后的 canonical coverage 为：

- classified：6,126,935 / 6,291,456（97.385009%）；
- unknown：164,521（2.614991%）；
- primary claims：14,562；
- segments：16,677；
- coverage SHA-256：
  `2592ce481515af301ef5ce4078d3e9101793bf790f1bc90a6d33d5a06c207317`。

全局 proof 仍正确报告 `complete=false`、`claim_status=incomplete`、175 blockers，且
外部 trust anchor 未验证；本包合同全过不等于“逆向 100%”。

## 冻结范围与 producer 分母

| root | producer file offsets | code | literals | frontier |
| --- | --- | --- | --- | --- |
| `0x0624C0` | `0x064594`, `0x065234` | `[0x0624C0,0x062500)` 64B | `[0x062500,0x062510)` 16B | `0x0624FE bx r0` |
| `0x062510` | `0x0644F2`, `0x06452C`, `0x065258` | `[0x062510,0x062548)` 56B | `[0x062548,0x062560)` 24B | `0x062546 bx r0` |

- 五条 producer raw 分别为 `fd f7 94 ff`、`fd f7 44 f9`、`fe f7 0d f8`、
  `fd f7 f0 ff`、`fd f7 5a f9`；均绑定 V12/V13 accepted node、当前 coverage owner、
  ROM raw bytes 与 target-limited 全 ROM denominator。
- 两个 target 合计 60 instructions、10 blocks、120 code bytes、40 literal bytes、
  4 promotion ranges、0 hole、2 unresolved `indirect_pc_target` frontiers。
- 两个 `bx r0` 均不得称为 structured return；当前证据没有解析 `r0` 的运行时目标。

统一非声明：自然运行时可达性；全局 caller、producer 或 code 分母；全局
indirect/computed/RAM target 分母；`bx r0` runtime dispatch；callee ABI 或业务语义；
literal 业务含义或 compiler authorship；相邻字节 padding/free/allocatable；编辑、
写回、重定位或 gameplay behavior。

## 冻结身份

- 基准 ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`；
- preflight contract / report-r4 / receipt-r4 SHA-256：
  `273d9853b31183414ee1ea57f551e1cabfd316eca721e3ec9469ded122fafe69` /
  `a30378af24bc7ea7d38bf43072570dc1c32d5bc78632ddeacf95fcbefef2b325` /
  `f3c26cd241b88e9c5f57693501b0270fbf71d56990db5793c6817444501124c3`；
- manifest / payload SHA-256：
  `666772f43529a5578414c5b749e16ea8733a755a0a818e86cea81bd86d57091d` /
  `d99c0cdc367637b62754b941926e22d09bef08f9a3e89817fbf42dafc0a7edff`；
- exporter / legacy verifier / immutable bundle SHA-256：
  `28fef68f4377a89896c6884433a36f949ee4819ed4f4edc28ffe915a189cdae6` /
  `f6125cf1270e67da57ac049c881a1d4033208664816f05f533b39e8152da8ea7` /
  `11464a0581da7e12a098df0c40a505fda3a898609c8793e2f1f5edd9e9169889`；
- immutable bundle standalone report SHA-256：
  `0ec1242f11a91c9241207743fc5e7ca18db82678e9b5311b17f3a4ff7a771f27`；
- proof spec / coverage auditor / formal auditor SHA-256：
  `b78b8b2fd112cd07cc4b096443f3aff246b2df080be4c7acf54f0c677440ca02` /
  `cfc6b59b2376308c3a63859585dacb0b0e8ecd06b5710dcdcaf9ab46bc2cb92f` /
  `1562de7b02fc781b79ede13a29a03137a02082ff2aa59b3ec212b90ae797104b`。

## TDD、coverage 与综合 CFG registry

所有高开销命令均通过 `tools/run_guarded.py` 串行取得精确
`build/experiments/heavy.lock`，未使用 `--allow-degraded`。

- 完整产品缺失的 RED receipt SHA-256：
  `baf6bedefacf936c4eae062fde73d1cce6b199980e41633c7165c93ea57fae0e`；
- artifact export log / guard SHA-256：
  `1fb415298f70ba13b11f182bd85dd6a6327419fbc1ea5f7900504d1f6d3e2131` /
  `392c15abaac25811d72505c35213ff2a717fc4db536bab6dbf4ba6410d9c5111`；
- bundle tests log / guard SHA-256：
  `bbf6b33c8a7af63f7d50bec24b9eb3c4b1773153ba653298504d90d3d7789dce` /
  `4f440ef6842a32747963cac5d56ef5df8002c8c5286be1d71d97e413e4818214`；
- canonical coverage write report / guard SHA-256：
  `82f964518787c58a67f88866642c803ff2a40a0259f8280681ca8d9e4fb13fbe` /
  `f736545716639cae09e99fd3127e06e6ca6517dc9fac05d99fe91002dda0253f`。

V14 接入时发现旧 coverage summary 的手写 allowlist 漏计多种早已接受的 ARM、
mixed-ISA、Thumb code 与 producer kind。新增冻结 registry 后，32 个 code kinds 与
2 个 producer kinds 纳入汇总，3 个 code-like 非 CFG kind 以哈希绑定排除；任何未来
带 `code`、`instruction` 或 `producer` token 的未登记 primary kind 都失败关闭。

- 正确 RED（synthetic ARM 与 producer 被旧 future-kind guard 漏过）log / guard
  SHA-256：
  `c134f3a34d4a7eafa37c3ae5c81673d73da0ab6e5e50aba9ca5a5449a85a3112` /
  `0209da9034cb6110063845ed925f84d1644be5fafcbc47b16985dc843295c5ea`；
- 修正后的 current aggregate：ARM 956、Thumb 148,380、producer 32，合计 149,368
  promoted bytes、3,829 primary claims、32 code kinds；registry SHA-256：
  `d57f6b22f597eb6cfcad6a746122870917fbc24b0e70a885a432a57c729a227f`。

旧文档中的 142,554、142,688、144,550、144,862 是旧不完整 allowlist 的历史输出，
不再代表当前综合 CFG aggregate。boot interwork 的 378 code bytes 仍有独立 accepted
artifact 与 note 证明；不能因其旧 claim 缺少后来标准化的 `promoted_from` 字段而排除。

## 正式 proof 审计

formal-r1 在旧 aggregate 合同下 91/91 通过，但已被 r2 取代。唯一当前权威命令实际
执行 `--execute-verifiers --allow-incomplete --output`，没有外部 trust anchor，也没有
使用 `--allow-degraded`。formal-r2 结果：

- 91 个唯一结构化 command，91/91 `exit_code=0`、91/91 `contract_ok=true`；
- ROM byte gate 81/81；bank contract 10/10；proof spec 另有 11 个只作哈希绑定证据
  的旧 bank verifier，所以配置引用总数为 92，不能写成 92 次执行；
- V14 bundle 在正式报告中恰好执行一次并通过；
- report 仍为 `complete=false`、`claim_status=incomplete`、175 blockers；
- 耗时 3,438.593624 秒，守卫非 degraded，峰值整树 RSS 660.1875 MiB；
- report / guard SHA-256：
  `f9c2a1014b62dc7449db7f35965a1d42db01eb4972e43c81d961688e0befa786` /
  `3786c8d4e51c8070a021064433535429dc22efe5dcfb84ae4e156fe1039d7fa4`。

接入后的 legacy exporter/verifier 继续锚定 V13 precoverage，因 current coverage 身份
变化而按设计失败关闭。当前复验权威是 immutable bundle、canonical coverage 和
formal-r2；不得为“让旧产品测试变绿”而重写冻结 baseline 或重导出 V14 artifact。

## 可证明的浪费与下一步

综合 registry 修正期间两次 canonical coverage write 在确定输入已过期后被主动中断，
分别运行 270.766387 秒与 461.130616 秒，共 731.897003 秒（约 12 分 12 秒）；两份
guard 均保留为 `protection-failure`，canonical 文件未被部分覆盖。这是本里程碑可证明
的纯执行浪费下限。正常 TDD RED、独立 verifier 重建、canonical coverage 与 formal
复验均产生可用证据，不计为浪费。

下一步只对五个 source-bound root 做 V15 root-isolated preflight：`0x09A3E0`、
`0x09C0F4`、`0x0611F4`、`0x0618FC`、`0x08B6F0`。五个 root-forward unknown
ceiling 合计 864 bytes，仅是 envelope 上限；必须逐根冻结实际 code/literal/hole/
frontier 和 producer 分母。`0x08B644→0x08ACC8` 不在 V8 accepted worklist，禁止纳入。
