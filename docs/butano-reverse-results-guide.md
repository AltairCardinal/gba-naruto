# Butano 查找与复用逆向成果指南

## 目的与边界

本指南用于把原作 ROM 的已验证结构、规则和资源转化为 Butano 续作输入。

| 工作 | 工作树 | 分支 |
|---|---|---|
| Butano 实现 | `/Users/altair/github/gba-naruto` | `codex/butano-foundation-research` |
| ROM 逆向 | `/Users/altair/github/gba-naruto-reverse` | `codex/reverse-engineering` |

两棵工作树共享 Git 对象，但文件状态和构建目录独立。Butano 可以只读检查逆向工作树，
也可以从逆向 commit 精确引入成果；运行时和构建脚本不得依赖另一工作树的绝对路径。

当前基准 ROM `rom/base.gba` 的 SHA-256 是
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
来源 ROM 哈希不一致时，地址、二进制片段和运行时快照默认不可复用。

## 成果分布

| 需求 | 首选入口 | 用途 |
|---|---|---|
| 当前完成度、最新结论 | `docs/sequel-roadmap.md` | 找到结论、限制和证据文件 |
| 稳定结构与字段语义 | `docs/structure-field-semantics.md`、`docs/content-pipeline.md` | 设计 Butano 数据模型和导入器 |
| 规则、地址和运行实验 | `notes/` | 理解结论的输入、地址、边界和反例 |
| 图形、音频、快照和机读结果 | `artifacts/<name>/manifest.json` | 作为生成器或测试的固定输入 |
| 可复现导出与验证 | `tools/export_*`、`tools/verify_*` | 重建成果并独立验真 |
| 回归契约 | `tests/` | 确认工具、格式和证据未漂移 |
| 已生成的语义内容 | `sequel/content/` | 供 Butano 生成固定内容表 |

常用成果类别：

- 地图与背景：`map-canvases-v1`、`bg-resource-canvases-v1`、
  `world-map-backgrounds-v1`。
- 角色与战斗视觉：`battle-visual-catalog-v1`、
  `battle-visual-runtime-timelines-v1`、`character-battle-visuals-v1`。
- 战斗效果：`battle-effect-resource-pairs-v1`、
  `battle-effect-sequence-bindings-v1`、`battle-effect-sprite-animations-v1`。
- 字体、肖像和剧情层：`battle-presentation-glyphs-v1`、
  `menu-portraits-v1`、`story-scene-layer-bindings-v1`。
- 运行时边界：`runtime-checkpoints/` 和 `scenario-*-reference-v1`。
- 音频：`audio/`、`scenario-41-audio-reference-v1`。

这份类别清单只是入口，不是完成度声明；以逆向分支的路线图、manifest 和 verifier
当前结果为准。

## 查找流程

先确认两棵工作树和分支：

```sh
git worktree list
git -C /Users/altair/github/gba-naruto-reverse status --short
git -C /Users/altair/github/gba-naruto-reverse log -5 --oneline
```

按功能关键词搜索已提交内容，避免把未跟踪实验误当成果：

```sh
git -C /Users/altair/github/gba-naruto-reverse grep -n -I \
  -e '角色战斗视觉' -e 'battle-visual' \
  codex/reverse-engineering -- docs notes tools tests \
  ':(exclude)notes/*.json'

git -C /Users/altair/github/gba-naruto-reverse ls-tree -r --name-only \
  codex/reverse-engineering -- artifacts |
  rg '/manifest\\.json$' |
  rg 'character|battle'

git log --max-count=50 --oneline \
  codex/butano-foundation-research..codex/reverse-engineering \
  -- artifacts notes tools tests docs/sequel-roadmap.md
```

找到候选成果后，按以下顺序阅读：

1. 路线图或说明文档中的结论与明确边界。
2. `notes/` 中对应调查记录，包括地址、输入和反例。
3. `artifacts/<name>/manifest.json` 中的 schema、来源哈希和文件清单。
4. 对应 exporter、verifier 和测试。
5. `git log -- <paths>` 中最后修改这些文件的 commit。

## 证据准入

一个成果只有同时满足以下条件，才能作为 Butano 实现依据：

1. 位于 `codex/reverse-engineering` 的已提交状态。
2. 来源 ROM、快照或上游产物哈希明确。
3. manifest 或说明能够关联 producer、verifier 和测试。
4. verifier 当前退出码为 0，测试能够在篡改或错误输入时失败。
5. 结论没有标记为 `candidate`、`disproved`、`rejected`、`superseded`
   或“已取代”。
6. Butano 只使用结论已经证明的范围，不从像素、名称或单个地址外推未证明语义。

项目中的验证字段并非所有旧 schema 都完全统一。通常
`runtime_verified` 强于 `code_verified`，但不能只看一个状态字符串；缺少字段也
不能自动判定失败。最终以说明、manifest、独立 verifier、测试和 commit 五者闭环为准。

