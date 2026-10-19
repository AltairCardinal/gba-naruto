# Butano 技能进度运行时实施记录

## 目标

把原作角色技能从“按等级拼出的菜单”改成可持久化、可修炼、可进入正式战斗结算的领域链，
并以同技能不同等级的 resolver 结果和 ARM 多场路线验收。

## 复用判断

1. 复用 `UnitDefinition` 的 15+24 四字节槽、既有角色 progression、scenario loader、
   action catalog/browser/resolver，不建立第二套技能表。
2. 在 `CharacterProgressionRecord` 与 `BattleUnitInstance` 上补充槽状态，供原链共享；
   不在 renderer、scenario 或 AI 中推导技能。
3. 等级结算追加解锁同步；修炼是独立领域命令；战斗目录继续是唯一入口。
4. 不能复用旧“角色等级达到阈值即出现技能”的原因是它违反 ROM 的 `0xFF→0→1`
   状态机，也让 20 个初始状态 0 的动作永久不可达。

## TDD 闭环

- [x] RED：缺少 `battle_action_progression.h`，技能状态/修炼测试无法编译。
- [x] GREEN：初始化、解锁、扣点、三级上限、主/副槽持久状态进入 progression。
- [x] RED：Kiba action 23 修炼后仍不能进入正式目录。
- [x] GREEN：progression→scenario loader→unit→catalog 可达。
- [x] GREEN：鸣人 action 5 的 LV1/LV3 通过正式 resolver 得到不同伤害。
- [x] RED：遥测缺少 `selected_action_level`，ARM 路线无法证明实际选择等级。
- [x] GREEN：UI 显示 `LV`，遥测末尾追加等级且保留旧字段偏移。
- [x] RED：场景切换时旧 sprite tile 未在新头像分配前回收。
- [x] GREEN：清句柄后提交 core update，再创建新场景 sprite。
- [x] RED：资源、AI 与防御收尾在外层事务内再次复制完整 session，ARM SP 覆盖
  Maxmod/IWRAM。
- [x] GREEN：encounter 只建立一次 EWRAM 候选，资源、技能、效果与防御内层全部
  in-place，失败丢弃候选。

## 验证

- 77 个宿主 C++ 程序全量通过：
  `/tmp/action-progression-full-host-20260726-07.json`；
- 46 个定向 Python 测试通过，1 个环境条件 skip；
- 固定 devkitARM Docker 构建通过：
  `/tmp/action-progression-arm-build-20260726-09.json`；
- 静音 mGBA 完成三场切换和 battle 9 round 2：
  `artifacts/butano-action-progression-runtime-20260726-09/`；
- `rom/base.sav` SHA-256 保持
  `2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc`。

## 未完成边界

- 玩家可见修炼页面和章节存档序列化；
- 副技能修炼资格与全部消费者；
- 技能专属动画/音频；
- AI 对组合动作 9 的完整策略；
- 非静音主观音频验收。
