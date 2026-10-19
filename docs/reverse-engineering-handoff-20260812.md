# 木叶战记 GBA 100% 逆向交接（更新至 2026-09-05）

> 本文是当前权威交接。旧的
> `docs/reverse-engineering-handoff-20260807.md` 已被 2026-08-09 之后的证据推翻，
> 只能用于查历史，不能用于判断当前 blocker 或进度。

## 0. 接手后先读这一节

- 仓库：`/Users/altair/github/gba-naruto-reverse`
- 分支：`codex/reverse-engineering`
- 基准 ROM：`rom/base.gba`
- ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 当前 Goal API 状态：**active**；用户已在 2026-08-27 明确要求“从中断处继续”，
  旧 CFG v10 暂停点已解除。目标仍是把 ROM 字节语义分类推进到
  `unknown_bytes=0`；每个里程碑前检查套餐余量，若有可验证证据表明余量不高于 5%，
  则暂停新写入。2026-09-05 最新账户检查为 `usedPercent=12`，可验证剩余约 88%，
  高于停止线；接手者启动下一里程碑前必须重新查询，不能沿用此历史余额。
- 不使用 Comet；不自动 commit；push 必须单独获得用户授权。
- 当前工作树有约 572 个修改或未跟踪路径。它们是累计逆向成果，禁止 reset、checkout
  或批量删除。
- `build/` 当前约 394 MiB；重任务必须继续通过共享 heavy lock 串行执行。

接手模型必须先执行：

```bash
cd /Users/altair/github/gba-naruto-reverse
git status --short --branch
python3 - <<'PY'
import hashlib
from pathlib import Path
p = Path('rom/base.gba')
print(p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
PY
```

若 ROM 不是 6,291,456 字节或 SHA 不匹配，立即停止，不得用其他 ROM 生成证据。

## 1. 唯一完成标准

目标不是“静态资源大致提取完”，而是以下条件同时成立：

1. `sequel/rom-byte-coverage.json` 的 `unknown_bytes=0` 且
   `semantic_classification_complete=true`；
2. 固定 114 个结构候选全部裁决；
3. 固定 32 个 bank 全部严格完成，其中 22 个有效 bank 的每条记录、每个字段都有
   哈希绑定、结构化且实际执行通过的证据，10 个 disproved bank 保持失败关闭；
4. 图像、音频、文本、地图、关卡、剧情、角色全部资源完成提取和 round-trip；
5. 地图、关卡、剧情、角色编辑器完成 UI→ROM→启动端到端矩阵；
6. 菜单与战斗逻辑修改完成行为回归；
7. clean rebuild、受守卫 mGBA 发布回归和实体 GBA 验证完成；
8. `tools/audit_reverse_engineering_proof.py` 在外部可信规范摘要下输出
   `complete=true`、32/32 bank、7/7 gate。

不得通过减少分母、改 `claim_status`、删除 limitation、把 unknown 改名为 padding，或
把单个 A/B 样本扩张成全记录覆盖来宣称完成。

## 2. 当前权威进度

| 指标 | 当前 | 目标 | 解释 |
| --- | ---: | ---: | --- |
| ROM 字节入账 | 6,291,456 / 6,291,456 | 全部 | unknown 也算入账 |
| ROM 字节语义分类 | 6,198,347 / 6,291,456 | 全部 | 98.52007230122885% |
| unknown | 93,109 | 0 | 1.47992769877115% |
| primary claims | 16,793 | 全部有独立证据 | 当前不是完成分母 |
| 规范 segments | 18,552 | 覆盖全 ROM | unknown 仍显式保留 |
| 结构候选 | 114 / 114 | 114 / 114 | 60 accepted、26 alias、28 rejected |
| bank 严格完成 | 10 / 32 | 32 / 32 | 当前完成的 10 个均为 disproved tombstone |
| 有效 bank 身份 | 22 / 22 | 22 / 22 | 不等于穷尽 |
| 有效 bank 全记录/字段 | 0 / 22 | 22 / 22 | 当前最大结构缺口 |
| 直接证据记录 | 23 / 2,954 | 2,954 / 2,954 | 0.7786% |
| 已执行结构化 verifier | 106 / 106 | 全部且语义完整 | ROM byte gate 96 / 96；bank contract 10 / 10 |
| 全局门禁 | 0 / 7 | 7 / 7 | 实体 GBA 仍缺硬件 |

权威文件按优先级为：

1. `sequel/reverse-engineering-proof.json`
2. `sequel/rom-byte-coverage.json`
3. `sequel/bank-proofs.json`
4. `docs/reverse-engineering-proof-policy.md`
5. `docs/final-completion-report.md`
6. `notes/reverse-engineering-current-gaps-20260806.md`
7. 各 artifact 的 manifest、payload、独立 verifier 和测试

不要从旧 handoff、聊天中的百分比或 artifact 目录名推导完成状态。

### 最新正式审计

v17/v18 helper、fixed pair、prebattle controller 与 scene source 四包 Tier-2 接入后的
正式审计已完成：

- proof / coverage SHA-256：
  `e50417ea10a2f485c3462812fe8aa74d518bb551fcac79f526ad75aad8c4a8e9` /
  `b14d1778bc9961356cca7f319c9d2ae85a07a6811276f9ee0cd1bc2070e96b82`
- formal / coverage auditor SHA-256：
  `4a979aaca355efa21e47b3889b6a2a0db21659d4ca8d3cb7f03d08df643a4144` /
  `b7552956dac37db445163d2287e53c647d731f6fd71f0e2c12a18a51cc801c86`
- 报告目录：
  `build/experiments/active/scene-source-four-packet-formal-r2-20260905/`
- report / guard SHA-256：
  `b2afd536ecc4437851664bda55874fa277fb8425085b75f07c7153498fb088da` /
  `f09deffdcc4fff545f003eb293b8cafe1632a13918686be170b3b66469afb30d`
- 106 次唯一结构化 verifier 全部 `exit_code=0`、`contract_ok=true`；ROM gate 96/96、
  coverage errors=0、evidence 校验通过。正式运行耗时约 40 分 08 秒，峰值 RSS
  492.828125 MiB，非降级。

报告 `complete=false`、`claim_status=incomplete`、177 blockers 是正确结果：93,109
unknown bytes、有效 bank 穷尽和 7 个最终门仍未完成。首次 canonical rebuild 暴露三个
packet verifier 读取 mutable live baseline 的自失效 P1；现已发布 immutable precoverage
并完成第二次 canonical rebuild。第一次重建、约 37 秒未受守卫 proof 预检和 spec 冻结前
约 82 秒 formal 均为已记录的可避免浪费，不得作为正式报告引用。
当前累计 artifact、
工具与测试尚未整体进入 Git 索引；“正式”只表示位于仓库标准 artifact 路径并通过
当前工作树的独立 verifier，不表示已 commit。未获用户或 Goal 授权不得擅自提交。

DirectSound 固定五个 primary range，共 344 bytes：16-byte mixed Thumb/ARM high32
helper、92-byte closed Thumb consumer、8-byte consumed literals、180-byte u8 scale
descriptors 与 48-byte（12×u32）frequency table。consumer 为 44 instructions / 5
blocks / 0 frontier，helper 为 5 instructions / 2 blocks / 0 frontier；两个 raw Thumb
BL producer 仅作 provenance，8 个 producer bytes 继续 unknown。不得外推自然运行时、
全局 caller/code/indirect 或 computed/RAM consumer 分母、播放行为、编辑、写回、
重定位或 free/allocatable space。

### 当前恢复状态（2026-09-05）

用户已明确恢复 Goal。DirectSound、PSG、u8-triplet、四段 artifact-bound gap、
MPlayMain、SoundMain relocated source/三个 alignment gap、M4A initializer-chain、
MP2K note allocator、MP2K dispatcher、CGB helper、CgbSound 与 CFG proven-roots v12/v13
均已闭环，不得重复制作。dispatcher 只净晋升
四段合计 102 bytes；五段既有 owner 共 238 bytes 只作 provenance，两个 2-byte gap
仍 unknown，历史 `candidate_027` 的 rejected 状态未改写。CGB 批次净晋升 1,282 bytes：
helper 164-byte code + 16-byte literal、CgbSound 1,008-byte code + 76-byte literal，
再加 13 段共 26-byte artifact-bound gap。不得重开或直接晋升
`[0x09B53C,0x09BCE4)` 1,960-byte 连续包络。后续调查已确认
`0x061F14 -> 0x09BA68` 是唯一可解码的 raw Thumb BL 形态，目标可线性闭合成
100-byte CFG 外观与 4-byte literal；但 producer 自身仍位于 current unknown，既无
冻结 source CFG，也无 table/callback membership，不能先假定它是指令再证明 target
是 code/root。该 104-byte 草案已在 GREEN 前停止并移出正常测试发现；只有先独立
闭合 source membership 才可重开，余下 630-byte CGB 尾段当前全部继续 unknown。

v12/v13/v14/v15 分别以 accepted artifact 和不读取 live coverage 的 immutable bundle
闭合固定 source-bound CFG 根，累计净晋升 1,502 bytes。V15 接受 `0x0611F4`、
`0x0618FC`、`0x08B6F0`、`0x09A3E0` 四根，拒绝 `0x09C0F4`；只晋升 398-byte
Thumb code 与 52-byte consumed literals，共 450 bytes。六段合计 386-byte holes、
一个 rejected range 与三个 indirect-PC frontiers 继续 unknown。V15 接入时
classified/unknown/claim/segment 为 6,127,385 / 164,071 / 14,572 / 16,693；随后
menu portrait LZ77→palette gap 净晋升 52 段 / 110 bytes；随后 tile-BG
LZ77→palette gap 净晋升 84 段 / 165 bytes；随后 boot Thumb code→consumed-literal
alignment gap 净晋升 12 段 / 24 bytes，当前为
6,127,684 / 163,772 / 14,720 / 16,693。权威 formal report 与 guard 位于
`build/experiments/active/boot-thumb-code-literal-alignment-gap-preflight-20260830/proof-formal-r1/`。

效率约束：最近三个 gap 包只净晋升 299 bytes，而每次完整 coverage / formal 均有较高
固定成本。后续接手者必须采用三级审计，不得再为每个小包重复跑完整 formal：

1. packet 完成时只做一级快速审计：TDD RED/GREEN、独立 raw-input verifier、身份哈希、
   current-unknown/重叠投影和失败关闭变异测试；只写候选 receipt，不改 canonical。
2. 待接入队列累计达到任一门槛后才做一次二级里程碑审计：净增至少 10 KiB、预计提升
   至少 0.15 个百分点、同类 packet 至少 4 个。该轮才统一
   rebuild canonical coverage、同步 proof 并执行一份非降级 formal。
3. 只有 `unknown_bytes == 0` 或发布验收时执行三级最终
   审计，重放所有 committed verifier 与发布门禁。

后续应先对 unknown 连续段按邻接 owner、已有消费者和可复用 verifier 批量聚类，优先
选择预期净增至少 1,000 bytes 的冻结合同；几十字节 gap 只能并入批次。分层只减少重复
执行频率，不放宽 owner、分母、独立 verifier、失败关闭或最终 `unknown_bytes == 0` 标准。

## 3. 已完成且可复用的成果

完整分类清单见 `docs/final-completion-report.md`。接手者不应重复制作以下成果：

### 3.1 图像与视觉

- 角色战斗视觉：558 槽、250 项资源、2,004 帧、2,190 component、784 animation、
  3,187 keyframe；coverage 2,023,076 字节。
- 战斗特效：18/18 组静态资源、phase 18/18、production pixel A/B 18/18。
- 47 张战斗地图；12 个非空 regular BG；24 条 story scene timeline；三页世界地图；
  43 个通用 Sprite ID；4 个 Cutscene OBJ ID；菜单/剧情立绘。
- 两张启动 framebuffer；107 个 tile BG palette；896 条指针可达 LZ77；41 条未绑定
  严格 LZ77 语法流。
- 菜单肖像目录的 311 个固定逻辑输出收敛为 74 个资源和 70 段物理 BGR555
  palette；每段 128 字节，共 8,960 字节，只有 54 种内容哈希。共享
  `0x084098C4` 的五个资源不能视为彼此独立的原位编辑槽。
- 菜单肖像 LZ77→palette 的 52 段 / 110-byte 短零对齐间隙已由独立 verifier
  接受；只能声明两侧 artifact-bound 原始零对齐字节，不得写成 padding、free、
  allocatable、自然可达、全局不可达、可编辑或可重定位空间。
- tile-BG 的 79 个 descriptor、236 个 palette entry、108 个 raw palette range 与
  107 个 merged claim 已与 896 条 pointer-reachable LZ77 共同冻结；其 endpoint 到
  palette source 起点之间的 84 段 / 165-byte 短零对齐间隙已由独立 verifier、
  165 个单字节 mutation、coverage/proof/formal 闭合。两个非零 long gap 与七个
  heterogeneous direct-CpuSet/reuse short gap 继续在合同外；不声明 padding、
  reserved/free/allocatable、自然可达、全局不可达、fixed-consumer 穷尽、最终像素、
  编辑或重定位安全。
- 场景视觉来源范围以 `scene-visual-packs-v1` 固定 9-record source table 的 57 段、
  88,756 字节完整分母为基线，冻结 29 段、3,288
  字节候选；保留 pack 5 已有 LZ77 owner 的 31 字节，只晋升 29 段、3,257 字节，
  类别为共享 OBJ palette、BG palette、definition record 与 animation record。
- 多个域已有原位回写、可变长 relocation 和修改 ROM 后像素 A/B；这仍不等于七类
  资源全量 round-trip。

### 3.2 音频

- MP2K/m4a：842 个语义区间、887,018 字节。
- 80/80 cue 目录与整曲渲染。
- Sappy 初始化函数单指令行为 A/B。
- 尚未完成全音频编辑器写回、全 ID 自然执行和真机音频矩阵。

### 3.3 文本、字库与脚本

- 对话：1,220 个 NUL 目标、18,207 字节文本、16,814 字节逐字节验证的零间隙。
- 字库：4,410 个 8×16 SJIS 字形、192 个 8×8 byte 字形、144,416 字节。
- SJIS lookup 表尾：rows 26..30 的五个 `<HBBI>=(0,0,0,0)` empty row，共 40
  字节；只声明冻结 lookup/parser 消费语义，不声明 padding、reserved/free space、
  natural runtime、全消费者、完整 Unicode、编辑或重定位安全。
- renderer 文本：11 表、704 槽、625 唯一 target、22,588 字节。
- fixed-consumer：11 表、750 槽（11 null）、735 记录、3,000 表字节、11,177 文本字节；
  同表零间隙另闭合 590 段、6,738 字节。
- profile、training、value-range、selector、battle-message 文本均有独立 verifier。
- 章节脚本：4 张根表、204 槽（200 非空）、18,994 节点、92 个合并记录范围、
  334,060 字节；speaker label 49 条、251 字节。
- 这些只证明 parser 实际消费边界，不声明 Unicode、全 ID 自然可达或安全编辑边界。

### 3.4 控制流

- 固定 263-root CFG：40,872 指令、7,725 block、86,184 指令字节、366 frontier。
- CFG v3：29 个固定间接 frontier、677 table cell、290 target、4,698 新指令、
  891 block、9,902 字节。
- proven-roots v1：3 producer、2 roots、6,166 指令、1,203 block、12,966 字节。
- proven-roots v2：5 producer、3 roots、4,809 指令、835 block、9,876 字节。
- boot interwork：唯一 BL→BX pc→ARM B，92 条 ARM 指令、8 block、10 edge、
  0 frontier，精确新增 414 字节。
- proven-roots v9：冻结 controller provenance 的 11 条 target-limited Thumb BL 中，
  9 条真实 controller source instruction 证明 8 个 root；独立重建 299 条指令、
  62 个 block、628 字节、16 条 baseline cross-edge、7 个 opaque return 与 0 个
  真正 frontier。`0x0736A4`、`0x07445C` 两条 excluded producer 继续 unknown。
- 当前综合、失败关闭的 bounded-CFG 汇总为 956 个 ARM instruction bytes、148,778 个
  Thumb instruction bytes，另有 32 个已证直接 producer bytes；合计晋升 149,766
  bytes、3,835 个 primary claims、33 个代码 kind，另单列 2 个 producer kind。冻结
  registry SHA-256 为
  `10ae3cc720e787630957b7cbbbbae379ec5f3e542dbabeb871df861915a676b`。
  该汇总仍不得称为全局函数图或自然运行时可达分母。
- `rom-selector-code-windows-v1` 固定 10 个 consumer source window、2,754 字节，
  只将其中 19 段、1,252 个 current-unknown 字节提升为 `consumer_code_slice`；它不
  计入 CFG reachable Thumb code，1,502 个已有 primary 字节也不重复认领。

### 3.5 bank

严格完成的 disproved bank：

`battle-handlers`、`character-stats-b`、`encounter-zones`、`fonts`、`items`、
`resource-pointers`、`sprite-animations`、`story-c`、`story-d`、`story-e`。

其余 22 个有效 bank 均只完成“至少一次身份关联”；各自记录分母和 limitations 以
最新 formal audit 的 `bank_results` 为准，不得写成 22/22 完成。

## 4. 已完成的历史里程碑：纠正战斗控制器分派

该里程碑已经由正式 artifact、coverage 与 proof 取代。以下内容保留用于解释旧证据
为什么错误，以及后续类似 CFG 工作应复用哪些合同；不得再按旧 RED 步骤重新开始。

### 4.1 已确认的旧证据错误

历史文件 `notes/battle-controller-states-20260723.json` 声称 36 个状态且结构闭合。
该结论已被独立逐状态解释推翻：

- 对所有 65,536 个 u16 状态输入执行 `0x0733A0..0x0735CA` 的真实 Thumb 分派器；
- 得到 38 个非默认状态、65,498 个默认状态；
- 映射 canonical SHA-256：
  `ce5e8ea24e274c4456482611609ee90144d31e064fccf0d85bf8f4643f44ac15`；
- 旧 `0x1020`、`0x3310`、`0x9200` 实际都走默认目标 `0x07504E`；
- 关键正确映射：
  - `0x1210 → 0x0736F8`
  - `0x1220 → 0x0737E6`
  - `0x2010 → 0x0739D0`
  - `0x3220 → 0x074074`
  - `0x3300 → 0x0740D4`
  - `0x8010 → 0x074510`
  - `0x9110 → 0x074834`
- 旧 controller end `0x075082` 在一条可达 4-byte BL 中间截断；
  `0x075080` 是 `BL 0x06EAD8`，之后还有 `0x075084` 的 BL 和 epilogue；
- 下一函数从 `0x07509C` 开始，纠正后的 controller context range 应为
  `[0x0732B4, 0x07509C)`，SHA-256：
  `c9bdc220590a851fa331960bcb32be90eb9ac7248a5cd3dabb9f8afa0b674bc1`。

完整 38 项映射已经逐项写在
`tests/test_export_rom_battle_controller_cfg.py`，不要重新手抄另一份常量。

### 4.2 完成态

正式成果位于 `artifacts/rom-battle-controller-cfg-v1/`，对应 exporter、独立 verifier
和两份测试均已接入 proof。它从完整 65,536 输入分母重建 38 个非默认状态，并得到
38 roots、2,756 条指令、739 个 block、6,172 个 reachable bytes、5 个 frontier、
227 条范围外 opaque edge 和 9 条 baseline opaque edge。纠正后的 controller 范围为
`[0x0732B4,0x07509C)`；`0x074918` 是唯一 frozen-baseline skipped root。旧 36-state
JSON 仍只作为历史输入保留。

### 4.3 不要直接修改旧 36-state JSON

`rom-cfg-proven-roots-v1/v2` 当前会哈希绑定旧 JSON。直接原位改旧文件会触发两套
artifact、coverage、proof 和审计哈希级联失效。

安全路线：

1. 保留旧 JSON 作为历史证据；
2. 新建 hash-bound 的 corrected dispatch inventory/artifact；
3. 在新文档和路线图中明确旧“36-state structurally closed”已被 supersede；
4. 新 CFG artifact 只以 ROM 原始分派器的 65,536 输入枚举为根分母，不复用旧语义标签；
5. 若以后要迁移旧 artifact，必须作为单独里程碑整体重导出并重跑 formal audit。

### 4.4 新 artifact 的正确设计

建议 schema：`rom-battle-controller-cfg-v1`。

必须包含：

- dispatcher range/body hash、65,536 输入分母、38 个非默认映射、65,498 默认映射；
- 38 个 target 先去重再作为 root，每个 root 保存全部 source state；
- 只跟随 controller 范围内的 Thumb direct/fallthrough edge；
- 范围外 direct target 记录为 `opaque_external_edge`，不得继续遍历；
- 外部 BL 的 fallthrough 若仍在范围内，必须继续；
- indirect PC、unsupported/decode failure 保留为真正 frontier；
- v2、v3、proven-roots-v1/v2 作为冻结 baseline；若进入 baseline 中部或新指令跨越
  baseline 字节，必须失败关闭；
- exporter 和 verifier 独立重建，verifier 禁止 import exporter；
- artifact 只包含 manifest 与 payload，输出目录拒绝 symlink、repo root、祖先和
  非本 schema 的非空目录，并以同级临时目录原子替换；
- coverage 只认领 `当前 unknown ∩ 新 block`，不得重复认领范围内已有 8 条 producer。

现有 8 条范围内 producer claim：

`0x73688`、`0x73690`、`0x7425A`、`0x7434E`、`0x7443C`、`0x74448`、
`0x74918`、`0x74F2C`。

### 4.5 已完成的验收清单（供同类 CFG 工作复用）

每项都先 RED，再最小 GREEN：

1. 完整 65,536→38 mapping 与 canonical SHA；
2. root 去重并保留 source states；
3. dispatcher、controller、root entry tamper 失败关闭；
4. bounded traversal：范围内 direct/fallthrough 扩展，范围外 target opaque；
5. 外部 BL target opaque、同一 BL 的范围内 fallthrough 继续；
6. indirect/unsupported 保持 frontier；
7. baseline entry/middle/straddle 三种 overlap 负测；
8. payload 与独立 verifier 重建相同 closure；
9. 修改 opaque edge 并重算 manifest hash 后 verifier 仍拒绝；
10. 输出路径 symlink/root/foreign-dir/implementation-only drift；
11. 正式仓库路径 artifact 独立验证；只有 Git 实际跟踪后才可称 committed；
12. coverage 只提升 current unknown，且不覆盖 8 条旧 producer claim；
13. ROM、artifact、verifier hash 漂移全部失败关闭；
14. proof spec 绑定新 verifier 的命令、source hash 和精确 summary。

完成 exporter 后，先输出精确 instruction/block/frontier/opaque-edge/coverage delta，再把
这些数字冻结进测试；不要预先把“controller 包络约 7.6 KB”当作实际收益。

## 5. 历史优先队列与当前选择规则

第 1–4 项后来已分别由 proven-roots v3/v4/v5 与控制器 artifact 处理，不是当前待办。
第 5 项仍因索引上界不足保持 unknown。当前新批必须从最新 coverage 的完整 unknown
范围与已验证 source provenance 重新复算，不能照抄本节历史地址作为任务清单。

1. `0x070DF8`：全 ROM target-limited Thumb BL 分母恰为 2，producer 为
   `0x074192`、`0x074836`；root 当前 unknown，可作为下一独立 CFG root。
2. `0x07305C`：真实 producer 分母为 4，不是旧结论的 2；必须包含
   `0x073696`、`0x0736C4`、`0x07444E`、`0x0749CE`，并使用纠正后的状态库存。
3. `0x07504E`：controller 内有大量直接 producer；需先做全 ROM target-limited
   denominator，再决定是否需要独立 root（controller artifact 很可能已覆盖其本体）。
4. `0x06DF88`、`0x08A534`、`0x08A588`：仅在 producer 分母和入口 provenance
   完整后处理。
5. 混合 UI 表 `0x5A7FCC..0x5A802C`：前 18 槽文本能贡献约 114 unknown 字节，
   后 6 槽是非文本资源；除非完整证明消费者 `r6∈[0,17]`，整表继续失败关闭。

不要再扫描已经 consumer-bound 且净收益为 0 的文本表；不要把 LZ77/m4a 数据中的
偶然 word 当代码或指针 provenance。

## 6. 资源与进程安全

