# Group 6 (sequence 8 / resource_group 6) 入口审计 v2（2026-08-06）

## 摘要

Group 6 / sequence 8 的真实入口由三层 dispatcher 串联，**全部静态可定位**：
- 内层 dispatcher `0x0807C93C`（push {r4-r7, lr}; mov r7, sl; ...）
- 中层 dispatcher `0x0807B8B8`
- 中层 case 10 handler `0x0807B9C0`
- 内层 case 8 handler `0x0807CCA8`

dispatcher 链路的最外层是 dynamic callback 调用，**需要 mGBA AI selector tracer**
找到具体 action/tool 触发器（继承 handoff 第 5.1 节 Group 12 的入口策略）。

## v1 → v2 增量

v1 记录：17 个 selector callsite 全部跳转到通用 binder `0x0807FE2C`，
dispatcher 函数起始在 >16KB 之外无法定位。本 v2 进一步反汇编 caller 链，
定位到三层 dispatcher 完整链路。

### 中层 dispatcher `0x0807B8B8`

入口字节序（Thumb 反汇编）：

```text
0x0807B8B8: PUSH {r4-r5-r6-r7, lr}; MOV r7, sl; MOV r6, sb; MOV r5, r8
0x0807B8C0: PUSH {r5-r6-r7}; SUB sp, #0x18
0x0807B8C4: ADDS r6, r0, #0          ; r6 = structure pointer (entry arg)
0x0807B8DA-D8: 检查 structure 字段是否越界（>0xe3 跳出）
0x0807B8E4: 初始化循环变量：r7=0, sl=0, [sp+0xc]=0, [sp+0x14]=structure+0x2d
0x0807B900-08: 检查 sl 与 side_count；超出则跳到函数末尾 0x0807C0CE
0x0807B90A-2A: 计算 side 偏移、sb = unit_state pointer
0x0807B934-38: 检查 unit_state[0]; 若为 0 跳到 next unit
0x0807B93A-48: 取 [unit_state + 8]; AND 0x3F; SUB 4; CMP 0x15; 范围 4..25
0x0807B94C-54: switch case dispatch（21-case table at 0x0807B966）
```

中层 dispatcher 遍历 side × unit，**对每个有效 unit** 调用对应 case handler。

### 中层 case 10 handler `0x0807B9C0`

```text
0x0807B9C0: LDRB R0, [r6, #1]        ; R0 = structure[1]
0x0807B9C2-6: BL 0x0807B2B0 (side effect)
0x0807B9CA-CC: BL 0x080798A4
0x0807B9D0-1E: 加载并 setup sb/r8
0x0807BA0E: BL 0x0807C5E8
0x0807BA18: BL 0x0807AE04(R1=6, R2=0x10) ; side effect handler
0x0807BA1C-66: 计算 phase anchor（X/Y）
0x0807BA70: BL 0x08080108 (spawn obj allocator)
0x0807BA76-7C: 准备 R0=structure, R1=[r6+1], R2=sl, R3=[sp+0xc]
0x0807BA7E: BL 0x0807C93C              ; ← 调内层 dispatcher
```

也就是说 case 10 handler 触发 Group 6/7/8/9/10/12/13/16/18 真实特效事件链：
1. 处理 side effect
2. 算 phase anchor
3. spawn obj
4. 调内层 dispatcher

### 内层 dispatcher `0x0807C93C`

入口字节序：

```text
0x0807C93C: PUSH {r4-r5-r6-r7, lr}; MOV r7, sl; MOV r6, sb; MOV r5, r8
0x0807C944: PUSH {r5-r6-r7}; SUB sp, #0x1c
0x0807C948: STR r0, [sp]              ; sp+0 = structure
0x0807C94E: STR r1, [sp, #4]          ; sp+4 = event
0x0807C954: MOV sl, r2                ; sl = side_left
0x0807C95A: STR r3, [sp, #8]          ; sp+8 = unit_index
0x0807C95E: STR #0, [sp, #0xc]        ; sp+12 = output init
```

函数体从 `0x0807C93C` 到 `0x0807DCB4`（BX r1 末尾）跨度约 5.4 KB。

### 内层 case 8 handler `0x0807CCA8`（Group 6 sequence 8）

```text
0x0807CCA8: LDR r3, [sp]
0x0807CCAA: LDR r4, [pc, #0x84]
0x0807CCAC: ADDS r0, r3, r4; ADD r0, sb
0x0807CCB0: LDRB r0, [r0]
0x0807CCB2: CMP sl, r0                 ; side_left vs [structure+sb+offset1]
0x0807CCB4: BNE 0x0807CD02             ; 不等则跳出 case
0x0807CCB6-C2: 比对 unit_index
0x0807CCC4: MOVS R0, #8
0x0807CCC6: BL 0x0807FE2C              ; 通用 binder 选 sequence 8
0x0807CCCA-CC: 处理返回值
0x0807CCD0-D6: 加载并计算 task offset
0x0807CCDC-DE: 处理 [R1, #0x20] task 字段
0x0807CCF6: BL 0x08080108              ; spawn / sequence submit
0x0807CCFC-FE: 0x70 → BL 0x08061E6C    ; 部分清理
```

