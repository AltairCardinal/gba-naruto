# Butano 运行时尺寸战斗网格设计

## 目标

让一套 `battle_scene_controller`、寻路、AI、部署和回合流程能够装载生成目录中的全部
47 张逻辑战斗地图，不再为 9×22、16×32 等尺寸复制模板实例或场景代码。

本里程碑只解决权威逻辑网格的容量与活动边界。原作地图视觉层仍必须由对应 ROM row
重建；宽度超过 GBA regular background 512px 上限的地图需要后续实现分块流送，禁止用
已有背景图替代。

## 事实与约束

- 47 张地图共有 22 种逻辑尺寸，最小 9×16，最大 23×32。
- 当前 `grid_map<Width, Height>` 把模板尺寸同时当作容量和活动边界，
  `materialize_battle_map` 只接受完全相等的宽高。
- 当前可见运行时因此分别实例化 9×22 和 16×32 控制器；继续扩展会形成 22 套模板代码、
  静态工作区和场景分支。
- GBA 运行时不使用堆分配。地图、寻路与控制器必须保持固定上界。
- 每个原作格点的视觉宽度为 32px；23 格宽为 736px，不能整体塞进 512px regular
  background。因此逻辑统一不等于视觉资源已经统一。

## 方案

采用 `grid_map<23, 32>` 作为战斗运行时最大容量，并在对象内保存
`active_width`、`active_height`：

- 模板参数只定义数组、寻路 workspace 和索引 stride 的容量；
- `contains()` 只接受活动矩形内的格点；
- 默认活动尺寸等于模板容量，保持已有 `grid_map<9, 22>` 测试和 scenario 41 兼容；
- `set_active_dimensions()` 只接受 `1..Width`、`1..Height`，失败时不改变对象；
- 切换尺寸时清空整块固定容量，并把活动区以外视为不可进入；
- `materialize_battle_map()` 接受不超过容量的地图，以定义自身宽度作为 ROM 内容行宽，
  以容量宽度作为目标数组 stride；
- occupancy、寻路、范围、AI 和 cursor 都通过 `contains()` 遵守活动边界，不能进入 padding。

新增共享容量定义：

```text
battle_runtime_grid_width  = 23
battle_runtime_grid_height = 32
battle_runtime_grid
battle_runtime_controller
```

可见场景只保留一个 `battle_runtime_controller` 静态实例。battle 9 和 battle 43 继续使用
各自 ROM 重建背景，但不再拥有不同领域控制器类型。

## 为什么不采用其他方案

### 每个尺寸一个模板实例

它无需改 loader，但会把现有两套模板扩张到 22 套，增加 ROM 代码和 EWRAM 静态工作区，
并让每新增地图尺寸都要求改 C++ wiring。它不能支撑后续关卡流水线。

### 多组容量桶

按宽高分为若干模板容量能节约单个 workspace，但仍需运行时分派和多套静态控制器。
只有在 ARM 构建证明单个 23×32 控制器超过内存预算时才退回此方案。

## 数据流与不变量

```text
generated_battle_content_entry
        |
        v
battle_map_definition(width, height, cell slice)
        |
        v
materialize_battle_map
        |
        v
grid_map<23,32>(active width/height + fixed storage)
        |
        +--> pathfinding / movement / range / AI
        +--> battle_scene_controller cursor validation
        +--> snapshot -> renderer
```

必须保持以下不变量：

1. 活动区外 `contains == false`、`cost == 0`、`directional_mask == fully_closed`。
2. 内容数组按地图定义宽度读取，目标数组按容量宽度存储。
3. 无效尺寸、内容越界或单位落在 padding 时，装载是事务性的，原目标不变。
4. 目录中的全部非空 variant 必须能装载到同一个控制器；动态占位 variant 使用显式角色绑定。
5. 空 variant 继续被目录分类为不可玩内容，不伪造单位或胜负条件。
6. renderer 不解析地图内容、不修改 session，也不决定寻路边界。

## 用户可见行为

- battle 43 和 battle 9 的部署、单位选择、移动、技能、敌方回合和返回路径保持不变。
- 光标、玩家移动和 AI 不可能进入实际地图宽高之外的 padding。
- 后续给任意原作关卡接入其背景和章节入口时，不再新增一套战斗控制器或回合 FSM。
- 当前开发菜单仍只展示已有可见关卡；没有对应视觉资源的其余地图不会以错误背景冒充完成。

## 错误与边界

- 地图宽高为零或超过 23×32：`dimension_mismatch`，不改变当前地图。
- cell slice 越界：`content_out_of_bounds`，不改变当前地图。
- 单位位于 padding 或阻挡格：装载失败，不能开始战斗。
- 23×32 控制器若使 ARM EWRAM/IWRAM 超预算：保留红绿证据，改用容量桶；不得通过移除
  验证、改回栈分配或削减战斗系统来掩盖。
- 自动 mGBA 路线保持静音，只验证画面、状态与流程，不签发音频听感。

## 验收

- 宿主测试覆盖活动尺寸设置、padding 查询、事务失败、寻路不越界。
- 迭代 47 张地图，全部能物化到 `battle_runtime_grid`，活动尺寸与定义一致。
- 迭代全部非空 variant，固定编队和带显式绑定的动态部署都能装载到同一个
  `battle_runtime_controller`。
- source wiring 测试证明可见运行时不再实例化尺寸模板，也不写死逻辑宽高。
- ARM 构建报告 section 占用且无 warning/error。
- 静音 mGBA 重跑 battle 9、battle 43、scenario 41，保存唯一 run ID、ROM/ELF 哈希、
  遥测与截图。

