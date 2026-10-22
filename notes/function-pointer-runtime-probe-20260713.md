# Function pointer runtime probe（2026-07-13）

## 结论

`0x0853D5F4` 的 11 个 Thumb 指针是实际运行的 UI task callback 表，不再只是
静态上形似代码指针。`tools/build_function_pointer_runtime_probe.py` 同时 hook
dispatcher 的两个直接调用点 `0x08061D84`、`0x0807C61C`，记录一基 callback ID、
两个参数、精确表项地址与读出的函数指针。

键盘输入 `A×5, Start, Down, A, A` 自然进入标题菜单的鸣人人物图鉴页。运行时虽
提供了 `tutorial-ui-save.sav`，后续复放确认该序列并未加载存档。control 共命中
dispatcher 4 次，
其中 callback 2 命中 2 次：entry `0x0853D5F8`，selected pointer
`0x08061C99`，与基础 ROM 完全一致；页面最终完整显示头像和资料正文。

## 单因素 A/B 与边界

variant 只把 ROM `0x53D5F8` 的四字节指针从 wrapper 2
`0x08061C99` 换成相邻的有效 wrapper 3 `0x08061CA5`。同一存档和输入下，人物资料
转场提前分叉，只留下未完成的资料面板；dispatcher 总命中从 4 降为 2，最终停在
callback 1。两张最终截图有 151902 / 691200 个像素不同，差异区域集中在游戏画面。

variant 没有再次 dispatch callback 2，因此其 callback-2 专用 scratch 为零。这个零
不能冒充“variant 读出了替换指针”；它表示被替换的 task callback 已在下一次
dispatcher 创建 ID 2 任务之前改变了状态机路径。严格证据由以下三部分共同组成：

1. control 的自然 ID 2 live hit 和精确 entry/pointer；
2. `0x08061DD4..0x08061DDC` 的静态 load/store 消费链；
3. 仅四字节同表替换造成的定向 UI 调度变化。

因此 `function-pointers` 升级为 `runtime_verified`。写回边界仍保持保守：只允许
指向已验证 Thumb 范围的指针；任意新代码目标、清除 Thumb 位或越界地址均不安全。
紧凑原始值见
`artifacts/runtime-checkpoints/function-pointer-runtime-evidence.json`。

重要地址：table `0x0853D5F4`；sentinel base `0x0853D5F0`；dispatcher
`0x08061D8C`；task callback store `0x08061DD4..0x08061DDC`；scratch
`0x0203F1C0`。

归因纠正不改变 verification：自然 callback hit、精确表项读取与单因素 UI 分叉都
成立；撤销的仅是“冷加载存档”说法。这条标题路线不能作为存档进度或 levels 入口。
