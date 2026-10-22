# Audio cue 语义来源审计（2026-07-13）

## 结论

本轮只使用 ROM 静态调用点、已闭合章节命令、既有运行时记录和 descriptor
结构，不按听感猜名。80 个有效 sound ID 中：

- 4 个得到高可信代码语义候选名：102 确认、103 取消、104 光标移动、105
  无效/拒绝；
- 4 个得到场景或来源约束候选名：4、101、118、144；
- 其余 72 个仍明确标为 `unknown`；
- 0 个具备游戏官方曲名或官方音效名证据。

因此“有玩家可理解候选名”为 **8/80**，但“官方名称”为 **0/80**。候选名不可在
没有新的受控运行时事件关联前去掉 `_candidate` 后缀。

## 方法与证据等级

`tools/extract_audio_cue_calls.py` 对 ARMv4T 两半字 Thumb `BL` 做原始半字扫描，目标是
公共播放 wrapper `0x08061E6C`。只有调用前一条指令精确为 `movs r0,#imm8` 时才记录
sound ID；寄存器、表或对象字段来源一律保留为 dynamic，不反向猜值。复现命令：

```bash
python3 tools/extract_audio_cue_calls.py rom/base.gba
python3 -m unittest tests.test_extract_audio_cue_calls
```

扫描结果为 290 个调用点：278 个立即数调用，覆盖 38 个有效 ID；12 个动态调用。
所有立即数都属于 `sequel/content/audio/bank.json` 的有效 ID，没有落到空 descriptor。

等级定义：

- **A**：输入位、选择值或失败分支直接决定调用，足以给出动作语义候选；
- **B**：章节/运行路线/音源类型把 cue 约束到可理解场景，但还没有精确可见事件 A/B；
- **C**：只证明结构家族或调用来源，不足以命名；
- **D**：只有 descriptor 可达性，或虽有调用点但没有安全的玩家语义名；名称必须为
  `unknown`。

player/track 家族也是结构结论而非听感判断：ID 1..18 都是 player 0、多轨、reverb
128 且跨 GOTO；51..54 是 player 3、多轨、reverb 128、一次性结束；101..105 与
156..158 是 player 1、单轨、priority 255；106..155 是 player 2、单轨、priority
255。下表用“loop music / jingle / system / gameplay”描述这些结构家族，不等价于曲名。

## 关键静态来源

### 直接输入语义

- ID 104：例如 `0x08067D68..0x08067F16` 检查方向位 `0x40/0x80/0x20/0x10`，
  修改 selection/scroll 字节后播放 104；相同模式分布于 64 个调用点。因此候选名为
  `ui_cursor_move_candidate`。
- ID 102/103：在同一批 UI controller 中反复位于确认进入和取消返回分支；例如
  `0x08067F3A..0x08067F88` 的两条提交路径分别播放 102/103。候选名保守写为
  `ui_confirm_accept_candidate` / `ui_cancel_back_candidate`。
- ID 105：例如 `0x0807191A..0x08071A4A` 中，有效目标播放 102，而表值为 `0xFF`
  的拒绝分支播放 105；其他 19 个调用也位于失败/不可用路径。候选名为
  `ui_rejected_invalid_action_candidate`。
- ID 101：`0x0808BE30..0x0808BE44` 在 input mask `0x08` 成立后播放，能证明是
  Start 键驱动的状态变化，但尚不能把状态安全命名为某个具体菜单。

### 章节、运行时与音源约束

- ID 4：alternate scenario 39 的真实脚本 `0x08031281` 以 `1B 04 00` 开始，
  随后是 portrait/speaker/text 序列并正常 End；ID 4 又属于 player-0 多轨循环家族。
  因而只命名为 `scenario39_dialogue_opening_music_candidate`，不猜角色主题或曲名。
- ID 118：title/new-game 运行探针捕获 ID 118；静态直接调用位于
  `0x0808B84A`（另有 `0x0807BCD4`）。路线能证明，具体画面动作尚未闭合，故为
  `title_new_game_route_transition_candidate`。
- ID 144：唯一含 CGB channel-4/noise 的 cue；又由 battle selector
  `0x0853E496[53]` 选择，因此可写 `battle_noise_effect_candidate`，不能进一步猜成
  爆炸、打击或某个忍术。

### 动态调用点（12/290）

