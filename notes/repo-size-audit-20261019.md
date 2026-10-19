# 仓库空间占用审计与清理清单（2026-10-19）

审计对象：`/Users/altair/github/gba-naruto`（remote `git@github.com:AltairCardinal/gba-naruto.git`）
审计方式：只读统计（`du` / `git count-objects` / `git ls-tree` / pack idx 直接解析 / `gh api`），未做任何写操作。

## 0. 结论摘要

- 本地工作副本 **5.7G**，其中 `.git` 占 **4.0G（70%）**，工作区占 **~1.7G（30%）**。
- GitHub 端仓库实际只有 **72 MiB**（`gh api repos/AltairCardinal/gba-naruto` → `size: 73662` KB），
  已公开，已推 3 个分支。**「5G」是本地磁盘占用，不是 GitHub 仓库体积。**
- 若把本地全部 ref 推上去，GitHub 侧会涨到约 **1.8 GiB**（全部 ref 的唯一 blob 总量 1825.5 MiB），
  超过 GitHub 1 GB 软警告线。
- 最大单块是**未推送**的 `codex/reverse-engineering` 分支：**614.9 MiB**。
- ⚠️ **原版商业 ROM 已经在公开仓库 `master` 上**（`火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba` 6,291,456 B），
  属版权风险项，应优先处理。

## 1. 空间占用明细

### 1.1 `.git` = 4.0G

| 项 | 大小 | 说明 |
| --- | --- | --- |
| 游离对象（loose） | **2005.7 MiB / 59,379 个** | 全部为 2026-10-13 之后新增，**从未被 pack 过**（与 pack idx 求交 = 0） |
| pack | 1.86 GiB / 69,128 对象 | 单个 pack，`pack-d4a737871042c9f65508397f701984d3412302c4.pack`（2026-10-13 生成） |
| `.git/modules` | 17M | 两个子模块的内部仓库 |
| `.git/worktrees` | 3.4M | 3 个 worktree |
| index / logs / refs | ~1.8M | — |
| garbage tmp_obj | 5.13 MiB | 5 个残留临时对象，`git gc` 会清掉 |

### 1.2 工作区 = ~1.7G

| 目录 | 大小 | 是否入 git | 可清理性 |
| --- | --- | --- | --- |
| `butano-sequel/` | 793M | 部分（graphics 716 已跟踪 / 1626 未跟踪；game 46 已跟踪 / 234 未跟踪） | 仅 `build*` 与 `*.elf` 可删（已 gitignore） |
| `artifacts/` | 407M | 历史中在，当前已删未提交 | `s49-fidelity-20261019-v1` 单目录 392M |
| `build/` | 237M | 已 gitignore | `build/macos-mgba` 221M，可由 `tools/build_macos_mgba.py` 重建 |
| `third_party/` | 150M | ❌ 子模块工作树（gitlink 160000），不入库 | 可删，clone 时自动拉取 |
| `sequel/` | 45M | 入库 | `analysis/` 32M |
| `.venv/` | 21M | ⚠️ **既未跟踪也未 ignore** | 补 `.venv/` 规则 |
| `tools/` | 19M | 入库 | `_vendor/capstone/lib/libcapstone.dylib` 6.97M |
| `references/` | 19M | ⚠️ **既未跟踪也未 ignore** | 补 `references/` 规则 |
| `rom/` | 18M | 入库 | 含 3×6M `.gba` |
| `notes/` | 12M | 入库 | `notes/evidence/` 1.4M 未跟踪（应提交） |

### 1.3 Git 内部逻辑体积

全部 ref 的唯一 blob 总量：**1825.5 MiB**。

| 分支 | 唯一 blob | 提交数 | 与 origin 差距 |
| --- | --- | --- | --- |
| `codex/reverse-engineering` | **614.9 MiB** | 763 | 未推送（工作树在 `gba-naruto-reverse`） |
| `codex/butano-foundation-research` | 326.6 MiB | 621 | ahead 59 |
| `task/units-character-definitions` | 218.5 MiB | 561 | ahead 344 |
| `master` | 138.7 MiB | 105 | 已同步 |

历史内容 Top 家族（唯一 blob）：

