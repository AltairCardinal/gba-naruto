# scenario 41 开始任务控制流（2026-07-13）

## 调查目标与结论

本轮从 scenario 41 story-only 脚本结束后的“队伍·装备”页面继续，静态追踪：

- `0x0200A882`、`0x0200A884`、`0x0200A885` 的写入者；
- 原先称作 `0x08097C78 SetBattle` 的来源；
- 队伍/装备 UI 返回后，怎样才会进入真实“开始任务”链路。

结论如下。

1. `0x0200A884..85` 是一个 **16-bit 过滤后输入位图**，不是两个相互独立的 UI
   状态字节。ROM 内没有 `0x0200A885` 的独立字面量引用；高字节变化来自对
   `0x0200A884` 的 `strh`。因此曾观察到的 `A885=0xFC` 只是该 halfword 的高 8 位，
   不能解释成队伍已就绪或任务可开始。
2. `0x0200A882` 是共享 modal/menu result。通用确认路径写 `1`，取消路径写 `2`；
   它不是持久的章节状态，也不能单独证明已选中“开始任务”。
3. `0x08097C78` 不是函数入口，不能寻找它的 `BL` caller。它只是章节解释器 opcode
   `0x1A` handler `0x08097C6C..94` 中间的 `ldrb`。真正来源是
   `0x0808F544 -> 0x0808F5D0 BL 0x080977B8 -> opcode jump table[0x1A]`。
4. 队伍/装备页是外层战前菜单的一个嵌套子流程，不会在内部直接开战：归一化 selector
   `2` 进入 `0x0808ECD0`；退出后回到同一外层菜单。归一化 selector `4` 才返回
   result `2`，令外层状态机进入真正的“开始任务”控制器 `0x08086A54`。
5. **scenario 41 的真实开战不要求出现新的 selector hit，也不要求命中 opcode
   `0x1A` / `0x08097C78`。** scenario 41 primary script 已把 ID 留在
   `0x020311D4[+0x16]`。开始任务流程成功后，`0x080871BE..C4` 直接把
   `+0x16/+0x19` 复制到 battle control `0x02026805/+06`。因此把“新 selector 或
   SetBattle hit”设为第二战必要门禁会错误拒绝正常路径。

## 可复现的静态方法

工作 ROM：`rom/base.gba`。本轮只读 ROM，没有修改诊断 ROM 或运行时工具。

### 1. 定位 WRAM 字面量

```bash
python3 - <<'PY'
from pathlib import Path

rom = Path("rom/base.gba").read_bytes()
for name, address in {
    "A882": 0x0200A882,
    "A884": 0x0200A884,
    "A885": 0x0200A885,
}.items():
    needle = address.to_bytes(4, "little")
    hits = [i for i in range(len(rom)) if rom.startswith(needle, i)]
    print(name, [f"0x{0x08000000 + i:08X}" for i in hits])
PY
```

结果：`A882`、`A884` 有多处 literal-pool 引用，`A885` 为零处。随后从 literal 所在
pool 反查 Thumb PC-relative `ldr`，再检查该寄存器附近的 `strb/strh`。这比对完整 ROM
运行 `tools/find_thumb_calls.py` 快；后者在本轮环境中全 ROM扫描超时，不适合此问题。

局部复核命令：

```bash
python3 tools/disasm_thumb.py rom/base.gba 0x08067F2C --before 0 --size 0x80
python3 tools/disasm_thumb.py rom/base.gba 0x08095F58 --before 0 --size 0x148
python3 tools/disasm_thumb.py rom/base.gba 0x0808F190 --before 0 --size 0x300
python3 tools/disasm_thumb.py rom/base.gba 0x0808F73C --before 0 --size 0x320
python3 tools/disasm_thumb.py rom/base.gba 0x08086A54 --before 0 --size 0x1D8
python3 tools/disasm_thumb.py rom/base.gba 0x08086FEC --before 0 --size 0x348
python3 tools/disasm_thumb.py rom/base.gba 0x080977B8 --before 0 --size 0x54
python3 tools/disasm_thumb.py rom/base.gba 0x08097C58 --before 0 --size 0x48
```

注意 `disasm_thumb.py` 不会自动跳过 literal pool；遇到数据后应以 `od` 确认下一段代码
地址，再从正确地址继续，例如 `0x08086B24`、`0x08087094`。

### 2. `A882` 直接写入点