| 调用点 | sound ID 来源 | 可安全得出的结论 |
|---|---|---|
| `0x08061F58` | 函数参数 u16，保存到 r4 | 播放并轮询完成的通用 wrapper；具体 ID 动态 |
| `0x0807BB84` | `0x0853E496[state+0x770]` | battle/gameplay selector |
| `0x0807BD64` | 同上 | battle/gameplay selector |
| `0x0807C05A` | 同上 | battle/gameplay selector |
| `0x0807C1E2` | 记录 `+7` 索引 `0x0853E496` | battle/gameplay selector |
| `0x0807CC98` | `0x0853E496[state+0x770]` | battle/gameplay selector |
| `0x08081528` | 参数 selector：3→107、4→106、6→117 | 三个动画/状态分支；动作名称未知 |
| `0x08088294` | r4 状态值 | 同函数稍后按相同值 stop；具体 ID 未静态固定 |
| `0x0809715C` | chapter opcode `1B` 的 cue operand | mode 0/1 播放；scenario 39 精确证明 ID 4 |
| `0x08098944` | 对象 byte `+8` | 对象携带的 cue；具体对象语义未知 |
| `0x08099628` | 对象 byte `+8` | 对象携带的 cue；具体对象语义未知 |
| `0x08099806` | 对象 byte `+9` | 对象携带的 cue；具体对象语义未知 |

`0x0853E496` 的五个 literal xref 分别位于 `0x0807BC64`、`0x0807BDF8`、
`0x0807C078`、`0x0807C33C`、`0x0807CCA4`。其 256-byte selector 中出现的有效
ID 为 120、121、122、123、124、125、130、131、133、136、137、138、140、
141、142、143、144。它证明 cue 与 battle/gameplay 状态相连，但没有角色/动作文本，
不能单凭索引给它们取音效名。

## 80 个 sound ID 的候选名清单