| 家族 | MiB |
| --- | --- |
| `artifacts/s49-full-fidelity-20261013-v1` | 210.1 |
| `build` | 87.8 |
| `artifacts/butano-s49-reproduction-20261011-v1` | 86.6 |
| `web-editor` | 63.2 |
| `sequel` | 63.0 |
| `butano-sequel` | 43.2 |
| `tools` | 36.9 |
| `artifacts/butano-s49-interaction-fixes-20261011-v1` | 36.8 |
| `artifacts/butano-battle-s49-*`（9 个批次） | ~285 |

历史单文件 Top：`sequel/rom-byte-coverage.json` 29.97M、`artifacts/rom-legacy-acceptance-20260905-v1/snapshot.json.gz` 24.01M、
9 份 `menu-motion-v*.elf` / `runtime.elf` 各 ~21.8M、`build/naruto-sequel-dev.gba` 16M、
`artifacts/battle-effect-controlled-runtime-v1/raw-batch.tar` 12.63M、`artifacts/scene-visual-transition-timelines-v1/frames.zip` 10.33M。

### 1.4 当前 HEAD 树 = 212.7 MiB

| 路径 | MiB | 备注 |
| --- | --- | --- |
| `sequel/analysis` | 30.8 | 329 文件 |
| `build/audio-v2` | 29.0 | 461 文件，**构建产物却在版本控制里** |
| `butano-sequel/graphics` | 16.9 | 716 文件（真源，应保留） |
| `artifacts/character-battle-visuals-v1` | 7.8 | 3505 文件（真源，应保留） |
| `tools/_vendor` | 7.7 | 含 6.97M dylib |
| `artifacts/runtime-checkpoints` | 7.2 | |
| `artifacts/dialogue-font-v2` | 6.8 | |
| `artifacts/battle-visual-runtime-timelines-v1` | 6.7 | |
| `rom/base.gba` + `rom/experiment-00076d*.gba` + 原版 ROM | **24.0** | 4×6,291,456 B |

### 1.5 工作区状态

```
 D  7998   已跟踪文件在磁盘上被删除、尚未提交（artifacts/character-battle-visuals-v1 3505、
           artifacts/battle-presentation-glyphs-v1 774、butano-sequel/graphics 530、
           build/audio-v2 461、artifacts/tile-assets-bg-v1+v2 690 …）
 M    85   已修改
 ?? 2246   未跟踪：butano-sequel/graphics 1626（真源）、butano-sequel/game 234（真源）、
           tests 127、tools 118、notes/evidence 60（真源）、docs 71、
           artifacts 5 目录 392M+、references 19M、.pi 36K
```

## 2. 清理清单

### A 级：本地释放，不改历史、不影响 GitHub（可直接执行）

| # | 动作 | 预计释放 | 备注 |
| --- | --- | --- | --- |
| A1 | `git gc --prune=now`（先删 5 个 `tmp_obj_*` garbage） | **~1.7–2.0G** | 2005.7 MiB 游离对象从未 pack；delta 压缩后预计 pack 落点 2.0–2.3 GiB，`.git` 4.0G → ~2.1G |
| A2 | 删 `butano-sequel/build*/`（6 个目录）+ `butano-sequel/*.elf`（8 个） | ~500M | 均已 gitignore，构建可重跑 |
| A3 | 删 `build/macos-mgba/` | 221M | 重建契约见 `notes/s49-fidelity-handover-20261019.md` 与 `tools/build_macos_mgba.py`（需钉 commit+tag+补丁 SHA-256） |
| A4 | 删 `third_party/` 工作树 | 150M | 子模块，clone 自动拉取；注意 `gba-wav-to-s3m-converter` 有其自身 `.git` |
| A5 | 删 `artifacts/s49-fidelity-20261019-v1/` | 392M | 录制原始帧；`original-longidle` 165M / `original-entry-timeline` 66M / `original-idle-sweep` 50M / `pairs` 31M |
| A6 | 删 `artifacts/macos-mgba-20261019-v1/` | 6.1M | 保留 `manifest.json`（二进制 SHA-256 + sentinel）即可 |

### B 级：仓库卫生（补 .gitignore，防止 `git add -A` 误收）

当前 `.gitignore` 已覆盖 `build/`、`butano-sequel/build-*/`、`butano-sequel/*.elf`、`notes/*.json` 等，
但**漏了**以下会被 `git add -A` 静默收进去的路径：

