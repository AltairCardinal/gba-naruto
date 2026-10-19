# ROM CFG proven-roots v15（2026-08-30）

## 结论

V15 以“固定直接分支 producer 证明的新 CFG 根与冻结基线增量”模式闭合五个
source-bound 候选中的四个，拒绝一个。canonical artifact、coverage 与 formal proof
均已验收；当前 ROM 字节语义进度为 6,127,385 / 6,291,456（97.392162%），仍有
164,071 bytes（2.607838%）显式 unknown。

本包只声明 398 bytes reachable Thumb instructions 与 52 bytes 实际消费 literal；
三个 indirect-PC frontier、六段合计 386-byte holes、拒绝根范围及所有其他相邻字节
继续 unknown。

## 任务模式与冻结输入

- 任务模式：复用 `AGENTS.md` 已登记的“固定直接分支 producer 证明的新 CFG 根与冻结
  基线增量”。执行方式仍是可复现 exporter + 独立 raw-control-flow verifier + TDD；
  Sol medium 只读复核，最终证据链由本体验收。
- 公开合同：
  `build/experiments/active/cfg-proven-roots-v15-preflight-20260830/CONTRACT.json`，
  SHA-256
  `b0c1e24b0eaea2f3fe9e6277b43dd39eb750a340403ce912fb9e762af0ae7485`。
- ROM：6,291,456 bytes，SHA-256
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- 上游只接受 V8/V12/V13 canonical manifest/payload 中的 accepted source membership；
  `0x08B644→0x08ACC8` 因不在 V8 accepted worklist 保持排除。
- 运行时不得读取 preflight report、CONTRACT 或 live coverage 作为控制流 oracle；
  exporter 与 verifier 使用不同 V13 oracle，并从 ROM 与哈希固定上游独立重建。

## 冻结根结果

| root | producer | instructions / blocks | code | literals | holes | frontier |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `0x0611F4` | `0x06144A` | 53 / 7 | 108B | 40B | 52B | 1 |
| `0x0618FC` | `0x061456` | 26 / 9 | 54B | 4B | 330B | 1 |
| `0x08B6F0` | `0x08BBAA` | 85 / 7 | 170B | 0B | 2B | 1 |
| `0x09A3E0` | `0x0612C8` | 33 / 8 | 66B | 8B | 2B | 0 |

合计：197 instructions、31 blocks、398 code bytes、52 literal bytes、450 promotion
bytes、2 external call edges、3 frontiers。10 条 semantic ranges 的 SHA-256 为
`4cb1b785aa18b03873dee55781289574009c42231d1dfd198aa024bc41d38974`；
7 条 union ranges 的 SHA-256 为
`9a91de64231f4d1cf2bbf41e4aa4858c4fa4e3af7dddf60a5ae79287da506ad0`；
promotion packed SHA-256 为
`764b272bc4d19be46d334c10e47d00419c05fa60d6878ef336f455d25e7b08e7`。

`0x09C0F4` 被拒绝：候选范围存在 literal/code overlap，且有未绑定 raw Thumb BL
命中。其 `[0x09C0F4,0x09C110)` 不得提升。

## 产品与 canonical artifact

- 产品：
  - `tools/rom_cfg_proven_roots_v15_contract.py`
  - `tools/export_rom_cfg_proven_roots_v15.py`
  - `tools/verify_rom_cfg_proven_roots_v15.py`
  - `tools/verify_rom_cfg_proven_roots_v15_bundle.py`
  - 对应 exporter、verifier 与 bundle 三组测试。
- 产品完整测试 25/25 通过；candidate r3 的 legacy 与 bundle 报告分别为
  `10440e…` 与 `e7d7dc…`，Sol 终审无 P0/P1。
- canonical 路径：`artifacts/rom-cfg-proven-roots-v15/`，只含 manifest 与 payload。
- canonical manifest：67,035 bytes，SHA-256
  `7fb00210d8347df1935d6997afa66183d6cbaa4d7d26208f744256e09f11755f`。
- canonical payload：57,245 bytes，SHA-256
  `5786c04ae36d78957705175dfce38da190bb29682c640c6821bb44ec4c321cd2`。
- legacy verifier SHA-256：
  `163f04429f5bdd117f540cdf2421c483ff110e6eab1042403fe29ab7736dc167`。
- immutable bundle verifier SHA-256：
  `7eeb291c75e89caf1873dfd49fb433c462cd421c22a11d996cd98e79e954ca79`。
- canonical exporter、legacy verifier、bundle verifier 三个 guard 均
  `completed / exit_code=0 / degraded=false`，证据目录：
  `build/experiments/active/cfg-proven-roots-v15-canonical-20260830/`。

## Coverage TDD 与结果

- RED 首次因缺少 `_cfg_proven_roots_v15_claims` 正确失败；随后只把 10 条 semantic
  ranges 投影成 10 个 primary claims，不能用 7 条 union ranges 合并语义边界。
