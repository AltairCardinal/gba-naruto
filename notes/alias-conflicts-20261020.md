# 别名（同址）冲突裁决记录 —— 2026-10-20

**范围**：`sequel/content/**/bank.json` 里遗留的同址冲突 + 已证伪的 "Sappy 音频" bank。
**产出**：`tools/alias_audit.py`（机械复核）、`tools/table_registry.py`（裁决的机器可读形式）、
本文件（长表与判死检验）。
**ROM**：`rom/base.gba`，SHA-256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。

---

## 0. 结论摘要

| # | 争用地址 | 涉及的 bank | 裁决 | 基址状态 | 裁决后的权威基址 |
|---|---|---|---|---|---|
| 1 | `0x546100` | `items` / `skills` | **merge**（命名层） | `unproven-window` | `0x546100`（规范名 `skills`，`items` 降级为弃用别名）—— **注意：这不是被证明的表根** |
| 2 | `0x53F138` | `palettes` / `audio` | **falsify**（`audio` 身份作废）+ **repoint**（重新定位） | `relocated` | `0x53F140`（规范 owner `map-sprites`） |
| 3 | `0x53D910` | `maps` / `encounter-zones` | **merge** | `native-reader` | `0x53D910`（规范名 `maps`，`encounter-zones` 降级为弃用别名） |
| 4 | `0x53F200` | `sprite-animations` | **repoint** | `relocated` | `0x596CCC`（真实精灵动作表） |
| 5 | `0x079668` | `sappy-engine` | **falsify** | `not-a-table` | 无基址（该地址是代码区，不是数据表） |
| 6 | `0x53F1DC` vs `0x53E1DC` | `map-sprites` | **repoint** | `relocated` | `0x53F140`（86 项 u32 指针表） |

`python tools/alias_audit.py rom/base.gba` 现在 **退出码 0**：未裁决冲突 0、失败判死检验 0、
registry-vs-bank 不一致 0。

> **与 `notes/legacy-table-base-correction-20261020.md` 的关系**：那份笔记用
> `tools/consumer_locate.py` 证明了 21 个 legacy 基址的 32 位值在整个 ROM 里
> **一次都没出现过**（`raw_occurrences == 0`），并给出推论 §5.2：
> 「该地址不可能是任何原生结构的**首址**（基址）… 冲突双方的地址**都**站在流沙上」，
> 唯一例外是 `0x53D910`（8 个读者，真的存在同址冲突）。
> 本文件**采用这条规则**，并把它落成 `base_status` 字段：
>
> - `0x53D910` = `native-reader`：地址真实存在 ⇒ 冲突是真的 ⇒ **merge**；
> - `0x53F138` / `0x53F1DC` / `0x53F200` = `relocated`：地址是窗口 ⇒
>   **repoint** 到重新定位出来的真实基址（`0x53F140` / `0x53F140` / `0x596CCC`）；
> - `0x079668` = `not-a-table`：那里是**代码**，零读者是预期，只能证伪**命名** ⇒
>   **falsify**（与那份笔记 §5.1 的特别说明一致）；
> - `0x546100` = `unproven-window`：零读者 ⇒ 不是表根；但**本轮找不到它的真实基址**
>   （见第 5 节第 1 条），所以只能先把**命名**层合并（items/skills 同一张表），
>   地址层保持「窗口」标记而不是伪装成基址。

---

## 1. 尝试记录（含走不通的路）

1. **先自己手写字面量扫描**（全 ROM 搜 `0x08000000 + offset` 的 u32，再反查
   `LDR Rn,[pc,#imm]` 消费点）。结果：`0x53D910` 有 8 个引用；`0x546100`、`0x53F138`、
   `0x53F200`、`0x079668`、`0x53F1DC`、`0x53E1DC` **一个引用都没有**。
   → 这本身已经说明「这些遗留基址不是被原生代码直接寻址的表根」。
