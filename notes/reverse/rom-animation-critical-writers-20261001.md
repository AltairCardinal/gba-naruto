# 动画生命周期：callback／关键写入／查表与推进的联合审计

> 后继联合验证见[对象初始化／两allocator／释放与counter](rom-animation-object-lifecycle-20261001.md)：
> 25tests、526人工case、672旧trace和永久目录重放通过；自然域与全writer义务未解除。

状态：八条固定入口假设的有限指针来源与两组独立来源验真已闭环；全局 writer、别名、
自然域与对象生命周期仍开放。沿用固定 BL／混合动画池审计模式，脚本优先，无子代理。
永久收据 `notes/evidence/rom-animation-critical-writers-20261001-v1/`，54 成员，manifest SHA
`9abb50194d42169b6e07d6a362c0a11249c19cfe59dbb5d78506ee3e6170cd6f`。
权威输出 `critical-writers-v2.json`，SHA
`c1ff95909964ca3c93bd5b800e30e5309347660e9b8cd1d16c833532800bf031`。
原报告、错误入口试跑、literal 地址修复前实现和失败重放启动器均保留，versions.json 区分。

## 来源与复用判断

直接复用旧 58 成员联合身份收据、固定来源图、callee identity validator 与 raw decoder，
追加有限 pointer provenance，而不是重造 allocator／dispatcher 或另一套自然运行模型。
旧图 64,926 指令不包含 v20 更新器；本包实际重放 `verify_rom_cfg_proven_roots_v20.verify_root`
和 `verify_rom_text_bg_task_closure.verify_artifact`，再引入 v20 的全部 1,405 条实际 code
成员，其中净新 1,369 条；union 为 **66,295 条**。旧 caller 图与 47 调用统计不改写。

v20 payload SHA `5d3186a688973b1733b0117aedee7c689a5270497c83f8726d4d2540bcfe1543`，
long callback payload SHA `014c4b8c4fd098e8049511df55f248505e4d680be5b394592cab92e26c512a0c`；
工具／manifest／coverage 输入身份与实际 verifier 结果在 source_inputs/source_verifiers。
来源 CFG 成员成立不外推自然执行、RAM 指针域或 existing owner 重分类。

短 callback **8EE40..8EE56** 是另行标记的 raw 候选，10 指令／22B，SHA
`1157e1f10151f5d4ca1cb577841ae34727c7f5e106c540e4838d808ecb60dc36`。
旧条件模型在 8EEA2/8EEC6 两个 allocator 调用固定 callback0808EE41，原字样全 ROM
逐字节分母仅 8EEEC 一处。两个注册仍保留原 call/context 前提，不变成自然域证明。
该候选 **canonical_source_membership=false**；8EE56..8EE58 的零 suffix 不混入 code。
8EE44 使用 literal8EE58→**0200A882**；原字节与注册证据只是候选根的绑定，未晋升。
初始盘点误选 6254C 实为 literal，missing_source_root 保留；不凭线性反汇编当 code。

## 有限指针来源方法与边界

`provenance.py`只传播已知整数和 `(object, relative_offset)`、`(sp, relative_offset)`。
对象指针被覆盖或从 RAM 重新加载时丢弃原 identity；地址加法累积实际偏移，不按 store
表面的 immediate 猜字段。分支全部探索、合流只保留一致事实；event 在 worklist 收敛后
从最终输入状态生成，不能保留第一条路径上的旧 definite 地址。

跨调用先通过旧 validator 递归核对原 ROM／source／return identity，只保留已验真的
r4..r11；所有 caller memory 始终清空，未知 call 销毁 GPR。条件保存区／opaque call
恢复与全局 alias 仍未证明。STR/STRH/STRB 按字节区间检查关键字段重叠；未知 store 和
STM 保留 may_alias_pool，不用 unknown 地址的空结果签发“不存在写入”。literal 读取
明确标记实际 ROM 地址；ROM 读取不会误标为 RAM pool alias。