Group 6 入口触发条件（**所有四个**都满足时调 binder）：
1. dispatcher `0x0807C93C` 被调用（参数 R0=structure, R1=event, R2=side_left, R3=unit_index）
2. `[structure + sb + offset1]` byte == side_left
3. `[structure + sb + offset2]` byte == unit_index
4. `[structure + offset3]` 半字 & 0x3F == 8（switch case）

### dispatch table（在 `0x0807CABA`，内层）

| table index | case | handler | group/seq |
|---:|---:|---|---|
| 5 | 6 | 0x0807D078 | (group 5 / seq 7) |
| 7 | **8** | **0x0807CCA8** | **group 6 / seq 8** |
| 13 | 14 | 0x0807CD3C | group 12 / seq 14 |
| 14 | 15 | 0x0807CE1C | group 13 / seq 15 |
| 16 | 18 | 0x0807CEE0 | group 18 / seq 7 |
| 17 | 19 | 0x0807D2F4 | group 16 / seq 19 |

（其它项指向 `0x0807DCA4` 函数末尾 fallback）

### dispatch table（在 `0x0807B966`，中层）

| table index | case | handler | 备注 |
|---:|---:|---|---|
| 0 | 4 | 0x0807BB08 | |
| 6 | 10 | **0x0807B9C0** | Group 6/7/8/9/10/12/13/16/18 入口 |
| 12 | 16 | 0x0807BC6C | |
| 18 | 22 | 0x0807BCE8 | |
| 21 | 25 | 0x0807BCE8 | |

其余跳 `0x0807BEB0` 中层 fallback dispatch。

### 中层 fallback dispatcher `0x0807BEB0`

```text
0x0807BEB0: LDR R0, [R6, #8]
0x0807BEB2: ADDS R0, #0xC0
0x0807BEB4: LDR R1, [R0]
0x0807BEB6: MOVS R0, #0xE
0x0807BEB8: ANDS R1, R0               ; state & 0xE
0x0807BEBA: CMP R1, #8
0x0807BEBC: BLS 0x0807BEC0
0x0807BEBE: B 0x0807C096
0x0807BEC0-C8: switch dispatch (table at 0x0807BECE)
```

中层 fallback dispatch table（在 0x0807BECE）：

| table index | state & 0xE | handler |
|---:|---:|---|
| 0 | 0 | 0x0807BEF4 |
| 1 | 1 | 0x0807C096 |
| 2 | 2 | 0x0807BFE0 |
| ... | ... | ... |

`0x0807BEF4` 与 `0x0807BFE0` 都先调 `0x0807AE04(R1=6, R2=0x10)`，然后处理 side
effect 与 phase anchor，最终再调内层 dispatcher `0x0807C93C` 或返回。

## 上层调用方（仍未解）

- 中层 dispatcher `0x0807B8B8` 没有 BL caller（`find_thumb_calls` returns 0）
- 没有指针引用
- 4 个 thunk caller (`0x0807F150/0x0807F184/0x0807F1D2/0x0807F1DC`) 也都没有 caller
- 推测由 **dynamic callback 或 BLX 寄存器跳转** 调用

**结论**：dispatcher 链路的**最外层触发器必须用 mGBA 追踪**。静态 disasm 已到尽头。

## dispatcher 链路总结

```
  dynamic callback / BLX
       │
       ▼
  ┌────────────────────────┐
  │ 0x0807B8B8 中层        │
  │   21-case switch       │
  │   case 4..25 → case    │
  │   handler              │
  └────────────────────────┘
       │ case 10 → 0x0807B9C0
       │   调内层前处理：
       │   - side effect
       │   - phase anchor
       │   - spawn obj
       ▼
  ┌────────────────────────┐
  │ 0x0807C93C 内层        │
  │   6/8/9/11 inline      │
  │   其余 6 cases 通过    │
  │   13-case switch table │
  │   at 0x0807CABA        │
  └────────────────────────┘
       │ case 8 → 0x0807CCA8
       │   比对 side + unit
       │   + spawn sequence
       ▼
  ┌────────────────────────┐
  │ 0x0807CCA8 case 8     │
  │   MOVS R0, #8          │
  │   BL 0x0807FE2C        │
  │   通用 binder          │
  └────────────────────────┘
       │
       ▼
  sequence 8 task spawned
```

## 下一步

### 不启动 mGBA

1. 把三层 dispatcher 链路 disasm 整理为可重现脚本
   `tools/disassemble_battle_effect_dispatchers.py`（low risk）
2. 写一个 `tools/find_battle_effect_sequence_callers.py` 自动展开
   任意 sequence 的 dispatcher 链（low risk）

### 启动 mGBA（下一个 session）

3. 用 `scenario-50-battle-15-escort-12hp-player-turn.ss9` 作为基础快照
4. 在 Group 13 风格的 AI selector tracer 中追踪 sequence 8 case 触发的
   action/tool
5. 找到真实自然入口后做 confirmation page → phase → pixel A/B

### Group 12（继承同样 dispatcher 链）

6. Group 12 / sequence 14 / action 32 "雷切" 共享同一 dispatcher `0x0807C93C`
7. 找含 action 32 的真实 formation（Lv25 卡卡西特定战斗）作为触发器
8. 复用 Group 13 的 battle 3 → battle 8 路线审计工具

## 不属于本次审计的结论

- 不启动 mGBA。
- 不修改任何受签 manifest。
- 不变更 aggregate verifier / phase / pixel evidence。
- 不创建新 artifact；本笔记是只读的当前状态记录。