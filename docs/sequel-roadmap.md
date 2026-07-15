# 木叶战记续作 Roadmap

## 目标

把当前仓库从"已建立续作工作区和逆向基础"推进到"可以持续生产续作内容并稳定回写 ROM"的状态。

**执行策略：先完成逆向工程，再建网页编辑器。**

---

## 现状总览

> 2026-07-13 当前调查闭合审计为 32/32：23 个有效数据 bank 均通过元数据和
> 基准 ROM fidelity，另 9 个是带负证据、空 entries、禁写回的 `disproved`
> tombstone。分布为 runtime 13 / code 10 / static 0 / disproved 9。32/32 只表示
> bank 身份调查闭合，不等于所有字段语义、运行时路径与端到端写回均已完成；
> save-state 已由真实 UI save 与冷启动恢复升级为 runtime_verified。

### 2026-07-13 最新执行边界

- scenario 41 任务准备菜单已确认：`A` 为队伍/装备，`Down,A` 为查看战场，
  `Down,Down,A` 为“开始任务？”，`Down,Down,Down,A` 为保存；
- 确认“开始任务？”后，battle ID 41、map 36×44、Naruto `(4,10)`、Iruka
  `(4,4)` 和白框画面连续六次采样保持稳定；但 2026-07-15 离线任务栈复核证明其保存时的活动链位于
  `0x0808F928 → 0x08088F10 → 0x0807509C → 0x0806F718` 的 pre-controller
  lineup/deployment，且不含 controller caller return；旧 strict arrival 对“该 state 证明 battle controller entry”产生了语义假阳性；
- 该边界尚未证明真实战斗入口、玩家接管、胜利、EXP 或升级：Naruto 仍为 level 1 / EXP 100，
  训练点 `+BA=0`、`A880=0`，因此 `levels` 继续保持 `code_verified`；
- 2026-07-15 五点 controller-path probe 已完成 builder/decoder 与 guarded A/B，但
  `actionable-move-grid.ss9` 的零输入 baseline 和显式 `B,Down,Down,A,A` final dump
  逐字节相同，`0x08073946` 与四个 `0x08073A04` 分支均无 fresh record。正对照未成立，
  因此没有运行 scenario 41 白框两轮，也没有提升玩家控制状态；
- 2026-07-15 原生 mGBA 0.10.5 Lua 已证明：从 accepted 白框 state 对 GBA B 做
  8-frame hold 可到达战前菜单。输出 task 2 resume PC 为 `0x08067D02`，活动 unwind
  为 `0x080885C1 → 0x08088F9F → 0x0808F92D`，仍不含 controller return
  `0x0808F957`。该 state 已随 Git 固化为 prebattle candidate，等待 macOS Intel
  零输入复放后才可 accepted；
- 下一 P0 先完成 lineup/deployment，并以 task 栈含 `0x0808F957` 或 fresh entry observer
  命中 `0x0808F952 → 0x080732B4` 证明真实 controller entry；随后依次命中玩家单位选择 `0x08073940`、
  MOVEDONE `0x080722A8`、胜负谓词 `0x080777FC`、结果写入 `0x02026807` 和
  postbattle `0x08074EE6`，再对自然命中的 levels record `+6` 做单因素 A/B；
- 当前证据分布仍为 13 `runtime_verified` / 10 `code_verified` / 9 `disproved`；
  本次纠正的是 scenario 41 功能边界，不改变 bank 状态。

Windows 前台 runtime 到此停止，后续转移到 macOS Intel。迁移、mGBA 0.10.5、Lua
8-frame 输入、candidate 零输入验收和进程守卫要求见
`docs/reverse-engineering-macos-intel-handoff-20260715.md`。

资源约束：全 ROM Capstone 对象扫描曾单进程膨胀到 3 GiB 以上并触发 OOM、swap
thrashing 和 I/O pressure；该路径现已替换为恒定内存 Thumb 编码扫描。静态重任务与
Chromium probe 必须统一经 `tools/run_guarded.py` 的共享 `heavy` 锁、内存准入、树级 RSS、
wall/idle timeout 和精确 owned-tree 清理；runtime 的实际入口是
`play/_scripts` 下的 `npm run probe:guarded`。禁止按进程名清理。当前 bank 分布仍为
13 runtime / 10 code / 9 disproved；资源安全实现不改变逆向证据等级。完整门槛、退出码和
命令见 `docs/reverse-engineering-handoff-20260711.md` 第 0.5 节。

### ✅ 已打通
- 对白 → ROM 写入闭环（dialogue patch pipeline）
- 5 段对话已验证写入 ROM
- 变长对白现已使用独占 `0x5F0000..0x5F7FFF` allocator，校验基准指针、FF
  空间、编码/NUL、对齐和容量；`group0.label2` 已从 6-byte slot 重定位到
  `0x5F0000`，构建 ROM 的 `0x461CF0` 指针和目标文本逐字节验证通过；该 ROM
  已在 WASM 路线 step 306 通过完整 strict battle arrival，变长重定位的构建→启动→
  文本流程→首战 no-crash E2E 已闭环
- 构建流水线支持 7 种 patch 类型（bytes/dialogue/pointer_redirect/map/battle_config/
  dialogue_var/chapter_script）
- mGBA headless 调试环境稳定（`tools/mgba-headless-snapshot.py`）
- mGBA PC/读取探针已加入：断点真实命中后可在同一上下文抓取 ROM 与 WRAM；
  复位 PC smoke test 已通过；maps width/height 与六类资源流均已由 WASM/mGBA
  同边界 A/B 闭合
- 网页 WASM 首战导航与编成探针已可复现：单位槽 1 坐标 `(4,4)` 唯一对应
  positions group 40 / variant 0 / record 0（ROM `0x588CA8`），positions 已完成
  runtime 验证
- WASM 探针现会记录 `0x02026804` 的 8 字节控制区、`0x02026805` 标识和
  `0x0201BE28..2B` map runtime；baseline 得到 `[36,44,9,22]`
- WASM 到达判据仍要求唯一完整编成、非零 battle ID、派生一致 map runtime 和
  真实地图截图，但旧颜色分类已纠正：旧 step 306 实际是角色详情面板假阳性；
  真正地图在 tail 阶段，菱形黑角 `darkRatio=0.200625`，面板仅 `0.003125`。
  分类器现用黑角比例区分，必须以新 live run 重新签发 strict-arrival 结果；详见
  `notes/strict-battle-arrival-gate-20260712.md`
