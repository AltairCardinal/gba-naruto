# 已观察战斗特效组的三阶段批量闭合（2026-08-01）

## 结论

战斗特效已有持久运行时身份的 groups 为 `[1,2,5,11,14]`，权威来源仍是
`battle-effect-runtime-oam-task-bindings-v1`。group 11 已有一个独立三阶段 artifact；
本轮复用四份 accepted 快照，零输入短恢复补齐 groups 1/2/5/14。当前子分母为：

- 已观察 group 的 renderer→submit→ack 事务：`5/5`；
- 全部非零 battle-effect groups：`5/18`（27.78%）；
- production 修改 ROM 最终像素 A/B：仍为 `4/18`（22.22%）。

机器可复算分母位于 `artifacts/battle-effect-observed-frame-phases-v1/`。独立聚合
verifier 会逐一调用单组独立 verifier，并重新核对 18-group animation catalog、
5-group runtime task binding 来源、批处理 spec 及四份 production pixel-A/B artifact；
结果为 `phase_verified_groups=5`、`all_groups=18`、
`production_pixel_ab_groups=4`、`errors=[]`。

## 四个新增事务

| Group | 输入性质 | ROM SHA-256 前缀 | 捕获 task slot | dispatcher ordinal | guard peak RSS MiB |
|---:|---|---|---:|---:|---:|
| 1 | tracked natural checkpoint | `1198ece781aa` | 113 | 12 | 71.515625 |
| 2 | accepted affine supplemental | `1198ece781aa` | 120 | 0 | 0.16796875* |
| 5 | production pixel-A/B baseline | `699674cc9316` | 124 | 2 | 0.16796875* |
| 14 | production pixel-A/B baseline | `97d318c7e927` | 124 | 2 | 0.18359375* |

`*` 三项运行过短，guard 采样值明显低于实际 mGBA 常驻集；只保留原始记录，不把它们
用作实际峰值结论。四次运行均为 `completed/0`、非 degraded、success-marker 完成，
PGID 和 mGBA listener 无残留，也没有新 crash report。

group 2 输入状态保存时有 slots 123/124/126；恢复后自然推进到下一次 renderer 时，
最先匹配的 group-2 task 为 slot 120。三阶段内 task pool、slot 120 指针对和 dispatcher
ordinal 0 均保持不变，因此这不是把输入状态的旧 slot 身份硬套到新事务。该用例首次把
已接受的 affine group 2 纳入精确提交相位，但仍属于 supplemental，不升级为 production
像素 A/B。

四组与既有 group 11 都独立满足：

1. `.ss9` 为 Thumb mode，`saved r15 - 2` 分别得到 renderer tail
   `0x08063328`、submit post `0x08061126`、ack post `0x080612AA`；
2. cycle 严格递增，frame 为 `0/0/1`，pending 为 `0/1/0`；
3. renderer 后 shadow OAM 与旧 hardware OAM 不同；
4. submit 后 shadow/hardware 均保持；
5. ack 后完整 1 KiB hardware OAM 精确等于 renderer 生成的 shadow OAM；
6. 目标 task 在 active dispatcher 中恰好一次，definition/animation 指针对由 18-group
   catalog 独立推导，而不是由 profile 自报；
7. task pool、active list、runtime offsets、submission、VRAM、PRAM、shadow/hardware
   OAM 等九类 dump 与同 phase savestate 逐字节一致。`io.bin` 仍按既有边界只作哈希
   锁定 live byte-read 观察。

由于 renderer 处理完整 active list，以上只证明事务中包含目标 group task，不证明完整
shadow OAM 变化由目标 task 排他产生。group 1 的 ordinal 12 尤其明确显示其前面还有
其他活动 sprite task。

## 批处理与快照复用

`tools/run_battle_effect_phase_batch.py` 在启动任何模拟器前一次性验证：

- batch spec 与四份 profile 的 schema、group、profile hash；
- 输入 `.ss9`、source runtime evidence 与 ROM hash；
- group 1/2 使用 immutable base ROM；group 5/14 使用各自 production baseline ROM；
- 输出根为空，ROM override 只属于 batch 中的 group。

