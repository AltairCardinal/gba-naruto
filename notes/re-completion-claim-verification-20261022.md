# 「逆向已达 100%、没有任何需要补全的内容」这句话的核对（2026-10-22）

日期：2026-10-22
工作树 `/Users/altair/github/gba-naruto`（分支 `codex/butano-foundation-research`）
核对对象：`docs/re-completion-criteria.md` + `notes/completion-audit-20261020.md`
（同批产出由会话 `mvs_482e63e012d443d79f76d96492fac759` 落地，合并提交 `14b8381e`）

## 0. 结论

**这句话是对原声明的过度概括。** 准确的说法分三层：

1. **原声明本身是有范围的，而且写得很清楚**：「逆向完成」不是 ROM 的客观属性，
   而是**相对于「已声明范围」**的可机器复核断言（判据 P1/P2/P3，覆盖 47→49 个结构）。
   同一份文档 §6「**不可以宣称**」明确列了 21 条加固缺口，并说
   「整个 ROM 每一处都反编译完了」**不可宣称**。⇒ **原声明不是空话，但也不是「没有缺口」。**
2. **但声明自带的验收闸门当前是红的**，且闸门读数与文档 §5 的表格**不一致**：
   `tools/completion_audit.py --check` **退出码 1**（4 个失败探针）；
   工具实算 49 结构 / `none` = **5** / 阻塞缺口 = **3** / 写回可用 = **23**，
   而文档 §5 写的是 47 / 3 / 0 / 24。
3. **它与「复刻侧接线」是两条正交的轴**：逆向侧的结构闭合了，
   复刻侧仍有 **68 个已闭合族没人接**、**332 条结论没转门禁**。
   **「逆向 100%」不蕴含「复刻完成」，反之亦然。**

## 1. 逐条核验：声明自带的闸门

| 闸门 | 文档声称（§4「2026-10-21 实测」） | **本次实测（2026-10-22 11:0x）** | 结论 |
| --- | --- | --- | --- |
| `tools/completion_audit.py --check` | ✅ 退出码 0，`failed_probes=0` | ❌ **退出码 1，failed_probes=4** | **红灯** |
| `tools/automated_test.py` | ✅ **28/28 PASS** | ⚠️ 本次核查开始时 **11/28**（构建崩）；修复后 **28/28** | 见 §3 |
| `tools/alias_audit.py rom/base.gba` | ✅ `RESULT: OK` | ✅ `RESULT: OK`（0 不一致 / 0 未裁决 / 0 判死失败） | 绿 |
| `tools/writeback_paths.py` | ✅ 17 条全 PASS | ✅ **19/19 PASS** | 绿 |
| `node rom-editor/tools/verify_pack.mjs` | （新增） | ✅ **全部通过** | 绿 |
| `tools/table_registry.py` 基址 | ✅ 与 ROM 一致 | ✅ registry-vs-bank 不一致 **0** | 绿 |

⇒ **4 个闸门绿、1 个红。** 红灯的那一个恰好是**声明自己最核心的自证闸门**。

### 1.1 红灯的根因：证据探针写进了 gitignore 目录

4 个失败探针全部是同一个文件：

```
tool build/probe_items2.py: build/probe_items2.py 不存在   （×4）
```

- `.gitignore` 有 `build/*` ⇒ 该探针**从未进过仓库**；
- 它现在**连文件都不存在**（`build/*.py` 计数 = 0）；
- 依赖它的 4 个结构是：**`skills` / `items` / `mechanism-effects` / `resource-pointers`**，
  全部被判为 **L3（模拟器正常按键复现）**。

**这恰好触发了文档 §3 自己写的防自证规则**：
> 「证据必须是**已提交**的产物 —— 审计用 `git ls-files` 区分『仓库内持久证据』与
> 『只在本地存在的产物』；**`build/` 下未被跟踪的探针 JSON / 渲染 PNG 一律不作为证据**。」

⇒ **闸门判红是对的**：这 4 个结构的 L3 证据**别人复现不了**。
但审计的**等级分布仍把它们算作 L3**（等级表与探针表是两条独立信号），
所以**「L3 = 41」这个数字在探针补回之前有一处不该有的乐观**。

### 1.2 合并前也是红的（不是这次合并造成的）

在合并前的提交 `b35351db` 上复跑：

| 闸门 | 合入前 | 合入后 |
| --- | --- | --- |
| `completion_audit --check` | ❌ exit 1（4 个失败探针，但指向 `tools/consumer_locate.py` 未提及本结构地址） | ❌ exit 1（4 个失败探针，指向 `build/probe_items2.py` 不存在） |
| `tools/automated_test.py` | ❌ **11/28** | ❌ 11/28 |

⇒ **两个红灯都先于合并存在**，合并既没造成也没修掉它们。

## 2. 工具实算 vs 文档 §5 表格

| 指标 | 文档 §5 | 工具实算 | 差 |
| --- | ---: | ---: | --- |
| 审计覆盖结构数 | 47 | **49** | +2 |
| L4 / L3 / L2 / L1 / none | 3 / 41 / 0 / 0 / 3 | 3 / 41 / 0 / 0 / **5** | none +2 |
| 格式已被独立证明 | 44 / 47 | 44 / **49** | 分母 +2 |
| 写回路径可用 | 24 / 47 | **23** / 49 | **−1** |
| 失败探针 | **0** | **4** | +4 |
| 阻塞缺口 | **0** | **3** | +3 |
| 加固缺口 | 20 | 24（其中 3 条 blocking） | +4 |

**3 条阻塞缺口**（工具 `gaps[].blocking == true`）：