- mGBA、Chromium、coverage、proof、全量 unittest 和大 CFG 必须通过
  `tools/run_guarded.py`，共用 `build/experiments/heavy.lock`。
- 推荐静态任务门限：`--min-available-mib 2048 --max-tree-rss-mib 1024`。
- 当前 coverage 只读重建实测约 16–18 分钟；v9 formal proof audit 实测约 41 分
  34 秒。两者长时间无 stdout 属于正常计算，不能据此重复启动第二份。
- proof verifier 单命令 timeout 已提高到 1,800 秒。formal audit 外层守卫必须复用
  v9 retry2 的 `wall=7200`、`idle=6900` 长任务门限，不能套用旧 1800/900 模板。
- 每 30–60 秒可用 `ps` 检查 owned process tree，但不得杀其他任务进程。
- 所有实验用唯一 run ID；候选输出放 `build/experiments/active/`，验证成功后再晋升
  `artifacts/`。
- 不生成数十万小文件；artifact 使用少量 canonical JSON/bundle；完成后归档实验。
- mGBA 长路线必须使用已验证快照，关键输入前后保存快照；一次实验只改变一个输入。

受守卫模板：

```bash
python3 tools/run_guarded.py \
  --summary build/experiments/active/<run-id>/guard.json \
  --lock-file build/experiments/heavy.lock \
  --min-available-mib 2048 \
  --max-tree-rss-mib 1024 \
  --wall-timeout-s 3600 \
  --idle-timeout-s 1800 \
  -- <command>
```

上面的模板适用于普通静态任务；formal proof audit 必须将两项分别改为 7200/6900。

## 7. 每个里程碑的固定收尾顺序

1. `git status --short`，确认未覆盖用户改动；
2. `git diff --check`；
3. 相关单元测试；
4. 相关集成测试；
5. 正式仓库路径 artifact 独立 verifier，并单独核对 Git 跟踪状态；
6. coverage `--write`，随后独立 audit；
7. proof spec/test 更新；
8. 通过受守卫 formal audit，并检查每项 `contract_ok=true`；
9. 更新 `notes/`、`docs/sequel-roadmap.md`、`docs/final-completion-report.md` 和
   `notes/reverse-engineering-current-gaps-20260806.md`；
10. 将新可复用模式登记到 `AGENTS.md` 的任务模式表；
11. 未获授权不得 commit/push。

`complete=false` 在中间阶段是正常结果。真正错误是 verifier 失败、contract false、
覆盖 overlap、分母漂移、哈希不匹配，或把 limitation 静默删掉。

## 8. 七个最终门的剩余工作

- ROM byte coverage：169,832 unknown。
- resource round-trip：图像、音频、文本、地图、关卡、剧情、角色尚无完整固定分母
  的全量写回矩阵。
- editor round-trip：缺地图/关卡/剧情/角色四类编辑器 UI→ROM→启动矩阵。
- logic modification：缺菜单/战斗逻辑完整行为回归。
- clean rebuild：缺固定依赖 clean-clone 确定性构建。
- emulator regression：缺原 ROM 与重建 ROM 的完整 mGBA 发布矩阵。
- physical hardware：缺实体 GBA、烧录介质和报告；这是唯一明确外部条件。

## 9. 低能力接手模型的最短执行清单

如果无法理解全部背景，只做以下动作，不要自行扩大结论：

1. 检查 Goal 和用户暂停状态；只有 Goal 为 `active` 且用户明确恢复后才继续逆向写入。
2. 检查 ROM SHA 和 Git 状态。
3. 从最新 coverage 的 `unknown` 与已有 artifact/consumer 证据交集选择一个固定分母小包。
4. 先冻结输入、范围、schema、失败关闭条件和精确验收数字；没有固定分母就停止。
5. 先写 RED 并保留正确失败收据，再实现 exporter、独立 verifier 与 artifact。
6. 不修改旧 artifact 来伪造新结论；新成果必须 additive 且不重复 primary ownership。
7. 静态闭包不需要 mGBA 时不得启动模拟器。
8. 大测试只能经 `run_guarded.py` 串行运行。
9. 任何 verifier 报错都先修根因，不改期望数字绕过。
10. 产物通过独立 verifier 后才接入 coverage/proof。
11. formal audit 的全部结构化执行均 `contract_ok=true` 才关闭该里程碑；当前
    DirectSound 基线为 78/78，ROM byte gate 为 68/68；proof spec 的 gate verifier
    配置总数为 79，其中 11 个旧 gate verifier 只有哈希绑定。
12. 用户已明确恢复；Goal active 且没有可验证的 ≤5% 余额证据时按冻结合同继续，直到
    unknown=0。Goal API 不提供余额百分比，不能虚构余额结论或提前宣称 100%。

### 9.1 Pi/MiniMax 接手的硬门槛（2026-08-12 实测补充）

一次 MiniMax-M3 接手会话已因连续两次无视 TDD 和资源守卫而终止。该会话在测试仍只有
dispatcher 7 项、`progress.md` 仍停留在首个 RED 时，就先生成正式 artifact、修改
coverage auditor，并两次直接运行未受守卫保护的全量 coverage audit。这不是工程或环境
blocker，而是低能力模型的范围控制和指令跟随失败。该会话留下的 controller CFG、verifier、
artifact 与 coverage 修改均只能视为未验收草稿。

以后用 Pi/MiniMax 接手时必须执行以下机器可观察门槛：

1. 启动时关闭 Lens、LSP、opengrep、自动格式化、自动修复和自动测试；本任务不允许安装
   formatter、linter、语言服务器或其他辅助工具。
2. 每轮只允许一个 RED→最小 GREEN；RED 命令、退出码、失败原因和 RSS 写入
   `progress.md` 后，才允许改产品代码。
3. `tests/test_export_rom_battle_controller_cfg.py` 未出现第 4.5 节对应测试前，禁止生成
   `artifacts/rom-battle-controller-cfg-v1/`，禁止修改 coverage/proof。
4. baseline 必须同时独立重建“合法指令入口集合”和“占用字节集合”：只有合法入口可作
   opaque stop；跳入指令中部或新指令跨越 baseline 字节必须失败关闭。只读取 artifact
   自报 block 范围不构成独立证明。
5. 每个 root 的计数必须由真实 CFG edge worklist 重建；只统计入口 block 或按地址包络
   推断闭包一律拒绝。
6. `progress.md` 超过一个实现步骤未更新，即视为停止门槛；监控者应先中止当前重任务，
   不允许模型继续扩大写入范围。
7. coverage、proof、全量 unittest、正式 exporter/verifier 均必须通过
   `tools/run_guarded.py`；直接运行即中止，不等待其自然结束。
8. 连续两次违反上述门槛时终止当前 Pi 会话，保留文件为未验收草稿；不得把这种情况写成
   环境 blocker。新会话只接收下一个尚未完成的 RED，不接收整个里程碑。
9. 禁止无意义断言，例如把同一表达式与自身比较；每个测试必须能通过单点篡改证明会因
   合同被破坏而失败。
10. 监控默认从 5 分钟开始；无须干涉则按 5→10→20→40→80 分钟退避，出现违例、
    blocker 或资源异常则恢复为 5 分钟。
11. 受守卫命令若需要保留子命令 JSON，首次运行就必须把子命令 stdout 写到实验目录；
    `run_guarded.py` 的终端 stdout 只有 guard 摘要，不能以“补全证据”为由在守卫外重跑。
12. 两个串行步骤之间超过 2 分钟没有新日志、子进程或 `progress.md` 更新，属于模型执行
    停滞而非环境 blocker；监控者只提醒继续已经授权的下一步，仍无动作才终止会话。

实测注意：`--no-lens --no-lsp` 不是进程级权限隔离；一个按这些参数启动的 Pi 会话后期
仍生成过 pyright 子进程。监控必须以实际进程树为准，不能只信启动参数或 TUI 的
`LSP Inactive` 文案。任务结束时终止该 Pi 拥有的辅助进程；运行中若出现未授权安装、
持续高 RSS 或与任务无关的分析进程，应先中止子进程并缩小下一会话范围。

## 10. 当前交接边界

### 2026-08-13 至 2026-08-20 Goal 续跑增量

控制器 CFG 已正式晋升并完成 dispatcher payload verifier 加固；随后 proven-roots v3
与 v4 已接入 coverage/proof。该批接入后覆盖为 classified 6,020,083、unknown
271,373、95.6866%，`semantic_classification_complete=false`。v3 的 `0x070DF8`
闭包为 52 指令/8 block/110 字节/0 frontier；v4 的 `0x07305C` 闭包为 486
指令/118 block/1,044 字节/6 个间接 PC frontier。当时的下一候选为 `0x07504E`；
该历史待办后来已由正式控制器 CFG 处理，接手者不得重复执行。完整证据见
`notes/rom-cfg-proven-roots-v3-v4-20260813.md`。

随后 v5 已完成三个 root `0x06DF88`、`0x08A534`、`0x08A588`，新增 1,252
字节；该批接入后为 classified 6,021,335、unknown 270,121、95.7065%。

随后按固定消费者/固定分母零间隙模式完成四组增量：renderer 548 段/12,431
字节、fixed-consumer 429 段/4,141 字节、dialogue font SJIS source 19 段/
2,848 字节、相邻固定 pointer-reachable LZ77 对齐 341 段/648 字节。每组均有
独立 verifier、逐段篡改负测和 guarded coverage 写后自审。battle-presentation 固定
消息表再闭合 78 段/1,293 字节零间隙；proven-roots v6 以 6 条固定 Thumb BL
producer 证明 5 个 root，独立重建 12,564 条指令、2,305 blocks、27,224 字节，
保留 85 个间接 PC frontier，只晋升 current-unknown 交集 25,926 字节。该批接入后为
classified 6,068,622、unknown 222,834、claim 12,978、96.4579%，coverage SHA-256
`17b35d793dc41f5335bb302bee9dabb76d7f8f614bacf00643fb6211b1ffe132`；Goal 仍未完成。
固定表之间 1,840 字节因 positions variant header/尾部消费者语义未闭合而保持 unknown。

随后 fixed-consumer artifact 从 9 表扩展到 11 表，绑定 active-action description
`0x5994D8..0x599634` 与 ninja-tool description 的非重叠后缀
`0x5997C4..0x599924`；逻辑表前 6 slots 与 message-command 物理重叠，仅作 provenance。
735 条记录与 590 段/6,738 字节同表零间隙均由独立 verifier 和逐段篡改负测闭合，
净增 7,694 字节。该批接入后 coverage 为 classified 6,076,316、unknown 215,140、
claim 13,306、96.5804%，SHA-256
`0e89d35fc7ffed988ce6a6c8aecc09041f5d08e86a368d8d0fe948178f01a9b9`。

随后复用已验真的 `sprite-definition-assets-v2`，独立重建 43 个从
component-list pointer 开始的 `0x28` resolved window；其联合与 current unknown
相交为 3 段/1,720 字节，不扩张到 animation payload 或窗口外间隙。该批接入后 coverage
为 classified 6,078,036、unknown 213,420、claim 13,309、96.6077%，SHA-256
`c6c052eb95427b624fe9a05f4c5dda5ab5083996c52a603d7e9bee6d528531fe`。

随后 proven-roots v7 固定两个 `mov pc,r0` dispatcher 的 45 个有序表项、21 个唯一
目标；扣除 13 个 v6 基线入口后，以 8 个新 root 重建 155 条指令、38 block、332
字节、17 cross-edge，并保留 1 个新的间接 frontier。正式覆盖现为 classified
6,078,368、unknown 213,088、claim 13,347（96.6130%）；coverage SHA-256 为
`91171b14c1ab3f649f0cf837bd80756f01f8910d4d385cf827a78f83a747d551`。

随后 proven-roots v8 从已验真的 scene visual source closure 中固定唯一 Thumb BL
producer `0x0808BE5C→0x0808B99C`，以 v7 及此前全部 CFG 产物为冻结基线，独立
重建 113 条指令、20 个 block、246 个可达字节、10 条 baseline cross-edge，并保留
1 个 `indirect_pc_target` frontier。producer 与 source consumer slice 已有更具体
分类，不重复认领；20 个 block 全部从 current unknown 晋升。v8 里程碑时正式覆盖为
classified 6,078,614、unknown 212,842、claim 13,367（96.6170%）；coverage
SHA-256 为
`49ee896c7b7a71a523a40bfc7823b62cee01b02b8d3947ba3e2acf3128af572c`。
60 次唯一 verifier 执行全部 `contract_ok=true`，但
`semantic_classification_complete=false`，Goal 仍为 active。

随后复用 `battle-effect-sprite-animations-v1` 的既有 manifest 与独立 verifier，按
ROM 原始字节重新冻结四类完整 source range：178 段 component list、18 张 definition
pointer table、23 段 animation timeline、18 张 animation pointer table。237 个范围
互不重叠且接入前均完整为 unknown，共晋升 11,120 字节；分母 SHA-256 为
`c30b25fbed4a80914e8bc9e8d33ec7545e47a01a005866460323ac8c9b84ba30`。
该 battle-effect 批次接入后覆盖为 classified 6,089,734、unknown 201,722、claim 13,604（96.7937%）；
coverage SHA-256 为
`6a05996ee76bbd9bee6acc7232c2ac969dd2f2b762282e2ba3698f6c5ef01b99`。
60/60 verifier 合同通过；不声明自然运行时可达、图形/调色板范围扩张、可编辑空间或
写回安全，Goal 继续保持 active。

随后新增 additive `rom-referenced-text-slot-padding-v1`：从消费者首个 NUL 后一字节到
固定物理槽末尾，独立重建 direct selector 46/550、configured selector 38/368、
chapter speaker-label 49/337，共 133 claim / 1,255 字节全零结构填充。接入前每段
完整属于 current unknown；未引用槽、NUL/前缀、文本语义、自然可达、编辑/写回安全
和可安全分配空间均不声明。该批接入时 coverage 为 classified 6,090,989、unknown 200,467、
claim 13,737、segment 16,009（96.8137%），SHA-256 为
`aebd73ea9bcf2e7eaf87f25301da25293015224ae0c77045c9822eb3c7b1f894`；Goal 继续保持
active。对应正式审计为 61/61 verifier、ROM byte gate 51/51，报告 SHA-256 为
`cac3e4634052391ae91cbc7eb20a41e01af7ebf42d92e89bac9a3673300c134c`。

随后新增 `rom-selector-direct-source-records-v1`：从固定 46-row producer 分母、
source/vector、19 字节目标槽 stride 指令链、6 个 renderer bridge 调用与
bridge→parser 调用，独立重建 `0x0059F5F0..0x0059F988` 的 46×20 字节完整来源记录。
920 字节接入前全部属于 current unknown；bytes 2..19 的字段语义、自然全行可达、
Unicode、编辑/写回安全、可分配空间、`0x0059F988` 与相邻 profile 均不声明。当前
coverage 为 classified 6,091,909、unknown 199,547、claim 13,783、segment 16,055
（96.8283%），SHA-256 为
`d441f702add65e36dce291cfa6e6235e3ee7156cbb7b259ad47255848a581049`；Goal 继续保持
active。正式审计为 62/62 verifier、ROM byte gate 52/52，报告 SHA-256 为
`dc15268b5cbff9113d241737529f591bac2836c51104696f49295b266d6e10d5`。

随后新增 `rom-selector-code-windows-v1`：固定 renderer/parser、bridge、enumerator、
direct consumer、menu selector、lifecycle、three-way mapper、configured consumer、
three-way producer 与 copy parser 共 10 个完整 source window、2,754 字节。coverage
只晋升其中 19 段 current-unknown 交集、1,252 字节，1,502 字节已有 primary
ownership 不变；bridge/mapper promotion 均为 0。接入后 classified 6,093,161、
unknown 198,295、claim 13,802、segment 16,066（96.8482%），coverage SHA-256 为
`5cee1d349689bf735e3517662f9142fbac5dd421dbf8c107ea6219ee6801a8b8`。不声明
instruction-only、自然运行时可达、global caller exhaustive、安全编辑/重定位、
可分配空间或新字段语义。正式审计为 63/63 verifier、ROM byte gate 53/53，报告
SHA-256 为 `6b8b7632f3957184ee539fa02c1951fc9fb7d88a19c15fb07411b513991b6473`。

随后新增 `rom-menu-portrait-palette-inventory-v1`：从固定 63×5 目录表（record 0
五个零 sentinel）、special pair、u8 selector 与五条 GPU queue caller 独立重建
311 个逻辑输出。74 个资源按物理 palette 指针/range 去重为 70 段 128 字节
BGR555 数据，共 8,960 字节；70 段只有 54 种内容哈希，不能按内容继续合并。唯一
跨资源别名为 `0x084098C4`，由资源 `[0,67,68,69,70]` 共用。全部 70 段接入前均
完整属于 current unknown；不声明动态 caller 输入域、全部自然可达、graphics、
运行时像素等价、独立别名原位编辑、指针改写、relocation 或 free space。接入后
classified 6,102,121、unknown 189,335、claim 13,872、segment 16,119（96.9906%），
coverage SHA-256 为
`b95e1239420e416fe03244d8e3584adc5dd93470dfa8bfe8e501addb78c3f2cd`。正式审计为
64/64 verifier、ROM byte gate 54/54，报告 SHA-256 为
`431829ea84d9f58b42164bd272852793b5e590dd87655328058a2a917e755809`；报告仍正确保持
`complete=false`、175 个 blocker。

随后新增 `rom-scene-visual-source-ranges-v1`：独立 verifier 从
`scene-visual-packs-v1` 固定 9-record source table 的 57 段、88,756 字节完整分母
重建 29 段、3,288 字节候选。pack 5 前 31 字节仍由既有 LZ77 primary
claim 唯一拥有，仅将 29 段、3,257 个 current-unknown 字节晋升；类别分母为共享
OBJ palette 2/64、BG palette 9/2,304、definition record 9/697、animation record
9/192。接入后 classified 6,105,378、unknown 186,078、claim 13,901、segment
16,142（97.0424%），coverage SHA-256 为
`02ca4394bd727c9b27c7ac168e12d141af0be4354b185d8242b8c1f66a353bea`。正式审计为
65/65 verifier、ROM byte gate 55/55，报告 SHA-256 为
`43a7106eeea71c47fa2af02d51b65b5d526ae7f580c142c566c9ace6a4611e58`；报告仍正确保持
`complete=false`、175 个 blocker。

随后新增 `rom-cutscene-obj-source-ranges-v1`：从两个固定四记录根表独立重建
4 个 Cutscene OBJ 资源 ID 的 10 个 frame 与 10 个 animation，将 28 段、400 个
current-unknown 字节晋升。类别分母为 component definition record 10/240、definition
pointer table 4/40、animation timeline 10/80、animation pointer table 4/40。接入后
classified 6,105,778、unknown 185,678、claim 13,929、segment 16,171（97.0487%）；
artifact manifest SHA-256 为
`a0e97ec43858a145a7c26dc71c5b89dfe8c4d9a5d6074ccad88c4ae56e03afd5`，独立 verifier
SHA-256 为 `a1075b8885378fe2c26c1c262126ad8098bb81c171a805cb3e08ed0d8217c446`，coverage
SHA-256 为 `2ff9bc857e182c4bfeeaa572929569801549765ef1d3566cf10c17334125b9d1`，proof spec
SHA-256 为 `1e695563b49712dd82aeab33677e06b39cbbf120712e8e3baa93ee73bac2c038`。受守卫正式审计
66/66 verifier 与 ROM byte gate 56/56 全部通过，报告 SHA-256 为
`65605bc56f29e641bc0f19821c32512ca69a6da6025a6b2f2d726f1055e00beb`，guard SHA-256
为 `ff643d70bc31774ef40ee9e274cf701406a7c513e55479f7166c72fa88fd7fd1`，formal auditor
SHA-256 为 `4e5b95705a2aa8252da96f927872a6701bb1561b6748230cbc4c209815e28d36`；`bad=0`、峰值
RSS 523.1171875 MiB，报告仍正确保持 `complete=false` 与 175 个 blocker。本批仅证明
固定来源范围及 parser/终止符/指针关系，不声明未知 component 字段语义、自然可达、
最终场景合成、graphics/palette 扩张、编辑/重定位安全、相邻间隙或 free space。

随后 proven-roots v9 将冻结 controller CFG provenance 的 11 条 target-limited
Thumb BL 分母闭合为 8 个新 root、299 条指令、62 个 block、628 字节、16 条
baseline cross-edge、7 个 opaque return 与 0 个真正 frontier；coverage 只晋升 62
个完整 current-unknown block。再接入 `rom-parser-bound-zero-padding-v1` 的 142 段/
198 字节，以及 proven-roots v3/v7 dispatcher 中 8 个/32 字节 masked residual cell
和 9 个/36 字节 indexed table cell。随后复用 direct CpuSet inventory 的完整 12-source
分母，只晋升其中仍完整 unknown 的 6 段 32-byte BGR555 palette，共 192 字节；另 6 段
保留既有 primary owner，`0x00405FF0` 也只接收已证明的 32 字节而不扩张到 256 字节父
记录。该批完成时基线为 classified 6,106,864、unknown 184,592、claim 14,156、
segment 16,257（97.0660%）。随后复用 `rom-boot-interwork-v1` 的冻结 producer chain、
artifact 身份与独立 verifier，将其显式跳过的 `0x0009C56E..0x0009C570` 两字节
`C0 46` / Thumb `MOV r8,r8` 只分类为 veneer alignment NOP；原 artifact 的
`skipped_interwork_padding_classified=false` scope 不变，也不外推自然可达、全局不可达、
sibling veneer、RAM 目标、编辑/重定位或可分配空间。该阶段基线为 classified
6,106,866、unknown 184,590、claim 14,157、segment 16,257（97.0660%）；coverage/proof
SHA-256 分别为
`5dc289d3b088b6f565e121ae9de2f288fa32a1c62cac4ad98027dbc9ffe3abca`、
`5da730524544645d25657e56d84e605c47a73deede6436e8a96c6628ffca7812`。该阶段正式审计
68/68 unique verifier 全部 `exit_code=0`、`contract_ok=true`，ROM byte gate 58/58、
bad=0；报告 SHA-256 为
`ccbf80ad4c74923135d00b86538fc48dc58d206e9cc31357086d2c07f1f0f0d0`。

随后由本轮闭合的小包是文件 `[0x0053D714,0x0053D73C)` / GBA
`[0x0853D714,0x0853D73C)` 的 40 字节：真实 31×8-byte SJIS lookup 完整分母
`[0x0053D644,0x0053D73C)` 中的 rows 26..30，五行 `<HBBI>=(0,0,0,0)`，由
31-row lookup loop 与 renderer parser 实际消费。只能命名为 empty lookup rows；
不能称为原作者意图上的 reserved、free space、自然不可达、可编辑或可重定位区域。

SJIS empty lookup rows 接入后，当前 classified 6,106,906、unknown 184,550、claim
14,158、segment 16,257（97.0667%）。coverage/auditor/proof SHA-256 分别为
`3b562213df931df21e1bf237226c73279b883d427d02dccbf54e063bd18e3dd7`、
`a0109d2443858b09f9193f80a45dafa046e9661c863440b6ddcb42e651936f29`、
`ba3f4a3ecc51931478bdacc4f7124d68c3faeac4c2262f2f36be926088dc1f29`。正式审计
68/68、ROM byte gate 58/58、bad=0、175 blockers；report/guard SHA-256 分别为
`ff6087c3313dec3b71f16d96af9aa503844a44aa4ea1a2f286e21b98dc5c93bc`、
`0260f58160f8f6f1ac108bf5254179fa6f443c4d6cfca43173fc9776211919ca`，峰值 RSS
614.55078125 MiB。窄语义仅限这五个冻结 empty rows；不外推 padding、reserved/free、
natural runtime、全消费者、完整 Unicode、编辑或重定位安全。

motion spawn→sequence descriptor 两字节对齐间隙现已闭合：文件
`[0x0053EF2E,0x0053EF30)` / GBA `[0x0853EF2E,0x0853EF30)` 的 `00 00` 只被分类为
达到下一 4-byte 边界所需的两个字节。合同固定 15×10-byte motion table、索引 14 的
`<hhhhh>=(-1,0,0,0,0)` 显式 terminator、22×24-byte sequence descriptor 完整表、
左右 owner、两套既有 artifact/verifier/test、精确 current-unknown 与对齐公式；右侧
primary owner 仍为 520 字节 `[0x53EF30,0x53F138)`，完整 table/source 则为 528 字节
`[0x53EF30,0x53F140)`，两者不得混淆。该 claim 不声明 padding、reserved/free space、
自然运行时可达、全局不可达、编辑/重定位安全、可安全分配、邻接字节或消费者完备性。

