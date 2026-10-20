# 木叶战记续作 Roadmap

## 目标

把当前仓库从"已建立续作工作区和逆向基础"推进到"可以持续生产续作内容并稳定回写 ROM"的状态。

**执行策略：~~先完成逆向工程，再建网页编辑器。~~**

> **2026-10-20 — 该执行策略已被证伪并推翻。**
> 与第三方剧情编辑器包的对比复盘（`notes/why-external-editor-shipped-20261020.md`）显示：
> 对方在**未完成全量逆向**的前提下，用"复制原生条目 + 只改已知字段 + hook 原生函数"
> 的写回模型，产出了可用的编辑器与 26 场可玩 DEMO；而本项目走了 3.5 个月、
> 105 次提交、32 个结构全量静态入库，最终**可玩新内容为 0**。
>
> 改用：
> 1. **写回模型**：复制原生条目 + 覆盖式改写，未知字段 raw 兜底、不再要求命名
> 2. **验收标准**：按需动态证据（仅对本次改动涉及的结构），不再全量门禁
> 3. **工程形态**：单文件夹离线 ROM 编辑器，暂停 Web 服务/认证/多用户方向
> 4. **逆向定位**：作为功能产出的副产品，按需推进，不作为开工前置条件

> **2026-10-20 — 平台约束（macOS → Windows 迁移后）**
> 新机接入与验真记录见 `notes/windows-migration-20261020.md`。要点：
> - 两条工作线（`codex/reverse-engineering` / `codex/butano-foundation-research`）
>   已落地为独立工作树，工作区字节与 git blob 逐字节一致，交接文档钉死的
>   账本/审计器/spec 三个 SHA-256 本机复算吻合。
> - **本机 `core.autocrlf` 必须保持 `false`**：仓库用文件 SHA-256 当证据身份，
>   换行符一改全部钉死失效，且 `git status` 不会报脏。
> - **重活仍需 POSIX 宿主或等价改造**：账本重建 / formal / D0 采集链上的工具
>   用了 `os.O_DIRECTORY` / `dir_fd` 等 POSIX 原语（`tools/` 下 47 个文件），
>   其中 D0 契约钉死的两个模块不能直接改。mGBA 运行时链在本机需按 Qt +
>   `d8bad14b` 重建才能做 D0 采集。
> - 结论：**续作编辑器的开发不受此阻塞；逆向重活需要单独决策。**

---

## 2026-10-21（上午）｜**木叶战记 ROM 编辑器落地**：六域可编辑，初始数据可重建原版 ROM

> 把 2026-10-20 策略反转定的工程形态（单文件夹离线 ROM 编辑器）落地。
> 详细方法与结果见 `notes/rom-editor-20261021.md`，面向使用者的说明见 `docs/rom-editor.md`。

- **交付物**：`rom-editor/` —— 纯 HTML + 原生 ES Module，**无构建步骤、无后端、无账号**。
  六个域全部可编辑：**剧情与对白 / 道具 / 角色属性与技能 / 忍术 / 战斗 / 剧情路线**，
  外加两个把「其余已证实内容」也摆出来的域（**音频** / **素材与资源**），
  以及一个覆盖整张卡带的**原始字节编辑器**（结构化编辑器覆盖不到的字节都能改）。
- **初始数据即可构建完整原版 ROM**：内容包 `rom-editor/content/pack.json` 含有
  原版 ROM 中**所有可证实结构的全量内容**（**39 张结构表 / 6,666 条记录** /
  10 张文本表 / 2,199 条文本 / 4,261 个字形码），
  另有一份 **16,008 条**的全 ROM 文本索引。
  `node rom-editor/tools/verify_pack.mjs` 现场证明「用未改动的内容包重建的 ROM
  与 `rom/base.gba` **逐字节相同**」（sha256 `1198ece7…`）。
- **写回模型与仓库既有路径一致**：复制原生条目 + 只改已知字段 + 未知字节原样保留；
  逐域落点已验（改一个字段只动那 1–2 个字节）。
- **文本两类长度策略**：指针表驱动的（人物名表、忍术名表、任务表、对白槽位表…）
  可变长——构建时重定位到空闲区 `0x5DFBEC` 并改写指针；被代码用绝对地址引用的
  只能等长改写，超长**报错而不是截断**。
- **本轮查出的结构判定更正**（都已写回内容包与笔记）：
  编成矩阵是 **47** 组不是 48（第 47 组正好落在 `battle_rules` 表基址上）；
  对白指针表是 **1524** 槽不是 50；任务文本表 **112** 条、任务索引表 **48** 字节；
  `story_logic_root`/`story_events_root` **47** 槽不是 56；
  忍术记录 `+0x0E` 是**单字节**（`+0x0F` 在 87 条里恒为 0）。
- **剧情路线落在脚本里，也被编辑到了**：`0x16`（48 处）与 `0x1A`（15 处）两条
  「下一场景」指令抽成**路线边表**（202 个剧本 / 63 条边），它们的操作数做成可改输入框；
  战斗侧的 `0x1E`（地图）、`0x1F`（子配置）、`0x23`（队员）、`0x22`（加入战斗配置）
  同样列出。这些操作数都是**定宽**的，改它们是原地写，不会移动任何字节，
  因此脚本里的分支目标依然有效——与仓库既有写回路径
  （`tools/import_story_script.py`）成立的是同一个前提。
- **自检两条**：
  - 命令行 `node rom-editor/tools/verify_pack.mjs` → **18/18 PASS**
    （含「未改动的内容包重建 ROM 与原版逐字节相同」、逐域落点、文本重定位、
    原始字节补丁落点、剧情 VM 操作数落点）；
  - 浏览器内 `rom-editor/tools/selftest.html` → **31/31 PASS**
    （九个模块视图与八个关键面板全部渲染成功、逐域落点全部正确、文本改动经指针可回读、
    原始字节补丁与「下一场景」改写真的进 ROM）。
- **一处环境限制（如实记录）**：本机内置浏览器对**单页下载量**有上限（实测约 6.3 MB），
  而原版 ROM 本身就是 6,291,456 字节。因此 ROM 由作者用顶栏「载入 ROM」选文件提供
  （0 字节下载，永远可靠），「载入内置 ROM」作为便捷路径。详见
  `notes/rom-editor-20261021.md` §5。

---

## 2026-10-21（凌晨）｜**L2 运行时证据 + 能力项收口**：L2 1→5，写回路径 18/18

> 这一轮把「只有静态推导」的结构补上**原生定点证据**，并把三项能力缺口（m4a→PCM、
> CGB PSG、头像写回）真正做出来。记录见 `notes/evidence/l2-runtime-evidence-20261021.md`、
> `audio-song-export-20261021.md`、`portrait-writeback-20261021.md`、
> `content-pack-export-20261021.md`。

- **L2 运行时证据（5 个结构）**：`tools/l2_runtime_capture.py` 是**可执行**的闸门
  —— 断点命中原生消费者、寄存器↔字段一一对应、再与静态表交叉核对，
  并且带**反向对照**（故意改坏寄存器，断言检查必须失败）。
  证据：字形段表（`0x08065EE6`）、sound-ID 表（`0x0809AAC6` / `0x0809AB92` / `0x08061E9E`）、
  角色定义表（`0x0806D984` / `0x0806D4D2`）、地图描述符表（`0x0808F4F6`）、
  头像表（`0x08096158`）。L2 从 **1** 提到 **5**。
- **m4a → PCM 端到端合成已实现**：`tools/audio_song_export.py` 可渲染五个已知 SongHeader
  （978 个音符）。**修正了 4 个真 bug**：PSG 频率表其实是 **12 项有符号 16 位**
  （`ldrsh` @ `0x0809B4FE`），旧工具读 16 项无符号、**读进了噪声表**；
  另有 `+0x800` 偏置、算术右移、噪声 key 重映射、`key-36` 先减后夹的顺序错误。
  修完后 PSG 事件数（616/534/746/612/498）已与 ROM 原始字节**逐条对上**。
- **头像写回已实现并可执行**：素材 = BIOS LZ77（`svc 0x11`）解压的 6400 字节 8bpp 图形
  + 128 字节原始 BGR555 调色板；每条表情的压缩预算 2320–4008 字节，
  **310 条表情全部能用回引用 LZ77 压得更小**（余量 11–51 字节）⇒ 写回可行。
  已登记为 `tools/writeback_paths.py` 的 `portrait-table` case：**18/18 全 PASS**。
- **内容包导出已验证**：`tools/export_content_pack.py --check` 通过，
  **5740/5740** 条记录仅凭字段值即可逐字节重建 ROM；
  并修掉 6 个「字段描述的是整张表、却按记录存储」的结构（编辑器会静默丢弃这些编辑）。
- **顺带修掉的工具 bug**：`tools/find_thumb_calls.py` 与 `tools/disasm_thumb.py`
  直接 `import capstone`，在本机必然 `ImportError` —— 已改为共用 `tools/capstone_loader.py`
  （会去找 `build/python-deps` 里那份能用的 DLL）；
  `tools/decode_story_script.py --stats` 不带 `--scene` 会 `TypeError`；
  `tools/extract_all_structures.py` 用系统默认编码（GBK）读自己写的 UTF-8 JSON。
- **审计变化**：等级分布 **L4=0 / L3=4 / L2=5 / L1=35 / 已裁决=3**；
  格式已证明 **44/47**、写回可用 **24/47**（其中 **19** 条是可执行往返自检）、
  失败探针 **0**、阻塞缺口 **0**、加固缺口 **122**。
- **回归**：unittest **84 OK**、automated_test **28/28**、写回自检 **18/18**、
  alias_audit **OK**、审计 `--check` 退出 **0**。

---

## 2026-10-21（凌晨）｜**最后 9 个 legacy 基址全部裁决**：格式已证明 35/47 → **44/47**

> 这一轮把 2026-10-20 审计里「基址无效、需重新定位」的 12 个结构压到 3 个已退役 bank。
> 详细记录见 `notes/evidence/legacy-rebase-final-20261021.md`。

