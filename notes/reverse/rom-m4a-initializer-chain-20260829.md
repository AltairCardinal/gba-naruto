# M4A initializer chain 518-byte closure（2026-08-29）

## 目的与结论

本里程碑把三个有固定 producer provenance 的 Thumb initializer/open root 及其实际消费
literal 闭合为一个失败关闭的 ROM 字节合同。正式 artifact 为
`artifacts/rom-m4a-initializer-chain-v1/`，只晋升六段、合计 518 bytes：390 bytes
bounded Thumb code 与 128 bytes consumed literals。

| 类别 | ROM 范围 | 字节 |
| --- | --- | ---: |
| Thumb code | `[0x09AA3C,0x09AA90)` | 84 |
| consumed literals | `[0x09AA90,0x09AAB4)` | 36 |
| Thumb code | `[0x09ACF8,0x09ADC0)` | 200 |
| consumed literals | `[0x09ADC0,0x09AE10)` | 80 |
| Thumb code | `[0x09B17C,0x09B1E6)` | 106 |
| consumed literals | `[0x09B1E8,0x09B1F4)` | 12 |

packed bytes SHA-256 为
`f5c0a94ac06bf6750edc038e0db95fc5d4e96c321129e57a11abd461aa678ea7`，range-vector
SHA-256 为
`8bcba07694e7375d59dddeb3cb12eeb4903e61147c91723482d61d06a47dbd72`。

不得从本结论外推完整 m4a runtime、自然执行可达性、computed/indirect producer、RAM
callback 状态、编辑/写回/重定位或 free space。raw BL producer
`[0x061E28,0x061E2C)` 只作 provenance，未证明其所在 caller CFG，仍为 unknown；
`[0x09B1E6,0x09B1E8)` 没有指令或 literal consumer，也仍为 unknown。

## 合同与独立复验

- CFG 分母：188 instructions、25 blocks、31 internal edges、7 direct calls、3 returns、
  0 unresolved frontier；
- literal 分母：33 PC-relative refs、32 unique words，恰好覆盖 128 bytes；
- 三个 root 的全 ROM target-limited producer 分母分别为 `[0x061E28]`、
  `[0x09AA56]`、`[0x09AA76]`；未发现额外 Thumb B/Bcond、ARM B/BL、u32 entry 或
  u32 Thumb-pointer forms；
- manifest / payload SHA-256：
  `9b9b9f2f49a1ee8224703ca47b73dc608d75ba83d2be44564e24873c44237c9c` /
  `7f019b01e800a3dd769463cbea907049429b1cad416dc17ed8719a561837babd`；
- exporter / independent verifier SHA-256：
  `4e0b8743247d9098a9d72667f4b2499abee1c71c45cd5a704feaa54f17a4ced9` /
  `5cd9ccf232ebb10c69e89962e9861add7675dfb935c6e6a293b16049fd6cec31`。

主要实现与复验入口：

- `tools/export_rom_m4a_initializer_chain.py`；
- `tools/verify_rom_m4a_initializer_chain.py`；
- `tests/test_export_rom_m4a_initializer_chain.py`；
- `tests/test_verify_rom_m4a_initializer_chain.py`。

测试覆盖身份漂移、六段 whole-range unknown、producer 形式分母、CFG/opaque-call/return/
frontier/literal 分母、单字节 mutation、重复 producer、branch/literal escape、pool hole、
stack epilogue、partial owner、upstream receipt 与误纳 2-byte gap。独立 verifier 使用自身
raw decode 路径，不把 exporter 输出当作真值。

## Coverage、proof 与 formal

接入前 coverage 已冻结在
`artifacts/rom-m4a-initializer-chain-precoverage-v1/`，其 raw coverage SHA-256 为
`31cf4a9c14666345482cad325433814e7fe26d458327c3bc5d9a13e680616563`。接入后的
`sequel/rom-byte-coverage.json`：

- SHA-256：`ab315087593f23bfbcc96c66ac99b8bfd002e5c29cd462088dda343139f9ac27`；
- classified / unknown：6,123,937 / 167,519；
- claims / segments：14,499 / 16,608；
- 相对 baseline 精确变化：+518 classified、-518 unknown、+6 claims、+8 segments。

proof spec SHA-256 为
`fcbd2cfb0b930853e82ce171f05d5f16b7019601ac4152e8174b5b6733057977`。TDD 中新增的
M4A proof test 首先因 evidence count 74≠73 正确 RED，更新 spec 后 GREEN；随后发现并
修复 proof policy 的 current/上一阶段 formal 身份混写。最终 67 项静态 proof tests
在受守卫 run
`build/experiments/active/m4a-initializer-chain-proof/codex-static-green-r2-20260828/`
通过，耗时 1,147.739 秒、峰值 RSS 441.58984375 MiB，日志 SHA-256 为
`6b3620818770f2ff9c4c9d1f49afdde9ad8cb52bb35c5884a3875aa97b5dd66f`。

正式审计 run：
`build/experiments/active/m4a-initializer-chain-proof/codex-formal-r1-20260828/`。
report / guard SHA-256 为
`8f6761d5f19cb9142caf5338971c4b1712aebf32f6f9cb08d98196b3d4d84c3e` /
`172d4a028aba3bfef2ca9ce9eeef9da8c07bbcf191e3fbe9424774a3a3e03628`；
2,805.908073 秒、峰值 RSS 588.98828125 MiB、非降级、exit 0。报告实际执行 85 个唯一
结构化 verifier（75 ROM + 10 bank），85/85 均 `contract_ok=true`；proof gate 的配置总数
是 86，因为另有 11 个 hash-only 旧 gate verifier，不能把 86 写成实际执行次数。
`complete=false` 与 175 blockers 是当前 167,519 unknown bytes 和其余严格完成条件的
真实状态，不是本里程碑失败。

## 失效尝试与成本控制

- mock-baseline/r7 产物已被正式 baseline 身份取代，只保留为历史诊断，不得复用；
- 第一次完整静态 proof run 因 policy current counts 过期而在约 19 分 30 秒后失败，且
  没有保存 child log；这是本里程碑可识别的主要无用浪费。修复后 r2 是权威收据；
- coverage 生命周期一度需要从 precoverage 快照恢复后重建；最终 artifact、coverage、
  proof 与 formal 身份已逐项核对，不能删除 precoverage 副本或失败 run；
- 后续复验优先跑独立 verifier 和定向测试。除非 manifest、工具或 proof 身份发生授权
  变更，不得重跑 46 分钟 formal。

## 下一接手点

下一优先候选是 562-byte MP2K note allocator/channel-gain closure：
`[0x09A6D8,0x09A708)`、`[0x09A708,0x09A8FE)`、`[0x09A900,0x09A908)`、
`[0x09AF24,0x09AF28)`；明确排除 `[0x09A6D2,0x09A6D8)` 与
`[0x09A8FE,0x09A900)`。完整合同冻结清单和模型编排见
`docs/reverse-engineering-handoff-20260812.md` 第 18 节。