接入后 classified 6,106,908、unknown 184,548、claim 14,159、segment 16,257
（97.0667% / 2.9333%）。coverage/auditor/proof SHA-256 分别为
`7b108bf257cc99e9d4af7a47824b51e79f23e823fc0e1fe6d59fbd47500a8eab`、
`6fbf0059d76116a9d9bb5d1313223dcc942cadf29c5fcbd3682292fa632f53a6`、
`57644273a2cf7e5f7f9bdfdad350cef0f21a99bb5137fcfa0900fc9d62b5b903`。正式审计
68/68、ROM byte gate 58/58、bad=0、175 blockers；report/guard SHA-256 分别为
`3844c1ff49a4a2da5142f517ee3066a15eccadf2b87e864407a7bc0e369bdd89`、
`66ae9eead07daaed3ac9485d8b75a6ba29eae1e901e7c2d9c65c47c1aafd52a7`，峰值 RSS
584.328125 MiB。全局状态仍为 partial，Goal 继续 active。

battle presentation binding→tile-assets 两字节对齐间隙随后闭合：文件
`[0x005A320A,0x005A320C)` / GBA `[0x085A320A,0x085A320C)` 的 `00 00` 只被分类为
达到下一 4-byte 边界所需的两个字节。左侧是 `[0x5A2EF4,0x5A320A)` 的
79×10-byte binding table，其终点来自固定 record count 而非 terminator；右侧是
`[0x5A320C,0x5A4708)` 的 79×68-byte tile-assets table。合同绑定精确 current-unknown、
左右 owner、完整表/末条与首条记录、两套 canonical artifact/verifier/test、表/候选/
范围分母 SHA 和对齐公式。该 claim 不声明 padding、reserved/free space、自然运行时
可达、全局不可达、编辑/重定位安全、可安全分配、邻接字节、额外字段或消费者完备性。

coverage/proof 静态合同接入后 classified 6,106,910、unknown 184,546、claim 14,160、
segment 16,257（97.0667% / 2.9333%）。coverage/auditor/proof SHA-256 分别为
`66f129450f31eb1ff9f4e931c219a463710b5caee21c0b1aa7f9c4ad3ffe70a6`、
`2c604c710fc058c7ad9e07653a38385726671ae5940eb54f9b204df1c4567fe4`、
`dc88f57780fde125b53b1ccffe29cdf1c3d0aecb880f0de30bb4f12f513c0782`。
正式审计 68/68、ROM byte gate 58/58、bad=0、175 blockers；report/guard
SHA-256 分别为
`6839a623b83967b523f6aca76f5f420fcee326ef2fbbc11f19ca91a0a78a03c1`、
`77a31c1b757eb5ab702fcbf62e466a3c91393ecdc027b72a2508ff98e45f34ea`，
峰值 RSS 593.7890625 MiB。全局状态仍为 partial，Goal 继续 active。

runtime-state selector→handler-pair 两字节对齐间隙随后闭合：文件
`[0x0053E696,0x0053E698)` / GBA `[0x0853E696,0x0853E698)` 的 `00 00` 只被分类为
达到下一 4-byte 边界所需的两个字节。左侧冻结 `[0x53E596,0x53E696)` 的
256×1-byte selector table 与三段现有 ownership；中间 `[0x53E5A8,0x53E5B3)` 的
LZ77 record 38 继续保持原 primary。右侧冻结 `[0x53E698,0x53EE98)` 的
256×8-byte handler-pair table，并逐行由 map-events bank 与独立 disproved-candidate
verifier 重建。合同不声明 padding、reserved/free space、自然运行时可达、全局不可达、
跨表 dataflow、编辑/重定位安全、可安全分配、邻接字节、额外字段或消费者完备性。

接入后 classified 6,106,912、unknown 184,544、claim 14,161、segment 16,257
（97.0668% / 2.9332%）。coverage/auditor/proof SHA-256 分别为
`a061b3f9fa9551d34f4a3add7b2b062152cc2c2f50f439dd75c210c004e3e1de`、
`8dccae1f87c4137228551096c1de14878b1d96b7a733be9748598542a410f7c4`、
`b8527d82fb35db5ad53e58fed96c873a95cf9b594c2ffdfba81c2d96434d81e4`。
正式审计 68/68、ROM byte gate 58/58、bad=0、175 blockers；report/guard
SHA-256 分别为
`63520dee7225e55e24dbcb71f5c724dea2cdadeba1a2f5e591edf353dd08a529`、
`ce11dfd822638d1617a148e7856262c7e566efd20000514404930c1442d6eab9`，峰值 RSS
616.96484375 MiB；完整 proof 测试 49/49 通过。全局状态仍为 partial，Goal 继续
active。实验目录为
`build/experiments/active/runtime-state-handler-table-alignment-gap-coverage/codex-r1-20260822/`。

Cutscene OBJ palette→definition 四处两字节对齐间隙随后闭合：文件范围
`[0x0012DEFA,0x0012DEFC)`、`[0x0012E442,0x0012E444)`、
`[0x0012E95E,0x0012E960)`、`[0x0012ED6E,0x0012ED70)` 合计 8 个 `00`
字节。独立 verifier 自行解析两张固定四记录根表、slot 0、四条 type-0x10 palette
stream、严格 parser endpoint、4-byte alignment equation 与 rooted first definition
record；既有 Cutscene OBJ source artifact 的 28 ranges / 400 bytes 保持不变。合同不
声明 padding、reserved/free/allocatable space、自然运行时可达、完整 Cutscene gap
分母、未知 definition 字段语义、最终像素、编辑或重定位安全。

接入后 classified 6,106,920、unknown 184,536、claim 14,165、segment 16,257
（97.0669% / 2.9331%）。coverage/auditor/proof SHA-256 分别为
`f77fbbf6271d04989c0e16ac36287cf6bcd4d2454d9549eb5fbed693a757c33f`、
`4908778b32fa5b2fc8473f88a8f3fa44f0541b5c9110d57260c3530ff38d65b4`、
`8b1093446d04cd68f83ef5cf2d978cb618540ca9bf0203ba57ee3487a9fd1ba7`。
正式审计 69/69 唯一结构化 contract 全部 `exit_code=0`、`contract_ok=true`，ROM
byte gate 59/59、bad=0、175 blockers；proof spec 的 gate verifier 配置总数为 70，
其中 11 个旧 gate verifier 只有哈希绑定。report/guard SHA-256 分别为
`6238a8f64de72cea9e0536d4a72f7b6825d0ea4dc1ac63b888d9516b9544f555`、
`ef9da54d81f0f1fe12e30fabefc6615de1476b274a964b961e9b641458f95ced`，峰值 RSS
616.93359375 MiB。报告保持 `complete=false`、`claim_status=incomplete`，Goal 继续
active。实验目录为
`build/experiments/active/cutscene-obj-palette-definition-alignment-gap-coverage/codex-r1-20260822/`。

以下 2026-08-12 控制器实验候选仅保留为历史来源，现已由正式仓库路径 artifact、
coverage 和 proof 取代：

`build/experiments/active/pi-minimax-m3-controller-artifact-probe2-20260812/candidate/`：

- manifest SHA-256：`9e2e961fd8d89accea910684c4310ddb05e40f7cf1fe2b1a5f0a34426020832c`；
- payload SHA-256：`8913d2e1e9db43d069cdb75ed481e39a2cb5ce15e6827518a0f65016a4c890d7`；
- 独立 verifier：`verified=true`、`errors=[]`；
- 38 roots、2,756 指令、739 blocks、6,172 reachable bytes、5 frontier、227 条外部
  opaque edge、9 条 baseline opaque edge；
- `0x074918` 是唯一 frozen-baseline skipped root，`entry_block_id=null`、count=0；
- exporter/verifier 守卫峰值分别为 88.30/76.86 MiB。

该候选后续已按正式仓库路径 artifact 独立验证 RED、受守卫 exporter 原子晋升和
implementation identity 合同完成正式接入；接手者不得再把这段历史待办当作当前
blocker，也不得重复生成控制器 artifact。

## 11. 2026-08-27 lookup + boot Thumb handoff 接手点

该里程碑当时的历史 coverage 快照为：

- classified：6,120,972 / 6,291,456（97.29022979736328%）；
- unknown：170,484（2.70977020263672%）；
- claims：14,459；segments：16,568；
- coverage SHA-256：
  `9ed94f7cab667383c136b6fdb11132d077329f8f6a67b74871ce32f4038b3529`；
- auditor SHA-256：
  `b9bb12d1aeed440b2dae3fc2eed0a699d9e35f95519fb028001f9f426c9cae4e`；
- proof spec SHA-256：
  `ca2afde1b83177f1bf3e503a72c22729070915d7c262bd3b0b96e1c424c7334d`。

本轮新增且不得重复生成：

1. `artifacts/rom-u8-indexed-u16-pair-lookup-v1/`：只晋升
   `[0x0059F560,0x0059F5F0)` 的 144 bytes / 1 claim；880-byte 逻辑后缀仍由既有
   selector-direct-source owner 持有。
2. `artifacts/rom-boot-thumb-handoff-cfg-v1/`：晋升 27 code claims / 1,226 bytes
   与 22 literal claims / 296 bytes；25-range union 为 1,522 bytes。wide envelope、
   两个 indirect frontier 和 opaque external targets 都没有分类。

正式审计收据位于
`build/experiments/active/lookup-boot-formal-proof/codex-r1-20260827/`：

- 76/76 executed structured contracts 均 `exit_code=0`、`contract_ok=true`；
- ROM byte gate 为 66/66 hash-bound + contracted，evidence valid；
- report SHA-256：
  `bc598b5a1f13547e80c35b0b765c9cea0cf89bb4a344a1bd69e04c049cf01eb8`；
- guard SHA-256：
  `3330400830e5234b076e49f7a11b70c69c93b0b7457e3ea5acdbd8e550370c24`；
- 耗时 2,754.867994 秒，峰值 RSS 627.62109375 MiB，非 degraded；
- 正确全局状态仍是 `complete=false`、`claim_status=incomplete`。

promotion 基础设施兼容性已按 TDD 修复：`tools/experiment_workspace.py` 现在同时接受
legacy bare SHA receipt 与严格 `{sha256,size}` receipt，拒绝额外字段、非法 SHA、bool/
负数/非整数 size 以及 size/hash mismatch；`tests.test_experiment_workspace` 13/13
通过，Sol medium 只读复核 ACCEPT。后续不得把 structured receipt 再误判为 artifact
hash mismatch，也不得把 verifier 的 structured manifest 改回弱 legacy 格式。

下一候选注意事项：

- `[0x00596CCC,0x00596D5C)` / 144-byte 全零范围已被 Luna max compatibility gate
  明确 `REJECT / 0 bytes`。现有 selector 公式只能说明它数学上对应 character ID 0，
  没有 producer/caller 证明 ID 0 是合法域；不得称为 sentinel row、padding、reserved、
  free/allocatable space，也不得接入 coverage。
- `[0x000000C4,0x000000C8)` / 4-byte boot gap 也已被 Luna max compatibility gate
  `REJECT / 0 bytes`。固定 display handoff chain 的局部控制流确实绕过该 word，但
  没有针对 `0x080000C4` 的完整 target-limited inbound producer denominator；原始字节
  `00 f0 29 e1` 也不能被命名为 NOP、padding 或 free space。只有新增独立 inbound
  producer census 后才能重新申请，当前继续 unknown。
- `[0x0059EAE0,0x0059F560)` / 2,688 bytes 已有负证据否证局部 112×24 上界；必须先
  由 Sol/Codex 闭合 scheduler callback 生命周期，当前不能交给 Luna 或直接分类。

### 11.1 `0x59EAE0` lifecycle gate 已停止在真实 frontier

上述 scheduler 前置任务现已完成，但结论是 `REJECT / 0 bytes`，不是 2,688 字节
晋升。权威报告：

`build/experiments/active/scheduler-callback-lifecycle-gate/codex-r2-20260827/report.json`

- report SHA-256：
  `1638ab9dab45800256fd921e950ef53600f6f592a05f39842b26bfbd7a983ec2`；
- verifier/test SHA-256：
  `70d7d3618adf124fc43a3f08acf6b294d1bbbcd412b048ff96c0556dfcc92878` /
  `b5d4a55239aafa053330efbc0cabf92aee93787a6bdf8892b388fd0e7ca053c6`；
- `verified=true`、`errors=[]`；定向测试 4/4 通过；Sol medium 只读复核 ACCEPT；
- 8 个 `0x08061D7C` 直接注册点、11 个 wrapper、`BX r1` dispatch、返回清理，以及
  `0x0808F73C`/`0x0808EF2C` 的 literal-registration 结构已经闭合；
- `0x0808F654` 仍没有 raw direct branch 或精确 Thumb pointer producer。报告只把它
  标为 computed/RAM/indirect frontier，不声称全局 producer 不存在；
- 决策固定为 `lifecycle_closed=false`、`promotion_eligible=false`、
  `bytes_promoted=0`、`coverage_action=keep_unknown`。

接手者不得继续原计划 Task 2（全 state writer/inheritance）或 Task 3（抽象索引），
除非先提供能失败关闭 `0x0808F654` producer 分母的新证据。当前 coverage/proof 哈希
和 170,484 unknown bytes 都没有因该 gate 改变。可立即转向其他可闭合候选；优先检查
本 gate 已冻结的通用 task scheduler 精确 code/literal 窗口能否作为独立小包，而不是
再次追逐 2,688-byte 表假设。

成本纪律：不要守卫外运行完整 proof 单测；其中
`test_current_repository_does_not_overclaim_completion` 会隐式重建完整 coverage。只改静态
proof 绑定时先跑定向静态测试，最终用一次受守卫 formal audit 验收。每次新重型里程碑
前仍需重新检查 Goal、`memory_pressure` 与 `build/experiments/heavy.lock`。Goal 当前为
active；Goal API 仍不返回套餐余额百分比，所以 5% 阈值不可验证，不能声称余额充足。

## 12. 2026-08-27 task scheduler core R4 正式接手点

第 11.1 节的 lifecycle `REJECT / 0 bytes` 仍有效，但它建议转向的独立 scheduler
code/literal 小包已经完成，不得重复生成。该里程碑当时的历史状态是：

- classified：6,121,280 / 6,291,456（97.29512532552084%）；
- unknown：170,176（2.704874674479167%）；
- claims：14,466；segments：16,577；
- coverage SHA-256：
  `5c3c9bcaa90a4d55a2de5ef37effbd9947502aff75f01b73738b90aa704b0d9f`；
- coverage auditor SHA-256：
  `491de8204291f0e41cc4aadb23fbacc54e76cd2435cf52b4274f0fd9b3c32973`；
- proof spec SHA-256：
  `6fd1fc01e7e52d44510ba66f7d83c5ef64f2d07b27a30554047e87929db955e5`。

canonical artifact 为 `artifacts/rom-task-scheduler-core-v1/`。固定身份如下：

- manifest：`88ef48526ed1bd096a8ece9a58aa4f5770f207084634a125f04dc99561c7d58c`；
- payload：`298dc0cf30765e0afe33487f92cce231bd76d4056719f825c1c9cef98d12a59d`；
- packed binary：`2cdbf5ee8ee1f24e9d5590363f05cf177c21821209d8b735666b4844c829842f`；
- exporter：`c8b5ba4f1153ba3c04dced031ea545149c91d7dc9db9dc260d82d8f53484eea2`；
- independent verifier：
  `90133f94b749dbd3d2d08404ac3be5a7a275f261076c82c8c01312271760d9f4`；
- 定向测试：`2880cf89d6bf82928466543cb78b7052004797e890d7863d5a5eeaa6fe90f39c`。

R4 精确晋升 264 code bytes / 4 claims 与 44 consumed-literal bytes / 3 claims，
union 为 308 bytes。verifier 重建 116 instructions、33 blocks、33 internal edges、
5 external edges、4 external targets、1 frontier、12 returns。138 个已有 owner 字节
仅保留 provenance，三个两字节 gap 继续 unknown。不得把 R4 扩大解释为动态 callback
目标或生命周期、自然运行时可达、全局 caller/code/indirect 分母、scheduler 业务语义、
编辑/重定位安全或 allocatable space。

被 R4 取代的 R3 official copy 已先归档到
`build/experiments/archive/rom-task-scheduler-core-superseded-official/2026-08/sorted-coverage-predecessor-r3-20260827.tar.gz`
（tar SHA-256 `f39301357c76475634c7873c2cee25a01561d42895914859a7fec8d27880a146`）。
归档内 R3 manifest/payload/binary SHA-256 分别为
`fd2fb66d2cf1a18976ce2a5cebdfa086cbec86eee318866d1e2d290289ae3cfe`、
`44bade693dfce91c579e6d03dc45d7146f52ee2bf111ad4efd251a800d88c1cc`、
`2cdbf5ee8ee1f24e9d5590363f05cf177c21821209d8b735666b4844c829842f`。
不要恢复该 R3 copy；它只用于审计排序前的 coverage receipt 历史。

正式审计收据位于
`build/experiments/active/rom-task-scheduler-core-proof/codex-r1-20260827/`：

- report SHA-256：
  `d975366d63c35c6a62f4e41d9199014828e689273d2d882f43188df519477c9e`；
- guard SHA-256：
  `e2ae0a75f524e70634b1a318d719e26c6591b4d789d995fb2bb839dd6d34ddc3`；
- 77/77 executed structured contracts 均 `exit_code=0`、`contract_ok=true`；
- ROM byte gate 为 67/67，bad=0；
- 2,891.251353 秒，峰值 RSS 646.03125 MiB，非 degraded；
- 正确全局状态仍为 `complete=false`、`claim_status=incomplete`、175 blockers。

该处旧 318-byte/90-byte DirectSound 候选已被下一节的实际 344-byte 合同取代。
不要恢复旧包络，也不要把 R4 coverage 当成当前 coverage。

## 13. 2026-08-27 DirectSound pitch lookup 344B 正式接手点

该里程碑当时的历史 coverage 快照是：

- classified：6,121,624 / 6,291,456（97.30059305826823%）；
- unknown：169,832（2.6994069417317707%）；
- claims：14,471；segments：16,582；
- coverage SHA-256：
  `922e06e9b195a31ae6a8ab8c03cb06159aee7218bc4268ac56e22c729b740de6`；
- coverage auditor SHA-256：
  `eb98accbd486377e4d5cf00f2708f7fff75b1b22319ed4dc1d7c24b7abb582d2`；
- proof spec SHA-256：
  `cf242a73211f4cda07a70c6c3bc0f59d8f5a9c995334d9fecd6bf6b808df2c0a`。

canonical artifact 为 `artifacts/rom-directsound-pitch-lookup-v1/`：

- manifest：`61f58bd4309d3b63389bdd09ddd62281dee6fe6ce91bcce0c351ce703012805d`；
- payload：`ea54c37199704e58f4fcfb0c7dccf3227a23c6363692a4f238ebd807a8003d85`；
- packed binary：`cdf62999570f66a283667ed85f535da4e04f8cbf5ea8a33ef66d1bee8ab0e850`；
- exporter：`57cdbc859f70c483a78ef6226a47dfc528927096ce88a5fbb6202c3780eb845e`；
- independent verifier：
  `d4947c8e3081374122b2e7fcd78be3caf3586e892a557965c19e2054986d8250`；
- exporter / verifier tests：
  `562cbecec47e0b35f80d48f1bc26c28c92e13c119e99b703bdd9d07c45f34177` /
  `a3afe0faf31a02c11787d079720ed7c36c1613fbc104bfc889865e6005eddcc9`。

五个 primary range 精确为：

1. `[0x099D7C,0x099D8C)`：16-byte mixed Thumb/ARM high32 helper；
2. `[0x09A998,0x09A9F4)`：92-byte closed Thumb consumer；
3. `[0x09A9F4,0x09A9FC)`：8-byte consumed pointer literals；
4. `[0x4645C4,0x464678)`：180-byte u8 scale descriptors；
5. `[0x464678,0x4646A8)`：48-byte、12×u32 frequency table。

consumer 为 44 instructions / 5 blocks / 0 frontier，helper 为 5 instructions /
2 blocks / 0 frontier。全 ROM target-limited raw Thumb BL 分母有两个 producer，但
producer bytes/source membership 仅作 provenance，仍保持 unknown。range vector SHA-256
为 `ac877e8eec80edbdab3d1b6f3991fc8a93dfc497a66c298dc9ee0c29034431bd`。
不得外推自然运行时、全局 caller/code/indirect 或 computed/RAM consumer 分母、播放
行为、编辑、写回、重定位或 free/allocatable space。

正式审计收据位于
`build/experiments/active/rom-directsound-pitch-lookup/codex-r1-20260827/`：

- report / guard SHA-256：
  `9ff9072dc1e501bd6bef9f792f6a318640ea9b8594719effa514288595d4714e` /
  `eadf80d080f795495304028e9ee8f4074a1ff34e768571e7152b917b278fe133`；
- 78/78 executed structured contracts 均 `exit_code=0`、`contract_ok=true`；
- ROM byte gate 为 68/68、bad=0；
- 2,702.786 秒，峰值 RSS 625.96875 MiB，非 degraded；
- 正确全局状态仍为 `complete=false`、`claim_status=incomplete`、175 blockers。

下一优先工作包是 PSG noise lookup 的最多 220 个 current-unknown 字节：consumer
`[0x09B494,0x09B534)` 160 bytes 与 table `[0x46475C,0x464798)` 60 bytes。
先复用脚本闭合 target-limited producer 分母、raw Thumb CFG/literal 与完整 key→index
0..59 域；合同冻结后可由 Luna max 处理机械 TDD packet，Sol medium 只读 P0/P1 复核，
本体负责独立 verifier、coverage、proof 与 formal。任一 indirect/computed producer、
frontier 或索引域缺口都必须保留 unknown。MPlayMain 旧 414-byte 错误包络（已作废）、SoundMain relocated
source 926 bytes 与 `0x53DFB0..0x53E000` 80-byte object 依次后置。不要重开
`0x596CCC..0x596D5C`、`0xC4..0xC8` 或 `[0x59EAE0,0x59F560)`。

每次重任务前检查 Goal active、内存和同一 heavy lock。Goal API 不提供套餐余额百分比，
所以 5% 阈值仍不可验证；不能虚构余额结论。

## 14. 2026-08-28 PSG frequency lookup 226B 正式接手点

本节取代第 13 节末尾“下一包为 PSG”的旧指令。该里程碑当时的历史 coverage 快照为：

- classified：6,121,850 / 6,291,456（97.3042%）；
- unknown：169,606（2.6958%）；
- claims：14,476；segments：16,589；
- coverage / auditor / proof SHA-256：
  `5432e12ff0aa9bd2722f7e18e169ac0d82d67f6a1afd4601a8d0011e502eba89` /
  `80d182d2fbfefbf68874bb1844e7c3b0e2d6be65f7a4be9d4d9d8e9718bc8d62` /
  `394fe598af8061b578ab9898e1887fba01ad352fd9cb8f4fb18a2f9a8e7afe09`。

canonical artifact 位于 `artifacts/rom-psg-frequency-lookup-v1/`：manifest、payload、
packed binary SHA-256 分别为
`4fffbcc7e252595834adb368d10b3ce8f13323aee18cc518d98e0ff9c519575f`、
`d2631b1a65a2e9fa0114dbd76a4e2c89853e3b2f402a491fdbc466e79dacd733`、
`e625a5fcc208a971a1ec98723f12b863a707fa9dd3ba8442f7f6d86b3099623b`。
五个 promotion range 精确为 `[0x09B494,0x09B4C6)`、
`[0x09B4C8,0x09B4CC)`、`[0x09B4CC,0x09B534)`、
`[0x09B534,0x09B53C)` 与 `[0x46475C,0x464798)`；共 226 bytes。
`[0x09B4C6,0x09B4C8)` 两字节继续 unknown。initializer→逻辑
`SoundInfo+0x30`→`BX r3` 入口链只作 provenance；RAM/computed producer、writer、
indirect caller、自然可达、另两张 target table 的业务语义、播放、编辑、写回、
重定位与 free/allocatable space 均未声明。

