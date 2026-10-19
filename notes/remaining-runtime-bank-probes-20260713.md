# Remaining runtime-bank probes（2026-07-13）

## 新的真实战斗边界

修复 runtime driver 的隐式 canvas 点击后，旧的四键 prebattle 路线少了明确确认。
从 `/tmp/primary-prebattle.ss9` 实际需要显式推进“开始任务？”、Start overlay 和
伊鲁卡教学对白，才能进入可操作战斗。最终固化的
`artifacts/runtime-checkpoints/actionable-move-grid.ss9` 已在原始 `rom/base.gba`
上零输入独立重放：battle ID 41、map `36×44` / grid `9×22`，slot 1 Naruto
`(4,10)`、slot 2 Iruka `(4,4)`，strict arrival 四项全过。

checkpoint SHA-256：
`4821a3a6694d32871a23bbea6a93ba1724663cb4a3c6e5f691d4fd48a5635fac`。
紧凑证据：`artifacts/runtime-checkpoints/actionable-battle-runtime-evidence.json`。

该 checkpoint 位于忍术目标选择网格；右上角 `SELECT` 打开人物信息，并非取消。
在空目标上 A/B 都会显示“请选择……范围内”提示。中间状态必须零输入重放后再保存，
否则 UI 结果边沿会被固化，下一键会同时消费旧确认。

## 已完成的专属探针与负证据

### resource-pointers `0x596F0C`

`tools/build_resource_pointer_runtime_probe.py` 包装专属 call site `0x0807B256`，
捕获 descriptor ID、表项地址和四个资源指针，并支持只把命中记录 `+0x0C`
palette source 从 `0x08170F90` 安全移到 `0x08170F98`。control 经过真实入场、
Start overlay、教学对白和目标选择仍为零命中。因此该表不属于入场 HUD/教学加载，
继续保持 `code_verified`；下一次应在实际状态/overlay 动作边界使用此探针。

自然 high-bit skill 入口闭合后又从
`artifacts/runtime-checkpoints/skill-list-pre-controller.ss9` 打开鸣人的“术列表”。
页面确实命中 skills initializer 并完整显示技能详情，但 resource-pointer scratch
`0x0203FE40` 仍为 48 字节全零。因此这五条 descriptor 也不属于人物术列表/详情面板
创建链；后续只在实际战斗 overlay/effect 对象阶段继续追踪，避免重复探测静态详情 UI。

### skills `0x545BE4`

`tools/build_skill_relation_runtime_probe.py` 包装 `0x0808E4A4 → 0x0808FF24`，
记录 selected slot/skill、row 3 `+A/+B`、post candidate count 和首个 candidate flag；
variant 只改 row 3 `+A: 2→0`。普通“忍者组合拳”详情、目标选择和无效目标提示均
零命中，证明该调用不是普通技能详情 reader，而是组合/候选关系子链。不得用它把
整个 skills bank 升级；下一步需触发组合候选 UI 或改 hook 到实际技能执行初始化器。

后续 writer 追踪已定位通用战斗动作详情渲染器 `0x080708BC`。它以 action ID 高位
明确分流：教程“忍者组合拳”的低位 ID 2 调 `0x0806D85C`，不是 skills；只有
`0x80|skill_id` 才在 `0x08070906` 调 `0x0806D910`。强制 ID 2 诊断 A/B 已证明
source/runtime `+4:6→7`，但由于不是自然选择且无稳定可见差异，仍不升级。
详见 `notes/battle-action-detail-renderer-20260713.md`。

为排除“只是目标距离过远”，`tools/build_adjacent_tutorial_runtime_probe.py` 只改
battle 41 伊鲁卡 formation record `0x58A80C`。敌对相邻 `(5,10)` 时，伊鲁卡能被
橙色范围光标选中，但教程拒绝直接攻击，低位 effect 也不在该单位上确认；同阵营相邻
则在提交移动后直接触发教程对白，skill-relation scratch 仍 48 字节全零。因此
“邻接即可进入组合链”也被证伪，不能把该对白当作技能执行。紧凑证据见
`artifacts/runtime-checkpoints/adjacent-tutorial-action-evidence.json`。

### data-table-b `0x5A2034`

`tools/build_battle_message_runtime_probe.py` hook `0x080985E2`，捕获 zero-based
message ID、表项、指针和目标前 16 bytes，并支持同表四字节指针 A/B。空目标产生的
“请选择……范围内”提示未命中，说明该提示属于另一套 UI 文本；该 bank 继续保持
`code_verified`。下一步应完成有效攻击/技能，让 battle-effect message object 真正
创建后复用该探针。

## 下一步优先级

1. 寻找自然产生 `0x80|skill_id` 的非教程战斗或组合候选 UI，并以
   `0x08070906` 专属探针捕获真实 skill ID；
2. 从 actionable checkpoint 完成一次有效攻击，继续观察 battle-message 与
   resource descriptor；
3. 命中后先锁定真实 ID，再生成唯一四字节 pointer/palette 或单字节 skill A/B；
4. 只有 live selector、ROM 目标一致和可见/行为差异同时成立才升级 bank。

重要地址：actionable checkpoint；skill relation call `0x0808E4A4`；battle message
selector `0x080985E2`；resource descriptor call `0x0807B256`。
