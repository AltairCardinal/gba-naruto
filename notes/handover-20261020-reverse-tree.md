# 逆向树交接文档 —— 2026-10-20（宿主机器退役）

本文件是 `codex/reverse-engineering` 分支在 2026-10-20 收尾时的完整交接。
接手方（另一台 Windows 机器）应先读本文件，再读 `notes/four-decisions-20261020.md`
与 `notes/live-ledger-identity-repair-20261020.md`。

> 术语红线：**「测试通过数」「轨迹数」「收据数」都不是逆向完成量。**
> 完成量只有一个口径：账本 `sequel/rom-byte-coverage.json` 的
> `summary.classified_bytes / ROM_SIZE`。

---

## 1. 一句话状态

甲线（覆盖驱动）本轮把 **Tier-2 门槛例外三包晋升入账**（3,361 B）、
**修完全部 12 个测试失败**、**93 套件在晋升后重跑全绿**、
**四道用户裁决全部落档**、**D0 契约 v2 修红**、**D0 多槽探针真机验证通过**；
**三道裁决的代码改动（④ purelib / ③ psg / ② 探针续作）尚未执行**，
其中 ③ 与 ④ 会改动被 pin 的脚本，**必须一次做完、只跑一次账本重建与一次 formal**。

---

## 2. 已完成并已推送的成果

逆向树 `/Users/altair/github/gba-naruto-reverse`（`codex/reverse-engineering`），
本轮共 9 个提交（截至 `222b833c`，之后本文件与 D0 成果再增 1 个）：

| 提交 | 内容 |
| --- | --- |
| `362c3c40` | 修 9 个失败 + 根因定量（90/90 生产者全部无法干净重放） |
| `063352d9` | 子代理 AST 扫描又找出 3 个真实失败（DirectSound / 审计总用例 / c4cc）+ AGENTS.md 登记表 |
| `97b90213` | 资源瓶颈实测补记（主因是进程超订 + 内存压力，不是磁盘/CPU） |
| `511f6c3e` | 回填 93 套件重跑结果（晋升前那次 93/93 OK，1,384.330 s） |
| `a2d3082a` | Tier-2 门槛例外三包晋升入账 + 四道裁决落档 |
| `ce9fb789` | 回填 formal v3 收据（175 blockers 零新增）+ roadmap 三包入账条目 |
| `222b833c` | D0 方案 B 探针结构实测（单槽为何只能记一条 ID） |
| 本次 | D0 契约 v2 修红 + 多槽探针真机验证 + 活账本身份系统性发现 + 交接文档 |

### 2.1 覆盖度分母（唯一权威口径）

```
sequel/rom-byte-coverage.json
  unknown_bytes      82,728
  classified_bytes  6,208,728
  claim_count        17,028
  segment_count      18,882
  完成度            98.68507385253906%
  ledger sha256     d34672a8f41adb6206b54f5324c8ff1220c302d916576a8ae8d7251033e1e88d
```

```
sequel/reverse-engineering-proof.json
  spec sha256        754042fef0a6ac64ef72ab57397791dd23a55c6a32408bf545f620f198b5403b
  trust_anchor.spec_sha256 由本次 formal 现算写入（不是外部钉；verified=false 是设计）
tools/audit_rom_byte_coverage.py
  auditor sha256     ea5b8b5050880cdea63133bf7000a61fb99664bb4cf8ab85e705f8406075b5ed
```

### 2.2 formal v3（晋升后的正式收据）

`notes/evidence/reverse-proof-update-20261020-v3/formal-run.log`

```
exit 0 / wall 1,349 s / blockers 175（零新增零减少）
verifiers_executed 109 / failed_verifiers []
```

### 2.3 93 套件（晋升后重跑，已完成）

`notes/evidence/auditor-module-shards-20261020-v1/proof-suite11.log`

```
Ran 93 tests in 2691.708s — OK（0 FAIL / 0 ERROR）
```

含最重的 `test_current_repository_does_not_overclaim_completion`（进程内跑完整 formal）
⇒ 「不夸大完成度」这条红线在晋升后依然成立。

### 2.4 D0 裁决②（本轮新增，已绿）

