# MP2K 18-entry dispatcher（2026-08-29）

## 状态与边界

`rom-mp2k-dispatcher-v1` 已接受为 canonical artifact，目录为
`artifacts/rom-mp2k-dispatcher-v1/`。

本包只证明固定的 18-entry MP2K dispatcher、其 bounded Thumb CFG、实际消费的
table tail 与 literal；不声明自然运行时可达性、全局 caller 完备性、完整启动路径，
也不把相邻 CGB/PSG 包络一并闭合。两个 2-byte gap 仍保持 `unknown`。

## 1. Canonical identity

- canonical manifest SHA-256：
  `212c3849eb8ead7fd01c74f8ed8a1ae85b4f2324d966fa2234320a6b78882b48`
- payload SHA-256：
  `3ddac8d6c690af4850d74f7aeeee2a424f32c4108a7ebebd26c51f280672b23c`
- binary SHA-256：
  `83f220623fff3f5effb8bf6cd21b7e7ce8d543ab660d7fa721b8632bd26b3bd5`
- post-coverage SHA-256：
  `22f8f88ca0929468289b749cb94b4aaa4c47d7a53fa68fe10cb93c9a01816839`

## 2. Primary promotion

本包净晋升 102 bytes，共四个 promotion claim：

| 类别 | ROM 范围 | 字节 |
| --- | --- | ---: |
| dispatcher root code | `[0x09BCB4,0x09BCE2)` | 46 |
| table tail | `[0x09BD24,0x09BD30)` | 12 |
| handler code | `[0x09BDC4,0x09BDEC)` | 40 |
| consumed literal | `[0x09BDFC,0x09BE00)` | 4 |

以下两个间隙各 2 bytes，仍为 unknown：

- `[0x09BCE2,0x09BCE4)`
- `[0x09BDFA,0x09BDFC)`

五个既有 owner 范围合计 238 bytes，只作为 provenance，不计入本次 primary
promotion：

- `[0x09BCE4,0x09BCE8)`：4 bytes（`candidate_050`）；
- `[0x09BCE8,0x09BD24)`：60 bytes（`candidate_051`）；
- `[0x09BD30,0x09BDC4)`：148 bytes（`cfg_0770`）；
- `[0x09BDEC,0x09BDFA)`：14 bytes（`cfg_0771`）；
- `[0x09BE00,0x09BE0C)`：12 bytes（`cfg_0772`）。

历史 `candidate_027` 的 `rejected/crosses_canonical_table_boundary` 状态保持不变。

## 3. Binding 与 bounded CFG

initializer binding：

- literal occurrence `[0x09ADD8,0x09ADDC)` 的值为 `0x0809BCB5`；
- load 位于 `0x09AD40`；
- store 位于 `0x09AD42`；
- 写入 `0x03007540`，即相对 `0x03007520` 的 `+0x20` 字段。

dispatcher：

- root：`0x0809BCB4`；
- `cmp r5,#0x11` 位于 `0x09BCD2`；
- unsigned `BLS` 位于 `0x09BCD4`；
- 默认分支位于 `0x09BCD6`，目标 `0x09BE06`；
- terminal `MOV PC,R0` 位于 `0x09BCE0`；
- 18-entry ordered u32 table：`[0x09BCE8,0x09BD30)`，域为 `0..17`；
- opaque external BL：`0x09BDF4 -> 0x09C118`；
- structured return：`0x09BE0A`。

完整 bounded CFG 为 129 instructions / 260 code bytes / 36 blocks / 65 internal
edges / 1 external edge / 1 structured return / 0 frontier，并解析 18 条 dispatch
edge。完整 literal projection 为 8 bytes；其中 table-base literal 已有 owner，本次只
新增 4-byte consumed literal。不得把 238-byte owner provenance 或 producer
provenance 误报为本次 promotion。

## 4. Coverage 与正式证明

接受后的 ROM coverage 为：

- classified：`6,124,601 / 6,291,456`（`97.3479%`）；
- unknown：`166,855`（`2.6521%`）；
- claims：`14,507`；
- segments：`16,617`。

相对 dispatcher 前状态，净变化为 classified `+102`、unknown `-102`、claims
`+4`、segments `+3`。`semantic_classification_complete` 仍为 `false`。

正式报告：

- report：
  `build/experiments/active/mp2k-dispatcher-proof-20260829/formal-r1-report.json`
- report SHA-256：
  `3321709fa8440c8857d895b1cb467a3959989be0cc639abfe439bdb91e43ddc0`
- guard SHA-256：
  `b6e177ccff24a0cb19ad6e500968c4905bae3a0758abd466a2174cfd4bf8d036`
- proof spec SHA-256：
  `823e1b23940044a60fda275772f04e0cef05bf88a5fdd8fe024f53aa17092efa`
- formal / coverage auditor SHA-256：
  `1562de7b02fc781b79ede13a29a03137a02082ff2aa59b3ec212b90ae797104b` /
  `ea5f1ad59d783c2cd75c1c7eb380c0eacd1c7001532a145e39949ba22f47824f`
- 87/87 唯一结构化 contract 通过，其中 ROM byte gate 77/77、bank contract
  10/10，bad=0；proof spec 的 gate 配置总数为 88；
- elapsed `3,077.844030` 秒，peak RSS `638.47265625 MiB`，`degraded=false`；
- `complete=false`、`claim_status=incomplete`、175 blockers，符合当前未完成事实。

## 5. Reproduction

```text
python3 -I -S tools/verify_rom_mp2k_dispatcher.py \
  artifacts/rom-mp2k-dispatcher-v1 --root .
```

全局正式审计仍必须使用共享 heavy lock 串行执行；上述正式报告是本里程碑已经完成的
唯一收据，不得为了读取状态重复运行。
