# Direct-call-proven CFG 根增量（2026-08-11）

## 结论

基准 ROM（SHA-256
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`）中，
对两个固定 Thumb 目标执行全 ROM、2 字节对齐的 BL 解码扫描，分母精确为三条：

| producer | 原始字节 | target |
|---:|---|---:|
| `0x073688` | `0e f0 72 fa` | `0x081B70` |
| `0x07443C` | `fd f7 34 ff` | `0x0722A8` |
| `0x074918` | `fd f7 c6 fc` | `0x0722A8` |

两 root 均不属于冻结的 v2/v3 CFG 指令入口。新遍历把 v2/v3 的有效指令入口作为
opaque stop：命中入口只记录 cross-edge，不再解码；命中基线指令中部或跨越其字节
立即失败。合并增量为：

- 2 个 root；
- 6,166 条 Thumb 指令；
- 1,203 个 basic block；
- 12,966 个可达指令字节；
- 259 条基线 cross-edge（v2 256、v3 3；call 256、branch 3）；
- 28 个 frontier（27 个 `indirect_pc_target`、1 个 `decode_failure`）。

## 产物与证据身份

- artifact：`artifacts/rom-cfg-proven-roots-v1/`
- manifest SHA-256：
  `ea1230fe24cf111a91044c059468a1467e46c471363780b23c2a0311bab8644a`
- payload SHA-256：
  `7fdee7d0d62d3a8c82bfe7b03804e9cb0e3d213ebdf63acce6b0533045aecf54`
- graph denominator SHA-256：
  `19898402cc7c168863a61114fa6e28bef12497724b631373f75cf364d370c024`
- verifier SHA-256：
  `693d9381f429346376a6400bea20025ca0c56e1e68d0bf3164b070ea722aa4d7`
- frontier vector SHA-256：
  `e426acd731a1de146e09c4446420c89a76439fba22e9db7b5238e16c532f1512`
- cross-edge vector SHA-256：
  `897401ae862b45444bd17792af2331def5be3b0a3426e67dde62c53cbae38739`

独立 verifier 不导入新 exporter；它从原始 ARMv4T 位编码重建 producer、root、
v2/v3 入口集合、worklist、block、frontier、cross-edge、root 汇总、graph 和完整
manifest。即使篡改 cross-edge 后同步重算 payload/manifest 文件哈希也会失败。

## Coverage 接入

12,966 个 delta 字节中有 20 字节已被更具体的 battle-effect consumer code slice
拥有，因此只提升仍为 unknown 的 12,946 字节。三条 producer 与 delta 不重叠，
原先也都为 unknown，另按 `thumb_bl_direct_call_producer` 单列 12 字节。

接入后的全 ROM 状态为：

- classified：6,002,861 / 6,291,456（95.4129%）；
- unknown：288,595（4.5871%）；
- 新增净分类：12,958 字节；
- ROM gate 结构化 verifier：37 个。

## 复现与资源边界

高开销导出和验证必须通过 `tools/run_guarded.py`。本轮正式导出峰值约 171 MiB，
独立验证约 155 MiB，coverage 双遍重建约 212 MiB；均未启动 mGBA。

```bash
python3 tools/run_guarded.py \
  --summary build/experiments/active/cfg-proven-roots/verify.guard.json \
  --cwd . --max-tree-rss-mib 1024 --wall-timeout-s 360 \
  -- python3 tools/verify_rom_cfg_proven_roots.py \
  --root . --artifact-dir artifacts/rom-cfg-proven-roots-v1
```

## 不声明的内容

- 不声明两个 root 或三条 producer 在自然玩法中已实际执行；
- 不声明全 ROM BL、函数入口或代码图分母完整；
- 不解析 27 个间接目标，也不越过一个 decode failure；
- 不重复认领 v2/v3 字节或已由更具体证据拥有的 20 字节；
- 不把静态 CFG 证据外推为菜单/战斗行为等价、mGBA 发布回归或实体 GBA 验证。
