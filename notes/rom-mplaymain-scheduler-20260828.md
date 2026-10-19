# MPlayMain scheduler 静态闭包（2026-08-28）

## 结论

基准 ROM `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
中的 MPlayMain 固定 Thumb 指针、RAM callback slot 写入、SoundMain 间接消费链与
target-limited raw Thumb CFG 已按失败关闭合同验收。canonical artifact 位于
`artifacts/rom-mplaymain-scheduler-v1/`。

本包只晋升两个接入前完整 unknown 范围：

- `[0x09A42C,0x09A684)`：600 字节 bounded Thumb instruction；
- `[0x09A688,0x09A694)`：12 字节 PC-relative-LDR consumed literal。

`[0x09A684,0x09A686)` 两字节 `BX r3` veneer 保留既有
`cfg-thumb-0752-09a684` owner，只作为 opaque-stop provenance；
`[0x09A686,0x09A688)` 两字节继续 unknown。净晋升为 612 字节。

## 任务模式与入口证据

任务模式是“固定 ROM Thumb 函数指针经 RAM callback slot/间接 thunk 绑定后的
target-limited raw Thumb CFG 闭包”。该模式要求同时冻结：

1. 唯一精确 Thumb pointer literal `0x0809A42D`（ROM `0x09B1F0`）；
2. MPlayOpen 的 slot writer：逻辑 `SoundInfo+0x20` 写入 callback，`+0x24` 写入参数；
3. SoundMain 的 `SoundInfo+0x20` load、`0x09A1AE: BX r3` thunk；
4. MPlayMain 内递归 callback load 与已有 owner `0x09A684: BX r3` opaque stop；
5. 固定 ROM、历史 coverage、既有 boot/CFG owner、producer/consumer 指令与所有
   promotion 字节身份。

全 ROM 中精确字节 `0x0809A42D` 只出现一次，且没有 direct BL 指向
`0x09A42C`。这只证明固定 ROM literal→slot→thunk 的结构绑定；computed value、RAM
copy、调用先后、动态 slot 值、callback 生命周期与自然可达均未穷尽。

## CFG 与 literal 分母

独立 worklist 结果固定为：

- 289 条 Thumb 指令 / 600 instruction bytes；
- 81 blocks；
- 117 internal edges；
- 12 external/opaque edges，7 个唯一 external target；
- 4 个 literal consumer、3 个 literal word、12 literal bytes；
- 1 frontier、1 return、0 个本包声称已解析的 raw indirect PC；
- code SHA-256：
  `0603b7d7cbd42674284783b638188595f07155ec8942d0ef96137bec36b1b86c`；
- literal SHA-256：
  `d1b4099db32ee07e0e14f3d78937fcdda9ee750b9b3128d23d4d5e56df04c764`；
- packed promotion SHA-256：
  `8ca6a2f02cd27d46b9d0e9dbae2491672f23702ee2230eb73fc460759ef14955`；
- range-vector SHA-256：
  `a8e11002ba5439c3d758e03faa1850a686e749cbe3230496f871329283300b4d`。

旧 `[0x09A42C,0x09A5CA)` 414-byte 包络不是闭合 CFG；至少有可达分支逃逸到
`0x09A5CA`、`0x09A5CC` 与 `0x09A674`。旧结论已作废，禁止复用。

## TDD、artifact 与独立验证

核心 TDD 先因 exporter/verifier 缺失而 RED，后由以下实现 GREEN：

- `tools/export_rom_mplaymain_scheduler.py`；
- `tools/verify_rom_mplaymain_scheduler.py`；
- `tests/test_export_rom_mplaymain_scheduler.py`；
- `tools/verify_rom_mplaymain_scheduler_bundle.py`；
- `tests/test_verify_rom_mplaymain_scheduler_bundle.py`。

核心 12 项测试受守卫通过；immutable bundle wrapper 的 6 项测试通过，并证明它不读取
live coverage。wrapper 只为已接受 artifact 注入历史 coverage receipt，当前所有权仍由
full coverage auditor 独立验证，从而避免历史 artifact 与新 coverage 相互重签成哈希环。

关键身份：

- manifest：`43399803451c393722522c9d2a363736541c34c37dd03d3cb2c1e292ed0b8f5d`；
- payload：`31bc026a8c83b3bf4af06746de2990a658bb86954a5aae31c45d63d68cf44f78`；
- exporter：`366c4e41db80c797bd01f36477a67243ac08f4d20d71e596c1332f273deed18d`；
- independent verifier：
  `c064fc6a576a518cbd825630babc40d1c2dab2d369846078c3950b68748a2c2a`；
- bundle verifier：
  `caa5e042401ed06f1f7e9978e10c5e487c643e909c50a274b75aed32ce557c06`。

## Coverage 与 formal proof

接入后的 canonical coverage 为：

- classified：6,122,489（97.3143%）；
- unknown：168,967（2.6857%）；
- claims：14,484；
- segments：16,593；
- coverage SHA-256：
  `2b93df18a7815cb966dad707dfa2ad606049911ae1772a341b57cf2347b58e3b`；
- coverage auditor SHA-256：
  `ddfb21b28bdf65fff2b5c5de7fb1a891a7aefea0191ee3d31f24932326bfa8dc`。

完整 proof 单测经守卫退出 0，非降级，峰值树 RSS 427.0859375 MiB。正式报告位于
`build/experiments/active/rom-mplaymain-scheduler-v1/codex-parent-r1-20260828/`：

- proof spec SHA-256：
  `748efea79aa849e0cece4331ada95d3cfb22e3934a8bde6c9b97226922ec5c7e`；
- formal report SHA-256：
  `34c390e98f367a2e885700fe95db32db9a2736ae8669cfe139524c576d2d9e1d`；
- guard SHA-256：
  `8ed618bc7b648046cb3c01f3ca3b009f31143b6b74a1bb99a6bf43711de2d906`；
- 82/82 唯一 structured contracts 均 `exit_code=0`、`contract_ok=true`；
- ROM byte gate 72/72、bad=0；
- 守卫耗时约 45.5 分钟、峰值树 RSS 611.7734375 MiB、非降级。

全局报告仍为 `complete=false`、`claim_status=incomplete`、175 blockers，这是正确结果。

## 明确未声明

本包不证明动态 callback target/RAM 值、callback 生命周期、自然运行时可达、全局
caller/code/indirect/computed producer 分母、调度业务语义、编辑/写回/重定位安全、
free 或 allocatable space。

## 后续状态

本节原定的下一首选 SoundMain relocated mixed-ISA source 已于同日完成，不再是待办：

- source envelope `[0x099E10,0x09A1AE)` 接入前完整 unknown，共 926 字节；
- 必须按运行地址 `0x030077C8` 解码，不能按 ROM PC 解码；
- 初步候选为 916 code bytes、8 consumed literal bytes、三段 2-byte alignment gap，
  并以既有 `[0x09A1AE,0x09A1B0)` return veneer 作 opaque stop；
- CpuSet 实际搬运窗口为 `[0x099E10,0x09A210)` 1,024 字节，不能整窗冒充 code；
- 在 producer denominator、两套 mixed-ISA decoder、四次模式切换与 gap 策略冻结前，
  不适合直接交给 Luna max 实现。

最终只晋升 916-byte code、8-byte consumed literals 与三个独立 2-byte align4 gap；
完整结果见 `notes/rom-soundmain-relocated-cfg-20260828.md`。当前下一包改为 handoff 第
17 节的 `rom-m4a-initializer-chain-v1` 518B。
