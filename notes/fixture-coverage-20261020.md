# 合成夹具覆盖度（2026-10-20）

**工具**: `tools/synthetic_fixture.py`（运行器 + 基础夹具）、
`tools/fixtures_extended.py`（扩展夹具）、`tools/lib/lz77.py`（LZ77 编解码）
**方法论来源**: `notes/re-methodology-improvements-20261020.md` §M1
**状态**: ✅ 9 个夹具、37 项检查全绿

---

## 0. 这份文件回答什么

"某张表的格式对不对"这个问题，过去只有两种答法：
看真实 ROM 的数据"感觉合理"（弱），或者等动态验证（贵且被阻塞）。

合成夹具给出第三种：

> 写入一段**已知内容** → 把游戏指向它 → 用**生产读取器**读回 →
> 读回必须与写入**逐字节相等**。

相等即证明格式假设成立。这**不需要模拟器**。

---

## 1. 覆盖清单

| 夹具 | 表 / 结构 | 指针链 | 检查数 | 证明了什么 |
|---|---|---|---:|---|
| `story_before` | 剧情脚本 VM `0x060C74` | 根表 → 脚本 | 4 | 根表 u32 指针、指令长度表、op `0x02/0x01/0x00`、字形码文本 |
| `battle_rules` | 胜负条件 `0x594758` | 直寻址 | 6 | 条目 0x44 布局、回合上限、条件 8 字节字段、说明文字指针 |
| `battle_actors` | 战斗配置 `0x5461C4` | 直寻址 | 4 | 角色槽 `0xB8` 字段、`+0x8A4` 地图物件 4 字节、角色名解析 |
| `reward_entry` | 奖励表 `0x59EAE0` | 直寻址 | 5 | 24 字节条目、`(忍具 id<<8)\|数量` 尾部、物品名解析 |
| `mission_text` | 任务文字三表 | **三级**：索引→表项→文本 | 5 | `rom[0x348DAC+stage]+sub` 索引算法、三张文本表指针、文本内容 |
| `portrait_table` | 头像表 `0x5A4DEC` | 表项→gfx/palette | 6 | `id*40+expr*8` 布局、gfx 为 LZ77、**调色板为 raw 128 字节** |
| `background_table` | 剧情底图 `0x59903C` | 表项→4 指针 | 5 | `id*16` 布局、gfx/palette/tilemap/8bpp 标志 |
| `ninjutsu_names` | 忍具名表 `0x599634` | 表项→文本 | 1 | u32 指针 + 字形码文本 |
| `skill_table` | 技能表 `0x545458` | 表项→文本 | 1 | u32 指针 + 字形码文本 |

**未覆盖**（需要写指针或字段语义尚未确定）：
单位 ID 表 `0x53F298`、旧剧情表 `0x53636C` 系、地图物件的 target 语义、
条件类型 2/3 的精确判定、奖励表低字节语义。

---

## 2. 本轮新增的技术件：LZ77 编码器

仓库此前**只有解压没有压缩**，所以 LZ 资源（头像 gfx、地图图块）无法做夹具。
`tools/lib/lz77.py` 补上了**仅字面量**编码：

```
0x10 | 24 位解压长度 | 每 8 字节一个 0x00 标志位 + 8 字节原文
```

这是合法的 GBA LZ77，原生解压器一定接受，且编码器本身可验证。
`portrait_table` 夹具顺带证明了它：写入的 6400 字节图案经
我们的编码器 → 我们的解码器 → 逐字节还原。

> 真实的后向引用压缩器暂时不需要 —— 证明格式不需要压缩率。

---

## 3. 夹具的边界

夹具证明的是**格式**，不是**游戏如何使用该字段**。
按四级证据分级（`notes/runtime-verification-gates-20260710.md`），
它落在 **L1（工具产出通过）**，**不构成 L2/L3**。

具体说，`mission_text` 夹具证明了"索引算式和三级指针是对的"，
但**没有**证明"游戏在第 40 关第 1 配置下确实会显示这段任务文字" ——
那是 L3 的事，仍然需要 mGBA 探针。

---

## 4. 夹具 ROM 的安全性

- 所有夹具都在**基准 ROM 的副本**上运行，产物写到
  `build/synthetic-fixtures/synthetic-fixture-<name>.gba`；
- 真实 ROM **从不被写入**（`tests/test_process_improvements.py`
  有专门用例断言这一点）；
- 写入位置固定在 ROM 尾部空闲区 `0x5DFBEC`，
  `free_space_claim()` 会先断言该区域确实是 `0xFF` 填充，
  越界申请直接抛错。

---

## 5. 复现

```powershell
python tools/synthetic_fixture.py
python tools/synthetic_fixture.py --fixture mission_text --json build/fx.json

# 在标准测试里也会跑
python tools/automated_test.py --suite process -v
python -m unittest discover -s tests -p 'test_process_improvements.py'
```