- 纠正后两次重跑分别停在“队伍・装备”和“特别宝箱”教程说明页，均被正确拒绝且
  save hook 为 0；菜单已确认包含“开始任务”，START 不能关闭教程。静态追踪现已
  确认队伍页只是 normalized selector 2 的嵌套页；真实路径必须退回外层选 selector 4，
  经 `0x08086A54` 成功后由 `0x080871BE..C4` 建立 battle control，再以黑角与下一 A
  打开真实行动菜单的双门禁确认战场
- 独立 A/B 仅把 maps 第 40 行 `0x53DE10` 的 width 36→32，同路线得到
  `[32,44,8,22]`，因此 maps width/height 字段链已升级为 runtime；
  资源指针字段仍保持 code 验证。47 行已有持久 `rom_map_headers` 镜像和
  immutable-base、精确 offset、尺寸、ROM 对齐、LZ header/解压长度门禁的
  32-byte 安全写回
- units 旧结论已撤销：`0x0806E654` 实为读取单位 x/y，`0x53F298` 唯一消费者
  将其作为 u16 偏移查找；legacy units 回写已安全禁用，真实角色记录已迁移到
  `0x54241C`；loader-derived base destinations、两组槽数组和过滤 ID 区已命名，
  完整记录安全写回已建立；玩家界面属性名称仍待 UI correlation
- 真实角色定义表已定位并迁移到 units bank：`0x54241C`，63×`0xB4`；
  `tools/extract_character_definitions.py` 可重复提取；formation character ID 经
  `0x02022E34` 模板池复制到 `0x1D4` 战斗槽；WASM 首战样本已证明
  template slot 1 → battle slot 1 的前 `0xBC` 字节复制，但 template payload 与
  ROM raw record `0x5424D0` 仅前 7 字节一致，raw record 字段转换仍待 PC/LR 或
  受控 A/B 证明；后续 `0x5424D1` byte `0x0e→0x0f` A/B 已证明 raw record byte `+1`
  进入 runtime template 和 battle slot，units 结构身份达到 runtime 证据；
  后续静态闭合 7 个 base value、15×4 主槽、24×4 次槽和 9 个候选 ID，
  `rom_character_definitions` 镜像支持带 immutable-base、精确 offset/length、
  sentinel/active flag 门禁的整条 `0xB4` 写回
- character-stats 旧两表结论已撤销：真实成长表为 `0x545068`，63×`0x10`，
  `0x0806D964` 按角色 ID 读取并以 `growth*(level-1)/100` 写入模板；受控首战
  两因素 A/B 已证明 record 1 `+4` 进入 template/battle slot `+2`。
  `0x54507A` 和 `0x545200` 都是错位切片，后者 legacy 回写已禁用
- `battle-config@0x545458` 的旧 u16 场景配置解释已撤销：真实结构是
  32×16-byte 战斗技能/效果模板，`0x0806D85C` 按 effect ID 复制记录，并用
  byte `+0x0C` 与 u16 `+0x0E` 应用等级成长；effect 2 的 level-2 A/B 已证明
  growth `1→2` 只令 type-4 输出 `+7:4→5`，升级 runtime；地图场景表仍是 `0x53D910`
- items 与 skills 的 `0x546100` 冲突已拆分：两者 entries 原本逐字节相同，且无
  独立 item consumer；items 已改为 disproved tombstone，legacy item 写回保持
  diagnostic-only；skills 真表已纠正为 `0x545BE4` 的 94×16-byte 模板，
  `0x0806D910` 按 skill ID 复制前 10 字节，旧 `0x546100` 是 record 81 起的尾部切片
- 五个旧 late-ROM `story*` 候选其实是 `0x465B70` 音频主表所指 song descriptor
  的 `+4` 切片；m4a SongHeader byte 0 是 track count，`+4` 是 voicegroup，
  `+8` 是 track sequence pointers。`story-c/d/e` 保持 tombstone；`story/story-b` 已迁移为真实章节表
  `0x60C74/0x60D54`，并有独立安全写回
- maps width/height 消费链已定位到 `0x0201BE28..2B`，并通过 width 36→32
  A/B 从 `[36,44,9,22]` 变为 `[32,44,8,22]`
- maps 资源字段静态语义已纠正：`+8` 是 BG palette（旧 extractor 错用 `+14`），
  `+0C/+10` 是主/可选 coarse layout，`+14` 是 metatile attributes，`+18` 是
  collision grid；47 行长度公式全部通过测试。row 41 的同边界 EWRAM/PRAM/VRAM
  比对已令六项全部通过，maps 升为 runtime_verified
- battle configs、units、chapters、skills、story beats、legacy audio、maps、levels、
  character_stats、battle_config_data、encounter_zones、items 等无 ROM 身份的
  legacy 危险回写已禁用，只输出 unmapped 诊断；lossless `rom_*` mirror 继续作为
  安全写回入口
- audio/palette/message 身份已拆分：`0x53F138` 的旧 palette 身份已撤销，
  `palettes` slug 实为 `0x53EE98` motion/effect 参数表；`0x599634` /
  `0x08079668` 是消息表/分发器。真实 sound-ID 主表为 `0x465B70`，域 0..158，
  80 个非空 descriptor；dispatcher `0x0809AAC0`、track initializer
  `0x0809B1F4`、FIFO/DMA initializer `0x0809AE3C` 已闭合。运行时 hook 命中
  230 次并证明 ID 118→`0x0853D06C`，audio 升级 runtime；真实指针可达提取器
  已导出 217 条 track blob、23 个 voicegroup、387 个 tone 和 79 个合法 WAV；
  track opcode/控制流已结构化解码并生成单循环 MIDI；player 级 mixer、同-slot
  硬替换和跨-player 共享池已有运行时差分，每个 cue 的可听名称仍待完成。
  sound-ID 主表已有持久
  `rom_audio_sound_ids` 镜像和 immutable-base、精确 offset、ROM 范围/对齐、
  descriptor track-count 门禁的 8-byte 安全写回
- save descriptor 第二字段已纠正为 payload length/累计 stride，而非独立 SRAM
  offset；group 3..9 累计起点为 `0x2548..0x55B0`。WASM 已改用 `getSave()`
  导出真实 32KiB `.sav`。裸 group 均返回1并改变七处，但 wrapper 在战斗初始化
  上下文仍返回0且记录校验不成立；自然 caller 已归属 postbattle controller
  `0x080732B4` 的 state `0xF400`。首战开始自然命中为0，强制 state/gate 会卡在
  更早的结果 UI 阶段，不能代替真实胜利转换；下一有效路线是自动完成首战或取得
  genuine post-victory state 后命中 `0x08074F2C`
