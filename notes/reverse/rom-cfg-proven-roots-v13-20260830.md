# ROM CFG proven-roots v13 验收记录

## 结论

CFG proven-roots v13 已完成 canonical artifact、独立 immutable bundle、coverage、
proof 与受守卫 formal audit。该里程碑只把 392 个接入前为 `unknown` 的字节分类为
312-byte bounded Thumb code 与 80-byte instruction-consumed literals；它没有把全
ROM ARM/Thumb code map、自然运行时可达性、间接目标、业务语义、编辑/写回/重定位或
可分配空间声明为已完成。

接入后的 canonical coverage 为：

- classified：6,126,775 / 6,291,456（97.3825%）；
- unknown：164,681（2.6175%）；
- primary claims：14,558；
- segments：16,673；
- coverage SHA-256：
  `e8787f8e200e84b2966c6f6b8c70ea164a0f90d81348d88e5daa614ea3cb8004`。

全局 proof 仍正确报告 `complete=false`、`claim_status=incomplete` 与 175 个
blocker，不能把本包合同全过扩张成“逆向 100%”。

## 冻结输入与产物

- 基准 ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- source root：file `0x0612BC`；237 instructions、40 blocks、508 instruction
  bytes、17 opaque external calls、0 frontier。
- 固定目标 `0x080651F8` 的全 ROM target-limited 直接 producer 分母只有一条：
  file `0x0614D0` / GBA `0x080614D0`，raw Thumb BL `03 f0 92 fe`，目标
  `0x080651F8`。source/producer 字节保留既有 owner。
- target root：file `0x0651F8`；153 instructions、25 blocks、312 instruction
  bytes、21 literal references / 20 unique literal words、80 literal bytes。
- promotion ranges：3 段 code 加 3 段 literal，共 6 段 / 392 bytes。
- 明确保留 unknown 的 holes：`[0x0652DE,0x0652E0)` 与
  `[0x06536A,0x06536C)`，均为 raw `00 00`；零值和邻接关系不证明 padding、NOP、
  reserved/free/allocatable space。
- 唯一 frontier：`0x065368 bx r0` / `indirect_pc_target`。虽然调用形态可能像返回，
  当前证据没有解析 `r0`，因此 `structured_return_proven=false`。
- manifest SHA-256：
  `589dd8e1536b2b6d0cc3997f31c5841204593f64ce491d6c0647ca7230f8e133`。
- payload SHA-256：
  `45b83aeb6e91249ebd5adefdb086c438b14c666e79aab780f7072a929343cb5b`。
- legacy verifier SHA-256：
  `a687af7750e9a177b47883f1b540d555bd4c666d92865d56e521f85174c869a7`。
- immutable wrapper SHA-256：
  `0fe1b8c1d1aa1a191d8bc7e210db952551e4b54aceeed1c13aecd9db6c12c272`。

wrapper 在动态加载 legacy verifier 之前和之后，都用自身导入的 `hashlib` 与安全路径
检查锚定运行时依赖；不能由被验证依赖提供的 `_sha` 或 `_safe_file` 自证身份。独立
standalone report 位于
`build/experiments/active/cfg-proven-roots-v13-red-20260829/bundle-report-r2.json`，
SHA-256 为
`1af5b070de422596e403f722d10f765c821c14d95c2d1f7547e1e831fb5ea5e6`。

## TDD 与集成验收

所有高开销命令均通过 `tools/run_guarded.py` 串行取得
`build/experiments/heavy.lock`；未使用 `--allow-degraded`。

- exporter 正确 RED：log / guard SHA-256 为
  `0213210621963e184db7ee33036024d625d5f564f023bd04e0f414625d94eed7` /
  `cd3c17985e0d8d66cd391d87e2ac9469395a242d13a64c6a411e876ffb705e8f`。
- exporter/verifier 完整 GREEN：log / guard SHA-256 为
  `c546a8d08faa40fdd127236a9d52aaa6a73ab69a1faca41ed0bccaaacbea3e2c` /
  `b34d57c7c216722cc79c5e84370e29c34de4c42cf875c6e1c138c0fca593c536`。
- dependency-first 加固正确 RED：log / guard SHA-256 为
  `3487f43afb2ed1e2286c45a0e1da15053acc11574ce903396d3c2d6ab29c8118` /
  `d8c171ef92a9585b9ba92f4e11ca2531fc4c9da100307180f5f2c21e88cc385c`。
- bundle 完整 GREEN：log / guard SHA-256 为
  `cee620a12bdf59120c0f4a798e2e5e6c0b4acffdc738024b6f5e70974db06cc5` /
  `cfa2f16268a2f6c2c195ce8b70f75fe4225f0efa7c4b70251fa4ec6f3f43e52d`。
- coverage 正确 RED：log / guard SHA-256 为
  `6a9852b86757852d949834f5382586206ca74e1ef96c3d0be9cf4bd0102596aa` /
  `85f00043c06e34f69c19dd7d4ee6dded12a5a1616973088c335267bf2f06d7d6`。
