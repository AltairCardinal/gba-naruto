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

### skills `0x545BE4`

`tools/build_skill_relation_runtime_probe.py` 包装 `0x0808E4A4 → 0x0808FF24`，
记录 selected slot/skill、row 3 `+A/+B`、post candidate count 和首个 candidate flag；
variant 只改 row 3 `+A: 2→0`。普通“忍者组合拳”详情、目标选择和无效目标提示均
零命中，证明该调用不是普通技能详情 reader，而是组合/候选关系子链。不得用它把
整个 skills bank 升级；下一步需触发组合候选 UI 或改 hook 到实际技能执行初始化器。

### data-table-b `0x5A2034`

`tools/build_battle_message_runtime_probe.py` hook `0x080985E2`，捕获 zero-based
message ID、表项、指针和目标前 16 bytes，并支持同表四字节指针 A/B。空目标产生的
“请选择……范围内”提示未命中，说明该提示属于另一套 UI 文本；该 bank 继续保持
`code_verified`。下一步应完成有效攻击/技能，让 battle-effect message object 真正
创建后复用该探针。

## 下一步优先级

1. 从 actionable checkpoint 完成一次有效技能/攻击，优先同时观察 battle-message、
   resource descriptor 和 skill initializer；
2. 命中后先锁定真实 ID，再生成唯一四字节 pointer/palette 或单字节 skill A/B；
3. 只有 live selector、ROM 目标一致和可见/行为差异同时成立才升级 bank。

重要地址：actionable checkpoint；skill relation call `0x0808E4A4`；battle message
selector `0x080985E2`；resource descriptor call `0x0807B256`。