2. **想给 `0x546100` 找一个真正的 16 字节记录表根**：往回扫了 `0x545E40` / `0x545D80` /
   `0x545BE4` / `0x5459C8` / `0x545458`。走不通：这些邻近表的基址都是 4 字节对齐但
   **不是 16 字节对齐**，与 `0x546100` 所在的 16 字节栅格不是同一条；而
   `0x545BE4`（有 7 个原生读者，消费者 `0x0806D910`）走的是 `index*16` 且
   `(0x546100-0x545BE4) % 16 = 12 ≠ 0`，所以 `0x546100` 不属于那张表。
   → 结论：`0x546100` 是一张**独立**的 16 字节记录表的一个 12 条窗口，但**这张表没有任何
   字面量引用**，无法再往深挖；本轮只把「它不是 items/skills 之外的第三张表」记录下来。
3. **想把 `0x53F138` 的目标读成 RGB555 调色板**：走不通。`0x12F5B0` 起的记录里嵌着
   u32 指针 `0x0812F598` / `0x0812F5B4`，不是 16 个 BGR555。→ `palettes` 的旧身份被证伪。
4. **想给 "Sappy 引擎" 找证据**：按 bank 自己的说法去找「音频命令 0x64-0xE3」与
   「0x08599634 音频指针表」。走不通：`0x08599634` 在本仓库早已登记为**忍具名表**
   （`tools/table_registry.py` 的 `ninjutsu_names`），其条目指向字模编码的中文串。
   → Sappy 叙事整体作废（详见第 4 节）。
5. **想在 `0x53F1DC` / `0x53E1DC` 之间二选一**：走不通。两者**都没有**原生读者；
   `0x53F1DC` 恰好是 `0x53F140 + 0x9C`（真实基址的第 39 项），而 `0x53E1DC` 落在
   事件处理程序区、字节是 `0x1C00 / 0x2400 / 0x07` 这类小整数，不含指针。
6. **手工 grep 散文当证据**：不可复现。改用父会话提供的 `tools/consumer_locate.py`
   的 `LiteralIndex`（全 ROM 18051 个常量被 29920 条指令引用），本工具直接复用它，
   裁决因此是机械可复现的，而不是「读起来像」。

---

## 2. 方法

1. **建全 ROM 字面量索引**：`tools/consumer_locate.py` 的 `LiteralIndex`
   （ARM / Thumb-1 / Thumb-2 的 `LDR Rn,[pc,#imm]`），得到「哪些常量被原生代码读过、
   在哪条指令读过」。
2. **找真实消费者**：对每个争用地址与裁决后的基址跑 `locate_consumers`，拿到
   「函数边界 + 消费指令 + 用法分类（deref / indexed / scaled / store）」。
3. **判数据是什么**：从消费者指令反推结构——`0x53D910` 被 `lsls r6, r2, #5`（步长 32）
   索引 ⇒ 32 字节记录数组；`0x53F140` 被 `muls`/偏移后整体当指针数组用 ⇒ u32 指针表；
   `0x596CCC` 被 `muls r1, r0, r1` 按 id 索引 ⇒ 144 字节/角色的动作记录。
4. **裁决并写进 registry**：`tools/table_registry.py` 新增 `CONFLICTS`（每条含
   verdict / 规范 owner / 权威基址 / 逐 bank 处置 / 证据 / 判死检验 / **机械检查**）、
   `ALIASES`（弃用别名 → 规范 bank）、`FALSIFIED`（被证伪的 bank）。
5. **机械复核**：`tools/alias_audit.py` 重新从 bank.json + ROM 推导一切：
   - 同址碰撞必须有 `CONFLICTS` 条目，否则 **unresolved**；
   - 每条 `checks` 必须通过（如「`0x546100` 必须 0 个原生读者」、
     「`0x08069040` 必须读 `0x0853D910`」）；
   - registry 与 bank 必须一致；
   - 任一不满足即退出码非 0。

> 注意：`tools/consumer_locate.py` 的 Thumb 函数起点识别用的是
> `(half & 0x80)`，而 `push {r4,r5,lr}`（`0xB530`）的 LR 位是 **bit 8**，
> 会漏判。`tools/alias_audit.py` 自己重算了函数起点（`thumb_push_is_prologue`），
> 所以本文件里引用的「函数边界」是准确的；`consumer_locate.py` 未被修改。

