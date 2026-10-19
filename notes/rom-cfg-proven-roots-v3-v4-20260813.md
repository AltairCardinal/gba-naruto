# CFG proven roots v3–v9（2026-08-13 至 2026-08-21）

## 目的与边界

本批复用“固定直接分支 producer 证明的新 CFG 根与冻结基线增量”模式，只把固定
Thumb BL producer 所证明 root 的静态可达指令字节晋升为代码。既有 CFG 入口均作为
opaque stop；不声称自然运行时可达、全 ROM 函数入口穷尽或全局代码图。

基准 ROM 为 6,291,456 字节，SHA-256
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。

## v3：root `0x070DF8`

- 全 ROM target-limited 分母恰为两条 Thumb BL：`0x074192`、`0x074836`。
- 冻结 v2、v3、proven-roots v1/v2 与 battle-controller 五组基线。
- 独立 raw-control-flow verifier 重建 52 条指令、8 个 block、110 字节、0 frontier、
  5 条进入 v2 的 baseline cross-edge。
- 两条 producer 已由 controller CFG 分类，因此只作 provenance；8 个 block 的 110
  字节全部从 current unknown 晋升。
- artifact：`artifacts/rom-cfg-proven-roots-v3/`；manifest SHA-256
  `4aa979aa65408163e577f7d728ba32a99a13bd6c9615c40f28a570036e5ba275`。

## v4：root `0x07305C`

- 全 ROM target-limited 分母恰为四条 Thumb BL：`0x073696`、`0x0736C4`、
  `0x07444E`、`0x0749CE`。
- 在 v3 基础上再冻结 proven-roots v3，合计六组基线。
- 独立 verifier 重建 486 条指令、118 个 block、1,044 字节、6 个
  `indirect_pc_target` frontier、29 条进入 v2 的 baseline cross-edge。
- 四条 producer 均只作 provenance；118 个 block 的 1,044 字节全部仍为 unknown，
  因而可逐块晋升。6 个间接目标保持失败关闭，不扩张推断。
- artifact：`artifacts/rom-cfg-proven-roots-v4/`；manifest SHA-256
  `e306ac59b4b9a815702fda8aef54058908fb9113a5afad4be938c69d42d67404`。

## 覆盖结果与资源证据

- 批前：classified 6,018,929；unknown 272,527。
- 批后：classified 6,020,083；unknown 271,373；语义覆盖 95.6866%。
- 净增 1,154 字节；`semantic_classification_complete` 仍为 false。
- v4 coverage 写入及自审经 `tools/run_guarded.py`，峰值 owned-tree RSS 256.16 MiB。
- MiniMax-M2.7-highspeed 仅用于只读候选归纳；其对 v3 的 4–8 KiB 收益估算与本地闭包
  110 字节不符，已被本体拒绝。模型输出不作为证据，所有数字均来自本地 artifact、
  verifier 与 coverage audit。
- Terra 只读 reviewer 随后发现 standalone v3/v4 verifier 未独立校验 cross-edge
  denominator 哈希，也未固定绑定 ROM、frozen baseline 与 scope。四项“篡改 payload
  并重算 manifest”负测先 RED，修复后全部 GREEN；加固后的 coverage 写入与自审经
  heavy lock 通过，峰值 253.05 MiB。该缺口已明确修复，不再依赖 coverage 外层固定
  SHA 作为唯一缓解。

## v5：roots `0x06DF88`、`0x08A534`、`0x08A588`

- 三个 root 各有且仅有一条全 ROM Thumb BL producer：`0x0736DE`、`0x073702`、
  `0x073780`；producer 已由 controller CFG 分类，只作 provenance。
- 冻结 v4 及以前七组基线，独立重建 576 条指令、124 个 block、1,252 字节、
  8 个 `indirect_pc_target` frontier 和 40 条 cross-edge（39→v2、1→v1）。
- 124 个 block 全部仍为 current unknown，正式晋升后 classified 为 6,021,335，
  unknown 为 270,121，语义覆盖 95.7065%。
- v5 从首版即固定校验 ROM、frozen baseline、scope 和独立 cross 哈希，并有篡改
  payload 后重算 manifest 的负测。coverage 写入与自审峰值 261.75 MiB。

## 同表 renderer 零 padding