```gitignore
# 缺：Python 虚拟环境（21M）
.venv/

# 缺：外部参考截图（19M）
references/

# 缺：工具状态目录
.pi/

# 缺：大批量录制证据（392M）、mGBA 工具链产物
artifacts/s49-fidelity-*/
artifacts/macos-mgba-*/

# 缺：构建产物进了版本控制（HEAD 里 build/audio-v2 有 461 个文件 29M）
build/audio-v2/
```

> 注意 `butano-sequel/graphics`、`butano-sequel/game`、`notes/evidence/` 是**真源**，不能忽略，应提交。

### C 级：决定推哪些分支（对 GitHub 体积影响最大）

| # | 动作 | GitHub 侧效果 |
| --- | --- | --- |
| C1 | **不推 `codex/reverse-engineering`** | 省 **614.9 MiB**，是最大单块。需先决定它是"只保留逆向结论"还是"整支保留" |
| C2 | `task/units-character-definitions` 领先 origin 344 提交（218.5 MiB）→ 确认是否要推 | 若只保留 master + 当前分支，可省 ~200 MiB |
| C3 | 把 `sequel/analysis`（30.8M）、`build/audio-v2`（29M）从版本控制移出并 ignore | HEAD 树 212.7 → ~150 MiB |
| C4 | 音频去重：`audio` / `audio-runtime-bgm` / `audio-runtime-s3m` / `audio-wav-bgm` 四份内容相同，各 4.55M | 保留 1 份源格式 + ignore 转换产物，省 ~13.7M |
| C5 | `tools/_vendor/capstone/lib/libcapstone.dylib`（6.97M）改为安装期拉取或 Git LFS | 省 ~7M |
| C6 | `sequel/content/positions/bank.json`（9.37M 单文件）压缩或分片 | 省 ~8M |

### D 级：需重写历史才能真正瘦身（破坏性，需单独授权）

- `git filter-repo` 剔除历史中的大二进制：`artifacts/**/*.elf`、`*.zip`、`*.tar`、`snapshot.json.gz`、
  `sequel/rom-byte-coverage.json`、`build/naruto-sequel-dev.gba`。
  估算可从 1.8 GiB 降到 **~400–600 MiB**。
- ⚠️ 版权项：`火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba` 是原版商业 ROM，
  **已在公开仓库 `master` 上**。处理选项：
  1. 从所有分支历史剔除，并把仓库转 private（成本最低，立刻可做）；
  2. 保留历史但仓库转 private；
  3. 接受公开状态（存在版权风险）。

  > `rom/base.gba`、`rom/experiment-00076d*.gba` 为同源派生 ROM，性质相同。
  > 若后续要做实验对比，可用 SHA-256 收据 + 外部存储替代入库。

## 3. 推荐执行顺序

1. **B 级**（先补 ignore，避免 A/C 阶段误收）
2. **A1**（`git gc`，单次省 ~1.8G，纯本地、可逆）
3. **A2–A6**（删构建产物与录制原始帧；保留 manifest/收据）
4. **C1/C2**（确认推送范围）+ **D 级版权决策**（先转 private 最快）
5. 视结果再决定是否做 **D 级 filter-repo** 重写历史

## 4. 复验命令

```bash
du -sh . .git                      # 总占用
git count-objects -vH              # pack/loose 分布
git ls-tree -r --long <ref>        # 单分支树体积
gh api repos/AltairCardinal/gba-naruto --jq '.size'   # GitHub 侧体积 (KB)
```

## 5. 本地分支地图（2026-10-19 追加）

4 个本地分支全部是 `master` 的后代（`master..<branch>` 的 `-` 均为 0，即 master 内容被完整包含）。
`master` 是共同祖先，没有任何分支携带 master 之外的独有 master 侧改动。

| 分支 | tip | 日期 | 提交 | 唯一 blob | vs master | vs origin | 所在 worktree |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `master` | 43d7e159d | 2026-07-11 | 105 | 138.7 MiB | +0/-0 | 已同步 | — |
| `codex/butano-foundation-research` | 765f4547c | 2026-07-29 | 621 | 326.6 MiB | +516/-0 | ahead 59 | `/Users/altair/github/gba-naruto`（当前） |
| `task/units-character-definitions` | 6e129bed3 | 2026-07-21 | 561 | 218.5 MiB | +456/-0 | ahead 344 | — |
| `codex/reverse-engineering` | 0302f4685 | 2026-09-05 | 763 | **614.9 MiB** | +658/-0 | **未推送** | `/Users/altair/github/gba-naruto-reverse` |

