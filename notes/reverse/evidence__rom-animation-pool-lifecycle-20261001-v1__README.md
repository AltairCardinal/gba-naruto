# 动画池生命周期局部审计收据

此目录保存固定分母研究、全部中间与失败结果、TDD 红绿日志和最终复验。
它不是 accepted ROM artifact。promotion=0；全生命周期、callback effects、外部对象
writer、自然执行与可编辑性仍开放。结论说明见 ../../rom-animation-pool-lifecycle-20261001.md。

## 读取顺序

1. `audit-final.json`：113 raw BL 形态、来源分区、47 条局部双表调用及所有排除原因。
2. `validation.json`：九组来源独立 verifier（四组原运行、五组恢复运行）全部通过，
   七序列的 672 组人工探针及原始 trace 示例。不是穷尽所有 runtime 状态。
3. `facts-final-v2.json`：正确 mask／caller stack 字段、group 1 和 8 个描述器候选。
4. `final-checks.json`、`portable-report.json`：19 项测试、原报告复验和 notes 路径复验。
5. `manifest.json`：每个永久成员的大小／SHA；source ROM 不复制，但其 SHA 固定。

参数采集阶段每项 `source_cfg_independently_replayed=false` 是当时状态。来源最终验真
单独保存在 `validation.json`；没有把参数局部确定升级为完整 caller 域。
`audit.json`／`audit2.json` 是中间报告，不能代替最终分母；`facts-final.json` 的初始
flags 标签由 `facts-final-v2.json` 区分为 caller 0x388 与对象 0x389，历史文件不覆盖。
首次静默超时与测试 fixture／字段地址断言失败全部保留，不当作游戏或 CFG bug。

## 从永久代码重放

在逆向仓库根目录工作，先初始化一个新的唯一 run，例如把下面的 `reader-...` 换成
未使用的 ID。不要写入本收据或已完成 run。

```sh
python3 tools/experiment_workspace.py --root . init --task animation-pool-lifecycle-replay --run-id reader-20261001-v2
python3 tools/run_guarded.py --lock-file build/experiments/heavy.lock --summary build/experiments/active/animation-pool-lifecycle-replay/reader-20261001-v2/replay-guard.json --wall-timeout-s 120 --max-tree-rss-mib 700 -- python3 notes/evidence/rom-animation-pool-lifecycle-20261001-v1/replay_receipt.py build/experiments/active/animation-pool-lifecycle-replay/reader-20261001-v2/result build/experiments/active/animation-pool-lifecycle-replay/reader-20261001-v2/replay.log
python3 tools/experiment_workspace.py --root . complete --task animation-pool-lifecycle-replay --run-id reader-20261001-v2
```

预期 `result/report.json` 显示 19 测试、参数语义和字段事实一致、672 trace SHA 一致。
重放重新检查实际 source artifact／manifest／verifier 身份与 raw 指令分区，但不再
调用九组完整 source CFG verifier；其实际独立重放报告已保存在本收据。需要完整再验
时，逐个调用 SOURCES 中列出的既有 verifier，并继续使用共享资源守卫。

代码全部从本目录加载，不使用原 build run 作为输入。脚本自身的定位路径可以变化，
其 SHA 必须相同，其他 input 与参数报告逐项相等；输入漂移或 unsupported opcode
失败关闭。此适配只用于调查重放，不签发 bank 或 canonical 分类。
