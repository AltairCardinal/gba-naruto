# Group 2 影分身术自然像素 A/B（2026-08-02）

## 结论

Group 2 / sequence 2 已从“只有 supplemental phase、没有可信自然入口”推进为
production relocation 的自然最终像素 A/B。入口是主动动作 7“影分身术”的专用
handler `0x0807E1C8`：callsite `0x0807E1D0` 直接装入 sequence 2。它与通用动态
action→sequence 表中 action 7→sequence 0 是两条不同生产链，builder 和独立 verifier
均绑定这项差异，不能用动态表或历史 tool 49 路线替代。

持久成果：

- profile：`sequel/content/battle-effect-pixel-ab/group-02-action7-shadow-clone.json`；
- 可复用输入：`artifacts/runtime-checkpoints/scenario-50-action7-shadow-clone-confirmation.ss9`；
- 运行证据：`artifacts/battle-effect-group2-pixel-ab-v1/`；
- 独立验证：`python3 tools/verify_battle_effect_pixel_ab_evidence.py --root . --artifact artifacts/battle-effect-group2-pixel-ab-v1`，返回 `errors=[]`。

## 输入与修改

输入快照 SHA-256 为
`2b800fe1609923966c7e3898cc8bc81c67e106e3f04a93afed919ed950e5ae71`，位于影分身术
确认页；证据在输入前确认目标 candidate 资源尚未进入 OBJ VRAM。两份 16 MiB ROM
都只在 frame 5..12 输入 A，并在 frame 510 捕获。

production relocation 只拆分并重定向 Group 2 primary pair `0x59912C`，保留相邻
Group 3 alias `0x599134`。源图形为 9728 bytes，迁移到 `0xB40000`；candidate 仅把
frame 2 / component 0 的局部像素 `(8,12)` 对应图形 offset `688` 从 `0x32` 改为
`0x34`，即 palette index `2→4`。

## 运行时结果

- baseline/candidate 运行峰值 tree RSS 分别为 `69.6171875/69.55078125 MiB`；
- guard 均为 completed、non-degraded，owned PGID 和 listener 均无残留；
- 六个内存域中仅 OBJ VRAM `0x060122B0` 一字节不同；
- 两边图形流、palette 和三项 OAM instance 均分别与各自 ROM/profile 一致；
- 最终截图只有 `(64,82)` 一个像素变化：`(255,255,247)→(255,255,197)`；
- baseline/candidate checkpoint 的离线 Mode-0 重建均与 mGBA PNG 达到 0 像素误差。

最后一项验证同时修正了项目合成器的一处硬件语义错误：同一点重叠的多个 OBJ 不会
全部进入后续图层混合；OAM/priority 选出的顶层 OBJ 先进入 sprite layer，半透明效果再
与其后的 BG/backdrop 混合。旧实现错误地让顶层烟雾 OBJ 与下层烟雾 OBJ 再混合，导致
frame 510 有 784 个伪差异。专门的红绿测试现覆盖该边界。

## 边界

本成果只签发 Group 2、frame 2、component 0、一个源像素及其三个 OAM instance。
它不外推 Group 2 全部动画帧、完整 affine/blend/window 时序、音频或实体 GBA。
production 自然最终像素覆盖由 7/18 提升到 **8/18（44.44%）**，其余 10 组仍待闭合。
