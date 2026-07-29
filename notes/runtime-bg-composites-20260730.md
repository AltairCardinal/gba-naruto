# 运行时 Mode 0 BG 图层批量解码（2026-07-30）

## 结论

`artifacts/runtime-bg-composites-v1/` 已离线解码全部 91 个 tracked mGBA
checkpoint 的当前 BG 输入。所有样本均为 GBA display mode 0，因而可以用同一套
text-BG 规则严格重建：

- BG0–BG3 enable、priority、charblock、screenblock、4/8bpp 和 map size；
- HOFS/VOFS 滚动、32×32 screenblock 分块、tile H/V flip；
- 4bpp palette bank、8bpp palette index 与 tile color 0 透明；
- 每个 enabled BG 的 240×160 RGBA 图层；
- 只按 BG priority 和 BG index 生成的调试预览。

91 个 checkpoint 归并为 89 个唯一 BG 状态，共生成 285 个 PNG archive member。
为避免把数百个小文件直接放入 Git，所有图层和预览集中在确定性
`layers.zip`；manifest 逐项保存 member 路径、尺寸、模式和 SHA-256。

## 覆盖事实

| 项目 | 结果 |
|---|---:|
| checkpoint | 91/91 |
| display mode 0 | 91/91 |
| 唯一 BG 状态 | 89 |
| PNG archive member | 285 |
| WIN0 enabled | 5 |
| blend control 非零 | 91 |
| MOSAIC 非零 | 0 |

启用 BG 组合覆盖 `(0,3)`、`(0,1,3)`、`(3)` 与 `(0,2,3)`。每个 checkpoint
还绑定原始 `.ss9`、IO/PRAM/VRAM/OAM、BG palette 与 BG VRAM 的 SHA-256，
并完整记录 window、mosaic 和 blend 寄存器。

## 证据边界

产物中的 `debug-pre-effect-bg-priority-preview` 只表示：

```text
enabled text BG pixels
→ BG priority / lower BG index tie-break
→ backdrop fallback
```

它明确位于 window、blend 和 OBJ 之前，不是最终硬件帧。91/91 样本均有非零
blend 配置，5 个还启用 WIN0；最终画面还取决于 OBJ/半透明 OBJ、OBJ window、
backdrop target、window mask、alpha/brighten/darken 及可能的逐 scanline 寄存器
变化。因此以下内容仍未签发：

- static regular-BG entry 到每个 runtime layer 的来源身份；
- window/OBJ window 的逐像素 mask；
- BG/OBJ/backdrop 的最终 priority 与 blend/brightness；
- camera/scroll writer 调度和跨帧切换时序；
- 最终 screen composition 与硬件 framebuffer 像素等价。

## 可复现与验证

导出器和独立 verifier 分别实现 `.ss9` 读取、mode-0 寄存器解码、tilemap 分块、
4/8bpp、flip、palette 和像素重建；verifier 不导入 exporter 或其他 `tools`
模块。测试包含四种 text-BG map size 的 block mapping、4/8bpp、双 flip、
palette bank 与 color-zero transparency golden，并验证 manifest 与 ZIP 篡改会失败。

```sh
python3 tools/export_runtime_bg_composites.py \
  --root . \
  --output-dir artifacts/runtime-bg-composites-v1

python3 tools/verify_runtime_bg_composites.py \
  --root . \
  --artifact artifacts/runtime-bg-composites-v1

python3 -m unittest tests.test_export_runtime_bg_composites -v
```
