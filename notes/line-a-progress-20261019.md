# 甲线推进记录与资源瓶颈实测（2026-10-19）

本轮按用户授权沿「甲线（覆盖驱动）」从 M0 推进，并全程实测本机资源对吞吐的限制。
本文件是本轮唯一权威记录：结论、实测数据、证据路径与未闭合义务都在这里，
不依赖对话历史。推进期间工作树被并发写入者提交过两次（见 §1），本文件按最终事实书写。

## 1. 基线与并发写入

| 时刻 | 事件 | 影响 |
| --- | --- | --- |
| 22:52 | 本轮开始，逆向树 HEAD `0302f4685`（2026-09-05），工作树 259 未跟踪 + 17 修改 | M0-b 的原始对象 |
| 22:53 | 主工作树 `70ef4233c` "untrack regenerable artifacts, build output and stale audio copies"（7,503 文件，891,986 行删除） | **主工作树的「恢复 8,055 个缺失文件」不再是待办**：缺失产物被判定为可再生并解除跟踪，`.gitignore` 补了 31 行带理由的规则 |
| 22:59 | 逆向树 `b4da99dfa` "commit the October evidence bundles and the remaining verifiers"（3,013 文件 / 2,143,255 行） | **M0-b 完成**：10 月全部证据与验证器入账，工作树归零 |
| 23:00+ | 本轮新建 `tools/measure_reverse_throughput.py` 等 | 唯一新增未跟踪内容 |

两个提交都不是本轮产生的。逆向树 `b4da99dfa` 之后的账本口径：

- coverage `sequel/rom-byte-coverage.json` SHA `b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2`（本轮实测一致）
- ROM `rom/base.gba` SHA `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`（本轮实测一致）
- unknown 87,631 B / 1,763 段；22 个有效 bank、2,954 条记录、声明覆盖 23 条；6 门 19 case 覆盖集合为空

## 2. 三个硬阻塞（都不是「算力不够」）

### 2.1 解释器版本不匹配 —— 全仓工具链默认不可运行

- 系统默认 `python3` 是 **3.9.6**（`/usr/bin/python3`）。
- 全仓 `zip(..., strict=True)` 出现 **1,219 处**；`strict` 参数要 Python 3.10+。
- 后果：`python3 tools/audit_rom_byte_coverage.py --root .` 在 3.9.6 下**秒失败**，报
  `"direct CpuSet GPU artifact failed independent verification: zip() takes no keyword arguments"`。
- 正确解释器是 **`/usr/local/bin/python3` = 3.14.3**（`tools/__pycache__/*.cpython-314.pyc` 证明历史成果就是在它下面跑出来的）。
- **本轮自定位该问题之后，所有工具调用一律使用 `/usr/local/bin/python3`**。这是本仓库的隐式前提，尚未写进任何文档或门禁。
- **更严重的下游后果（本轮实测）**：proof 账本里 97 条验证器命令全部写成裸 `python3`，
  而本运行时环境的 `PATH` 是
  `/Users/altair/.minimax/shims:/Users/altair/.pi/agent/bin:/Users/altair/.minimax/bin:/usr/bin:/bin:...`
  ——**没有 `/usr/local/bin`**，所以 `python3` 解析到 3.9.6。实测同一验证器：

  | 解释器 | 结果 |
  | --- | --- |
  | `python3`（3.9.6） | `{"verified": false, "errors": ["zip() takes no keyword arguments"]}`，exit 1 |
  | `/usr/local/bin/python3`（3.14.3） | `{"verified": true, "direct_call_count": 146}`，exit 0 |
  | `PATH=/usr/local/bin:$PATH python3` | 同上，通过 |

  也就是说：**照账本原样跑正式审计，会得到一批"假 blocker"**——它们是解释器版本问题，
  不是逆向证据缺失。正式审计必须以 `PATH=/usr/local/bin:$PATH` 执行。

### 2.2 守卫默认 idle 超时 60 秒 —— 静默杀掉所有重活

`tools/project_resource_guard.py` 的 `GuardConfig` 默认值：

```
min_available_mib = 1024   # 物理内存，不是磁盘
max_tree_rss_mib = 1536
wall_timeout_s   = 600
idle_timeout_s   = 60
```

实测（第一次测量运行，受管执行）：

| 阶段 | 墙钟 | 退出码 | 守卫结论 |
| --- | ---: | ---: | --- |
| coverage 审计 | 60.82 s | 124 | **idle-timeout** |
| unknown 排名 | 1.31 s | 0 | completed |
| 正式 proof（`--execute-verifiers`） | 60.24 s | 124 | **idle-timeout** |

两个重活都在**恰好 60 秒**被杀，表现为 exit 124，看起来像「工具卡住」而不是「配置闸门」。
2026-10-01 的 `notes/rom-small-cfg-dependency-tier2-20260930.md` 已记录过同一现象
（当时显式改用 idle 240 秒才通过），但默认值至今没有改。

**结论：任何重跑都必须显式提高 `--idle-timeout-s`。** 本轮的测量 spec 已改为
coverage 1800 s / formal 3600 s，见 `notes/evidence/reverse-throughput-20261019-v1/stages.json`。

补充实测：把 idle 超时放宽后，coverage 审计在**单核 95% 占用下已连续跑过 8 分 26 秒
仍未结束**（CPU 时间与墙钟几乎相等）。这说明它同时撞上了默认 `wall_timeout_s=600`
的另一侧——**两个默认超时都对这批工具过紧**，必须同时放宽。

### 2.3 heavy 锁是非阻塞的 —— 并发不是排队，是直接失败

`ProjectLock` 用非阻塞文件锁。并发受管运行实测：

```
lock-probe-0: reason=lock-busy, exit_code=75
lock-probe-1: reason=lock-busy, exit_code=75
```

两个并发受管运行**两个都被拒**（当时 coverage 审计正持锁）。含义：

- **同一时刻只有一个受管重活能跑**；多开的子代理只会得到一堆 exit 75 的失败运行。
- 子代理并发只能用于**只读侦察与静态分析**，不能用于并行重活。

## 3. 实测吞吐

工具：`tools/measure_reverse_throughput.py`（本轮新建，12 项测试全绿），
收据在 `notes/evidence/reverse-throughput-20261019-v1/`。

- **CPU 并行探针**：4 个 CPU 密集工作者，串行 11.707 s vs 并行 4.711 s，
  **加速 2.485×，并行效率 0.621**。名义 12 逻辑核、实测 4 路并发只有 ~2.5×，
  因为 1 分钟负载常驻 10 左右（桌面应用本身在占）。
- **主机基线**：12 逻辑核 / 16.0 GiB 内存 / 数据卷可用 6.6–9.9 GiB（98% → 96%）。
- 内存守卫按**物理内存**判定：`free + inactive + speculative` 实测约 6.4 GiB，
  1 GiB 准入线通过；但单树上限 1,536 MiB，4 棵树并发会互相挤占。

**瓶颈排序（结论）**：

| 排名 | 瓶颈 | 性质 | 证据 |
| ---: | --- | --- | --- |
| 1 | 守卫 idle 超时 60 s | 硬闸门 | 两个重活 exit 124 |
| 2 | heavy 锁非阻塞序列化 | 硬闸门 | 2/2 并发被 lock-busy 拒 |
| 3 | 磁盘余量 6.6–9.9 GiB（96–98%） | 硬约束 | 产物、录制、收据全写盘 |
| 4 | CPU 并行效率仅 0.62 | 软 | 4 路并发只有 2.485× |
| 5 | 解释器默认版本不匹配 | 硬闸门 | 1,219 处 `zip(strict=True)` |

**一句话**：限制推进速度的不是 CPU，也不是子代理数量，是**两个配置闸门（idle 60 s、
非阻塞 heavy 锁）加一个磁盘余量**。把它们调对之前，加更多子代理只增加失败运行。

### 3.1 单次入账的真实成本（本轮实测 + 历史收据）

| 操作 | 耗时 | 来源 |
| --- | ---: | --- |
| coverage 账本重建（`audit_rom_byte_coverage.py --write`） | **实测 30 分钟仍未结束**（单核 95–100%，纯 Python 计算，栈采样确认非死锁） | 本轮 |
| 正式 proof 全量（`audit_reverse_engineering_proof.py --execute-verifiers`，107 个验证器） | **39.7 分钟**，峰值 RSS 533 MiB | `notes/evidence/rom-small-cfg-batch-formal-20260930-v1/formal-guard.json` |
| unknown 排名 | 1.09 秒 | 本轮 |

**这是"一次晋升 = 约 40 分钟单核"的事实**，它解释了为什么政策规定
「同类 4 包 / 10 KiB / 0.15 pp 才触发一次 formal」——在单机单核的账本重建成本下，
逐包跑 formal 在算术上就不成立。也解释了为什么加速点不在"再开几个子代理"，
而在**减少每次账本重建的成本**（账本构建是 O(claims × segments) 的 Python 热点，
当前 16,913 claims / 18,675 segments）。

#### 3.1.0 守卫 idle 的真实语义，以及正式审计的正确配方（**可复用**）

`tools/project_resource_guard.py` 的 idle 判定是 `_ProgressTracker.is_idle`：
**「stdout/stderr 没有输出完整行」的持续时长**（`_drain_stream` 只在读到以
`\n` 结尾的完整行时 `record_complete_line()`）。

而 `tools/audit_reverse_engineering_proof.py` **全程不输出，只在最后一次性打印
整个报告**。于是 idle 计时器从启动起**从不重置**，守卫必然在恰好
`idle_timeout_s` 处把它杀掉（exit 124、无报告文件）。

**实测**：本轮第一次正式审计给了 `--idle-timeout-s 3600`，
16:22:52 启动 → 17:22:52 被杀，**恰好 3600 秒**，收据
`reason: "idle-timeout"`, `exit_code: 124`, `degraded: false`。

**项目里已有的正确配方**（`notes/rom-small-cfg-dependency-tier2-20260930.md:44,84`）：
**wall 9000 秒 / idle 7200 秒**。9-30 那次成功运行的收据
（`formal-guard.json`，`reason: completed`, `exit_code: 0`, 2,383 秒）用的就是它。

⚠️ 这条同时解释了 §2.2 观察到的"两个重活都在恰好 60 秒被杀"：
**默认 idle 60 秒对这两个工具都是致命的**——coverage 审计和正式审计都不流式输出。
凡是跑这两个工具，必须显式给 `--idle-timeout-s 7200`（或更大），
否则再长的 wall 超时也没有意义。

#### 3.1.1 重建成本的真正热点（栈采样定位）

`sample` 采样显示热点**不在**语义计算，而在 **JSON 解析**
（`scan_once_unicode` / `scanner_call` / `scanstring_unicode` 占采样帧的绝大部分）。
`sequel/rom-byte-coverage.json` 本身是 **31.4 MB**，另有 186 个 evidence 条目、
其中多份 payload 在 200 KB–4 MB 量级；~40 个 claim producer 各自读入并解析这些
JSON。**因此提速点是"让账本构建复用已解析的账本/收据"，而不是增加并发或换更快的机器。**

另一个观测：父进程在等待子验证器（`verify_rom_cfg_proven_roots_v15_bundle` 等原生
trace 重放）时进入 `poll()`，此时父进程 CPU 冻结但**并未死锁**——排查时不要把它
误判成卡死。整体有效并行度是 **2 核**（父 + 一个子验证器），这与 4 路 CPU 探针
只有 2.485× 加速的实测一致。

## 4. M0 状态

| 项 | 状态 | 证据 |
| --- | --- | --- |
| M0-a 主工作树缺失文件 | **被取代** | 用户 `70ef4233c` 解除跟踪可再生产物 |
| M0-b 逆向树 259 未跟踪分类 | **完成** | 用户 `b4da99dfa` 入账；proof ledger 186 evidence + 97 verifier，0 missing / 0 mismatched |
| M0-c 118 B 四包入账 | **已完成** | 21 条 claim 来自 `artifacts/rom-small-cfg-dependency-batch-v1/`；87,749→87,631 B 差额逐字节吻合（12×align4 + 3×literal_word + 5×thumb_code + 1×dispatch_slot = 118 B） |
| M0-c 2,721 B 两包入账 | **未完成** | 显示文本 1,053 B 有永久收据；**旧命令脚本 1,668 B 的产物只在被 gitignore 的 `build/` 下，没有 artifact 目录**，必须先走受管发布才能入账 |
| M0-c 孤儿 artifact | 待清理 | `artifacts/rom-low-script-delta-v1/` 账本引用 0、proof 引用 0，且其 note 自承违反受管发布流程 |

## 5. 本轮新增成果：池 3 固定合同（1,542 B）

### 5.1 为什么换目标

侦察与复算都指向同一个结论：**先做的包应该是 `0x0CEA..0x12F0`，不是动画 descriptor 池。**

| 候选 | 净收益 | 需要的语义 | 风险 |
| --- | ---: | --- | --- |
| 池 3 `0x0CEA..0x12F0` | **1,542 B** | **零新语义**（复用已验收的 opcode 0/1/3/4/5/12） | 低 |
| 动画池 `0x45832C..0x4585AC` | 640 B | 需自证 8 个 descriptor 的可变 stride | 中（5 对 base 的 caller 未定位） |
| 脚本 5 根 | 125 B | 需全新 opcode 7/8 handler 合同 | 高（已证「每次进入 7 都 +3」为假） |

### 5.2 结构（本轮从 ROM 字节独立复现，非引用笔记）

- `0x0CEA..0x12F0` 链式解析出 **27 条记录，无缝隙、无重叠**，字节和 **1,542 == 池大小**，
  末条正好终止于 `0x12F0`。
- 27 条的 opcode 序列**全部**是 `[1,5,4,12,3,0]`，与左侧已验收记录
  `(0x0CC7,0x0CEA,[1,5,4,12,3,0])` 和右侧已验收记录 `(0x12F0,0x12FA,...)` 的规范序列一致。
  池 3 正好是两条已验收记录之间的缺口。
- 消费者是 **`0x53DF00..0x53DF70` 的 28 槽 u32 指针表**：slot 0 = null，
  slot 1..27 与 27 条记录根**一一对应且顺序一致**。
- 消费点 `0x0712D0..0x071350`：`0x0712EE` 是 `LDR`（PC 相对池 = `0x071350`），
  该字面量 **`0x0853DF00` 在全 ROM 只出现 1 次**；`0x071340` 是 `BL`，
  目标 **`0x067158`**（既有解释器入口，与 41 个已验收 consumer site 同构）。

### 5.3 交付物

| 文件 | 内容 |
| --- | --- |
| `tools/export_rom_renderer_script_pointer_pool_records.py` | 导出器：指针表反推分母、链式解析、消费者合同、原子不可覆盖发布 |
| `tools/verify_rom_renderer_script_pointer_pool_records.py` | 独立验证器：**不 import 导出器**，自带解析实现，要求 payload 与 manifest 逐字节等于独立重建 |
| `tests/test_export_rom_renderer_script_pointer_pool_records.py` | 23 项测试：结构、作用域、AST 独立性、7 组变异双侧拒绝、artifact 篡改拒绝、CLI |
| `artifacts/rom-renderer-script-pointer-pool-records-v1/` | 已发布，manifest + payload |
| `tools/measure_reverse_throughput.py` + `tests/test_measure_reverse_throughput.py` | 12 项测试；本节全部实测数据的来源 |

CLI 复验：

```bash
/usr/local/bin/python3 tools/verify_rom_renderer_script_pointer_pool_records.py \
  --root . --artifact artifacts/rom-renderer-script-pointer-pool-records-v1
# {"verified": true, "record_count": 27, "promotion_bytes": 1542, "errors": []}
```

### 5.4 明确不声称什么

payload 的 `scope` 五项**全为 false**，且新增两条旧合同没有的：

- `natural_runtime_reachability` —— 27 条记录只有 `0x53DF00` 一条静态路径；
- `index_domain_closed` —— 索引来自 RAM 6 字节行字段，**无 `<=27` 守卫**（全段搜 `cmp #0x1b` 无命中）；
- `row_writer_lifecycle_closed` —— 该 RAM 字段的 writer / 初始化 / 轮询路径未闭合；
- `null_slot_semantics_closed` —— slot 0 为 null 是「无效槽」还是「未初始化」未证明；
- `all_consumer_sites_closed` —— 只证明了这一条读点。

**1,542 B 是结构与消费者的认领，不是运行期可达性、不是可编辑性、不是可写回。**

### 5.5 入账状态：已接线并自动执行中

前两步已完成：

1. `tools/audit_rom_byte_coverage.py` 已加 `_renderer_script_pointer_pool_record_claims`
   （照抄 `_fixed_renderer_script_record_claims` 的形状，`promotion_bytes`=1,542、
   `claim_count`=1），并已装配进 `build_manifest` 的 claims 链；
