# 这类项目在 AI 上花了多少钱：可核实数据 + 推算（2026-10-20）

上游笔记：`notes/native-port-case-studies-20261020.md`、`notes/static-recompilation-native-port-20261020.md`

## 0. 结论先行

1. **没有任何一个项目公开披露过自己的 AI 账单。** 我在四个仓库的 issue 里搜 `cost` / `tokens` / `spent` / `budget` / `credits` / `API key`，
   命中的全是"运行时开销""GPU 显存预算"，**没有一条是钱**。所以下面的金额都是**推算**，不是披露。
2. **量级：四个项目加起来，直接掏腰包的 AI 花费大概在 $2,000 – $6,000**，折合**每项目每月几百美元**。
   如果申请到了开源补贴计划（Claude for Open Source / Codex for Open Source），
   **实际自付可以接近 $0**。
3. **token 根本不是瓶颈。** 真正的成本在**人类验证时间**和**上下文读取**上。
   MacNativeGames 从建仓到能玩，**只用了 3 天**（2026-10-17 → 10-20），对应订阅成本约 **$20**，
   而同等工作量的传统人工实现是"数月级资深系统程序员"。

---

## 1. 可核实的一手数据

### 1.1 AI 产出的规模（GitHub API 实测，2026-10-20 快照）

| 仓库 | 建仓 | 累计 PR | ★ | AI 标记 |
|---|---|---|---|---|
| `peiikai/LASRecomp` | 2026-10-08 | **158** | 1397 | 几乎每个 PR 结尾 `🤖 Generated with [Claude Code](https://claude.com/claude-code)` |
| `mstan/gbarecomp` | 2026-05-25 | **60**（框架）+ 13 个游戏子仓库 | 59 | 同样带 Claude Code 标记 |
| `ly05010419/MacNativeGames` | 2026-10-17 | **54** | **2283** | Claude Code；且 `docs/how-it-works.md` 明写 *"the original port (`d309e62`, **by Codex**)"* → Claude Code + Codex 混用 |
| `999sian/melee-pc` | 2026-09-14 | **25**（含外部贡献者的 AI PR） | 510 | Claude Code；外部贡献者 `stephenjayakar` 的 PR 直接写 *"Haven't read any of the changes"* |

**关键观察**：AI 不只写代码，还写**验证方案和测试报告**。例如：
- `gbarecomp` PR #63：*"46/46 configured Release CTest checks pass … All 121 real ROM PCs harvested across Sonic Advance 1/2/3 USA … 349,050 accepted PC/mode keys"*
- `melee-pc` PR #106：*"the same seeded 4-CPU stock match recorded as `.slp` … The pre-frame and post-frame records are identical (0 of 12,016 differ)"*
- `MacNativeGames`：*"55,018 rewrite-site checks and 600 negative controls"*、*"292 mismatches before, none after"*

### 1.2 单价基准（第三方实测账单，2026 年 6 月）

来源：hqwc.cn《2026年AI编程工具真实成本大起底》。作者贴了自己的真实账单：

```
Claude Code 月度 API 调用统计（6 月）
  Total tokens: 8,234,567   (Input 7,891,234 / Output 343,333)
  Total cost:   $137.42
  ├─ Claude Opus 4.7: $98.50  (12 sessions, avg 35K tokens/session → 每次约 $8.20)
  └─ Claude Sonnet 4.6: $38.92 (47 sessions, avg 5K tokens/session)
```
对照：同期 DeepSeek-TUI 同样任务量 $3.87（约 Claude Code 的 **1/35**）。

单价表（该文整理）：

| 工具 | 单次代码生成 | 月均（活跃使用） | 年成本 |
|---|---|---|---|
| Claude Code (Opus) | ~$0.80–2.00 | $100–200 | $1,200–2,400 |
| Claude Code (Sonnet) | ~$0.05–0.50 | $30–60 | $360–720 |
| Codex (OpenAI) | ~$0.30–1.50 | $50–120 | $600–1,440 |

该文最有用的一句结论：
> "Claude Code 的贵不是因为它「贵」，而是因为它「太能干了」。你会不自觉地让它处理越来越复杂的任务，然后账单就上去了。"
> 且若只用 Sonnet 做日常编码，一个月 $40–50。

### 1.3 Anthropic 现行单价（2026-10-12 数据，Opus 5.5）

