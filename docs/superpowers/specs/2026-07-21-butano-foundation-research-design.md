# Butano 部署与木叶战记基础系统成本预研设计

日期：2026-07-21

## 1. 目标

在不干扰当前 ROM 逆向与补丁流水线的前提下，建立一个可复现的 Butano 开发基线，并形成《木叶战记》全部基础系统在 Butano 中按“功能等价”重建的成本预研。

本轮交付包含：

- 创建 `codex/butano-foundation-research` Git 分支；
- 将 Butano 21.7.1 固定到完整提交 `112a1827c9c6d9e6041a7e93e66f04c4561a6415`；
- 在本地保存该版本的源码、示例、许可证和生成后的 HTML 文档；
- 建立一个可构建的 Butano 最小 ROM，用于证明工具链、链接、资源转换和运行循环可用；
- 输出基础系统清单、证据成熟度、复用边界、成本区间、风险和推荐里程碑。

本轮不实现《木叶战记》的战斗、AI、地图、剧情等正式系统，也不迁移完整内容。

## 2. 成本口径

“功能等价”表示保留原作的玩法规则、章节流程、数值含义、玩家操作路径和可感知反馈，但不要求：

- 像素级 UI 一致；
- 动画逐帧一致；
- 音频波形或混音器实现一致；
- 原 ROM 内存布局、函数地址或二进制格式一致；
- 与原版存档兼容。

成本以一名熟悉现代 C++、GBA 硬件和 Butano 的工程师所需“工程师人周”为基本单位。每项给出乐观、最可能、悲观区间，并显式列出逆向证据不足导致的风险储备。内容制作、完整美术重制、剧本文案和批量关卡生产单列，不混入基础系统成本。

## 3. 选型

采用“固定 submodule + 固定 Docker 工具链”的方案：

- `third_party/butano/` 是 Butano 官方仓库的 Git submodule，固定到 21.7.1 的完整提交；
- submodule 工作树包含源码、第三方依赖、示例、游戏源码、许可证和 `docs/` HTML，因此源码和文档均可本地查阅；
- devkitARM 使用 devkitPro 官方 Docker 镜像，部署时解析并记录镜像 digest，构建脚本只接受该 digest；
- 仓库记录 Butano tag、commit、许可证、工具链版本、镜像 digest、文件入口和验证哈希；
- 不在宿主机全局安装 devkitARM，避免不可见的系统依赖和版本漂移。

不把整个 Butano 快照直接复制进主仓库，因为 submodule 已能固定完整来源，而直接 vendor 会让主仓库增加约 120 MiB，并提高升级、diff 和许可证审计成本。也不采用仓库外的松散 clone，因为它无法给协作者提供可追踪版本。

## 4. 仓库结构

```text
third_party/
  butano/                         # 固定版本 submodule，含源码和 docs/index.html
butano-sequel/
  Makefile                        # 指向 ../third_party/butano/butano
  include/
  src/
  graphics/
  audio/
tools/butano/
  build.sh                        # 统一 Docker 构建入口
  verify_setup.py                 # 版本、路径、文档和工具链完整性检查
  toolchain.lock                  # 镜像 digest 与版本证据
tests/
  test_butano_setup.py            # 部署与 wiring 单元/集成检查
docs/
  butano-local-reference.md       # 本地源码、文档和构建入口
  butano-konoha-systems-cost.md   # 基础系统成本预研
```

最小 ROM 只包含 Butano 初始化、主循环、按键输入和一段可见文本。它是部署验收物，不是正式游戏架构的先行实现。

## 5. 现有能力复用

### 5.1 能否直接复用

可以直接复用：

- `sequel/content/` 中已审计的角色、地图、技能、章节和文本内容；
- 现有提取器、编解码器、运行时证据和 checkpoint；
- 角色定义、positions、成长、skills、地图、章节、save descriptor 和音频提取结果；
- 现有测试中的字段语义、地址身份和行为断言，作为新引擎的黑盒验收依据。

不能直接复用原 ROM 的 Thumb 运行时代码、WRAM 结构、PC 地址或补丁生成器作为 Butano 运行时实现。

### 5.2 公共能力边界

原 ROM patch 管线和 Butano 新引擎共享“内容模型与行为规格”，不共享“构建产物与运行时代码”。后续应增加从现有内容 JSON 到 Butano C++/二进制资产的转换层，而不是另建一套角色、地图、技能和章节数据源。

### 5.3 追加还是独立维护

Butano 工程作为现有续作链路的新构建目标追加：

```text
sequel/content + 已验证提取结果
        ├── 现有 ROM patch 构建
        └── Butano 资产转换与新 ROM 构建
```

两条构建链独立维护的技术原因是：前者修改既有 ROM，后者从 C++ 源码重新链接 ROM。用户体验原因是：现有 ROM patch 仍可用于低风险内容验证，而 Butano 路线承担超出原 ROM 扩展边界的新系统。

## 6. 预研系统边界

成本报告覆盖以下基础系统：