| 指令地址 | 写入 | 已确认语义 |
| --- | --- | --- |
| `0x0806780E` | `0` | 初始化 |
| `0x08067F4C` | `1` | A/确认结果 |
| `0x08067F7E` | `2` | B/取消结果 |
| `0x080680EC` | `0` | 初始化 |
| `0x0808F348` | `5` | 战前菜单内部 modal/list 状态推进 |
| `0x0809242E` | `0` | 初始化 |
| `0x08092FA4` | `0` | 初始化 |
| `0x08095FBE` | `0` | 通用列表初始化 |
| `0x0809608A` | `1` | 通用列表 A 确认 |

`0x08067F2C` 一带会读取 `A884`：bit 0 被消费时在 `0x08067F4C` 写
`A882=1`，bit 1 被消费时在 `0x08067F7E` 写 `A882=2`，并以 `strh` 清除已消费
输入位。这说明 `A882` 表示一次 modal/list 的返回结果，而不是“已组成有效队伍”。

### 3. `A884..85` halfword 直接写入点

所有已找到的直接写入均为 `strh`：

```text
0x08067D36  0x08067D4E  0x08067D62  0x08067DD6
0x08067EA8  0x08067F22  0x08067F94  0x08068036
```

通用列表 `0x08095F58` 读取该 halfword：bit `0x40/0x80` 上下移动，bit `1`
确认；确认时 `0x0809608A` 写 `A882=1`，`0x08096090` 把当前 row 写入
`0x0200A880`。因此开战控制应观察 `(A882, A880)` 的组合以及外层函数返回值，而不是
单看 `A884/A885`。

## `0x08097C78` 的真实身份

章节解释器入口为 `0x080977B8`。`0x080977D8..E8` 读取 opcode 并通过
`0x080977F4` 起始的 jump table 分派；table entry `0x1A`（地址
`0x0809785C`）等于 `0x08097C6C`。

```text
0x08097C6C  ldrb r0, [r7, #2]
0x08097C6E  ldr  r4, =0x020311D4
0x08097C70  cmp  r0, #0
0x08097C74  adds r0, #1              ; parameter[2] 非零时
0x08097C76  strb r0, [r4, #0x18]
0x08097C78  ldrb r0, [r7, #1]        ; 不是函数入口
0x08097C7A  strb r0, [r4, #0x16]     ; 写 chapter/battle ID
0x08097C7E  bl    0x0808CC80
```

脚本选择器 `0x0808F544` 根据 `0x020311D4[+0x18]` 选择 primary/alternate 表项，
在 `0x0808F5D0` 调解释器。其上游 caller 是 `0x0808F676` 与
`0x0808F8DE`。因此对 `0x08097C78` 做直接 BL caller 扫描得到零个命中是预期行为，
不能据此认为 SetBattle 无调用来源。

scenario 41 primary `0x08031A12..0x08031D5F` 正常以 opcode `0x00` 终止且没有
opcode `0x1A`。它是 story-only，之后直接进入已有 ID 的战前准备链。

## 战前菜单到真实开始任务的控制流

### 外层菜单归一化

战前菜单控制器是 `0x0808F190`，唯一 caller 为 `0x0808F894`。当
`A882==1` 时，`0x0808F358` 读取 `A880`，并在需要时通过 `0x08097130` 的模式结果
归一化 row，随后使用 `0x0808F39C` 起始的六项 jump table：

| 归一化 selector | 分支 | 结果 |
| --- | --- | --- |
| `0` | `0x0808F3B4` | 内部 state `0x1000` |
| `1` | `0x0808F3C4` | cleanup 后调用 `0x0808E118` |
| `2` | `0x0808F3CA` | cleanup 后调用 `0x0808ECD0`，即队伍/装备子流程 |
| `3` | `0x0808F3D6` | cleanup 后调用 `0x0808768C` |
| `4` | `0x0808F3E2` | 返回 `2`，进入“开始任务”状态 |
| `5` | `0x0808F3EC` | 返回 `3`，直接进入地图/部署控制器 |

不要把屏幕上的可见序号机械等同于该归一化 selector：`0x0808F35C..7E` 会在
`0x08097130()!=0` 时重映射部分值。运行探针应记录确认瞬间的最终 `A880` 以及
`0x0808F190` 返回值。

队伍/装备控制器 `0x0808ECD0` 只由 `0x0808F474` 调用。它内部循环：

```text
state 0x00 -> 0x0808E1D0  队伍页
state 0x10 -> 0x0808E6F4  装备相关页
state 0x40 -> 0x0808E954  另一装备/详情页
```

