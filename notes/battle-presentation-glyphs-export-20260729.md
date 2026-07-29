# 战斗演出文字与 32×32 字形导出证据（2026-07-29）

## 结论

旧扫描器把 `0x085A2B08..0x085A2EE8` 识别为 62×16 的四指针表。消费者证明这只是
把两张一维表强行每四项换行后的扫描形状，不是 ROM 的业务 schema：

- `0x085A2B08..0x085A2C44`：79 个按 effect/message ID 索引的 NUL 字节串指针；
- `0x085A2C44..0x085A2EF4`：172 个 LZ77 图形块指针；
- `0x085A2EF4..0x085A320A`：79×10 的 message → glyph binding；
- `0x085A320A..0x085A320C`：2 字节零 padding，之后才是 79×0x44 effect descriptor。

人工 62×4 视图在第 20 行把 3 个消息指针和 glyph 0 拼在同一行，并漏掉 glyph
169–171。代码中不存在 `row*16+column*4` 或“前 20 行/后 42 行”的分支。

## 消费者证据

- message literal `0x080995E0 = 0x085A2B08`；
- `0x08099564..0x08099582` 以 `u8(message_id)*4` 选择消息指针，再调用
  `0x08098290` 的文本 renderer；
- binding literal `0x080981A4 = 0x085A2EF4`；
- glyph literal `0x080981A8 = 0x085A2C44`；
- `0x0809812C..0x0809819C` 以 `message_id*10` 选择 binding，读取 byte 0 的 count，
  按 glyph ID×4 选择 LZ77 stream；`0xFF` 跳过加载；
- 每个非跳过项通过 `0x0809C0E8` 的 `svc #0x12` 解压到 OBJ VRAM，目的槽固定递增
  `0x200` 字节。
- 第二个 binding literal `0x08098FC4 = 0x085A2EF4` 由
  `0x08098EDC..0x08098FBA` 的显示 consumer 使用；它按
  `binding[1 + display_slot]` 重新读取 glyph ID、跳过 `0xFF`，再创建对应显示对象。

五段消费者代码及 SHA-256 已写入 manifest。静态数据和视觉重建共同证明每个 chunk
为 512 字节、16 个 4bpp tile；按 4×4 tile 还原为 32×32 后得到完整的汉字、假名、
数字和标点字形。artifact 使用灰阶诊断 palette 保存索引像素，不宣称已闭合运行时
palette 来源。

## 完整导出

成果位于 `artifacts/battle-presentation-glyphs-v1/`：

- 79/79 条原始 NUL 字节串；
- 172/172 条原始 LZ77 record；
- 172/172 份 512-byte 4bpp graphics；
- 172/172 张 32×32 indexed PNG；
- 一张 512×352 的完整字形总览；
- 三张源表的原始字节；
- 79/79 条 binding 的原始 10 字节、count 与 active glyph IDs；
- 171 份唯一图形内容；glyph 64/116 是唯一的内容重复组；
- 138 个 glyph 被当前 binding 引用，34 个未绑定但仍完整保留；
- 空 binding 为 message 13/31/32/46。

消息字节是游戏编码流。本里程碑只保存原始字节、NUL 边界、指针和哈希，不把
CP932/GBK 的乱码尝试写成自然语言解码，也不猜测 79 个业务名称。

## 可重复验证

```sh
python3 -m unittest tests.test_export_battle_presentation_glyphs -v
python3 tools/export_battle_presentation_glyphs.py \
  --root . \
  --output-dir artifacts/battle-presentation-glyphs-v1
python3 tools/verify_battle_presentation_glyphs.py \
  --root . \
  --artifact-dir artifacts/battle-presentation-glyphs-v1
```

独立 verifier 不导入 exporter；它从基准 ROM 重建三张表、79 条消息、172 条 LZ77
记录、全部 4bpp raster、PNG 和总览图，并拒绝消息、图形、PNG、manifest 元数据或
文件集合篡改。当前结果为 `messages=79`、`glyphs=172`、`errors=[]`。

## 同轮扫描纠正

另一个旧候选 `0x085A4E14..0x085A57C4` 也不是独立的 155×16 表。它恰好是
`0x085A4DEC` 的 63×40 立绘矩阵跳过全零 record 0 后的 62×5 非零后缀；现有
`artifacts/menu-portraits-v1/` 已逐项覆盖全部 310 个 pair。该候选不再进入图像
逆向队列。

## 边界

本里程碑闭合三张静态表、全部 172 个图形块及其 binding。以下仍未闭合：

- 79 条消息的自然语言字符映射；
- 每条消息的最终用户可见业务名称；
- 字形运行时 palette 的完整选择链；
- 这些文字与 79×0x44 effect descriptor 的完整逐帧 screen-space 合成；当前只闭合了
  binding → 单 glyph 显示对象的静态消费者链。
