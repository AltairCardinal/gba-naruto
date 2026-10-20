# 12 个未知 battle-controller 态的 handler 级证据（2026-10-20）

## 目的与边界

`sequel/content/battle_controller_states.json` 的 38 态里仍有 12 态 `name_status=unknown`。本轮
只为这 12 态找**可引用的 handler 级证据**（入口地址、分派它的 ROM 代码、handler 行为），
并据此给出**被证据支持的命名**或「未确立 + 下一步最省测量」。

- 逆向树只读：`/Users/altair/github/gba-naruto-reverse`，本轮**未写入任何逆向侧文件**。
- ROM：`/Users/altair/github/gba-naruto/rom/base.gba`，SHA-256
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`（已复核）。
- 权威分母：`reverse/artifacts/rom-battle-controller-cfg-v1/`（manifest
  `282b4323bf965676…`，payload `c8b1d1c2068d8591…`），65,536 输入分母、38 个非 default 值。
- 反汇编用逆向树自带解码器 `reverse/tools/export_rom_cfg_inventory.py::_decode_one`
  （校验 ARMv4T 编码与对齐）。**注意**：直接用 capstone 线性反汇整块 ROM 会因非法指令字节
  偏移而错位（本轮实测把 `lsls r5, r5, #6` 误读成 `#5`），故下述指令均以 `_decode_one` 复核。

## 调度机制（本轮先闭合，之前未成文）

1. 分派区是 `0x080733A0..0x080735C8` 的二分比较梯，比较对象是 `r6`。
2. 每个 handler 结束时把**下一个状态值写进 `r6`**，再 `bl 0x0807504E`。该公共出口先比 `r6`
   是否等于哨兵 `0x0000FFFF`（`0x0807504E` 处字面量），不等则 `bl 0x080733A0` 回到分派梯
   → handler 之间靠 `r6` 串成一条尾调用链。证据：`0x0807504E: ldr r0,[pc,#0x1c] / cmp r6,r0
   / beq / bl #0x80733a0`。
3. 字段语义沿用逆向树已签清单 `reverse/tools/extract_battle_controller_states.py` 的
   `runtime_fields`：`0x0202680E`=current side、`0x02026810`=current unit object pointer、
   `0x02026A41`=selected unit slot、`0x020240C0`=unit pool（槽 1..12，步长 `0x1D4`）、
   `unit+0xC0`=action-category bits、`unit+0xCC`=affiliation、`unit+0xCD`=per-unit action
   state、`unit+0xC4/+0xC5`=x/y、`0x0200A880`=action-tail substate block；另
   `0x0202680F`=acting unit slot（本轮由 `0x080743DE` 写入推出）。
4. **被动 checkpoint 的限制**：`tools/analyze_battle_controller_checkpoints.py` 要求「内层
   返回点落在某个状态入口区间内」，而区间内必须有 `bl`。本轮逐条核对：**0x3100、0x8010、
   0xA000 三个 handler 区间内除公共出口外没有任何 `bl`**，纯 `.ss9` 存档**不可能**把
   controller frame 落进这三个区间，只能用一次性断点/观测器；其余 9 态区间内都有 `bl`。

## 12 态逐条

### 0x0010 → 提议 `battle_scene_resource_preload`
- 入口 `0x08073638`，区间 `[0x08073638,0x0807364A)`；分派点 `0x080733D0`
  （`0x080733CC: cmp r6,#0x10 / bne / b #0x8073638`）。
- 行为：`movs r0,#0; bl #0x08072EDC` → `bl #0x08073000` → `movs r6,#0x90; lsls r6,#5`
  （=0x1200）→ `bl 0x0807504E`。
- 证据：`0x08072EDC` 是逆向树已归档的 cutscene 图形/调色板载入器
  （`reverse/tools/verify_cutscene_obj_export.py:45` `loader_gba_address: "0x08072EDC"`）；
  `0x08073000` 是 controller provenance 已证明的 root（`reverse/notes/rom-cfg-proven-roots-v3-v4-20260813.md:147`
  「9 条 controller producer 证明 8 个 root：… `0x08073000` …」），其 producer 就在本
  handler 内：`reverse/artifacts/rom-cfg-proven-roots-v9` 中 `producer 0x0807363E → 0x08073000`。
  `0x08073000` 遍历 `0x02026BB0` 的 4 个字并逐个 `bl 0x08062788` 释放，再把 `0x0812C8B0`
  拷到 VRAM `0x06016FE0`。
