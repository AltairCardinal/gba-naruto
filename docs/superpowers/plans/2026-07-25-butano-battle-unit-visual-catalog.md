# Butano 战斗单位视觉目录实施计划

**设计：**
`docs/superpowers/specs/2026-07-25-butano-battle-unit-visual-catalog-design.md`

## 1. 以测试固定 ROM 视觉表

- [x] 新增生成器测试，要求 62×9=558 行、342 个有效槽和 62 个有效槽 0。
- [x] 固定代表角色的帧尺寸、中心偏移和像素 SHA-256。
- [x] 运行测试并保存因生成器不存在而失败的 RED 证据。

## 2. 生成可维护的角色待机资源

- [x] 抽取 scenario 41 与新生成器共用的 4bpp BMP writer。
- [x] 实现 ROM 哈希、指针边界、帧尺寸、tile 范围和 palette 校验。
- [x] 生成 62 个 BMP/JSON、可审计 JSON 目录和 C++ 资源目录。
- [x] 两次生成对比，证明结果确定。

## 3. 接入同一通用部署/战斗渲染链

- [x] 先写 source wiring RED 测试。
- [x] 部署按 `battle_deployment_entry.character_id` 创建 sprite。
- [x] 战斗按 `battle_scene_unit_view.character_id` 创建 sprite。
- [x] 身份变化时按 `character_id` 热切换 sprite item 与 ROM 锚点。
- [x] 删除通用场景对鸣人/通用敌人替代资源的依赖。

## 4. 验证并持久化结论

- [x] 运行生成器单测、source wiring、相关宿主 C++ 集成测试。
- [x] 经资源守卫执行 ARM 构建和 mGBA 路线。
- [x] 人工检查 battle 32 的四种角色视觉和固定路线截图。
- [x] 更新逆向记录、架构设计、路线图和工具说明。
- [x] `git diff --check`，记录不能运行或仍未完成的边界。

## 验证证据

- Python 相关回归：`build/test-results/butano-unit-visual-python-focused-final-20260725-108.log`，
  121 项通过、1 项按既有条件跳过；资源守卫摘要
  `build/resource-guard/butano-unit-visual-python-focused-final-20260725-108.json`。
- 宿主 C++：`build/resource-guard/butano-unit-visual-host-all-20260725-106.json`，
  65 个测试程序全部通过。
- ARM 构建：`build/resource-guard/butano-unit-visual-arm-build-final-20260725-99.json`；
  ROM SHA-256 为
  `97677fab0c5afc860286db3db95a469917e82a7b5c03d1626eed5b388435a899`。
- battle 32 动态部署：
  `artifacts/butano-unit-visual-b32-final-20260725-66/`，逐个部署截图确认鸣人、
  佐助、小樱和角色 35 使用不同 ROM 角色资源；最终审计进入第 2 回合且错误数为 0。
- 固定路线回归：scenario 43、battle 09、battle 11、scenario 41 分别保存在
  `artifacts/butano-unit-visual-regression-s43-20260725-67/`、
  `artifacts/butano-unit-visual-regression-b09-20260725-68/`、
  `artifacts/butano-unit-visual-regression-b11-20260725-69/`、
  `artifacts/butano-unit-visual-regression-s41-20260725-70/`。
- 自动化 mGBA 路线均静音执行，因此这里只证明视觉、状态机和资源稳定性，
  不把它当作主观音质验收。

## 仍未完成的边界

本里程碑只恢复了每名角色槽 0 的静态待机帧和身份切换。其余 8 个视觉槽的语义、
帧序列、持续时间、朝向和战斗阶段驱动仍需继续逆向与接入；在这些工作完成前，
不得把当前视觉层描述为完整角色动画系统。
