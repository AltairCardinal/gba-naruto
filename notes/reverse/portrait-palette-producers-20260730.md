# 肖像调色板生产者闭环（2026-07-30）

## 结论

`0x08096536` 的固定源 `0x02002880` 已从“producer 未知”升级为可复现的
肖像转场调色板生产链：

```text
chapter opcode 0x17
  -> 0x08097966
  -> 0x08096B74(slot, mode, argument)
  -> mode 0 target 0x08096BD4
  -> CpuSet fixed-source fill 0x02002882..0x020028FF
  -> portrait state 0x40
  -> tick % 8 == 0
  -> 0x08096536 enqueue 0x02002880 -> OBJ palette bank, 128 bytes
```

这里必须称为 **mode 0**。早期实验把跳转表第一个 entry 错当成 mode 1，并把
脚本游标改到 `17 00 01 01`；mGBA 正确执行了 mode 1，所以没有发生 fill 或
`0x08096536` enqueue。纠正跳转表索引后，受控脚本节点改为
`0x08032724 = 17 00 00 01`，正样本一次命中。问题根因是静态索引误读，不是
mGBA 故障。

## 全剧情分母

导出器从 primary/alternate 两张 56-entry 表的 110 个非空 slot 出发，遍历
98 个唯一脚本根和 14,199 个唯一指令节点；解析失败为 0。opcode `0x17` 有
161 个唯一节点、193 次根引用，各 mode 的唯一节点数为：

| mode | 节点数 | 占 161 节点 |
|---:|---:|---:|
| 0 | 48 | 48/161 |
| 1 | 2 | 2/161 |
| 2 | 29 | 29/161 |
| 3 | 31 | 31/161 |
| 4 | 11 | 11/161 |
| 5 | 18 | 18/161 |
| 6 | 4 | 4/161 |
| 7 | 5 | 5/161 |
| 8 | 13 | 13/161 |

跳转表 `0x08096BB0` 的目标依次为
`0x08096BD4/0x08096BF8/0x08096C22/0x08096C56/0x08096C9C/`
`0x08096C9C/0x08096CA8/0x08096CBC/0x08096CCC`。mode 4/5 共享目标，
不能按目标地址去重后再充当 mode 分母。

## mode 0 静态语义

`0x08096BD4` 在栈上写入 BGR555 `0x001F`，随后以：

```text
source  = stack u16 0x001F
dest    = 0x02002882
control = 0x0100003F
```

调用 `0x0809C0E0`。control 表示 fixed-source、63 halfwords，因此保留
`0x02002880` 的第一色，只把后 63 色填成红色；接着把肖像对象状态设为
`0x40`、tick 清零。`0x0809651C` 的 state-0x40 handler 在
`tick % 8 == 0` 时通过 `0x08096536` 把完整 128-byte scratch palette 提交到
`0x05000200 + palette_bank*32`。

另一条已固定但尚未做运行时正样本的 dim 路径为：

```text
0x08096E3A -> 0x08096D4C -> 0x08096E44
out = ((color & 0x7BDE) >> 1) + ((color & 0x739C) >> 2)
```

helper 对 `0x02002880` 的 64 色原地处理，再提交 128 bytes。该静态公式不能
冒充 dim 路径运行时覆盖，也不能证明 `0x02002880` 的所有生产者已闭合。

## 运行时正负对照

输入夹具从
`artifacts/runtime-checkpoints/scenario-41-postbattle-dialogue-8.ss9`
派生，原 SHA-256 为
`62adcd52b577f73ca1ffd6d2d4ec3b9fafa2a2b130ac644a6834e2a56a50d4d8`。
只把 `0x030011F0` 的游标从 `0x08031F31` 改为 `0x08032724`；解压后的
savestate 仅有两个字节变化。夹具 SHA-256 为
`69c1d96d4077b67f1b7594f234191b6f6a0956db53a1f62b4bf4ca635df11805`。

- 零输入：240 帧超时，0 次 scratch 写入、0 条目标 trace；峰值 owned-tree
  RSS `105.01953125 MiB`。
- 单输入：frame 2 按 A、frame 10 松开；frame 2 依次命中 opcode handler、
  transition helper、mode dispatch、mode-0 fill 与目标 CpuSet，frame 9 在
  state `0x40`、tick 8 命中 enqueue。参数为
  `r0=0x02002880`、`r1=0x05000200`、`r2=0x80`，
  `lr=0x0809653B`；63 条 halfword 写覆盖
  `0x02002882..0x020028FE`，最终 histogram 为 `0x0000×1`、
  `0x001F×63`。峰值 RSS `84.015625 MiB`。

两次运行均经 `tools/run_guarded.py` 的 shared heavy lock、2 GiB 启动门槛、
512 MiB tree ceiling 与 success-marker 收尾，`completed/0`、非 degraded；
没有残留 mGBA 进程或新增 mGBA crash report。

## 持久成果与复现

- 成果：`artifacts/portrait-palette-producers-v1/`
- 原始输入/对照/正样本快照：成果下 `raw/`
- 探针：`tools/mgba_palette_producer_probe.lua`
- 导出器：`tools/export_portrait_palette_producers.py`
- 独立校验器：`tools/verify_portrait_palette_producers.py`
- mGBA source commit：
  `c16c3ff55585e71bee83c95539c2ecde15d728c8`
- mGBA binary SHA-256：
  `4856a8f95a32d0d2d97e0141a4dbe33c162abf27295a8f85ed8fb3c17a42ea72`

```bash
python3 tools/export_portrait_palette_producers.py \
  --root . \
  --raw-root artifacts/portrait-palette-producers-v1/raw \
  --output-dir artifacts/portrait-palette-producers-v1

python3 tools/verify_portrait_palette_producers.py \
  --root . \
  --artifact artifacts/portrait-palette-producers-v1
```

独立 verifier 不导入 exporter，会自行重走剧情 CFG、重读跳转表和静态代码、
解析 `.ss9`、校验正负对照、write/trace/scratch/state、manifest 及实现哈希。

## 边界

本成果闭合的是 opcode `0x17` mode 分母、mode 0 红色 fill 生产链，以及
`0x08096536` 的一次真实队列提交。它不签发：

- dim helper 的运行时可达性；
- `0x02002880` 的所有生产者；
- 所有肖像转场路径的逐 mode 运行时覆盖；
- 通用调色板编辑/回写；
- 全部游戏视觉状态或实体 GBA 输出。