入口 object 是明确的**规划假设**，不是 runtime handle 证明；报告均标
entry_object_domain_proven=false。SP 地址也不凭文字假设与对象池 disjoint。
32,000 次 worklist 更新、source 缺失、unsupported control、动态 SP/PC 与坏 callee
摘要都失败关闭。指定 iteration stop 仅结束本入口分析，不证明运行时一定到达／终止。

## 八条入口及实际发现

| 入口假设 | 节点 | 关键结果 |
| --- | ---: | --- |
| long callback8AA50，r0=当前 task | 266 | 29 store，3 个仍具当前 task identity，14 个地址 unknown；15 call |
| short callback 候选8EE40，r0=当前 task | 10 | 无直接 store；唯一 call8EE4E→62788，r0 仍为当前 task |
| disable helper62788，r0=当前 task | 8 | 62794 写 flags，表达式 `(old_flags & FFFFFFFE) | 2` |
| reset helper62798，r0=当前 task | 9 | group写 caller r1，slot/timer写0，flags & FEFFFFFB |
| advance63238，r7=当前 task，stop632F8 | 89 | 8 个当前 task store，slot/timer/flags 路径均登记；62798 call 保持边界 |
| selection6298C，r7=刚加载的 task，stop629B0/629B4 | 20 | group、sequence table、slot 在 freeze test 前已读取 |
| dispatch62940，r7=当前 task，stop62958 | 12 | 62954→9C114 的 r0=当前 task；间接 callback/context 未闭合 |
| active filter627D6，r6=当前 task，stop62808 | 19 | 62806 写 inactive task flags，另两 store 地址 unknown |

long callback 的三个已识别 store 在 **8AA7C/8AA80/8AA82 → task+2E/+2C/+30**，
都是上下文区，不是 group/slot/timer。r5 之后改指向其他资源记录；必须丢弃旧 task
identity。14 个 unknown store 及 SVC/其他 callee 仍可能通过别名影响对象，所以
“已识别 direct critical store 为0”不能换成“callback 不修改关键字段”。

短 callback 在 RAM0200A882 非零时调用 disable helper，清 active bit0、置 bit1。
62924 先扫描 128 task 的 callback，62968 再调用 627B0 重建活动列表；后者重新检查
bit0。627E0 inactive 路径在 62800..62806 以 FFFFFFFD 清 bit1。allocator 检查
flags&3；这些原指令关系有助于研究释放／复用阶段，但不证明全局 handle 永远有效，
也未穷尽其他 callback、computed producer、全 ROM RAM writer 或 IRQ/BIOS alias。

序列查表：6298C读 group+14，6298E读 sequence table+20，62994读 slot+16，62998
取 table entry，6299A加 slot×4。freeze mask8 在63244检查，明显晚于这些读取。
因此即使 group1 初始冻结，也不能以冻结为理由免除 group/slot/table 的有效性义务。
本包没有建立 descriptor 的完整合法索引域，不能将 496B 候选升为受证动画 bank。

## timer/counter 与后续里程碑

63256 LDRH →63258 +1→6325A STRH，timer 为 u16 模运算；63260 将 duration
作为 signed16 读取，再与 63262 的 u16 timer 做相等比较。负 duration 不等于任何
u16 timer；duration0可在FFFF→0时匹配。这是宽度与比较的静态事实，不是自然 timer
取值穷尽。63276 增 slot，632B8/632BA 清 slot/timer，632CC helper 的 group 参数是0。

counter 在632E6 LDRB 从03000075读取，得到 byte 上界，**producer domain 未证明**。
前包672人工 trace 已显示 mode20/counter≥2 可读 sequence sentinel 后 duration；
本包不重复算作新 runtime，也未用 byte 上界替代完整索引域。

