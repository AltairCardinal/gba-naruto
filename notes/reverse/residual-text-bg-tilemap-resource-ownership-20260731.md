# 残余 text-BG tilemap 资源归属（2026-07-31）

## 结论

`0x08349368` 的 32×20 text-BG tilemap 已静态绑定到完整 BG、graphics 和
palette 资源链：

- tilemap：`0x08349368`，178→1,280 bytes，写入 `0x06001000`；
- BG：BG2，`BG2CNT=0x0204`，charbase 1、screenbase 2、4bpp；
- graphics：`0x08348F00`，907→2,176 bytes / 68 tiles，经
  `0x0808B5D4..0x0808B5D8` 写入 `0x06004000`；
- palette：raw `0x0834941C`，32 bytes，经 `0x0808B5DC..0x0808B5E2`
  写入 `0x05000020`，即 BG palette bank 1；
- tilemap 只使用 tiles 0–5，完整落在 graphics 的 tiles 0–67 内，且全部 entry
  使用 bank 1。

这组 tiles 0–5 与同一资源初始化链中 `0x0834928C` overlay 使用的 tiles 6–67
互补，不发生 tile index 重叠。

## 自然静态链

`0x0808B58C` 先加载 graphics 和 palette。它的两个直接入口是
`0x0808F844`、`0x0808FA04`；其循环在 `0x0808B640` 调用
`0x0808B2C8`，后者设置 BG2 并于 `0x0808B348..0x0808B34C` 把 tilemap
解压至 screenblock 2。

独立 verifier 不导入 exporter，而是从基准 ROM 重做两次 LZ77、tilemap entry
统计、BG 位域、palette 字节、五个代码窗口及四份上游 artifact 哈希。重新签名后
篡改 graphics VRAM 目标会被拒绝。

正式证据：

- `artifacts/residual-text-bg-tilemap-resource-ownership-v1/`
- `artifacts/residual-text-bg-tilemap-relocation-v1/`

迁移 spec、importer、exporter 和独立 verifier 均固定 ownership 路径与 payload
SHA，并交叉检查 BG2、tiles 0–5/0–67 和 palette bank 1。

## 边界

本成果证明资源归属和静态 caller 链，不证明：

- 两个自然入口已在现有 checkpoint 中运行命中；
- `0x08405F10` 的另一条流复用 `0x06001000` 时的跨帧顺序；
- 32×32 screenblock 中未由本 32×20 payload 覆盖的剩余 12 行；
- 精确业务文案、修改后最终屏幕像素或时序等价。

因此运行时 reachability 和最终像素 scope 继续保持未完成。
