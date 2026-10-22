# Battle-effect：容量证据恢复与完整固定变异写回矩阵

## 可用结果和入口

全部 34 个 content resource、35 个 physical slot、36 个 logical reference 已贯通
独立提取/codec、既有 importer、真实 build CLI 和输出重读。一次全资源 no-op 构建与
原始 6MiB ROM 逐字节相同；随后 34 个独立变异构建，23 个资源接受并写入 24 slots /
24 references，11 个因容量不足拒绝，拒绝项既不发布 ROM，也不发布构建报告。

固定变异为 graphics byte0 / palette byte2 的 low-bit toggle；不是任意编辑容量完成。
每个成功输出都与独立编码重建的完整 ROM 逐字节一致，所有物理/逻辑 alias 都重读为
目标内容，0x59911C..0x5991B4 的 19×8 指针表保持原样，槽外字节不变。
没有编辑器 DB、重定位、自然游戏帧或实体硬件验证；graphics 全局 release case 仍未完成。

在逆向工作树先初始化一个新的 run，再执行：

```sh
python3 tools/experiment_workspace.py init --task battle-effect-roundtrip --run-id manual-01
python3 tools/run_guarded.py \
  --summary build/experiments/active/battle-effect-roundtrip/manual-01/guard.json \
  --lock-file build/experiments/heavy.lock --max-tree-rss-mib 768 --wall-timeout-s 180 -- \
  python3 tools/audit_battle_effect_fixed_roundtrip.py --root . \
  --run build/experiments/active/battle-effect-roundtrip/manual-01
```

成功输出 verified=true JSON，并在 run/roundtrip/result.json 保存同样结果；fixture/cases
内可查看独立 project/spec、改动二进制、构建日志、成功 ROM/report 和 readback.json。
等待工具同步结束即可。缺输入/身份漂移、非 active 或不受管路径、重用已有 roundtrip
目录、非预期构建失败或错误字节/别名都会 exit1，给出 verified=false/errors，失败产物
保留。11 个预期容量拒绝属于成功矩阵的一部分，不能解释为工具失败或编辑成功。
这是开发者入口，游戏 UI 和编辑器入口没有变化。

## 容量证据恢复、输入与复用

旧 artifacts/battle-effect-resource-writeback-v1 原样保留，当前 verifier 仍正确拒绝它的
implementation mismatch。仅 tests/test_import_battle_effect_resources.py 的身份漂移，
旧 SHA=1331e9586a1d46fef82931a2c1bc4c2bee63fd30d6df382b3e41698561f38293，
当前 SHA=a6e8519ff82f5b719e57bcbe0b04fd090f881aba20e1c0ad309cd131a4598583。
既有 exporter 重新生成两份新收据，独立 _expected_payload/verification 均通过，两份
文件完全相同；去掉 implementation 后，新旧 payload 完全相同，不是直接刷新旧 hash。
[恢复收据](evidence/rom-battle-effect-capacity-refresh-20261001-v1/)为 19 成员，manifest SHA=
a59c8e61dbed4c2427a924622d368b775da9808d19538c0408ce0b3c0636f6cf；5.18s、38.90MiB、非降级。

任务模式是冻结资源身份恢复及固定内容/slot/alias 写回矩阵，脚本优先，无子代理。
51 项冻结输入的合同 tools/data/battle-effect-fixed-roundtrip-contract-v1.json SHA=
d01f10b1467ff16da2e423a25d7396952284dda0d163a3367f8c41d96298ec31，绑定 ROM、catalog/
导出 bin、新 capacity 两文件、实现与安全读取工具。新工具源码另由 result/receipt 固定。

直接复用原 importer、build_mod/安全门、独立 capacity verifier 的 codec 与 alias 数据，
没有另写资源编码器或 ROM patcher。新工具只负责固定矩阵、隔离 fixture、真实 CLI
接线和独立整 ROM/alias 后置条件，追加到既有验收链。当前第一族不抽象未知的跨族
接口；后续第二族确认共性后再抽取 fixture/CLI/身份机制，保持消费者特有验真独立。

构建 fixture 仅复制六个 hash-bound 工具、ROM、catalog 和导出内容；子进程使用明确
的 Python/PYTHONPATH，DB_PATH 指向 fixture 内不存在的 DB，环境中其他 DB/output
变量不继承。没有复制脏工作树或调用真实项目 DB；也不将这个最小 fixture 说成完整
release clean-checkout 构建。每个变异从相同 immutable base 开始，不串联上一项 ROM。

## TDD、真实集成和可移植复验

6 项初始失败测试先在未实现 API stub 上运行并保存 RED；随后最小实现全部转绿。
重构材料化输入的公共步骤后，新增故障注入/环境测试，最终新 7 项 + 相关旧 15 项 =
22/22 通过。包括真实目录迁移 CLI、全34分母、容量拒绝、缺文件/symlink/身份漂移、
非 active/外部路径/重用目录，以及真实输出槽外篡改、漏报 alias、overflow 后残留 ROM
的拒绝；环境中无关 DB 和 BUILD_OUTPUT_DIR 保持不变。最终 guard 38.25s、152.92MiB，非降级。

正式 run=battle-effect-roundtrip/fixed-20261001-v1，35 个真实 build CLI，9.31s、109.90MiB，
非降级；结果 SHA=2da707c38a0fede7dc287c751964e354df2745286ba299a73dd3254a286d3432。
另外复制 51 输入/合同/新工具共 53 文件到新目录，主验证进程禁止读取源工作树；六个
hash-bound 构建工具在 fixture 内执行。再次完成35个 CLI，完整 result 精确一致。
该禁止读取钩子没有覆盖子构建进程，不宣称全进程文件访问审计或外部密码学证明。
重放 guard 9.31s、118.37MiB、非降级。没有 mGBA 采集、UI 或硬件测试。

## 持久证据、正式状态与后续

[固定矩阵收据](evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/)保存 TDD/guard、结果、
可复用重放脚本及实现/合同/测试。每个 case 的 spec/编辑内容/readback/build report/
日志保存；约 150MiB 可重建 ROM 留在受管源 run，不重复放入 notes。receipt 明确列出
省略 ROM 的文件 SHA/size，不能称包含完整原始输出。结果可以从冻结输入重建并验真。

canonical/proof/bank-proofs SHA 均不变，unknown=87,631B，正式 bank typed=0；175 blockers
仍是历史 formal。fixed_mutation_matrix_complete 只针对本族固定变异，full_graphics_release_gate_complete=false；
没有把 34 资源矩阵提升为全部 graphics、其他六个资源 case、任意修改或整体逆向完成。
未 commit/push，未修改 Butano 工作树。

下一里程碑以 map resource 的 166 content / 217 slots / 249 references 为第二族，
先检查 mutation 合法域与 importer/schema，不盲搬 battle-effect 的容量分类。
复用 fixture/CLI/输入身份机制，再贯通完整分母；域校验拒绝与容量拒绝必须分别记账。
自然 record×field、全局七门、字节 unknown 和实体硬件继续按既有完整目标推进。

## 几分钟验收

- [ ] 执行上述 guard 命令 → verified=true，35 CLI / 34 resources / 23 接受 / 11 拒绝。
- [ ] 查看 result.json → 所有 ID 显式列出，接受项整 ROM/alias/槽外检查为 true。
- [ ] 查看拒绝 case → stderr 明确容量不足，没有 output.gba 或 build-report.json。
- [ ] 查看复验结果 → 完整 JSON 相同；DB/runtime/硬件/graphics release scope 均未升级。