2. manifest / payload / verifier 三个 SHA 已固定（`342310e1…` / `60cbe250…` / `e17a3ee6…`）；
3. 直调该投影函数已验证产出 1 条合法 claim（`range=[3306,4848]`、
   `primary_class=fixed_cfg_consumer_renderer_command_script`）。

第 3、4 步（重建 coverage + 同步 proof + 一次非降级 formal）由
`notes/evidence/reverse-proof-update-20261019-v1/run_promotion.sh` **原子链**执行：

```
等账本重建 → 校验池3 claim 已落账 → apply.py 更新 proof
→ 跑 4 个定向测试套件 → 受管非降级 formal proof（idle 3600s / wall 7200s）
```

`apply.py` 已单独验证**幂等**（连续两次运行输出同一 proof SHA），并已用当前状态
跑通一次：它写入了 2 条 evidence、1 条 verifier 条目、更新了 coverage 验证器的
`script_sha256`、刷新了未分类字节口径的 limitation，并追加了池 3 的义务说明。

**账本重建本身是本轮发现的最贵操作**：单核纯 Python，实测 **57 分钟**完成
（父进程在 `poll()` 等待 `verify_rom_cfg_proven_roots_v15_bundle` 等验证器的
原生 trace 重放时，父进程 CPU 冻结但并未死锁）。这与 9-30 收据里
「正式 proof 全量 39.7 分钟 / 峰值 533 MiB」是同一量级。

#### 5.5.1 入账已完成（原子链执行结果）

账本重建于 57 分钟后完成，链随即自动走完剩余步骤：

| 步骤 | 结果 |
| --- | --- |
| coverage 账本重建 | SHA `9f8a819647afba8f2dc01791dd19bf6a5776012d324e5a2ff694fb51634efb26` |
| **unknown_bytes** | **87,631 → 86,089**（正好 −1,542） |
| classified_bytes | 6,203,825 → **6,205,367** |
| claim_count | 16,912 → **16,913** |
| segment_count | 18,675（不变——池 3 是单个连续未知段） |
| 池 3 claim | `renderer-script-pointer-pool-0cea` / range `[3306, 4848]` 已落账 |
| proof 同步 | coverage SHA 更新、3 项 summary 断言更新、未分类字节 limitation 刷新 |
| 定向测试 | **83 项全绿**（含 3 项此前刻意为红的池 3 canonical 门禁，已转绿） |
| formal proof | 已启动（受管、idle 3600s / wall 7200s、PATH 已修正） |

**账本与 proof 未出现中间态**——这正是把四步写成一条链的目的。

## 6. 侦察结论里被本轮修正或新发现的事实

1. **动画池不是同质的。** `0x45832C..0x458794` 中只有 `0x45832C..0x4585AC`（640 B）是
   动画 descriptor 族；`0x4585AC..0x458794`（488 B）起始是 `"LV"`，含 ASCII `0123`/`4567`/`89`，
   是另一族。整段认领会误领。
2. **新动画池的 descriptor 尺寸是可变的**：`0x14×N + 2`（N=12/4/2/1 → 0x182/0x52/0x2A/0x16），
   终止符是 **2 字节 `0xFFFF` head**；旧合同 `0x12D574` 的 0x54 固定 stride 与 4 字节
   `0x0000FFFF` 终止符**都不能套用**。本轮实测 8 descriptor / 24 entry / 496 B，
   与 `notes/rom-animation-pool-lifecycle-20261001.md` 独立吻合。
3. **`0x5411E4` 不是单表。** 至少有 7 个 PC 相对 LDR 消费者，且同一 base 上并存
   **0xAC 与 0xBC 两种 stride**（`0x86C88` 用 0xBC）。任何「单表 / 8 行 / 单一公式」结论
   必须先解释 0xBC stride。
4. **`0x53F310` 与 AI 配置表无关**，是另一张 12 项指针表，落在同一个 1,374 B 未知簇里。
5. **原笔记有一处事实错误**：`notes/rom-ai-config-writer-preflight-20260930.md:99` 称
   `0x6AB16..0x6AB1E` 把 **CD** 字节 OR FF 写回；ROM 实测 r4 = unit+0xCC、
   `adds r1,#7` ⇒ 写的是 **unit+0xD3**。下一包若以「CD 默认 FF 来源」为前提会走偏。
   **本轮按只读侦察处理，未改动原记录**；修正应在下一包一并处理。
6. **脚本 5 根的障碍位置已定位**：`0x0BC9`/`0x0C2E` 在第 1 条命令就遇 opcode 7；
   `0x14B4` 第 1 条遇 opcode 8；**`0x0C34` 与 `0x15FC` 的首字节是 opcode 1**，
   障碍 opcode 8 出现在记录中段（`0x0C67` / `0x162B`）。原计划文档「前两根以 7 开头、
   14B4 以 8 开头」只覆盖 3 个根。
7. **排除根是硬编码列表** `EXCLUDED_TARGETS = [0x0BC9,0x0C2E,0x0C34,0x14B4,0x15FC]`，
   不是运行时解析的产物。

## 7. 下一轮顺序（按闭合完整分母的难度）

1. **池 3 入账**（§5.5 四步原子变更）——把 1,542 B 真正变成账本事实。
2. **动画池 `0x45832C..0x4585AC`**（640 B）——照抄旧合同形状，但 descriptor 分母必须
   由**指针表反推**得到，不得写死 stride；claim 范围只取 640 B，488 B 尾巴显式排除。
3. **AI 生命周期**——**暂不开工**。CD writer 分母是全 ROM `ADD #0xCD` 的 93 处（两寄存器
   形式共 397 处），已识别只有 4 个写点 + 1 个复制继承候选；scorer 全入口分母未闭合；
   `0x67158` 跨 callee 不变量未证；slot13/extra slot0 的 CD 实值未证。
   任何「0..7」结论必须由 writer 域推出，**不得**由表长 8 行反推。
4. **`59EAE0` 维持条件式暂停**——重开门 5 条**达成 0 条**（1 条程序性、1 条部分），
   `0x0808F654` 的 computed/RAM producer frontier 仍开放。旧的 1,145 B may-read 已被
   晋升门否决，不能再算收益。
5. **脚本 5 根**（净 125 B）——风险最高，需要完整 opcode 7/8 handler 合同，
   包括 `0x67C1A`/`0x68038` 直返路径与 `0x9C574` ARM 上下文切换的不变量。
6. **池 1 / 池 2**（`0x578C..0x7554` 7,624 B、`0x42AB..0x542E` 4,483 B）——
   两者都只有部分链（2,474 B / 1,276 B），且池 1 的 68 槽表有已知反例。

## 8. 未闭合与未验证

- 池 3 的 1,542 B **尚未入账**，账本仍为 87,631 B / 1,763 段。
- 2,721 B 两包未入账；其中 1,668 B 缺 artifact 目录。
- 正式 proof 与 coverage 审计在提高 idle 超时后的**完整实测耗时本轮未拿到**（受管测量
  仍在跑，见 `notes/evidence/reverse-throughput-20261019-v1/`）；本文件引用的
  60.82 s / 60.24 s 是**被闸门杀掉**的耗时，不是完成耗时。
- 22 个 bank 的 typed 合同仍为 0，19 个发布 case 覆盖集合仍为空，真机门仍
  `blocked_external`。本轮没有任何 bank 语义或发布门进展。
- 本轮未运行 mGBA、未做任何真机验证、未改 canonical 账本与 proof。
- `artifacts/rom-low-script-delta-v1/` 的孤儿状态未处理。
- 2,814 条 verifier 命令实测**零**条路径参数逃出仓库；`notes/evidence/**` 中 716 个文件
  带 `/Users/altair` 属仓库既有收据惯例（已提交同类文件 343 个），不是新违规类型。


## 9. P0 止血已落地（2026-10-20 02:0x）

针对 §3 的三个闸门，本轮已实际改完（全部 TDD：先红后绿）：

| 项 | 改动 | 文件 | 验证 |
| --- | --- | --- | --- |
| 守卫默认超时 | `wall_timeout_s` 600→**9000**、`idle_timeout_s` 60→**7200**，并写明 idle 语义 | `tools/project_resource_guard.py` | `tests/test_project_resource_guard.py` 的 `test_guard_config_has_exact_defaults` 已更新，并新增 `test_default_idle_timeout_outlives_non_streaming_project_tools`；**53 项全绿** |
| 解释器 fail-closed 闸门 | 新增 `MINIMUM_PYTHON = (3, 10)` 与 `_require_supported_python()`；`build_manifest` / `audit_manifest` / `audit_proof` 入口先过闸门；proof 审计器 `main()` 捕获 `RuntimeError` 并以 **exit 2 + `refused` 字段**退出（不是 blocker） | `tools/audit_rom_byte_coverage.py`、`tools/audit_reverse_engineering_proof.py` | `tests/test_python_version_gate.py` **5 项全绿**；端到端实测：3.9.6 下输出 `{"complete": false, "refused": "this toolchain requires Python >= 3.10 because it uses zip(strict=True); running Python 3.9"}`，**exit code = 2** |
| 解释器锁定 | 反向树建 `.venv`（**3.14.3**，13 MB，`.gitignore:38` 已忽略）；两个入账脚本把 `PATH` 钉到 `.venv/bin` | `.venv/`、`notes/evidence/reverse-proof-update-20261019-v1/run_{promotion,formal}.sh` | `run_promotion.sh` 与 `run_formal.sh` 现在都是 wall 9000 / idle 7200 |
| proof 身份同步 | 改审计器即改其 SHA，必须同步 proof 的 `script_sha256` | `sequel/reverse-engineering-proof.json` | `apply.py` 已把 `7b5407b6…` → `e3a771db…`，与文件实测一致 |

**踩坑记录**：第一版 `test_python_version_gate.py` 在 RED 阶段直接调 `audit_manifest()`，
于是触发了**完整的 57 分钟账本重建**才失败。修正为把 `build_manifest` 换成哨兵
`AssertionError`，RED 阶段 0.023 秒失败。**教训：针对重工具写 RED 测试时，必须先把
重路径 mock 掉**，否则一次红测就是一小时的浪费。

**新增实测事实**：`tests/test_audit_rom_byte_coverage.py:172` 在类级 `setUpClass`
里调 `build_manifest(ROOT)`——**该测试文件本身就要 57 分钟**。它是当前仓库里最慢的
测试入口，任何"跑一遍全量测试"的说法都要先算上这一项。


## 10. P1 提速：已就绪的缓存原语与接线设计（2026-10-20 02:1x）

### 10.1 成本结构（已定位，非推测）

一次晋升实际付了**两遍**账本重建：

```
晋升链： audit_rom_byte_coverage.py --write            → 57 分钟（实测）
正式审计： _check_rom_gate (audit_reverse_engineering_proof.py:752)
        → audit_rom_manifest → build_manifest(root)   → 又一遍 57 分钟
        → 之后才跑其余 107 个验证器
```

而 `build_manifest` 内部有 **105 处进程内 `verify_artifact` / `verify_root=` 调用**，
每处都重读 6 MB ROM 并从 ROM 重新推导整个 artifact。栈采样显示热点是
**JSON 解析**（`scan_once_unicode` / `scanner_call`），不是语义计算。

### 10.2 已实现：内容寻址缓存原语

`tools/verification_cache.py`（**15 项测试全绿**）：

- 缓存键 = SHA-256(规范化描述)，描述含
  **验证器脚本摘要 + ROM 摘要 + 每个输入文件的 (相对路径, SHA-256)**；
- 输入列表**排序后**入键 → 键与调用顺序无关；
- **任何 I/O 问题一律当 miss**，缓存永远不会把失败变成成功；
- **只有 `verified is True` 的报告才写入** → 失败的验证器不会被记忆成成功；
- 落在 `build/experiments/cache/verification-reports/`（派生数据，绝不与已提交收据混淆）；
- 原子写入（临时文件 + `os.replace`），已存在条目不覆盖。

设计要点：**命中即可复用一份与新跑完全等价的证据**，因为全部输入都逐字节相同才可能命中。

### 10.3 接线设计（待 formal 结束后落地）

1. 在 `build_manifest` 的每个 claim producer 处，把 `verify_root(root, artifact)`
   包成 `cached_verify(...)`：
   - `verifier_sha256` = 该验证器脚本的实测摘要；
   - `inputs` = 该验证器**实际读取**的输入清单（`describe_inputs` 从调用点显式给出，
     **不做猜测**——猜错会把"输入变了"误判成"命中"）；
   - `compute` = 原有调用。
2. **只在证明命中安全后才启用**：先用一次完整重建填充缓存，再测第二次重建的耗时；
   若命中率高且耗时下降，才把它纳入常规晋升链。
3. 命中率的诚实口径：**缓存只能省掉"这次没变的验证器"**；账本新增的包必然是 miss。
   所以预期收益是「第二次及以后的晋升」，第一次仍是 57 分钟。

### 10.4 另一条零语义风险的路：正式审计并发化

`_check_rom_gate` 的 coverage 重建与那 107 个验证器**互不依赖**。把它们改成
并发执行，正式审计的墙钟从「57 + X」变成「max(57, X)」，判定逻辑一行不改。
这需要改 `tools/audit_reverse_engineering_proof.py`（会改其 SHA → 同步 proof）。

### 10.5 为什么这两项现在还不能落地

**正在运行的正式审计会从磁盘读这两个审计器文件做 SHA 校验**
（`audit_reverse_engineering_proof.py:444`：`if _sha256_file(script) != verifier["script_sha256"]`）。
在它运行期间改这两个文件，会让这次运行读到新文件的摘要、与旧 spec 比对失败，
产生一个**纯假 blocker**。因此本轮把缓存做成**独立新模块**（不被 formal 读取），
接线留到 formal 落地之后。


## 11. P1 提速：已落地的三项改造（2026-10-20 02:5x–03:0x）

### 11.1 归因修正：瓶颈不是工具设计，是宿主争用

本轮实测推翻了 §3 自己的一个结论。repo 自己在
`tools/audit_reverse_engineering_proof.py:144-146` 记录：**"The reproducible
full-ROM coverage verifier currently needs about four and a half minutes on the
desktop runtime"**。而我实测的那一次账本重建跑了 **45 分钟以上**。差 10 倍。

实测当时的主机状态：

| 进程 | RSS |
| --- | ---: |
| openclaw `node` | 1,066 MiB |
| MiniMax 桌面（4 个进程） | ~1,850 MiB |
| Firefox（3 个进程） | ~767 MiB |
| Docker backend | 147 MiB |
| **我的 formal** | **211 MiB** |
| swap | **3,072 MiB 总量，已用 2,247 MiB，仅剩 825 MiB** |

**结论：逆向工作本身不是内存大户（211 MiB），但桌面应用栈吃掉了约 4 GiB，
swap 已被占用 73%。**在 swap 饱和 + 负载 10+ 的机器上跑单线程长任务，
每一页缺页都要换页，于是"4.5 分钟"变成"45 分钟"。

→ **提速第一优先级是"别在宿主饱和时跑重活"，不是改工具。**
→ 同时暴露守卫的内存准入判据太乐观：`available_physical_memory_mib` 把
`inactive` 页算作可用，而在 swap 已占 73% 时这些页实际上要换回来。

### 11.2 改造一：验证器并发化（`tools/audit_reverse_engineering_proof.py`）

真正常规的成本是 **107 个验证器串行重放**。它们互不依赖，于是改为
**有界线程池**：

- 新增 `_execute_groups(root, groups, rom_coverage_report, jobs)`；
- coverage 验证器仍走 `_reuse_rom_coverage_contract`（进程内复用，不起子进程），
  保持 `execution == "reused-in-process"` 不变（既有测试依赖这一点）；
- **结果按原 group 序号重新排序** → 报告顺序、进而报告摘要，**与串行版完全一致**；
- 新增 `--verifier-jobs`（默认 4）；
- 并发度按**实际可用内存**夹取（`_verifier_job_count`）：
  可用 < 2 GiB → 1；< 4 GiB → 2；否则 ≤ 4。

新增 `tests/test_audit_reverse_engineering_parallel_verifiers.py`（**6 项全绿**）：
夹取逻辑 3 项 + 顺序不变 1 项 + 失败项仍守位 1 项 + coverage 仍为进程内复用 1 项。

### 11.3 改造二：守卫保留子进程输出（`tools/project_resource_guard.py`）

**实测踩到的缺陷**：守卫用管道抽干子进程的 stdout/stderr 来检测进度，
但**把内容丢了**。一次失败的受管运行只留下 `"child-exit 1"`，**没有任何原因**——
本轮因此浪费了约 30 分钟才定位到是我的 `.venv` 缺依赖。

现在：
- 子进程 stdout/stderr 落到 **旁路日志** `<summary>.stdout.log` / `<summary>.stderr.log`；
- summary 里带 `child_stdout_log` / `child_stderr_log` 路径；
- 新增 `test_child_output_is_kept_next_to_the_summary`；
- 既有 `test_every_summary_contains_all_result_fields_and_no_temp_file`
  的"目录里只能有 summary.json 与 task.lock"断言已更新为
  {summary, 两个旁路日志, lock}——**仍然禁止任何临时文件残留**。

