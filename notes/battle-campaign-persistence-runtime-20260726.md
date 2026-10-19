# Butano 战斗战役档案与冷启动恢复（2026-07-26）

## 纠错目标

旧入口把三条 `character_progression_record` 按值塞进单场 scene。战斗中的升级和技能修炼
虽然由真实 controller 产生，但离开 scene 后没有长期所有者；换关、换队或冷启动都会回到
夹具。这仍不足以承载后续关卡。

本里程碑新增独立于表现层和单场 `BattleSession` 的 `battle_campaign_state`。截图只用于
人工查看，验收结论来自领域测试、显式存储协议、ELF 符号和两次独立 mGBA 进程的遥测。

## 领域所有权

- 档案固定保存 63 名角色，数组索引就是角色 ID；
- 每名角色保存等级、经验、修炼点、15 个主技能状态、24 个副技能状态和 9 个忍具 ID；
- 当前三人队伍只保存三个角色 ID，不复制另一份角色成长；
- scene 入场按 ID 投影三条 progression，战后结果、升级和修炼完成后再按 ID 原子合并；
- 队伍在 scene 生命周期中变化、角色 ID 不匹配或角色未激活时拒绝合并，档案零写；
- 当前战斗 HP、查克拉、坐标、行动账本、RNG、表现队列和 mGBA savestate 不进入档案。

`main` 的 campaign、checkpoint 和双槽工作区均位于 EWRAM。由于
`character_progression_record` 的默认等级是 1，两个 campaign 不能直接声明在全零
`.sbss`；最终实现使用对齐的 EWRAM BSS 原始存储并在启动时 placement-new，避免大型对象
落入 IWRAM 栈或带着非零初值进入错误 section。

## 显式 SRAM 协议

SRAM 使用两个 4096 字节槽。每槽带 `KBCS` magic、版本、payload 长度、32 位 generation
和 CRC32。63 条角色记录逐字段 little-endian 编码，不写 C++ padding 或原始 struct。
未使用字节必须为零；解码后还要验证角色、等级、技能状态、忍具 ID 和三人队伍领域约束。

保存总是写无效/较旧槽，随后从 SRAM 读回并完整解码比较；失败不破坏另一有效槽。两个槽
均无效时只接受调用方提供且通过领域验证的新游戏档案。generation 使用 32 位串行号比较，
测试覆盖 `0xFFFFFFFF → 1` 回绕，避免普通无符号比较误选旧槽。

当前格式是 Butano 续作内部的 version 1 自动档，不与原作 SRAM 二进制兼容。

## TDD 证据

RED 分别观察到：

1. campaign 领域头不存在；
2. save codec 头不存在；
3. controller/campaign bridge 不存在；
4. `main` 没有 SRAM load/save wiring；
5. ARM 构建拒绝把非全零 campaign 放入 `.sbss`；
6. generation 回绕测试错误选择 `0xFFFFFFFF` 旧槽。

GREEN 后：

- `test_battle_campaign`：63 角色初始化、三人投影、按 ID 合并、错误零写；
- `test_battle_campaign_save`：确定性 round-trip、magic/version/size/CRC、非法领域值、
  单槽恢复、双槽默认、目标槽选择和 generation 回绕；
- `test_battle_scene_results`：真实 battle 41 controller 产生
  `LV1→LV2 / EXP25 / TP1→0 / action 8 0→1`，再合并回 campaign；
- 全量 80 个宿主 C++ 程序通过，guard：
  `build/resource-guard/butano-campaign-full-host-20260726-02.json`，
  `exit_code=0`、`degraded=false`、峰值 RSS `136.89453125 MiB`；
- 相关 71 项 Python wiring/脚本/阶段/文档测试通过。

## ARM 布局与构建

最终源码先通过清洁构建
`build/resource-guard/butano-campaign-arm-clean-build-20260726-04.json`，随后只重编译
消除既有 menu pointer 编译器误告警的场景源，最终 guard 为
`build/resource-guard/butano-campaign-arm-build-20260726-06.json`，
`exit_code=0`、`degraded=false`、峰值 RSS `20.6328125 MiB`，最终编译日志无 warning。

