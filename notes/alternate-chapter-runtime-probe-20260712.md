# Alternate chapter table runtime probe (2026-07-12)

## Objective and method

Runtime-close table `0x60D54` without changing the scenario ID or interpreter.
`tools/build_alternate_chapter_runtime_probe.py` changes the `beq` at
`0x0808F5A4` to a Thumb NOP, forcing the existing selector to fall through the
alternate-table path. It also reuses the opcode tracer at `0x08097C78`.
Only the two-byte selector branch, four-byte hook, and checked zero-filled
diagnostic stub may differ from the immutable base ROM.

## Attempts and result

Probe ROM SHA-256:
`c98e2d2c02e4e0235e14e584a5a423a20a079db897b85fa09adea7ef0a93e6a4`.

Two automated routes were attempted:

1. 250 dialogue confirms ended in the pre-selector Kakashi conversation.
   Result SHA-256 `33bb3160704fe4bcda76dccf9f3642e54ebf442e439a476a73177b5cc4943233`.
2. 700 faster confirms reached the character page, but the fixed tail sequence
   did not exit it. Result SHA-256
   `d3ae1c436b4f0c1516a2cf613b0bdcae279db380e0415f3edcd6621d01026a51`;
   screenshot SHA-256
   `4897c8f158e6e7c1d5280ad44c9812438eed8166c4e998a93b95bf5912a5e8d0`.

Both runs had opcode hit count 0, battle ID 0, empty unit memory, and empty map
runtime. Therefore neither executed `0x0808F544`, and neither is evidence for
or against alternate table consumption. The visual classifier called these
screens `battle-map`, but the strict memory gate correctly rejected them.

## Next acceptance gate

Resume at or reproducibly reach the character page, exit with a verified B
transition, select prebattle “start mission”, then require all of:

- tracer hit count > 0;
- captured script pointer equals the pointer in `0x60D54[scenario_id]`;
- captured opcode bytes belong to that script;
- resulting chapter/battle state is nonzero or the alternate script terminates
  through another explicitly decoded opcode.

Until that gate passes, `story-b` remains `code_verified`.