- 命名前提：**只是静态读法**；是否就是「战斗开场演出」仍无运行时证据。
- 下一步最省测量：从既有 `artifacts/runtime-checkpoints/scenario-41-controller-entry.ss9`
  （SHA `4569846c…`，绑定 0x0000，resume PC `0x08073616`）零输入推进一次控制器迭代，在
  `0x08073000` 内部取帧，使 frame 落入 `[0x08073638,0x0807364A)`；用
  `tools/analyze_battle_controller_checkpoints.py` 复跑。

### 0x1000 → 提议 `side_activation_setup`
- 入口 `0x0807364A`，区间 `[0x0807364A,0x0807367C)`；分派点 `0x080733E8`
  （`0x080733E0: movs r0,#0x80 / lsls r0,#5`（=0x1000）/ `cmp r6,r0 / bne / b #0x807364a`）。
- 行为：清 `0x02026A56`、清 `0x0202680F`、清 `0x02026810`（current unit pointer），
  读 side `0x0202680E`，`bl #0x080753F8`（下一个本单位单位扫描）：该函数按
  `unit+0xCC==side` 且 `(unit+0xC0 & 0x70)==0` 且 `unit+0xCD!=0` 扫槽 1..12，命中返回 0、
  未命中返回 1。命中 → `r6=0x1300`；未命中 → `r6=r4`（寄存器传递，未静态钉住）。
- 证据：producer `0x0807365A → 0x080753F8`（`reverse/artifacts/rom-cfg-proven-roots-v9`）；
  `0x080753F8` 是已证明 root（同上 note 第 147 行）。
- 未闭合点：未命中分支的 `r6=r4` 只能靠运行时观察补齐。
- 下一步最省测量：在 `0x080753F8` 内取一帧（enemy-phase 存档
  `build/scenario-45-round1-enemy-phase-20260719/pulse-01.ss9` 已有 0x7000 绑定），
  同时记录返回后的 `r4`，判掉未命中分支的后继态。

### 0x1200 → 提议 `side_toggle`（本轮证据最强的一条）
- 入口 `0x080736B0`，区间 `[0x080736B0,0x080736F8)`；分派点 `0x08073400`
  （`0x080733EE: ldr r0,[pc,#0x18]`=0x1210 → `subs r0,#0x10`（=0x1200）/ `cmp / bne / b #0x80736b0`）。
- 行为：`ldrb r2,[0x0202680E]`（current side）→ `eors r2,#1` → `strb r2,[0x0202680E]`
  **翻转阵营位**；随后 `bl 0x0807305C` / `bl 0x08074FDA` / `bl 0x0806DF88` /
  `bl 0x08075350`，最后 `ldr r6,[pc,#8]`（=0x1210）→ `bl 0x0807504E`。
- 证据（逆向树自己已命名过）：
  - `reverse/tools/analyze_battle_status_expiry.py:35` `SIDE_TOGGLE = 0x080736B0`，
    同文件第 118–124 行把该处 12 字节**逐字节钉死**为
    `"0f498a78012042408a704878"`，并断言 `SIDE_END_ENTRY(0x0807367C) < SIDE_TOGGLE`。
  - `reverse/notes/battle-system-restoration-evidence-20260723.md:571-580`
    「控制器状态 `0x1100` 在 `0x0807367C` 调用 `0x0806C308`，随后才切换阵营位」；
    `reverse/notes/battle-status-expiry-bindings-20260723.json` 记录两组单输入对照，
    side 均 `0→1`。
  - producer `0x080736E4 → 0x08075350`（已证明 root）。
  - 本轮补上分派侧闭环：`0x080736A8: movs r6,#0x90 / lsls r6,#5`（0x1100 → 0x1200）。
- 下一步最省测量：复用 `battle-status-expiry` 已有的 side-end 单输入复放，把帧停在
  `0x08075350` 内（该 handler 最后一个调用），使 frame 落入 `[0x080736B0,0x080736F8)`；
  同一次采样读 `0x0202680E` 前后值即可把「静态翻转」与「运行时翻转」绑在同一收据上。