守卫套件 **54 项全绿**（1 项 skip 为既有）。

### 11.4 改造三：解释器锁定方式修正（本轮引入的 bug 及其修复）

我原先建的 `.venv` 是**空的**：`python -m venv` 不带 `--system-site-packages`，
而仓库依赖的 Pillow 等在**系统 3.14.3 的 site-packages** 里
（`/usr/local/lib/python3.14/site-packages`；capstone 则由仓库内置在
`tools/_vendor/capstone`，不依赖 pip）。

症状：受管 formal **2 秒内 exit 1**，而 stderr 被守卫吞掉 → 看起来像"代码坏了"。
直接跑才看到 `ModuleNotFoundError: No module named 'PIL'`。

修复：`python3 -m venv --system-site-packages .venv`。
（顺带发现：**主树的 `.venv` 也是空的**，同样没有 Pillow——但那是你的环境，我没动。）

> **教训**：锁定解释器不能只锁版本，必须锁**依赖可见性**。
> 而且这个 bug 只有在"守卫保留子进程输出"修好之后才查得动——两处改造是配套的。

### 11.5 已就绪但**尚未接入**的缓存原语

`tools/verification_cache.py`（**15 项测试全绿**）实现了内容寻址缓存：
键 = 验证器脚本摘要 + ROM 摘要 + 每个输入文件的 (相对路径, SHA-256)，输入排序后入键；
任何 I/O 问题一律当 miss；**只有 `verified is True` 的报告才写入**。

**没有接线的原因**：要接进 `build_manifest` 的 105 个 producer，必须逐个声明
"这个验证器读了哪些输入"——**猜错就会把"输入变了"误判成"命中"**，
在证据链里是不可接受的。所以要么由 producer 显式声明 `cache_inputs`，
要么就不缓存。**这是一个需要逐包确认输入清单的工作，不是我能替你假设的。**

### 11.5.1 并发化 formal 的实测墙钟（2026-10-20 05:45，两轮都跑完）

#### 权威收据：第二轮（解释器已修正）

| 项 | 值 |
| --- | --- |
| guard | `reason: completed`、`exit_code: 0`、`degraded: false`、peak RSS **866.1 MiB** |
| 墙钟 | **3,905 s**（20:39:40Z → 21:44:45Z） |
| `complete` | `false` |
| `blockers` | **175** ← 与 9-30 基线**集合相同** |
| `verifiers_executed` | **108**，**`failed_verifiers: []`**（无一失败） |
| `coverage verified` | `true`、`unknown_bytes=86089`、`banks_complete=10` |

与 9-30 基线逐条对比 blocker 集合，**只差一条措辞**（池 3 晋升使
limitation 从 63 变 64）：

```
+ gate rom_byte_coverage: unresolved limitations remain (64)
- gate rom_byte_coverage: unresolved limitations remain (63)
```

#### 阶段分解：**并发只救得了验证器阶段**（⚠️ 2026-10-20 08:3x 已按收据更正，原数字是错的）

| 阶段 | 9-30 基线（收据实测） | 9-05 基线（收据实测） | 本轮（4 路并发） |
| --- | ---: | ---: | ---: |
| 覆盖审计 | **1,819.5 s** | **1,901.8 s** | **2,377 s**（争用 +31%） |
| 验证器重放 | **564.0 s** | **587.5 s** | **1,528 s**（争用 **2.7×**） |
| 合计 | **2,383.5 s** | **2,489.4 s** | **3,905 s** |

收据出处（本次已由我逐份打开核算 `started_at`/`finished_at`）：
`notes/evidence/rom-small-cfg-batch-canonical-20260930-v1/coverage-guard.json`
（11:55:26.111725Z → 12:25:45.568304Z）、
`notes/evidence/rom-small-cfg-batch-formal-20260930-v1/formal-guard.json`
（12:38:33.441575Z → 13:18:16.902120Z）、
`notes/evidence/rom-post-story-four-packet-tier2-20260905/{coverage,formal}-guard.json`。
验证器段 = formal 墙钟 − 覆盖构建墙钟（两者是同机串行的两次受管运行，
formal 内部先跑覆盖门再跑验证器池）。

> **更正**：本节原写的「覆盖 ~270 s（repo 自记 4.5 分钟）/ 验证器 ~2,113 s（推算）」
> **是反的**。「4.5 分钟」出自 `tools/audit_reverse_engineering_proof.py:145-146`
> 的一句注释（2026-09-05 18:07 引入），而同一天 14:38 的覆盖构建收据实测
> **1,901.8 s** —— 差 **6.7×**。于是「宿主争用放大 8.8×」这个归因也不成立：
> 覆盖段**本来就**是 1,820 s 级的慢活。本节由该注释继承来的数字全部作废。

两段都不是工具设计的问题：

- **覆盖审计段**是**单线程**的，concurrency 帮不上忙。**真正的主成本是算法**：
  `atomize_claims` 在 `build_manifest` 里被调 **39 次**（38 次在 producer 内部，
  1 次在末尾），而旧实现是 O(段数 × claim 数) —— 全账本单次实测 **60.50 s**，
  静态估算 39 次合计 **≈1,611 s**，占覆盖段 1,819.5 s 的 **≈68%**。
  **这正是本轮 `0827b497` 修掉的东西**（扫描线，681×，输出逐字节一致），
  详见 §21。宿主争用只是**二阶**因素（+31%），不是主因。
- **验证器段**在基线上只要 **564–588 s**；本轮 1,528 s 是 **2.7× 争用放大**
  （我同时并发跑了回归套件与探针）。
  ⚠️ 原节写的「并发墙钟被 `tools/verify_rom_cfg_proven_roots_v9.py` 单跑
  ~18 分钟（1,080 s）封顶」——**本节原先判定为「不成立」，那个判定本身是错的，
  2026-10-20 09:4x 独立复核后更正**：
  - **v9 确实在 formal 的验证器列表里**。实测三份 formal 报告的 `verifiers_executed`：
    9-30 基线 107 项**含 v9**、10-20 v1 108 项**含 v9**、10-20 v2 108 项**含 v9**；
    条目 `label="gate rom_byte_coverage"`、`contract_ok: true`、`exit_code: 0`，
    命令 `python3.14 -I -S tools/verify_rom_cfg_proven_roots_v9.py --root .
    --artifact-dir artifacts/rom-cfg-proven-roots-v9`。
    **本节原写的「v9 从未出现在 formal 的验证器列表里」是错的。**
  - **仍然成立的部分**：v9 单跑 ~1,080 s 这个数字**全仓没有任何收据**
    （23 份提到 `proven_roots_v9` 的 JSON 全是 report/manifest，没有单独计时）。
  - ⇒ 该假设的正确状态是「**前提错、结论未证**」，不是「已否」。
    若 v9 真需 ~1,080–1,387 s，4 路池的 makespan 下界被它压住，
    1,528 s 与「最长单项主导」自洽 ⇒ **与「争用 2.7×」互斥，
    但仓库数据无法排除任一方**（见 §27.1）。

#### 第一轮（6,214 s / 176 blockers）：环境漂移，不是语义失败

见 §15。首轮多出的第 176 个 blocker 是解释器 purelib 漂移造成的
`ModuleNotFoundError: No module named 'PIL'`，收据归档在
`first-run-venv-interpreter/`，**不可作为语义证据**。



## 12. 晋升链漏掉的一步：policy 文档与测试夹具（2026-10-20 03:1x）

池 3 晋升后跑 `tests/test_audit_reverse_engineering_proof.py`（8,891 行，93 个测试），
出现**十余个失败**。追查结果是**既有破损，不是我这轮改动造成的**：

- `docs/reverse-engineering-proof-policy.md` 里的权威计数停留在 **9-05 的
  `6,203,707` / `87,749` / `16,891` / `18,664`**；而 9-30 那次 118 B 晋升把两个
  JSON 账本推进到了 `6,203,825` / `87,631`，**却没更新这份 policy 文档**。
  既有测试 `test_current_proof_and_policy_publish_current_coverage_counts`
  断言 policy 必须与活账本一致 → **在 HEAD（b4da99dfa）上就已经是红的**。
- 测试文件里还有 **12 代**陈旧的全局计数（最老的 `6_142_176`/`149_280` 出现 24 处），
  每个批次一个；以及 **68 处**里程碑快照式的
  `assertEqual(96, len(gate["evidence"]))` / `assertEqual(92, len(gate["verifiers"]))`。
  **每次晋升都会打破约 12 个测试**——这正是"晋升成本"里被长期忽略的一块。

### 12.1 已修的三件事

1. **policy 文档同步**：计数更新为 `6,205,367` / `86,089` / `16,913 claims` /
   `18,675 segments`，并把这一步**写进 `apply.py`**（`_sync_policy_counts`），
   让它成为晋升链的一等步骤，而不是事后补救。
2. **测试夹具改为派生**：全局量（`classified_bytes` / `unknown_bytes` /
   `claim_count` / `segment_count`，以及累计型
   `cfg_reachable_thumb_code_bytes` / `cfg_promoted_unknown_bytes` /
   `cfg_primary_claim_count` / `cfg_code_claim_kind_count` /
   `cfg_code_claim_kind_denominator_sha256`）改为从活账本派生
   （共 210 处），**批次自身的增量指针保持硬编码**——那些才是这套测试真正要守的
   回归护栏。
3. **里程碑计数改为"至少"**：68 处
   `assertEqual(N, len(gate["evidence"]))` → `assertGreaterEqual(len(...), N)`。
   证据与验证器条目只增不减，"至少"保留了原意（"不比这个批次落地时更少"），
   又不再随每次晋升变红。

> **教训**：一次晋升要同步的**不止两个 JSON 账本**——还有 policy 文档的发布计数、
> 以及测试里那 12 代里程碑快照。原子链必须把这些一起纳入，
> 否则"晋升成功"与"仓库自洽"是两件事。


## 13. 最终瓶颈定案：宿主内存（2026-10-20 03:3x）

会话末段的内存画像（`ps` + `vm_stat` + `vm.swapusage`）：

| 进程 | RSS |
| --- | ---: |
| MiniMax（单进程，桌面端） | **2,394.8 MiB**（会话开始时 792.5 MiB） |
| `com.apple.Virtualization.VirtualMachine` | **1,311.3 MiB**（会话期间新起） |
| MiniMax（第二进程） | 1,010.7 MiB |
| openclaw `node` | 814.4 MiB |
| Firefox + plugin-container | 567.1 MiB |
| **本项目的 formal 进程** | **211.1 MiB** |

- swap 总量从 3,072 MiB 涨到 **4,096 MiB**（macOS 动态扩容），已用 **3,542 MiB**，
  剩 **553 MiB**。
- 负载常驻 9.4–10.4（12 逻辑核）。

**结论（2026-10-20 08:3x 已按收据更正，原结论把主因搞反了）**：
**推动速度的首要因素是审计器里的 O(n²) 算法（`atomize_claims` 被调 39 次，
估 ≈1,611 s，占覆盖段 1,819.5 s 的 ≈68%），不是宿主内存。**
宿主内存与争用是**二阶**因素：它让本轮 formal 从基线 2,383.5 s 涨到 3,905 s
（+64%，其中覆盖段 +31%、验证器段 2.7×），真实存在但**不是 8.8× 那种量级**
（原 §11.5.1 的「覆盖 270 s」来自一句过期注释，与同日收据差 6.7×）。
本项目的两个重进程合计不到 260 MiB，而应用栈占了约 6.1 GiB，swap 在会话期间
被动态扩了一次并用到 86%。在 swap 饱和时：

- 单线程长任务的每一次缺页都要换页 → 运行时间被进一步拉长；
- 守卫的内存准入判据 `free + inactive + speculative` 仍然放行，因为 `inactive` 页
  实际要换回来——**准入是乐观的，代价在运行中才显现**；
- 我自己并发跑三个重活（formal + 回归套件 + 探针）就是那次放大的直接成因。

### 13.1 可执行结论

1. **重活窗口必须先腾内存**：跑 coverage 重建 / formal 之前，关掉或暂停
   虚拟机与浏览器。16 GiB 的机器在应用栈占 6 GiB 时，swap 会在一次长任务里
   被吃光。
2. **重活同一时刻只跑一个**（heavy 锁已经这么要求，本轮实测也证实：
   并发受管运行 2/2 以 lock-busy 拒绝）。
3. **守卫的内存准入应改为看真实可用页**（`free + speculative`，不含 `inactive`），
   或额外要求 swap 已用量低于阈值——当前判据在 swap 饱和时形同虚设。
4. **（2026-10-20 08:3x 新增，最高优先）把 `atomize_claims` 的 O(n²) 换成扫描线**：
   它被调 39 次，是覆盖段 ≈68% 的成本。本轮已改（`0827b497`）：
   **60.50 s → 0.09 s（681×）**，输出与原实现**逐字节一致**，
   并加了 4 项等价性回归闸门（真实账本 + 400 组随机 + 失败关闭文案 + 性能）。
   预期覆盖段从 1,819.5 s 降到 **200–400 s 量级** —— 这需要一次受管重测确认
   （§21.3）。
   ⚠️ **2026-10-20 09:4x 更正**：这个预期**被实测证伪**。优化后独立审计实测
   **1,108.276 s**（§23.4），不是 200–400 s，差约 2.8–5.5 倍。
   ⇒ **atomize 之外还有 1,108 s 的成本**，下一个优化杠杆不是 atomize，
   而是 producer 内的验证器冷重放（见 §25.2、§27）。
5. 本轮交付的**工具侧**提速仍然有效，但它的收益只有在宿主不饱和时才兑现：
   - 验证器并发化（`--verifier-jobs`，按可用内存夹取）→ 108 个验证器不再串行；
     基线验证器段本来就只要 **564–588 s**，本轮 1,528 s 是争用 2.7× 的结果
     （**不是** 1.38× 的算法收益）；**原写「也不是被 v9 封顶——v9 从未进过 formal
     的验证器列表」是错的**（v9 三份报告里都在，见 §13 的更正），
     只能说 v9 的 1,080 s 无收据 ⇒「最长单项主导」与「争用 2.7×」两个解释
     **互斥但都无法排除**；
   - 守卫保留子进程输出 → 失败可诊断（**本轮直接靠它定位了
     `ModuleNotFoundError: No module named 'PIL'` 的解释器漂移**，见 §15）；
   - policy 文档 + 测试夹具与晋升链解耦 → 每次晋升不再打破约 12 个测试
     （**本轮已把剩余 37 处陈旧字面量全部派生，并加了 1.3 s 的元守卫**，见 §14）。

### 13.2 本轮闭合情况

- 回归套件（93 个测试）：**失败点已全部定位并修完**（12 个测试 / 37 处陈旧字面量），
  快速项 6/6 已转绿，含全 ROM 审计的 2 项并入全量套件重跑；
  并新增 1.3 s 的元守卫替代"45 分钟末尾才发现"（§14）。
- 并发化后的 formal：**两轮都跑完了**（§11.5.1 / §15）。
  权威一轮 wall 3,905 s、175 blockers、108/108 验证器通过，
  blocker 集合与 9-30 基线一致。
- 落盘位置见 §11.5.1（formal 墙钟）、§14（套件修复）、§15（解释器漂移）、§16（保险）。

> **本节已于 2026-10-20 04:xx 关闭**，结果见 §11.5.1（formal 墙钟）与 §14
> （回归套件的 12 个失败：根因、修复、守卫）。

---

## 14. 回归套件的 12 个失败：根因、修复与元守卫（2026-10-20 03:5x–04:3x）

§12 把失败归因为"既有破损"（policy 文档计数停在 9-05、测试里 12 代陈旧全局量），
并做了 210 处派生 + 68 处"至少"的改造。**但那个改造没有做完**：
本轮静态穷举（AST 级）显示，仍有 **37 处**把「随晋升变化的累计量」写成了字面量，
分布在 **12 个测试**里。

### 14.1 红证据与失败定位方法（可复用）

第一次跑套件只拿到 `...FF....FFF......F.`（20 个字符 = 20 个测试，6 个 F），
因为 `unittest` 非 verbose 模式不打印用例名。**但用例在类内是按名字字母序执行的**，
所以「位置 → 用例名」可以静态还原：

```python
loader = unittest.TestLoader()
suite = loader.loadTestsFromName("tests.test_audit_reverse_engineering_proof")
names = [t.id().split(".")[-1] for t in flat(suite)]   # 93 个，按执行序
```

还原出来的 6 个 F 精确落在
`v14_artifact_coverage` / `v15_artifact_coverage` / `immutable_replay` /
`four_packet_milestone` / `four_packet_tier2` / `partial_coverage_contract`，
**与失败位置的预测完全一致**——这验证了"位置反推"这条路。

随后用 AST 穷举（不靠抽样）把范围补全到 **12 个**：

