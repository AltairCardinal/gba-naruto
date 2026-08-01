# Group 15 分配器与 side 受控 A/B（2026-08-01）

## 结论

此前 sequence 17 / group 15 在通用 binder 探针中四阶段均无目标 task。新实验把原因
拆成两个相邻变量：

1. 原 case 不重置资源分配器且使用 side 0，selector 返回 `0xFF`；
2. 加入 ROM 自然调用点已经使用的
   `0x0807FDCC(0x300,0x37F,12,14)` 后，side 0/1 的 selector 都返回有效 handle `0`；
3. 在完全相同的 reset 条件下，side 0 仍无目标 task，side 1 则在
   renderer/submit/ack 稳定出现 slot 108，definition/animation 为
   `0x0834711C/0x08347168`。

因此，在该固定 checkpoint、sequence 17、side 0 的受控对照中，资源窗口重置是
selector 从 `0xFF` 变为有效 handle 的已观察前置条件；这不是对所有自然入口作出的
全局必要性声明。selector 有效后，reset side 0/1 两份 probe ROM 仅在
`0x0809E852` 相差一个字节（`0→1`），所以该对照中的 group 15 child task 出现可归因
于 side 1，没有混入其他变量。

## 资源与可见边界

side 1 task 使用 OBJ tile base 768、palette bank 12；renderer/submit/ack 三阶段的
3,584-byte graphics 与 32-byte palette 都和静态 group 15 资源逐字节一致。

task 的 anchor 为 `(-98,62)`，frame 0 唯一 component 的 local bounds 是
`x=-16..16, y=-16..16`；考虑 task 水平镜像后仍完全位于左屏外。因此本成果只升级
group 15 的受控 selector/resource/task 覆盖，明确保持：

- `visible_target_oam_binding_count = 0`；
- 不声明自然 action 64/65 入口已复现；
- 不声明最终像素 A/B、完整动画、音频或实体 GBA 输出。

下一步应在桃地再不斩（unit 20）的自然 action 64“水遁・水龙弹术”或 action 65
“水遁・大瀑布术”链路中捕获 `0x0807F0FC → 0x0807F10C`，而不是继续猜测 parent
坐标或直接改写 task。

## 可复算证据

`artifacts/battle-effect-group15-allocator-side-runtime-v1/` 只含
`evidence.json`、`raw-batch.tar`、`manifest.json`。归档精确保存 113 个来源成员：
batch audit、两案 profile/audit/guard/完成标记，以及 `2 × 4 × 13` 份四相输出。

独立 verifier 会重新检查：

- 固定 SHA 的 ROM、输入快照、sequence/animation/resource catalog、group 15
  graphics/palette 原始载荷、toolchain profile、capture script 与父受控 artifact；
- 运行父 artifact verifier、独立重建旧 no-reset probe ROM，并从父归档四份 `.ss9`
  复算 selector=`0xFF`；
- 两案 profile/audit/guard 和 113-member 归档闭包；
- mGBA 二进制 SHA、toolchain source commit 及完整 guard/runner 依赖链；
- selector handle、完整 active dispatcher、task pointer identity、slot 与 phase 稳定性；
- group 15 OBJ VRAM/PRAM 字节；
- 单字节 side A/B、屏外几何和“零可见 target OAM”边界。

## 资源安全

两次运行均通过同一 guarded capture 路径完成，无 mGBA 进程或 listener 残留。side 0
峰值 RSS 样本为 `71.7421875 MiB`；side 1 仅采到 `0.16796875 MiB`，属于短运行欠采样，
所以不生成批次峰值、均值或上界声明。
