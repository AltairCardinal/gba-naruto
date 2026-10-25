# 静态重编译产物的可改性分析（2026-10-20）

关联：`notes/gba-static-recomp-feasibility-20261020.md`（可行性实测）、`recomp/`（工程）
性质：结论整理，基于本仓库实测 + 框架官方文档（`mstan/gbarecomp` 的
`docs/MOD_PACKAGES.md` / `docs/TOML_SCHEMA.md` / `docs/ARCHITECTURE.md`）。

## 0. 一句话结论

**"源码"不在我们手里，但"可编译的等价实现"在。** 能改的内容分四层，
成本从低到高递增；**最优路线不是改生成码，而是改 ROM 数据 + 用框架的 hook 机制换函数**。

## 1. 我们手上到底有什么

| 产物 | 规模 | 性质 |
|---|---|---|
| 原机器码 | ROM 内 6 MiB | 任天堂的原始 ARM64/Thumb 指令，**完整保留** |
| 生成 C++ | **102.4 MB / 2,752,398 行 / 13,254 个函数** | 每条原指令降级为 1~3 条 C 语句，**带原地址注释** |
| 自动发现的结构 | 51 个跳转表、1,328 个 RAM 拷贝模板、98,861 条中缀别名→12,304 宿主函数 | 函数边界、switch 表、ROM→RAM 拷贝关系 |
| **原始源码** | ❌ **没有** | LocalThunk 当年写的那份代码不在这里 |

**我们做的不是反编译（decomp），是静态重编译。**
反编译（Ship of Harkinian / 黄昏公主那条路）要人工逆向匹配出可读源码，以年计工作量；
静态重编译保留机器码语义、只换执行环境，所以快，但产物是"降级后的汇编"。

可读性实样（生成码里的一条 ARM 指令）：

```cpp
    /* 08000234  08000234 A orr r1,r1,r2 */
    {
    g_cpu.R[15] = 0x08000234u;
    if (runtime_should_yield()) return;
    if (g_runtime_insn_trace) runtime_insn_fp();
    uint32_t _cyc_08000234 = 1u + (uint32_t)g_runtime_waits.s32[8];
    uint32_t _rm_08000234 = g_cpu.R[2];
    uint32_t _op2_08000234; uint32_t _co_08000234;
    _op2_08000234 = _rm_08000234; _co_08000234 = cpsr_c();
    uint32_t _rn_08000234 = g_cpu.R[1];
    uint32_t _r_08000234 = _rn_08000234 | _op2_08000234;
    ...
```

→ **能看懂每条指令，但函数名是 `gf_afunc_080000C8` 这种自动名，局部变量是 `_r_08000234` 这种。
可读 ≠ 好改。**

## 2. 可改的四层（成本递增）

### 层 1：改游戏数据（文本 / 图块 / 调色板 / 数值表）—— 完全可行，成本最低

**关键事实：数据不在生成码里。** 运行时游戏仍通过 `bus_read_u32` 等从 ROM 读数据
（生成码里 63 万处 `0x08xxxxxx/0x06xxxxxx` 字面量绝大多数是代码地址与字面量池，不是资源数据）。

所以：**改数据 = 改 ROM**，用本仓库现成工具链
（`tools/text_codec.py`、`tools/patch_sjis.py`、`tools/import_dialogue.py`、
`tools/tile_asset_rules.py`、`tools/extract_text_block.py`…），改完重跑
`build.ps1`（重编译 0.1s + 编译 ~60s + 运行）。

> 这条路**与静态重编译无关**，是现有续作主线。静态重编译只是给了一个更好的宿主。

### 层 2：改单个 guest 函数 —— 框架原生支持，**不用重编译**

TOML 里声明允许被替换的函数：

```toml
[[mod_function_hook]]
addr = 0x08003000
mode = "thumb"
note  = "Reviewed; replaced by trusted plugin"
```

游戏侧写 trusted native plugin：

```cpp
static int replace_draw(uint32_t addr, int thumb, ArmCpuState* cpu) {
    (void)addr; (void)thumb;
    cpu->R[0] = 1;                 // callback 自己写 guest 返回值
    cpu->R[15] = cpu->R[14] & ~1u; // 返回到 guest 调用者
    return 1;                      // 1 = 已处理，跳过原函数体
}
gba_mod_register_function_entry_plugin("example.replace-draw", 0x08003000u, 1, replace_draw);
```

- 可以**整段替换**一个 guest 函数，不改 ROM、不重编译、不重跑重编译
- 返回 0 = 拒绝本次调用，丢弃 callback 的 CPU 写入，走原函数体
- 框架有**审计**：TOML 里的 hook 地址若与生成的函数根漂移，编译直接失败
  （"An otherwise valid declaration that matches no static root is a hard codegen error"），
  防止 hook 静默失效