- 首战已建立可恢复的 WASM slot-9 checkpoint 闭环：稳定真地图重载仍得到 battle
  ID 40、map `[36,44,9,22]`、唯一 slot 1 `(4,4)`；新增 EWRAM dump 证明光标是
  `0x02026A78/79`，与单位记录 `+0xC4/+0xC5` 不同。地图/面板门禁改以纹理
  `edgeRatio` 为主，稳定地图约 `0.3435`、角色面板约 `0.1263`。当前 A→单步 Down
  只令光标到 `(4,8)`，单位未移动、natural-save hook 仍为0，故不得升级 SRAM
  结论；下一步必须闭合教程的真实 unit-action 子状态后再验证保存与冷加载。详见
  `notes/first-battle-savestate-checkpoints-20260712.md`
- 上述 checkpoint 后续确认是战前“查看战场”，不是可行动战斗；此假阳性已撤销。
  正确选择“开始任务”后，首战以真实两回合 `(4,4)→(4,7)→(4,10)` 完成，
  在宝箱 `(4,11)` 相邻格行动结束并进入胜利转场。木叶界面 UI Save 写出 32KiB
  存档；descriptor 0/2 的 19-byte `Naruto-KONOHASENKI\0` header、payload 和
  NOT-sum checksum 均有效，未使用记录保持全 FF。冷启动 Continue 识别 slot 1
  并恢复相同木叶状态，因此 save-state bank 已升为 runtime_verified。旧 verifier
  把 payload/checksum 起点提前19字节，旧“冷加载必须命中 0x08068AF0”也混淆了
  optional battle restore caller，均已纠正。详见
  `notes/tutorial-victory-save-load-runtime-20260712.md`
- `0x60D54` 受控运行时探针已从无效的 `0x1A` 专用 hook 改为 selector + 通用
  dispatch 追踪。scenario 39 运行时选中 `0x08031281`，共执行 25 次 dispatch，
  最终在 `0x0803142E` 的 opcode `00` 正常返回；live bytes 与 ROM 一致。该脚本
  不产生 battle state 是已解码的预期行为，story-b 已升为 runtime_verified。
- 备用章节实验的 checkpoint 导出已修正：旧实现可能复制同槽旧文件，现保存前
  清理 `.ss9` 候选并要求唯一新文件，加载后也显式释放全部 GBA 键。新的
  `木叶里 / 对战` 任务选择 checkpoint 已通过独立零输入重放；下一段从该页 A
  进入卡卡西对白，继续追到 selector hook。
- 浏览器键盘映射修正后，`PROBE_TAIL_REPEAT` 可复现重复选择。后续通用 dispatch
  探针证明该分支本身就是备用章节对白消费链，而不是必须进入战斗才算成功；runner
  现在会在终止证据出现时立即固化，避免后续输入覆盖最后 cursor。
- Phase 1/2/6 框架级完成

### 🔴 核心瓶颈（P0 — 逆向工程阶段）

| 目标 | 状态 | 备注 |
|------|------|------|
| tilemap 布局数据 | ✅ 已定位 | 32x32 grid at 0x14D000+ |
| 战斗配置表 | ✅ 已定位 | ROM 表(0x53D910, 0x53F298) + WRAM 地址均已确认，patch 生成可用 |
| 章节流程入口 | ✅ 两链已闭合 | `0x60C74/0x60D54` 两张 56 项脚本表；primary scenario 39→`0x31020`→三字节 `SetBattle(40,2)` 后接独立 `End`；alternate scenario 39→`0x31281`→25 次 dispatch→`0x3142E` opcode `00` 正常终止，均有 runtime 证据 |
| 资源提取（图片/音频） | ⚠️ 部分 | 47/47 tileset atlas、217 条音频 track blob、79 个 pointer-reachable WAV 和 80/80 整曲 PCM 已导出；track opcode、mixer/player 并发已闭合，cue 语义命名仍未完成 |

### 🟡 续作内容创作（逆向完成后）
- episode-01 剧情源稿细化
- 多章节内容模板

### 🟢 网页编辑器（逆向工程 100% 完成后启动）
- 技术方案：FastAPI 后端 + Vue 前端，部署于本服务器（14.103.49.74）
- 功能：地图编辑器、角色编辑器、技能编辑器、剧情编辑器、道具编辑器等
- 架构：多用户 WebSocket 协作编辑，ROM 在服务端操作

---

## 逆向工程路线图

### P0-Step 1｜稳定 mGBA 调试环境
**状态：✅ 已完成**

- `tools/mgba-headless-snapshot.py`：snapshot / watch / diff 三种模式可用
- `docs/next-action-plan.md`：方案 A 执行结果已记录
- 验证：watchpoint 命中 PC=0x08060FD2，cycle=182801696

---

### P0-Step 2｜定位 tilemap 布局数据（Phase 4 收尾）

**状态：✅ 已完成**

**现状：**
- Tile 描述表 `0x596D5C` 已完整分析（312行×16字节，每行含 tile data/attribute/layout/palette 4 个指针）
- tilemap 布局数据（2D 瓦片 ID 网格）已定位！

**发现：**
- 多个 tilemap 数据区位于 ROM: 0x14D000, 0x195000, 0x1CB000 等
- 格式：2字节/条目，32×32 网格 (1024条目，2048字节)
- 编码：低10位为 tile ID (0-311)， bits 10-15 为 flip/调色板属性

**方法：**
1. 用静态分析扫描 ROM 寻找 tile ID 有效范围内的 2D 网格模式
2. 通过对比验证找到多个有效的 tilemap 数据区

**交付物：**
- `notes/map-format.md`（完整版）✓
- `notes/map-addresses.md`（完整版）✓
- `tools/import_map.py`（完整 patch 生成逻辑）✓

---

### P0-Step 3｜定位战斗配置与角色定义

**状态：⚠️ 部分完成**（positions、maps 全资源、角色定义及成长表已有运行时闭环；units 已有结构字段和安全 lossless 写回，剩余玩家属性命名仍未完成）

**已确认 ROM 数据表：**
- ❌ 旧 `0x0853F298` 单位 ID 映射结论已撤销；唯一消费者把它作为 u16
  对象/渲染偏移查找，legacy 回写已禁用
