# 残余 text-BG tilemap 可变存储迁移（2026-07-31）

## 结论

残余指针可达LZ77分母中唯一已定型的text-BG tilemap现已具备安全迁移能力：

- 源`0x08349368`，压缩178 bytes，解压1280 bytes；
- 唯一全ROM四字节对齐根`0x0808B464`；
- 唯一literal user`0x0808B348`，经`0x0808B34C`调用
  `LZ77UnCompVram_wrapper`加载到`0x06001000`；
- 结构为32×20、640个little-endian u16 entry。

原内容只使用tile 0–5、palette bank 1、0个H flip和12个V flip。新
`residual_text_bg_tilemap_relocation`允许编辑全部640项、tile 0–5及标准H/V flip，
但palette bank必须保持1。

## 区域与容量

图像区域注册表新增：

- `residual-text-bg-tilemap`：`0xBC0400..0xBC0C00`；
- `future-image-resources`：`0xBC0C00..0xC00000`。

原样迁移仍压缩为178 bytes，占用`0xBC0400..0xBC04B2`，形成1个allocation和
1个pointer patch，区域余1870 bytes。任意1280-byte输入的全literal GBA LZ77
最坏为`4+1280+ceil(1280/8)=1444` bytes，最坏末端`0xBC09A4`，2 KiB区域仍余
604 bytes。

## 独立证据

正式成果位于`artifacts/residual-text-bg-tilemap-relocation-v1/`。独立verifier
不导入生产迁移器或导出器；它自行：

- 从固定ROM和inventory重建178→1280-byte LZ77源；
- 复核真实压缩/解压哈希、代码窗口、consumer、完整word直方图和唯一根；
- 验证640项的tile/palette/flip字段；
- 独立重建完整ROM layout partition合同，并检查全部分区唯一、范围合法、按2次幂
  对齐且全局无重叠；随后检查完整图像区域连续、无重叠；
- 重建preservation与修改一个entry的capability 16 MiB ROM；
- 拒绝重签后的summary、spec、tilemap、额外文件和全局区域重叠篡改。

红阶段分别确认模块缺失、区域缺失、统一重建仍只有25条命令，以及正式
exporter/verifier缺失。最小实现后，importer、build wiring、区域和独立audit的
15项目标测试通过。正式导出峰值进程树RSS为39.109375 MiB；独立验证完成且未降级。
加固source/consumer合同后，13个图像artifact的27条统一重建命令全部通过，随后
137项`test_*relocation*.py`跨域回归`completed/0`，峰值123.71875 MiB。

独立审查又用重新签名的恶意layout暴露验证器只核对父分区、未拒绝全局重叠的缺口。
新增测试先确认该攻击被错误接受，再补齐全部partition的version、base、target、
fill、唯一ID、owner、origin、范围、对齐和全局无重叠合同，并固定图像父分区
alignment为4。修复后16项目标测试通过，13域27命令再次在统一heavy lock下重建并
验证，峰值RSS为110.64453125 MiB；正式自动化检查26/26通过。本里程碑没有运行
mGBA，因此没有新建快照。

## 边界

ROM源字节不与其他LZ77流或相邻raw palette重叠，但`0x08405F10`的另一条流也可能
在不同时间使用`0x06001000`。当前没有证据证明两者共存或互斥。本成果还不证明：

- text-BG对应的graphics/palette/BG2归属已由后续
  `residual-text-bg-tilemap-resource-ownership-v1`闭合，并被本迁移链固定；
- 精确自然语言业务身份；
- 32×32 screenblock中未由1280-byte payload覆盖的剩余12行；
- `0x0808B352→0x08067158`调用的语义；
- 修改后自然路线的加载顺序、最终屏幕像素与时序等价。
