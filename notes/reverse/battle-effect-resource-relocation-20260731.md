# 战斗特效资源可变长迁移（2026-07-31）

## 结论

`0x0859911C`表的18个有效graphics/palette pair已从固定槽原位回编推进到扩展ROM
区域迁移。严格分母为：

- 34份按“资源类型+解压SHA-256”去重的内容：17 graphics、17 palette；
- 35个物理LZ77 payload；
- 36个pair-table指针字段；
- 全ROM四字节对齐精确指针扫描额外引用0、缺失引用0。

`battle_effect_resource_relocation`接受原始解压二进制，压缩后不再受原槽容量
限制。默认把同内容的全部pair别名指向一个新payload，也可用经catalog验证的
`target_pointer_offsets`选择子集。所有规格项验证完成后才返回完整分配和指针计划。

## 别名与原子门禁

迁移器从基准ROM和既有独立资源catalog重新建立`36 → 35 → 34`：

- group 2/3共用同一graphics物理指针，默认联动，也可只重定向其中一个pair；
- group 16/17的palette内容相同但物理指针不同，默认按内容合并迁移，也可按指针
  子集保持独立配色；
- graphics必须非空且由完整32-byte 4bpp tile组成；
- palette必须恰好32 bytes／16色BGR555；
- 基准ROM、catalog、区域注册表、全部物理来源和36个精确引用均失败关闭；
- 重复认领、非catalog别名、容量越界或格式错误会在返回补丁前整体失败。

## 区域与容量

图像区域注册表划定`battle-effects`为`0xB40000..0xB50000`（64 KiB），后续图像
区域从`0xB50000`开始。正式preservation结果：

| 项目 | 数值 |
|---|---:|
| 特效group | 18 |
| 内容／物理payload／逻辑指针 | 34 / 35 / 36 |
| 存储payload | 20,216 bytes |
| 实际占用跨度 | 20,260 bytes |
| 起止 | `0xB40000..0xB44F24` |
| 区域剩余 | 45,276 bytes |
| 分配／指针补丁 | 34 / 36 |

## 独立证据与边界

成果位于`artifacts/battle-effect-resource-relocation-v1/`。独立verifier不导入
新迁移器或artifact exporter；它从基准ROM、`0x0859911C`和旧独立原位审计器重建
catalog与LZ77，重新扫描35个源指针的全部引用，验证完整spec、区域、递归文件集合、
verifier命令和实现哈希，再独立重建完整16 MiB输出。

最终受资源守卫的正式导出与独立验证均`completed/0`、非降级，峰值进程树RSS分别
为42.87890625 MiB和0.79296875 MiB。覆盖全部图像迁移、原位回编与构建集成的
121项统一回归耗时249.094秒，峰值进程树RSS 104.47265625 MiB，结果`OK`。
本里程碑只做离线静态工作，没有启动mGBA，也没有触碰Butano工作树。

本成果不证明不同graphics几何、OAM位置、affine参数、动画帧时序、blend/window、
音频耦合或修改后最终运行时像素等价。
