# 菜单／剧情立绘可变长迁移（2026-07-31）

## 结论

菜单与剧情共311个可见立绘形成74种逻辑`(graphics,palette)`组合；底层实际是
70个LZ77 graphics指针和70个128-byte palette指针。`0x085A4DEC`的63×5矩阵
加全局variant 5共有311个pair、622个四字节指针字段。全ROM四字节对齐精确扫描
得到expected=actual=622，额外和缺失引用均为0。

`menu_portrait_relocation`构建类型继续接受80×80 indexed PNG，复用已验证的六段
1D OBJ逆变换，并把6400-byte图形确定性压缩、palette转为BGR555。每个逻辑pair
可默认迁移全部可见别名，也可用`target_pair_pointer_offsets`显式拆分catalog
允许的子集。resolver在生成任何补丁前完成PNG、provenance、别名、区域容量和
全部引用验证，因此失败不返回部分计划。

## 区域与容量

图像区域注册表将原`future-image-resources`无缝细分为：

- `menu-portraits`：`0xA80000..0xB00000`，512 KiB；
- `regular-bg`：`0xB00000..0xB40000`，256 KiB；
- `battle-effects`：`0xB40000..0xB50000`，64 KiB；
- `story-visual-layers`：`0xB50000..0xB71000`；
- `future-image-resources`：`0xB71000..0xC00000`。

512 KiB可容纳70份6400-byte图形在全literal最坏LZ77编码下的存储，加70份
128-byte palette及四字节对齐。正式preservation迁移结果：

| 项目 | 数值 |
|---|---:|
| 逻辑立绘／pair | 311 / 74 |
| 物理payload | 140（70 graphics + 70 palette） |
| 重定向指针 | 622 |
| 存储payload字节 | 230,251 |
| 实际占用跨度 | 230,344 |
| 起止 | `0xA80000..0xAB83C8` |
| 区域剩余 | 293,944 |

## 独立证据与边界

成果位于`artifacts/menu-portrait-relocation-v1/`。独立verifier不导入新的
importer或exporter；它复用旧独立审计器的独立LZ77实现，从ROM、portrait catalog、
PNG哈希、完整spec、区域注册表和实现哈希重新建立74/140/622分母，重建16 MiB
输出。重新签名后删减summary或把`not_proved`改成过度声明都会被拒绝。

区域注册表更新后的受守卫重签导出峰值进程树RSS为64.74609375 MiB，独立验证峰值
为47.8515625 MiB，均`completed/0`、非降级。本里程碑没有运行mGBA，并明确不证明：

- 80×80以外的任意尺寸或可变OBJ组件布局；
- 修改后所有菜单、剧情、调色变换和转场的运行时像素等价；
- 其他图像family可直接复用portrait布局。

它证明的是已知311个菜单／剧情立绘可摆脱原压缩槽容量限制并安全迁移。
