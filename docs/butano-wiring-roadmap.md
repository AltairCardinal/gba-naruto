# Butano 复刻接线补全路线图

> 2026-10-22 立。此文档是**执行路线图**：按「能换多少像素 / 能防多少回归 / 结构成本」排序，
> 每个里程碑带**验收分母**与**门禁**。
> 读数来源：`notes/butano-wiring-coverage-20261022.md`（接线点全量枚举）、
> `notes/butano-usable-backlog-20261022.md`（存量分诊）、
> `docs/butano-reverse-gap-roadmap.md`（差异清单与 M0–M7）。
> **读数必须来自当轮收据，不得写死。**

## 目标

把「逆向侧已闭合、复刻侧还没接线」的部分补完，使 **S49 一关的像素差分收敛到 0**，
并让后续每铺一关的接线成本从「重新发明」降到「填表 + 跑审计」。

**明确不在本路线图范围内**：铺关卡数量、补功能面（技能／忍具／宝箱／胜负分支／音频）。
它们由 `docs/sequel-roadmap.md` 负责；本图只保证**接线的机制与存量**。

## 起点读数（2026-10-22 当轮实测；W1 闭合后已刷新）

| 项 | W1 前 | **当前** | 出处 |
| --- | ---: | ---: | --- |
| 逆向成果族 | 264 | 264 | 索引 |
| 带声明的接线（全部有门禁） | **66** | **66** | 54 导入器载体 + 12 provenance 载体 |
| 本地产物缺失（有 exporter，产物不在树里） | **26** | **0** ✅ | W1 补回，26 族逐字节相同 |
| └ 其中复刻侧 producer **自己复现**的 | — | **16** | `rederived`：含解码器的强结论 |
| └ 其中从逆向树**导入**的 | — | **9** | `imported`：抓取／verifier 证据／schema 已迭代 |
| 已闭合带 payload、**无人接** | **71** | **71** | 资产直取 30 + 一次生成器 41 |
| 其中 `scope` 全部闭合 | 3 | 3 | 逆向 manifest 的 `scope` 块 |
| 其中 `scope` 有未闭合声明 | 69 | 69 | 多为 `runtime_reachability_complete` |
| sink 侧未登记面 | 110 手写头 / 34 内容库 / 1819 图形资产 / 4 运行时源码 | 同左 | 无声明载体 |
| notes `needs_guard`（未转门禁） | 333（314 连测试都没引用） | 333（314） | notes 索引五桶 |
| 差异清单 `local_artifact` | 3 | **0** | 逆向成果的本地副本不再被当成消费 |
| S49 像素残差 | **2,917 @ step-20** | **2,917 @ step-20** | `tools/butano/measure_s49_movegrid_baseline.py` |
| 复刻关卡数 | 3 / 47 | 3 / 47 | 场景 41/43/49 vs map header 表 47 条 |

## 里程碑

### W0 · 接线点全量枚举（✅ 已完成，2026-10-22）

| 项 | 内容 |
| --- | --- |
| 产出 | `tools/measure_butano_usable_backlog.py`、`tools/measure_butano_wiring_coverage.py` |
| 收据 | `artifacts/butano-usable-backlog-v1/`、`artifacts/butano-wiring-coverage-v1/` |
| 门禁 | 20 + 9 项，全绿 |
| 验收 | 264 族**九态全覆盖**，每族有可审计的判定证据；连跑读数逐字节一致 |

**本里程碑的产出是后续所有 W 的分母来源。**

---

### W1 · 补回 26 族缺失的本地产物（✅ 已完成，2026-10-22）

**为什么先做**：这 26 族的 exporter 还在复刻树里，**产物却不在**。
它们不是「没接线」，是**线断在工作树里**。补回来比新接 26 个族便宜一个数量级。

| 项 | 内容 |
| --- | --- |
| 动作 | 逐族跑复刻侧对应 exporter，重生成 `artifacts/<family>/`；或从逆向树导入 |
| 验收分母 | 26 族本地 manifest 存在，且与逆向树原始**逐字节相同**（分叉即失败关闭） |
| 门禁 | `measure_butano_wiring_coverage.py` 的 `local-derivation-missing` 计数 **= 0** |
| 依赖 | 无 |
| 风险 | 本地 exporter 用的解码器与逆向树不同 ⇒ 会分叉。**分叉必须报错，不许「就近取一个」** |

**本轮结果（`notes/butano-local-derivations-20261022.md`）**：