- `tools/data/data-table-b-partial-bank-contract-v2.json`（v1 保持原样不动）
  - 关键修正：`tools/project_resource_guard.py` 从「活树输入」改归
    **`frozen_capture_inputs`（采集时冻结 provenance）**。
    理由：离线重放**从不执行**该 guard，它只在 2026-08-09 采集时被用过；
    把它绑死在活树上，会让「guard 后来改了」直接误判为「证据漂移」。
  - v2 里其余 21 项输入逐字节与 v1 相同，只改了这一项归属。
- `tools/verify_data_table_b_partial_bank.py`：契约指向 v2，
  `load_contract` 新增「冻结组与活树组不得重叠、摘要须 64 位十六进制」的失败关闭检查，
  legacy 实现绑定改为「manifest 实现表 vs（活树输入 ∪ 冻结组）」。
- `tests/test_data_table_b_partial_bank.py`：**14/14 绿**。
  其中 `test_frozen_legacy_verifier_agrees` 改为用 legacy 的内层离线重建
  `collect_evidence` 做交叉核对，并**显式钉住** legacy 整包验收现在只因
  `project_resource_guard.py` 一项而失败（防止它日后以别的理由失败而无人察觉）。
- **多槽探针**（新文件 `tools/build_battle_message_runtime_probe_slots.py`）：
  - **不修改**被 legacy artifact manifest 冻结的旧探针
    （`tools/build_battle_message_runtime_probe.py` 的 sha 被 manifest 钉死，
    改了会让 D0 离线重放失效）⇒ 多槽必须是新工具。
  - 槽表地址 `0x0203F174`（4 字节对齐），79 槽 × 16 B = 1,264 B，
    落在 `0x0203F173..0x0203FD60` 内，**不与 legacy scratch `0x0203FD60` 重叠**。
  - 该空闲区是**实测**的：对 4 份归档 mGBA 存档（scenario-50 输入 checkpoint
    + 归档 baseline/candidate 输出）求 EWRAM 共同零区得到 3,053 B，不是猜的。
  - 工具内置**等价性自检**：关掉槽代码时生成的 stub 与旧探针的 stub **逐字节相同**。
  - **真机验证通过**：`notes/evidence/d0-multi-slot-probe-20261020/runtime-verification.json`
    —— 用自建 mGBA（d8bad14b）跑同一场景，槽表精确记录
    `message_id=0, hit_count=1, selected_pointer=0x085A1580`，
    与 legacy scratch 一致；**截图与归档 baseline.png 逐字节相同**（槽代码不扰动游戏）。
  - `tests/test_build_battle_message_runtime_probe_slots.py`：8/8 绿。

---

## 3. 未闭合项（诚实清单）

1. **整模块 `tests.test_audit_rom_byte_coverage` 全量重跑未完成**。
   4 片（均衡分片，3/4/3/4 次 manifest 重建）在宿主退役时各跑到
   **1/7/7/6 个用例通过、0 失败**（约 8%），被按精确 PID 停止。
   **因此「整模块全绿」这一条不成立**；分片清单与日志在
   `notes/evidence/auditor-module-shards-20261020-v1/`。
   新机器上应重跑（见 §4.1），预计 1.5–2 h。
2. **三道裁决的代码改动未执行**：④ purelib 加固、③ psg 链时身份、② 探针续作（见 §4）。
3. **D0 闸门本身未闭合**：`data-table-b` 仍是 `records_covered 1 / 79`
   （只有 message 0 有 A/B 指针证据），`catalog_classification` 仍不是穷尽。
   79 条采集需要真实运行到 79 个不同消息状态，本轮只证明了**采集载具可用**。
4. **179 处重放点中 98 处潜在脆弱**（拿最终账本重放已晋升生产者）：
   需要一个「按生产链顺序自动剔本包 + 其后所有批次」的链时基线 helper，
   一次覆盖 31 个类。**注意：不能一刀切剔后继批次**
   （`_task_scheduler_core_claims` 明确要求后继批次在基线里）。
5. 审计器里 **174 处 `_TEST_SHA256`**（62 个被钉上游测试文件）的系统性 pin 问题未处理。
6. 「producer 内冷重放」优化未做（需改 97 个函数 + 两阶段拆分，高风险）。
7. 元守卫补强两条规则（接收者是局部变量的全局量、全局量摘要）未做
   （现在改元守卫不需要重跑 formal）。

