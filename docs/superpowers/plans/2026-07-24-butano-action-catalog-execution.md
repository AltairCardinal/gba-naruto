# Butano 通用动作目录、目标执行与固定单位池计划

**Goal:** 把角色完整已学动作、本场忍具、目标预览、空闲召唤槽和效果提交接成同一条
可复用运行链，并用 scenario 43 的影分身跨关卡验证，替代 scenario facade 自建固定技能。

**Architecture:** 先抽取只读 `battle_action_catalog`，由角色实例等级的 15 个主动槽与
4 个本场忍具槽生成稳定条目；进攻浏览器与防御浏览器都消费它，不复制内容映射。
场景 loader 可显式保留原 ROM 的 12 个单位槽，空记录成为 inactive reserve。
`battle_action_execution` 根据 target policy 与 effect handler 选择目标、召唤 reserve 和
共享 resolver；预览零写，提交仍使用 session 副本的原子边界。

## Task 1：共享动作目录

- [x] 红测：角色等级 1 的鸣人目录包含 action 2、5、7，装备忍具保留来源与槽位。
- [x] 红测：无效 action/tool 引用返回错误且不产生半截目录。
- [x] 抽取 `battle_action_catalog`，防御浏览器改为复用目录。

## Task 2：固定 12 单位槽

- [x] 红测：loader 在显式策略下保留 12 个稳定 UnitId，未部署记录为 inactive reserve。
- [x] 红测：容量不足时原子失败；默认策略继续只装载有效单位。
- [x] 为 session 提供只读位置与空闲 reserve 查询，不向表现层开放写入口。

## Task 3：通用动作浏览与执行

- [x] 红测：动作浏览器复用等级、资格、成本和本场忍具校验，构建过程零写。
- [x] 红测：scenario 43 action 7 在空地预览不写 session，提交后 reserve 变为真实影分身。
- [x] 红测：占用格、无 reserve 或资源不足失败时 HP、查克拉、坐标和单位池均不变。
- [x] 实现 handler/target-policy 驱动的 preview/resolve 入口。

## Task 4：场景适配

- [x] scenario 41 的教程动作选择从通用目录按显式教学规则取得，不再直接索引固定数组。
- [x] presenter/snapshot 只读取所选目录条目，不写领域结果。

## Task 5：验收

- [x] 全宿主 C++、定向 Python、格式检查。
- [x] devkitARM 与受守卫 mGBA 既有路线。
- [x] 文档明确 scenario 43 领域闭环与尚未可见接入的边界。
