# 原生消费者定位：字面量索引方法与 legacy 基址裁决（2026-10-20）

**工具**: `tools/consumer_locate.py`（可复现扫描器）
**证据文件**: `notes/evidence/consumer-evidence.json`（机器可校验，含 ROM SHA-256）
**ROM**: `rom/base.gba`
**关联**: `notes/completion-audit-20261020.md`（完成度审计）、
`notes/resource-locations.md`、`notes/alias-conflicts-20261020.md`、
`notes/character-template-format-20261020.md`、`notes/story-script-vm.md`

---

## 0. 结论摘要

- 建成了**全 ROM 字面量索引**：扫描所有 ARM `LDR Rn,[pc,#imm]`、Thumb-1
  `LDR Rt,[pc,#imm]`、Thumb-2 `LDR.W Rt,[pc,#imm]`，得到
  **18051 个被原生代码引用过的常量值 / 29920 条读取指令**。
- 审计覆盖的 **53 张表**里，**30 张找到了原生消费者**（L2 取证的机械入口），
  工具自动推出了多条表的**条目步长**（例：角色模板 → `0xB4`=180，
  战斗地图 → 4，技能表 → 16）。
- **决定性结论**：**22 个 legacy bank 的声明基址在原生代码里零读者**，
  其中 **21 个在整个 ROM 里连一次都没出现过**（既不是字面量池里的常量，
  也不是任何数据指针里的指针）。**这些 legacy 基址不是 ROM 里的真实结构首址**，
  而是早期按字节模式提取时落点选错的产物。
- 真正有原生读者的 legacy 项只有 5 个：
  `0x53D910`（= 战斗地图表，与 maps 同址，8 读者）、
  `0x53DF70`（过场脚本表，1 读者）、`0x53D848`（4 读者）、
  `0x596F0C`（1 读者）、`0x53F298`（1 读者）。

---

## 1. 为什么需要这个工具

`notes/completion-audit-20261020.md` 的 C2 条把「**原生代码定址**」列为四种
可接受的格式证明之一，但此前所有这类证明都是**手工**的：有人读了一段反汇编，
看见一个地址，把它抄进笔记。审计器只能 `grep` 笔记里有没有那个字符串 ——
**散文里出现一个地址，不等于 ROM 里那个地址是活的**。

`tools/consumer_locate.py` 把这一步机械化：

1. **建索引**：一次性扫出整个 ROM 里所有「被字面量加载读过的 32 位常量」，
   以及每条读取指令的地址、所在函数、用法分类；
2. **定位消费者**：对任意表基址，给出全部原生读者；
3. **判定基址真假**：某地址在**整个 ROM** 里一次都没出现 → 它不是 ROM 认识的地址；
4. **推步长**：从消费者的算术（`add rX,rX,rY,lsl #n` / `movs rT,#imm`+`muls`）
   自动推出条目大小；
5. **邻居探测**：列出该基址附近**真正被索引**的地址，用来把错的基址拉回真基址。

---

## 2. 方法（可复现）

### 2.1 三种寻址形态都要覆盖

只看 ARM 字面量池会漏掉本 ROM 的大部分代码 —— 实测本 ROM 的原生代码**以 Thumb 为主**：

| 形态 | 编码 | 目标地址公式 |
|---|---|---|
| ARM `LDR Rd,[pc,#imm]` | `cond 01 0 U 1 0 0 1 1111 Rd imm12` | `insn+8 ± imm12*4` |
| Thumb-1 `LDR Rt,[pc,#imm8]` | `01001 Rt imm8` | `Align(insn+4,4) + imm8*4` |
| Thumb-2 `LDR.W Rt,[pc,#imm12]` | `11111000 U 1011111 Rt imm12` | `Align(insn+4,4) ± imm12*4` |

> **踩坑记录**：第一版只实现了 ARM + Thumb-2，对 `0x53D910` 报「0 消费者」，
> 而实际消费者就在 `0x08069040`（`ldr r0,[pc,#0x24]`）。补上 Thumb-1 之后，
> 同一地址报出 8 个消费者。**只实现 Thumb-2 是不够的。**
>
> 另外 Thumb-2 的 `movw`/`movt` 常量构造也检查过：本 ROM 的 code 区**没有**
> 成对的 `movw`/`movt`（扫到的 271 个 `movw` 候选全在数据区），
> 所以「字面量池」这一条路径就是全部路径。

