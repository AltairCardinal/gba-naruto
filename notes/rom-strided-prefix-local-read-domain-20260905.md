# 固定 stride 的局部 may-read 候选（2026-09-05）

状态：局部实验可复现，但父级政策复核拒绝接入；**keep_unknown / bytes_promoted=0**。
canonical 仍为 6,203,707 classified / **87,749 unknown**，SHA 为
`1c6af01a54f3522ba277a4744b5b821d53588b853b3e7755902c65431df584b6`。
1,145 字节仅是任意注入局部机器状态下的 unknown 交集，不是合格待接入收益。

## 复用模式与范围

最初尝试复用 AGENTS 的固定 u8 逻辑 lookup overlay 模式：冻结 consumer、输入域、字段读取宽度，
分别保留逻辑视图和 immutable precoverage 的 primary/overlap 投影。现有 interval
脚本可复用，但两段 consumer 的截断和条件读取不同，不能直接复用整 cell 表合同。
Luna max 完成公开合同内的 producer/TDD；Sol medium 只读复核边界；主代理完成独立
raw Thumb 解码、局部机器状态 witness、失败关闭测试及恢复收据。没有使用未提供的模型。

- lookup 为 `[0x348DAC,0x348EAC)`，256 个 u8；record base 为 `0x59EAE0`，stride 24。
- C1 从局部 slice `0x893E4` 开始，index=`lookup[selector_u8]+tail_u8`，域为 0..503。
  读取每行 `+0..+1` 与 `+4..+5`；在 comparison byte 为零的 witness 下也读取 `+2..+3`。
- C2 从局部 slice `0x89E90` 开始，index 为上述和截断到 u8，域为 0..255。
  总是读取 `+7`，仅当固定 ROM 的 `+7!=0` 时读取 `+6`。192 行非零，64 行为零。
  验证在首个 BL `0x89ED8→0x68EA4` 前停止，callee 没有执行。

局部 witness 显式设 `r9=0x02002880`、`SP=0x0203F000`、`RAM[0x0202680C]=0`。
两个 u8 输入分别是 `state(0x020311D4)+0x16/+0x19`。C1 的 STRH 写回与这些地址不别名；
unsigned `0 > u16 threshold` 恒假，因此每个 logical index 都有读取 `+2/+3` 的局部 witness。
这不是函数 `0x89310` 的入口 witness，也没有证明前序 callee 保存 r9。

26 项测试包含相反状态：comparison=255 或 r9 与 comparison 别名时，`+2/+3` 可以不读。
因此字段必须称 **local_typed_may_read_witness**，不称 must-read、自然可达或全状态读取。
原 112×24 物理表否证仍有效；旧 2,500 字节估算把后续 pair fields 算入，现已被取代。

## 精确候选分母

| 分母 | ranges | bytes |
| --- | ---: | ---: |
| 合并后的逻辑读取域 | 569 | 3,728 |
| immutable baseline 中的 unknown 投影 | 162 | 1,145 |
| 已有 primary owner 的 provenance | 446 | 2,583 |

新增候选由 256 lookup 字节和 889 record-prefix 字节组成。零 flag 阻断的 `+6`、所有
`+8..+23`、以及索引 256..503 的 `+6..+23` 均不在本合同读取域内，不新增分类。
overlap 保留原 segment 的完整 owner，不改写任何旧 primary claim。

原始 consumer 和两条 BL producer 都绑定已验收 v6 CFG 的 blocks
887/888/1120..1125/1177/1185；全 ROM raw BL/B/Bcond scan 和 literal occurrence 分母另行重算。
本包只重验所需 block/member 与源文件身份，不声称在这里重跑了整个 v6 CFG verifier。

## 可恢复输入与验证收据

run：`build/experiments/active/strided-logical-read-domain/base-59eae0-preflight-20260905/`。
当前 packet 为 `luna-packet/`，候选为 `candidate-parent-v3/`。原 Luna 产物保留在
`luna-original/`；v2 和所有失败日志保留；固定恢复副本在 `snapshots/tier1-v3/`。

