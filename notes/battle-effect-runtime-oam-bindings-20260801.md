# 战斗特效持久快照 OAM/VRAM 批量绑定（2026-08-01）

## 结论

无需启动 mGBA，新增批量目录把当前全部 93 个 tracked `.ss9` 与五份既有 accepted
运行时状态逐一解析，并将 active OAM 与 18 组战斗特效的完整 graphics、frame、
component、OBJ VRAM load base 和 OBJ palette 建立内容寻址绑定。

当前 tracked corpus 中有一个快照直接命中特效：

- `scenario-50-battle-15-escort-12hp-player-turn.ss9` 的 OAM 17、18、19；
- 三项均唯一绑定 group 1 / frame 6 / component 0；
- 源 component tile 24，OAM tile 792，因此完整 1,024-byte group graphics 的
  load tile base 为 768，即 `0x06016000`；
- 三项 runtime palette 与源 palette 均为 16/16 色完全一致。

五份补充状态独立覆盖 groups `[1,2,5,11,14]`。因此“已有持久运行时状态中的特效
资源身份”覆盖为 5/18（27.78%）；其中 group 2 是 affine runtime golden，只有
groups 1/5/11/14 具 production natural pixel A/B，所以像素 A/B 覆盖仍为 4/18
（22.22%），本目录不提高该分子。

## 分母与父证据

`runtime-screen-composites-v1` 固定了 91 个 accepted checkpoint 的路径、容器
SHA-256 和 IO/PRAM/VRAM/hardware OAM 哈希。此后 Git 又增加两份确认页快照：

- `scenario-47-fire-action16-confirmation.ss9`
- `scenario-50-cross-shuriken-confirmation.ss9`

目录没有把父 artifact 虚报为 93，而是明确记录 `91 accepted parent + 2
post-parent tracked extensions`，并扫描当前真实的 93/93，解析失败为 0。全部快照
共有 1,254 个 active OAM；一个快照的三个 OAM 命中 group 1。

静态身份父项是 `battle-effect-sprite-animations-v1`：18 groups、178 frames、437
components。四份自然 pixel A/B baseline 和一份 group 2 affine state 只进入
`supplemental_states`，不污染 tracked checkpoint 分母。

## 匹配契约

对每个 4bpp、1D OBJ mapping 的 active OAM：

1. 用 OAM shape/size 限制 source component 尺寸。
2. 计算 `load_tile_base = attr2.tile_index - component.tile_index`。
3. 从 `0x06010000 + load_tile_base*32` 读取完整 group graphics；必须与源资源全部
   字节精确一致，不能只靠 component 局部 tile 碰撞。
4. 对所有完整 graphics 候选比较 OAM 选择的 16 色 OBJ palette，以 BGR555 不同
   颜色数排序。
5. 同 graphics 或重复 frame/component 仍保留歧义。group 2 的两个 affine OAM
   因 frame 0/1 内容身份相同而明确标为 frame/component ambiguous；不借旧标签强行
   消歧。

独立 verifier 不导入导出器，使用既有 GPU decoder 重建 OAM，再独立读取 ROM资源、
PRAM 和 VRAM。它对 93 个 tracked 状态、5 个 supplemental 状态、12 条总匹配得到
逐字段相同结果，并拒绝 frame identity 篡改。

## 复现、资源与产物

```bash
python3 tools/export_battle_effect_runtime_oam_bindings.py \
  --root . \
  --output artifacts/battle-effect-runtime-oam-bindings-v1/bindings.json
python3 tools/verify_battle_effect_runtime_oam_bindings.py \
  --root . \
  --bindings artifacts/battle-effect-runtime-oam-bindings-v1/bindings.json
python3 -m unittest \
  tests.test_export_battle_effect_runtime_oam_bindings \
  tests.test_verify_battle_effect_runtime_oam_bindings
```

导出器加独立验证器的 10 项定向测试约 1.04 秒；`/usr/bin/time -l` 记录最大 RSS
约 25.5 MiB、swap 0。正式成果只有 149 KiB `bindings.json` 和一个 promotion
manifest，没有生成大量 PNG 或零碎调试文件。临时 dry-run 位于 ignored
`build/experiments/`，不进入 Git。

## 边界与下一步

本目录证明完整 group graphics 与 active OAM 的内容身份，不证明：

- 当前 OAM 的 task/selector 排他 writer 或自然动作语义；
- 仅存在于确认页“下一次输入后”才会发生的效果；
- 全部 frame、跨帧 hold、RNG、affine 参数历史、blend/window/audio 耦合；
- 修改 ROM 后的所有组自然最终像素，或实体 GBA 输出。

下一步应复用同一批状态和现有 sprite task pool 目录，批量加入 task pointer triple、
animation/keyframe 和 dispatcher phase；对仍未观察的 13 组，再用通用受控批量回放器
生成少量可恢复状态，而不是逐组手工导航。