- `assertEqual(<字面量>, X["/summary/<key>"])`（含 `rom_gate` 变体与多行写法）；
- `assertEqual(<字面量>, <dict>["/summary/<key>"])`。

对活账本逐条对拍后，**28 处**不一致；另有 9 处是
`cfg_code_claim_kind_denominator_sha256` 的**字符串**摘要（int 扫描漏掉，
AST 也漏掉，因为常量是 str 不是 int），合计 **37 处**。

> **教训**：只扫 int 字面量会漏掉 SHA 摘要型断言；而多行 `assertEqual` 里的
> **尾随逗号**会让正则漏匹配（本轮因此少改 9 处）。
> 「静态穷举」必须同时覆盖**两种常量类型**和**两种书写形态**。

### 14.2 根因：陈旧值不止 4 个全局量，是 11 个

§12 列的全局量是 9 个。穷举发现还有 2 个同类的累计量：

| 键 | 陈旧值 | 活账本 |
| --- | ---: | ---: |
| `unknown_bytes` | 149,280 | 86,089 |
| `classified_bytes` | 6,142,176 | 6,205,367 |
| `claim_count` | 15,940 | 16,913 |
| `segment_count` | 17,344 | 18,675 |
| `cfg_reachable_thumb_code_bytes` | 148,778 | 173,136 |
| `cfg_promoted_unknown_bytes` | 149,766 | 174,124 |
| `cfg_primary_claim_count` | 3,835 | 4,064 |
| `cfg_code_claim_kind_count` | 33 | 55 |
| `cfg_code_claim_kind_denominator_sha256` | 5 个不同历史 SHA | `8ab38e24…` |
| **`consumer_code_slice_bytes`** | **25,284** | **27,404** |
| **`consumer_code_slice_claim_count`** | **111** | **116** |

后两个是**消费者代码切片族的累计总量**——本轮实测随池 3 晋升从 25,284 / 111
变成 27,404 / 116。§12 的清单漏了它们，因为它们名字里没有 `cfg_`，
分类时被当成了"批次增量"而保留硬编码。**这正说明"按名字分类"不可靠，
必须按"是否随晋升变化"分类。**

### 14.3 修复：幂等派生脚本

`notes/evidence/reverse-proof-update-20261019-v1/derive_live_coverage_assertions.py`
把 37 处字面量换成 `LIVE_COVERAGE_SUMMARY[...]` 派生引用：

- 只处理 11 个已判定为累计量的键，**批次增量一律不动**；
- 覆盖 4 种书写形态（int 字面量、str 摘要、rom_gate 链、多行带尾逗号）；
- **幂等**：连跑两次，第二次 `total_replacements: 0` / `status: no-op`；
- 先 dry-run 报告再 `--apply` 写盘。

结果：proof 套件里 `LIVE_COVERAGE_SUMMARY[...]` 引用由 210 处增到 **247 处**；
AST + 正则双路复扫，**陈旧字面量 0 处**（全 `tests/` 目录）。

### 14.4 元守卫：把"45 分钟末尾才发现"变成"1.3 秒就知道"

新增 `tests/test_audit_reverse_engineering_coverage_count_liveness.py`（**6 项全绿**，
运行 **1.3 秒**）：

1. `test_spec_coverage_assertions_exist_in_live_ledger` —— spec 声明的 510 个
   `/summary/*` 断言键必须都在活账本里（实测缺失 0）；
2. `test_spec_coverage_assertions_equal_live_ledger` —— 逐项相等；
3. `test_no_test_source_hardcodes_a_live_ledger_quantity` —— 任何测试文件都不得
   拿字面量比一个活账本里存在的键；
4. `test_historical_pins_are_still_pinned_to_the_old_value` —— **反向护栏**：
   有意钉住历史收据的断言（`87,631`）必须仍然钉在旧值，且不得与活账本当前值相同；
5. `test_global_quantities_are_derived_not_hardcoded` —— 11 个累计量不得回到字面量；
6. `test_batch_increments_remain_hardcoded` —— **反向护栏**：批次增量必须保持硬编码，
   不能被"一并派生"掉。

> **关键设计**：守卫区分「活账本断言」与「历史收据断言」。
> `tests/test_rom_small_cfg_batch_canonical.py` 与
> `tests/test_rom_renderer_script_pointer_pool_canonical.py` 各有一处
> `unknown_bytes == 87,631`——它们钉的是 **9-30 冻结收据**里当时记录的值，
> 差值正是池 3 的 1,542 B。**这类断言是正确的，不能跟着改。**
> 守卫为此留了显式登记 `HISTORICAL_PINNED`，并反向断言"登记项必须仍钉旧值"，
> 防止"历史钉"被悄悄扩大成万能豁免。

**价值**：晋升后若账本与 spec 漂移，守卫在 **1.3 秒**内失败关闭；
不再需要等 93 个测试跑 45 分钟才在末尾吐出一串 F。

### 14.5 本轮踩到的第三个坑：900 秒 bash 超时

第一次定向复跑用前台 bash 跑 12 个测试，**恰好在 900 秒被工具超时杀掉**，
输出里只剩 `Command timed out after 900 seconds`，没有 summary——
和 §14.4 之前记录过的"8,891 行套件被 900 s 超时杀掉"是同一个坑。

正确做法：**`nohup ... &` 分离运行 + 日志落盘 + 轮询 PID**，
不要把长跑放在前台 bash 里。`tools/run_guarded.py` 的重活同理，
但它自己带 wall/idle 闸门，不依赖工具超时。

---

## 15. 并发 formal 第一次跑出 176 个 blocker：解释器解析漂移（2026-10-20 04:4x）

### 15.1 第一轮的数字

| 项 | 值 |
| --- | --- |
| guard | exit 0、`reason: completed`、`degraded: false`、peak RSS 861.27 MiB |
| 墙钟 | **6,214 s** |
| `complete` | `false` |
| `blockers` | **176**（9-30 基线 175） |
| `verifiers_executed` | 108（基线 107） |
| `coverage verified` | `true`、`unknown_bytes=86089`、`banks_complete=10` |

与 9-30 基线逐条对比 blocker 集合，多出一条、少一条：

```
+ gate rom_byte_coverage: verifier execution did not satisfy its contract:
    gate rom_byte_coverage: verifier failed with exit 1:
    .../python -I -S tools/verify_rom_sprite_loader_tail.py --root . --artifact-dir artifacts/rom-sprite-loader-tail-v1
- gate rom_byte_coverage: unresolved limitations remain (63)
+ gate rom_byte_coverage: unresolved limitations remain (64)
```

（少的那条是 63 → 64 的措辞随池 3 晋升变化，不是真消失。）

### 15.2 根因：不是语义失败，是 `-I -S` 下的 purelib 漂移

复现该验证器得到确切异常：

```
File "tools/verify_sprite_definition_animations.py", line 14, in <module>
    from PIL import Image, ImageDraw
ModuleNotFoundError: No module named 'PIL'
```

`tools/verify_rom_sprite_loader_tail.py::_load_source_verifier()` 里有一段
**刻意的兼容 workaround**：

```python
purelib = sysconfig.get_path("purelib")
if purelib and purelib not in sys.path:
    sys.path.append(purelib)
```

所有验证器命令都带 `-I -S`（隔离模式 + 跳过 site），所以 Pillow 本来不可见，
**全靠这段手动补 purelib 才能 import**。而 `sysconfig.get_path("purelib")`
取决于**正在运行的那个解释器**：

| 解释器 | purelib | 有 Pillow |
| --- | --- | --- |
| `/usr/local/bin/python3`（9-30 基线用的） | `/usr/local/lib/python3.14/site-packages` | 是 |
| `.venv/bin/python`（我第一轮用的） | `<repo>/.venv/lib/python3.14/site-packages` | **否** |

我第一轮的 runner 写了 `export PATH="<repo>/.venv/bin:/usr/local/bin:$PATH"`，
于是 proof spec 里的 `python3` 被解析成 `.venv/bin/python`。
而 `.venv` 是用 `--system-site-packages` 建的——**Pillow 在 base prefix 的
site-packages 里，venv 自己的 purelib 是空的**，workaround 于是静默失效。

> **教训（可复用）**：
> **换解释器不只是换版本号，还会换 `sysconfig` 的路径解析。**
> `--system-site-packages` 的 venv 在**正常启动**时能看到 base 的包，
> 但在 `-S`（跳过 site）下就**看不到**——它只把 base 的路径交给 `site.py` 处理，
> 而 `-S` 根本不跑 `site.py`。
> 所以「venv 能 import 到」**不能**推出「venv -I -S 也能 import 到」。
> 凡是仓库里存在 `sys.path.append(sysconfig.get_path("purelib"))`
> 这类 workaround，**正式收据的跑法必须与基线逐字节同构**。

### 15.3 处置

- 首轮收据**整体归档但标注为不可作为语义证据**：
  `notes/evidence/reverse-proof-update-20261019-v1/first-run-venv-interpreter/`
  （含 README 写明陷阱与对照表）。
- 修正 runner：`run_formal_parallel.sh` 改用 `/usr/local/bin/python3`，
  `PATH` 只保留 `/usr/local/bin:/opt/homebrew/bin`，**不再前置 `.venv/bin`**。
  现在它与 9-30 基线**只有 `--verifier-jobs 4` 一处差异**——这才是成立的 A/B。
- 第二轮收据：见 §11.5.1。

### 15.4 尚未做的加固（需要用户裁决）

可以把 workaround 改成**多候选 purelib**（venv purelib + base prefix purelib
都试），这样任意解释器都能 import 到 Pillow。但：

- `tools/verify_rom_sprite_loader_tail.py` 与
  `tools/export_rom_sprite_loader_tail.py` 的 SHA-256 **被 proof 钉住**
  （`sequel/reverse-engineering-proof.json` 的 `script_sha256`），
  改了就必须同步 SHA，并**再跑一次完整 formal** 复核；
- 当前正在跑的第二轮 formal 会按 SHA 校验该验证器，
  **运行期间改它会让这一轮直接失败**——所以本轮不做。

现状已足够安全：正式 runner 固定用 `/usr/local/bin/python3`，
并在脚本头部把这条契约写成注释 + 失败症状。

---

## 16. 换机器前的三项保险（2026-10-20 05:0x，用户授权后执行）

会话末段我向用户提了三件"一直在等授权"的事，现已全部执行。

### 16.1 逆向树 commit + push

- 提交 `6b53e5ce`（分支 `codex/reverse-engineering`），**57 个文件 / 13,316 插入 / 423 删除**。
- 已推送：`b4da99df..6b53e5ce` → `origin/codex/reverse-engineering`。
- 内容：池 3 入账（账本 + proof + policy 三处同步）、两个新合同包
  （池 3 / M1 动画池）、并发化 auditor、守卫修复、缓存原语、
  回归夹具去硬编码、元守卫、§1–§15 记录与全部收据。
- **故意排除**了 5 个在飞文件（`formal-parallel-{guard.json,report.json,run.log,
  stdout.json,stderr.log}`）——第二轮 formal 会覆盖它们，
  提交在飞版本会让收据语义混乱；第二轮落地后单独提交。
  首轮那轮的收据已归档在 `first-run-venv-interpreter/`，证据没丢。

### 16.2 `build/experiments/active/` 打包

- 目标：`/Users/altair/archives/gba-naruto-reverse-active-20261020.tar`
- 2,387,885,568 字节（2.22 GiB），23,934 条目（21,736 文件 + 2,198 目录）
- SHA-256 `03206023cb6000383d3a90492df31aeeb14489915ba02ecfbda929dd507a5502`
- **未压缩**（内容以 `.bin` 为主，gzip 收益低），24 秒打完
- 放在**仓库外**：仓库内被忽略的 `build/` 会被 `git clean -xfd` 删掉
- 同目录有 `README.md` 写明校验与恢复命令
- ⚠️ **仍在同一台机器上**——要真正跨机器保险，还得复制到外置存储；
  本机 `/Volumes` 只有未挂载数据卷的 `BOOTCAMP`

### 16.3 主树 `AGENTS.md` 单独提交

- 提交 `0a703846`（分支 `codex/butano-foundation-research`），
  **只改 `AGENTS.md`，只 +2 行**——就是本会话新增的两条登记表条目。
- 用**临时 index + `commit-tree` + `update-ref`** 完成，
  **全程不碰共享 index、不改工作树**：
  这样 Butano 复刻会话 166 项未提交改动**不会被卷走**，
  它的 `git add -A` 也不会与我的提交抢 `.git/index` 锁。
- 它的 `AGENTS.md` 里另外几行（PNG 透明化等）仍是未提交状态，
  留在工作树里归它自己提交。

---

## 17. 全量套件第一轮：29 个失败的四个根因（2026-10-20 06:2x–07:0x）

§14 修完 12 个测试后，全量套件（93 个测试 / 2,039 s）跑完，
**29 个失败**。本节记录这 29 个失败的完整归因与修复。

### 17.1 一个必须先记住的方法论教训

**每个测试的第一个失败会遮住它后面的所有断言。**

29 个失败背后实际有 **72 处**坏点：
16 个测试在 ledger SHA 处挂掉 → 遮住了同一测试里另外 6 处
陈旧的 `script_sha256`；6 个测试在计数里程碑处挂掉 → 遮住了
同一测试里后面的断言。

> **只按"失败清单"修是不够的**，必须**穷举每一类断言形态**，
> 把被遮住的一并修掉，否则下一轮还会红。

### 17.2 四个根因与 71 处修复

| # | 根因 | 处数 | 修法 |
| --- | --- | ---: | --- |
| A | `evidence["sequel/rom-byte-coverage.json"]` 钉在 9-05 的 `7726d471…` | 22 | 改为**与活文件对拍**：`_sha256(ROOT / "sequel/rom-byte-coverage.json")` |
| B | `coverage["script_sha256"]` 钉在旧版 `audit_rom_byte_coverage.py` 的 `63870355…`（本轮给它加了解释器闸门后变了） | 21 | 同上，改为与活文件对拍 |
| C | 计数里程碑 `assertEqual(96, sum(len(item["verifiers"]) …))` 等 | 23 | 改为 `assertGreaterEqual`（原意是"只增不减"） |
| D | **上一轮批量派生的误伤** | 5 | 按**作用域**恢复原字面量 |

A/B 的修法保留了断言的**实质含义**：「spec 声称的摘要 == 文件真实摘要」，
既不随晋升过期，又真能抓出 spec 与磁盘不一致。
C 的 23 处里 21 处是 `sum(len(item["verifiers"]) …)`、2 处是
`rom_gate["hash_bound_verifier_count"]` / `["contracted_verifier_count"]`；
`cfg_proven_roots_v4_extension_code_claim_count=118`、
`chapter_script_claim_count=92`、`adjudicated_candidate_count=114`
这些**批次量**经对拍确认仍然成立，保持硬编码。

修复脚本：`notes/evidence/reverse-proof-update-20261019-v1/repair_stale_ledger_pins.py`
（幂等：二次运行 0 替换 / `status: no-op`；写盘前先 `ast.parse` 兜底）。

### 17.3 D 类：按**键名**分类是错的，必须按**作用域**

`classified_bytes` 与 `unknown_bytes` 既是**全局覆盖量**的键名，
也出现在**单验证器批次合同**和**合成夹具**里：

| 位置 | 语义 | 正确值 | 被错换成 |
| --- | --- | ---: | --- |
| `test_current_spec_binds_selector_text_inventory` | 单验证器合同 | 816 | 6,205,367 |
| `test_current_spec_binds_battle_message_text_inventory` | 单验证器合同 | 2,740 | 6,205,367 |
| `test_current_spec_binds_boot_interwork_inventory` | 单验证器合同 | 414 | 6,205,367 |
| `test_reuses_the_already_executed_rom_coverage_audit_contract` | 合成夹具合同 | 7 | 86,089 |
| 同上（不匹配夹具） | 合成夹具合同 | 0 | 86,089 |

上一轮按**键名**批量派生，把这 5 处也换成了活账本全局量，
**直接打破 4 个测试**——这是我方引入的真回归。

> **教训（比 §14 更重要）**：
> **「是否随晋升变化」不能只看键名，必须看它属于哪个合同作用域。**
> 跨域撞名的键（`classified_bytes` / `unknown_bytes`）必须按**作用域**判定：
> 全局覆盖合同 → 派生；单验证器合同 / 合成夹具 → 保持字面量。

### 17.4 元守卫补强：从 6 项到 9 项

`tests/test_audit_reverse_engineering_coverage_count_liveness.py` 新增三道防线：

1. `test_no_test_source_pins_a_stale_digest` —— 任何测试文件都不得把
   **文件摘要**钉成字面量（`evidence["<path>"]` 与 `X["script_sha256"]`）。
   注意要排除 `/summary/..._denominator_sha256` 这类**区间/分母派生哈希**，
   它们不是文件摘要。