复验示例：

```sh
cd /Users/altair/github/gba-naruto-reverse
python3 tools/verify_character_battle_visuals.py \
  --root . --artifact-dir artifacts/character-battle-visuals-v1
python3 -m unittest tests.test_export_character_battle_visuals -v
```

高开销或 mGBA verifier 必须遵循资源守卫要求；不要为“顺手确认”重复执行已经
哈希锁定且与当前实现无关的运行实验。

## 只读复用与正式引入

设计阶段可以直接从逆向工作树只读查看文件：

```sh
git -C /Users/altair/github/gba-naruto-reverse show \
  codex/reverse-engineering:artifacts/character-fbff-runtime-v1/manifest.json
```

但 Butano 的源码、测试和构建不得读取
`/Users/altair/github/gba-naruto-reverse/...`。正式依赖必须进入 Butano 分支。

### 首选：引入完整成果 commit

```sh
git show --stat <reverse-commit>
git show --name-status <reverse-commit>
git cherry-pick <reverse-commit>
```

只在 Butano 工作树没有重叠未提交改动、且该 commit 的路径范围与当前需求一致时使用。
完整闭环通常应同时包含 note、artifact、producer、verifier 和测试。

### 备选：从 commit 精确取路径

当逆向 commit 含有 Butano 不需要的独立成果时，先记录来源 commit，再只取所需路径：

```sh
git restore --source=<reverse-commit> --worktree -- \
  artifacts/<artifact-name> \
  notes/<evidence-note> \
  tools/<producer-or-verifier> \
  tests/<contract-test>
```

随后检查 `git diff -- <paths>`、运行 verifier 和测试，再显式暂存这些路径。不得复制
整个逆向工作树，也不得从其未提交状态或 `build/experiments/` 取文件。

### 仅生成 Butano 资产

如果 Butano 最终只需要转换后的素材：

1. 先把已验证的上游 manifest 和转换脚本纳入 Butano 分支。
2. 为转换结果写失败测试，约束数量、尺寸、palette、透明色、帧序和哈希。
3. 生成到 Butano 既有 graphics/audio/content 链路，不建立第二套资产系统。
4. 构建 ROM 并运行对应集成测试。
5. 在 Butano 的成果说明中记录逆向 commit、上游 schema、manifest SHA-256、
   转换命令和验证结果。

只复制 PNG、WAV 或 JSON 而不保留来源与转换契约，不算完成复用。

## Butano 实现闭环

每次复用按以下顺序执行：

1. **需求映射**：说明要复用的原作行为、用户可见效果及不准备复刻的边界。
2. **红**：先写会因成果缺失、schema 漂移或错误映射而失败的单元/集成测试。
3. **验真**：在逆向工作树运行对应 verifier，确认来源仍有效。
4. **引入**：按 commit 或精确路径导入最小闭环。
5. **绿**：复用现有 Butano 生成器、内容表和渲染/战斗链路完成实现。
6. **集成**：构建 GBA ROM；涉及画面、输入或音频时经资源守卫运行 mGBA。
7. **留痕**：记录来源 commit、manifest、verifier、Butano 测试和运行时边界。

当逆向结论更新时，用以下命令审查漂移：

```sh
git log --oneline <old-reverse-commit>..codex/reverse-engineering -- \
  artifacts/<artifact-name> notes/<evidence-note> tools/<verifier>
git diff <old-reverse-commit>..codex/reverse-engineering -- \
  artifacts/<artifact-name>/manifest.json
```

如果 schema、地址、文件哈希或结论边界发生变化，先让 Butano 契约测试失败，再更新
适配层和生成结果；不要直接修改逆向 artifact 来迎合现有 Butano 代码。

## 禁止事项

- 不读取或提交 `build/experiments/active/`、archive、trash 中的实验文件。
- 不依赖逆向工作树绝对路径、未提交文件或本地 `info/exclude` 状态。
- 不使用已取代、被证伪或只有候选状态的结论。
- 不把源空间 sprite 当成已证明的屏幕坐标、相机、blend 或 palette transform。
- 不因只需要一个文件而丢弃其 manifest、verifier 和适用边界。
- 不为复用成果另建与现有 Butano content/graphics/audio 链路重复的实现。
- 不在脏工作树中执行范围不明的 cherry-pick。

## 验收清单

- [ ] 已记录逆向 commit 和基准 ROM/上游产物哈希。
- [ ] 已读 note、manifest，并确认结论未被取代。
- [ ] 对应 verifier 和反例测试通过。
- [ ] Butano 先有失败测试，且复用现有架构完成实现。
- [ ] 构建和相关集成测试通过；必要的 mGBA 验收有资源守卫记录。
- [ ] Butano 不依赖另一工作树、临时目录或未跟踪文件。
- [ ] 用户可见行为与未覆盖边界已写入完成报告。