下一里程碑应联合：03000075 的实际生产／清零／更新域，62560 初始化与两类 allocator
的128对象选择，disable→active-list→复用的全部相关 writer，以及 callback alias、
group/slot/timer 的不变量。先取得真实来源入口或 writer 新证据，再扩索引消费合同；
不要增加独立几字节窗口、猜 BIOS 寄存器保存、把活动列表 shape 当自然穷尽。
92018→8A4D8 软件 effects、caller SP+48 与协程同上下文恢复继续保留各自义务。

## 验证、失败保存与实际边界

六项新测试先因缺 provenance 模块正确失败，再最小实现通过。后续 PC-relative literal
读取被标成 unknown 地址的反例真正失败；首次同时添加的 overlap 反例把0xC..0x10
误当触及0x14，原错误 fixture 保留。改用0x12..0x16后重新 red，仅 literal 一项失败；
修复与重构后 **9/9** 通过。覆盖偏移累计、寄存器改用途、合流丢值、opaque call、
受证 child 只保留 GPR、不猜 RAM pointee、partial overlap、source 缺失与预算失败。

首次真实 joint run 的 selection 种子错误：62982会覆盖 r7，正确单对象假设入口为6298C；
失败日志与旧 driver 留存，修正后八入口集成通过。source launcher曾误导入 verify，
实际入口为 verify_root；该失败未运行 verifier。首次 notes 重放缺 parent import path，
在 log/output 初始化前失败，修正后使用全新 run。都不伪装成 ROM 缺陷或 successful red。

最终批量：9测试、AST／脚本行尾空白、两组来源独立 verifier、八入口 raw 集成通过；
15.53s／峰值281.46MiB，统一heavy lock，非降级exit0。永久目录重放15.55s／262.25MiB，
9测试、两组 fresh verifier 与权威JSON逐字节复现。前期试跑也重复来源验真：本轮共5次
调用每组 verifier（共10调用），不是10个新来源或formal合同。所有 owned run 均 complete，
失败 run 的 completed 只表示产物停止写入，不表示验证成功。

复验（逆向工作树根，新 CHECK_UNIQUE）：

```sh
python3 tools/experiment_workspace.py --root . init --task animation-critical-writers-replay --run-id CHECK_UNIQUE
python3 tools/run_guarded.py --lock-file build/experiments/heavy.lock --summary build/experiments/active/animation-critical-writers-replay/CHECK_UNIQUE/guard.json --wall-timeout-s 240 --idle-timeout-s 120 --max-tree-rss-mib 1536 -- python3 notes/evidence/rom-animation-critical-writers-20261001-v1/replay_receipt.py build/experiments/active/animation-critical-writers-replay/CHECK_UNIQUE/output build/experiments/active/animation-critical-writers-replay/CHECK_UNIQUE/replay.log
python3 tools/experiment_workspace.py --root . complete --task animation-critical-writers-replay --run-id CHECK_UNIQUE
```

canonical/proof/bank-proofs 身份不变，unknown87,631B，175 blockers仍是历史正式结果。
31双字段候选／16字段缺口未重算；new Tier-1、formal、mGBA、hardware均0，promotion=0。
未提交或push，Butano不改。Goal active，周剩34%，20%停止预算继续有效。

### 【功能特性】
- 从本记录查看两类callback、两helper与四阶段的真实读取／写入地址及未闭合项；仅用于逆向。

### 【BUG 修复】
- 分析器literal地址已修复：PC-relative ROM读取被标成unknown/pool alias → 绑定真实ROM地址。

### 【验收清单】
- [ ] 查看reports → 八入口，long callback三处context写入及14 unknown；不宣称critical writer穷尽。
- [ ] 查看short binding →22B／10候选指令，两个条件注册，0200A882，suffix/source promotion均排除。
- [ ] 查看selection/advance →查表先于freeze，timer u16、duration signed16、counter producer未证明。
- [ ] 查看portable-report →9测试／两组source verifier通过，payload逐字节一致，promotion0。
