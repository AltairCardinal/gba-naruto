# Chapter-flow runtime consumer chain (2026-07-12)

## Result

The real scenario/chapter flow tables are 56-entry script-pointer tables at
file `0x60C74` (primary) and `0x60D54` (alternate), not the five late-ROM
resource-descriptor slices formerly labeled `story*`.

## Static chain

`0x0808F544` receives a scenario ID and indexes it as `id*4`:

- when chapter state `0x020311D4 + 0x18` is zero, base `0x08060C74`;
- otherwise, base `0x08060D54`.

Entry 0 is null in both tables; entries 1..55 are ROM script pointers. The
selected script is passed to interpreter `0x080977B8`. Within the interpreter,
the handler at `0x08097C6C` consumes the three-byte instruction `0x1A`:

1. `r7[0]` is opcode `0x1A`;
2. `r7[1]` is written to chapter state `+0x16` (`0x020311EA`);
3. `r7[2]` 非零时把 `r7[2]+1` 写入状态 `+0x18`；
4. `0x0808CC80` derives state `+0x14` from that ID;
5. handler 最终将 cursor 增加 3；later `0x0808F618` copies `+0x16` to battle
   control `0x02026805`。

因此样本窗口 `1A 28 02 00` 必须解码为 `SetBattle(40,2)`（前三字节）随后独立
`End`（第四字节），不能把 `00` 吞成 `0x1A` 的参数。`End` handler `0x08097916`
在 call depth 为零时退出整个脚本，非零时弹出解释器内部返回栈。

## Live first-battle evidence

`tools/build_chapter_script_probe.py` replaces only the two instructions at
`0x08097C78..7B` with a BL to a zero-filled diagnostic stub. Those instructions
are inside the `0x08097C6C` handler and perform the battle-ID write. The stub preserves
the original write and records the live `r7` pointer and command bytes at
`0x0203FFB0`.

The standard WASM route, using the strict battle-arrival gate, recorded:

- script cursor `r7 = 0x08031070`;
- bytes `1A 28 02 00`;
- chapter/battle operand `0x28` (40);
- hit count 1;
- final `0x02026805 = 40`;
- strict battle map arrival with map runtime `[36,44,9,22]` and formation
  group 40 / variant 0.

Pointer backtracking shows `0x08031070` is inside the script starting at
`0x08031020`, and primary table entry 39 at file `0x60D10` points to that
script. The resulting proven chain is:

```
scenario 39
  -> 0x08060C74[39] = 0x08031020
  -> opcode 0x1A at 0x08031070, operand 40
  -> 0x020311EA = 40
  -> 0x0808F618
  -> 0x02026805 = 40
```

Artifacts:

- probe ROM SHA-256 `3d9ebca68ace8a52a9a9d48edb8f71883014b75b003ca21ed22f9841d7cbbae4`;
- result SHA-256 `51ed2851bdcd33a82c0afebd27e192a10bb0405528a69d7c169fcd8a6d902cb2`;
- screenshot SHA-256 `e4b6bb23b7c4b76f1d2ab83c4e749737029fd6308aad1d9215f31b45835bf8b5`.

## Live alternate-table evidence

The first alternate probe incorrectly hooked only opcode `0x1A`. Scenario 39's
alternate script `0x08031281..0x0803142E` has no `0x1A`, so the corrected probe
captures selector `r4/r0` at `0x0808F5CC` and every interpreter dispatch at
`0x080977D8`.

Starting from the mission-selection checkpoint, the live run recorded:

- selector scenario 39 and `0x08060D54[39] = 0x08031281`;
- 25 dispatches, ending at cursor `0x0803142E`;
- terminal bytes `00 00 1B 04`, equal to ROM;
- opcode `00` returning normally through `0x08097916 -> 0x08097E34` at zero
  call depth, explaining why this dialogue-only script creates no battle ID.

The compact result is
`artifacts/runtime-checkpoints/alternate-story-b-runtime-evidence.json`.

## Repository changes

- `tools/extract_chapter_flow_tables.py` extracts both 56-entry tables.
- `story/bank.json` now represents the primary table and is runtime verified.
- `story-b/bank.json` represents the alternate table and is runtime verified.
- `story-c`, `story-d`, and `story-e` remain disproved tombstones for their
  former false identities.

Semantic script editing is still disabled. Lossless pointer writeback requires
new mirrors keyed by exact table/index/base pointer; old `rom_story_b..e`
mirrors must not be reused because they describe the revoked addresses.

## 2026-07-13 最小语义 codec

新增 `tools/chapter_script_codec.py`，严格白名单仅包含已经闭合的：

- `00`：End / interpreter return；长度 1；
- `1A <battle_id> <mode>`：SetBattle；长度 3。

codec 对截断、End 后尾随字节、未证明 opcode，以及 jump table 中 `0x24..0x31`
共享 invalid handler 的保留 opcode 全部显式拒绝。它能 byte-exact round-trip
`1a280200`，但尚未接入生产 allocator 与 pointer+payload 原子回写，所以不能据此宣称
章节编辑器已可安全写入任意脚本。

`tools/build_chapter_semantic_probe.py` 随后把 codec 输出放到已审计零区
`0x0809E800`，只把 primary scenario 39 指针从 `0x08031020` 改到该地址，并安装按
scenario 39 / script range 过滤的 preserving selector/dispatch tracer。用
`alternate-mission-selection.ss9` 仅输入一次 A，运行结果为：

- selector hit 1，scenario 39，selected script `0x0809E800`；
- dispatch 恰为 2 次，末 cursor `0x0809E803`，ROM/live opcode 均为 `00`；
- `0x020311EA` 从 39 变为 40，证明 `SetBattle(40,2)` 的非零状态因果；
- 通用 driver 以 `semantic-script-terminated` 正常返回 verified；
- 该短路线停在对话画面，battle control 尚为 0，未宣称 strict battle arrival。

compact evidence：
`artifacts/runtime-checkpoints/chapter-semantic-codec-evidence.json`。重要新增范围：
诊断脚本 `0x0809E800..0x0809E81F`；primary 指针 slot file `0x60D10`。
