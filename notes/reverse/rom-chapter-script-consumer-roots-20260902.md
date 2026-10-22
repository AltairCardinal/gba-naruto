# Chapter script consumer-bound roots（2026-09-02）

## 结论

- `0x08A548` 的 PC-relative LDR、`0x08A54A MOVS r1,#0` 与
  `0x08A54C BL 0x0977B8` 绑定 root `0x05CD41`。
- `0x08A5E8` 的 PC-relative LDR、`0x08A5F8 MOV r0,r5`、
  `0x08A5FA MOV r1,r6` 与 `0x08A5FC BL 0x0977B8` 绑定 root
  `0x05D593`。
- 两个失败关闭的 parser closure 分别为 `[0x05CD41,0x05D593)`（2,130
  bytes）和 `[0x05D593,0x060C70)`（14,045 bytes），合计 16,175 bytes、
  1,120 nodes、1,322 directed edges、102 terminals、0 frontier。
- consumer slices `[0x08A534,0x08A588)` / `[0x08A588,0x08A638)` 只作为
  数据流证据，不进入 coverage promotion。`[0x05CD40,0x05CD41)` 与
  `[0x060C70,0x060C74)` 继续 unknown。

## 可复验证据

- artifact：`artifacts/rom-chapter-script-consumer-roots-v1/`
- bundle SHA-256：`7e506f02abfe85c21a01066ce010b40d0a43b8d528fb53b77cc3be7cb1b22907`
- manifest SHA-256：`c8d4b29142bed3d8031bb141bbdf409582a01ffa838cd860c23d80a32b695575`
- payload SHA-256：`c0118f0ad71dcabd4e10a057950437528d85aa1abee4b829d92aa6e340d6cb9c`
- exporter / verifier SHA-256：
  `7ec40eb7cd97d875ebbdcdb5359d94c2e55a99bd224c2ad001e9fb9598a503d0` /
  `cfbe787cb884499ee062e56073f33995ad331519a3d31f6cde47bf0efedf8582`。
- exporter 使用 macOS `renameatx_np(RENAME_EXCL)` 或 Linux
  `renameat2(RENAME_NOREPLACE)` 原子发布。故障注入证明 rename 后父目录 fsync
  失败不会误删已发布 artifact。

## Coverage 与 formal

- coverage 复用统一 dependency-packet 投影入口；artifact 身份、独立 verifier、
  current-unknown、逐范围 ROM 哈希与无重叠只执行一套公共门。
- canonical 为 6,176,433 classified / 115,023 unknown / 16,129 claims /
  17,562 segments，即 98.171758651733%；SHA-256
  `b71a91d1e3c469a884f6d434a82ce23e751e201e83728e6ffc040a6226bfed52`。
- proof SHA-256：`8d6ec4cf311bbe420aae318ec70f4f5e85dd89b8f4fe68d8807fdbfcfd2d0c96`。
- formal report SHA-256：
  `b7ff8d64d0a797fa6aa065dc8f056211fad80f3da0c1b80a021f8d2acdf4a289`；
  106/106 contracts、ROM gate 96/96 全部 `contract_ok`。报告保持 incomplete
  是因为仍有 115,023 unknown 及既有发布门，而不是本 packet 验证失败。

## 边界

该成果只证明两个 consumer 所绑定的 parser syntax closure；不证明所有 chapter
script roots、自然剧情可达性、命令业务含义、邻接字节、编辑/重定位/write-back 或
free/allocatable space。
