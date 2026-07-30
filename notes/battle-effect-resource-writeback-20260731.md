# 战斗特效资源安全原位回编（2026-07-31）

## 结论

`battle-effect-resource-pairs-v1` 的18个有效 group 共有36条 graphics/palette
逻辑引用。group 2/3 共用一个 graphics 指针，group 16/17 的 palette 内容相同但
保存在两个物理槽，因此完整分母为：

| 口径 | 数量 |
|---|---:|
| 特效 group | 18 |
| 逻辑引用 | 36 |
| 物理 LZ77 槽 | 35 |
| 按“类型 + 解压 SHA-256”去重的内容资源 | 34 |

`tools/import_battle_effect_resources.py` 以内容资源为编辑身份。graphics 必须保持
完整32字节4bpp tile，palette 必须保持32字节/16色 BGR555；输入同时声明原始
解压长度和全部物理偏移。导入器重新验证基准 ROM、catalog、pair table 指针、
压缩/解压哈希和资源格式，再使用共享确定性 GBA LZ77 编码器重压缩。

同一内容的全部逻辑别名和物理槽会作为一个原子计划处理：

- 修改 group 2/3 共用 graphics 时只写一个物理槽，但报告两个 group 别名；
- 默认修改 group 16/17 的同内容 palette 时同步写两个物理槽；
- 两个 palette 指针本身不同；规格可显式给出经 catalog 验证的
  `target_physical_offsets` 子集，使两组独立配色，而不能隐式拆分共享指针；
- 任一物理槽容量不足时整项拒绝，不返回部分补丁；
- 18个 pair table 的36个指针均保持不变。

`tools/build_mod.py` 已接入 `battle_effect_resource` 类型，构建报告保留资源类型、
原始/替换 SHA、编码长度、槽长度、受影响 group 和完整逻辑别名。

## 容量审计

`artifacts/battle-effect-resource-writeback-v1/` 对完整 `36 → 35 → 34` 分母进行
独立容量审计：

- 34/34份内容、35/35个物理槽均能把原始内容确定性重编码并装回；
- 固定低位变异后，31/34份内容可装回全部别名；
- 物理槽口径为32/35可装回，3/35溢出；
- 逻辑引用口径为33/36可装回，3/36进入容量失败边界；
- 三个已知溢出的 graphics 槽为 `0x3426D8`、`0x34311C`、`0x34716C`。

固定变异只是容量见证，不是“任意编辑成功率”。真实编辑仍必须逐项通过导入器的
全别名容量门禁。

## 独立验证与边界

独立 verifier 不导入 importer、artifact exporter 或共享 LZ77 实现。它从基准
ROM 和 `0x0859911C` pair table 重新建立 `36 → 35 → 34`，独立编解码全部资源，
重算容量、实现哈希和 promotion manifest，并拒绝重签后的 slot-size 语义篡改。
审计 scope 同时绑定导入器已提供显式物理槽选择；回归测试证明 group 16/17
默认同步，也能在指定不同物理指针时安全拆分。

明确未完成：

- 超槽资源迁移或 pair-table 指针改写；
- 任意内容都能装回原槽；
- 从合成动画画面自动反编译 graphics/palette；
- 修改后的 OAM、affine、blend、帧时序或音频等价；
- 全 ROM 通用图像回编。

本成果闭合的是18组战斗特效静态像素资源的安全原位回编，不扩张到表现逻辑。

## 验证记录

- TDD 红灯：首个共享 graphics 测试因
  `tools.import_battle_effect_resources` 尚不存在而失败；物理槽拆分测试随后因旧实现
  返回两个补丁而失败。
- 绿灯：`tests.test_import_battle_effect_resources` 11项通过。
- 相关回归：特效导出、特效回编、地图回编、菜单立绘回编共38项，在
  `tools/run_guarded.py` 下 `completed/0`，峰值 tree RSS `56.4609375 MiB`，
  `degraded=false`。
- 独立 verifier 返回 `34/35/36`、`errors=[]`；`tools/automated_test.py`
  为25/25。
- 本切片只做离线静态工作，没有启动 mGBA，也没有写入 Butano 工作树。