DirectSound 历史 verifier 仍绑定其 immutable post-DirectSound receipt；PSG 后的正式
proof 使用 `tools/verify_rom_directsound_pitch_lookup_bundle.py` 复验旧 artifact 与历史
receipt，并显式声明不读取 live coverage。当前所有权由 full coverage auditor 独立
复验；不要重新签旧 DirectSound verifier，否则会形成 DirectSound↔PSG coverage 哈希环。

正式收据位于
`build/experiments/active/rom-psg-frequency-lookup/codex-parent-r1-20260827/`：report /
guard SHA-256 为
`41f25e7c10aa32136f676145b2191a18245d2205ac888a300c8139890b06e670` /
`dcb342bcfaa4b6ad5ddd523fda985e7cef5389427efaadc55f8cf3df0f94edaa`；
79/79 executed structured contracts 全部通过，ROM byte gate 69/69、bad=0，耗时
2,717.188 秒、峰值 RSS 626.12109375 MiB、非 degraded。`complete=false`、175
blockers 是符合 169,606 unknown 与其他未闭合门的正确结果。

下一包只能晋升两段、共 19 bytes：

1. `[0x075C0C,0x075C10)`：唯一 little-endian pointer `0x0853DFB0`；
2. `[0x53DFB0,0x53DFBF)`：五条 3-byte raw record。

必须固定 consumer 的 `index=0..4`、`stride=3`、三个 `ldrb` 字段与全 ROM pointer
occurrence 分母。generic CFG 已拥有的 272 code bytes、四段 literal pool 及右侧
65 bytes 不得晋升；字段只能使用中性 raw 名称，不得误并为 cutscene 第五条记录或
附会业务语义。预期 coverage delta 为 `+19 classified / -19 unknown / +2 claims /
+4 segments`，但所有输出 SHA 与 size 必须在正式 rebuild 后现场取得。

## 15. 2026-08-28 artifact-bound 8B 正式接手点

本节取代第 14 节末尾“下一包为 19 bytes”的旧指令。triplet 已完成；随后四段
artifact-bound align4 gap 也已完成：

1. `[0x061D62,0x061D64)`；
2. `[0x061D7A,0x061D7C)`；
3. `[0x061DEA,0x061DEC)`；
4. `[0x09B4C6,0x09B4C8)`。

四段共 8 bytes、4 条 primary claim。独立 verifier/report SHA-256 为
`befdf8545a0d2763514996935676a1a6384967174dcca119e0da62b71bd4da66` /
`344e3fe2660a48342b5f82bb9d7aeefc28c1f4fe0b99fc3f23bdb2a894f3f662`。
它只从 task-scheduler 与 PSG 已接受 artifact 的固定 owner 边界、raw ROM 和
`gap_end == align4(left_owner_end)` 重建这些字节；不声明 padding、NOP、reserved/
free/allocatable space、自然可达、compiler authorship、相邻 owner 新语义或编辑/
写回/重定位安全。

当前 canonical 状态：

- classified / unknown / claims / segments：
  `6,123,419 / 168,037 / 14,493 / 16,600`（`97.3291% / 2.6709%`）；
- coverage / coverage auditor / proof spec SHA-256：
  `31cf4a9c14666345482cad325433814e7fe26d458327c3bc5d9a13e680616563` /
  `7cd79b584b8ae43706c97df4c3604d4fcf344288c95052bda7072e7e0ff9a3d4` /
  `c8e18ab374b96962d4b1a65d44bd4a0de85dece8d71e6906f39e0143d9a84604`；
- 65 项非 heavy proof 单测全部通过；
- formal report / guard SHA-256：
  `d2e265e4c7ddc3148eeaa877772246a4944b53f1bfc75c8c97fc99ca5826f8b1` /
  `edf30aa3feb13ba7500973c2ecad10a2f7f2c3bfb9c1f47d6f3d4d6d5c48c084`；
- 84/84 structured contracts 全部 `exit_code=0`、`contract_ok=true`，ROM byte gate
  74/74、bad=0；2,866.934973 秒、峰值 RSS 597.23046875 MiB、非 degraded；
- 正确全局状态仍为 `complete=false`、`claim_status=incomplete`、175 blockers。

MPlayMain 与 SoundMain 已完成，证据见 `notes/rom-mplaymain-scheduler-20260828.md` 和
`notes/rom-soundmain-relocated-cfg-20260828.md`。下一包冻结为 518-byte
`rom-m4a-initializer-chain-v1`；其六段范围、producer denominator、CFG/literal 分母和
非声明边界见本文第 17 节。

## 16. 2026-08-28 MPlayMain 612B 正式接手点

### 16.1 已完成，禁止重做

- artifact：`artifacts/rom-mplaymain-scheduler-v1/`；
- manifest / payload / binary SHA-256：
  `43399803451c393722522c9d2a363736541c34c37dd03d3cb2c1e292ed0b8f5d` /
  `31bc026a8c83b3bf4af06746de2990a658bb86954a5aae31c45d63d68cf44f78` /
  `8ca6a2f02cd27d46b9d0e9dbae2491672f23702ee2230eb73fc460759ef14955`；
- code `[0x09A42C,0x09A684)` 600B；preowned veneer
  `[0x09A684,0x09A686)` 2B；keep-unknown `[0x09A686,0x09A688)` 2B；consumed
  literals `[0x09A688,0x09A694)` 12B；净晋升 612B；
- CFG：289 instructions / 81 blocks / 117 internal edges / 12 external edges /
  7 external targets / 4 literal refs / 3 literal words / 1 frontier / 1 return；
- range-vector SHA-256：
  `a8e11002ba5439c3d758e03faa1850a686e749cbe3230496f871329283300b4d`；
- core exporter / independent verifier / immutable bundle verifier SHA-256：
  `366c4e41db80c797bd01f36477a67243ac08f4d20d71e596c1332f273deed18d` /
  `c064fc6a576a518cbd825630babc40d1c2dab2d369846078c3950b68748a2c2a` /
  `caa5e042401ed06f1f7e9978e10c5e487c643e909c50a274b75aed32ce557c06`。

旧 `[0x09A42C,0x09A5CA)` 414B 包络因可达分支逃逸而无效。不要修改 immutable
wrapper 中的历史 coverage SHA；`live_coverage_verified=false` 是设计边界，当前 owner
由 full coverage auditor 复验。完整说明见
`notes/rom-mplaymain-scheduler-20260828.md`。

### 16.2 SoundMain 冻结合同（已完成，保留作复现输入）

权威输入：

- ROM source envelope `[0x099E10,0x09A1AE)`：926B，接入前完整 unknown，
  SHA-256 `1099dd6414c3f8a052a9e0e19c7ef9497661c4c15b4e8d1dd056f791bb115df8`；
- 运行地址 root：`0x030077C8`；所有 PC-relative branch、ADR 与 literal 必须按该
  IWRAM 地址解码，再映回 ROM；
- `m4aSoundInit` `[0x09AA3C,0x09AA90)` 与 literals `[0x09AA90,0x09AAB4)`；
  `0x09AA3E` 取 source `0x08099E11` 并清 Thumb bit，destination `0x030077C8`，
  control `0x04000100`，`BL 0x09C0E0`→`SVC 0x0B`；实际 copy window 为
  `[0x099E10,0x09A210)` 1,024B；
- 既有 boot owner：stub code `[0x099D8C,0x099DF6)`、literal
  `[0x099DF8,0x099E10)`、return veneer `[0x09A1AE,0x09A1B0)`。

必须由两套独立 decoder 复核的候选分区：

| 类型 | ROM 范围 | 字节 |
| --- | --- | ---: |
| code | `[0x099E10,0x099E1A)` | 10 |
| gap | `[0x099E1A,0x099E1C)` | 2 |
| code | `[0x099E1C,0x099EC2)` | 166 |
| gap | `[0x099EC2,0x099EC4)` | 2 |
| internal literal | `[0x099EC4,0x099EC8)` | 4 |
| code | `[0x099EC8,0x099FA6)` | 222 |
| gap | `[0x099FA6,0x099FA8)` | 2 |
| code | `[0x099FA8,0x09A1AE)` | 518 |
| preowned return | `[0x09A1AE,0x09A1B0)` | 2 |
| external consumed literal | `[0x09A1B0,0x09A1B4)` | 4 |

候选统计为 315 instructions、916 code bytes、8 literal bytes、三个 2B gap、0 unresolved
target frontier。四次模式切换必须逐项冻结：

1. `0x099E16 ADR`→`0x099E18 BX`→ARM `0x099E1C`；
2. `0x099E68 ADD pc`→`0x099E6C BX`→Thumb `0x099E9E`；
3. `0x099FA2 ADR`→`0x099FA4 BX`→ARM `0x099FA8`；
4. `0x09A188 ADD pc`→`0x09A18C BX`→Thumb `0x09A190`。

执行顺序不得颠倒：

1. 先写轻量 preflight tests，固定 CpuSet source/destination/count 与 ROM↔IWRAM 映射；
2. 用可复现脚本闭合全 ROM target-limited direct-BL/Thumb-pointer producer denominator；
3. 两套 decoder 对指令、block/edge、四次模式切换、literal、return owner 达成一致；
4. 决定 920B 保守 promotion，或把三个 gap 以独立 artifact-bound align4 claims 加入
   930B promotion；gap 不能并入 code，也不能命名为 padding/NOP/free；
5. 合同完全冻结后，才可考虑 Luna max 承担单一小型公开合同包；本体仍负责
   coverage/proof/formal。

出现 producer 分母不完整、decoder 不一致、模式切换或 return owner 不闭合时，写
`blocker.md` 并停止；不得靠扩大 1,024B copy window、忽略 gap 或猜测运行时语义绕过。

实际结果采用 924B core promotion 加 6B 独立 gap promotion，共 930B；证据、哈希和
formal 收据见 `notes/rom-soundmain-relocated-cfg-20260828.md`。本节的“执行顺序”只供
复现实验，不再是待办。

## 17. 2026-08-29 已完成：m4a initializer chain 518B

### 17.1 任务模式与执行边界

复用 AGENTS 已登记的“固定 initializer/callback provenance + target-limited bounded
Thumb CFG + consumed literals”模式。合同冻结时曾判定适合 Luna max 的单一短包；实际
产物由本体复核，并由本体完成 coverage/proof/formal。不得修改任何既有 accepted
exporter/verifier 或历史 receipt。

实际 artifact/schema：`rom-m4a-initializer-chain-v1`。只允许六条 primary claim：

| 类型 | ROM 范围 | 字节 | SHA-256 |
| --- | --- | ---: | --- |
| Thumb code | `[0x09AA3C,0x09AA90)` | 84 | `c782ff96fc49708def45c12c5ba3c4170449390bf0ea4aa389561e09f359013b` |
| consumed literals | `[0x09AA90,0x09AAB4)` | 36 | `7f208987daf90cface78da36557a0773839b56b2bf1fe174358f1a56cfebbc6f` |
| Thumb code | `[0x09ACF8,0x09ADC0)` | 200 | `b2c254e31eb7da12ddfd1a22a1fecb176659d1cc344e70cb8cad311230c84c9a` |
| consumed literals | `[0x09ADC0,0x09AE10)` | 80 | `5b0dd3fbbfc9f8c964f9c0f806548ccd9b72059ee6b67188c9432ac2342652b0` |
| Thumb code | `[0x09B17C,0x09B1E6)` | 106 | `b89251f7ae5e7e69702a82f4777b07d2a5ed1747b3aa8cfb8ea90bbfe0c7c733` |
| consumed literals | `[0x09B1E8,0x09B1F4)` | 12 | `93fd80ddfc01693c7d0a9011380fb8fc6fe9c830809470f90cdacb2979bf0c46` |

总计 390 code bytes、128 literal bytes、518 bytes；packed/range-vector SHA-256：

- `f5c0a94ac06bf6750edc038e0db95fc5d4e96c321129e57a11abd461aa678ea7`；
- `8bcba07694e7375d59dddeb3cb12eeb4903e61147c91723482d61d06a47dbd72`。

接入前 baseline 已冻结为 coverage SHA-256
`31cf4a9c14666345482cad325433814e7fe26d458327c3bc5d9a13e680616563`，
classified/unknown/claims/segments 为 6,123,419 / 168,037 / 14,493 / 16,600。
六段均 whole-range unknown、零 primary overlap。合同冻结时预计净接入后为
6,123,937 / 167,519 / 14,499 / 16,607；实际重新计算得到
6,123,937 / 167,519 / 14,499 / 16,608。原 segment 预测少 1，属于预估误差；任何接手者
必须以 canonical coverage 的实际重建结果为准，不能抄预计值。

### 17.2 CFG、literal 与 producer 分母

- 总 CFG：188 instructions、25 blocks、31 intra-function edges、7 direct calls、
  3 个结构化 `BX r0` return、0 unresolved frontier；全部为 Thumb；
- 两条 included-root call：`0x09AA56→0x09ACF8`、`0x09AA76→0x09B17C`；
- 五条 opaque call edge 的 target 白名单：`0x09C0E0`（两次）、`0x09AE3C`、
  `0x09AFD8`、`0x09AE28`；不得追随或声明 target 内容语义；
- 33 个 PC-relative LDR ref、32 个唯一 literal word，必须恰好覆盖 128-byte pools；
- 全 ROM target-limited raw producer denominator：
  - root `0x09AA3C`：唯一 Thumb BL `[0x061E28]`；
  - root `0x09ACF8`：唯一 Thumb BL `[0x09AA56]`；
  - root `0x09B17C`：唯一 Thumb BL `[0x09AA76]`；
  - 三个 root 的 Thumb B/Bcond、ARM B/BL、u32 entry、u32 Thumb-pointer forms 均为空。

P0 边界：`[0x061E28,0x061E2C)` 自身仍 unknown，只允许作为 unpromoted raw-match
provenance。必须显式输出 `producer_source_instruction_membership_proven=false` 和
`producer_bytes_promoted=false`；不声明 caller CFG、computed/indirect producer 或
自然可达。如果实现政策要求 producer 必须同步晋升，则整个 518B packet 失败关闭，
不得擅自扩大为 522B。

`[0x09B1E6,0x09B1E8)` 为 `0000`，位于 MPlayOpen return 与 align4 literal pool
之间，但无指令可达、无 literal consumer，必须保持 unknown；不得称为 NOP、padding
或 free space。只有六段左右 owner 接入后，才可另开 artifact-bound gap 合同。

### 17.3 强制 RED 与停止条件

至少覆盖：缺 exporter/verifier 的初始 RED；ROM/coverage/upstream receipt 身份；六段
whole-range unknown；producer-form 精确分母；CFG/opaque-call/return/frontier/literal
分母；每段单字节 mutation；重复 raw producer；branch/literal escape；pool hole；
return/stack epilogue 漂移；upstream receipt 漂移；partial owner；误纳 2-byte gap。
独立 verifier 必须使用另一套 raw decoder，不能导入 exporter 结果充当证明。

任一 producer 分母、CFG 目标、literal pool、upstream identity 或 baseline coverage
不一致时写 `blocker.md` 并停止；不得修改测试、旧 artifact/receipt 或扩大范围绕过。

### 17.4 验收结果与不可变身份

- 正式 artifact manifest / payload SHA-256：
  `9b9b9f2f49a1ee8224703ca47b73dc608d75ba83d2be44564e24873c44237c9c` /
  `7f019b01e800a3dd769463cbea907049429b1cad416dc17ed8719a561837babd`；
- exporter / verifier SHA-256：
  `4e0b8743247d9098a9d72667f4b2499abee1c71c45cd5a704feaa54f17a4ced9` /
  `5cd9ccf232ebb10c69e89962e9861add7675dfb935c6e6a293b16049fd6cec31`；
- coverage 接入前副本保存在
  `artifacts/rom-m4a-initializer-chain-precoverage-v1/`；接入后 canonical coverage
  SHA-256 为
  `ab315087593f23bfbcc96c66ac99b8bfd002e5c29cd462088dda343139f9ac27`；
- proof spec SHA-256 为
  `fcbd2cfb0b930853e82ce171f05d5f16b7019601ac4152e8174b5b6733057977`；
- 67 项静态 proof 测试受守卫通过，日志 SHA-256 为
  `6b3620818770f2ff9c4c9d1f49afdde9ad8cb52bb35c5884a3875aa97b5dd66f`；
- 正式报告位于
  `build/experiments/active/m4a-initializer-chain-proof/codex-formal-r1-20260828/formal-report.json`，
  report / guard SHA-256 为
  `8f6761d5f19cb9142caf5338971c4b1712aebf32f6f9cb08d98196b3d4d84c3e` /
  `172d4a028aba3bfef2ca9ce9eeef9da8c07bbcf191e3fbe9424774a3a3e03628`；
  85 次结构化 verifier 全部 `exit_code=0`、`contract_ok=true`。

本里程碑已完成，禁止再次导出、覆盖 artifact 或重跑 formal 来“确认”。如需复验，优先
运行独立 verifier 与定向测试；只有 manifest、工具或 proof 身份发生授权变更后，才允许
创建新的唯一 run ID。

## 18. 2026-08-29 已完成：MP2K note allocator 562B

### 18.1 已接受范围与结构分母

`rom-mp2k-note-allocator-v1` 只分类四条 primary range：

| 类别 | ROM 范围 | 字节 | SHA-256 |
| --- | --- | ---: | --- |
| bounded Thumb code | `[0x09A6D8,0x09A708)` | 48 | `04988bf8e911a12b477d9aafa24342b68e83960a06796e555869cc67b24bd4d2` |
| bounded Thumb code | `[0x09A708,0x09A8FE)` | 502 | `4c78dfb62e2d92b0b0ed96c8d05e86d3d2867a1bb2a76c82818a672f380eee2e` |
| consumed literals | `[0x09A900,0x09A908)` | 8 | `aea41d042f130b46329f8b5a5fdb976816ec280b367dc424f28bc624072867c1` |
| initializer-consumed entry pointer | `[0x09AF24,0x09AF28)` | 4 | `ee8951cbf1e4a1f69fce481a4537a84678e2615bc7e3f175ff69a97044ab7016` |

总计 562 bytes；packed SHA-256 为
`3c3a1dab618964db40570b65c28ae08500a30392c65c25d870291ee5abb1587c`，union
range-vector SHA-256 为
`bd9139f26305fea7813e7daf944d6a6e131861b31c3c98065b5e7d13bf65c88b`。
独立 worklist 固定 269 instructions、66 blocks、99 internal edges、5 external edges、
2 returns、0 frontier；entry-pointer consumer 接受的固定命令域为 0..48，共 49 个值。

四段相邻范围合计 68 bytes 必须保持 unknown：`[0x09A6D2,0x09A6D8)` 6 bytes、
`[0x09A8FE,0x09A900)` 2 bytes、`[0x09AEF4,0x09AF24)` 48 bytes、
`[0x09AF28,0x09AF34)` 12 bytes。不得把自然运行时、全局 caller/code/indirect/computed
producer、RAM writer、literal target 业务语义、音频行为、编辑、写回、重定位或
free/allocatable space 扩张进本合同。

### 18.2 Artifact、TDD、coverage 与 formal 收据

- canonical manifest / payload / binary SHA-256：
  `a2f61cb3596c8e48294ba07c710a2681bbe8ca8173c6d9288beccd5dd3e1cf8a` /
  `a4ccf706d2c8db658b6fa402d13155c73d15e84c197f9da4e8975759a14b0fa6` /
  `3c3a1dab618964db40570b65c28ae08500a30392c65c25d870291ee5abb1587c`；
- exporter / independent verifier SHA-256：
  `a54f665a7f713f5754cc25a1bc2e2c5761179460a64f44e2cd276a731a9c235a` /
  `177d1fb694b01f5938d6169438cd454db0ff7a1e826cf101b32630ffc51d9716`；
- exporter / verifier test SHA-256：
  `0af69ec928c352f41c5e2daf0db1870f2980333d9767f2e207acb22126af64ac` /
  `2e30e8af036a1157a9e0edaf541ee1724aebf5c23b784fa5a675daf5d47e76c6`；
- 24 项定向测试全部通过，日志 / guard SHA-256：
  `5cc228099e0ec363173f1ac1e543e618aa5b1757ebd23bae2ad19a6518273f61` /
  `dc2779abf08db55b0ddff95ecd5f73166585670049a8e1e3f6e90a2c0ff96584`；
- coverage 接入后 classified / unknown / claims / segments 为
  6,124,499 / 166,957 / 14,503 / 16,614，coverage SHA-256 为
  `3926d1cd6e09c8b45b85cb33d0b2f77d83578ec71c17d61fa1282d863f220735`；
- formal proof report / guard SHA-256：
  `46b4b0c9b80b7ef2d8eaff9fb0572370c315d47baa05290d4fb2da327a95e7ce` /
  `7a69b38343c8a1b68392368cd0b130d6817b888fa3b3c90cf445a7d05e54adaa`；
  86/86 实际结构化 verifier 全部 `exit_code=0`、`contract_ok=true`。

首轮 coverage rebuild 因 15 分钟 idle timeout 被守卫停止，未改 canonical coverage；
第二轮仅调大受守卫 idle 上限后首次成功，属于保存完好的基础设施浪费证据，禁止删除或
把首轮误报成 ROM/逻辑 blocker。完整说明见
`notes/rom-mp2k-note-allocator-20260829.md`。

## 19. 2026-08-29 已完成：MP2K 18-entry dispatcher 102B

### 19.1 已接受范围与不可扩张边界

canonical artifact 只接受四段原 current-unknown additive delta：

- `[0x09BCB4,0x09BCE2)`：46-byte root code；
- `[0x09BD24,0x09BD30)`：12-byte jump-table entries 15..17；
- `[0x09BDC4,0x09BDEC)`：40-byte handler code；
- `[0x09BDFC,0x09BE00)`：4-byte consumed literal。

`[0x09BCE2,0x09BCE4)` 与 `[0x09BDFA,0x09BDFC)` 两个 2-byte gap 保持 unknown。
完整 18-entry 表为 `[0x09BCE8,0x09BD30)`；其 literal 与前 15 项已有 accepted owner，
只能作 provenance。历史 `similar-table-candidate-027` 的整体
`rejected/crosses_canonical_table_boundary` 状态不得修改。

### 19.2 Artifact、coverage 与 formal 收据

canonical manifest / payload / binary SHA-256 分别为：

- `212c3849eb8ead7fd01c74f8ed8a1ae85b4f2324d966fa2234320a6b78882b48`；
- `3ddac8d6c690af4850d74f7aeeee2a424f32c4108a7ebebd26c51f280672b23c`；
- `83f220623fff3f5effb8bf6cd21b7e7ce8d543ab660d7fa721b8632bd26b3bd5`。

完整 bounded CFG 固定 129 instructions / 260 code bytes / 36 blocks / 65 internal
edges / 1 external edge / 1 return / 0 frontier，并解析 18 条 dispatch edge。接入后
classified / unknown / claims / segments 为
6,124,601 / 166,855 / 14,507 / 16,617；coverage SHA-256 为
`22f8f88ca0929468289b749cb94b4aaa4c47d7a53fa68fe10cb93c9a01816839`。

正式 report / guard SHA-256 为：

- `3321709fa8440c8857d895b1cb467a3959989be0cc639abfe439bdb91e43ddc0`；
- `b6e177ccff24a0cb19ad6e500968c4905bae3a0758abd466a2174cfd4bf8d036`。

87/87 实际结构化 contract 全部 `exit_code=0`、`contract_ok=true`；ROM byte gate
77/77、bad=0。报告保持 `complete=false`、175 blockers。完整说明见
`notes/rom-mp2k-dispatcher-20260829.md`。

### 19.3 已完成：CGB helper + CgbSound

- 已从接入前 coverage 生成一份共享 immutable precoverage；
- `[0x09B53C,0x09B5F4)` 拆为两个根，冻结 164-byte code、16-byte consumed
  literals，两个 2-byte align4 gap 另交独立 gap verifier；
- `[0x09B5F4,0x09BA3E)` 冻结 1,008-byte code、76-byte consumed literals，三个
  调用 helper 的 edge 只作 opaque external stop；七个 2-byte align4 gap 另验；
- 两个 artifact 分别接受后，已把 9 个 gap 与其他 4 个 artifact-bound gap 合并为
  13 段、26-byte 独立 verifier；coverage rebuild、proof 更新和 formal audit 已通过；
