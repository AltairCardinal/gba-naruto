# 忍具装备分配与战斗消耗证据（2026-07-26）

## 结论

原作的忍具持有数量与角色装备槽是两个不同状态：

- `0x02023FD6..0x02024032` 记录忍具 ID 1–93 的持有数量；
- 角色记录 `+0xB0/+0xB1..` 记录该角色已占用槽数与忍具 ID；
- 装备/卸下本身只改变角色槽，不改变持有数量；
- 同一持有副本不能同时分配给多个角色；
- 战斗内消耗既清除战斗槽，也必须在回到 campaign 时扣除对应持有副本。

因此 Butano 版使用“持有量－全角色已分配量＝可装备量”的统一分配规则；战前换装、强化、
存档校验与战斗提交均消费这一规则，不能各自维护一套数量。

## 原 ROM 静态调用链

- `0x08090004`：从角色 `+0xB1` 起寻找首个空槽，写入忍具 ID，并递增 `+0xB0`；
- `0x0809004C`：从相同区域移除第一个匹配忍具，并递减 `+0xB0`；
- 两个例程均不修改 `0x02023FD6..0x02024032` 的持有数量；
- `0x0808FCCC`：枚举所有角色及其装备槽，证明持有副本的分配必须跨角色统计；
- `0x0808FBE0..0x0808FC0C`：另一条丢弃/消耗路径会清空装备并减少持有量，不能与普通卸下
  混为一谈；
- 忍具模板 `+0x0C/+0x0D` 由 `0x0808FC20` 作为角色白名单消费；
- 角色等级属性中的 `ninja_tool_capacity` 是装备数量上限；漩涡鸣人 1 级为 5。

2026-07-27 复核进一步锁定 `0x08090004` 的循环上界直接来自角色 `+0x06`
`ninja_tool_capacity`；每次成功只写一个 ID 并把 `+0xB0` 加一，未读取当前忍具的任何
容量成本。完整函数 `0x08090004..0x08090049` SHA-256 为
`faf70d7b38b82e37c823e4d42ece06d4d6086f69abc672b0b7fed7f621f4c9af`。
这排除了“不同忍具占不同容量”的假设。角色物理区仍只有 `+0xB1..+0xB9` 九格；target 10
属性修正中的 99 只是算术分支上限，不能扩大结构。

## Butano 领域边界

### 分配事务

`battle_campaign_equipment_service.h` 提供：

- `equip_campaign_ninja_tool`：验证角色、白名单、等级容量、全角色可用副本与首个空槽；
- `unequip_campaign_ninja_tool`：只清除指定非空槽；
- `valid_battle_campaign_equipment`：统一验证所有角色的白名单、容量和全局副本占用。

装备和卸下均先完成全部校验，失败时 campaign 逐字节不变。普通换装不修改持有数量。
`ninja_tool_upgrade_service` 复用同一分配统计，禁止 bag-only 强化消耗正在装备的唯一父忍具。

### 存档与冷启动

`battle_campaign_save` version 2 在编码和解码后都调用统一装备校验，因此下列非法状态不能进入
SRAM：

- 装备数超过等级容量；
- 角色装备白名单不允许的忍具；
- 所有角色对某忍具的占用数超过持有数；
- 未激活角色残留装备。

### 战斗提交

`battle_campaign_scene_progression` 在 `begin` 时保存参战队伍的初始装备多重集，在 `commit`
时比较最终多重集：

- 最终多于初始：拒绝为 `inventory_mismatch`；
- 初始减最终：视为战斗内实际消耗，并从 campaign 持有量扣除；
- 任一持有量不足：整笔提交失败且 campaign 不变；
- 成功时角色进度、最终装备和持有量一次提交。

这修复了旧实现“战斗只清槽但不扣背包，消耗品可无限重新装备”的架构缺口。

## TDD 与构建证据

- 装备服务 RED：
  `build/resource-guard/butano-campaign-equipment-red-20260726-01.json`
- 装备服务 GREEN：
  `build/resource-guard/butano-campaign-equipment-green-20260726-01.json`
- 存档非法分配 RED/GREEN：
  `build/resource-guard/butano-campaign-equipment-save-red-20260726-01.json` →
  `build/resource-guard/butano-campaign-equipment-save-green-20260726-01.json`
- 战前换装 flow RED/GREEN：
  `build/resource-guard/butano-campaign-equipment-preparation-red-20260726-01.json` →
  `build/resource-guard/butano-campaign-equipment-preparation-green-20260726-01.json`
- 实时场景 wiring RED/GREEN：
  `build/resource-guard/butano-campaign-equipment-scene-wiring-red-20260726-01.json` →
  `build/resource-guard/butano-campaign-equipment-scene-wiring-green-20260726-01.json`
