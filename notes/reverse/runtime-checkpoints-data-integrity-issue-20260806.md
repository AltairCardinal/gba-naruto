# Runtime checkpoint 容器误判更正（2026-08-09）

> 本文更正 2026-08-06 的错误结论。原调查只检查了文件头和 `file(1)` 输出，
> 没有解析 mGBA 的状态容器；因此把合法 savestate 错判成了普通 PNG。

## 正确格式

mGBA 的 `.ss9` 是 PNG 容器：标准 PNG 图像保存预览帧，自定义 `gbAs` chunk
保存 zlib 压缩的 GBA 状态，`gbAx` chunk 保存扩展数据。PNG 文件头本身不是
损坏证据，也不存在原文假定的 `MGST` 文件头要求。

仓库工具 `tools/inspect_mgba_savestate.py` 已按该格式解析状态。新增的批量守卫
`tools/verify_runtime_checkpoint_containers.py` 会验证：

- PNG 签名、chunk 长度和 CRC；
- 恰好一个 `gbAs` chunk；
- `gbAs` 能 zlib 解压并满足 GBA 状态版本及 `0x61000` 字节长度约束；
- 保存 PC 能从状态中读取。

2026-08-09 批量结果：104/104 个 `.ss9` 有效，普通 PNG 0 个，无效文件 0 个；
版本分布为 `0x01000007` 93 个、`0x0100000A` 11 个。该检查证明容器和状态载荷
有效，但不替代各实验自己的运行时语义 verifier。

## 影响范围

- 因“`.ss9` 是 PNG”而对 Group 13、Group 17 等证据做出的统一降级无效；这些
  证据仍应由各自 manifest、哈希、运行时输出和 verifier 独立审计。
- commit `38af6dd5b` 新增的 101 个 `.png` 与同名 `.ss9` 逐字节相同，只是重复
  复制了带状态 chunk 的容器，并非独立视觉证据；后续更正提交删除这些副本。
- Group 12 AI observer v1 仍不能作为已接受证据，但真实原因是它使用了与
  profile 不匹配的 mGBA、debug monkey-patch 绕过校验，并引用了当时尚不存在的
  verifier，而不是输入 checkpoint 损坏。

## 可复现验证

```bash
python3 tools/verify_runtime_checkpoint_containers.py
python3 -m unittest -q tests.test_verify_runtime_checkpoint_containers
```

边界：容器验证器不声称 checkpoint 对应的游戏场景或运行时实验结论正确；那些
结论继续由相应的场景/像素 A/B verifier 负责。