### 0x1220 → 提议 `current_side_unit_activation`
- 入口 `0x080737E6`，区间 `[0x080737E6,0x080738C0)`；分派点 `0x08073414`
  （`0x0807340C: movs r0,#0x91 / lsls r0,#5`（=0x1220）/ `cmp / bne / b #0x80737e6`）。
- 行为：以 `0x020240C0 + 0x1D4*slot` 扫槽 1..12，取 `unit+0xCC`（affiliation）等于
  `[0x0202680E]`（current side）的**第一个**单位，命中即 `b 0x080737D0` →
  `bl 0x0806F210(unit, unit+0xC4, unit+0xC5, 0, 2)`（与 `0x0000`/`0x0800` 相同的落位
  helper，把单位摆到地图上），随后显示 `0x0800096C`、调 `0x08066A48`、按阵营分派
  `0x0812F170`(side 0) / `0x0812F178`(side 1)（后者紧邻 ASCII `ATKCOMMAND`）、
  `bl 0x0806571C`、等待、再显示 `0x08000990`，最后 `movs r6,#0x80; lsls r6,#5`
  （=0x1000）→ `bl 0x0807504E`。
- 证据：`0x0806F210` 的落位用法与 `0x080735F0`（0x0000）、`0x08074416`（0x8000）一致；
  `unit+0xCC`=affiliation、`0x0202680E`=current side 来自逆向树已签 `runtime_fields`；
  ROM `0812F178: 8bd195d3 00000000 41544b43 4f4d4d41`（紧邻 `ATKCOMMAND`）。
- 注意命名撞车：逆向树旧标签把 `0x080736F8`（本分母的 **0x1210**）叫 `0x1220`
  `round_transition_script`，其 checkpoint 也在 `0x080736F8`。本条 **0x1220 = 0x080737E6**
  是另一个 handler，旧库存 36 态里根本没有它。
- 下一步最省测量：从 `scenario-41-turn-1-complete.ss9`（旧标签 0x1220 / 本分母 0x1210，
  SHA `a9e255d8…`）往后一步，在 `0x08066A48` 内取帧即可把 frame 钉进
  `[0x080737E6,0x080738C0)`。

### 0x3100 → 提议 `move_selection_gate`
- 入口 `0x08073B84`，区间 `[0x08073B84,0x08073BA8)`；分派点 `0x08073458`
  （`0x08073450: movs r0,#0xc4 / lsls r0,#6`（=0x3100）/ `cmp / bne / b #0x8073b84`）。
- 行为：`ldr r0,[0x0202680C]; ldr r0,[r0,#4]`（取 current unit pointer P）→
  `ldrb r0,[r0,#5]`（单位记录 +5 字节）；`!=0` → `ldr r6,[pc,#4]`（=0x3110，
  player_move_selection）→ 出口；`==0` → `ldr r0,=0x08000A34; b 0x08073E44`
  → `bl 0x08067158` 显示消息 → `movs r6,#0xc0; lsls r6,#6`（=0x3000，unit_action_menu）。
- 证据：`unit+5` 在整个控制器区间（`0x080732B4..0x0807509C`）**只被读过一次**，就是
  `0x08073B88`；其生产者不在控制器内，含义未闭合（不要猜成「移动力」）。
- 区间内**无 `bl`**（唯一出口是 `bl 0x0807504E`），故 `.ss9` 被动 checkpoint 落不进来。
- 下一步最省测量：在 `0x08073B84`（或分派点 `0x08073458`）下一次性断点，读 `r1`（P）、
  `P+5` 与 `0x0202680E`；这是本条唯一可行的最小测量。

### 0x3200 → 提议 `chakra_exchange_step_gate`
- 入口 `0x08073E14`，区间 `[0x08073E14,0x08073EB0)`；分派点 `0x0807342A`
  （`0x08073422: movs r0,#0xc8 / lsls r0,#6`（=0x3200）/ `cmp / bne / bl #0x8073e14`）。