| ID | 候选名 | 等级 | 结构与 ID-specific 来源 |
|---:|---|:---:|---|
| 1 | `unknown` | D | loop music，player 0 / 8 tracks；仅见立即 stop |
| 2 | `unknown` | D | loop music，player 0 / 10 tracks；仅见立即 stop |
| 3 | `unknown` | D | loop music，player 0 / 10 tracks；无 ID-specific caller |
| 4 | `scenario39_dialogue_opening_music_candidate` | B | loop music，player 0 / 7 tracks；scenario 39 `1B 04 00` |
| 5 | `unknown` | D | loop music，player 0 / 6 tracks；立即播放 `0x08088F2C` |
| 6 | `unknown` | D | loop music，player 0 / 7 tracks；无 ID-specific caller |
| 7 | `unknown` | D | loop music，player 0 / 5 tracks；无 ID-specific caller |
| 8 | `unknown` | D | loop music，player 0 / 9 tracks；无 ID-specific caller |
| 9 | `unknown` | D | loop music，player 0 / 10 tracks；无 ID-specific caller |
| 10 | `unknown` | D | loop music，player 0 / 8 tracks；无 ID-specific caller |
| 11 | `unknown` | D | loop music，player 0 / 10 tracks；仅见立即 stop |
| 12 | `unknown` | D | loop music，player 0 / 9 tracks；无 ID-specific caller |
| 13 | `unknown` | D | loop music，player 0 / 9 tracks；无 ID-specific caller |
| 14 | `unknown` | D | loop music，player 0 / 8 tracks；立即播放 `0x080894FC` |
| 15 | `unknown` | D | loop music，player 0 / 4 tracks；无 ID-specific caller |
| 16 | `unknown` | D | loop music，player 0 / 6 tracks；无 ID-specific caller |
| 17 | `unknown` | D | loop music，player 0 / 5 tracks；无 ID-specific caller |
| 18 | `unknown` | D | loop music，player 0 / 7 tracks；无 ID-specific caller |
| 51 | `unknown` | D | one-shot multitrack jingle，立即播放 `0x08073106` |
| 52 | `unknown` | D | one-shot multitrack jingle，立即播放 `0x08089CDA` |
| 53 | `unknown` | D | one-shot multitrack jingle，13 个立即调用 |
| 54 | `unknown` | D | one-shot multitrack jingle；仅见立即 stop |
| 101 | `start_button_state_change_candidate` | B | system one-shot；`0x0808BE40` |
| 102 | `ui_confirm_accept_candidate` | A | system one-shot；48 个立即调用 |
| 103 | `ui_cancel_back_candidate` | A | system one-shot；23 个立即调用 |
| 104 | `ui_cursor_move_candidate` | A | system one-shot；64 个立即调用 |
| 105 | `ui_rejected_invalid_action_candidate` | A | system one-shot；20 个立即调用 |
| 106 | `unknown` | D | gameplay one-shot；`0x08081528` selector 4 |
| 107 | `unknown` | D | gameplay one-shot；`0x08081528` selector 3 |
| 108 | `unknown` | D | gameplay one-shot；无 ID-specific caller |
| 109 | `unknown` | D | gameplay one-shot；立即调用×2 |
| 110 | `unknown` | D | gameplay one-shot；立即调用×3 |
| 111 | `unknown` | D | gameplay one-shot；立即调用×2 |
| 112 | `unknown` | D | gameplay one-shot；立即调用×22 |
| 113 | `unknown` | D | gameplay one-shot；立即调用 `0x08091C02` |
| 114 | `unknown` | D | gameplay one-shot；立即调用 `0x08091C3A` |
| 115 | `unknown` | D | gameplay one-shot；立即调用×13 |
| 116 | `unknown` | D | gameplay one-shot；立即调用×2 |
| 117 | `unknown` | D | gameplay one-shot；立即 `0x0806BEA2`，另由 selector 6 |
| 118 | `title_new_game_route_transition_candidate` | B | gameplay one-shot；`0x0807BCD4`、`0x0808B84A` 及 live route |
| 119 | `unknown` | D | gameplay one-shot；立即调用 `0x0807C90E` |
| 120 | `unknown` | D | gameplay one-shot；`0x0853E496` selector |
| 121 | `unknown` | D | gameplay one-shot；`0x0853E496` selector |
| 122 | `unknown` | D | gameplay one-shot；`0x0853E496` selector |
| 123 | `unknown` | D | gameplay one-shot；`0x0853E496` selector |
| 124 | `unknown` | D | gameplay one-shot；`0x0853E496` selector |
| 125 | `unknown` | D | gameplay one-shot；`0x0853E496` selector |
| 126 | `unknown` | D | gameplay one-shot；`0x080878B6`、`0x08087B3C` |
| 127 | `unknown` | D | gameplay one-shot；`0x0807DCA0` |
| 128 | `unknown` | D | gameplay one-shot；立即调用×4 |
| 129 | `unknown` | D | gameplay one-shot；立即调用×21 |
| 130 | `unknown` | D | gameplay one-shot；立即调用×2，另见 selector |
| 131 | `unknown` | D | gameplay one-shot；`0x0853E496` selector |
| 132 | `unknown` | D | gameplay one-shot；`0x0806BB86`、`0x0807DD36` |
| 133 | `unknown` | D | gameplay one-shot；`0x0853E496` selector |
| 134 | `unknown` | D | gameplay one-shot；无 ID-specific caller |
| 135 | `unknown` | D | gameplay one-shot；`0x08081B34` |
| 136 | `unknown` | D | gameplay one-shot；`0x0853E496` selector |
| 137 | `unknown` | D | gameplay one-shot；`0x0853E496` selector |
| 138 | `unknown` | D | gameplay one-shot；`0x0853E496` selector |
| 139 | `unknown` | D | gameplay one-shot；立即调用×7 |
| 140 | `unknown` | D | gameplay one-shot；`0x0853E496` selector |
| 141 | `unknown` | D | gameplay one-shot；`0x0853E496` selector |
| 142 | `unknown` | D | gameplay one-shot；`0x0853E496` selector |
| 143 | `unknown` | D | gameplay one-shot；`0x0853E496` selector |
| 144 | `battle_noise_effect_candidate` | B | gameplay one-shot；selector index 53；唯一 CGB noise |
| 145 | `unknown` | D | gameplay one-shot；立即调用×4 |
| 146 | `unknown` | D | gameplay one-shot；`0x0807EE1E` |
| 147 | `unknown` | D | gameplay one-shot；`0x0807EF4E` |
| 148 | `unknown` | D | gameplay one-shot；无 ID-specific caller |
| 149 | `unknown` | D | gameplay one-shot；`0x0806C3AA`、`0x0807F33E` |
| 150 | `unknown` | D | gameplay one-shot；无 ID-specific caller |
| 151 | `unknown` | D | gameplay one-shot；无 ID-specific caller |
| 152 | `unknown` | D | gameplay one-shot；`0x0806BB8E`、`0x0807DD3E` |
| 153 | `unknown` | D | gameplay one-shot；无 ID-specific caller |
| 154 | `unknown` | D | gameplay one-shot；无 ID-specific caller |
| 155 | `unknown` | D | gameplay one-shot；`0x0806BB7E`、`0x0807DD2E` |
| 156 | `unknown` | D | system one-shot；`0x080896CE` |
| 157 | `unknown` | D | system one-shot；`0x080896BA` |
| 158 | `unknown` | D | system one-shot；`0x08072EB8` |

