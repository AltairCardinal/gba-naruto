# Butano 通用战斗表现脚本设计

## 状态与目标

本设计补齐当前通用战斗运行时缺失的“战斗开场、回合插话、结果前后对白与章节打断”层。
它不能是 `battle_id == 41` 的条件分支，也不能把原 ROM 截图按 A 键顺序切换。脚本只产生
表现命令和受控的章节事件；地图、单位、HP、资源、行动账本、回合与胜负仍只由
`battle_session`、动作 resolver、scheduler 和 condition interpreter 修改。

首个验收样本是 battle 41 的原作战斗开场和教程对白，第二个样本必须来自另一场使用不同
脚本分支的战斗。只有两场都由同一内容格式、解释器和 controller 接线运行，才算证明架构
可供后续关卡复用。

## 原 ROM 事实边界

战斗主控制器在 `0x080736F8..0x080737C8` 的初始回合边界读取：

- `0x02026805`：battle ID；
- `0x02026806`：variant/secondary ID；
- `0x0202680C`：round index；
- `0x085461C4 + battle_id×0x1AAC + variant×0x8E4`：编队首角色 selector。

控制器在 `0x02026804 == 0` 的战斗边界且当前战斗有表现脚本时调用：

- `0x0808A534`：运行 selector-builder 脚本并检查生成的分支数量；
- `0x0808A588`：按 selector-builder 结果逐项运行表现脚本；
- `0x080977B8`：共用章节/对白解释器。

两张连续的 47 项指针表是：

- `0x08060E34`：selector-builder roots；
- `0x08060EF0`：presentation roots。

entry 0 是空哨兵，battle 1–46 均有有效 ROM 指针。解释器跳转表覆盖
opcode `0x00..0x39`，其中 `0x24..0x31` 进入统一拒绝路径；战斗 selector-builder
实际使用 `0x00`、`0x01`、`0x02`、`0x07`、`0x08`、`0x32..0x39`。

已由控制流闭合的指令结构：

- `0x07 + u32 pointer`：无条件跳转；
- `0x32 + u32 pointer`：连续 case 表，按 selector-builder 产生的当前 selector 选择；
- `0x33 + u8 selector`：把 selector 追加到最多 16 项的运行时列表；
- `0x34`：8 字节条件跳转，pointer 位于 `+4`；
- `0x35`：9 字节条件跳转；比较“指定阵营/关系模式下两个角色是否相邻”的结果与
  expected byte，pointer 位于 `+5`；
- `0x36`：8 字节条件跳转；比较“指定阵营是否存在活动角色”的结果与 expected byte，
  pointer 位于 `+4`；
- `0x37`：3 字节脚本私有 flag 写入；
- `0x38`：7 字节脚本私有 flag 已设置/未设置查询，pointer 位于 `+3`；
- `0x39`：6 字节 secondary battle state/variant 等值分支，pointer 位于 `+2`。

这些语义由 `0x08097D86..0x08097E0C` 的 handler 及其
`0x0808A1C4/0x0808A420/0x0808A490/0x0808A4D8/0x0808A504` helper 闭合；
内容层仍保留 opcode、原始 operands、branch target、fallthrough 和源地址，避免只留下
二次命名。

## 复用与分层

### ROM 内容分析层

新增独立分析器读取两张 47 项表，先验证 ROM、控制器调用区、解释器、跳转表及指针表
SHA-256，再构造 selector-builder 控制流图。分析器枚举所有可达 selector 序列，并解析
presentation root 起始的连续 `0x32` case 表。任何越界指针、未知 builder opcode、
超过 16 项的 selector 路径、无终止路径或 case 数不足都失败关闭。

该层复用现有 `chapter_script_analyzer` 的 ROM 指针和文本边界知识，但单独维护战斗脚本的
控制图；不能把只在 scenario 39 观察到的六个线性 opcode 误当完整战斗脚本语法。

### Butano 内容层

生成内容使用固定容量记录：

- battle ID 与 variant；
- selector-builder 控制节点；
- presentation case roots；
- 已闭合的表现命令；
- 未闭合 payload 的原始地址、长度和证据状态。

未知命令不进入可玩关卡。生成阶段拒绝，而不是运行时跳过后继续显示不完整流程。

### 运行时层

`battle_scene_controller` 增加独立的 script-blocked phase 和只读 script snapshot。
脚本解释器只能：