### 2.2 索引规模

```
literal index: 18051 distinct values referenced by 29920 instructions
```

### 2.3 基址真伪判据

- `consumers > 0` → 该地址是 ROM 认识的活结构首址（至少有一条原生加载）。
- `consumers == 0` 但 `raw_occurrences > 0` → 地址只被当作**数据指针/偏移**引用
  （例：`portrait_pieces` `0x4643C0` 只在 `0x46443C` = base+0x7C 处出现）。
- `consumers == 0` 且 `raw_occurrences == 0` → **这个地址 ROM 从来没提过**。
  它不可能是任何结构的基址。

---

## 3. 逐表结果

`consumers` = 读这个地址的原生指令条数；`raw` = 该地址在整个 ROM 里作为
32 位值出现的次数（含未对齐）。

| 表 | 文件偏移 | ARM 地址 | consumers | raw |
|---|---|---|---:|---:|
| background_table | `0x59903C` | `0x0859903C` | 2 | 2 |
| battle_actors | `0x5461C4` | `0x085461C4` | 24 | 25 |
| battle_rules | `0x594758` | `0x08594758` | 2 | 2 |
| character_names | `0x599280` | `0x08599280` | 24 | 26 |
| character_perks | `0x5459C8` | `0x085459C8` | 6 | 6 |
| character_template | `0x54241C` | `0x0854241C` | 4 | 4 |
| font_segments | `0x53D644` | `0x0853D644` | 2 | 2 |
| legacy_audio_or_palettes | `0x53F138` | `0x0853F138` | **0** | **0** |
| legacy_battle_encounters | `0x542384` | `0x08542384` | **0** | **0** |
| legacy_battle_handlers | `0x53E6D8` | `0x0853E6D8` | **0** | **0** |
| legacy_character_stats | `0x54507A` | `0x0854507A` | **0** | **0** |
| legacy_character_stats_b | `0x545200` | `0x08545200` | **0** | **0** |
| legacy_cutscene_scripts | `0x53DF70` | `0x0853DF70` | 1 | 1 |
| legacy_data_table_a | `0x5A14A4` | `0x085A14A4` | **0** | **0** |
| legacy_data_table_b | `0x5A2120` | `0x085A2120` | **0** | **0** |
| legacy_fonts | `0x53E5B4` | `0x0853E5B4` | **0** | **0** |
| legacy_function_pointers | `0x53D5F4` | `0x0853D5F4` | **0** | **0** |
| legacy_items_or_skills | `0x546100` | `0x08546100` | **0** | **0** |
| legacy_levels | `0x5459D4` | `0x085459D4` | **0** | **0** |
| legacy_map_events | `0x53EB08` | `0x0853EB08` | **0** | **0** |
| legacy_map_sprites | `0x53F1DC` | `0x0853F1DC` | **0** | **0** |
| legacy_menu_ui | `0x5A5774` | `0x085A5774` | **0** | **0** |
| legacy_resource_pointers | `0x596F0C` | `0x08596F0C` | 1 | 1 |
| legacy_sappy_engine | `0x079668` | `0x08079668` | **0** | **0** |
| legacy_save_state | `0x53D848` | `0x0853D848` | 4 | 4 |
| legacy_sprite_animations | `0x53F200` | `0x0853F200` | **0** | **0** |
| legacy_story | `0x53636C` | `0x0853636C` | **0** | **0** |
| legacy_story_b | `0x536BC8` | `0x08536BC8` | **0** | **0** |
| legacy_story_c | `0x538FF0` | `0x08538FF0` | **0** | **0** |
| legacy_story_d | `0x53AB78` | `0x0853AB78` | **0** | **0** |
| legacy_story_e | `0x53C3C0` | `0x0853C3C0` | **0** | **0** |
| legacy_tile_assets | `0x5A3218` | `0x085A3218` | **0** | **0** |
| legacy_units | `0x53F298` | `0x0853F298` | 1 | 1 |
| map_table | `0x53D910` | `0x0853D910` | 8 | 8 |
| material_names | `0x5A7E8C` | `0x085A7E8C` | 6 | 7 |
| mechanism_effects | `0x08136C` | `0x0808136C` | 1 | 1 |
| mission_description_table | `0x59D214` | `0x0859D214` | 3 | 3 |
| mission_hint_table | `0x59E920` | `0x0859E920` | 3 | 3 |
| mission_index | `0x348DAC` | `0x08348DAC` | 6 | 6 |
| mission_title_table | `0x59AA5C` | `0x0859AA5C` | 4 | 4 |
| ninjutsu_names | `0x599634` | `0x08599634` | 12 | 12 |
| per_character_skills | `0x545068` | `0x08545068` | 1 | 1 |
| pickup_dispatch | `0x0815E4` | `0x080815E4` | 1 | 1 |
| portrait_pieces | `0x4643C0` | `0x084643C0` | 0 | 1 |
| portrait_table | `0x5A4DEC` | `0x085A4DEC` | 1 | 1 |
| reward_table | `0x59EAE0` | `0x0859EAE0` | 4 | 2 |
| skill_table | `0x545458` | `0x08545458` | 8 | 8 |
| sound_id_table | `0x465B70` | `0x08465B70` | 9 | 9 |
| sprite_action_table | `0x596CCC` | `0x08596CCC` | 18 | 18 |
| story_after_root | `0x060D54` | `0x08060D54` | 1 | 1 |
| story_before_root | `0x060C74` | `0x08060C74` | 1 | 1 |
| story_events_root | `0x060EF0` | `0x08060EF0` | 1 | 1 |
| story_logic_root | `0x060E34` | `0x08060E34` | 1 | 1 |

