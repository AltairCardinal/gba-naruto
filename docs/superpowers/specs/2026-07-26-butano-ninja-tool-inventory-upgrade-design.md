# Butano 忍具背包与强化架构设计

状态：领域、SRAM、实时战前入口和两进程 mGBA 验收已实现；商店/掉落/补给仍在边界外。

## 目标

把当前 campaign 的九格已装备 ID 扩展为可支撑后续关卡的库存架构，并实现原作已经由 ROM
写入链证明的忍具强化事务。该里程碑不复制原作截图，也不把 UI 游标状态放进领域模型。

## 方案比较

### 方案 A：把所有逻辑继续塞进 `battle_campaign.h`

改动少，但会让队伍、成长、库存、配方和交易继续耦合，战前 UI、掉落和商店只能依赖一个
越来越大的头文件。拒绝。

### 方案 B：UI 自己维护数量并在退出时写回

开发快，但取消、失败和存档中断会产生半提交；也无法让关卡奖励、商店和脚本共享规则。
拒绝。

### 方案 C：独立 inventory aggregate，campaign 只持有长期状态

采用本方案。`battle_campaign_inventory` 保存按 ID 直接索引的 94 个忍具数量和 18 个素材
数量；`ninja_tool_upgrade_service` 只接收 campaign、产物 ID 和可选装备角色，先在副本中
验证并执行，再一次替换 campaign。配方由 ROM 内容生成器产生，UI、脚本和奖励只调用服务。

## 架构

```text
ROM 0x08545BE4 (+A/+B/+C/+D)
            │ 生成
            ▼
generated_ninja_tool_recipe_content
            │
            ▼
ninja_tool_upgrade_service ── draft/validate/commit
       │                       │
       ├── tool quantities     ├── parent -1
       ├── material quantities ├── material -1
       └── equipped IDs        └── output +1 / optional replace
            │
            ▼
battle_campaign_state ── codec v2 ── 双槽 SRAM
```

### 内容真值

`tools/extract_skill_templates.py` 将 `+0x0B` 命名为 `required_material_id`，保留旧 JSON
字段只会继续传播错误，因此生成后的 bank 直接升级 schema，不保留含糊别名。动作结算结构
不增加配方字段；生成器输出独立的 `ninja_tool_upgrade_recipe` 数组，维持战斗动作与战前
强化的正交性。

### 库存

- 忍具数组大小 94，合法 ID 为 1–93，索引 0 必须为 0；
- 素材数组大小 18，合法 ID 为 1–17，索引 0 必须为 0；
- 数量使用 `uint8_t`，交易在加一前拒绝 255 溢出；
- 不依赖 `0x02023FD4` 的未闭合聚合语义；
- 战斗消费只清空长期装备引用，不自动改变持有数量，符合原作战斗样本中背包零差异的边界。

### 强化事务

输入产物 ID 后从生成配方读取父忍具和素材：

1. 拒绝 ID 0、越界 ID、无父项配方；
2. 拒绝父忍具或素材数量为 0；
3. 拒绝产物数量已为 255；
4. 可选装备角色为 0 时只更新背包；
5. 非零角色必须 active、ID 一致，并至少装备一个父忍具；
6. 在 campaign 副本内完成三项数量变化和首个匹配装备槽替换；
7. 全部成功才覆盖原 campaign。

失败返回稳定错误码，campaign 必须逐字节不变。

### 存档

save version 升到 2，payload 在 campaign header 与角色记录之间编码两个数量数组。当前项目
不承诺旧 Butano 原型存档兼容；version 1 明确返回 `unsupported_version`，损坏或旧档由既有
双槽/default 策略恢复。CRC、代际选择和写后读验证保持不变。

## 用户可见行为

战前“队伍/装备”入口最终读取同一 inventory aggregate：

- 显示已持有忍具、数量、父项、所需素材及库存；
- 可强化时 A 确认，成功后数量与已装备引用同步变化；
- 缺父项、缺素材、产物已满、角色无匹配装备时显示明确错误且不改变状态；
- B 返回，空库存显示“无可用忍具”；
- 存档只在成功交易后写入。

可见入口已经通过 `battle_preparation_flow` 调用该服务；renderer 只消费 snapshot，
不持有数量、不复制配方校验或交易逻辑。

## 测试

- Python：逐项验证 94 条配方，特别是 2=`1+素材3`、5=`1+素材1`、8=`1+素材2`；
- C++：背包强化成功、装备替换、缺父项、缺素材、产物溢出、非法角色、无匹配装备均验证
  原子性；
- codec：数量数组确定性 round-trip、坏 sentinel、坏 version、CRC、双槽恢复；
- 集成：战斗消费后持有数量不变，装备槽清空；强化后下一场 loader 得到产物 ID；
- ARM/mGBA：冷启动载入数量，执行战前交易后保存并由第二进程验证。

最终运行证据为
`artifacts/butano-ninja-tool-preparation-runtime-20260726-04/` 和
`artifacts/butano-ninja-tool-preparation-load-20260726-03/`。前者证明实时菜单
`67→68` 后进入 battle 41 部署，而非停留在黑色过渡帧；后者用独立零输入进程证明
装备、背包和素材从 version 2 SRAM 恢复。

## 边界

本设计不猜测商店价格、掉落表、素材奖励来源、自动补货或 `0x02023FD4` 聚合语义。它提供
这些系统以后必须复用的库存与原子交易底座。
