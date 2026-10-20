# 写回路径证据（2026-10-20）

**主题**：给完成度审计里 10 个「无可用写回路径」的结构补上**真实可跑的写回路径**，
并对确实还不能写的给出**可证伪的理由**。

**模型（仓库既有约定）**：**复制原生条目 + 只改已知字段**；未知字段按原样拷贝，
绝不臆造。一条写回路径算「可用」的条件是：有工具能
(a) 读出原生条目 → (b) 施加作者给的改动 → (c) **回读并断言回读值 == 作者输入**。

**新增/扩展的工具**

| 文件 | 作用 |
|---|---|
| `tools/writeback_paths.py`（新） | 自检：逐结构跑一遍写回，打印「作者输入 / 回读值」，不等就非 0 退出 |
| `tools/import_character_template.py`（新） | 角色模板 `0x54241C` + 成长表 `0x545068` + 战斗记录 `0x545458` 的读/写 |
| `tools/import_sprite_action.py`（新） | 精灵动作表 `0x596CCC`（含 `0x596F0C` 窗口）的读/写 |
| `tools/import_story_script.py`（新） | 剧情 VM 四根表 `0x060C74/0x060D54/0x060E34/0x060EF0` 的定宽操作数改写 |
| `tools/import_battle_config.py`（扩展） | 地图描述符 `0x53D910`、编成矩阵 `0x5461C4`、对象描述符 `0x53F140`、关卡指针 `0x53DF70`、WRAM 分配表 `0x53D848`、u16 偏移表 `0x53F298` |
| `tools/build_db_patches.py`（扩展） | 上面这些写回路径的 **patch 生成面**（作者驱动，产出仓库标准 `bytes` patch） |

**复现（一条命令）**

```powershell
python tools/writeback_paths.py rom/base.gba        # 退出码 0 = 11 条写回路径全部往返通过
```

**基线不变**：`python -m unittest discover -s tests -p 'test_*.py'` 仍是
**74 tests / 7 failures + 1 error**（全部为既有失败，见 §5）；
`python tools/completion_audit.py --check` 仍退出 0。
`build/naruto-sequel-dev.gba` 与 `build/naruto-sequel-build-report.json` 未被改动
（新增的 patch 生成面**没有**接进 `tools/build_mod.py`，构建产物不受影响）。

---

## 1. 总表：10 个结构逐条结论

| # | 审计结构键 | 权威基址 | 写回路径 | 形式 | 入口 |
|---|---|---|---|---|---|
| 1 | `story-vm-roots` | `0x060C74` / `0x060D54` / `0x060E34` / `0x060EF0` | **有** | **长度保持**：只改定宽操作数，脚本长度与分支目标不变 | `tools/import_story_script.py` |
| 2 | `character-template` | `0x54241C`（0xB4/条，id 1..62） | **有** | 定长记录 + 已知字段 | `tools/import_character_template.py` |
| 3 | `battle-config` | `0x545458`（16 字节记录，87 条） | **有** | 定长记录 + 已知字段 | `tools/import_character_template.py` |
| 4 | `sprite-action-table` | `0x596CCC`（id*144 + action*16） | **有** | 4 个 u32 指针 | `tools/import_sprite_action.py` |
| 5 | `resource-pointers` | `0x596F0C` = `0x596CCC + 0x240` | **有（同一张表的窗口）** | 4 个 u32 指针 | `tools/import_sprite_action.py --window 0x596F0C` |
| 6 | `encounter-zones` | `0x53D910`（= `maps` 的别名） | **有** | 32 字节地图描述符 | `tools/import_battle_config.py --writeback` |
| 7 | `map-sprites` | `0x53F140`（86 项 u32 指针表） | **有** | 指针重定向 | `tools/import_battle_config.py --writeback` |
| 8 | `cutscene-scripts`（内容身份已裁决为**关卡数据块表**） | `0x53DF70`（**4 项 × 8 字节**指针对） | **有，但仅指针层** | 指针重定向（块格式已解：LZ77 图块/调色板，见 §2.8） | `tools/import_battle_config.py --writeback` |
| 9 | `save-state` | `0x53D848`（10 组 `{u32 addr, u32 size}`） | **有，但「存档案」身份已证伪**（见 §3.3） | 定长记录 | `tools/import_battle_config.py --writeback` |
| 10 | `units` | `0x53F298`（u16[64]） | **有，但受限**：只能复用原生偏移（见 §3.4） | 偏移重定向 | `tools/import_battle_config.py --writeback` |
| ＋ | `positions`（额外） | `0x5461C4`（0xB8/记录） | **有** | 定长记录 | `tools/import_battle_config.py --writeback` |

