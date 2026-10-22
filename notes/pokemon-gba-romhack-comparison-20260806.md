# Pokémon GBA ROM Hack 与本项目投入差异调查（2026-08-06）

## 结论

Pokémon GBA 二次开发作品多，不是因为单个作者普遍完成了整作逆向，而是因为社区把逆向成本沉淀成了可复用的公共底座：早期通过二进制编辑器、地址表、脚本器和补丁开发；现代项目更多直接 fork 可重编译且匹配原 ROM 的反编译源码，再叠加通用扩展框架。作品作者主要投入地图、剧情、美术、数值和少量新机制，而不是从未知 ROM 重建引擎。

本项目目前同时承担四项工作：专有日文战棋 ROM 的黑盒逆向、证据化资产/数据提取、原作规则与表现重建、续作内容和工具开发。它与“基于 pokeemerald-expansion 做一部新作”不是同一工作口径。

## 两代技术路线

### 二进制 ROM Hacking

- 在固定版本 ROM 上识别表、指针、脚本、压缩图像和 Thumb hook。
- AdvanceMap、XSE 等旧工具以及后来的 HexManiacAdvance 把社区已知格式包装成地图、脚本、文本、图片和表格编辑器。
- 适合替换内容、扩表和注入局部汇编/C；复杂改动容易遇到地址冲突、重定位和不可维护问题。
- HexManiacAdvance 的公开说明明确限定并深度支持英文 Ruby/Sapphire/FireRed/LeafGreen/Emerald；“打开其他文件”只有缩减功能集。这说明工具优势来自对少数 Pokémon ROM 版本的长期专门建模，并非通用 GBA 自动逆向。

### Decomp / Source-based Hacking

- `pret/pokeemerald` 把 Emerald 还原为人类可读的 C/汇编/数据/素材工程，编译产物与原 ROM SHA-1 匹配。
- Hack 作者不直接改 ROM 字节，而是修改源码与数据后重新编译 ROM。
- `rh-hideout/pokeemerald-expansion` 再提供跨世代战斗机制、宝可梦、招式、特性、物品、测试与配置，是“Romhack Base”，并明确说明其自身不是可玩的游戏。
- 因而一部现代作品的表面开发周期不能包含 pret、Expansion、编辑器、素材贡献者此前累计的投入。

## 可核验规模（GitHub，2026-08-06 查询）

| 公共工程 | 公开起始 | 提交量 | 贡献者数 | 集中度/含义 |
|---|---:|---:|---:|---|
| `pret/pokeemerald` | 2015-10 | GitHub 页面约 8,061 | API 161（含匿名） | 前 10 人约 5,949 次提交；十年以上持续逆向与维护 |
| `rh-hideout/pokeemerald-expansion` | 2020-10 | GitHub 页面约 20,100 | API 326（含匿名） | 前 10 人约 11,495 次提交；仍有长尾数百名贡献者 |
| `Complete-Fire-Red-Upgrade` | 2019-01 仓库创建 | 2,403 | 10 | 主作者 2,059 次；README 自述投入数百乃至数千小时 |
| `HexManiacAdvance` | 2018-09 | API 贡献总数约 4,274 | 15 | 主作者约 4,178 次；一个专用编辑器本身已持续约 7.5 年 |
| 本仓库已提交历史 | 2026-03-28 | 621 | 4 个 author identity | 截至 2026-07-29；主身份 449 次，历史跨度约 4 个月 |

注意：提交数不是工时；贡献者也不是全职员工。它们只能证明生态跨度、参与面和复用底座的数量级差异。

## 人力成本估算

### 公共底座

公开资料没有可信工时账本，不能把 326 名贡献者乘以六年。可采用保守的数量级估算：

- `pokeemerald`：十年以上、核心贡献集中于约十人、另有百余长尾贡献者。即使只按核心成员平均每年 200–500 业余小时、长尾每人 10–50 小时，累计也约 **2.2万–5.8万小时（约 11–29 个 2,000 小时人年）**。
- `pokeemerald-expansion`：近六年、约十名高频核心和数百长尾；同一保守法约 **1.5万–4.5万小时（约 8–23 人年）**。
- 编辑器、CFRU、素材库、教程、测试和 Discord 支持尚未包含。将 Pokémon GBA 可复用生态合计写成 **至少数十人年** 比写成“某个 Hack 一个人做了一年”更接近真实成本。

这些是基于公开年限和贡献分布的规划估算，不是审计事实；上下界对志愿者活跃强度非常敏感。

### 单个成品 Hack

