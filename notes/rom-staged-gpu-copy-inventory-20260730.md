# RAM→GPU 两段搬运有限分母（2026-07-30）

## 结论

`artifacts/rom-staged-gpu-copy-inventory-v1/` 将已有证据中同时固定 RAM slot、
GPU consumer、长度或公式、producer 类型与代码哈希的路线收敛为有限 allowlist：

| family | RAM slot | GPU route | 分类 |
|---|---|---|---|
| shadow OAM | `0x0300027C..0x0300067C`，1024 bytes | CpuFastSet `0x08061346` 或 DMA3 `0x08061386` → `0x07000000` | `metadata_excluded` |
| overview tiles | `0x02002AB0..0x02002C10`，352 bytes | `0x0808D9C6` → `0x06002000` | `procedural_excluded` |
| overview palette | `0x02002C10..0x02002C30`，32 bytes | `0x0808DA0E` → `0x050001A0` | `procedural_excluded` |
| overview tilemap | `0x02002C30..0x020030E0`，1200 bytes | `0x0808DA6E` → `0x06000000`，30×20、destination stride 32 | `procedural_excluded` |
| battle status bar | `0x0201BD84..0x0201BE24`，160 bytes | 五个 32-byte tile → 动态 BG VRAM | `procedural_excluded` |

分母为 3 个 consumer family、5 个 RAM slot、6 条 GPU copy route；接纳 raw
ROM source 为 0。零结果是有效排除：OAM 是 renderer 生成的属性 metadata；
overview 由 `0x0808D934..0x0808DA80` 算法生成；status bar 由
`0x08068370..0x08068642` 从 initializer template 和填充公式生成。三者均不能
从 RAM 内容相似性反推为新的 ROM 原始图像。

## 证据门禁

- base ROM SHA-256 固定为
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`；
- OAM VBlank callback、overview generator、status-bar generator 均从 ROM
  重算代码哈希；
- 三份上游 artifact 数据与 promotion manifest 均记录路径和 SHA-256；
- exporter 只生成 JSON 与 manifest，不为零接受项创建空 bundle；
- 独立 verifier 不导入 exporter 或 `tools.*`，从 ROM 与上游成果重建完整
  payload/manifest；
- RAM 地址、分类、copy size 或 scope 即使篡改后重签 manifest 也会被拒绝。
- staged-copy、direct DMA、direct CpuSet 与 pointer-LZ77 相邻回归经同一 heavy
  lock 完成，exit 0，owned-tree peak RSS `39.796875 MiB`，无降级或残留进程。

## 边界与下一步

本成果只闭合 hash-bound allowlist，不声称枚举全部 ROM→RAM producer 或
RAM→GPU consumer。以下路线仍不在本分母：

- 对话 tilemap `0x0200A900+` 的最终 GPU submit 尚未固定 source、长度和提交
  routine；
- 通用 asynchronous transfer queue 的 record ABI 与 submit function 尚未闭合；
- 对话 glyph 是 ROM 2bpp→VRAM 自定义展开，不属于两段 copy，已由
  `dialogue-font-v2` 单独覆盖；
- 非 literal DMA、跨函数 wrapper、其他 custom loop 与未跟踪视觉状态；
- 通用未压缩图像回写。

因此下一条图像主线应优先闭合通用 transfer queue ABI 或枚举固定地址 custom
copy loop，不能把本轮零 raw source 误报为两段搬运已经全量完成。本轮未启动
mGBA，也没有产生新的快照或高内存实验。