---

## 3. 逐冲突裁决表

| 地址 | 冲突的 bank 名 | 原生消费者地址 | 消费者证据指令 | 裁决 | 裁决后的权威基址 | 判死检验 |
|---|---|---|---|---|---|---|
| `0x546100` | `items` / `skills` | `0x08546100`：**0 个读者**；最近的读者 `0x0806E6D2`（fn `0x0806E1B4`）读 `0x085461C4` | `0806E6D2: ldr r1, [pc, #0x12c]` → `0x085461C4`；其后 `0806E6D8: adds r5, r2, #4`、`0806E704: movs r0, #0xb8` / `0806E706: muls r0, r4, r0`（公式 `0x5461C4 + stage*0x1AAC + sub*0x8E4 + 4 + slot*0xB8`） | **merge**：同一张 16 字节记录表，规范名 `skills`，`items` 降级为弃用别名 | `0x546100` | 搜 u32 `0x08546100` 必须 0 命中；若被读到则应拆成两张表，本裁决作废。`0x085461C4` 必须 > 0 命中（当前 26） |
| `0x53F138` | `palettes` / `audio` | `0x0853F138`：**0 个读者**；真实基址 `0x0853F140` 的读者 `0x08080B12`（fn `0x08080B08`） | `08080B12: ldr r5, [pc, #0x40]` → `0x0853F140`；`08080B72: adds r1, r5, #0` / `08080B78: bl #0x8063494` → `080625A4` 索引 `table[id*11]` | **falsify**（`audio` 身份作废：此处与音频无关）+ **repoint**（真实基址 `0x53F140`） | `0x53F140` | `0x0812F5B0` 起的 32 字节若能解出 16 个 BGR555 且含 `0x7FFF`，则 `palettes` 旧身份成立、本裁决作废；`0x08080B12` 若不是读 `0x0853F140`，则真实基址另有其处 |
| `0x53D910` | `maps` / `encounter-zones` | `0x0853D910`：**8 个读者**（`0x08068FB8` / `0x08069040` / `0x08069220` / `0x08069268` / `0x0807AA90` / `0x0808067C` / `0x0808096C` / `0x0808F4F6`） | `08069040: ldr r5, [pc, #0x98]` → `0x0853D910`；`08069044: lsls r6, r2, #5`（步长 32 字节）；`08069046: adds r0, r5, #4`（+0x04 图形指针）；`0806905C: adds r0, #8`、`0806906C: adds r0, #0xc`、`0806907C: adds r0, #0x10`、`080690A0: adds r0, #0x14` | **merge**：同一张 32 字节地图描述符表，规范名 `maps`，`encounter-zones` 降级为弃用别名 | `0x53D910` | `0x08069040` 的步长若不是 32、或基址不是 `0x0853D910`，则 `maps` 身份不成立；反向：47 个条目 terrain 解压长度 == 宽×高×2（47/47，第三方已在原版脚本上复核） |
| `0x53F200` | `sprite-animations` | `0x0853F200`：**0 个读者**；真实基址 `0x08596CCC`：**18 个读者** | `0806B76C: ldr r1, [pc, #0x48]` → `0x08596CCC`；`0806B77E: muls r1, r0, r1`（按 id 索引）+ `0x90`（144）步长 | **repoint**：bank 名字「精灵动画」对应的是真实精灵动作表 | `0x596CCC` | `0x596CCC + 63*144` 的条目必须全 0、`+ 64*144` 的条目必须含非 ROM 指针；若 id 64 起仍是动作表，则 id 范围不是 1..62，表长需修正 |
| `0x079668` | `sappy-engine` | `0x08079668`：**0 个读者**（它是代码）；其字面量池里有 `0x08599634` / `0x0859937C` | `080796E4: ldr r1, [pc, #0x18]` → `0x08599634`（忍具名文本指针表）；`080796D8: ldr r1, [pc, #4]` → `0x0859937C`；`080796F0: ldr r0, [r0]` 取文本指针后 `080796FA: bl #0x8066758` | **falsify**：是文本/消息显示对象分派函数，不是 Sappy 音频分发器 | 无基址 | 若 `0x08066758` 内出现 PCM/混音寄存器写入或调用 Sappy 播放例程，则判定作废；若 `0x08599634` 的条目指向音频采样而非字模编码文本，则 bank 反而成立 |
| `0x53F1DC` | `map-sprites`（vs 门禁文档记的 `0x53E1DC`） | `0x0853F1DC`：**0 个读者**；`0x0853E1DC`：**0 个读者**；真实基址 `0x0853F140` 的读者 `0x08080B12` | 同上：`08080B12: ldr r5, [pc, #0x40]` → `0x0853F140` | **repoint**：`0x53F1DC` 是 `0x53F140 + 0x9C`（第 39 项）起的 47 窗口；`0x53E1DC` 不成立 | `0x53F140` | `0x53E1DC` 起的连续项若能读成合法 `0x08xxxxxx` 指针，则门禁文档成立、本裁决作废；反向：`0x53F140` 的 86 项必须全部是合法 ROM 指针 |

