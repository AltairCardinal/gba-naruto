# 最后 9 个 legacy bank 的基址裁决（2026-10-21）

本文件是 `tools/rebase_resolve.py` 裁决结果的**最终落档**，并把裁决接进
`tools/table_registry.py`（`TABLES` / `BANK_TO_REGISTRY` / `CONFLICTS`）、
`sequel/content/*/bank.json` 与 `tools/completion_audit.py`。

- ROM：`rom/base.gba`，SHA-256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 工具：`tools/rebase_resolve.py`（全量字面量索引 18051 个常量 / 29920 条引用指令）
- 机器检查：`tools/alias_audit.py rom/base.gba` → **RESULT: OK**（0 未裁决 / 0 失败检验 / 0 registry 不一致）
- 前序记录：`notes/evidence/rebase-resolve-20261021.md`（工具与首轮候选）

---

## 1. 方法

旧基址全部是**错位窗口**：bank.json 里记的地址本身在 ROM 里没有任何原生读者
（`LiteralIndex` 零命中），但那一段字节又确实属于某张真表。

裁决用三条可复算的判据，不再靠"看起来像"：

1. **真基址必须被原生读者加载**：对每个候选地址，用全 ROM 字面量索引
   （`LDR Rn,[pc,#imm]` 的 ARM/Thumb-1/Thumb-2 全覆盖）找出所有读者，
   读出读者执行的乘法链，从而得到**步长**。
2. **真基址 + 条数 × 步长必须正好落在下一个已知结构上**。
3. **旧 bank 记录的条目必须逐字节等于 ROM 在真基址处的字节**
   （否则旧 bank 记录的来源另有其表）。

只有同时满足三条才认。落点取**最近的可达结构**，不是最远的。

## 2. 裁决结果

| bank | 旧基址 | 真基址 | 结构 | 原生读者 |
|---|---|---|---|---|
| `battle-handlers` | `0x53E6D8` | **`0x53E698`** | 8 字节/条 × 256（每条两个 u32 代码指针） | `0x0807F934` / `0x0807FD28`（fn `0x0807F414`） |
| `map-events` | `0x53EB08` | **`0x53E698`**（与上同一张表） | 同上 | 同上 |
| `fonts` | `0x53E5B4` | **`0x53E596`** | 1 字节/条 × 256（按字符码索引） | `0x0807F0FC`（fn `0x0807EE50`） |
| `data-table-a` | `0x5A14A4` | **`0x5A143C`** | u32 ROM 指针 × 46（46/46 是指针） | `0x0808A6BA` / `0x0808B19E` |
| `data-table-b` | `0x5A2120` | **`0x5A2034`** | u32 × 90（79/90 是指针） | `0x080985D8` / `0x08099D26` |
| `menu-ui` | `0x5A5774` | **`0x5A4DEC`**（头像表 `portrait_table`） | 40 字节/条 × 63（`id*40 + expr*8`） | `0x08096158`（fn `0x08096138`） |
| `function-pointers` | `0x53D5F4` | **`0x53D5F0`** | 13 槽 u32（槽 0/12 = `FFFFFFFF` 哨兵，槽 1..11 = 代码指针） | `0x08061DD4`（fn `0x08061D8C`） |
| `tile-assets` | `0x5A3218` | **`0x5A320C`** | 68 字节/条 × **79**（+0x0C 是 6 个 u32 图块指针） | 10 个，例如 `0x0809881E`（fn `0x0809880C`） |
| `sappy-engine` | `0x079668` | —— **退役** | `0x08079668` 是文本/消息对象分派函数，不是音频分发器 | 无 |

### 2.1 逐条判死检验

- **battle-handlers / map-events**：`0x0807F934` 必须仍读 `0x0853E698`；
  `0x53E698 + 256*8` 必须仍等于 `0x53EE98`；
  两个 bank 的记录必须逐字节等于 ROM 在 `0x53E698 + 8*i` 处的字节。
- **fonts**：`0x0807F0FC` 必须仍读 `0x0853E596`，且必须仍执行
  `ldrb` 取字符码再相加（读者把**索引宽度**钉死在 8 位 ⇒ 表长 256）。
- **data-table-a / data-table-b**：`0x0808A6BA` / `0x080985D8` 必须仍读
  `0x085A143C` / `0x085A2034`；表尾必须仍分别是 `0x5A14F4` / `0x5A219C`。
