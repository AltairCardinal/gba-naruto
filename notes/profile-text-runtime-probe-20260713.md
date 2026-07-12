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
variant 只把 character 1 表项 file `0x5A1440` 从 `0x0859FA18` 改为同表
character 7 的 `0x0859FDE8`，SHA-256：
`e5584a1c4adc962399b2efcb002c48fa4b1a5b13bec9c9548f6ca9e646a692df`。
源目标均位于资料文本区并有 NUL terminator。测试保证 control/variant 的唯一差异
落在该四字节指针槽。

## 未通过的导航（不得升级 bank）

1. 从 `alternate-mission-selection.ss9` 输入 `A,Up,A,B,Up,A`，实际只推进到
   relocated alternate script 的第 13 次 dispatch，末 cursor `0x085F80A8`；profile
   scratch 全零。该简写路线不是人物概览入口。
2. 从 `alternate-equipment-page.ss9` 输入 `B,Up,A`，本次 browser replay 超时，
   没有生成 scratch 证据。
3. 直接载入 `alternate-character-overview.ss9` 会遇到已渲染缓存或 replay 挂起，
   即使截图存在也不能证明 ROM 表重新被读取。

因此 `data-table-a` 严格保持 `code_verified`。下一次只在取得可独立 replay、且位于
资料页 reader 之前的 checkpoint 后重跑 control/variant；通过条件是两边 hook 均命中、
`character_id=1`、entry=`0x085A1440`，指针分别为 `0x0859FA18/0x0859FDE8`，并且
可见资料文本区域变化而头像/等级/属性不变。

重要地址：table `0x5A143C`；selected-pointer consumer
`0x0808B19E..0x0808B1B2`；list builder `0x0808A6AC..0x0808A6F8`。
