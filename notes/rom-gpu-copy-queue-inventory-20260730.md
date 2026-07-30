# 通用 GPU copy queue 全 ROM 直接调用审计（2026-07-30）

## 结论

共享队列 `0x03005BBC..0x03005CBC` 的 ABI 和全 ROM 直接 Thumb `BL`
调用分母已经闭合。基准 ROM 中精确存在 14 个对 `0x080635B8` 的直接调用：

```text
08063168 0808812E 0808D9C6 0808DA0E
080962EE 080962FE 08096536 0809655C 080965A4
08096DBA 08096E00 08096E44 08098B6C 08098D90
```

分类结果：

- 5 个调用从既有 `menu-ui` 视觉记录读取 128-byte ROM palette；
- 1 个调用把既有 `menu-ui` LZ77 graphics 解压、调整后从 RAM 提交到 OBJ VRAM；
- 6 个调用使用静态可证的 RAM 源；
- 1 个固定使用 `0x02002880`，但 caller-local 路径不能证明其 producer；
- 1 个使用动态 task source，现有 sequence artifact 只证明公式，不能证明自然实例中的
  source 一定为 ROM；
- 新发现且需要另行打包的 ROM 源为 0。

这消除了“该 queue 隐藏一批未收录固定 ROM 图像”的不确定性，但没有把动态来源或
RAM 缓冲反推成 ROM 原始资源。

成果：

- `artifacts/rom-gpu-copy-queue-inventory-v1/`
- `tools/export_rom_gpu_copy_queue_inventory.py`
- `tools/verify_rom_gpu_copy_queue_inventory.py`
- `tests/test_export_rom_gpu_copy_queue_inventory.py`

## 队列 ABI

status-1 enqueue `0x080635B8..0x08063604`：

```text
queue = 0x03005BBC
slot_count = 16
slot_stride = 16

+0x00 u32 flags
+0x04 u32 source
+0x08 u32 destination
+0x0C u16 size_bytes
```

enqueue 参数为 `(source, destination, size_bytes)`；第一个空 slot 写入
`flags=1`，成功返回 1，满队列返回 0。consumer
`0x0806365C..0x080636DC` 对 status 1 执行：

```text
CpuSet(source, destination, u16(size_bytes) >> 1)
```

随后清 `flags` bit 0。

status-3 enqueue `0x08063604..0x0806365C` 复用同一 slot，并将 `+0x0C/+0x0E`
解释为 `source_stride_halfwords/row_count`。consumer 逐行把源 stride
halfwords 写到目标的 64-byte 行距，然后只清 bit 1、保留 bit 0。该结构和本次
consumer 行为已由代码固定；bit 0 后续生命周期仍未闭合。

dispatcher `0x080612BC..0x080614E4` 的相对顺序为：

1. `0x08061320 -> 0x08062924` 执行 sprite renderer；
2. `0x080613FC -> 0x0806365C` 首次 flush；
3. `0x080614C2 -> 0x0806365C` 可选第二次 flush。

这只证明相对调用顺序，不把该函数冒充唯一硬件 VBlank phase。

## menu-ui 来源绑定

`0x08096138..0x08096162` 的 selector 精确实现：

```text
Pair(record, variant < 5) =
    0x085A4DEC + record * 40 + variant * 8
Pair(record, variant == 5) = 0x085A4DE4

gfx_ptr     = u32[Pair + 0]
palette_ptr = u32[Pair + 4]
```

这与 `sequel/content/menu-ui/bank.json` 的 63×40-byte 表及 special variant 5
一致。以下 5 个 queue caller 都读取 `Pair+4`：

```text
0x080962FE 0x0809655C 0x080965A4 0x08096DBA 0x08096E00
```

它们属于同一既有 palette family，动态 record、variant 和目标 palette bank
保持表达式；record 0 的零哨兵也不被隐去。`0x080962EE` 则在同一函数内先把
`Pair+0` 的 LZ77 graphics 解压到调用者 buffer，再调整 tile bytes 并提交 6400
bytes，因此绑定为既有菜单图像的两段链，不重复导出。

## RAM 与动态来源

| caller | source | destination | bytes | 判定 |
|---|---|---|---:|---|
| `0x0808812E` | `0x02002BC0` | `0x05000000` | 416 | 固定 EWRAM→PRAM |
| `0x0808D9C6` | `0x02002AB0` | `0x06002000` | 352 | overview 过程式 tiles |
| `0x0808DA0E` | `0x02002C10` | `0x050001A0` | 32 | overview 过程式 palette |
| `0x08096536` | `0x02002880` | 动态 OBJ palette bank | 128 | 已被后续成果取代：mode 0 producer 已闭合 |
| `0x08096E44` | `0x02002880` | 动态 OBJ palette bank | 128 | helper 输出，完整 producer 语义未签发 |
| `0x08098B6C` | `0x02002880` | 动态 BG palette bank | 32 | caller 内生成的变换 palette |
| `0x08098D90` | `work+0x40` | 动态 BG palette bank | 32 | helper 生成的 work RAM palette |
| `0x08063168` | 动态 task tile pointer | 动态 OBJ VRAM | 动态 | 公式已知，自然 source identity 未知 |

`0x08098B6C` 邻近读取 `0x085A320C` 的 tile-assets descriptor，但 enqueue
source 已是 `0x02002880`；仅凭邻近表地址不能把 descriptor 原字段冒充本次 raw
palette source。

上表中 `0x08096536` 的“producer 未闭合”是本成果生成时的历史分类，现已被
`artifacts/portrait-palette-producers-v1/` 取代：后续成果通过全剧情
opcode `0x17` 分母、mode 0 静态链和 mGBA 正负对照证明该 caller 接收
`0x02002880` 的 64 色红色转场 palette。父 artifact 保持不可变，故在本说明中
标记 superseded，而不重写旧 manifest。`0x08096E44` 的 dim helper 仍只有静态
公式，运行时路径保持未完成。

## 完整性与边界

独立 verifier 不导入 exporter，重新执行：

- ROM SHA-256 校验；
- 全 ROM Thumb BL 解码并要求 14/14 地址完全一致；
- selector 的表基址、special pair、record/variant stride、字段偏移，以及五条
  palette route 的 selector BL、`Pair+4` load、128-byte size 与目标 PRAM
  literal 等指令级断言；
- menu graphics 两段链的 selector、`Pair+0`、LZ77 helper、栈 buffer 与
  6400-byte enqueue，以及固定 RAM route 的 literal/BL 指令级断言；
- queue、consumer、dispatcher、selector 及 caller/function 窗口哈希；
- `menu-ui`、menu portraits、overview、battle-effect 与 tile-assets 上游契约；
- canonical JSON、manifest 与目录文件集合检查；
- 重签后的 callsite、分类、slot count、scope 和非 canonical JSON 负例。

当前闭合范围：

- status-1 ABI 与消费；
- status-3 enqueue 结构及本次 consumer 行为；
- 对 `0x080635B8` 的全 ROM 直接 Thumb BL 分母；
- 14/14 caller 的 fail-closed 来源分类。

仍未闭合：

- 间接 enqueue 调用；
- 其他可能存在的异步 transfer queue；
- status-3 bit 0 的后续生命周期；
- 对话 tilemap submit；
- 所有运行时可达性；
- 全部未压缩图像、全部游戏视觉状态和通用图像回写。

本轮只做静态分析，没有启动 mGBA。生产导出由 `tools/run_guarded.py` 使用 heavy
lock 执行，最终生产运行峰值 owned-tree RSS 为 0.6015625 MiB，`completed/0`、
非 degraded。