- ✅ 真实角色定义表：`0x0854241C` / file `0x54241C`，63×`0xB4`；
  `tools/extract_character_definitions.py` 已建立，`sequel/content/units/bank.json`
  已迁移；runtime 样本已把战斗槽 character ID 和模板槽闭合到 ID 1 / ROM
  `0x5424D0`；`0x5424D1` 单字节 A/B 已动态闭合 raw record byte `+1` 到模板字段；
  两组槽数组及过滤候选区已按 loader 命名，整条记录可受保护写回
- ✅ 战斗场景配置表：`0x0853D910` / file `0x53D910`，8 个有效条目 × 16 字节
  - 条目格式：u16 tiles_x, u16 tiles_y, u32 ptr1, u32 ptr2, u16 flag, u16 extra
  - ptr1：12 字节头 + 原始 tile 数据（u16/tile）
  - ptr2：LZ77 压缩数据（解压后 384 字节，调色板/属性数据）
- ✅ 状态机函数指针表：`0x0853F1C0` / file `0x53F1C0`，u32[60]，指向 0x0812Fxxx
- ✅ WRAM 分配表：`0x0853D848` / file `0x53D848`

**已确认 WRAM 战斗数据地址：**
| WRAM 地址 | 大小 | 说明 |
|---|---|---|
| `0x0201BE28` | 4 字节 | map width/height 及 `>>2/>>1` 派生尺寸 |
| `0x02021E2C` | 网格相关 | 单位坐标查找表基址 |
| `0x020240C0` | `0x17C4` 总区间；`0x1D4*N` | 主战斗数据/单位数组物理基址（单位 stride 468 字节） |
| `0x02024294` | `0x1D4` | 第一个可分配/常用单位槽（slot 1） |
| `0x02022E34` | 24×`0xBC` | 角色模板池；模板 `+0` 为 character ID |
| `0x02022EF0` | `0xBC` | 角色模板池 slot 1；旧 character-stats WRAM 假设已撤销 |
| `0x02026804` | 8 字节 | 战斗控制标志 |

**交付物：**
- ✅ `notes/battle-config-format.md` — 完整版（ROM 表、WRAM 布局、LZ77 格式、代码引用）
- ✅ `notes/unit-skill-addresses.md` — 完整版（单位 ID 表、场景配置、状态机函数）
- ✅ `notes/unit-id-mapping-analysis.md` — 完整版
- ✅ `notes/battle-scenario-config.md` — 完整版（8 个场景条目解析）
- ✅ `tools/import_battle_config.py` — 可生成 ROM patches + WRAM cheat patches
- ✅ `tools/extract_positions.py` — 从 ROM `0x5461C4` 编成矩阵可复现提取 48×3×12 条记录；记录 `+2/+3` 已静态确认为初始 x/y
- ✅ positions ROM→WRAM 静态链路：`0x0806E41E/0x0806E71E → 0x0806AC70 → 0x0806AA64`；单位 stride 已纠正为 `0x1D4`
- ✅ positions 编辑/回写链：通用 ROM mirror 导入 `rom_positions` 1728 行并保留完整 `0xB8` 原始记录；构建器验证 index、ROM offset 与长度后写回真实矩阵
- ⚠️ 旧 `unit_positions` CRUD 仅是运行时编辑概念，没有一行一 ROM 地址证据，不计入真实回写完成度
- ✅ runtime WRAM dump 已通过网页 WASM 探针取得并与 ROM 编成记录唯一关联；CLI
  headless 仍无按键注入与 PC/LR 联合采集能力

---

### P0-Step 4｜定位章节流程入口（Phase 3 收尾）

**状态：✅ 主流程入口已完成；脚本 opcode 全语义仍属后续字段工作**

**2026-07-12 纠正：**
- `0x0808F544` 根据状态 `+0x18` 在 `0x60C74` / `0x60D54` 两张
  56-entry script pointer table 之间选择，并按 scenario ID 索引；
- WASM hook 捕获 primary scenario 39 → `0x08031020`，脚本游标
  `0x08031070` 的 `1A 28 02 | 00`（三字节 SetBattle + 一字节 End）将 battle ID 40 写入状态并最终到
  `0x02026805`；
- `story` bank 已迁移为 primary/runtime，`story-b` 为 alternate/runtime；
  旧 late-ROM `story*` 资源切片结论已撤销。

**已完成：**
- 静态分析：遍历 38 个 late-ROM 表候选，全部为视觉/资源描述表
- 代码引用分析：定位到 9 处对战斗配置表（0x0853D910, 0x0853F298）的引用
- 章节 ID 序列搜索：在 0xBD713, 0xC1717 等处发现 u16(1,2,3...) 模式，但未找到明确配置表

**Runtime 验证尝试：**
- 尝试 1：加载 savestate - 失败（所有 save 文件为 0xFF，未初始化）
- 尝试 2：设断点 0x080894DE - 未命中（游戏卡在 UI 循环 0x085CCDxx）
- 尝试 3：设断点 0x0806E654 - 未命中（无用户输入无法到达战斗）
- 尝试 4：frame advance + breakpoint - 停留在 video/UI 子系统，无法进入主游戏逻辑

**环境限制：**
- mgba-sdl 0.10.1 缺少 `--script` 参数支持
- CLI 调试器无法注入按键输入
- 无有效 savestate 文件

**交付物：**
- `notes/chapter-entry-points.md` - 运行时验证尝试记录 + 静态分析
- `notes/chapter-flow-format.md` - 格式分析（待 runtime 验证）

---

### P0-Step 5｜资源提取链路（图片/音频）

**状态：⚠️ 字节提取、整曲渲染及 player 运行时完成，cue 语义部分完成**

**现状：**
- 47/47 tileset atlas 已由真实 descriptor 指针导出
- m4a SongHeader 已纠正：`+4` voicegroup，`+8` track sequences
- 已导出 217 条 track blob、23 个 voicegroup、387 个 tone、79 个 WAV
- 217 条 track 已结构化解码为 18,090 条命令和 6,750 个 note/tie；1,287 个
  控制流目标全部落在已知 track 范围
- PATT/PEND/GOTO 已按单循环策略执行；80/80 sound ID 已生成标准 MIDI，
  217 条 track 共发出 17,202 个时间线事件
- 16,180/16,180 note 已解析 terminal tone：16,169 个 DirectSound note 覆盖
  79/79 waves，其中 5,340 个经 drum table；剩余 11 个明确为 0x0C PSG/noise