随后它串行调用 `tools/run_macos_mgba_battle_effect_phase_capture.py`。后者才实际启动
mGBA，并为每个 case 分别套用同一 heavy lock、内存准入、树级 RSS、wall/idle timeout、
success marker、crash latch 和 owned-tree residue 检查。批处理不会并行启动四个 mGBA，
也不会绕过单组守卫。

独立审查后又补齐三项可复现性门禁。batch spec 的 profile 必须是仓库内相对路径，
绝对路径、`..` 与符号链接逃逸都会在启动任何子进程前拒绝。运行时 profile 本身继续
保持与原 audit 完全相同的 SHA-256；新增
`sequel/content/battle-effect-phase-capture/source-provenance-v1.json` 在 promotion
阶段把每个 profile 的原始 source evidence 绑定到 accepted 父 artifact、父 manifest
和载荷哈希，并逐项核对输入 state、ROM 与 group 身份。聚合覆盖也不再信任
`bindings.json` 的自述 summary：它要求父 promotion 为 accepted、载荷由 manifest
哈希锁定，并实际调用独立 task-binding verifier 重建 93 个 tracked、5 个
supplemental 状态及 `[1,2,5,11,14]` 分母。负测覆盖父 manifest/payload、profile
来源、PC、dispatcher 与路径逃逸篡改。最终复审又要求聚合 manifest 精确哈希锁定
其实际导入的单组 phase verifier、task-binding verifier、savestate parser 及对应测试，
避免动态依赖被替换后仍返回成功；单组独立 verifier 也会重新比对
`runtime-audit.profile_sha256 == manifest.profile.sha256 == 当前 profile SHA-256`，
不再只依赖 exporter 当时的检查。

group 5 baseline ROM 已用现有确定性 builder 经 heavy guard 重建；builder 峰值 RSS
82.24609375 MiB，输出 SHA-256 与 accepted build manifest 的
`699674cc9316e3c9d307ac093dc8145273097bd393ae67630dd31631a9b18179`
完全一致。其余调试直接从已有快照恢复，没有重复长导航。

## 正式成果

- 聚合分母：`artifacts/battle-effect-observed-frame-phases-v1/`
- group 1：`artifacts/battle-effect-frame-phase-group1-v1/`
- group 2：`artifacts/battle-effect-frame-phase-group2-v1/`
- group 5：`artifacts/battle-effect-frame-phase-group5-v1/`
- group 11：`artifacts/battle-effect-frame-phase-v1/`
- group 14：`artifacts/battle-effect-frame-phase-group14-v1/`
- 批处理 spec：
  `sequel/content/battle-effect-phase-capture/observed-groups-batch-v1.json`

## 未完成边界

- 13 个尚未观察的 group 没有因此获得运行时身份或 phase 证据；
- group 2 没有 natural modified-ROM pixel A/B；
- 每组只覆盖一个全局 renderer 事务，不是全部 178 frame、437 component 的逐帧运行；
- target task→具体 OAM allocation/writer index 的排他映射仍未闭合；
- dynamic-copy queue、blend/window、音频同步与实体 GBA 时序仍未全量验证。

下一步应转向未观察 13 组的动作/sequence 入口发现和可恢复 checkpoint 批量生成，而非
继续对这五个已观察组重复采样同类 phase。

## 2026-08-02 Group 3 自然到期扩展

Group 3 已通过忍具 67 的 C3 对象自然到期入口完成 production baseline/candidate
最终像素 A/B。聚合分母现为 phase `6/18`、production natural pixel A/B `6/18`；
新增像素成果为 `artifacts/battle-effect-group03-natural-pixel-ab-v1/`，详细证据见
`notes/battle-effect-group3-natural-pixel-ab-20260802.md`。

## 2026-08-02 Group 4/18 聚合更新

Group 18 的自然延迟对象和 Group 4 的自然忍具确认路线现已进入同一可复算聚合。
当前 phase groups 为 `[1,2,3,4,5,11,14,18]`，即 **8/18**；production
modified-ROM pixel groups 为 `[1,2,3,4,5,11,13,14,15,18]`，即
**10/18（55.56%）**。聚合 verifier 会按 artifact schema 分别调用 generic、
Group 5 和 natural-delayed 独立 verifier，而不再只检查 manifest 自报与哈希。

Group 4 详细证据见
`notes/battle-effect-group4-natural-pixel-ab-20260802.md`；剩余 production pixel
组为 `{6,7,8,9,10,12,16,17}`。