- 不声明 helper/CgbSound 的自然运行时可达性、动态 RAM/callback、完整音频行为、
  全局 caller/producer、编辑、写回、重定位或 allocatable space。

接入后 classified / unknown / claims / segments 为
6,125,883 / 165,573 / 14,544 / 16,654；coverage SHA-256 为
`05215215595f0614f0461fa7502703ca62ccaa07159ddb27810f9903a31ef6d6`。
formal report / guard SHA-256 为
`613cee1f8c72882aebe6ffaf617fc2fa1ea556ca9235f9f78607132dd189a567` /
`7515d1e4c9a47f6508209a17747992e4219619075ada9f6a8766bb9045315e7a`；
88/88 实际结构化 verifier 全部通过，ROM byte gate 78/78、bad=0。

## 20. 2026-08-29 已完成：CFG proven-roots v12 500B

- 固定目标 `0x08064478` 的唯一已证 producer 是 file `0x061416` / GBA
  `0x08061416`，不是 `0x080614D0`；旧文档中的 `0x080614D0 -> 0x08064478`
  是地址抄写错误，已纠正。file `0x0614D0` 属于下一包 V13 的 producer。
- V12 只晋升四段 372-byte bounded Thumb code 与四段 128-byte consumed
  literals，共 8 claims / 500 bytes；`[0x0644C2,0x0644C4)` 与
  `[0x06450A,0x06450C)` 两个 2-byte hole 保持 unknown。
- canonical manifest / payload SHA-256：
  `bf88e08f4eed6b53e1debef709c2ef13fb891c11e9c172485e494eef57954677` /
  `fd9df8f3d93de1df5aa7e725040f27f854d08e8203d6cada51db829ddcd9bcee`。
- immutable wrapper SHA-256：
  `ee1d50f3018b5d78d652eb5ed6d1f7108670669b60e5518b9956df987b60275a`。
- V12 接入后的历史 coverage 为
  6,126,383 / 165,073 / 14,552 / 16,665；当前已被 V13 canonical coverage
  取代，不得用 V12 coverage 覆盖当前文件。
- 历史 formal report / guard SHA-256：
  `961ace784373243954097418880fdbf52419385b2e34f62a136f7920b032306a` /
  `53546d31216f134a9e22cddfb79fb2e01cd9642e494e4429eb0b2ebe4e6ab0eb`；
  89/89 实际结构化 contract 通过，ROM byte gate 79/79。

## 21. 2026-08-30 已完成：CFG proven-roots v13 392B

### 21.1 当前不可变身份

- artifact：`artifacts/rom-cfg-proven-roots-v13/`；
- manifest / payload SHA-256：
  `589dd8e1536b2b6d0cc3997f31c5841204593f64ce491d6c0647ca7230f8e133` /
  `45b83aeb6e91249ebd5adefdb086c438b14c666e79aab780f7072a929343cb5b`；
- legacy / immutable wrapper verifier SHA-256：
  `a687af7750e9a177b47883f1b540d555bd4c666d92865d56e521f85174c869a7` /
  `0fe1b8c1d1aa1a191d8bc7e210db952551e4b54aceeed1c13aecd9db6c12c272`；
- wrapper standalone report SHA-256：
  `1af5b070de422596e403f722d10f765c821c14d95c2d1f7547e1e831fb5ea5e6`；
- canonical coverage SHA-256：
  `e8787f8e200e84b2966c6f6b8c70ea164a0f90d81348d88e5daa614ea3cb8004`；
- proof spec / coverage auditor / formal auditor SHA-256：
  `1818d80f92cf3cf28e4f473d954cd1e900e8b42bb3cf430052651c7c27594e1a` /
  `56f7ebc073678e79f9ba5328be508e98ee4c33095f20120976baaa0718353d79` /
  `1562de7b02fc781b79ede13a29a03137a02082ff2aa59b3ec212b90ae797104b`。

### 21.2 范围、frontier 与正式验收

- 固定目标 `0x080651F8` 的全 ROM target-limited 直接 producer 分母只有 file
  `0x0614D0` / GBA `0x080614D0` 一条已证 source Thumb BL，raw `03 f0 92 fe`。
- target 为 153 instructions / 25 blocks / 312 code bytes，另实际消费 80 literal
  bytes；coverage 只晋升 6 ranges / 392 bytes。
- `[0x0652DE,0x0652E0)` 与 `[0x06536A,0x06536C)` 两个 2-byte hole
  保持 unknown；`0x065368 bx r0` 是唯一 unresolved `indirect_pc_target`，不得称为
  structured return。
- canonical classified / unknown / claims / segments 为
  6,126,775 / 164,681 / 14,558 / 16,673（97.3825% / 2.6175%）。
- formal report / guard SHA-256：
  `6bced154df1d4ca3940f597f64ef36bb5ebd8c3f9d995f62fce34ad92b8793c2` /
  `23893d0b4996fac334cc4b93596e1e3a28ee5cc7302636c5abd5b8b34037d369`。
- 90 个唯一结构化 command 全部 `exit_code=0`、`contract_ok=true`；ROM byte gate
  80/80、bank contract 10/10。报告仍为 `complete=false`、175 blockers。
- proof 全模块 72/72 通过；完整日志、红绿哈希、浪费记录和非声明项见
  `notes/rom-cfg-proven-roots-v13-20260830.md`。

本里程碑已经完成。不要再次导出 V13 artifact、覆盖 current coverage 或重跑 formal
来“确认”；除非其 manifest、工具或 proof 身份经授权改变，否则只运行定向只读 verifier。

## 22. 2026-08-30 已完成：CFG proven-roots v14 160B

### 22.1 冻结范围与身份

| target root | 已证 producer file offsets | code | consumed literals | unresolved frontier |
| --- | --- | --- | --- | --- |
| `0x0624C0` | `0x064594`, `0x065234` | `[0x0624C0,0x062500)` 64B | `[0x062500,0x062510)` 16B | `0x0624FE bx r0` |
| `0x062510` | `0x0644F2`, `0x06452C`, `0x065258` | `[0x062510,0x062548)` 56B | `[0x062548,0x062560)` 24B | `0x062546 bx r0` |

- 五条 producer 均由 V12/V13 accepted node、ROM raw bytes、当前 coverage owner 与
  target-limited 全 ROM denominator 共同绑定；两个 target 合计 60 instructions、
  10 blocks、120 code bytes、40 literal bytes、4 ranges、0 hole。
- manifest / payload SHA-256：
  `666772f43529a5578414c5b749e16ea8733a755a0a818e86cea81bd86d57091d` /
  `d99c0cdc367637b62754b941926e22d09bef08f9a3e89817fbf42dafc0a7edff`。
- legacy / immutable bundle verifier SHA-256：
  `f6125cf1270e67da57ac049c881a1d4033208664816f05f533b39e8152da8ea7` /
  `11464a0581da7e12a098df0c40a505fda3a898609c8793e2f1f5edd9e9169889`。
- canonical coverage SHA-256：
  `2592ce481515af301ef5ce4078d3e9101793bf790f1bc90a6d33d5a06c207317`；
  classified / unknown / claims / segments 为
  6,126,935 / 164,521 / 14,562 / 16,677（97.385009% / 2.614991%）。

### 22.2 综合 CFG 汇总修正与正式验收

旧 coverage auditor 的手写 allowlist 漏计多种已接受 ARM、mixed-ISA、Thumb code 与
producer kind，因此 V14 formal-r1 虽通过当时合同，但不是后续汇总权威。TDD 修正后，
冻结 registry 包含 32 个代码 kind、2 个 producer kind，并对 3 个 code-like 非 CFG
kind 作哈希绑定排除；任何未来带 `code`、`instruction` 或 `producer` token 的新 primary
kind 未登记都会失败关闭。V14 当时汇总为 ARM 956、Thumb 148,380、producer 32，合计
149,368 promoted bytes、3,829 primary claims；registry SHA-256 为
`d57f6b22f597eb6cfcad6a746122870917fbc24b0e70a885a432a57c729a227f`。

- proof spec SHA-256：
  `b78b8b2fd112cd07cc4b096443f3aff246b2df080be4c7acf54f0c677440ca02`；
- formal-r2 report / guard SHA-256：
  `f9c2a1014b62dc7449db7f35965a1d42db01eb4972e43c81d961688e0befa786` /
  `3786c8d4e51c8070a021064433535429dc22efe5dcfb84ae4e156fe1039d7fa4`；
- 91/91 唯一结构化 contract 全部 `exit_code=0`、`contract_ok=true`；ROM byte gate
  81/81、bank contract 10/10、bad=0；耗时 3,438.593624 秒，峰值 RSS 660.1875 MiB，
  非 degraded。报告正确保持 `complete=false`、175 blockers、trust anchor 未验证。

两个 `bx r0` 都是 unresolved indirect-PC frontier，不能按函数形态写成 return。V14
不声明自然运行时可达性、全局 caller/producer/code 分母、全局 indirect/computed/RAM
target 分母、callee ABI 或业务语义、literal 含义或 compiler authorship、相邻字节
padding/free/allocatable、编辑、写回、重定位或 gameplay behavior。接入后 legacy
exporter/verifier 因冻结 precoverage 身份不再匹配而按设计失败关闭；复验当前里程碑应
使用 immutable bundle、canonical coverage 与 formal-r2，而不是重导出 artifact。

## 23. 2026-08-30 已完成：CFG proven-roots v15 450B

### 23.1 冻结结果

| root | 已证 producer | code | consumed literal | preserved hole | frontier |
| --- | --- | ---: | ---: | ---: | ---: |
| `0x0611F4` | `0x06144A` | 108B | 40B | 52B | 1 |
| `0x0618FC` | `0x061456` | 54B | 4B | 330B | 1 |
| `0x08B6F0` | `0x08BBAA` | 170B | 0B | 2B | 1 |
| `0x09A3E0` | `0x0612C8` | 66B | 8B | 2B | 0 |

- 四个 accepted roots 合计 197 instructions、31 blocks、398 code bytes、52 literal
  bytes、10 semantic ranges、7 union ranges、450 promotion bytes、3 unresolved
  indirect-PC frontiers 与 386 preserved unknown hole bytes。
- `0x09C0F4` 因 literal/code overlap 和未绑定 raw Thumb BL 命中被拒绝；其
  `[0x09C0F4,0x09C110)` 范围不进入 coverage。`0x08B644→0x08ACC8` 仍因 source
  不在 V8 accepted worklist 而排除。
- canonical manifest / payload SHA-256：
  `7fb00210d8347df1935d6997afa66183d6cbaa4d7d26208f744256e09f11755f` /
  `5786c04ae36d78957705175dfce38da190bb29682c640c6821bb44ec4c321cd2`。
- legacy / immutable bundle verifier SHA-256：
  `163f04429f5bdd117f540cdf2421c483ff110e6eab1042403fe29ab7736dc167` /
  `7eeb291c75e89caf1873dfd49fb433c462cd421c22a11d996cd98e79e954ca79`。
- canonical coverage SHA-256：
  `c76ac479b6798b856ff839b9f9388f537f912247481ee06ff53ad52c504624c9`；
  classified / unknown / claims / segments 为
  6,127,385 / 164,071 / 14,572 / 16,693（97.392162% / 2.607838%）。综合 CFG
  aggregate 为 ARM 956、Thumb 148,778、producer 32、promoted 149,766 bytes、
  3,835 claims、33 code kinds，registry SHA-256 为
  `10ae3cc720e787630957b7c7bbbbae379ec5f3e542dbabeb871df861915a676b`。

### 23.2 proof 与 formal 验收

- proof spec SHA-256：
  `3c622bc59bf414cd511eeb900bd421bb85122e57c152b065e19349d4a3aa842b`。
- formal-r2 report / guard SHA-256：
  `3002d624f4a5354c4bf0f410aa7923c8377c33e96c263d6df6299ef67deefb63` /
  `b10f03289ab3b941a3bb3d0dd30edc806816dc5a262224ec5137a28e94ada220`。
- 92/92 唯一结构化 contract 全部 `exit_code=0`、`contract_ok=true`；ROM byte gate
  82/82、bank contract 10/10、bad=0；耗时 3,192.960532 秒，峰值 RSS
  677.41796875 MiB，非 degraded。报告保持 `complete=false`、177 blockers。
- formal-r1 不是验收证据：它实际有 coverage auditor 与 V15 bundle 两项失败，根因
  是 formal executor 无条件注入 `PYTHONPATH`，与 V15 `-I -S` bundle 的路径污染
  拒绝合同冲突。新增 RED 精确复现两个边界；最小 GREEN 只在隔离命令和 coverage
  内部 wrapper 子进程清理 `PYTHONPATH/PYTHONHOME/LIBCAPSTONE_PATH`，非隔离命令仍
  保留仓库 `PYTHONPATH`。formal-r2 已同时证明两条修复路径。

V15 不声明自然运行时可达性、全局 caller/producer/code 分母、全局 indirect/
computed/RAM target 分母、callee ABI 或业务语义、literal 含义或 compiler authorship、
相邻字节 padding/free/allocatable、编辑、写回、重定位或 gameplay behavior。除非
canonical identity 或 proof 合同经授权改变，不得重导出 V15 artifact 或再跑 formal
来“确认”。

## 24. 已完成：menu portrait LZ77→palette 对齐间隙 110B

1. 每个里程碑前调用 Goal API；非 `active` 不得写。余额百分比若仍不返回，只记录
   “不可验证”；出现可验证 `<=5%` 时立即停止新写入。
2. 本体独立 preflight 已冻结 52 段、合计 110 bytes 的完整分母（1/2/3-byte 段分别
   16/14/22 段）：每段紧邻一个独立解析的
   LZ77 endpoint 与一个 `menu_portrait_palette_bgr555` 起点、长度 1–3 bytes、右端
   `align4`，且当前 owner 完整为 unknown、ROM 逐字节为零。preflight script/report
   SHA-256 为
   `bad6c078d8c3f8abab4aebf2f5123962bfca2ddeec53aed12c646bb6245ad991` /
   `52e8b35dc934697a7e8e70981cab6d0ade20fe3292ed0857c65ffa1f33cebc56`；range /
   boundary / packed SHA-256 为 `e88d3a42d6e3144919668ade6db9f9caa21e8aab1502d8b3d9c84a148875bbf7` /
   `13ab975a67b42528abeef6075ff1f71b9440a7e53806f4f07f345d2e30900ddb` /
   `f23391587f1c9fc48eabd1e95f4caf16f585ef09941b7bc24f023d228e81ccd5`。
3. 首选复用现有 LZ77 alignment-gap、menu portrait palette artifact 和参数化 TDD
   模式；独立 verifier 必须从 ROM、LZ77 artifact 与 palette artifact 重建完整分母，
   对任一非零、非紧邻、非 align4、partial owner、artifact/hash 漂移或分母增减失败关闭。
4. 冻结合同位于
   `build/experiments/active/menu-portrait-lz77-palette-gap-preflight-20260830/CONTRACT.json`
   （SHA-256 `168033362a4567b508d8fdbd43ef26dd7ea7a3c2445082c207e204c52a706a7e`）。该包属于公开
   边界闭合的小型重复包，已由 Luna max 单 writer 实现 verifier/tests；父代理随后补强
   110-byte 单字节变异覆盖并负责 coverage、proof 与 formal 验收。
5. 只能声明“两侧 artifact-bound 的零对齐字节”，不能称为 padding、reserved、free、
   allocatable、自然可达、全局不可达、可编辑或可重定位空间。
6. 保留全部现有工作树和 experiment，不 reset、checkout、clean、覆盖历史 run，不
   commit、不 push。所有重任务继续使用精确 `build/experiments/heavy.lock`，禁止
   `--allow-degraded`。
7. canonical coverage / proof SHA-256：
   `c2798b35f4ac21f170c9a7575cbf10118aad98d58efbebf3d59ca9f599216133` /
   `eaa8b7f2b37feaa9686d83c84f6fd16672e6b6ae3038e0ccf16ece96c4698eb2`；
   standalone verifier SHA-256：
   `9bbf3532a5edde0cbf0f0d5924c037bb7df6873f6b02bd278f7215cd3b1af27d`。
   formal report / guard SHA-256：
   `92b4b471b972bcc789848f78192f8c5162deeeb0ab0c1bce77e818694e88ba3a` /
   `e0985d49922e2473229c8c28c4182013e9497718977e07807a52885e76b2b66e`；
   93/93 实际唯一命令、ROM gate 83/83、bank 10/10、bad=0，耗时
   3,385.228261 秒、峰值 RSS 680.0625 MiB、非降级。报告正确保持
   `complete=false`、177 blockers。

## 25. 已完成：tile-BG LZ77→palette 对齐间隙 165B

1. 每个里程碑前调用 Goal API；非 `active` 不得写。余额百分比若仍不返回，只记录
   “不可验证”；出现可验证 `<=5%` 时立即停止新写入。
2. 接入前 canonical coverage 的 `lz77_resource → unknown → palette_bgr555` 共 93 段 /
   284 bytes。必须排除两个非合同长洞：`[0x13E02D,0x13E070)` 67 bytes 与
   `[0x349E51,0x349E74)` 35 bytes；两者含非零数据，不能称为短零对齐间隙。
3. 剩余 91 段 / 182 bytes 虽都为 1–3-byte 零 align4 gap，但右侧证据异构。本包最终
   只收 `tile_bg_palette_source_range` 的 84 段 / 165 bytes；长度分布为 31×1、
   25×2、28×3。另 4 个 direct-CpuSet-bound、2 个 verified-reuse、1 个旧 direct
   CpuSet gap 必须留给各自消费者包，禁止混入。
4. 冻结标量：range-vector / boundary-vector / packed-bytes SHA-256 分别为
   `684c4ad2fa1256261de50ed01f8a781bde09b7514f4cab0c5ec5dec9a0b472e2` /
   `b96f496cb68ed87905d62c39a148f67b2fef4e10bfa9e2b6b004f2d1644fe448` /
   `2aa1fd6b1e4d7e4352751c0a8b7acb6fd9aa3a3a4c994f52b0a214c6f346277d`。
5. standalone verifier 必须独立绑定并重建：ROM identity；896 条 aligned
   pointer-reachable Type-0x10 LZ77 及每条 endpoint；`tile-assets-bg-v2` 的 79×68
   descriptor table、236 个 palette entries、108 个原始 palette ranges 与 107 个
   合并 claims / 9,984 bytes；84 行完整左右边界向量；逐字节零值、紧邻和右端
   align4。不得从 live coverage 推导候选，否则形成循环证据。
6. 输入身份：LZ77 inventory SHA-256
   `0c4aed52328b0506e8e41afebe5e5c0ef3dccb830cf8af6c092eb1d0566581c5`；tile manifest
   SHA-256 `1df63cf6cf49079115e997c6f0f33c57578e517dbe22dc16c15f64c4d218a749`；
   tile descriptor table `[0x5A320C,0x5A4708)` SHA-256
   `0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73`；
   tile independent verifier SHA-256
   `4273c6d0cada4e7d018a805e5c96fca9654c19aabeff9a1a7b26e5aa8380d57c`。
7. 只允许声明“固定 LZ77 endpoint 与固定 tile-BG palette source 之间的
   artifact-bound 原始零对齐字节”。不得声明 padding、reserved/free/allocatable、
   自然运行时可达、全局不可达、固定消费者已穷尽、最终像素、编辑或重定位安全。
8. 执行顺序已完成：本体先以可复现 preflight 脚本冻结完整公开合同，Luna max 单
   writer 只实现 standalone verifier/tests；父代理随后验收有效 RED、所有 165 个
   单字节变异、输入/分母漂移、symlink 与 CLI 退出语义，并完成 coverage、proof 和
   唯一一份受守卫 formal。全程未 commit/push、未覆盖旧 run。
9. preflight / report / contract 已落盘于
   `build/experiments/active/tile-bg-lz77-palette-gap-preflight-20260830/`；三者 SHA-256
   分别为 `a97197bbff847e2926d813c8fca72d243055bf290a0a83c486cab1f235e7512c` /
   `a3852626acd31e3b46049cfc39646f49cdd6e5f2737936eace4c78951fc53a24` /
   `191e2d60debbb4ff580a800bb53fa9a025b33c599cc6710c25999427985cef1d`。
10. Luna max 的首版 verifier/tests 经过父代理复核后补了两项语义 RED：右端 align4
    必须绑定 gap end，而不是 palette end；右侧 primary class 与 claim kind 必须分开。
    最终 verifier / tests SHA-256 为
    `cd4f61cb1226989c235dd710be7e37b039a6548eec6e5448b23bff97fccbc80b` /
    `781bcf76d984d2a6d210fd8c1ae2a7d4fc82e0d441115a29b7114ae775353660`；
    14/14 测试含全部 165 个单字节 mutation，耗时 106.630 秒。canonical compact
    report SHA-256 为
    `4122e5404dc32e9f1f0429b06e8446d4025b01fb566eeaf1110d92cab0b9a4dc`。
11. coverage 先 RED 后 GREEN；首次 full manifest 测试因 stdout 重定向与 900 秒 idle
    timeout 被守卫终止，属于真实 guard 配置错误而非代码失败。修正后唯一重跑 1/1
    通过，canonical coverage 为
    `1ddc10027b7642399bce8c1a07871ce3a141ca6f2b323c19a650469274cb2df4`，
    classified/unknown/claim/segment 为 6,127,660 / 163,796 / 14,708 / 16,693。
    coverage auditor SHA-256 为
    `9075985f53c263619da34c24c9e0d15a1e2abec0c120a5094b0759397411b230`。
12. proof TDD 的 76 项轻量测试全部通过；一次误把 live coverage 深度测试混入轻量
    命令，约 3 分 55 秒后主动终止，并由正式受守卫审计覆盖。proof SHA-256 为
    `b7423201e3f84280c5556d8d42b95de6c03c07fefcfc85f3d05bf71d5c614c57`。
    formal report / guard SHA-256 为
    `37ef4055b419cb520e3bbaf953ca81f3ae72fdc2613032235498ec298dc87832` /
    `7d7fd44829fa1359c619182f2103b3856d359a63dc6f143113a10eb850592779`；
    94/94 实际唯一命令、ROM gate 84/84、bank 10/10、bad=0，耗时 3,263.08749 秒，
    峰值 RSS 692.83984375 MiB、非降级。报告正确保持 `complete=false`、177 blockers。

## 26. 当前唯一写入方向：boot Thumb code→literal 对齐边界 24B

1. 每个里程碑前调用 Goal API；非 `active` 不得写。余额百分比若仍不返回，只记录
   “不可验证”；出现可验证 `<=5%` 时立即停止新写入。
2. script-first preflight 必须从 `rom-boot-thumb-handoff-cfg-v1` 的完整 27 code
   range / 22 consumed-literal range 分母投影全部正长度 `code_end→literal_start`
   邻接；不得从 live coverage 反向发现候选。完整候选恰为 12 段 / 24 bytes，每段
   `00 00` 且 `gap_end == align4(code_end) == literal_start`。
3. 冻结范围为：`[0x061022,0x061024)`、`[0x0610FE,0x061100)`、
   `[0x06111E,0x061120)`、`[0x06114A,0x06114C)`、`[0x06185E,0x061860)`、
   `[0x061F8A,0x061F8C)`、`[0x0620C6,0x0620C8)`、`[0x062276,0x062278)`、
   `[0x06231E,0x062320)`、`[0x099DF6,0x099DF8)`、`[0x09C046,0x09C048)`、
   `[0x09C086,0x09C088)`。compact range-vector / packed-bytes SHA-256 为
   `dec4177a9818ff7b3349a7c678f8e4a223f4a6e8ac254e2cd81bb4cf1362ce58` /
   `9d908ecfb6b256def8b49a7c504e6c889c4b0e41fe6ce3e01863dd7b61a20aa0`。
4. 独立 verifier 必须从 raw ROM 重解 12 个左侧 terminal：六个 unconditional
   branch、五个 return、一个 indirect branch；验证它们均不 fall through 到 gap，
   并绑定精确 left code owner、right literal owner、源 artifact/manifest/verifier
   identity、12 个范围顺序与逐字节 mutation。源 artifact 的“envelope gaps 未声明”
   是历史 scope，不得重写；新包只能新增独立 alignment 分类。
5. 非声明至少包括：不扩展 boot 自然运行时、全 ROM code/literal/gap 分母、literal
   业务语义、padding/NOP、reserved/free/allocatable、compiler authorship、编辑、
   写回或重定位安全。
