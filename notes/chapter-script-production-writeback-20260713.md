# Chapter script production writeback（2026-07-13）

## 结果

章节脚本已接入正式 `tools/build_mod.py`，不再依赖诊断 probe 的固定零区。
`tools/import_chapter_scripts.py` 支持直接语义 commands，或对 immutable-base 范围先
严格 decode 再 byte-exact encode。所有 entry 会先完成以下验证，之后才返回构建计划：

1. table/scenario 唯一且 scenario 位于 `1..55`；
2. 表内基准指针与 spec 完全一致；
3. payload 通过严格 chapter codec；
4. `0x5F8000..0x5FFFFF` 完整分区仍为 `0xFF`；
5. 四字节对齐后的全部 payload 不越过分区；
6. 每个 payload 与 pointer redirect 都携带 immutable-base precondition。

构建在内存中应用整个安全计划，只有全部 patch 通过后才写输出文件，因此不会留下
“payload 已写但指针失败”或相反的部分 ROM。旧 `rom_chapter_flow_*` DB 镜像仍可刷新
和检查，但改动 pointer 会收到明确错误，不能绕过 semantic importer。

## 分区

- `0x5E0000..0x5EFFFF`：DB audit；
- `0x5F0000..0x5F7FFF`：variable dialogue；
- `0x5F8000..0x5FFFFF`：chapter scripts。

三者均在已审计的尾部连续 `0xFF` 区内，所有权不重叠。

## 实际构建证据

启用的 `sequel/content/story-b/scenario-39-relocation.json` 对运行时已验证脚本
`0x08031281..0x0803142E` 做语义往返后生成：

- payload：file `0x5F8000`，长度 430 (`0x1AE`)；
- pointer slot：file `0x60DF0` (`0x60D54 + 39*4`)；
- old pointer：`0x08031281`；
- new pointer：`0x085F8000`；
- 输出 ROM SHA-256：
  `2b482adc72e183bc3eaacc0f25473fc29f8130d2ebca930d4dd5045a2483a1ff`。

构建报告把两项均标为 `game_effective`、`overlap_disposition=unique`。直接跟随输出
ROM 指针可读到与基准脚本完全相同的 430 字节。

## Relocated runtime closure

`tools/build_relocated_chapter_runtime_probe.py` 在正式 importer 计划上只叠加已有的
alternate selector/dispatch trace hook。诊断 ROM SHA-256 为
`392bfcd2570be007d0413da5d9d5d626d245ee6e911d5f3aebb83ec3d9443b50`。

从 `alternate-mission-selection.ss9` 使用 keyboard 序列
`A, Down, A, A×7`，第 10 步得到：

- selector hit `1`，scenario `39`，selected pointer `0x085F8000`；
- dispatch hit `25`；
- terminal cursor `0x085F81AD`，live/ROM bytes 均为 `00ffffff`；
- 八项 evidence checks 全部为 true；
- outcome `verified`，reason `alternate-script-terminated`。

完整结果 SHA-256 为
`eb57952ebf414d03495349972a51dbce8abc646600dc8d2ce802d7e98db004ba`，截图为
`0932561f5032911e543f8474564832d55533f23f68f05201ae90164cf567c869`。精简证据存于
`artifacts/runtime-checkpoints/chapter-relocated-runtime-evidence.json`。这同时证明
正式 allocator、guarded pointer、relocated payload 与真实 interpreter 消费链。
