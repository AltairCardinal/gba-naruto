# 固定消费者文本表闭包（2026-08-11）

## 结论

基准 ROM `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
中，9 张固定 ROM 指针表可由实际 Thumb 消费者静态绑定到 renderer/parser。固定分母
为 575 个槽（含 1 个显式空槽）、570 个唯一记录；保守分类 2,300 个表字节与 6,780 个
parser 实际消费字节，共 9,080 字节。记录间隙、运行时索引上界、自然玩法全槽可达、
Unicode 解码和安全写回均未声明。

| 表 | ROM 半开区间 | 槽 / 唯一目标 | 消费字节 |
|---|---:|---:|---:|
| UI summary name | `0x5A65C8..0x5A65EC` | 9 / 9 | 383 |
| low-detail action name | `0x5A6D04..0x5A6E60` | 87 / 86 | 728 |
| passive auxiliary text | `0x5A7060..0x5A7114` | 45 / 44 | 364 |
| passive detail name | `0x5A73E0..0x5A7494` | 45 / 44 | 364 |
| ninja-tool detail name | `0x5A7C50..0x5A7DC8` | 94 / 93 | 917 |
| unit name | `0x599280..0x59937C` | 63 / 63 | 447 |
| active-action name | `0x59937C..0x5994D8` | 87 / 87 | 731 |
| message-command text | `0x599634..0x5997C4` | 100 / 99（槽 94 为空） | 1,065 |
| passive description | `0x5AAEDC..0x5AAF90` | 45 / 45 | 1,781 |

## 消费者与语法证据

- 前五条消费者分别在 `0x08078436`、`0x08071176`、`0x0808189E`、
  `0x08078812/0x0807884E` 与 `0x080711C8` 一带装载固定表 literal，以索引×4 取出
  指针，再直接调用 parser `0x0806626C` 或经 bridge `0x08066758` 转发。
- verifier 解码并断言 bridge 在 `0x08066760` 捕获、`0x08066788` 转发源指针，
  `0x0806678A` 调用 parser；不是只比较一段实现哈希。
- parser 以 `0x00` 终止；控制字节 `0x01` 宽 2、`0x02` 宽 3、`0x80..0x9F`
  宽 2；有效 SJIS 对宽 2，其余宽 1。SJIS 判断绑定 `0x08065E80` 与
  `0x0853D644` 的 31×8 范围表。
- `ninja-tool` 消费者把索引掩码到 7 bit，静态域仍宽于物理 94 槽；因此 artifact
  明确保留 `runtime_index_bounds_proven=false`，不能凭表存在声称全部运行安全。
- 新增四表分别绑定 `0x08070F32`、`0x080796D8`、`0x08079668/0x080796E4`
  与 `0x080926EC/0x08092718/0x080927D8` 的索引、载入和 bridge 链。message-command
  的 `0x80..0xE3` 静态域完整证明 100 槽，并把 command `0xDE` 的空槽保留为 null。
- `0x5A7FCC..0x5A802C` 是 24 槽混合 UI 资源表；后 6 槽不是文本，且没有 producer
  证明索引只落在前 18 槽，因此整个文本前缀按失败关闭原则排除。

## 复现与边界

```bash
python3 tools/export_rom_fixed_consumer_text_inventory.py --root .
python3 tools/verify_rom_fixed_consumer_text_inventory.py \
  --root . \
  --artifact-dir artifacts/rom-fixed-consumer-text-inventory-v1
python3 tools/audit_rom_byte_coverage.py --root .
```

验证产物位于 `artifacts/rom-fixed-consumer-text-inventory-v1/`。manifest SHA-256 为
`1ca5109d14b8f15faee777034525b36e08669bc20ab67a6639cf90b750e1d375`，顺序字节 bundle
SHA-256 为 `44901041d05432a598de86315e546170a3714350d566db6d9ea62ce4ce5d7c43`。
接入后逐字节清单为 5,989,903 classified / 301,553 unknown（95.2069% / 4.7931%）。

## 后续审计说明（2026-08-22）

本页上方的 9 表、575 槽（1 个空槽）、570 记录及旧 manifest/bundle 哈希，是
2026-08-11 首次闭包的历史快照，不是当前同路径 artifact 的 live summary，不能据此
缩小当前分母。后续 additive 扩展已经把当前权威 artifact 固定为 11 表、750 槽
（11 个显式空槽）、735 条 parser-bounded 记录，合计 3,000 表字节与 11,177 个
parser 消费字节；当前 manifest/payload SHA-256 分别为
`560464a6fed43de1a77c6339362dc2ef28534a7374ff976df572d05a9bad6b94`、
`fd73b9dedf34aee5a4537c451f30d8479dd43f849dfb3ab81c18360a0883e461`。

文件 `[0x0053D714,0x0053D73C)` 的五个 SJIS empty lookup rows 是 2026-08-22
单独接入的 coverage additive claim。它复用当前 fixed-consumer 的 lookup/parser
selector 与 dialogue-font owner 证据，但不倒灌为 2026-08-11 九表版本自身的历史
结论，也不把这些全零行称为 padding、reserved/free space、自然不可达、完整 Unicode
或可安全编辑区域。