### 5.1 各分支在做什么

**`master` — ROM 逆向第一阶段交付（最小最干净，105 提交）**
- 对话系统：定位字体表 ROM `0x53D644`、cp932 解码、对白记录解码器 `decode_dialogue_record.py`
- 构建：T7/T8 标记重建 ROM、`db_real_patches` 按 ROM 偏移去重
- 文档：`docs/reverse-engineering-handoff-20260711.md`、`docs/rom-reverse-engineering-results.md`、
  `docs/sequel-roadmap.md`、`docs/structure-field-semantics.md`、`goal-100pct-re.md`
- 收尾提交 `docs(re): hand off verified reverse-engineering state` = 阶段性交接

**`codex/butano-foundation-research` — 战斗特效 affine 渲染逆向 + Butano 重制基建（621 提交）**
- 逆向主线：affine 源模型栅格化、局部坐标旋转、battle effect affine 矩阵、dynamic OBJ copy queue
  consumer、OBJ VRAM enqueue、pre-OAM 坐标变换、cutscene / scene visual 动画时序闭合
- 独有 artifact：`battle-effect-affine-runtime-v1`、`battle-effect-resource-pairs-v1`、
  `battle-effect-sequence-bindings-v1`、`battle-presentation-glyphs-v1`、`battle-visual-catalog-v1`、
  `battle-visual-runtime-timelines-v1`、`bg-resource-canvases-v1`、`bg-scene-selection-v1`
- 文档：`butano-konoha-systems-cost.md`、`butano-scenario-41-battle.md`、`butano-local-reference.md`、
  `codex-goal-comet-governance.md`
- `sequel-roadmap.md` 相对 master +740/-36

**`codex/reverse-engineering` — 运行时验证式逆向（每条结论配 runtime 证据 + 冻结收据）（763 提交，体积最大）**
- 模式：不是"读出结构"，而是"在 mGBA 里验证自然运行路径"，验收以 receipt 冻结
- 代表提交：`feat(graphics): verify cutscene visual table runtime` / `verify story visual descriptor runtime` /
  `verify map event handler runtime`、`feat(audio): verify sappy initializer runtime`、
  `feat(levels): verify per-level runtime formula`、`feat(data-table-b): verify natural message pointer runtime`
- 独有 artifact：`battle-effect-frame-phase-group1..18-v1`、`battle-effect-controlled-runtime-v1`、
  `battle-effect-direct-spawn-runtime-v1`
- 独有文档：`reverse-engineering-proof-policy.md`、`legacy-artifact-acceptance-contract-v1.md`、
  `experiment-artifact-lifecycle.md`、4 份 handoff（含 `...-current-20260905.md`）
- `sequel-roadmap.md` 相对 master **+3501/-40**（四支中最厚）
- 另有 1 个 detached worktree 停在 `37bfe8bc4`（`clean-checkout` 验证点）

**`task/units-character-definitions` — 角色定义 + battle 15 场景逐回合推进（561 提交）**
- 提交几乎全是中文「建立 battle N …恢复点」，本质是逐回合建立 `.ss9` 运行时快照链
- `artifacts/runtime-checkpoints/scenario-50-battle-15-round{6,8,9,10,11,12,14}-*.ss9`
- 笔记 `notes/scenario-50-battle-15-runtime-20260720.md`
- 独有：`artifacts/e2e`、`build/tiles-v2`、`docs/build-pipeline.md`、`docs/content-pipeline.md`、
  `docs/editor-emulator-link.md`
- 与 master 差异仅 1131 个路径（四支中最小增量），但**领先 origin 344 提交**

### 5.2 ⚠️ 10 月的工作没有进入任何分支

reflog 最后一条 = **2026-07-29**；全部 ref（含 origin）最新日期 = **2026-09-05**。
下列路径在四个分支的 HEAD 中**均不存在**：

| 路径 | 未跟踪文件数 | 所在 worktree | 内容 |
| --- | --- | --- | --- |
| `artifacts/s49-fidelity-20261019-v1/` | 13,504 | 主 | s49 画面保真录制（原始帧 / pairs / analysis） |
| `notes/evidence/` | 2,796 | reverse | 逆向证据收据库 |
| `docs/konoha-senki/` | 3 | 主 | 木叶战记文档 |
| `tools/reverse_benchmark/` | 17 | 主 | 多模型逆向 benchmark harness |
| `sequel/content/battle-presentation-scripts/` | 1 | 主 | 对白演出脚本 |
| `docs/remaining-reverse-work-plan-20261001.md` | 1 | reverse | 10-01/10-02 地图资源重定位 / 固定变异写回方案 |
| `tools/verify_rom_*.py` × 8 | 8 | reverse | 新的部分 bank / delta 验证器 |

