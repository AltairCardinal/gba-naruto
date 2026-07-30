# 战斗状态条过程式图像闭环（2026-07-30）

## 结论

已跟踪 checkpoint 中最后 181 个可见 BG 未解释 cell（22 种 tile 内容）不是遗漏的
ROM 静态图片，而是 `0x08068370` 运行时生成的两种五 tile 战斗状态条。成果位于
`artifacts/battle-status-bars-v1/`：

- 两种源模板共 320 bytes；
- 两种 style × 39 个填充等级 × 160 bytes 的完整生成族，共 12,480 bytes；
- 运行时 BG palette bank 13；
- 80×312 索引色总览图；
- 30 个 checkpoint、60 条自然状态条及 181 个父未知 cell 的逐项绑定。

本成果把 `overview-gradient-overlay-v1` 留下的玩家可见图像资源缺口从
181 cell / 22 种内容降为 0 / 0。这个 0 只表示当前已跟踪可见资源分母已经闭合，
不表示所有游戏视觉状态、所有 generator caller、跨帧合成或通用 ROM 回写已经完成。

## 静态生成器

generator 主体为 `[0x08068370,0x08068642)`，722 bytes，SHA-256：

`13ef2ceedfe889bee6b7a6666d268246f43daa3fe5ad0be83a37f275e4ff4b20`

包含尾部 literal pool 的完整对象为 `[0x08068370,0x08068660)`，SHA-256：

`9ed2404ba8cae02b834b691ef5f7b9df8db76eca6cc52f280a4e3737dd8e0b3e`

全 ROM 恰有四个直接调用：

| 调用点 | 位置/用途 | style 与数值来源 |
|---|---|---|
| `0x0806F0D6` | 常规 HUD 第一行 | style 0，单位记录 `+0x0C/+0x0E` |
| `0x0806F0EC` | 常规 HUD 第二行 | style 1，单位记录 `+7/+8` |
| `0x0807A83C` | 确认面板第一行 | style 0，对象 `+0x2B` / 38 |
| `0x0807A8A6` | 确认面板第二行 | style 1，对象 `+0x2C` / 38 |

生成等级公式为：

```text
fill_level = floor(38 * numerator / denominator)
```

结果以 u8 保存；现有合法自然样本落在 `0..38`。函数先从
`*0x0201BD54 + (24 + style*5)*32` 复制五个初始化器 BG template 到
`0x0201BD84`，再用成对 nibble 写入 38 个内部像素位置。两种模板 SHA-256 为：

- style 0：`cacf8c0f71ff964ddd962a02ad4f5a2713dd0dc9e43f1adc5d3f690f72f5b21f`
- style 1：`d0eda4d1836693671205f7c9cfb82abed04167600ecf498fdcbf2b98608791cd`

模板本身已包含在 `initializer-resource-pack-v1`，本成果保留副本是为了让完整生成族
可直接复用，不把它重复计为新的 ROM 静态资源。

## 运行时路线

30 个 checkpoint 一致给出：

```text
0x0201BD48 = 0x0600C000  动态 BG tile VRAM 基址
0x0201BD50 = 0x06001800  BG3 screenblock
0x0201BD54 = 0x0600F800  初始化器 BG graphics 基址
0x0201BD84               160-byte 工作区
```

palette 压缩流位于 `0x0809C8B0`，解压到 BG palette bank 13
（`0x050001A0`）；32-byte SHA-256 为
`82f1c93a86b077a17e05e44c28d7f6522ff69542a6356487ce25a45b61a8a9d2`。

函数分配五个动态 tile ID，把工作区逐 tile 复制到
`*0x0201BD48 + tile_id*32`，并把 `tile_id | 0xD000` 写入 BG record。
通用更新器随后通过 transfer queue 将 record tilemap 提交到
`0x06001800`。因此图形是 generator 内直接 EWRAM→VRAM，tilemap 则先进入
EWRAM record，再走共享异步上传链。

## checkpoint 与父分母绑定

30 个 BG3 checkpoint 每个恰有两条连续五 tile 状态条，共 60 条、300 个 cell：

- 常规位置为 screenblock `(x=21..25,y=17/18)`；
- `scenario-41-attack-confirmation.ss9` 为 `(x=21..25,y=15/16)`；
- 60 条完整序列均唯一反推出 `(style, fill_level)`；
- 其中 119 个 cell 的内容此前已与初始化器资源形成内容别名；
- 剩余 181 个父未知 cell、22 种 SHA-256 全部逐坐标命中同一生成族；
- 未命中为 0。

单个 tile 内容可能对应多个 fill level 或序列位置，所以不能只凭单 tile 哈希反推
参数；artifact 始终以连续五格为唯一性单位，再把父 cell 逐项绑定到已确定的整条
状态条。`0x0201BD84` 只保存同帧最后一次生成结果，也没有被误用来证明更早的一条。

## TDD 与独立验证

- 红阶段先建立导出、完整族、父分母、范围边界、篡改拒绝和输出目录安全测试；
  初次运行因导出模块不存在而按预期失败。
- 绿阶段 8/8 定向测试通过。
- 独立 verifier 不导入导出器或任何其他 `tools` 模块；它自行解析 `.ss9`、
  解码 Thumb BL、重建 78 条完整序列、检查 60 条自然状态条、重算父分母并复核 PNG。
- verifier 拒绝五个成果文件与 manifest 的逐文件篡改，并拒绝重算 manifest 后的
  生成公式、copy route 和 manifest 来源语义伪造。
- 输出目录替换前要求旧 manifest 完整 accepted、文件集合精确且所有声明哈希有效；
  只有同名 schema 的伪 manifest 不能取得目录所有权。
- contact sheet 使用固定 indexed PNG chunk、filter 0 和 stored-DEFLATE 编码，
  不依赖 Pillow/zlib 压缩器版本产生字节流，编码契约为
  `canonical-indexed-png-stored-deflate-v1`。
- 正式 CLI 结果为
  `verified=true, exact_generated_unknown_cell_count=181, errors=[]`。

本轮只读取已有快照，没有启动 mGBA，没有产生新的导航、崩溃提示或模拟器进程树。

## 范围边界

本成果不签发：

- 未跟踪游戏状态也已穷尽；
- 四个静态 caller 均有自然运行时 PC/watchpoint 绑定；
- numerator/denominator 字段的全部业务语义；
- 所有 BG/OBJ/window/blend 跨帧最终像素；
- 物理 GBA 输出；
- 通用图像编辑器、编码器和 ROM 回写。
