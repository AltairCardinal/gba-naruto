# Butano 主动技/被动技统一训练 Implementation Plan

**Goal:** 把现有主动技专用训练 flow 泛化为原 ROM 的统一训练目录，并证明被动训练结果进入
后续真实战斗的 passive consumer 链。

**Architecture:** 领域层新增唯一的 secondary 训练事务；统一 flow 只投影 primary/secondary
条目并按类型分派；controller、renderer、campaign 继续复用既有所有权和持久化链。

## 约束

- 严格执行红绿重构；controller/input 变化必须有集成测试。
- 不复制训练点或等级写入规则到 UI/controller。
- 不新增独立被动页面，不猜测未校字名称。
- 不改 `rom/base.sav`，不提交、不推送，不回滚工作区已有改动。
- ARM 构建和 mGBA 必须经 `tools/run_guarded.py` 的 heavy lock。

## Task 1：固化 ROM 双分支证据

- [x] 扩展 `tests/test_analyze_battle_action_progression.py`，要求 manifest 明确记录
  `+0x15` primary 与 `+0x51` secondary 写入、type 4 行判定和统一 TP 扣除。
- [x] 运行测试确认旧 manifest 因缺少 secondary allocation contract 失败。
- [x] 最小修改 analyzer，重新生成稳定 JSON，并确认测试通过。

## Task 2：secondary 训练领域事务

- [x] 先扩展 `test_battle_action_progression.cpp`，覆盖真实角色 3 / slot 13 / passive 15：
  `0→1→2→3`、锁定、满级、无点数、无效槽、失败原子性。
- [x] 确认编译或断言 RED。
- [x] 实现 `train_secondary_passive`，复用 45 项生成定义和统一错误模型。
- [x] 证明训练后经 scenario loader 进入单位 passive state，`query(0x14)` 返回 value 30。

## Task 3：统一训练 flow

- [x] 新建 `test_battle_training_flow.cpp`，要求角色目录先列非空 primary，再列非空
  secondary；鸣人第一项 secondary 位于索引 8；按类型确认分别写正确数组。
- [x] 确认旧 `battle_primary_training_flow` 无法满足类型和 secondary 条目，得到 RED。
- [x] 重构为 `battle_training_flow` 与统一 snapshot；保留最小兼容头，避免无关调用者断裂。
- [x] 更新 controller 集成测试，证明 secondary 选择与确认通过 controller 完成。

## Task 4：只读 UI 与遥测

- [x] 先扩展 runtime wiring/layout 测试，要求训练快照和遥测携带 entry kind。
- [x] 确认旧 UI 只能渲染主动动作身份，得到 RED。
- [x] renderer 对 primary 复用主动动作身份，对 secondary 显示 `PASSIVE #ID`；
  telemetry 末尾追加 kind，保持既有字段偏移不变。
- [x] 回归 battle 41 的主动技训练脚本，确保既有 action 8 路线不变。

## Task 5：验证与持久证据

- [x] 运行聚焦 C++、controller 集成测试、相关 Python 测试和格式检查。
- [x] 经 guard 运行全量 host C++。
- [x] 经 heavy guard 构建 ARM ROM。
- [x] 经 heavy guard 跑 battle 41 mGBA 主动训练回归；若没有自然达到被动解锁等级，明确以
  host 场景装载集成证明 secondary 链，不伪造自然运行时证据。
- [x] 更新 action progression、domain rewrite、battle architecture 与 roadmap，纠正旧
  “只实现主动训练”的边界，并记录 run ID、哈希和仍未闭合项。