> 结论：**10 个结构全部有写回路径**，其中 3 个带明确的**范围限制**
> （`cutscene-scripts` 仅指针层——**因为该 bank 里没有脚本内容**，见 §2.8；
> `save-state` 的旧身份作废、`units` 仅限原生偏移）。
> 没有「完全写不了」的结构。

---

## 2. 逐条证据（读什么、改什么、怎么回读）

### 2.1 `story-vm-roots` —— 长度保持的定宽操作数改写

* **结构**：四张根表各 56 个 u32 槽（`0x060C74`→`0x060D54` 相差 0xE0 = 56×4），
  槽 0 全 0，场景 1..55（logic/events 1..46）指向脚本首地址。
* **可改的已知操作数**（`notes/story-script-vm.md` §4，指令语义已代码级证实）：
  `0x08` 头像 id、`0x0E` 双头像、`0x09/0x0A` 故事标志、`0x0F` 等待帧、
  `0x11` 清头像、`0x14` 剧情进度(u16)、`0x16/0x1A` 切场景、`0x1B/0x1D` 音乐、
  `0x1E` 载入地图、`0x1F` 子配置、`0x23` 队伍角色、`0x33` 事件队列值。
* **为什么必须长度保持**：文本指令 `0x01/0x05/0x13/0x20` 是变长的
  （NUL 结尾），改文本会移动后续所有指令，而脚本里的分支目标是**绝对 ROM 地址**
  （`0x06` +1/+5、`0x07/0x0D/0x32` +1、`0x0B/0x0C` +2、`0x15` +4、
  `0x34/0x36` +4、`0x35` +5、`0x38` +3、`0x39` +2），长度一变就全部失效。
  因此本路径**只改定宽操作数、原地改写**，脚本长度、根指针、分支目标都不动
  （自检里对这三项都有断言）。
