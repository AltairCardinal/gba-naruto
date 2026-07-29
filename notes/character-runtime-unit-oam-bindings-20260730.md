# 角色运行时单位格坐标与 OAM 原点绑定（2026-07-30）

## 结论

在已经签发的 91 个自然 `.ss9` checkpoint 和 222 个角色 OAM 图形命中之上，
现可对单位池格坐标、BG0 scroll 与非 affine 角色原点候选建立统一的基础模型：

```text
origin_x ≡ grid_x * 32 - BG0HOFS + 16  (mod 512)
origin_y ≡ grid_y * 16 - BG0VOFS + 8   (mod 256)
```

横向使用 OBJ `attr1` 的 9-bit 坐标回绕；纵向使用 OBJ `attr0` 的 8-bit
坐标回绕。纵向不能按 BG scroll 的 9-bit 域比较，因为最终 OBJ Y 字段只有 8 bit。

在 222 个 OAM 观测中：

- 220 个能在同一 checkpoint 的单位槽 1–12 找到相同 character ID；
- 208 个能由上述二维模型唯一落到一个单位槽；
- 12 个只有一个同 character live unit，但存在非零演出偏移；
- 2 个没有同 character live unit；
- 0 个需要在多个单位槽之间保留基础锚点歧义；
- 单位 OAM ownership 仍为 0 个已证明。

成果位于 `artifacts/character-runtime-unit-oam-bindings-v1/`。导出器为
`tools/export_character_runtime_unit_oam_bindings.py`，独立验证器为
`tools/verify_character_runtime_unit_oam_bindings.py`。

## 输入与哈希边界

- ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 上游 OAM bindings SHA-256：
  `d13782ef403d49c32668c6692c67f826df518dee3619e9cebdae21d94bd86ddf`
- 本成果 `bindings.json` SHA-256：
  `346310eecece5053f3b7a23f7620104f2980ecadb3e36d869768c78eb7aca0f3`
- 单位池物理基址：`0x020240C0`
- 单位记录大小：`0x1D4`
- 原始哈希区域：slot 0–12，共 `13 * 0x1D4 = 0x17C4` 字节
- live candidate：slot 1–12 且 record `+0 != 0`
- character ID：record `+0`
- grid X/Y：record `+0xC4/+0xC5`

每个 checkpoint 都绑定原始 `.ss9` SHA、上游 checkpoint canonical SHA、
完整 `0x17C4` 单位池 SHA 和每条 live record SHA。下游结果不能在不触发 verifier
失败的情况下改写坐标、角色、槽位或空间候选。

## 模型选择证据

模型不是从单个 scenario 41 样本猜出。导出器与独立 verifier 都对 220 个
存在 live character candidate 的 OAM 观测重新枚举：

- X 像素步长 `1..64`、中心偏移 `0..511`；
- Y 像素步长 `1..32`、中心偏移 `0..255`；
- 每个模型按“该 OAM 的任一 source-origin × same-character live-unit pair
  命中”计一次，避免重复角色或 source ambiguity 放大计数。

结果：

| 轴 | 最优模型 | 命中 | 次优模型 | 命中 |
|---|---|---:|---|---:|
| X | `32*x + 16` | 209/220 | `16*x + 80` | 56/220 |
| Y | `16*y + 8` | 208/220 | `32*y + 200` | 54/220 |
| 联合 | `32*x+16, 16*y+8` | 208/220 | — | — |

BG0HOFS/BG0VOFS 在比较前按各自硬件寄存器读取，最终投影分别进入 mod 512
和 mod 256。

曾有只读复核从 scenario 41 的单个 `grid_x=4` 样本误推
`24*x+48`。该样本同时满足 `32*4+16` 和 `24*4+48`，属于欠约束输入。
跨全部 X 值枚举后，错误模型只有 40/220 个 X 命中、37/220 个二维命中，
已撤回，不进入产物。

## 决定性样本

### Scenario 41 玩家回合

`scenario-41-player-turn.ss9`：

- BG0 scroll `(24,88)`；
- slot 1 / character 1 / grid `(4,10)`；
- OAM 11 的 source-origin candidate `(120,80)`；
- `4*32-24+16=120`；
- `10*16-88+8=80`。

### Scenario 46 开战

`scenario-46-battle-start.ss9` 的 BG0 scroll 为 `(248,168)`：

