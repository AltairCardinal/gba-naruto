# 自然术列表技能详情闭环（2026-07-13）

> 2026-07-23 身份纠错：该自然 high-bit 分支是在“忍者组合拳”页面下选择十字手里剑，row 1 的 `6×3 / 距离3 / 90%` 与攻略 Ninja-Tools 项完全一致。它证明的是 `0x545BE4` **忍具数值模板**及忍具详情链，不是角色主动术模板；角色主动动作是 `0x545458` 的 87×16 字节同 ID 表。下文地址、A/B 和字段映射仍有效，但所有 `skill` 实体名应按忍具理解。

## 自然入口

无需寻找非教学战斗。人物“术列表”控制器 `0x08078E38` 在
`0x0807902A`、`0x08079076` 把真实 skill ID 与 `0x80` 合并，随后分别从
`0x08079036`、`0x0807907E` 调 `0x080708BC`。高位分支在 `0x08070906` 调
skills initializer `0x0806D910`，因此这是自然 high-bit action，不是旧的强制诊断。

固化 checkpoint `artifacts/runtime-checkpoints/skill-list-pre-controller.ss9` 位于
“队伍·装备 → 鸣人”子菜单，initializer scratch 全零。从该状态输入 `Down,A` 打开
“术列表”。control 命中一次 skill ID 1，destination `0x02026B80`，输出前 16 字节：

`05 01 01 02 06 03 5A 83 01 00 00 00 00 00 00 00`

它与 ROM row `0x545BF4` 经已证明的 initializer 映射一致。页面自然显示攻击力
`6×3`、距离 `3`、直线、范围 `1`、成功率 `90%`。

## 单字节 A/B

variant 只改 skill 1 source `+4`，即 file `0x545BF8: 6→7`。同一路线仍命中
skill ID 1，runtime destination `+4` 同步变 7，页面攻击力变为 `7×3`；距离、形状、
范围和成功率均未变。游戏画面内仅 192 / 154080 像素变化，绝对边界框
`(657,110)..(669,132)` 只覆盖攻击力首位数字。

由同一自然详情行和 2026-07-23 多行交叉可建立保守字段映射：`+4` 攻击力，`+5` 打击次数，`+6` 成功率百分比，
`+7` 距离/直线形状的 packed 字段（ninja-tool 1 的 `0x83` 显示 `距离3 / 直`），`+8`
范围。`+2/+3/+9` 仍不命名；不能因本次样本推断它们。

不同 ROM variant 载入 checkpoint 时应先零输入重放并导出一个临时 normalized state，
再输入 `Down,A`，避免把活跃 UI 转场边沿跨 ROM 携带。该步骤不产生 skill hit。

因此 `skills` 升级为 `runtime_verified`。紧凑证据见
`artifacts/runtime-checkpoints/skill-detail-runtime-evidence.json`。