---

## 4. 工具自动推出的条目步长（交叉验证已知结论）

| 表 | 推出的 stride | 消费者 | 与既有结论 |
|---|---:|---|---|
| `0x54241C` 角色模板 | **180 (0xB4)** | `0x0806D964` `movs r0,#0xb4` + `muls r1,r0,r1` | ✅ 与 `notes/character-template-format-20261020.md` 一致 |
| `0x545458` 技能表 | **16** | `0x0806D866` | ✅ 与该笔记「16 字节记录、87 条」一致 |
| `0x5461C4` 战斗配置 | 4（指针步长） | `0x08069040` | ✅ |
| `0x594758` 胜负条件 | **204 (0xCC)** | `0x080751AA` | ✅ 与 `stage*0xCC` 一致 |
| `0x465B70` 音频 sound-ID | **8** | `0x08061E3A` `adds r1,#8` | ✅ 与「159×8」一致 |
| `0x53D910` 战斗地图 | 4（指针步长） | `0x08069040` | ✅ |

---

## 5. legacy 基址裁决：21 个地址 ROM 从来没提过

### 5.1 事实

下列 21 个 legacy 基址，`raw_occurrences == 0` —— 它们的 32 位值在**整个 ROM 的
任何位置**（代码字面量池、数据指针表、任何字节对齐）**一次都没出现过**：

`0x53F138` `0x542384` `0x53E6D8` `0x54507A` `0x545200` `0x5A14A4` `0x5A2120`
`0x53E5B4` `0x53D5F4` `0x546100` `0x5459D4` `0x53EB08` `0x53F1DC` `0x5A5774`
`0x08079668` `0x53F200` `0x53636C` `0x536BC8` `0x538FF0` `0x53AB78` `0x53C3C0`
`0x5A3218`

> `0x08079668` 特别说明：它本来就是**代码**（文本/消息脚本解释器），
> 不是数据表，所以「零读者」是**预期**的 —— 这条不能拿来证伪地址本身，
> 只能用来证伪「Sappy 音频引擎表」这个**命名**。

### 5.2 推论

「ROM 从未提及这个地址」意味着：

- 该地址**不可能**是任何原生结构的**首址**（基址）；
- 但**不能**由此推出「那里的字节不是表数据」——早期 legacy 提取是按字节模式
  落点的，模式像表而地址错，是完全可能的。真正的结论是：
  **legacy bank 声明的 `table_offset` 不能当作结构基址使用。**