- **menu-ui**：`0x08096158` 必须仍读 `0x085A4DEC` 并按 `id*40 + expr*8` 索引；
  `0x5A5774 - 0x5A4DEC = 0x988 = 61*40` 必须仍等于旧窗口的行偏移。
- **function-pointers**：`0x08061DD4` 必须仍读 `0x0853D5F0`；
  `ROM[0x53D5F4 + 4i]` 必须仍等于 `0x08061C8D + 12*i`（i = 0..10）；
  槽 0 与槽 12 必须仍是 `FFFFFFFF`；`0x53D5F0 + 13*4` 必须仍等于 `0x53D624`。
- **tile-assets**：`0x0809881E` 必须仍读 `0x085A320C` 并按 `idx*68` 定位；
  记录数 79 由「指针块结构在 `0x5A4708` 处干净断裂」确定
  （`0x5A320C + 79*68 = 0x5A4708`）；若 `0x5A4708` 起又能按 68 字节读成同样记录，条数需修正。

## 3. 两条被推翻的旧结论

1. **「`menu-ui` 的 `0x5A57C4` 不可复现」——错。**
   `0x5A57C4` **确实**被 12 个原生读者加载，它是一张 12 字节/条的表
   （每条 = 一个 u32 色值 + 8 字节 0），并且正好是头像表 `0x5A4DEC + 63*40` 的下一张表。
   旧结论把它当成了"menu-ui 的候选基址"；实际上它与 `menu-ui` 无关。
2. **「`map-events` 是独立表、在 `0x53EBC4` 处以 0 结尾」——错。**
   `0x0853EB08` 在**整个 ROM 里没有任何字节模式出现**（零字面量引用）；
   `0x53EB08 - 0x53E698 = 0x470 = 142*8`；旧记录 47 条里有 23 条是同一个处理程序
   —— 这是「8 字节记录按 4 字节步长读」的特征，不是「独立表 + 0 结尾」。

## 4. `tile-assets` 条数是怎么定下来的（一度三选一）

候选 `142` / `256` / `288` 都被逐一判死：

- **288 不可能**：读者 `0x0809880C` 的索引是 `ldrb` 出来的**字节**
  （`lsls #0x18 / lsrs #0x18` 掩到 8 位），且 `fn 0x080983B8` 是 `(arg-1) & 0xFF`，
  所以索引 ≤ 255 ⇒ 记录数 ≤ 256。
- **142 不可能**：`0x5A320C + 142*68 = 0x5A57C4`，而 `0x5A4DEC..0x5A57C4`
  已经是**头像表 `portrait_table`**（63 行 × 40 字节，唯一读者 `0x08096158`）。
  两张表不能重叠 ⇒ 142 被证伪。
- **79 成立**：逐条扫描"读者真正解引用的 u32 槽"（+0x0C 的 6 个图块指针、
  +0x28/+0x2C/+0x30 的 3 个脚本指针、+0x38 与 +0x40），
  允许全 0 空槽，从记录 0 起**连续 79 条**都满足"指针块或全 0"，
  第 80 条（`0x5A4708`）结构干净断裂（之后是 16 字节步长的另一张表）。

> 调试方法留档：判断"结构在哪儿断"要**按读者实际解引用的槽**来判，
> 不能按"字段长得像不像"来判 —— 记录里有全 0 空槽、按固定字段签名的检查
> 会在第 4 条就误判。

## 5. 顺带修掉的两个真 bug

1. `tools/extract_all_structures.py` 用**系统默认编码**读自己写出的 UTF-8 JSON
   （`json.load(open(bank_path))`），在非 UTF-8 locale（这里是 GBK）上直接
   `UnicodeDecodeError`。已改为显式 `encoding="utf-8"`。
2. 同一工具 `import tools.lib.io` 会 `ModuleNotFoundError`（脚本方式运行时
   `sys.path[0]` 是 `tools/` 而不是仓库根）。已补上仓库根的 `sys.path`。
   另外它对 `positions`（带 computed id 与 `bytes` 字段，不是扁平记录表）
   会 `KeyError: 'offset'` —— 已改成**跳过**并说明原因，不再崩掉整轮抽取，
   也不再覆盖该 bank 手写的 entries。

## 6. 复现命令

```powershell
$env:PYTHONIOENCODING='utf-8'
python tools\rebase_resolve.py rom\base.gba --bank tile-assets
python tools\alias_audit.py rom\base.gba
python tools\consumer_locate.py rom\base.gba --all --evidence notes\evidence\consumer-evidence.json
python tools\extract_all_structures.py --rom rom\base.gba
python tools\completion_audit.py --check
```
