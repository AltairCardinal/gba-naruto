# AI额外单位池：复制与成对字段写入预检归档

状态：上轮待归档的有限窗口已重放，与inventory-v2逐字节一致；promotion=0。
沿用固定producer/consumer窗口与生命周期调查模式，脚本完成有限事实，未外派。
永久收据位于`notes/evidence/rom-ai-extra-pool-lifecycle-preflight-20260930-v1/`。

在已有instruction owner中核对21个指令点。6ABCA/6ABCC将extra/main作为复制参数，
6ABCE/6ABD0构造468B长度，6ABD2调用9C3EC；468=1D4，算术范围覆盖相对CD偏移205。
复制callee窗口具有按16B组、4B、字节尾部复制的形态；29×16+4只是给定对齐/长度下的
形态算术，未关闭完整callee语义、ABI或异步影响。不得将其当成CD一定继承的已证明不变量。

6ABE8调用6A780。这个16B叶子窗口的唯一识别字段store为C0..C3，公式
`(word & FFFFFFF1) | r1`；当前局部调用r1=0。它不是CD store，不外推其他writer。
普通初始化6ACAC在6AD6E写main CD，并在mode6条件下于6AD90写关联extra CD；特殊
formation路径6E2A0之后在6E2CC写main CD，来源5411E4+lookup×AC+2，不能与普通路径混同。

固定1728条formation内容中，非零selector且初始C0&0E==6的12条都位于group30的
variant0/2、record03..08，selector为22/23/24，raw+0E均6。FA/FB/FC的24条初始mask
均0。这里只枚举固定ROM内容，不证明真实matrix索引域、当前RAM标志或自然选中这些记录。

ROM与固定coverage分别绑定1198ece7…59d05b / b568db6f…cf06d2；全部窗口和输入点由
receipt绑定。首轮NEG指令预期写错字节的失败脚本、空输出及说明保留，修正预期后两次
输出一致，本轮再重放仍一致，没有改ROM或旧owner。未新增生产功能代码，不宣称新BUG修复。
原始run已completed，恢复用永久收据与新run，不覆盖旧产物。

这些事实应并入主池slot13=extra0的同一个CD/CC/C0生命周期合同，不独立拼出“8行索引
安全”结论；copy/inherit/clear、全部writer、caller与异步边界仍开放。canonical仍87,631B。
