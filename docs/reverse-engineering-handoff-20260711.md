# GBA 木叶战记逆向工程交接（2026-07-11）

## 1. 交接结论

当前工程**尚未达到 100% 逆向完成**，但已经从“32 个目录和生成器数量齐全”推进到
可以审计的基线：

- 32/32 个 `bank.json` 通过元数据、地址、条目和基准 ROM 字节一致性检查；
- 当前严格证据分布为 **1 runtime / 6 code / 24 static / 1 none**；
- positions 已取得可复查运行时证据；maps 是下一项最接近 runtime 的结构；
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
python unittest: 31/31
runtime probe node tests: 16/16
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

### 3.2 maps：字段链已确认，动态样本未闭合

- header：file `0x53D910`，47×32；
- `0x08068FB4` 把选中行 width/height 写到 `0x0201BE28/29`，并把
  `width>>2` / `height>>1` 写到 `0x0201BE2A/2B`；
- `0x08068FF0` 消费同一行的资源指针；
- 首战 ID 40 对应 file `0x53DE10`，width/height 为 36×44；运行时预期
  `[36,44,9,22]`；
- 安全 A/B：仅将 width 36→32，预期运行时变为 `[32,44,8,22]`。不要扩大尺寸或
  修改资源指针。

入口：`notes/maps-runtime-fields-20260711.md`、
`play/_scripts/runtime-formation-probe.js`。

### 3.3 units：旧 bank 身份错误，真实角色表已定位

旧 `0x53F298 = battle slot → character ID` 结论已撤销。唯一消费者把该表当作
u16 对象/渲染偏移查找，不能继续写 editor `char_id`。

真实角色定义：

- file `0x54241C`，63 条（ID 0..62），stride `0xB4`；
- 表结束 `0x545068`；到现有成长表 bank `0x54507A` 前有 18 字节 gap，
  实际为 16 字节零后接 `aa05`，不能再称为全零填充；
- WRAM 模板池 `0x02022E34`，24×`0xBC`；
- formation record `+0` 与模板 `+0` 匹配；
- `0x0806AC70 → 0x0806AA64` 把模板前 `0xBC` 字节复制到
  `0x020240C0 + slot*0x1D4`，因此战斗槽 `+0` 是 character ID；
- 首战预测：formation `0x588CA8[0]=1`，slot 1 `0x02024294[0]` 应为 1。

入口：`notes/character-definition-source-20260711.md`、
`notes/units-unsafe-table-fix-20260711.md`。

`tools/extract_character_definitions.py` 和 `tests/test_extract_character_definitions.py`
已建立，`sequel/content/units/bank.json` 已从错误的 `0x53F298` 迁移到 63×`0xB4`
真表。剩余工作是把 runtime 探针样本闭合到具体 `0x54241C` 记录，并在字段语义逐项
证明后恢复安全回写。

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
- audio files。

仍需按同一模式封堵的潜在危险入口：maps、levels、character_stats、
battle_config_data、encounter_zones、items。它们在当前数据库中可能尚无表，但一旦创建
就会按 DB 主键、默认指针或补零模板写真实 ROM。

入口：`notes/legacy-generator-safety-20260711.md`、
`notes/battle-config-unsafe-template-fix-20260710.md`、
`tools/build_db_patches.py`、`tests/test_unsafe_legacy_patches.py`。

## 4. 当前运行时探针状态

部署地址：`https://sh.kibox.com.cn/gba-naruto/play/`。

WASM 暴露 GBA 内存读取和本地 ROM `uploadRom/loadGame`，但不暴露 PC、LR、寄存器或
断点。现有探针支持：

- START/A/B/方向键导航；
- 单位槽坐标、character ID；
- battle-control `0x02026804..0B`；
- map runtime `0x0201BE28..2B`；
- 画面颜色比例分类；
- 人物页 B 重试、转场等待、显式焦点恢复；
- settle 轮询与可选恢复确认键；
- 唯一编成匹配，歧义时拒绝猜测。

已知问题：固定 250 次 A 可到人物页，但人物页→战前菜单转场仍存在输入/时序漂移。
最近失败样本停在人物页解体的转场帧，目标 WRAM 全零，探针正确返回 `not-found`。
最新代码增加了每次 B 后四轮（约 2.4 秒）宽限期，但尚未完成下一次真实重放。

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
  PROBE_RESULT=/tmp/maps-units-result.json \
  PROBE_SCREENSHOT=/tmp/maps-units-final.png \
  node play/_scripts/runtime-formation-probe.js
```

通过条件：

- `outcome=matched`；
- battle ID 40；
- slot 1 `characterId=1, x=4, y=4`；
- map runtime `[36,44,9,22]`；
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

1. 用最新宽限状态机重放 baseline；
2. 若成功，固化 `[36,44,9,22]` 和 character ID 1；
3. 自动上传 width 36→32 的本地 ROM B；
4. 同路线验证 `[32,44,8,22]`；
5. maps 升级 runtime，units 只有在真实 `0x54241C` 记录也被关联后才升级。

### P0-3：清除剩余危险 legacy 写入

参数化测试 maps、levels、character_stats、battle_config_data、encounter_zones、items，
要求没有显式 ROM 身份时零 `bytes` patch，只返回 diagnostic。随后再逐项从 `rom_*`
mirror 恢复安全字段编辑。

### P1：逐项提升 32 结构证据

严格按 `notes/runtime-verification-gates-20260710.md` 执行。优先顺序：

1. maps / units；
2. battle-config / character-stats / character-stats-b；
3. story / cutscene-scripts / map-events；
4. save-state；
5. skills/items 身份拆分；
6. audio/palettes 身份拆分；
7. 资源、动画、后续章节和未知表。

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