* **回读**：`read_story_field()` 重新扫脚本、重新定位第 n 条该操作码的指令再读操作数。
* **跑法**：
  ```powershell
  python tools/import_story_script.py rom/base.gba --table before --scene 1 `
      --patch '{"opcode":8,"occurrence":0,"field":"portrait","value":3}'
  ```
  （PowerShell 5.1 会吃掉原生命令参数里的双引号，JSON 建议写成文件再传：
  `--patch patch.json`。）

### 2.2 `character-template` —— 定长记录 + 已知字段

* **几何**：`0x54241C + id*0xB4`，id 1..62（id 0 是全 0 空槽）；
  紧邻的成长表 `0x545068 + id*0x10`（8 个 u16 全部解出）。
* **只改这些**：`+0x01..+0x06` 六个属性基础值、`+0x08` 副属性(u16)、`+0x0A` 体力基础值(u16)、
  `+0x0C` 起 15 个 `(index,value,门槛,pad)`、`+0x48` 起 24 个同构条目、
  `+0xA8` 起 9 个道具 id。`+0x00`/`+0x07` 语义未解 → **原样拷贝**。
* **证据**：`notes/character-template-format-20261020.md`（消费者 `0x0806D4A0` / `0x0806D964`）。
* **回读**：`read_character_template()` 逐字段读回；自检额外断言**未改字节一个都没动**。

### 2.3 `battle-config` —— 16 字节战斗记录表

* **几何**：`0x545458 + i*0x10`，87 条（`0x545458 + 87*0x10 = 0x5459C8` 正好接上
  §4.2 的 12 字节特性表）。消费者 `0x0806D85C`（`ldm r0!,{r2,r6,r7}` 取 12 字节 + 4 字节）。
* **只改这些**：`+0x04..+0x09` 六个随等级成长的字节字段、`+0x0C` 成长类型(0..7)、
  `+0x0E` u16 成长量。其余字节语义未解 → 原样拷贝。
* **注意**：审计里 `battle-config` 指的是 `0x545458`（技能表那 16 字节记录），
  **不是** `0x5461C4` 编成矩阵；编成矩阵另有 `positions` 一行，本轮也一并补了写回路径。

### 2.4 / 2.5 `sprite-action-table` + `resource-pointers` —— 一张表、一个窗口

* **几何**：`0x596CCC + id*144 + action*16`，每项 4 个 u32
  （frames / animations / gfx / palette）；id 1..62 有效，id 0/63 全 0。
* **别名关系**：`resource-pointers` 声称的 `0x596F0C` 正好是
  `0x596CCC + 0x240` = 第 36 项 = **id 4 / action 0**；
  唯一原生读者 `0x0807B220` 与读表首的 `0x0807AF1C` **在同一个函数 `0x0807AE04` 里**
  → 是同一张表的窗口（`tools/table_registry.py` `CONFLICTS["0x596f0c"]`）。
* **写回**：改这 4 个指针字段；指针必须落在 48 Mbit ROM 地址范围内（或 0）。
* **注意**：表基址 `0x596CCC` 只按 4 字节对齐，所以条目是**按步长对齐**而不是
  绝对 16 字节对齐（第一次实现按绝对对齐判定，被自检打回后改正）。

### 2.6 `encounter-zones` —— 32 字节地图描述符（= `maps` 别名）

* **身份**：`tools/table_registry.py` `CONFLICTS["0x53d910"]` 判定
  `encounter-zones` 与 `maps` 是**同一张表**（8 个原生读者），`encounter-zones` 降级为弃用别名。
* **几何**：基址 `0x53D910`，**步长 32 字节、没有 4 字节头**（见 §4.2 的更正）。
  字段：`+0x00` u16 原始宽、`+0x02` u16 原始高、`+0x04` tile_gfx、`+0x08` palette、
  `+0x0C` layer0、`+0x10` layer1、`+0x14` metatile、`+0x18` terrain、`+0x1C` u8 background_id(+3 pad)。
  旧 bank 把 `+0x1C` 叫 `zone_id`——**命名仍待定**，写回按 `background_id` 处理。
* **回读**：`read_map_entry()` 逐字段读回。

### 2.7 `map-sprites` —— 86 项 u32 指针表

* **身份**：`CONFLICTS["0x53f1dc"]` 判定旧基址 `0x53F1DC` 只是
  `0x53F140 + 0x9C`（第 39 项窗口），门禁文档记的 `0x53E1DC` 零读者；
  **权威基址 `0x53F140`**，86 项 u32 指针，原生读者 `0x08080B12`。
* **写回**：把某一项重新指向**另一个原生块**（指针必须是合法 ROM 指针）。
* **还没做到的**：这些描述符记录本身的字段语义未解（`notes/alias-conflicts-20261020.md` §6.3），
  所以只能改「指向哪一条记录」，不能改记录内部的字段。

### 2.8 `cutscene-scripts` —— 内容身份已裁决：**关卡数据块表**（写回范围仍是指针层）

* **结论（一句话）**：`0x53DF70` **不是**剧情 VM 脚本表，而是
  **「关卡数据块表（战斗关卡图形资源表）」**——4 项 × 8 字节，每项是一对 u32 指针
  `(图块, 调色板)`。详见 `notes/evidence/cutscene-block-format-20261020.md`。
* **结构（已更正）**：原生步长是 **8 字节**（`0x08072F10: lsls r5, r0, #3`），
  即 **4 项 × (2 个 u32)**，占 `0x53DF70..0x53DF8F`。
  旧写法「16 项 × u32」把**两张表**并成了一张：
  `0x53DF90` 起还有 8 个 u32，是同一函数在 `0x08072F8C` 读的**另一张表**
  （对象描述符表，`0x080625A4` 按同样 8 字节步长索引它）；
  `0x53DFB0` 起是第三张**字节表**（由另一个函数 `0x08075B58` 在读）。
* **原生代码（决定性）**：唯一读者是 `0x08072EDC`（读指令 `0x08072F0C`），
  它把每对的两个指针分别交给 BIOS thunk `0x809C0E8`（`svc 0x12` = `LZ77UnCompVram`），
  目的地址是 **VRAM `0x06016000`**（图块像素）与 **调色板 RAM `0x05000380`**（第 28 号调色板槽）。
  剧情 VM 解释器 `0x080977B8` **不在**该函数的调用表里。
* **块格式（已解出）**：`10`（LZ77 魔数）+ u24 小端**解压长度** + LZ77 载荷；
  图块块解出 4096/4096/4096/2048 字节的 4bpp 图块像素，
  调色板块解出 32 字节（16 × BGR555）。
* **可写**：指针重定向（改「用哪一套图形资源」）。
* **不可写（现在是正面结论，不再是遗留缺口）**：这个 bank 里**根本没有脚本内容**，
  所以「把作者写的新剧情脚本塞进这些块」这条路**不存在**；
  写回范围就此**停在指针层**——理由从「块格式未解」升级为「**这里没有脚本可写**」。