- 行为（对 P = current unit pointer）：`P+7`=已走步数、`P+8`=目标步数、
  `P+0xA`=每步量、`P+0xC`=剩余池。`P+7==P+8` → `bl 0x08061E6C`+`bl 0x08067158`
  （消息 `0x08000ADC`）→ `r6=0x3000`；否则 `P+0xC<=P+0xA` → 消息 `0x08000B1D` →
  `r6=0x3000`；否则 `P+7+=1`、`P+0xC-=P+0xA` → `ldr r6,[pc,#4]`（=0x3210）→ 出口。
- 证据：`0x08061E6C` 是 VBlankIntrWait；同族的 `0x3210` 在逆向树已被命名
  `chakra_exchange_result`（`reverse/tools/extract_battle_controller_states.py` SEMANTICS[0x3210]，
  运行时证据「134 HP/4 查克拉 → 119 HP/5 查克拉，忍具库存不变」）。
  故本条按同一「查克拉交换」族命名；**具体字段角色（P+0xA/P+0xC 为每步量/剩余池）是
  指令流推断，未被运行时闭合**。
- 下一步最省测量：在 `0x08073E5C..0x08073E6A`（写 `P+7`/`P+0xC` 的两条指令）外侧取一次
  断点，读 `P+7/P+8/P+0xA/P+0xC` 与 `P+0x0E`（HP）前后值，一次即可确认「剩余池=HP」。

### 0x3220 → 提议 `chakra_exchange_commit`
- 入口 `0x08074074`，区间 `[0x08074074,0x080740D4)`；分派点 `0x0807346C`
  （`0x08073466: ldr r0,[pc,#0x1c]`=0x3220 / `cmp / bne / bl #0x8074074`）。
- 行为：`bl 0x08067158`（消息 `0x08001499`）→ `bl 0x08067158`（消息 `0x080014B4`）→
  读 action-tail 块 `0x0200A882`（≠1 → 转 0x3210）与 `0x0200A880`（≠0 → 转 0x3210）；
  两者满足时：`delta = P+7 - [sp+0x2C]` → `movs r0,#2; bl #0x08070D84`
  （该函数把值 2 与 delta 字节写进按选中槽索引的表 `0x0202680C+0x236` /
  `+0x238+slot*8`），再把 `P+7`、`P+0xC` 从栈上保存值还原 → `movs r6,#0xc0; lsls r6,#7`
  （=0x6000，player_action_confirmation）→ 出口。
- 证据：`0x0200A880` 的语义来自逆向树已签 `runtime_fields`「action-tail/menu substate
  block」；`0x08070D84` 是本态内唯一的写操作点。
- 注意：逆向树旧标签把这个 handler 记作 `0x3300`（`unresolved_state_3300`）。
- 下一步最省测量：在 `0x080740A4`（`bl 0x08070D84`）下一次断点，读 `r1`（=sp+0x18 的
  delta）、`0x02026A41`（选中槽）与 `0x02026A42+slot` 的落值。

### 0x8010 → 提议 `action_completion_router`
- 入口 `0x08074510`，区间 `[0x08074510,0x08074550)`；分派点 `0x080734BA`
  （`0x080734B4: ldr r5,[pc,#0x2c]`=0x8010 / `cmp / bne / bl #0x8074510`）。
- 行为：清 `0x02026A41`（selected unit slot）→ 读 P；`unit+0xCC`（affiliation）≠0 →
  `r6=0xC000`；否则 `unit+0xCD`（per-unit action state）==0xFF → `r6=0x9000`
  （facing_selection）；否则 → `r6=0xA000`。
- 证据：`0x08074828`（位于 0x9100 区间内的共享尾）写着 `ldr r6,[pc,#4]`=0x8010，
  而 `0x080744FE: b #0x8074828` 正是 `0x8000` 在结果码 r5==0 时的分支
  → 「动作无结果后先过 0x8010 再分流」成立；`0x08074548`/`0x08074538`/`0x0807452C` 三条
  `r6` 赋值即分流本体。
- 区间内**无 `bl`**（仅公共出口），`.ss9` 被动 checkpoint 落不进来。
- 下一步最省测量：在 `0x08074510` 一次性断点，读 `P+0xCC`、`P+0xCD` 与分支后 `r6`；
  一次采样可同时确认三分支条件。

### 0xA000 → 提议 `command_descriptor_stage`
- 入口 `0x0807484E`，区间 `[0x0807484E,0x08074870)`；分派点 `0x08073536`
  （`0x0807352E: movs r0,#0xa0 / lsls r0,#8`（=0xA000）/ `cmp / bne / bl #0x807484e`）。
