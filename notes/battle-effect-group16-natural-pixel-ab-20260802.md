# Group 16 自然 phase 与最终像素 A/B

## 自然入口

Group 16 不是忍具 67 动态绑定的 sequence 0，而是该忍具编码动作 `0xC3` 的
handler `0x0807EE50` 在 `0x0807EE6A` 以 `MOVS r0,#19` 调用特效选择器后产生。
`artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-confirmation.ss9` 固定在
战斗 14 的最终“是/否”确认页；它由已接受的 active-C3 子快照反向哈希锚定，并经
零输入恢复验证。实验只追加 `A:5:13`，不注入 selector、hook 或对象。

`artifacts/battle-effect-frame-phase-group16-natural-v1/` 记录 Group 16 task
`0x03005904` 在 frame `135/135/136` 依次经过 renderer、submit、ack，pending 为
`0→1→0`。definition/animation 为 `0x0834751C/0x08347548`。

## Production relocation 像素 A/B

`sequel/content/battle-effect-pixel-ab/group-16-tool67-tag.json` 选择 frame 4、
component 0 的局部像素 `(9,17)`。baseline/candidate 都只重定向 Group 16 graphics
指针 `0x59919C` 到 production `battle-effects` 分区；Group 16 palette 指针
`0x5991A0` 及 Group 17 的 graphics/palette 指针对保持原样。候选只把解压 graphics
offset `2340` 从 `0x10` 改为 `0x20`，两份 LZ77 都保持 781 bytes。

`artifacts/battle-effect-group16-pixel-ab-v1/` 的两次当前桌面 mGBA 运行均从上述
确认快照执行同一个 A 输入并在 frame 160 捕获。六个运行时域只有 OBJ-VRAM
`0x06015724` 一字节不同；最终 PNG 也只有 `(169,89)` 从
`[247,255,222]` 变为 `[181,189,165]`。离线 Mode-0 重建与两份 PNG 逐像素一致；
峰值 RSS 为 `69.82421875/70.0234375 MiB`，进程组和监听端口均无残留。

## 边界

本成果签发 Group 16 的一个自然 renderer transaction 与一个 production relocation
最终像素，不等于签发该组全部帧、仿射/混合/时序/音频等价性或实体 GBA。
