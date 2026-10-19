# Butano 战斗单位逐帧动画设计

## 目标

把 `0x596D5C` 的角色视觉数据从“每名角色只取第一张待机图”升级为可执行的
ROM 时间线，使部署、战场移动、结印、投掷、近战和受击都由角色自身帧表驱动。
本里程碑只负责角色 OBJ；招式特效、转场、文字条、镜头和音频继续由独立表现层维护。

## ROM 结构

62 名角色各有 9 个稀疏视觉槽。有效行的四个指针依次为：

1. 帧指针表；
2. 动画指针表；
3. 1D 4bpp OBJ tile；
4. 16 色 BGR555 palette。

动画指针指向 `u16 frame_index + u16 duration` 序列，以 `frame_index=0xFFFF`
结束。全表最大 48 帧、12 条动画、单条 16 步，已观察时长为
`1/2/4/6/8/16` 帧。

帧不是恒定单 OAM。一个帧指针覆盖一条重叠链：

- 首节点 24 字节；
- 后续节点以 20 字节步长开始，前一节点末尾 4 字节同时是下一节点的
  `tile_index + flags`；
- 下一帧指针（最后一帧则为帧指针表起点）给出链的确定边界；
- 每帧最多 5 个 OAM component；
- `flags=1` 是水平镜像资源引用；
- `next_tile_index & 0x3FF == 0x3FF` 表示链结束。

角色 39、40、55 的第一帧就是复合 OAM。旧生成器只读取第一个 24 字节节点，
因此这三名角色的待机图不完整；新生成器必须修复这一点。

## 槽语义

ROM 帧图、`0x08078F16` 显示对象消费者和 scenario 41“忍者组合拳”逐帧共同约束：

| 槽 | 语义 |
|---:|---|
| 0 | 战场四向待机、离场移动、到达移动 |
| 1 | 结印/施术，面向右 |
| 2 | 投掷，面向右 |
| 3 | 近战，面向右 |
| 4 | 受击/反应，面向右 |
| 5 | 结印/施术，面向左 |
| 6 | 投掷，面向左 |
| 7 | 近战，面向左 |
| 8 | 受击/反应，面向左 |

只有角色 1、2、3、7、25、26、27、28 提供槽 5–8。其余角色在面向左时
复用槽 1–4 并由运行时水平镜像，不能把空槽当成缺资源错误。

槽 0 的动画 0–3 对应下、上、右、左待机；4–7 是同方向离场/移动；
8–11 是同方向到达/收势。

## 资产模型

每个有效视觉槽按原 OAM component 序号和实际 GBA OBJ shape 分组。342 个有效槽
最终生成 534 个 shape-specialized sprite 资产；同一槽最多 8 个资源项、同一时刻最多
显示 5 个 component。每个 sheet 纵向排列同 shape 的 graphics，缺失 component 不分配
OBJ。这样既保留复合角色，也不把超过 64 像素的组合帧裁掉。

生成目录持久保存：

- 每帧的 component、原点、尺寸、tile、镜像和像素哈希；
- 每条时间线的帧索引、持续时间和总时长；
- 每条 component sheet 的画布、帧数和资源名；
- C++ 固定容量 frame/step/sequence 表和角色槽查询函数。

## 运行时

每个领域单位持有最多 5 个可选 sprite component。非活动槽释放全部 component；
召唤或身份覆盖按 `character_id` 重新绑定目录。

表现层只请求“待机/移动/结印/投掷/近战/受击 + 面向 + 已过帧数”，目录驱动器
按 ROM duration 返回具体 frame index。面向左但无槽 5–8 时返回基础槽并设置
水平镜像。动作效果和数值结算不依赖动画完成结果；视觉资源缺失则断言停止，
不回退到鸣人或通用敌人。

行动解析结果会把所有受影响单位 ID 传给玩家/AI flow，再进入
`battle_scene_presentation_event`。因此范围攻击、治疗、召唤和致死攻击不靠目标格
反猜对象；已经被本次行动击倒的单位会保留到表现事务结束。近战突进只用于
`animation_family=1` 的敌对非忍具动作，结印/忍具原地播放，避免把所有动作套成
同一种冲撞。

命中时间线也必须来自领域事务。resolver 的 `resolved.generated_hits` 经玩家/AI flow
投影为 presentation event 的 `impact_count`，表现层据此计算 0、1、2 或更多次 impact，
再进入返回和收势阶段。非伤害动作的 `impact_count=0`，不会凭空播放三次受击；单击与多段
动作也不会被压成同一个 96 帧模板。上限 32 与固定容量 damage event 队列一致，表现层只读
该值，不反向修改命中、HP 或回合状态。

scenario 41 默认入口调用共享 `run_battle_41_scene()`，与 battle 9、32 等样本使用同一
`battle_runtime_scene`、controller、resolver、AI 和单位 renderer。旧 264 帧整屏攻击
资产已移出生产 `graphics/`，仅保存在
`references/scenario-41-attack-animation/` 作为离线证据。

## 边界

- 本里程碑不伪造招式特效和星形转场；它们必须从各自 ROM 表继续提取。
- 自动 mGBA 验收静音，只证明帧序列、状态机和资源安全，不证明主观音质。
- 原作逐帧证据只证明忍者组合拳的槽 0→槽 3→目标槽 4 链；其他动作类别继续用
  ROM 字段与新增实机样本复核，不能把当前映射写成所有技能的最终电影脚本。

## 动态命中时长验证

- ARM：`build/resource-guard/butano-resolved-impact-outcome-mask-arm-build-20260725-188.json`；
- scenario 41：`artifacts/butano-resolved-impact-s41-20260725-93/`，单次命中、返回、
  动画期 `RESOLVING` 和动画后 `BATTLE COMPLETE`；
- battle 9：`artifacts/butano-resolved-impact-b09-20260725-94/`，零 hit 分身、不同角色
  行动和五敌 AI 后回到 round 2；
- 最终 ROM：9,106,908 字节，SHA-256
  `23ec3ecfec4b50c14605318983fa86823aeda85baf87e80d7ace48411cad6a02`。