- **裁决方法**（不再靠"看起来像"）：① 真基址必须被**原生读者加载**
  （全 ROM 字面量索引，18051 个常量 / 29920 条引用指令）；
  ② 真基址 + 条数 × 步长必须**正好落在下一个已知结构**上；
  ③ 旧 bank 记录的条目必须**逐字节等于** ROM 在真基址处的字节。
  三条同时成立才认。
- **9 个裁决**：

  | bank | 旧基址 | 真基址 | 结构 |
  |---|---|---|---|
  | `battle-handlers` | `0x53E6D8` | `0x53E698` | 8 字节/条 × 256（2 个 u32 代码指针） |
  | `map-events` | `0x53EB08` | `0x53E698` | 与上**同一张表** |
  | `fonts` | `0x53E5B4` | `0x53E596` | 字宽表 256 字节（按字符码索引） |
  | `data-table-a` | `0x5A14A4` | `0x5A143C` | u32 ROM 指针 × 46 |
  | `data-table-b` | `0x5A2120` | `0x5A2034` | u32 × 90 |
  | `menu-ui` | `0x5A5774` | `0x5A4DEC` | 头像表 40 字节/条 × 63（`id*40+expr*8`） |
  | `function-pointers` | `0x53D5F4` | `0x53D5F0` | 13 槽 u32（槽 0/12 为哨兵） |
  | `tile-assets` | `0x5A3218` | `0x5A320C` | 68 字节/条 × **79** |
  | `sappy-engine` | `0x079668` | —— **退役** | `0x08079668` 是文本分派函数 |

- **推翻两条旧结论**：① 「`menu-ui` 的 `0x5A57C4` 不可复现」——**错**，它确实有 12 个读者，
  是一张 12 字节/条的表，且与 menu-ui 无关；② 「`map-events` 是独立表、`0x53EBC4` 处以 0 结尾」
  ——**错**，`0x0853EB08` 在整个 ROM 里零引用，旧记录是 8 字节记录按 4 字节步长读出来的窗口。
- **`tile-assets` 条数定案 = 79**（曾三选一）：288 被 8 位索引判死；
  142 会与头像表 `0x5A4DEC..0x5A57C4` 重叠被证伪；
  79 由「读者真正解引用的指针块结构在 `0x5A4708` 处干净断裂」确定。
- **顺带修掉两个真 bug**：`tools/extract_all_structures.py` 用系统默认编码（GBK）读自己写的
  UTF-8 JSON（`UnicodeDecodeError`）；`import tools.lib.io` 缺仓库根 `sys.path`
  （`ModuleNotFoundError`）；并让它**跳过** `positions` 这类非扁平记录表而不是崩掉整轮抽取。
- **审计变化**：等级分布 **L4=0 / L3=4 / L2=1 / L1=39 / 已裁决=3**；
  格式已证明 **44/47**、写回可用 **24/47**、失败探针 **0**、阻塞缺口 **0**、加固缺口 **121**。
- **回归**：unittest **84 OK**、automated_test **28/28**、写回自检 **17/17**、
  alias_audit **OK**、审计 `--check` 退出 **0**、746 文本文件 **0 CRLF / 0 BOM**。

---

## 2026-10-21（凌晨）｜**完成度判据固化为可执行文档** `docs/re-completion-criteria.md`

> 本轮不推进逆向内容，只把「**怎么判断逆向已经全部完成**」写成一份稳定文档，
> 供后续每一轮收尾自查。详细记录见 `docs/re-completion-criteria.md`。

- **文档**：`docs/re-completion-criteria.md` —— 五种「假完成」（元数据齐全 / 工具跑通 /
  构建成功 / 全局门禁 / 反向证明被当正证据）、本项目三层判据（C1–C6 · P1/P2/P3 · L1–L4）、
  防止自证的四道闸（已提交产物 / ROM SHA-256 绑定 / 探针失配自动降级并返回 1 /
  写回探针真的跑一遍）、自检命令清单、当前实测状态、可以宣称与不可以宣称的清单。
- **2026-10-21 重跑实测**（全部现跑，非引用旧快照）：

  | 自检命令 | 结果 |
  |---|---|
  | `python tools/completion_audit.py --check` | 退出码 **0**，`failed_probes=0`，47 结构 |
  | `python tools/automated_test.py` | **28/28 PASS** |
  | `python tools/alias_audit.py rom/base.gba` | `RESULT: OK`，未裁决冲突 **0** |
  | `python tools/writeback_paths.py` | **17/17** 写回路径 PASS |

  等级分布 **L4=0 / L3=4 / L2=1 / L1=30 / 无独立证据=12（全部已裁决=基址无效）**；
  格式已证明 **35/47**、写回可用 **24/47**、阻塞缺口 **0**、加固缺口 **105**。
- **判据结论**：**P1 / P2 / P3 三条已达成** —— 在这个口径下"逆向 100% 完成"成立；
  但 **L4=0**（未完整通关）、12 个结构仍待重新定位真实基址，
  所以**不得**宣称"整个 ROM 每一处都反编译完了"。
- **对续作路线的影响**：再次确认「加固缺口不是开工前置条件」——
  按需为本次改动涉及的结构补动态证据即可；把 L4 当开工门槛是本项目已付过学费的错。

---

## 2026-10-21（凌晨）｜**木叶战记汉化 ROM 静态重编译完成**：正式工程 `recomp/` 达到 100% 静态覆盖

> 承接上面两条（基线复现 → IWRAM 拷贝代码收敛）。这一轮把「在 scratch 目录里跑出结果」
> 变成**正式工程 `recomp/` 本身可复现地达到同一状态**，并补齐了流水线的两处硬伤。
> 详细记录：`notes/gba-static-recomp-feasibility-20261020.md` §13。

- **重编译对象确认**：`rom/base.gba` 与用户那份
  `火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba` **SHA-1 完全相同**
  （`26f60795fa5e63b4f0264b84e453beffd56b9f7d`，6,291,456 字节）——确认编译的就是这份汉化 ROM。
- **配置归位到正式工程**：`recomp/config/naruto_konoha_senki.toml` 从 9 个 `[[extra_func]]`
  扩到 **22 个 `[[extra_func]]` + 4 张 `[[code_copy]]` + 3 块 `[[data_range]]`**，
  把 IWRAM 重定位代码的映射（含 `source_addr`）正式纳入工程配置。
- **最终指标（`recomp/` 端到端重建实测）**：
  | 项 | 值 |
  |---|---|
  | 静态函数 | **13,271** / 8 分片 / 103 MB C++ |
  | 静态覆盖 | **`FULLY_STATIC`**：`dispatch_misses=0`、`interpreted_insns=0`、`healed_native=0` |
  | BIOS 后端 | `LLE (recompiled BIOS)` |
  | 渲染 | 调色板 512/1024、VRAM 40,688/98,304、OAM 158/1024 |
  | exe / 静态库 | 22.9 MB / 58.2 MB |
  | **画面一致性** | 20,000 帧 PNG 与 `recomp/screenshots/03-chinese-nameplate-20000frames.png` **SHA-256 逐字节相同** |
  | **端到端重建耗时** | **100 秒**（BIOS 重编译 → ROM 重编译 → 编译链接 → 跑 20,000 帧） |
- **两条运行路径都验证**：无窗口（`--no-window --dump-png`）与
  SDL 窗口（`renderer=direct3d11`、`frames_presented=900`、真实 720x480 窗口），
  两者都是 `FULLY_STATIC`。
- **流水线修缮（三处，都是"能跑但不对"级别）**：
  1. `recomp/CMakeLists.txt` —— `add_executable` 里重复列了分片源文件，导致同一批 11–14 MB
     分片被编两遍（构建时间翻倍）；同时补上 `/bigobj`（否则 C1128）。
  2. `recomp/build.ps1` —— 把自愈缓存按**配置文件内容哈希**隔离到独立目录。
     框架判 `FULLY_STATIC` 的条件含 `healed==0`，而旧 overlay 的**热缓存**会让
     `dispatch_misses=0` 却报 `NOT_STATIC`——看起来像还有缺口，其实只是缓存残留
     （本次在运行目录里抓到了 10-20 19:17 的旧 overlay 残留作为活证据）。
     另外框架的缓存子路径只按 ROM sha1 分，同一 ROM 的不同配置会共用同一批 overlay，
     所以还必须按配置再分一层，否则用对照配置做实验会污染正式构建。
  3. `recomp/build.ps1` —— 运行日志落盘（`run_<frames>.out`）+ 构建结束自动打印覆盖率指标。
- **顺手修好了 Stage-2 自愈层（上游框架缺陷，本工程绕过并修复）**：
  框架原版的 tcc overlay 路径在 Windows 上是**断的**——三件事凑不齐：
  overlay 的 shim 没声明 `g_runtime_resume_pc`；overlay 是 DLL，访问宿主符号只能走
  导入表，而框架的 tcc 命令行既不带宿主 exe、声明也没有 `__declspec(dllimport)`；
  宿主 exe 默认还没有导出表。
  修法（本工程承担两件 + 框架一件，见 `recomp/patch-gbarecomp-overlay.ps1`）：
  shim 声明打 `__declspec(dllimport)` 补丁（打在**暂存副本**上，对上游零侵入、幂等）、
  `CMakeLists.txt` 加 `/EXPORT:g_runtime_resume_pc`、给框架 `overlay_compile.cpp`
  打补丁把宿主 exe 加进编译命令行。
  **实测**（用去掉 `[[code_copy]]` 的对照配置强制制造 4 个缺口）：
  `failed 4 → 0`、`healed_native 0 → 6`、`interpreted_insns 3,516,074 → 0`、
  `native_calls 0 → 602,065`——**缺口全部被原生 overlay 接管，解释器一条指令都没执行**。
- **对续作路线的影响**：原生化路线的**移植层已收口**——
  ROM → 原生 exe 的整条链路在本仓库内可复现，静态覆盖缺口为 0，
  画面与参考逐字节一致。后续工作回到内容生产（改数据 / 改函数 / 发 mod 包），
  与移植层彻底解耦，可并行推进。