- 行为：用 `ldm/stm` 把 **20 字节（5 个字）** 从 battle globals `0x0202D228+0x24`
  = `0x0202D24C` 拷到 `0x02026A40`；最后一个被载入的字（源 +0x10）留在 `r6` 里，
  即**后继状态值由该描述符携带**（`adds r6,r7,#0` 只是搬运 `ldm` 的结果）→
  `bl 0x0807504E`。
- 证据：`0x0202D228` 是逆向树已签的 battle globals 基址
  （`reverse/tools/analyze_battle_ai_utility_policy.py:174`）；`0x02026A40` 是同族
  0x8000/0xB000/0xC000 共用的「命令/单位槽记录」区。
- 区间内**无 `bl`**，`.ss9` 被动 checkpoint 落不进来。
- 下一步最省测量：在 `0x08074862`（`adds r6,r7,#0`）下一次断点，直接读被载入的
  `r6` 与 `0x0202D24C..0x0202D25F` 20 字节；一次采样即可确定该描述符里携带的后继态。

### 0xB000 → 提议 `default_command_load`
- 入口 `0x08074870`，区间 `[0x08074870,0x080748AC)`；分派点 `0x080734AC`
  （`0x080734A4: movs r7,#0xb0 / lsls r7,#8`（=0xB000）/ `cmp / bne / bl #0x8074870`）。
- 行为：`ldrb r0,[0x02026804]`；若 ==0 → 直接 `b 0x08074900`（`movs r6,#0xd0; lsls r6,#8`
  → 0xD000）；否则 `bl 0x08067158`（消息 `0x0800175D`）→ `bl 0x08085A40`（把 ROM
  `0x0812F18C` 起 **20 字节**拷到 `0x02026A40` 的请求函数）→ `bl 0x08085A74` 轮询完成
  → `b 0x08074900` → 0xD000。
- 证据：ROM `0x0812F18C` 的 20 字节以 ASCII `44 45 46 43 4f 4d 4d 41 4e 44` 开头 =
  **`"DEFCOMMAND"`**，这是本条命名最硬的证据；`0x08085A40` 把 (dst, len, src) 写入
  `0x03005E30/38/40/48` 并置位 `0x03005E48`，`0x08085A74` 轮询同一标志。
- 下一步最省测量：在 `0x08074884`（`bl 0x08085A40`）下一次断点，读 `0x02026A40` 的
  20 字节与 `0x0200A880/0x0200A882`；一次采样即证明「载入 DEFCOMMAND 到选中槽记录」。

### 0xC000 → 提议 `command_record_init`
- 入口 `0x080748AC`，区间 `[0x080748AC,0x08074918)`；分派点 `0x0807356C`
  （`0x08073564: movs r0,#0xc0 / lsls r0,#8`（=0xC000）/ `cmp / bne / bl #0x80748ac`）。
- 行为：`ldrb r0,[0x02026804]`；若 **==0** → 与 0xA000 同样的 20 字节
  `0x0202D24C → 0x02026A40` 搬运 → `b 0x08074900`（0xD000）；若 **≠0** →
  `bl 0x08067158`（`0x0800175D`）→ `bl 0x08085B8C`（同样请求把 ROM `0x0812F18C` 的
  `"DEFCOMMAND"` 20 字节拷进 `0x02026A40`）→ `bl 0x08085BC0` 轮询 → 再 `bl 0x08067158`
  （`0x0800177D`）→ `b 0x08074900` → 0xD000。
- 证据同 0xB000（同一段 ASCII `DEFCOMMAND`、同一目标地址、同一后继 0xD000）。
- 与 0xB000 的差别只在「battle struct +0 标志」两分支各多做/少做一件事，**游戏语义
  差别未闭合**，故只按「初始化命令记录」这一结构事实命名。
- 下一步最省测量：在 `0x080748B0`（`cmp r0,#0`）一次性断点，同时读 `0x02026804`、
  `0x02026A40` 的 20 字节与后继 `r6`；一次采样可把两分支都覆盖。

