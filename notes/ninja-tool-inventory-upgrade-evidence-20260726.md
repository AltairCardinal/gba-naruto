# 忍具背包与强化事务证据（2026-07-26）

## 结论

原作把三类状态分开保存：

1. `0x02023FD6..0x02024032`：忍具 ID 1–93 的持有数量；
2. `0x02024034..0x02024044`：素材 ID 1–17 的持有数量；
3. 角色记录 `+0xB0/+0xB1..`：装备数量与装备忍具 ID。

强化不是 UI 局部效果，而是一笔领域事务。选择产物后，原作先验证父忍具和素材，再在同一
确认分支内执行：

- 父忍具数量 `-1`；
- 素材数量 `-1`；
- 产物忍具数量 `+1`；
- 若父忍具正在角色身上，卸下父项并装备产物。

这证明背包、配方、角色装备和战斗内可用槽必须是四个边界清楚但可原子提交的模型，不能继续
把九格战斗槽当成完整库存系统。

## 运行时单输入证据

输入检查点：

- `artifacts/runtime-checkpoints/alternate-equipment-page.ss9`
- SHA-256：
  `b410703bf0bcec6135286df17b5686d9200380a8e0ff2ca14ac35aa9fb786e02`
- 原 ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`

检查点显示真实可交互忍具页。库存区为：

```text
0x02023FD4 = 1  # 页面计数字段
0x02023FD5 = 0  # 空标记
0x02023FD6 = 1  # 忍具 1（十字手里剑）
0x02023FD7..0x02024044 = 0
```

从该状态只输入一次 A：

- 证据目录：
  `artifacts/original-equipment-single-input-20260726-a-01/`
- 输出状态 SHA-256：
  `c2791abb498c9b9f9786addfd7f2f1347e90847af1a659b8136829d3ac997264`
- guard：
  `build/resource-guard/original-equipment-single-input-20260726-a-01.json`
- guard 结果：`completed/0`、`degraded=false`、PGID/listener clean；
- 画面进入“缺少强化素材”反馈；
- 忍具与素材库存保持逐字节不变，证明失败路径不半提交。

第二次独立 A 只关闭反馈并回到同一列表：

- 证据目录：
  `artifacts/original-equipment-single-input-20260726-a2-01/`
- 输出状态 SHA-256：
  `84bb28feaa4b4bb2350e8807ac8c48ea0fd8a1426198dd51cfd414a00d1a4ade`
- guard：
  `build/resource-guard/original-equipment-single-input-20260726-a2-01.json`
- 库存仍无变化。

## 静态调用链

### 配方字段

忍具模板位于 `0x08545BE4`，94×16 字节。`0x0808FF24` 扫描 ID 1–93：

- `0x0808FF7C` 读取模板 `+0x0A`，与当前父忍具 ID 比较；
- `0x0808FF88` 读取模板 `+0x0B`，作为所需素材 ID；
- 模板 `+0x0C/+0x0D` 仍由 `0x0808FC20` 作为可选角色白名单消费。

字段模式也与素材身份一致。例如：

- 忍具 2：父项 1、素材 3（钢石）；
- 忍具 5：父项 1、素材 1（铁翼）；
- 忍具 8：父项 1、素材 2（铝罐）；
- 超级强化链常用素材 17（强化剂）。

因此旧名 `eligible_ninja_tool_id` 已被更强证据取代，正确语义是
`required_material_id`。

### 原子写入

强化页控制器为 `0x0808E954`。确认分支：

- `0x0808EBC0..0x0808EBCE`：
  `0x02024033 + material_id` 数量减一；
- `0x0808EBD0..0x0808EBE8`：
  `0x02023FD5 + parent_tool_id` 数量减一；
- `0x0808EBEA..0x0808EBFE`：
  `0x02023FD5 + output_tool_id` 数量加一；
- `0x0808EC14..0x0808EC38`：
  已装备时先调用 `0x0809004C` 卸下父忍具，再调用 `0x08090004` 装备产物。

`0x08090004` 从角色 `+0xB1` 起寻找首个空槽并递增 `+0xB0`；
`0x0809004C` 从同一区间移除首个匹配 ID 并递减 `+0xB0`。这条链是后续
Butano campaign 库存/强化服务的直接契约。

## 边界

- `0x02023FD4` 是字节计数字段，但现有样本不能区分“总件数”与“非空种类数”；实现不得
  用它作为交易真值，数量数组才是真值。
- 本证据闭合强化配方与交易，不闭合商店、掉落、战后补给价格或所有素材来源。
- 后续装备分配里程碑已补齐战斗提交：战斗内消耗会以开始/结束装备多重集的差值原子扣减
  campaign 持有量；证据见 `notes/ninja-tool-equipment-allocation-evidence-20260726.md`。

## Butano 实现与运行验收

本轮不是把原作页截图带入 ROM，而是把上述写入链实现成可被不同入口复用的领域边界：

- `battle_campaign_inventory` 分别保存 94 个忍具数量和 18 个素材数量；
- `ninja_tool_upgrade_recipes` 由 94 条原 ROM 模板生成，和战斗动作定义保持正交；
- `upgrade_ninja_tool` 在 campaign 副本中完成校验、三项数量变更和首个装备槽替换，全部
  成功后才提交；
- `battle_preparation_flow` 只组织菜单状态，实际确认仍调用同一强化服务；
- 同一实时战前页现已追加手工装备/卸下；它们复用全角色副本分配、等级容量和角色白名单，
  不另建数量真值；
- `battle_preparation_scene.cpp` 用实时文字、输入和 campaign 快照渲染，没有引用整屏
  `regular_bg_items`；
- `battle_campaign_save` version 2 在角色记录前编码两个数量数组，双槽 generation、
  CRC32 和写后读验证保持不变。

TDD 证据：

- 内容生成 Python：4/4；
- 强化事务：
  `build/resource-guard/butano-ninja-tool-inventory-cpp-red-20260726-01.json` →
  `build/resource-guard/butano-ninja-tool-inventory-cpp-green-20260726-01.json`；
- 存档：
  `build/resource-guard/butano-ninja-tool-inventory-save-red-20260726-01.json` →
  `build/resource-guard/butano-ninja-tool-inventory-save-green-20260726-01.json`；
- 战前 flow：
  `build/resource-guard/butano-battle-preparation-flow-red-20260726-01.json` →
  `build/resource-guard/butano-battle-preparation-flow-green-20260726-01.json`；
- 全量宿主：86/86，
  `build/resource-guard/butano-ninja-tool-preparation-full-host-20260726-01.json`；
- 清洁 ARM：
  `build/resource-guard/butano-ninja-tool-preparation-arm-clean-20260726-01.json`。

最终 ROM/ELF SHA-256：

```text
ROM 25db3b5b3c5085600f8f61c47e1eef7fccf1f70fbd45e42062c4881ec6e26dc3
ELF eb13a1f17b883d29d0b41358b1ee8d2f6f172f13634fe00a3fae9efdc22ecddf
```

静音 mGBA 的正式强化路线位于
`artifacts/butano-ninja-tool-preparation-runtime-20260726-04/`。它从默认装备
`67/11/37` 进入实时战前页，移动到第 3/4 条配方，显示
`TOOL 67 -> 68 / MATERIAL 6 OWNED 1`，确认后显示 `UPGRADE COMPLETE`。随后 campaign
遥测要求：

```text
save generation=1, slot=1, verified=1
equipped[0]=68
owned[67]=0, owned[68]=1
material[6]=0
last_error=0
```

路线不会在保存完成的黑色过渡帧签发；它继续等待 15 帧并要求
`battle_id=41 / phase=0xFFFFFFFE`，最终截图显示真实地图、单位、游标和部署文字。第二个
完全独立、零输入 mGBA 进程在
`artifacts/butano-ninja-tool-preparation-load-20260726-03/` 的 frame 1 从非默认
slot 1 读回同一装备、背包和素材状态，证明 version 2 冷启动恢复成立。

第一次自动路线
`artifacts/butano-ninja-tool-preparation-runtime-20260726-01/` 选择了按 ROM 顺序排在首位
的 `11→12`，正确得到 `MATERIAL MISSING` 且无保存；它是失败回滚证据，不是成功验收。
`runtime-20260726-03` 在部署遥测建立的同一帧过早截图得到黑色过渡帧，已由等待实际呈现帧
的 `runtime-20260726-04` 取代，不能解释为战斗黑屏。

仓库内 `rom/base.sav` 与 `butano-sequel/butano-sequel.sav` 均保持 SHA-256
`2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc`。