- TIE 生命周期已纠正为 90 条：25 条由 EOT 释放、19 条由 FINE 进入 release、
  46 条在单循环 GOTO 边界仍活跃；只保留后 46 条为 open tie，不伪造释放
- DirectSound nominal pitch-step 已按 `0x0809A998` 的 ROM 两表与 UMULL high32
  精确整数公式闭合；16169/16169 DirectSound note、79/79 waves 均产生正 step，
  23-bit mixer phase 与本 ROM 15768 Hz / divFreq 532 也已代码锁定
- KEYSH/BEND/BENDR/TUNE 与当前 MODT=0 LFO 状态已接入 16169 条 DirectSound
  note，971 条 noncenter，零无效 step
- MP2K triangle LFO/LFODL/MOD 的逐 tick pitch automation 已闭合；对活跃 note 共
  产生 30937 次有效 step 更新（BEND 323、LFO 30413、MOD 201），零无效；open TIE
  只追踪到单循环边界
- `TrkVolPitSet→ChnVolSetAsm` 的两级 volume/pan 整数链已闭合；16169/16169
  DirectSound note 均得到有效双声道系数，活跃 note 内 39 次 VOL 更新全部有效；
  MODT=1/2 由合成向量锁定，但实际 track 中 MODT/LFODL 均为 0 次。timeline 现为
  38979 events（21328 pitch-state、449 mix-state）
- DirectSound ADSR/release/pseudo-echo 与 master gain 状态机已按
  `0x08099EC8..0x08099F82` 代码锁定；16169/16169 note 共 4 种有效 tuple，零非法。
  状态按 SoundMain mixer invocation 而非 MP2K tick 推进
- 11/11 PSG note 已闭合至 CGB channel-4 寄存器向量、NR43 时钟和 15/7-bit
  LFSR；实际语料均为 sound ID 144、NR43=`0x14`，三档 NR42 向量已代码锁定
- DirectSound 16169/16169 note 的 forward-linear 插值、跨 sample/loop、非循环
  停止、reverb seed、signed-byte modulo-256（非饱和）累加和 stereo WAV 写入已锁定；
  8442 条非循环、7727 条循环语料全部走此路径
- MP2K tempo threshold=150、同一 SoundMain 内 0/1/多 tick、linked-player 递归顺序、
  每次 264-frame mix 与 6×264 DMA/reverb ring 已代码锁定；多 tick 间不得插入混音
- 持久 WAIT/GOTO/PATT/REPT command VM 已让 217/217 track 各运行 2048 ticks：累计
  39825 commands、163 次真实 GOTO，79 条 FINE 终止、138 条在时长边界继续运行
- 10 DirectSound pool + 4 fixed CGB 的 free/released/active 选择、priority/track-address
  tie-break、steal、newest-first track chain 与 same-key EOT 已代码锁定
- persistent TEMPO/PRIO/VOICE/VOL/PAN/pitch/LFO registers 已让全部 track 在 2048 ticks
  产生 17546 NoteRequest、21 EOT、79 FINE stop，复用现有 decoded commands/整数公式
- request→terminal tone→allocated channel 已闭合：全库 17546 请求全部到达解析/分配
  路径；真实 sound 1 DirectSound 与 sound 144 CGB noise 向量、drum-root pitch、
  mid-note pitch/mix dirty 传播、自然停止后的 track unlink 和首个 264-frame PCM hash
  均已测试。bounded allocator rejection 不能冒充真实 SoundMain 丢音统计
- player 级整曲 SoundMain 与 DirectSound+CGB 联合 PCM 已闭合：80/80 sound ID
  均生成非静音 WAV，62 个 one-shot 自然结束，18 个 loop song 的全部 138 条
  GOTO track 均跨过首次 GOTO；首次 GOTO 上 21 个 active TIE 保持跨边界
- 独立 mGBA 差分已闭合：sound 101 的 79/79 个 Direct FIFO 块逐字节一致，sound 144
  的 68/68 组可读 CGB register/channel-4 status 一致；两条路径均自然结束
- player-slot 差分已闭合：活跃同-slot sound 101→102 硬替换 27/27、slot 1/2
  linked-player DirectSound 共享池 25/25、跨-player 固定 CGB channel 竞争 68/68；
  equal-priority active owner 稳定为低地址 `0x03006178`
- 播放 wrapper 共 290 个 callsite：278 个立即数调用覆盖 38 个有效 ID，12 个动态
  来源；仅四个 A 级与四个 B 级语义候选有当前证据，72 个仍保持 `unknown`，尚无
  官方名称来源

**方法：**
1. 从 `0x596D5C` descriptor 链提取 tileset PNG（已完成）
2. 从 `0x465B70` sound-ID → SongHeader → voicegroup/track/wave（已完成）
3. 闭合同 player hard replacement、linked-player 并发和全局 CGB pool 竞争（已完成）
4. 动态对照显式 `MPlayStop` 与 FINE release，并为 80 个 cue 建立有来源语义名称（下一步）

**交付物：**
- `tools/extract_tileset.py`
- `tools/extract_audio_assets.py`
- `tools/build_controlled_audio_runtime_probe.py`
- `tools/compare_mgba_audio_capture.py`
- `tools/compare_mgba_cgb_capture.py`
- `tools/build_delayed_audio_retrigger_probe.py`
- `tools/compare_mgba_retrigger_capture.py`
- `tools/compare_mgba_linked_audio_capture.py`
- `tools/build_cross_player_cgb_probe.py`
- `tools/compare_mgba_cross_player_cgb_capture.py`
- `tools/extract_audio_cue_calls.py`
- `artifacts/audio/mgba-sound101-full-differential.json`
- `artifacts/audio/mgba-sound144-cgb-differential.json`
- `artifacts/audio/mgba-same-player-101-102-differential.json`
- `artifacts/audio/mgba-active-retrigger-101-102-differential.json`
- `artifacts/audio/mgba-linked-player-101-106-differential.json`
- `artifacts/audio/mgba-cross-player-cgb-143-144-differential.json`
- `notes/m4a-emulator-differential-20260713.md`
- `notes/m4a-player-slot-runtime-differential-20260713.md`
- `notes/audio-cue-semantics-20260713.md`
- `notes/resource-locations.md`

---

### P0-Step 6｜可变长对话（Phase 2 收尾）

**现状：**
- 同长替换可行，变长 redirect 需要已验证的空闲 ROM 区域

**方法：**
1. 用 mGBA 在游戏运行时检测 ROM 空闲区域（写入后读回为 0xFF 且不被读的地址）
2. 验证后实现 pointer_redirect 策略