- 解释器/自愈 overlay 路径没有静态 TOML 语料，走 trusted registry 自己的窄 allowlist

### 层 3：点状常量修改 —— `[[thumb_alu_immediate_override]]`

精确到某一条 THUMB 立即数指令的 PC，替换其立即数（生成码在该 PC 插一个回调钩子）。
无条目时（默认）立即数保持编译期字面量，零性能开销。
用途：改伤害常量、掉落率、解锁门槛等。

### 层 4：呈现层 / 外挂式扩展

- `gba_mod_publish_foreign_background()`：插件发布自己的 240×160 BGR555 画面作"外来背景"，
  不改 guest 代码、不改 guest OAM/碰撞
- 宽屏：`gba_mod_set_view_width()` / `RunOptions::max_view_width`
  （引擎容量上限 896，含 32:9=569、50:9=889；**默认仍是 240**，每个游戏自己设上限）
- `gba_mod_publish_foreign_obj_focus()`：外来 OBJ 的焦点/缩放描述符

#### 层 4 补全（2026-10-23，直接核对框架源码 `build/gbarecomp-src`）

本文原来只记了 3 个呈现层接口。**框架实际提供的 mod 接口清单**（grep
`build/gbarecomp-src/src` + `platform` + `docs` 得到）比这多得多：

| 类别 | 接口 | 能力 |
|---|---|---|
| **屏幕叠加层** | `gba_mod_publish_foreign_screen_overlay()` / `gba_mod_clear_foreign_screen_overlay()` | **在 guest 画面上盖一层自己画的 UI**。契约见 `docs/FOREIGN_SCREEN_OVERLAY.md`：裁剪到 240×160、在原生 BG/backdrop 之后、**guest OBJ 之上之前**；可被 WIN0/WIN1/OBJ window 遮住；参与 BG2 的 `BLDCNT` 淡入淡出。**这是"新增 UI"最省的一条路——不用写一行 Thumb** |
| 呈现 | `gba_mod_publish_foreign_background()` / `_obj_focus()` / 对应的 clear | 外来背景层 / 外来 OBJ 的焦点描述符 |
| 函数 hook | `gba_mod_register_function_entry_plugin()` / `gba_mod_set_function_hook_enabled()` / `gba_mod_disable_all_function_hooks()` / `gba_mod_function_hook_hits()` | 整段替换 guest 函数；可统计命中次数 |
| 激活时机 | `gba_mod_register_activation_plugin()` / `gba_mod_register_reset_callback()` | 插件在**运行期**被激活/复位 |
| 音频 | `gba_mod_audio_play()` / `gba_mod_audio_register_pcm_s()` / `gba_mod_audio_stream_play()` / `gba_mod_audio_stream_register_s()` / `gba_mod_audio_mix()` | 新音乐/新音效（PCM 流） |
| 分辨率 | `gba_mod_set_internal_resolution()` / `gba_mod_internal_resolution()` / `gba_mod_set_adaptive_view_enabled()` | 内部分辨率（不是简单拉伸，是真的按更高分辨率渲染） |
| 选项 | `gba_mod_option_value()` | 读 `.gbamod` manifest 里的 `[[option]]` → **mod 自带可调参数**（例：分身数量 1..5 做成一个选项） |
| 资源 | `gba_mod_required_asset_path()` | 插件声明自己需要的资源路径 |
| 诊断 | `gba_mod_set_diagnostic_replay_enabled()` / `gba_mod_diagnostic_replay_enabled()` | 诊断回放开关 |

**信任模型（决定"谁能把原生代码放进去"）**（`docs/MOD_PACKAGES.md` L59-64）：

- **trusted plugin = 游戏自有的原生行为，静态链接进游戏二进制** ⇒
  **我们自己编译的 exe 里可以放任意 C++**（这就是"改到什么程度"的天花板）。
- `.gbamod` 包 = ZIP + `manifest.toml`，**"Archives contain data only"**：
  不能带原生代码 / DLL / 符号 / 库路径。

**hook 契约的硬保证**（`docs/TOML_SCHEMA.md` L200-225）：

- `[[mod_function_hook]]` 的 `addr`+`mode` 必须**正好命中一个静态函数根**，
  否则是**硬 codegen 错误**（不是警告）⇒ 不会出现"地址漂移导致 mod 静默失效"。
- 回调默认禁用；可以拒绝本次调用（走原函数体）；一旦接管，
  **必须自己写好返回后的 `ArmCpuState`（含调用者返回 PC）**，原函数体不再执行。
- 静态 ROM 根**必须**在 TOML 里声明；self-heal/解释器路径另走 trusted registry。

### 发补丁包：`.gbamod`

