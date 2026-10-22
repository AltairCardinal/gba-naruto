# BG 场景选择目录完整导出（2026-07-29）

## 结论

`artifacts/bg-scene-selection-v1/` 将已导出的 12 张 regular BG 画布与 ROM 中所有
已识别的选择机制连接起来，没有复制 PNG。成果包含：

- 47/47 个 battle header 的 `+0x1C` 背景 ID；
- primary/alternate 两张 56 项章节指针表的完整 CFG 遍历；
- 6 个唯一 opcode `0x1E` 背景选择记录；
- `0x08088348` loader 的 4 个直接 BL caller；
- `0x0808F4D4` 选择 wrapper 的 5 个 BL caller；
- 每个有效 ID 到 `bg-resource-canvases-v1` 画布路径和 SHA-256 的绑定。

这闭合的是“运行时如何选择表项”，不等于 12 张图都已有自然语言场景名，也不包含
滚动、其他 BG/OBJ 层或最终画面合成。

## Battle header 选择

47 个 `0x20` 字节 header 位于 `0x0853D910..0x0853DEF0`，选择公式为：

```text
entry_id = u8[0x0853D910 + battle_id * 0x20 + 0x1C]
```

全部 ID 均在 1–7，分布为：

| entry ID | battle 数 |
|---:|---:|
| 1 | 23 |
| 2 | 3 |
| 3 | 5 |
| 4 | 4 |
| 5 | 1 |
| 6 | 1 |
| 7 | 10 |

`battle-headers.json` 保存每个 battle ID、header/selector 地址、画布路径和画布哈希。

## 章节脚本遍历

章节根来自 primary `0x08060C74` 和 alternate `0x08060D54`，各 56 项且 index 0
为空哨兵。遍历不是原始字节搜索，而是按解释器 `0x080977B8` 的真实记录边界和控制流：

- 110/110 个非空槽，98 个唯一根；
- 14,199 个唯一可达指令节点；
- 42 个 opcode `0x06` 动态分派节点；
- 0 个解析失败；
- 6 个唯一 opcode `0x1E` 记录。

文本边界分别复现 `0x0806626C` 和 `0x080960F0` 的 token 规则。前者对
`0xA0..0xFF` 双字节候选还会查询 `0x0853D644` 的 31×8 glyph range 表，不能简单把
所有高位字节一律当作双字节。

opcode `0x06` 的 handler 以 `0x0200A880` 为索引直接读取指针，但没有上界检查。
本 ROM 的 42 个可达记录均明确包含两个连续有效指针，因此目录只枚举结构契约中的
index 0/1；索引大于 1 属于会越过记录的运行时不变量破坏，不冒充第三分支。

## Opcode `0x1E` 命中

dispatch table `0x080977F4[0x1E]` 指向 `0x08097CE4`。handler 从 `+1` 读取 u8，
调用 `0x0808F4D4`，再经 `0x08097954` 前进 2 字节，所以记录长度严格为 2。

| 地址 | bytes | input | entry | 根 |
|---|---|---:|---:|---|
| `0x0804435F` | `1E 00` | 0 | 1 | primary 51 |
| `0x080446F0` | `1E 33` | 51 | 10 | primary 51 |
| `0x080459F4` | `1E 07` | 7 | 2 | primary 51 |
| `0x08046118` | `1E 07` | 7 | 2 | primary 51 |
| `0x08047F40` | `1E 1E` | 30 | 7 | primary 53 |
| `0x08048087` | `1E 35` | 53 | 12 | primary/alternate 53 |

wrapper 的代码对 input 0–49 都按 battle header 公式读取，但权威表只有 47 项，
所以只有 0–46 属于合法 header。input 47/48/49 会越表并分别读出 entry
96/36/214；对 50–54 才改用 `entry_id = input_id - 41`，连接 8bpp ID 9–13。
input 大于 54 又会产生 ID 14+。loader 没有边界检查，因此完整安全域是不连续的
`0..46 ∪ 50..54`；目录显式保存 47–49 的实际危险读值。

## 调用链与覆盖边界

全 ROM Thumb BL 扫描证明 loader 只有四个直接调用点：

- `0x0807AAA6`：battle header；
- `0x0808F522`：wrapper 结果；
- `0x08091716`：固定 ID 9；
- `0x080930D6`：固定 ID 1。

wrapper 只有五个 BL caller：`0x0808A596`、`0x0808A648`、`0x0808F588`、
`0x08097038`、`0x08097CEC`。其中最后一个是章节 opcode；`0x08097038` 重新应用保存
在状态 `+0x17` 的上次 input；其余三个转发各入口函数参数。

静态 header、章节命中和固定调用实际观察到 ID 1–7、9、10、12，共 10 项。ID 11/13
只由 wrapper 的合法 input 52/54 域证明可选择，当前 ROM 没有静态章节记录使用它们。
artifact 明确区分“合法可选择”与“静态已观察”，不为 ID 11/13 编造场景语义。

## 哈希与验证

| 证据 | SHA-256 |
|---|---|
| battle headers `0x0853D910..0x0853DEF0` | `977b4393a2c5d37124d09e772de42f11d2d9abff9ec832d1160aeeb194a6566c` |
| primary pointers | `f6c872afd0b653ae2e0e04407bdbc059719eb823801d165e22a1d7e5c98aa099` |
| alternate pointers | `767308a8e78947f7795c61965155d27925265327466c9df9d5d547b2f0368b5c` |
| opcode `0x1E` handler | `bffbff149e2ecf3deb9309a48123cffe724652121f6d4699720dc23b1d8f25dc` |
| selection wrapper | `5a5e08c007d48247ab0f8cce8c1e6c9b86c0a43c4fd8fd19d364790ac0dc71dd` |
| loader | `1d581ddbdfb89f17de5b5e52fd1b34d9952fcaddf8e4f24f1f86982facf6db27` |

```sh
python3 -m unittest tests.test_export_bg_scene_selection -v
python3 tools/verify_bg_scene_selection.py \
  --root . \
  --artifact-dir artifacts/bg-scene-selection-v1
```

独立 verifier 不导入 exporter 或其他 `tools` 模块；它从 ROM 重新解析两张根表、
文本 token、全部 CFG、BL callsites、47 个 header 和上游 PNG/hash，并拒绝 manifest、
三个目录文件或额外文件篡改。
