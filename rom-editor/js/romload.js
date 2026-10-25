// 载入 ROM 的**唯一流程**。
//
// 为什么不写在 app.js 里：那两个 bug 都是「同一个动作被写了两遍、其中一遍漏了半截」
// 造成的，所以流程本身必须**只有一条**，而来源（内置 ROM / 本地文件）只负责
// 「怎么把字节取回来」。
//
// 两个 bug（都是用户报出来的，2026-10-24）：
//
//   1. **门禁里选「载入内置 ROM」之后，编辑器里没有 ROM。**
//      以前两条路各写一遍：本地文件那条调了 `apply()`（写状态），
//      内置那条只取字节、忘了写状态 ⇒ 门禁关掉了，`state.rom` 还是 null。
//      用户看到的现象：弹窗里选了内置 ROM，关掉弹窗后载入状态条仍然是
//      「木叶战记熊组汉化版原版 / 在本地浏览上传」，也就是**没载入**。
//
//   2. **载入完成之后，顶栏还在转「加载中」的滚动条。**
//      载入条那条路显示了顶栏的进度条，却从来没人把它撤掉 ——
//      「显示」与「撤掉」分写在两处，漏一处就永远转下去。
//
// 现在：取字节 → 写状态 → 管进度条，三步在**同一条流程**里；
// 显示与撤掉也成对出现，漏不掉。

/** 来源的人话 —— 用来写进度与错误信息。 */
const SOURCE_LABEL = {
  bundled: '内置 ROM',
  file: '本地 ROM',
};

/**
 * 造一个 ROM 载入器。
 *
 * @param {object} deps
 * @param {(onProgress: (msg: string) => void) => Promise<Uint8Array>} deps.fetchBundled
 *        取内置 ROM 的字节。取不到要**抛异常**（门禁会把错误显示在窗口里）。
 * @param {(file: File) => Promise<Uint8Array>} deps.readLocalFile
 *        读本地 ROM 文件的字节。
 * @param {(bytes: Uint8Array, source: string, name: string) => Promise<void>} deps.apply
 *        把 ROM 写进编辑器状态：设 `state.rom` / 算 sha256 / 解析内容包 / 重绘。
 *        **这一步不能少** —— 少一步就等于「ROM 没载入」。
 * @param {{show: (phase: object) => void, hide: () => void,
 *          showError: (text: string) => void}} [deps.indicator]
 *        顶栏的载入指示器。只有 `bar: true` 的那条路用它 ——
 *        门禁那条路自己在窗口里显示状态，不需要顶栏。
 */
export function createRomLoader(deps) {
  const { fetchBundled, readLocalFile, apply, indicator } = deps;

  /**
   * 载入一条路：取字节 → 写状态 → 管进度条。
   *
   * @param {object} spec
   * @param {'bundled'|'file'} spec.source
   * @param {string} spec.name          显示用的名字（载入状态条上写的那一个）
   * @param {boolean} spec.bar          顶栏要不要显示进度条
   * @param {(notify: (msg: string) => void) => Promise<Uint8Array>} spec.fetchBytes
   */
  async function run(spec) {
    const { source, name, bar, fetchBytes } = spec;
    const show = (label) => {
      if (bar && indicator) indicator.show({ stage: 'download', label, percent: undefined });
    };
    if (bar) show(`正在载入${SOURCE_LABEL[source]}…`);
    try {
      const bytes = await fetchBytes(show);
      if (!bytes || !bytes.length) throw new Error('没有读到任何字节');
      // 写状态 —— 这一步**不能少**：少一步就等于「ROM 没载入」。
      await apply(bytes, source, name);
      // 载入完了 ⇒ 顶栏的进度条必须撤掉（否则它会一直转下去）。
      if (bar && indicator) indicator.hide();
      return bytes;
    } catch (err) {
      // 失败时进度条**留在屏幕上**并变成红色 —— 作者得看得见「没载入成功」。
      if (bar && indicator) {
        indicator.showError(`${SOURCE_LABEL[source]}载入失败：${(err && err.message) || err}`);
      }
      throw err;
    }
  }

  return {
    /**
     * 内置 ROM。
     *
     * @param {(msg: string) => void} [onProgress] 下载进度（门禁用它显示状态）
     * @param {{bar?: boolean}} [options] `bar: true` ⇒ 顶栏显示进度条
     */
    loadBundled(onProgress, options = {}) {
      return run({
        source: 'bundled',
        name: 'base.gba',
        bar: !!options.bar,
        fetchBytes: async (notify) => {
          const bytes = await fetchBundled((msg) => {
            notify(msg);
            if (onProgress) onProgress(msg);
          });
          return bytes;
        },
      });
    },

    /**
     * 本地 ROM 文件。
     *
     * @param {File} file
     * @param {{bar?: boolean}} [options] `bar: true` ⇒ 顶栏显示进度条
     */
    loadFile(file, options = {}) {
      return run({
        source: 'file',
        name: (file && file.name) || 'base.gba',
        bar: !!options.bar,
        fetchBytes: () => readLocalFile(file),
      });
    },
  };
}