## 2026-10-20（深夜）｜原生化经验沉淀为可分发技能包 `gba-static-recomp`

> 把本轮「GBA ROM 静态重编译成原生 C++」的全过程抽象成一份 Mavis 技能包，
> **不安装到本机，只做成分发包**。详细记录：`notes/gba-static-recomp-skill-package-20261020.md`。

- **产物**：`dist/gba-static-recomp/`（源码）+ `dist/gba-static-recomp.zip`（36,761 字节，
  内层目录固定 `gba-static-recomp/`）。安装方式 = 解压到任一技能根。
- **结构**：`SKILL.md`（255 行正文，只写执行规则）+ 4 篇 references
  （排错表 §1–§22 / TOML 配置速查 / 工具链搭建 / 验证与覆盖率）+ 2 个脚本
  （端到端 `build-recomp.ps1`、日志解析 `summarize-run-log.mjs`，纯 Node 内置模块）。
- **评测**：with-skill vs baseline 两个 worker 并行跑同一任务（真实 ROM + 真实 BIOS）。
  结论——**技能无回归，且覆盖率收敛明显更强**：

  | 指标 | with-skill | baseline |
  |---|---|---|
  | 静态函数数 | **13,271** | 13,254 |
  | dispatch_misses | **0** | 4 |
  | interpreted_insns | **0** | 3,516,074 |
  | self_heal_coverage | **FULLY_STATIC** | NOT_STATIC |

- **评测驱动的技能迭代**（全部已回填进 references）：
  - baseline 贡献 §16–§20（BIOS 目录时序 / RAM overlay 开关 / overlay ABI 漂移 /
    `Tee-Object` 无 `-Encoding` / 分片被编两遍）；
  - with-skill 贡献 **§21 RAM 残留 PC 的四步定位法**与 **§22 tcc 热缓存导致
    `dispatch_misses=0` 却报 `NOT_STATIC`**；另补 `config-schema.md` 的
    `[[code_copy]]` 取值对照表、`verification.md` 的 `FULLY_STATIC` 判据。
- **对续作路线的影响**：原生化这条线现在有了**可分发的流程资产**——
  下一个 ROM 移植不必再从零踩一遍 20 个坑。静态覆盖缺口已归零，
  剩余工作回到内容生产（改数据 / 改函数 / 发 mod 包），与移植层解耦。
- **合规**：BIOS（任天堂版权）与生成的 C++（含任天堂代码）**均未进包、未入库**；
  `recomp/bios/.gitignore` 已挡住 BIOS。

## 2026-10-20（晚）｜静态重编译基线复现：GBA ROM → 原生 Windows 可执行文件

> 独立复现「不用模拟器、把 GBA ROM 做成 PC 原生程序」的完整链路，作为本仓库
> 静态重编译路线（`recomp/`）的**基线评测**。产物落在 `build/eval-baseline/`，
> **未改动 `recomp/` 下任何文件**。详细记录：
> `notes/gba-static-recomp-baseline-eval-20261020.md`。

- **链路跑通**：BIOS 静态重编译（LLE，770 函数）→ 卡带 ROM 静态重编译
  （13,254 函数 / 8 分片 / 103 MB C++）→ MSVC Release 编译 →
  `NarutoKonohaSenkiRecomp.exe`（22.9 MB）→ 无头跑 20000 帧并 `--dump-png` 出图。
  **编译 42 秒 + 运行 37 秒**（16 线程并行，生成语料只编一遍）。
- **画面**：3,000 / 20,000 / 60,000 帧导出 PNG 与 `recomp/screenshots/` 下的参考图
  **逐字节相同**（SHA-256 一致）——独立构建可复现既有渲染结果。
- **静态覆盖率**：13,254 个函数原生编译；运行期仅 **4 个 PC** 落到解释器
  （`0x030006A4` / `0x030006B4` / `0x03000930` / `0x03005CE8`，全部是 IWRAM
  运行期拷贝地址），解释器执行 3,516,074 条指令 / 总周期 62,191,750（≈ ≤5.7%）。
  渲染侧调色板 512/1024、VRAM 40,688/98,304、OAM 158/1024 全部非零。
- ~~**新增结论（剩余缺口的根因）**：这 4 个缺口**自愈编译器救不了**，原因不是配置，
  而是 **overlay ABI v6 的 `GbaOverlayCallbacks` 没有 resume_pc 访问口**：
  生成的 overlay C 引用 `g_runtime_resume_pc` → tcc 报
  `'g_runtime_resume_pc' undeclared`；而 exe 无导出表，overlay DLL 也无法在加载时
  从宿主解析该符号。要闭合这 4 个 PC，需要给回调结构体加 resume_pc 通道并升 ABI
  版本，或给 exe 加 `/EXPORT` 并在 shim 里补 `extern "C"` 声明。~~
  **↑ 这条归因已被后续实验证伪，见下面「IWRAM 运行期拷贝代码」条目。**
  正确结论是：这 4 个 PC **不是 ROM 地址**，而是启动时从 ROM 重定位到 IWRAM 的代码，
  用 `[[code_copy]]` + `[[extra_func]].source_addr` 即可闭合，
  **不需要动 overlay ABI，也不需要动 exe 导出表。**
- **对续作路线的影响**：原生化路线（改数据 / 改函数 / 发 mod 包）现在有了**可复现的
  基线工具链**；剩余工作收敛为上面那一个 ABI 缺口，与续作内容生产解耦，
  可并行推进。

## 2026-10-20（晚）｜静态重编译覆盖收敛：IWRAM 运行期拷贝代码 → **100% 静态覆盖**

> 承接上一条「静态重编译基线复现」。这一轮把基线留下的 4 个解释器桥接 PC
> 全部静态化，**dispatch miss 13 → 0、解释器执行指令 12,710,612 → 0**。
> 产物在 `build/eval-with-skill/`，**未改动 `recomp/` 下任何文件**。
> 详细记录：`notes/static-recomp-iwram-code-copies-20261020.md`。

- **关键纠正**：上一条把残留的 4 个 IWRAM PC（`0x030006A4` / `0x030006B4` /
  `0x03000930` / `0x03005CE8`）归因为「overlay ABI v6 没有 resume_pc 访问口，
  自愈编译器救不了，需要升 ABI 或给 exe 加 `/EXPORT`」。**这个归因是错的。**
  这 4 个 PC **不是 ROM 地址**，而是游戏启动时从 ROM **重定位到 IWRAM** 的代码；
  重编译器按卡带地址取字节当然取不到，于是退化成解释器桥接。
  正确解法是配置层面的 `[[code_copy]]`（运行期地址 → ROM 源地址映射）
  + `[[extra_func]].source_addr`，**不需要动 overlay ABI，也不需要动 exe 导出表**。
- **定位方法（可复现）**：
  1. `GBARECOMP_SELFHEAL_VERBOSE=1` 打出 `LR=0x03000694` —— 给出跳转来源；
  2. 在 ROM 里找拷贝例程的**字面量池**，成对读出 `(ROM 源, IWRAM 目标)`；
  3. 用「IWRAM 快照字节 == ROM 字节」实测每张拷贝表的 `size`；
  4. ARM 反汇编模块，逐个读出函数头，映射回运行期地址。
  工具留在 `build/eval-with-skill/tools/`（`find-iwram-source.mjs` /
  `block-extent.mjs` / `iwram-map.mjs` / `rom-inspect.mjs` / `disasm_arm.py`）。
- **四张拷贝表（实测，逐字节相同长度即 `size`）**：
  | 运行期 | ROM 源 | size | 内容 |
  |---|---|---|---|
  | `0x03000680` | `0x080004C8` | `0x200` | stub 跳板模块 |
  | `0x0300088C` | `0x08000520` | `0x0A4` | 同一模块的第二份拷贝 |
  | `0x03000930` | `0x080005AC` | `0x060` | 算术 helper |
  | `0x03005CE8` | `0x08000638` | `0x05C` | 表查找 helper |
- **最终指标**：BIOS 静态重编译 770 函数（LLE）；卡带 ROM 静态重编译
  **13,271 函数 / 8 分片 / 103 MB C++**；`NarutoBaseRecomp.exe` 22.9 MB；
  20000 帧运行 `self_heal_coverage=FULLY_STATIC dispatch_misses=0
  interpreted_insns=0 healed_native=0`；渲染侧调色板 512/1024、VRAM 40,688/98,304、
  OAM 158/1024 全部非零；`--dump-png` 出的 PNG 与 `recomp/screenshots/` 参考图
  **SHA-256 逐字节相同**。
- **对续作路线的影响**：原生化路线的**静态覆盖缺口已归零**，
  之前担心的「残留 PC 要靠改 ABI / 改 exe」不成立了；
  后续工作回到内容生产（改数据 / 改函数 / 发 mod 包），与移植层解耦。

## 2026-10-20（晚）｜逆向推进：原生消费者定位器 + 完成度审计重算

> 本轮把「逆向是否完成」从**人工读反汇编抄地址**变成了**机器可复现的判据**。

### 新增的通用取证器
- `tools/consumer_locate.py`：**全 ROM 字面量索引**。扫出所有 ARM
  `LDR Rn,[pc,#imm]`、Thumb-1 `LDR Rt,[pc,#imm]`、Thumb-2 `LDR.W Rt,[pc,#imm]`，
  得到 **18051 个被原生代码引用过的常量值 / 29920 条读取指令**。
  对任意表基址给出全部消费者（函数边界 + 用法分类 + 自动推步长），
  还能**邻居探测**（该基址附近真正被索引的地址）与**零引用判定**。
- 由此得到一条硬判据：**21 个 legacy 基址在整个 ROM 里一次都没出现过**
  （既不是字面量池常量，也不是任何数据指针）→ 它们的声明基址无效。
  笔记：`notes/legacy-table-base-correction-20261020.md`。
- `notes/evidence/consumer-evidence.json`：机器可校验的消费者证据，
  带 ROM 的 SHA-256（换 ROM 自动作废）。

