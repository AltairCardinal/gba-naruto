# Scenario 41 教程控制路径探针设计

## 目的与边界

Task 5 已固化稳定的 `scenario-41-start-row.ss9`，并从其导出的
`build/task5-after-start-a.ss9` 复现 battle 41 白框边界；但既有
`0x08073946` 与 `0x080739D8` observer 在零输入和独立单 A 后均无 fresh hit。
本设计只定位白框状态实际经过的 controller/action-dispatch 分支，不证明玩家控制、
MOVEDONE、胜利或 postbattle，也不修改游戏行为。

## 方案比较与决定

1. **五点 published-call observer + browser 输入（采用）**：复用现有
   `published_call_observer.py`、浏览器实例内 `buttonPress/buttonUnpress`、savestate 和
   `run_guarded.py`。无需改变原生 mGBA 的只读边界，输入和 observer 都可审计。
2. **扩展 strict-GDB 为 native 输入驱动**：需要重新引入已被正式接口拒绝的
   `--key`/窗口消息/SendInput，扩大所有权与误输入风险，不采用。
3. **继续截图和猜键**：无法定位执行分支，且会重复导航与制造弱证据，不采用。

用户已授权所有确认由代理自行判定；基于最小改动、复用优先和资源风险，选择方案 1。

## 已核对的挂点

新诊断 ROM 只改写五条已核对的 Thumb BL：

| event | call-site | 原目标 | 原始字节 | 含义 |
|---|---:|---:|---|---|
| 1 | `0x08073946` | `0x0806F718` | `fb f7 e7 fe` | 既有玩家选择边界 |
| 2 | `0x08073A16` | `0x08067158` | `f3 f7 9f fb` | action-dispatch 分支 1 |
| 3 | `0x08073A2E` | `0x08067158` | `f3 f7 93 fb` | action-dispatch 分支 2 |
| 4 | `0x08073A3E` | `0x08067158` | `f3 f7 8b fb` | action-dispatch 分支 3 |
| 5 | `0x08073A4A` | `0x08067158` | `f3 f7 85 fb` | action-dispatch 分支 4 |

构建时必须逐条验证 base ROM 原始字节和解码后的 BL 目标；任何不匹配都 fail closed。

## 布局与复用

- 共享 event counter：`0x0203F040`。
- 五个 24-byte published records：`0x0203F060`、`0x0203F080`、
  `0x0203F0A0`、`0x0203F0C0`、`0x0203F0E0`。
- 五个 96-byte stub：从已验证零区 `0x0809E800` 起按 `0x80` 步长放置，
  即 `0x0809E800`、`0x0809E880`、`0x0809E900`、`0x0809E980`、
  `0x0809EA00`。
- 每个 stub 调用原目标并发布参数、sequence、event code；五个 stub/record/call-site
  的范围必须有成对 non-overlap 测试。

诊断 ROM 是从 `rom/base.gba` 独立构建的临时 ROM，不与 Task 2 的双 observer ROM
叠加，因此可以复用其 cave/scratch 保留区。新增 builder 应直接复用
`published_call_observer.py`，不能另写一套 wrapper ABI。

## 运行与数据流

浏览器 driver 不增加新的成功出口，也不需要修改。每轮通过现有
`PROBE_MEMORY_DUMP` 在结束时一次读取 `0x0203F040..0x0203F100`，离线 decoder 解析共享
counter 和五个 record；结果与 driver 的结构化 input audit、battle/map/unit 诊断、截图和
guard summary 一起持久化。

运行分两类，均从 savestate 直接进入边界，避免重复导航：

1. **正对照**：从 `artifacts/runtime-checkpoints/actionable-move-grid.ss9` 启动诊断 ROM，
   使用交接中已有的短显式序列 `KeyX,ArrowDown,ArrowDown,KeyZ,KeyZ`。它只用于证明至少
   一个 action-dispatch observer 能在已知可行动教程链发布 fresh record；不能回溯证明
   player-selection hook。
2. **scenario 41 诊断**：从 `build/task5-after-start-a.ss9` 启动同一 ROM，先零输入建立
   scratch baseline，再在独立运行中只发一个完整 `KeyZ/A`。只有相对 baseline 新增的
   record 才能定位该白框后缀经过的 checked call-site。

两类运行不得共享带旧 magic 的内存作为正证据；每轮记录 ROM/checkpoint/hash、完整输入、
raw record、sequence、screen/WRAM、guard raw reason/exit/peak 和证据来源。

## 失败语义与停止条件

- 构建字节、目标、cave 或 record 范围不符：构建失败，不运行。
- 正对照无任何 fresh action-dispatch hit：探针运行时有效性为 `not-proven`，停止，不测试
  scenario 41，也不把零 hit 解释为路径缺失。
- 正对照通过但 scenario 41 五点均无 fresh hit：结论仅为“这些 checked call-site 在观察
  后缀未执行”；保持 player-control `not-proven`，转向其上游 dispatcher 的静态 call-site。
- scenario 41 命中一个或多个点：以最早 sequence 的 fresh event 作为下一轮更窄 observer
  的入口候选；命中本身仍不等于玩家控制。
- 任意 automatic/unlisted input、资源守卫 degraded、ROM/checkpoint hash 不符或 project
  owned-tree 残留：该轮无效。

## 测试与资源约束

- 严格 TDD：先写 base-byte/BL-target/cave/scratch/non-overlap/错误 ROM/decoder RED，
  再实现最小 builder 与 decoder。
- 运行前后检查可用内存、heavy lock、owned PID tree 和端口；所有浏览器/mGBA 任务必须经
  `run_guarded.py` 串行执行。
- 预算最多三轮 guarded browser（正对照、scenario 零输入、scenario 单 A），每轮预期峰值
  不超过 700 MiB；达到停止条件后不得继续猜键。
- 阶段成果必须记录到 `notes/`，同步当前 Task 5 边界，并单独提交推送远端。