1. `battle-presentation-scripts` —— 格式未证明（无独立证据）
2. `battle-results` —— 格式未证明（无独立证据）
3. `units` —— 无可用写回路径

**5 个 `none` 级结构** = 3 个已退役（`sappy-engine` 已证伪 / `palettes` / `audio` 是别名窗口）
+ **2 个真的没有独立证据**（`battle-presentation-scripts` / `battle-results`）。

⇒ **P1（无独立证据 = 0）当前不成立**（是 5，不是 0）；**P3（阻塞缺口 = 0）当前不成立**（是 3，不是 0）。
**P2（三类必测面达 L3）成立。**

## 3. 声明之外：这次核查修好的东西（都不是「逆向」的缺口）

核查过程中发现**复刻侧**有两个真实构建缺陷，与逆向无关，但让**整个构建链是断的**：

| # | 位置 | 症状 | 根因 | 处置 |
| --- | --- | --- | --- | --- |
| 1 | `tools/build_mod.py` | `TypeError: ... not 'int'` | `import_dialogue_variable()` 的第 4 个位置参数是 `rom_path`，而 `free_space_end` 是**仅关键字**参数——调用方把它**按位置**传了进去，于是 `rom_path` 收到一个 int | 改成 `free_space_end=free_end` 关键字传参 |
| 2 | `tools/build_mod.py` | `change radius violation: 0x60DF0..0x60DF3` | `apply_pointer_redirect_patch()` 的**返回值**没带 `offset`/`length`，而改动半径检查正是从「已应用补丁自报的区间」算的 ⇒ 指针写入看起来像「未声明的写入」 | 返回值补上 `offset`/`length`（**声明真实写入区间，不是放宽闸门**） |

修 1 之后暴露出修 2；修 2 之后构建通过：
`changed_bytes=560 / declared_ranges=7 / undeclared=0`，产出 6,291,456 B 的 ROM（与基座同尺寸）。

**`tools/automated_test.py` 从 11/28 → 28/28**，另外 3 处是**合并遗留的测试契约过期**：

- `chapter_script` 这个 patch 类型 master 已加进 manifest、构建器也支持，但测试的合法类型表没加；
- **合成 editor DB 的契约有 16/20 条几何过期**（合并改了 16 张表的基址），
  6 条列名过期 —— 生成器因此**正确地**拒绝（"stale _rom_offset" / "legacy editor schema"），
  而测试把这种拒绝误读成「静默无输出」；
  ⇒ 已把合成契约**改成按生成器自己的契约**（`table_offset`/`entry_count`/`pointer_column`/`record_stride`）写，
  **不再从 bank 抄一份**——两边本来就不是 1:1（`rom_story_b` 是 m4a SongHeader，
  而 `story-b` bank 已 rebase 到剧情 VM 根表）；
- `generate_character_stats_b_patches` 的 `SELECT` 只取 2 列却读 8 列 ⇒ 永远拒绝（真实生成器 bug，改成 `SELECT *`）；
- `rom_battle_encounters` / `rom_story_c` / `rom_story_d` / `rom_story_e` 是**故意拒绝**的表，
  补进「必须拒绝而不是写」的集合。

## 4. 与「复刻侧接线」的关系（两条正交的轴）

| 轴 | 谁在管 | 当前读数 | 「100%」覆盖它吗 |
| --- | --- | --- | --- |
| **逆向侧结构闭合** | 逆向树 + `completion_audit.py` | 49 结构；P2 成立；P1/P3 当前不成立（none=5、阻塞=3） | —— |
| **复刻侧接线** | `measure_butano_wiring_coverage.py` | 带声明的接线 **69** 族；**68** 族已闭合带 payload 但**无人接**；**332** 条结论未转门禁 | ❌ **不覆盖** |

⇒ **「逆向 100%」这句话既不证明复刻做完，也不因为复刻没做完而变假。**
两个数字说的是两件事。

## 5. 要让这句话站得住，缺的是这三件（都不是「补逆向」）

1. **把 4 个探针搬进仓库**（`tools/mgba_probe/` 下），或让 `items` / `skills` /
   `mechanism-effects` / `resource-pointers` 的 L3 证据指向**已提交**的探针；
   否则 `completion_audit --check` 永远是 1。
2. **补齐 `battle-presentation-scripts` / `battle-results` 的格式证明**，
   给 `units` 一条写回路径 ⇒ 阻塞缺口 3 → 0，P1 成立。
3. **文档 §5 的数字改成「由当次收据重算」**，别再手抄：
   现在文档写 47/3/0/24，工具算 49/5/3/23。

## 6. 边界声明

- 本次核对**没有**重跑逆向分析，也没有改动任何逆向结论；只跑了闸门、修了复刻侧构建与测试契约。
- `completion_audit --check` 的失败**先于本次合并存在**（合并前 b35351db 同样是 exit 1），
  所以不能把它记成「这次合并引入的回归」。
- 文档 §6「不可以宣称」里那 21 条加固缺口**依然有效**，本次没有动它们。
- 复刻侧的接线存量（68 族 / 332 条）**本次也没有动**——
  它属于 `docs/butano-wiring-roadmap.md` 的 W4 / W5。

## 7. 相关

- `docs/re-completion-criteria.md`（判据 P1/P2/P3、证据分级 L1–L4）
- `notes/completion-audit-20261020.md`（审计表）
- `docs/butano-wiring-roadmap.md`（复刻侧接线路线图 W0–W5）
- `notes/butano-wiring-coverage-20261022.md` / `notes/butano-usable-backlog-20261022.md`
- `notes/master-merge-20261022.md`（本轮 25 个冲突的裁决记录）