---

## 4. 下一步（按此顺序，一次做完只跑一次账本重建 + 一次 formal）

### 4.1 先把整模块补跑绿

```bash
cd /Users/altair/github/gba-naruto-reverse
# 分片清单已存在 notes/evidence/auditor-module-shards-20261020-v1/shardB{0..3}.txt
for k in 0 1 2 3; do ( cd /Users/altair/github/gba-naruto-reverse && \
  PYTHONUNBUFFERED=1 nohup /usr/local/bin/python3 -m unittest -v \
  $(cat notes/evidence/auditor-module-shards-20261020-v1/shardB$k.txt | tr '\n' ' ') \
  > /tmp/auditor-v4-shard$k.log 2>&1 & ) ; done
```

### 4.2 ④ + ③ + 4 个红导出器：一次改完（**期间不要动被 pin 的文件**）

**先读** `notes/live-ledger-identity-repair-20261020.md`（含实测证据与逐项偏差说明）。

被改文件清单：

| 文件 | 改什么 |
| --- | --- |
| `tools/export_rom_sprite_loader_tail.py` | 补 `BASELINE_SUMMARY` + 移植验证器的 `_validate_coverage`（post 模式）+ purelib 候选补全 |
| `tools/verify_rom_sprite_loader_tail.py` | purelib 候选补全（当前解释器 + 系统 + venv，**只补同 minor 版本**，PIL 是 C 扩展） |
| `tools/export_rom_chapter_selector_code_slice.py` | 同上（post 模式） |
| `tools/export_rom_profile_selector_code_slices.py` | 同上（post 模式） |
| `tools/export_rom_battle_status_bar_caller_slice.py` | 同上（post 模式） |
| `tools/export_rom_psg_frequency_lookup.py` | 整账本摘要 → 链时语义身份 |
| `tools/verify_rom_psg_frequency_lookup.py` | 同上（legacy 验证器） |
| `tools/audit_rom_byte_coverage.py` | 更新 4 个包的 manifest/payload/verifier SHA pin + psg manifest SHA pin |

**为什么必须一起改**：4 个导出器测试模块现在**红 23 项**（本轮晋升打红，
不在 93 套件也不在整模块覆盖范围内），根因全是「以整账本 SHA 做身份」；
验证器侧仓库早已有正确的 `baseline/post` 双模式，导出器侧照抄即可。

**为什么必须重跑账本**：账本 claim 里内嵌
`evidence_sha256` / `promotion_manifest_sha256` / `independent_verifier_sha256` /
`independent_verifier_report_sha256` ⇒ 重新落地 artifact ⇒ 这四个值变 ⇒ 账本字节变。

**落地顺序**（否则导出器会拒绝覆盖，见 notes §3.3）：
先移走旧 artifact 目录 → 改完脚本 → 重新落地 5 个 artifact → 更新 audit pin →
受管重建账本 → 同步 spec → 一次 formal。

```bash
# 受管重建账本（wall/idle 必须抬高，默认 600/60 会静默杀掉重活）
/usr/local/bin/python3 tools/run_guarded.py \
  --summary notes/evidence/reverse-proof-update-20261020-v4/ledger-guard.json \
  --lock-file build/resource-guard/heavy.lock \
  --cwd . --wall-timeout-s 9000 --idle-timeout-s 7200 \
  -- /usr/local/bin/python3 tools/audit_rom_byte_coverage.py --root . --write

# 一次 formal：系统解释器 + **不得**把 .venv 前置到 PATH
bash notes/evidence/reverse-proof-update-20261020-v4/run_formal.sh
```

spec 要同步的**不是 3 个值**（cron 里的旧说法有误）：按改动面逐项重算，
sprite-loader-tail 一包即 5 个值（审计器 sha、验证器 sha、2 个 evidence sha、账本 sha）。

### 4.3 ② D0 续作

- 探针载具已就绪（§2.4）。下一步是**采集**：对 79 个消息状态各跑一次，
  用多槽探针一次记录该次运行碰到的所有 ID。
