# GBA 木叶战记逆向工程交接（2026-07-11）

> 2026-07-13 continuation：本文前半保留历史调查脉络；最新事实以本节、
> notes/current-re-progress-20260711.md、docs/sequel-roadmap.md 和
> artifacts/runtime-checkpoints/README.md 为准。story-b 已闭合为
> runtime_verified；当前主线已转到 scenario 41 真实战斗、战后升级和 levels bank。

## 0. 2026-07-13 当前交接快照

### 0.1 Git 与总体完成度

- 工作分支：task/units-character-definitions；
- Draft PR：https://github.com/AltairCardinal/gba-naruto/pull/1；
- 本轮开始时 HEAD：59dba83 feat(audio): verify player slot runtime behavior；
- 调查闭合审计：32/32；
- 其中 23 个有效数据 bank、9 个 disproved 且禁写回的 tombstone；
- 证据分布：13 runtime_verified / 10 code_verified / 9 disproved；
- 运行时 bank 覆盖率为 13/23，约 56.5%，不能写成整个逆向工程已完成 56.5%，
  更不能把 32/32 审计写成运行时 100%。

仍为 code_verified 的十项：

1. battle-encounters；
2. cutscene-scripts；
3. data-table-b；
4. levels；
5. map-events；
6. map-sprites；
7. palettes；
8. resource-pointers；
9. sappy-engine；
10. tile-assets。

### 0.2 scenario 41 新进展

story-only scenario 41 终止后的 preparation menu 已完成逐项映射：

- A：队伍/装备；
- Down,A：查看战场；
- Down,Down,A：“开始任务？”；
- Down,Down,Down,A：保存。

在“开始任务？”默认“是”上输入 A 后，连续六个采样周期稳定保持：

- battle ID 41；
- map 36×44 / grid 9×22；
- Naruto slot 1 (4,10)；
- Iruka slot 2 (4,4)；
- 旧 `strict battle arrival` 四项全过。

2026-07-15 对 `.ss9` 的 CPU/IWRAM/EWRAM 与协作任务栈复核推翻了“已经进入战斗
控制器”的语义：该白框 state 的 task 2 链为 `0x0808F928 → 0x08088F10 →
0x0807509C → 0x0806F718`，当前活动 unwind 中没有 `0x0808F957`，因此保存时位于 pre-controller
lineup/deployment。旧 strict predicate 只能识别 battle/map 资源已装载，不能识别
`0x080732B4` 已启动。当前边界不证明真实战斗入口、玩家接管、胜利或升级；Naruto 仍为
level 1 / EXP 100，A880=0，template +0xBA=0，secondary levels 仍为 FF；levels 必须继续
保持 code_verified。

紧凑证据：

- artifacts/runtime-checkpoints/scenario-41-battle-entry-evidence.json；
- notes/scenario-41-battle-entry-runtime-20260713.md；
- notes/levels-runtime-probe-20260713.md；
- artifacts/runtime-checkpoints/scenario-41-savestate-context-evidence.json；
- notes/scenario-41-savestate-context-reanalysis-20260715.md。

### 0.3 新诊断工具与已排除误区

tools/build_battle_start_runtime_probe.py 覆盖 prebattle menu、start-task、lineup、
lineup exit 和 deployment 边界。caller wrapper 的 lineup 计数位于 scratch +0x20，
exit hook 已使用独立 scratch +0x40，避免一次正常返回被误计为两个调用。当前构建
SHA-256：

ca701983f5d566dc468f57e49e00ae2d61d8ef659395ed84284057514e1d52f5

从“开始任务？”checkpoint 加载新 probe ROM 后，上述早期 hook 仍为零。最新调查已证明：

- ss9 的 gbAs 数据不包含 ROM pages；
- loadState 后 0x0808F894 仍读到新 probe BL；
- `.ss9` 中的游戏 task context 可离线恢复；白框 checkpoint 的当前活动链明确恢复在
  `0x0806F718` continuation，且不在 `0x080732B4` 调用内；这不否定保存前的历史调用；
- 不需要也不应开发“savestate 后重注入 ROM”。

下一门槛必须先完成 lineup/deployment，并以 task 栈出现 `0x0808F957` 或 entry observer
fresh 命中 `0x0808F952 → 0x080732B4` 证明真实 controller entry。