### 3.1 逐行的「裁决后权威基址」是怎么来的

- `0x53D910` —— 地址本身被原生代码引用（8 个读者），基址就是它。
- `0x53F140` —— `0x53F138` / `0x53F1DC` / `0x53F200` 三个旧基址**都是它的窗口**
  （槽 0 / 第 39 项 / 第 48 项起），真实基址是**唯一有原生读者**的那个（`0x08080B12`）。
- `0x596CCC` —— `0x53F200` 旧基址零读者；真表 `0x596CCC` 有 18 个原生读者，
  且条目形态（每项 4 个 u32 指针）与 `notes/sprite-frame-format-20261020.md` 完全一致。
- `0x546100` —— **注意：这不是被证明的表根**。它零读者，是一张独立 16 字节记录表
  的 12 条窗口；本轮找不到该表的真实基址（第 5 节第 1 条），所以它只是
  `base_status = unproven-window` 的暂定地址，写回路径仍不可用。

### 3.2 顺带发现的第 7 处重叠（**不在本次裁决范围**，仅登记）

`resource-pointers` bank 记的 `0x53F1DC`… 之外的 `legacy_resource_pointers` = `0x596F0C`
= `0x596CCC + 0x240` = 精灵动作表的**第 36 项**（id 4 / action 0），
即它同样是 `0x596CCC` 的一个窗口，而不是独立的资源指针表。
`0x08596F0C` 只有 1 个原生读者 `0x0807B220`（fn `0x0807AE04`），而**同一个函数**
也在读 `0x08596CCC`（`0x0807AF1C` / `0x0807AF64` / `0x0807AFA4` / `0x0807AFE4`），
这强烈支持「同一张表、两个窗口」的读法。
`resource-pointers` 不在本次允许改动的 bank 清单内，故**只登记不改**；
`tools/alias_audit.py` 把它列在「重叠窗口（信息项）」一节，不计入未裁决冲突。

---

## 4. Sappy 银行作废说明

**`sequel/content/sappy-engine/bank.json` 与 `sequel/content/audio/bank.json` 的全部结论作废。**

### 4.1 `0x08079668` 到底是什么

`0x08079668` 是一个 Thumb 函数，**不是数据表**，因此它本来就不该有「表读者」。
逐条反汇编（`tools/alias_audit.py` 会自动打印）：