- 采集必须走受管启动器 `tools/run_macos_mgba_input_sequence.py`
  （它会校验工具链 profile，profile 缺失即失败关闭）。
  **本机的 mGBA 构建在 Windows 上不存在**，见 §5.2。

---

## 5. 平台迁移须知（macOS → Windows）

### 5.1 仓库与解释器

- 两个仓库都要 clone：
  - 逆向树 `https://github.com/AltairCardinal/gba-naruto.git` 分支 `codex/reverse-engineering`
  - 主树 `gba-naruto` 分支 `codex/butano-foundation-research`
- `rom/base.gba`（6,291,456 B，sha `1198ece7…`）**已跟踪在 git 里**，clone 即得。
- 归档 checkpoint `artifacts/runtime-checkpoints/scenario-50-action7-shadow-clone-confirmation.ss9`
  也已跟踪。
- **解释器必须 ≥ 3.10**：审计器 `MINIMUM_PYTHON = (3, 10)`；
  仓库大量使用 `zip(strict=True)`，3.9 直接炸（报 `zip() takes no keyword arguments`）。
- 反向树 `.venv` 已锁 3.14.3，但 **venv 里没有 PIL**（只有 pip），
  且 venv 的 purelib 是空的 ⇒ 跑 `-I -S` 的验证器时 PIL 会 import 失败，
  这正是裁决④ 要修的那条（第 176 个 blocker 的真因）。
- 正式 formal 必须用**系统解释器**，且**不得**把 `.venv/bin` 前置到 PATH：
  `tools/audit_reverse_engineering_proof.py:470` 用 `sys.executable` 顶替 spec 里的 `"python3"`
  ⇒ 解释器换谁，子验证器就换谁。

### 5.2 mGBA 运行时链路（本机专属，Windows 上要重建）

本轮实测结论：

- `/Users/altair/github/mgba-build-c16/...`（旧自定义构建）：**已损坏**，
  其 `libmgba.0.11.dylib` 随 `/tmp` 清理消失 ⇒ 不可用。
- Homebrew mGBA 0.10.5：**不支持 `--script`** ⇒ 跑不了 lua 采集脚本。
- `/Users/altair/github/mgba-build-qt/qt/mGBA.app/Contents/MacOS/mGBA`
  （sha `c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8`，
  version `0.11-1-d8bad14`）：**可用**，支持 `--script`。
  源树 `/Users/altair/github/mgba-src` @ `d8bad14b4540f9114246c0281d74985cf81adc68`
  （= 仓库声明的 `CURRENT_MGBA_SOURCE_COMMIT`）。
- 本轮用它复现了归档采集：**截图与归档 baseline.png 逐字节相同**，
  legacy scratch 六个字段全等 ⇒ 运行时链路可信。
- **Windows 上必须重新构建 mGBA**（Qt 版，源码同一 commit d8bad14b）。
  重建后二进制 sha 会变 ⇒ `tools/macos_mgba_toolchain_profile.py` 声明的
  `CURRENT_TOOLCHAIN_PROFILE_SHA256` / `CURRENT_MGBA_SOURCE_COMMIT` 与
  工具链 profile 都要重新生成并同步；**不得**沿用 macOS 的二进制 sha。
  仓库已有重建脚本 `tools/build_macos_mgba.py`（macOS 专用）与
  `docs/butano-antigravity-video-review.md`（记录 `--sandbox --dangerously-skip-permissions`
  必须成对使用、`webm_encoder` 在 macOS 不可用、`-fps_mode passthrough` 必需）。

### 5.3 资源守卫

- 重活一律经 `tools/run_guarded.py`（heavy lock `build/resource-guard/heavy.lock`，
  busy 即 exit 75 ⇒ **必须串行**）。
- **wall 9000 / idle 7200**；默认 600/60 会把重活静默杀掉，表现为 exit 124，
  看起来像「工具卡住」而不是「被守卫杀了」。
- idle 的定义是「无完整输出行的时长」⇒ 对**末尾才一次性输出**的工具，
  idle 闸门等于运行时间上限。
- 守卫的重活必须**显式抬高 idle 超时**，否则 coverage 审计与正式 proof 会被误杀。

### 5.4 本机专属、下台机器没有的东西