### 完成度审计的变化（`tools/completion_audit.py`）
- 新增两类探针：
  - `codecite` —— C2 第 ④ 类「原生代码定址」的**机器化**版本：
    校验 ROM 指纹 + 该基址确实被游戏自己的加载读过 + 要求的指令片段出现在反汇编里；
  - `notatable` —— 反向证明：基址**零引用**，身份问题已裁决（但不算格式证明）。
- 两类探针**按结构基址自动挂上**，新增证据不需要改审计器。
- **修正了一个真实弱点**：此前 `tool` / `note` 探针拿不到结构的 `rom`，
  「提到本结构地址」这条**从未被检查过**。现已生效并修完两处失配。

| 指标 | 之前 | 现在 |
|---|---|---|
| L1（工具产出） | 15 | **20** |
| L2（原生定点） | 0 | 0（已被下面的 L3 覆盖，证据仍在） |
| L3（模拟器按键） | 1 | **3** |
| 无独立证据 | 30 | **0**（23 个已裁决 + 7 个升档） |
| 格式已被独立证明 | 17 / 46 | **23 / 46** |
| 写回路径可用 | 9 / 46 | 9 / 46 |
| 阻塞缺口 | 48 | **31**（21 条字段语义 + 10 条写回路径；identity 缺口已清零） |

> **P2 达成**：三类必测面**全部**达到 L3 ——
> 地图/战斗配置（positions）、剧情脚本（story VM 根表）、文本编码（字形段表）。
> - **剧情脚本**：`START` + `A`×3/4 → 剧情调度器 `0x0808F544` 命中（r0 = 0x36 = 54）→
>   VM 入口 `0x080977B8` 命中（r0 = 0x08049E76 = `before_root[54]`）→
>   画面上出现对白框，名牌「伊鲁卡」+「“是啊，是我这个班主任所承认的嘛！”」，
>   与场景 54 剧本**第 5 句逐字相同**。
> - **文本编码**：同一画面上，标点的像素与 ROM 字形表 `0x53D644` 的位图**逐位相同**
>   （`0x8142` = 「。」，8 个像素 0 差异）。
>
> **P1 也已达成**：46 个结构全部达到 L1 或以上，或被显式裁决（无独立证据 = 0）。

### 流程加固（本轮新增）
- `tests/test_line_endings.py` 增加 **UTF-8 BOM 守卫**：
  BOM 和 CRLF 是同一类「静默腐化」（会改掉 SHA-256 证据身份而 `git status` 干净）。
  守卫上线时立刻抓到 `tools/font_roundtrip.py` 是**带着 BOM 提交**的，已修掉。
  `third_party/` 是别人的只读副本，不在守卫范围内。
- `tools/populate_bank_json.py` 增加**裁决守卫**：已裁决的 bank 不再从旧基址重新导入
  条目，避免一次运行就把 `notes/alias-conflicts-20261020.md` 的裁决冲回原状。
- `tools/consumer_locate.py` 的证据文件带 **ROM 的 SHA-256**，
  换 ROM 后证据自动作废（审计器会报 `stale`）。

- **P1 判据已达成**：46 个结构全部达到 L1 或以上，或被显式裁决。

### 本轮并行取得的硬结论
- **剧情脚本 VM 指令语义**：44 条指令里 **38 条已证明 / 6 条推定 / 0 条未证**，
  出现覆盖率 19476/19476；解释器入口 `0x080977B8`、跳转表 `0x080977F4`。
  见 `notes/story-vm-opcodes-20261020.md`。
- **同址冲突全部裁决**：6 项冲突 + 第 7 处重叠
  （`resource-pointers` `0x596F0C` = 精灵动作表 `0x596CCC` + `0x240`）。
  见 `notes/alias-conflicts-20261020.md`、`tools/alias_audit.py`。
- **角色模板字段语义**：消费者 `0x0806D4A0` / `0x0806D964` / `0x0806D6B8` 全部定位，
  `+0x0A` 证实为体力基础值；`0x545458` 正确读法是 **16 字节记录表（87 条）**，
  不是 u32 指针表。见 `notes/character-template-format-20261020.md`。
- **战斗奖励表尾部字节**：已定为**奖励类别标签**（0=忍具 / 1=强化素材 / 2=认识卡 /
  3=技术，四路分派在 `0x0809731E`），**不是数量也不是档位**；
  同时证明条目步长是 **24 字节**（旧笔记的 16 字节说法作废）。
  见 `notes/reward-and-rules-semantics-20261020.md`。
- **胜负条件类型 3**：**「指定角色已离场」**（`rule.a`=阵营、`rule.b`=角色 id，
  判据是 `0x020240C0` 的 12 个单位槽里没有匹配者）。类型 2 的**代码**判据却是
  「回合上限到达」，而其数据行与类型 3 成对出现（意图是类型 3 的反面），
  本 ROM 未实现该意图 —— 需要一次 L2 断点 + 一次 L3 改写才能定案。

### mGBA 无头探针：运行时取证能力补齐
- 之前只用了 mGBA CLI 调试器命令的一小部分。实际有 **30+ 条命令**，
  含 **写监视点**、**删除断点**、**单步**、**读写内存/寄存器**、**指令跟踪**。
- 修掉三个致命坑：
  1. `frames`/`run` 走 fast path **永远不检查断点**；
  2. 断点命中后 **CPU 停在原地且断点仍挂着**（下次 `cont` 立刻重复报同一地址）；
  3. mGBA 的 `delete` **只删断点、删不掉监视点** → 反复重挂会累积监视点。
- 另外给宿主加了**帧步数上限**：mGBA 的 `mDebuggerRunFrame()` 是个
  「帧计数不变就一直 step」的循环，断点停在中断处理程序里时会**死转**，
  探针会静默烧 CPU。
- 定位到游戏**自己的按键状态**：`0x0300000C`（按住）/ `0x0300000E`（新按下）。
  按键注入一直是好的。
- **两条旧结论被证伪**：`0x020311EA` 不是场景号（是剧情 flag 位域内部）；
  `0x0808F698` 不是起始场景数据字节（是 `movs r0,#0x36` 的立即数操作数）。
- **L2 原生定点证据已取得**：`START → A → A → A` 的**第 3 次 A** 触发剧情调度器
  `0x0808F544`（**r0 = 0x36 = 54** = 场景号），随后 VM 解释器入口
  `0x080977B8` 命中（**r0 = 0x08049E76** = 场景 54 的脚本指针，
  与 `before_root[54] = 0x49E76` 逐位相等）。
  证据：`notes/evidence/story-vm-l2-20261020.md` + `story-vm-l2-capture.json`。
- **L3 模拟器按键复现已取得**：宿主原来先 `reset()` 再 `setVideoBuffer()`，
  而 mGBA 只在 `_GBACoreReset()` 里挂软件渲染器 → core 一直用 dummy 渲染器，
  画面全是白的。修好顺序后新增 `rawshot` 命令直接导出 **mGBA 自己的视频缓冲**
  （240×160 RGBA），不再需要 mGBA 的 PNG 支持。
  `START` + `A`×4 之后，画面上出现对白框：
  名牌「**伊鲁卡**」+ 对白「**“是啊，是我这个班主任所承认的嘛！”**」，
  与 `tools/decode_story_script.py --scene 54` 的**第 5 句一字不差**。
  画面冻结在 `notes/evidence/story-scene-l3.png`，
  说明见 `notes/evidence/story-scene-l3-20261020.md`。
- 附带结论：对话里的汉字是 **16×16**、标点是 **8×8**，而 `0x53D644` 那张
  字形段表是 **8×8**（渲染器 `0x08065EF4` 的 `lsls r0, r0, #5`）→ **游戏有两套字形**。
  再深一层：对话汉字的位图**也不在这张表里**（试遍 8×8 4bpp / 8×16 2bpp /
  16×8 2bpp / 16×16 1bpp / 2 倍放大各向都无法复现屏幕，最佳平均差异 27/128 像素）。
  候选区已列出（`0x0813E040` / `0x0813E120` / `0x0596D60` / `0x0142A70` /
  `0x0142AC0`），但**均未证实**；「屏幕 → 调色板索引 → ROM 字节」的反推链
  在密集汉字上不成立（文字带抗锯齿/半透明混合）。
  `notes/font-encoding.md` §1.1/§1.2 与 `notes/resource-locations.md` 已相应更正
  （并留档了一条被推翻的断言）。
- 新工具 `tools/mgba_probe/runtime_probe.py`、`tools/mgba_probe/screen_text.py`；
  笔记 `notes/mgba-probe-runtime-20261020.md`。

---

## 2026-10-20（深夜）｜逆向推进：写回路径**可执行化** + 缺口分类重构

> 上一节把「格式有没有被独立证明」机械化。这一节把**「写回路径可用」**
> 也机械化 —— 原来只要 `grep` 到生成器文件里有这个词就算数。

### 完成度审计的三处改造（`tools/completion_audit.py`）

1. **新增 `writeback` 探针（可执行）**
   `tools/writeback_paths.py` 为每个结构准备一条 case：读原生记录 → 施加作者改动 →
   回读 → 断言「回读 == 作者输入」**且**「除已知字段外没有任何字节被改动」。
   审计器**真的跑一遍**这条 case，并交叉核对 case 声明的基址与结构基址一致。
   → 写回路径可用：`9 / 46` → **`19 / 46`**；10 条写回阻塞缺口清零。
2. **未结项按类型拆分**
   旧口径把所有未结项都算成「字段语义未解」，于是「没有 m4a→PCM 导出器」
   和「某字段含义未知」混在一栏。现在分 `field` / `relation` / `evidence` /
   `capability` / `integrity` / `ambiguity` 六类，只有前两类（且 `field` 未被
   显式列出、或写回路径会碰它）才算**阻塞**。
3. **过期结论移出未结项**
   「`0x545458` 正确读法未确认」「`0x53D848` 是存档描述符表」这类**已经定了**
   的句子被从未结项里删掉，改记进结构目录的 `corrections`（结论变更留档，
   不许悄悄消失）。

