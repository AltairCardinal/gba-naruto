# 运行时 BG 图层静态来源目录（2026-07-30）

## 结论

`artifacts/runtime-layer-static-provenance-v1/` 将全部 91 个 tracked `.ss9`
checkpoint 中启用的 Mode 0 BG 图层，与仓库已有的六类静态图像资产逐字节比对。
91 个 checkpoint 共包含 199 个启用图层观测；按完整 BG 状态去重后为 89 个状态、
196 个图层。每个图层都进入三态目录，没有静默遗漏：

| 分类 | 数量 | 含义 |
|---|---:|---|
| `exact_static_source` | 28 | graphics、loader-normalized tilemap、palette 三域均满足严格匹配 |
| `partial_static_source` | 107 | 只有一或两个字节域匹配，只保留候选，不签发来源身份 |
| `unidentified_runtime_payload` | 61 | 六类已登记静态资产中没有任何精确字节域命中 |

28 个精确来源只落在三个已证明的静态项：

- `bg-resource-canvases-v1/entry-01`：16 个运行时图层；
- `bg-resource-canvases-v1/entry-09`：2 个运行时图层；
- `world-map-backgrounds-v1/page-00`：10 个运行时图层。

代表性结果包括：

- `scenario-42-postbattle-world-map.ss9` BG0 精确对应 world-map page 0；
- `scenario-41-turn-1-complete.ss9` BG0 精确对应 regular BG entry 1；
- `scenario-46-client-dialogue.ss9` BG0 精确对应 regular BG entry 9；
- `scenario-41-player-turn.ss9` BG0 只有 map graphics 部分匹配，不提升为精确身份；
- 同一 checkpoint 的 BG3 没有已登记静态字节域命中，保持未识别。

## 固定分母与静态候选

静态注册表包含 345 个候选，全部绑定各自上游 manifest SHA-256：

| 静态族 | 候选数 |
|---|---:|
| `bg-resource-canvases-v1` | 12 |
| `map-canvases-v1` | 61 |
| `scene-visual-packs-v1` | 9 |
| `story-visual-layers-v1` | 24 |
| `tile-assets-bg-v2` | 236 |
| `world-map-backgrounds-v1` | 3 |

匹配器不把文件名、画面相似度或人工场景猜测作为证据。它从 ROM 或上游 artifact
重新取得静态 payload，并与 `.ss9` 中的 VRAM/PRAM/寄存器状态比较。

## 严格匹配契约

精确来源必须同时满足：

1. bpp 与 text-BG 布局兼容；
2. graphics 完整字节串在 runtime charblock 中以 tile 边界出现；
3. 对 graphics 的全部重复 VRAM 位置逐一尝试，不固定采用第一次出现；
4. tilemap 的 H/V flip 一致，tile index 只允许一个固定 relocation delta；
5. 4bpp palette bank 只允许一个固定 delta；
6. 按 GBA screenblock 布局搜索 runtime tilemap 原点；
7. palette 要么完整 payload 相同，要么当前 tilemap 实际使用的非零颜色全部相同。

透明 color index 0 不参与“实际使用颜色”比较，但完整 palette 匹配仍覆盖它。这样可以
处理 loader 重定位和未使用 palette 槽变化，同时不会把仅有 graphics alias 的候选误报
为完整来源。

独立 verifier 没有导入 exporter 或其他 `tools` 模块；它自行解析 `.ss9`、LZ77、
六类静态 manifest、tilemap relocation 和 palette，并重建完整 payload 与 promotion
manifest。测试除正常重建外，还验证 classification、静态源 manifest 哈希和额外 artifact
文件篡改均会被拒绝。

## 证据边界

本成果只签发：

- 91 个已跟踪 checkpoint 的固定分母；
- 其中 196 个唯一状态启用图层的三态静态来源证据；
- 28 个三域精确来源及 107 个部分候选；
- 六类静态注册表、ROM、checkpoint、实现和测试哈希绑定。

它明确不签发：

- 61 个未识别 payload 的自然语言或 ROM 来源名称；
- 107 个部分匹配候选的唯一来源身份；
- 未跟踪游戏状态的视觉覆盖；
- camera/scroll writer 调度、跨帧切换和动态 palette transform；
- 最终 screen composition 或实体 GBA 像素等价。

此前 `runtime-bg-composites-v1` 中“static regular-BG entry 到每个 runtime layer
的来源身份未签发”是该旧 artifact 自身的正确边界；本成果以独立 artifact 对已跟踪
状态追加来源目录，不改变旧产物内容或把观察范围外推到全游戏。

## 可复现与资源占用

```sh
python3 tools/export_runtime_layer_static_provenance.py \
  --root . \
  --output-dir artifacts/runtime-layer-static-provenance-v1

python3 tools/verify_runtime_layer_static_provenance.py \
  --root . \
  --artifact artifacts/runtime-layer-static-provenance-v1

python3 -m unittest tests.test_export_runtime_layer_static_provenance -v
```

正式导出与验证均通过 `tools/run_guarded.py` 取得共享 heavy lock：

- 正式导出耗时约 14.5 秒，峰值 tree RSS 31.34 MiB；
- 独立验证耗时约 12.5 秒，峰值 tree RSS 27.69 MiB；
- 9 项测试通过，包含三类篡改负例，峰值 tree RSS 40.31 MiB；
- 最终 artifact 只有 manifest 和 1.50 MiB JSON payload；
- 全过程未启动 mGBA，不产生新快照、模拟器进程或 ROM 改写。