- **$4 / 1M 输入 token**，1M 上下文
- 读一个 40 万 token 的代码库：**不靠缓存 $1.60**；首次加载按 $5/1M 写缓存，**合计约 $2.00**；之后**缓存读 $0.20 / 1M**
- → **缓存读取比裸读便宜 20 倍**。这是这类项目唯一重要的成本杠杆。

### 1.4 官方补贴计划（可核实条款）

**Anthropic「Claude for Open Source」**（claude.com 官方条款）：
- 免费提供 **Claude Max 20x 订阅 6 个月**（Max 20x = $200/月 → **面值 $1,200**）
- 名额上限 **10,000 人**；**基准订阅期内不收费，但超额（overage）按标准价计费**
- 资格（满足其一即可，Anthropic 自由裁量）：
  1. 维护一个被广泛使用的开源项目；
  2. 申请前 12 个月内，向**自己不具备所有权的**公共仓库合入 **100+ 个 PR**；
  3. 自己维护的仓库在 12 个月内有 **20+ 位不同的外部贡献者**合入 PR；
  4. 仓库 **OpenSSF criticality ≥ 0.4**
- 需提交 ≤500 词说明；决定终局、不可申诉

**OpenAI「Codex for Open Source」**：
- **6 个月 ChatGPT Pro with Codex**（=$1,200）+ 来自 **$1,000,000 Codex Open Source Fund** 的 API 额度
- 面向被广泛使用的公共项目的核心维护者

**其他相关**：GitHub Copilot Pro 对维护者免费（原价 $10/月）；Sentry OSS（500 万错误 / 10 亿 span / 5,000 GB 日志，无期限）；
Netlify 每月 10,000 credits；CircleCI 每月 40 万 Linux credits；Vercel $3,600 credits。

### 1.5 这四个项目够不够格申领

| 项目 | ★ | 外部贡献者 | 判定 |
|---|---|---|---|
| LASRecomp | 1397 | README 列 9 位 + 作者 | **大概率符合**（"被广泛使用的开源项目"） |
| MacNativeGames | 2283 | 多位外部贡献者（PR #30/#67/#6 等） | **大概率符合** |
| melee-pc | 510 | 至少 4 位外部贡献者 | **大概率符合** |
| ZeldaWWHDRecomp | 821（org） | 多位 | **大概率符合** |
| gbarecomp | 59 | 13 个游戏仓库 + R.A.I.D. 社区 | 可能走"贡献者"或"关键基础设施"通道 |

→ **每个核心维护者约 $2,400 的补贴额度（Claude $1,200 + OpenAI $1,200）**，足以覆盖 6 个月的全职强度。

---

## 2. 推算（明确标注为估算）

### 方法 A：订阅封顶（最可能的情况）
个人开发者用 **Claude Max 20x $200/月**而不是 API 按量计费——因为 API 账单没有上限（该文的"坑 1"就是忘了设 $50 月限额，月底收到 $137 账单）。

| 项目 | 有效投入期 | 估算订阅成本 |
|---|---|---|
| LASRecomp | 12 天高强度 | ~$200 |
| MacNativeGames | 3 天 + 持续 | ~$200 |
| melee-pc | 5 周 | $300–400 |
| gbarecomp | 5 个月 + 13 个游戏仓库 | $1,000–2,000 |
| **合计** | | **$1,700 – $2,800** |

### 方法 B：API 按量计费（如果没用订阅）
以该文作者的 $137/月（8.2M token、59 sessions）为基线，按项目强度线性放大：
- LASRecomp 158 PR × 2–5 sessions/PR ≈ 400–800 sessions → **$900–1,900**
- gbarecomp 5 个月持续工作 → **$1,500–3,000**
- melee-pc + MacNativeGames → **$800–1,500**
- **合计 $3,200 – $6,400**

### 综合结论
- **不领补贴的自付：$2,000 – $6,000**（四个项目合计）
- **领了补贴的自付：$0 – $1,000**
- 折合**每项目每月 $200 – $600**，即 1–3 个 Claude Max 订阅或等量 API 用量。

---

## 3. 比 token 钱更值得注意的四件事

### 3.1 token 不是瓶颈，人类验证时间才是
每个 PR 结尾都有一段 **"Needs in-game testing"** 清单——AI 把代码和测试方案都写了，
但**游戏得有人亲自玩一遍**。这是每个项目真实的人力消耗所在。

