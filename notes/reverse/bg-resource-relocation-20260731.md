# Regular BG 资源可变长迁移（2026-07-31）

## 结论

`0x0859903C`表的12个有效场景已从固定槽原位回编推进到扩展ROM区域迁移。严格分母为：

- 31份内容：11 graphics、12 palette、8 tilemap；
- 36个互不重叠的物理LZ77 payload；
- 36个descriptor指针字段；
- 全ROM四字节对齐精确指针扫描额外引用0、缺失引用0。

`bg_resource_relocation`继续接受原始解压二进制，压缩后大小不再受旧槽限制。默认把
同内容的全部descriptor别名重定向到一个新payload；也可用经catalog验证的
`target_pointer_offsets`拆分子集。所有编辑验证完成后才返回分配和指针计划。

## 格式与原子门禁

迁移器复用原`bg_resource`的完整catalog和12-entry联合视图，分配前重新验证：

- 4bpp/8bpp graphics均由完整tile组成，解压尺寸保持原consumer契约；
- palette固定384 bytes，tilemap固定32×10 u16／640 bytes；
- tilemap tile index落在对应graphics范围；
- 4bpp palette bank完整16色范围落在192色palette内；
- 8bpp全部像素色号小于192；
- 基准ROM、catalog、区域注册表、物理payload和36个精确引用均未漂移。

任一格式、引用、别名或容量错误会在生成补丁前整体失败，不借用后续区域。

## 区域与容量

注册区域为`0xB00000..0xB40000`（256 KiB）。31份内容在全literal最坏GBA LZ77
编码并计四字节对齐时不超过140,164 bytes。正式preservation结果：

| 项目 | 数值 |
|---|---:|
| 存储payload | 87,037 bytes |
| 实际占用跨度 | 87,085 bytes |
| 起止 | `0xB00000..0xB1542D` |
| 区域剩余 | 175,059 bytes |
| 分配／指针补丁 | 31 / 36 |

## 独立证据与边界

成果位于`artifacts/bg-resource-relocation-v1/`。独立verifier不导入新迁移器或
artifact exporter；它通过旧独立BG审计器的编解码/表重建路径，重新核对catalog、
31/36/36分母、全ROM精确引用、完整spec、区域、实现哈希和16 MiB输出。

区域注册表更新后的受守卫重签导出与独立验证均`completed/0`、非降级，峰值进程树
RSS分别为62.875 MiB和0.91796875 MiB。本里程碑没有运行mGBA，也不证明不同画布
几何、底部运行时填充、修改后场景选择/滚动、OBJ/window/blend或最终像素等价。
