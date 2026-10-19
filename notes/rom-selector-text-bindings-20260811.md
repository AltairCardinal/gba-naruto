# Selector 文本绑定闭包（2026-08-11）

## 结论

基准 ROM SHA-256 为
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
本批只接入两个具有固定 producer、consumer 与 parser 边界的 selector 文本族，共
86 个不重叠范围、816 字节：

- 46 行来源域映射出的 46 条 renderer 文本前缀：324 字节；
- 三路配置域引用的 38 条 copy-parser 文本前缀：316 字节；
- 3 个 `0xFF` 终止配置列表：164 字节；
- 三路配置指针表：12 字节。

artifact 位于 `artifacts/rom-selector-text-bindings-v1/`。manifest SHA-256 为
`05cd987a60990ca6b2d3ee187eae963fd6ac8728ef9b42b92d6b37b5dc4bc031`，
payload SHA-256 为
`8737d04de14949cbbbb9215c892a7776476c4230eb1e2b0c2abbbbe4440ce2eb`。

## 46 行来源域

`0x0808A6AC..0x0808A700` 固定枚举 `0..45`，以 20 字节 stride 读取
`0x0859F5F0..0x0859F988`。46 个来源记录的 byte 1 映射到 46 个唯一文本槽：

```text
01..1F, 2B..36, 38, 3D, 3E
```

`0x0808B2C8..0x0808B57A` 的菜单链只从该枚举结果取 ID，
`0x0808AFE0..0x0808B07C` 再以 19 字节 stride 定位观察区
`0x085A5AB8..0x085A5F65`，最后经 renderer/parser 消费到首个 NUL。因此只能
分类上述 46 个离散槽的 NUL 前缀（含终止符），合计 324 字节。

该观察区不能被称为“63 槽完整表”：另有 `0x08077EE2`、`0x080939D6` 使用同一
基址，但尚无固定索引分母；46 个已引用槽的 550 字节 NUL 后零后缀也不被 parser
消费，继续保持 unknown。

## 三路配置域

`0x0808CC80..0x0808CCB4` 的 selector 输出域固定为 `0..2`，索引
`0x085A63E8..0x085A63F4` 的三指针表。三个目标列表位于
`0x085A6344..0x085A63E8`，均由 `0xFF` 终止，共 164 字节、38 个唯一槽引用。
这些引用落入 55×18 的物理表 `0x085A5F65..0x085A6343`；只对 38 个引用槽按
真实 copy parser 的首个 NUL 分类 316 字节。

38 个引用槽的 368 字节 NUL 后零后缀、17 个未引用槽的 306 字节，以及边界字节
`0x5A6343` 均保持 unknown。该证据不声明运行时自然遍历所有配置、Unicode 解释或
安全写回边界。

## 失败关闭与复核

exporter 与独立 verifier 固定 ROM 身份、producer/consumer 指令窗口、枚举界、
映射集合、三路 selector、配置终止符、每条 parser 边界、范围分母及 bundle 哈希；
任一映射越界、槽内缺少 NUL、代码窗口漂移、artifact 文件缺失/增加或 coverage
交叠都会失败。输出目录拒绝仓库根、祖先和符号链接。

```bash
python3 tools/export_rom_selector_text_bindings.py --root .
python3 tools/verify_rom_selector_text_bindings.py \
  --root . \
  --artifact-dir artifacts/rom-selector-text-bindings-v1
python3 tools/audit_rom_byte_coverage.py --root .
```

本批接入后，保守语义分类为 5,981,545 / 6,291,456（95.0741%），unknown 为
309,911（4.9259%）。

## 后续增量

上述数字与“后缀保持 unknown”描述是 2026-08-11 本批完成时的历史状态。后续
`rom-referenced-text-slot-padding-v1` 已仅对实际引用槽的 NUL 后零后缀建立独立
结构证据；2026-08-20 又由 `rom-selector-direct-source-records-v1` 固定并分类
`0x0059F5F0..0x0059F988` 的完整 46×20 字节来源记录。最新 source-record 证据、
失败关闭边界和 coverage 收据见
`notes/rom-selector-direct-source-records-20260820.md`。

随后 `rom-selector-code-windows-v1` 又固定 10 个完整 consumer source window，
只把其中 19 段、1,252 字节 current-unknown 交集分类为 `consumer_code_slice`。这不
改变本页的文本前缀/parser 分母，也不把 63 槽观察区升级为完整文本表；详见
`notes/rom-selector-code-windows-20260820.md`。
