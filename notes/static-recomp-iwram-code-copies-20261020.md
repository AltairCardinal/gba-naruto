# IWRAM 运行期拷贝代码映射（GBARecomp 静态重编译）

日期：2026-10-20
性质：技术笔记。与 `notes/gba-static-recomp-baseline-eval-20261020.md`（基线复现）同族，
但**推翻**了该笔记里「这 4 个 PC 自愈编译器救不了」的结论。
产物目录：`build/eval-with-skill/`；**未改动 `recomp/` 下任何文件**。

## 0. 结论速览

上一轮基线留下 4 个解释器桥接 PC：

```
bridged 0x030006A4 (arm) x124032
bridged 0x030006B4 (arm) x124032
bridged 0x03000930 (arm) x18897
bridged 0x03005CE8 (arm) x124032
```

基线结论是「根因是 overlay ABI v6 的 `GbaOverlayCallbacks` 没有 resume_pc 访问口，
自愈编译器救不了」。**这个判断是错的**：这 4 个 PC 不是「找不到静态实现」，
而是**根本不是 ROM 地址**——它们是游戏启动时从 ROM 拷进 IWRAM 的代码，
重编译器按卡带地址去取字节当然取不到。正确的解法不是修 overlay ABI，
而是给重编译配置补 `[[code_copy]]`（运行期地址 → ROM 源地址映射）。

本轮把这 4 个 PC 全部静态化：dispatch miss 从 13 → 0，解释器执行指令数
12,710,612 → 0。

## 1. 怎么定位的（可复现的方法）

### 1.1 关键前提：IWRAM 快照

`notes/*-iwram.bin` 是 mGBA 跑同一个 `rom/base.gba` 时导出的**完整 32 KB IWRAM 快照**
（`0x03000000`-`0x03007FFF`）。它就是「运行期拷贝后的 ROM 字节」。

### 1.2 第一步：定位漏掉的那个 PC

第一次跑 verbose self-heal（`GBARECOMP_SELFHEAL_VERBOSE=1`）时，框架打出了关键一行：

```
runtime_arm: SELF-HEAL bridge entered at top level (empty call-return stack)
  for pc=0x03005CE8; LR=0x03000694 (fallback stop)
```

`LR=0x03000694` 说明**跳转是从 IWRAM 里的 0x03000694 发起的**。
于是把 `0x03000694` 当作新的检索起点。

### 1.3 第二步：找拷贝例程的字面量池

ROM 0x080616D0 一带是 THUMB 代码（**注意：这块不是 ARM，用 ARM 反汇编全是垃圾**）。
它的字面量池里成对出现 `(ROM 源地址, IWRAM 目标地址)`：

| ROM 字面量池位置 | 源地址 | 目标地址 | bias |
|---|---|---|---|
| `0x08061730` | `0x080004C8` | `0x03000680` | `0x28001B8` |
| `0x08061738` | `0x08000520` | `0x0300088C` | `0x2800036C` |
| `0x08061744` | `0x080005AC` | `0x03000930` | `0x28000384` |
| `0x08064638` | `0x08000638` | `0x03005CE8` | `0x279FF6B0` |

（`0x08064634` 是 `0x03005CE8`，`0x08064638` 是 `0x08000638`——上一轮把它当成了
普通数据变量，其实它是第 4 张拷贝表。）

### 1.4 第三步：用「IWRAM 字节 == ROM 字节」实测每张表的 size

`tools/block-extent.mjs`：给定 bias，逐 16 字节比对 IWRAM 与 ROM，输出匹配率。
实测（`rom/base.gba`，SHA-1 `26f60795fa5e63b4f0264b84e453beffd56b9f7d`）：

| 运行期窗口 | ROM 源 | 连续逐字节相同长度 | 备注 |
|---|---|---|---|
| `0x03000680` | `0x080004C8` | **512 B** (`0x200`) | stub 模块 |
| `0x0300088C` | `0x08000520` | **164 B** (`0xA4`) | stub 模块（同一段 ROM 的第二份拷贝） |
| `0x03000930` | `0x080005AC` | **96 B** (`0x60`) | 算术 helper |
| `0x03005CE8` | `0x08000638` | **92 B** (`0x5C`) | 表查找 helper |

`0x03005CE8` 这一块在**所有 mGBA 快照里都是全零**（那段拷贝在那些采样点还没发生），
只有本轮重编译器自己的 `--dump-state` 快照里才有内容——所以
「mGBA 快照找不到源」≠「没有源」。用重编译器自己 dump 的状态才是正解。

