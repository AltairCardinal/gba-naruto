# ROM Boot Interwork ARM Root（2026-08-11）

## 结论

基准 ROM SHA-256
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
中存在唯一固定 producer spine：

```text
Thumb 0x08061086  BL  0x0809C56C
Thumb 0x0809C56C  BX  pc          ; 切换 ARM，目标 0x0809C570
ARM   0x0809C570  B   0x0800024C
```

这条链允许把 `0x0800024C` 作为一个固定 ROM interwork 证明的 ARM root，但不证明
reset 后每次自然执行都到达该调用点。全 ROM 原始直接分支扫描中，到
`0x0809C56C` 的 Thumb BL 只有 `0x08061086`，到 `0x0800024C` 的 ARM B 只有
`0x0809C570`。相邻 `0x0809C574` 是另一个指向 `0x0800026C` 的 sibling veneer，
不属于本 root。

## 静态闭包

固定 vendored Capstone ARMv4T decoder 与独立 raw-control-flow worklist 均重建：

- root code：`0x00024C..0x0003BC`，92 条指令、368 字节；
- basic blocks：8；CFG edges：10；open frontier：0；
- 实际由 PC-relative LDR 消费的 literal：`0x0003BC..0x0003E0`，9×4=36 字节；
- producer 指令：4+2+4=10 字节；
- coverage 净增：414 字节。

四个 canonical denominator：

- instruction：`c25c738607397cb60f90d73d7a6efe079ef52c89c11f787b0cc7d896101beebf`
- block：`1c9d08d16c2f4c3b5cdb4123d8ae94b6fd3bb4f7921c9a28a55b77f279c3af50`
- edge：`ba298a7c1f9f7811e7dd2ac899c7faa42d013599d9e94a6c41e129b34e7176e7`
- literal binding：`1e812f886d0e0abe614780f0c4a94af1c789831fd966c59e85e0a6ef690f4e9f`

## 可复现成果

- `artifacts/rom-boot-interwork-v1/`
- `tools/export_rom_boot_interwork.py`
- `tools/verify_rom_boot_interwork.py`
- `tests/test_export_rom_boot_interwork.py`

TDD 先确认缺少 exporter 的失败，再实现最小闭包；artifact 定向测试 6/6 通过。
verifier 不导入 exporter，并拒绝将传入 root 的依赖哈希用于另一已加载工作树的
CFG engine。coverage 使用同一 artifact 的固定 manifest、payload、实现与测试哈希，
将 classified 更新为 5,984,699 / 6,291,456（95.1242%），unknown 更新为
306,757（4.8758%）。

## 明确边界

- `runtime_reachability_complete=false`；不声明完整 reset-to-root 动态路径。
- `0x09C56E..0x09C570` 的两字节对齐仍保持 unknown。
- sibling veneer、RAM 数据目标及 RAM code 均不纳入。
- 不把 `0x00024C..0x009F2E` 的约 40 KiB 包络整体认作代码。
- 未启动 mGBA；本里程碑完全由固定 ROM 静态证据闭合。