2. `test_cumulative_counts_use_at_least_not_equal` —— 累计型计数不得用
   `assertEqual` 钉死。作用域限 proof 套件模块：其他模块里的
   `contracted_verifier_count == 1` 是**单 bank** 的稳定计数，语义不同。
3. `test_per_verifier_contracts_do_not_use_global_derived_values` ——
   **整字典对拍**只用于单验证器合同（全局覆盖合同永远逐键对拍），
   所以「整字典里出现 `LIVE_COVERAGE_SUMMARY` 引用」即是越界；
   合成夹具（`_reuse_rom_coverage_contract`）同理。

另外把 `test_no_test_source_hardcodes_a_live_ledger_quantity` 的判定
从"任何 summary 指针"收紧为"**确实绑定到活账本**的对象"：
`<对象>["summary"][<key>]` 形态下，只有当该对象在本文件里
从 `sequel/rom-byte-coverage.json` 读出来时才算活账本断言；
夹具／历史收据的摘要写死是**对的**。

**红绿验证**：把修复前的文件换回去，9 项守卫里**恰好 3 项变红**
（上面三条新防线），恢复后 9/9 全绿（1.2–3.8 s）。

### 17.5 越出 cron 范围的两个发现（**未修，留给用户裁决**）

**发现一：`tests/` 实际有 622 个文件 / 4,487 个测试。**
cron 说的"93 个测试"只是 `tests/test_audit_reverse_engineering_proof.py`
**一个模块**。守卫按"活账本绑定"收紧后，在全树里精确锁定**1 处**
同类问题：`tests/test_coverage_evidence_selector_repairs.py:66`
（`self.coverage` 是活账本，钉着 87,749）——本轮已修为
「`accounted_bytes == unknown_bytes + classified_bytes`」的自洽校验。
其余 11 处经判定是**夹具／历史收据**的合法断言，未动。

**发现二：池 3 晋升也打破了工具层。**
`tools/export_rom_psg_frequency_lookup.py` 的 `_coverage_baseline()`
在账本变化后抛 `ValueError: coverage baseline identity changed`，
`tests/test_verify_rom_psg_frequency_lookup.py` 因此 6 个 error。

**为什么本轮不修**：该脚本的 SHA-256 **被 proof 钉住**
（`sequel/reverse-engineering-proof.json` 的 `script_sha256`），
改它必须同步 SHA 并**再跑一次完整 formal**（本轮 3,905 s）
才能复核；而且"导出器该不该钉住覆盖基线身份"本身是**语义决策**——
钉住能保证"重跑得到逐字节相同的 artifact"，不钉住则让导出器
总能对当前账本工作。**这需要用户裁决，不是我能替他假设的。**

## 18. 守卫补到 11 项 + psg 真相（三层因果）（2026-10-20 07:0x–08:0x）

### 18.1 元守卫第 10、11 项：上下界断言的参数顺序

**根因（本轮第二次同类事故）**：第 17 轮把 `assertEqual(N, expr)` 批量改成
`assertGreaterEqual(N, expr)` 时**参数顺序写反了**——正确写法是
`assertGreaterEqual(实际值, 下限)`，实际值在**第一个**参数。
写反后断言变成「下限 ≥ 实际值」，21 个测试全红（`96 not greater than or equal to 109`）。

**为什么元守卫抓不到**：这类写法**语法完全合法**，任何"有没有用 assertEqual"
的检查都看不见；而且它只在运行到那条断言时才炸，仍然要等 45 分钟的套件末尾。

**规则（`_reversed_bound_assertions`）**：

| 判据 | 说明 |
|---|---|
| 第一个参数是**整数字面量** | 候选越界（字面量只能是界，不能是实际值） |
| 第二个参数是**量表达式** | `Call(len/sum/max/min/…)` \| `BinOp` \| `Subscript` 且**字符串键**像计数（`*_count`/`*_bytes`/`verifiers`…） \| `Name` 且名字像计量或指向**模块级常量／导入名** |
| **豁免**：`Subscript` 的下标是**整数** | `DISPATCH_RANGE[0]` 是**固定区间端点**，不是量。`assertGreaterEqual(0x735C6, DISPATCH_RANGE[0])` 语义正确（断言默认目标落在派发窗口内），不得误报 |

判定必须**窄**：宁可漏掉部分真越界，也不能误伤「固定地址 vs 固定区间端点」。

**红绿验证**：

| 输入 | 期望 | 实测 |
|---|---|---|
| 当前（已修好）proof 测试文件 | 0 | **0** ✅ |
| 重建「参数对调」错误态 | 全覆盖 | **92/92** ✅ |
| 全 `tests/` 树 | 0 | **0** ✅ |
| 合成反向自检（`test_bound_order_detector_is_not_vacuous`） | 3 正例 / 0 反例 | ✅ |

**新加第 11 项** `test_bound_order_detector_is_not_vacuous`：用合成片段证明
检测器**认得出"写反"、认不出"写对"**。没有这一条，规则一旦收窄到什么都不匹配，
第 10 项就会**永远绿**——而它保护的正是「语法合法、只在运行时炸」的一类错。

守卫现为 **11 项 / 3.98–4.16 s**。

### 18.2 psg 的三层因果：不是 bug，是「冻结状态没有副本」

§17.5 记的"导出器抛 `coverage baseline identity changed`"只是一层。实测到三层：

**第一层（表面）**：`tools/export_rom_psg_frequency_lookup.py` 的 `_coverage_baseline(root)`
读**活账本** `sequel/rom-byte-coverage.json`，要求其 SHA-256 等于冻结常量
`922e06e9b195a31ae6a8ab8c03cb06159aee7218bc4268ac56e22c729b740de6`；
活账本现为 `9f8a8196…`。

**第二层（这道闸门永远不可能通过）**：该冻结状态
**在全仓 37,542 个文件里没有副本**（扫 `notes/evidence/**`、`notes/**`、
`artifacts/**`、`build/experiments/**`，含 `.gz` 解压后复算）。
晋升前的账本快照**从未被保存**。

**第三层（语义：这 226 B 早已是 psg 自己的）**：psg packet 于 2026-08-27
晋升并 accepted（`artifacts/rom-psg-frequency-lookup-v1/manifest.json`，
`artifact_status: accepted`）。它的 5 条 claim（**合计 226 B**）**现在就是**
这 5 个区间在活账本里的 owner：

| 区间 | 字节 | live `primary_class` | live claim id |
|---|---:|---|---|
| `0x9b494–0x9b4c6` | 50 | `armv4t_psg_frequency_lookup_thumb_code` | `psg-frequency-code-a-09b494` |
| `0x9b4c8–0x9b4cc` | 4 | `psg_frequency_lookup_consumed_pointer_literals` | `psg-frequency-noise-literal-09b4c8` |
| `0x9b4cc–0x9b534` | 104 | `armv4t_psg_frequency_lookup_thumb_code` | `psg-frequency-code-b-09b4cc` |
| `0x9b534–0x9b53c` | 8 | `psg_frequency_lookup_consumed_pointer_literals` | `psg-frequency-nonnoise-literals-09b534` |
| `0x46475c–0x464798` | 60 | `psg_noise_register_descriptor_table` | `psg-noise-register-table-46475c` |

所以「这 226 B 现在必须是 unknown」这个断言**被本 packet 自己的晋升推翻了**。
任何声称它为真的导出器都是错的——**它不是配置问题，是前提已被自身行动消灭**。

### 18.3 正确的分层：legacy 冻结 / bundle 活账本（设计写在代码里）

`tools/verify_rom_psg_frequency_lookup_bundle.py` 的 docstring **原文**：

> The accepted PSG verifier deliberately recognizes only its frozen pre/post
> coverage states. Later independently audited promotions must not rewrite that
> historical verifier or receipt. This wrapper replays the raw-ROM, payload,
> binary, manifest, implementation, and accepted-receipt checks while leaving
> the current live coverage state to `tools/audit_rom_byte_coverage.py`.

代码印证：`tools/verify_rom_psg_frequency_lookup.py:1358`
`rebuild_payload(repository, validate_live_baseline=status == "candidate")`
——**accepted 走冻结基线**，只有 candidate 才走活基线。

实测三道门的状态：

| 命令 | 结果 | 耗时 |
|---|---|---:|
| `tools/verify_rom_psg_frequency_lookup_bundle.py`（**formal 用的就是这道**） | `artifact_bundle_verified: true`、`legacy_receipt_verified: true`、`errors: []` ✅ | 0.48 s |
| `tools/verify_rom_psg_frequency_lookup.py`（legacy 完整验证器，对 accepted artifact） | ❌ `coverage exact post non-PSG claims identity changed` | 1.24 s |
| `tools/export_rom_psg_frequency_lookup.py`（写 candidate） | ❌ `coverage baseline identity changed` | — |

legacy 的失败点 `analyze_live_coverage`（`:1258`）的 else 分支要求
「**非 PSG 的其余 claim 集合**」与晋升时的冻结集合**逐字节相同**——
账本此后又被别的 packet 晋升过（unknown 169,832 → 86,089），这个
「此后不许再变」的合同已不成立。值得注意的是 `analyze_live_coverage` **本身**
已实现正确的二态判定（`unknown` / `owned`，且要求 5 个区间**同态**），
只有 `verify_artifact` 的 candidate 分支多加了「活文件 SHA 必须等于冻结 SHA」
这道死闸。

**结论**：psg 的"坏"是**分层的**——formal 实际执行的那道门是绿的；
坏的是 legacy 活账本路径与导出器，而它们**按设计只认冻结状态**。
处置方向因此从「语义裁决」收敛为「让测试对齐真正生效的合同」。

### 18.4 更正 §17.5 的一处判断

§17.5 写「该脚本的 SHA-256 **被 proof 钉住**（`script_sha256`）」——**不准确**。
实测：

- proof 的 `script_sha256` 钉的是 **`tools/verify_rom_psg_frequency_lookup_bundle.py`**
  （`f9bb2bed…`），**不是** exporter 或 legacy 验证器；
- exporter / legacy 验证器的 SHA 出现在 **artifact manifest 的 `implementation` 段**，
  而 manifest 本身作为 **evidence** 被 proof 钉摘要。

所以改 exporter 或 legacy 验证器 → accepted manifest 必须重生成 → manifest 摘要变
→ proof 的 evidence 摘要要同步 → **仍需重跑 formal**（结论不变，**机制不同**）。
但改**测试**不动这些文件 → **零下游成本**。这就是本轮选「只改测试」路线的理由。

## 19. 上面那条「零下游成本」也错了：审计器钉死了测试文件（2026-10-20 07:2x–08:0x）

### 19.1 实测经过

改完 psg 测试模块后重跑 93 个 proof 测试，结果是
**93 tests / 1,488.160 s / failures=1**，唯一失败：

```
FAIL: test_current_repository_does_not_overclaim_completion
  self.assertEqual([], rom_gate["rom_coverage_audit"].get("errors"))
AssertionError: Lists differ: [] != ['PSG frequency verifier test identity changed']
```

`tools/audit_rom_byte_coverage.py:2998-3001` 有一处**硬钉**：

```python
PSG_FREQUENCY_VERIFIER_TEST = Path("tests/test_verify_rom_psg_frequency_lookup.py")
PSG_FREQUENCY_VERIFIER_TEST_SHA256 = (
    "74f41c42ca5511f9331d59aead138f6bdfc198233cc10ba1180fee37d996c124"   # 旧值
)
```

`tools/audit_rom_byte_coverage.py:2994` 还有第二处，钉着导出器测试文件。

**因此 §18.4 的「改测试不动这些文件 → 零下游成本」是错的**：
审计器**把测试文件本身当受管输入钉住**，改测试就会打破 `rom_byte_coverage` 门。
这不是新问题，而是**系统性模式**——审计器里共有 **174 处** `*_TEST_SHA256` 形式的硬钉
（**口径更正，2026-10-20 09:2x**：174 是该**模式在文件里的字符串出现次数**
（64 个常量定义 + 110 处使用），**不是**「被钉的测试文件数」；后者是 **62 个不同的
测试文件**。下面的连锁成本按 62 算，见 §19.5）。

**失败是自伤造成的**：子代理在套件运行**中途**改了测试文件，
而审计器在运行**时**从磁盘读该文件并与硬钉比对 → 套件末尾才报出来。
**这本身是一个教训**：跑长套件期间不要改被 pin 的文件。

### 19.2 实际影响面（实测，不是推算）

| 改什么 | 要不要动账本 | 要不要重跑 formal | 原因 |
|---|---|---|---|
| `tests/test_verify_rom_psg_frequency_lookup.py` | **不要** | **要** | 审计器 pin 变 → 审计器 SHA 变 → spec 的 `script_sha256` 要同步 |
| `tests/test_export_rom_psg_frequency_lookup.py` | **不要** | **要** | 同上（第二处 pin） |
| `sequel/rom-byte-coverage.json` | **不要** | — | 账本 `summary` 的 569 个键里**没有** `script_sha256`；审计器源码里也搜不到该字段 → **改审计器不改变账本内容**，账本 SHA 保持 `9f8a8196…`，spec 的 evidence 条目不必改 |
| `sequel/reverse-engineering-proof.json` | — | — | `gates.rom_byte_coverage.verifiers[0].script_sha256` 是**唯一**钉审计器 SHA 的地方 |

**好消息**：链路比预想的短 —— **不需要重建账本**，只要
「改 2 行 pin → 同步 spec 1 个 SHA → 重跑 formal」。

### 19.3 已执行的修复

| 步骤 | 内容 | 结果 |
|---|---|---|
| 1 | `PSG_FREQUENCY_VERIFIER_TEST_SHA256`：`74f41c42…` → `c10ff259…` | 审计器 SHA → `33932f14…`（与子代理独立预测的值**一致**） |
| 2 | `PSG_FREQUENCY_EXPORTER_TEST_SHA256`：`d1983847…` → `9844b120…` | 审计器 SHA → `1fba1112…` |
| 3 | spec `gates.rom_byte_coverage.verifiers[0].script_sha256` 同步 | `1fba1112…` |
| 4 | 复验 | `tests/test_verify_rom_psg_frequency_lookup_bundle.py` **4/4 OK**（这两道 pin 的守门人） |

### 19.4 psg 两个测试模块的最终状态

| 模块 | 改前 | 改后 |
|---|---|---|
| `tests/test_verify_rom_psg_frequency_lookup.py` | 10 tests / **6 errors** | **10 tests / 全绿** |
| `tests/test_export_rom_psg_frequency_lookup.py` | 11 tests / **9 errors** | **15 tests / 全绿** |
| `artifacts/rom-psg-frequency-lookup-v1/` | manifest `4fffbcc7…` / .bin `e625a5fc…` / .json `d2631b1a…` | **逐字节不变** ✅ |
| `tools/verify_rom_psg_frequency_lookup_bundle.py` | `f9bb2bed…` | **未变** ✅（proof 钉的就是它） |

**改写原则**：不改任何脚本，只把「活账本耦合」的用例改成覆盖
**今天真正成立的合同**——legacy 验证器的**冻结路径**
（`rebuild_payload(validate_live_baseline=False)`）产出的 payload 与 accepted artifact
**逐字节相同**；导出器的**活账本路径必须 fail-closed 且不落任何文件**；
活账本侧的归属事实（psg 5 条 claim / 226 B / 区间正好等于 `PROMOTION_RANGES`）
改为直接对拍活账本。**没有删除任何一条风险覆盖**，每个新断言都做过红绿验证。

### 19.5 遗留的系统性问题

审计器里 **174 处** `*_TEST_SHA256` 硬钉意味着：
**每改一次被钉的测试文件，就要走一次「改 pin → 审计器 SHA 变 → spec 同步 → 重跑 formal」**。
这与本轮刚修掉的 21 处「活账本量硬编码」是**同一类病**：
**把会随正当演进而变化的东西钉成了常量**。
可行的收窄方向：区分两种 pin 的语义——
「该文件必须存在且自述」的改成**与活文件对拍**；
「必须是某一版」的才保留硬编码。**本轮未动**（174 处一次性改动风险过高）。

**口径更正（2026-10-20 09:2x，实测脚本解析）**：
「174 处」是 `*_TEST_SHA256` 这个**模式在审计器文件里的字符串出现次数**
（**64 个常量定义 + 110 处使用**），**不是**「被钉的测试文件数量」。
后者是 **62 个不同的测试文件**（64 个常量 → 62 条不同路径，其中 2 个文件被钉两次）。
连锁成本要按 **62** 估，不是 174：

| 口径 | 数 | 含义 |
|---|---:|---|
| `*_TEST_SHA256` 字符串出现次数 | 174 | 模式在文件里出现多频繁（63% 是使用点，37% 是定义点） |
| `_TEST*_SHA256` 常量定义数 | 64 | 审计器里有多少个 pin 常量 |
| **被 pin 的不同测试文件数** | **62** | **改一个就要付一次 formal 的实际成本** |