1. 核心循环、场景栈、输入上下文与转场；
2. 标题、Continue、木叶世界地图、任务菜单、编队和部署；
3. 章节/剧情脚本解释器、对白和事件；
4. 地图、metatile、碰撞、占位、移动范围与寻路；
5. 角色定义、队伍、模板和战斗实例；
6. 战棋回合、行动状态机、朝向、防御和行动提交；
7. 伤害、命中、查克拉、技能、效果、联携和召唤单位；
8. AI 策略、任务目标、胜利与失败谓词；
9. 经验、成长、训练、奖励和解锁；
10. SRAM 存档、版本、校验、槽位和恢复；
11. UI、字体、文本、图形资源、动画和演出；
12. 音乐、音效及离线资产转换；
13. 内容转换、调试、性能预算和自动化验收。

报告将把当前 13 个 `runtime_verified`、10 个 `code_verified` 和 9 个 `disproved` bank 的证据等级纳入风险系数。旧文档中的“32/32 调查闭合”不解释为“所有行为已规格化”。

## 7. Butano 能力边界

Butano 直接提供 GBA 图形、Sprite、BG、调色板、文本、输入、音频、SRAM、定点数学、资源管理、日志和 profiler。项目仍需自行实现：

- scene/state stack；
- 菜单和 UI widget/focus；
- metatile 与地图逻辑层；
- 寻路、碰撞和占位规则；
- 战斗状态机、AI、任务目标和数值系统；
- 存档 schema、版本迁移、校验和事务；
- 章节脚本 VM 和内容转换层。

因此成本不能按“引擎已有绘图和输入”低估。Butano 降低的是硬件访问、资源导入和常用表现层成本，不替代战棋与 RPG 领域逻辑。

## 8. 用户可见行为与边界

部署完成后的可操作入口是 `tools/butano/build.sh`：

- 正常：生成最小 `.gba`，ROM 启动后显示部署成功文本，并对按键给出可见反馈；
- 首次构建：显示需要启动 Docker Desktop 或拉取固定镜像的明确提示；
- 加载中：Docker 构建日志显示工具链与编译进度；
- 缺少 submodule：提示准确的初始化命令，不静默联网；
- 版本错误：报告期望 tag/commit 与实际 commit；
- 文档缺失：报告 `third_party/butano/docs/index.html` 缺失；
- 工具链错误：报告镜像 digest 或 devkitARM 工具缺失；
- 构建错误：保留编译器原始诊断并以非零状态退出。

本轮没有游戏菜单、地图或战斗入口；最小 ROM 只证明 Butano 已正确部署。

## 9. TDD 与验证

严格执行红绿重构：

1. 先添加 `tests/test_butano_setup.py`，断言固定版本、submodule、离线文档、项目 wiring、锁文件和构建入口；确认测试因部署尚不存在而失败。
2. 添加最小 submodule、项目和工具，使完整性测试通过。
3. 清理命名和重复配置，再次运行测试。

集成验证包括：

- Butano 官方 `examples/sprites` 构建；
- Butano 官方 Maxmod/audio 示例或等价官方音频示例构建；
- `butano-sequel` 最小 ROM 构建；
- 生成 ROM 的 SHA-256 与工具链版本清单；
- 用现有 mGBA 只做最小启动/画面验收时，必须通过 `tools/run_guarded.py` 的 heavy lock；若无需运行模拟器，不能把“编译成功”描述成“运行成功”。

任何无法执行的验证都在报告中明确标记，不以推测替代结果。

## 10. Git 与现有改动保护

- 分支从当前 HEAD 创建，名称为 `codex/butano-foundation-research`；
- 当前 `AGENTS.md`、`docs/sequel-roadmap.md` 和大量 build/artifact 文件视为用户改动；
- 本任务不回滚、不清理、不自动暂存这些文件；
- 本任务只修改本设计列出的新路径、必要的 `.gitmodules`，并在完成时以追加方式更新 `docs/sequel-roadmap.md`；若无法与用户现有改动安全区分，则不修改该文件并在报告中说明；
- 未获得明确授权前不 commit、不 push。

## 11. 完成条件

- 新分支存在且当前工作树位于该分支；
- Butano submodule 指向固定的 21.7.1 commit；
- 本地源码、许可证和 HTML 文档可以直接打开；
- 部署完整性测试通过；
- 至少完成最小 ROM 的可复现构建；
- 若 Docker 与资源条件允许，官方图形和音频示例构建通过；
- 成本报告覆盖全部基础系统、复用资产、用户体验、风险、估算假设和里程碑；
- `docs/sequel-roadmap.md` 仅在不覆盖用户改动的前提下追加 Butano 预研状态，否则在完成报告中说明未更新原因；
- 最终报告按仓库规定列出功能特性、BUG 修复和可执行验收清单。

## 12. 主要风险

- AI、目标谓词、技能效果链和部分成长规则尚未完全规格化，成本区间必须保留较大风险储备；
- GBA 的 VRAM、OAM、IWRAM/EWRAM 和每扫描线 Sprite 限制可能迫使 UI 与地图表现调整；
- Butano 不支持通用 metatile、寻路、scene stack、UI 框架和可靠存档层，这些均是项目代码；
- Docker 镜像 tag 不是可复现标识，部署时必须解析并锁定 digest；
- 原作内容可能包含第三方版权素材；本轮只做本地技术参考与迁移成本评估，不重新分发原作资产。
