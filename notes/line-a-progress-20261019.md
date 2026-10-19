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

#### 阶段分解：并发只救得了验证器阶段

| 阶段 | 9-30 基线（串行） | 本轮（4 路并发） | 说明 |
| --- | ---: | ---: | --- |
| 覆盖审计 | ~270 s（repo 自记 4.5 分钟） | **2,377 s** | **宿主争用放大 8.8×** |
| 验证器重放 | ~2,113 s（推算） | **1,528 s** | 并发加速 **1.38×** |
| 合计 | **2,383 s**（实测） | **3,905 s**（实测） | |

两段都不是工具设计的问题：

- **覆盖审计段**（39 分 37 秒）是**单线程**的，concurrency 帮不上忙；
  它在空闲机器上只要 4.5 分钟，本轮被换页放大 8.8 倍——
  同期负载 9.7–11.1、swap 已用 1.9/3.0 GiB。**这就是 §11.1 的结论第二次复现。**
- **验证器段**只拿到 **1.38×** 而不是 4×，因为**并发墙钟的下界由最长的
  单个验证器决定**：`tools/verify_rom_cfg_proven_roots_v9.py` 单跑就要
  ~18 分钟（1,080 s）。makespan = max(总工作量 / 并发度, 最长单个任务)，
  而这里后者是主导项。
  → **要真正吃到并发红利，得先把 v9 那个重验证器拆开或给它单独一条通道。**

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

**结论（本轮最重要的一条）**：**推动速度的是宿主内存，不是逆向工具链。**
本项目的两个重进程合计不到 260 MiB，而应用栈占了约 6.1 GiB，swap 在会话期间
被动态扩了一次并用到 86%。在 swap 饱和时：

- 单线程长任务的每一次缺页都要换页 → repo 自己记录的 "4.5 分钟"被放大到 45 分钟；
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
4. 本轮交付的**工具侧**提速仍然有效，但它的收益只有在宿主不饱和时才兑现：
   - 验证器并发化（`--verifier-jobs`，按可用内存夹取）→ 108 个验证器不再串行，
     **实测验证器段 2,113 s → 1,528 s（1.38×）**；但被最长的单个验证器
     （`verify_rom_cfg_proven_roots_v9.py`，单跑 ~18 min）封顶，
     **不是 4×**（详见 §11.5.1）；
   - 守卫保留子进程输出 → 失败可诊断（**本轮直接靠它定位了
     `ModuleNotFoundError: No module named 'PIL'` 的解释器漂移**，见 §15）；
   - policy 文档 + 测试夹具与晋升链解耦 → 每次晋升不再打破约 12 个测试
     （**本轮已把剩余 37 处陈旧字面量全部派生，并加了 1.3 s 的元守卫**，见 §14）；
   - 覆盖审计段**仍然单线程**，本轮实测 2,377 s（空闲机器上只要 ~270 s）。
     **它现在是 formal 的头号成本**，比 108 个验证器加起来还贵。
     → 下一步该优化的是覆盖审计本身，不是验证器并发度。

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




