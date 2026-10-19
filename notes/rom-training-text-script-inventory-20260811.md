# 训练文本命令脚本清单（2026-08-11）

## 结论

固定表 `0x59A104..0x59A1B8` 有 45 个 u32 槽：ID 0 为 null，ID 1..44 为严格递增、
互不重复的 ROM 指针。消费者 `0x0932DA..0x0932E8` 从 training row 的 `+6` 字节
取得 ID、乘 4 索引该表并调用 `0x067158`。这条固定数据流把 44 个非空槽绑定到训练
命令解释器，而不依赖“字节看起来像文本”的启发式。

解释器有 14 项 dispatch；这 44 条记录均使用固定 opcode 序列
`[1, 5, 4, 12, 3, 0]`。opcode 5 的内嵌文本由实际 renderer/parser grammar 界定，
最后一条记录由真实 opcode 0 在 `0x007F1D` 终止，不借用下一指针猜测尾界。结果为：

- 44 条连续记录，范围并集 `0x007554..0x007F1D`；
- 264 条命令；
- 44 段内嵌 renderer 文本，共 1,889 字节；
- 记录总计 2,505 字节，无间隙、交叠或解析失败；
- 180 字节指针表已由既有候选覆盖层分类，本成果不重复认领。

## 可复验产物

- artifact：`artifacts/rom-training-text-script-inventory-v1/`
- exporter：`tools/export_rom_training_text_script_inventory.py`
- independent verifier：`tools/verify_rom_training_text_script_inventory.py`
- tests：`tests/test_export_rom_training_text_script_inventory.py`、
  `tests/test_audit_rom_byte_coverage.py`、`tests/test_audit_reverse_engineering_proof.py`

```bash
python3 tools/export_rom_training_text_script_inventory.py --root .
python3 tools/verify_rom_training_text_script_inventory.py \
  --root . \
  --artifact-dir artifacts/rom-training-text-script-inventory-v1
python3 tools/audit_rom_byte_coverage.py --root .
```

关键固定摘要：

- table SHA-256：`98b063cc49b8ab7b036b612bd81fb3f564187b54fd963e36c9cdc78909d9876b`
- record-range denominator：`d4658b515cf3f02813546f9ae909a0a00a646a70096470f1475695f9b46ede94`
- command-range denominator：`6c055dc42bb2012bfb1879a07ffcdc765cfe67b129ca8f68f48677b10ab9a4db`
- packed bundle：`fa9991353e99ecd63d8e0617fb078198b62527d548c8c5eb5fbac173d0302da0`

## 边界

本成果证明固定消费者与解释器可消费这些 ROM 字节，不证明自然玩法一定执行全部 44
个 ID，也不提供 Unicode 转写或安全写回。任何扩展必须继续以固定 producer/consumer
分母、实际 parser 边界、ROM 哈希和独立 verifier 失败关闭；不得把邻接未知字节并入。