```
08079668: push     {lr}
0807966A: sub      sp, #4
0807966C: lsls     r0, r0, #0x18
0807966E: lsrs     r2, r0, #0x18      ; r2 = cmd & 0xFF
08079670: cmp      r2, #0xe3
08079672: bhi      #0x8079704
08079674: movs     r0, #0x80
08079676: ands     r0, r2
0807967C: cmp      r1, #0
0807967E: bne      #0x80796e4         ; cmd & 0x80 -> 查表
08079688: cmp      r2, #0x64
0807968A: beq      #0x8079698         ; 0x64 -> [state+0x60]
08079692: cmp      r2, #0x67
08079694: beq      #0x80796c8         ; 0x67 -> [state+0x8C]
080796D8: ldr      r1, [pc, #4]        ; -> 0x0859937C
080796E4: ldr      r1, [pc, #0x18]     ; -> 0x08599634
080796F0: ldr      r0, [r0]            ; 取出一个 u32 指针
080796FA: bl       #0x8066758          ; 0x08066758：构造显示对象
```

它的行为是：**给一个字节 id → 从 0x08599634（忍具名文本指针表）/ 0x0859937C
或状态结构 +0x60/+0x64/+0x68/+0x8C 取出一个指针 → 调 0x08066758 造一个显示对象。**

### 4.2 第三方 / 旧 bank 声称了什么

- `sappy-engine/bank.json`：`command_handlers`（0x64-0x67「从引擎状态偏移装载」、
  0x80-0xE3「索引命令表 0x08599634」）、`related_structures.audio_table` =
  「0x53F138，88 条 Sappy 音频项」、`sappy_playback_function` = `0x08066758`、
  以及 `call_sites` 里的「15 个 BL 调用点来自 6 个函数」。
- `audio/bank.json`：`dispatcher` = 「0x08079668 音频命令分发器」、
  `indexed_command_table` = 「0x08599634，100 条 Sappy 音频指针」、
  `event_audio_mapping` = 「config_struct[0x770] 是每场战斗/每张地图的 BGM 命令」。

### 4.3 为什么作废（逐条判死）

| 旧声称 | 实测 | 判据 |
|---|---|---|
| `0x08599634` 是 Sappy 音频指针表 | 它是**忍具名文本指针表**：条目指向字模编码的中文串，如 `0x08002288` = `81 7C 81 7C 81 7C … 00`（全角空格 + 字形码 + 结束符），`0x08001F17` = `92 59 9A 9A 00 …` | 本仓库早已把 `0x599634` 登记为 `ninjutsu_names`；第三方 §4/C3 也实测「内容为『忍具…』中文」 |
| `0x08066758` 是 Sappy 播放函数 | 它是**显示对象构造函数**：`0806675E: push {r5, r6}` → `0806677E: bl #0x80655b4`（分配对象）→ `08066788: mov r1, sb` → `0806678A: bl #0x806626c`（初始化） | 里面没有 PCM/混音写入，也没有 Sappy 播放例程 |
| `0x53F138` 是 88 条音频表 | `0x0853F138` **0 个原生读者**；它是 `0x53F140` 起的指针数组头部（前 2 槽是代码指针 `0x080808BD` / `0x08080965`），槽 2..87 指向 `0x0812F5xx` 的场景对象描述符 | `LiteralIndex` 读数 0 |
| 「15 个 BL 调用点传的是音频命令」 | 调用点确实存在（`0x0807B9FC` / `0x0807F026` / `0x0807F052` / …），但传的是**消息 id**：例如 `0807F016: movs r0, #0xee` / `0807F018: lsls r0, r0, #3` / `0807F01A: adds r4, r4, r0` / `0807F01C: ldrb r0, [r4]` —— 即 `config_struct[0x770]` 里的一个字节，随后 `0807F026: bl #0x8079668` | 0x770 字段被旧 bank 描述成「音频命令」，实际是消息 id |
| 真正的 sound-ID 表在哪 | `0x465B70`（159 条 × 8 字节），9 个原生读者（`0x08061E3A` fn `0x08061D8C`；`0x0809AAC6` fn `0x0809A998`） | 本仓库已用 `tools/extract_audio.py` 独立提取 |

### 4.4 仓库现在怎么记录

- `tools/table_registry.py`：
  - 新条目 `falsified_sappy_claim`（`0x079668`）——**只保留被证伪的地址以便追溯**，
    note 写明「已证伪：0x08079668 是文本/消息对象分派函数」。
  - 新条目 `sound_id_table`（`0x465B70`，`verified=True`）——真正的音频表。
  - `FALSIFIED = {"sappy-engine": ..., "audio": ...}`。
  - `CONFLICTS["0x079668"]` / `CONFLICTS["0x53f138"]` 记录 verdict、判死检验与机械检查。