6. 该合同闭合后属于公开边界小包，可由 Luna max 单 writer 只实现 standalone
   verifier/tests；父代理负责 RED 验收、语义补强、coverage/proof/formal 与最终审查。
   下一候选为 battle-effect LZ77→component 12 段 / 20 bytes；异构 direct-CpuSet/
   reuse palette gap 必须拆包，禁止合并为统一 right-owner 合同。

## 27. 2026-08-31 审计提速规则与下一批次

1. 用户已授权把逐 packet 全量审计改为三级审计。每个 packet 仍必须完成 TDD、独立
   raw-input verifier、身份/分母哈希、current-unknown 投影、重叠拒绝和失败关闭变异；
   但在达到批量门槛前不得逐包重建 canonical coverage 或运行 formal proof。
2. 二级门槛与 `AGENTS.md`、证明策略一致：累计净增至少 10 KiB、预计提升至少 0.15
   个百分点或同类 packet 达到 4 个。达到门槛后只做一次 coverage
   rebuild、一次 proof 同步和一份非降级 formal；`unknown_bytes == 0` 后再做三级最终
   全审计。
3. 本节建立规则时的 authoritative coverage 为 6,138,856 classified、152,600 unknown、
   15,666 claims、17,182 segments，即 97.574488%。任何尚未接入 packet 的数字只能称为
   projection。
4. 下一批次优先完成固定 accepted CFG instruction denominator 的 Thumb
   `LDR Rd,[PC,#imm]` consumed-literal packet：v2 预计 6,796 bytes、v6 预计 2,980
   bytes、v1 预计 1,396 bytes，合计 11,172 bytes，达到二级 10 KiB 门槛；三包均通过
   一级审计后再统一接入 coverage/formal。v3 预计 1,228 bytes，但与 v2 有 8 bytes
   target overlap，必须以后状态或全局去重失败关闭处理，不能直接相加。
5. 三级策略不允许把 code owner 之间的整段 unknown、相邻零值、padding/free space、
   自然可达或业务语义批量外推；只能晋升独立 decoder 从冻结 accepted instruction
   membership 重建出的实际消费 4-byte words。
6. 本节建立规则时 Goal 曾为 `blocked`；2026-09-01 已由用户恢复并经 Goal API 确认为
   `active`，后续仍须在每个里程碑前重新检查。

## 28. 2026-09-01 consumed-literal 第二批里程碑

1. 四个新增 packet 已完成一级审计并统一接入：CFG v3 为 1,220 bytes / 95 ranges；
   proven-roots v2/v3/v4/v5/v7/v8/v9 合并包为 1,256 bytes / 116 ranges；battle
   controller 为 536 bytes / 46 ranges；v2 `consumer_code_slice` shadow 包为 308
   bytes / 17 ranges。四包精确零重叠，净增 3,320 bytes。
2. authoritative coverage 更新为 6,142,176 classified、149,280 unknown、15,940
   claims、17,344 segments，即 97.627258%；coverage SHA-256 为
   `24cf30aa8049f961ce71737ca9cacfa42c63771643e8bb6784a8a834ee097987`。
3. proof evidence/verifier 分母为 96/92；2026-09-01 非降级 formal report
   `build/experiments/active/cfg-consumed-literals-batch2-formal/codex-r1-20260901/formal-report.json`
   的 SHA-256 为 `8ec5119f4f21132721a0727bc4d6caf18a570076bce45093425334b573fe001d`，
   102/102 实际结构化 verifier 全部 contract-ok，ROM gate 92/92。
4. 下一批从新 coverage 重聚类。已验证的低风险候选为 profile selector/wrapper
   164 bytes、chapter selector 64 bytes、generic sprite loader tail 36 bytes；另有
   battle status-bar caller 1,856 bytes 与 OAM/task slice family 1,686 bytes，但历史
   artifact/verifier 身份已漂移，必须先恢复冻结基线，不能直接晋升。

## 29. 2026-09-01 consumer-code-slice 四包里程碑与 formal 去重

1. 四包已从 projection 变为 canonical：`rom-profile-selector-code-slices-v1`
   164 bytes / 2 ranges、`rom-chapter-selector-code-slice-v1` 64 / 1、
   `rom-sprite-loader-tail-v1` 36 / 1、`rom-battle-status-bar-caller-slice-v1`
   1,856 / 1，合计 2,120 bytes / 5 claims；均只声明冻结 consumer/producer 分母内的
   `consumer_code_slice`，不外推自然可达、完整函数/CFG、相邻字节或业务语义。
2. authoritative coverage 为 6,144,296 classified、147,160 unknown、15,945 claims、
   17,349 segments，即 97.66095479329428%；SHA-256 为
   `064370aa0eca861d99d96e4ee15be4b50c569bea86c67a279d4084517e543baa`。
3. 旧 CFG consumed-literal verifier 的 post 模式不再绑定某次历史全局 summary；baseline
   模式仍精确绑定旧 SHA/分母，post 模式改为验证 claims/segments 计数、从 0 到 ROM_SIZE
   的完整无缝分区及由 segments 重算的 classified/unknown。自身 owner、范围、字节、
   分母与 artifact 身份仍按原合同失败关闭。该规则已覆盖 v3、proven-roots batch、
   battle-controller、v2-shadowed 以及本批四个 verifier 的后续增量回归。
4. `audit_reverse_engineering_proof.py` 已消除 formal 内同一 coverage 的双重执行：ROM gate
   先调用导入的 `audit_rom_manifest` 得到完整报告；当结构化合同命令精确规范化为
   `python* tools/audit_rom_byte_coverage.py --root .` 时，只对这份已执行报告重放 JSON
   pointer 断言并标记 `execution=reused-in-process`。脚本身份仍由 proof spec 哈希绑定，
   其他 verifier 不复用。单元测试同时覆盖成功、断言不符失败关闭和绝不 spawn 第二个
   coverage CLI。
5. 最终 coverage rebuild 守卫位于
   `build/experiments/active/consumer-code-slice-batch-coverage/codex-r4-final-20260901/`，
   22 分 49 秒、峰值 423.554688 MiB、非降级。去重 formal 位于
   `build/experiments/active/consumer-code-slice-batch-formal/codex-r2-dedup-20260901/`；
   report / guard SHA-256 为
   `369c84311c2a753c93b4d7b9868f7752f8d8a9780021264737002b4a7269c80c` /
   `af1a7354baf64a6942a6f37a32015b553e91cdc7675714e3dfcbd5ee47fa4ef9`，
   106/106 contracts、ROM gate 96/96 全部 contract-ok，唯一 coverage 合同被安全复用；
   报告仍正确为 `complete=false`、177 blockers，因为 100% 与其余全局发布 gate 尚未完成。
6. 下一批不要回到几十字节 gap。优先顺序：event-handler table roots→Thumb CFG，冻结窗口
   `[0x07E070,0x07F0FC)`、最大 4,236 bytes、19 roots；sprite component source
   `[0x12C904,0x12D134)`、2,096 bytes。每包先走快速审计，达到二级门槛再统一
   rebuild/formal。此前列出的 positions group47 renderer text `1,022 / 1,710 bytes`
   估算已被第 30 节独立负证据撤回，不得再作为晋升候选。

## 30. 2026-09-01 event-handler CFG 快速审计队列

1. `rom-event-handler-cfg-v1` 已完成一级快速审计，但尚未接入 canonical coverage/proof。
   authoritative coverage 仍是第 29 节的 6,144,296 / 147,160；本包只可称为
   `+4,062 bytes` projection，接入后预计为 6,148,358 / 143,098，不能称为正式进度。
2. 固定 producer `[0x53E698,0x53EE98)` 共 512 个 u32 slots；247 个匹配冻结 unknown
   窗口，归一化为 19 个 Thumb roots。18 个 root 接受，`0x07F064` 因
   `0x07F0E8 -> 0x07F11E` 越过冻结边界而失败关闭拒绝。
3. 接受闭包为 1,742 instructions / 3,910 code bytes / 471 blocks；另绑定 53 次实际
   PC-relative literal 引用、38 个唯一 word / 152 bytes。晋升 union 为 11 ranges /
   4,062 bytes；11 个 holes / 174 bytes 继续 unknown。
4. Luna max 首次实现因多次抄错冻结 range/hash 且长时间未落 exporter/verifier被终止；
   Sol medium 复用 RED 与修正合同完成实现。父代理随后发现并 TDD 修复一项 P1：不得用
   packet 晋升量覆盖 canonical baseline 的 `unknown_bytes`；现保留 147,160，并另记
   `promoted_from_unknown_bytes=4,062`，且断言 classified + unknown == ROM_SIZE。
5. 最终 contract/exporter/verifier/manifest/payload SHA-256 分别为
   `42ff03212b40d435093c8de589b5750f704d0e3b5910e4a6dc2b7f1c5e657ae9` /
   `a5cad2500b1336ed8e6bff54a77f9b4764597f0ae9f3f52df32f39a3daadc736` /
   `f47e7e5a570ae6a1fc1a7bff11064df0b53bf60136314a799c0cc3962bfc36d3` /
   `c665fe39c92124717ea851822542b883803a8957fe0d4b5bacaac0a47ed6a906` /
   `577fb65f3d73ba0f797fa9cdc306165b60941de4f88e13dede0eac7e573f8892`。
   父代理复跑 11/11 tests 与 `python3 -I -S` 独立 verifier 均通过。
6. 本包不声明自然运行时可达、全局 handler/producer 穷尽、literal 业务含义、完整
   包络、相邻 holes 的 padding/free/allocatable 状态、编辑、写回、重定位或 gameplay
   语义。继续累计有固定消费者分母的包；达到至少
   4 packets、10 KiB 或 0.15 个百分点后，只统一运行一次 canonical rebuild/formal。
7. `rom-sprite-component-source-v1` 已作为本批第二包通过一级快速审计，仍未接入
   canonical coverage。固定 source `[0x12C904,0x12D134)` 精确闭合 12 个 component
   lists（96×20-byte records + 12 terminators）、12-entry definition table、4 条
   timeline（12 keyframes + 4 terminators）与 4-entry animation table，共 2,096 bytes。
   `0x06F2AA/0x06F2AC` 两条 PC literal load 和 `0x06F2C4 -> 0x0626B4` direct BL
   绑定 allocator/selector/renderer/stride/timing 消费链；consumer code 只作 provenance，
   `[0x0631F6,0x063210)` 与相邻 `[0x12C901,0x12C904)` 均保持 unknown。
8. 父代理复核发现首版 mutation 测试会先被全 ROM/coverage SHA gate 拒绝，无法证明局部
   pointer/terminator/consumer/owner validator；已增加绕过外层 identity gate 的独立
   decoder 与 owner mutation 测试，并断言具体失败原因。测试变更使旧 artifact 因绑定
   旧测试哈希而正确失效；旧版已保留在 parent-review experiment，新候选独立验证后
   提升为 official。最终 15/15 tests 与隔离 verifier 通过。
9. sprite contract/exporter/verifier/manifest/payload/bundle SHA-256 分别为
   `4fe44811116e78e7492c3cdb42f6a07e218f45a4f709776c1f0515df58d0df8f` /
   `19055db3722f02921cd17914536042aef54f7e494dc265e5f406d989a6124b7a` /
   `70bad678100f3f525f8f83dd67a79ed7492078be08c620bcca6e2e61862f7912` /
   `30c9629581ae62329c147bdb31914f41dd2972e1326c18bde7a03823fc5ad719` /
   `8fe0742e60878d2f71ce87115ee48223f02f8d8eafce3f6e08df2e57f860fdb7` /
   `896a1b46f36cd8ad7f5e1c95a048b9aca099eb03ba55c21d4a43730979edcafb`。
   本批两包 projection 合计 +6,158 bytes，即 6,150,454 classified / 141,002 unknown /
   97.75883356730142%；正式 authoritative progress 仍为 97.66095479329428%。
10. positions group47 的 `1,022 / 1,710 bytes` 候选已独立否证。`0x06E810`
    dispatcher 固定扫描 3 张表 × 16 个 4-byte cells，selector 1..7 的 handlers 只读取
    当前 cell 的 byte 0..3 并调用 battlefield object allocator `0x081024`；不存在
    `[r4+4]` 读取、指针解引用或通向 renderer `0x06626C/0x066758` 的边。8 个
    pointer-shaped cells 的低字节均大于 7，因此均走 default skip；严格
    renderer-consumed denominator 为 0。机械套用 renderer grammar 只能解析 8 段 /
    146 bytes，`1,022` 恰为错误的 `146×7`；同簇严格零间隙也只有 66 bytes，且无消费者
    顺序证明。除非找到真实解引用与 renderer 链，否则这些字节及间隙全部保持 unknown，
    不得用形态扫描或相邻关系晋升。
11. `rom-cfg-proven-roots-v16` 作为本批第三包通过一级快速审计。current canonical 的
    target-limited 全 ROM Thumb BL 扫描得到 21 个形态命中：19 个已分类 code owner
    接受为 producer，`0x0610C6 -> 0x09C0F4` 与 `0x09ACD2 -> 0x09AE28`
    因 source owner=unknown 显式拒绝、不得晋升。15 roots 合并闭包最终为 369
    instructions / 70 blocks / 778 code bytes / 0 decode reject / 18 baseline cross edges。
12. 第三包父代理复核发现并 TDD 修复一项 P1：`0x09C106` 的 BIOS SoftReset
    `svc #0` 永不返回，通用 decoder 原先却 fallthrough，把其后
    `[0x09C108,0x09C110)` 两个 inline literal words 错算成 4 条 Thumb 指令。v16
    exporter 与独立 verifier 现各自验证冻结 terminal/raw/incoming 边界，再把这 8 bytes
    留给 literal pool；不修改全局 decoder。修复前 artifact 非破坏性归档于
    `build/experiments/active/cfg-proven-roots-v16-parent-fix-20260901/`。最终 9/9 tests 与
    隔离 verifier 通过；manifest/payload SHA-256 为
    `1a8bec0c59290851b388a1bedbbf58957b18b6e1eddf483558d6e30cd6dc650a` /
    `2d8f65b5345a89e02778bcdba2de01f420f3b378149c9eeb6e549c7d2c0ad99a`。
13. `rom-cfg-proven-roots-v16-consumed-literals-v1` 作为第四包，从修复后 v16 的 369
    条冻结指令独立重解 51 次 Thumb PC-relative LDR，精确闭合 51 个唯一对齐 word /
    204 bytes；所有 target 在 canonical baseline 均为 unknown，且与 778-byte code
    union 零重叠。loaded value 不声明 pointer/table/resource/业务语义。最终 9/9 tests
    与隔离 verifier 通过；manifest/payload SHA-256 为
    `0fa52bc1c61d246c7264afc23fb381ffe5e0aecbc278af50ff3df92b92199c5b` /
    `5049833533e7183c6be51db189fe6f9c72a2bd74990ca6559f11f3d5ff3acee0`。
14. 本批四包已从 projection 接入 canonical：event-handler 4,062 + sprite component
    2,096 + v16 code 778 + v16 literals 204 = 7,140 bytes / 116 claims。authoritative
    coverage 为 6,151,436 classified / 140,020 unknown / 16,061 claims / 17,483
    segments，即 97.77444203694662%；coverage SHA-256 为
    `4e8ab6b090825901ab7b055326e64a6a16343ec95ac33cfe5e0dbe7721eb2440`。
    第 1、7、9 项中的“尚未接入”和 projection 数字仅保留历史过程含义，均由本项取代。
15. 审计链路已去除 mutable-baseline 自失效与 formal 重复执行。四个原 verifier 保持
    原文件与哈希不变；旧 coverage `064370aa...` 以 deterministic gzip 固化在
    `artifacts/rom-fast-audit-four-packet-baseline-v1/`（1,649,084 bytes），统一 verifier
    在临时根恢复该基线、重放四个 verifier，再核对当前 canonical 恰有 116 条 / 7,140
    bytes claims。proof 不再单列重复的第 97 个合同，而由唯一 coverage audit 在构建时
    执行统一重放，并把 baseline/replay-verifier SHA 写入 summary；proof 分母为 115
    evidence / 96 ROM verifier contracts。
16. 最终 coverage guard 位于
    `build/experiments/active/fast-audit-replay-coverage-final2-20260901/`，24 分 21 秒、峰值
    423.4140625 MiB、非降级，guard SHA-256 为
    `67222205d9687204b230939b5f28b0b886fa52efd30e3c82723f73f20c6166ea`。
    proof SHA-256 为
    `9b78c91a30b1150c82b9e213b08087afcaeb8237a3d3365ec5b57c409ae481d7`；formal report /
    guard SHA-256 为
    `8e6dbd0bb776672ac7927f865fc43b97638091f034b583eb94bd28d5e167104f` /
    `8e09c74bf4212cf735673d9196dfb16530eafcb11eca244c1aeea27da241b81f`。
    106/106 实际结构化合同全部 contract-ok，ROM gate 96/96、evidence valid，coverage
    合同有且仅有一次 `reused-in-process`；报告保持 `complete=false` / 177 blockers，
    因 unknown 仍为 140,020 且其他发布 gate 未闭合。两次前置 coverage guard 分别因
    `-I -S` CLI 缺口与 proof 内重复统一 verifier 设计被主动终止，不得作为正式证据；
    一次 `--proof`/`--spec` 参数错误仅耗时约 5 秒且未生成 report。
17. 下一轮重聚类后，`rom-cfg-proven-roots-v17` 已以合并 code/literal 包接入
    canonical。两个已分类 BL `0x08F9E6/0x08F9F0 -> 0x0914D8` 证明 root；目标
    `[0x091676,0x091FE0)` 精确晋升 2,092 code + 308 consumed literal = 2,400 bytes / 26
    claims，五个 2-byte gap 保持 unknown。新 authoritative coverage 为 6,153,836
    classified / 137,620 unknown / 16,087 claims / 17,513 segments，即
    97.81258900960286%；SHA-256 为
    `23eb0ceaf4d38b8cadb74e05ddf8686de454d5e73c433da26073075d1fa71e78`。
    coverage guard 位于 `build/experiments/active/cfg-proven-roots-v17-20260901/`，耗时
    24 分 56 秒、峰值 440.29296875 MiB、非降级，guard SHA-256 为
    `630a28835fb7156daff69ae6bbc2805256d454530e3255df1616bdfc23fda6e3`。
    同轮两个形态候选严格拒绝：`[0x59EAE0,0x59F560)` 因 index=120 反例与 callback
    lifecycle 开放保持 2,688 bytes unknown；`[0x0B9BB4,0x0B9E94)` 因不满足任何
    alignment/parser-bound padding 合同保持 736-byte 全零 unknown。坐标修正和完整
    负证据见 `notes/rom-unknown-cluster-refresh-20260901.md`。proof SHA-256 为
    `2110942b50ea9e33592b0f1ce339092fbc1e041c647e343c4e298f69231f80c4`；最终 formal
    report / guard SHA-256 为
    `9a66f8b2fc5e7840b4226ad306dbd10c68dc4243c5e40cab7927ed84c15eaf3f` /
    `7be0f457a6da35600c868972df77dac384a1bae4d7500e0e2e36f5a691e5ed8d`。
    106/106 contracts、ROM gate 96/96 全部 contract-ok，evidence valid，coverage 仅一次
    `reused-in-process`；报告正确保持 `complete=false` / 177 blockers。formal r1 因 proof
    漏更新五个 CFG aggregate assertions 耗时约 35 分钟，报告
    `8261e3a8e5df891709fdee946e2eb4da2cb8f253da94e2b612340ede5b0ebd34`
    保留为失败证据，不得作为正式验收；另一次所谓静态 proof 预检因实际会重复完整
    coverage，在约 30 秒内主动终止，未生成 report。
18. `rom-cfg-proven-roots-v18` 已完成并接入 canonical。固定 roots 为
    `0x0910D0/0x0914D8`；target-limited 全 ROM Thumb BL/B/Bcond denominator 恰有四条
    accepted producers：`0x091E82/0x091F1C -> 0x0910D0` 与
    `0x08F9E6/0x08F9F0 -> 0x0914D8`，无 rejected producer。目标
    `[0x09106C,0x09163E)` 精确晋升 1,386 reachable code + 96 closure-wide consumed
    literal = 1,482 bytes / 17 claims；四个 2-byte holes 与两个 indirect-PC frontier
    之外不外推。artifact manifest/payload SHA-256 为
    `0eccd4e7235e88ca2711f6afff4adad8d939e0ff8b757c405f6194b49138a651` /
    `fa92bc6fc3234bbc053e902567125cf2e1653aca39b3928e80ffb66043c76859`。
19. v18 authoritative coverage 为 6,155,318 classified / 136,138 unknown / 16,104
    claims / 17,533 segments，即 97.836144765218%；coverage SHA-256 为
    `984eb8ed8ef72691e1b580b00465d24e1762bb5c0604c35fe76db40153fc42e0`。
    coverage guard `58c4a267...d5af4` 耗时 26 分 8 秒、峰值 433.722656 MiB；proof
    SHA-256 `af16a0e8...9f80c`。formal report/guard SHA-256 为
    `fc3d2ce85af12f5d26e2703811edd8bf56070c35b7ffac7efa24a4fde1105290` /
    `9f31c62b289e9d127256db543ff264f37f1082be3452d13f0dc410ed55853f69`，
    36 分 13 秒、峰值 508.230469 MiB、非降级；106/106 contracts、ROM gate 96/96、
    evidence valid，coverage 唯一实例进程内复用。报告保持 `complete=false` / 177
    blockers 是因为尚有 136,138 unknown 和其他发布 gate。
20. `[0x063ADC,0x064478)` 保持整段 2,460 bytes unknown。条件重解可形成五个 roots
    和 2,436-byte union，但其 dispatcher `0x064670` 唯一 direct producer
    `0x06109A` 的 source owner 仍为 unknown；前一条 interwork reset 路径不证明返回。
    不得用邻接、形态命中或条件闭包晋升。后续若要重开，必须先独立证明
    `0x06109A -> 0x064670` 可达，再冻结 dispatcher 6-slot table、五 roots、23 code
    ranges、21 literal ranges 与 12 holes。
21. boot interwork continuation 与 v19 已原子接入。continuation 静态 root
    `0x06108A` 分类 74 code + 20 literal = 94 bytes；其 code claim 内唯一 producer
    `0x061092 BL -> 0x065728` 解锁 v19，后者分类 1,600 code + 60 literal = 1,660
    bytes。v19 固定 798 instructions / 54 blocks，两条 outbound call 均绑定冻结 v2
    block entry `0x063604`，frontier `0x065D98`；六个 2-byte holes 保持 unknown。
22. authoritative coverage 现为 6,157,072 classified / 134,384 unknown / 16,124
    claims / 17,557 segments，即 97.86402384440103%；coverage/proof SHA-256 为
    `b51f322daf9e1b9af453f5423fad590d81eb42ae0440cc76482553a15d574008` /
    `57b62f81403009be715ff8ba7658098b94500d523fbe8b7089022f346cb60b45`。
    formal report/guard SHA-256 为 `f31c5546a578aa0e1ff7c0fe7003dd3c45a3901c56015303be2c9c8207dbfc95` /
    `73b3d913e4542f34eee90e55fcabd94e5ddc437e0f30e7ef932b815efbf189c2`；
    106/106 contracts 与 ROM gate 96/96 通过，complete=false / 177 blockers。
23. 下一步重新聚类 authoritative unknown，并按 producer-owner 依赖拓扑选候选。
    continuation/v19 的复用边界：producer 必须完整落在哈希绑定 upstream code claim；
    artifact/verifier/receipt、baseline owner、全 ROM producer 分母与 DAG 无环性必须
    失败关闭。不得凭相邻代码或零洞外推自然可达、padding、free 或可编辑性。
