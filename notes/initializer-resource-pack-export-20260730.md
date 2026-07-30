# 初始化器资源包导出与运行时 BG 组件绑定（2026-07-30）

## 结论

`0x08065404..0x08065554` 是一个被 23 个静态调用点复用的初始化函数。它从
同一 literal pool 装载四项资源：

| 资源 | GBA 地址 | LZ77 / 解压大小 | 解压 SHA-256 |
|---|---:|---:|---|
| BG graphics | `0x0809C614` | 604 / 2048 bytes | `d2338ea2e8d155029010b4dfac8f72e01e73a74e9ccccc8998f62ec0ba81909e` |
| BG palette | `0x0809C870` | 64 / 64 bytes | `f20fc5a725aba48ad552db95ec211c78b1bef25732c8978324a6bf72e64d72e5` |
| OBJ graphics | `0x085B64E0` | 753 / 1536 bytes | `be06481834463afa0226757f897601ef07291106257bc716ef42bf4572df1848` |
| OBJ palette | `0x0809CBC4` | 40 / 32 bytes | `dc72a37cfa3893bc9979d1801b80c9e356b04990751d4bf525e2879fa6e52393` |

成果位于 `artifacts/initializer-resource-pack-v1/`。四项压缩流和解压数据均
逐字节保存；64 个 BG 4bpp tile、48 个 OBJ 4bpp tile 另有完整索引图集。BG
graphics 有 29 种不同 tile 内容，OBJ graphics 有 43 种。

这里使用中性的“初始化器资源包”，不按图集视觉给资源附会菜单、按钮或业务名称；
函数同时加载 BG 和 OBJ 资源，静态代码证据也不等于某个 checkpoint 已动态执行该
函数。

## 静态 loader 证据

初始化函数切片 SHA-256 为
`213423e70948ef3dbd91ed7854efb5c52fd7543f4b73b4a4a2219ffd89ce66f7`。
资源路线为：

- `0x0806549E/0x080654A0`：读取 BG graphics literal，调用
  `0x0809C0E8` 的 `LZ77UnCompVram` wrapper；目的地址公式为
  `0x06000000 + bg_charblock*0x4000 + bg_tile_base*32`，并写入
  `0x0201BD54`。
- `0x080654A4/0x080654B8`：读取 BG palette literal，经
  `0x0808830C` 先解压到 `0x02002880`，再复制到
  `0x05000000 + bg_palette_slot*32`。
- `0x080654BC/0x080654C6`：读取 OBJ graphics literal，经
  `LZ77UnCompVram` 写到 `0x06010000 + obj_tile_slot*32`。
- `0x080654CA/0x080654D6`：读取 OBJ palette literal，经同一 palette helper
  写到 `0x05000200 + obj_palette_slot*32`。

23 个 direct caller、四个 literal 地址、四个 BL 目标和资源内容均由导出器及独立
verifier 从 base ROM 重新核对。manifest 将这些路线明确标记为
`evidence_type=static_code`。

## 运行时 BG 组件绑定

上一个里程碑把 61 个父未知层的 62,464 个 cell 分成 2,827 个非空字体 cell、
26 个空白字体歧义 cell 和 59,611 个非字体 cell。本成果对固定的 59,611 分母
继续分类：

| 分类 | cell | 不同内容 | 层 |
|---|---:|---:|---:|
| 精确命中本包非空、非通用填充 BG tile 内容 | 5,225 | 23 | 58 |
| 全零内容别名 | 48,815 | 1 | 61 |
| 通用填充内容别名 | 4,673 | 1 | 58 |
| 本包未命中 | 898 | 39 | — |

全零内容在源包中对应 tile `0,34..63`；通用填充对应 tile `1,10`。两者都
显式保留完整候选集并标记 `unique_source_identity=false`，不用于签发来源身份。

5,225 个独特内容 cell 中：

- 5,106 个符合 `runtime_tile_id = source_tile_id + 448`；
- 119 个不符合该固定偏移，仍保留为内容相等，不强行套用 relocation；
- 只有 28 个父层的全部独特内容 cell 都符合 `+448`；
- 58 个有独特内容的层都存在 runtime palette bank 14 与 source palette bank 0
  的 32 bytes 精确相等；
- runtime palette bank 13 不匹配该源 palette，不能被归并。

没有独特内容命中的三个层为：

- `alternate-character-overview.ss9` BG0；
- `scenario-41-pre-controller-after-a.ss9` BG3；
- `scenario-41-victory.ss9` BG3。

每层都继续绑定原 `parent_layer_key`、父记录 canonical SHA-256 和
`parent_classification=unidentified_runtime_payload`。组件命中没有把任何父 BG
升级为整层静态来源。

## 产物与验证

- 导出器：`tools/export_initializer_resource_pack.py`
- 独立验证器：`tools/verify_initializer_resource_pack.py`
- 定向测试：`tests/test_export_initializer_resource_pack.py`
- 主数据：`artifacts/initializer-resource-pack-v1/initializer-resource-pack.json`
- 索引图集：`bg-graphics-atlas.png`、`obj-graphics-atlas.png`

独立验证器没有导入任何 `tools` 模块；它自行实现 Thumb BL 解码、LZ77、`.ss9`
PNG 容器解析、Mode 0 BG tilemap 读取、4bpp atlas 重建和 BGR555 palette 校验，
然后重建全部 61 层结果及 promotion manifest。

定向测试 9 项通过，包括资源、图集、payload、父分类、manifest 和额外文件篡改
负例。测试峰值 tree RSS 为 74.52 MiB；正式导出加验证峰值 26.75 MiB。两次均
通过共享 heavy lock，未启动 mGBA，没有内存异常或残留进程。

## 未完成边界

本成果不签发：

- 任一 checkpoint 动态执行了 `0x08065404`；
- 完整 BG、OBJ 或最终屏幕的自然语言身份；
- 运行时 writer、调用时刻、跨帧覆盖或资源释放顺序；
- OBJ resource 到自然 OAM 实例的绑定；
- 剩余 39 种、898 个非字体 cell 的来源；
- 未跟踪游戏视觉状态。

下一图像主线应围绕剩余 39 种内容的 loader/ROM 来源或 OBJ 实例绑定继续，
不应重复扫描已经闭合的字体和本资源包内容。