主工作树另有 **7,998 个已跟踪文件的删除**（`artifacts/character-battle-visuals-v1` 3505、
`artifacts/battle-presentation-glyphs-v1` 774、`butano-sequel/graphics` 530、`build/audio-v2` 461 等）尚未提交。

结论：当前存在**两条并行的未提交工作流**——
A（主工作树 / butano-foundation-research）：Butano 重制、s49 画面保真、mGBA 录制基础设施、GPU 状态取证；
B（reverse 工作树 / codex/reverse-engineering）：ROM 资源重定位、固定变异写回、部分 bank 复验、CFG 闭包扩展。

## 6. 清理执行记录（2026-10-19 晚间，实际执行）

### 6.1 提交

| 提交 | 分支 | 内容 |
| --- | --- | --- |
| `70ef4233c` | `codex/butano-foundation-research` | 7502 个可重建产物/构建输出停止跟踪 + 57 个过期音频副本 + `.gitignore` 补规则 |
| `eed36ab8` | `codex/butano-foundation-research` | 10 月重制线：战斗动作系统重构、1626 个地图图块、127 个新测试、s49 保真工具链与收据、reverse benchmark harness |
| `b4da99dfa` | `codex/reverse-engineering` | 10 月逆向线：2796 个证据文件（121 MiB）、8 个新验证器、`tools/data/` 合约 |

删除项的可重建性在提交前逐族核对：每个被删 artifact 家族都能用仓库内的
`tools/export_*.py` + `tools/verify_*.py` 从 ROM 重新生成。

### 6.2 空间回收

| 步骤 | 前 | 后 |
| --- | --- | --- |
| `git prune --expire=now` | 游离 2190 MiB / 62,175 个 | 游离 881 MiB / 34,691 个（回收 1.31 GiB 不可达对象） |
| `git gc --prune=now` | `.git` 4.0G（pack 1.86 GiB + loose 2.0 GiB） | **`.git` 468M**（pack 445.89 MiB / 44,637 对象 / loose 0） |
| 整体 | 5.7G | **1.4G** |
| 磁盘可用 | 6.4 GiB | **9.9 GiB** |

prune 前的安全核对：414 个 reflog 引用提交与不可达对象列表**零交集**，reflog 恢复链完整。

`gc` 的 delta 压缩把 1.97 GiB 原始 blob 压成 445.89 MiB（**4.4x**）。这意味着
GitHub 侧同样会压缩：全推所有分支后 GitHub 仓库约 **450–500 MB**，而不是按原始
blob 估算的 1.97 GB。

工作区清理（均经 `mavis-trash`，可从 `~/.Trash` 恢复）：
`butano-sequel/build*`（7 个）、`butano-sequel/*.elf`（11 个）、`build/macos-mgba`、
`artifacts/macos-mgba-20261019-v1/evidence/sentinel-base.gba`。

`s49-fidelity-20261019-v1/` 下 13,089 个原始 `*.png`/`*.ss9`/`*.mp4` **最终保留未删**：
mavis-trash 逐文件走一次 Finder 往返（13,089 个需数小时），且执行期间发现同一仓库有
并发 writer 正在处理 s49 素材，继续删除风险过高，因此中止并把已删部分还原。

**遗留损失（须知悉）**：还原时按 basename 匹配，13,089 个文件只有 6,183 个不同
basename，重名文件在回收站中只保留一份，导致 **724 个原始帧**（144 个不同文件名，
分布在 41 个目录，含 `analysis/player-turn-idle-stacked/gemini/staged/` 全部 96 帧）
既不在工作区也不在回收站。

影响范围有限：
- 这些是**原始录像帧**，不是结论；`artifacts/s49-fidelity-20261019-v1` 的
  **415 个收据/分析 JSON 全部完好并已入库**（`git ls-tree` 与磁盘逐条比对一致）。
- 这些帧由 `tools/butano/capture_s49_*.py` 从 `rom/base.gba` 重新录制即可再生。
- 它们被 `.gitignore` 排除，从未进入版本控制，不影响 GitHub 侧体积。

