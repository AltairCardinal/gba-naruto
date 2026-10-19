# 战斗效果高位 follow-up（2026-07-26）

## 结论

本里程碑恢复的是 queued battle event 的真实后续状态链，不是按技能名称显示一段“中毒”
文字：

- 有效对手命中后的 effect bit `0x80` 建立一回合状态 `0x3F`，并写 reaction state
  `0x30`；
- bit `0x40` 原子建立三回合 `0x1F/0x21/0x23`，每条固定为 10%，再按状态槽顺序重算
  攻击、防御和敏捷；
- miss 不建立状态；状态容量不足时不扣资源、不消耗忍具、不保留部分状态，也不推进 RNG；
- 原 ROM 在主效果 handler 返回后不检查目标 HP/active，致死命中同样建立 follow-up；
- 普通攻击忍具、毒烟防御反应和定时 type 1 对象到期共用同一 resolver policy。

这使忍具 11–13、25–27、43–45、70–72 的 `0x40` 不再被忽略，也使主动动作
8、10、60 的 `0x80` 不再退化成纯伤害。

## 原 ROM 证据

- ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- follow-up helper：`0x080768D8..0x08076A26`
- helper SHA-256：
  `eea2a918515d8c367ac0f464c5a33092cd1da83963708282e93dba020bef84b4`
- 队列门：`0x0807764E..0x08077670`
- 队列门 SHA-256：
  `8c0638a3f11746e5ec72fed04f9edfc1635c20ef17e7de5f777b91ee46c92f14`
- 调用点：`0x0807766C → 0x080768D8`
- 条件：`sp+0x18 != 0` 且 `(event+0x0E & 0x0700) == 0x0200`
- `0x0807764E..0x0807766C` 从 handler 返回门到 helper 调用之间没有读取 HP/active
  或按存活状态分支，因此 follow-up 明确发生在致死结算之后；
- 状态 upsert 调用点：
  `0x0807690A/0x08076960/0x080769A4/0x080769E8 → 0x0806C204`
- reaction state 调用点：`0x08076940 → 0x0806A8C0`

机读分析器为 `tools/analyze_battle_effect_flag_followups.py`，输出
`notes/battle-effect-flag-followups-20260726.json`；重复生成结果字节一致。

[GameFAQs Skill List](https://gamefaqs.gamespot.com/gba/918717-naruto-konoha-senki/faqs/25752)
说明色诱术使敌人一回合无法行动，毒手里剑使 STR/DEF/AGI 各下降 10%。攻略只用于交叉
验证显示语义，状态 code、持续时间、调用门和参数仍以 ROM 指令为准。

## 实现与事务边界

`battle_action_resolver` 在一个动作—目标的首个有效 damage 结算后调用 follow-up policy：

1. 复制目标单位；
2. 按 flag 构建完整状态记录；
3. 在副本上 upsert 全部状态并重算属性；
4. 全部成功后一次写回；
5. 任一步失败返回 `status_capacity_exhausted`，外层会话与 RNG 事务整体回滚。

毒烟工具 43–45 通过防御准备写入带来源身份和 tool slot 的 `0x16|0x40` 反应记录。相邻攻击
触发替身后，防御者移动到合法落点，进攻者获得三条下降状态；反击事件保留
`defense_action_kind::ninja_tool`，不再误报为主动术。

忍具 70–72 的 type 1 对象到期时从 payload 还原完整动作定义，因此也会进入相同 policy，
而不是只造成普通爆炸伤害。对象到期解析自身也使用 session/RNG 草稿事务：单目标容量
失败，以及多目标中前一目标成功、后一目标失败，都不会保留任何伤害、状态或 RNG 推进。

## TDD 与运行证据

RED：

- `test_battle_effect_handlers.cpp` 首先失败于 `0x80` 没有建立 `0x3F`；
- `test_battle_defense_counter.cpp` 首先失败于 poison smoke 被防御准备拒绝；
- telemetry contract 首先因缺失 cursor unit 状态字段而编译失败；
- mGBA 首次真实路线在 phase 13 发现目标已退场，遥测只读活动单位，保留在
  `artifacts/butano-effect-flag-runtime-20260726-03/`。

GREEN：

- 领域测试覆盖 `0x80`、毒手里剑 11、毒起爆对象 70、毒烟 43、容量原子失败和 RNG 回滚；
- 审查补测覆盖致死目标仍获得三状态、毒对象单目标容量失败，以及多目标后置失败的完整
  session/RNG 回滚；
- controller 测试通过正式装备目录、移动、动作浏览、目标确认后观察目标新增三条状态；
- HUD 显示选中单位活动状态总数 `ST`；
- 最终 ARM 构建和静音 mGBA 证据在
  `artifacts/butano-effect-flag-runtime-20260726-07/`：
  frame 202、battle 41、action 11、target 2、HP 0、inactive、status count 3、
  控制错误 0、玩家错误 0。

最终 ROM SHA-256 为
`a6709258af72e7aa513f558ced0dc7fa760eb439c22c488b1d512d37e7b6d246`；
ELF SHA-256 为
`4af80474c4b11600b9161c38af2bd82a69224f9ff650ef39019d1a4d37c4d82a`；
原始存档保持
`2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc`。

当前 scenario 41 敌人的攻/防/敏均为 6，原作逐项向下取整公式使 10% 下降为 0；
20 点属性领域样本验证重算结果为 18。状态写入和数值 reducer 是两层独立断言。

## 边界

- HUD 只显示活动状态总数，尚无逐状态名称、图标或专属动画；
- 当前自动路线静音，只签发状态机、领域值和画面稳定性，不签发音频；
- 本里程碑不解决主动动作自然解锁、AI 组合、type 2 对象或全部技能专属表现；
- 完整战斗 Goal 继续保持 active。
