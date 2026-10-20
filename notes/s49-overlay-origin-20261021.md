# S49 覆盖层溯源：BG2 tilemap 的烘焙布局从哪来 + 那 212 格按什么状态变

日期：2026-10-21（第 23 轮，接续网络中断的第 22 轮）

工作树 `/Users/altair/github/gba-naruto`（分支 `codex/butano-foundation-research`）；
逆向树 `/Users/altair/github/gba-naruto-reverse` **只读**。
ROM `rom/base.gba`（SHA-256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`）。
Python 一律 `/usr/local/bin/python3`（3.14.3）。**未运行 mGBA**。

## 0. 继承的既成事实（不重新推导）

| 事实 | 出处 |
| --- | --- |
| 覆盖层 = 独立 BG2（DISPCNT bit 10 = BG2 enable） | `notes/s49-dispcnt-bit10-layer-20261020.md` |
| BGCNT2 = 0x0202；BG2 tilemap 在 VRAM `0x06001000`；图块 256..287 在 `0x06002000`；palette bank 12 | `notes/s49-movegrid-overlay-assets-20261020.md` §A/§B/§G |
| 图块 = ROM LZ77 `0x080B9E94`（1024 B）；调色板 = LZ77 `0x080B9F5C`（32 B） | 同上 §A |
| 装载器在 ROM `0x080694C4`，字面量池 `0x080694E0..EF` | 同上 §B |
| field 帧 BG2 tilemap 已完全填充（1024 项、22 种图块、16 种 2×2 签名）；移动光标/选单位会改写 212 项 | `notes/s49-battlefield-overlay-baked-20261021.md` §1、`notes/s49-movegrid-overlay-tilemap-20261020.md` §3.1 |
| 212 项落在 53 个 16×16 逻辑格上（整格替换，无半改格） | `notes/s49-movegrid-overlay-tilemap-20261020.md` §3.2 |

（本文件按「每问一节」追加，网络中断不会丢成果。）

## 1. 问题一：BG2 那张烘焙布局图从哪来？

（进行中）