### 0.4 玩家控制、移动事件与胜利链

只读静态分析给出后续最小探针链：

- 0x080732B4：战斗主控制器；
- 0x080738C0：判断玩家/AI 行动方；
- 0x08073940：玩家单位选择，命中即可证明玩家控制；
- 0x080739D0：当前单位确定；
- 0x08073A04：行动菜单；
- 0x080722A8：行动/MOVEDONE 事件队列；
- 0x0807444E：玩家行动结算后的胜负检查；
- 0x080777FC：实际胜负谓词；
- 0x08073068：结果写入 0x02026807；
- 0x08074FDA：战斗控制器终止；
- 0x08074EE6：postbattle state 0xF400。

2026-07-15 的五点 controller-path probe 观察了 `0x08073946` 和
`0x08073A16/2E/3E/4A` 四条 checked BL。`actionable-move-grid.ss9` 零输入 baseline 与显式
`B,Down,Down,A,A` final 的 192-byte observer dump 逐字节相同，baseline/final compare
没有 fresh record。由于正对照未证明，按停止条件没有运行 scenario 41 白框诊断；这不否定
其他教程控制路径，也不证明玩家控制。后续离线任务栈复核又确认白框 state 保存时的活动链
不在 `0x080732B4` 内。下一步先完成 pre-controller lineup/deployment，固化含 `0x0808F957`
的真实 controller checkpoint；在此之前禁止继续对白框盲试 action-dispatch 按键。

scenario 41 的胜负描述符位于 ROM file 0x596804。类型 1 条件会扫描 slot 1..12：
unit+0xC0 bit 0 是队伍，bit 0x80 表示不再作为有效存活单位。当前 Iruka
unit+0xC0=0x11，仍是有效队伍 1 单位，所以现有 checkpoint 尚未满足胜利条件。
教程已知自然路线仍是第一回合移动到 (4,7)，第二回合移动到宝箱 (4,11) 上方
(4,10) 并结束行动。应捕获：

MOVEDONE → 0x0807444E → 0x080777FC → 0x02026807 → 0x08074FDA

胜利后再观察 Naruto level 2、EXP、template +0xBA 和 A880==3，随后捕获
0x0808E16E → 0x08093698 → 0x08093070 → 0x080932CA，最后只对自然命中的
levels record +6 做受控 A/B。

### 0.5 机器资源事故与强制约束

2026-07-13 调查期间机器两次进入严重 swap thrashing。系统日志证据：

- 22:37:56：OOM kill python3，anon RSS 3,143,600 KiB；
- 23:19:52：OOM kill python3，anon RSS 3,496,848 KiB；
- 两次均为 4 GiB RAM 接近耗尽、2 GiB swap 完全耗尽；
- systemd-journald、SSH session 与 proxima watchdog 同时超时；
- 内核 I/O pressure 在事故后五分钟窗口仍显示 full avg300 约 25%。

直接原因是多个未受限的 tools/find_thumb_calls.py 全 ROM Capstone 线性反汇编扫描
长期驻留并并发；该工具对 6 MiB ROM 从 0x08000000 连续启用 detail/skipdata，
在当前 4 GiB 机器上单进程可膨胀到 3 GiB 以上。同期又并发启动四个
runtime-formation-probe/Chromium，进一步压缩可用内存，最终让 swap I/O 看起来像
“磁盘读写占满”。磁盘本身没有 I/O error，文件系统也不是写满；当前根分区约 95%
使用、仍有约 2.2 GiB 空间，但这会降低抖动余量。

截至 2026-07-14，以上约束已从文档约定升级为代码门禁：

1. `find_thumb_calls.py` 已改为逐 halfword 的恒定内存 ARMv4T Thumb 编码扫描，不再对
   整份 ROM 调用 `Capstone.disasm(..., count=0)`；候选仍须用 bounded disasm 复核；
2. `tools/run_guarded.py` 为静态重任务和 Chromium probe 共用同一个非阻塞 `heavy`
   锁，并在启动子进程前执行可用物理内存准入；
3. 默认门槛为：可用内存至少 1024 MiB、owned process tree RSS 最多 1536 MiB、
   wall timeout 600 秒、无完整输出行 idle timeout 60 秒、1 秒采样、5 秒终止宽限；
