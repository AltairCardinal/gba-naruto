# S49 / battle 14：Butano 单关复刻验证

> 后续纠正：[地图交互修复记录](butano-s49-interaction-fixes-20261011.md)。本版宝箱只是
> 静态摆设，移动缺少转向和动画；静态截图及通关路线没有覆盖这些问题。新版已修复并
> 增加交互验收。下文保留本版当时的证据，不作为交互完整或 100% 还原的结论。

## 结论与交付

本轮复用工作区已有的 S49 通用战斗链，将逆向资源的导入、独立构建、实际整关运行和
原作画面对照串成一次新的验收。已得到可以试玩的 GBA ROM，但 **尚未证明 100% 原作还原**。
短音效恢复实验在第二回合超时，交付版保持原有的仅 BGM 配置。不能把局部画面零差异
解释为音频、操作时序、AI 和所有新关卡均完全一致。

- 试玩：`artifacts/butano-s49-reproduction-20261011-v1/Konoha-S49-Demo.gba`
- 符号：同目录 `Konoha-S49-Demo.elf`
- 机读验收：同目录 `manifest.json`
- ROM SHA-256：`3998fb1ab64b556f3514ca39730c9ad79fb51d73633204425ffc1dfe6e00c424`
- 原有 `butano-sequel/butano-sequel.gba` 未被覆盖；没有提交或推送。

这是当前含用户未提交工作的源码重建，不是从 Git HEAD 干净检出的重建。独立构建目录
从空目录开始；2,088 个当前源码和资源文件的哈希保存在 `build-inputs.json`。最终 ROM
与本轮完整运行的 `baseline-runtime/runtime.gba` 逐字相同。

## 复用判断与执行模式

任务模式为“固定单关的资源引入、Butano 构建及原作差分验收”：输入固定 ROM、原作
快照、现有生成器和关卡路线；操作为资源验真、导入、构建、自动操作和截图比较；产出
为可玩 ROM、来源清单、运行收据、差分结果以及明确的未通过项。

1. 直接复用现有地图、角色、UI 生成器及 `battle_campaign`、controller、renderer、
   SRAM 和 mGBA 路线；没有新建另一套游戏引擎或关卡状态机。
2. 宝箱只需接入已有 `load_gba_state` 和 indexed BMP writer，无需另写解压器。
3. 修改追加到已有 S49 scenery 生成链；固定 OAM 12 的合同不提升为通用资源发现能力。
4. 独立的是构建及证据输出目录，用于保护旧 ROM 和历史实验，不是平行维护的功能实现。

优先使用已有脚本完成确定性工作。当前原生协作工具的模型 schema 未提供 GPT-5.6
Luna max / Terra，记为“当前环境不可用”；主代理承担跨链路判断和唯一写入，已有
只读代理复核音效失败边界及宝箱来源。未启动外部模型、Comet 或新 Goal。

## 已提交资源来源与本次修复

固定基准 ROM：`rom/base.gba`，SHA-256
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。

下列输入通过 `git show <commit>:<path>` 与本地文件逐字比较；完整记录在
`committed-source-checks.json`，未从逆向工作树的未提交文件导入新资源。

| 输入 | 已提交来源 | 本轮验证 |
| --- | --- | --- |
| `map-canvases-v1/manifest.json` | `fc6253f6ab747ddc2c024557c211997cb0f302dd` | verifier：47 地图、61 canvas，errors=[] |
| `character-battle-visuals-v1/manifest.json` | `b04e0b00702ce612cc50ca551ff77ed24c657e22` | verifier：250 资源、558 槽、2,004 源空间帧，errors=[] |
| S49 entry ss9 | `c16018a282d00f32ec8323877df68918cc478d8d` | 哈希固定；直接解析 OAM、VRAM、PRAM |
| `tools/inspect_mgba_savestate.py` | 逆向 HEAD `0302f4685946d9fa97747cb9814ea9c83fd02df4` | 与已提交 parser 逐字相同 |

