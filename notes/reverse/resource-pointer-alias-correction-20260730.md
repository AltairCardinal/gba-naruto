# Resource-pointer 别名纠正（2026-07-30）

## 结论

历史 `resource-pointers@0x596F0C` 不是独立资源表。它是角色战斗视觉矩阵
`0x596D5C` 的连续五行：

```text
0x596F0C = 0x596D5C + 27 * 16
```

矩阵每个角色有 9 个 visual slot，因此 rows 27..31 对应 character 4 的
visual slots 0..4。五行的
`frame_pointer_table / animation_pointer_table / graphics / palette`
四元组均与
`artifacts/character-battle-visuals-v1/manifest.json` 完全一致。

## 消费者边界

`0x0807B278` 的 literal 是 `0x08596F0C`。`0x0807B220` 将 ID 0..4 和该
基址交给 `0x080625A4` 的 16-byte descriptor 路径。它证明消费者有意选择
角色视觉矩阵的五行 subview，但不能据此把 subview 声明成第二套可独立编辑的
资源表。

## 安全处理

- `sequel/content/resource-pointers/bank.json` 改为空的 `disproved`
  tombstone，并设置 `do_not_write=true`。
- canonical 数据与导出结果由
  `artifacts/character-battle-visuals-v1/manifest.json` 维护。
- legacy `rom_resource_pointers` patch 继续只输出 unmapped 诊断，不写 ROM。
- `tools/populate_bank_json.py` 不再从这五行重新生成错误 bank。

该纠正把 32-bank 分布从 23 active / 9 disproved、13 runtime / 10 code
调整为 22 active / 10 disproved、13 runtime / 9 code。32/32 身份调查闭合
不变。
