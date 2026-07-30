# 角色总览 BG0 过程式渐变来源（2026-07-30）

## 结论

`alternate-character-overview.ss9` 的 BG0 灰阶带不是待寻找的 ROM 压缩图块。
`0x0808D934` 在 EWRAM 中过程式生成 11 个 4bpp tile、16 色灰阶 palette 和
30×20 tilemap；`0x0808DA90` 传入 tile base `0x100`、palette bank 13，并将结果
安装到 BG0。成果位于 `artifacts/overview-gradient-overlay-v1/`。

该来源已经达到 `checkpoint_writer_proven`：

- generator、caller、controller 三段代码分别绑定固定 ROM 哈希；
- 两个直接 Thumb BL 为 `0x0808DAB8 → 0x0808D934` 和
  `0x0808DCFC → 0x0808DA90`；
- checkpoint 中活动 task 2 的 `SP=0x030011D4`、
  `LR=0x0808DF1B`，恢复点 `0x0808DF1A` 位于同一 controller；
- 生成结果与 checkpoint 的三个 EWRAM 工作域、VRAM tiles、PRAM palette 和
  30×20 可见 tilemap 六域逐字节一致，BG0CNT 同为 `0x0002`。

因此不再把 `0x08064700/0x08064A48` 的全局 palette fade 控制误认为渐变 writer。
它们不写目标 VRAM，也不生成 `0xD101..0xD10A`。

## 生成算法

工作域和硬件目的地为：

| 内容 | 工作域 | 目的地 | 大小 |
|---|---:|---:|---:|
| tiles | `0x02002AB0` | `0x06002000` | 352 bytes |
| palette | `0x02002C10` | `0x050001A0` | 32 bytes |
| 30×20 tilemap | `0x02002C30` | `0x06000000` | 1,200 bytes |

tile 256 全零。80 条渐变扫描线按
`pixel_index = floor(y * 15 / 80) + 1` 生成，每行八个像素使用同一 4bpp
索引，形成 tiles 257–266。palette index 0 为 0；其余索引的 B/G/R 五位分量均为
`20-index`。tilemap 的 rows 4–13 各重复 30 次
`0xD101..0xD10A`；其余可见行使用 tile `0x0100`。

三个生成文件的 SHA-256 为：

- tiles：`9c54d11cc0b46d60728f59611b2181241626bfaad61c479536a14dbf0e54a2e4`
- palette：`19b43b15fd2dcc824f03e524fad7a77d990ecb7b79eb3fa876ac862a53b7c7a5`
- tilemap：`9d3188d3ef983613085b4808e19063e4bb1b4be955aa6e67041ae07a73a0d523`

## 对父未知分母的消减

本成果哈希绑定
`artifacts/initializer-resource-pack-v1/initializer-resource-pack.json` 和其
promotion manifest，并从父记录重新计算而非手填进度：

| 范围 | 父分母 | 本次闭合 | 剩余 |
|---|---:|---:|---:|
| 全部 61 个父层未知 cell | 898 / 39 种内容 | 300 / 10 种 | 598 / 29 种 |
| overview BG0 未知 cell | 717 / 17 种内容 | 300 / 10 种 | 417 / 7 种 |

300 个 cell 是 tiles 257–266 各 30 次，且十种 tile SHA-256 均与 generator
输出逐项一致。全零 tile 256 已在父 artifact 中按内容别名分类，不重复计为本次
独特来源。剩余 417 个 overview BG0 cell 包含旧 tilemap/UI 内容，不因本次渐变
闭合而被升级。

## TDD 与独立验证

- 第一次红阶段因导出模块不存在而失败；
- 第二次红阶段分别因缺少父分母绑定、验证器接受重哈希后的公式语义篡改而失败；
- 第三次红阶段因导出器缺少与父 artifact 一致的输出目标安全校验而失败；
- 只读复核后的第四次红阶段证明重哈希后可伪造 runtime checkpoint 描述字段；
- 绿阶段定向测试 10/10 通过；
- 独立 verifier 不导入 exporter 或其他 `tools` 模块，自行解析 `.ss9`、生成
  tiles/palette/tilemap、解码 Thumb BL、复核父分母并重建 PNG；
- verifier 拒绝二进制、payload、manifest、重哈希语义篡改、额外文件及 artifact
  目录符号链接；
- 正式 CLI 验证结果为 `verified=true, errors=[]`。

本轮直接复用已验证 checkpoint，没有启动 mGBA，也没有产生新的导航或进程树。
新里程碑及三个父链测试通过统一资源守卫回归，退出码 0、未降级，峰值进程树
RSS 为 76.39 MiB。

## 范围边界

本成果闭合该 checkpoint 的 BG0 渐变 writer、算法、工作缓冲、硬件目的地和静态
预览，不签发：

- overview 其余 BG/OBJ/window/blend 的完整来源；
- 未观察 caller 或其他游戏视觉状态；
- 剩余 598 个、29 种非字体未知内容；
- 通用图像编辑、编码与 ROM 回写。
