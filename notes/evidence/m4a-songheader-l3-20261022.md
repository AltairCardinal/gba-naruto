# 音频方向的 L3 证据：战斗 BGM 读 `story` 的 SongHeader + 剧情音效读 sound-id 表（2026-10-22）

> 配套：`notes/evidence/callback-dispatch-runtime-20261021.md`（回调派发）、
> `notes/evidence/level-mode-l3-20261022.md`（关卡模式）。
> 这一份是**音频**方向的两条 L3 证据。

---

## 1. 推翻了旧笔记的一句话

`notes/evidence/l2-runtime-evidence-20261021.md` 写：

> 「sound id 1 只经由 *stop* 路径 `fn 0x0809AB8C` 被请求 ——
> 声音 id 表到 SongHeader 的**链接**在运行时被观察到了，
> 但**引擎从不读这个 header 的字段**。」

**作废。** 战斗 BGM 启动时，m4a 播放入口**确实读**了 sound id 1 的
SongHeader 字段。

## 2. 机制

m4a 播放入口的三个「解引用读者」（`tools/l2_runtime_capture.py` 里
`story` 条目已经登记的 `dereference_readers`）：

| 指令 | 指令 | 作用 |
|---|---|---|
| `0x0809B242` | `ldr r0,[r0,#0x18]` | 取 SongHeader 里的**轨道指针** |
| `0x0809B25C` | `ldrb r1,[r0,r3]` | 取轨道的字节字段 |
| `0x0809B282` | `ldr r0,[r0]` | 取下一个指针 |

**复现命令**（纯自然路径：开机 → 状态机 → 相位 `0x0110` 战斗 → BGM 起播）：

```
python tools/mgba_probe/callback_census.py rom/base.gba \
    --route battle --groups 0-3 --presses 40 --json build/census-battle-m4a.json
```

## 3. 运行时读数

战斗路线（组 0–3）里三个点全部命中：

| 断点 | 命中次数 | 命中时的关键寄存器 |
|---|---|---|
| `0x0809B242` | 7 | `r3 = 0x08536368`（**SongHeader 基址**）；`r0 = 0x08538440` / `0x0853802E` / `0x08538448` / `0x0853816B` / `0x08538450` / `0x085382D2`（**表内的轨道指针**） |
| `0x0809B25C` | 7 | `r3 = 0x08536368`；`r0 = 0x0853A1F4` / `0x0853D574` |
| `0x0809B282` | 26 | `r3 = 0x08536368`；`r0 = 0x08538440` … `0x0853A20C`（12 个轨道指针，见下） |

**`r3` 在全部 38 次命中里恒为 `0x08536368`** = `audio_song_1`（sound id 1）
的 SongHeader 基址 —— 这正是 `story` 结构（registry key `audio_song_1`）。

`0x0809B282` 命中 26 次，出现的轨道指针共 12 个：
`0x08538440` `0x0853802E` `0x08538448` `0x0853816B` `0x08538450` `0x085382D2`
`0x08539A88` `0x0853A1FC` `0x08539CC6` `0x0853A204` `0x08539EB2` `0x0853A20C`
—— 全部落在 `0x08536368` 之后的区域内，**与「8 轨 SongHeader」的形状一致**。

## 4. 这证明了什么

| 结构 | registry key | 基址 | 本轮结论 |
|---|---|---|---|
| `story` | `audio_song_1`（sound id 1） | `0x08536368` | **L3 成立**（m4a 引擎在战斗里读它的字段） |
| `story-b` | `audio_song_2`（sound id 2） | `0x08536BC4` | 剧情 sweep 路线（另测） |
| `story-c` / `story-d` / `story-e` | `audio_song_8/11/14` | `0x08538FEC` / `0x0853AB74` / `0x0853C3BC` | **仍缺 L3** —— 战斗 BGM 只放 id 1；这三个 SongHeader 的字段在自然路径上还没被读到（`tools/l2_runtime_capture.py` 里它们也只做了**静态核对**） |

### 3.1 负证据：**战斗 BGM 恒为 sound id 1**（48 个战斗组全跑过）

把 m4a 三个点挂上，跑**全部 48 个战斗组**（`--groups 0-47 --presses 30`）：

| 断点 | 总命中 | `r3`（SongHeader 基址）出现过的值 |
|---|---|---|
| `0x0809B242` | 40 | `0x08536368`（+ 一个非指针值 `0x1`） |
| `0x0809B25C` | 40 | `0x08536368`（+ `0x1` `0x7` `0x1744`） |
| `0x0809B282` | 40 | `0x08536368`（+ `0x1` `0x7` `0x1744`） |

**48 个组、120 次命中，`r3` 里出现的 SongHeader 基址只有 `0x08536368` 一个。**
⇒ **战斗 BGM 永远是 sound id 1**；`story-c` / `story-d` / `story-e`
（id 8 / 11 / 14）**不在战斗路线上** —— 它们需要别的场景/界面才会播。
这是对「48 组都试过了」这件事的**可判死检验**，省掉以后重复扫全部战斗组。

**边界**：本文件证明的是「**战斗 BGM 启动时 m4a 引擎读了 sound id 1 的
SongHeader 字段**」；**不**宣称另外三个 SongHeader 已被运行时读到
（那三条仍是开口项）。

## 3.2 `story-c`（`0x08538FEC`）与 `story-d`（`0x0853AB74`）—— 也拿到了 L3

声音 id 表 `0x08465B70`（159 条 × 8 字节）的映射是**逐条确认**的：