- 公共 CONTRACT SHA：`3941100ecfcc6744e490b560fc2a81d78b838a1fa92642eb1ebc46a41127358c`。
- baseline 使用已提交的 `notes/evidence/rom-evidence-selector-repair-20260905/coverage-after.json.gz`，
  压缩 SHA `f996d62735f43b00fc3375b1e74423aac6b331edbca0943ae3033c2ceea0942b`；raw SHA 为上述 canonical。
- producer SHA：`9d47c3191d49b36263f3b0979bdf7ed605cdfca898b272490c1837f42eb4c244`。
- independent verifier SHA：`e84b6dd1cbd548b6bdb2e916e00f7c181f541ad8b84ad8c42ca97806deda753d`。
- payload SHA：`063f4f71d5271ac003263897e800456fc02266ec19d4a9284c54c3dbd927cf2c`；
  1,145-byte bundle SHA：`4f3f1e6d43a449250aa1a393b9e401fc881e63ef509de53fe1ea450618441443`。
- 两次独立 report 相同，SHA：`23fbee1579cffff8c8ac9fbd3ef712bddfb0120f97f0853f7c16ee73d8ef4257`。
- `tier1-candidate-receipt-v3.json` SHA：`100af24c4a6696a0f2870f5554688175040d7f158a94f29365f08e49af6a9e39`。

最终 26/26 测试在 12:12:56Z–12:13:05Z 通过，guard 非降级、exit0、峰值203.21MiB；
两次稳定重放在12:14:02Z–12:14:05Z通过，峰值181.82MiB。五个 Python 源通过语法检查。
测试包括隐藏同构输入、全部116个consumer-window单字节变异、更新成员哈希后的语义篡改、
零 flag、unsigned branch、alias store、真实 CLI 重放、文件/目录替换及重复输出。

父代理以 RED/GREEN 修复：输出 `..` 越界、零长度区间、错误重放路径、成员替换，
以及异常清理 stat→unlink 竞态。发布使用 held dirfd 和原子 no-replace，前后复验精确
三成员身份与内容。**失败路径不执行名字删除**，保留0700 staging供恢复；不得递归清理
可能已被替换的目录。原始失败日志保留在 packet，不把失败运行改记为通过。

## 父级裁决：不进入待接入队列

Sol medium 只读审查与主代理核对确认，AGENTS.md 的组合持久 RAM 索引规则比普通
单 u8 overlay 更严格：所有入口首入/续入 callback、字段 writer、clear/copy/inherit、
脚本 root 和支配检查必须闭合。当前 `0x0808F654` 的 computed/RAM/indirect producer
frontier 仍开放。旧 `verify_rom_scheduler_callback_lifecycle_gate.py` 的 keep_unknown
门继续有效；不得通过 may-read 标签、增加 wrapper 元数据或绑定更多摘要绕过它。

C1 还缺 `0x89310→0x893E4` 前序 callee 对 r9/state/comparison 的保存和别名不变量；
C2 虽然紧接 prologue、在首个 BL 前停止，256-cell union 仍来自任意注入的 RAM 两字节，
不是已证明的入口状态域。两者当前都不能签发 primary claim。原普通 u8 overlay 先例
不能解除这一特定规则。

重新开启的先决条件是先解决 `0x0808F654` producer frontier，并让生命周期 gate 实际
闭合，再穷尽字段写入与继承分母，按已证明入口状态重算读取域。随后还需完整 direct/
literal/entry-pointer 分母、上游 CFG、真实投影和正式验收。之前“只补 accepted wrapper
即可入队”的判断已被取代；原实验与测试收据保留，不篡改为晋升证据。当前停止此方向的
抽象索引扩张，转到有完整边界证据的其他 packet。套餐余量71%，Goal active；未push或reset。
