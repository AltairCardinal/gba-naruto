# 角色自然 OAM 与 sprite task 渲染身份（2026-07-30）

## 结论

在已经签发的 91 个自然 `.ss9` checkpoint、222 个角色 OAM 图形命中和
2004 个完整角色源帧之上，现可离线重建角色 sprite task 的当前渲染状态，并将
53 个 OAM 唯一关联到同 checkpoint 中一个 frame-state-consistent task：

- 91/91 个 checkpoint 均成功解析；
- 16×`0x3C` 的 sprite task pool 已由 allocator 代码证明；
- 59 个 OAM 同时满足资源三指针和 task origin；
- 53 个又满足当前 animation/keyframe 选中的 frame，并精确重建完整
  `attr0/attr1/attr2`；
- 6 个资源与原点相关项因当前 frame 不一致而拒绝，不升级为渲染身份；
- 53 个已接受观测覆盖 9 个 checkpoint、8 个 task slot、6 套角色资源。

成果位于 `artifacts/character-runtime-oam-task-bindings-v1/`。导出器为
`tools/export_character_runtime_oam_task_bindings.py`，独立验证器为
`tools/verify_character_runtime_oam_task_bindings.py`。

这里的“渲染身份”只表示：同一帧内的 task 字段按已证明 renderer 公式可生成该
OAM。它不表示已经追踪到实际 OAM allocator index、逐帧 writer 或业务单位 ownership。

## 输入与哈希

- ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 上游 OAM bindings SHA-256：
  `d13782ef403d49c32668c6692c67f826df518dee3619e9cebdae21d94bd86ddf`
- 上游 OAM promotion manifest SHA-256：
  `98d84e6ce9a75b9d47be3efc4e1d7a14924729b3605dfde6b65d4b370f3fdce6`
- 角色视觉 manifest SHA-256：
  `a048eb6b494ceab3cee09ff3db98947ff739e750551e52d6692dc489c4c3db4c`
- 本成果 `bindings.json` SHA-256：
  `4b80e428d1a8292509d05048a29764f593cc56eb59c49b3523d8858e6d2cfd8e`

每个 checkpoint 都记录原始 `.ss9` SHA、完整 task pool SHA 和各 task
record SHA。上游 OAM artifact 还反向绑定角色视觉 manifest；导出器和 verifier
都会检查这条跨 artifact 哈希链。

## task pool 与字段契约

allocator `0x080625A4..0x080626B0` 从末槽 `0x0300597C` 按
`index*0x3C` 反向扫描，证明 task pool 为：

```text
base        = 0x030055F8
record_size = 0x3C
slot_count  = 16
last_slot   = 0x0300597C
```

本成果使用并由代码窗口绑定的字段如下：

| task 偏移 | 类型 | renderer/推进语义 |
|---:|---|---|
| `+0x04/+0x06` | `s16` | OAM 原点 X/Y |
| `+0x10` | `u16` | OBJ tile base |
| `+0x12` | `u8` | OBJ palette bank |
| `+0x14` | `u16` | animation ID |
| `+0x16` | `u16` | keyframe index |
| `+0x18` | `u16` | 当前 keyframe hold timer |
| `+0x1C` | `u32` | frame pointer table |
| `+0x20` | `u32` | animation/timeline pointer table |
| `+0x24` | `u32` | raw 4bpp graphics pointer |
| `+0x28` | `u32` | callback，业务类型未全量命名 |
| `+0x2C` | `u32` | context |
| `+0x30` | `u32` | context index |

component renderer 为 `0x08062982..0x08063278`。它以 `+0x14/+0x16`
选择当前 timeline item，再以其 frame ID 索引 `+0x1C`。flag
`0x00400000` 进入 dynamic OBJ copy：从 `task+0x24 + source_tile_offset`
复制到从 `task+0x10` 起的连续 OBJ tile。

## 接受规则

每条接受结果必须依次通过四层条件：

1. 上游 OAM 已由 OBJ VRAM、尺寸和 palette 差异关联到角色源 component；
2. task 的 frame/animation/graphics 三指针精确对应同一资源；
3. task origin 精确等于上游 component 推导的非 affine origin；
4. task 当前 animation/keyframe 选中的 frame 等于 OAM 源 frame，且 renderer
   公式生成的完整 `attr0/attr1/attr2` 与 OAM 逐字相等。

完整属性重建使用：

```text
x = (task.origin_x + component.x) & 0x1FF
y = (task.origin_y + component.y) & 0xFF

hflip = component.hflip XOR task.flag_0x00008000
vflip = component.vflip XOR task.flag_0x00010000
priority = (task.flags >> 6) & 3

dynamic-copy:
  tile = task.tile_base + preceding_component_output_tiles
normal:
  tile = task.tile_base + component.source_tile_offset

attr0 = y | (shape << 14)
attr1 = x | (hflip << 12) | (vflip << 13) | (size << 14)
attr2 = tile | (priority << 10) | (palette_bank << 12)
```

