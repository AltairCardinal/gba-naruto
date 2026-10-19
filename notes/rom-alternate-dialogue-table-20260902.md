# Alternate dialogue table（2026-09-02）

## 结论

`rom-alternate-dialogue-table-v1` 在固定 direct invocation 合同下，精确闭合 20 行
alternate-dialogue table、80 条 renderer-consumed text 与 80 段 parser-bound zero gap，
合计 3,200 ROM bytes / 161 claims。该 packet 已通过一级快速审计，尚未写入 canonical。

## Consumer 与索引分母

- `0x0808F9F0` 固定 `r0=3,r1=0` 并 BL `0x080914D8`。
- `0x080915AC` 以 CpuSet fill32 清零 `0x02002880` 的 224-byte work struct；alternate
  mode 跳过 `[r7+1]=20` 的主表初始化，因此首次 index 精确为 0。
- `0x08091BEC` 完成每轮自增；`0x08091E52 CMP #19` 是循环上界。
- `<=19` 仅能经 `0x08091F76 MOVS r6,#0` 与 `0x08091F82 -> 0x0809182E`
  backedge 再次消费；index 20 跳过 state-zero write、进入退出状态。
- `literal@0x080918EC = 0x08459284` 固定表基址；record stride 20，文本字段在
  `+4/+8/+12/+16`，经 `0x08066758` renderer 与 `0x0806626C` NUL parser 消费。

## 字节分母

- 表 `[0x459284,0x459414)`：20×20 = 400 bytes，SHA-256
  `862744fc83953431199106f3b3d88ffc4b4135eeee9730b26809cf5dd624b6fe`。
- 80 个唯一 NUL targets：1,214 bytes，bundle SHA-256
  `256d059e355d1a4a5af65416f40680bcb2eacdb397e1c71b6d5353522bf954a5`。
- 80 段固定有序 zero gaps：1,586 bytes。它们只以相邻两个实际 target/parser 边界
  或最后 target→table boundary 分类，不推广为一般 padding/free space。

## 产物与 TDD

- artifact：`artifacts/rom-alternate-dialogue-table-v1/`。
- manifest/payload/verifier SHA-256：`f7ded383f1c7334d714337768867496d083a85db051a69688fea121023f121b0` /
  `62576a9d495fb143575f1a9be43816d78806910ea3840db8305e05f4050f696e` /
  `e0e72584e5aef7d6d55f8b9fa6498c67e01f2bb1f849fdbda0848152a82967da`。
- 子代理 RED 6 项因 exporter 缺失正确失败，初始 GREEN 6/6。父代理再以 RED 暴露
  mutable coverage 自失效、promotion metadata 缺失与 verifier 接受嵌套成员；最终
  packet tests 7/7、coverage projection tests 3/3、独立 verifier 通过。

## Coverage 与边界

- 与 condition-result-text 包累计投影为 +7,161 bytes / 380 claims：6,183,594
  classified / 107,862 unknown / 98.28557968139648%。未达到批量门槛，canonical 仍为
  98.171758651733%。
- `[0x45832C,0x458794)` 1,128 bytes 保持 unknown。
- computed/indirect `0x0914D8` producers 未穷尽；不声明所有自然入口、Unicode、编辑、
  写回、重定位或 free/allocatable space。
