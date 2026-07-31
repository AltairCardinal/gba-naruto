# 三条坐标变换 WRAM tilemap 的受控运行时闭环（2026-08-01）

## 结论

派生 WRAM tilemap 中剩余的三条 12×12 坐标变换源已经完成受控入口下的运行时闭环：

| ROM 源 | load | submit | queue slot | submit/flush frame | 变化字节 |
|---|---:|---:|---:|---:|---:|
| `0x084634B8` | `0x08090B5C` | `0x08090CB0` | 0 | 101/102 | 18 |
| `0x0846356C` | `0x08090D56` | `0x08090F3C` | 2 | 142/143 | 17 |
| `0x084635D8` | `0x08090DC4` | `0x08090F3C` | 0 | 150/151 | 9 |

每条事务都独立证明：ROM LZ77 解压结果等于 `0x0200A640` 的 288-byte staging；
变换输出位于 `0x0200A760`；提交参数为目标 `0x06000806`、12×12 halfword；
对应 queue slot 从 status 3 变为 2；按 64-byte screenblock 行距从完整 VRAM dump
抽取的 12×24 bytes 在提交前不同、flush 后与变换输出逐字节相等。所有事件满足严格的
`load < load-post < submit < queue-pre < queue-post` cycle 顺序，phase B 的第一条
事务还必须在第二条 load 前完成，防止共享 submit 地址造成来源串证。queue pre/post
必须同帧且各自在 `audit.events` 中唯一逐字段匹配，不能只信任 correlation 内嵌副本。

正式成果位于 `artifacts/residual-wram-transformed-tilemap-runtime-v1/`。其
`runtime-evidence.json`、所有原始 binary、快照、截图、run audit、guard 与 manifest
都受 SHA-256 约束。独立 verifier 不导入 exporter，并自行解压 ROM、解析 queue、
解码 `.ss9`、从 load-post 快照的旧输出重建唯一 3×3 裁剪与 `+0x02BC` 更新、
抽取 strided VRAM rows、检查 ABI/ownership 父证据和入口链。

## 入口边界

这项成果明确是 `controlled`，不是 `natural`。入口链在 base ROM 上通过一次内存补丁
`0x020240BC: 0 -> 1` 解锁选择界面，然后保存选择界面与 state 3 快照；两条正式 run
均从已验证的 state 3 快照恢复。该补丁、父快照哈希和每一跳 audit 都已收入 artifact。

因此可以声称三条 transformed source 的运行时 load、变换、queue submit 与 VRAM
flush 均已闭合，子分母为 3/3；不能声称自然游戏流程已经到达该界面，也不能据此声称
修改 ROM 后的最终像素或完整演出时序等价。

## 复现与验证

正式运行均经 `tools/run_guarded.py` 的 heavy lock 执行，退出码为 0、非 degraded，
phase A/B 的 owned-tree 峰值 RSS 分别为 116.7890625 MiB 和 116.734375 MiB；
运行结束后没有遗留 mGBA 进程。

从仓库根目录执行独立验证：

```sh
python3 tools/verify_residual_wram_transformed_tilemap_runtime_evidence.py \
  --artifact artifacts/residual-wram-transformed-tilemap-runtime-v1
```

重建 artifact 时必须使用原始、未修改的四个 run 目录：

```sh
python3 tools/export_residual_wram_transformed_tilemap_runtime_evidence.py \
  --root . \
  --unlock build/experiments/active/residual-wram-tilemap-reachability/choice-completion-unlock-default-20260731-v2 \
  --state3 build/experiments/active/residual-wram-tilemap-reachability/choice-state3-checkpoint-20260801 \
  --phase-a build/experiments/active/residual-wram-tilemap-reachability/choice-state3-phase-a-closure-v6-20260801 \
  --phase-b build/experiments/active/residual-wram-tilemap-reachability/choice-state3-phase-b-closure-v6-20260801 \
  --output artifacts/residual-wram-transformed-tilemap-runtime-v1
```

exporter 拒绝覆盖既有输出；若需重建，应输出到新的实验目录，验证后再进行受审计的
promotion，不能直接删除或改写正式成果。

## 未闭合项

- 无补丁的自然入口可达性。
- 修改后 ROM 的最终像素 A/B 和完整帧时序等价。
- 该界面的精确业务名称与剧情语义。
- 同一画面内所有 writer 的排他性证明；本成果只证明所记录事务确实完成目标写入。
