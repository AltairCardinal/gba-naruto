# ROM boot register-init dependency CFG

## 结论

- root `0x06178C` 的全 ROM、2-byte stride Thumb BL/B/Bcond target-limited
  producer 分母恰有一项：`0x06109E BL -> 0x06178C`。producer 位于已独立验证的
  boot-interwork continuation exact block `block-thumb-06109e`，不是只由宽泛 owner
  range 推断。
- raw worklist 为 154 instructions / 12 blocks / 318 code bytes；32 个
  PC-relative LDR 绑定 32 个唯一 literal words / 128 bytes。
- 三条 direct call 均进入 CFG inventory v2 的 exact entry `block-thumb-09c0e0`；
  `0x06181C`、`0x06207A`、`0x0620FE` 的 `BX r0` 保守保留为 unresolved
  indirect-PC frontiers，structured return 数为 0。

## 字节晋升与边界

- 精确晋升 4 段 Thumb code / 318 bytes 与 4 段 consumed literals / 128 bytes，
  共 8 claims / 4 union ranges / 446 bytes。
- `[0x06181E,0x061820)` 的 2-byte 零洞继续 unknown。
- `[0x0620B4,0x0620CC)` 不在本 root worklist，但 immutable precoverage 已分别归属
  boot-thumb-handoff code、code/literal alignment 与 consumed literal 三个既有 owner；
  本包只记录 exclusion，零重复晋升、零 owner 改写。

## 证据、TDD 与审计

- 正式 artifact：`artifacts/rom-boot-register-init-dependency-cfg-v1/`。
- manifest / payload / verifier SHA-256：
  `367a72b1131aa2301cb9b364415dc06a99522f8f5d468ee63ffb56cf79e3a932` /
  `ec89abce638edd878811697fe5d4f2abc08d5170fb4763f8ee199839d6fb22bd` /
  `6710e77a312c4818d654f4741bd7fe5753116a0c53a5ae3c5255367478b4ff91`。
- packet RED 先由缺 exporter 触发；GREEN 后又针对 exact producer block、完整 CFG
  inventory entry/owner 与原子 no-replace 三项 P1 各补 RED。父代理最终复跑 15/15，
  guard 峰值 270.75 MiB；candidate 与 official exporter/verifier 均非降级通过。
- Tier-1 RED 由缺 projection helper 触发，GREEN 后 3/3；四包合并预检 13/13，峰值
  544.1640625 MiB。
- 四包累计 4,382 bytes / 77 claims，达到简化审计的 4-packet Tier-2 门槛。唯一一次
  canonical rebuild 耗时 30 分 20 秒、峰值 439.7265625 MiB；coverage 更新为
  6,202,729 classified / 88,727 unknown / 16,870 claims / 18,641 segments，即
  98.58972231547037%，SHA-256
  `2cc07bc74d24276b994219900ad7419787f9b8832dd62a66bb7839d09df42c01`。
- proof SHA-256 为
  `3655c4a20a605e3fc32d1ad8d4aa82ee4b3e22cc71239a7d61837b2aedc205ce`。
  唯一一次 non-degraded formal 耗时 40 分 46 秒、峰值 534.92578125 MiB；
  report / guard SHA-256 为
  `3971d9ea6d910f14d15e073c268f61f785c26286abda44e1943c9bb85798ac3b` /
  `88d11d5f9227a75dbcdb9599ecdbdd691f17c9127f91d89d4fa519df2117d26a`，
  106/106 executed contracts 均 exit 0 且 `contract_ok=true`，ROM coverage gate 的
  96/96 contracted verifiers、evidence 与 coverage errors 均通过。

## 明确不声明

- 不声明自然运行时可达、全局 caller/code/indirect/computed/RAM producer 穷尽、
  三个 BX target 或 structured return、literal 业务语义、ABI/compiler 意图、holes/
  alignment/padding/free、编辑、写回、重定位或 gameplay。
- formal 的 `complete=false` / 177 blockers 来自仍有 88,727 unknown bytes 与既有
  bank、round-trip、发布及实体硬件门，不是本批回归。

## 模型编排记录

- 任务模式复用“固定直接 producer + 有限 Thumb CFG + consumed literals”脚本模式。
- Luna max 只写出初始 RED 后约 5 分钟无实现且无 blocker，已停止；这是模型执行纪律
  浪费，不是环境阻塞。Sol medium 完成 GREEN，父代理与只读 reviewer 发现并关闭三项
  P1，最终证据链和 Tier-2 由父代理验收。