* **新增事实（未实施，属另一条线）**：块本身已解出（LZ77），所以
  *「图形/调色板内容级」*改写机械上可行（原地重写载荷且解压后长度不变，
  或把表项指向另一个原生块）。建议单开一个「关卡图形资源」结构条目来做，
  **不要**混在 `cutscene-scripts` 这个 bank 名下。
* **可证伪的判据**：若能证明任一块地址被送进剧情 VM 解释器 `0x080977B8`，
  或被剧情 VM 四根表（文件偏移 `0x060C74/0x060D54/0x060E34/0x060EF0`）引用，
  则本结论作废。实测：8 个块地址在整 ROM 里**零 literal 引用**，
  且都不在 VM 四根表的 207 个脚本地址（`0x08009F2E..0x0805C6D3`）里。
* **⚠ 新发现的越界风险（留给 owner，本轮未改工具）**：
  `tools/import_battle_config.py` 的 `STAGE_POINTER_TABLE_COUNT = 16` 与
  `tools/build_db_patches.py::generate_cutscene_script_patches` 的 `entry_count=16`
  仍然按「16 项 u32」写 `0x53DF70..0x53DFAF`，
  因此 **index 8..15 会写进隔壁那张表 `0x53DF90..0x53DFAF`**。
  这两个文件不在本轮授权范围内，未改动；建议把计数收紧到 **4**，
  并把 `0x53DF90` 起的那张表单独立项。

### 2.9 `save-state` —— 表是真的，旧身份是假的

* **实测**：`0x53D848` 起 10 组 8 字节：`{u32 wram_addr, u32 size}`。
  取值与 `notes/battle-config-format.md` 的运行时结构一一对上：
  `(0x02022E30, 0x127C)` 战斗状态 4732 字节、`(0x020240C0, 0x17C4)` 战斗主数据 6084 字节、
  `(0x02026804, 8)` 战斗控制标志 8 字节……；4 个原生读者
  `0x0806869A / 0x08068954 / 0x08068CC0 / 0x08068D98`。
* **所以**：它是**WRAM 分配表**，不是「存档描述符表」。旧 bank 的内容身份不成立，
  按「存档描述符」写是**没有**写回路径的（存档数据在 SRAM，不在 ROM，
  见 `notes/unknown-save-state.md`）。
* **本轮给的路径**：对这张**实际存在**的分配表做定长记录写回
  （改 `wram_addr` / `size`，地址必须落在 EWRAM 范围）。
  这满足「结构有写回路径」，但**不等于**证明了存档格式。

### 2.10 `units` —— 受限路径（只能复用原生偏移）

* **事实**：唯一原生引用是 `0x08080B2C`（fn `0x08080814`），
  它把 `0x53F298` 当**u16 偏移表**索引（同一个函数 `0x08080B12` 读 `0x0853F140`）。
  `tools/build_db_patches.py::generate_unit_patches` 因此**拒绝**把编辑器的
  `char_id` 写进这里（"skipped unsafe 0x53F298 write"）。
* **本轮给的路径**：**受限**写回——只允许把某槽指向**同一张表里已经存在的原生偏移**
  （值的集合不变，等于「换一个已有目标」），写别的值直接抛
  `WriteBackError`。自检里专门断言这条约束**会咬人**
  （写 `0xBEEF` 必须被拒）。
* **为什么受限**：偏移的**取值域**没有证明。放开成任意值之前必须先证明
  「u16 偏移 + 某个基址 = 合法目标」，否则一次写错就是渲染崩。
* **可证伪的判据**：反汇编 `0x08080B2C` 之后，若能证明它把读出的 u16
  **加到某个基址上**（而不是当成角色 id 比较），则「偏移表」判定成立，
  接着证明目标区间上界，才可以把写回放开到任意合法偏移。

---

## 3. 负结果 / 死路（按 AGENTS.md 记录）

1. **本机 capstone 不可用**：`tools/_vendor/capstone/lib/` 只带了
   `libcapstone.dylib`（macOS），Windows 上 `import capstone` 直接
   `ImportError: fail to load the dynamic library`。
   → 本轮**没有**新增反汇编证据，所有字段语义都引用仓库里已有的指令级结论；
   需要新反汇编的结论（§2.8 块格式、§2.10 取值域）留作开放项。
