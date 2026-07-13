# levels / effect progression runtime probe（2026-07-13）

## 身份修正

`0x5459C8` 的 45×12-byte 表不是角色经验等级表，而是角色模板 `+0x50` 的 24 个
次槽/被动效果所引用的成长记录。`0x0806DDA4` 按 requested `target_type` 查询：

```text
record = 0x085459C8 + record_id*12
level_minus_one = stored_level-1
out_a = base_a + per_level_a*level_minus_one
out_b = base_b + per_level_b*level_minus_one
```

返回匹配的 slot index，无匹配返回 `0xFF`。15 个调用点请求 type
`0x0C,0x14..0x20`。

## 两条被否决的捷径

现有 actionable battle 与人物 checkpoint 中，Naruto 次槽虽保留 IDs 1..24，
stored levels 全为 `0xFF`，消费者会在读取 ROM 表项前跳过。

第一版诊断直接把 ROM 角色定义次槽改为 record 16 / level 1。它在到达资料页前改变
了游戏状态，同一输入落入“木叶旋风”演出，scratch 为零；该方案已撤销。

`tools/build_levels_runtime_probe.py` 现改为更安全的 call-local 方案：只在
`0x080890C2` 调 `0x0806DDA4` 的瞬间临时替换 EWRAM slot 0，调用返回后立即恢复，
ROM 角色定义完全不变。自然存档确实到达鸣人简介页，但该 UI 路线没有执行
`0x080890C2`：scratch `0x0203F100` 36 bytes 全零。control ROM SHA-256
`af7abe8fc8d4f023b0b4e6fd7c65a6a2a384e91b954e578c92b4868eb8ed3cfc`；
scratch SHA-256 `6db65fd59fd356f6729140571b5bcd6bb3b83492a16e1bf0a3884442fc3c8a0e`。

因此 levels 严格保持 `code_verified`。下一条有效路线必须先自然获得已激活的次槽，
优先固化 `0x080932CA` 的次槽升级/奖励 UI checkpoint，再对真实命中 record 的
`per_level_a` 做单字段 A/B。不能用强制激活把 bank 提前升级。

重要地址：table `0x5459C8..0x545BE3`；pair query `0x0806DDA4`；升级 consumer
`0x080932CA`。
