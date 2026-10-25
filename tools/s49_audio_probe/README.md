# tools/s49_audio_probe — S49 音频事件级探针（stream J）

**目的**：把「S49 木叶丸 vs 野蜂」这场仗的**音频事件序列**在两侧各自导出，
逐事件配对，给出差异表。

## 一条命令

```powershell
python tools/s49_audio_probe/run_all.py --out build/s49-audio
```

产物（全部 LF/UTF-8、无 BOM）：

| 文件 | 内容 |
|---|---|
| `build/s49-audio/original_events.json` | 原版 MP2K 逐帧事件序列（cue / 触发帧 / slot / 起停） |
| `build/s49-audio/original_frames.json` | 原版逐帧 4 个 player 槽的完整解码 |
| `build/s49-audio/cue_census.json` | 每个存档时"在播哪个 cue" |
| `build/s49-audio/remake_events.json` | 重制侧 cue 表 + 调度调用点 + PSG/DMA 逐帧窗口 |
| `build/s49-audio/event_diff.md` / `.json` | **逐事件差异表** |

## 模块

| 文件 | 作用 |
|---|---|
| `probe_driver.py` | 无头 mGBA 探针的驱动（`load` / `frames` / `framedump` / `keyseq`），按前缀分目录收集逐帧 dump |
| `mp2k_layout.py` | MP2K 运行时布局：ROM dispatcher 表（0x08465B70）、4 个 player 槽、track 数组 |
| `psg_state.py` | GBA 声音/DMA 寄存器块解码（0x04000060..0x040000DF） |
| `extract_original.py` | 原版侧：采集 + 解码 + 确定性/扰动对照 |
| `cue_census.py` | 对每个存档读一次 MP2K 槽状态，得到"这个场景在播哪个 cue" |
| `extract_remake.py` | 重制侧：采集 + 解析 `battle_audio_director.h` / `battle_audio_runtime.h` / 调用点 |
| `compare_events.py` | 按**游戏时刻**配对两侧序列，生成差异表 |
| `run_all.py` | 串起全流程 |

## 依赖

* 无头 mGBA 探针：`build/mgba-probe-j/mgba-probe.exe`
  （用 `$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-j'` 另建，
  **不要**覆盖共享的 `build/mgba-probe/mgba-probe.exe`）。
* 原版 ROM：`rom/base.gba`（sha256 `1198ece7…`）
* 原版存档：`D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints\scenario-49-battle-14-entry.ss9`
* 重制 ROM：`D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba`
  （**每次重建 hash 都会变** ⇒ 结果里一定记 sha256）

## 关键事实（都在代码注释里，可复核）

* MP2K `player+0x00` = 当前 song descriptor 指针 ⇒ 经 ROM dispatcher 表映射回 sound ID。
* MP2K `track+0x00` = 状态字节：`0x80` 在跑，`0xC0` = **这一帧被调度**
  （`MPlayStart` 写 0xC0）。这是"同一 cue 重复触发"的唯一可靠指纹。
* `track+0x40` = 命令指针，**会因 GOTO 循环而回跳** ⇒ 不能单独用作重触发判据。
* GBA 声音控制块在 `0x04000080..0x04000087`（GB 兼容布局），
  与逆向线 `oracle/audio_io_probe.py` 的分区一致。