4. Windows 只终止本次 Job Object，POSIX 只终止本次新建 process group；禁止任何
   `pkill`、`killall`、`taskkill /IM` 或按进程名清理；
5. Chromium probe 必须从 `play/_scripts` 运行 `npm run probe:guarded`；它在六类真实
   生命周期边界输出可解析 `resource-progress` JSON 行，npm 脚本显式传入仓库根目录的
   `--lock-file ../../build/resource-guard/heavy.lock`，不能依赖子目录 cwd 的默认锁路径；
6. 退出码 75 表示锁忙/准入拒绝，124 表示 wall/idle timeout，125 表示内存、启动或
   保护失败；每次运行原子写入包含 PID、峰值 RSS、backend 与原因的 JSON 摘要；
7. 每批运行前后仍需检查系统内存，只能处理本项目守卫拥有的进程树，不能清理无关进程。

受守卫的实际入口：

```powershell
python tools/run_guarded.py --summary build/resource-guard/thumb-calls.json -- python tools/find_thumb_calls.py build/naruto-sequel-dev.gba 0x08066D14 --start 0x08060000 --end 0x08070000 --output notes/calls-08066D14.txt
Set-Location play/_scripts
npm run probe:guarded
```

2026-07-14 验证：资源守卫 35/35、聚焦 Python 59/59、Node probe 37/37 均通过；
干净 headless WSL 下，同一 393 项全量套件经 POSIX guard 返回 0，峰值 owned-tree RSS
379.5 MiB。完成度审计保持 32/32、13 runtime / 10 code / 9 disproved。Windows 原生全量
仍有 6 项既有路径/OCR/临时数据库环境差异，不属于本轮资源安全回归。

### 0.6 后续执行顺序

P0：

1. 完成 scenario 41 的 pre-controller lineup/deployment，以 task 栈 `0x0808F957`
   或 fresh entry observer 证明 `0x0808F952 → 0x080732B4`；
2. 从真实 controller checkpoint 证明 0x08073940 玩家控制边界；
3. 完成两回合教程自然输入并捕获 MOVEDONE/胜负链；
4. 固化真实 victory/postbattle checkpoint；
5. 捕获 Naruto level 2、训练点 +BA>0 与 A880==3；
6. 进入训练分配 UI，命中 levels consumer 并完成 record +6 的单因素 A/B；
7. levels 达到全部门槛后才更新 bank.json 和 roadmap 状态。

P1：

1. 使用同一次有效战斗事件复用 data-table-b、resource-pointers 与技能执行探针；
2. 再按 player-visible 价值处理 units 未命名字段和 skills +2/+3/+9；
3. 对其余 code_verified bank 逐项执行“自然 selector → ROM 目标一致 →
   可见/行为差异”的运行时升级。

P2：

1. 完成 72 个仍为 unknown 的 audio cue 语义；
2. 完成 legacy web CRUD 与真实 ROM mirror 的边界；
3. 最后进行逐要求 completion audit；在所有门槛闭合前 Draft PR 不转 Ready、不合并。

## 1. 交接结论

当前工程**尚未达到 100% 逆向完成**，但已经从“32 个目录和生成器数量齐全”推进到
可以审计的基线：

- 32/32 个 `bank.json` 通过元数据、地址、条目和基准 ROM 字节一致性检查；
- 当前严格证据分布为 **3 runtime / 4 code / 24 static / 1 none**；
- positions、maps、units 已取得可复查运行时证据；units 仍需逐字段语义证明和安全写回；
- 构建链已具备 immutable-base 前置校验、跨补丁冲突检测及 audit/game-effective
  区域隔离；
- 已停止 battle-config、units、chapters、skills、story beats、audio 等缺少 ROM
  记录身份的 legacy 危险写入；
- 旧“100% 完成”声明已经撤销，不能用构建成功或 32/32 bank 字节一致性代替运行时
  消费证明。

权威完成度入口：

- `notes/dynamic-verification-audit.md`：32 项逐项证据等级；
- `notes/re-completion-audit.md` / `.json`：可机器复核的静态与字节一致性审计；
- `docs/sequel-roadmap.md`：当前优先级与长期路线；
- 本文：接手顺序、运行命令和已知风险。