- `sequel/content/sappy-engine/bank.json`：删除 `command_range` / `command_handlers` /
  `related_structures` / `verification_method` / `verification_level`，
  加入 `falsified: true` + `falsification{reason, void_claims, replacement}`，
  `verification` 改为 `"falsified"`，**保留 `entries` 供追溯原始码字**。
- `sequel/content/audio/bank.json`：同样删除 `dispatcher` / `command_types` / `call_sites` /
  `audio_table` / `indexed_command_table` / `event_audio_mapping`，加入同样的
  `falsified` 记录。
- `tools/alias_audit.py` 的机械检查（每次运行都会跑）：
  - `0x53F138` 必须 0 个原生读者；
  - `0x080796E4` 必须读 `0x08599634`；
  - `0x080796D8` 必须读 `0x0859937C`。

---

## 5. 未决项

1. **`0x546100` 所在 16 字节记录表的真正表根与消费者。**
   已证实：0 个原生读者；同形记录向后延伸到 `0x5461BF`（末条止于 `0x5461C0`，
   距战斗配置矩阵 `0x5461C4` 恰好 4 字节），向前至少到 `0x545D80`。
   缺的证据：**一个能指向该数组的原生字面量**。
   下一步：用 `tools/consumer_locate.py --neighbors` 在 `0x545D80..0x5461C4` 区间里
   找被索引的地址（目前该区间**没有**任何被索引的地址，所以这条路要先解决
   「消费者用的是哪张表」）。在此之前 `0x546100` 只能当作「窗口」而不是「表根」，
   写回路径仍然不可用。
2. **地图描述符 `+0x1C` 字段的语义。** `maps` 叫「剧情底图 ID」，`encounter-zones`
   叫「zone_id（1..7，特殊地图 258 = 0x0102）」。两者指同一块 4 字节（47 条全对得上），
   但**两种读法都没有被原生代码证实**（没有消费者读 `+0x1C`）。
   缺的证据：一个读 `+0x1C` 的原生指令，或一次运行时读数。
   本轮只合并身份、不合并字段名。
3. **`0x53F140` 那 86 项记录到底是什么对象。**
   消费者链是 `0x08080BA0` → `0x08080B08` → `0x08063494` → `0x080625A4`，
   索引是 `id*11`；目标记录含 u32 指针与成组的 `u16` 标志位
   （`0x0001 / 0xFFFF / 0x0100 / 0x00080008` 一类）。
   缺的证据：一次把「id」与场景对象对应起来的运行时读数；
   `notes/mechanisms-20261020.md` 的机关效果表可能相关，但尚未打通。
4. **`resource-pointers`（`0x596F0C`）与精灵动作表 `0x596CCC` 的窗口关系**（第 3.1 节）。
   缺的证据：把 `0x53F140`/`0x596CCC` 两组指针的**目标区段**逐一比对，
   确认 `0x0812Fxxx`（对象描述符）与 `0x0813xxxx`/`0x0814xxxx`（精灵素材）确属两套。
   本轮的机械检查只覆盖了「`0x0807AE04` 同时读 `0x08596CCC` 与 `0x08596F0C`」这一条。
5. **`tools/populate_bank_json.py` 会把本次的 bank 改写回旧状态**（它仍按
   `0x53F1DC` / `0x53F200` 重新生成 `map-sprites` / `sprite-animations`）。
   该文件不在本次可改范围，故只登记：需要把它改成读 registry，否则下次跑一遍
   提取器就会把裁决冲掉。

### 5.1 对不在本次可改范围文件的**建议 diff**