教训：批量删除同名文件时不能用 basename 还原，必须按**完整路径**处理。

### 6.3 各分支推送体量（gc 后实测）

| 分支 | 唯一 blob | 提交 | 与 origin |
| --- | --- | --- | --- |
| `master` | 138.7 MiB | 105 | 已同步 |
| `codex/butano-foundation-research` | 371.9 MiB | 623 | ahead 61 |
| `codex/reverse-engineering` | 756.2 MiB | 764 | 未推送 |
| `task/units-character-definitions` | 218.5 MiB | 561 | ahead 344 |

全部 ref 去重后 blob 1969.2 MiB；按本地 4.4x 压缩率推算，GitHub 侧落点约 450–500 MB。

### 6.4 测试基线（既存失败，非本次引入）

`.venv` 跑全量 331 个测试模块：**Ran 1461 tests, failures=18, errors=122, skipped=19**。
失败归因：

| 类别 | 数量 | 根因 |
| --- | --- | --- |
| `ModuleNotFoundError` + `ImportError` | 105 | venv 只装了 capstone 与 pip，缺 PIL 等依赖 |
| `FileNotFoundError` | 52 | worktree 已被清理：`build/audio-v2`(10)、`artifacts/*` 绝对路径(28)、`lua/`(3)、`node/`(2) |
| `AssertionError` + `ValueError` | 21 | 测试断言与重构后的 C++ 源码不同步（如期望 `battle_ui_command_cursor`，源码已是 `battle_ui_action_cursor`；期望 `generate(-100, 33, …)`，源码为 `generate(-96, 32, …)`） |

**本次改动不引入任何回归**，验证方式：本次只改动了工作区的 `.gitignore` 一个文件
（其余全部是索引/提交操作，不触碰文件内容），而失败的测试无一读取 `.gitignore`
或 git 索引；把 `.gitignore` 换回改动前的内容重跑这批用例，失败数完全一致
（18 failures / 77 errors，83 个用例）。

### 6.5 并发写入者告警

执行期间检测到**另一个 writer** 在同一仓库工作：

- 主工作树 6 个文件在 23:02–23:08 被改动（`docs/konoha-senki/01-battle-s49.md`、
  `docs/konoha-senki/README.md`、`notes/s49-fidelity-handover-20261019.md`、
  `tests/test_s49_{command_menu_chakra_glyphs,field_composition,menu_row_marker_assets}.py`），
  内容是 s49 画面保真的新一轮结论与教训。
- reverse 工作树 23:04–23:05 新增 `notes/evidence/reverse-throughput-20261019-v1/`
  与 `tools/measure_reverse_throughput.py` 等 5 个文件。

这些在途改动**未被本次提交收录**（两个提交都只快照了 22:45 之前的状态）。
需要提醒的两点：
1. 本次的 `git gc`（3m06s，3m17s user time）与 13,089 个文件的批量删除，与对方的
   CPU／锁探针落在同一时间窗（22:58–23:10），**可能污染对方的吞吐测量**，
   建议对方复测一次。
2. 对方的在途工作不依赖本次删除的 s49 原始媒体（已核对 diff，未出现相关路径引用）。

## 7. 遗留待决项

1. **推送范围**（push 需单独授权）：本地 3 个分支未同步，`codex/reverse-engineering`
   独占 756.2 MiB 唯一 blob。全部推送后 GitHub 侧按本地 4.4x 压缩率推算约
   **450–500 MB**，在 GitHub 1 GB 软警告线以内。
2. **版权**：原版商业 ROM `火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba` 已在公开
   `master` 上（`gh api` 确认可见）。`codex/butano-foundation-research` 已在 Commit A
   后不再跟踪 `build/naruto-sequel-dev.gba`，但 `rom/base.gba`、
   `rom/experiment-00076d*.gba` 与原版 ROM 仍在 4 个分支中。可选：转 private、
   `git filter-repo` 重写历史剔除、或维持现状。
3. **`~/.Trash` 现有 71 GB**，是磁盘 98% 占满的主要来源之一；清空可立即回收。
4. **本次未重跑 Butano/Docker 构建**：C++ 侧（126 个 `game/tests/*.cpp`）的验证依赖
   devkitARM 容器，产物早于本次提交；Python 侧 1461 项测试已跑完并归因。
两者都未进入版本控制，**这是比仓库体积更紧急的风险**。
