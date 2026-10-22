# Butano 主动技/被动技统一训练运行时（2026-07-26）

## 纠错

此前 Butano 已有 15 个主动技与 24 个被动技状态，也能把被动状态保存到 campaign/SRAM 并
装载进战斗单位，但战后训练 flow 只列出主动技并只调用 `train_primary_action`。这会让
被动技永远无法通过玩家流程从 0 变成 1，属于成长架构缺口。

原 ROM 的 `0x08093070` 是统一训练提交函数：

- `0x08093160` 统一递减角色模板 `+0xBA` 的训练点；
- row `+4 == 4` 时，`0x08093170..0x08093188` 写
  `template + 0x51 + slot*4`，即 24 个 secondary/passive 槽；
- 其他训练行由 `0x080931A0..0x080931B4` 写
  `template + 0x15 + slot*4`，即 15 个 primary/action 槽；
- type 4 row 的 `+6` 是 45 项被动成长定义 ID，`+7` 是角色 secondary 槽索引。

自然场景 42 已观察到鸣人的 8 个主动行之后，第一个 type 4 行位于 index 8。因此 Butano
目录按角色模板顺序先列全部非空 primary 槽，再列全部非空 secondary 槽。

## 实现

- `battle_training_flow` 取代主动技专用 flow；条目显式带
  `primary_action / secondary_passive` 类型。
- `train_secondary_passive` 是被动训练唯一写入口，验证角色、槽、`0xFF/0/1..3` 状态、
  训练点和 45 项 ROM 成长定义。失败时 progression 不变。
- controller 仍只持有 progression roster 和 flow；renderer 只读 snapshot，不扣点、不写等级。
- 训练成功后沿既有
  `progression.secondary_action_levels → scenario loader → unit.passives`
  链进入后续战斗，并继续由共享 passive query/consumer 使用。
- 未二次校字的被动名称显示为 `PASSIVE #ID`，不把猜测文本写入正式身份表。

## TDD 与集成证据

RED：

1. progression analyzer 缺少 type 4、`+0x51` 与 secondary 写入契约；
2. C++ 没有 `train_secondary_passive`；
3. 没有 `battle_training_flow.h`；
4. runtime telemetry 没有 entry kind，UI 只能按主动动作渲染；
5. mGBA 脚本不能证明统一目录中的 secondary 条目可达。

GREEN：

- 角色 3、level 5 的 secondary slot 13 / passive 15 从 `0→1`，TP `1→0`；
- 失败的无效槽、锁定、无点数和满级事务保持角色记录不变；
- 装载后单位 slot 13 为 passive 15 / level 1，
  `query(target_type=0x14)` 返回 ROM 物化值 30；
- 鸣人 level 9 的统一目录为 8 个主动条目后接 24 个被动条目，index 8 为
  secondary slot 0 / passive 1；
- battle 41 controller 可从 action 8 继续向下到 secondary 条目；锁定确认零写。

全量宿主 C++ guard：
`build/resource-guard/butano-unified-training-full-host-20260726-02.json`，
`exit_code=0`、`degraded=false`、峰值 RSS `140.28125 MiB`。

相关 Python 20 项以及新增 Lua 契约 4 项通过。ARM 第一次清洁构建因 GCC
`-Wchanges-meaning` 拒绝字段名 `passive_id passive_id`；字段改名为
`trained_passive_id` 后，第二次清洁构建通过：
`build/resource-guard/butano-unified-training-arm-build-20260726-02.json`，
峰值 RSS `139.60546875 MiB`。

最终 ROM SHA-256：
`918831d622494a7a8f1b2f68b0c385c8048136cbd8b171f0c4feae89492bcc93`。
ELF SHA-256：
`5270cdb068ce6d293343572fd26225c8ff3d8a9048ce9c27b5b25528f4471f87`。
`rom/base.sav` SHA-256 仍为
`2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc`。

## mGBA 运行时

exact ELF 符号：

- `konoha_battle_runtime_telemetry = 0x0201ECC4`；
- `konoha_battle_campaign_runtime_telemetry = 0x02005438`。

最终静音运行：
`artifacts/butano-unified-training-runtime-20260726-02/`。

审计在 frame 478 完成 battle 41：

- round 2、phase complete；
- 总经验 175、`LV1→LV2`、剩余经验 25、HP 成长 14；
- action 8 `0→1`、TP `1→0`；
- 最终动作 ID 5；
- controller/player error 均为 0。

脚本在退出前继续向下移动到第一个 secondary 条目，遥测确认
`entry_kind=secondary_passive / definition_id=1 / level=0xFF`，截图为
`training-passive.png`。这只证明统一目录和只读表现可达；该等级没有合法可训练被动，
因此没有伪造一次自然被动训练。

运行使用 `mute=1`，不签发非静音音质。45 项被动名称二次校字、全部 consumer、训练专属
动画/音频和达到自然被动解锁等级的章节路线仍由完整战斗 Goal 后续闭合。