- ZIP + 根 `manifest.toml`，含 `[[target]]`（game_id + rom_sha1）、`[[feature]]`、`[[option]]`
- **只含数据，不含原生代码 / DLL / 符号 / 库路径**（硬性安全模型）
- 限制：≤4096 文件、展开 ≤256 MiB、校验 CRC、拒绝加密条目与不安全路径
- 装在 exe 旁边的 `mods/packages/<id>/<version>/`，选择状态存 `mods/state.toml`
- 适合发"显示增强包""难度选项包"这类可开关补丁

## 3. 明确不能做的

| 不能 | 原因 |
|---|---|
| `.gbamod` 里塞原生代码 | 安全模型硬性禁止（"Archives contain data only"） |
| hook 没在 TOML allowlist 里的静态 ROM 函数 | 必须先有 `[[mod_function_hook]]` 条目 |
| 永久改写 ROM 字节（通过 mod） | hook 机制明确"without permanently patching ROM bytes"；要改 ROM 就自己改 |
| 跨会话保存 native 状态到 guest 存档 | 框架用独立的 `write_mod_state_slot` / `read_mod_state_slot`，不借用 guest 存档填充 |
| 靠改生成码做"续作新内容" | 生成码是原版逻辑，续作内容必须走数据注入 / 外部代码 |

## 4. 法律边界（必须说清）

框架自己的 README 写得很直白：

> "Generated C++ is evidence, not authority"
> "The game code you generate and the build made from it **contain Nintendo's code**.
>  They are for your own use only: don't share them, upload them or ship them."

所以：
- **技术上**可以任意改动（上述四层）
- **分发上**受限：自用/研究 OK；公开发布改版 = 与发行原版同一风险等级
- 静态重编译的产物是**原版的原生复活**，不是续作

## 5. 给本项目的落地建议

按"改动成本 ÷ 收益"排序：

| 目标 | 路线 | 成本 |
|---|---|---|
| 改中文文本 / 对话 / 数值 | 改 ROM（现有 `tools/` 工具链）→ 重跑 `build.ps1` | **最低**（分钟级） |
| 改单个行为（伤害公式、掉落率、解锁条件、UI 排版） | `[[mod_function_hook]]` + native plugin | 低（不重编译） |
| 宽屏 / 画面增强 | `max_view_width` + `gba_mod_publish_foreign_background()` | 低 |
| 改一段大逻辑（整个战斗系统） | 改生成码（可读但难维护）或写 mod 层替换 | 中 |
| 续作新剧情 / 新角色 / 新地图 | 数据注入（现有主线）+ 必要的原生代码补充 | 高（本来就贵） |

**核心判断**：静态重编译对这个项目的价值**不是**"拿到源码好改"，
而是三件事：
1. **一个现成的原生宿主**（窗口/音频/输入/存档/联机/宽屏/mod 框架/诊断回放），
   省掉在 PC/移动端重建引擎的成本
2. **原版逻辑的可读 C++ 参考实现**，续作重写时有可对照的蓝本
3. **mod 基础设施**（hook + `.gbamod` + 存档槽 + 诊断回放），
   让"小改小挂"变成可分发、可版本化、可回滚的产品形态

而**续作内容本身，仍然走数据注入那条路**——两条路互补，不重叠。

## 6. 反编译 vs 逆向工程：概念判据与本项目选型

### 6.1 包含关系

**逆向工程（RE）= 伞形学科；反编译（decomp）= 其中一种具体手段。**
反编译 ⊂ 逆向工程 ⊂ 理解陌生系统的全部工作。

```
逆向工程 RE
├── 静态分析
│   ├── 反汇编 (disasm)      机器码 → 汇编文本
│   ├── 反编译 (decomp)       机器码 → 高层语言（★ 本文讨论的）
│   ├── 数据结构/格式还原
│   └── 符号与常量恢复
├── 动态分析
│   ├── 断点/单步/追踪
│   ├── 黑盒行为观测
│   └── 差分分析（本仓库的 mGBA 探针、诊断回放）
├── 协议 / 文件格式逆向
└── 硬件 / 固件逆向
```

### 6.2 关键差别

| 维度 | 逆向工程 RE | 反编译 Decomp |
|---|---|---|
| **目标** | *理解*——建立行为模型 | *重建*——产出可再编译的工程 |
| **产物** | 文档、符号表、地址表、数据结构定义、调用图、PoC | `.c/.cpp/.lua` 源码 + 构建系统 + 符号表 |
| **成功判据** | 能解释行为、能改对、能量化 | 能编译，且产出与原版**匹配**（函数级/指令级/字节级） |
| **成本形态** | 可按需切片，投入线性 | 追求全覆盖时是**整个游戏**的量级 |
| **是否必须** | 很多程序无法反编译，但照样能 RE | 可选路径 |
| **人力占比** | 自动化辅助，人做判断 | 大量人工匹配（社区用 asm-differ 逐函数比对） |

### 6.3 三个常见误解