- 因此「items/skills 同址 `0x546100`」「palettes/audio 同址 `0x53F138`」
  这类**同址冲突**，冲突双方的地址**都**站在流沙上 ——
  正确裁决不是「合并」或「拆分」，而是「两个基址都无效，重新定位」。
  唯一例外是 `0x53D910`：它确实被原生代码引用（8 个读者），
  真的存在「maps 与 encounter-zones 同址」这一冲突。

### 5.3 邻居探测：附近被索引的地址（**不是**本表的修正基址）

`--neighbors` 列出该地址附近**真正被原生索引**的地址（读者数 ≥ 1）。

> **重要更正（同一工作周期内发现）**：这些邻居**绝大多数是紧邻的其它表**，
> **不是**「本表被写错了地址、应该改成这里」。
> 判据：`tests/test_u32_pointer_patches.py` 里已经写死了 legacy 表的声明跨度，
> 例如 `menu-ui` 声明 `0x5A5774..0x5A57C0`（20 条 × 4 字节），
> 而邻居探针给出的高热度地址是 `0x5A57C4` —— 那是**声明跨度的下一张表**，
> 差 4 字节。`tile-assets` 声明 `0x5A3218..0x5A322C`，邻居 `0x5A320C` 在其
> **前面** 0xC 字节，是上一张结构。`sprite-animations` 声明
> `0x53F200..0x53F294`，邻居 `0x53F298` 又是下一张表。
> 所以：**「邻居」只说明该片区有活表，不说明本表该挪到哪。**

| legacy 基址 | 最近被索引地址 | 读者数 | 与声明跨度的关系 |
|---|---|---:|---|
| `0x546100` items/skills | `0x5461C4` | 26 | 战斗配置矩阵，在其**前面** 0xC4 字节 |
| `0x5459D4` levels | `0x5459C8` | 6 | 角色特性表，在其**前面** 0xC 字节 |
| `0x54507A` character-stats | `0x545068` | 1 | 逐角色技能表，在其**前面** 0x12 字节 |
| `0x5A5774` menu-ui | `0x5A57C4` | 12 | 声明跨度 `0x5A5774..0x5A57C0` 的**下一张表** |
| `0x5A3218` tile-assets | `0x5A320C` | 10 | 声明跨度 `0x5A3218..0x5A322C` 的**上一张结构** |
| `0x53E5B4` fonts | `0x53E596` / `0x53E698` | 1 / 2 | 字宽表候选在 `0x53E596` 一带 |
| `0x53D5F4` function-pointers | `0x53D5B4` / `0x53D5F0` | 1 / 1 | 声明跨度 `0x53D5F4..0x53D61C` 之前的结构 |
| `0x53F138` palettes/audio | `0x53F140` / `0x53F298` / `0x53F2EE` / `0x53F310` | 1~2 | 真实运动/精灵对象表在 `0x53F140`..`0x53F348` 一带 |
| `0x53F1DC` map-sprites | `0x53F140` / `0x53F298` / `0x53F310` | 1~2 | 同上簇 |
| `0x53F200` sprite-animations | `0x53F140` / `0x53F298` / `0x53F310` | 1~2 | 声明跨度 `0x53F200..0x53F294` 的下一张表（真表是 `0x596CCC`） |
| `0x5A14A4` data-table-a | `0x5A14F4` / `0x5A143C` | 1 / 2 | 声明跨度 `0x5A14A4..0x5A14F0` 的下一张表 |
| `0x5A2120` data-table-b | `0x5A219C` / `0x5A2034` | 2 / 2 | 声明跨度 `0x5A2120..0x5A216C` 之后的表 |
| `0x53EB08` map-events | `0x53EE98` / `0x53EF30` | 3 / 6 | — |
| `0x53636C` story | `0x536A23` | 1 | 该片区只有一处被索引 |
| `0x536BC8` story-b | `0x536A23` | 1 | 同上 |
| `0x538FF0` story-c | `0x5387FA` | 1 | — |
| `0x53AB78` story-d | `0x53AC48` | 1 | — |
| `0x53C3C0` story-e | `0x53C7F9` / `0x53C8E0` | 1 / 1 | — |
| `0x53E6D8` battle-handlers | `0x53E69C` / `0x53E698` | 1 / 2 | — |
| `0x542384` battle-encounters | `0x54241C` | 4 | 紧邻角色模板表；`0x542384` 在其**前面** 0x98 字节 |
| `0x545200` character-stats-b | `0x545158` | 1 | — |

