# LÖVE / Lua 游戏移植 Android 手法调查（B站 UP「家里排第六」小丑牌安卓版）

调查日期：2026-10-20
性质：技术手法参考（侧向调查，不影响 GBA 逆向主线；未触发 `docs/sequel-roadmap.md` 进度变更）

## 1. 调查目标

用户提问：B站 UP 主 https://space.bilibili.com/609004093 在《小丑牌》(Balatro) 官方安卓版发布前就做出了安卓移植版，
求其实现手法。

## 2. 结论（一句话）

Balatro 是 **LÖVE 11.x (Lua)** 游戏，Steam 版 `Game.love` 本质是一个 zip（Lua 源码 + 资源）。
该 UP 把它解包、在 **Lua 源码层**做移动端适配与汉化，再用 **love-android 的 embed 版 APK 作为运行时外壳**、
把改好的游戏重新打成 `game.love` 塞进 `assets/`，用 **APKTool 重打包 + uber-apk-signer 签名**，得到可安装的安卓 APK。
不需要 C++ 重写，不需要 Unity/Godot 导出。

## 3. 关键时间线（已核实）

| 时间 | 事件 | 证据 |
|---|---|---|
| 2024-02-20 | Balatro 正式发售（PC/主机） | balatrowiki / Wikipedia |
| 2024-02-27 | UP 专栏《还没用过YUZU模拟器想玩小丑牌的小可爱看这里》，先做 **Yuzu/Suyu 模拟器中文 mod** | 专栏 `cv32074066`（publish_time 1708948355） |
| **2024-03-05** | **首个安卓原生移植版发布**（BV1yu4m1371p，APK `org.bal6tro.android` v1.0.0K，69.47MB） | 7723 手游网条目 Release Date 2024-03-05；3DMGAME 搬运帖 2024-03-06 明确写「原版移植来着B站UP:家里排第六」并给出该 BV 号 |
| 2024-03-16 | 专栏《行吧，不是盗资源蹭流量还反手举报我吗？您等官方发手机版吧！我停更！》（2.3万播放 / 86 回复），随后删视频停更 | 专栏 `cv33243782`（publish_time 1710579380） |
| 2024-03-19 | **开源工具 `blake502/balatro-mobile-maker` 建仓**（C#，Steam 版→安卓 APK 一键转换） | GitHub API `created_at: 2024-03-19T21:13:13Z` |
| 2024-03-23 | UP 仍在发布 Switch 模拟器试玩视频（现存最早投稿之一） | 投稿列表 `aid 1002104556` |
| 2024-04-05 | 1.0.1c 中文版（可与旧版共存）+《免root自定义模组使用和存档导出教程》 | BV1gE42137oS / BV1qm421775Z |
| 2024-04-20 | 《吐槽一下移植这件事》（主要吐槽被举报盗资源与侵权风险） | BV12Z421Y7NE |
| 2024-04-30 | 1.0.1f 简体中文版，同步 Steam 1.0.1o | BV1yM4m1o7oX |
| 2024-05 | 扩展到非 LÖVE 游戏：《恶魔轮盘 Buckshot Roulette 安卓直装（非模拟器）》 | BV1jt421E7ek（Godot 游戏） |
| **2024-09-26** | **官方手游版（iOS + Android）才发布** | balatrowiki：Mobile 2024-09-26 |
| 2025-01 起 | 版本号追到 1.0.1o；拖拽操作、32 倍速、快速存读档、内置修改器、天玑/骁龙 优化 | BV1gVo7Y7E4G / BV1RaLxznEWa |
| 2025-05 | 联机版（局域网 1v1 + 生存/对决/消耗战），后加在线列表、房间码、软键盘 | BV17qGezuEvt / BV1nWJuz4E1Y / BV15sTiztEmn |
| 2025-09 ~ 2025-10 | Maximus 模组版、游戏王机制模组（37 分类 403 张卡） | BV1nXHSz2EZu / BV1GvHJz2EyZ |
| 2026-06 | 「全网首发！真小丑牌自定义模组移动版！免Root！」（可加载任意电脑端模组、作弊菜单、自定义虚拟手柄） | BV13YL965ELh |
| 2026-07 | 自定义模组「模组市场」上线 | BV1ErMF69Eo9 |

> **结论性推论**：他的首个安卓版（2024-03-05）比开源工具 `balatro-mobile-maker`（2024-03-19 建仓）
> 早约 **两周**，比官方手游版（2024-09-26）早约 **半年**。即他是这条路线的先行者，工具是后来者。