**交付物：**
- 空闲 ROM 区域验证文档
- `import_dialogue_var.py`（变长 redirect patch 生成）

---

### P0-Step 7｜全面测试闭环

**现状：**
- `docs/testing-checklist.md` 已建立
- 离线无 OCR 子闭环已完成：`tools/run_offline_e2e.py` 执行正式 build checks，核对
  输出 SHA-1，并用原生 mGBA + tracked checkpoint 断言 battle 41、map 36×44、
  Naruto `(4,10)`、Iruka `(4,4)`；持久报告在
  `artifacts/e2e/offline-smoke-20260713/`
- 编辑器 DB 隔离正式构建已闭合：完整 mirror DB 中只改 map 40 width 36→32，正式
  build 后 reserved region 之前仅 `0x53DE10:0x24→0x20`；测试同时修复了旧
  cutscene 16×pointer generator 与 8×pair schema 不一致、以及未编辑 chapter mirror
  与 scenario 39 semantic relocation 冲突
- 私有 build-ID HTTP 所有权已闭合：owner 可查状态/下载，其他登录用户得到 403；
  “最新 build”改按创建插入顺序而非随机 UUID 字典序。公开 UUID ROM endpoint 保持
  显式 capability URL；浏览器下载现通过带 Bearer 的 fetch/blob 并显示下载中/错误；
  WebSocket 改为首帧 JWT+显式 build ID，拒绝跨用户订阅且不再泄露服务器 ROM 路径
- build-ID 子进程隔离已闭合：`DB_PATH` 贯穿 dialogue 与全部 generator，外部
  `BUILD_OUTPUT_DIR` 的 ROM/build report/automated report 三件套均被当前请求验证，
  全局 build 哈希不变；backend 支持注入 BUILD_CWD/PROJECT_ROOT，并在 trigger 时用
  SQLite backup 固化 build-ID 专属 DB snapshot
- 浏览器 UI/API 鉴权下载已闭合；玩家可见 OCR 与剧情→战斗→存档长程回归仍未完成

**方法：**
1. 在现有离线 runtime smoke 与 editor DB 隔离 build 上追加浏览器 API 与跨平台 OCR
2. 每完成一个格式的 patch 生成，都要跑一遍 checklist

**交付物：**
- `tools/run_offline_e2e.py`（当前无 OCR runtime smoke）
- `tests/test_editor_build_integration.py`（临时 DB 与临时 build ROOT）
- 后续跨平台 mGBA + OCR 验证
- 所有格式的验证报告

---

## 当前推荐顺序

### 2026-07-10 Positions 与构建安全更新

- positions 真实 ROM 来源已更正为 `0x5461C4` 编成矩阵，记录 `+2/+3`
  为初始 x/y；旧 `0x53D914` 结论已撤销。
- 新增可重复提取器 `tools/extract_positions.py`，共提取 `48×3×12=1728`
  条完整 `0xB8` 记录，并通过 `rom_positions` 无损回写。
- 单位物理数组基址是 WRAM `0x020240C0`，stride `0x1D4`；
  `0x02024294` 是 slot 1。
- 补丁冲突门禁发现旧 battle-config 模板会覆盖 `0x547934+`；
  已停止将未映射的 `scenario_id` 当 ROM 索引。
- 32/32 bank 已通过基准 ROM 字节一致性门禁；动态消费路径验证仍在进行。
- 新增只读 WASM 导航/WRAM 轮询探针 `play/_scripts/runtime-formation-probe.js`：
  可按 START → 新游戏 → 连续 A 计划导航，读取 `0x020240C0` 单位数组，并将
  `+0xC4/+0xC5` 坐标与 positions bank 匹配；已验证 core 就绪门禁与真实 WRAM
  读取。后续真实部署运行已进入首战，两次观察到 slot 1 `(4,4)` 并唯一匹配
  group 40 / variant 0 / record 0，因此 positions 已升级为 `runtime_verified`。
  当前导航已闭合 maps width/height A/B，并继续用于闭合真实角色定义的运行时证据。

### 2026-07-10 Bank 元数据审计基线

- 新增 `tools/audit_re_completion.py`，可重复检查 32 个 `sequel/content/*/bank.json` 的表偏移、格式字段、条目、验证标签和 Markdown 文档覆盖。
- 审计产物为 `notes/re-completion-audit.json` 与 `notes/re-completion-audit.md`。
- 首次审计结果为 23/32；随后已纠正错误偏移并从基准 ROM 重新提取。审计现采用双轨规则：23 个有效 bank 必须有非空 entries 和 ROM fidelity；9 个 `disproved` tombstone 必须为空、记录负证据并禁写回。调查闭合为 32/32，但这仍不代表动态语义或真实回写完成。
- 最新严格审计分布为 0 个 `static_verified`、10 个 `code_verified`、13 个
  `runtime_verified`、9 个 `disproved`；仍不能作为“100% 完成”的单独证据。

### 2026-07-11 Character growth 消费链修正

- 从精确地址零引用改为扫描 `0x545000..0x545458` 邻域，找到
  `0x0806D998 -> 0x08545068`，并反汇编闭合 `0x0806D964` 消费者。
- 真实表为 63×`0x10`，地址公式 `0x545068 + character_id*0x10`；ID 57/58
  分别复用 physical record 8/15。
- 七个 u16 成长字段写入模板 `+0x0E/+0x08/+0x02..+0x06`；首战 level 1
  会令正常增量为零，因此使用严格两因素插桩 A/B 避免伪阴性。
- character 1 record `+4` 从 100→200 后，template 与 battle slot 唯一变化为
  `+2: 15→16`，结构升级为 runtime_verified。
- 人物信息页与同边界 EWRAM 已把 template `+2/+3/+4/+5/+0A/+0C/+0E/+10`
  分别关联为攻击/防御/敏捷/移动/印/当前体力/体力上限/经验；growth 的体力、
  攻击、防御、敏捷、移动字段可同步命名。随后以 `0x08089AE0` 的标签行和数值读取
  行直接闭合 `template +8 = 查克拉容量`、`template +6 = 忍具数上限`，对应 growth
  `+2/+C`；两个运行值同为 5 不再构成歧义，也不再需要 UI A/B