- focused coverage GREEN：5/5；log / guard SHA-256 为
  `48de0773c55cbce6498f41a161d0f40e79319a69857da6ae720e1ec6ec4cb5d8` /
  `91f0ec68828a36998ee35efb4908926a6a886b95e8384fff111674d628e18f21`。
- canonical coverage write report / guard SHA-256 为
  `270a47009c1df22fcb3380865fb9eb97c12756bac5c85fac13e9ef0ab0a5cfd5` /
  `e53b3707fced9f3515fde1355f202101bc219ae52c1d1afc79f78057216f24f7`。
- proof 正确 RED：log / guard SHA-256 为
  `b605dde6573e6aec5680052bf5ad086c652f5fcf95473bc2842caabbae06dd58` /
  `036ce3775411e4f8970ab1bd9075ce7c37c045e7df5cedd1dcb58ba38475d165`。
- V12/V13 focused proof GREEN：2/2；log / guard SHA-256 为
  `ad61be9b74efb8a4b8ae7d0427622d79c722d44dc55c2f4aeb51140568dfc278` /
  `f32ae85470b76a3bb47b36c7f35e495fcef25d15dda66a19da619178d3b4054c`。
- proof 全模块 GREEN：72/72，1,258.222 秒，非降级、峰值整树 RSS
  421.3359375 MiB；log / guard SHA-256 为
  `d977ff5f8a5d010eb600efab8b5d4abf6bfd01a603ff488ff746d8d1212c59a6` /
  `b2f447ac74fbfc8c4218c3d6c99cbad6143e0a7b28638790cacd926281607263`。

## 正式 proof 审计

唯一正式命令实际执行 `--execute-verifiers --allow-incomplete --output`，没有外部
trust anchor，也没有用 `--allow-degraded`。结果：

- 90 个唯一结构化 command，90/90 `exit_code=0`、90/90
  `contract_ok=true`；
- ROM byte gate：80 个 hash-bound verifier、80 个 contracted verifier；
- bank contract：10 个；proof spec 另有 11 个只作哈希绑定证据的旧 gate
  verifier，所以 gate 引用总数是 91，不能误写成 91 次实际执行；
- V13 bundle 在正式报告中恰好执行一次并通过；
- report 仍为 `complete=false`、`claim_status=incomplete`、175 blockers；
- 耗时 3,139.922584 秒，守卫非降级，峰值整树 RSS 661.4140625 MiB；
- report SHA-256：
  `6bced154df1d4ca3940f597f64ef36bb5ebd8c3f9d995f62fce34ad92b8793c2`；
- guard SHA-256：
  `23893d0b4996fac334cc4b93596e1e3a28ee5cc7302636c5abd5b8b34037d369`；
- proof spec SHA-256：
  `1818d80f92cf3cf28e4f473d954cd1e900e8b42bb3cf430052651c7c27594e1a`；
- coverage auditor SHA-256：
  `56f7ebc073678e79f9ba5328be508e98ee4c33095f20120976baaa0718353d79`；
- formal auditor SHA-256：
  `1562de7b02fc781b79ede13a29a03137a02082ff2aa59b3ec212b90ae797104b`。

## 已知浪费与模型编排

- 一次 proof RED 使用了错误 unittest class 名，约 1 秒即失败；它不是有效 RED。
- proof 全模块首次运行因守卫 `idle-timeout=600s` 过短，在 CPU 正常工作的第 10
  分钟被终止；保留 guard SHA-256
  `b61aec49c6b1b598976a7bdb52334743a6033215ba2c925032a97f8c2c539e2c`，
  后续用 1,800 秒 idle 阈值一次通过。该约 10 分钟属于可避免的守卫配置浪费。
- 两个 Luna max 只读整理任务在限定窗口内没有返回可用产物，已终止；这是任务粒度/
  执行纪律问题，不是工作区或资源 blocker。
- Sol medium 只读 review 找到 dependency-first 锚定和 build-manifest 集成覆盖两项
  P1；本体完成 TDD 修复后，第二次 Sol medium proof review 未发现 P0/P1。
- V14 候选的 Sol medium 输出仅是草稿，未作为 V13 证据，也未写入 artifact 或
  coverage。

## 下一步边界

只读候选预筛把 `0x0624C0` 与 `0x062510` 双 root 列为 V14 首选，预估最多覆盖
160 个 current-unknown 字节；五条 direct producer 声称均来自 V12/V13 已有 owner，
两个 closure 各保留一个 `bx r0` indirect frontier。开始 V14 前，本体必须独立重放
current coverage identity、全 ROM target-limited producer 分母、source membership、
两套 bounded worklist、literal 投影和 frontier。任一项不一致即失败关闭；Sol 草稿
本身不能成为晋升依据。

> 后续状态（2026-08-30）：上述草稿已由 V14 独立 preflight、accepted artifact、
> immutable bundle、canonical coverage 与 formal-r2 取代；本段只保留 V13 当时的
> 下一步记录。V14 的当前证据见 `notes/rom-cfg-proven-roots-v14-20260830.md`，不得
> 用 V14 数字改写本文件冻结的 V13 coverage、holes、frontier 或 formal 收据。