宝箱生成器原先依赖本地 `references/battle-scenario-49-scenery/` GPU 切片。现在
直接从已提交快照读取，导入前拒绝 ROM 或快照哈希不符；因此缺少旧切片目录也能
生成相同 BMP。生成元数据保留 commit 和快照哈希。

- 快照：`artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9`
- 快照 SHA-256：`a3628723ac595f41b87d329f49d5422a7b9b397a8491379abb8c9620568a0aa1`
- OAM 12：`0x07000060`；32×32、4bpp、1D tile mapping。
- tile 944：VRAM `0x06017600` 起 512 字节；palette 14：PRAM `0x050003C0` 起 32 字节。
- BMP 与原输出逐字相同；582 个非透明像素与快照中的宝箱逐像素相同。

TDD：`scenery-red-corrected.log` 记录旧实现缺少已提交输入独立运行能力，以及未拒绝
损坏 ROM/快照；最小实现后的 `scenery-green.log` 为 5/5。重构时移除了两个负例测试
残留的本地切片复制依赖，最终相关测试再次通过。导入器仍限定 S49 的固定快照和
world center，不承诺自动识别其他关卡的宝箱。

**来源闭包仍有边界：**本轮沿用工作区已有的原作 UI 捕获和剧情候选输入，不能把它们
全部称为已提交逆向成果。整关可玩证明与“全部资源已完成已提交来源闭包”是两项验收。

## 新构建与整关结果

固定 Butano：`112a1827c9c6d9e6041a7e93e66f04c4561a6415`；Docker 工具链：
`devkitpro/devkitarm@sha256:116afba8df8453961de2936ffab20dd441edf4d682856c1ec8b0e53d7ed0bbf5`。
构建使用 `BUILD=build-s49-reproduction-20261011-v1` 和
`TARGET=butano-s49-reproduction-20261011-v1`，Docker 限制 1,536 MiB / 2 CPU。
构建和 mGBA 均通过主工作树的 `tools/run_guarded.py` / `heavy.lock`。
完整命令、时间、退出码在各 `*-guard.json`，编译输出另存 `*.stdout` / `*.stderr`。

`baseline-runtime/` 从无 SAV 冷启动，使用现有真实按键路线，`mute=0`，自动运行：

- 10,851 帧、368 次领域转换，在第 9 回合击败五只野蜂、保住木叶丸。
- 任务经验 125、战斗经验 100、合计 225；鸣人等级 6、经验 0、修行点 5。
- 完成结果、升级和六页修行流程，保存 generation 1 / verified 1，推进 S49→S50。
- 最终 controller/player error 均为 0；guard 以 success marker / exit 0 收束。

`save_verified` 表示本次运行中写后验证成功；本轮未另做断电冷启动读档测试。
`objective_verified=0` 等其他通用路线字段不能当作额外能力通过，结论限于 S49
专用路线实际断言及五条击败记录。

## 与原作的画面对照

执行 `verify_visuals.py` 会调用已有比较器，重新生成 `visual-comparisons.json`。
运行捕获均为新 ROM，原作输入与当前截图哈希均记入报告。

| 比较项 | 分母与范围 | 本轮差异 |
| --- | --- | --- |
| 战前根菜单、出击确认 | 各 240×160 整屏 | 各 0 / 38,400 |
| 升级第一页 | 240×160 整屏 | 0 / 38,400 |
| 修行 / 新术提示六页 | 各 240×160 整屏 | 每页 0 / 38,400 |
| 动作菜单 | 排除 192 像素动态 HP 的 38,208 像素，以及既有子区域检查 | 0 |
| 移动后命令菜单 | 固定面板、文字、箭头区域 | 0 |
| 目标状态栏 | 240×48，11,520 像素 | 0 |
| 目标确认框 | 80×64，5,120 像素 | 0 |

共 9 个整屏加 4 组局部比较。子区域有重叠，不累加为总体还原率。三名角色各两页
升级的离线分层重组测试也通过，但运行路线只捕获了升级首屏，不能混称六页运行捕获。
父代理另查看了战场、动作菜单和升级截图。

## 未通过：短音效恢复实验

