# 完整菜单/剧情立绘导出证据（2026-07-29）

## 结论

`0x085A4DEC` 的菜单/剧情立绘矩阵已经从“表结构和少量使用项可用”推进为
可重复的全量图像导出成果：

- 63 条记录，每条 5 个 `(gfx, palette)` 变体；
- 记录 0 是全零哨兵；
- 记录 1–62 共导出 310 个可寻址变体；
- 表前 `0x085A4DE4` 的全局 variant 5 另导出 1 个变体；
- 311 个逻辑输出归并为 74 组唯一 `(gfx, palette)` 资源和 70 份唯一图形；
- 每份图形都是 6400 字节的 80×80 8bpp OBJ 数据，配套 128 字节、
  64 色 BGR555 调色板；
- PNG 保留原始调色板索引，并把 OBJ 调色板索引 0 标为透明。

本分类现在具备完整的可视成果、源地址回链和重生成工具，但不代表全部 ROM
图像资源已经完成。

## ROM 与表锚点

- ROM：`rom/base.gba`
- ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 主表文件偏移：`0x5A4DEC`
- 主表 GBA 地址：`0x085A4DEC`
- 主表范围：`63 × 0x28`
- 主表 SHA-256：
  `bfc995240519eca9035e140a45e506a5c1f6f561e05827a589b5ac03543bba7e`
- 全局 variant 5 指针对文件偏移：`0x5A4DE4`
- 全局 variant 5 图形/调色板：
  `0x0840D1A8 / 0x0840DE80`
- 已有运行时消费者证据：
  `0x08096138` 按 `record_id * 40 + variant * 8` 选择资源；
  variant 5 使用主表之前的全局指针对。

## 可重复成果

- 导出器：`tools/export_menu_portraits.py`
- 测试：`tests/test_export_menu_portraits.py`
- 产物：`artifacts/menu-portraits-v1/`
- 清单：`artifacts/menu-portraits-v1/manifest.json`
- 清单 schema：`menu-portrait-export-v1`

导出器先逐条比较 `sequel/content/menu-ui/bank.json` 与 ROM 内的原始指针对，
再严格读取单个 LZ77 记录。图形流不是普通的 10×10 平铺图集，而是原 OAM
任务依次装载的六个硬件支持矩形；导出器按六段 1D OBJ tile 顺序还原完整
80×80 画布。清单为每个逻辑变体保存：

- 指针对的 ROM 文件偏移和 GBA 地址；
- gfx/palette 指针；
- LZ77、解压图形、调色板和 PNG 的 SHA-256；
- 压缩/解压大小、最大调色板索引；
- 去重后的 `resource_id` 和输出文件名。

重复执行：

```bash
python3 tools/export_menu_portraits.py \
  --root . \
  --output-dir artifacts/menu-portraits-v1
```

## 验证结果

```text
python3 -m unittest \
  tests.test_export_menu_portraits \
  tests.test_generate_butano_battle_portrait_content \
  tests.test_text_and_visual_table_identity

Ran 17 tests in 1.856s
OK
```

额外离线复核：

- 311/311 个 PNG 均能完成解码，尺寸均为 80×80、模式均为 indexed、
  透明索引均为 0；
- 311 个文件哈希与 manifest 全部一致；
- 311 个逻辑输出恰好有 74 个唯一 PNG 哈希，与唯一资源数一致；
- 旧生成器使用的 46 个 `(portrait_id, expression_id)` 与全量结果逐项比较，
  gfx 指针、palette 指针、解压图形 SHA-256 和 palette SHA-256 全部一致；
- 两次独立导出的 manifest 与所有 PNG 逐字节一致；
- 实际产物大小约 1.5 MiB；
- 导出耗时 0.55 秒，最大 RSS 25,456,640 字节，无 page fault 或 swap。

本里程碑完全离线读取 ROM，不启动 mGBA，因此不存在导航重放，也无需建立
模拟器快照。没有写入 `butano-sequel/`，不会覆盖并行 Butano 重制任务。

## 剩余图像优先项

下列资源仍不能因本里程碑而标记完成：

1. `0x54229C` 的 24 条 story visual bundle：gfx/palette/tilemap 已定位，
   尚缺全量静态合成图与 manifest。
2. `0x53DF70` 的 4 条 cutscene visual bundle：静态 atlas 可导出，
   最终 OAM 布局还需解析相邻 definition/animation。
3. `0x5A320C` 的 79 条 battle visual descriptor：gfx、palette 字段已有部分
   consumer 证据，但完整 OAM/布局语义未闭合。
4. `0x53F140` 的 43 条 sprite definition/animation pair：表内没有直接
   gfx/palette，需要继续追踪资源分配链。

后续仍按图像优先顺序处理，优先选择可一次覆盖整表的离线脚本。
