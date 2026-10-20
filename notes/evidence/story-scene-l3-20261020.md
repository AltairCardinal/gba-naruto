# 剧情脚本：L3 模拟器按键复现证据（2026-10-20）

**等级**: L3（模拟器正常按键复现）
**结构**: 剧情脚本 VM 四根表 `0x060C74` / `0x060D54` / `0x060E34` / `0x060EF0`
**采集**: `tools/mgba_probe/runtime_probe.py` + `tools/mgba_probe/render_screen.py`
**画面**: `notes/evidence/story-scene-l3.png`（mGBA 自己的渲染器输出，像素级精确）
**关联**: `notes/evidence/story-vm-l2-20261020.md`（同一场景的 L2 原生定点）、
`notes/story-script-vm.md`、`notes/story-vm-opcodes-20261020.md`、
`notes/mgba-probe-runtime-20261020.md`

---

## 1. 复现命令

```powershell
$env:PYTHONIOENCODING='utf-8'

# 画面（mGBA 自己的渲染器）
python tools/mgba_probe/render_screen.py notes/evidence/story-scene-l3.png \
    --live --rom rom/base.gba --press START --press A --press A --press A --press A

# 同一序列下的 VM 入口断点（r0 = 脚本指针）
python tools/mgba_probe/runtime_probe.py rom/base.gba \
    --boot-frames 1500 --press START --press A --press A --press A --press A \
    --breakpoint 0x0808F5D0 --breakpoint 0x080977B8 --settle-frames 90 \
    --json build/runtime-trace.json
```

**按键序列**：`START` → `A` → `A` → `A` → `A`。
这是**正常按键**，没有改写任何内存、没有注入脚本、没有改 ROM。
`START` 进标题，按 `A` 逐句推进对白。

---

## 2. 屏幕上出现了什么

`notes/evidence/story-scene-l3.png` 里，文本框显示：

| 元素 | 内容 |
|---|---|
| 说话人名牌（蓝紫色） | **「伊鲁卡」** |
| 对白 | **「“是啊，是我这个班主任所承认的嘛！”」** |
| 背景 | 伊鲁卡与鸣人的立绘 |

## 3. 剧本里对应的内容

`tools/decode_story_script.py --scene 54` 解出的场景 54（`before` 根表第 54 项 =
`0x08049E76`）对白序列：

| # | 指令 | 文本 |
|---|---|---|
| 1 | `op=0x02 portrait` | 漩涡鸣人的立绘 |
| 2 | `op=0x01` | 「“呜哇！果然还是一乐的拉面最好吃呀！！”」 |
| 3 | `op=0x01` | 「“鸣人……一听到是我请客你就这么不客气了啊……真是的！”」 |
| 4 | `op=0x01` | 「“老师！老师！从今天起我就是个真正的忍者了！！”」 |
| 5 | `op=0x01` | **「“是啊，是我这个班主任所承认的嘛！”」** ← 屏幕上这句 |
| 6 | `op=0x01` | 「“你已经从忍者学校毕业，成了木叶村里优秀的忍者了！”」 |
| 7 | `op=0x01` | 「“伊鲁卡老师！我有一个请求……”」 |

第 4 次 `A` 正好推进到第 5 句，说话人变成**伊鲁卡**（与第 2~4 句的鸣人交替）。

→ **屏幕上显示的文字 = 场景 54 剧本里第 5 句，一个字不差**；
   说话人名牌也对得上。剧本本身是从 `before_root[54] = 0x49E76` 解出来的，
   而 `0x49E76` 正是 L2 采样里 VM 入口 `0x080977B8` 收到的 `r0`
   （`0x08049E76`）。

## 4. 为什么这张图是「可见行为」的证据

- 画面**不是**探针自己画的。`tools/mgba_probe/host_main.c` 的 `rawshot` 命令
  直接导出 **mGBA 自己的视频缓冲**（240×160 的 `color_t`，字节序 R,G,B,A），
  也就是玩家在屏幕上看到的同一份数据。
- 之前探针里 `shot`（PNG）一直返回 0，因为本机 mGBA 没开 `USE_PNG`；
  现在不再依赖 PNG，也不再需要在 Python 里重写一遍 PPU。
- 渲染器接线也修好了：视频缓冲必须在 `core->reset()` **之前**安装，
  否则 GBA core 不会把软件渲染器挂上去（`src/gba/core.c` 的 `_GBACoreReset`
  只在 `renderer.outputBuffer` 已设置时才关联渲染器）。

---

## 5. 判死检验

| 结论 | 能推翻它的检验 |
|---|---|
| 屏幕文字 = 场景 54 剧本第 5 句 | 重新跑第 1 节的命令；若画面上的句子不是剧本里的任何一句（且不是别的场景的句子），则「按 A 推进 = 推进剧本」作废 |
| 这次按键真的执行了 `before_root[54]` | 跑第 1 节的断点命令；若 VM 入口 `0x080977B8` 命中的 `r0` 不是 `0x08049E76`，则画面与场景 54 无关 |
| 对白是逐句推进的 | 把 `--press A` 的次数改掉；若画面不随次数变化，则推进机制另有解释 |
| 画面是游戏自己渲染的 | `rawshot` 读的是 mGBA 渲染器的输出缓冲；若探针的帧循环没跑（`done=0`），则画面可能是上一帧残留 |

---

## 6. 仍未闭合的一项：16×16 对话字体

画面上的汉字是 **16×16**，而 `notes/font-encoding.md` 记录的字体段表
`0x53D644` 是 **8×8 4bpp**（每字形 32 字节；`0x08065EF4` 的
`lsls r0, r0, #5` 就是这个 32）。实测字距约 12 px = 汉字 16 px + 标点 8 px，
说明**对话用的是另一套 16×16 字形**（ASCII 标点仍用 8×8）。

全 ROM 扫描后**没有**找到第二张同构的字体段表（31 项、start 递增、count>0、
glyph offset 合法），因此：

- **字形码的编码**（`text_codec.py` / `konoha_font.py`）依然有效 ——
  剧本解码出的中文与屏幕显示一致，这本身就是编码正确的强证据；
- 但**对话字形的位图来源**尚未定位：它在 VRAM 里（sprite 或 tile），
  而 `0x53D644` 那张 8×8 表显然不是它的来源。
- 这**修正**了 `notes/font-encoding.md` 的隐含前提
  （「游戏的中文用 `0x53D644` 这一个字形表渲染」）—— 需要补一句：
  **存在 8×8 与 16×16 两套字形**，`0x53D644` 对应的是小字（任务文字/名牌一类）。

**待办**：定位 16×16 字形表（候选方向：sprite tile 数据 `0x06010000` 起、
OBJ 1D 映射；或对话渲染器里另一条 `lsls #7` 的路径），
然后把屏幕像素与 ROM 字形逐位对上，把这一项也升到 L3。
