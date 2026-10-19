# 第二批 direct-call-proven CFG 根（2026-08-12）

## 结论

基准 ROM：
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。

对三个固定 Thumb 目标执行全 ROM、2 字节对齐、目标限定的 BL 解码扫描，完整分母
恰为五条 producer：

| producer offset | raw | target offset |
| ---: | --- | ---: |
| `0x073690` | `f7f704ff` | `0x06B49C` |
| `0x07425A` | `10f0cdff` | `0x0851F8` |
| `0x07434E` | `10f053ff` | `0x0851F8` |
| `0x074448` | `f7f728f8` | `0x06B49C` |
| `0x074F2C` | `f3f73afd` | `0x0689A4` |

三根入口均不属于 v2、v3 或首批 proven-roots 的已占字节。新遍历把三份已验证
baseline 的精确入口视为 opaque stop；跳入已有指令中部或新指令跨越 baseline 字节
时失败关闭。

## 冻结分母

- roots：3；producer：5；
- Thumb 指令：4,809；basic blocks：835；指令字节：9,876；
- frontiers：28（27 `indirect_pc_target`、1 `unsupported_armv4t_instruction`）；
- baseline cross-edges：82，全部为 `call_target` 并指向 v2；
- producer vector：
  `8cc04030df779e573950c4d1ad00b480368444439af3cc4ec97f62624c6c76c3`；
- root vector：
  `36e5c9045b5d7ffb931c3dc145d790b1965c18829757bf9b8ca347ed00caae19`；
- frontier vector：
  `5878c2596fecd2eeabe4205f688413f03488f006491440fd71e48e404d671838`；
- cross-edge vector：
  `b0123d804c3e083bcf123cece476c79f555f949f053f33a5c73b18ab0b765698`；
- graph denominator：
  `4cb6844907b0a0679c52e5ac9b251d3cc1b5db8d1d1cf1108c9b4ee507a14a1a`。

产物：`artifacts/rom-cfg-proven-roots-v2/`，仅含 manifest 与 payload：

- manifest SHA-256：
  `a3683f3d21ec5a162b4cdb97c70b639ff261d9ff5e0f3bb4941848205bb4d9ca`；
- payload：696,273 字节，SHA-256：
  `a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba`；
- verifier SHA-256：
  `3d834e1e92c1ea1c7cf4146ac6f23b940ea864c69783c341af64ba462545fe55`。

独立 verifier 不导入 v2 exporter；它重新扫描 producer、验证三份 baseline、使用 raw
ARMv4T decoder 重建 worklist、block、frontier、cross-edge、root 结果、graph 与
manifest。正常 CLI 始终严格绑定当前实现哈希。原子替换预检仅可显式放宽旧 artifact
的三项 implementation 哈希，其他 ROM、CFG、graph、payload 与 manifest 合同仍完整
验证，从而避免“源码升级后旧 artifact 永远不可替换”的更新死锁。

## Coverage 变化

在首批 proven-roots 已接入的 baseline 上，835 个 block 的全部 9,876 字节仍为
unknown；相邻合并后形成 86 个代码 claim。五条 producer 另形成 5 个 claim、20
字节，均不与闭包代码重叠。

- classified：`6,002,861 → 6,012,757`；
- unknown：`288,595 → 278,699`（`4.4298%`）；
- claims：`8,961 → 9,052`；
- CFG promoted unknown：`96,980 → 106,876`。

`sequel/rom-byte-coverage.json` SHA-256：
`ca8d02d8312ea44ca11c84b926f98fcfffe693eb904e473f4fad6bae622131ec`。

## 验证与资源记录

- producer RED：缺少 v2 exporter，按预期 import 失败；最小 producer/root 实现后 3 项
  测试通过；
- closure GREEN：42.4 秒，峰值 172.0 MiB；
- exporter/verifier 完整测试：2 分 55 秒，峰值 184.7 MiB；
- 仓库 artifact 严格验证：29.4 秒，峰值 188.8 MiB；
- 最终导出：1 分 41.6 秒，峰值 177.0 MiB；
- coverage helper：66.6 秒，峰值 191.6 MiB；
- coverage 写入及独立重建：8 分 56 秒，峰值 224.5 MiB；
- coverage 三项定向集成测试：5 分 16 秒，峰值 206.9 MiB。

正式证据审计通过：在受守卫进程中执行 48 次 verifier，全部 `exit_code=0` 且
`contract_ok=true`；ROM coverage gate 的 38 个结构化 verifier 合同全部有效，
trust anchor 与预先冻结的 proof spec SHA-256
`e94755ae355901926d694487a3ad3fd6330f1e7cbccdd3ca208d8e025dd5083b`
一致。审计总耗时 11 分 34 秒，峰值 217.0 MiB，无降级、超时或内存异常：

- 报告：`build/experiments/active/cfg-proven-roots-v2-20260812/formal-audit.json`，
  SHA-256 `e94ad1c3388eaacf8a7769d96a4373b219f97c7fcb9f3302cfe01163a5368f71`；
- guard：`build/experiments/active/cfg-proven-roots-v2-20260812/formal-audit.guard.json`，
  SHA-256 `72ff100be405ef2be296ba5971b78d857b4a66ef704972a1b640050696a32217`。

审计的 `complete=false` 是预期的失败关闭结果：仍有 278,699 个 unknown 字节，且
编辑器、逻辑修改、干净重建、模拟器与实机门尚未完成；它不代表本批 verifier 失败。

一次向量展示命令因使用错误字段名浪费约 45 秒；一次旧 artifact 重导出揭示实现哈希
更新死锁，未覆盖原产物。两次均由 guard 留下记录，未发生内存异常、mGBA 启动或
大规模临时文件生成。

## 不主张内容

- 不证明三个根在自然玩法中一定执行；
- 不解析 27 个间接 PC target，也不外推 unsupported instruction 后的控制流；
- 不声明全 ROM 函数入口、全部 Thumb BL 或全局代码图分母；
- 不重复认领 v2、v3、首批 proven-roots 的任何字节；
- 不改变 `semantic_classification_complete=false` 与 Goal 的严格 100% 标准。