复用“固定消费者记录闭包”的低成本脚本模式，对 625 条 renderer 文本按
`candidate_ids` 分组，只接受同表相邻记录之间逐字节全零的间隙。548 段合计 12,431
字节，每段首字节篡改均使 verifier 失败；跨表零段和非零间隙排除。接入后 unknown
为 257,690，覆盖 95.9041%。

## 固定消费者、字库与 LZ77 对齐 padding 增量

- fixed-consumer：570 条固定记录中，仅接受相邻记录共享 `table_id` 且间隙逐字节
  为零的 429 段，共 4,141 字节；跨表与非零间隙排除。
- dialogue font：26 个固定 SJIS source extent 中，只接受相邻 extent 的近端全零
  间隙，19 段共 2,848 字节；1 个 2,048 字节非零间隙及 1 个跨外置区域远间隙排除。
- LZ77：独立重建 896 条 4 字节对齐且有对齐 ROM 指针引用的严格 stream，仅接受
  parser 终点到紧邻下一固定 stream 起点的 1–3 字节全零对齐，341 段共 648 字节。
- 三组 verifier 均固定 ROM/上游分母并逐段篡改失败关闭，且提供结构化 JSON CLI；
  正式 coverage 写入与写后自审均经 heavy lock 通过。
- battle-presentation 固定 79 槽消息表另闭合 78 段/1,293 字节零间隙；随后 v6
  固定 6 条 Thumb BL producer 与 5 个 root，独立重建 12,564 条指令、2,305 个
  block、27,224 可达字节、85 个保留的间接 PC frontier 和 916 条冻结基线
  cross-edge。只晋升 block 与 current unknown 的交集 25,926 字节，1,298 个已分类
  可达字节不重复认领。
- 该批接入后覆盖为 classified 6,068,622、unknown 222,834、claim 12,978，语义覆盖
  96.4579%；`semantic_classification_complete` 仍为 false。
- 随后复用同一 fixed-consumer artifact，新增 active-action description 87 slots
  （10 null/77 unique records）与 ninja-tool description 的非重叠 slots 6–93
  （88 records）。11 表合计 750 slots、735 records；新增记录/表和同表零间隙净增
  7,694 字节，权威覆盖更新为 classified 6,076,316、unknown 215,140、claim
  13,306（96.5804%）。
- `sprite-definition-assets-v2` 已独立验证的 43 个 component-list `0x28` resolved
  window 与 current unknown 相交为 3 段/1,720 字节；接入后 classified 6,078,036、
  unknown 213,420、claim 13,309（96.6077%）。
- MiniMax-M2.7-highspeed 只读草稿包含 controller/v4/v5 等过期建议，已由本体依据
  最新 artifact 与 coverage 拒绝；有效线索仅用于候选分组，不作为分类证据。

## v7：两个固定 dispatcher 表

- v6 的 85 个间接 PC frontier 中，83 个由原始指令固定为 `bx r0/r1` return 型，保持
  opaque；另两个 `mov pc,r0` 分别绑定 `0x06E868` 的 7 项表和 `0x092864` 的 38 项表。
- 固定 proof window、index 上界、literal、完整有序 table vector 后共有 21 个唯一目标；
  其中 13 个已是 v6 冻结基线入口，故仅以其余 8 个目标启动增量 worklist。
- 独立 verifier 从 ROM 重建 155 条指令、38 个 block、332 字节、17 条 cross-edge；
  新闭包在 `0x06D6B4` 保留 1 个 `indirect_pc_target`，不继续猜测扩张。
- 38 个 block 全部与当时 current unknown 完全相交，正式晋升 332 字节。权威覆盖更新为
  classified 6,078,368、unknown 213,088、claim 13,347（96.6130%）；
  `semantic_classification_complete` 仍为 false。
- artifact 为 `artifacts/rom-cfg-proven-roots-v7/`；payload SHA-256
  `184e9b84df829fb1ad41f272aabe931c1a1f86111eebd60629ad2d2a23d89a06`，manifest
  SHA-256 `da9a1b5fe7ce8e7889fbba9fe8251c907ed18f6b273cbcc3be145101ece99114`。
- coverage 写入及写后自审经 heavy lock 完成，耗时 14 分 03 秒，峰值 owned-tree RSS
  267.88 MiB。只读 sidecar 曾错误预计 21 个新 root、32 block、0 frontier；本体按
  ROM 与 v6 基线复算后拒绝这些数字，未将草稿作为证据。

