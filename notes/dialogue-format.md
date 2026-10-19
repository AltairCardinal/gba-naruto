# 对话表与文本格式

## 权威基线

本说明只适用于 `rom/base.gba`：

- 大小：`0x600000`（6,291,456 字节）
- SHA-256：`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 可重复产物：`artifacts/rom-dialogue-text-inventory-v1/` 与
  `artifacts/rom-dialogue-padding-inventory-v1/`

开发 ROM 可能重定向表项，不能沿用本页的目标范围、总字节数或哈希。

## 物理布局

真正的表范围是半开区间 `[0x461CE4, 0x4634B8)`，共 6,100 字节，恰好是
305 个 20 字节记录：

| word | 已证明含义 |
|---:|---|
| 0 | 固定 `u32 0` 哨兵 |
| 1 | primary 文本 ROM 指针 |
| 2 | label 0 文本 ROM 指针 |
| 3 | label 1 文本 ROM 指针 |
| 4 | label 2 文本 ROM 指针 |

旧文档从 `0x461CE8` 起数出“1,524 个平坦槽位”，漏掉了第 0 行哨兵，也掩盖了
真实的 305×20 记录结构。完整表 SHA-256 为
`5b36c67620030d5ccc8795a2a260aca604d90fad4a49f7c7cb9d4c7cdc63c73f`。

1,220 个指针全部非零、互异并严格递增，目标位于
`[0x459414, 0x461CE1)`。每个目标取到首个 NUL（含终止符）后：

- 有效载荷：16,987 字节；
- NUL：1,220 字节；
- 精确目标合计：18,207 字节；
- 目标之间的零填充：16,814 字节；
- 目标 bundle SHA-256：
  `7509a63b2f892ea9f2892ed4cc703da72457247df148a1435edbbee8b2d95569`。

填充不属于目标，不能把 35,021 字节包络整体标成文本。独立 padding verifier 已从
固定指针表重新扫描全部目标并证明 1,219 个相邻间隙恰好 16,814 字节且全部为零，
因此这些间隙现可分类为结构性 `dialogue_inter_record_zero_padding`；该分类不声明
文本语义、自然运行时可达，也不表示可安全分配或覆写。

## 消费者与渲染链

表首没有 `0x08461CE8` literal。真实代码在 `0x080917B0` 读取
`literal@0x080918E8 = 0x08461CE4`，随后：

```text
0x0808F9EC -> 0x080914D8
             -> 0x080917B0  装入表基址
             -> 0x08091950  table_base + group_index * 20
             -> 0x080919DA  读取 record + 4 的 primary 指针
             -> 0x08066758  文本对象 wrapper
             -> 0x0806626C  字节流解析器
             -> 0x08065F84  字形/tilemap wrapper
             -> 0x08065EB8  字形展开器
```

`0x08091A24..0x08091A64` 的三次循环从 `record + 8 + selector * 4` 读取标签
指针。因此四个字段角色是机器码事实，不再只是按字符串长度推测。

解析器在 `0x0806671C..0x08066726` 对当前源字节执行 NUL 退出；本表目标中低于
`0x20` 的非终止字节只有 `0x0A`，共 203 次、分布于 170 个目标。这里把它记录为
引擎控制码/换行路径，但不据此宣称主机 CP932 或 GBK 解码就是游戏的自然语言语义。
ROM 使用的是与字库映射配套的游戏字形码；主机编解码预览只能辅助观察。

## 已知边界

- 一个已确认的 group 选择分支使用 u8；另一个分支可返回 halfword。尚无路径级证据
  证明 0..304 每一行都在自然玩法中可达。
- label selector 的 0..2 上游约束不在本函数内检查；验证器保留这一限制。
- 静态消费者链证明结构、目标格式和渲染用途，不等于 1,220 个目标逐一经过运行时
  截获或画面验收。
- `sequel/content/text/dialogue-bank-full.json` 是旧的开发 ROM 混合扫描结果，无固定
  ROM 身份且不完整；不得作为全量清单。
- `tools/extract_dialogue_full.py` 只扫旧范围和有限条目，不能生成规范产物。
- `tools/import_dialogue_var.py` 目前只覆盖少量已登记项；本次只闭合全量只读提取与
  字节分类，不签发 1,220 项全量编辑/写回能力。

## 验证

```bash
python3 tools/export_rom_dialogue_text_inventory.py \
  --root . --output-dir artifacts/rom-dialogue-text-inventory-v1
python3 tools/verify_rom_dialogue_text_inventory.py \
  --root . --artifact-dir artifacts/rom-dialogue-text-inventory-v1
python3 tools/export_rom_dialogue_padding_inventory.py \
  --root . --output-dir artifacts/rom-dialogue-padding-inventory-v1
python3 tools/verify_rom_dialogue_padding_inventory.py \
  --root . --artifact-dir artifacts/rom-dialogue-padding-inventory-v1
python3 -m unittest -v tests.test_export_rom_dialogue_text_inventory
python3 -m unittest -v tests.test_export_rom_dialogue_padding_inventory
```

独立验证器不导入 exporter；它从固定 ROM 重做表几何、消费者指令和 BL 目标、
1,220 个范围、NUL、控制码统计、逐目标哈希及两个聚合二进制。