2. **`0x53D910` 的「4 字节头」是错的**（旧 `import_battle_config.py` 一直这么写）：
   实测 entry 1 的宽高在 `0x53D930`、指针在 `0x53D934`，
   即 `slot = 0x53D910 + id*32`、无头；`+0x04` 是**字段偏移**不是头。
   旧代码因此会把宽高写到 entry 0 的 `tile_gfx` 指针上（错位一格）。
   本轮已更正（`ROM_BATTLE_SCENARIO_HEADER = 0`，并换成
   `notes/battle-config-format.md` 的字段顺序）。
3. **精灵动作表条目不是绝对 16 字节对齐**（基址只 4 字节对齐）→ 第一版
   `window_offset()` 判错，被自检打回后改成「按步长对齐」。
4. **第一版往返是空转的**：给 `sprite-action-table` 选的「另一个原生指针」
   恰好和原值相同（同一 sprite 各 action 共用同一调色板），
   「作者输入 == 回读」根本没证明写进去了。
   → 现在每个用例都必须**改到不同的字节**（`_donor()` 选一个与原值不同的候选），
   并额外断言「这次改动确实改了至少一个字节」。
5. **PowerShell 5.1 会剥掉原生命令参数里的双引号**：内联 JSON 参数会被打成
   `{kind:map_entry,...}`。→ CLI 改成同时接受 **JSON 文件路径**，
   解析失败时打印清楚收到的字符串。

---

## 4. 顺带发现（**未改**，留给对应 owner）

1. `tools/build_db_patches.py::generate_sprite_animation_patches` 仍写
   `0x53F200`，而按 `tools/table_registry.py` `CONFLICTS["0x53f200"]`，
   `0x53F200` **零原生读者**（它只是 `0x53F140` 指针数组第 48 项起的窗口），
   权威基址是 `0x596CCC`。→ 这条 DB 写回**写进了游戏不读的窗口**。
   本轮没动：改了会改变 `build/naruto-sequel-dev.gba` 的补丁集合（越权）。
2. `generate_resource_pointer_patches` 仍把 `0x596F0C` 当独立表；
   按裁决它是 `0x596CCC` 的窗口（见 §2.5）。
3. `generate_save_state_patches` 把第二个 u32 叫 `sram_offset_field`，
   实际是**分配大小**（§2.9）。
4. `generate_cutscene_script_patches` 的 docstring 写「17 entries」，
   实际是 16（`0x53DFB0` 起是下一张表）。
   **2026-10-20 续（见 §2.8）**：进一步证明这 16 项其实是**两张 4 项的 8 字节表**
   （`0x53DF70` 关卡图形资源表 + `0x53DF90` 对象描述符表），
   而 `entry_count=16` / `STAGE_POINTER_TABLE_COUNT=16` 会让 index 8..15
   **写进隔壁那张表**。两个文件都不在本轮授权范围内，未改动。
5. 审计表里 `battle-config`（`0x545458`）与 `positions`（`0x5461C4`）是两行，
   旧 `import_battle_config.py` 的注释把二者混为一谈；本轮已在代码里分开。
6. `docs/sequel-roadmap.md` 里可能需要补一行「10 个结构已有写回路径」——
   该文件不在本轮授权范围内，未改动。

---

## 5. 验证记录

```
$ python tools/writeback_paths.py rom/base.gba
PASS  story-vm-roots       0x060C74  剧情脚本 VM 四根表
      author input : {"portrait": 3, "offset": "0x009F3C"}
      read back    : {"portrait": 3, "offset": "0x009F3C"}
PASS  character-template   0x54241C  角色定义表
      author input : {"attr_a": 20, "hp_base": 90, "entries2[0]": {...}}
      read back    : {"attr_a": 20, "hp_base": 90, "entries2[0]": {...}}
PASS  battle-config        0x545458  战斗记录表
      author input : {"growth_type": 3, "growth_amount": 120}
      read back    : {"growth_type": 3, "growth_amount": 120}
PASS  sprite-action-table  0x596CCC  精灵动作表
      author input : {"gfx": "0x081746F0"}
      read back    : {"gfx": "0x081746F0"}
PASS  resource-pointers    0x596F0C  资源指针（动作表窗口）
      author input : {"frames": "0x08175B68"}
      read back    : {"frames": "0x08175B68"}
PASS  encounter-zones      0x53D910  地图描述符表（encounter-zones 别名）
      author input : {"background_id": 2}
      read back    : {"background_id": 2}
PASS  positions            0x5461C4  战斗编成矩阵
      author input : {"x": 3, "y": 5}
      read back    : {"x": 3, "y": 5}
PASS  map-sprites          0x53F140  场景对象描述符指针表
      author input : {"pointer": "0x0812F5B0"}
      read back    : {"pointer": "0x0812F5B0"}
PASS  cutscene-scripts     0x53DF70  关卡数据指针表
      author input : {"pointer": "0x0812DEE4"}
      read back    : {"pointer": "0x0812DEE4"}
PASS  save-state           0x53D848  WRAM 分配表
      author input : {"wram_addr": "0x02022E30", "size": 4732}
      read back    : {"wram_addr": "0x02022E30", "size": 4732}
PASS  units                0x53F298  u16 偏移表
      author input : {"value": 1}
      read back    : {"value": 1}

write-back paths checked: 11  passed: 11  failed: 0
$ echo $LASTEXITCODE
0
```

