# Unknown cluster refresh（2026-09-05）

## 输入与总量

- ROM SHA-256：`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- authoritative coverage SHA-256：
  `2cc07bc74d24276b994219900ad7419787f9b8832dd62a66bb7839d09df42c01`。
- 6,202,729 classified / 88,727 unknown / 1,771 unknown ranges，语义覆盖率
  98.58972231547037%。
- 17 个 unknown ranges 长度至少 1,024 bytes，合计 42,884 bytes；这只是候选集中度，
  不是可晋升量。

## 当前最大单段

| range | bytes | 左右 owner | 当前边界 |
| --- | ---: | --- | --- |
| `[0x00578C,0x007554)` | 7,624 | value-range text → training script | 旧复核仍缺动态 u8 index 完整分母 |
| `[0x53F89C,0x541368)` | 6,860 | unbound LZ77 → unbound LZ77 | 14 个 `0x10` 形态头均不是有效 LZ77；不是 padding/free 证明 |
| `[0x0042AB,0x00542E)` | 4,483 | fixed-consumer text → value-range text | 63×8-byte 物理表消费者 index 未受 `<=62` 支配 |
| `[0x54136F,0x5421FC)` | 3,733 | unbound LZ77 → value-range selector | 高零比例不构成语义证据 |
| `[0x59EAE0,0x59F560)` | 2,688 | unclassified pointer table → bounded u16 pair | 已有 index=120 反例与 callback lifecycle blocker |
| `[0x0A1954,0x0A2154)` | 2,048 | dialogue font → dialogue font | 固定 glyph 分母不命中该 gap |
| `[0x04BE31,0x04C616)` | 2,021 | chapter script → chapter script | 语法可闭合但无 producer/root，固定表明确跳过 |
| `[0x599924,0x599F5C)` | 1,592 | fixed text table → value-range pointer table | dynamic RAM count / mixed schema 未闭合 |
| `[0x000CEA,0x0012F0)` | 1,542 | fixed renderer script → fixed renderer script | 低脚本池动态 index 无完整上界 |
| `[0x5A4708,0x5A4CE8)` | 1,504 | fixed table → scene source | 无 direct pointer/base literal 或 parser consumer |

## 新一轮筛选

- 先复用 `tools/analyze_rom_unknown_clusters.py`，不以邻接、熵、零字节或反汇编形态直接
  分类。
- Luna max 只读 scout A：从 canonical instruction-only claims 反向扫描 direct
  BL/B/Bcond 到 unknown root，优先寻找 >=1 KiB 或可解除 blocker 的依赖包。
- Luna max 只读 scout B：专查 `[0x078E38,0x07914C)` 788-byte code-like gap 的 exact
  producer、decoder、literal 与 frontier 分母。
- 本体保留 boot residual `[0x0003E0,0x0004C8)` + `[0x000734,0x000A65)` 的后续筛选；
  代理线程上限使第三个 Luna 未启动，不能把该候选记为已外派。

## 选择规则

- 只有 raw ROM、exact instruction owner、current-unknown、独立 verifier 与失败关闭边界
  均可冻结时才进入 TDD packet。
- 第一批 Tier-1 队列从 0 重新计数；达到 4 packets、10 KiB 或 0.15pp 前不重复运行
  canonical/proof/formal。

## 筛选结果补充

- 启动区 `[0x0003E0,0x0004C8)` 可完整解码为 58 条 ARM 指令，末尾 `BX lr`，但全 ROM
  ARM B/BL 与 raw pointer `0x080003E0/1` 均为零；没有 producer，保持 232 bytes
  unknown。`[0x000734,0x000A65)` 为 record/script 形态，也没有冻结 consumer 分母。
- `[0x078E38,0x07914C)` 已由后续 `rom-task-callback-078e38-closure-v1` 取代早期
  “lifecycle 未闭合、净晋升为 0”的诊断。唯一 pointer `0x08078E39` 在 `0x079378`，经
  `0x0792BE` 作为 arg8 传给 allocator、写入 task `+0x28`，再由 scheduler dispatcher
  读取并经 `BX r1` 调用；source/allocator/dispatcher/veneer owner 均已独立绑定。
  最终只晋升 718 code + 60 literal = 778 bytes，五个 2-byte holes 保持 unknown；
  `BX r0` 因 opaque callee 副作用未闭合继续保留 1 个 frontier，不声明 structured return。
- 从 4,041 个 instruction-only claims / 173,184 code bytes 反扫得到 18 条 Thumb BL 到
  unknown、6 个唯一 targets；没有新增 B/Bcond/ARM 命中。最低风险下一项是唯一 accepted
  producer `0x08F8DE BL -> 0x08F544`：闭包 `[0x08F544,0x08F594)` 80 code bytes、0
  frontier，三个 direct calls 与 fallthrough 均进入既有 owner。其余候选受
  `pop {r0}; bx r0` saved-LR/SP 证明或 dynamic tail-jump 阻塞。
- 上述最低风险候选已发布为 `rom-story-selector-dependency-cfg-v1`，父级 TDD/只读审查后
  最终精确晋升 80 bytes / 1 claim；与 fixed-index 小包累计投影 unknown 为 88,643。
  其余候选的动态 return/callback blocker 未因本包而解除，仍不得仅按可反汇编形态晋升。
- task callback 包完成后，三包累计为 862 bytes / 18 claims，线性投影 unknown 为
  87,865（98.60342343648275%）；authoritative canonical 仍为 88,727 unknown。下一份
  有效 packet 将达到 4-packet Tier-2 门槛，届时才统一重建 coverage/proof/formal。
