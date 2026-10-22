# 战斗特效 group 3/18 直接入口运行时闭环（2026-08-02）

## 结论

此前受控 binder 批次中保持负例的 group 3 与 group 18，现已通过各自的直接
selector→spawn 入口形成稳定 task 和三相 OAM 提交事务。与既有已观察/受控组取并集后，
18 个战斗特效组均至少有一条受控或自然运行时资源/task 身份证据，即技术子分母
`18/18`；这不改变 production 自然最终像素 A/B 的 `4/18`。

四个正例均从已验收的
`scenario-50-battle-15-escort-12hp-player-turn.ss9` 零输入恢复：

| case | selector | task | anchor | tile / palette |
|---|---:|---:|---:|---:|
| group 3 / sequence 3 / side 0 | 0 | 109 | `(136,80)` | `256 / 4` |
| group 3 / sequence 3 / side 1 | 0 | 109 | `(136,80)` | `256 / 4` |
| group 18 / sequence 7 | 0 | 109 | `(120,80)` | `768 / 12` |
| group 18 / sequence 18 | 0 | 109 | `(120,80)` | `768 / 12` |

四案均依次捕获 `renderer 0x08063328 → submit 0x08061126 → ack 0x080612AA`，
pending 为 `0→1→0`；renderer shadow 与旧 hardware 不同，submit 后 hardware
尚未改变，ack 后完整 1 KiB hardware OAM 等于 renderer shadow。

## group 3 失败根因

group 3 graphics 为 304 tiles / 9,728 bytes。旧探针错误沿用 group 18 的
`0x300..0x37F`，容量只有 128 tiles，因此 selector 返回 `0xFF`，spawn 不会产生目标
task。改用同战斗特效子系统其他 reset 点使用的受控窗口
`0x100..0x39F / palette 4..14` 后，side 0/1 均返回 handle 0。

这是容量 A/B，而不是自然调用者归属证明：group 3 自然函数
`0x0807F208..0x0807F284` 自身不调用 allocator reset；它先选择 sequence 5，再选择
sequence 3，并对 side 0/1 调 `0x08080108`。当前 wide window 只称为可复现的受控容量
重建，不冒充已找到 group 3 的直接自然 reset caller。

## side 与 palette 边界

group 3 两案使用非中心 `x=104`，task flags 分别为 `0x61009281` 与
`0xE100B2C1`，证明 side 会进入后续 task 状态。但输入 checkpoint 的 side 0/1 owner
`+2` 分别是 `1/0`，两案都会走 `240-x` 分支，因此 anchor 都是 `(136,80)`；本成果
不宣称左右镜像两个分支均已运行时覆盖。

group 3 的 9,728-byte graphics 在三相均逐字节一致；32-byte palette 的前 30 bytes
一致，最后两字节在 renderer 边界已被改写为 `01 00`，源为 `6C 2D`。group 18 的
3,584-byte graphics 与 32-byte palette 均完整一致。成果明确保留 group 3 palette
尾字差异，不把 30/32 冒充完整运行时 palette 等价。

## 可复算成果与资源安全

- artifact：`artifacts/battle-effect-direct-spawn-runtime-v1/`
- verifier：`python3 tools/verify_battle_effect_direct_spawn_runtime.py artifacts/battle-effect-direct-spawn-runtime-v1`
- 51 个来源成员被压成约 1.27 MiB 的确定性 `raw-batch.tar`；只保留 12 份原始
  savestate、phase 元数据、profile/audit/guard 与一份窄窗口负例，不重复提交每相的
  VRAM/PRAM/task/OAM dump。另保留窄窗口原始完成态 run inventory/metadata，不提交
  两份重复的 6 MiB probe/staged ROM；verifier 从 inventory 哈希和重建 ROM核对它们。
  verifier 直接从 savestate 重建运行时内存域。
- `18/18` 并集不是本 artifact 内的硬编码自证：verifier 会先独立复验既有 controlled
  15 组和 group 15 两份父 artifact，再与本次 groups 3/18 取并集；两份父 manifest、
  父 verifier 及完整 phase-runner 传递依赖均进入哈希分母。
- 每个正例的 batch/profile/audit/guard/done 会交叉核对输入快照、探针 ROM、profile、
  toolchain、mGBA binary/source commit、capture script、staged ROM、运行 ID 和清理状态；
  窄窗口负例还由固定哈希的 completed-run inventory 绑定输入、profile、audit、guard、
  staged ROM、mGBA binary、capture script 和 run ID。更新归档字段或完成态 ledger
  并重签 artifact 的负测试都会被拒绝。
- 四次 mGBA 均由 heavy guard 完成，非 degraded 且无 PGID/listener 残留。sequence 7
  的有效采样峰值为 74.2578125 MiB；其余三次约 0.17 MiB 属于短运行采样遗漏，已从
  内存统计中排除，不能作为真实峰值。

后续 group 3 与 group 18 都已闭合 production relocation 下的受控最终像素写回；
仍未完成的是 group 3 自然 allocator 上游、非镜像分支与 palette 尾字生命周期，
以及 group 3/18 的自然玩法入口和自然最终像素 A/B、完整动画、音频耦合与实体 GBA。
