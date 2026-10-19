# 场景视觉来源范围字节晋升（2026-08-20）

## 结论

本批复用已验收的 `scene-visual-packs-v1`，没有重新导出画面，也没有扩大其运行时
结论。新 artifact `rom-scene-visual-source-ranges-v1` 从固定 ROM、9 条 source table
记录及真实消费者/parser 独立重建该固定 9-record source table 的完整来源分母，并只
晋升接入前仍为 `unknown` 的字节。

- 固定 9-record source table 的完整 source 分母：57 段、88,756 字节；
- 候选分母：29 段、3,288 字节；
- 既有 primary overlap：1 段、31 字节，位于 pack 5 definition，继续由
  `lz77_syntax_unbound` claim 唯一拥有；
- 本批实际晋升：29 个 claim、3,257 字节；
- promotion range denominator SHA-256：
  `13dc504bebbff131700bb77869afb29e98a2f032d60bab4165eba90bcb2be7df`。

分类分母如下：

| 类别 | claim | 字节 |
| --- | ---: | ---: |
| shared OBJ BGR555 palette | 2 | 64 |
| BG BGR555 palette | 9 | 2,304 |
| parser-bounded definition record | 9 | 697 |
| animation record | 9 | 192 |
| 合计 | 29 | 3,257 |

pack 5 的 candidate 是混合 ownership：GBA 地址 `0x08407BF0..0x08407C0F` 的 31
字节保持旧 LZ77 owner，只有 `0x08407C0F..0x08407C50` 的 65 字节进入本批
promotion。artifact 与
coverage 都不得把 candidate 的混合状态误写为整个范围已知或整个范围未知。

## 失败关闭合同

- 固定基准 ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`；
- 独立 verifier 不导入 exporter 或 coverage auditor，并从 ROM、上游 manifest、
  source table、consumer/parser 与冻结基线重新构建分母；
- 29 段 promotion 必须完整落在接入前 current-unknown，不能切片、跳过或重复认领；
- pack 5 的 31 字节 overlap 必须精确绑定旧 LZ77 primary owner；
- manifest、payload、bundle、命令、实现哈希、范围顺序、类别分母或任一 ROM 字节漂移
  都必须拒绝；
- candidate 中的 mixed slices 只属于 candidate 记录，不得泄漏到 promotion 记录。

关键身份：

- artifact manifest SHA-256：
  `d9440e4ea32db1ea51dc6d00bbb3788c9f79ea5b8d20d0e1444f9a3d07c22baf`；
- payload SHA-256：
  `a4f7c40ea8730ad620faa5fe43abf77a59d3375c31e524d77af30f6828e58df9`；
- promotion bundle SHA-256：
  `2eec5a820e1f79cc817e5976dc710e889adbee1038a4247652812a695832bc95`；
- 独立 verifier SHA-256：
  `91f55da0370db3ae291f0845812b610bf3e2bd71efd8acf8501af62201f9af87`。

## Coverage 与正式证明

接入后机器清单为：

- classified：6,105,378 / 6,291,456（97.0424%）；
- unknown：186,078（2.9576%）；
- claim：13,901；
- segment：16,142；
- coverage SHA-256：
  `02ca4394bd727c9b27c7ac168e12d141af0be4354b185d8242b8c1f66a353bea`；
- coverage auditor SHA-256：
  `876b26d595ac5f6ebb85e3939215f8868b20ef67f5c909edb1afc0337c7f970e`；
- proof spec SHA-256：
  `d11e19eeb9b3697045181fae05197e6c1b85bba66b0dbc9ef88fed695a04bf86`。

受守卫 formal audit 位于
`build/experiments/active/scene-visual-source-coverage/scene-visual-source-coverage-20260820/`：

- report SHA-256：
  `43a7106eeea71c47fa2af02d51b65b5d526ae7f580c142c566c9ace6a4611e58`；
- guard SHA-256：
  `8a36cda8aa593f11bc57f50bb95a036d631d8a5b1368fc71d1ccf7a22c87bbf2`；
- formal auditor SHA-256：
  `4e5b95705a2aa8252da96f927872a6701bb1561b6748230cbc4c209815e28d36`；
- 65/65 个唯一 verifier 均 `exit_code=0`、`contract_ok=true`；
- ROM byte gate 为 55/55；峰值 RSS 522.61 MiB；
- 报告仍正确为 `complete=false`、`claim_status=incomplete`、175 个 blocker。

## 明确边界

本批不声明：

- 57 段 source 都在自然玩法中可达，或该 9-record table 是全部 scene sources 的分母；
- 最终屏幕像素、viewport、BG/OBJ 合成或实体 GBA 等价；
- overlap 中 LZ77 数据的新语义；
- definition 未命名字段的业务语义；
- 相邻 gap、padding 或零字节是可分配空间；
- 任意编辑、写回、指针改写或 relocation 安全。

因此本里程碑只把 3,257 个有固定来源边界的字节从 `unknown` 晋升，不能据此宣称
ROM 字节级逆向已完成。