24. `rom-chapter-script-unbound-tail-v1` 已接入。slots 45/46 的 8-byte tail vector 加两个
    parser closure 共 3,186 bytes / 3 claims，128 nodes / 128 edges / 0 frontier；两个
    1-byte 边界洞继续 unknown。authoritative coverage 为 6,160,258 classified /
    131,198 unknown / 16,127 claims / 17,559 segments，即 97.9146639506022%，SHA-256
    `3b13c811baf8f8d14af074c9e2dc9057932cfe720ad8e16e06f8f6cd17d09daf`。
    packet replay 不再读取 mutable canonical coverage：旧 SHA 只是明确未观察的 historical
    reference，独立 verifier 明示 deferred gate，coverage auditor 在投影前实际验证
    current-unknown 并写 accepted-claim receipt。proof SHA-256 `fdaef96c...68df`；formal
    report/guard SHA-256 `1f3a392b...ef75` / `52e34d3e...a2b6`，106/106 contracts 通过。
    后续优先实现已冻结的 consumer-bound script roots `[0x05CD41,0x060C70)`，预期净增
    16,175 bytes；必须基于当前 coverage `3b13...9daf` 重新冻结 unknown 交集与 receipt。
25. `rom-chapter-script-consumer-roots-v1` 已接入并取代上一条的“下一步”状态。consumer
    `[0x08A534,0x08A588)` 绑定 root `0x05CD41`，consumer
    `[0x08A588,0x08A638)` 绑定 root `0x05D593`；两个 closure 为
    `[0x05CD41,0x05D593)` / `[0x05D593,0x060C70)`，合计 16,175 bytes、1,120 nodes、
    1,322 edges、102 terminals、0 frontier。consumer slices 只作 data-flow evidence，
    不得作为 promotion；`[0x05CD40,0x05CD41)` 与 `[0x060C70,0x060C74)` 保持 unknown。
    authoritative coverage 为 6,176,433 classified / 115,023 unknown / 16,129 claims /
    17,562 segments，即 98.171758651733%，SHA-256 `b71a91d1...ed52`。proof SHA-256
    `8d6ec4cf...0c96`；formal report/guard SHA-256 `b7ff8d64...a289` /
    `12b01904...fe9`，106/106 contracts、ROM gate 96/96 全部通过。下一步必须基于
    `b71a91d1...ed52` 重聚类 remaining unknown；不得继续使用上一条旧 coverage 身份。
26. `rom-battle-condition-result-text-v1` 已完成一级快速审计但尚未接入 canonical。
    完整物理 denominator 为 47 battles × 3 variants × win/lose × 4 slots = 1,128 rows；
    898 empty、230 active，active type 计数为 `{1:155,2:11,3:18,6:8,7:16,8:16,9:6}`。
    公共仲裁路径从 row `+4` 读取 payload，并调用 result renderer→bridge→parser；219 个
    唯一目标均在 `[0x007F1D,0x009F2E)`，解析为 219 条 NUL 终止记录 / 3,961 bytes。
    artifact manifest/payload/verifier SHA-256 为 `93e3a9f8...69aa` /
    `16457b1e...0f2` / `ec8de0fe...c361`；packed bytes SHA-256 为
    `9826a706...3d91`。packet tests 6/6、coverage projection tests 3/3 和独立 verifier
    均通过。基于 canonical `b71a91d1...ed52` 的投影为 6,180,394 classified /
    111,062 unknown / 98.23471705118814%，但批量门槛只有 3,961 bytes / 1 packet，故
    canonical 仍保持 98.171758651733%。下一接手者应继续积累同信任边界 packet；达到
    10 KiB、0.15 个百分点或 4 packets 后，才统一 rebuild coverage 与
    formal。不得晋升 2,782-byte inter-record gaps、`[0x9974,0x9F2E)` 尾部，亦不得把
    positions group47 的物理别名当成独立 provenance。快速收据位于
    `build/experiments/active/battle-condition-result-text-20260902/codex-r1/quick-projection.json`。
27. `rom-alternate-dialogue-table-v1` 已作为第二包通过一级快速审计。direct producer
    `0x08F9F0` 固定 `r0=3,r1=0` 并调用 `0x0914D8`；`0x0915AC` CpuSet 清零
    `0x02002880` work struct，alternate mode 首次 index=0。`0x091BEC` 自增，
    `0x091E52 CMP #19` 只在 `<=19` 时经唯一 `0x091F76 MOVS r6,#0` 与
    `0x091F82 -> 0x09182E` backedge 重入；index 20 保留 state32 并退出，不解引用 row20。
    因此 `[0x459284,0x459414)` 20×20-byte table 的 `+4/+8/+12/+16` 四字段完整消费，
    80 条 NUL targets / 1,214 bytes 与 80 段固定 zero gaps / 1,586 bytes 连同表 400 bytes
    合计 3,200 bytes / 161 claims。artifact manifest/payload/verifier SHA-256 为
    `f7ded383...21b0` / `62576a9d...696e` / `e0e72584...67da`；7/7 packet tests、3/3
    projection tests、独立 verifier 通过。父代理 TDD 修复了 mutable coverage 自失效、
    缺 claim kind/hash 及 verifier 接受嵌套成员三项证据链问题。
    两包累计 projection 为 6,183,594 classified / 107,862 unknown /
    98.28557968139648%，仍低于二级门槛；canonical 保持 98.171758651733%。下一包只需
    再净增 3,079 bytes 即达到 10 KiB 门槛，或净增约 2,277 bytes 即达到 0.15pp 门槛，
    届时应统一 rebuild coverage/proof/formal。`[0x45832C,0x458794)` 与 computed/
    indirect `0x0914D8` producers 保持 unknown/open。
28. `rom-story-state-callback-cfg-v1` 已闭合固定 callback `0x0808F73C`。两处 Thumb
    pointer occurrence 与 scheduler dispatch/return owner 均绑定；336 instructions、
    28 opaque BL、0 frontier，精确晋升 678 code + 24 literal = 702 bytes / 13 claims。
    state `0x0700` 分支内唯一 `0x08FA26 BL -> 0x08C4CC` 是下一 packet 的 producer；
    四个 2-byte gaps 不晋升。Luna max 能完成 RED 草稿，但错误填写 literal value 且未能
    继续 GREEN，父代理纠正并完成实现；这是模型纪律/执行能力问题，不是环境 blocker。
29. `rom-story-state-entry-c4cc-v1` 由 Sol medium 在冻结小包内完成，父代理复验 8/8 与
    独立 verifier。target-local `[0x08C4CC,0x08C584)` 为 184-byte Thumb code，
    `[0x08C584,0x08C5A8)` 为 36-byte、9-binding literal pool，strict return 是
    `add sp,#0x18; pop r4; pop r0; bx r0`；共 220 bytes / 2 claims、0 frontier。
    后续 `[0x08C5A8,0x08CBB4)` 1,548 bytes 没有同一 producer 证明，必须保持 unknown。
30. 四包达到二级审计门槛并已合并。authoritative coverage 为 6,184,516 classified /
    106,940 unknown / 16,524 claims / 18,175 segments，即 98.30023447672525%，SHA-256
    `e48c8f6d...9c36`；proof SHA-256 `7efbccde...83e0`。formal report/guard SHA-256
    `6960c095...9cc5` / `b056eddf...8b69`，106/106、ROM gate 96/96 全部 contract-ok，
    report 正确保持 incomplete / 177 blockers。coverage 全链约 32 分钟且长期无 stdout；
    idle timeout 必须至少 120 分钟。昂贵重放前必须先跑“四包叠加 + CFG aggregate”定向
    预检，冻结 code-kind registry 与 `mode=thumb`，不得重复本轮链尾失败。
31. 新一轮第一包 `rom-text-bg-loop-continuation-v1` 已通过一级快速审计，canonical 未改。
    旧 V15 曾因 source 不在 accepted worklist 排除 `0x08B644 -> 0x08ACC8`；当前 coverage
    已由独立 residual-text-BG artifact 将 `[0x08B640,0x08B64E)` 分类为唯一
    `consumer_code_slice` owner，故旧 blocker 已解除。全 ROM target-limited producer
    denominator 恰为一条 Thumb BL，且无 B/Bcond、ARM B/BL 或 ROM pointer 命中。
    target-local 在 current accepted owner 起点 `0x08ACF2` opaque stop，只晋升
    `[0x08ACC8,0x08ACF2)` 42-byte code 与四次 LDR 实际消费的三个 literal words
    `[0x08AEB4,0x08AEC0)` 12 bytes，共 54 bytes / 2 claims、0 frontier。artifact
    manifest/payload/verifier SHA-256 为 `b1e29845...3bea2` / `b5d16813...2b67e` /
    `abad4787...dd114`；13/13 packet tests、4/4 quick projection tests和独立 verifier
    通过。投影为 6,184,570 classified / 106,886 unknown / 98.30109278361002%，但本批
    只有 54 bytes / 1 packet / 0.000858pp，必须继续积累，不能单独跑 full audit。
    初版被 Sol review 判定五项 P1 后已加固：`consumer_code_slice` 的
    `instruction_only_claimed=false` 不再作为指令证明；packet 先重放 residual text-BG
    ownership，再独立冻结两个 natural entry callers、root `0x08B58C`、55-instruction /
    130-byte path、`0x08B608 B -> 0x08B644` 与 producer BL membership。另绑定
    `[0x08ACF2,0x08AD08)` opaque owner；immutable payload 不再写 live observed SHA/state，
    verifier 已通过 synthetic post-promotion replay。发布使用原子 NOREPLACE、文件/目录
    fsync，并拒绝 ancestor symlink；mutation 测试命中各自 producer/CFG/literal/path guard。
    Sol 末轮提出的两个残余 P1 也已关闭：exporter 在 `resolve()` 前检查词法 output
    ancestors，且第 4 次 fsync 故障注入覆盖“rename 已成功、parent fsync 失败”路径；
    最终只读复核结论为无 P0/P1。
32. `[0x04BE31,0x04C616)` 2,021-byte chapter-shaped gap 当前裁决为 keep-unknown。
    假设 `0x04BE31` 是 root 时，现有 decoder 可闭合 `[0x04BE31,0x04C615)` 2,020
    bytes（87 nodes / 86 edges / 1 terminal / 0 outside edge），但全 ROM 逐字节 u32
    扫描零命中；左侧脚本在 `0x04BE30` 已 terminal，primary/alternate scenario 54/55
    表均从 `0x049E76` 直接跳到 `0x04C616`。因此缺少真实 producer/root，不能把语法
    可解析性或两侧邻接当作消费者证据；末尾 `0x04C615` 也在 terminal 后不被消费。
33. 新一轮第二包 `rom-boot-copy-sources-v1` 已通过一级快速审计，canonical 未改。
    唯一 full-ROM producer `0x060FE0 BL -> 0x061624` 绑定本地 straight-line consumer；
    独立 verifier 从 raw Thumb 解码 112 条 CFG 指令并重建全部 9 条 DMA3 descriptor，
    其中三条固定 ROM source 分别覆盖 `[0x4C8,0x6C8)`、`[0x520,0x5C4)`、
    `[0x5AC,0x60C)`。V12 `0x06459E` 的 CpuSet source `[0x638,0x694)` 实际 destination
    是 literal `0x03005CE8`，boot `0x0646DE` source `[0x690,0x734)` destination 为
    `0x03005D50`；五段 union 恰为 `[0x4C8,0x734)` 620 bytes / 1 claim。
34. artifact manifest/payload/verifier SHA-256 为 `040e009c...a464` /
    `aeecd2f0...f59b` / `57c336d3...189a`；14/14 packet tests、3/3 quick projection、
    official independent verifier 全部通过。Sol 最终复核的三项 P1 已关闭：错误 CpuSet
    destination 已纠正；9 条 DMA denominator 不再由 exporter/verifier 共享硬编码解释；
    payload `rom`、完整 `upstream_evidence` 与完整 `promotion` 均精确失败关闭。
35. `rom-text-bg-loop-continuation-v1` 与本包累计 projection 为 6,185,190 classified /
    106,266 unknown / 98.31094741821289%，即 +674 bytes / +0.010712941487630207pp /
    2 packets。尚未达到 10 KiB、0.15pp、4 packets 或 blocker-unlock 门槛，因此不得
    运行 full coverage/proof/formal，也不得把投影冒充 authoritative canonical。
    `[0x578C,0x7554)` 仍受动态 index denominator 阻塞；`[0x53F89C,0x541368)` 的 14 个
    `0x10` 形态头经长度/边界验证均不是有效 LZ77 stream，二者继续 unknown。
36. `rom-text-bg-task-closure-v1` 已作为第三个一级 packet 完成。入口
    `0x08ACC8` 在本包内继续遍历至 strict return `0x08AF44`，并通过 direct-call DAG
    闭合 `0x08A708/0x08C5A8/0x08C5D8`；callback literal `0x08AF0C =
    0x0808AA51` 经 caller stack arg、`0x0626B4` allocator variant、`0x062760`
    task `+0x28` store、renderer `0x06294C` field load 和 `0x09C114 BX r1` wrapper
    证明 callback root `0x08AA50`，再闭合 `0x08A84C/0x08A7B4/0x08C70C/
    0x08CA4C/0x08C8B4`。完整闭包为 10 roots、1,330 instructions、2,782 code
    bytes、80 LDR literal references / 65 unique words / 260 literal bytes、0 frontier；
    排除 queued `[0x08ACC8,0x08ACF2)` / `[0x08AEB4,0x08AEC0)` 与 canonical
    `[0x08ACF2,0x08AD08)` / `[0x08AD30,0x08AD4A)` 后，净投影 2,940 bytes /
    34 claims。packet 9/9、quick projection 3/3 和独立 raw Thumb-1 verifier 全绿。
    旧 character-runtime 整体 verifier 的父 OAM blocker 被显式保留为 false；本包只
    独立重放所需 `task+0x28` 字段与 ROM 调用链，不借其总体状态冒充通过。三包累计
    projection 为 6,188,130 classified / 103,326 unknown / 98.3576774597168%，
    canonical 仍为 6,184,516 / 106,940 / 98.30023447672525%。
37. Luna max 已筛出第四包候选：canonical v2/v3 CFG 内 41 个 PC-relative literal
    consumers 均最终调用 `0x08067158`；其中可由现有 parser 合同闭合 36 sites / 30
    unique records / 1,124 bytes，且与 queued boot copy source 不重叠。七段 union 为
    `[0x0A65,0x0ABB)`、`[0x0B9A,0x0BC9)`、`[0x0BF5,0x0C2E)`、
    `[0x0C6C,0x0CEA)`、`[0x12F0,0x14B4)`、`[0x15B0,0x15C4)`、
    `[0x1631,0x1781)`；range-vector SHA `a781ac70...b9ce`、record-vector SHA
    `6fa95454...8df3`、packed bytes SHA `badb4ac6...0b9`。五个 opcode 7/8 targets
    `0x0BC9/0x0C2E/0x0C34/0x14B4/0x15FC` 必须排除，因其 handler 尚无 bounded parser
    contract。该候选通过后达到 4-packet 门槛，再统一 coverage/proof/formal。
38. `rom-fixed-renderer-script-records-v1` 已实现并通过父代理复核。exporter/verifier 不再
    硬编码 41-site 清单，而是从哈希固定的 v2/v3 manifest、payload、verifier 六个上游
    文件重建完整 block denominator，再用 bounded Thumb CFG register-taint 证明 literal
    destination 经分支及 r7/r6 copy 最终进入 `0x067158` 的 r0。41 sites 中接受 36，排除
    targets `0x0BC9/0x0C2E/0x0C34/0x14B4/0x15FC`，得到 30 unique records /
    1,124 bytes / 30 claims。8/8 tests、official verifier 均通过；修改 `0x8179C`
    destination register 的负例失败关闭。Sol medium 末轮结论无 P0/P1。
39. 四包已达到 `4 packets` 二级门槛并统一接入：continuation 54、boot copy 620、task
    closure 2,940、fixed renderer records 1,124，共净增 4,738 bytes / 67 claims。
    authoritative coverage 为 6,189,254 classified / 102,202 unknown / 16,591 claims /
    18,261 segments，即 98.37554295857748%。coverage / proof SHA-256 为
    `ff1b9a98fafbe7a14e569db229deddd201a5ec3bea64ced57eb2c0a86c3622b8` /
    `d615ac4562a28e645a68038c64f3f6825f54900862bc477e49eb785fd86bc2df`。
40. 首次 formal 虽进程 exit 0，但只有 105/106 `contract_ok`，因此未冒充成功。根因是
    text-BG continuation verifier report 的 `coverage_state` 从首次构建前 `baseline`
    变为接入后 `post-promotion`，导致被 claim 绑定的 report SHA 一次性变化；字节、范围、
    summary 均未变化。一次合并诊断/稳定重建修正两条 claim，随后 verifier 连续两次报告
    SHA 均为 `46e784...a656`。此类瞬时字段今后必须在一级审计连续重放中发现，不再用
    full rebuild 探测。
41. 最终非降级 formal-r2 report / guard SHA-256 为
    `3dcfb9d2b3dc00838370e8d461b4f005940ec1ea4ed4e7962974163c98b1dc86` /
    `d8e0b4d716c291036b1b88b9b443f701af0964cc540db4c5e55fda62a4def0ce`：106/106
    contracts 全部 `contract_ok`，coverage `verified=true`、errors `[]`。proof 正确保持
    incomplete，只因为仍有 102,202 unknown 与既有发布/bank gates，不是本轮回归。
42. 下一步只能基于 coverage `ff1b9a98...3622b8` 重聚类。优先复核
    `[0x063ADC,0x064478)` dispatcher 家族：上游 continuation source 已解锁，但五个
    `BX r0` frontier 仍需结构化返回/目标分母合同；在合同闭合前不得按包络晋升。
43. 上一条 blocker 已由 `rom-boot-state-dispatcher-cfg-v1` 的一级快速审计关闭。上游
    continuation claim 内唯一 `0x06109A BL -> 0x064670`；全 ROM、2-byte stride 的
    BL/B/Bcond target-limited denominator 连同 dispatcher wrappers 恰为六条。dispatcher
    固定读取 `0x03005CBC`、mask 7、减一、unsigned `<=5` 与 6-slot table；五 roots
    独立重建 1,116 instructions / 23 code ranges / 2,248 code bytes / 21 literal ranges /
    188 literal bytes / 8 opaque calls，12 个 2-byte holes 继续 unknown。加上 96-byte
    dispatcher，packet 净投影 2,532 bytes / 45 claims，frontier 为零。
44. 结构化返回不能只依据指定 terminal。Luna max 复核发现 root `0x063C34` 在
    `0x063C84` 把 SP 传入 opaque `CpuFastSet`；已固定唯一 SP alias、20 个 SP-relative
    store、saved LR 为当前 `SP+0x30`、最大直接 store 为 `SP+0x10`、wrapper
    `0x09C0DC = SWI 0x0C; BX LR`、source `SP`、destination `0x02000A00` 与 fill-mode
    control `0x01000050`，因此 BIOS 只读首个 source word并不写 LR 槽。五 root 与
    dispatcher 的六个 `pop {r0}; bx r0` 才据此闭合。
45. Sol medium P1 复核进一步指出真实 ROM 命中全为 BL，B/Bcond 扫描分支未受测试保护。
    已新增 synthetic `B 0x063ADC` / `Bcond 0x063ADC` extra-producer mutation，并让 exporter
    与 verifier 都失败关闭；verifier 改为独立位级 producer decoder，最终六个命中再由
    vendored Capstone 二次确认。最终 Sol 复核无 P0/P1，packet tests 7/7、quick projection
    3/3；official verifier 连续两次 report SHA 均为 `46240245...7002`。manifest /
    payload / verifier SHA 为 `c3296d25...6004` / `ac14c13a...0465` /
    `5b373b90...a802`。
46. 该包预计把 authoritative 6,189,254 / 102,202 投影为 6,191,786 classified /
    99,670 unknown，即 98.41578801472983%。它只有 2,532 bytes / 1 packet /
    +0.04024505615234375pp，未达到 10 KiB、0.15pp 或 4 packets 的二级门槛，因此
    canonical coverage/proof/formal 暂不重建。下一包必须以 `ff1b9a98...3622b8`
    canonical 加本 packet projection 做 current-unknown 检查，不能把预计值写成正式状态。
47. 第二个一级 packet `rom-fixed-animation-descriptor-groups-v1` 已闭合
    `[0x12D574,0x12D9E4)` 1,136 bytes。调用者 `0x071EA8..0x071EBE` 穷尽生成 group
    `0..3`，`0x071EC0/0x071EC2` 装入 12-record pointer table 与 4-group table，再调用
    `0x0626B4`。allocator 明确把 slot 初始化为 0；renderer 只在 next group entry 不是
    `0xFFFF` 时增加 slot，因此每组访问恰好 3 records。
48. 描述器范围不是凭形态晋升：`0x0631F6..0x063208` 明确以 `0x14` 前进，对 next
    entry head 做 signed load 并与 `-1` 比较后停止；12 个描述器均为 4 entries +
    `0x0000FFFF` terminator，恰好 `0x54`。stride/stop/slot/table/consumer mutations 全部
    失败关闭。
49. 最终 artifact manifest/payload/verifier SHA-256 为 `83e526c5...ff05` /
    `8afa72be...5e3b` / `9555d5bf...6e529`。11/11 packet tests、3/3 quick projection、
    standalone verifier 通过；Sol 最终复核无 P0/P1。verifier 拒绝非 canonical JSON、
    额外文件、status/implementation 篡改、member 与 ancestor symlink；发布为原子
    no-replace。预加固 artifact 已移入 `build/experiments/superseded/`，不得引用。
50. 本批两包累计 +3,668 bytes / 46 claims；投影为 6,192,922 classified / 98,534
    unknown / 98.43384424845377%，但 authoritative 仍是 coverage `ff1b9a98...3622b8`
    的 6,189,254 / 102,202 / 98.37554295857748%。未达二级门槛，禁止提前 full rebuild。
    下一优先候选为 AI 配置表 `[0x53F348,0x53F86C)` 1,316-byte current-unknown
    projection；必须先核实 `unit+0xCD` 的边界，不能把 8-row 物理形态当成 runtime index
    证明。若该边界不闭合，切换到已有 accepted 7-slot dispatcher 的
    `[0x083B5C,0x083FEA)` bounded packet。
51. AI 配置表路线已失败关闭地暂缓。scorer 从 `unit+0xCD` 取动态 ID 并乘 `0xA8`；已
    找到 `0x0806AD6C/6E` 与 `0x0806E246/248` 的字段复制 writer，但未闭合 source-record
    ID 的完整生命周期与 `<=7` 分母。因此不得把 `[0x53F348,0x53F888)` 的 8 行物理
    形态当作 runtime index 证明，也不得重分类与旧 LZ77-syntax claim 重叠的尾部。
52. 替代包 `rom-battle-distance-dispatcher-cfg-v1` 已完成。upstream v2 code blocks 与
    batch-consumed-literal artifact 分别绑定 `0x083B3C..0x083B4E` 和
    `0x083B50..0x083B5C`；unsigned `LDRB/CMP #6/BLS` 与 table-base literal 完整闭合
    7 个 slots/roots，越界 selector 进入 accepted `0x083FEA`。
53. target-local worklist 重建 555 instructions / 126 blocks / 1,110 code bytes，六个
    literal words为 24 bytes；25 exits 只到 accepted `0x083FEA`/`0x083FFA`，frontier=0。
    table+code+literal 共 1,162 bytes / 14 claims；两个 2-byte 零洞保持 unknown。
54. packet tests 7/7、quick projection 3/3、standalone verifier 通过。artifact manifest /
    payload / verifier SHA 为 `ce7844f6...5fa2` / `2b8efd1f...c718` /
    `8f6f3ce4...5716`。三包累计 +4,830 bytes / 60 claims，投影 6,194,084 classified /
    97,372 unknown；仍只有 3 packets，禁止提前 full rebuild。下一步优先找一个边界闭合
    的第四包，随后按 tier-2 门槛统一 coverage/proof/formal。
55. Sol 对 Tier-1 接入的最终复核发现 `battle_distance_target_reachable_instruction_bytes`
    尚未登记 `CFG_CODE_KIND_REGISTRY['thumb_only']`，因此 quick projection 虽可通过，
    Tier-2 `_cfg_code_aggregate()` 会失败关闭。已先增加独立 registry RED，再补登记并
    GREEN；后续每个新增 CFG code kind 都必须同时覆盖 Tier-1 projection 与 Tier-2
    aggregate admissibility。