- `/Users/altair/archives/gba-naruto-reverse-active-20261020.tar`（2.2 GiB 活跃实验归档）
- `/Users/altair/github/mgba-src`、`mgba-build`、`mgba-build-qt`、`mgba-build-c16`
- 会话快照：`/Users/altair/.minimax/v2/sessions/2026/10/19/14-24-41-384-*/snapshots`
  （四道裁决的**原始问卷选项 ID**就是从 `g000000000002--ctx_63f48c4c-…jsonl` 第 127 行找回的；
  以后再遇到「选项与题面对应关系」，别猜，去快照里取。）
- 主树 `/Users/altair/github/gba-naruto` 的 `AGENTS.md` 处于 `MM`
  （Butano 复刻会话的在飞改动，**未提交**）⇒ 换机器前要么先提交它，要么把那 8 行
  手工带过去；本轮**没有**碰它。

---

## 6. 已知坑（别再踩）

1. **禁止 `pkill -f` 宽模式**：会误杀同仓库并行跑（子代理曾差点命中）。
   要清理就按 PID 精确 kill。
2. **同一轮 cron 可能重复拉起分片并截断同名日志** ⇒ 长跑一律用独立日志名。
3. `unittest -v` 输出走 stderr，重定向到文件时**块缓冲** ⇒
   「0 字节日志」≠ 卡死；判活性用 `ps -o time=` **两次采样差**。
4. macOS `ps -o %cpu` 是衰减均值会骗人。
5. `tools/experiment_workspace.py promote` 的 `--root` 必须放在子命令**之前**。
6. `cd X && nohup ... &` 会把整个列表丢进后台子 shell ⇒ 写成 `( cd X && nohup ... & )`。
7. `pgrep -f` 会匹配自身 ⇒ 用 `ps -axo pid,ppid,state,etime,%cpu,command | awk '$1==<pid>'`。
8. **改任一被 proof 钉住 SHA 的脚本后，必须同步 `sequel/reverse-engineering-proof.json` 的
   `script_sha256`**；漏同步 ⇒ formal 直接多出 blocker。
9. **量分类按「是否随晋升变化」**：全局量/累计量 → 派生（或写成「界」）；
   批次增量 → 保持硬编码。**界的方向必须按键名/语义判，不能按「表达式有无减号」判**
   （元组改写的减号启发式是 17 处缺陷的根因，已全部还原）。
10. **段表 = 主 claim 表的逐字节投影**（实测全局成立）⇒ 硬编码段区间键一律换成逐字节派生比对。
11. **链时不变式 ≠ 账本时不变式**：生产者的 current-unknown 门要链时基线
    （剔本包 + 剔后继批次），不能用最终账本。
12. **故意喂活账本以断言 fail-closed 的站点不要改**
    （`tests/test_audit_rom_byte_coverage.py` 的 `:2017`/`:3654`/`:3844`/`:4081`）。
13. **只有带 `/schema` 的 verifier 报告才能进 spec 的 `verifiers`**
    （否则 `_contract()` 拒收并新增 blocker）⇒ 其余只进 evidence 哈希绑定。
14. **本轮新发现（务必读 notes）**：41+ 个工具以整账本 SHA 做身份。
    晋升 ⇒ 导出器红、验证器绿。四份活账本包的**验证器**已实现正确的
    `baseline/post` 双模式，**导出器**照抄即可；不要自己发明机制。

---

## 7. 新机器上的第一组命令（先确认环境，再动代码）

```bash
cd <reverse-tree>
python -V                                  # 必须 >= 3.10
python -m unittest tests.test_audit_reverse_engineering_coverage_count_liveness   # 元守卫 12 项
python -m unittest tests.test_data_table_b_partial_bank                          # D0 14 项
python -m unittest tests.test_build_battle_message_runtime_probe_slots           # 多槽 8 项
python -m unittest tests.test_export_rom_sprite_loader_tail \
                     tests.test_export_rom_chapter_selector_code_slice \
                     tests.test_export_rom_profile_selector_code_slices \
                     tests.test_export_rom_battle_status_bar_caller_slice        # 预期：现在红 23 项
git log --oneline -1 && git status --short
```

预期结果：前 3 组全绿，第 4 组红 23 项（这是**已知**回归，§4.2 要修，不是新问题）。
