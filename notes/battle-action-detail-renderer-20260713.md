# 战斗动作详情渲染链（2026-07-13）

## 结论

从稳定的第二回合指令菜单进入“术・忍具”后，详情页渲染器已定位到
`0x080708BC`。它先检查动作 ID：

- `action_id & 0x80 == 0`：以低 7 位作为 battle effect ID，调用
  `0x0806D85C`；
- `action_id & 0x80 != 0`：清除高位后作为 skill ID，在
  `0x08070906` 调用 `0x0806D910`。

教程里的“忍者组合拳”实际传入低位 `effect_id=2`，不是 `skill_id=2`。这解释了
此前技能 initializer 和 relation 探针在同一页面全部零命中。该纠正是严格的负证据：
`skills` 继续保持 `code_verified`，不得用这个低位动作详情页升级。

## 可复现追踪方法

本轮新增三层通用调用点追踪器：

- `tools/build_tilemap_writer_trace_probe.py`：包装 `0x08066D14` 的全部 75 个
  已校验 BL，记录首末调用者和 panel ID；
- `tools/build_numeric_writer_trace_probe.py`：包装 `0x08066A48` 的全部 101 个
  已校验 BL，记录最多 32 个调用者和数值；
- `tools/build_text_writer_trace_probe.py`：在 SHA-1 校验后的基础 ROM 中发现并包装
  `0x08066758` 的 256 个 BL，记录调用者、文本指针和前四字节。

真实页面的结果为：

- tilemap writer 4 次：首个 `0x08066E92 / panel 4`，末个
  `0x0806ED9E / panel 0`；
- numeric writer 2 次：`0x080710AA → 80`、`0x080710C4 → 5`，两者是底部
  体力/查克拉 HUD，不是右侧详情数字；
- text writer 10 次，实际调用集中在 `0x08070922..0x08071222`，从而把详情页
  主渲染函数锁定到 `0x080708BC`。

这套“公共 writer → 实际 caller → 上游 reader”方法可复用于剩余 UI 字段，不需要
猜测屏幕文字属于哪张 ROM 表。

## 专属 skill 分支探针

`tools/build_skill_detail_runtime_probe.py` 包装唯一详情调用点
`0x08070906 → 0x0806D910`，记录 skill ID、level/context、目标指针和返回后的
16 字节 runtime block。它还提供明确标记的 `--force-skill-id` 诊断选项，只把
`0x08071104` 的本次详情动作 ID 改为 `0x80|skill_id`。

强制 ID 2 的 control 命中一次：

```text
skill_id=2
level/context=0x02024294
destination=0x02026B80
output=05 01 01 02 06 03 5A 83 02 00 00 00 00 00 00 00
```

只改 ROM record 2 `+4: 6→7` 后，输出只在对应 runtime `+4` 变为 7：

```text
variant=05 01 01 02 07 03 5A 83 02 00 00 00 00 00 00 00
```

这个 A/B 证明详情调用点确实可消费 skills row，并再次确认 source `+4 → runtime +4`。
但它由强制诊断参数触发，且最终截图只出现指令菜单、没有稳定可见字段差异，所以不满足
自然运行时升级门槛。

## 边界与下一步

下一条有效路径必须让游戏自然产生 `0x80|skill_id` 动作：优先寻找非教程战斗、组合
候选 UI，或从角色真实技能选择页进入。接受证据必须同时包含未强制的
`0x08070906` 命中、被选 skill ID、ROM row、runtime 输出，以及可见或行为 A/B。

重要地址：详情渲染器 `0x080708BC`；effect 分支 `0x080708F0`；skills 分支
`0x08070906`；动作 ID reader `0x08071104`；详情 runtime block `0x02026B80`。
