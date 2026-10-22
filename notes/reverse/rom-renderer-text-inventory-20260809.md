# Renderer 文本精确字节清单（2026-08-09）

## 结论

候选表 94、95、96、105、107、108、109、111、112、113、114 都有实际的
table-base+index 消费者，并汇入 `0x08066758 -> 0x0806626C` 的 renderer 路径；
候选 94 先经居中绘制 helper `0x0809822C`。它们不是仅凭“指针看起来像文本”推断。

固定分母为 11 张表、704 个 pointer slot、625 个唯一 target。控制感知 parser 逐目标
读到 renderer-valid NUL，得到 625 个互不重叠记录、22,588 字节，解析失败为 0。
重复指针不重复计数，记录间隙保持 `unknown`。

## Parser 边界

边界规则直接对应 renderer `0x0806626C..0x08066736`：

- `0x00` 终止；
- `0x01` 消费 2 字节；
- `0x02` 消费 3 字节；
- `0x80..0x9F` 消费 2 字节；
- `>=0xA0` 只有在 `0x0853D644..0x0853D73C` 的 31×8 SJIS range 表验证通过时
  才按双字节处理；其他字节按单字节处理。

因此实现没有使用简单的 `bytes.find(0)`，也不会把控制参数中的零误认成字符串终点。
范围分母 SHA-256 为
`60ae795037f79f4246718a5448dfeacbcfa4bc80e2759318764f2db9196d210e`；顺序内容
bundle SHA-256 为 `28c999f31b51fe2727f66e295ad259920d2d472042d81ff98673c58e51c28cf5`。

## 产物与复验

正式产物 `artifacts/rom-renderer-text-inventory-v1/` 仅含：

- `renderer-text-inventory.json`：逐表 consumer、逐 target 范围及 SHA-256；
- `renderer-text-targets.bin`：625 段按顺序连接的 22,588 字节；
- `manifest.json`：固定 ROM、exporter、verifier、测试和产物哈希。

独立 verifier 不导入 exporter，重新验证 11 个 lookup/call 路径、renderer、SJIS
表、625 个 parser 边界和 bundle。验证命令：

```bash
python3 -m unittest tests.test_export_rom_renderer_text_inventory -v
python3 tools/export_rom_renderer_text_inventory.py --root .
python3 tools/verify_rom_renderer_text_inventory.py --root .
python3 tools/audit_rom_byte_coverage.py --root .
```

## 限制

- 只主张固定 11 表引用目标及 renderer 实际消费的字节，不主张所有动态索引都在自然
  玩法中执行。
- 游戏编码字节尚未全部解码为 Unicode 或自然语言语义。
- 表与 target 之间、target 之间的间隙必须由新的消费者或结构证据另行闭合。
