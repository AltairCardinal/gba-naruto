# Profile text runtime probe（2026-07-13）

## 已完成的可重复探针

`tools/build_profile_text_runtime_probe.py` 在已验证 relocated chapter probe 上增加
`0x0808B1A4` hook。该点原指令为 `adds r0,r0,r1; ldr r0,[r0]`，正好位于人物
资料页按 `character_id*4 + 0x085A143C` 选择文本指针的位置。

scratch `0x0203FE80` 布局：

| offset | 内容 |
|---:|---|
| `+0` | magic `PTPR` |
| `+4` | hit count |
| `+8` | `character_id` (`r6[0]`) |
| `+C` | table entry address |
| `+10` | selected text pointer |
| `+14..+23` | selected target first 16 bytes |

control ROM SHA-256：
`a51636f1326c34fb68d41cb450eafc2914b9cbba281f7996c96586cfc1beee8a`。
最终 runtime 证明纠正了旧 character ID 假设：标题人物图鉴中的鸣人在该 reader 使用
character 0 / file `0x5A143C`，不是 character 1。variant 只把该四字节表项从
`0x0859F988` 改为同表 character 7 的 `0x0859FDE8`，正式 ROM SHA-256：
`66c9dbc60c2ab1962ea6d08b189bb0118668f069a93e133080fc8a5046bae74a`。
源目标均位于资料文本区并有 NUL terminator。测试保证 control/variant 的唯一差异
落在该四字节指针槽。

## 已淘汰的 checkpoint 路线

1. 从 `alternate-mission-selection.ss9` 输入 `A,Up,A,B,Up,A`，实际只推进到
   relocated alternate script 的第 13 次 dispatch，末 cursor `0x085F80A8`；profile
   scratch 全零。该简写路线不是人物概览入口。
2. `alternate-character-submenu.ss9` 与 `alternate-character-overview.ss9` 实际都在
   outer state `0x20` 的 `0x0808F190` 三栏 UI。它与 `0x0808B58C` profile browser
   是两套界面，旧 README 名称不能作为 reader 前后关系。
3. 驱动原先每次键盘输入前都会点击 `(480,215)` 的触摸敏感 canvas；该点击会额外
   注入一次确认，令方向键/B 路线看似随机跳页。回归测试先复现点击，再把聚焦改为
   `document.body.focus()`，不再产生隐式游戏输入。

## 2026-07-13 标题人物图鉴运行时闭合与归因纠正

运行时提供了 `tutorial-ui-save.sav`，但输入 `A×5, Start, Down, A, A` 实际进入
标题菜单的“人物图鉴”，自然渲染多行人物资料卡；后续复放确认 B 会直接返回标题，
outer state 为 1，而非存档恢复后的游戏状态。这条路线没有加载存档，旧“继续游戏
冷加载”归因撤销。

- control ROM SHA-256
  `a51636f1326c34fb68d41cb450eafc2914b9cbba281f7996c96586cfc1beee8a`；
- control：hit 1，character 0，entry `0x085A143C`，pointer `0x0859F988`；
- variant：hit 1，同一 character/entry，pointer `0x0859FDE8`；
- 两边 first-16 与各自 ROM 目标一致，可见多行简介正文改变；较长替换文本会覆盖
  更多诊断帧，因此只声明文本消费链，不把其他 UI 布局作为不变量。

`data-table-a` 已升级为 `runtime_verified`。紧凑证据在
`artifacts/runtime-checkpoints/profile-text-runtime-evidence.json`。

verification 保持不变，因为自然 reader 命中、精确 entry/pointer 与单四字节可见
A/B 均成立；被撤销的只有 save-load 前置归因。该路线不得再用作 levels 或其他
依赖存档进度的入口证据。

重要地址：table `0x5A143C`；selected-pointer consumer
`0x0808B19E..0x0808B1B2`；list builder `0x0808A6AC..0x0808A6F8`。
