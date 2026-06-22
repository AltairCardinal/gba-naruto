# mGBA WebAssembly threaded 倍速修复 (2026-06-22)

## 问题
- `https://sh.kibox.com.cn/gba-naruto/play/` 的 mGBA 是 nonthreaded 构建
- `setFastForwardMultiplier(n)` 在 nonthreaded C 端**不真生效**（只换按钮高亮），因为没 thread 同步机制
- 切到 threaded 构建后，调用 emscripten_set_main_loop 的 callback 抛 `wasm-function[1938] signature mismatch`

## 解决
1. **替换 wasm**：`cp mgba/_threaded-attempt/mgba.{js,wasm} play/mgba/`
   - threaded wasm hash: `348c8a493bd36a3b886ebfbbdc5db9f9b39a2e8101ca5558111abdb720bb5e4e`
   - nonthreaded wasm hash: `a57ed56869d7dbb2a30d88a4454b7601da9e60f64850dc4681beef6eb1d10fad`
2. **改 main.js 手动 RAF 驱动 _runLoopJs**：
   ```js
   const Module = await mGBAFactory({...});
   Module.pauseMainLoop();  // 立即禁掉坏签名的 emscripten main loop
   // ...
   function tick() {
     for (let i = 0; i < runLoopCallsPerFrame; i++) {
       Module._runLoopJs();  // 手动驱动取代 emscripten main loop
     }
     requestAnimationFrame(tick);
   }
   ```
3. **双轨倍速**：调 `gba.setFastForwardMultiplier(n)`（C 端 thread fpsTarget）+ RAF 每帧 N 次（兜底）

## 验证
puppeteer 跑 `https://sh.kibox.com.cn/gba-naruto/play/`：
- 0 错误（之前 signature mismatch）
- `getFastForwardMultiplier()` 在 1x/2x/3x/4x 返回 1/2/3/4
- 视觉证据（连续 10s 截图）：
  - 1x → Naruto 标题介绍
  - 2x → 佐助火遁·豪火球术（推进 2 个过场）
  - 4x → 回到 PUSH START 标题（10s 走完整个过场）

## 关键文件
- `play/mgba/mgba.{js,wasm}` — 替换为 threaded 版
- `play/main.js` — 改用 manual RAF driver
- `play/index.html` — cache-buster 改 `?v=threaded-v2-fix`

## 回滚保险（**没动**）
- `play.bak-threaded-20260618144910/`（紧急回滚）
- `play/.mgba-backup*/`
- `play/mgba/mgba.{js,wasm}.pre-threaded-v2-fix.bak`（本次操作的备份）

## 关键教训
- **signature mismatch 修法 = pause emscripten main loop + 手动 RAF 调 _runLoopJs**
- 永远别用 cwrap 包装的 `setFastForwardMultiplier` 做端到端验证（同样会被 signature 问题挡住），用 raw `_setFastForwardMultiplier` 或 `?debug=1` query 后从 `window.__mGBA.getFastForwardMultiplier()` 读
- puppeteer 视觉对比截图是金标准（不要只信帧率或 callback 计数）
- 详细记录见 `~/.openclaw/workspace-eta/memory/2026-06-22-threaded-mgba-fix.md`
