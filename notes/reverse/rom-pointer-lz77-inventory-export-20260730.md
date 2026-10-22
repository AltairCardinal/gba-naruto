# ROM 指针可达 LZ77 资源分母闭环（2026-07-30）

## 结论

`tools/export_rom_pointer_lz77_inventory.py` 对固定基准 ROM 做逐字节严格
type-`0x10` 扫描，再只保留“源地址四字节对齐且至少被一个对齐 ROM u32 指针
引用”的记录，建立了有限、可重复的静态资源分母：

- 1,099 条语法完整的 type-`0x10` 记录；
- 896 条满足对齐指针可达规则；
- 其中 865 条由 17 份哈希固定的既有 artifact JSON 中、schema 白名单明确标为
  资源起点的字段绑定；
- 剩余 31 条现已全部无损导出；
- 该限定分母的未绑定量从 31 降为 0，即 896/896。

成果位于 `artifacts/rom-pointer-lz77-inventory-v1/`。为避免大量小文件，31 条
压缩记录和解压 payload 分别按 ROM 地址排序打包为两个二进制；JSON 保存每条记录
在包内的 offset/size、双层 SHA-256、ROM 指针引用、Thumb literal-load 用户、
邻近直接调用和分类代码窗口。

## 分类

31 条记录全部有静态 loader 路线：

| 分类 | 数量 | 接纳规则 |
|---|---:|---|
| graphics | 20 | `ldr r0` 后进入 `0x0809C0E8`，目标为 VRAM，且 payload 不满足已证明的 text-BG 结构 |
| palette | 3 | `ldr r0` 后进入 `0x0809C0E8`，目标为 PRAM |
| visual metadata | 8 | 七条进入 WRAM；一条进入 BG screenblock 且为 32×20 text-BG tilemap |

graphics 的解压目标覆盖固定 BG/OBJ VRAM 地址和一个动态 OBJ slot；palette 的
目标是 `0x05000180`、`0x050003C0`、`0x05000000`。`0x08349368` 解压为
640 个 little-endian u16：全部使用 palette bank 1，tile ID 范围 0..5，无水平翻转、
12 个垂直翻转；同时静态加载到对齐的 BG screenblock `0x06001000`，因此归为
`text_bg_tilemap` 而不是把 1280-byte tilemap 错渲染成 4bpp 图形。WRAM 七项仍只保留
中性 `visual_metadata` 名称。每个分类同时保存全部 literal-load 用户起始的
16-byte ROM 代码窗口哈希，避免分类脱离消费者证据。

## 上游绑定边界

上游 865 条使用“文件哈希 + 精确 schema 路径白名单 + 资源起点角色 + ROM
解码/指针条件”的交集作为 `artifact-bound` 判据。边界、代码范围、`raw_words`
和未知路径一律不算绑定，宁可重复导出也不误吞资源。旧算法曾把
`dialogue-font-v2.sjis_entries[].source_end_pointer=0x085B6000` 当成绑定；
该值实际只是前一字体段的排他结束地址，而 ROM 同址又开始一条独立图形 LZ77。
修正后它作为第 31 条记录导出，有七个代码消费者，目标覆盖 `0x06016600`、
`0x06010000` 和动态 OBJ tile slot。17 份输入文件、哈希、白名单命中地址及并集
完整记录在 payload；`dialogue-font-v2` 本轮合法贡献为零。

其余 203 条虽然能按 type-`0x10` 语法走完，但不满足源地址对齐加 ROM 指针引用。
其中存在 `declared_size=1` 等明显假阳性；在出现新的代码/表可达证据前，不把它们
扩张进资源分母。

## 验证

```bash
python3 -m unittest -v tests.test_export_rom_pointer_lz77_inventory
python3 tools/export_rom_pointer_lz77_inventory.py \
  --root . \
  --output-dir artifacts/rom-pointer-lz77-inventory-v1
python3 tools/verify_rom_pointer_lz77_inventory.py \
  --root . \
  --artifact-dir artifacts/rom-pointer-lz77-inventory-v1
```

独立 verifier 不导入 exporter 或其他 `tools` 模块；它重新扫描 ROM、解压记录、
建立对齐指针索引、按 schema 白名单解析 17 份上游 JSON，并用受限 Thumb 符号执行
从消费者指令直接推导 `r0` 源、`r1` 目标和解压 wrapper；分类不复制 exporter 的
地址映射表。对于 VRAM 记录，它独立解析解压 payload，并只在 32×20、screenblock
对齐、单 palette bank、低 tile ID 的条件同时成立时升级为 text-BG metadata。
它还从 ROM 重建两个 bundle 全字节，要求 offset 连续、无重叠且覆盖到 EOF。测试
覆盖四个成果文件逐字节篡改、重算 manifest 后的分类及契约语义篡改、bundle 尾部
垃圾、重复导出确定性和外来目录拒绝。

## 明确未完成

本成果只闭合“对齐 ROM 指针可达的严格 LZ77 记录”这一静态分母，不声称：

- 896 条全部都是图像；其中七条已明确只进入 WRAM，另有一条是 BG tilemap；
- 未压缩 tiles、raw palette、字体或过程式图形已经被这一分母覆盖；
- 静态指针存在等于任意自然流程实际执行；
- 所有资源已有自然语言业务名称、最终画面组合或安全写回；
- 所有游戏视觉状态或实体 GBA 输出已经完成。

后继图像成果已沿静态 palette copy 和运行时 OAM 绑定把 18/20 条图形关联到源色。
下一主线应建立未压缩图形的有限分母，不能回到无约束“字节像图像”扫描。