### 0xE000 → 提议 `post_action_unit_state_sync`
- 入口 `0x08074988`，区间 `[0x08074988,0x080749CC)`；分派点 `0x0807357C`
  （`0x08073574: movs r0,#0xe0 / lsls r0,#8`（=0xE000）/ `cmp / bne / bl #0x8074988`）。
- 行为：`ldrb r0,[0x0202680F]`（acting unit slot）→ `bl #0x08081544(slot)`（该函数按
  `unit+0xC0 & 0x0E` 分派单位动作类别）→ 读 P；`unit+0xCC`==0 → `bl #0x0806A854(slot)`
  （按槽取 `unit+0xD0` 状态并刷新）；否则若 `0x02026A56`<=1 → 同一条刷新路径；否则
  `bl #0x0806A854(P+0xCA)` → `ldr r6,[pc,#4]`（=0xE010，victory_exit_check）→ 出口。
- 证据：共享尾 `0x08074978: movs r6,#0xe0 / lsls r6,#8`（=0xE000）被
  `0x080744F4: b #0x8074978`（`0x8000` 结果码 r5==1 分支）调用 → 0xE000 由 0x8000
  进入；`0x080749C2: ldr r6,[pc,#4]`=0xE010 钉死后继。
- 下一步最省测量：在 `0x0807498C`（`bl 0x08081544`）下一次断点，读
  `0x0202680F`、`P+0xCC`、`0x02026A56` 与 `unit+0xC0`；一次采样可判定「动作类别分派
  + 状态刷新」是否成立。

## 汇总

| 态 | 入口 | 分派点 | 提议名 | 证据等级 |
|---|---|---|---|---|
| 0x0010 | 0x08073638 | 0x080733D0 | `battle_scene_resource_preload` | static（root 证明 + 载入器文档） |
| 0x1000 | 0x0807364A | 0x080733E8 | `side_activation_setup` | static（root 证明；未命中分支未闭合） |
| 0x1200 | 0x080736B0 | 0x08073400 | `side_toggle` | static 字节级 + 运行时 side 翻转 |
| 0x1220 | 0x080737E6 | 0x08073414 | `current_side_unit_activation` | static |
| 0x3100 | 0x08073B84 | 0x08073458 | `move_selection_gate` | static（`unit+5` 含义未闭合） |
| 0x3200 | 0x08073E14 | 0x0807342A | `chakra_exchange_step_gate` | static + 族内运行时证据 |
| 0x3220 | 0x08074074 | 0x0807346C | `chakra_exchange_commit` | static |
| 0x8010 | 0x08074510 | 0x080734BA | `action_completion_router` | static |
| 0xA000 | 0x0807484E | 0x08073536 | `command_descriptor_stage` | static |
| 0xB000 | 0x08074870 | 0x080734AC | `default_command_load` | static（ROM ASCII `DEFCOMMAND`） |
| 0xC000 | 0x080748AC | 0x0807356C | `command_record_init` | static |
| 0xE000 | 0x08074988 | 0x0807357C | `post_action_unit_state_sync` | static |

## 命名与升级规则（重要）

- 上表 12 个名字**只是提议**：每条都由本轮反汇编中的一条决定性指令 + 逆向树里可点名的
  路径/常量支撑。凡是只有推断的地方（`unit+5`、`P+0xA/P+0xC` 的字段角色、0xB000 与
  0xC000 的行为差别、0x1000 未命中分支）都在正文里写明了「未闭合」，**没有拿推断当
  事实写进名字**。
- `sequel/content/battle_controller_states.json` 的 `missing_evidence` 要求**两件**东西：
  (1) handler 级静态断言；(2) 至少一个 **hash 绑定的运行时 checkpoint，其 controller frame
  落在该态区间内**。本轮只闭合了 (1) 的材料，**(2) 对 12 态全部仍然缺失**，因此这 12 态
  在该 JSON 里**还不能**改成 `name_status: named`。
- 其中 0x3100 / 0x8010 / 0xA000 三个区间内没有 `bl`，用现有
  `tools/analyze_battle_controller_checkpoints.py` 的「栈内返回点」判据**不可能**命中，
  必须改用一次性断点/观测器；这三态是下一步最该先做的。
- 落盘本文件时**未修改逆向树任何文件**，也**未跑 mGBA**；所有结论均由 ROM 字节 +
  逆向树已签 artifact/notes 推出。