56. 第四包 `rom-bounded-index-u16-pair-table-v1` 已闭合
    `[0x53F2EE,0x53F30E)`。consumer 内 unsigned `CMP #7/BHI` 支配 `index*4` 和两个
    `LDRH`，完整物理分母为 8×4-byte records；唯一 index writer、base literal、43-node
    局部 CFG、双字段数据流和最高访问偏移均由 exporter/verifier 独立重建。精确晋升
    32 bytes / 1 claim，右侧 `[0x53F30E,0x53F310)` 保持 unknown。8/8 packet tests、
    standalone verifier 和 Sol P0/P1 review 通过；manifest / payload / verifier SHA-256
    为 `d909fed886e1779ae8db16a04dbcce7471d74a9a808ad17f6afd7372a0cb8d04` /
    `d95ab9f397511a88550301bed432315e66e75899e15073b74c19a643fff85af2` /
    `077037c6924ba2e184f98bf84ef8f1598035ee7ad4d11698d79c7370fee7de7a`。
57. 四包达到 Tier-2 门槛后已真实接入 canonical，不是收益算术外推。新的集成测试逐包
    检查 45/2,532、1/1,136、14/1,162、1/32 claims/bytes，确认跨包无重叠、右侧 gap
    仍 unknown，并重建 CFG aggregate。authoritative coverage 为 6,194,116 classified /
    97,340 unknown / 16,652 claims / 18,332 segments，即 98.45282236735026%；coverage
    SHA-256 为 `ae7c69330285bd3d668612b057a793f1b98edda5e0df421a8bda6f5e90290024`。
    CFG aggregate 为 956 ARM + 165,572 Thumb code bytes、166,560 promoted unknown
    bytes / 3,969 primary claims / 45 code kinds，denominator SHA-256
    `140cd11a51f55efba1c9bada8627ad2ce17652d34fee8b459991705ce96b90cd`。
58. proof spec 已同步八个新 artifact evidence、coverage/script 哈希、四包分母与新
    canonical summary；SHA-256 为
    `754089931606cd2d8bcd28e21c00baf4ccc93fdbcad6b52def7f1e7b2739034f`。
    唯一非降级 formal report / guard SHA-256 为
    `18c6c60f6b00ed6fb83e04bb62805cbee07d2ad4249ed2d15c9a292c2eddda2a` /
    `1b0c772287ed6a0d1f00c903b69eb42d8da572562d5166e3fa864f2f8304b9d9`；
    106/106 unique contracts 全部 exit 0 且 `contract_ok=true`，ROM gate 96/96，bad=0。
    `complete=false` / 177 blockers 是 97,340 unknown 与既有 bank、round-trip、发布和
    实体硬件门，不是本批回归。
59. 审计成本已失败关闭记录。coverage 首次以 `idle-timeout=1800s` 在仍满 CPU 时被误杀，
    canonical 未写；R2 以 3,600s idle 在 2,317s 完成，峰值 444.24609375 MiB。一次误判
    为轻量的 structural proof 在 83s 后主动终止且无报告。两项可避免浪费合计 1,883s。
    formal 正式运行 2,916s，峰值 532.828125 MiB。今后静默 coverage/formal 的 idle
    不得低于 120 分钟；一级 packet 只跑快速审计，二级必须保留真实 canonical 集成测试，
    禁止用常数相加冒充验收。
60. 下一优先 packet 为 `rom-v17-v18-helper-cfg-v1`，预计净增 1,254 bytes：11 roots、
    575 instructions、1,198 code + 56 literal bytes、14 promotion ranges、0 frontier。
    合同必须保留六个 2-byte holes、33 个 accepted direct producers、1 个 unknown source
    `0x090FF0 -> 0x090758` 和一条 M4A 数据形态误报；不得声明所有 inbound producer 已
    accepted，也不得外推自然可达或业务语义。低收益兜底为 `[0x53E00A,0x53E034)` 的
    42-byte 双表包；只有大包合同不能闭合时才切换。
61. 上一包已完成并正式提升为 `artifacts/rom-v17-v18-helper-cfg-v1/`。独立 raw-Thumb
    verifier 重建 575 instructions / 81 blocks / 24 opaque exits / 11 returns / 0 frontier；
    全 ROM direct denominator 为 99,909，root hits 34 = 33 accepted + 1 unbound，另保留
    一条 M4A 数据形态误报。精确晋升 1,198 code + 56 literals = 1,254 bytes / 14 claims，
    六个 2-byte holes 保持 unknown。8/8 packet tests 与 5/5 Tier-1 projection tests
    GREEN；投影为 6,195,370 classified / 96,086 unknown / 98.47275416056314%。这是新批次
    第一个 packet，authoritative canonical 仍是 `ae7c6933...90024` / 97,340 unknown，
    禁止把投影写成正式状态或提前运行 full/formal。
62. Sol review 发现并关闭一个真实 P1：Tier-1 helper code kind 不得提前进入稳定 CFG
    registry，否则旧 canonical aggregate 会报 missing。现使用 active-only staged registry；
    absent 时保持稳定 hash，present 时强制 Thumb mode、计入 bytes/claims/kind denominator，
    未注册 code-like kind 仍失败关闭。verifier 也不再把任意未知 halfword 当 linear，而是
    独立拒绝 Thumb-1 合法 opcode family 外编码。R2 manifest / verifier SHA-256 为
    `aaee06ec...32f0` / `8e544183...603a`，official verifier 再次通过。
63. 低收益兜底 `rom-fixed-pair-tables-v1` 也已完成并正式提升。A 表
    `[0x53E00A,0x53E014)` 为五个 signed-u16；B 表 `[0x53E014,0x53E034)` 由九条冻结
    consumer 路径共同绑定，index 经过 `&7` 和 `<<2` 后读取两 u16。只晋升 42 bytes /
    2 claims，左右 gap 保持 unknown。9/9 packet tests、standalone verifier、输出范围、
    symlink、mutation 与原子 no-replace guards 通过；manifest / payload / verifier SHA 为
    `70bab2c2...233d` / `dae6a761...98dc` / `66c33983...9ee`。R2 另以 RED/GREEN
    关闭 `build/experiments/../...` traversal；R1 official 已移入 superseded。
64. 新批两包累计 +1,296 bytes / 16 claims，Tier-1 overlay 为 6,195,412 classified /
    96,044 unknown / 98.47342173258463%；authoritative canonical 仍为 6,194,116 /
    97,340，禁止冒充正式进度。为降低逐包成本，通用 current-unknown gate 已从反复对
    16,652 claims 做全 ROM atomization 改为等价的线性 primary-range 交叠检查；同组
    5 tests 从 215.686s 降到 55.812s，重叠/非法输入仍失败关闭。当前 2 packets 未达
    Tier-2 门槛，不跑 full/proof/formal；继续优先选择净增 >=1,000 bytes 的闭合包。
65. `rom-prebattle-menu-controller-cfg-v1` 已完成并正式发布。唯一 producer
    `0x08F894 BL -> 0x08F190` 由上游 accepted story-state callback claim 提供 owner；
    selector 固定 `0..5` 并解析六项 jump table。独立 closure 为 786 instructions /
    1,752 bytes，净晋升 1,564 code + 332 literals + 24 table = 1,920 bytes / 52 claims；
    83 opaque calls 只允许进入当前 accepted code/CFG owner，保留 7 个 indirect frontiers。
66. packet suite 12/12、candidate 和 official verifier 均通过。manifest / payload /
    verifier SHA-256 为 `51824fc2...712d` / `ed05a078...ae13` / `f82f0778...908`。
    Sol review 的 union 未从组件派生、producer owner 合同回显两个 P1 已关闭；正式
    artifact 不得替换为 superseded candidate。
67. 审计已分层：mutation 内层只做冻结身份、canonical JSON、manifest/payload claim、
    ROM 与 coverage owner 的轻量失败关闭；完整上游 verifier 只在正式 exporter 和独立
    verifier 入口运行。Tier-1 coverage 仍调用独立 packet verifier，并用线性 primary-range
    gate 验证 52 段 current unknown；不得以“快速”跳过正式发布验收。
68. 三包 overlay 为 6,197,332 classified / 94,124 unknown / 98.50393931070963%，
    authoritative 仍为 6,194,116 / 97,340。3 packets / 3,216 bytes 不达 Tier-2 门槛，
    禁止提前 full/formal。下一包冻结 `[0x46401C,0x464534)` 的 1,029-byte 主合同；
    两个 OBJ closures + 71 source ranges 可同包，另 98-byte alignment gaps 必须分包。
69. 上一条是入队时的历史状态。正式 `rom-scene-source-closures-v1` 拒绝了草案中的
    12 bytes unknown-only roots 与 2 bytes parser overrun，只晋升 71 段 parser-bounded
    sources 655 bytes + 2 个 OBJ closures 360 bytes，共 1,015 bytes / 73 claims。46 段 /
    90 bytes alignment gaps 独立排队，23 段 / 199 bytes residual 与 roots `0x464298`、
    `0x4642AC` 保持 unknown。12/12 packet tests、独立 verifier 与 Sol P0/P1 review 通过；
    manifest / payload / verifier SHA-256 为 `df3616f...98467` / `0013db71...4929` /
    `8a5ed29f...393a`。
70. 三个依赖接入前 coverage 的 packet verifier 曾读取 live canonical，第一次 rebuild 后
    因自身 claims 已被提升而自失效。这是真实 P1，不是 coverage 回归。现已发布
    `rom-scene-source-four-packet-precoverage-v1`：manifest / gzip SHA-256 为
    `b3aaeca2...220a` / `9b1d55e7...25ff`，解压后精确等于旧 canonical
    `ae7c6933...90024`。三份合同固定读取该 archive；永久测试重放 archive，并要求历史
    one-shot builder 在 live canonical 前进后失败关闭，禁止改写旧 manifest 伪造 receipt。
71. 四包合计 4,231 bytes / 141 claims 已真实完成 Tier-2 接入。authoritative coverage
    为 6,198,347 classified / 93,109 unknown / 16,793 claims / 18,552 segments，即
    98.52007230122885%，SHA-256 `b14d1778...96b82`；CFG aggregate 为 956 ARM /
    168,334 Thumb / 169,322 promoted / 4,005 primary claims / 47 code kinds。proof SHA-256
    `e50417ea...a8e9`。正式非降级 formal report / guard 为 `b2afd536...88da` /
    `f09deffd...30d`，106/106 contracts、ROM gate 96/96、coverage errors=0；177 blockers
    来自 93,109 unknown 与既有全局门。
72. 审计策略已简化并固化：Tier-1 只做 packet TDD、独立 verifier 和线性
    current-unknown projection；只有 4 packets、10 KiB 或 0.15pp 任一门槛触发 Tier-2
    canonical/proof/formal；最终全量审计只在 `unknown_bytes==0` 或 release 运行。下一优先
    packet 为 story callback 六条固定 BL 边驱动的 direct-callee 依赖闭包，预核定净增
    1,460 unknown bytes。精确候选 ranges 是 `[0x0861C8,0x0863FE)`、
    `[0x086A54,0x086C2A)`、`[0x068DFC,0x068E42)`、`[0x068E44,0x068E5C)`、
    `[0x0752D0,0x075342)`、`[0x075344,0x075350)`、`[0x08B65C,0x08B6EE)`、
    `[0x08A69C,0x08A6AC)`、`[0x08F710,0x08F73A)`；相邻洞不得吞并。
73. 第 72 条候选已按递归直接依赖收紧并完成：`rom-story-callback-dependency-closures-v1`
    实际为 9 roots / 762 instructions / 156 blocks / 1,656 code + 276 literal = 1,932
    bytes / 32 claims。草案的 1,460 bytes 既误吞 6 个 2-byte hole，又漏掉两个唯一直接
    callee 和 24 bytes 外置 consumed literal；正式包保留全部 12-byte holes unknown，
    63 exits 绑定 37 个既有 owner，8 个 indirect return 绑定逐 root epilogue，0 frontier。
74. 初版绑定 mutable `sequel/rom-byte-coverage.json` 会在下一次接入后自失效；Sol 复核
    将其判为 P1。已发布 immutable
    `rom-story-callback-dependency-closures-precoverage-v1`，manifest / gzip SHA 为
    `fbdc769f...f423` / `af9fd00d...1c00`，解压 SHA 为当前 canonical
    `b14d1778...96b82`。主 exporter/verifier 只读该 archive，post-advance 模拟禁止读取
    live coverage 后仍通过。packet manifest / payload / verifier SHA 为
    `0c0209dc...85ea` / `62d3ad44...a18b` / `3338abda...2364`。
75. 新 Tier-1 队列为 1 packet / 1,932 bytes / 32 claims；线性 current-unknown 投影
    6,200,279 classified / 91,177 unknown / 98.55078061421713%，CFG 投影为 169,990
    Thumb / 170,978 promoted / 4,023 primary / 48 kinds。当前 canonical 仍保持第 71 条，
    不得把投影冒充正式进度；未达 4 packets、10 KiB 或 0.15pp，禁止运行 full
    coverage/proof/formal。下一步继续选择可失败关闭的 >=1 KiB unknown packet。
76. 第二个 Tier-1 packet `rom-cfg-proven-roots-v20` 已完成。全 ROM Thumb
    BL/B/Bcond target-limited scan 只命中 `0x06108E` 与 `0x061320`；前者属于已接受
    boot continuation instruction owner，后者仅属于 `consumer_code_slice`，所以只接受
    前者。root `0x062924` 的 raw closure 为 1,405 instructions / 249 blocks /
    2,866 code bytes，39 个唯一 consumed literal words / 156 bytes、17 个 accepted
    opaque exits、三个 unresolved BX frontiers。
77. v20 精确晋升 11 段 code / 1,070 bytes 与 7 段 literal / 80 bytes，共 18 claims /
    1,150 bytes；与 story overlay 重叠 0。正式 manifest / payload / verifier SHA 为
    `7f5ed6e4...f2d` / `5d3186a6...543` / `0f185e03...e66`；9/9 packet tests、3/3
    Tier-1 projection、official independent verifier 全部通过。
78. 当前两包累计 +3,082 bytes / 50 claims，投影 6,201,429 classified / 90,027
    unknown / 98.56905937194824%。authoritative canonical 仍是第 71 条；未达 4 packets、
    10 KiB 或 0.15pp，禁止运行 full coverage/proof/formal。下一步优先另找 >=1 KiB
    闭合包；`[0x53E492,0x53E496)` 的 4-byte 固定 caller tail 只作低收益兜底。
79. 第三个 Tier-1 packet `rom-story-next-dependency-cfg-v1` 已完成。root `0x088F10`
    的 target-limited producer 分母只有 `0x08F61A` / `0x08F928`；前者 source 仍为
    unknown，后者属于已排队 story instruction owner，故只接受后者。闭包为 338
    instructions / 96 blocks / 770 code bytes、21 literal words / 84 bytes、43 opaque
    calls 与三个 unresolved BX frontiers。
80. 本包精确晋升 19 claims / 854 bytes，五个 2-byte holes 保持 unknown。三个特殊
    opaque targets `0x065404/0x08CBF4/0x08CC18` 均绑定独立验证的 CFG-inventory v2
    exact instruction entry，不能用宽泛 `consumer_code_slice` 代替 instruction
    membership。manifest / payload / verifier SHA 为 `a5429f89...669` /
    `d12f4b28...e6b` / `ed5b3581...fa8`；10/10 packet、3/3 Tier-1、正式 verifier 通过。
81. 当前三包累计 +3,936 bytes / 69 claims，投影 6,202,283 classified / 89,173
    unknown / 98.5826333363851%。authoritative canonical 仍为第 71 条。下一包完成即
    达到 4-packet Tier-2 门槛；在此之前不得运行 full coverage/proof/formal。优先候选
    是 `0x06109E BL -> 0x06178C` 所绑定的 boot register-init dependency CFG，预计
    446 bytes，保守保留三个 BX frontiers。
82. 第四包 `rom-boot-register-init-dependency-cfg-v1` 已完成。唯一 target-limited
    producer `0x06109E BL -> 0x06178C` 绑定 boot continuation exact block；raw closure
    为 154 instructions / 12 blocks / 318 code bytes，32 个唯一 consumed literal
    words / 128 bytes。三条 opaque calls 绑定 CFG inventory v2 exact entry，三个
    `BX r0` 保持 unresolved。
83. 本包精确晋升 8 claims / 446 bytes；`[0x06181E,0x061820)` 保持 unknown，
    `[0x0620B4,0x0620CC)` 绑定三个既有 boot-handoff owners 且零重复晋升。manifest /
    payload / verifier SHA 为 `367a72b1...a932` / `ec89abce...22bd` /
    `6710e77a...ff91`；packet 15/15、Tier-1 3/3、四包合并 13/13、candidate/official
    verifier 均通过。
84. 四包达到 Tier-2 门槛后已真实接入 canonical。authoritative 为 6,202,729
    classified / 88,727 unknown / 16,870 claims / 18,641 segments，即
    98.58972231547037%；CFG aggregate 为 956 ARM / 172,148 Thumb / 173,136 promoted /
    4,048 primary / 51 kinds。coverage / proof SHA 为 `2cc07bc7...c01` /
    `3655c4a2...05ce`。
85. 唯一 coverage rebuild 耗时 30 分 20 秒、峰值 439.7265625 MiB；唯一 formal
    耗时 40 分 46 秒、峰值 534.92578125 MiB，均 non-degraded、无重跑。formal report /
    guard SHA 为 `3971d9ea...ac3b` / `88d11d5f...26a`，106/106 contracts、ROM coverage
    gate 96/96、errors=0。`complete=false` / 177 blockers 来自 88,727 unknown 与既有
    全局门。下一步必须基于新 canonical 重聚类；优先选择 >=1 KiB 或能解锁现有
    unknown producer/owner 的冻结 packet，Tier-1 队列从 0 重新计数。
86. 新批第一包 `rom-fixed-index-u8-tail-v1` 已完成。唯一 table-base literal
    `0x0853E424`、唯一 literal-LDR consumer `0x07C72E` 与四个 fixed callers 精确读取
    `[0x53E492,0x53E496)`；全 ROM direct BL 分母为 13，其余九项仅标
    `excluded_non_fixed`，不得称作动态索引证明。只晋升 4 bytes / 1 claim，不声明完整
    114-byte 表。共享 immutable precoverage manifest / gzip SHA 为
    `95cb2fef...e65a` / `88365f67...a6b6`；最终 packet manifest / payload / verifier SHA
    为 `4e8bbe70...fa88` / `25c49e18...2666` / `ab5ee9ab...a11f`。
87. Luna max 在正确 RED 后约 5 分钟无产品实现、无环境 blocker，已升级 Sol medium。
    父级 review 找到三个 P1：非固定 caller 过度命名、coverage owner 只验范围起点、
    输出 `..` 可在拒绝前建目录；三项均先 RED 再修复。随后增加 immutable replay
    RED/GREEN，证明 packet 不读取 live coverage。最终 precoverage + packet 16/16、
    Tier-1 3/3、independent verifier 通过，guard 非降级。
88. authoritative 仍为 6,202,729 classified / 88,727 unknown /
    98.58972231547037%；当前 Tier-1 队列为 1 packet / 4 bytes，线性投影
    6,202,733 / 88,723 / 98.58978589375815%。不运行 full coverage/proof/formal。后续首选
    `0x08F544..0x08F594` 的 80-byte story-selector direct dependency（唯一 accepted
    producer `0x08F8DE`、0 frontier）；`0x078E38..0x07914C` 虽形态可解析 778 bytes，
    但必须先闭合 task `+0x28` callback lifecycle，当前净增为 0。
89. 第 88 条首选已完成为 `rom-story-selector-dependency-cfg-v1`。全 ROM Thumb
    BL/B/Bcond internal-entry 分母只命中 `0x08F676` / `0x08F8DE`；前者 source
    unknown 而拒绝，后者绑定 story callback exact instruction owner 而接受。root
    `[0x08F544,0x08F594)` 为 37 instructions / 80 bytes，3 opaque calls、1 preowned
    literal、0 holes、0 frontier；fallthrough 进入既有 chapter coarse owner。
90. 初版由 Sol medium 完成；Luna max 约 2 分钟无 RED/文件后已停止。只读 reviewer
    找到两个 P1：instruction vector/CFG denominator 只回填常量，且普通 rename 有
    no-replace TOCTOU。父代理新增正确 RED 后，exporter/verifier 分别独立重建 vector、
    worklist、opaque calls、literal、hole/frontier，并复用平台原子 rename-no-replace。
    最终 packet 10/10、Tier-1 3/3、official verifier 通过；manifest / payload /
    verifier SHA 为 `c810e710...19ec` / `9909ace4...676` / `5bafd0fe...9d10`。
91. authoritative 仍是 6,202,729 / 88,727 / 98.58972231547037%；新批队列为
    fixed-index 4 bytes + story-selector 80 bytes = 2 packets / 84 bytes / 2 claims。
    线性投影为 6,202,813 classified / 88,643 unknown / 98.59105745951334%。未达
    4 packets、10 KiB 或 0.15pp，按简化审计规则禁止运行 full coverage/proof/formal。
92. 第 88 条关于 `0x078E38..0x07914C` “callback lifecycle 未闭合、净增为 0”的状态已
    被新证据取代。唯一静态 pointer `0x08078E39` 位于 `0x079378`；source
    `0x0792BE..0x0792CA` 将其作为 arg8 传给 `0x0626B4` allocator，allocator 在
    `0x062760` 写 `task+0x28`，dispatcher `0x062940..0x062958` 在 `0x06294C` 读取该
    字段并经 `0x09C114: bx r1` 调用。上述 source/allocator/dispatcher/veneer owner 与
    task-field artifact 均哈希固定并由 raw ROM 重放。
93. `rom-task-callback-078e38-closure-v1` 已正式发布：342 instructions / 61 blocks /
    718 code + 60 consumed-literal bytes，16 claims / 778 bytes；五个 2-byte holes 保持
    unknown。17 opaque calls / 7 targets 的 SP 与内存副作用未闭合，所以
    `0x079144: bx r0` 保留一个 `indirect_pc_target` frontier，
    `structured_return_count=0`；禁止恢复初版的 0-frontier/structured-return 声明，
    除非为全部 opaque targets 新增独立 ABI/内存副作用证明。
94. 初版由 Sol medium 完成；父级 reviewer 找到四个 P1：verifier 对缺字段/claim/
    lifecycle/scope/implementation 篡改不失败、opaque callee 未证明却宣称 structured
    return、artifact/output path 检查后使用，以及最终验证后 staging 名称仍可替换。
    父代理按 TDD 改为完整 payload/manifest exact 重建、candidate 与 accepted 双阶段独立
    验真、dirfd + O_NOFOLLOW + held-inode + 原子 no-replace，并补 ROM 末 halfword
    direct-scan 回归。正式 manifest / payload / verifier SHA 为 `a9441633...7ca0` /
    `ac163dad...e1aa` / `46ad2406...6f14`；packet 13/13、Tier-1 3/3、三包合并
    22/22 非降级通过；最终只读 P0/P1 reviewer 独立复验后无发现。
95. 当前队列为 fixed-index、story-selector、task-callback 三包，共 862 bytes / 18 claims；
    线性投影 6,203,591 classified / 87,865 unknown / 98.60342343648275%。authoritative
    仍是 6,202,729 / 88,727 / 98.58972231547037%；只有下一份有效 packet 达到
    4-packet 门槛后，才运行一次 Tier-2 canonical/proof/formal。当前余额约 83%。
96. 2026-09-05 当前 Goal 已暂停；最新账户周期 `usedPercent=18`，约剩 82%。完整的
    当前进度、估时、V21 中断点和机械恢复顺序已冻结在
    `docs/reverse-engineering-handoff-current-20260905.md`。恢复时必须先确认 Goal 重新
    `active`，不得依据本文件较早条目的旧“下一步”直接写入。
97. 中断中的 `rom-cfg-proven-roots-v21` 目前只是一份 11/11 GREEN 的实现草稿：root
    `0x063400`、70 instructions / 17 blocks，预计晋升 112 code + 4 literal = 116
    bytes / 3 claims。它尚无 artifact、独立 P0/P1 review、Tier-1 投影或 canonical 接入；
    禁止把条件投影 6,203,707 / 87,749 / 98.60526720682780% 写成正式进度。
98. Goal 起点到当前 canonical 共净解出 124,361 bytes，消耗 245.6444 agent-hours，
    历史均速 506.2642 bytes/agent-hour。线性剩余约 175.26 agent-hours；考虑尾段变难，
    交接预算按 346.65–519.98 agent-hours管理。该估时仅覆盖 `unknown_bytes=0`，不含
    bank、round-trip、UI/editor、mGBA、实体硬件与 trust-anchor 发布门。