| 模式 | 族数 | 含义 |
| --- | ---: | --- |
| `rederived` | **16** | 复刻侧 producer 复现了逆向树字节（**含解码器**）——强结论 |
| `imported` | **9** | 复刻侧无 producer 能复现（抓取／verifier 证据／schema 已迭代），按 reverse commit + 逐文件摘要导入——弱结论 |
| `already-identical` | **1** | 还原前已存在且逐字节一致 |
| `diverged` | **0** | 无分叉 |

> **产物**：`tools/restore_butano_local_derivations.py`（还原器）+ `tools/verify_butano_local_derivations.py`（独立复核，**不 import** 还原器）
> **收据**：`artifacts/butano-local-derivations-v1/{local.json,local.md,provenance.json}`
> **门禁**：`tests/test_restore_butano_local_derivations.py`（13 项，全绿）

**本轮顺带收紧了两处旧判定**（不是新功能，是旧判定不够严）：

1. **接线审计器从「只比 manifest」改成「比整棵目录树」**——manifest 只证明描述一致，
   不证明载荷一致；4 个两侧都没有 manifest 的抓取族此前永远判不出「一致」。
2. **差异清单按内容排除「逆向成果的本地副本」**——副本内部的引用不是消费
   （与 `artifacts/butano-reverse-m3-import-v1/` 同理由），本轮命中 30 个目录。
   规则是量出来的：本地摘要**等于**逆向树摘要才排除，一旦分叉立刻重新参与扫描。

> ⚠️ 这 26 族本地产物在 2026-10-19 的 artifacts 清理里被带走
> （`notes/s49-fidelity-handover-20261019.md` §1 记录了 8,124 个被跟踪文件整体缺失）。
> **它们大概率可以重跑出来**——工具还在。
> ⇒ **已证实**：16 族确实重跑出来了，9 族确实没有能重跑的工具。

---

### W2 · S49 覆盖层 1:1 接线（唯一直接换像素的当前项）

**为什么现在做**：S49 残差 2,917 像素的**原版那一侧早就闭合了**——
`overview-gradient-overlay-v1` 里就有原版覆盖层的 `generated-tiles.4bpp.bin`、
`generated-tilemap-30x20.bin` 与调色板。**这是接线问题，不是逆向问题。**

| 项 | 内容 |
| --- | --- |
| 动作 | 按第 26 轮施工单（`artifacts/s49-overlay-plan-20261021-v1/patch-plan.md` §5）三步：① 块预算 77→101 ② 把原版 32 个 4bpp 图块装进 77..100 ③ 移动相位按滚动公式装原版 30×20 烘焙窗口 |
| **前置** | **先读重制侧 VRAM** 核对三件事：槽 77..100 的图块字节 / 可见窗口 30×20 的 tile index / 8bpp 上传长度与基址对齐。**不先改代码**（第 26 轮否证就败在没核对这三处） |
| 验收分母 | step-20 残差 **≤ 2,917**，且**任何一帧都不得变差**；逐帧报告用 `tools/butano/measure_s49_movegrid_baseline.py` |
| 失败处置 | 一旦变差立即回滚（照第 26 轮处置），收据保留 |
| 依赖 | 无。`overview-gradient-overlay-v1` 当前是 `on-shelf`（payload 在**逆向树**，26,201 B），复刻侧可直接读逆向树 |
| 风险 | Butano 的 8bpp tile index 语义与块基址对齐**从未验证过** |

---

### W3 · 让接线审计器覆盖两套载体，并给 sink 面补载体（🟡 动作 1 已完成，动作 2 待逐条判定）

| 项 | 内容 |
| --- | --- |
| 动作 1 | provenance 审计器增读**导入器载体**（`import_rom_*` 的 `*_FAMILIES` 常量）；覆盖率断言从「只看头注释」改成「两套都要看」 |
| 动作 2 | 内容库 JSON 增加 `_provenance` 块（族 + manifest 哈希）；图形资产**按生成器**登记 sidecar（不逐文件） |
| 验收分母 | ① 审计器可见的带声明接线 = 实际带声明接线（差 = 0）；② 34 个内容库**全部**能回答「来自哪个族 / 哪条 note」；③ 图形资产按生成器归组后 100% 有 sidecar |
| 门禁 | `audit_butano_reverse_provenance.py` exit 0 且 `problems: none`；新增「没有族处于未登记态」的断言 |
| 依赖 | W1（W1 的产物会新增声明，必须先有载体） |
| 风险 | 载体加在 JSON 里会改内容库字节 ⇒ 要确认现有门禁不依赖内容库的精确字节 |

