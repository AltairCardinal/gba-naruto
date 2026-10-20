# 文本编码：L3 模拟器按键复现证据（2026-10-20）

**等级**: L3（模拟器正常按键复现）
**结构**: 字形段表 / 文本编码 `0x53D644`（`tools/konoha_font.py` / `tools/text_codec.py`）
**画面**: `notes/evidence/story-scene-l3.png`（mGBA 自己的渲染器输出）
**工具**: `tools/mgba_probe/screen_text.py`（把屏幕像素反查成字形码）
**关联**: `notes/evidence/story-scene-l3-20261020.md`（同一画面，剧情脚本侧）、
`notes/font-encoding.md`、`notes/story-script-vm.md`

---

## 1. 复现命令

```powershell
$env:PYTHONIOENCODING='utf-8'

# 画面
python tools/mgba_probe/render_screen.py notes/evidence/story-scene-l3.png \
    --live --rom rom/base.gba --press START --press A --press A --press A --press A

# 把屏幕上的字反查成字形码
python tools/mgba_probe/screen_text.py rom/base.gba \
    --press START --press A --press A --press A --press A \
    --rect 16,96,216,44 --json build/screen-text.json
```

---

## 2. 证据链

| 环节 | 证据 |
|---|---|
| 正常按键 | `START` + `A`×4（无内存改写、无脚本注入、ROM 未改） |
| 游戏真的执行了场景 54 的剧本 | VM 入口 `0x080977B8` 命中，**r0 = 0x08049E76** = `before_root[54]`（L2 采样，见 `notes/evidence/story-vm-l2-20261020.md`） |
| 屏幕上出现了中文对白 | `notes/evidence/story-scene-l3.png`：名牌「伊鲁卡」+「“是啊，是我这个班主任所承认的嘛！”」 |
| 剧本里的字形码解码后 == 屏幕上的字 | `tools/decode_story_script.py --scene 54` 的**第 5 句**就是「“是啊，是我这个班主任所承认的嘛！”」，逐字相同 |
| 像素 ↔ 字形码的逐位对应 | `tools/mgba_probe/screen_text.py` 报告 **CONFIRMED bit-exact** 的格子：`y=120` 的 `0x8142` = 「**。**」（8 个墨迹像素，掩码完全相同） |

最后一行是**像素级**的证据：屏幕上的那 8 个像素，与 ROM 字形表里
`0x8142` 的位图**完全相同**（0 个像素不同），而 `0x8142` 经
`tools/text_codec.py` 解码为「。」。

## 3. 一个必须写清楚的限定

`tools/mgba_probe/screen_text.py` 目前只能在**标点**上做到逐位精确；
**汉字**做不到。原因已经查清（见 `notes/font-encoding.md` §1.1、§1.2）：

- 对话里的汉字，其字形位图**不在** `0x53D644` 那张表里；
- 那张表的 32 字节/字形，在所有可能的排布下
  （8×8 4bpp / 8×16 2bpp / 16×8 2bpp / 16×16 1bpp / 2 倍放大各向）
  都无法复现屏幕上的汉字（最佳平均差异 27/128 像素，而真正匹配应当是 0）；
- **「屏幕像素 → 调色板索引 → ROM 字节」这条反推链在密集汉字上不成立**：
  文字带抗锯齿/半透明混合，屏幕颜色不是字形索引的直接投影。
  （本轮曾据这条链声称某个单元与 ROM `0x0813E209` 逐字节相同，
  **该断言已被推翻** —— 那个格子只有 2 个墨迹像素，匹配到的是零填充区。
  详见 `notes/resource-locations.md` 的留档。）

所以：**字形码（编码）是对的、并且在屏幕上被验证了**（剧本解码出的中文
与屏幕显示逐字相同）；但**对话汉字的位图数据**属于另一处 ROM 数据，
本轮只列出了**候选**表（`0x0813E040` / `0x0813E120` / `0x0596D60` /
`0x0142A70` / `0x0142AC0`），**没有证实**哪一个是它，
更没有解出「码位 → 字形偏移」的索引规则。

已确证的只有两件事：
1. 对话里的汉字是 **16×16**、ASCII 标点是 **8×8**；
2. 两者的位图**都不是** `0x53D644` 那张 8×8 4bpp 表的。

## 4. 判死检验

| 结论 | 能推翻它的检验 |
|---|---|
| 屏幕文字 == 场景 54 剧本第 5 句 | 改 `--press` 次数重抓画面；若画面句子不是剧本里的任何一句，则「A 推进 = 推进剧本」作废 |
| 剧本第 54 项确实被执行 | 跑 L2 的断点命令；若 VM 入口 `0x080977B8` 的 `r0` 不是 `0x08049E76`，则画面与场景 54 无关 |
| `0x8142` 的位图 == 屏幕上的 8 个像素 | 跑 `tools/mgba_probe/screen_text.py`；若 `CONFIRMED bit-exact` 计数为 0，则像素级对应不成立 |
| 对话字形表在 `0x0813E040` / `0x0813E120` | 改窗口再抓一次；若屏幕上的汉字仍能在 ROM 里逐字节命中其它地址，则这里不是字形表 |
