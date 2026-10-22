# ROM task callback 0x078E38 closure（2026-09-05）

## 任务模式

本工作包属于“公开合同闭合的小型冻结逆向工作包”：输入 ROM、immutable
precoverage、根、包络、失败关闭语义与验收分母均已冻结。选用可复现脚本（TDD、
独立 exporter/verifier）作为最终执行方式；Sol medium 子代理完成生命周期 scout 与
初版 packet，父代理复核、补 RED 并修复全部 P1。适用边界是固定 Thumb 直接控制流、
PC-relative literal 与静态 callback 生命周期，不适用于动态间接目标、自然运行时
可达性或完整 scheduler 语义。本包明确不复用另一套 0x4C record 的
`rom-task-scheduler-core-v1`，子代理输出也不作为最终结论。

## 结果

- 根 `0x078E38` 的 envelope 为 `[0x078E38,0x07914C)`，788 bytes，SHA-256
  `05503553bc42650c8d3d42c4ae1f4178efed6014b77dae610cf17524c4cb06bf`。
- raw Thumb worklist 闭合 342 条指令、61 个 basic blocks、718 code bytes；15 个
  LDR references 对应 15 个唯一 literal words、60 literal bytes；17 个 opaque calls
  指向 7 个既有入口；`0x079144: bx r0` 保留 1 个 `indirect_pc_target` frontier。
- code packed SHA-256：
  `5e4a0aa24845934f720ec9aece56e635416d319b6e3f05b7e9b4b4cddb00df14`。
- literal packed SHA-256：
  `3e4411efa69c56cc72b45c72ff8b21f9312ff406339b54e5d277907c029d1b34`。
- code-then-literal SHA-256：
  `39a86a9609bd90115ec76bd8beb64208e2271820f9ee7afc34ee8cadef032e27`；
  address-order union SHA-256：
  `361878bfaf3c4edf5da0f7db4266cb1d08446a1fcd4b96393cdfc88d602eb41e`。
- 16 个 current-unknown claims 共提升 778 bytes；5 个 holes 共 10 bytes 保持
  `unknown`，holes packed SHA-256 为
  `01d448afd928065458cf670b60f5a594d735af0172c8d67f22a81680132681ca`。

## producer 与生命周期证据

全 ROM 以 2-byte stride 重解 direct Thumb BL/B/Bcond；排除 closure 自身后，指向
root 或 internal block entry 的外部 direct producer 为 0。raw callback pointer
`39 8e 07 08` 仅在 `0x079378` 出现一次。

accepted source block `[0x0792B0,0x0792CE)` 在 `0x0792BE` 读取上述 pointer，
`0x0792C0` 写入 allocator arg8 的 caller stack `+0x10`，`0x0792CA` 调用
`0x0626B4`。allocator `[0x0626B4,0x062768)` 在 `0x06272C` 写 active bit，
`0x06275E` 从入口栈布局读取 arg8，`0x062760` 写 task `+0x28`。字段合同绑定
pool `0x03003BB8`、128 records、record size `0x3C`。dispatcher
`[0x062940,0x062958)` 检查 bit 0，在 `0x06294C` 读取 `+0x28`，以 task 为 r0，
经 `0x062954` 调用 `0x09C114: bx r1`。字段 artifact 的 whole verifier 状态没有被
冒充为成功；本包仅 replay 相关静态字段合同。

## 返回候选的失败关闭边界

epilogue `[0x079136,0x079146)` raw bytes 为
`02b038bc9846a146aa46f0bc01bc0047`，SHA-256
`b3072b4016ff811fcd06b302dc4b3eff9c521411df3a843f0c9307bddba94ee7`。
exporter/verifier 都从 raw ROM 重建该 epilogue、15 个可见 SP site 和末端
`pop r0; bx r0`，但这只能证明“返回候选形态”。17 个 opaque callees 的 SP 与内存
副作用没有被本包闭合，不能证明它们保持 caller SP 或不触及 saved-LR slot。因此
artifact 明确记录 `opaque_callee_stack_effects_proven=false`、
`structured_return_proven=false`，`structured_return_count=0`，末端保持一个未解析
frontier。对 epilogue/SP site/raw bytes 的变异仍失败关闭，但不会被夸大成 ABI 证明。

## verifier 与发布门禁加固

- verifier 从 raw ROM、immutable precoverage 与全部 upstream identity 独立重建完整
  payload，再执行 exact equality；删除 closure 字段、篡改 claim kind/hash、lifecycle、
  scope、implementation 或命令均不能通过。
- exporter 先在 staging inode 写 `candidate` manifest，调用不导入 exporter 的独立
  verifier；验证后把同一 inode 以最终名字原子 no-replace 发布并核对 inode 身份，再通过
  持有的目录 fd 写入 receipt 和 `accepted` manifest。accepted 复验及最终 inode 身份检查
  均通过才返回成功；任一阶段失败都只清理本次拥有的同一 inode。
- repository inputs、artifact members、staging 与发布目录都通过 `dirfd`、
  `O_NOFOLLOW`、inode identity 与原子 no-replace 绑定；并发替换路径时 verifier 读取
  已打开目录快照，不会逃逸到替换目录。
- 全 ROM direct BL/B/Bcond scan 已覆盖最后一个 2-byte halfword；synthetic 尾部 B
  回归锁定这一边界。

## 可复验命令与边界

```sh
python3 -m unittest tests.test_export_rom_task_callback_078e38_closure
python3 tools/verify_rom_task_callback_078e38_closure.py --root . \
  --artifact artifacts/rom-task-callback-078e38-closure-v1
```

正式 manifest / payload / verifier SHA-256 分别为
`a944163366106871fc983fb03bfb8e42666268b453083a6f38ba3ead6f737ca0` /
`ac163dad2bf1120ba1b5dc15936502d7b3a6efab59cd0b6b0e8db2e4ad48e1aa` /
`46ad2406bf153106d4fe523109e8ff2ab3e888fbb5f66e8739ef6aff360a6f14`。
packet 13/13、当前包 Tier-1 3/3、三包合并 22/22 均经 resource guard 非降级通过；
合并 guard SHA-256 为
`efd59389c943acb3120bcb24a1a17f9782fe06e73b7b254455ac800f3ddb16f0`，峰值
360.3125 MiB。最终只读 P0/P1 reviewer 独立重放 packet、Tier-1 projection 与正式
verifier，未发现 P0/P1。

本包不证明 natural runtime reachability、computed/RAM producer 穷尽、opaque callee
语义、结构化返回、holes 是 padding/free space、业务语义、编辑、回写或 relocation
安全，也不对 envelope 外相邻字节作分类。