| 指标 | 上一节 | 现在 |
|---|---|---|
| L1 | 20 | 18（3 个升到 L2/L3） |
| L2 | 0 | **1**（战斗胜负条件的类型 2 判据） |
| L3 | 3 | **4**（+ 运行时状态） |
| 写回路径可用 | 9 / 46 | **19 / 46** |
| 阻塞缺口 | 31 | **0**（P3 达成） |

> **P1 / P2 / P3 三条判据现已同时满足**，即本仓库自定义口径下的
> 「逆向 100% 完成」。这**不等于** ROM 每一处都反编译完了：
> L4（完整通关）仍是 0，23 个结构仍待重新定位真实基址，
> 81 条加固缺口列在 `notes/completion-audit-20261020.md` 的生成块里。

### 并行子代理拿到的硬结论（全部在本 ROM 上复核过）

- **胜负条件类型 2 = 「回合上限到达」**（L2 原生执行证据，
  `notes/evidence/battle-rules-l2-20261020.md`）：它在 `mode=1` 且回合上限 ≠ 0 时
  比对 `ctrl[6]`（`0x0202680A`）与 `byte[0x0202680C]`，
  **从不读 `rule.a` / `rule.b`**。所以旧笔记「与类型 3 成对出现、意图是类型 3
  的反面」的所谓矛盾**不成立** —— 它本来就不看 a/b。
- **运行时状态拿到读数**（`notes/evidence/runtime-state-l3-20261020.md`）：
  `scene_id`（`0x020311EA`）在开场剧情里是 **54 → 50 → 40**，
  `battle_stage`（`0x02026805`）= 40、`battle_sub` = 0、队伍槽 1 = 漩涡鸣人等级 1。
  旧推断「`0x020311EA` 不是场景号」**被运行时读数推翻**。
- **编成矩阵字段名定名**：`group_id`→**battle_stage**、`variant_id`→**battle_sub**、
  `record_id`→**actor_slot**、`selector`→**character_id**、`aux_u32`→**unit_flags**、
  `+0x02/+0x03`→**spawn_x/spawn_y**、`+0x04`→**facing**。
- **角色模板字段语义**（`notes/evidence/char-reward-fields-20261020.md`）：
  `+0x00` / `+0x07` 仍未知（4 个消费者都不读），`+0x0A` = **体力基数**；
  `0x545458` = **16 字节忍术记录表，87 条，下标 = 忍术 id**。
- **奖励表取值域**（同笔记）：328 个尾槽的 id **全部落在各自类别的名字表容量内**
  （0 越界）；类别 → 名字表由 ROM 自带的 4 槽指针表 `0x0859F5E0` 证明。
- **机关效果表 target 9 / 11**：target 9 **根本到不了效果表**（被 `0x08081984`
  截走跑剧情 VM 脚本），target 11 是**空操作**；type 5/6/7 **不决定脚本**，
  脚本由 target 决定。
- **剧情底图 8bpp**：4bpp 与 8bpp **互斥**而不是叠加 —— 每条都是一整张 32×32
  硬件 BG 地图。旧结论「8bpp 层叠关系未还原」**作废**。
- **地图描述符**：metatile 缓冲 = WRAM `0x0201DE2C`、每项 8 字节、容量 **2048**；
  「没有图层 1」的判据就是 **`layer1_ptr == 0`**（14 非空 / 33 NULL，已复核）。
- **字形码反向映射**：8 个重复字符的**规范码 = 基础 GB2312 序里的那个码**，
  规则有 ROM 证据与 5 条可证伪检验（`notes/evidence/font-reverse-mapping-20261020.md`）。

### 顺带修掉的工程缺陷（详见 `notes/db-writeback-correction-20261020.md`）

- 5 个 DB 生成器仍在往**已被裁决为窗口**的地址写（`0x53F200` / `0x53F1DC` /
  `0x53F138` / `0x596F0C`），其中 3 个会破坏活表 —— 现在改写到裁决后的真实基址，
  两个身份被证伪的**显式拒绝**（沿用 `generate_unit_patches` 的先例）。
- `0x53D848` 的第二个 u32 是**分配大小**不是 `sram_offset`（旧名误导）。
- **编辑器 → 构建的 override 链是断的**：editor.db 的键是 `group0`，
  bank 的 id 是 `group0.main`，**交集为空**，即使数据库塞满也产出 0 条 override。
  现在按 **ROM 偏移**连接，且**只把作者真正改过的行**当 override
  （种子文本来自 dev ROM，推回 base ROM 会静默覆盖真对白）。
- 新增奖励表写回路径 `tools/import_reward.py`（用 ROM 自带的类别→名字表指针表
  校验 id 越界），并接入往返自检 —— 现在 **12 条写回路径全部 PASS**。
- 测试：`74 tests / 7 failures + 1 error` → **`79 tests / OK`**；
  `automated_test` `27/28` → **`28/28`**。三个测试依赖被 gitignore 的
  `sequel/editor.db`、或断言了**已证伪**的地址，都改成了合成库 + 真实基址。
- **`0x53DF70` 的身份裁决**（`notes/evidence/cutscene-block-format-20261020.md`）：
  它**不是**剧情 VM 脚本表，而是**关卡数据块表** —— **4 项 × 8 字节**，
  每项一对指针（LZ77 4bpp 图块 → VRAM `0x06016000`、LZ77 16 色调色板 →
  调色板 RAM `0x05000380`），由 BIOS `svc 0x12`（LZ77UnCompVram）解压。
  旧结构库的「16 项 × u32」把**两张表并成了一张**（`0x53DF90` 起是另一个
  对象描述符表），并且允许下标越过表尾写进下一张表 —— 写回路径与
  bank.json 都已按 4 项 × 8 字节更正。

---

## 2026-10-21｜继续推进：`units` 偏移表定案 + 发现一张此前没被登记的活表

> 上一节把审计推到「阻塞缺口 0」。这一节继续啃**加固项**里最硬的那块：
> 17 个 legacy bank 的基址到底在哪。

### 方法论修正：邻域分析必须查**全量**字面量索引

`notes/evidence/consumer-evidence.json` 只存了 **54 张表**（审计关心的那些），
而字面量索引有 **18051** 个值、其中 **1196** 个是「活的」（有原生代码加载）。
用那份子集做「哪个活字面量离这个地址近」的邻域分析，**候选集会被静默截断**，
结论就跟着错。本轮第一遍调查就栽在这里 —— 纠正后候选集一下子从 0~3 个变成
5~10 个。

### `units` 表（`0x53F298`）语义定案

2026-07-11 的笔记 `notes/units-unsafe-table-fix-20260711.md` 留了一条可证伪判据：
「若能证明它把读出的 u16 **加到某个基址上**」。本轮**证实**了：

```asm
08080B2C  ldr   r1, [pc, #0x2c]   ; 0x0853F298   本表
08080B2E  lsls  r0, r3, #1        ; (入参 & 0xFF) * 2
08080B32  ldrh  r0, [r0]          ; V = 表值
08080B34  ldrh  r2, [r2]          ; B = WRAM 0x0202CA24 的 u16（运行时值）
08080B36  adds  r0, r0, r2        ; V + B
08080B38  lsls  r0, r0, #0x10
08080B3A  lsrs  r0, r0, #0x10     ; (V + B) & 0xFFFF  → 64 KB 窗口内的索引
```

并且旧 bank 的「`0x53F298`，128 字节，`u16[64]` 角色 ID 表」**横跨三张表**：
`0x53F298`..`0x53F2EE` 是 **43 项的 u16 重映射表**（{0..48} 去掉 6 个未用 id
的排列）、`0x53F2EE` 起是 **16 项有符号增量表**（独立读者 `0x08080AE0`）、
`0x53F318` 起是**代码指针表**。

### 附带发现：`0x53EE98` —— 一张此前完全没被登记的活表

3 个原生读者（`0x080806BA` / `0x0808077E` / `0x0808082E`），
**10 字节步长**、15 条记录（`0x53EE98`..`0x53EF2E`），每条 5 个 u16。
新增提取器 `tools/frame_descriptors.py`（自带取值域自检 ——
**上线第一天就抓到我把 `field_4` 上界写错**，如实报出并退出 1）。
已登记进 registry 与审计（结构数 46 → **47**，格式已证明 23 → **24**）。

| 指标 | 上一节 | 现在 |
|---|---|---|
| 审计结构数 | 46 | **47** |
| 格式已被独立证明 | 23 / 46 | **35 / 47** |
| L1 | 18 | **30** |
| 写回路径可用 | 19 / 46 | **24 / 47**（写回自检 12 → **17** 条） |
| 阻塞缺口 | 0 | **0** |
| 加固缺口 | 81 | 105（多出的行是新增结构自身的 L2/L3 加固行） |

### 十一个「基址无效」的 legacy bank 被重新定位

这一轮的收获集中在**旧基址错位**这一类问题上。机器扫全量字面量索引
（而不是只有 54 张表的证据子集）之后，17 个未定位基址里对上了 11 个：

| bank | 旧基址 | **真基址** | 真相 |
|---|---|---|---|
| `story` | `0x53636C` | **`0x536368`** | 不是剧情表，是 **sound id 1 的 m4a SongHeader**；旧基址锚在 `voicegroup_ptr`（+0x04）而不是表头起点 |
| `story-b` | `0x536BC8` | **`0x536BC4`** | sound id 2 的 SongHeader |
| `story-c` | `0x538FF0` | **`0x538FEC`** | sound id 8 的 SongHeader |
| `story-d` | `0x53AB78` | **`0x53AB74`** | sound id 11 的 SongHeader |
| `story-e` | `0x53C3BC`→`0x53C3C0` | **`0x53C3BC`** | sound id 14 的 SongHeader |
| `character-stats` | `0x54507A` | **`0x545068`** | 逐角色属性表，**63 条 × 16 字节**（表尾正好接忍术记录表 `0x545458`） |
| `character-stats-b` | `0x545200` | **`0x545068`** | 同一张表的另一个错位窗口（+25×16+8），**不是**嵌套关系 |
| `levels` | `0x5459D4` | **`0x5459C8`** | 角色特性表，**45 条 × 12 字节**（旧表声明 47 条，末尾 3 条其实越过表尾） |
| `items` / `skills` | `0x546100` | **`0x545BE4`** | 道具/技能记录表，**94 条 × 16 字节**（7 个读者；旧基址是第 81 条 + 12 字节的窗口；表尾正好接编成矩阵 `0x5461C4`） |
| `battle-encounters` | `0x542384` | **`0x54229C`** | 战斗遭遇记录表，**24 条 × 16 字节**（3 个指针 + 1 个编号，编号就在原生代码 `ldr r0,[r0,#0xc]` 读的位置；表尾正好接角色模板 `0x54241C`） |