| OAM | character | unit slot | grid | origin |
|---:|---:|---:|---|---|
| 12 | 1 | 1 | `(11,15)` | `(120,80)` |
| 11 | 2 | 2 | `(9,15)` | `(56,80)` |
| 10 | 3 | 3 | `(13,15)` | `(184,80)` |
| 8 | 41 | 8 | `(7,22)` | `(-8,192)` |

character 41 在该 checkpoint 同时存在 slots 4–8；上游 source 仍是
`ambiguous_best_source`，但基础空间锚点只命中 slot 8。X 原点 `-8`
等价于 raw 9-bit `504`。

这只签发 `unique_base_grid_anchor_observation`，不把空间一致性改名为
constructor/selector 已追踪的 ownership。

### Scenario 50 重复角色

`scenario-50-battle-15-round9-objective16-sasuke46.ss9` 同时存在五个
character 35 单位，slots 5–9。五个 OAM 的基础空间候选分别唯一命中：

| OAM | unit slot |
|---:|---:|
| 11 | 6 |
| 13 | 9 |
| 14 | 5 |
| 15 | 8 |
| 19 | 7 |

这排除了按 OAM 顺序或同角色数量机械配对；每个结果都由 grid、scroll 和
source-origin 的模坐标等式独立得到。

## 非基础偏移与负边界

12 个观测不满足基础模型，但都只有一个同 character live unit，因此产物只记录
`observed_offset`，不解释其业务语义：

| checkpoint / OAM | delta `(x,y)` |
|---|---|
| scenario-41-attack-confirmation / 9 | `(32,-32)` |
| scenario-41-target-select / 11 | `(32,-32)` |
| scenario-41-combat-dialogue / 1 | `(10,8)` |
| scenario-41-combat-dialogue / 2 | `(-60,-8)` |
| scenario-41-result / 0 | `(-108,24)` |
| scenario-46-lineup / 12 | `(-8,-56)` |
| scenario-46-lineup / 13 | `(-24,-72)` |
| scenario-46-lineup / 14 | `(-136,-56)` |
| scenario-46-south-approach-action-menu / 10 | `(0,48)` |
| scenario-46-victory-reward / 0 | `(132,40)` |
| scenario-46-victory-reward / 1 | `(12,24)` |
| scenario-46-victory-reward / 2 | `(-76,8)` |

`alternate-character-overview.ss9` OAM 12 与
`skill-list-pre-controller.ss9` OAM 13 有角色源图形，但 checkpoint 中没有
同 ID live unit，因此显式记录为 `no_live_character_candidate`。

## 证据边界

本成果证明：

- 当前 91 个 checkpoint 的单位池原始记录可重复读取与哈希绑定；
- OAM source character 与 live unit character ID 的完整交集；
- 32×16 grid、中心偏移 `(16,8)`、BG0 scroll 与 OBJ 坐标回绕构成当前语料的
  唯一最优基础空间模型；
- 208 个观测的基础空间候选可唯一落到单位槽；
- 重复 character ID 不需要用 OAM 顺序消歧。

本成果不证明：

- OAM 由哪个 constructor、selector 或 task writer 创建；
- 非零 offset 是动作、对白、lineup、结果页还是其他演出状态的通用公式；
- camera/offset writer 的逐帧调度；
- unit animation state 到 source frame 的全量映射；
- 所有 live unit 都在当前 checkpoint 语料中可见；
- BG/OBJ/window/blend 的最终 screen-space 像素合成；
- unit OAM ownership 已闭合。

因此 artifact 中所有 `unit_ownership` 均为 `null`，
`screen_space_composition_complete` 保持 `false`。

## 验证与资源占用

```bash
python3 -m unittest \
  tests.test_export_character_runtime_unit_oam_bindings -v

python3 tools/verify_character_runtime_unit_oam_bindings.py \
  --root . \
  --bindings artifacts/character-runtime-unit-oam-bindings-v1/bindings.json
```

- 专用测试：14 项通过；
- 独立 verifier：91 checkpoints、222 observations、`errors=[]`；
- 确定性重建 SHA 与已提升 artifact 完全一致；
- 纯重建墙钟约 0.68 秒；
- `maximum resident set size` 39,387,136 bytes；
- 0 swap；
- 未启动 mGBA，未新增 ROM、save-state、截图或 Butano 文件。
