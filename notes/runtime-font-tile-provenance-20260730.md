# 运行时 BG 字体组件来源（2026-07-30）

## 结论

`artifacts/runtime-font-tile-provenance-v1/` 对
`runtime-layer-static-provenance-v1` 中全部 61 个
`unidentified_runtime_payload` 图层逐 cell 检查，不再把复合 UI/BG 整层误报为
“动态文字层”。固定分母与结果如下：

| 项目 | 数量 |
|---|---:|
| 父未知图层 | 61 |
| 32×32 tilemap cell | 62,464 |
| 精确命中非空 dialogue-font 展开内容的 cell | 2,827 |
| 只命中全零字体源、保持歧义的 cell | 26 |
| 未命中字体内容的 cell | 59,611 |
| 有序 SJIS 8×16 垂直字形对 | 1,050 |
| 被有序字形对覆盖的 cell | 2,100 |
| 含有序字形对的父图层 | 58 |
| 不同 SJIS 码 | 226 |

1,050 个有序对的源候选均唯一；其中 palette expansion group 2 为 996 对，
group 3 为 54 对。它们覆盖 BG3 的 56 个图层及 BG1 的 2 个图层。以下三层没有
可签发的非空有序字形对：

- `alternate-character-overview.ss9` BG0；
- `scenario-41-pre-controller-after-a.ss9` BG3；
- `scenario-41-victory.ss9` BG3。

## 证明方法

导出器从基准 ROM 按 `dialogue-font-v2` 的 9,012 个物理 half-tile 记录重读
16-byte packed 2bpp 源，并逐条验证源 SHA-256。只使用现有消费者已经证明的展开式：

```text
runtime index = source 2bpp index + (palette group << 2)
```

其中 group 2 对应输出索引 8–11，group 3 对应输出索引 12–15。每个父层从 `.ss9`
重读 BGCNT、charblock、screenblock、tilemap 和 4bpp graphics。普通内容命中只证明
“该 runtime tile 的 32 字节等于至少一个非空字体 half-tile 展开结果”；只有同时满足
以下条件时才签发 SJIS 字形对：

1. 上下两个 cell 位于同一列的相邻行；
2. 两个 tilemap entry 均无 H/V flip；
3. 两个 entry 使用同一 palette bank；
4. 上格精确匹配同一 SJIS 记录的 half 0；
5. 下格精确匹配该记录的 half 1；
6. palette expansion group 相同；
7. 候选源记录唯一。

不要求 runtime tile ID 连续。1,048 对的下 tile ID 是上 tile ID `+1`，另 2 对在
level-up 画面为 `+7`；缓存复用可以让相邻 cell 引用非连续 tile ID，字节内容与
有序源 half 才是身份依据。

代表性绑定：

- 世界地图：`scenario-42-postbattle-world-map.ss9` BG3 `(4,1)`，
  `0x92BB`，group 2，runtime tiles `0/1`；
- 对白：`scenario-46-client-dialogue.ss9` BG3 `(3,13)`，
  `0x9298`，runtime tiles `294/295`；
- 人物资料菜单：`alternate-character-overview.ss9` BG1 `(14,14)`，
  `0x9298`；
- 术列表：`skill-list-pre-controller.ss9` BG1 `(4,14)`，
  `0x9298`；
- group 3：`scenario-49-battle-14-postbattle-task-menu.ss9` BG3
  `(8,5)`，`0x909D`，runtime tiles `42/43`。

同一 group 3 图层的 `(14,5)` / tile 54 是全零 tile，能匹配 176 个空白字体候选，
因此只记录为 `ambiguous_blank_font_content`，不会进入有序字形对。

## Artifact 与独立验证

每个图层保留：

- 父 `state_id:bgN` 键、父记录 canonical SHA-256 和原
  `unidentified_runtime_payload` 分类；
- checkpoint、BGCNT、char/screen base、tilemap SHA-256 和固定 cell 计数；
- 按 runtime tile ID 聚合的非空字体内容、位置 ranges 和全部源 half 候选；
- 26 个空白歧义 cell；
- 1,050 个有序 SJIS 对的 runtime 地址/tile/hash、源记录/half/hash 和 palette group。

独立 verifier 不导入导出器或仓库图像 helper；它自行解析 `.ss9` PNG/`gbAs`
容器、GBA 内存域、Mode 0 tilemap，重新实现 2bpp→4bpp 展开，并从 ROM 重建全部
9,012 个源 half。它还重建 payload 与 promotion manifest，并拒绝以下篡改：

- SJIS 码；
- expansion group；
- runtime tile hash；
- dialogue-font manifest hash；
- 上下 cell 空间顺序；
- 上下 runtime tile ID 顺序；
- artifact 额外文件。

## 证据边界

本成果只闭合 61 个父未知层中“字体内容组件”的来源。它明确不签发：

- 任何父 BG 的完整来源身份；
- 非字体 tile 的来源；
- 每个 checkpoint 的具体 writer 或 loader 身份；
- 汉化字形到 Unicode/自然语言字符的完整映射；
- 未跟踪游戏状态、跨帧文本变化、camera、window 或 blend 时序。

因此父 artifact 的 61 个 `unidentified_runtime_payload` 分类保持不变。后续应优先
调查剩余非字体 tile 的复用族或动态 UI loader，不应把 58 个含字形的复合 BG
整体改名为文字层。

## 可复现与资源占用

```sh
python3 tools/export_runtime_font_tile_provenance.py \
  --root . \
  --output-dir artifacts/runtime-font-tile-provenance-v1

python3 tools/verify_runtime_font_tile_provenance.py \
  --root . \
  --artifact artifacts/runtime-font-tile-provenance-v1

python3 -m unittest tests.test_export_runtime_font_tile_provenance -v
```

- 9 项测试通过；
- 正式 artifact 为两个文件、约 3.6 MiB；
- 受资源守卫测试峰值 tree RSS 约 69.6 MiB；
- 正式导出与独立验证均在约 1.1 秒内完成；
- 全过程未启动 mGBA，没有新增模拟器快照或进程。