| sound id | SongHeader | 结构 |
|---|---|---|
| 1 | `0x08536368` | `story`（`audio_song_1`） |
| 2 | `0x08536BC4` | `story-b`（`audio_song_2`） |
| **8** | **`0x08538FEC`** | **`story-c`（`audio_song_8`）** |
| **11** | **`0x0853AB74`** | **`story-d`（`audio_song_11`）** |
| 14 | `0x0853C3BC` | `story-e`（`audio_song_14`） |

**剧情 VM 的「播声音」opcode 是 `0x1B`**，操作数是 u16（`0x08097C9C: ldrb r0,[r7,#1]` /
`ldrb r1,[r7,#2]` → `fn 0x08097140` → `fn 0x08061E98`）。
扫全部场景脚本可知**哪些场景请求了哪些 id**；
其中请求 id 8 的场景有 10/12/19/20/25/26/40/41/47/48/49/50/52。

| 结构 | 路线 | 判定点命中时的寄存器 |
|---|---|---|
| `story-b`（`0x08536BC4`） | **剧情路线**（55 场全扫） | `0x0809B242`：`r7 = 0x08536BC4`（SongHeader 基址） |
| `story-c`（`0x08538FEC`） | **剧情路线**（场景 10/12/19/… 请求 sound id 8） | `0x0809B282`：`r7 = 0x08538FEC`、**`r0 = 0x08538FF4` = 基址 + 8**（header 里的第一个指针） |
| `story-d`（`0x0853AB74`） | **战斗路线**（战斗 BGM 之一） | `0x0809B282`：`r7 = 0x0853AB74`、**`r0 = 0x0853AB7C` = 基址 + 8** |

**顺带发现：剧情路线其实会播好几首歌** —— 55 场全扫时，m4a 入口的 `r7`
带过的 SongHeader 基址有
`0x08536BC4`(id 2) / `0x08537B90`(id 4) / `0x08537F7C`(id 5) /
`0x0853BBE8` / `0x0853CEC0` / `0x0853CE88` / `0x0853CF90`
（`r7` 的取值直方图见 `build/census-songs.json`）。

两条都是**真命中**（`|pc - 判定点| <= 4`），且 `r0` 正好是
「SongHeader 基址 + 8」—— 与「header 的第一个字段是指针」一致。

**边界**：`story-e`（id 14）的请求在 **0x080xxxxx 的地图/事件脚本**里
（0x0806ADF0 / 0x080773FE / 0x0808B712 / …），
剧情路线跑不到 ⇒ **它的 L3 本轮未成立**。

---

## 4. `sound-id-table`（`0x08465B70`）的 L3：剧情里的音效读它

菜单/剧情音效走 `fn 0x08061E6C`（blip）→ `fn 0x0809AAC0`：

```
0x0809AAC4: ldr  r2, [0x08465B40]   ; m4a SongHeader 指针表
0x0809AAC6: ldr  r1, [0x08465B70]   ; ★ sound id 表
0x0809AAC8: lsrs r0, r0, #0xd
0x0809AACA: adds r0, r0, r1         ; 条目地址 = 基址 + id*8
0x0809AACC: ldrh r3, [r0, #4]       ; 条目的 u16
```

**判定点必须选 `0x0809AACC`**：下一条 `0x0809AACE`（`lsls r1,r3,#1`）
会把 `r1`（表基址）覆盖掉。

**复现命令**（纯自然路径：开机 → 逐场剧情 → 场景里播音效）：

```
python tools/mgba_probe/callback_census.py rom/base.gba \
    --route sweep --scenes 1-20 --presses 20 --json build/census-sweep-text.json
```

**运行时读数**（真命中，`pc` 与判定点相差 ≤ 4）：

| 断点 | 命中时的寄存器 |
|---|---|
| `0x0809AACC` | `r1 = 0x08465B70`（**sound id 表基址**）；`r0 = 0x08465B90` = 基址 + **0x20**（id 4）；另一条 `r0 = 0x08465EE8` = 基址 + **0x378**（id 111）；`r3 = 0` / `0x2` = 条目的 u16 |

⇒ `sound-id-table`（159 条 × 8 字节）的 L3 成立。

---

## 6. 判死检验

> **读数真伪的判据**：一次 `frames` 运行里可以撞到多个断点，但调试器只停在
> **第一处**，后面的条目拿到的是被 `next` 推着走的同一个停靠的寄存器。
> 所以**只有 `|pc - addr| <= 4` 的记录才是真命中**
> （见 `notes/evidence/callback-dispatch-runtime-20261021.md` §2.5.2）。
> 下表所有数字都按这条判据筛过。

| 检验 | 期望 | 实际 |
|---|---|---|
| 不进战斗（只跑剧情 sweep） | m4a 三个点不命中 | ✅ |
| 进战斗（相位 `0x0110`） | 三个点命中，且 `r3` 恒为 `0x08536368` | ✅ **22 条真命中**，`r3` 全部 = `0x08536368` |
| `r3` 是不是随便某个指针 | 它必须**恰好**是 `audio_song_1` 的基址 | ✅ `0x08536368`（registry `audio_song_1`） |
| 轨道指针是否落在该 header 之后 | 是（SongHeader 的轨道表） | ✅ 12 个指针全在 `0x08536368` 之后 |
| sound id 表的基址在寄存器里 | `r1` 必须等于 `0x08465B70` | ✅ **5 条真命中**：`r1 = 0x08465B70`，`r0` = 基址 + id×8（id 4 / 5 / 8 / 111） |
| 判定点选错会怎样 | `0x0809AACE` 处 `r1` 已被覆盖 | ✅ 那里读到 `r1 = 0` |
