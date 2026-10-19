# Butano 战斗单位逐帧动画实施计划

**设计：**
`docs/superpowers/specs/2026-07-25-butano-battle-unit-animation-design.md`

## 1. RED：固定复合帧与时间线

- [x] 扩充 Python 测试，要求 schema 2、9 槽语义、20/12 帧表和动画表。
- [x] 以角色 39 固定 3 component 待机帧和水平镜像复合帧。
- [x] 新增宿主 C++ 测试，固定左右槽回退、四向槽 0 序列和 duration 采样。
- [x] 运行并确认测试因旧生成器和缺失动画驱动器失败。

## 2. GREEN：生成完整 ROM 角色动画

- [x] 解码 342 个有效槽的所有帧、复合 OAM 与时间线。
- [x] 生成 534 个按 component/shape 分组的 sprite 资产、JSON 目录和 C++ 固定容量表。
- [x] 修复角色 39、40、55 的复合待机图。
- [x] 两次生成对比，证明确定性。

## 3. GREEN：接入通用战斗表现

- [x] 用最多 5 component 的单位 sprite 状态替换单 sprite 状态。
- [x] 部署与战场待机由槽 0 和真实角色身份驱动。
- [x] 移动、结印、投掷、近战和受击使用 ROM duration。
- [x] 角色缺少左向槽时显式镜像基础槽，空领域槽仍不分配资源。
- [x] 表现事件携带所有受影响单位 ID，致死目标和范围目标保持到动画结束。
- [x] scenario 41 默认入口改用共享运行时，旧整屏攻击帧退出生产 graphics。

## 4. REFACTOR 与验证

- [x] 运行生成器、宿主 C++、source wiring 和文档测试。
- [x] 经资源守卫执行 ARM 构建。
- [x] 静音 mGBA 覆盖 scenario 41 忍者组合拳、battle 09 多角色与 battle 32 动态召唤。
- [x] 保存逐帧截图/审计和资源守卫 manifest。
- [x] 更新架构、逆向记录、工具说明与路线图，运行 `git diff --check`。

最终实机证据：

- `artifacts/butano-shared-s41-runtime-20260725-84/`
- `artifacts/butano-unit-animation-b09-20260725-86/`
- `artifacts/butano-dynamic-deployment-b32-20260725-87/`
- `build/resource-guard/butano-final-unit-animation-arm-build-20260725-155.json`