另有 2 个文件也引用了被钉测试文件（`tools/rom_boot_interwork_continuation_contract.py`、
`tools/verify_rom_boot_thumb_code_literal_alignment_gaps.py`），
所以改某些测试文件时**扇出不止审计器一个**。
除此之外还有 **5 对 exporter/verifier**（共 10 个文件）各自用 `SOURCE_TEST_SHA256`
钉自己的测试文件：`chapter_selector_code_slice`、`profile_selector_code_slices`、
`battle_status_bar_caller_slice`、`sprite_loader_tail`、`boot_interwork_continuation`。
这类 pin **不经过审计器**，但改测试会连带改 exporter + verifier **两个**脚本的 SHA。

## 20. 甲线三包接入施工单（只读侦察产出，2026-10-20 08:0x）

完整施工单：**`notes/evidence/reverse-proof-update-20261020-v2/三包接入施工单-raw.md`**（872 行，
含可直接粘贴的常量块 / claim 函数 / spec 同步项 / 逐阶段验收命令）。
下面是**结论层**。

### 20.1 三个 packet 的实测身份

| | M1 动画池 | 命令脚本 | 显示文本 |
|---|---|---|---|
| artifact | `artifacts/rom-animation-descriptor-pool-v2`（**已 promote**） | `rom-renderer-records-delta-v1`（**未 promote**） | `rom-display-text-delta-v1`（**未 promote**） |
| claim 数 | **1** | 29 | 85 |
| 认领字节 | 640 | 1,668 | 1,053 |
| 区间 | `[4555564,4556204]`（0x458564–0x45879C） | 29 段，跨 0x0BCD–0x542E | 85 段，跨 0x12EE4C–0x463B16 |
| `primary_class` | `fixed_consumer_animation_descriptor_group_bytes` | `fixed_cfg_consumer_renderer_command_script` | `fixed_cfg_consumer_renderer_display_text` |
| 独立 verifier | `tools/verify_rom_animation_descriptor_pool_v2.py`（**0.17 s 通过**） | `tools/verify_rom_renderer_records_delta.py`（<1 s 通过） | `tools/verify_rom_display_text_delta.py`（~70 s 通过） |
| `implementation_inputs` 与仓库实时文件 | 3/3 MATCH | 3/3 MATCH | 4/4 MATCH |

**合计 3,361 B / 115 条 claim。**

### 20.2 promote 的确切事实（实测，不是推算）

- 两个受管 run **都还活着**：`build/experiments/active/renderer-records-delta/combined-tier1-20261001-v1/`
  与 `build/experiments/active/display-text-delta/tier1-20261001-v1/`，`status: completed`、无 `promoted_to`。
- 命令：`tools/experiment_workspace.py promote --root . --task <t> --run-id <r> --artifact-name <n>`。
  `--artifact-name` **必须**等于 verifier 里写死的 `ARTIFACT` 常量，否则 `manifest contract changed`；
  目标目录**必须不存在**（`promote_run` 抛 `FileExistsError`）——当前两个目录都不存在 ✅。
- **`notes/evidence/**/final/` 的副本不能 promote**：`_run_path()` 硬编码为
  `root/build/experiments/active/<task>/<run_id>`。副本内容与受管 run **逐字节相同**，
  但若 `build/` 被清，必须**重建受管 run**（init → 重放 exporter → 重冻 final/），不能只拷文件。
- promote **只改** `.experiment.json`（新增 `promoted_to` + `promoted_at`）；
  `.inventory.json` 会被重写但**内容逐字节相同**（已离线复算验证）；
  `notes/evidence/**` 的历史收据**不会被回写** ✅。
- **主要收益**：`artifacts/` **不在** `.gitignore` 里（只有 `build/`）→ promote 之后
  这两个包进入版本控制，从此不再依赖会被清理的 `build/`。

### 20.3 canonical 重建后的投影（用审计器自己的原子化语义离线复算，基线自校验通过）

| 指标 | 现值 | 投影值 | Δ |
|---|---:|---:|---:|
| `unknown_bytes` | 86,089 | **82,728** | **−3,361** |
| `classified_bytes` | 6,205,367 | **6,208,728** | **+3,361** |
| `claim_count` | 16,913 | **17,028** | **+115** |
| `segment_count` | 18,675 | **18,882** | **+207** |

复算的**基线自校验**：claim_count 16,913 / segment_count 18,675 / accounted 6,291,456 /
unknown 86,089 / classified 6,205,367 **逐项与账本 `summary` 相等** → 复算方法与 `atomize_claims` 等价。
（段数 +207 而非 +115：3,361 B 被切成 115 段后，原有的连续 unknown 段被这些边界**进一步细分**。）

**不重叠核对**：三包内部自重叠 **0**；三包 × 活账本 16,913 条既有 primary claim **0**；
三包两两 **0**；活账本自身 primary claim 之间 **0**。

### 20.4 三个必须先知道的坑

1. **M1 的 `primary_class` 与既有 `rom-fixed-animation-descriptor-groups-v1` 完全同名**
   → 账本按 class 汇总时两族**合并**（1,136 + 640 = **1,776 B**）。
   该值被 exporter/verifier **逐字节钉死**（`payload_raw != _canonical(rebuilt)`），
   **改不了** → 接受撞名，靠 `promotion_batch` 区分。
2. **两个 renderer verifier 的 report 里没有 `schema` 键** → **不能**进 proof 的 `verifiers`
   （`_contract()` 校验 + 逐键比对会失败，**新增 blocker**）。只有 M1 的 report 形状合规。
   ⇒ 接线时**只有 M1** 能作为新 verifier 进 spec；两个 renderer 包只能进 `evidence`。
3. **`artifacts/rom-low-script-delta-v1`（12 B）是新命令脚本包的真子集**
   （`low-script-delta-42b5` = `renderer-records-delta-42b5`，
   `low-script-delta-42c2` = `renderer-records-delta-42c2`，**逐字节相同**）。
   它是**账本孤儿**（账本引用 0、proof 引用 0）→ **不会**造成重复 claim，
   但**绝不能**接进审计器（否则 `atomize_claims` 抛 conflicting primary claims）。

### 20.5 不可并行的串行约束

1. heavy lock 一次只容一个受管重活（busy 即 exit 75）；
2. **promote → auditor 接线**（审计器常量指向 `artifacts/`）；
3. **auditor 改完 → 账本重建**；
4. **账本重建完 → proof 同步**（`/summary/*` 断言读活账本）；
5. `NEW_AUDIT_SHA` 必须在 auditor 定稿后算；
6. **proof 改完 → formal**。

**接线后必须冻结的文件**（同时被 manifest 的 `implementation_inputs` 和审计器常量钉住）：
`tools/verify_rom_renderer_records_delta.py`、`tools/verify_rom_display_text_delta.py`、
`tools/export_rom_renderer_records_delta.py`、`tools/export_rom_display_text_delta.py`、
`tools/rom_display_text_parameter_flow.py` 及两个测试文件 + 两个 `tools/data/` 合同 JSON。

## 21. 覆盖审计段的瓶颈定位与第一笔优化（2026-10-20 08:0x–08:2x）

### 21.1 机器侧事实（实测）

| 项 | 值 | 来源 |
|---|---|---|
| 物理内存 | 16 GiB / 12 逻辑核 | `top` |
| 交换 | 2,048 MiB 总量 / 1,240 MiB 已用 | `sysctl vm.swapusage` |
| 磁盘可用 | 74–77 GiB | `df -h`（96–98% 的旧记录已过期） |
| 跑重活时的负载 | 3.4–4.8 | `uptime` |
| **覆盖审计器的 CPU 占用** | **100.0%（恰好 1 核）** | `ps` 连续观测 20+ 分钟 |

**结论**：覆盖审计段是**单线程 CPU 瓶颈**，不是内存瓶颈，也不是磁盘瓶颈。
机器有 12 个逻辑核，审计器只吃满 1 个 —— **并行度被算法本身限死**。

### 21.2 定位到的第一处热点：`atomize_claims`

原实现对**每个段**全量扫一遍所有 claim：

```python
for start, end in zip(ordered, ordered[1:]):
    active = [claim for claim in normalized
              if ranges[claim["id"]][0] <= start and end <= ranges[claim["id"]][1]]
```

真实账本 16 913 条 claim / 18 675 段 → 约 **5.7 亿次**内层迭代。

| | 耗时 | 段数 |
|---|---:|---:|
| 旧实现 | **60.50 s** | 18 675 |
| 扫描线 | **0.09 s** | 18 675 |
| 加速 | **681.5×** | — |
| 逐字节等价 | **True** | — |

**等价性推导**：claim 覆盖段 `[a, b)` ⟺ `claim.start ≤ a` 且 `claim.end ≥ b`。
因为 `b` 是 `a` 之后的**下一个端点**、且所有 claim 的端点都在 `endpoints` 里，
所以 `claim.end ≥ b ⟺ claim.end > a`，活跃集合 = `{claim : start ≤ a < end}`，
可用起点/终点两个有序指针增量维护。输出按 claim id 排序（原实现也是按 id 排序），
因此与原实现**逐字节一致**。

**新增闸门** `tests/test_audit_rom_byte_coverage_atomize_sweep.py`（4 项 / 90.8 s）：
真实账本逐字节一致 + 400 组随机输入一致 + **失败关闭报错文案**逐字一致 +
性能闸门。**把参照实现（原样抄写）钉在测试里** —— 这类优化最危险的不是慢，
而是**悄悄改变分段语义**，而分段决定整个账本的 claim 归属。

审计器 SHA：`1fba1112…` → **`15425f37…`**，spec 已同步。

### 21.3 但 60 s 只是小头：`audit_manifest` 的时间几乎全在 `build_manifest`

```python
def audit_manifest(root, manifest):
    expected = build_manifest(root)      # ← 全部时间在这里
    if manifest != expected:             # ← 一次 O(n) 字典比较，可忽略
        errors.append("manifest differs from reproducible scan")
```

实测：`atomize_claims` 60.50 s，而**整个 `build_manifest` 约 2,377 s**（formal 的
覆盖段）。差值 **≈ 2,317 s** 去哪了？两个数字对得上：

- formal 的 108 个验证器**4 路并发**共 1,528 s → 串行推算 **≈ 2,113 s**；
- 覆盖段 2,377 s ≈ 2,113 s（串行冷重放） + 60 s（atomize）+ 账本构建开销。

**假设（正在核实）**：`build_manifest` 内部**串行**把各 packet 的独立 verifier
**冷重放**了一遍 —— 于是同一批验证工作在一次 formal 里被做了**两次**：
一次在 formal 的 verifier 列表里并发跑，一次在 auditor 内部串行跑。
若成立，可选修法有两条：
**(A)** 把 `build_manifest` 里的冷重放阶段与 claim 投影阶段拆开，前者并发；
**(B)** 让 auditor **复用** formal 已跑过的 verifier report 收据（缓存键 =
ROM SHA + artifact SHA + verifier SHA，缓存命中必须可被独立复验，否则 fail-closed）。
**两条都还没动手** —— (A) 触及 claim 投影的顺序语义，(B) 引入新的缓存失效面，
都要先看清 `existing_claims` 的 current-unknown 门依赖再决定。

### 21.4 一个必须记住的坑

**跑长套件期间不要改被 pin 的文件**。本轮子代理在 93 个测试套件**运行中途**
改了 `tests/test_verify_rom_psg_frequency_lookup.py`，而审计器在运行**时**从磁盘
读该文件并与硬钉比对 → 套件末尾才报 `PSG frequency verifier test identity changed`，
93 个测试里唯一那个失败**是自伤造成的**，不是回归。§19 有完整记录。

## 22. 审计器自己的测试模块从没被整体跑过（2026-10-20 08:2x–08:4x）

### 22.1 发现

`tests/test_audit_rom_byte_coverage.py`（**15 933 行 / 60+ 测试类**）把账本总量
**写死**成字面量。账本每晋升一次，这些字面量就变成历史值 —— 实测 **131 处**
陈旧断言，已经让该模块**跑不过**。这是 §14 在 proof 套件里修掉的 21 处那种病的
**另一个副本**，只是**这个模块从没被整体跑过**，所以一直没暴露。

**五种形态**（脚本 `notes/evidence/reverse-proof-update-20261020-v2/derive_live_coverage_bounds.py`，
幂等、可复现、`--dry-run` 可先看）：

| # | 形态 | 处数 |
|---|---|---:|
| 1 | `assertEqual(<字面量>, summary["<键>"])` | 91 |
| 2 | `assertEqual((<数>, …), (<表达式>, …))` | 35 |
| 3 | `assertEqual((<数>, …), tuple(coverage["summary"][k] for k in (…)))` | 3 |
| 4 | `assertEqual(<字面量>, aggregate["<cfg 键>"])`（aggregate 来自**全量**活账本 claims） | 2 |
| 5 | `assertEqual({…}, aggregate)`（整字典） | 2 |

**改法**（仓库自己已有先例：同文件 11565–11568、11796–11799 行就是这个形态）：
快照等号的原意是「账本**至少**已经到这个状态」→ 变成**界**：
只会增长的量（`classified_bytes` / `claim_count` / `segment_count` / `cfg_*` 聚合）
用**下界** `assertGreaterEqual(实际值, 冻结值)`；
只会缩小的量（`unknown_bytes`）用**上界** `assertLessEqual(实际值, 冻结值)`。

**两条必须守住的边界**：

1. **批次增量一律不动**（各 packet 自己的 `promotion_bytes` / `claim_count` 等）——
   那些是真正的回归护栏，必须保持硬编码。
2. **只转换「对全量活账本 claims 求的聚合」**；「prior + 本包 claim」这类
   **子集投影**的冻结值**本来就是对的**（它就该等于那个子集的投影），必须原样保留。
   判据按**作用域**做（同名变量在不同作用域可能指向活账本或重建结果），fail-closed。

**方向的坑**：元组形态里，方向必须按**键名**判（`unknown_bytes` 只会缩小），
不能按「表达式里有没有减号」判 —— 实参是 `self.COVERAGE["summary"]["unknown_bytes"]`
时根本没有减号。第一版就是这么写错的，被守卫当场抓出来（见 §22.3）。

### 22.2 元守卫补两个盲区（11 → 12 项）

| 盲区 | 症状 | 修法 |
|---|---|---|
| **本地别名** | 守卫只认 `coverage["summary"][key]` 这种直接下标链；`summary = manifest["summary"]` 之后的**别名形态整类漏掉** —— 实测那 131 处**一个都没被抓到** | 按**作用域**解析别名链（同名变量在不同作用域可能指向活账本或重建结果） |
| **界的方向** | 转成界之后，守卫只扫 `assertEqual` 就**看不见**了 | 新增第 12 项 `test_bound_assertions_against_live_keys_keep_the_bound_on_the_right_side`：界必须留在正确的一侧 |

第 12 项当场抓出一处**既存的错向断言**（`unknown_bytes` 用了 `assertGreaterEqual`，
方向反了，断言恒假）—— 这是守卫的自我证明。

### 22.3 结果

- 守卫 **12/12 全绿**（7.4 s）
- 受影响的 6 个测试类 **15 tests 全绿**（60.7 s）
- 转换脚本**幂等**（二次运行「没有任何改动」）
- 整个模块的整体跑在后台进行中（该模块的 `setUpClass` 要跑一遍 `build_manifest`，
  历史上要 ~57 分钟）

## 23. formal v2：优化后的实测结果（2026-10-20 08:47Z）

### 23.1 收据（`notes/evidence/reverse-proof-update-20261020-v2/formal-parallel-guard.json`）

| 项 | 值 |
|---|---|
| 墙钟 | **1,464.7 s（24.4 min）** |
| 退出码 / 降级 | **0** / `degraded=false` |
| 峰值 RSS | 845 MiB |
| `complete` | false（预期：175 blockers 未清） |
| `blockers` | **175** —— 与基线**集合一致，无新增** |
| `verifiers_executed` | 108，**`failed_verifiers: []`** |
| coverage 门 | `verified=true`，`errors=[]` |
| 账本数 | `unknown_bytes=86089` / `claim_count=16913` / `segment_count=18675` |

### 23.2 墙钟对比（**收据强度逐列标注**，2026-10-20 09:4x 更正）

| 轮次 | 墙钟 | 覆盖段 | 验证器段 |
|---|---:|---:|---:|
| 9-05 基线（串行） | 2,489.4 s | 1,901.8 s | 587.5 s |
| 9-30 基线（串行） | 2,383.5 s | 1,819.5 s | 564.0 s |
| 10-20（4 路并发，旧代码） | 3,905 s | 2,377 s | 1,528 s |
| **本轮 v2（4 路并发，atomize 优化后）** | **1,464.7 s** | — | — |

- **vs 10-20 同配置：2.67× 更快**
- **vs 9-30 空闲基线：1.63× 更快**

⚠️ **本节原标题写「全部来自收据，不是推算」——这句话对 10-20 那两列不成立，
2026-10-20 09:4x 更正**。逐列收据强度：

