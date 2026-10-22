# Butano 战后主技能修炼运行时闭环（2026-07-26）

> 本文记录最初的主动技训练里程碑。其“副技能另行实现”边界已由
> `notes/battle-unified-training-runtime-20260726.md` 取代；当前生产架构使用统一
> `battle_training_flow`，本文保留作为历史 RED/GREEN 与 battle 41 action 8 证据。

## 结论

主技能修炼已从“后台函数可调用”接入玩家可见的战后流程：

```text
战斗胜利
  → 结果经验确认
  → 等级结算 / LEVEL UP
  → TRAINING
  → 完整主技能槽目录
  → train_primary_action
  → 修炼点与技能等级原子提交
  → COMPLETE
```

页面不是截图或脚本直接改数据。controller 只持有 `battle_primary_training_flow` 的选择状态；
角色等级、修炼点和 15 个主技能槽继续由 `character_progression_record` 唯一拥有。A 键的
唯一写入口是既有 `train_primary_action`，renderer 只读取独立紧凑快照。

## 玩家可见行为

- 战后升级页确认后，存在修炼点时进入 `TRAINING`。
- 页面显示角色、剩余 `TP`、当前技能在完整非空主槽目录中的序号、技能名及
  `LOCK/NEW/LV/MAX/FIXED` 状态。
- 上下切换技能，L/R 切换仍有修炼点的角色，A 投入一点，B 结束分配。
- 成功后同一页立即显示技能等级增加与 TP 减少。
- 锁定、满级、不可成长、无点数和空目录不写角色数据；稳定 error code 保留在快照和遥测。

## 原 ROM 依据

本实现继续使用
`notes/battle-action-progression-20260726.json` 已哈希绑定的控制流：

- `0x0808E16E → 0x08093698 → 0x0809337C`：升级后的训练列表入口；
- `0x08093670 → 0x08093070`：所选训练行确认；
- `0x08093160`：角色模板 `+0xBA` 修炼点减一；
- `0x080931AA`：所选主技能槽等级加一；
- `0x0806FDF2..0x0806FE3A`：只有技能状态 `1..254` 进入正式战斗目录。

因此等级达到阈值只负责 `0xFF→0`，训练页负责 `0→1→2→3`，战斗 catalog 继续只读取
提交后的持久状态。

## TDD 证据

RED：

1. `test_battle_primary_training_flow` 首次因头文件不存在而编译失败；
2. `test_battle_scene_results` 首次因 controller 没有 `training` phase/snapshot 而失败；
3. 85 个非空关卡变体测试首次在 battle 22 遇到未知 phase 16；
4. runtime wiring 测试首次因无 `TRAINING` 文本与遥测而失败；
5. mGBA 脚本契约首次因无 training phase、offset 和训练截图而失败。

GREEN：

- flow 覆盖完整非空目录、上下循环、角色循环、`0→1`、无点、满级、锁定和空 roster；
- battle 41 controller 集成覆盖
  `result → level_up → training → complete` 与 action 8 `0→1 / TP 1→0`；
- 85 个非空 `(battle_id, variant)` 首轮通用流程继续通过；
- battle scene snapshot 仍不超过 1,120 字节。训练快照独立读取，不复制 15 项目录进每帧
  战斗 snapshot；
- 遥测从 336 扩展到 356 字节，旧字段 `0..332` 偏移全部保持不变，新字段只追加在尾部。

## ARM 与 mGBA 证据

- 全量宿主 C++：
  `build/resource-guard/butano-training-full-host-20260726-02.json`，
  exit 0、无降级、峰值 144.33984375 MiB。
- 固定 devkitARM：
  `build/resource-guard/butano-training-arm-build-20260726-03.json`，
  exit 0、无降级。
- ROM SHA-256：
  `bacd5d68bf80988974c893185750dd927a9458643f3a32bc8b874ab926945cff`。
- ELF SHA-256：
  `4afe7fe9d4d08ae4abd73a95544a2ed5f4afdecd2d5d643c93a5b48bc28692c3`。
- exact ELF 遥测地址：`0x0201A848`。
- 静音 mGBA：
  `artifacts/butano-training-runtime-20260726-04/audit.json`。

最终实机路线在 frame 460 到达 phase 16 `COMPLETE`，结果为 mission 100、battle 50、
round bonus 25、总经验 175、`LV1→LV2`、剩余经验 25、HP 成长 14；训练 action 8
为 `0→1`，修炼点 `1→0`，控制器/玩家错误均为 0，SP 为 `0x03006804`。

前三次运行保留为诊断证据：

- `...-01`：旧脚本在过期的 y=6 空格确认目标；
- `...-02`：进度遥测证明 target phase 返回 `invalid_target`；
- `...-03`：脚本找到 y=4 敌人，但 actor 尚在 y=7，距离门正确拒绝。

最终脚本先把 actor 合法移动到 y=5，再通过 cursor-unit 遥测寻找真实活动敌人。修正的是
自动化假设，没有放宽游戏目标或距离规则。

## 证据边界纠正

`0x0806A8C0` 不是缺失的“束缚行动资格消费者”。它检查状态
`0x15/0x11/0x0F/0x3F/0x3E/0x3D`，选择 `0x10/0x20/0x30/0x40`，再通过
`0x0806A790` 写原 ROM `unit+0xC0` 的 `0x70` 位域。该字段是反应/表现状态；
effect `0x3F` 的持续生命周期由活动状态槽承担。Butano 不增加无证据的禁行规则。

## 未完成边界

- progression 尚未序列化到 SRAM，跨 ROM 重启不持久；
- 副技能 24 槽的玩家修炼资格和全部消费者仍未闭合；
- 页面使用通用文字/战场背景，原作专属面板、光标动画和音频未恢复；
- 本次 mGBA 使用 `mute=1`，不能签发音频撕裂修复；
- 完整章节导航、专属技能表现和所有关卡完整胜负仍未完成。
