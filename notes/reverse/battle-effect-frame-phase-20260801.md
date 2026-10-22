# 战斗特效单帧 renderer→submit→ack 运行时证据（2026-08-01）

## 结论

复用已验收的 group 11 活动任务快照，没有重新导航，也没有注入按键，捕获了同一个
特效 task 在一次 OAM 事务中的三个严格递增边界：

| Phase | ROM address | Cycle | Frame | pending | shadow/hardware OAM |
|---|---:|---:|---:|---:|---|
| renderer-post | `0x08063328` | 291959155359 | 0 | 0 | 不同 |
| submit-post | `0x08061126` | 291959155722 | 0 | 1 | 仍不同 |
| ack-post | `0x080612AA` | 291959378542 | 1 | 0 | 完全相同 |

三个边界中选定的 group 11 活动对象始终为 slot 124、地址 `0x030058C8`、flags
`0xC1003081`，task `+0x1C/+0x20` 始终为 group 11 的
`0x08345530/0x08345564`。active dispatcher 三阶段均为 slots
`[124,125,127]`，目标 slot 124 始终是 ordinal 0；task pool 三阶段逐字节相同。
renderer-post 产生的
1 KiB shadow OAM SHA-256 为
`692b2b5a5dc85aab5bc2b34b1203d44f8805dbfc5b4d1bad4a6d882387cb89df`；
submit-post 时 hardware OAM 仍保持旧哈希
`4be4cd6f43cc612bdee87bad33c56a339ea5ec99260b7de3d96d4494c95e70f2`；
ack-post 的 hardware OAM 最终精确等于该 shadow OAM。

这证明包含一个自然 group 11 代表 task 的 renderer 事务在主循环中的实际链路是：
renderer 完成 shadow OAM → 主循环置 pending → 下一帧确认 hardware OAM 已接收。
由于同一 dispatcher 中还有两个非 group-11 task，完整 OAM 变化不能排他归因给
slot 124。它纠正了先前把
VBlank 返回点 `0x08061324` 当作唯一 renderer 后边界的假设；本次实际 renderer
调用来自 `0x0806108E → 0x08062924`。

## 可恢复输入与运行边界

- 输入状态：
  `artifacts/battle-effect-group11-pixel-ab-v1/raw/baseline/frame106.ss9`
- 状态 SHA-256：
  `0cb839b5ac6972724b9551afd260ca2a91443399f6c3d1bae7ec2b7f917ae625`
- profile：
  `sequel/content/battle-effect-phase-capture/group-11-cross-shuriken-frame106.json`
- profile SHA-256：
  `29f464d252e345e6225097fdbc9fb2fd5bb13d33770d2342c7ec1be385c6c562`
- baseline ROM SHA-256：
  `8e24aa7de358ba92a4a5c7347e9c5898d7304b9e9a2bed4cf0a9906da5be0ff6`
- mGBA binary SHA-256：
  `c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8`
- mGBA runtime profile SHA-256：
  `e21d375914dda3c20b05ccec45c39406db310609e69ee19d04dfa342f4b70287`
- 正式 run：
  `build/experiments/battle-effect-phase-group11-20260801-13/`
- 正式成果：`artifacts/battle-effect-frame-phase-v1/`

正式运行的 `input_mode` 为 `zero-input-active-state`，`inputs`、
`automatic_inputs` 和 `recovery_inputs` 均为空。运行通过统一 heavy lock 的资源守卫，
以 success marker 正常完成，非 degraded；PGID 与 mGBA listener 均无残留，也没有产生
新的崩溃报告。guard 记录的 peak tree RSS 只有 `0.16796875 MiB`，明显受极短运行与
采样粒度影响，因此只保留原值，不把它当作可信的 mGBA 实际峰值。

## 捕获实现

`tools/mgba_battle_effect_phase_capture.lua` 只保留 renderer-post 常驻断点。它通过
`0x0300067C` 的 WRITE_CHANGE watchpoint 发现 pending 变为 1 后，动态安装
submit-post 与 ack-post 断点，完成后立即退出。这样避免在高频确认路径上保留侵入式
断点，也不再把 CPU/DMA 路由作为未经运行证明的先验。

每个 phase 保存 task pool、active dispatcher、runtime offsets、shadow/hardware
OAM、submission bytes、VRAM、PRAM、I/O、`.ss9` 和截图。正式 artifact 为约
716 KiB，只提升三阶段所需文件，不把完整实验目录或启动诊断文件写入 Git。

## 独立验真与 I/O 边界

`tools/verify_battle_effect_frame_phase.py` 不导入生产器，并从每份 `.ss9` 重新读取
IWRAM、VRAM、PRAM 与 OAM。它要求九类稳定 dump 与存档逐字节一致，并独立检查：

- phase 名称、地址、cycle 严格递增及 pending `0→1→0`；
- mGBA Thumb breakpoint 存档的 `saved r15 - 2` 地址与 phase metadata 一致；
- task slot/address/flags、active bit、group 11 指针对及 active dispatcher 唯一成员关系；
- renderer/submit 时 shadow/hardware 的保持关系；
- ack 时 hardware 等于 renderer 生成的 shadow；
- runtime audit、profile、输入状态、ROM、mGBA profile、guard、残留探针和全部文件
  哈希。

`io.bin` 是唯一例外：Lua 使用 `emu:read8` 对 MMIO 逐字节实时读取，而 `.ss9` 保存
mGBA 的序列化 I/O image；两种接口对动态、只读或非字节寻址寄存器并不逐字节等价。
因此 manifest 将它明确标为 `live_byte_read_only`：文件仍有固定长度与内容哈希，但
验证器不得伪称它等于存档 I/O 区。OAM、PRAM、VRAM 和所有本结论依赖的 IWRAM 不受
此例外影响。

## 复现

```sh
python3 tools/run_macos_mgba_battle_effect_phase_capture.py \
  --binary /Users/altair/github/mgba-build-qt/qt/mGBA.app/Contents/MacOS/mGBA \
  --toolchain-profile artifacts/rom-expansion-profile-v1/profile.json \
  --binary-sha256 c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8 \
  --rom build/experiments/active/battle-effect-group11-pixel-ab-build-v3/baseline/baseline.gba \
  --profile sequel/content/battle-effect-phase-capture/group-11-cross-shuriken-frame106.json \
  --output build/experiments/<new-run>/output \
  --guard-summary build/experiments/<new-run>/guard-summary.json

python3 tools/verify_battle_effect_frame_phase.py \
  --artifact artifacts/battle-effect-frame-phase-v1
```

运行时捕获必须继续通过 runner 间接调用 `tools/run_guarded.py`，不得直接启动 mGBA。
后续调试优先复用上述 active-task 状态，除非目标 group/phase 必须建立新的自然快照。

## 未完成边界

本成果只签发包含一个 group 11 代表 task的一次 renderer→submit→ack 全局事务。它不证明：

- 其余 17 个 group 或 group 11 其他帧的相同跨帧行为；
- affine、多 component、dynamic-copy queue、blend/window 的全部运行时组合；
- OAM ordinal 的通用 allocator/writer 对应；
- 本次完整 shadow OAM 变化全部由 slot 124 排他产生；
- 音频同步、实体 GBA 时序或真机像素输出。

因此它关闭的是此前路线图中的“一条精确跨帧提交相位”缺口，不改变 production 自然
像素 A/B 的 `4/18` 分母，也不代表图像逆向已达到 100%。