| 数字 | 强度 |
|---|---|
| formal 总 3,905.06 s | **收据**（`formal-parallel-guard.json` 的 `started_at`/`finished_at`） |
| `--verifier-jobs 4` | **收据**（同上）——但这是**请求值**；有效并发 = `_verifier_job_count(4)`（`tools/audit_reverse_engineering_proof.py:846-866`）按启动瞬间可用内存夹取，**结果不落 report、不落收据** |
| 覆盖段 2,377 s | **无独立收据**；同工作负载的独立实测 2,413.787 s 强佐证（差 1.5%） |
| 验证器段 1,528 s | **纯减法推算**（3,905 − 2,377），无收据 |
| 基线 564.0 / 587.5 s | 两个**不同**受管运行相减 ⇒ 是**上界**（formal 内部还会再跑一遍覆盖门） |

⇒ 「1,528 / 564 = 2.71× 争用放大」是**下界**；且该数字与「最长单验证器封顶」
（v9 确实在列表里，但 1,080 s 无收据）**互斥而无法排除任一方**（§27.1）。

### 23.3 结论要写得诚实

`atomize_claims` 的 681× 是**单函数**的实测；它在整轮 formal 里换来的实际降幅
**小于**「38+1 次调用 × 60.50 s ≈ 1,611 s」这个**静态推算**。原因：推算按
「每次都按全账本规模计」估的，而 producer 内部的 38 次调用跑的是**逐渐变大的
子集**，O(段数×claim 数) 的代价远低于全账本。**推算上界 ≈ 1,611 s，实际收益更小** ——
这正是 AGENTS.md 要求「逆向结论变化时更新原记录」要处理的另一类：
**不是错，但高估**。

剩下的覆盖段成本是各 packet 的**验证器冷重放**（112/124 个 producer 会调外部
verifier，其中 51 个模块与 formal 的验证器列表重叠 ⇒ 同一批冷重放在一次 formal
里被做了两遍）。要再往下压，方向是**把 producer 内的冷重放与 claim 投影拆成两阶段**
（前者并发、后者保持串行），或**让 auditor 复用 formal 已跑过的 verifier 收据**。
两条都还没动手：前者要改 97 个函数且要保证「第一个抛出的异常」在并发下仍按链序
归位；后者会削弱 auditor「独立重算一遍」的价值，fail-closed 反转风险高。

### 23.4 独立审计的同条件 A/B（已完成，2026-10-20 09:07Z）

| 轮次 | 起止（UTC） | 墙钟 | 退出码 | 峰值 RSS | 收据 |
|---|---|---:|---:|---:|---|
| 优化前 | 23:42:12.51 → 00:22:26.30 | **2,413.787 s** | 0 | 495.47 MiB | `auditor-standalone-guard.json` |
| 优化后 | 00:49:31.46 → 01:07:59.74 | **1,108.276 s** | 0 | 500.68 MiB | `auditor-optimized-guard.json` |

- **2.178× 更快**（省 1,305.5 s ≈ 21.8 min），峰值 RSS 只涨 1.05%。
- **输出逐字节一致**：两轮 `*.stdout.log` 经 `cmp` 比对 **IDENTICAL**
  （各 41,303 B）。所以这 1,305.5 s 是**纯性能收益，零语义漂移**。

**A/B 的变量只有一个性能项，且两轮条件可比。**

- 时间线：优化前那轮 07:42:12 启动，早于 `0827b497`（atomize 改扫描线，
  08:03:44 提交）→ 跑的是**旧实现**；优化后那轮 08:49:31 启动，晚于该提交 →
  跑的是**新实现**。两轮之间审计器另有两处变更（`093b870a` 刷新两处
  `_TEST_SHA256` 硬钉），但那是 **O(1) 常量替换**、不进入任何热点路径。
- 条件可比：两轮**都同时有审计器测试模块整体跑在后台**、都有应用栈占用。
- `degraded=false`、`exit_code=0` 两轮一致；账本 `sequel/rom-byte-coverage.json`
  **SHA 未变**（`9f8a8196…`）——审计器只读账本，不写。

**这同时收紧了 §23.3 的「高估」判断。** §23.3 按静态推算认为实际收益会明显小于
1,611 s；实测省下 **1,305.5 s**，是推算上界的 **81%**，落在推算区间内且接近上界。
原因与 §23.3 相同：producer 内部的 38 次 `atomize_claims` 跑的是**逐渐变大的子集**，
不是全账本规模；但「逐渐变大」不等于「可忽略」。
**第一因的归属由推算升级为实测确认：`build_manifest` 里 `atomize_claims` 的 39 次
重复调用，单项就占掉整轮覆盖审计 2,413.8 s 中的 54.1%。**

## 24. 权威全量结果（2026-10-20 09:0xZ）

### 24.1 93 个 proof 测试套件 —— **93/93 OK，0 失败**

```
Ran 93 tests in 1138.308s

OK
```

- 日志：`/tmp/proof-suite9-full.log`（19,139 B，收尾于 09:06:03）。
- 跑的是**优化后**代码：链子 `chain_suite_after_formal.sh` 在 formal v2
  （08:47Z 完成）结束后自动开跑，起点晚于 `0827b497`（atomize）与 `c3e2b71c`
  （131 处改写）。
- 运行期间**没有改动任何被 pin 的文件**（`c3e2b71c` 之后的提交只有本文件的
  文档与收据），因此这 93 项是**无自伤污染**的权威全量结果。

**这 93 项不是逆向完成量。** 它只证明「93 条既有断言在新代码下仍成立」。
四类分母一个都没动：

| 分母 | 值 | 本轮是否变化 |
|---|---:|---|
| `unknown_bytes` | 86,089 | 否 |
| `classified_bytes` | 6,205,367 | 否 |
| `claim_count` | 16,913 | 否 |
| `segment_count` | 18,675 | 否 |
| formal `blockers` | 175 | 否（集合一致，无新增） |

### 24.2 覆盖证据选择器修复模块（`/tmp/cesr2.log`）—— **已转绿**

```
Ran 8 tests in 191.529s

OK
```

`tests/test_coverage_evidence_selector_repairs.py` 8 项全绿，无残留 error。

### 24.3 审计器测试模块整体跑（**进行中**）

`tests/test_audit_rom_byte_coverage`（15,933 行 / **88 个测试类 / 359 个测试方法**）
整体跑在后台，截至 09:2x：**35 项 ok / 0 项 FAIL**，仍在跑（PID 47459，
100% CPU，单进程，已 35 min）。§22 的 131 处陈旧快照改写到目前为止
**没有引出任何失败**；最终 summary 待它跑完补。
跑满全模块的耗时预期在 **1 h 量级**（该模块的 `setUpClass` 会调
`build_manifest`），不是分钟级。

---

## 25. 三个待裁决项的实测答案（2026-10-20 09:2x）

### 25.1 裁决 ④（purelib 加固）：**存在一条「零脚本改动」的更优路径**

原问题被表述成「加固为补所有候选 purelib（改动需同步 SHA + 重跑 formal）」。
**实测表明有更省的路**：

| 事实 | 证据 |
|---|---|
| Pillow 12.2.0 在 `/usr/local/lib/python3.14/site-packages/PIL/` | `python3 -I -c "import PIL"` → **OK** |
| `-I -S` 下 Pillow **不可见** | `python3 -I -S -c "import PIL"` → `ModuleNotFoundError: No module named 'PIL'` |
| venv（`--system-site-packages`）的 `-I` 也能看到 | `.venv/bin/python3 -I -c "import PIL"` → OK |
| 触发点**不在脚本里**，在 **spec** | `sequel/reverse-engineering-proof.json` 的 `gates.rom_byte_coverage.verifiers[95].command` = `['python3','-I','-S','tools/verify_rom_sprite_loader_tail.py','--root','.','--artifact-dir','artifacts/rom-sprite-loader-tail-v1']` |
| spec 的 SHA **没有被任何脚本或测试钉住** | `grep -rn "reverse-engineering-proof.json" tools/*.py tests/*.py \| grep -i sha` → **无结果** |
| 验证器**自己记录的**命令本来就没有 `-I -S` | `tools/verify_rom_sprite_loader_tail.py:443-452` 记的是 `['python3','tools/verify_rom_sprite_loader_tail.py','--root','.','--artifact-dir',...]` → 改 spec **不与 artifact 冲突** |
| 审计器是 **in-process import**，不是子进程 | `tools/audit_rom_byte_coverage.py:119` `from tools.verify_rom_sprite_loader_tail import verify_artifact`；`:33054` 硬钉该验证器 SHA `4bbb8db3…` |

**结论**：把 spec 里那条命令的 `-S` 删掉（`-I -S` → `-I`），
**不动任何脚本** ⇒ 验证器 SHA 不变 ⇒ artifact `rom-sprite-loader-tail-v1` 不变
⇒ 审计器不变 ⇒ **零 SHA 连锁**。原「补 purelib」的改法反而要动验证器源码
⇒ 触发上面整条链，是**更贵**的方案。

**仍需重跑一次 formal 的唯一原因**：formal 报告的
`trust_anchor.spec_sha256` 钉的是 spec 自身的 SHA（当前 `39b7ebd7…`），
改 spec 后旧收据不再绑定新 spec ⇒ 需一次 formal 产出新收据。
（`trust_anchor.verified=false` **不是失败**：那是
`tools/audit_reverse_engineering_proof.py:1062-1071` 的设计——只有外部传入
`--trusted-spec-sha256` 才为 true；当前 `claim_status=incomplete`，
不触发任何 blocker。）

**代价对比**：

| 方案 | 改什么 | SHA 连锁 | 额外成本 |
|---|---|---|---|
| **A（推荐）** | spec 删 `-S`（1 行） | **零** | 1 次 formal（~1,465 s） |
| B（原设想） | 验证器补候选 purelib | 验证器 → artifact → 审计器 → spec 四级 | artifact 重落地 + 1 次 formal |

**取舍要说清**：`-I` 仍隔离环境变量与 user site，但**重新暴露 system
site-packages** ⇒ 该验证器会看到已安装的第三方包。这对「要用 Pillow 的验证器」
是必需的，但确实降低了隔离度。是否接受由用户定。

### 25.2 一个被实测证伪的预测（影响下一个优化方向的选择）

早先的只读侦察报告（基于 `0827b497` 之前的代码）预测：
「atomize 优化后覆盖审计段将降到 **~200–300 s**」。**本次 A/B 证伪了这个预测**：

- 实测优化后独立审计 = **1,108.276 s**（不是 200–300 s）。
- 也就是说 `atomize_claims` 之外**还有 1,108 s** 的成本，
  比侦察报告的「其余 ~200 s」上界高出约 5 倍。
- 推论：§23.3 说的「剩下的是 112 个 producer 的**验证器冷重放**」，
  规模上**就是**这 1,108 s 的大头，不是「小头」。
  **下一个优化杠杆因此从「atomize」转移到「producer 内冷重放」**，
  而后者按侦察报告的评估需要改 97 个函数 + 两阶段拆分 + 报错按链序归位，
  属于**高风险大改**。
- 这个量级差也解释了为什么 formal v2（1,464.7 s，4 路并发）比
  独立审计（1,108.3 s，单线程）只慢 **356 s**：并发验证器段已经比
  单线程覆盖段短，并发带来的争用把收益吃掉了一部分。

### 25.3 硬件/资源瓶颈：现状实测

| 项 | 实测值 | 来源 |
|---|---|---|
| 审计器并行度 | **只吃满 1 核**（单线程 CPU 瓶颈） | 独立审计全程 100% CPU / 1 进程 |
| 审计器峰值 RSS | 495.47 → 500.68 MiB（+1.05%） | 两份 `auditor-*guard.json` |
| formal v2 峰值 RSS | 845 MiB | `formal-parallel-guard.json` |
| 4 路并发验证器段 | 564 s（空闲）→ **1,528 s**（有争用）= **2.7× 更慢** | 9-30 收据 vs 10-20 收据 |
| 机器 | 16 GiB 内存 / 12 逻辑核 / swap 2,048 MiB（已用 1,240）/ 磁盘 75 GiB 可用 | `notes/line-a-progress-20261019.md` §11.5.1 / §21.1 |

**最有决策价值的一条**：**并发不等于更快**。在有其它长跑任务占着宿主时，
4 路并发把验证器段从 564 s 推到 1,528 s，整轮 formal 反而比串行基线慢
（3,905 s vs 2,383.5 s）。**空闲宿主上单线程覆盖段（1,108 s）目前仍是最优解**，
4 路并发只在覆盖段与验证器段**真正重叠**且宿主空闲时才可能赢。

---

## 26. Tier-2 门槛：原文固化 + 我们自己转述的错误（2026-10-20 09:3x）

原文、先例、差异表已单独固化为
**`notes/tier2-threshold-policy-source-20261020.md`**（本节只记要点与更正）。

### 26.1 三条决定性事实

1. **这道门没有代码实现**。`tools/` 与 `tests/` 里搜不到任何阈值常量，
   proof spec 顶层也没有 threshold/milestone 键 ⇒ 它是**人读约定**。
   裁决结果**不能靠改一个常量生效**，必须落进 `AGENTS.md` /
   `docs/reverse-engineering-proof-policy.md` / `notes/`。
2. **有效字节门槛是 9,437 B，不是 10 KiB**。`docs/remaining-reverse-work-plan-20261001.md:301`
   给了换算：「0.15个百分点对本ROM 约9,438B」；ROM accounted = 6,291,456 B ⇒
   0.15 pp = 9,437.2 B < 10 KiB = 10,240 B。我们此前转述的「≥10 KiB」**高估了 803 B**。
3. **原文没有"晋升受门控"这回事**。Tier-1 通过的 packet **已经**可以进待接入队列
   （`policy:88-89`）。原文是「**才触发二级里程碑审计**」——**批次**进 canonical，
   不是单个 packet 被卡住。

### 26.2 我们自己笔记的错误（必须更正的三处）

| # | 错误 | 更正 |
|---|---|---|
| **E6** | 笔记里同时存在 **3,361 B**（§20.1）、**4,334 B**（§18.5 ③ 行）、**4,903 B**（对话）三个数 | 直接读账本实测：**待接入 = 3,361 B**（640 + 1,668 + 1,053）；**4,334 B** 是**命令脚本类全体**（1,668 待接入 + 1,542 pointer-pool + 1,124 fixed-renderer）；**4,903 B 是算错的**（只加了 pointer-pool 却点名 fixed-renderer） |
| **E7** | 「政策明禁合计」 | 仓库里**没有**这六个字，是我们的转述。原文是**五条**不同措辞的禁令（`AGENTS.md:41` 合并异构证据 / `remaining-reverse-work-plan:302` 不得硬拼凑4包 / `rom-release-gate-work-plan:95` 不能把不同信任边界合并凑审计次数 / `rom-renderer-records-delta-tier1:88-89` 不能为凑包数拆相邻同边界记录 / `sequel-roadmap:153-154` 这两包**分开**） |
| **E9/E10** | 把 pointer-pool + fixed-renderer 算进「同类待接入 4 个」；把 M1 当新类 | `AGENTS.md:36` 字面是「同类**待接入**」——这两个包**已在账本里**（实测 2,666 B），按字面**不计入**；M1 的 `primary_class` 与既有 `rom-fixed-animation-descriptor-groups-v1` **完全同名**，接入后并为 1,776 B，是**向既有类追加**不是新类 |

### 26.3 账本实测（`sequel/rom-byte-coverage.json` SHA `9f8a8196…`）

| `primary_class` | 账本现状 | 待接入 |
|---|---|---:|
| `fixed_cfg_consumer_renderer_command_script` | 31 claims / 2,666 B | 1,668 B |
| `fixed_cfg_consumer_renderer_display_text` | **不存在（0 claims）** | 1,053 B |
| `fixed_consumer_animation_descriptor_group_bytes` | 1 claim / 1,136 B | 640 B（并为 1,776 B） |

⇒ 待接入 **3 包 / 3,361 B / 3 个不同 class 各 1 个** = **0.0534 pp** ⇒ 三门槛全不满足。

### 26.4 历史先例给出的两条出路

- **宽义是既成事实**：2026-09-01（7,140 B 四包，`proof.json:4966`）与
  2026-09-02（gross 8,083 B → **净增 4,738 B / 0.0753 pp** 四包，
  `sequel-roadmap.md:3860-3862`、`:3895-3897`）**都跨 primary_class**，
  却按「4 packets」放行 ⇒ 实践中"同类"被解释得**很宽**。
- **最干净的「不通过」样本正是我们这一对**：2026-10-01
  `sequel-roadmap.md:153-154` —— 新显示文本 1 包 + 旧命令脚本 1 包 = 2,721 B，
  「**分开**…未达同类/净增门槛，不做Tier-2」。**同样的两包，今天仍然不接。**
