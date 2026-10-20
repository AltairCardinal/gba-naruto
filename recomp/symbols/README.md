# symbols/ — 符号导入

`gba_recompile` 支持 `--symbols <TSV>` 导入外部符号表，用于：

* 给自动发现不到的函数命名（`[[extra_func]]` 的等价物）
* 固定函数边界（`--boundaries`）
* 覆盖率统计时区分「自动发现」与「人工声明」

格式为 TSV，每行一个 `地址<TAB>名称`（地址为十六进制）。具体字段以框架
`docs/TOML_SCHEMA.md` 与 `docs/SYMBOL_OVERLAY.md` 为准。

## 本项目的独特优势

框架对**没有符号表的新游戏**只能从零开始靠 finder 猜函数边界，
而本仓库已经有大量已验证的地址知识：

| 来源笔记 | 内容 | 可转成的符号 |
|---|---|---|
| `notes/addresses.md` | 通用地址表 | 函数名 + 边界 |
| `notes/battle-tables.md` | 战斗相关表地址 | 数据段 → `[[data_range]]` |
| `notes/resource-locations.md` | 资源指针（LZ77 压缩图块/调色板/元块） | 数据段 → `[[data_range]]` |
| `notes/text-regions.md` | 文本区 | 数据段 → `[[data_range]]` |
| `notes/character-stats-addresses.md` | 角色属性表 | 数据段 |
| `notes/map-addresses.md` / `notes/map-format.md` | 地图表 | 数据段 |
| `notes/ninja-tool-addresses.md` | 忍具表 | 数据段 |
| `notes/dialogue-*.md` | 对话系统 | 函数 + 数据段 |

**最重要的一条**：`[[data_range]]` 写错会让 finder 把压缩数据当代码解码，
生成垃圾 C++ 并可能静默跳进垃圾代码，**掩盖真实 bug**（schema 原文：
"Decoding data as code is a false positive — catastrophic"）。
而漏函数只是 "miss"，运行时会明确报出精确 PC，容易修。

> 原则：**宁可漏，不可错。** 数据段宁可多标几个字节。

## 待办

1. 从 `notes/` 导出 `imported_symbols.tsv`
2. 从 `notes/` 导出 `function_boundaries.tsv`
3. 依据 `config/naruto_konoha_senki.toml` 的 `[[data_range]]` 补全资源区
4. 用 `--strict` 模式跑，把剩余 dispatch miss 逐个补成 `[[extra_func]]`

## 快速试跑（不导入符号）

```powershell
.\gbarecomp.exe build --rom rom\base.gba --output build\gbarecomp-out --force
# ==> discovered 12048 functions (arm=69 thumb=11979 indirect=2907 undefined=138 ...)
```
