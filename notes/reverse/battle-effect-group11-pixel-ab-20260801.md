# 战斗特效 group 11 自然最终像素 A/B（2026-08-01）

## 结论

战斗特效运行时修改链由 group 5 扩展到第二个独立资源组。scenario 50 战斗中，鸣人
自然选择忍具 1“十字手里剑”，对应 encoded action 129、sequence 13、resource
group 11；确认框前的十段输入已合并成一次受控批量重放，并固化为可复用 checkpoint。

从该 checkpoint 仅输入一次 A 后，两份 production-relocation ROM 都加载 group 11
frame 0。候选只改动解压 graphics offset `0x16` 的低 nibble：byte
`0x21→0x22`、palette index `1→2`。最终证据位于
`artifacts/battle-effect-group11-pixel-ab-v1/`，独立 verifier 返回
`errors=[]`。

## 可复用输入边界

- 父状态：`scenario-50-battle-15-safe-intercept-turn3.ss9`，SHA-256
  `2d872689345ade80d0027dfa7bbb58adfc28cfe3028f6b13856d43c8dc7a6ba8`。
- 批量重放：A、Down、A、Down、Down、Down、A、Down、A、A；精确帧时序记录在
  `scenario-50-cross-shuriken-confirmation-evidence.json`。
- 新 checkpoint：`scenario-50-cross-shuriken-confirmation.ss9`，SHA-256
  `57d4929ef3c8b3050fbe74f0a7898bcbc0b563b96239d1361d9df95667de4139`。
- 本次批量输出 PNG 的审计 SHA-256 为
  `adea2d60d32636e7059aca017f95518e517b454940f0f2707d41664c457fc026`；历史十段逐步
  重放审计记录了同一 SHA。仓库只保留 checkpoint 内嵌画面及这两个历史哈希声明，
  因此不把两份外部 PNG 的字节一致性列为可独立复算结论。
- 边界停在“可以吗？”确认框，尚未按最终 A；因此可直接重复运行候选 ROM，不必重走
  菜单和战斗导航。

批量运行通过统一 heavy guard，峰值 tree RSS 51.87890625 MiB，`completed/0`、
非 degraded，owned PGID 和 mGBA listener 均清洁。

## ROM、内存与像素隔离

基线和候选都把 group 11 graphics 迁移到 `0x08B40000`，并把 pair-table pointer
`0x08599174` 重定向到该地址；安全 LZ77 大小均为 488 bytes，patch topology 完全
相同。候选不依赖运行时内存注入。

最终 frame 106：

- 完整 1,664-byte graphics 分别与各自 ROM 解压内容逐字节一致，位于
  `0x06012C00`；
- 32-byte palette 位于 OBJ palette bank 6；
- OAM entry 0 为 `0x0038/0x40A8/0x6960`，tile base 352；
- EWRAM、IWRAM、IO、PRAM、OAM 完全相同；
- VRAM 只在 `0x06012C16` 有 `0x21→0x22`；
- mGBA PNG 只在 `(172,61)` 有 `(255,255,255)→(255,214,181)`；
- 独立 Mode-0 renderer 与两份 mGBA PNG 均逐 RGB 完全一致。

输入 checkpoint 的动态 OBJ VRAM 中尚不存在完整 group 11 graphics，排除了先前残留
资源被误当作本次自然加载的情况。

## 工具化与边界

新增 `run_macos_mgba_input_sequence.py` 和 Lua runner，把任意多输入导航压缩为单次
受控 mGBA 进程。profile-driven builder/exporter/verifier 可复用到后续其他特效组；
profile 固定资源目录、action/sequence/group 绑定、checkpoint 证据、OAM、帧和像素
oracle。独立 verifier 不导入 builder/exporter，自行从基准 ROM 解压资源、编码安全
LZ77、重建两份 16 MiB ROM并复核完整内存域和屏幕像素。

本成果只签发 18 组中的 group 11、sequence 13、frame 0 的一个 graphics 像素。
group 5 与 group 11 合计为 2/18 个具有自然最终像素 A/B 的代表组；它不外推到其余
16 组、其他帧、完整 affine/blend/时序/音频或实体 GBA。

## 验证

```bash
python3 -m unittest \
  tests.test_run_macos_mgba_input_sequence \
  tests.test_build_battle_effect_pixel_ab \
  tests.test_export_battle_effect_pixel_ab_evidence \
  tests.test_verify_battle_effect_pixel_ab_evidence -v

python3 tools/verify_battle_effect_pixel_ab_evidence.py \
  --artifact artifacts/battle-effect-group11-pixel-ab-v1
```
