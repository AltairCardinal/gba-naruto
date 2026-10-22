# 角色战斗视觉的自然 OAM/VRAM 批量绑定（2026-07-30）

## 结论

仓库已有的全部 91 个 tracked `.ss9` checkpoint 现在都能离线、确定性地扫描，
无需重新启动 mGBA。批量分析把自然运行时 OAM 对象的尺寸和 OBJ VRAM 图形字节精确
绑定到 `character-battle-visuals-v1` 的源 component，并用运行时 OBJ palette 与
源 BGR555 palette 的差异数处理同图形候选歧义。

成果位于：

- `artifacts/character-runtime-oam-bindings-v1/bindings.json`
- `tools/export_character_runtime_oam_bindings.py`
- `tools/verify_character_runtime_oam_bindings.py`

当前批次得到：

| 项目 | 数量 |
|---|---:|
| tracked checkpoint | 91 |
| 成功解析 / 1D OBJ mapping | 91 / 91 |
| 活动 OAM 对象 | 1211 |
| 命中角色源 component 的 OAM | 222 |
| 含命中的 checkpoint | 57 |
| 唯一最优源绑定 | 133 |
| 明确保留歧义的最优绑定 | 89 |
| palette 完全相同 | 11 |
| palette 仅一色不同 | 194 |
| palette 差异不超过一色 | 205 |

最优候选覆盖 8 个可证明的角色 ID
`[1,2,3,30,33,35,41,55]`、47 个去重角色视觉 resource、146 个
`(resource, frame)` 组合和全部 9 个 visual slot。这里的覆盖只描述现有 checkpoint
自然观察值，不代表其他 54 个角色或全部 558 个槽已经有运行时样本。

## 绑定规则

每个 checkpoint 均绑定容器 SHA-256、mGBA state version，以及实际用于判断的
IO/PRAM/OAM/VRAM 四个 region 的 size 和 SHA-256。只有 `DISPCNT bit 6=1`
的一维 OBJ mapping 才进入连续 tile 匹配。

对每个合法活动 OAM：

1. 非 affine 且 `attr0 bit 9=1` 的 disabled 项跳过；affine 的 bit 9 保留为
   double-size。
2. 从 attr0/1 解码 12 种合法 shape/size；shape 3 失败关闭。
3. 当前角色源为 4bpp，因此 8bpp 对象不参与角色绑定。
4. 以
   `VRAM[0x10000 + tile_index*32 : + width*height/2]`
   读取运行时 OBJ 图形。
5. 只有尺寸和整段图形 SHA-256 都相同的源 component 才成为候选。
6. 以 attr2 palette bank 读取
   `PRAM[0x200 + bank*32 : +32]`，逐个 little-endian BGR555 颜色比较。
7. palette 差异数最少的候选为 best；单个 best 标记
   `unique_best_source`，同分多个则保留全部并标记
   `ambiguous_best_source`，不按坐标、文件顺序或截图观感猜测。

导出器记录 `screen_x/screen_y`、priority、palette bank、OAM 原始 attr 和
显示/窗口/blend 寄存器。非 affine 情况下还记录
`screen coordinate - component-local coordinate`，字段明确命名为
`non_affine_task_origin_candidate`；它只是代数候选，不冒充已经 trace 到 writer 的
task anchor。

## 代表性自然样本

`scenario-41-player-turn.ss9`
（SHA-256 `ba411e…c436171`）的 OAM 11 为：

- attr0/1/2：`0x8018 / 0xC068 / 0x0800`
- 屏幕坐标 `(104,24)`，32×64，priority 2，OBJ palette bank 0；
- 唯一绑定到 resource 0 / frame 4 / component 0，即角色 1、visual slot 0；
- 源 tile offset 为 128，但运行时 OAM tile index 为 0；
- 源 palette index 15 `0x0421` 在运行时为 `0x7FE0`，其他 15 色相同；
- 代数 origin candidate 为 `(120,80)`。

`scenario-41-first-movedone-facing.ss9` 在相同 OAM 坐标和 origin candidate 下，
唯一绑定到同一 resource 的 frame 5、源 tile offset 160。两条自然样本共同证明角色
帧会被重定位到动态 OBJ VRAM；不能把 attr2 tile index 直接解释为 ROM 源 tile
offset。

`scenario-41-attack-confirmation.ss9` 同时绑定角色 1 和角色 30；
`scenario-46-battle-start.ss9` 同时绑定角色 1、2、3、41。后者的角色 41 对象保留
三个同分 best source（同一角色的 slot 0/4 帧候选），没有强行压成唯一帧。

本批次 194 个“一色不同”命中全部只改变 palette index 15；另有 16 个 best
palette 差 12 色、1 个差 13 色。这把选择/状态相关 palette 变换从笼统缺口缩小为
可逐 checkpoint 审计的具体差分，但尚未给这些颜色变化命名业务语义。

当前 222 个命中都观察为 normal OBJ、priority 2。该事实只对当前自然 checkpoint
语料成立，不能升级为全角色、全动画的不变量。

## 独立验证与范围

独立 verifier 不导入导出器。OAM 的 active/shape/坐标/flip/tile/priority/palette
字段复用本成果之前已经存在、另有手工 fixture 测试的
`tools/butano/analyze_scenario_41_gpu.py::decode_gpu`，不复制导出器的 OAM
遍历实现；随后再独立：

- 枚举 Git tracked checkpoint；
- 严格解析 `.ss9` PNG/CRC/zlib/GBA state；
- 验证 base ROM 与静态角色 artifact；
- 重建全部源 component 图形索引；
- 重解 OAM、VRAM 和 BGR555 palette；
- 对完整 JSON 做精确比较。

测试同时覆盖已知 Naruto 样本、多角色与歧义样本、GPU region 哈希、两次字节级
确定性导出、CLI 单文件写入，以及篡改 checkpoint SHA 后 verifier 必须失败。另以
既有 GPU decoder 对 91 个 checkpoint 的 1211 个 active OAM 和全部 222 个命中字段
逐项交叉检查，并手工从 Naruto checkpoint 读取 OBJ VRAM slice、源 graphics slice、
OBJ PRAM bank 和源 palette，确认 tile 逐字节相同且唯一颜色差为
`index 15: 0x0421→0x7FE0`。

本成果已闭合的是“现有自然 checkpoint 中，哪些 OAM 图形来自哪些角色源
component，以及观察到的坐标、priority 和 palette 差分”。它仍不证明：

- 自然 constructor/selector/task 的完整 trace；
- 62×9 全槽的自然运行时覆盖；
- camera/offset writer 的逐帧调度；
- BG/OBJ priority tie、window、blend 的最终像素合成；
- 全部角色 screen-space composition 已完成。

因此 `bindings.json` 的 `screen_space_composition_complete` 保持 `false`。

## 复现

```bash
python3 tools/export_character_runtime_oam_bindings.py \
  --root . \
  --output build/experiments/active/<task>/<run-id>/final/bindings.json

python3 tools/verify_character_runtime_oam_bindings.py \
  --root . \
  --bindings artifacts/character-runtime-oam-bindings-v1/bindings.json

python3 -m unittest \
  tests.test_export_character_runtime_oam_bindings -v
```

生产导出和独立验证均为离线处理。一次纯重建实测 0.60 秒、maximum RSS
34,156,544 bytes、0 swap；未启动 mGBA、未产生新 ROM、快照或进程树，也未触碰
Butano 工作树。
