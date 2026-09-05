# 历史 verifier 在干净检出中缺失合同输入

B=`80faaebd2d441e94afbe7f0c7921609659f4d0fe` 已经通过实际 artifact hook 并提交835个
相关文件；干净B导入coverage auditor时失败，CgbSound verifier在import阶段读取了
被忽略的 `build/experiments/active/cgbsound-contract/codex-r1-20260829/CONTRACT.json`。
因此B的提交成功不等于干净运行闭包完整，不能省略这次失败。

按固定历史身份恢复模式，保留三份原始合同到 `tools/data/rom-verifier-contracts-v1/`：
CgbSound 11,410B、CGB helper 8,694B、MP2K dispatcher 7,761B，合计27,865B。
固定SHA、原始路径和consumer源码SHA由 `tools/prepare_rom_verifier_contracts.py` 绑定。
旧consumer会再次独立核对原CONTRACT_SHA256；未修改旧verifier、manifest或A授权包。
使用方法及失败处理见 `docs/rom-verifier-checkout-setup.md`。

Sol medium只读检查proof的107个工具路径、递归静态导入的206模块、coverage的145个
tool-path字段及全部67个含build字面量工具，确认当前冻结命令集的真实运行输入只有
上述三份。历史candidate/output字符串不当作输入，未来动态CLI参数不在此结论内。
该结果已用本地源代码的实际读取函数及原始SHA逐项核对。

TDD先记录缺失恢复入口的RED；第一轮测试因macOS `/var` 符号链接被拒绝，改为使用
测试临时目录的真实路径后通过。FIFO目标阻塞由5秒timeout红测暴露，以非阻塞打开并
核对regular file修复。Luna max只读review发现临时名碰撞时错误清理未拥有文件；确定性
RED复现后，清理所有权改为仅在O_EXCL创建成功后取得。另以祖先目录在预检后替换为
symlink的RED固定读取竞态，改用逐级dirfd/O_NOFOLLOW。最终11项测试通过，包含三个
原始consumer的真实合同读取集成；两份新增Python源码可编译。

原始B失败、TDD红绿和逐文件manifest保存在
`notes/evidence/rom-verifier-runtime-inputs-20260905/`。当前状态为初始化修复已验证，
尚待提交后的干净检出重放。当前87,749 unknown，新增语义字节0；106/96 formal旧成功
收据仍绑定相同ROM、canonical、proof和verifier字节，本修复不冒充新的全量formal执行。
