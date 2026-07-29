# 角色自然 OAM 与 sprite task 渲染身份（2026-07-30）

## 结论

在已经签发的 91 个自然 `.ss9` checkpoint、222 个角色 OAM 图形命中和
2004 个完整角色源帧之上，现可离线重建角色 sprite task 的当前渲染状态，并将
53 个 OAM 唯一关联到同 checkpoint 中一个 frame-state-consistent task：

- 91/91 个 checkpoint 均成功解析；
- 128×`0x3C` 的全局 sprite task pool 已由 allocator 与 dispatcher 代码证明；
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
  `59fcb484fcba0a80c6d3575d28896be13e070215c12bfd36dd0e3fc948a1c975`

每个 checkpoint 都记录原始 `.ss9` SHA、完整 task pool SHA 和各 task
record SHA。上游 OAM artifact 还反向绑定角色视觉 manifest；导出器和 verifier
都会检查这条跨 artifact 哈希链。

## task pool 与字段契约

allocator `0x080625A4..0x080626B0` 从全局 slot 127
`0x0300597C` 按 `index*0x3C` 反向扫描；dispatcher
`0x080627B0..0x0806291A` 也遍历 index 0–127，并把活动 task 指针写到
`0x030059B8`。因此全局 task pool 为：

```text
base        = 0x03003BB8
record_size = 0x3C
slot_count  = 128
last_slot   = 0x0300597C
```

`0x030055F8` 只是全局 slot 112，不能作为 task pool 基址。本成果接受的 53 条
角色观测均落在全局 slots 120–127；每个 checkpoint 的 pool SHA 仍覆盖全部
128 条记录，而不只哈希角色恰好占用的尾部。

dispatcher 随后以稳定插入排序生成活动指针表。比较顺序由
`0x0806288C..0x080628D4` 锁定为：

1. flags `& 0xC0` 升序；
2. flags `& 0x300` 升序；
3. `0x40000` depth-sort task 在前；
4. 两者都设置 `0x40000` 时，按 task sort-y 降序。

离线重放这段 comparator 后，91/91 个 checkpoint 的完整活动指针顺序均与
`0x030059B8` 逐项一致，共复核 741 个活动指针，而不只是检查集合成员或
pool slot 顺序。`scenario-46-lineup.ss9` 的实际顺序为
`[121,123,125,127,122,124,126]`，说明 dispatcher ordinal 不能用全局 slot
序号替代。

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
| 12 | 123 / `0x0300588C` | 18 / 0 | `(200,96)` | `8028/C0B8/2880` |
| 13 | 125 / `0x03005904` | 9 / 0 | `(120,96)` | `8028/C068/1840` |
| 14 | 127 / `0x0300597C` | 0 / 0 | `(40,96)` | `8028/C018/0800` |

三条结果的坐标、shape/size、tile、palette、priority 和 flip 均由 task 与
source component 重建，而不是从 OAM 反填。

`scenario-41-result.ss9` OAM 0 则证明非零 keyframe 状态：

- 全局 slot 127，resource 0；
- animation 0、keyframe 2、hold timer 6；
- 当前选中 frame 2；
- task origin `(100,96)` 加 component `(-16,-56)` 得到 OAM `(84,40)`；
- dynamic-copy tile base 0、palette 0、priority 2；
- 完整结果为 `attr0/1/2=8028/C054/0800`。

## dispatcher、shadow OAM 与硬件 OAM

driver `0x08062924..0x08063338` 在 `0x08062968` 调用 dispatcher，随后把输出
指针初始化为 shadow OAM `0x0300027C`，按活动指针表调用 renderer，最后把
未使用条目填成 disabled OBJ，直到 `0x0300067C`。该完整代码窗口 SHA-256 为
`5e29f07126eb06c69170c5c15a2ab28fe0e1ad86ffdd85f6dfbd4601defbee36`。

批量读取同一批 91 个 checkpoint 得到：

- 80/91 的 1024-byte shadow OAM 与硬件 OAM `0x07000000..0x07000400`
  完全一致；
- 其余 11 个只在部分条目不同，按快照帧相位差原样记录两域哈希和差异索引；
- 53/53 条已接受角色绑定，在各自 OAM index 上的完整 8-byte shadow entry
  与硬件 entry 一致，且前三个 halfword 同 renderer 预测的 attr0/1/2 一致；
- 53/53 个 task 在活动指针表中均只有一个 dispatch ordinal。

这形成 `task frame state → dispatcher membership → renderer prediction →
shadow/hardware OAM 同索引观测` 的同快照证据链，但不把 ordinal 冒充 writer
index。最直接的反例是 lineup：dispatch ordinals `1/2/3` 对应观察 OAM
`12/13/14`，因为前序 task 可产生多个、零个或复制的 OBJ。当前没有逐指令追踪
renderer cursor，也没有完整重建所有前序 task 的 component 可见性，因此
`task_to_oam_writer_or_allocation_index_traced` 和
`shadow_to_hardware_copy_schedule_traced` 继续保持 false。

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
- 91/91 个活动 pointer list 的完整排序可以从 pool 与 comparator 重建；
- task pool 布局、资源字段、动画状态和 renderer 坐标/属性公式有代码证据；
- 53 条自然 OAM 具有唯一、frame-state-consistent 的 task renderer identity；
- 完整 `attr0/attr1/attr2` 可从 task 与源 component 逐位重建；
- 53/53 个接受项在 shadow OAM 与硬件 OAM 同索引逐字节一致。

本成果不证明：

- task 到实际 OAM allocator index 或逐帧 writer 的因果 trace；
- shadow OAM 到硬件 OAM 的逐帧 copy schedule；
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

- 专用测试：11 项通过；
- 独立 verifier：91 checkpoints、53 bindings、`errors=[]`；
- 测试包含 dispatcher comparator 分支、sort-y 字段选择、活动顺序、shadow
  entry、tile base、priority、dynamic-copy flag、shape/size、flip 和 artifact
  hash 的负向篡改；
- verifier 不导入 exporter，而是独立重读 ROM、父 artifact、视觉 manifest 和
  91 个 `.ss9` 后重建结果；
- 全程未启动 mGBA，未新增 ROM、save-state、截图或 Butano 文件。