APK 包名序列（同一作者不同版本共存用改 applicationId 实现）：
`org.bal6tro.android` → `bal6tro.Multiplayer.android` → `bal6tro.JoyousSpring.android`（游戏王模组）→ `bal6tro.maximus.android`（等离子模组）

## 4. 技术拆解（源码级，已核对 `balatro-mobile-maker` 的 `Patching.cs` / `Constants.cs`）

### 4.1 素材来源
Steam 安装目录里的 `Balatro.exe` / `Game.love`。`.love` = zip，内含：
`main.lua`、`conf.lua`、`globals.lua`、`game.lua`、`functions/*.lua`、`resources/`（shaders / 字体 / 精灵 / 音频）。

### 4.2 必须打的移动端补丁（精确到行）

| 文件 | 定位串 | 改法 | 原因 |
|---|---|---|---|
| `globals.lua` | `loadstring` | 整行替换为 Android/iOS 分支：`F_SAVE_TIMER=5`、`F_DISCORD=true`、`F_NO_ACHIEVEMENTS=true`、`F_CRASH_REPORTS=false`、`F_SOUND_THREAD=true`、`F_VIDEO_SETTINGS=false`、`F_ENGLISH_ONLY=false`、`F_QUIT_BUTTON=false` | 原行会 loadstring 出"移动端直接退出"的代码，必须先摘掉 |
| `functions/button_callbacks.lua` | `G.CONTROLLER.text_input_hook == e and G.CONTROLLER.HID.controller` | 追加 `or G.CONTROLLER.HID.touch` | 触屏也要能弹软键盘输入 |
| `resources/shaders/flame.fs` | `#endif` | 追加 `#ifdef GL_ES / precision MY_HIGHP_OR_MEDIUMP float; / #endif` | GLSL ES 精度限定符，缺了手机上花屏 |
| `resources/shaders/flame.fs` | `vec4 effect( vec4 colour, Image texture, vec2 texture_coords, vec2 screen_coords )` | 全部加 `mediump` | 同上 |
| `main.lua` | `G.FPS_CAP = G.FPS_CAP or` | 改成固定帧数或 `select(3, love.window.getMode())['refreshrate']` | 省电 / 帧率锁定 |
| `functions/button_callbacks.lua` | `resizable = true,` | `resizable = not (love.system.getOS() == 'Android' or love.system.getOS() == 'iOS')` | 强制横屏 |
| `conf.lua` | `t.window.width = 0` | 追加 `t.window.usedpiscale = false` | 高 DPI |
| `functions/button_callbacks.lua` | `highdpi = (love.system.getOS() == 'OS X')` | 追加 Android / iOS | 高 DPI |
| `globals.lua` | `crt = ` | `crt = 0,` | 关 CRT 滤镜（Pixel 等机型必关） |
| `game.lua` | `G.SHADERS['CRT'])` | 移除 | 同上 |
| `conf.lua` | `t.window.width = 0` | 追加 `t.externalstorage = true` | 存档放外置存储（可选，官方建议别开） |

### 4.3 打包流水线

1. 7-Zip 解出 `Game.love` → `Balatro/` 目录
2. 应用上面 4.2 的 Lua 补丁（**汉化就是在这一步直接改 Lua 里的英文字符串**，所以他的"简体中文版"是自己翻译 Lua 文本）
3. 下载 `love-11.5-android-embed.apk`（love2d/love-android 11.5a release）——这是 LÖVE 官方安卓运行时，embed 变体可以把游戏塞进 `assets/game.love`
4. `apktool d` 解包 → `balatro-apk/`；解压 `Balatro-APK-Patch.zip` 覆盖 `AndroidManifest.xml`（包名、应用名、方向）与图标
5. 把改好的 `Balatro/` 压成 zip → 重命名为 `game.love` → 放进 `balatro-apk/assets/`
6. `apktool b` 回包 → `uber-apk-signer` 用 debug key 签名 → `balatro.apk`
7. 可选：`adb install` 装机；用 adb push/pull 搬运 PC 端存档

依赖工具（与 `Constants.cs` 中的常量一一对应）：
`apktool_2.9.3.jar` / `uber-apk-signer-1.3.0.jar` / `love-11.5-android-embed.apk` / `Balatro-APK-Patch.zip` / `OpenJDK 21` / `platform-tools (adb)` / `7-Zip`

### 4.4 他额外做的事（超出开源工具能力）