配套产出：
- `tools/audio_song_headers.py` —— m4a SongHeader 提取器（带取值域自检）；
- `tools/import_audio_song.py` —— 音频写回路径（换 BGM 轨指针；
  轨块格式未证明，所以**只允许复用 ROM 里已有的轨指针**）；
- 写回自检从 12 条增到 **17 条**（新增 5 个 SongHeader 的往返 case）；
- `tools/frame_descriptors.py` —— 上一节发现的新表 `0x53EE98` 的提取器 + 5 条测试。

### 一条方法论教训

`notes/evidence/consumer-evidence.json` **只存了 54 张表**（审计关心的那些），
而字面量索引有 **18051** 个值、其中 **1196** 个是活的。
拿子集做邻域分析会**静默截断候选集**——本轮第一遍调查就栽在这里，
纠正后候选集从「0~3 个」变成「5~10 个」，三个基址当场对上。
详见 `notes/legacy-table-base-correction-20261020.md` §9。

### 剩下 9 个未定位基址：线索已查到候选，但没有一条够格裁决

`battle-handlers`（候选 `0x53E698`，步长 8）、`fonts`（候选 `0x53E496`，
字节表）、`data-table-a/b`、`menu-ui`、`map-events`（已判定为独立表）、
`function-pointers`、`tile-assets`——
线索、已查实的内容、**还缺哪条证据**都记在
`notes/evidence/remaining-rebase-leads-20261021.md`。
没有把「候选」写成「结论」。

---

## 现状总览

### ✅ 已打通
- 对白 → ROM 写入闭环（dialogue patch pipeline）
- 5 段对话已验证写入 ROM
- 构建流水线支持 5 种 patch 类型（bytes/dialogue/pointer_redirect/map/battle_config）
- mGBA headless 调试环境稳定（`tools/mgba-headless-snapshot.py`）
- mGBA PC/读取探针已加入：断点真实命中后可在同一上下文抓取 ROM 与 WRAM；
  复位 PC smoke test 已通过，地图 loader `0x08068FF0` 仍需可复现导航/有效状态
  才能将 maps 提升为动态验证
- **（2026-10-20 更新）无头 mGBA 探针已完全可用**：
  ① 视频缓冲接线修好后，`shot` 之外的 `rawshot` 能导出 **mGBA 自己的渲染帧**，
  画面是像素级精确的；
  ② `frames` / `run` 在挂着断点时走 debugger 路径，**按键与断点命中同窗口**；
  ③ 宿主新增帧步数上限 —— mGBA 的 `mDebuggerRunFrame()` 在断点停在中断处理
  程序里时会**死转烧 CPU**；
  ④ 导航已打通：`START` + `A`×3/4 就能进剧情，**第 3 次 A** 触发剧情调度器
  `0x0808F544`（r0 = 0x36 = 54 = 场景号），随后 VM 入口 `0x080977B8` 命中
  （r0 = 0x08049E76 = `before_root[54]`）。
- 剧情脚本与文本编码的 **L3 证据已取得**：
  画面上的对白「“是啊，是我这个班主任所承认的嘛！”」与
  `tools/decode_story_script.py --scene 54` 的**第 5 句逐字相同**；
  同一画面上的标点像素与 ROM 字形表 `0x53D644` 的位图**逐位相同**。
- 旧的 WASM 探针结论已被取代：当时报「一次相同按键计数重放未进入战斗」，
  根因是**导航判据用错了字段**（读 `0x020311EA` 当场景号，
  而它其实是剧情 flag 位域内部）；用「VM 入口断点 + 脚本指针」作判据后，
  剧情场景可稳定复现。
- 网页 WASM 首战导航与编成探针已可复现：单位槽 1 坐标 `(4,4)` 唯一对应
  positions group 40 / variant 0 / record 0（ROM `0x588CA8`），positions 已完成
  runtime 验证
- WASM 探针现会记录 `0x02026804` 的 8 字节控制区及 `0x02026805` 标识；一次
  相同按键计数重放未进入战斗，证明下一步需改为画面/内存状态驱动导航，maps
  暂不升级验证等级
- 独立重放再次得到 slot 1 `(4,4)`，且 `0x02026805 = 40` 与 positions group 40
  一致；maps 第 40 行为 `0x53DE10`（36×44），但尚缺字段消费因果证据，仍保持
  code 验证
- units 旧结论已撤销：`0x0806E654` 实为读取单位 x/y，`0x53F298` 唯一消费者
  将其作为 u16 偏移查找；legacy units 回写已安全禁用，真实角色记录映射待定位
- 真实角色定义表已定位：`0x54241C`，63×`0xB4`；formation character ID 经
  `0x02022E34` 模板池复制到 `0x1D4` 战斗槽，待成功探针样本闭合动态证据
- maps width/height 消费链已定位到 `0x0201BE28..2B`；首战第 40 行预期
  `[36,44,9,22]`，探针已加入读取，待稳定状态导航取得结果
- chapters、skills、story beats、audio 四类无 ROM 身份的 legacy 危险回写已禁用，
  只输出 unmapped 诊断；lossless `rom_*` mirror 继续作为安全写回入口
- Phase 1/2/6 框架级完成

### 🔴 核心瓶颈（P0 — 逆向工程阶段）

| 目标 | 状态 | 备注 |
|------|------|------|
| tilemap 布局数据 | ✅ 已定位 | 32x32 grid at 0x14D000+ |
| 战斗配置表 | ⚠️ 需修正 | ROM 表(0x53D910, 0x53F298) + WRAM 地址均已确认，但**条目 32 字节字段顺序已判定为错**，按 P0-Step 3.5 统一 |
| 章节流程入口 | ✅ 已定位 | 剧情调度器 `0x0808F544`（r0 = 场景号，实测 54）+ VM 入口 `0x080977B8`（r0 = 脚本指针）|
| 剧情脚本 VM | ✅ 已实现 | 自研解码器，55 场景 0 问题；6184 行可读对白，见 P0-Step 3.5b |
| 战斗胜负判定条件表 | ✅ 已定位 | `0x594758`，7 种原版类型语义已证实，见 `notes/battle-tables.md` |
| 任务文字三表 | ✅ 已定位 | `0x348DAC` + `0x59AA5C`/`0x59D214`/`0x59E920`，138 条目已解出 |
| 游戏文本编码 | ✅ 已更正 | **自定义双字节字形码，不是 Shift-JIS**；见 `notes/font-encoding.md` |
| 文本写回路径 | ✅ 已修 | **2026-10-20 已切到字形码**：此前所有对白补丁写入的是玩家读不懂的乱码（日文按 cp932 编码进中文字形 ROM），且验收只查字节落位。现 `tools/text_codec.py` 为统一入口，5/5 槽位渲染结果 == 作者文本。见 `notes/text-writeback-migration-20261020.md` |
| 资源提取（图片/音频） | ⚠️ 部分 | tileset 地址已知，提取未完成 |

### 🟡 续作内容创作（逆向完成后）
- episode-01 剧情源稿细化
- 多章节内容模板

### 🟢 网页编辑器（❌ 方向已修正 2026-10-20）

> 原计划："逆向工程 100% 完成后启动"。该前提已被证伪 —— 见
> `notes/why-external-editor-shipped-20261020.md`。
> 新方向：**单文件夹离线 ROM 编辑器**（原生条目复制 + 覆盖式改写），
> 暂停 FastAPI + Vue + 登录/多用户/WebSocket 平台路线。
>
> 若未来确需多人协作，以下既有方案可复用：
> - 技术方案：FastAPI 后端 + Vue 前端，部署于本服务器（14.103.49.74）
> - 功能：地图编辑器、角色编辑器、技能编辑器、剧情编辑器、道具编辑器等
> - 架构：多用户 WebSocket 协作编辑，ROM 在服务端操作

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
- ⚠️ **2026-10-20 修正**：`0x596D5C` 不是"图块描述符表"，而是**精灵动作表**
  `0x596CCC + id*144 + action*16` 的 id=1 行（`0x596CCC + 144 = 0x596D5C`），
  每行 4 个指针 = `(frames, animations, gfx, palette)`。我们原记录的
  "col0 嵌套描述符 / col3 调色板"实际就是这 4 个指针。详见
  `notes/external-konoha-workshop-gap-20261020.md` §2.2
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

**状态：⚠️ 部分完成**（positions 已运行时验证；maps 与角色定义仍待动态闭环）

**已确认 ROM 数据表：**
- ❌ 旧 `0x0853F298` 单位 ID 映射结论已撤销；唯一消费者把它作为 u16
  对象/渲染偏移查找，legacy 回写已禁用
- ✅ 真实角色定义表：`0x0854241C` / file `0x54241C`，63×`0xB4`；待建立提取器并迁移 units bank
- ✅ 战斗场景配置表：`0x0853D910` / file `0x53D910`，8 个有效条目 × 32 字节
  - ⚠️ **2026-10-20 修正**：条目格式为
    `+0 u16 原始宽 / +2 u16 原始高 / +4 tile gfx / +8 palette / +C 图层0 tilemap /
    +10 图层1 tilemap / +14 metatiles / +18 terrain / +1C 剧情底图ID`
    （宽/4、高/2 得图块网格）。terrain 解压长度 = 宽×高×2 已实测精确吻合。
    此前 `notes/battle-config-format.md` 与 `notes/chapter-flow-format.md` 的字段顺序
    互相矛盾且均与实测不符，需按 §2.1 统一
  - ptr1（+12/+10 图层 tilemap）：12 字节头 + 原始 tile 数据（u16/tile）
  - ptr2（+8 palette）：LZ77 压缩数据（解压后 384 字节）
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