本页最初 progression-only 构建的 ELF 符号（后续装备遥测扩展不沿用这些地址/大小）：

| 地址 | 大小 | 符号 |
|---|---:|---|
| `0x020010AC` | `0x2000` | 双 SRAM 槽工作区 |
| `0x020030AC` | `0x11C4` | campaign checkpoint 原始存储 |
| `0x02004270` | `0x11C4` | 当前 campaign 原始存储 |
| `0x02005434` | `0x30` | campaign load/save 遥测 |
| `0x0201ECC0` | `0x164` | battle runtime 遥测 |

最终 ROM 为 `9,797,768` 字节，SHA-256：
`6d8961d5c849ebeb049f3907728b08b95c12d4d439340a86b5d6ccf93f89339c`。
ELF SHA-256：
`0cab94051f2030f972525b3faaf24beecd5cce0823c754b058f7f887db54aec3`。

## 两进程冷启动验收

证据目录：
`artifacts/butano-campaign-persistence-20260726-03/`。staged ROM 与最终 ROM 哈希相同，
只在该目录旁创建 `staged.sav`，没有读取或写入 `rom/base.sav`。

第一次独立 mGBA 进程由共享 scenario 41 状态驱动脚本完成部署、两轮行动、动作 5、结果、
升级和 action 8 修炼，然后退出 scene 触发保存：

- frame 470，battle 41，round 2，phase complete；
- 总经验 175，action 8 `0→1`，修炼点 `1→0`；
- 新档 load generation 0 / default 1；
- save generation 1 / slot 1 / read-back verified 1；
- campaign 为 Naruto `LV2 / EXP25 / TP0 / action8 LV1`；
- controller/player/save error 均为 0，SP `0x03005368`。

审计：
`artifacts/butano-campaign-persistence-20260726-03/save/audit.json`。

完全关闭该进程后，第二个 mGBA 进程复用同一个 `.sav`。加载脚本没有调用
`addKey`/`clearKey`，在 frame 1 直接观察：

- load generation 1 / slot 1 / default 0；
- 本进程尚未保存，save generation 0 / verified 0；
- Naruto 仍为 `LV2 / EXP25 / TP0 / action8 LV1`；
- error 0。

审计：
`artifacts/butano-campaign-persistence-20260726-03/load/audit.json`。
32 KiB SAV SHA-256 在第二次运行后仍为
`be5f1bd401d2ec93db32cc225f9e13b16963eea8524e7da9c2c796c4680ee5ac`。

两次运行均经 `tools/run_guarded.py` 和同一 heavy lock 执行，completion trigger 为
success marker，未出现 mGBA crash。运行使用 `mute=1`，只验收领域、流程与持久化，
不签发音频听感。

## 2026-07-26 装备消费回写跟进

本页以上内容记录最初只合并成长记录的里程碑。后续实现已把 controller 的九格最终装备与
成长记录一起原子提交，并由相同双槽 SRAM 协议保存。隔离两进程路线证明默认装备
`67/11/37` 中的忍具 37 在正式 resolver 消费后保存为 `67/11/0`，新进程零输入仍读回 0。
完整 TDD、运行时遥测、当前 ROM/ELF/SAV 哈希及未部署队员保留规则见
`notes/battle-campaign-tool-writeback-runtime-20260726.md`。

## 当前边界

该里程碑修复的是战斗角色成长没有跨场景所有者的问题，不代表完整战斗 Goal 已完成：

- 九格已装备忍具的战斗消费与 SRAM 回写已经闭合；背包数量、强化、补给、战前装备 UI 和
  章节背包来源仍未接线；
- 没有世界地图、章节解锁、手动存档 UI、原作存档兼容或战斗中途存档；
- 副技能修炼资格和玩家页面仍未闭合；
- 剩余动作真实生产可达性、未知效果/状态语义、专属表现与非静音音频仍要继续验证；
- 自动从 battle 41 接到 legacy scenario 43 只是当前开发入口，不是最终章节流程。
