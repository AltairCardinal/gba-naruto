# 直接图像调色板可变存储迁移（2026-07-31）

## 结论

所有已严格证明由ROM直接复制到PRAM的图像调色板已具备可变存储迁移能力：

- 18个逻辑源收敛为17个物理资源；
- 29个四字节对齐精确根指针，额外未知引用为0；
- 3个LZ77调色板固定解压为96 bytes；
- 14个raw BGR555物理资源合计672 bytes。

新`direct_image_palette_relocation`构建类型必须一次提供完整17项。每项可修改
全部未锁定BGR555颜色，但保持原解压或raw长度；LZ77压缩长度不再受原槽限制。

## 别名与跨域锁

`0x08406010`不是独立物理资源，而是`0x08405FF0+0x20`的range alias。迁移后该
逻辑根继续指向父资源新地址加`0x20`，不得为它分配第二份内容。

父资源`0x08405FF0`的`+0xB8..+0x100`共72 bytes同时属于从`0x084060A8`开始的
剧情LZ77流。调色板域只能读取并原样保存这段字节；任何编辑都会在生成补丁前失败，
避免破坏另一资源域。

## 区域与容量

图像区域注册表新增：

- `direct-image-palettes`：`0xBC0000..0xBC0400`；
- `future-image-resources`相应收缩为`0xBC0400..0xC00000`。

完整保持迁移生成17个allocation和29个pointer patch，共46项安全写入。存储载荷
786 bytes，占用跨度788 bytes，末端`0xBC0314`，区域剩余236 bytes；输出ROM为
完整16 MiB。

## 独立证据

正式成果位于`artifacts/direct-image-palette-relocation-v1/`。独立verifier不导入
生产迁移器或导出器；它重新解析基准ROM、LZ77 inventory、graphics catalog和
direct CpuSet inventory，自行执行LZ77编解码、全ROM指针扫描、区域布局检查及
preservation/capability两次16 MiB重建。

验证同时覆盖：

- 18/17/29严格分母、3个LZ77与14个raw物理资源；
- range alias仍为父地址加`0x20`；
- 72-byte跨域锁不可修改；
- 17个物理资源与18个逻辑源均可通过非锁定字节产生变化；
- 重签后的分母、spec、实现哈希、文件集合和全局区域重叠篡改均被拒绝。

受守卫的目标测试峰值进程树RSS为74.984375 MiB，正式导出为39.8203125 MiB，
独立验证为23.5234375 MiB，均`completed/0`且未降级。本里程碑没有运行mGBA，
因此没有新建快照。

## TDD与全量回归

红阶段依次确认了三个正确失败：

- 缺少direct palette模块与注册区域；
- `build_mod.py`拒绝未知的`direct_image_palette_relocation`类型；
- 统一重建计划仍为23条命令，未包含第12个图像域。

最小实现闭合后，direct importer、独立audit、区域与统一重建目标测试全部通过。
随后串行重建并验证12个图像迁移artifact，25条命令全部成功，峰值进程树RSS为
109.99609375 MiB。完整`test_*relocation*.py`回归共126个测试，使用unbuffered
verbose输出避免长测试被idle守卫误判，最终`completed/0`，峰值125.14453125 MiB；
正式`automated_test.py`为26/26通过。

## 边界

本成果不证明：

- `0x0812D2F0`与`0x083496F8`两条残余图形的palette身份；
- 7条WRAM visual metadata和1条32×20 text-BG tilemap的ABI与迁移；
- PRAM目标地址、copy长度或业务名称可任意改变；
- 修改后自然路线的OAM、window、blend、帧时序和最终屏幕像素等价。