**这些候选只说明「该片区有活表」，不构成本表的修正基址。**
真正的裁决见 `notes/alias-conflicts-20261020.md`。

**反例（必须一起看）**：`legacy_resource_pointers` `0x596F0C` **有 1 个原生读者**
（`0x0807B220`，函数 `0x0807AE04`），声明跨度 `0x596F0C..0x596F58`。
它虽然同样来自 legacy 提取，却**是真的**。
→ 所以「legacy 提取出来的一定是假的」是错的；判据必须是
**「这个具体地址 ROM 有没有提过」**，而不是「它来自 legacy 提取」。

### 5.4 判死检验

| 结论 | 检验（能推翻它） |
|---|---|
| 21 个 legacy 基址 ROM 从未提及 | `python tools/consumer_locate.py rom/base.gba --all --evidence notes/evidence/consumer-evidence.json` 后查 `raw_occurrences`；若某个基址的 raw > 0，本结论对该基址作废 |
| `0x546100` 落在战斗配置表头部 | 反汇编 `0x08069040` 附近的消费者，确认 `0x5461C4` 的索引范围回退到 `0x546100`；若 `0x5461C4` 的最小索引 > 0 则本条作废 |
| 真实基址候选（§5.3） | 逐条读候选地址的消费者反汇编，确认它索引的元素数与该 bank 的条目数一致 |

---

## 6. 复现命令

```powershell
$env:PYTHONIOENCODING='utf-8'

# 全量扫描 + 生成证据文件
python tools/consumer_locate.py rom/base.gba --all --evidence notes/evidence/consumer-evidence.json

# 单表消费者
python tools/consumer_locate.py rom/base.gba --target 0x54241C

# 邻居探测（找真实基址）
python tools/consumer_locate.py rom/base.gba --target 0x546100 --neighbors 4096

# 完整 JSON
python tools/consumer_locate.py rom/base.gba --all --json build/consumer-scan.json
```

`notes/evidence/consumer-evidence.json` 里带 **ROM 的 SHA-256**，
换 ROM 后必须重新生成 —— 审计器会核对指纹，避免陈旧证据蒙混过关。

---

## 7. 遗留

- `portrait_pieces` `0x4643C0`：只在 `0x46443C`（base+0x7C）被引用，
  说明头像拼块表是按**固定偏移**取块，而不是按基址索引；
  拼块表的真实结构仍需单独判读。
- `reward_table` `0x59EAE0`：raw 2 次但 consumers 4 次（同一值被两条指令读、
  只存一份），条数与 24 字节/条 的说法需要另证。
- `legacy_sappy_engine` `0x079668`：零读者是**预期**（那里是代码不是表），
  只能用「命名」层面的证伪，不能用零读者证伪地址。

---

## 8. 后续裁决（本轮补完）

同址冲突的完整裁决在 `notes/alias-conflicts-20261020.md`
（工具 `tools/alias_audit.py`，6 项冲突全部裁决、判死检验全绿）。
本轮补上的**第 7 处重叠**：

| 地址 | 关系 | 证据 | 裁决 |
|---|---|---|---|
| `legacy_resource_pointers` `0x596F0C` | = `0x596CCC + 0x240`，即**精灵动作表的第 36 项**（id 4 / action 0） | `0x08596F0C` 只有 1 个读者 `0x0807B220`（fn `0x0807AE04`），而**同一个函数**还读表首 `0x08596CCC`（`0x0807AF1C` / `0x0807AF64` / `0x0807AFA4` / `0x0807AFE4`） | **merge**：它是 `sprite-animations`（权威基址 `0x596CCC`）的弃用窗口，不是独立的资源指针表 |

登记位置：
- `tools/table_registry.py` 的 `CONFLICTS["0x596f0c"]` + `ALIASES["resource-pointers"]`
- `sequel/content/resource-pointers/bank.json`（保留历史 `table_offset`，
  但 `description` / `notes` / `canonical_bank` 已写明是窗口）
- 判死检验：`0x0807AE04` 若不再读 `0x08596CCC`，
  或 `0x596F0C` 处的条目形态与 `0x596CCC` 的 4-u32 指针记录不同构，本裁决作废。

