# 战斗特效 group 5 自然最终像素 A/B（2026-08-01）

## 结论

战斗特效从 18/18 组静态导出、22/22 sequence 结构和生产 relocation，推进到首条
修改 ROM 后的自然攻击最终像素 A/B。玩家在 scenario 41 攻击确认页只按一次 A，
action 5 自然选择 sequence 6 并加载 group 5；没有 selector 强制、运行时内存补丁、
自动输入或恢复输入。

成果位于 `artifacts/battle-effect-group5-pixel-ab-v1/`，独立 verifier 返回
`errors=[]`。本成果只签发 group 5、sequence 6、frame 1 的一个 graphics 像素，
不外推至其他 17 组、group 5 其他帧、完整 affine/blend/时序/音频或实体 GBA。

## 可复用边界

- 输入快照：`artifacts/runtime-checkpoints/scenario-41-attack-confirmation.ss9`
- 快照 SHA-256：
  `544cffbaea182a55d1963447965d95750984a915cae9877d66d6bc3aebbd560f`
- 唯一输入：A，frame 5 down、frame 13 up
- 捕获：frame 150
- 基线/候选 ROM 均由 production
  `resolve_battle_effect_resource_relocation_patches` 构建；group 5 graphics 均迁移到
  `0x08B40000`，pair-table pointer `0x08599144` 同样重写为该地址。
- 两边安全 LZ77 大小均为 1,165 bytes；allocation、redirect 和 ROM 布局完全相同。

该快照位于资源加载前。输入后完整 3,840-byte group 5 graphics 位于
`0x06012400`（OBJ tile base 288），完整 32-byte palette 位于
`0x050002A0`（OBJ palette bank 5）。OAM entry 1 为
`attr0/1/2 = 0x0030/0x80A0/0x5930`，即 `(160,48)`、32×32、tile 304、
priority 2，精确对应 group 5 frame 1 的 tile 16。

## 单像素修改与隔离

生产资源的解压 graphics offset `0x200` 是 tile 16 local `(0,0)` 的低 nibble：

- baseline byte/index：`0x02` / palette index 2；
- candidate byte/index：`0x04` / palette index 4；
- 完整 VRAM 只有 `0x06012600` 一个 byte 不同；
- EWRAM、IWRAM、IO、PRAM、OAM 全部逐字节相同；
- mGBA 最终截图只在 `(160,48)` 一个像素不同：
  `(255,222,198) → (189,123,115)`；
- 独立 Mode-0 compositor 对两份 `.ss9` 的输出均与各自 mGBA PNG 逐 RGB 完全一致。

这同时证明变化来自迁移后的 ROM graphics，经自然 loader 进入 OBJ VRAM，再由已绑定
OAM/palette 形成最终屏幕像素；不是截图后处理、调色板替换或运行时内存注入。

## 运行与资源安全

两次正式运行均通过 `tools/run_macos_mgba_single_input.py` 内置 heavy guard：

- baseline 峰值 tree RSS：56.23828125 MiB；
- candidate 峰值 tree RSS：56.109375 MiB；
- `completed/0`、非 degraded、POSIX process group；
- owned PGID 清洁，无 mGBA listener 或 `.sav` 残留。

promotion 会把 audit、guard 与 authoring spec 中的宿主机、缓存和临时实验绝对路径
规范化为仓库相对或 `runtime-only/` 身份；提交工件不依赖本机目录，也不包含构建 ROM。
独立 verifier 不导入本里程碑 builder/exporter，而是自行编码 LZ77、重建两份完整
16 MiB ROM、patch ledger、authoring spec 和运行时／像素契约。

复现实验时应继续从上述攻击确认快照开始，不得重走标题和关卡流程。若编辑其他 group，
优先复用本成果的构建器、运行器、内存域差分、Mode-0 compositor 和独立 verifier
结构；只替换资源身份、自然 action/sequence 边界、捕获帧及像素 oracle。

## 验证命令

```bash
python3 -m unittest \
  tests.test_build_battle_effect_group5_pixel_ab \
  tests.test_export_battle_effect_group5_pixel_ab_evidence \
  tests.test_verify_battle_effect_group5_pixel_ab_evidence -v

python3 tools/verify_battle_effect_group5_pixel_ab_evidence.py \
  --root . \
  --artifact artifacts/battle-effect-group5-pixel-ab-v1
```
