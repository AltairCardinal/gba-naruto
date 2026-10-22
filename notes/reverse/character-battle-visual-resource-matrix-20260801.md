# 角色战斗视觉 palette/component/timeline 自然像素矩阵（2026-08-01）

## 结论

`artifacts/character-battle-visual-resource-matrix-v1/` 将角色 battle bundle 中除
graphics 像素以外的三类核心可编辑字段推进到修改 ROM 后的自然最终像素 A/B：

- palette：OBJ palette index 1 的 BGR555 低字节 `0x84→0x85`；
- component geometry：frame 3/component 0 的 `x=-16→-15`；
- animation timeline：animation 1/keyframe 0 的 `frame_id=3→4`。

三项均使用 resource 0（character 1／鸣人 visual slot 0）和同一个已验收
`scenario-41-start-row.ss9`。baseline 与三个 candidate 均为独立 mGBA 运行，只输入
一次 A（frame 5 down、frame 13 up），在 frame 80 到达 battle 41。

## 单因素 ROM

`tools/build_character_battle_visual_resource_matrix.py` 复用生产
`character_battle_bundle` 迁移器，完整提供原 2,004 帧和 784 条 animation 的 authored
结构。四份 16 MiB ROM 都把 resource 0 bundle 放在
`0x08600000..0x08604B60`，descriptor row 0 固定为：

```text
frame table  0x08604A00
animation    0x08604B30
graphics     0x08600020
palette      0x08600000
```

四份 ROM 的 allocation/descriptor patch topology 完全相同。相对 baseline 的完整
ROM 差异分别只有：

| candidate | ROM offset | bundle offset | before → after |
|---|---:|---:|---|
| palette | `0x600002` | `0x0002` | `84→85` |
| component | `0x60486C` | `0x486C` | `F0→F1` |
| timeline | `0x604A64` | `0x4A64` | `03→04` |

## 运行结果

### Palette

- 完整 EWRAM/VRAM/IO/OAM 与 baseline 相同；
- 完整 PRAM 只有 `0x05000202: 84→85`；
- OAM entry 0 和 task 完全不变；
- 最终 PNG 有 268 个像素变化，边界 `[109,25,131,68]`；
- 268 个像素全部为 RGB `(33,33,33)→(41,33,33)`。

这把 bundle palette index 1、运行时 OBJ palette bank 0/index 1 和所有实际可见的
index-1 像素闭合为同一条因果链。

### Component geometry

- 完整 EWRAM/VRAM/IO/PRAM 与 baseline 相同；
- 完整 OAM 只有 `0x07000002: 68→69`，即 entry 0 attr1
  `0xC068→0xC069`；
- task、动态 OBJ 1 KiB graphics 与 palette 均不变；
- 最终 PNG 有 634 个像素变化，边界 `[108,17,134,68]`。

源 component `x` 增加 1 后，唯一硬件状态变化是该 OBJ 的 screen X 增加 1；最终
差异是同一角色图形相对不变背景右移一像素后的精确合成结果。

### Animation timeline

frame 80 的全局 task slot 127（`0x0300597C`）在四边均保持：

- animation ID 1；
- keyframe index 0；
- hold timer 0；
- frame/animation/graphics pointers
  `0x08604A00/0x08604B30/0x08600020`。

baseline timeline 的当前 keyframe 选择 frame 3，其 component 使用 source tiles
`96..127`；candidate 把同一 keyframe 改为 frame 4，使用 source tiles `128..159`。
verifier 从 task 的 animation table pointer `0x08604B30` 按 animation ID 1 读取
`table[1]=0x08604A64`，再按 keyframe index 0 解引用 `<frame_id,hold=8>`，不直接把
`0x4A64` 当作未经证明的常量。
两边 `0x06010000..0x060103FF` 的动态 OBJ 1 KiB 均逐字节等于各自 ROM 源帧：

- frame 3 SHA-256：
  `deb659b4689777837b319752e36ae387ee8b7264fab001d099415f5e717c207b`；
- frame 4 SHA-256：
  `568a5b980d4f858cc783b47303d3ffd29d8d2e23e89bb83697107cb51473aed8`。

完整 EWRAM/IO/PRAM/OAM 不变，VRAM 有 394 个 byte 不同；最终 PNG 有 616 个像素
变化，边界 `[107,17,133,65]`。这证明 timeline byte 选择了另一源帧，不是运行抖动
或 OAM 几何变化。

## 证据和抗篡改

artifact 只保留四份 bundle、frame 80 savestate/PNG、audit/sentinel、内外两层 guard、
build manifest 和汇总 evidence，共 31 个文件、约 584 KiB；四份 16 MiB ROM 只在
临时实验归档中保存，不进入 Git。

独立 verifier 不导入 builder、exporter 或 bundle importer。它从基准 ROM 和 bundle
重建四份完整 ROM，验证单因素差异、task/frame pointer、1 KiB dynamic-copy 来源、
五个完整内存域、OAM、最终像素集合、输入父快照、mGBA binary/build manifest、Lua、
audit、两层 guard 和文件全集。负测覆盖重签后的三个 bundle、PRAM、OAM、VRAM、task、
animation table pointer、截图、pixel evidence、audit/guard、child PID、run ID、outer
command 参数配对、父快照、build、scope 与 verifier 声明篡改。原始四边
audit/sentinel/guard/outer-guard 自身哈希也由独立 verifier 固定，不能通过同步重签
manifest 与 runtime-evidence 改写运行身份。

最终加固版导出峰值 tree RSS 为 `86.84765625 MiB`；12项构建/证据测试峰值为
`137.3515625 MiB`，覆盖既有graphics像素证据、bundle迁移、视觉导出、task绑定和
三类旧写回的71项相关回归峰值为`156.01171875 MiB`。三组均经共享heavy lock、
`completed/0`、非 degraded。额外的`test_verify_rom_expansion_profile`仍有1项既有
失败：其artifact固定的`tools/patch_safety.py`和`tools/build_mod.py`旧哈希与当前
HEAD不符；这两个文件不在本里程碑改动中，未把该陈旧父成果混入当前提交。

## 边界

本成果只签发 resource 0 在当前自然 battle 41 入场帧的 palette、frame 3 component X
和 animation 1/keyframe 0 frame selection。它不外推至其余 249 个资源、342 个逻辑
槽、全部 component、关键帧推进时序、完整动作/特效组合、camera/window/blend 或实体
GBA 输出，Goal 保持 active。