**这一步是「以后不再产生灰区」的结构性修复。** 每一铺一关都要重接一遍线，
先建机制比先接一关更省。

**动作 1 已完成**（`notes/butano-wiring-carriers-20261022.md`）：

| 项 | 之前 | 现在 |
| --- | ---: | ---: |
| 审计器可见的带声明接线 | **12**（只读头注释载体） | **66**（头注释 12 + 导入器 54） |
| **覆盖率断言 `difference`** | 不可比 | **0** ✅ |
| 导入器载体读取器 | 测量器私有副本 | **审计器持有**，测量器 import 它 |

> **载体规则只能有一份实现。** 上一轮是「测量器自己补一份读取」，登记表本身没动，
> 于是同一棵树有两个不一致的登记表（12 vs 66）——**那不是修好了，是把灰区从一处搬到另一处**。

**动作 2 的两个分母实测下来不可脚本化**（不是判断，是试过的）：

| 尝试 | 结果 |
| --- | --- |
| 用内容库 `table_offset` 反查逆向树 259 份 family manifest 的同址/近址 | 32 个有地址的内容库**只中 2 个** ⇒ **地址不是可用的连接键** |
| 用内容库自带的 `extraction`/`discovered_by`/`notes` 反查来源 | 这些字段记的是「逆向侧当时怎么提取的」，**不是**「哪一族闭合了它」 |
| 扫 37 个生成器源码里字面出现的图形资产名 | 1819 个图形资产里**只 174 个**被点名，其余由循环/模板生成 |

⇒ 动作 2 与 **W5 同类**：**逐条判定**，先给分母与缺口清单，再逐族/逐生成器落地。

---

### W4 · 71 个「已闭合带 payload、无人接」的族按子系统接线

**这是唯一「换像素」的批量项，但每一族都是设计判断，脚本做不了。**

建议顺序（按复刻子系统归位，详见 `notes/butano-usable-backlog-20261022.md` §4）：

| 序 | 子系统 | 族 | 备注 |
| --- | --- | --- | --- |
| 1 | 状态栏 / 调色板 | `battle-status-bars-v1`、`rom-menu-portrait-palette-inventory-v1`（70 个 128 B 物理调色板）、`portrait-palette-producers-v1` | 调色板逐号同色是像素等价的必要条件 |
| 2 | 文本 / 对白 | `rom-alternate-dialogue-table-v1`（80 条对白文本）、`rom-dialogue-text-inventory-v1`、`rom-renderer-text-inventory-v1`、`rom-display-text-delta-v1` | 复刻侧对白/文本还原是当前最大内容缺口 |
| 3 | 场景 / 地图 | `scene-visual-composites-v1`（10 张 240×160 合成图）、`runtime-bg-composites-v1`、`runtime-screen-composites-v1`、`map41-visual-resource-matrix-v1` | 背景合成与图层 |
| 4 | 战斗特效基准 | 13 个 `battle-effect-*` 族（带 `capture.png` 240×160 + VRAM/OAM/PRAM dump） | 可直接当 1:1 验收基准，导入器现成 |
| 5 | 音频表 | `rom-battle-sound-selector-v1`、`rom-directsound-pitch-lookup-v1`、`rom-psg-frequency-lookup-v1` | 只给音频运行时，**不换像素** |
| 6 | 文字 / 其它 | `rom-pointer-lz77-graphics-v1`、`rom-renderer-script-pointer-pool-records-v1` 等 | 杂项 |

| 项 | 内容 |
| --- | --- |
| 验收分母 | 逐族：① 接线声明登记 ② 像素差分或内容等价验收 ③ 门禁 |
| 门禁 | 每族一条；总门禁 = `measure_butano_wiring_coverage.py` 的 `on-shelf` 计数逐族归零 |
| 依赖 | W3（声明载体要先在） |
| 风险 | **`scope` 未闭合的 69 族**：多数是「自然运行期可达性未证明」。接进去可以，但**不能声称原版一定会走到那里** |

---

### W5 · notes 侧：333 条 `needs_guard` 转门禁

