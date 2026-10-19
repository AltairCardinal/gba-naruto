# 菜单肖像调色板物理分母（2026-08-20）

## 结论

`rom-menu-portrait-palette-inventory-v1` 从基准 ROM、固定目录表、selector、五条
GPU queue caller 和既有写回合同独立重建菜单肖像调色板分母：311 个固定逻辑输出
收敛为 74 个资源，再按物理 palette 指针/range 去重为 70 段互不重叠的 128 字节
BGR555 数据，共 8,960 字节。70 个物理范围只有 54 种内容哈希，因此不能按内容
哈希继续合并。

正式 artifact：`artifacts/rom-menu-portrait-palette-inventory-v1/`。

## 固定分母与来源

- 基准 ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`；
- 63×5 目录表中 record 0 的五个 pair 均为零 sentinel；有效矩阵分母是
  `(63 - 1) × 5 = 310`，再加 variant 5 的 special pair，共 311 个逻辑输出；
- selector 对 record/variant 先做 u8 截断；variant 5 选择 special pair，其余路径
  使用 `base + record8 × 40 + variant8 × 8`。selector 本身没有 bounds check；
- 74 个唯一 `(gfx_pointer, palette_pointer)` 资源按物理 palette 指针/range 形成
  70 段，每段 128 字节且两两不重叠；
- 唯一跨资源物理别名为 `0x084098C4`（文件范围
  `[0x004098C4,0x00409944)`），由资源 `[0,67,68,69,70]` 共用，覆盖 56 个逻辑输出；
- 物理 range 分母 SHA-256：
  `84e8b9f99a51f94e1b9e0b972d6458c883428443aa173a9f739beaf601b4e338`；
- 按物理地址排序的 8,960 字节 bundle SHA-256：
  `d5d80e37d88000ec81501d9549b4c6038c42e6ec172614127821213d9dbcdccc`。

## 失败关闭与验收

exporter 与 verifier 分别从原始 ROM 重建表、special pair、selector、五条 queue
caller、128 字节上传长度、资源别名和物理范围；verifier 不导入 exporter。TDD 覆盖
BNE 条件码、u8 截断、caller/queue 语义、source hash、非规范 JSON、缺失或额外成员、
相对 root、祖先/member symlink、bundle/manifest 重签篡改以及正式 artifact 身份。

最终身份：

- manifest SHA-256：
  `8a8675c2724131a6caa9b956825d74280fa26fe99447470b3cc3810688e6f88b`；
- payload SHA-256：
  `ac263fc071b6c6ad4b94b649df38560c180f2b2fd350212cc3875055146d908d`；
- verifier SHA-256：
  `63d60ffe786841d910b0655de31cbb4a3d52178b433fc1a40b24729f683cda46`；
- 独立 verifier：`verified=true`、`errors=[]`、311/74/70、8,960 字节、
  overlap 0、alias group 1。

## Coverage

70 段在接入前逐字节均为 current unknown，且与既有 primary claim 无交叠；coverage
不切片，每段只生成一个物理 claim。本批净增 8,960 字节和 70 个 claim。接入后：

- classified：`6,102,121 / 6,291,456`（`96.9906%`）；
- unknown：`189,335`（`3.0094%`）；
- claim：`13,872`；segment：`16,119`；
- coverage SHA-256：
  `b95e1239420e416fe03244d8e3584adc5dd93470dfa8bfe8e501addb78c3f2cd`。

## 边界

本批只证明固定目录分母中的 128 字节物理 BGR555 palette 及固定长度写回能力。它不
声明任意动态 caller 输入、全部逻辑项自然玩法可达、运行时最终像素等价、graphics、
相邻 gap、free space、任意尺寸写回、指针改写或 relocation。共享
`0x084098C4` 原位修改会同时影响五个资源；若要独立拆分必须另证 relocation。

## 正式证明收据

- report：`build/experiments/active/menu-portrait-palette-formal-20260820/report.json`；
- report SHA-256：
  `431829ea84d9f58b42164bd272852793b5e590dd87655328058a2a917e755809`；
- guard SHA-256：
  `347e78e625ed6be0f09052afcd405c751f3eb6c7870e40452e0a56ec2d470226`；
- proof spec SHA-256：
  `28ab2d060fd871d638025c1349da3f6c9dfc5ff9a5e2912653d02522ba8b90f0`；
- formal auditor SHA-256：
  `4e5b95705a2aa8252da96f927872a6701bb1561b6748230cbc4c209815e28d36`；
- 64/64 唯一 verifier 均 `exit_code=0`、`contract_ok=true`；ROM byte gate 54/54；
- guard 峰值 RSS：519.89 MiB；
- 报告保持 `complete=false`、`claim_status=incomplete`、175 个 blocker，因为
  unknown 尚有 189,335 字节且其余全局门禁仍未完成。