- 章节最小语义创作链新增严格 codec；在 `End(00)` 与三字节
  `SetBattle(1A,id,mode)` 基础上，进一步沿 handler 闭合并开放
  `ShowPortrait(02,slot,portrait,expression)`、`UpdatePortrait(04,...)`、
  `SetSpeakerLabel(08,label_id)`、`AudioCue(1B,cue_id,mode)` 与
  `RenderText(01,encoded_text_hex)`。portrait 参数复用
  已闭合的 63×5 visual matrix 与 variant 5 特殊 pair，并限制真实 slot/记录边界。
  受控 primary
  scenario 39 探针选择 codec 输出
  `0x0809E800: 1A 28 02 | 00`，恰好 dispatch 两次并将章节/战斗状态 39→40。
  这证明 authoring bytes 的运行时因果，但生产 allocator、pointer+payload 原子回写和
  对话 opcode 子集仍未完成，短路线也未冒充 strict battle-map arrival
- alternate scenario 39 已由 control-aware text walker 完整拆成 25 条 command，边界与
  runtime 分布 `1B×1/02×5/08×8/01×8/04×2/00×1` 一致，末端精确落在
  `0x0803142E`。`1B` 已由 `0x08097C9C→0x08097140` 闭合为播放/等待/停止音频，
  `08` 已由 `0x080979E8` 与 12-byte 表 `0x085A57C4` 闭合为说话人标签选择；`02`
  按需创建 portrait slot 并等待转场，`04` 更新既有 slot，二者均通过
  `0x08096138` 选择 portrait/expression 资源。`01` 复用 `0x0806626C` 的控制感知
  token walker，并只承诺已编码字节的无损创作，不把汉化字形误当作 Unicode 同一。
  scenario 39 完整 25-command/`0x1AE` 字节现可 byte-exact codec 往返；analyzer 仍负责
  地址/raw 调查证据。生产 importer 已在独立 `0x5F8000..0x5FFFFF` 分区完成四字节
  对齐 allocator、immutable-base 指针校验与 payload+pointer 原子计划；真实构建将
  scenario 39 的 430 字节语义往返 payload 写到 `0x5F8000` 并重定向到 `0x085F8000`。
  旧 DB pointer-only 写回已禁用，避免绕过 codec。随后 runtime trace 捕获 selector
  实际选择 `0x085F8000`、25 次 dispatch，并在 `0x085F81AD` 的 `00` 正常终止，
  allocator→pointer→payload→interpreter 因果链已闭合
- skills initializer 字段链已纠正为 source `+0→runtime+1`、`+1` skip、`+2..+9`
  原位复制，`+A/+B` 另有 consumer。自然“术列表”控制器把 skill ID 1 与 `0x80`
  合并并命中 initializer；只改 row 1 `+4:6→7` 后，runtime `+4` 与可见攻击力
  `6×3→7×3` 同步改变，因此 skills 升级 runtime_verified
- skills 的非详情字段进一步闭合：`+0` 是战斗显示/动画族；`+A/+B` 构建前置技能到
  可联动候选的映射；`+C/+D` 是最多两个 ID 的资格白名单。它们均有明确消费者与
  错误反馈路径。自然详情另闭合 `+4` 攻击力、`+5` 距离、`+6` 成功率、packed
  `+7` 次数/直线和 `+8` 范围；`+2/+3/+9` 继续保持未知
- 战斗动作详情渲染器已锁定为 `0x080708BC`：action ID 高位清零时调用 effect
  initializer `0x0806D85C`，置位时才在 `0x08070906` 调 skills initializer
  `0x0806D910`。教程“忍者组合拳”是低位 effect 2，解释了旧 skills 探针零命中。
  旧强制 high-bit 诊断只作为负边界保留；现已由自然术列表 skill 1 的稳定可见 A/B
  取代，不能再用旧诊断的零可见差异否定新证据
- function-pointers 已从“11个看似有效 Thumb 指针”推进到真实 dispatcher 消费链：
  `0x08061D8C` 从 sentinel base `0x53D5F0` 按一基 ID 取表项并写入 task callback，
  11个 wrapper 均把对应 ID 传给 `0x08061C58`。自然标题人物图鉴路线两次命中
  ID 2 / entry `0x0853D5F8` / pointer `0x08061C99`；只把该四字节槽替换为相邻
  wrapper 3 后，同一输入提前分叉并留下未完成资料面板，因此升级 runtime_verified。
  variant 在再次 dispatch ID 2 前已分叉，其专用 scratch 为零，证据不把它误写成
  第二次 pointer hit
- `encounter-zones` 已证伪：其47行完整重复 maps，所谓 `zone_id` 实为已运行时
  追踪的 map `flags`/渲染配置字段；旧 bank 现为空且禁写。
- 历史 `cutscene-scripts@0x53DF70` 已修正为两个相邻的四记录视觉资源表：
  `0x08072EDC` 按 ID 0..3 解压 gfx/palette，并把第二组 pair 交给 sprite task，
  因此升级为 code_verified，但不再作为剧情脚本证据。
- 历史 `battle-encounters@0x542384` 已纠正为从真实 `0x54229C` 视觉资源表
  第14条 `+8` 处开始的错位切片；真实24条记录由剧情 opcode loader 消费，
  每条三条 LZ77 流，因此升级 code_verified，旧 editor 行禁写。
- 历史 `map-events@0x53EB08` 已纠正为完整 `0x53E698` 256×8-byte handler
  pair 表的 index 142 起始切片；消费者按 runtime state byte 同时选择 primary /
  secondary callback，因此升级 code_verified，旧47行 editor view 禁写。
- `battle-handlers@0x53E6D8` 又被证明是同一 handler-pair 表的 records 8..14
  重复视图，现为空、禁写的 disproved tombstone。
- `palettes` / `map-sprites` / `sprite-animations` 三个重叠目录已拆清：前两者
  分别修正为15条 motion/effect 参数与43条 sprite pair 并 code-verified；后者
  是 pair 24..42 的重复视图，已 tombstone。三个 legacy editor shape 均禁写。
- `fonts` 旧表跨入 handler pairs，已证伪；`levels` 修正为 `0x5459C8`
  45×12 effect/stat progression records；`resource-pointers` 修正为5×16嵌套
  descriptor。后两者均由消费者升级 code_verified。
- levels 的真正 Continue 已复现：Naruto level 1、经验100/250、训练点`+BA=0`；
  自然 selector 证明“移动→对战→木叶丸对白”消费 primary scenario 41 脚本
  `0x08031A12..0x08031D5F`，44 次 dispatch 后 opcode 00 正常终止、无 SetBattle，
  随后 UI 是 story 后任务准备而非标题图鉴。`A→B→Down×2→A` 曾产生瞬时 battle41，
  但完整 settle 回到 battle/map=0 的队伍页，已作为控制器假阳性撤销；真正入口必须
  settle 后仍可操作。目标仍是 A880=3 / level2 / 分配前训练点1
