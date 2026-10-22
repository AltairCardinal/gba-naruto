# Battle condition result text（2026-09-02）

## 结论

`rom-battle-condition-result-text-v1` 将完整 battle-condition 物理表中的 active payload
绑定到公共 result renderer/parser，精确分类 219 条 NUL 终止记录、3,961 ROM bytes。
该结论已通过一级快速审计，尚未写入 canonical coverage。

## 冻结分母与消费链

- ROM SHA-256：`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- 条件表：`[0x594758,0x596CCC)`，47 battles × 3 variants × win/lose × 4 slots =
  1,128 rows；898 empty、230 active，219 个唯一 payload targets。
- 候选簇：`[0x007F1D,0x009F2E)`；active targets 全部位于该簇。
- 公共仲裁路径读取 row `+4` payload，并调用 `0x077764` result renderer；后者经
  `0x0667A0` bridge 调用 `0x06626C` parser。字符宽度判定绑定固定 SJIS 表。
- 219 条记录 range-vector SHA-256：
  `7d81f7ec06a8969969305002afc307da90b7f3787f8f958fc5799c72ed844fe4`；
  packed bytes SHA-256：
  `9826a706b7c4e840117c5ff1a3a6c9d06057cac9188c66f2bd523592cf533d91`。

## 产物与验证

- artifact：`artifacts/rom-battle-condition-result-text-v1/`。
- manifest/payload SHA-256：
  `93e3a9f88c95fee8025446616c1fed54b9645a94db5c3d09b4d9fa0f40e769aa` /
  `16457b1e3152451073489cdd6287b6a7429f9b298ba6f4cf8a3216fadcd4b0f2`。
- 独立 verifier SHA-256：
  `ec8de0fe812cf59df0e4e73c9ee1d2e0aa0364442f10921416aa00da05f7c361`；
  canonical report SHA-256：
  `313dd6baaef94a9fa3884764c30510ff6a27539c76d631434367c2379770e017`。
- TDD：初始 RED 因 exporter 缺失正确失败；GREEN 后父代理又用 RED 暴露并修复
  `rom_override` 未绑定整 ROM 身份与普通 rename 可覆盖的发布竞态。最终 packet tests
  6/6、coverage projection tests 3/3、独立 verifier 全部通过。

## Coverage 状态

- authoritative canonical 仍为 6,176,433 classified / 115,023 unknown /
  98.171758651733%，coverage SHA-256 `b71a91d1...ed52`。
- current-unknown/无重叠快速投影为 6,180,394 classified / 111,062 unknown /
  98.23471705118814%，净增 3,961 bytes / 219 claims。
- 本批只有 3,961 bytes / 1 packet / +0.062958 个百分点，未触发 10 KiB、0.15 个百分点、
  4 packets 或 blocker 解锁门槛，因此不单独重跑全量 coverage/formal。

## 明确边界

- 2,782-byte inter-record gaps 不由 parser 消费，继续 unknown。
- `[0x9974,0x9980)`、6-byte script `[0x9980,0x9986)` 与
  `[0x9986,0x9F2E)` 不属于本 packet。
- positions group47 是同一物理数据的别名，不提供第二份独立 provenance。
- 不声明自然执行可达性、Unicode 解码、编辑、写回、重定位或 free space。