- `notes/character-template-format-20261020.md` —— **这是 `python tools/completion_audit.py --check`
  当前唯一失败的探针，且在本轮开始前就已经失败（与本轮无关）**：
  `tools/completion_audit.py` 的 `SPECS["character-template"]` 要求该笔记里出现字面串
  `0x54241C + id * 0xB4` 与 `63 条有效`，而笔记现在写的是 `0x54241C + id*0xB4`
  与 `63 槽 (id 0..62)`。最小修法（把两处改成探针要的字面串）：

  ```diff
  --- a/notes/character-template-format-20261020.md
  +++ b/notes/character-template-format-20261020.md
  @@ -45 @@
  -0x54241C  角色定义表   id*0xB4   63 槽 (id 0..62)  -> 0x545068
  +0x54241C  角色定义表   0x54241C + id * 0xB4   63 条有效 (id 0..62)  -> 0x545068
  ```

  该文件不在本次可改范围（属于另一个 agent 的产出），故只登记不改。
- `tools/completion_audit.py`：`SPECS` 里 `items` / `skills` / `audio` / `palettes` /
  `encounter-zones` / `sprite-animations` / `sappy-engine` 的 `rom` 与 `unresolved`
  是硬编码的旧地址与旧结论（`SPECS["sprite-animations"]["rom"] = 0x53F200`、
  `SPECS["sappy-engine"]["rom"] = 0x079668`），`alias_map` 也按这些硬编码值算，
  所以即使 registry 已裁决，审计里仍会打印「与 X 同址」。
  建议：把这些 `rom` 改成裁决后的地址，并把 `unresolved` 换成指向本文件的说明。
- `notes/runtime-verification-gates-20260710.md`：
  - 第 46 行 `0x0853D914 + id*0x20` → 应为 `0x0853D910 + id*0x20`
    （`0x53D914` 是旧错误基址，见 `notes/battle-config-unsafe-template-fix-20260710.md` 第 38 行）；
  - 第 47 / 106 行 `0x0853E1DC` → 应为 `0x0853F140`；
  - 第 108 行「palettes（当前 bank `0x0853F138`）」→ 应为 `0x0853F140`；
  - 第 111 行「sappy-engine（`0x08079268` 代码范围）」→ 该 bank 已证伪。
- `notes/addresses.md`：「Audio Table 0x53F138」「Palette Table 0x53F138」
  「Map Sprite Animation Table 0x53F1DC」「Sappy Audio Engine Command Handler 0x079668」
  「Skill Table 0x546100」这 5 条都已过期。

---

## 6. 复现命令

```powershell
# 1) 别名冲突审计（本轮的交付物）：未裁决冲突 0、失败检验 0、registry 不一致 0
python tools/alias_audit.py rom/base.gba
python tools/alias_audit.py rom/base.gba --json build/alias_audit.json

# 2) registry 交叉核对：mismatches 必须为 0；alias conflicts 会继续列出原始碰撞（审计轨迹）
python tools/table_registry.py
python tools/table_registry.py --json build/table-registry.json

# 3) 完成度审计（--check 的既有失败与本轮无关，见 §5.1）
python tools/completion_audit.py --check

# 4) 单测基线：7 failures + 1 error（db_integrity / u32_pointer_patches，均为既有）
python -m unittest discover -s tests -p 'test_*.py'

# 5) 独立复核某个地址的原生消费者（父会话提供的通用定位器）
python tools/consumer_locate.py rom/base.gba --target 0x53D910
python tools/consumer_locate.py rom/base.gba --target 0x53F140 --neighbors 0x1000
python tools/consumer_locate.py rom/base.gba --target 0x596CCC
```

### 机器可读形式

裁决存在 `tools/table_registry.py`：

- `CONFLICTS` —— 争用地址 → `{verdict, canonical_bank, canonical_address,
  dispositions, evidence, falsifiable_test, checks, also_inspect}`；
- `ALIASES` —— 弃用别名 bank → 规范 bank（`items→skills`、`encounter-zones→maps`、
  `palettes→map-sprites`）；
- `FALSIFIED` —— 被证伪的 bank（`sappy-engine`、`audio`）；
- `TABLES` —— 每张表的权威基址（`verified=True` 表示本仓库独立复核过）。
