# 角色场景视觉包稳定 BG+OBJ 合成（2026-07-30）

## 结论

`0x0808C214..0x0808C4CB` 控制器的两个直接调用 mode 已闭合到稳定帧的
240×160 BG+OBJ 合成：

- mode 0：main pack 0–3，共 4 张；
- mode 1：main pack 0–7，共 8 张；
- exit：两种 mode 均以 pack 8 为背景，分别以 pack 4 / pack 8 为 OBJ，共 2 张；
- 合计 14 张，9/9 个 `scene-visual-packs-v1` 源 pack 均至少出现一次。

成果位于 `artifacts/scene-visual-composites-v1/`。这里的“稳定”只表示 motion
callback 不再改 task 坐标、控制器尚未销毁该 task 的保持区间；不包含进入/退出的
逐 tick 中间帧、presentation overlay、运行时逐像素等价、实体 GBA 输出或自然语言
场景名称。

## 主场景坐标

spawner `0x0808C0B4..0x0808C163` 固定：

| mode | task 初始 X | task 初始 Y | task 目标 Y |
|---|---|---|---|
| 0 | `[192,160]` | `[-160,240]` | `[16,64]` |
| 1 | `[48,16]` | `[-160,240]` | `[16,64]` |

task index 同时写入 `task+0x34`，并作为 `task+0x38` 的初始 counter，因此两个
task 的 counter 分别从 0、1 开始。callback `0x0808C030..0x0808C077` 每次先把
counter 加一，只在新值 `<=31` 时更新；第 32 次起不再写坐标。它把
`counter<<7` 交给 `0x08090AA8`，后者以 Q12 计算，并对负数加 `0xFFF` 后算术
右移，因此是向零截断：

```text
task 0: -160 + trunc((16 - -160) * 31 / 32) = 10
task 1:  240 + trunc((64 -  240) * 31 / 32) = 70
```

所以稳定坐标为：

- mode 0：`[(192,10),(160,70)]`；
- mode 1：`[(48,10),(16,70)]`；
- 单 task pack 只使用 index 0。

旧未提交实现错误地按 mode 把全部对象写成 Y=16/64，并误以为插值会到达目标值；
失败测试先固定该反例，再由修正实现通过。

## exit 坐标

controller `0x0808C464..0x0808C480` 调 allocator 时：

- `r3=240` 写入 `task+4`，即初始 X；
- 第一个栈参数 `128` 写入 `task+6`，即初始 Y；
- `task+0x38=0`。

exit callback `0x0808C07C..0x0808C0B3` 保留 Y=128，只将 X 从 240 插值到 80，
同样最后一次写入发生在 counter 31：

```text
240 + trunc((80 - 240) * 31 / 32) = 85
```

故稳定 task 坐标是 `(85,128)`。旧未提交实现使用 `(0,128)`，没有 ROM 数据流
依据，已由测试和独立 verifier 拒绝。

## 背景与层叠

row loader `0x0808BEE4..0x0808BF61` 先以 tile 0 清空 512×256 screen map，再把
紧致背景写到左上角：

- mode 0 从 `width_pixels` 开始按每 tick 4 像素回到 0，稳定 scroll 为 `(0,0)`；
- mode 1 从 `-240` 开始运行 `width_tiles×2` tick，稳定 X 为
  `width_pixels-240`，即右对齐；
- exit 从 `(-40,-240)` 开始，第二轴按每 tick 4 像素回到 0，稳定 scroll
  为 `(-40,0)`，把 160 像素宽的 pack 8 背景居中。

setup `0x0808BAF4..0x0808BAFB` 把 BG0CNT 写成 `0x4086`，BG priority 为 2。
OBJ attr2 writer `0x08063108..0x0806311F` 则把 task flags 的 `0xC0` 两位移到
attr2 priority：

- main spawner flags `0xA0`，OBJ priority 2；与 BG 同级时 GBA 规则是 OBJ 在前；
- exit allocator flags `0xE0`，OBJ priority 3；BG priority 2 在前，exit OBJ
  只能透过 BG palette index 0 的透明像素显示。

因此 exit PNG 不能把整个 OBJ 无条件覆盖到背景之上。导出器保留完整 BG 索引画布，
仅在 BG index 0 处合入 exit OBJ，并为每个 placement 记录源非透明像素和被 BG
遮挡的像素数；独立 verifier 从 ROM 重新推导两种 flags/priority 并重建相同遮挡。
稳定端点上，mode 0 的 562/562 与 mode 1 的 1515/1515 个 OBJ 非透明像素均被
BG 遮挡，因此两张稳定 exit PNG 像素相同；这不否定过渡帧可能显示 OBJ。旧未提交
实现生成的两张 exit PNG 因无条件覆盖而被取代。

allocator 从 OAM slot 127 向下寻找空槽。双 task 时 index 0 先得到 127，index 1
后得到 126；相同 priority 下较小 OAM index 在前，因此离线合成先贴 task 0、再贴
task 1。

## 独立验证

导出器：

```bash
python3 tools/export_scene_visual_composites.py \
  --root . \
  --output artifacts/scene-visual-composites-v1
```

验证器：

```bash
python3 tools/verify_scene_visual_composites.py \
  --root . \
  --artifact artifacts/scene-visual-composites-v1
python3 -m unittest tests.test_export_scene_visual_composites -v
```

验证器不导入导出器。它从基准 ROM 的关键 Thumb 指令和 literal 独立提取 mode X、
初始/目标 Y、counter 上限、Q12 shift、负数舍入、scroll 初值/步长和 exit
allocator 参数，以及 BG0/OBJ priority 和 attr2 写入链，再从
`scene-visual-packs-v1` 重建 14 张像素并核对完整文件集合、PNG/像素哈希、实现
哈希和 promotion manifest。重新签名后篡改 task 坐标仍会失败。

本里程碑只做小规模离线读取和 PNG 合成，没有启动 mGBA，不需要 heavy lock 或新
快照，也没有触及 Butano worktree。
