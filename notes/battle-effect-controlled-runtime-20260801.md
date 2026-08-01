# 战斗特效未观察组受控运行时证据（2026-08-01）

## 结论

从已验收的 `scenario-50-battle-15-escort-12hp-player-turn.ss9` 恢复，在零输入条件下
分别注入 13 个此前未观察的 effect sequence。13/13 均执行一次受控 binder，并捕获
`binder-return → renderer-post → submit-post → ack-post` 四个边界；但只有 10 组形成
完整目标资源、task 与 OAM 提交事务：

`[4, 6, 7, 8, 9, 10, 12, 13, 16, 17]`

groups `[3, 15, 18]` 在四个边界都没有目标 definition/animation 指针对应的活动 task，
OBJ VRAM 也没有完整目标 graphics，OBJ palette banks 没有完整目标 palette，因此作为
明确负结果保留，不能降级为“分段加载成功”。

## 可复算证据

正式成果位于 `artifacts/battle-effect-controlled-runtime-v1/`，只含：

- `evidence.json`：13 个 case 的输入、ROM、catalog、guard、阶段、task/OAM 绑定和
  正负 verdict；
- `raw-batch.tar`：确定性 USTAR，精确包含 729 个成员：batch audit、13 份 profile、
  audit、guard、完成标记，以及 `13 × 4 × 13` 份审计声明输出；
- `manifest.json`：promotion、文件和实现哈希，以及独立 verifier 命令。

`tools/verify_battle_effect_controlled_runtime.py` 不导入导出器。它从完整原始批次
独立重建并强制检查：

1. Thumb breakpoint 的 `saved r15 - 2`、scratch `0→1`、pending `0,0,1,0` 与
   cycle 严格递增；phase 的 `frame` 是运行审计字段，不把 `0x0300067D` 伪装成通用
   frame counter。
2. 从 18-group animation catalog 重建 task `+0x1C/+0x20` 身份，并逐项复算
   dispatcher 的计数、顺序、slot 与 pointer；正例在 renderer/submit/ack 均为稳定
   slot 108，binder-return 尚无目标 task。
3. 从 task `+0x10` 的 tile base 和 `+0x12` 的 palette bank 计算 OBJ VRAM/PRAM
   地址，逐字节匹配静态资源 pair；不把 task `+0x24` 当作 group 身份。
4. 依据 task anchor/offset/flip、动画 frame/component 和 OAM shape/size，独立重建
   25 个可见组件的 `attr0/attr1/attr2`，绑定到具体 shadow OAM index；renderer 的
   shadow OAM 与 binder 旧值不同，ack 后相同 index 的 hardware OAM 精确等于
   renderer shadow。group 9 单独保留“输出 frame 0、post-task 已推进到 frame 1”；
   group 10 的第 6 个屏外组件不强绑到 disabled OAM。
5. 负例四阶段目标 task 均缺席，且没有完整目标 graphics/palette；任何部分状态或
   身份不一致会变为 `invalid_inconclusive`，不能计正也不能计负。

## 指标边界

- 受控 binder 边界：`13/13`；
- 受控目标资源/task/OAM 事务：`10/13`；
- 与既有已观察 groups `[1,2,5,11,14]`（包含 supplemental 快照）取并集：`15/18`。
  这是补充技术覆盖，不是自然玩法覆盖；
- production 修改 ROM 最终像素 A/B 仍为 `4/18`；
- 自然/既有快照 frame-phase 覆盖仍为 `5/18`；
- tracked parent checkpoint 分母仍为 `93`；
- group 18 的 sequence 18 路径尚未覆盖。sequence 7 受控失败不能证明 group 18
  的所有入口失败或完成。

本成果不证明自然动作入口、排他 task→OAM writer、全帧动画、RNG、affine、
blend/window/audio 或实体 GBA 输出。

verifier 内置已验收 spec、ROM、输入快照和三份父 catalog 的固定 SHA-256，并锁定
导出/验证脚本、间接 probe/runner/guard 依赖与父 verifier。这样不能靠同时替换 catalog
并重签 manifest 绕过验证；但 verifier 源本身仍以本仓库 review/commit 为信任根。

## 资源安全

13 次运行都由 guard 以 `completed/0`、`success-marker`、非 degraded 结束，并且
PGID 与 mGBA listener 无残留。9 次 RSS 采样约为 `71.46–73.82 MiB`；另 4 次短任务
只记录到 `0.168–0.176 MiB`，明显是采样遗漏。artifact 保留逐案原值并显式标记
`valid_for_batch_statistics=false`，不据此报告批次峰值、平均值或上界。

## 下一入口

- group 3 / sequence 3 与 group 18 / sequences 7、18 的自然 callsite 在 selector 后
  还调用对象 spawner，下一探针必须复现 selector+spawn 参数，不能只调用通用 binder。
- group 15 / sequence 17 需要补 action/side/runtime context；在静态或自然证据确定
  上游状态前，不猜测 side 参数或把当前负结果改写为资源缺失。
