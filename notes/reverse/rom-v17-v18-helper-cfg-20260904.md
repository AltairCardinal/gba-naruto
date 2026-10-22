# V17/V18 helper CFG 冻结闭包（2026-09-04）

## 结论

`rom-v17-v18-helper-cfg-v1` 已作为新批次第一个 Tier-1 packet 完成。正式 artifact
精确分类 1,254 个当前 unknown 字节：1,198 bytes Thumb 指令与 56 bytes 实际消费的
literal words。基于 authoritative coverage `ae7c6933...90024` 的投影为
6,195,370 classified / 96,086 unknown / 98.47275416056314%。本次不改写 canonical，
也不重跑 full coverage、proof 或 formal audit。

## 固定输入与分母

- 11 roots：`0x090564/584/5A4/618/634/658/758/8D8/A20/A90` 与 `0x095F38`。
- bounded closure：575 instructions、81 basic blocks、24 opaque accepted exits、
  11 structured returns、0 frontier。
- literal：14 references / 14 unique words / 56 bytes。
- 全 ROM 2-byte stride direct branch denominator：99,909 条；34 条命中 roots。
  其中 33 条 source 位于 V17/V18 accepted reachable-code claims；
  `0x090FF0 -> 0x090758` 保留为 unbound；`0x485DAE -> 0x0909A4` 位于
  `m4a_directsound_wave`，只作为数据形态误报拒绝。
- 六个 `[0x090656,658)`、`[0x0906DE,6E0)`、`[0x090756,758)`、
  `[0x0908D2,8D4)`、`[0x090A0A,A0C)`、`[0x090A8E,A90)` 共 12 bytes
  保持 unknown。

## 结构化返回与失败关闭

十个函数以入口保存 LR，并以 `pop {r0/r1}; bx r0/r1` 返回；`0x090618` root 直接
`bx lr`。对含 SP 临时区的两个较大闭包额外冻结全部 19 个 SP operand sites；
`0x0909DA` 调用固定 `SWI 0x0B; BX LR` wrapper，source 只读 `SP+0x14`，saved LR
位于 `SP+0x34` 且无写入。该合同只证明本闭包的 return 归一化，不声明 ABI、业务用途或
自然执行。

测试先以 exporter/verifier 缺失得到 RED，再实现 GREEN。8 项 packet tests 覆盖 accepted
producer、unbound producer、M4A 误报、code、literal、hole、exit、payload/manifest、
symlink 与原子 no-replace 变异。独立 verifier 不导入 exporter，以 raw Thumb 位域重建
闭包与 producer denominator，并拒绝 ARMv4T Thumb-1 合法 opcode family 之外的编码。
正式 verifier 返回 `contract_ok=true`、
`promotion_bytes=1254`、`frontier_count=0`。

Sol P0/P1 复核发现 Tier-1 code kind 被过早放入稳定 registry，会令尚未含本包的旧
canonical 因 missing kind 失败；现已改为 active-only staged registry。staged kind 缺席时
稳定 denominator/hash 不变，出现时才接受、强制 Thumb mode并计入 aggregate；其他未注册
code-like kind 继续以 extra 失败关闭。artifact 同时明确区分“路径无关的内容验真”和
“固定 official 路径的 canonical reproduction recipe”，staging 只允许位于
`build/experiments` 或正式目标。

## 证据与边界

- artifact：`artifacts/rom-v17-v18-helper-cfg-v1/`
- payload SHA-256：`add16ebfc58ad853ad1edd72b43dc05737e8d3e6139b6c4477e8a7744f67d183`
- manifest SHA-256：`aaee06ec6f347b972bcc506bd34e68fd8222695e39c1b19eb53a3700f2ee32f0`
- verifier SHA-256：`8e544183b84c54b0b5aef09493ec0e2fabb4d8e758afb540ae3e49bc1b3a603a`

不声明所有 inbound producer 已接受、computed/indirect producer 穷尽、自然运行时可达、
函数名或业务语义、padding/free space、编辑、写回或重定位安全。Tier-1 接入只做
current-unknown projection；达到批量门槛后才运行真正的 Tier-2 canonical 集成。

## 2026-09-05 接入状态

该包后来与 fixed pair、prebattle controller、scene source 共四包统一接入。当前
authoritative canonical 为 6,198,347 classified / 93,109 unknown /
98.52007230122885%；本节前述 6,195,370 / 96,086 仅保留为入队时的历史 projection。