### 8.1 流程加固：`populate_bank_json.py` 不会再把裁决冲掉

`tools/populate_bank_json.py` 原来会按**旧基址**重新导入条目并把
`verification` 写成 `static_verified` —— 一次运行就能把上面所有裁决冲回原状。
现在它读 `tools/table_registry.py` 的 `ALIASES` / `FALSIFIED` / `CONFLICTS`，
遇到**已裁决的 bank 直接跳过并打印原因**。
（顺带修掉该文件用 `Path.write_text` 写 CRLF 的老问题，改走
`tools/lib/io.write_text`。）

### 8.2 重新定位的操作方法：`consumer_locate.py --suggest`

23 个「基址无效」的结构要重新定位真实基址，不能靠猜。
`tools/consumer_locate.py` 新增 `--suggest N`：对一个**零读者**的基址，
列出它周围 N 字节内**被原生代码引用过**的地址，按读者数排序，
并给出第一个读者的地址 —— 于是搜索从「猜测」变成「有证据的候选」。

```powershell
python tools/consumer_locate.py rom/base.gba --target 0x546100 --suggest 4096
```

实测（`0x546100`，items/skills 的旧基址）：

```
candidate base 0x085461C4 (file 0x5461C4, delta +0xc4, 26 readers, first reader 0x0806DF28)
candidate base 0x08545458 (file 0x545458, delta -0xca8,  8 readers, first reader 0x0806D866)
candidate base 0x08545BE4 (file 0x545BE4, delta -0x51c,  7 readers, first reader 0x0806D91A)
candidate base 0x085459C8 (file 0x5459C8, delta -0x738,  6 readers, first reader 0x0806D6E6)
```

`0x5461C4` 正是**战斗配置矩阵**（26 个读者），
说明 items/skills 那张 16 字节记录表就落在它前 0xC4 字节处。

`0x5A5774`（menu-ui 的旧基址）同理：
`0x085A57C4`（12 个读者）是最强候选。

> 判死检验：候选只是「附近被引用过的地址」，
> 真正的基址还要用**结构形态**确认（条目数、步长、字段语义）。
> 上面的 0x5461C4 / 0x5A57C4 都**不是**这两个 bank 的真实基址 ——
> 它们是各自片区里被引用最多的地址。

---

## 9. 方法修正（2026-10-21）：邻域分析必须查**全量**索引

本轮用 §8.2 的方法去找 17 个仍未定位的 legacy 基址时踩了一个坑，值得写下来：

- `notes/evidence/consumer-evidence.json` **只存了 54 张表**（审计关心的那些），
  而字面量索引本身有 **18051** 个值、其中 **1196** 个是「活的」
  （有原生代码加载）。
- 拿那份 54 张表的子集做邻域分析，**候选集会被静默截断**，结论跟着错。
- 例：`0x0853EE98` 在证据文件里**查不到**，但全量索引显示它有 **3 个原生读者**
  （`0x080806BA` / `0x0808077E` / `0x0808082E`），是一张**此前完全没被登记**
  的活表（10 字节步长、15 条记录）—— 见
  `notes/evidence/units-offset-table-20261020.md` 与
  `tools/frame_descriptors.py`。

**正确做法**：用全量索引。

```python
import sys, pathlib
sys.path.insert(0, '.')
from tools import consumer_locate as cl
index = cl.LiteralIndex(pathlib.Path('rom/base.gba').read_bytes())
# index.readers: 值 -> [(读者指令地址, 模式)]
# index.pool_value: 常量池地址 -> 值
```

纠正后，17 个未定位基址的候选集从「0~3 个」变成「5~10 个」，
其中三个已直接对上（`character-stats` = 生长表 `0x545068` + 0x12、
`levels` = perks 表 `0x5459C8` + 0xC、`battle-encounters` = 角色模板 `0x54241C`
− 0x98）。工具化版本见 `tools/legacy_rebase.py` 与
`tools/story_table_locate.py`。

> 顺带修正 §8.2 的那句话：`--suggest` 走的是**全量**索引，所以它给出的
> 候选本来就是全的；被截断的是**手工拿证据文件做邻域分析**的做法。
> 两条路的结论因此可以互相印证。
