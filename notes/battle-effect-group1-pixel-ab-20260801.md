# 战斗特效 group 1 自然最终像素 A/B（2026-08-01）

## 结论

复用 `artifacts/runtime-checkpoints/scenario-41-attack-confirmation.ss9`，只输入一次
`A`。在同一自然 action 5 路径中，直接 selector 身份为
`sequence 6 / group 5`，同时观察到 `sequence 1 / group 1` 的三个弹道尘土
子任务。profile 因此分别记录
`trigger_sequence_id=6` 与资源 `sequence_id=1`，不再把触发动作和被验证表现资源
强行写成同一条序列。

两份 16 MiB ROM 都通过 production relocation 把 group 1 graphics 指向
`0x08B40000`；allocation、`0x599124` pointer redirect 和 735-byte 安全 LZ77
拓扑完全相同。candidate 只把 1,024-byte 解压 graphics 的 offset 262 从
`0x40` 改为 `0x10`，对应 frame 2、component 0 local pixel `(5,1)` 的 palette
index `4→1`。

## 运行时结果

frame 90 的两份状态都在 `0x06012000` 保存完整 group 1 graphics，并使用 palette
bank 4。三个自然 OAM 实例为：

| OAM | attr0 / attr1 / attr2 | 源 frame | 候选屏幕像素 |
|---:|---|---:|---|
| 0 | `0x0048 / 0x4027 / 0x4908` | 2 | `(44,73)`，可见 |
| 1 | `0x004C / 0x4020 / 0x4908` | 2 | `(37,77)`，可见 |
| 2 | `0x0055 / 0x4023 / 0x4908` | 2 | `(40,86)`，未进入最终像素差异，不推断原因 |

基线与候选的 EWRAM、IWRAM、IO、PRAM 和 OAM 均零差异，VRAM 只在
`0x06012106` 有 `0x40→0x10`。最终 mGBA PNG 只有两个可见实例发生变化：

- `(44,73)`：`(148,140,90)→(222,214,148)`；
- `(37,77)`：`(148,140,90)→(222,214,148)`。

独立 Mode-0 renderer 与两张 PNG 逐 RGB exact。基线/候选 guard 均为
`completed/0`、非 degraded，峰值进程树 RSS 分别为 55.87109375 MiB 和
56.1484375 MiB，PGID 与 mGBA listener 均无残留。

profile与独立verifier还逐项绑定三个实例的OAM索引、attr0/1/2、frame、component、
局部像素、屏幕候选坐标和是否进入最终差异。`obj_vram_address=0x06012000`
对应OBJ tile基址256，frame 2/component 0的源tile为8，因此三个实例的attr2低10位
必须严格等于`256+8=264`，不能只复述profile中的tile号。artifact manifest分别保留raw运行证据
生成时的实现哈希与本次复核实现哈希，不再用当前代码哈希覆盖历史生成事实。

输入 checkpoint 的 `0x06016000` 存在旧 group 1 基线缓存，不能宣称“输入前任何
位置都没有该资源”。证据明确记录该旧地址，同时证明候选完整资源在输入前不存在、
目标 `0x06012000` 不含候选；输入后目标区域完整等于各自 relocation ROM 的解压
内容。因此结论依赖本次重新加载，而不是旧 VRAM 缓存。

## 证据与边界

- profile：`sequel/content/battle-effect-pixel-ab/group-01-action5-dust.json`；
- artifact：`artifacts/battle-effect-group1-pixel-ab-v1/`；
- 独立验证：

```bash
python3 tools/verify_battle_effect_pixel_ab_evidence.py \
  --root . --artifact artifacts/battle-effect-group1-pixel-ab-v1
```

本成果使自然最终像素 A/B 代表组达到 4/18。它只签发 group 1、sequence 1、
frame 2 的一个源像素及两个可见自然实例；不外推 sequence 5、其他帧、完整弹道 RNG、
affine/blend/时序/音频或实体 GBA。