- 战斗消耗回写 RED/GREEN：
  `build/resource-guard/butano-campaign-tool-consumption-red-20260726-01.json` →
  `build/resource-guard/butano-campaign-tool-consumption-green-20260726-01.json`
- 装备里程碑全量 host：87/87，
  `build/resource-guard/butano-campaign-equipment-full-host-20260726-02.json`；
  多角色战前集成加入后最终为 88/88，
  `build/resource-guard/butano-preparation-party-full-host-20260726-01.json`；
- ARM 从清洁对象构建及最终增量复核：
  `build/resource-guard/butano-campaign-equipment-arm-clean-build-20260726-01.json`、
  `build/resource-guard/butano-campaign-equipment-arm-build-20260726-02.json`

最终 ROM/ELF：

```text
ROM 580c41d69f2079ee2a5f7a8f690f0acfb9fb3d70b16fd5779ba92f4689f57159
ELF 5a85214b207532da0ef75f874c5a052cb5d5985ec2e65f0eb6c0cb371a0f1877
campaign telemetry 0x02005B88
battle telemetry   0x0201F64C
```

## mGBA 运行验收

正式换装路线：

- `artifacts/butano-ninja-tool-equipment-runtime-20260726-03/`
- 从默认 `67/11/37` 先卸下槽 0，再把未分配的忍具 1 装入首个空槽；
- SRAM 写后读：generation 1、slot 1、verified 1；
- campaign 遥测：`equipped[0]=1`、`owned[1]=1`、`owned[67]=1`、`last_error=0`；
- 进入第 41 战后继续完成部署、移动确认和动作菜单；
- frame 477 的正式动作目录为 `action_count=6`，选中项为
  `action_id=1 / kind=ninja_tool / tool_slot=0`。

这条路线证明战前换装不是菜单截图：同一 campaign 变化被保存、被战斗装载，并生成正式
resolver 使用的动作目录。截图为
`battle-action-catalog-after-equipment.png`。

独立零输入冷启动：

- `artifacts/butano-ninja-tool-equipment-load-20260726-02/`
- 新 mGBA 进程在 frame 1 从非默认 slot 1 恢复；
- 恢复值为 `tool0=1 / tool1=11 / tool2=37`，
  `owned1=1 / owned67=1 / owned68=0 / material6=1`。

菜单扩展后，强化路线也重新运行并通过：

- `artifacts/butano-ninja-tool-preparation-runtime-20260726-05/`
- `67→68`、素材 6 消耗、写后读和可见部署均保持成立。

第一次换装路线
`artifacts/butano-ninja-tool-equipment-runtime-20260726-01/` 已完成卸下和装备，但停在第 41
战脚本输入等待态；它被增加正式脚本等待处理的 `runtime-02` 取代，不作为验收证据。

## 多角色战前接线

`battle_preparation_flow` 从 campaign party 计算当前角色索引与队伍人数；只有队伍成员
可被载入。根菜单可用 L/R 循环切换角色，切换后装备、卸下和强化仍调用同一共享事务。
实时 renderer 显示 `CHARACTER` 与 `PARTY current/total`，不复制角色档案。

`test_battle_preparation_party_integration` 从三人 campaign 切到角色 2、装备唯一忍具 1，
随后依次经过 version 2 编码/解码、campaign scene policy 与 battle 1 variant 2 的正式
scenario loader。最终角色 1 无该忍具、角色 2 的 battle unit 槽 0 为 1、全局可用量为 0，
证明切换不是 UI 局部状态。TDD 与构建证据：

- flow RED/GREEN：
  `build/resource-guard/butano-preparation-party-switch-red-20260726-01.json` →
  `build/resource-guard/butano-preparation-party-switch-green-20260726-01.json`；
- L/R wiring RED/GREEN：
  `build/resource-guard/butano-preparation-party-scene-wiring-red-20260726-01.json` →
  `build/resource-guard/butano-preparation-party-scene-wiring-green-20260726-01.json`；
- loader 集成：
  `build/resource-guard/butano-preparation-party-integration-green-20260726-02.json`；
- ARM：
  `build/resource-guard/butano-preparation-party-arm-build-20260726-01.json`。

默认 battle 41 campaign 仍只有鸣人，不伪造额外剧情队员；最终 `runtime-03` 回放证明
新增 L/R 接线没有破坏单人换装、SRAM 与正式动作目录。三人实际页面由宿主的完整
campaign→save→loader 集成负责，不通过修改默认剧情阵容制造截图。

仓库内 `rom/base.sav` 与 `butano-sequel/butano-sequel.sav` 均保持：

```text
2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc
```

## 边界

- 已闭合手工装备、卸下、强化、战斗消耗、SRAM 与动作目录之间的状态一致性；
- 尚未闭合商店购买、掉落、战后补给价格和素材来源；
- 本里程碑不代表完整战斗 Goal 完成；回合状态机、全部动作的真实生产可达性及残余效果语义
  仍按路线图继续闭合。