### 3.2 上下文读取是唯一重要的成本杠杆
- LASRecomp 的运行时约 10 万行代码；BOTW 是 **196,000 个函数**
- 读 40 万 token 代码库：不缓存 $1.60 / 首次带缓存 $2.00 / 之后缓存读 $0.20 每 1M
- → 迭代式工作必须走缓存。**MacNativeGames 的 README 第一行就让"用你的 AI 助手来构建"**，
  正是因为助手 session 的缓存能跨整个构建周期复用。

### 3.3 同一类 bug 在多个项目里被反复重犯
`MacNativeGames` PR #91 修的是"顶点着色器未写的分量在 Maxwell 上读作 (0,0,0,1)，但 Ryujinx 翻译器只在下游读取时补默认值"，
并注明 *"In another native port of this game, the same fix took the marker area from 66 to 3,670 near-white pixels"*——
**同一个 bug 在 d2r-mobile 等其他移植项目里也出现过并被独立修了一次**。
每次重犯都是几次 Opus session 的返工成本。

### 3.4 AI 正在替代"人力工时"这一项
MacNativeGames：**3 天**建仓 → 3 天后已有 2283★、可玩的 TOTK 原生 Mac/iPhone 移植、
NVN-on-Metal、Ryujinx→SPIR-V→SPIRV-Cross→MSL 着色器链、.NET NativeAOT 预编译翻译器、
NCA/票据/RomFS 六级 IVFC 校验、MetalFX、21:9 超宽、iOS IPA、88 项单元测试。
同等工作量的传统人工实现是**数月级**。
对应订阅成本：**3 天 × $200/月 ÷ 30 ≈ $20**。

---

## 4. 质量风险（成本之外的隐性代价）

- `melee-pc` PR #106 的作者写：*"I managed to get high refresh rates working locally. I confirmed by stepping through frame by frame and also playing it myself on a 240hz monitor. **Haven't read any of the changes.**"*——
  **人没读代码就签字合并**，AI 顺手把验证报告也写了。
- 三个项目都自发形成了 **"negative control"（反向对照）** 测试纪律：
  MacNativeGames 的"55,018 次改写点校验 + 600 个反向对照"、
  `melee-pc` 的 `net_determinism.py` 跨平台找首个分歧帧、
  `gbarecomp` 的 "Generated C++ is evidence, not authority"（生成代码是证据不是权威，
  出错要改分析器而不是手改生成物——这条同时也是**成本控制策略**：改生成器比手改生成物便宜）。
- 这些纪律明显是**在 AI 写的代码不可全信的前提下被迫建立的**，是这类项目真正的隐性成本。

---

## 5. 复现这套推算的方法

1. `https://api.github.com/search/issues?q=repo:{owner}/{repo}+is:pr+type:pr&per_page=1` → `total_count` = PR 总数
2. 抽样若干 PR body，统计结尾的 `🤖 Generated with [Claude Code](...)` 出现比例 → AI 参与率
3. 搜 issue 里的 `cost|tokens|spent|budget|credits` → 确认**有无官方披露**（本轮：四个仓库全无）
4. 单价基准取 Anthropic 官方定价 + 第三方真实账单（本次用 hqwc.cn 的 2026-06 账单）
5. 补贴额度查官方计划条款（claude.com / openai.com 的 program 页面）

---

## 6. 结论对本仓库（GBA 火影忍者）的意义

1. **成本几乎不是门槛。** 即使不领补贴，一个 GBA 静态重编译项目
   （`mstan/gbarecomp` 已提供完整框架：`src/armv4t/` + `src/gba/` 硬件运行时）的
   AI 成本量级也就是**每月几百美元**。
2. **真正的门槛是"人得会验证"。** 本仓库已有的 `notes/runtime-verification-gates-20260710.md`、
   `tools/` 下的差分/回放测试，正是这类项目里 AI 无法替代的那部分能力——
   **本仓库的工程资产比 token 贵**。
3. **如果要走这条路**：优先领 `Claude for Open Source`（$1,200），
   固定用**同一款模型 + 开启缓存**（40 万 token 代码库：裸读 $1.60 / 缓存读 $0.20 每 1M），
   并把 `gbarecomp` 的 "negative control" 纪律和 "生成代码是证据不是权威" 原则写进流程。