1. **"反编译 = 逆向"** → 反编译只是静态分析的一种具体技术。纯黑盒 RE（观察输入输出推断协议）、
   纯动态调试，都不是反编译。
2. **"反编译出来就是原始源码"** → 不是，是**重建**。编译器会做优化/内联/宏展开，
   反编译器只能产出"语义等价"的一份，可能与原作者写法差别很大。
   所以社区才强调 **matching**（用 asm-differ 逐函数比对到字节级一致）。
3. **"逆向必须先反编译"** → 不对。先反编译再分析是**最贵**的顺序；
   工程上通常是"先动态定位 → 局部静态反编译 → 验证"。

### 6.4 本项目的对照

| 本仓库做的事 | 属于哪一类 |
|---|---|
| `notes/addresses.md`、`battle-tables.md`、`text-regions.md`、指针结构、调用图 | **逆向工程**（动态 + 静态混合） |
| `tools/*.py`（解包/注入/文本编解码/LZ77/图块规则） | RE 的**可执行产物**（把理解变成工具） |
| 静态重编译（`gbarecomp`，13,254 函数） | **不是反编译**——保留机器码语义，只换执行环境 |
| 反编译（把 ARM 还原成可读的原始 C/Lua） | **本项目没做**，也不打算做 |

### 6.5 为什么本项目不做反编译

> ⚠️ **2026-10-23 更正：本节的前提已被推翻。**
> 本节的理由是「**本项目要的是续作，不是复刻**」。
> 但ano 重制版的存在意图已被明确为——
> **「获得一份与原版完全一致并且可进行任意修改的源码」**，
> 也就是**复刻**，不是续作。
> ⇒ 本节与 §6.6 的裁决**按新前提重排**，见
> `docs/butano-fidelity-roadmap.md` §2.3。摘要：
>
> | 用途 | 新裁决 |
> |---|---|
> | 行为真值 / 对拍 oracle | **静态重编译**（100% 静态、确定性、可 hook、540–600 fps）——**不是全量反编译** |
> | 规格来源（读不懂时） | **按需局部反编译 + 读 recomp 生成码**（103 MB 生成 C++ 已含完整语义） |
> | 可交付的最终源码 | **Butano C++**（用户要的那份"可任意修改的源码"） |
>
> ⇒ 反编译从"**不做**"变成"**按需局部用**"，并附一条纪律：
> **局部反编译的产物只作规格，不直接进 Butano 树**（否则变成两份实现）。
> ⇒ 不采纳"全量 + matching"：48 MB ROM 的全量 matching 产出 275 万行**重建源码**，
> 它满足"可读可改"但**不是 Butano 实现**，等于作废 Butano 重制再重做一遍。

反编译的价值在于"拿到可读、可维护、可任意重写的源码"。但**当时**本项目要的是**续作**，
不是复刻。用反编译要付出全游戏量级的匹配成本，换来的却是：

* 一份 275 万行的"重建源码"——比生成码可读，但仍不等于原作者的代码
* **不解决续作的核心成本**（新剧情/新角色/新地图的内容生产）
* 却引入了额外风险与工程负担

而静态重编译 + hook + 数据注入三件套，直接对应续作真正需要的三件事：
**原生宿主、可定点改行为、内容可注入**。

### 6.6 选型判据（目标 → 手段）

> ⚠️ **2026-10-23 更正**：下表「1:1 复刻原版」那一行的裁决**部分采纳**——
> 反编译由"全量 + matching"降为"**按需局部**"；
> **行为真值改用静态重编译**（它已经是 100% 静态覆盖、确定性、可 hook 的可执行原版，
> 比 275 万行重建源码更适合当对拍 oracle）。
> 完整裁决见 `docs/butano-fidelity-roadmap.md` §2.3。

| 目标 | 该用哪条路 | 是否需要反编译 |
|---|---|---|
| 改中文文本 / 数值 / 图块 | 数据注入（改 ROM）+ 现有 `tools/` | ❌ 不需要 |
| 改单个行为（伤害公式、掉落率） | `[[mod_function_hook]]` + native plugin | ❌ 不需要 |
| 读懂原版某段逻辑以重做 | 逆向：定位地址 → 局部反编译 → 验证 | 局部需要 |
| **1:1 复刻原版（教学/存档研究）** | ~~全量反编译 + matching~~ → **静态重编译当真值 + 按需局部反编译当规格** | **局部需要**（不再全量） |
| 把原版搬到 PC/移动端跑 | 静态重编译 | ❌ 不需要 |

**结论**：反编译是"手段"而不是"终点"。本项目的终点是续作，
所以在"读懂"这一环用逆向（成本可控、可切片、已有大量既有成果），
在"复刻"这一环用静态重编译（成本低、保真），在"改"这一环用数据注入 + hook。
**反编译只在需要逐函数复现的局部才值得动用。**