- scenario 41 开始任务控制流已纠正：`0x08097C78` 是 opcode `0x1A` handler 的
  中间指令而非 SetBattle 函数入口；story-only script 已留下 battle ID，正常开战由
  selector 4 → `0x08086A54 return 1` → `0x080871BE..C4` 复制到 battle control，
  不要求新增 selector/opcode hit。下一运行探针按该三段链路签发，详见
  `notes/battle-start-control-flow-20260713.md`
- `data-table-a/b` 已从20条尾片恢复为46条人物资料文本和79条战斗消息文本；
  `tile-assets` 已恢复为79×0x44战斗视觉 descriptor，三者均 code-verified。
  `menu-ui` 随后由 `0x08096138` 纠正为63×5 visual variant matrix，加 special
  variant 5 pair；旧20项是records 61–62。record 7 / variant 0 的单因素 pair A/B
  又令同一步 `ShowPortrait(1,7,0)` 从卡卡西变为小樱，因此升级 runtime_verified。
  当前无 static bank。
- `data-table-a` 的 selected-pointer hook 已通过自然标题人物图鉴闭合。两边均在
  `0x0808B1A4` 命中一次 character 0 / entry
  `0x085A143C`；只替换该四字节指针为 entry 7 后，目标从 `0x0859F988` 变为
  `0x0859FDE8`，可见多行人物简介同步改变，因此升级 runtime_verified。旧 state
  `0x20` checkpoint 属于另一套三栏 UI，不再作为此 reader 的前置状态。
  后续复放确认原输入没有加载随附 save；该纠正不影响 reader A/B，但禁止把它当作
  存档进度或 levels 入口
- 已新增 base-ROM 可独立重放的真实 battle 41 actionable checkpoint：Naruto
  `(4,10)`、Iruka `(4,4)`、map 36×44，strict arrival 全过。基于该边界的三条
  专属探针进一步排除了入场期 `resource-pointers`、普通忍术下的组合关系 reader、
  以及无效目标提示属于 `data-table-b` 的假设；三项严格保持 code_verified，下一步
  从有效攻击/技能事件捕获真实运行 ID。详见
  `notes/remaining-runtime-bank-probes-20260713.md`。
- battle 41 的最小编成诊断又把伊鲁卡移到相邻 `(5,10)`：敌对时可被范围光标选中，
  但教程拒绝直接攻击；同阵营时提交移动直接进入教程对白，skill-relation 专属 scratch
  仍为零。该路线是剧情假阳性，不再作为组合技能入口继续扩展
- `character-stats-b@0x545200` 被证明是 record 25 `+8` 的错位别名，保留
  disproved tombstone；错误 bytes 写回已改为 diagnostic。
- 交付：`tools/extract_character_growth.py`、
  `tools/build_character_growth_probe.py`、验证器和回归测试；完整证据见
  `notes/character-growth-runtime-chain-20260711.md`。

### 2026-07-11 Save-state 首战 SRAM 负结果

- WASM 探针现会在导航前后读取七个已知 SRAM 记录并验证 19+1 checksum；
- 标题→新游戏→首战路线成功，但七条记录均保持 `FF×20`，证明该路线不自动保存；
- save-state 仍为 code 证据，下一步必须定位并执行显式保存菜单，或在
  `0x08068684` 捕获真实写处理器调用；
- 结果与哈希见 `notes/save-state-wasm-probe-20260711.md`。

### 2026-07-10 u32 指针表回写进展

- 新增带索引边界、48 Mbit ROM 地址范围、Thumb bit 和数据指针对齐检查的通用
  u32 指针表真实回写 helper，并补充 6 项单元测试。
- `map_events` 与 story B–E 当前可生成 88 个真实表补丁，不再写 audit 保留区。
- 安全检查发现 `rom_battle_handlers` 和 `rom_map_sprites` 共 61 行 DB 数据使用陈旧
  `_rom_offset`，现已拒绝回写；下一工作周期需从 `rom/base.gba` 重新导入并验证。
- `battle_encounters` 的旧混合值解释仍需纠正；`cutscene_scripts` 已确认是八个
  视觉资源 pointer pair，不是脚本表。详见
  `notes/cutscene-visual-resource-consumer-20260712.md`。
- 第二批已把 data table A/B、function pointers、menu UI、resource pointers、
  sprite animations、tile assets 共 135 行转换为带严格校验的真实 ROM 回写；旧
  audit-only 不可达代码已删除。palette 因表冲突证据不足仍保持隔离。

```
P0-Step 1（mGBA调试） ✅
       ↓
P0-Step 2（tilemap） ✅
       ↓
P0-Step 3（战斗配置） ✅（ROM 表已定位，patch 生成可用）
P0-Step 4（章节流程）
P0-Step 5（资源提取）
P0-Step 6（变长对话）
P0-Step 7（测试闭环）
       ↓
100% 逆向覆盖
       ↓
网页编辑器开发
```

---

## 不该现在做的事

1. 不要现在开始写大量剧情 —— 格式还没定，内容随时可能废弃
2. 不要现在开始建网页编辑器 —— 等逆向覆盖到 80%+ 再动手
3. 不要把手工十六进制修改当正式开发流程 —— 一切要走 pipeline

---

## 网页编辑器架构（逆向完成后）

**技术方案：** FastAPI + Vue + SQLite

**服务器：** 14.103.49.74:443（Debian 12，2核/4GB）

**架构图：**
```
用户浏览器 (Vue)
    │ HTTPS
[FastAPI 服务]
    │
 ┌──┼──┐
 │     │
SQLite  ROM文件
(队列)  (本地)
 │
WebSocket
(协作编辑)
```

**功能模块（逆向完成后按序开发）：**

| 模块 | 说明 |
|------|------|
| 对话编辑器 | 文本表单，调用 import_dialogue.py |
| 地图编辑器 | Canvas 瓦片地图，调用 import_map.py |
| 角色编辑器 | 数值表单，调用 import_battle_config.py |
| 技能编辑器 | 效果链配置 |
| 道具编辑器 | 表格编辑 |
| 剧情编辑器 | 分支对话树 |
| 构建验证 | build_mod.py 输出可下载 patch ROM |

**优先级：** 对话 > 地图 > 角色 > 技能 > 道具 > 剧情