- **汉化**：直接改 Lua 文本 → 字体换成中文字体（他另发专栏《部分机型游戏中报异常的解决方法》说"图形设置里关闭像素画平滑"）
- **免 Root 加载任意 PC 模组**：改 LÖVE 运行时，让它从外置存储扫描并加载 `.love` 模组包
- **联机**：自己写 Lua 网络层 + 房间码/在线列表/软键盘
- **改器、倍速、拖拽操作、快速存读档、天玑/骁龙 分支优化**
- **多版本共存**：改 applicationId

## 4.5 补充核实：引擎与各平台版本的关系（2026-10-20 二次核实）

### 4.5.1 他改包的对象 = **Steam Windows PC 版**

`balatro-mobile-maker` 的 README 明确写着：
> "This script assumes that **Balatro.exe** or **Game.love** is located in the default **Steam** directory."

Steam 安装目录结构（Windows 版）：
- `Balatro.exe` — LÖVE 启动壳（自带 love 运行时）
- `love/` — LÖVE 运行时 DLL 目录（BalatroBot 的 `BALATROBOT_LOVE_PATH` 就指向这里）
- `Game.love` — 游戏本体，**本质是 zip**，用 7-Zip 解开即得全部 Lua 源码

macOS 版 2024-03-01 才推出，Steam Deck 同属 Steam 版；因此 2024-03 时可用的、可改包的源只有 Windows Steam 版。

### 4.5.2 Steam 版本身就是 LÖVE/Lua 脚本游戏（**"是这样"的答案**）

Balatro Wiki（`balatrowiki.org/api.php` extract，title=Balatro）Trivia 段原文：
> "The game is written in the **Lua programming language**, using the **Löve framework**."

因此"给 PC 版打 mod"和"给 PC 版做安卓移植"**本质是同一件事**——脚本层开放，不需要反编译：

| 生态 | 做法 | 说明 |
|---|---|---|
| Lovely | 往游戏目录丢 `version.dll` / `liblovely.dylib` / `liblovely.so` | 运行时 Lua 注入器；文档原话 "Patch targets are the relative paths of source files when dumped from the game with a tool like **7zip**" |
| Steamodded | 模组加载器，装在 `%AppData%/Balatro/Mods` | 在 `main.lua` / `game.lua` 注入 `initSteamodded()` |
| BalatroBot | headless 跑 LÖVE + 暴露 HTTP API | 直接 patch `love.draw` / `love.graphics.present` / `love.window.setMode` |
| 模组本体 | 纯 `.lua` + 贴图 | Thunderstore 上 Balatro 模组全是 Lua（如 `localization/en-us.lua` 1254 行） |
| 移动版 UI 补丁 | `MobileLikeDragding` | 官方手游版才有拖拽出牌/卖牌，PC 端要靠 mod 补 |

**结论**：他做的事 = 把「PC 端跑 mod 的那套 Lua 改动」+「移动端补丁」+「LÖVE 安卓壳」三件事合到一起。

### 4.5.3 为什么 2024-03 官方没有中文，他必须自己汉化

- Steam 官方 API（`store.steampowered.com/api/appdetails?appids=2379780`）当前 `supported_languages` 已包含
  **Simplified Chinese / Traditional Chinese** —— 但这是**后来补上的**。
- 间接证据：他自己 2024-04-30 发布的《**小丑牌balatro 1.0.1f 安卓简体中文更新**》简介写
  "**原汁官方1.0.1f**"，说明当时官方 1.0.1f 仍是纯英文，中文是他自己翻译 Lua 文本做的。
- 对照：3DMGAME 搬运帖也把他的版本描述为"手机**汉化**移植"。

### 4.5.4 官方手游版为什么还要半年才出（且不是同一条路）

- 官方时间线：2024-09-26 发布 iOS + Android，另有 Apple Arcade 版 `Balatro+`；2026-02-25 又出了 Switch 2 版。
- 官方手游版走的是**官方原生移植 + 平台服务**路线：触屏 UI 重做（拖拽出牌/卖牌）、成就、云存档、内购、Apple Arcade 适配、
  以及 App Store / Google Play 审核与分级流程。
- 社区能用的"野生安卓包"（他的、以及 `balatro-mobile-maker` 生成的）在这些平台能力上全部缺失，**但能带 mod**——
  官方手游版并不支持 mod 生态，这正是他这条线长期有人用的原因。

---

## 5. 调查方法（可复用）