## 2. 当前可复现状态

### 2.1 审计与测试

最近一次完整验证：

```text
python unittest: 37/37
runtime probe node tests: 19/19
tools/automated_test.py: 22/22
web-editor backend pytest: 9/9
audit_re_completion.py: 32/32 banks
```

运行命令：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node play/_scripts/runtime-formation-probe.test.js
python3 tools/automated_test.py
pytest -q web-editor/backend/tests
python3 tools/audit_re_completion.py
python3 tools/build_mod.py
git diff --check
```

最近构建报告分类：

```text
game_effective: 2443
audit: 471
diagnostic: 169
```

`diagnostic` 是被安全拒绝的 legacy 行，不是 ROM 写入，也不能计入有效功能。

### 2.2 ROM 基线

- 基准 ROM SHA-1：`26f60795fa5e63b4f0264b84e453beffd56b9f7d`；
- 构建产物：`build/naruto-sequel-dev.gba`；
- 构建报告：`build/naruto-sequel-build-report.json`；
- 不要把 `.sav`、临时 screenshot 或 `/tmp/*.json` 当作持久证据；关键结果必须摘要到
  `notes/`。

## 3. 已确认的重要结论

### 3.1 positions：已完成 runtime 验证

- ROM 编成矩阵：file `0x5461C4`；
- 公式：`base + group*0x1AAC + variant*0x08E4 + 4 + record*0xB8`；
- 总量：48×3×12 = 1728 条；
- record `+2/+3` 是初始 x/y；
- 单位物理数组：WRAM `0x020240C0`，stride `0x1D4`；slot 1 为
  `0x02024294`；
- WASM 首战样本：slot 1 `(4,4)` 唯一匹配 group 40 / variant 0 / record 0，
  ROM `0x588CA8`；第二次成功样本还得到 `0x02026805=40`。

入口：`tools/extract_positions.py`、`tests/test_extract_positions.py`、
`notes/positions-rom-source-20260710.md`、
`notes/wasm-formation-probe-result-20260710.md`。

### 3.2 maps：width/height 已完成 runtime A/B

- header：file `0x53D910`，47×32；
- `0x08068FB4` 把选中行 width/height 写到 `0x0201BE28/29`，并把
  `width>>2` / `height>>1` 写到 `0x0201BE2A/2B`；
- `0x08068FF0` 消费同一行的资源指针；
- 首战 ID 40 对应 file `0x53DE10`，width/height 为 36×44；baseline 运行时为
  `[36,44,9,22]`；
- 安全 A/B 仅将 width 36→32，同路线运行时变为 `[32,44,8,22]`，证明
  width/height 运行时字段链；不要扩大尺寸或修改资源指针。

入口：`notes/maps-runtime-fields-20260711.md`、
`play/_scripts/runtime-formation-probe.js`。

### 3.3 units：旧 bank 身份错误，真实角色表已定位

旧 `0x53F298 = battle slot → character ID` 结论已撤销。唯一消费者把该表当作
u16 对象/渲染偏移查找，不能继续写 editor `char_id`。

真实角色定义：

- file `0x54241C`，63 条（ID 0..62），stride `0xB4`；
- 表结束 `0x545068`，并在同一地址直接接 63×`0x10` 成长表；旧“到
  `0x54507A` 有 18 字节 gap”结论是把成长表 record 0 和 record 1 前两字节
  误认成 gap，现已撤销；
- WRAM 模板池 `0x02022E34`，24×`0xBC`；
- formation record `+0` 与模板 `+0` 匹配；
- `0x0806AC70 → 0x0806AA64` 把模板前 `0xBC` 字节复制到
  `0x020240C0 + slot*0x1D4`，因此战斗槽 `+0` 是 character ID；
- 首战样本：formation `0x588CA8[0]=1`，slot 1 `0x02024294[0]=1`；
  template slot 1 `+0=1`，且 template 前 `0xBC` 字节完整复制到战斗 slot 1。
  `characterId=1` 对应 ROM record `0x5424D0`，但 template payload 与 ROM raw
  record 仅前 7 字节一致，说明 raw record 到 template 有运行时转换/重排；
- 单字节 A/B：只改 file `0x5424D1`（record byte `+1`）`0x0e→0x0f`，同路线
  template slot 1 first16 从 `01010e0d0803050505000f0050005000` 变为
  `01010f0d0803050505000f0050005000`，battle slot 1 同步变化。因此 units 结构身份
  和至少一个 raw 字段消费链已达到 runtime 证据级别。

入口：`notes/character-definition-source-20260711.md`、
`notes/units-unsafe-table-fix-20260711.md`。

`tools/extract_character_definitions.py` 和 `tests/test_extract_character_definitions.py`
已建立，`sequel/content/units/bank.json` 已从错误的 `0x53F298` 迁移到 63×`0xB4`
真表。当前已把 runtime character ID 闭合到具体 `0x54241C` 记录，并证明
template→unit 复制；`0x5424D1` 单字节 A/B 已证明 raw-record→template 的字段来源。
剩余工作是逐字段语义命名和安全语义写回。

### 3.4 构建安全边界

安全真实写回应具备：

1. 明确 `_idx`；
2. 明确 `_rom_offset`；
3. 完整 `raw_hex` 或已证明字段序列化；
4. immutable base-ROM `before_hex`；
5. 边界、长度、指针范围和跨生成器冲突检查。

以下 legacy 编辑目前只产生 `db_*_unmapped`：

- battle configs；
- units；
- chapters；
- skills；
- story beats；
- audio files；
- maps；
- levels；
- character_stats；
- battle_config_data；
- encounter_zones；
- items。

这些 legacy 入口后续只能在具备明确 ROM 身份、完整 raw/base 校验和字段级序列化证据
后逐项恢复真实写回；已有 `rom_*` lossless mirror 入口不受影响。

入口：`notes/legacy-generator-safety-20260711.md`、
`notes/battle-config-unsafe-template-fix-20260710.md`、
`tools/build_db_patches.py`、`tests/test_unsafe_legacy_patches.py`。

## 4. 当前运行时探针状态

部署地址：`https://sh.kibox.com.cn/gba-naruto/play/`。

WASM 暴露 GBA 内存读取和本地 ROM `uploadRom/loadGame`，但不暴露 PC、LR、寄存器或
断点。现有探针支持：

- START/A/B/方向键导航；
- 单位槽坐标、character ID；
- 角色模板池 `0x02022E34`、template→unit 复制匹配、template payload 与 units
  ROM raw record 的前缀/首个 mismatch 检查；
- battle-control `0x02026804..0B`；
- map runtime `0x0201BE28..2B`；
- 画面颜色比例分类；
- 人物页 B 重试、转场等待、显式焦点恢复；
- settle 轮询与可选恢复确认键；
- 唯一编成匹配，歧义时拒绝猜测。

最新成功样本保存在 `/tmp/units-template-result.json`，result SHA-256 为
`47eb0ce26fe1f0296b448ab931cbf4d9ddf91b00592397bcafc5770029b9819b`，最终截图
SHA-256 为 `a5fb3caaad684fb83a19e83ddfcc258ef0cfd2b6c5c2504532865d5b0d16fb24`。
`0x5424D1` A/B 样本保存在 `/tmp/units-char1-byte01-0f-result.json`，result
SHA-256 为 `ae30e8a149106e4ea4df5dcd67d4e46e29af106efc48023693180ed6c91e0495`，
最终截图 SHA-256 为 `9154ccd58af26ca9f2181ceb0c1271e7aa7ad0006451479b53a30fe5876cca97`。
固定 250 次 A 可到人物页，但人物页→战前菜单转场仍可能受输入/时序漂移影响；失败时
优先检查 `screenState`、`adaptiveRetries` 和 phase screenshots。

建议下一次命令：

```bash
env \
  PROBE_START_COUNT=30 \
  PROBE_ADVANCE_COUNT=250 \
  PROBE_START_DELAY_MS=500 \
  PROBE_CONFIRM_DELAY_MS=750 \
  PROBE_ADVANCE_DELAY_MS=300 \
  PROBE_KEY_HOLD_MS=150 \
  PROBE_TAIL_DELAY_MS=600 \
  PROBE_TAIL_KEYS=KeyX,ArrowDown,ArrowDown,KeyZ,KeyZ \
  PROBE_SETTLE_COUNT=40 \
  PROBE_SETTLE_DELAY=500 \
  PROBE_SETTLE_CONFIRM_EVERY=2 \
  PROBE_RESULT=/tmp/units-template-result.json \
  PROBE_SCREENSHOT=/tmp/units-template-final.png \
  node play/_scripts/runtime-formation-probe.js
```

通过条件：

- `outcome=matched`；
- battle ID 40；
- slot 1 `characterId=1, x=4, y=4`；
- map runtime `[36,44,9,22]`；
- template slot 1 与 battle slot 1 前 `0xBC` 字节匹配；
- character definition match 指向 `0x5424D0`，并记录
  `matchingPrefixBytes=7, rawRecordMatchesRom=false`；
- 若使用 patched ROM `/tmp/units-char1-byte01-0f.gba`，template/battle slot first16
  应从 `01010e0d...` 变为 `01010f0d...`；
- 截图为首战地图；
- 结果摘要和 SHA-256 写入仓库 note。

## 5. 后续执行顺序

### P0-1：修正 units bank

1. ✅ 红测/回归测试：63 条、stride `0xB4`、首末地址、完整 raw bytes、ROM fidelity；
2. ✅ 编写可重复提取器：`tools/extract_character_definitions.py`；
3. ✅ 迁移 units bank 到 `0x54241C` 真表；
4. ⚠️ 回写生成器仍保持 diagnostic-only，待字段级 ROM 身份证明后恢复；
5. ⚠️ audit、文档和测试需随后续 runtime 闭环继续更新。

### P0-2：闭合 maps 与 units 动态证据

1. ✅ 用最新状态机重放 baseline，并固化 `[36,44,9,22]` 和 character ID 1；
2. ✅ 通过 `PROBE_ROM` request-interception 自动加载 width 36→32 的本地 ROM B；
3. ✅ 同路线验证 `[32,44,8,22]`，maps width/height 升级 runtime；
4. ✅ units 已取得 character ID 选择与 template→unit 复制样本；
5. ✅ units 已通过 `0x5424D1` 单字节 A/B 证明 raw record 字段进入 template；
6. ⚠️ units 后续仍需逐字段语义命名和安全语义写回。

### P0-3：清除剩余危险 legacy 写入

参数化测试 maps、levels、character_stats、battle_config_data、encounter_zones、items，
要求没有显式 ROM 身份时零 `bytes` patch，只返回 diagnostic，已完成。随后再逐项从 `rom_*`
mirror 恢复安全字段编辑。

### P1：逐项提升 32 结构证据

严格按 `notes/runtime-verification-gates-20260710.md` 执行。优先顺序：

1. save-state；
2. battle-config；
3. ✅ character growth：真实表 `0x545068`、63×`0x10` 已由
   `0x0806D964` 和两因素首战 A/B 升级 runtime；`0x545200` B 表已否定并禁写；
4. character growth 字段 UI 命名与 63 行 editor schema 安全迁移；
5. story / cutscene-scripts / map-events；
6. skills/items 身份拆分；
7. audio/palettes 身份拆分；
8. units 字段语义和安全语义写回；
9. 资源、动画、后续章节和未知表。

## 6. 100% 完成门槛

只有同时满足以下条件才可恢复“100% 完成”声明：

- 32 个结构身份和边界无别名冲突；
- 每个结构有可复现提取器或等价机器验证；
- 字段语义由代码流、运行时观察或安全 A/B 支持；
- 所有用户可编辑字段都有明确 ROM 记录身份和安全回写；
- 集成点具失败时能报警的测试；
- 32 项逐项 runtime/code/static 证据符合项目最终约定；若目标要求全动态，则必须
  32/32 runtime，不得用静态字节一致性替代；
- 完整构建、单元、集成、模拟器验收全部通过；
- `docs/final-completion-report.md` 与真实证据一致。

当前不满足这些条件，禁止调用完成标记。

## 7. Git 与工作树说明

- 本轮由用户明确要求提交并推送；
- 不应提交本地 `.sav`、临时运行截图或与逆向无关的编辑器 polish goal；
- `build/naruto-sequel-dev.gba` 和 build report 是项目既有跟踪产物，本次随安全构建结果
  更新；
- 推送前必须再次运行验证、`git diff --check`、`git status`，并确认没有把凭据或本地
  运行状态写入仓库。
