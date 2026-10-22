# Story selector dependency CFG Tier-1 packet

## 结论

本 packet 仅把 ROM `[0x08F544, 0x08F594)` 的 80 bytes 晋升为一条
`armv4t_story_selector_dependency_cfg` Thumb code claim。它绑定 ROM SHA-256
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`，并只读取不可变
`artifacts/rom-post-story-dependency-precoverage-v1`，没有读取 live coverage。

独立 raw verifier 重建了 37 条 Capstone 指令，规范指令向量 SHA-256 为
`45a21a888ddd96cbbaa13236e1b47a2c32d4e0ee08b98f8b5d406d2e771df9e8`，解码末端恰为
`0x08F594`；完整的全 ROM
Thumb BL/B/Bcond internal-entry 分母恰有两项：`0x08F676` 因 source 仍为 unknown 而拒绝，
`0x08F8DE` 因 owner 为 `story-callback-reachable_thumb_code-04-08f872` 而接受。固定 Thumb
root pointer 出现数为 0。

## 边界证据

- 三个 direct BL 在 `0x08F582`、`0x08F588`、`0x08F590` 终止于既有 opaque owner；
  `0x065404` 的 `consumer_code_slice` 仅称 coarse owner，不作为指令 membership。
- 唯一 PC-relative LDR 位于 `0x08F552`，消费 preowned word `[0x08F5B0,0x08F5B4)`；该
  literal 不重复 claim，也不解释其业务语义。
- root 末端 fallthrough `0x08F594` 进入既有 `chapter-root-table-selector` coarse owner。
- root 恰为 80 current-unknown bytes，0 holes、0 frontier；投影后 unknown 从 88,727 降至
  88,647，但这只是 Tier-1 immutable precoverage 投影，不是 canonical coverage rebuild。

## TDD 与复现

RED：先新增测试并运行
`python3 -m unittest tests.test_export_rom_story_selector_dependency_cfg`，因 exporter 尚不存在而
以 ImportError 正确失败。GREEN：最小实现后同命令通过。父代理只读审查随后发现两项
P1：初版没有从 raw 指令向量重建全部 control-flow 分母，且普通 `rename()` 存在
no-replace TOCTOU 窗口。两项均新增定向 RED，分别改为独立 worklist/向量/opaque-call/
literal/hole/frontier 重建和平台原子 `RENAME_NOREPLACE` 后，packet 10/10 通过。最终
immutable precoverage + 两个 packet + 两组 Tier-1 的合并守卫为 32/32，峰值
341.57421875 MiB，非降级。

正式复验：

```text
python3 tools/verify_rom_story_selector_dependency_cfg.py --root . \
  --artifact artifacts/rom-story-selector-dependency-cfg-v1
```

返回 `verified=true`、`promotion_bytes=80`。最终 manifest / payload / verifier SHA-256 为
`c810e710...19ec` / `9909ace4...676` / `5bafd0fe...9d10`。原子 no-replace、输出 traversal、symlink ancestor、
artifact member symlink、extra member、payload mutation 与代表性 ROM byte mutation 均由定向测试
失败关闭。实验 receipt 位于
`build/experiments/active/story-selector-dependency-cfg-20260905/receipt.json`。

## 非声明项

本 packet 不证明自然运行时可达、完整 callee 或 ABI、selector 业务行为、literal 值语义、
computed/RAM/indirect producer 穷尽、邻接字节或 hole、可编辑性、写回/重定位安全以及
free/allocatable space。`consumer_code_slice` 只作 coarse owner 边界。

## Tier-1 队列

本包与先前 `rom-fixed-index-u8-tail-v1` 累计为 2 packets / 84 bytes / 2 claims；线性
current-unknown 投影为 6,202,813 classified / 88,643 unknown /
98.59105745951334%。尚未达到 4 packets、10 KiB 或 0.15 个百分点任一 Tier-2 门槛，
因此 canonical coverage、proof 与 formal 均未重建。
