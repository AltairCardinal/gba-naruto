# 四包 CFG 依赖批次正式接入（2026-09-30，进行中）

本轮Goal为“推进逆向工程，直到完成或周额度只剩40%”。实时状态active，开始时账户
used43%／余量57%；本体唯一writer，未启动子代理、未提交、未push。
沿用固定direct producer、有限Thumb闭包、code→literal align4与有界dispatcher模式。
现有四包可直接复用，不另建decoder或语义扫描器；新增层只组合发布与账本接入。

## 输入与边界

- 逆向HEAD `0302f4685946d9fa97747cb9814ea9c83fd02df4`，所有既有未提交内容保留。
- 基准ROM SHA `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- 接入前canonical SHA `1c6af01a54f3522ba277a4744b5b821d53588b853b3e7755902c65431df584b6`，
  6,203,707 classified／87,749 unknown。
- 原四包及永久合同保持字节身份不变；新增发布合同冻结11份既有工具及四份合同，
  SHA `9f8390a6db4c32add3d723e57483f94b7f3d70cb5c483eb2cd6983818cd3fc6a`。
- 四包10/54/14/40B；21claims、118B，分为78 code、12 literal、24 alignment、4 table。
  不声明自然可达、opaque callee副作用、完整上游生命周期、编辑/重定位或可分配空间。

## TDD与验证

1. publication RED 4项：缺发布入口与canonical wiring；projection RED 2项：缺live投影。
2. 新publisher复用v21的held-dirfd文件写入与atomic no-replace primitive；候选与accepted
   两次独立验证后才发布，错误保留stage，不按可替换名字删除。verifier逐包复用原始独立
   raw verifier，冻结payload/report，并对合并claims的顺序、ID和不重叠重新验真。
3. 第一次GREEN首项通过，第二项被默认60秒idle timeout中断；原guard/log保留，不能
   冒充全部通过。重跑显式idle240秒，5/5通过，非降级、峰值232.1953125MiB。
4. 实际promotion合同额外RED暴露schema不匹配；改为复用现有PROMOTION_SCHEMA，
   随后既有promotion validator集成通过。未放宽现有准入规则。
5. 原包与新投影回归47/47通过，非降级、峰值534.3984375MiB。投影保持精确类型，
   并验证live upstream owner、每段current-unknown；已有owner或二次认领失败关闭。
6. canonical落盘RED：真实账本没有21条新claim；proof RED：正式证据没有新batch。
   这两项必须在真实重建及proof同步后GREEN，不能用118B算术代替。

## 已发布artifact，尚未正式验收canonical

实验`small-cfg-tier2/resume-20260930-v1`经现有experiment_workspace promote完成发布：
`artifacts/rom-small-cfg-dependency-batch-v1/`。

- manifest SHA `1fb38be9cacc64857d308fdb48dd750718ee12a69a5c990b9985538daf9b8ff3`。
- payload SHA `4420a02756dfc59f73e8e051440d174fafa590d62086e3812e96960f8ea0336d`。
- verifier SHA `013d4ca34c378d158e4e4673e7904a6253e4d78052743a30f333b2d75bf17fad`。

新验收实验`small-cfg-tier2/acceptance-20260930-v1`保留before canonical/proof及红绿日志。
coverage通过同一heavy lock启动，wall9000秒、idle7200秒、禁止degraded。唯一运行handle
记录于`resume-state.json`，恢复必须先poll既有handle/确认进程；静默不能作为重启依据。
当前仍待coverage落盘、canonical GREEN、proof同步和一次完整formal；不宣称净增已验收。

## 后续

canonical通过后再同步proof，添加四包结构化verifier合同并以真实输入摘要执行formal；
永久收据及路线图随最终结果更新。之后按AI索引和低脚本消费者簇继续，不回到已否决的
59EAE0 may-read扩张。AI旧8×0xA8标签本身也不能作物理表证明，消费者索引生命周期
和表尾交叠仍须独立闭合。

同轮等待期取得另一条writer锚点与数据簇入口，见
`notes/rom-ai-config-writer-preflight-20260930.md`及永久窗口收据。该预检promotion=0，
不计118B批次，不改变当前canonical。最新账户used44%／余量56%。

本轮为离线逆向工具，入口为`tools/export_rom_small_cfg_dependency_batch.py`与
`tools/verify_rom_small_cfg_dependency_batch.py`；成功产出固定JSON，错误返回非零，
不提供游戏页面或修改ROM玩法。

## 验收清单

- [ ] 运行batch verifier → verified=true、118B/21claims，重复输出一致。
- [ ] 查看真实canonical → 新batch21claims、旧primary owner保留、三个未证明洞仍unknown。
- [ ] 查看新的formal → 新结构化合同真实执行通过；global incomplete仍如实保留。
- [ ] 核对永久manifest和guard → 哈希吻合、exit0、非降级。

## 真实canonical完成，formal运行中（2026-09-30 12:38 UTC）

上述“尚待重建”阶段已由真实落盘取代。coverage guard正常结束、exit0、非降级，
峰值425.63671875MiB；report verified=true、errors=[]、global语义完成仍false。
现在为6,203,825 classified／87,631 unknown、16,912 claims／18,675 segments。
CFG Thumb173,136B、4,064 primary claims、55 kinds；四包净增118B/21claims。
canonical SHA `b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2`，
proof SHA `465a13104b6c9a6d0ea418ca513dd0be732438634f1124a3a531c893b11db568`。
新canonical/proof与历史回放共11/11测试通过，非降级；旧回放5项RED显示旧批次
错误依赖最新账本，现改为SHA固定的历史coverage-after快照，保留原收据及所有旧分母。
新的固定118B验收独立检查live canonical，live proof测试仍绑定真实摘要及assertions。
格式检查和改动Python源码编译通过。永久canonical收据位于
`notes/evidence/rom-small-cfg-batch-canonical-20260930-v1/`，状态formal_pending。

完整formal已启动且只运行一次：session67131、同heavy lock、wall9000／idle7200，
可信spec SHA如上。恢复先读`resume-state-after-canonical.json`并poll原handle，
不能因静默重启；完成后另存formal收据，不覆盖本阶段manifest。
本批不更改自然运行、实体硬件或bank穷尽语义，最终formal尚未出结果。

## 完整Tier-2验收完成（2026-09-30 13:18 UTC）

正式guard于12:38:33–13:18:16 UTC正常完成，exit0、非降级、峰值533.33203125MiB。
107/107实际执行verifier均contract_ok=true、exit0；ROM gate97/97结构化合同，
其coverage audit verified=true、errors=[]，真实summary与当前canonical完全一致。
新增batch verifier实际执行一次并通过；全局complete=false、claim_status=incomplete，
175 blockers与10/32 bank穷尽状态保持，不把本批验收解释为整个逆向完成。

永久formal收据`notes/evidence/rom-small-cfg-batch-formal-20260930-v1/`，report SHA
`5953aa753d4d35d21a4d7f4d399cf3a374027702399baba8db5cdc0ec22650ef`，manifest SHA
`1dfacd81c11913112548aaaae96f07a74928b2cf53909105f61109964609a5f0`。
收据RED先确认永久结果缺失；落盘后当前canonical/proof及永久formal集成3/3通过。
validation-receipt单独绑定被测试manifest与GREEN log，未改早期publication/canonical
阶段manifest或任何历史结果。输入proof SHA仍465a1310…1db568、canonical b568db6f…cf06d2。

当前无heavy job；完整验收后的恢复状态为run内`resume-state-after-formal.json`。
后续packet依旧先一级积累，不为这118B重复full coverage/formal。AI新发现详见
`notes/rom-ai-renderer-script-dependencies-20260930.md`：67158是命令解释器，已有
两条32B/4B脚本可复用；postplanner指令membership尚未证明。Goal保持active。