每个用例除「作者输入 == 回读值」外，还断言：

* **未知字节一个都没动**（角色模板 / 战斗记录 / 精灵动作 / 地图描述符 / 编成记录）；
* **这次改动确实改了至少一个字节**（避免空转往返）；
* 剧情脚本：**根指针没动、脚本长度没动**（长度保持的硬条件）；
* `units`：**非原生偏移必须被拒绝**（受限路径的硬条件）。

**基线**

| 命令 | 改动前 | 改动后 |
|---|---|---|
| `python -m unittest discover -s tests -p 'test_*.py'` | 74 tests / 7 failures + 1 error | 同左（失败项逐条一致） |
| `python tools/completion_audit.py --check` | 退出 0 | 退出 0 |

既有失败项（与本轮无关）：`test_positions_integration` 的
`test_build_syncs_rom_mirror_before_generating_patches`（error，缺 `sequel/editor.db`），
以及 `test_u32_pointer_patches` 里 7 个 `generate_*_patches` 子用例
（同样因为 `sequel/editor.db` 被 gitignore，纯净检出下没有 DB 行）。
`python tools/automated_test.py` 会**重跑构建**并改写
`build/naruto-sequel-dev.gba` 与 `build/naruto-sequel-build-report.json`，
本轮按要求**没有跑它**（新增 patch 生成面未接进 `build_mod.py`，构建产物不受影响）。

---

## 6. 仍开放的问题

| # | 问题 | 卡在哪 | 需要什么证据 |
|---|---|---|---|
| 1 | 剧情脚本**改文本** | 文本指令变长 → 脚本整体位移 → 绝对分支目标失效 | 在空闲区写新脚本 + 重定位 + 修全部 u32 分支目标（+1/+2/+3/+4/+5 各形式），并证明重定位后 `tools/decode_story_script.py` 仍然 0 issue |
| 2 | ~~`cutscene-scripts` 块的**内容**格式~~ **已关闭（2026-10-20）** | — | 已解：块是 LZ77（`10` + u24 解压长度 + 载荷），内容是 4bpp 图块 + 16 色 BGR555 调色板；**不是**剧情 VM 脚本。见 `notes/evidence/cutscene-block-format-20261020.md` 与 §2.8 |
| 2b | `0x53DF90` 起那张**对象描述符表**的记录格式 | 本轮只证明它与 `0x53DF70` 是两张不同的表 | 解 `0x0812DF2C` 起的记录字段（u32 指针 + u16 标志位），并找出 `0x08062668` 写进对象 `+0x1C/+0x20` 的两个 u32 的语义 |
| 2c | `cutscene-scripts` 写回路径的**越界风险** | `STAGE_POINTER_TABLE_COUNT=16` / `entry_count=16` 会写到隔壁表 `0x53DF90..0x53DFAF` | 把计数收紧到 **4**（`tools/import_battle_config.py`、`tools/build_db_patches.py` 不在本轮授权范围，未改动） |
| 3 | `units` 的 u16 **取值域** | 消费者 `0x08080B2C` 的用法未在本机反汇编（capstone 不可用） | 反汇编证明「u16 + 基址 = 目标」并给出目标区间上界 |
| 4 | `map-sprites` 描述符记录内部字段 | 记录含 u32 指针 + 成组 u16 标志位，字段名未定（`notes/alias-conflicts-20261020.md` §6.3） | 找到读这些标志位的原生代码 |
| 5 | `save-state` 的**存档**语义 | 存档数据在 SRAM，ROM 里没有存档描述符表 | 动态：mGBA 存档前后 dump SRAM 对比 |
| 6 | DB 驱动的写回层 | 编辑器 DB 没有这些结构的**已证明行键** | 给每张表一个能落到 ROM 行的键，才能把 `tools/build_db_patches.py` 的作者驱动生成面接进 `build_mod.py` |