### P0-Step 3.5｜吸收第三方剧情编辑器的逆向成果（2026-10-20）

**状态：🔴 刚发现，未开始实施**

**背景**：在 `D:\Downloads\火影忍者_木叶\木叶工房_剧情编辑器与后续DEMO_v0.4.4_无ROM`
发现一套第三方"剧情编辑器 + 剧情脚本编译器"。其基线 ROM 与本仓库 ROM
**SHA-256 完全一致**（`1198ece7…`），因此其全部地址/偏移/指令编号**可直接复用**。

**已在本仓库 ROM 上实测复核通过的关键结论**（复现：`tools/probe_external_re_claims.py`）：

| 结论 | 状态 |
|---|---|
| 地图表 `0x53D910` 32 字节字段顺序（+0 宽/+2 高/+4 gfx/+8 palette/+C/+10 图层/+14 metatiles/+18 terrain/+1C 底图ID） | ✅ 实测（terrain 解压 = 宽×高×2 精确吻合） |
| `0x596CCC` = 精灵动作表（id*144 + action*16 → frames/anim/gfx/pal） | ✅ 实测 |
| 头像表 `0x5A4DEC`（id*40+expr*8）+ 拼块表 `0x4643C0`（20 字节/块） | ✅ 实测 |
| 剧情脚本根表 `0x60C74`/`0x60D54`/`0x60E34`/`0x60EF0` + 指令表（0x01/0x02/0x03/0x07/0x15/0x1A/0x1B/0x22/0x32/0x34/0x36…） | ✅ 实测（原版脚本字节核对） |
| 任务文字索引表 `0x348DAC`（u8×48，每场景 3 条）+ 三张文本表 `0x59AA5C`/`0x59D214`/`0x59E920` | ✅ 实测 |
| 战斗条件表 `0x594758`（stage*0xCC + sub*0x44，2 组 × 4 条 × 8 字节） | ⚠️ 结构可用，类型 0..9 逐条语义待我们确认 |
| 战斗单位槽 stride 468（`0x020240C0`）、队员池 stride 188（`0x02022E34`） | ✅ 与既有结论一致 |

**本仓库完全没有、而对方已实现的三块（P0 缺口）**：
1. **剧情脚本 VM 图解码器**（`E.graph`：带 op/length/targets/text/offset 的节点图）
   → 没有它就没有剧情编辑器
2. **战斗胜负判定条件表读写**（`0x594758`）
3. **任务文字三表 + 索引算法**

**方法论解锁点**：对方用 **mGBA 0.11 C API**（`tools/gba_probe.c`）在 C 层驱动模拟器，
**可以注入按键**。我们长期卡住的 "mGBA headless 无法注入按键" 属工具层限制，可绕过。

**必须先裁决的冲突（C1~C4）**：
- C1 地图表字段顺序错（`notes/battle-config-format.md` + `notes/chapter-flow-format.md` 互相矛盾）
- C2 `0x596D5C` 被误认作图块描述符表（`notes/map-format.md`）
- C3 `0x599634` 被误认作 Sappy 音频索引表，实测是**忍具名称文本指针表**
  （`notes/dynamic-verification-audit.md`、`notes/patch-generator-audit.md`、
  `docs/structure-field-semantics.md` #22 均需复核）
- C4 `notes/battle-config-format.md` 的单位结构 236 字节已过期（应为 468）

**交付物**：
- ✅ `notes/external-konoha-workshop-gap-20261020.md` — 完整差集清单与验证记录
- ✅ `tools/probe_external_re_claims.py` — 可复现探针（本仓库自写）
- ✅ `third_party/konoha-workshop/` — 第三方自编代码已 vendored（155 文件，1.28 MB，
  MIT 授权部分；原作音乐/字形位图/参考美术/BPS 补丁已按许可排除）。
  **定位为只读逆向知识库**，改动请在本仓库另起实现，详见其 README
- ✅ **成果已吸收为自有实现**（见下方"已吸收"小节）
- ⬜ 剧情脚本 VM 解码器（`tools/decode_story_script.py` + `notes/story-script-vm.md`）
- ⬜ `notes/battle-condition-table.md` — 条件表结构与类型语义
- ⬜ `notes/mission-text-tables.md` — 任务文字三表

### P0-Step 3.5b｜已吸收：字形码 + 剧情 VM + 战斗表（2026-10-20）

**状态：✅ 核心三项已完成并静态验证**

第三方包带来的最大收获不是那几个地址，而是它的**字形码映射**。
用它做指纹校验后确认了一个颠覆性结论：

> **游戏文本是自定义双字节字形码，不是 Shift-JIS。**
> 本仓库此前把全部游戏文本当 cp932 处理，产出的都是乱码。

| 吸收项 | 本仓库实现 | 结果 | 笔记 |
|---|---|---|---|
| 字形码映射 + FNV-1a 指纹校验 + 编码器 | `tools/konoha_font.py` | 26/26 段指纹匹配；4261 码位 0 未解析 | `notes/font-encoding.md` |
| 往返验证 + 旧手工映射表判定 | `tools/font_roundtrip.py` | 真实文本 `encode(decode(x))==x` 字节级一致 | 同上 |
| 剧情脚本 VM 解码器 | `tools/decode_story_script.py` | 55 场景 × 4 根表，**0 问题** | `notes/story-script-vm.md` |
| 可读剧本导出 | `tools/dump_story_text.py` | **6184 行可读中文对白** | 同上 |
| 战斗条件表 / 任务文字三表 / 角色槽 | `tools/extract_battle_tables.py` | 86 条件条目 / 138 任务条目 / 85 角色条目 | `notes/battle-tables.md` |

**关键收获**：
- 62 个角色名全部从 ROM 姓名表解出（含"岸本齐史"彩蛋）
- 战斗条件 7 种原版类型语义由原版说明文字直接证实
  （type 10 是第三方新增扩展，**不是原版能力**）
- 任务标题/说明/提示三表此前完全无人解出

**遗留最高优先级风险**：~~写回路径仍按 cp932 编码中文，会写坏 ROM。~~
**✅ 2026-10-20 已关闭**：写回路径已切到字形码，
详见 `notes/text-writeback-migration-20261020.md`。
遗留项见该笔记 §5（`find_sjis_blocks.py` / `decode_dialogue_record.py`
仍用旧手工表；`sequel/editor.db` 被 gitignore 导致编辑器 override 链空转）。

---

### P0-Step 3.5c｜已吸收：字形码写回路径（2026-10-20）

**状态：✅ 端到端验收通过**

P0-Step 3.5b 解出了字形码，但**写回链路还停在 cp932**。本步骤把写回切过去，
并补上了此前缺失的那一环验收：**回读渲染结果**。

| 项 | 结果 |
|---|---|
| 统一编解码入口 | `tools/text_codec.py`（`encode`/`decode`/`decode_bounded`/`encode_tokens`） |
| 写回工具改造 | `import_dialogue.py` / `import_dialogue_var.py` / `patch_sjis.py` |
| 读侧改造 | `extract_dialogue_full.py` / `extract_text_block.py` / `import_rom_to_editor.py` |
| 内容库迁移 | `dialogue-bank.json` 7 条 → `encoding: "font"`；`dialogue-patches.json` → 真实中文 |
| 迁移工具 | `tools/migrate_text_bank_to_font.py`（可复现） |
| 验收工具 | `tools/verify_text_writeback.py`（打补丁 → 回读渲染 → 断言 == 作者文本） |
| 单元测试 | `tests/test_text_writeback.py`（11/11） |

**关键发现**：此前所有对白补丁写进 ROM 的都是玩家读不懂的乱码 ——
作者写的日文被按 cp932 编码进了中文字形 ROM；历次验收只查"字节落位"，
从未查"渲染成什么"。迁移后 5/5 槽位渲染结果与作者文本逐字相同。

详见 `notes/text-writeback-migration-20261020.md`。

---

### P0-Step 4｜定位章节流程入口（Phase 3 收尾）

**状态：⚠️ 部分完成 - 静态分析完成，runtime 验证受限于环境**

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

**状态：✅ 已打通并产出可用素材（2026-10-20）**

**现状：**
- **战斗地图图块**：`tools/extract_tileset.py` 重写完成。
  场景表 `0x53D910` 的字段顺序此前是错的（把维度数当指针，导出全是空图），
  现按 `0x08068FF0` 加载器的反汇编更正。
  产出 70 张 PNG：图块图集、2×2 组合图块图集、地图渲染图、剧情底图。
  **目视判据**：`build/tiles/battle_00_map_layer0_0.png` 渲染出连贯的木叶村，
  LZ77/4bpp/BGR555/metatile 排列任一错位都会碎成噪点。
- **音频**：真正的 sound-ID 表在 **file `0x465B70`**（ARM `0x08465B70`，159 行 × 8 字节），
  判据是 `0x0809AAC0` 的字面量池 + 指针链能解出 wave 头与 PCM。
  `tools/extract_audio.py` 据此重写，产出 manifest + 217 条 track bin
  + 79 个可播放 WAV + 80 个单循环 MIDI。
- **旧结论 `0x599634` 已被彻底证伪**：它是**文本脚本解释器**
  （`0x08079668`）的命令索引表，内容是 94 项中文（1 分隔线 + **93 个忍具名**），
  指针最终送进控制码文本解析器 `0x0806626C` —— 音频引擎不解析控制码。
  这与 `notes/font-encoding.md` 独立得出的"93 条忍具名"**互相印证**。

**遗留**：完整乐曲的 m4a→PCM 端到端合成（通道分配/鼓组/PSG/包络/混音）未实现，
MIDI 仅供结构试听；CGB PSG 声道无法导出；剧情 8bpp 底图的层叠未还原；
`0x53F138` 的身份冲突（audio/palettes 同称此址）仍未解决。

