# 角色场景控制器阶段与独立 task 运动见证（2026-07-30）

## 结论

`0x0808C214..0x0808C4CB` 不能静态还原成一条固定的逐帧合成时间线：

- state 3 等待外部全局值变为2，等待次数没有静态上界；
- controller yield、多个OBJ task callback与VBlank之间的调度顺序未证明；
- main state 0在同一次dispatch内先写初始scroll，再落入state 1写第一次4像素更新。

因此成果 `artifacts/scene-visual-transition-timelines-v1/` 明确拆成两类：

1. controller自身可证明的403次背景scroll写入，全部在spawn前按背景单独渲染；
2. 16条OBJ task各自的521个callback局部见证，以稳定背景作空间参照，但不声称它们
   与controller写入一一对应或同时发生。

旧的“14轨道、634个BG+OBJ callback状态”模型已撤销。它把OBJ错误地放在spawn前，
还把mode 1错误扩展到pack 0–7并伪造了mode 0 exit。

## mode路由

ROM `0x0808C226..0x0808C23A` 把当前pack / 排他上界设置为：

| 参数 | main pack | main scroll写入 | main dispatch | main task |
|---|---|---:|---:|---:|
| mode 0 | 0–3 | 170 | 166 | 8 |
| mode非零 | 4–7 | 172 | 168 | 7 |

`0x0808C3EA..0x0808C3FE` 在main pack结束后递增pack并比较上界。mode 0随后直接
退出；只有非零mode进入state 10，以pack 8作为唯一exit背景和OBJ资源。exit包含
state 10初始写入1次及state 11的60次更新，共61次scroll写入和1条task。

因此有限背景写入分母为：

```text
main: 39+43+41+47 + 45+37+43+47 = 342
exit: 1+60 = 61
合计: 403
```

main每pack的首个记录是state 0初始scroll；紧接着的第二个记录是同一dispatch落入
state 1后的首次更新。后续每个dispatch写一次scroll。最后一次scroll写入完成后，
`0x0808C3C0` 才调用spawner `0x0808C0B4`；所有403张背景记录的
`obj_placements=[]`，最后记录只保存spawn事件和task初始内存值。

## controller状态边界

跳转表基址由 `0x0808C2F8` 的literal指向 `0x0808C2FC`，共21项：

- state 0/1：main背景初始化、4像素更新，完成后spawn；
- state 2：计数从0增至64，第64次转state 3并调用presentation helper；
- state 3：等待外部 `0x020311D4 == 2`，满足后cleanup并切换pack；
- state 10/11：唯一exit背景初始化和60次纵向更新，完成后spawn exit task；
- state 20：计数从0增至212，第212次把状态设为255并退出；
- 其余表项只落到公共yield，本函数内部没有写入这些状态的路径。

state 2和state 20的有限计数作为控制模型记录，但没有渲染成联合视觉帧，因为对应
期间OBJ task可能由另一个调度链更新。state 3明确保留为无有限分母。

## 独立 task 轨迹

main spawner对每个task分别设置初始counter与坐标。callback先递增counter，只在
新值不超过31时写Y：

- 8条task 0：初态counter 0，加counter 1–31的31次写入，再保留counter 32首个
  不写坐标的稳定回调，共 `8×33=264` 个见证；
- 7条task 1：初态counter 1，加counter 2–31的30次写入，再保留counter 32首个
  稳定回调，共 `7×32=224` 个见证；
- 唯一exit task：初态counter 0，加31次X写入和首个稳定回调，共33个见证。

总计 `264+224+33=521`。最终写入坐标仍为main Y `10/70`、exit `(85,128)`；
counter 32记录与counter 31像素相同，但用来证明“不再写坐标”的代码边界。

每条task帧只绘制该task本身，背景使用对应pack的稳定scroll作为空间参照。它不是
实际wall frame，也不声明另一task当时处于初态、稳定态或任何指定位置。

## Artifact与独立验证

artifact只包含：

- `scene-visual-transition-timelines.json`：路由、状态模型、403个背景写入和521个
  task见证；
- `frames.zip`：924张240×160 RGBA PNG；
- `manifest.json`：文件哈希、scope及验证命令。

ZIP使用固定顺序、stored PNG、1980时间戳、Unix create system、`0644`权限和空
extra/comment。独立verifier不导入新导出器；它从ROM重新读取跳转表基址、mode
初始化、pack切换、spawn顺序、state 2/20计数、task counter边界和Q12插值，再重建
全部记录与PNG。测试覆盖：

- 在首个背景写入伪造spawner事件并重签payload仍被拒绝；
- 修改ZIP archive comment，并同步重签archive、payload和manifest哈希仍被拒绝；
- 重复导出三个文件逐字节一致。

## 资源守卫与边界

```text
stable composite tests: completed/0, peak tree RSS 30.68 MiB
phase tests:            completed/0, peak tree RSS 50.15 MiB
phase export:           completed/0, peak tree RSS 35.09 MiB
phase verify:           completed/0, peak tree RSS 37.32 MiB
```

全部运行共用heavy lock、非降级，未启动mGBA，也未读写Butano工作树。当前明确不
签发完整controller时间线、跨task调度、VBlank/wall-frame映射、presentation
overlay、window/blend/mosaic、运行时逐像素等价或自然语言场景身份。