- B站空间页未登录时只渲染登录弹窗 → 需登录态（用户在 FilePanel 浏览器登录后才拿到投稿列表）
- 未登录走 API 也可拿数据，且比页面更全：
  - 投稿列表：`https://api.bilibili.com/x/space/arc/search?mid={uid}&pn=1&ps=50&order=pubdate`（pn=2 为最早期）
  - 专栏列表：`https://api.bilibili.com/x/space/article?mid={uid}&pn=1&ps=30`（返回 11 篇，含 cv id 与 publish_time）
  - 动态流：`https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?host_mid={uid}`
  - 评论：`https://api.bilibili.com/x/v2/reply/main?type=1&oid={aid}&mode=3`（type=1 视频 / type=17 专栏）
- `www.bilibili.com/read/cv{ id }` 直接抓会返回验证码页；改用 API + 浏览器登录态
- 风控：短时间内高频请求会返回 `-799 请求过于频繁` 或 412 验证码页，需降频
- 视频 BV 号可反查 aid（`/x/web-interface/view?bvid=`）后取评论
- 已被 UP 删除的视频页面会显示"视频内容已被UP主删除"，此时只能靠转载站 + 专栏 + API 交叉还原

### 5.1 游戏本体与引擎类事实的取证途径

- 官方 Steam API（无需 key）：`https://store.steampowered.com/api/appdetails?appids=2379780&l=english&cc=us`
  → `platforms` / `supported_languages` / `pc_requirements` / `release_date` 全在里面，可确认"官方是否已支持中文"。
- Balatro Wiki 的 MediaWiki API 用**根路径** `https://balatrowiki.org/api.php?...`（注意 `/w/api.php` 会被当成页面名，报 "No such action"）：
  - 正文纯文本：`action=query&prop=extracts&explaintext&titles=Balatro&format=json`
  - 全文检索：`action=query&list=search&srsearch=...&srlimit=15&format=json`
  - 注意 `insource:"Chinese" prefix:Updates` 这类组合在本站返回 0 命中，检索策略要换。
- SteamDB（`steamdb.info/app/2379780/depots/`）被 Cloudflare 拦截，且页面明确声明 **"SteamDB does not have an API... refuse any further requests"** →
  取 depot 文件结构应改用官方 Steam API 或第三方 mod 文档反推，不要再反复请求该站。
- 判断"某游戏是不是脚本引擎做的"的最快路径：看它的 mod 生态用不用 Lua/脚本注入（Balatro → Lovely/Steamodded/Thunderstore 全是 Lua），
  再去 wiki 的 Trivia 段找引擎原话。

## 6. 重要资源清单

- UP 主页：https://space.bilibili.com/609004093 （uid 609004093，4.6万粉，自述"自制视频总播放数≥100万"）
- 开源工具：https://github.com/blake502/balatro-mobile-maker （C#，1771 star / 105 fork，最后提交 2024-11-10）
  - 关键源码：`balatro-mobile-maker/Patching.cs`（补丁定义）、`Constants.cs`（工具链 URL）
- LÖVE 安卓运行时：https://github.com/love2d/love-android （11.5a，`love-11.5-android-embed.apk`）
- 补丁包：https://github.com/blake502/balatro-apk-maker/releases/tag/Additional-Tools-1.0
- 已删首版视频：BV1yu4m1371p（2024-03-05）
- 关键专栏：`cv33243782`（2024-03-16 停更声明）、`cv32074066`（2024-02-27 Yuzu 中文 mod）

## 7. 结论对当前项目的可迁移价值

本仓库的续作若选用 Lua/LÖVE 或同类"脚本层可改"的技术栈，**移植/重制的主要工作量在 Lua 层而非引擎层**：
UI 文本、牌面数值、判定规则、模式系统都可以在解包后的脚本目录里直接改，重新打包即可产出新版本，
无需逆向原生指令或重写引擎。此结论是方法论参考，未对本仓库现有 ROM 逆向结论产生任何影响。

> **相关笔记**：`notes/static-recompilation-native-port-20261020.md` —— 主机游戏"原生移植到 PC"的三条技术路线
> （静态重编译 / 反编译 / 模拟器+预重编译），含 GBA 侧 `mstan/gbarecomp` 框架，
> 与本仓库的 ROM 逆向成果（符号导入、地址表）直接互补。
>
> **本项目实测**：`notes/gba-static-recomp-feasibility-20261020.md` —— 在本 ROM 上实跑 gbarecomp 静态重编译，
> 实测 ROM→原生 x86-64 静态库 **21 秒**完成，并给出到"可发布可玩"的用时估算。