**交付物：**
- ✅ `tools/extract_tileset.py`（重写）
- ✅ `tools/extract_audio.py`（重写）
- ✅ `notes/resource-locations.md`（新表地址、判据、旧结论错在哪）

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
- mGBA + OCR 验证流程未完成

**方法：**
1. 搭建自动化验证：`build_mod.py` → mGBA 加载 → OCR 比对 → 报告
2. 每完成一个格式的 patch 生成，都要跑一遍 checklist

**交付物：**
- `tools/automated-test.py`（mGBA + OCR 验证）
- 所有格式的验证报告

---

## 当前推荐顺序

### 2026-10-20 文本写回路径迁移（关闭 P0 风险）

- 写回链路从 cp932 切到游戏自有的双字节字形码，统一入口 `tools/text_codec.py`。
- **核心发现**：此前所有对白补丁写入的是玩家读不懂的乱码
  （作者写的日文被按 cp932 编码进中文字形 ROM），
  而历次验收只检查"字节落位"、从不检查"渲染成什么"。
- `dialogue-bank.json` 7 条改为 `encoding: "font"`，notes 换成真实中文原文；
  `dialogue-patches.json` 重写为真实中文续作对白，对齐 `episode-01.json` 剧情草案。
- 验收改为**回读渲染结果**：`tools/verify_text_writeback.py`，
  对基准 ROM 与已构建 ROM 两种模式均 5/5 PASS。
- ROM 原文经字形码重编码与原字节逐字节一致（7/7），构成对映射表的独立强验证。
- 构建 `tools/build_mod.py` 通过（5 条 game_effective 补丁）；
  新增 `tests/test_text_writeback.py` 11/11；`tools/automated_test.py` 23/24
  （唯一失败项 `db_integrity` 为既有问题：`sequel/editor.db` 被 gitignore 排除）。
- **产物三方对照证实**：仓库已提交的 `build/naruto-sequel-dev.gba` 里对白就是乱码
  （`傣ROMV_20260624_100950崔`、`麻１夏`…）。已提交产物**有意未覆盖** ——
  它是用被 gitignore 的 `sequel/editor.db` 生成的（2438 条 db 补丁），
  重建会丢掉这些内容；修复改在隔离输出目录验收（5/5 PASS）。
- 顺带修掉 `tools/import_dialogue_var.py` 里从未被触发的 `ROM_BASE` 未定义 bug
  （`dialogue_var` 类型没在 manifest 里启用过），变长 redirect 路径现已打通并有回归测试。
- **第三方差集对账已完成两轮**（`notes/external-konoha-workshop-gap-20261020.md` §12）：
  - 第一轮：C1~C4 冲突裁决 + P0-1/P0-2/P0-3/P1-4 吸收 + P2-2 hook 点资产化
    （`tools/hook_points.py`，16/16 前像字节与本 ROM 逐字节一致）。
  - 第二轮：**P0-4 / P1-1 / P1-2 / P1-3 / P2-1 / P3-1 / P3-3 全部吸收**，
    P3-1 的 mGBA 探针**已移植并跑通**。每条都重新推导，**3 条结论与对方说法不同**：
    `0x02022EA0` 与两个 RAM 镜像是第三方自造簿记（ROM 中 0 引用）；
    原生机关 = 7 拾取 + 7 建立 + **13 项效果表**（不是"13 个拾取程序"）；
    事件队列上限 16 由 **stage 1 原始脚本顶满**得到实证，
    而 stage 20 静态值 17 说明静态分析是过近似。
  - 落点：`notes/runtime-and-object-tables-20261020.md`、
    `notes/mechanisms-20261020.md`、`notes/sprite-frame-format-20261020.md`、
    `notes/mgba-probe-build-20261020.md`、
    `notes/runtime-verification-gates-20260710.md`（四级证据分级）。
- **方法论增量已落地**（`notes/re-methodology-improvements-20261020.md` §4）：
  - **M1 合成夹具往返**：`tools/synthetic_fixture.py` —— **9 个夹具 37 项检查全绿**
    （story_before / battle_rules / battle_actors / reward_entry / mission_text /
    portrait_table / background_table / ninjutsu_names / skill_table）。
    把"写入已知内容 → 读回必须相等"变成格式证明，不再依赖模拟器。
    覆盖度见 `notes/fixture-coverage-20261020.md`。
    **限制：只达 L1，不构成动态语义证明。**
  - **M2+M3 变更半径**：`tools/build_mod.py` 报告新增 `change_radius` 段，
    任何声明区间外的字节改动**直接让构建失败**。
  - **M4 基址只从 ROM 取**：`tools/table_registry.py` —— 32 个内容 bank 与权威
    注册表 0 mismatch；投毒测试把 `maps` 的偏移改掉必须被检出。
  - **M5 负向测试**：`tests/test_process_improvements.py` 14 项。
  - 新增 `process` 套件进 `tools/automated_test.py`，**每次标准测试都跑**。
  - 附带修掉 **CRLF 污染**：`Path.write_text` 在 Windows 上把 `\n` 转成 `\r\n`，
    3 个受版本控制的文件被无声改写而 `git status` 不报。已加
    `tools/lib/io.py`（强制 LF）与守卫测试 `tests/test_line_endings.py`。
- **素材与物件格式（并行子代理产出）**：
  - `tools/tile_asset_rules.py` + `notes/tile-asset-rules-20261020.md`：
    单格地块替换的全部规则；**纠正两个旧数字**——调色板只有 **12 组**（不是 16）、
    地图表 **47 条有效**；47/47 图端到端模拟干净通过。
  - `tools/sprite_frames.py`：精灵动作表 `0x596CCC` 的 20 字节拼块描述符格式，
    **62 id × 9 action = 558 表项，342 个有素材**（2674 帧 / 2861 片），
    2860/2861 片完全合规。**纠正第三方三处**：id 实测 1..62（他们写 1..60）、
    帧指针表**没有终止符**（其后的第一个非指针字就是第一段动画描述符）、
    一帧最多 5 片（32 只是他们的扫描窗口）。`flags` 只有 0/1，
    **Y 翻转 bit1 全 ROM 零出现**，故其语义无法用本 ROM 证实。
    查实 ROM 自带一处单字节损坏（`0x25A8E5` 为 `0xFB`，应为 `0xFF`），
    仓库根 ROM 与 `rom/base.gba` 逐字节相同 → 随汉化版发货，非工具链引入。
    工具**不吞掉**它：`--check` 把这 5 条违规归因到该已知缺陷后 exit 0 可当门禁用，
    `--strict-rom` 则 exit 1。
  - `tools/object_tables.py` / `tools/portrait_assets.py` / `tools/extract_rewards.py`
    / `tools/runtime_state.py` / `tools/event_queue_budget.py`：见
    `notes/runtime-and-object-tables-20261020.md`。
  - `tools/mechanism_map.py` + `notes/mechanisms-20261020.md`：
    原生 = **7 个拾取处理程序**（`0x815E4`，索引 = 记录 type − 1）
    + **7 个建立期分支**（`0x0806E868`）
    + **13 项机关效果表**（`0x0808136C`，索引 = target − 1）。
    第三方那"13 种机关"的字是**叠加在原生 13 项效果表之上的命名**，
    数量对得上但不是 13 个拾取程序。type 6 在原版 46 战场里**一次未用**；
    忍具名表 93 条只用了 7 条、素材 16 条只用了 14 条、人物 62 条只用了 19 条。
  - `notes/character-template-format-20261020.md`：角色模板 `0x54241C` 的**结构**
    已定（12 字节头 + 24 字节条目区），字段语义仍未解；并查实
    **模板并未预烘焙进战斗配置**（原版那里全是 0，运行时才套用）。
- **当前关键路径**：静态工具已到位，但所有 L2/L3 动态证据都卡在
  **mGBA 注入按键 + 造 savestate** 上。**该阻塞已解除**：
  `tools/mgba_probe/` 的无头 mGBA 宿主已跑通 —— 按键注入实测生效
  （KEYINPUT 0x04000130 由 `FF03` 变 `F703`），savestate 实测可存可读
  （397412 字节）。根因与用法见 `notes/mgba-probe-build-20261020.md`。
  剩余缺口是**导航到目标场景**（进入战斗 / 章节），即
  `notes/runtime-verification-gates-20260710.md` 要求的
  "有效状态 + 有效输入" 仍需用新宿主重做。
- 详见 `notes/text-writeback-migration-20261020.md`。

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
  当前导航继续扩展 battle-control、map runtime、画面分类和转场等待，用于闭合
  maps 与真实角色定义的运行时证据。

### 2026-07-10 Bank 元数据审计基线

- 新增 `tools/audit_re_completion.py`，可重复检查 32 个 `sequel/content/*/bank.json` 的表偏移、格式字段、条目、验证标签和 Markdown 文档覆盖。
- 审计产物为 `notes/re-completion-audit.json` 与 `notes/re-completion-audit.md`。
- 首次审计结果为 23/32；随后已纠正 7 个偏移错误并从校验过的基准 ROM 重新提取，同时补齐 3 个格式描述。当前元数据检查为 32/32，但这仍不代表动态语义或真实回写完成。
- 验证分布现为 30 个 `static_verified`、1 个 `code_verified`、1 个
  `runtime_verified`（positions）；仍不能作为“100% 完成”的单独证据。

### 2026-07-10 u32 指针表回写进展

- 新增带索引边界、48 Mbit ROM 地址范围、Thumb bit 和数据指针对齐检查的通用
  u32 指针表真实回写 helper，并补充 6 项单元测试。
- `map_events` 与 story B–E 当前可生成 88 个真实表补丁，不再写 audit 保留区。
- 安全检查发现 `rom_battle_handlers` 和 `rom_map_sprites` 共 61 行 DB 数据使用陈旧
  `_rom_offset`，现已拒绝回写；下一工作周期需从 `rom/base.gba` 重新导入并验证。
- `battle_encounters` 是混合值表；`cutscene_scripts` 的声明边界含越界值，两者仍需
  重新确认格式，未计为完成。详见 `notes/u32-pointer-real-writeback-20260710.md`。
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
