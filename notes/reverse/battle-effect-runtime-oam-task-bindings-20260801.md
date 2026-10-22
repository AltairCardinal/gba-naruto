# 战斗特效运行时 task/OAM 身份绑定（2026-08-01）

## 结论

在不启动 mGBA 的前提下，`battle-effect-runtime-oam-task-bindings-v1` 复用现有
93 个 tracked checkpoint 与 5 个 supplemental state，逐状态解析完整
128×`0x3C` sprite task pool、active dispatcher、运行时坐标偏移表、shadow OAM、
hardware OAM 和 VBlank 提交相位。

现有 tracked corpus 中唯一含战斗特效 OAM 内容身份的
`scenario-50-battle-15-escort-12hp-player-turn.ss9` 同时存在三个活动特效 task：

| task slot | dispatch ordinal | group/frame | OAM index | anchor | runtime Y offset |
|---:|---:|---|---:|---|---:|
| 113 | 12 | 1 / 6 | 17 | `(150,33)` | 24 |
| 114 | 13 | 1 / 6 | 18 | `(146,22)` | 24 |
| 115 | 14 | 1 / 6 | 19 | `(137,33)` | 24 |

frame 6 / component 0 的局部坐标为 `(-8,-8)`。对三个实例分别计算
`anchor + follow_delta + component - runtime_offset`，再按 GBA 坐标域取低位，
精确得到 OAM 的 `(142,1)`、`(138,246)`、`(129,1)`。同一计算还从 task tile
base 768、component tile 24、palette bank 12 和 priority bits 完整重建三条
`attr0/attr1/attr2`，与父 OAM 内容记录、shadow OAM 和 hardware OAM 全部一致。

因此 tracked 父记录的 3/3 个唯一、非 affine 特效 OAM 已从“内容相同”升级为
`task current frame → renderer attributes → OAM` 的严格身份。dispatch ordinal
为 12/13/14，而 OAM index 为 17/18/19，也实证两者不是同一个索引。

## 资源身份纠正

角色 task 目录使用 `(frame table, animation table, graphics)` 三指针识别资源，
但该规则不能直接用于战斗特效。真实快照中：

- group 1 静态 graphics 指针是 `0x083406F0`；
- tracked 三个 group 1 task 的 `+0x24` 分别是 `0x081592F4`、
  `0x081592F4`、`0x081606A0`；
- supplemental group 1 的部分 task `+0x24` 为零。

`+0x24` 是动态 tile source 或动作数据地址，不是稳定的静态 group graphics
身份。18 组的 `(+0x1C definition_pointer_table, +0x20
animation_pointer_table)` 指针对彼此唯一，因此新目录只用该二元组识别 group，
并把 `+0x24` 独立保存为运行时字段。若沿用角色三指针规则，当前样本会得到零命中。

## 全量批处理结果

- 93/93 tracked checkpoint 与 5/5 supplemental state 均成功解析；
- 98/98 active dispatcher pointer list 均由 task flags/sort-y 精确重建；
- tracked 识别 3 个活动特效 task，覆盖 group 1；
- supplemental 识别 9 个活动特效 task，覆盖 groups 1/2/5/11/14；
- 98 个状态中 82 个 shadow/hardware OAM 全缓冲一致；
- 另外 16 个存在差异，全部同时满足 pending flag 为 1/2 且 PC 位于代码证明的
  `0x08061126..0x0806112C` 等待窗口；未解释提交差异为 0；
- tracked 3/3 父 OAM match 获得严格 task 身份；supplemental 只保留 task/frame/OAM
  相位观察，不混入 tracked 自然分母。

## 独立验证

独立 verifier 不导入导出器。它重新读取 ROM、战斗特效动画 manifest、OAM 父
artifact 和全部 98 个 savestate，独立重建 task 字段、dispatcher、runtime offset、
提交相位、完整 renderer attr 和 summary。测试明确拒绝：

- 把 runtime offset Y 从 24 篡改为 0；
- 把已绑定 task 的 group 1 篡改为 group 2；
- producer、verifier、测试或 payload 哈希不一致。

定向 13 项测试约 1.3 秒，最大 RSS 约 30 MiB，swap 0。该流程只顺序读取现有小型
状态和 JSON，不生成 PNG，不创建大量小文件，也未启动 mGBA。

## 复现

```bash
python3 tools/export_battle_effect_runtime_oam_task_bindings.py \
  --root . \
  --output artifacts/battle-effect-runtime-oam-task-bindings-v1/bindings.json
python3 tools/verify_battle_effect_runtime_oam_task_bindings.py \
  --root . \
  --bindings artifacts/battle-effect-runtime-oam-task-bindings-v1/bindings.json
python3 -m unittest \
  tests.test_export_battle_effect_runtime_oam_task_bindings \
  tests.test_verify_battle_effect_runtime_oam_task_bindings
```

## 边界与下一步

本成果不宣称：

- group 2 affine matrix slot、double-size 或多 component task 已闭合；
- dynamic-copy 多 component 的逐组件输出 tile 累加已运行时签发；
- dispatch ordinal 就是 allocator/writer OAM index；
- supplemental task current frame 与 hardware OAM 的序列化相位差已经还原为精确
  历史帧；
- 未观察的 13 组、全部 frame、RNG、blend/window/audio 或实体 GBA 已完成。

下一步应从现有可恢复确认页批量生成“输入前、renderer 后、VBlank 后”三相快照，
先覆盖当前五组的 frame-phase，再用动作/sequence 目录自动选择未观察的 13 组；不得
逐组恢复手工导航，也不得把 supplemental 单帧猜测升级为 writer identity。