## v8：scene visual source 证明的单根闭包

- 上游 `scene-visual-packs-v1` 的 source manifest、独立 verifier 和
  `/consumer_evidence/setup_and_initial_row` selector 均从传入 root 重新读取并哈希
  绑定；不能只信 v8 artifact 自报的 source identity。
- 全 ROM target-limited 分母唯一命中 Thumb BL
  `0x0808BE5C→0x0808B99C`。producer 与 source consumer slice 已有更具体分类，
  因而只作 provenance，不产生重复 primary claim。
- 以 v7 及此前所有 CFG artifact 为冻结 baseline，独立 verifier 重建 113 条指令、
  20 个 block、246 个可达字节、10 条 baseline cross-edge，并保留 1 个
  `indirect_pc_target` frontier。20 个 block 均完整落在当时 current unknown。
- exporter/verifier 的 baseline loader 不跨调用缓存；同一进程内任一依赖漂移都会在
  下一次装载时被重新读取并失败关闭。
- artifact payload SHA-256
  `3e1c62c7c330ab54fabb5b1db33a15a977bf070c22ac1cacba2c908762689dda`；manifest
  SHA-256 `9c3b4c4c02981930646ab4b451ec7a5db6a03f00a184217cefe25a9ecf7f9b56`；
  verifier SHA-256
  `96555718fbb371ea705fe620022a8310f5a6874ae7315cc48d50309dc8a26d85`。
- 正式接入后 classified 6,078,614、unknown 212,842、claim 13,367
  （96.6170%）；coverage SHA-256
  `49ee896c7b7a71a523a40bfc7823b62cee01b02b8d3947ba3e2acf3128af572c`。
- 受守卫 formal audit 执行 60 个唯一 verifier，60/60 `contract_ok=true`，峰值
  owned-tree RSS 408.28 MiB。该结果只证明当前 partial 合同自洽；未解析间接目标、
  相邻代码洞、自然运行时可达及全局函数分母均不声明。

## v9：controller provenance 证明的八根闭包

- 全 ROM target-limited 分母固定为 11 条对齐 Thumb BL。其中 9 条既是
  `rom-battle-controller-cfg-v1` 的已解码 source instruction，又有对应的
  `outside_controller_range/call_target` opaque edge；另外两条
  `0x0736A4`、`0x07445C` 虽是合法 BL 编码，但不属于冻结 controller CFG 的
  source instruction，只保留为 `provenance_excluded`，其 8 个字节继续 unknown。
- 9 条 controller producer 证明 8 个 root：`0x0806C010`、`0x0806C308`、
  `0x0806C40C`、`0x0806D46C`、`0x08070DD8`、`0x08073000`、
  `0x08075350`、`0x080753F8`。
- 独立 ARMv4T raw-control-flow verifier 在 v2/v3、proven-roots v1–v8 与
  controller CFG 冻结基线上重建 299 条指令、62 个 block、628 个可达字节和
  16 条 baseline cross-edge。7 个 `pop rN; bx rN` 只登记为 opaque return exit，
  不冒充已解析的间接目标；真正 frontier 为 0。
- 62 个完整 block 在接入时均属于 current unknown；coverage 只晋升这 628 字节，
  不重复认领 9 条已有 controller producer，也不晋升两条 excluded producer。
- artifact manifest/payload/verifier SHA-256 分别为
  `1914d6244ceaa7791cb4c77d97143151b4f28183ea857c052c9c51d3c8a09e6b`、
  `fb961c6d0ba5cdb56c016a5d10b149d87e5ce9158bcb1e6e9deae8664c46555b`、
  `b75ed5bad517fb08ebf2ae08d336c1dcee6ab334c4927559f41a2fcfad399935`。
  coverage 写后 SHA-256 为
  `778a4a856cadfe222dd415950a6c356e94bf3ee64b58ab5a4ad3a00231e38458`；
  classified 6,106,406、unknown 185,050、claim 13,991、segment 16,239
  （97.0587%）。
- 本批不证明自然执行、全 ROM 函数入口、全局 BL/间接目标穷尽、编辑或重定位安全，
  也不把 opaque return 的动态返回地址宣称为已解析目标。