在成功基线上，试验性把 12 种短 cue 接到 `bn::sound_items`。宿主替身验证能收到
正确 cue，说明接线成立，但不能证明真实 Maxmod 播放稳定。实际 SFX ROM 在
`sfx-runtime/` 最后报告 frame 1508、round 2、phase 12（enemy_turn），之后未继续
产生进度，60 秒 idle timeout / exit 124；没有完成标记。

父代理重算两组转换：前 82 次转换排除 frame 后完全相同；成功基线共有 368 次。
结果保存在 `audio-regression-comparison.json`。这证明本次启用短音效的整关路线
未通过；没有停点 PC、平台断言或首次坏写证据，不能确定具体 Maxmod 故障机制。

失败后停止扩张音效实验，保留失败 ROM、ELF、实验 header 和测试文本。交付源码
恢复为试验前 header，重建后 ROM 与成功基线逐字相同。最终接线集成测试明确约束
当前仅 BGM 的配置；早期 `audio-scenery-green.log` 不代表 SFX 验收通过。
长结算曲 51/52 也仍未接通。`mute=0` 只说明没有设置模拟器静音，并非原作音质证明。

## 验证清单与复验

- 56 项 Python / Lua / 资源 / 宿主音频接线测试通过：`final-tests.stderr`。
- 3 个 C++ 宿主程序通过：audio director、S49 campaign、scene controller。
  runner 的命令还带了不存在的 SRAM 测试名，但没有执行它，因此不计为第四项。
- 地图和角色独立 verifier 通过；新目录完整 ARM 构建通过；mGBA 全路线通过。
- 本次 Python 改动通过 AST 语法和尾部空白检查；仓库无 Python formatter 配置，环境
  无 Ruff/Black，未声称运行这些 formatter。已有 UI 生成器仍有 Pillow 弃用警告。
- 未做物理 GBA 验证、全库回归、音频波形一致性或全部动画逐帧差分。

在仓库根目录复查图像：

```sh
recheck_dir=$(mktemp -d /tmp/konoha-s49-recheck.XXXXXX)
python3 tools/run_guarded.py \
  --summary "$recheck_dir/guard.json" \
  --lock-file build/resource-guard/heavy.lock \
  --max-tree-rss-mib 512 --wall-timeout-s 60 --idle-timeout-s 60 \
  -- python3 -B artifacts/butano-s49-reproduction-20261011-v1/verify_visuals.py \
  --output-dir "$recheck_dir/comparisons"
```

这个脚本在新目录生成派生比较结果，拒绝覆盖已有输出目录，不修改原始截图。重新做运行实验时必须改用新 run ID，
复制交付 ROM 到新目录且不带 SAV；不得覆盖本轮 `baseline-runtime` 或失败证据。

人工试玩：在 mGBA 打开交付 ROM；同名 SAV 不存在时从 S49 进入。使用 GBA 方向键选
人物和移动格，A 确认，B 返回；行动菜单选术后选目标，再确认面向及防御。模拟器键盘
映射以本机设置为准。可以几分钟内核对战前菜单、移动范围、动作菜单和一次战斗演出。
完整通关由自动路线验证。已有 SAV 会续接保存进度；需要重测时复制 ROM 至新目录。

## 下一道验收门槛

1. 音效：在当前冻结失败路线补齐播放事件、停点 PC / 断言及声道状态，先定位阻塞，
   再跑短 cue、BGM 混音、完整关卡；不能通过静音或只有宿主替身来签发。
2. 动态还原：同初始状态与输入下，比对地图移动、决斗动画逐帧时长、相机、调色和
   命中帧；补足敌方及木叶丸决策分支，不能只依据九回合通关结果。
3. 可生产性：将现存 UI / 剧情候选输入补齐来源准入后，在同一生成链中只修改地图、
   部署、事件和胜利条件制作第二个小关卡，再重复构建、像素、时序、音频和存档验收。

第 3 步通过，才能开始证明“新增关卡仍保留原作表现”；复刻一条原关路线本身不覆盖
所有新关卡组合，也不能直接得出 100% 的总体保证。
