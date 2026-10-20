# 原生移植案例研究：四个代表性仓库拆解（2026-10-20）

调查日期：2026-10-20
上游笔记：`notes/static-recompilation-native-port-20261020.md`（技术路线总览）
本篇是**四个具体仓库的一手源码/README 级拆解**。未影响本仓库 ROM 逆向结论；`docs/sequel-roadmap.md` 进度未变。

> **延伸笔记**：`notes/ai-cost-of-native-port-projects-20261020.md` —— 这四个项目在 AI 上花了多少钱
> （可核实的 PR 规模、订阅补贴条款、单价基准与推算区间）。

## 0. 为什么这四个要放在一起看

它们经常被混称为"NS/GC 游戏原生移植 PC"，但**技术路线、复用关系、成熟度、可移植目标平台全都不同**。
放在一起对比才能看出 2026 年这门手艺的真实结构。

| 仓库 | 游戏 | 原平台 | star | 路线 | 关键复用点 |
|---|---|---|---|---|---|
| `999sian/melee-pc` | 任天堂明星大乱斗斗技 | **GameCube** | 510 | **B 反编译** + 硬件兼容层 | `doldecomp/melee` + `aurora`(WebGPU) |
| `ZeldaWWHDRecomp/ZeldaWWHDRecomp` | 塞尔达 御风之杖 HD | **Wii U** | 821 | **A 静态重编译** | 自带 Cafe OS 重实现 + GX2 直写 Metal/Vulkan |
| `peiikai/LASRecomp` | 塞尔达 织梦岛 | **Switch** | 1397 | **A 静态重编译** | AArch64→C→Zig/Clang，NVN-on-Vulkan |
| `ly05010419/MacNativeGames` | 塞尔达 王国之泪 | **Switch** | 2283 | **A' 原地 ARM64 改写** | NSO 改写器 + Horizon 宿主 + NVN-on-Metal |

---

## 1. `999sian/melee-pc` — 反编译 + WebGPU 兼容层

`https://github.com/999sian/melee-pc` · C · default branch `master` · 建仓 2026-09-14