- 但**118 B 四包通过**（2026-09-30，`notes/rom-small-cfg-dependency-tier2-20260930.md:16`）
  证明「4-packet 计数」这条路成本极低 ⇒ **补第 4 个包比等字节数现实**。
  只是必须**新做逆向证据**：12 B 孤儿包是命令脚本包 1,668 B 的**逐字节真子集**，
  接进去会让 `atomize_claims` 抛 `conflicting primary claims` ⇒ **绝不能接**。

---

## 27. 推进速度瓶颈：收据级证据链（2026-10-20 09:4x）

### 27.1 「4 路并发反而更慢」：三个候选，逐一给证据

| 候选 | 判定 | 依据 |
|---|---|---|
| 覆盖段与验证器段**重叠** | **结构性排除** | `tools/audit_reverse_engineering_proof.py:1149` 覆盖门 `_check_rom_gate` 先跑完，`:1209` 才起验证器池；同进程严格顺序。`run_formal_parallel.sh:37-46` 只起一个进程 |
| **并发本身变慢** | **无证据** | 池是 `ThreadPoolExecutor(max_workers=jobs)` + `subprocess`（`:904-918`），无共享可变状态、无锁；结果按原 group 序号重排（`:919`）保证顺序与串行一致；108 项全 `contract_ok: true` / `exit 0`，无超时无重试 |
| **宿主争用** | **只有自述，收据层面对账为负** | 窗口 `2026-10-19T20:39:40Z–21:44:45Z` 内，`notes/**/*.json` 的时间戳**只有 2 条**（formal 自身）。全仓 476 份 guard 收据**无一份**落在窗口内。**根因是结构性的：回归套件与探针不走 guard，所以永远不会有 guard.json** ⇒ 该自述**天然无法被收据证实或否证** |

⇒ **诚实结论：在补上「每验证器耗时」与「有效并发度」两项记录之前，
不能断言 2.7× 是宿主争用。** 两个互斥解释都还活着：
「最长单验证器封顶」（v9 确实在列表里，但其 1,080 s 无收据）
与「宿主争用」（作者自述，窗口内无并发任务收据）。

### 27.2 有效并发度根本没被记录（这是可修的工程缺口）

`--verifier-jobs 4` 只是**请求值**。实际并发 = `_verifier_job_count(4)`
（`tools/audit_reverse_engineering_proof.py:846-866`），按**启动瞬间**的可用内存夹取
（`<2048 MiB → 1`、`<4096 MiB → 2`、否则 `≤4`；darwin 下
`available_physical_memory_mib()` = free + inactive + speculative，
`tools/project_resource_guard.py:133-152`）。
**该值既不写 report 也不写 guard 收据** ⇒ 那轮宿主 swap 已用 86%（3,542/4,096 MiB）、
负载 9.4–10.4 的情况下，**有效并发可能只有 2 甚至 1**，仓库里查不到实际值。

同理，**每个验证器的耗时也完全没被记录**：
`verifiers_executed` 的 108 项字段只有 `command/contract_ok/exit_code/label/labels`；
`formal-parallel-guard.json.stdout.log` 与 report **逐字节相同**（md5 `a9c9918…`），
无任何时间行；`tools/audit_reverse_engineering_proof.py` 全文**没有**
`monotonic`/`perf_counter`/`elapsed`。

**⇒ 这两条是「影响推进速度的瓶颈」里唯一还能靠工程手段消除的盲区**：
加两个字段（有效并发度 + 每验证器墙钟）就能把 2.7× 的归因变成可判定。
成本极低（只改报告 schema），但改审计器要同步 spec SHA + 重跑 formal。

### 27.3 「瓶颈真实咬过人」的异常收据（全仓 476 份 guard 收据扫描）

分母：`notes/evidence/**` 下 476 份 guard 收据（含 `reason`/`started_at`），
另 25 份 mGBA 的 `guard.json.done.json` 非收据 schema 已排除。
`reason` 分布：`completed` 310 ｜ `child-exit` 157 ｜ `idle-timeout` 5 ｜
`lock-busy` 3 ｜ `mgba-crash-report` 1。**`degraded: true` 的收据 0 份。**

| 时刻（UTC） | reason | exit | 墙钟 | 任务 |
|---|---|---:|---:|---|
| 10-19T17:23:45 | **child-exit** | **−15** | 5,071.8 s | 串行 formal 被 SIGTERM 杀掉 |
| 10-19T15:05:03.53 | **lock-busy** | **75** | 0.001 s | heavy 锁探针 0 / 1（2/2 被拒） |
| 10-01T13:11:12 | **idle-timeout** | **124** | 61.05 s | animation-object-native batch-v2 |
| 10-01T05:21:43 | **idle-timeout** | **124** | 60.08 s | animation-pool-lifecycle validation |
| 10-01T16:11:06 | **idle-timeout** | **124** | 61.02 s | map-roundtrip tdd/green |
| 09-30T11:41:42 | **idle-timeout** | **124** | 60.18 s | small-cfg-batch-publication green1 |
| 09-05T08:06:53 | **idle-timeout** | **124** | 120.54 s | legacy-acceptance candidate-verify-v1 |
| 10-01T03:02:26 | **mgba-crash-report** | **125** | 1.05 s | cutscene ptr-ab zero-baseline-1 |

- **没有 wall-timeout 的收据**（476 份中 0 次）；`wall-timeout` 代码路径在
  `tools/project_resource_guard.py:1037-1040`。
- 另有 2 条 idle-timeout 证据（coverage 审计 60.82 s / formal proof 60.24 s）
  **收据文件已不在树上**，只以 `stdout_tail` 内嵌在
  `notes/evidence/reverse-throughput-20261019-v1/throughput.json:85-200`。
- 5 次 idle-timeout 全部落在 **60–61 s** ⇒ 正是守卫**默认 idle 60 s** 的行为，
  已通过把默认改成 7,200 s 修掉（`tools/project_resource_guard.py:31-40`）。

### 27.4 机器级事实（标注采集时刻，过期的已标）

| 项 | 值 | 时刻 | 状态 |
|---|---|---|---|
| CPU 逻辑核 | 12 | 10-19T15:05Z | 稳定 |
| 物理内存 | 16.0 GiB | 10-20 08:0x | 稳定 |
| swap 总量/已用 | 2,048 / 1,240 MiB | 10-20 08:0x | **仓库内最新**（更早的 3,072/2,247 与 4,096/3,542 已过期） |
| 磁盘可用 | 74–77 GiB | 10-20 08:0x | **仓库内最新**（更早的 6.6–9.9 GiB / 96–98% 占用已过期） |
| 1 分钟负载 | 3.4–4.8 | 10-20 08:0x | **仓库内最新**（更早的 9.4–10.4、10.12 已过期） |
| **4 路 CPU 并行** | 串行 11.707 s → 并行 4.711 s，**加速 2.485×**，并行效率 **0.621** | 10-19T15:05Z | 实测 |
| **单线程瓶颈** | 覆盖审计器 CPU **100.0%（恰好 1 核）**，`ps` 连续观测 20+ 分钟 | 10-20 08:0x | 实测 |
| heavy 锁争用 | 2/2 并发受管运行被 `lock-busy`(75) 拒 | 10-19T15:05Z | 实测 |
| 守卫默认（现行代码） | wall **9000** / idle **7200** / min_avail 1024 MiB / max_rss 1536 MiB | 现行 | 已从 600/60 上调 |

**⇒ 瓶颈结论（诚实版）**：限制推进速度的第一因是覆盖审计器的**单线程算法**
（`atomize_claims` 被调 39 次，实测 60.50 s → 0.09 s，681×，占覆盖段 ≈54% 已消除），
**不是** CPU 核数，**不是**子代理数。剩下的 1,108 s 是 producer 内的验证器冷重放，
要再压需要改 97 个函数做两阶段拆分（高风险大改）。
宿主侧（16 GiB / 12 核 / 2 GiB swap）**不是**当前瓶颈。

---

## 28. D0「bank 字段穷尽」：闸门真身与真实量级（2026-10-20 09:4x）

完整证据链已固化为 **`notes/d0-bank-exhaustion-gate-20261020.md`**。要点：

### 28.1 原来的二选一（A 静态闭包 vs B 79 次采集）框架本身有问题

1. **`natural_gameplay_all_ids_proven` 不是闸门，也不是阻塞源**。
   它是一个被哈希钉死的「**不夸大**标记」——
   `tools/audit_rom_byte_coverage.py:29523`/`:29532` 只对 scope **字典整体**做相等性
   比对，**从不对其中任何布尔量做 `if` 分支**；
   把它改成 `true` 反而会让审计器 **raise**（fail-closed，防静默超额声明）。
   `grep -n "natural_gameplay" tools/audit_reverse_engineering_proof.py` → **零命中**；
   `sequel/bank-proofs.json` 里也没有这个字段。
2. **真正的闸门**在 `tools/audit_reverse_engineering_proof.py:648-679`，判三条：
   ① `coverage.status == "exhaustive"` ② `record_ids_covered == record_ids_total`
   ③ 存在哈希绑定了 record/field/bank/evidence 四组 ID 的 verifier 合同。
3. **字节层早已 100% 入账**：region `[5903744, 5906800)` = 3,056 B / 159 段 /
   **unknown 0**（指针表 316 B + 文本与间隙 2,740 B），2 个消费者已绑定
   （`0x08098624` / `0x08099D58`）。⇒ D0 是 **bank 完结判定**问题，
   **不是字节晋升问题**。
4. **D0 的真实量级不是 79 条**：同一份 175-blocker 报告里，
   `coverage_status_not_exhaustive` / `record_coverage_not_id_bound` /
   `no_exhaustive_contract` **各 22 条**；`declared_runtime_record_coverage`
   = **{records_covered: 23, records_total: 2954}**；
   `docs/final-completion-report.md:29-30` 写「有效 bank 全记录/字段穷尽 **0 / 22**」。
   ⇒ **D0 决定 22 个 bank / 2,954 条记录 / 25,543 个 record×field 单元的完结判定；
   data-table-b 的 79 条只占 2.7%。**

### 28.2 方案 B 的成本差是**两到三个数量级**，不是「一个数量级」

| 组成 | 量级 | 标注 |
|---|---|---|
| 纯 emulator 时间 | 79 × 2 × 6.35 s ≈ **16.7 分钟** | [实测单次外推]，来源 `artifacts/data-table-b-message0-pointer-pixel-ab-v1/raw.tar` 的 `guard.json`（baseline 6.357 s / candidate 6.335 s） |
| 含 ROM 重建的单条端到端 | ≈ **80 s/条 ⇒ 79 条 ≈ 1.8 小时** | [由实测时间戳推导] |
| **route 发现**（真正的成本大头） | battle-effect 同构 campaign：18 组 / **8 天**（2026-08-01→08-09） | [类比推算] 79 组外推 ⇒ **24–40 工作日** |
| 结构性放大因子 | 79 个 message ID ↔ 79 个战斗/特效 descriptor **一对一**（`sequel/content/data-table-b/bank.json` notes 原文）⇒ route 发现次数 ≈ **79 而不是 1** | 原文直述 |

**⇒ 只看 emulator 时间会把 B 与 A 的差距看成「分钟级 vs 零」，严重低估。**
另有一个硬约束：现有探针 `tools/build_battle_message_runtime_probe.py:31-54` 每次命中
都写**同一个** `SCRATCH = 0x0203FD60`，**一次 run 只能产出一条 ID 的证据**。

### 28.3 仓库里已有 5 类中间方案先例

- `sequel/bank-proofs.json` 的 `coverage.status` **已有 17 种 denomination**，
  data-table-b 用的是 `artifact_verified_natural_route`（1/79）；
  **没有任何一个 bank 是 `"exhaustive"`** ⇒
  「静态闭包 + 代表性运行时抽样 + 显式未覆盖分母」就是既有正式口径。
- **typed partial contract 工具链已存在**：
  `tools/verify_data_table_b_partial_bank.py` +
  `tools/data/data-table-b-partial-bank-contract-v1.json`
  （1/79 覆盖 + **78 个单元显式列入 `cells_uncovered`**，exhaustive=false，
  离线重放仅 **4.14 s**）。⚠️ 状态是**候选**，未入正式 catalog
  （`notes/rom-data-table-b-partial-bank-20261001.md:66` 原文：
  "proposal.json 仅作候选，**没有写入 sequel/bank-proofs.json**"）。
- **分数式「N/79」** 已在用（`artifacts/battle-effect-group18-natural-pixel-ab-v1`：
  `"production_natural_pixel_ab": "9/18"`）。
- **107 个已提交 artifact** 带 false 自然标记**且都已入账** ⇒
  「静态闭包已提交、运行时标记留 false」是全仓库既定做法。
- **OpenSpec 已把「单条代表性 A/B + 显式降级」写成正式任务**
  （`openspec/changes/upgrade-remaining-runtime-banks/tasks.md:22-23`）。

### 28.4 建议：把 D0 拆成两个独立判据

- 仓库已把「静态闭包穷尽」与「运行时自然可达」拆成**两个不同的 scope 字段**
  （`fixed_79_slot_denominator_complete` vs `natural_gameplay_all_ids_proven`），
  且 `docs/reverse-engineering-proof-policy.md:123` 明文要求
  「控制物化、自然入口和实体硬件**分别声明**」⇒
  **把 D0 合成一个布尔量本身就违反仓库自己的分声明原则。**
- 最小落法：保留 `natural_gameplay_all_ids_proven=false` 不动；
  在 `sequel/bank-proofs.json` 加第三维（允许 `partial_explicit_denominator` +
  `records_uncovered` 显式列表），复用已写好的 typed partial 合同；
  改 `audit_reverse_engineering_proof.py:648-679` 接受「显式未覆盖分母」为合法态，
  **保留** policy 第 5 条对最终 100% 声明的要求；
  同步 spec 的 `bank_proofs.sha256` + 审计器 SHA → 重跑 1 次 formal（~24.4 min）。
  `notes/rom-data-table-b-partial-bank-20261001.md:65-66` 已预演过这个接入动作：
  "真实 auditor 的 CLI contract_ok=true，但 partial bank complete=false，保留 4 个局部
  blockers" ⇒ **脚本和合同都已就绪，只差 policy 决策**。
- **若坚持 B**：先做一个抽样探针测 `k` = 一次 battle run 最多能自然产出多少个不同
  message ID。这直接把 B 从「79 条 route」降到「约 79/k 条 route」，
  是**唯一能把 B 的成本从数周压到可裁决区间的信息**，成本约 1 个工作日。

---

### 18.5 待裁决项（证据已齐，等口径）

| # | 事项 | 关键实测证据 | 决策点 |
|---|---|---|---|
| ① | psg 修复路线 | legacy 活账本路径**在设计上**只认冻结状态；bundle 门绿 | 走「只改测试对齐 bundle 合同」（**已完成**，零 formal 成本）还是「连 legacy+导出器一起修、artifact 重落地」（需一次 formal） |
| ② | **D0** bank 字段穷尽定义 | **完整证据链见 `notes/d0-bank-exhaustion-gate-20261020.md`**。原问题框架有误：①`natural_gameplay_all_ids_proven` **不是闸门**（是 fail-closed 的「不夸大」钉，改 true 反而 raise），真闸门在 `audit_reverse_engineering_proof.py:648-679`；②字节层**已 100% 入账**（3,056 B / unknown 0）；③**真实量级是 22 bank / 2,954 记录 / 25,543 单元**，data-table-b 的 79 条只占 2.7%；④B 的成本差是**两到三个数量级**（emulator 仅 16.7 min，但 route 发现 24–40 工作日） | 走**中间方案**（把「静态闭包穷尽」与「运行时自然可达」拆成两个判据，typed partial 合同工具链已就绪、离线重放 4.14 s、仓库已有 5 类先例）还是坚持 B（先做 1 天的 `k` 抽样探针把成本从「数周」变成可裁决数字） |
| ③ | **Tier-2 门槛** | **口径原文与先例已固化到 `notes/tier2-threshold-policy-source-20261020.md`**。三个门槛**全不满足**：待接入 3 包 = 3,361 B = **0.0534 pp**，字节门槛**有效值是 9,437 B**（0.15 pp 换算，比 10 KiB 低 803 B）、同类待接入按 `primary_class` 每类各 1 个 | 三点待裁：①「同类」按 `primary_class` / `promotion_batch` / 文字信任边界哪个判（**原文无定义**）② 窄义（同批次内同边界）还是宽义（历史先例 09-01、09-02 两批**跨 primary_class 放行**）③「待接入」是否排除已入账包（`AGENTS.md:36` 字面排除） |
| ④ | `sprite_loader_tail` 的 purelib workaround | **已实测出零脚本改动的解法**（§25.1）：改 spec 删 `-S`，`-I` 下 Pillow 可见、验证器 SHA 与 artifact 全不变、零 SHA 连锁 | 接受「重新暴露 system site-packages」这点隔离度取舍 + 一次 formal？还是坚持原方案（改验证器源码 → 四级 SHA 连锁） |