## 立即数调用清单摘要

完整 278 条地址由只读提取器逐条输出；以下对低频 ID 列全地址，对高频 ID 保留
首尾地址与总数，避免文档被重复 UI callsite 淹没：

| ID | 数量 | 地址摘要 |
|---:|---:|---|
| 5 | 1 | `0x08088F2C` |
| 14 | 1 | `0x080894FC` |
| 51 | 1 | `0x08073106` |
| 52 | 1 | `0x08089CDA` |
| 53 | 13 | `0x08074F56`、`0x08081632` … `0x08097492`、`0x080974D6` |
| 101 | 1 | `0x0808BE40` |
| 102 | 48 | `0x080665F2`、`0x08067478` … `0x08095F26`、`0x08096094` |
| 103 | 23 | `0x08067F88`、`0x08068198` … `0x08093FC2`、`0x080940AC` |
| 104 | 64 | `0x08067D9A`、`0x08067DCA` … `0x08095A14`、`0x0809606A` |
| 105 | 20 | `0x0806C79E`、`0x0806C802` … `0x080958EC`、`0x08095CB6` |
| 109 | 2 | `0x080726DC`、`0x0807D0D2` |
| 110 | 3 | `0x080725E2`、`0x0807D1BA`、`0x080892BE` |
| 111 | 2 | `0x08099C04`、`0x08099CB8` |
| 112 | 22 | `0x0806CB7C`、`0x0806CC0A` … `0x0808EB8A`、`0x080931F6` |
| 113 | 1 | `0x08091C02` |
| 114 | 1 | `0x08091C3A` |
| 115 | 13 | `0x0806CD44`、`0x0806CE30` … `0x0807D60E`、`0x0807D726` |
| 116 | 2 | `0x0806BDEA`、`0x0807DF52` |
| 117 | 1 | `0x0806BEA2` |
| 118 | 2 | `0x0807BCD4`、`0x0808B84A` |
| 119 | 1 | `0x0807C90E` |
| 126 | 2 | `0x080878B6`、`0x08087B3C` |
| 127 | 1 | `0x0807DCA0` |
| 128 | 4 | `0x0807EDDC`、`0x0807EF0C`、`0x08081BFC`、`0x08081FDA` |
| 129 | 21 | `0x0806B6CE`、`0x0806C5E0` … `0x0807E8FE`、`0x0807EA36` |
| 130 | 2 | `0x0807D062`、`0x0807F23A` |
| 132 | 2 | `0x0806BB86`、`0x0807DD36` |
| 135 | 1 | `0x08081B34` |
| 139 | 7 | `0x0807EAE0`、`0x0807EB88` … `0x0807EED0`、`0x0807EFE4` |
| 145 | 4 | `0x0807C9F4`、`0x0807CDCE`、`0x0807CE72`、`0x0807D946` |
| 146 | 1 | `0x0807EE1E` |
| 147 | 1 | `0x0807EF4E` |
| 149 | 2 | `0x0806C3AA`、`0x0807F33E` |
| 152 | 2 | `0x0806BB8E`、`0x0807DD3E` |
| 155 | 2 | `0x0806BB7E`、`0x0807DD2E` |
| 156 | 1 | `0x080896CE` |
| 157 | 1 | `0x080896BA` |
| 158 | 1 | `0x08072EB8` |

## 剩余闭合路线

1. 对 72 个 `unknown` 建立“一个可见动作只改变一个输入”的受控 replay，记录
   wrapper ID、调用 PC、场景状态和前后画面；同一 ID 至少需要两个一致实例，或一个
   单因素 A/B。
2. 对 B 级候选补精确事件边界：ID 4 捕获脚本开始帧，ID 101 捕获 Start 前后 UI，
   ID 118 把 230 次 route hit 收敛到具体调用 PC，ID 144 关联 selector index 53 的
   实际 battle effect。
3. 对 `0x0853E496` 先闭合 selector index 的上游领域身份，再把 17 个表内 ID 与动作
   名对应；目前只能称 battle/gameplay selector。
4. 扩展章节脚本解析必须遵循真实 opcode 边界；不能在 ROM 中搜索裸
   `1B <id> <mode>` 后直接当命令，因为文本/operand 中也可能出现相同三字节。
5. 最终名称表应同时保存 `candidate_name`、`evidence_level`、`source_addresses` 和
   `official_name_known=false`，避免编辑器把调查标签显示成官方曲名。