子页返回 `-1` 时退出到外层菜单。这里没有跳到章节 selector 或 opcode handler 的
路径；所以在队伍页继续按 A/方向键并不会自动变成“开始任务”。正确操作边界是先退出
该嵌套页，再在外层菜单选择会令 `0x0808F190` 返回 `2` 的项目。

### “开始任务”状态机

`0x0808F894` 收到 menu result `2` 后：

```text
[0x020311D4 + 0x12] = 0x1000
r8 = 3
```

主状态机 `0x0808F73C` 对 state `0x1000` 在 `0x0808FA0A` 调
`0x08086A54`。该函数不是单个布尔“队伍是否有效”检查，而是完整、可取消的开始任务
交互：

```text
0x08086A54
  state 0:
    0x08085DF0(0)             “开始任务？”类确认
    result 0 -> return 0      取消，回外层菜单
    result 1 -> state 1
  state 1:
    0x080861C8                编成/出击成员设置循环
    result -1 -> state 0
    result 6  -> state 2
    result 0/1/2 -> 对当前成员打开对应详情/术/装备子页，再回 state 1
  state 2:
    0x080868AC(0)             部署/位置确认
    result 0 -> state 1
    result 1 -> 写 battle_control+6，return 1
    result 2 -> return 0
```

在 `0x08086BF0..0x08086C0E`，部署确认 result `1` 才使 `0x08086A54` 返回
`1`；一般 battle ID 下 `0x0202680A` 写 `0`，ID `0x26` 特例写 `0x0F`。

外层收到成功后把 state 改为 `0x0110`，下一轮在 `0x0808FA1C` 调
`0x08086FEC`。取消则在 `0x0808FA20` 回到 state `0x20` 的战前菜单。

### 不经过新 SetBattle opcode 的 battle-control 建立

`0x08086FEC` 是开始任务和直接查看/部署路径共用的控制器。关键复制位于：

```text
0x080871B4  ldr  r4, =0x02026804
0x080871B6  ldr  r5, =0x020311D4
0x080871BE  ldrb r1, [r5, #0x16]
0x080871C0  strb r1, [r4, #1]       ; 0x02026805 = battle ID
0x080871C2  ldrb r0, [r5, #0x19]
0x080871C4  strb r0, [r4, #2]       ; 0x02026806 = secondary ID
```

之后该函数还会调用 `0x080868AC(1)`、`0x08075184`、`0x080732B4` 完成地图/战斗
准备。scenario 41 已有 `0x020311D4[+0x16]=41`，因此这里能直接得到
`0x02026805=41`，无需再次运行 `0x0808F544` 或 opcode `0x1A`。

这也解释了先前 transient 样本为何能短暂看到 battle 41：battle control 和 map 可以在
共用控制器中建立，但若导航随后取消、返回或继续进入队伍页，最终 settle 仍会清零。
所以单次非零 battle ID 仍不足以证明真实可操作战斗；只是“必须有新 SetBattle hit”这一
门槛同样不正确。

## 下一次运行探针建议

优先从 scenario 41 preparation checkpoint 做只读 watch/hook，按以下顺序记录：

1. `0x0808F350`：`A882==1` 时记录原始 `A880`；
2. `0x0808F392`：记录 jump-table 最终目标，确认归一化 selector 为 `4`；
3. `0x0808F8BE`：确认 menu result `2` 将 outer state 写成 `0x1000`；
4. `0x0808FA0A` / `0x08086C0E`：确认开始任务控制器进入且最终返回 `1`；
5. `0x080871BE..C4`：确认 `0x020311D4 +0x16/+0x19` 被复制到
   `0x02026805/+06`；
6. 完整 settle 后再检查 battle/map/formation，并用下一次 A 必须打开真实战斗行动菜单
   的既有门禁排除“查看战场”或返回队伍页假阳性。

仍可保留 `0x0808F5CC` selector 与 `0x08097C6C` opcode hook 作为诊断信息，但对
scenario 41 这条路径两者的新增 hit count 应允许为零。最有判别力的控制条件是
`menu result 2 -> state 0x1000 -> 0x08086A54 return 1 -> 0x080871BE copy`。

本轮没有执行写入式运行探针。一次对稳定 checkpoint 的零输入 watch 尝试因没有新写入而
超时，只能说明静止页面不会自行改写这些字段，不构成正向运行时证据。