### 1.5 第四步：读出模块里的函数头

`0x080004C8..0x0800068F` 是同一个模块，被装到 IWRAM **两个**位置
（`0x03000680` 与 `0x0300088C`），其中一部分又被单独拷到 `0x03000930`。
ARM 反汇编给出的函数头：

| ROM | IWRAM 落点 | 形态 |
|---|---|---|
| `0x080004C8` | `0x03000680` | 跳板：`ldr r2,[pc]; ldr r1,[r2]; mov lr,pc; bx r1` |
| `0x080004DC` | `0x03000694` | 同上 |
| `0x080004EC` | `0x030006A4` | 同上 |
| `0x080004FC` | `0x030006B4` | 往 `0x03007FF8` 写半字 2（BIOS hook 开关） |
| `0x08000520` | `0x030006D8` / `0x0300088C` | BIOS 分发 helper |
| `0x080005AC` | `0x03000930` | 算术 helper |
| `0x080005E0` | `0x03000798` / `0x03000964` | `add r0,r0,#4` |
| `0x080005F8` | `0x030007B0` / `0x0300097C` | `push {r8,sb,sl,fp} … pop` |
| `0x08000638` | `0x03005CE8` | 表查找 helper |

## 2. 这套机制到底是什么（补充理解）

- `0x03000014` 是一张**函数指针表**（从 ROM `0x0853D5B4` 拷来，56 B）：
  ```
  0x03000014 = 0x080612BD   (ROM thumb 函数指针)
  0x03000018 = 0x03000680   (对应的 IWRAM 跳板)
  0x0300001C = 0x0300088C   (对应的 IWRAM 跳板)
  0x03000020.. = 0x08061535  (重复项)
  ```
- ROM `0x080004C8` 那个跳板做的是
  `ldr r2,[pc,#0x3c]`（取 `0x03000000`）→ `ldr r1,[r2]` → `mov lr,pc` → `bx r1`。
  也就是**从 IWRAM 的指针槽里取一个函数地址再跳过去**。
  本轮运行中该槽的值是 `0x03005CE8`，所以才出现了 `0x03005CE8` 这个缺口。
- 结论：游戏把热函数**重定位**到 IWRAM（GBA 上 IWRAM 比 ROM 快），
  再用指针表间接调用。这类地址**永远不能**按卡带地址去反汇编。

## 3. 工具（留在 `build/eval-with-skill/tools/`）

| 脚本 | 作用 |
|---|---|
| `find-iwram-source.mjs` | 给定 IWRAM 偏移，在 ROM 里找字节相同的源地址；并报告全零保护 |
| `block-extent.mjs` | 给定 (IWRAM 偏移, ROM 偏移) 对，逐 16 字节输出匹配率 → 定 size |
| `iwram-map.mjs` | 扫整份 IWRAM 快照，列出所有与 ROM 相同的区段（自动发现拷贝块） |
| `rom-inspect.mjs` | 十六进制转储 / u32 字面量检索 |
| `disasm_arm.py` | capstone ARM/THUMB 反汇编（仓库里 vendored 的 capstone 只有 macOS dylib，Windows 下要 `pip install capstone`） |

## 4. 踩到的坑

1. **这段代码是 THUMB，不是 ARM。** 用 ARM 反汇编 0x080616D0 一带全是
   `movweq / strhi` 之类的垃圾；换成 THUMB 立刻通顺。
2. **全零 IWRAM 会让字节搜索命中百万个位置。** 必须先判零再搜
   （`find-iwram-source.mjs` 里有显式保护）。
3. **零对零的假阳性。** `iwram-map.mjs` 会把「IWRAM 的零 == ROM 的零」当成一块拷贝，
   必须逐条复核。
4. **mGBA 快照不代表全部拷贝点。** `0x03005CE8` 在所有 mGBA 快照里都是零。
   要用重编译器自己的 `--dump-state`（GBAS 二进制格式：`magic "GBAS"` +
   `tag|payload_len|payload` 分段，`BUS0` 段里 EWRAM 32 KB 之后紧跟 IWRAM 32 KB）。

## 5. 对基线结论的修正

`notes/gba-static-recomp-baseline-eval-20261020.md` 写的是
「要闭合这 4 个 PC，需要给回调结构体加 resume_pc 通道并升 ABI 版本，
或给 exe 加 `/EXPORT`」。**这个需求不存在**——`[[code_copy]]` +
`[[extra_func]].source_addr` 就是官方支持的正解，不需要动 overlay ABI 也不需要动 exe 导出表。