- 发布可见对白/头像/提示/音频 cue；
- 等待 A 或自动时长；
- 设置脚本私有变量；
- 请求已注册的强类型章节事件。

强类型事件在 controller 的明确边界转换为领域命令；脚本本身不能写 `battle_session`。
脚本阻塞期间方向键、L/R、战斗确认和 AI tick 均不得穿透。

### 表现层

renderer 根据结构化命令绘制窗口、头像、文本和 cue，不读取整屏截图。原截图、save-state
和录屏只用于像素/时序验收。缺失字体或头像资源时进入显式 error phase，不能显示空黑屏。

立绘 renderer 直接消费原 ROM 的 63×5 资源矩阵，只嵌入当前 400 个 case 实际引用的
46 个 `(portrait_id, expression_id)` 组合。每张立绘是 80×80、8bpp、6,400 字节，
按原 OAM helper 的 6 个组件拆成硬件支持的 sprite shape；左右槽共享 128 色 OBJ
palette，右槽非零像素索引增加 64，失焦槽使用原函数的
`((color & 0x7BDE) >> 1) + ((color & 0x739C) >> 2)` 暗化公式。压缩流在生成 bank
内逐条做 4 字节对齐，因为 GBA LZ77 解压器读取未对齐的第二条资源会冻结。

窗口不是截图裁片，而是 script snapshot 中 `message_window_visible` 驱动的 4bpp
半透明 sprite layer；字形继续由 ROM 字库生成。脚本阻塞期间释放普通单位 sprite，
隐藏战斗游标；脚本完成后销毁窗口/立绘 sprite，并由正常单位 renderer 从领域快照重建。

## 数据流

1. 场景请求携带 battle、variant、章节 party 与持久角色数据。
2. controller 装载地图、单位、condition 和战斗表现脚本。
3. `start()` 先执行 battle-start trigger；有可见命令时进入 script-blocked。
4. 玩家逐页确认后脚本完成，controller 才打开 unit selection。
5. scheduler 在 round/side/action/outcome 边界发布事件；脚本匹配 trigger 后可再次阻塞。
6. 脚本结束恢复此前明确保存的 controller continuation，不重新推断状态。
7. 胜负、经验和升级继续使用现有通用结算链。

## TDD 与验收

### 静态内容测试

- 两张表均为 47 项，entry 0 为空，1–46 为 ROM 指针；
- interpreter/call site/jump table/table hashes 与权威 ROM 一致；
- 全部 builder roots 只出现已闭合控制 opcode；
- battle 41 builder 的可达 selector 序列和 presentation case roots 精确匹配 ROM；
- 至少一场非 41 战的分支结构作为交叉样本；
- 改坏任一指针、opcode、长度或哈希时分析器必须失败。

### 领域与接线测试

- 脚本阻塞时战斗输入和 AI 不推进；
- 每次 A 只推进一个 wait-for-input 命令；
- 脚本完成后恢复预定 controller continuation；
- 取消/重复确认不写 battle session；
- battle 41 与第二场战斗共用同一解释器；
- 无脚本 entry 直接进入正常战斗。

### 运行时验收

- 宿主 C++ 与 Python 测试；
- 无警告 ARM 构建；
- 受资源守卫的 mGBA 路线；
- 原 ROM/Butano 在相同输入边界比较 phase、round、单位状态、脚本 cursor、页面数与可见截图；
- 音频另以非静音人工/采样验收签发，静音自动化不能证明听感。

## 当前边界

现已闭合 46 个非空 selector-builder 控制图、400 个 presentation case、3,213 条实际
payload 命令边界、`0x34..0x39` 条件/flag 语义、`0x02/0x03/0x04/0x11/0x12/0x17`
的立绘状态语义和 862 个 ROM 字形。Butano 运行时以固定容量单位快照、脚本 flag、
case/command/text bank 执行，不读取整屏截图；battle 41 与 battle 43 均由同一 renderer
逐页核对文本地址、窗口、立绘身份、表情、焦点，并在脚本完成后恢复 unit selection。

当前只按逆向结果实现了脚本实际使用的 motion 2/3/4 最终位置，尚未还原所有 motion
mode 的逐帧插值和精确时长；只嵌入脚本引用的 46 个立绘/表情组合；自动化路线静音，
不能证明音频质量。另有 45 场尚未逐场执行 mGBA 可见路线，因此不能据此宣称 47 场表现、
battle 41 教程整体或完整战斗系统已经功能等价。