| 项 | 内容 |
| --- | --- |
| 动作 | 按 W4 的子系统挑相关 note，逐条转成行为门禁；剩下的按 M5 分批消化 |
| 验收分母 | `needs_guard` 从 333 降下来；**314 条「连测试都没引用」的优先** |
| 门禁 | `docs/reverse-results-index/notes-index.md` 重新生成后的桶分布 |
| 依赖 | 无（可与 W1–W4 并行） |
| 风险 | 「被测试引用」≠「行为门禁」——文档类测试也算引用。**逐条判定仍需人看** |

---

## 依赖与推进顺序

```
W0（已完成，分母来源）
 ├─► W1（补回 26 族本地产物）──► W3（审计器覆盖两套载体 + sink 载体）
 ├─► W2（S49 覆盖层 1:1 接线）        │
 └─► W5（notes 转门禁，可全程并行）    ▼
                                  W4（71 族按子系统接线）
                                       │
                                       ▼
                            （交棒给 sequel-roadmap：铺关卡 + 补功能面）
```

**W1 与 W2 的先后**：**两者无依赖**。W2 要用的 `overview-gradient-overlay-v1` 属于
`on-shelf`（payload 在逆向树，26,201 B），复刻侧直接读逆向树即可；
W1 处理的是**复刻树本地副本缺失**的那 26 族。两条线可以并行。

## 验收总表

| 里程碑 | 验收分母 | 门禁 | 状态 |
| --- | --- | --- | --- |
| W0 | 264 族九态全覆盖 | 29 项 | ✅ |
| W1 | 26 族本地产物齐全且与逆向树逐字节相同 | `local-derivation-missing` = 0 | ✅ |
| W2 | step-20 残差 ≤ 2,917 且无帧变差 | `measure_s49_movegrid_baseline.py` 逐帧报告 | ⬜ |
| W3 | 审计器可见接线 = 实际接线（差 = 0）；34 内容库 + 图形 sidecar 齐全 | provenance 审计 exit 0 | 🟡 动作 1 ✅ / 动作 2 ⬜ |
| W4 | 71 族逐族接线 + 门禁 | `on-shelf` 计数归零 | ⬜ |
| W5 | `needs_guard` 333 → 逐条降 | notes 索引重新生成 | ⬜ |

## 边界声明

- 本路线图**只管接线**。像素差分驱动的是「改重制侧逻辑」（例如 AI 朝向 bug、
  状态栏判据），那类差异**逆向侧没有也不需要**对应成果，不在本图内。
- 「可用」≠「已闭合」：71 族里 `scope` 全闭合的只有 3 族。
  接进去可以，但**不能声称原版一定会走到那里**。
- 「有门禁」是**上界**：测试提到产物路径或导入其生成器模块都算，可能是文档类测试。
- 全部读数由脚本从当次三份收据重算，**逆向树一变就变**，不得写死。
- **每多一份逐族枚举的收据，就必须同步扩一次差异清单的 `EXCLUDED_PREFIXES`**——
  否则测量会静默漂移（已踩两次，见 `notes/butano-wiring-coverage-20261022.md` §5）。

## 不该现在做的事

1. **不要为「接线率」本身去刷数字**——接线是手段，S49 的像素残差才是判据。
2. **不要先接 `not-importable` 的 51 族**——它们是控制流／覆盖分母，
   约束行为但不是素材，接了也不会换像素。
3. **不要在 W3 的载体落地前逐族手写声明**——载体没建好，手写声明无处安放，
   且会被 W3 重新格式化成另一套。
4. **不要把「复刻侧本地重导出的副本」当成「接上了逆向成果」**——
   26 族那批就是教训：exporter 在，产物不在，两者都不是「接了」。

## 相关

- `notes/butano-local-derivations-20261022.md`（W1 还原：16 复现 / 9 导入 / 0 分叉）
- `notes/butano-wiring-coverage-20261022.md`（接线点枚举 + 两处自我更正）
- `notes/butano-usable-backlog-20261022.md`（存量分诊 + 词表探针的三处错分）
- `docs/butano-reverse-gap-roadmap.md`（差异清单与 M0–M7）
- `docs/sequel-roadmap.md`（铺关卡与功能面）
- `notes/s49-fidelity-handover-20261019.md`（S49 工作交接，第 26 轮末）
- `tools/restore_butano_local_derivations.py`、`tools/verify_butano_local_derivations.py`、
  `tools/measure_butano_usable_backlog.py`、`tools/measure_butano_wiring_coverage.py`、
  `tools/audit_butano_reverse_provenance.py`、`tools/measure_butano_reverse_gap.py`