- 轻量 QoL/难度/换皮项目：在现成底座上可为数十到数百小时。
- 原地区、完整剧情、较多新美术的作品：常见为主创 **1–3 年业余时间，约 1,000–4,000 小时**，另有美术、音乐、测试和资料贡献。
- 大型作品或自建引擎扩展：可达 **4–8+ 年、3,000–10,000+ 小时**。公开例子中 Pokémon Prism 被报道开发八年；CrystalDust 作者回顾了十年项目周期；CFRU 主作者直接称投入数百乃至数千小时。
- 2025 年 Pokémon Lazarus 的报道给出“接近一年”完成 1.0，但作者此前已做过 Emerald Seaglass，且作品消费 pokeemerald/Expansion 和社区素材。它能说明成熟底座上的高产速度，不能说明一年完成了 Emerald 的逆向。

## 与 gba-naruto 的直接对照

本仓库的路线不是简单 ROM Hack，而是先调查一个没有公共 decomp、没有专用地图/脚本/战斗编辑器、没有数百贡献者生态的游戏，再尝试用 Butano 重建。仓库现有证据显示：

- 已定位和导出大量地图、角色视觉、背景、音频、战斗配置、角色/动作/成长数据；这相当于 Pokémon 社区早已替作品作者承担的底座工作。
- 已有可运行的 scenario 41 纵切片和多个通用战斗域能力，但路线图明确记录过一次“截图/固定选项伪战斗”被验收否决，之后才重写真实规则链。
- 47 场内容目录和若干场景运行链已有进展，但章节脚本、全技能专属表现、剩余规则消费者、动态队伍/部署、全场景验收仍不完整。
- 项目还要求逐地址证据、运行时 A/B、可恢复快照、单元/集成测试、GBA 资源预算和原作画面/音频对照；严格度高于多数发布 ROM Hack 的工程门槛。

因此“进行了很久仍做不到”的核心原因是：

1. 实际日历只有约四个月的已提交历史，而对标公共底座是 6–11 年。
2. 本项目贡献规模接近单一主作者工程，却同时承担逆向团队、引擎团队、内容团队和 QA 团队职责。
3. 目标从“可修改 ROM”扩张到了“功能等价重建 + 续作生产平台”；两者成本可能相差一个数量级。
4. 原作是战棋/剧情驱动的专有引擎，关卡条件、单位状态、动作反应和演出高度耦合；Pokémon 的回合战斗与地图/脚本格式则已被社区标准化。
5. 已发生的返工不是纯粹没有产出：它暴露并纠正了把黄金截图路线误当通用系统、把静态表猜测误当运行时语义等问题；但也说明目标和验收边界过去不够早地锁定。

## 建议的可交付路线

- 若目标是尽快出现“火影 ROM Hack”：停止追求全游戏反编译和一比一重建，选择一个已证明的原 ROM 配置链，做一关/一章的 lossless patch 垂直切片。边界是只改已知表与脚本，不新增通用引擎机制。
- 若目标是独立续作：承认这是新游戏开发，继续 Butano，但冻结在一个可玩的 3–5 关 MVP；只复用已证实的原作数据和资产，不把剩余原作 100% 逆向作为前置条件。
- 若目标是形成类似 Pokémon 的生态：优先交付可复编译/可扩展的源码底座、稳定内容 schema、编辑器和示例，而不是先承诺完整续作。该目标仍需要多年持续维护和更多贡献者。

## 来源

- pret/pokeemerald: https://github.com/pret/pokeemerald
- pokeemerald-expansion: https://github.com/rh-hideout/pokeemerald-expansion
- HexManiacAdvance: https://github.com/haven1433/HexManiacAdvance
- Complete Fire Red Upgrade: https://github.com/Skeli789/Complete-Fire-Red-Upgrade
- Decomp 资源说明: https://github-wiki-see.page/m/Bivurnum/decomps-resources/wiki/Introduction
- CrystalDust 十年回顾: https://domoreaweso.me/blog/the-end-of-an-era
- Pokémon Prism 八年开发报道汇总: https://en.wikipedia.org/wiki/Pok%C3%A9mon_Prism
- Pokémon Lazarus 1.0 开发周期报道: https://www.gamesradar.com/games/pokemon/hyped-pokemon-rom-hack-gets-its-1-0-release-next-week-with-a-greek-region-400-cross-gen-monsters-mega-evolutions-mini-games-side-quests-and-more/

GitHub 数字通过公开 API 与仓库页面交叉查询。人力小时是明确标注的区间估算，不应当作作者自报或精确财务成本。
