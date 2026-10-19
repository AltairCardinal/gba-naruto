# Butano AI 动态候选场与朝向评分实施计划

> 状态：纠错后已实现并完成独立 ARM/mGBA 回归。本计划只闭合原 ROM 静态与运行时证据已经证明的候选朝向、动态候选场和两层择优；不据此宣称 AI 防御、资源命令或全部关卡策略完成。

## 目标

把原作 `0x080833A8` 的动态候选场与 `0x08085160` 的候选格评分接入 Butano 通用 AI，使候选保存最终朝向，规划与执行读取同一事实；保持“站位内动作择优 → 站位间候选场择优”的两层结构，避免位置 RNG 污染同一站位内的技能比较。

## 任务

- [x] **红：锁定原作格评分公式**
  - 新增 `test_battle_ai_candidate_score.cpp`。
  - 覆盖同向 `+50`、无威胁 `+200`、面向方向无来源 `+100`、`(rng×50)>>15` 和无威胁分支不消费 RNG。
  - 失败证据：`build/resource-guard/butano-ai-candidate-score-red-20260725-235.json`。

- [x] **绿：让候选拥有朝向和最终评分位置**
  - 新增 `battle_ai_candidate_score.h`。
  - `AiCandidate` 保存 `facing` 与 `scoring_position`。
  - planner 先在单一 destination 内严格选择动作，再对该 destination 的最终候选调用 `score_tile`。
  - `battle_ai_turn_flow` 直接提交 `plan.facing`，不在执行阶段重新推导。

- [x] **重构：修正两层 RNG 顺序**
  - 初次直接给每个动作候选加格分会改变同一站位的技能比较，保留失败证据
    `butano-ai-candidate-score-green-20260725-237/238`。
  - 改为本地动作候选先择优、空间候选后评分。

- [x] **纠错：以原版运行时字段替换错误地图标志接线**
  - `0x08085590` 捕获证明 `0x0201BE2A` 是地图宽度，评分字段位于 `0x02002880`，并由
    `0x080833A8` 在每次规划时动态构建。
  - 新增 `battle_ai_candidate_field_builder`，从敌对单位可达站位、可用伤害动作和范围
    生成独立字段；明确不是 `grid_map::flags`。
  - TDD 证据：
    `butano-ai-candidate-field-green-20260725-267`、
    `butano-ai-candidate-field-integration-red-20260725-268`、
    `butano-ai-candidate-field-integration-green-20260725-269`。

### 独立动态字段版本验证

纠错后的实现已产生一组全新的证据：

  - 68 个宿主 C++ 测试：
    `build/resource-guard/butano-ai-candidate-field-host-all-20260725-285.json`。
  - 77 个 Python 测试通过、1 个环境条件测试跳过：
    `build/resource-guard/butano-ai-candidate-field-python-final-20260725-287.json`。
  - Docker/devkitARM 构建：
    `build/resource-guard/butano-ai-candidate-field-arm-build-20260725-288.json`。
  - 静音 mGBA battle 9：
    `artifacts/butano-ai-candidate-field-b09-20260725-02/`，9 个活动单位完成首轮并于
    frame 1167 进入 round 2、phase 1。
  - `git diff --check` 与研究文档测试。

## 明确边界

- 当前公式只覆盖已哈希绑定的朝向、动态候选场五个 bit 和 0–49 随机项。
- helper mode `0/2/4/6` 的全部差异、状态排除、视线、范围动作边缘及全部碰撞过滤尚未闭合。
- AI 主动准备防御、补充查克拉、休息的选择策略仍缺运行时闭环，不做猜测。
- battle 9 的忍具装备仍是接线夹具；本里程碑不补写章节队伍、剧情或战后结算数据。