### 做法
> "A native PC port of Super Smash Bros. Melee (NTSC-U 1.02), built from
> [doldecomp/melee](https://github.com/doldecomp/melee) on top of
> [aurora](https://github.com/encounter/aurora) (GX/OS/PAD/DVD/CARD/THP compatibility layer with a **WebGPU** backend) and SDL3.
> Same approach as [dusklight](https://github.com/TwilitRealm/dusklight)."

关键点：
- **游戏代码来自反编译工程**（可读的 C++），不是重编译机器码 → 路线 B
- 硬件层用 **aurora**：模拟 GameCube 的 GX/OS/PAD/DVD/CARD/THP，但**图形后端是 WebGPU（Dawn）**
  → 不是"翻译 GPU 指令"，而是**用现代 API 重新实现 GX 图形层**
- 渲染后端 Dawn/WebGPU → Vulkan / D3D12 / D3D11 / Metal 一套通吃

### 平台覆盖（README 自称"唯一事实来源"的状态表）
| 平台 | 状态 |
|---|---|
| Linux x86-64 / aarch64 | ✅ AppImage + tarball，CI 构建 |
| Windows x86-64 / ARM64 | ✅ D3D12 或 Vulkan（ARM64 走 llvm-mingw） |
| **Android arm64** | ✅ 有自绘的 GameCube 触屏 overlay（透明度/死区/震动设置） |
| iOS arm64 | ⚠️ 可侧载 IPA（Metal，交叉编译自 Linux）；触屏是固定隐形区域，无 overlay/校准 |
| macOS (ASL/Intel) | ⚠️ Apple Silicon 已测，Intel 未测 |
| **浏览器 (WebGPU)** | ⚠️ 浏览器里直接玩（`https://999sian.github.io/melee-pc/play/`），自带 GALE01 rev 2 镜像 |

### 特性
- RmlUi 启动器 + **Redump SHA-1 校验**（`d4e70c064cc714ba8400a849cf299dbd1aa326fc`，1,459,978,240 bytes）
- 内部分辨率 Auto→10x 原生（**6400×4800**）、后处理 shader、4x MSAA、16x 各向异性
- 手柄重映射（含 C-Stick 方向）、软件 AX 音频混音、用户 `.ogg`/`.wav` 替换 BGM
- 兼容 Dolphin `.gci` 记忆卡 + Dolphin 格式高清贴图包
- 作弊：Unlock Everything / 冰冻宝可梦竞技场 / 自由暂停相机 / 宽 16:9 HUD
- **UCF 0.8x** 后撤与盾下（dashback / shield drop）
- **1000 Hz GC 手柄适配器（WUP-028）**原始读数路径（走 SDL hidapi，绕开 SDL 重标定）
- `.slp` Slippi 回放录制（格式 3.18.0），`MELEE_SLP_DIR` 开启

### 联机：**rollback netcode**（本仓库最硬的部分）
- UDP 41000 游戏端口 + mDNS 5353 发现；直连 IP、好友码（`NAME#XXXXXXXX`）、Unranked 匹配、**Ranked 三局两胜**
- **协议 9，每个数据报带认证** → 两端必须同 build + 同盘（LAN 大厅广播 32 位盘 id，含区域/版本/文件表结构/DOL，改过码也算不同）
- **断线可恢复**：静默 7s 进入重连阶段，15s 内对方回来就从断点续演
- 输入延迟自动 1–4 帧（按 ping 与抖动推算，格斗中至少 2 帧，LAN<10ms 时 1 帧），每 600 帧重估
- **链路模拟器**：`MELEE_SIM_LOSS/DELAY_MS/JITTER_MS/REORDER/DUP/BURST`，PRNG 由 `MELEE_NET_PORT` 播种可复现
- 工具链：`net_test.py`（双实例真人对局断言）、`net_acceptance.py`（链路矩阵出 markdown 表）、
  `net_lan_test.py`（大厅路径）、`net_determinism.py`（跨平台录制回放找首个分歧帧）、`net_fuzz.py`（畸形数据报）
- 关键设计细节：*"A peer that is **loading** is not a peer that is gone"*——静默计时从"最后一次收到数据报"算起，
  正在加载关卡/角色/首次编译 shader 的一方 sender 仍在跑，链接能一直撑住

### 许可（**四种仓库里最讲究的**）
- `src/melee`、`src/sysdolphin` 里的**反编译游戏代码：未授权**，仍是原版权方的财产
- `src/pc`、`tools`、`platforms`、`cmake`、`.github` 里的**移植代码：GPL-3.0-or-later**
- 因为游戏代码不能 relicense，**整个仓库不是 GPL 可再分发物**
- 仓库内无任何游戏素材

### 性能
CPU 侧很轻：任意 x86-64（SSE2）或 arm64。VS 对局锁 60fps，整局钉在两个 2.5GHz Meteor Lake 低功耗 E-core 上，总占用约 1/3 个核。

---

## 2. `ZeldaWWHDRecomp/ZeldaWWHDRecomp` — PPC→C + Cafe OS 重实现 + GX2 直写

`https://github.com/ZeldaWWHDRecomp/ZeldaWWHDRecomp` · C · MPL-2.0 · org · 建仓 2026-10-01

### 做法（README 首段）
> "The game's **PowerPC code is translated to C ahead of time**, the **Cafe OS libraries the game uses are reimplemented natively**,
> and **GX2 graphics are implemented directly on Metal (macOS) or Vulkan (all platforms)**,
> with **no Cemu runtime and no GPU command emulation**."

### 三个仓库组成一个体系
1. **移植本体**（本仓库）：重编译 + 运行时 + 工具 + setup
2. **反编译**（`ZeldaWWHDDecomp/wwhd`）：可读 C++ 源码，**每个函数都与原版对比测试过**；
   移植版已能用 `-DWWHD_DECOMP=ON` 跑**反编译源码构建**（实验性，macOS only）——通往"完全源码移植"的路径
3. **Mods**（`ZeldaWWHDRecomp/ZeldaWWHDMods`）：游戏内 mod 目录 + 社区 mod 目录

### 构建三步（关键：编译发生在玩家机器上）
```sh
python3 tools/wudextract.py game.wux extract game     # -> game/code/cking.rpx, game/content/..., game/meta/...
python3 tools/recomp/recomp.py game/code/cking.rpx build/gen   # PPC -> C，写到 build/gen/
cmake -S . -B build/cmake && make -C build/cmake wwhd
```
- 需要：自己的 `.wud`/`.wux`/Cemu `.wua` 镜像 + **盘 key** + **Wii U common key（16 字节）**
- 只支持 **version 0**（无更新）：USA `00050000-10143500` / EU `00050000-10143600`
- 首次启动约 2 分钟在本机完成"解包 → 翻译 → 编译"
- **Windows 编译器必须用 Clang**（重编译代码需要 `musttail` 支持），MSVC `cl.exe` 不支持

### 图形与运行时
- 渲染器：Metal（macOS）/ Vulkan（Win/Linux/Android）；**从 Cemu vendor 了 GPU 地址库、着色器反编译器、参考结构**（MPL-2.0）
- 另有 metal-cpp(Apache-2.0) / {fmt}(MIT) / Dear ImGui(MIT)
- 内置 Cemu 移植：`tools/wudextract.py`、`runtime/src/espresso_fp.c`、部分 OS 层、顶点格式表、着色器解析胶水
- 着色器首次使用时翻译并缓存；提供**预编译 + 玩家贡献模板**机制（issue #177）

### 功能面（相当完整）
- 30fps 原生 / 帧插值 60·120·240fps / **真 60fps**（实验性，Link 与相机 60Hz，游戏状态仍 30Hz 逐位一致，
  但随机数序列会漂移，因为绘制代码也抽随机数）
- 内部分辨率 1x/1.5x/2x/3x、FXAA、AO 模式、16x 各向异性、**HDR（scRGB，Windows/Vulkan）**、**立体 3D**（Half/Full SBS、TAB）
- **Gameplay FOV 75%–250%**（战斗/过场用匹配投影，立体双眼各自渲染）
- 双窗口：TV + GamePad 屏（独立窗 / 画中画 / 自动浮层 / 仅 GamePad）
- 陀螺仪瞄准（手柄 / Cemuhook(DSU) / 鼠标"Steam Input gyro to mouse" 三种来源）
- **便携存档 `slotN.wwstate`（几 KB，不含游戏数据，可安全附在 bug report 里）** vs 完整存档 `slotN.bin`（约 270MB，**绝不可分享**）
- 崩溃恢复（每 2 分钟自动存 3 个状态 + 记录输入，`WWHD_REPLAY=<n>` 可重放复现）
- GC 存档转 HD：`tools/savegame/gc2hd.py`（实测 167 个 GC 存档），Tingle Tuner → Tingle Bottle，HD 专属统计不迁移
- 欧美版都支持，欧版自带 5 种语言文本；可实验性混用日/欧版资源 + 美版代码
- 右到左文本（阿拉伯语/希伯来语翻译）支持

### Mod SDK v2（最有产品化的部分）
- 代码 mod 用 **C/C++ 写成，编译给游戏自己的 32 位 PowerPC**；**一个包同时跑 macOS/Windows/Linux**
- 玩家安装时，移植版**用自己已有的编译器翻译并编译**它（游戏本体不再翻译）
- mod 在运行时 hook/替换游戏函数，用游戏自己的数据和对象，可绘制 HUD，可调用宿主服务
- 内容 mod（文件替换）与设置预设无需代码
- v0.3.0 起有**任务系统**：Story Notebook（任务日志）、Letters（Rito 邮筒送信）、Treasure charts、首批任务 *Call of the Sky* / *The Old map*
- mod 包只含数据与清单，**不含游戏代码**

### Android
由 `rhemfur` 开发：Vulkan + SDL3 Android activity，Galaxy S25 Ultra 上最重场景 30–32fps。
**release 里永远不会包含 `libmain.so` 或任何由游戏文件派生的东西**；release 只带 setup app，
玩家在**手机上**完成构建。CI 只用占位代码验证能编译。

### 交叉引用
- Switch 版本：`centollOS/SwitchWakerHD`（社区基于本项目做的 Switch 移植，独立项目）
- 工具链还用到 `zeldaret/tww`（GC 风之杖反编译，CC0）做**函数名匹配**（`tools/decomp/match.py`），
  以及 `tools/verify/` 差分测试台：让手写 C++ 与重编译原版在生成/录制输入上并行跑，比对返回值、内存效果与调用序列

---

## 3. `peiikai/LASRecomp` — Switch AArch64→C + NVN-on-Vulkan（已详查，见上轮）

`https://github.com/peiikai/LASRecomp` · C（生成器 Python）· MIT · 建仓 2026-10-08 · 1397★

要点复述（细节见 `notes/static-recompilation-native-port-20261020.md`）：
- 织梦岛（Switch v1.0.0）→ macOS(ASL, Metal+MetalFX) / Win x86-64(Vulkan) / Linux x86-64(Vulkan, AppImage) / Linux aarch64(实验)
- **AArch64 → C（`tools/gen.py`）→ 编译成本机库**；运行时替代 Switch：内核 + 系统服务 + **NVN-on-Vulkan + Maxwell 着色器翻译器** + 音频
- **release 包里不含任何游戏代码**，start screen 用自带的生成器 + Zig 编译器在**玩家机器上**完成重编译
- 内置随机生成器（item/room/连接器/音乐/敌人/宝箱/钥匙…全套 + check tracker）
- Switch 系统字体是任天堂 IP，需玩家自备
- **README 顶部明写：几乎全部由 AI（Claude Code）写成，人类负责指导/测试/审阅**

---

## 4. `ly05010419/MacNativeGames` — Switch ARM64 原地改写 + NVN-on-Metal（最激进也最优雅）

`https://github.com/ly05010419/MacNativeGames` · C · MIT · 建仓 2026-10-17 · 2283★ · 345 forks

### 做法（README 首段）
> "It is **not an emulator**: the game's own **ARM64 code runs directly on Apple chips
> (rewritten where the operating system requires it)**, the **Switch system services are answered by a small host**,
> and the game's **NVN graphics are rebuilt on Metal**."

**这是四者里最值得单独拎出来的一条路**：目标平台（Apple Silicon）**也是 ARM64**，
所以**根本不需要做跨架构指令翻译**——只需要
1. **NSO 改写器**：把游戏里所有面向 OS 的部分（系统调用、ABI、地址空间、异常处理）就地改写，
   让它能在 macOS/iOS 上跑；游戏主体代码原样保留
2. **Horizon 宿主**：一个小程序回答 Switch 的系统服务
3. **NVN-on-Metal**：把 NVN 图形 API 重建在 Metal 上

对比 LAS Recomp（AArch64→C→再编译）：

| | LAS Recomp | MacNativeGames |
|---|---|---|
| 指令处理 | 全部翻译成 C 再编译 | **原地改写，只改 OS 面向的部分** |
| 目标架构限制 | 任意（含 x86-64） | **仅 ARM64**（Mac/iPhone/iPad） |
| 主代码模块处理耗时 | 需完整重编译 | **约 1 分钟**（M4 Mac mini 上改写主代码模块） |
| 落地体积 | 编译产物 | 复用原始 ARM64 二进制 |

### 构建
```sh
python3.14 build_app.py ~/Games/totk.xci -k ~/keys/prod.keys                 # macOS .app
python3.14 build_app.py ~/Games/totk.xci -k ~/keys/prod.keys --platform ios -o ~/Games/TOTK.ipa
python3.14 build_app.py ~/Games/totk.xci -k ~/keys/prod.keys --update ~/Games/1.4.3.nsz
```
- 需要自己的 **XCI 或 NSP** + **`prod.keys`**；更新 1.1.2 / 1.2.1 / 1.4.3 用 `--update`（支持 NSZ，NCA 哈希会校验）
- NSP 另需通用票据 + `--firmware` / `--shared-fonts`（**六个 BFTTF 共享字体**，属任天堂 IP）
- 磁盘：工作目录 ~25GB + App 副本 ~17GB；**iOS 全新构建 45–60GB**
- iOS 需 iOS/iPadOS 26、iPhone 14 起；IPA 未签名，需侧载并保留提权 entitlement（用了提高的内存上限）
- **Mac 构建不需要 .NET 或 CMake**；成品运行时也不需要 Python——着色器翻译器是仓库自带的原生程序

### 技术栈（与前三个最大的不同）
| 组件 | 作用 | 来源 |
|---|---|---|
| **NSO 改写器 + Horizon 宿主 + NVN-on-Metal** | 方法论起点 | **`d2r-mobile`（jhaizhou-ops，MIT）**——为《暗黑破坏神 II：狱火重生》开发的同款做法 |
| **Ryujinx** 着色器翻译器 | Maxwell 着色器 → SPIR-V | MIT；用 **.NET NativeAOT** 预编成原生程序 `totk_xlate`（.NET 10 SDK 仅开发者需要） |
| **SPIRV-Cross** | SPIR-V → Metal Shading Language | Apache-2.0，固定提交 |
| deko3d / bcdec / libopus / libvpx | 贴图布局 / BC 解码 / 音频 / 预渲染影片 | zlib / - / BSD |
| `nxnative`（seedds） | 一脚本打包 + NSP 通用票据导入 | 参考其做法 |

### 着色器共享清单（**社区协作式解决卡顿**）
- 公共清单现有 **26,832 个 shader 变体（23,867 个 shader）**，只存标识与 bind state，**不含着色器代码**
- 游戏遇到清单里没有的变体 → 记进 `shader-list-contribution.txt`；Mac 上每 500 个问一次是否用 GitHub Issue 提交；
  iOS 设备连着打包它的 Mac 时由 Mac 代问；**游戏自己绝不上传任何东西**
- 打包时从玩家自己的游戏数据生成全部着色器（1.4.3 准备 15,266 个）并预热
- 用 Metal toolchain 构建 → 直接编进 App（M4 约 6 分钟）；没有 → 编进 macOS Metal 缓存（**不随 App 移动**，挪位置要重编）

### 表现
- M4（MacBook Air / Mac mini）：着色器预热后约 **90 FPS**，菜单里可达 120 FPS
- 帧插值、MetalFX 2K / 原生 2K、21:9 超宽屏（1.2.1 与 1.4.3）
- iPhone 14（iOS 26.6.1）与 A16 iPad（iPadOS 26.7.1）实测过 1.4.3
  - iPhone 14 内存占用接近 **4GB**，iOS 可能在 8 分钟左右因内存不足关掉游戏（已出现 2 次）
  - iOS 上**不能运行时翻译着色器**，缺失变体对应的绘制会被跳过 → 没人报过的地方可能缺物体
- 无联网、无 amiibo；DLC 不支持

### 质量工程
- **79 项自动测试**：生成的容器/更新样本、重定位格式、工作目录隔离、打包、桌面入口迁移、
  着色器提取（BNSH、agl 的 `.sharcb`、游戏模块内着色器）、共享清单与玩家贡献文件、
  首次导入的缓存保留、Metal 工具链查找、27 个原生 RomFS 路径用例
- GitHub Actions 跑源码测试，并在 **UBSan** 下跑原生路径解析器（不需要游戏数据或 key）
- 完整 Mac 构建用本地 XCI 派生的 NSP 样本 + 自动生成的通用票据跑通
- 哈希/签名校验严格：模块与 RomFS 对 `expected-v1.0.0.json` 等清单核对；**同版本的另一份真实零售转储也可接受**
  （改用任天堂 ACID 签名 `npdm_signed()` 校验 `main.npdm`，字体按 BFTTF 结构校验并绑实际 SHA-256）；**密钥值不进命令行也不打印**
- **README 第一行就是让用户用 AI 助手构建 App**（推荐 Claude Code / Codex）

---

## 5. 横向对比：四条路的真正区别

| 维度 | melee-pc | ZeldaWWHDRecomp | LASRecomp | MacNativeGames |
|---|---|---|---|---|
| 路线 | **反编译** | 静态重编译 | 静态重编译 | **原地 ARM64 改写** |
| 游戏代码来源 | 可读 C++ 源码 | 原版 PPC → C | 原版 AArch64 → C | **原版 ARM64 二进制，原样** |
| 硬件层 | aurora 兼容层 | Cafe OS 重实现 | Switch OS 重实现 | Horizon 宿主 + **NSO 改写器** |
| 图形 | **GX 重实现于 WebGPU/Dawn** | GX2 直写 Metal/Vulkan | NVN-on-Vulkan | NVN-on-Metal |
| 跨架构 | ✅ x86-64/ARM64 | ✅ x86-64/ARM64 | ✅ x86-64/ARM64 | ❌ **仅 ARM64** |
| 浏览器 | ✅ WebGPU 直接玩 | ❌ | ❌ | ❌ |
| Android | ✅ | ✅（手机上自建） | ❌ | ✅（iOS 侧载） |
| 联机 | ✅ rollback netcode | — | — | ❌ |
| Mod 体系 | 贴图/内存卡/cheat | **Mod SDK v2（任务系统）** | 随机生成器 | RomFS 替换式 mod |
| 许可 | 游戏码未授权 / 移植 GPL-3.0+ | MPL-2.0 | MIT | MIT |
| AI 参与 | 强（有风格检查与测试制度） | 强（差分测试台） | **明写"几乎全部由 AI 写成"** | **明写"用你的 AI 助手来构建"** |

### 可提炼的通法（四个仓库共同遵守的"规矩"）
1. **仓库里一个字节的游戏内容都不放**：程序、美术、文本、音频、shader、key、BIOS、解密工具一律没有
2. **编译/重写发生在玩家自己的机器上**：从 dump → 翻译/改写 → 编译 → 产出 App
3. **"你得自己拥有这份游戏"写在最前面**，并明确"只供自用、不要分享生成物"
4. **工具/框架开源，游戏专属补丁不开源**（LASRecomp 的 `make gen` 工具 MIT，生成的 `build/gen` 不进仓库）
5. **尽可能自动化 + 严格校验**：hash 清单、签名校验、差分测试、UBSan、自动化测试套件
6. **把"缺什么"变成社区协作**：LAS 的随机生成器生态、MacNativeGames 的 shader 共享清单、
   ZeldaWWHDRecomp 的 shader 模板贡献、melee-pc 的工具矩阵

### 三个"坑"（四个仓库都踩过并给出解法）
- **着色器卡顿**：都在做"预热 + 缓存 + 社区共享清单"，因为新场景必然触发首次编译
- **移植物是衍生物**：都明确写"生成物含原厂代码，仅供自用"（macOS/iOS 上尤其容易被当成分发）
- **玩家自备 dump 的门槛**：MacNativeGames 还要额外处理通用票据与 6 个 BFTTF 共享字体（Switch 系统字体是任天堂 IP）

---

## 6. 对本仓库（GBA 火影忍者）的可迁移结论

1. **GBA 也有对应的两条成熟路线**，不必从零造轮子：
   - `mstan/gbarecomp`（59★，C++）：ARM7TDMI → C++，含完整 GBA 硬件运行时（PPU/音频/DMA/定时器/IRQ/存档芯片/GPIO），
     已有 adaptive widescreen、`.gbamod` mod 包、Link Cable 联机、**Android arm64**、**WebAssembly 浏览器版**
   - `sp00nznet/gbarecomp`（MIT，C）：GBA 静态重编译工具包
   - 反编译路线本仓库已在做（`notes/addresses.md`、`notes/battle-tables.md` 等符号成果即是反编译的输入）
2. **本仓库的符号/地址知识可以直接喂给重编译工具链的"symbol import"**，
   与 `melee-pc` 依赖 `doldecomp/melee`、`ZeldaWWHDRecomp` 依赖 `zeldaret/tww` 做函数名匹配是同一模式。
3. **"宿主层 + 平台抽象"的做法值得直接照抄**：`gbarecomp` 的 `src/gba/` 就是现成的"GBA 是什么"的完整答案，
   比自己重新逆向一遍省事得多。
4. **产品形态参考**：`ZeldaWWHDRecomp` 的 Mod SDK v2（mod 编译给游戏自己的 CPU，玩家机上现编现跑）
   和 `MacNativeGames` 的共享清单（把"缺着色器"变成社区协作问题），
   对续作如果有 mod 计划，是可直接借鉴的两个成熟范式。
5. **质量门槛参考**：`melee-pc` 的 `CODING_STYLE.md` + `tools/check_style.py`、跨平台确定性回放工具链
   （`net_determinism.py` 找首个分歧帧）——这类"可复现"工程能力比功能本身更值得抄。