- code claims 6 条 / 398B，literal claims 4 条 / 52B；每条必须完整位于 pre-V15
  current-unknown，保留 payload target 原顺序与 selector。
- 六段 386-byte holes 与 rejected range 逐字节保持 atomized unknown，并有 overlap
  禁止测试。
- full V15 coverage class 4/4 通过；正式 `coverage --write` 由 guard 串行运行，耗时
  约 21 分 48 秒、峰值 427.984 MiB、非降级。
- `sequel/rom-byte-coverage.json`：23,395,622 bytes，SHA-256
  `c76ac479b6798b856ff839b9f9388f537f912247481ee06ff53ad52c504624c9`。
- post-V15 totals：classified 6,127,385、unknown 164,071、claims 14,572、segments
  16,693。
- 综合 CFG：ARM 956、Thumb 148,778、producer 32、promoted 149,766 bytes、
  primary claims 3,835、code kinds 33，registry SHA-256
  `10ae3cc720e787630957b7c7bbbbae379ec5f3e542dbabeb871df861915a676b`。

## Proof TDD、环境缺陷与 formal

- proof RED：V15 canonical evidence 缺失，日志 SHA-256
  `fe95f111e9d53074a845bc014d7cb8ac941fa8e98b58e5640c5828e6bbe5452b`。
- proof GREEN 绑定 82 evidence、82 ROM verifier、coverage 当前 totals、V15 八个
  summary 字段、25 项 bundle assertions。25 项是冻结 16 项的严格超集，额外绑定
  schema、errors、artifact/legacy 安全状态、live coverage 非依赖与 ROM identity。
- formal-r1 report / guard SHA-256：
  `97c0f09dc03431bcd9fbccfbf82555fd0a3592fa7f753086e2471acff236ab` /
  `ba8cbfa8bcb665b16102e234c7aef8325cd1e53ce9a3fa153cc37d965bf769e6`。
  守卫退出 0 不能视为通过：92 项中 coverage auditor 与 V15 bundle 两项实际
  `exit_code=1 / contract_ok=false`。
- 根因：formal executor 无条件对子进程设置 `PYTHONPATH`；V15 `-I -S` bundle 的
  安全合同明确拒绝 `PYTHONPATH/PYTHONHOME/LIBCAPSTONE_PATH`。coverage auditor
  继承同一变量后调用 bundle，造成连带失败。
- 环境 RED 精确出现 `PYTHONPATH unexpectedly found` 与缺少 `env` 参数；RED log /
  guard SHA-256：
  `400527baee5d693ab8678acde3ec1120e0e58bc378ad760344ca39563c8fa98c` /
  `c031e24d8d2e28ea5d7a86d71fb6968afd17e1898a6e216e1cdcb350d762cdf0`。
- 最小 GREEN：formal executor 只对受上游语法验证的隔离 Python 命令省略
  `PYTHONPATH`，非隔离命令继续设置仓库 root；coverage runner 从环境副本清除三项
  污染变量，不修改父环境。定向集 8/8 通过；formal executor 对真实 V15 bundle 的
  诊断为 `exit_code=0 / contract_ok=true / blockers=[]`。
- formal-r2 report / guard SHA-256：
  `3002d624f4a5354c4bf0f410aa7923c8377c33e96c263d6df6299ef67deefb63` /
  `b10f03289ab3b941a3bb3d0dd30edc806816dc5a262224ec5137a28e94ada220`。
- proof spec / coverage auditor / formal auditor SHA-256：
  `3c622bc59bf414cd511eeb900bd421bb85122e57c152b065e19349d4a3aa842b` /
  `19dcdfd9fc81d1c8a13cba7bd07bd8f05fe0a52da0582602828bc77f3de71ba4` /
  `59ffdd85782c5127db1a545e49a5c0daa48e0033eb7c3b5196a4c492817b8c33`。
- r2 实际执行 92 个唯一结构化 contract：ROM 82/82、bank 10/10、bad=0；耗时
  3,192.960532 秒，峰值 RSS 677.41796875 MiB，非降级。报告保持
  `complete=false`、`claim_status=incomplete`、177 blockers，这是正确结果。

## 非声明与下一步

V15 不证明自然执行或运行时可达、全局 caller/code/producer/indirect/computed/RAM
target 分母、callee ABI 或业务语义、literal 业务含义或 compiler authorship、hole/
相邻字节是 padding/free/allocatable、编辑、写回、重定位或 gameplay behavior。

下一闭环优先独立冻结 menu portrait LZ77 endpoint→palette 起点之间的短零对齐间隙。
只读筛选给出 52 段 / 110 bytes，但这不是可直接写入的合同；必须先从 ROM、LZ77
canonical artifact 与 palette canonical artifact 独立重建完整分母，并对零值、紧邻、
align4、current-unknown 与 mutation fail-closed 逐项验证。合同冻结后才适合 Luna max
实现，父代理负责 canonical、coverage、proof 与 formal 验收。
