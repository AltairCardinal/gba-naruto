# GBA VRAM 安全 LZ77 编码与运行时回归（2026-08-01）

## 根因与修复

仓库编码器此前允许生成距离为 1 的 LZ77 回引用。普通字节级解压器可以正确还原，
但 GBA BIOS `LZ77UnCompVram` 以半字提交 VRAM；距离 1 的重叠复制可能在偶地址低字节
尚未提交时读取它，导致 mGBA/GBA 语义与离线解压不一致。

mGBA 0.10.5 源码 `src/gba/bios.c::_unLz77(width=2)` 证实了半字提交语义。TDD 先用
独立半字 VRAM 解码器复现旧编码结果错误，再修改 `tools/gba_image_export.py` 跳过
distance 1 候选。所有独立 verifier 编码器也加入相同限制，并由
`tests/test_vram_lz77_encoder_safety.py` 统一锁定。

## 级联重建

共享编码器变化后，13 份图像重定位成果全部重新导出并由独立 verifier 验证：角色
战斗 bundle、tile asset、地图、菜单立绘、regular BG、战斗特效、剧情视觉层、世界
地图、通用 sprite、Cutscene OBJ、残余 LZ77 图形、direct palette、残余 text BG
tilemap。相关 WRAM ABI/relocation 及像素成果也按实现哈希重新签发。

旧固定槽位审计不再把“不适配安全编码”的资源当作成功：

| 类别 | 安全编码微改动可原槽位容纳 | 总内容 |
|---|---:|---:|
| 菜单／剧情立绘 | 37 | 74 |
| 战斗地图资源 | 70 | 166 |
| 战斗特效资源 | 23 | 34 |
| regular BG 资源 | 10 | 31 |

这只收窄旧原位写回能力，不影响已经签发的可变长重定位能力。超出原槽位的编辑必须
走对应 relocation importer。

## 运行时回归

- 世界地图 page 0 的两份安全流均为 31,988 bytes，frame 80 的完整 32 KiB VRAM
  graphics 与各自源逐字节相等。旧证据中的 806 个共同覆盖字节实际是距离 1 编码
  造成的损坏，修复后为 0；最终单像素链仍成立。
- 菜单立绘选择压缩尺寸与基线同为 3,306 bytes 的 index `52→14`，避免 A/B 分配
  拓扑差异。重新运行后完整 6,400-byte OBJ 流只差目标字节，最终只改变一个像素。
- Cutscene OBJ ID 1 的源流和候选流均为 1,187 bytes、distance-1 token 为 0；自然
  胜利加载后完整 `0x06016000..0x06016FFF` 与各自 4 KiB 源逐字节一致。

所有正式 mGBA 重放均使用已接纳 checkpoint、共享 heavy lock、2 GiB 启动门槛、
owned-tree RSS 上限及进程/监听残留检查；本轮运行峰值均约 56 MiB，未产生崩溃或
残留进程。

## 边界

本结论证明当前 production 编码器与独立 verifier 不再生成 distance 1 token，并
闭合三条代表性自然像素回归；不等于所有图像资源都已逐项完成自然运行时像素验证，
也不替代实体 GBA 验证。