当前 53 条接受结果都位于 dynamic-copy 的 component 0，所以
`preceding_component_output_tiles=0`。导出器对其他 component fail-closed，
不把这个子集外推成多 component dynamic-copy 已完成。

## 决定性样本

`scenario-46-lineup.ss9` 同时给出三条互不重叠的渲染身份：

| OAM | task slot / address | resource / frame | task origin | `attr0/1/2` |
|---:|---|---|---|---|
| 12 | 11 / `0x0300588C` | 18 / 0 | `(200,96)` | `8028/C0B8/2880` |
| 13 | 13 / `0x03005904` | 9 / 0 | `(120,96)` | `8028/C068/1840` |
| 14 | 15 / `0x0300597C` | 0 / 0 | `(40,96)` | `8028/C018/0800` |

三条结果的坐标、shape/size、tile、palette、priority 和 flip 均由 task 与
source component 重建，而不是从 OAM 反填。

`scenario-41-result.ss9` OAM 0 则证明非零 keyframe 状态：

- slot 15，resource 0；
- animation 0、keyframe 2、hold timer 6；
- 当前选中 frame 2；
- task origin `(100,96)` 加 component `(-16,-56)` 得到 OAM `(84,40)`；
- dynamic-copy tile base 0、palette 0、priority 2；
- 完整结果为 `attr0/1/2=8028/C054/0800`。

## 被拒绝的六条相关项

以下 OAM 能找到资源三指针及 origin 一致的 task，但 task 当前选中 frame 与
OAM 源 frame 不一致，因此只保留为 `frame_state_mismatch`：

- `alternate-character-overview.ss9` / OAM 12；
- `scenario-46-victory-reward.ss9` / OAM 0、1、2；
- `scenario-50-battle-15-round10-objective4-sasuke26.ss9` / OAM 16；
- `skill-list-pre-controller.ss9` / OAM 13。

这六条负结果避免把“同资源、同原点”误报为当前 renderer identity，也说明仍需
继续追踪 OAM writer/分配顺序或 checkpoint 内的更新相位。

## presentation owner 旁系

另有一套代码证明的 presentation owner family：

- callback `0x0807AC40..0x0807ADB2`；
- selector `0x0807AE04..0x0807B278`；
- constructor `0x0807B444..0x0807B632`；
- variant constructor `0x0807B6E0..0x0807B758`；
- owner table `0x02026BE0 + 0xC4 + slot*4`；
- owner `+0x20/+0x24` 为 Q8.8 X/Y；
- task `+0x2C/+0x30` 为 owner context 和 offset index；
- signed offset table 为 `0x0853E000`。

它证明另一类演出对象如何向 task 提供坐标，但当前没有证据证明它就是上述
53 条 field task 的 owner。artifact 因而保持
`presentation_owner_family_linked_to_bound_field_tasks=false`。

## 证据边界

本成果证明：

- 91 个 tracked checkpoint 的 task pool 可以确定性重建；
- task pool 布局、资源字段、动画状态和 renderer 坐标/属性公式有代码证据；
- 53 条自然 OAM 具有唯一、frame-state-consistent 的 task renderer identity；
- 完整 `attr0/attr1/attr2` 可从 task 与源 component 逐位重建。

本成果不证明：

- task 到实际 OAM allocator index 或逐帧 writer 的因果 trace；
- 62×9 全部角色槽都有自然 task 样本；
- 多 component dynamic-copy 的输出 tile 累加已由自然样本覆盖；
- presentation owner family 与 field task 相同；
- unit ownership、camera/viewport、window/blend 或最终屏幕合成；
- 所有 priority、affine 和 palette transform 分支。

## 验证

```bash
python3 -m unittest \
  tests.test_export_character_runtime_oam_task_bindings -v

python3 tools/verify_character_runtime_oam_task_bindings.py \
  --root . \
  --bindings artifacts/character-runtime-oam-task-bindings-v1/bindings.json
```

- 专用测试：8 项通过；
- 独立 verifier：91 checkpoints、53 bindings、`errors=[]`；
- 测试包含 tile base、priority、dynamic-copy flag、shape/size、flip 和 artifact
  hash 的负向篡改；
- verifier 不导入 exporter，而是独立重读 ROM、父 artifact、视觉 manifest 和
  91 个 `.ss9` 后重建结果；
- 全程未启动 mGBA，未新增 ROM、save-state、截图或 Butano 文件。
