// Getting the base ROM into the editor.
//
// Three sources, tried in order:
//   1. `content/base-rom/part-*.bin` — the ROM shipped next to the editor as
//      raw binary chunks.  Fetched and concatenated: an earlier design used
//      base64 + a <script> tag, which stalled in an embedded browser
//      (a multi-megabyte `atob` never finishes there).
//   2. `fetch('../rom/base.gba')` — the repository's copy, when a server is up.
//   3. The 载入 ROM button — the user picks the file by hand.
//
// The editor is fully usable without the ROM (all editing works off the
// content pack); the ROM is only needed to *build* and for the raw hex view.

import { readFile } from './ui.js';

export async function loadBundledRom(onProgress) {
  if (onProgress) onProgress('正在载入内置原版 ROM…');

  // Preferred path: a separate document fetches the ROM.  Some embedded
  // browsers allow only one large response body per document, and the editor
  // needs two large payloads (content pack + ROM).
  const viaFrame = await loadRomInFrame(onProgress);
  if (viaFrame) return viaFrame;

  if (onProgress) onProgress('内置 ROM 不可用，改为读取仓库副本…');
  for (const candidate of ['../rom/base.gba', 'content/base-rom/base-rom.bin']) {
    try {
      const response = await fetch(candidate, { cache: 'no-cache' });
      if (!response.ok) continue;
      const buffer = await response.arrayBuffer();
      if (buffer.byteLength < 0x100000) continue;
      return new Uint8Array(buffer);
    } catch (err) {
      /* try the next candidate */
    }
  }
  return null;
}

/**
 * Load the ROM in a hidden iframe and receive it via postMessage.
 *
 * The loader document fetches the ROM as its *first* request, which is the
 * case that reliably completes in every browser we tried; a document that
 * has already downloaded something is the case that stalls.
 */
async function loadRomInFrame(onProgress) {
  return loadRomSlice(0, 0);
}

/** One slice of the ROM, fetched by its own document. */
function loadRomSlice(from, count) {
  const ATTEMPTS = 3;
  return new Promise((resolve) => {
    let attempt = 0;
    let frame = null;
    let timer = null;
    let done = false;

    const cleanup = () => {
      window.removeEventListener('message', onMessage);
      if (timer) clearTimeout(timer);
      if (frame) frame.remove();
    };
    const finish = (value) => {
      if (done) return;
      done = true;
      cleanup();
      resolve(value);
    };
    const onMessage = (event) => {
      const data = event.data;
      if (!data || data.source !== 'rom-loader') return;
      if (data.state === 'ok') {
        finish(new Uint8Array(data.buffer));
      } else {
        console.log(`[editor] rom loader failed: ${data.payload}`);
        retry();
      }
    };
    const retry = () => {
      if (done) return;
      if (attempt >= ATTEMPTS) {
        finish(null);
        return;
      }
      attempt += 1;
      if (frame) frame.remove();
      frame = document.createElement('iframe');
      frame.style.display = 'none';
      frame.src = 'content/base-rom/rom-loader.html';
      frame.addEventListener('error', retry);
      frame.addEventListener('load', () => {
        // The slice range travels by postMessage: a query string does not
        // reliably reach an embedded document in every browser.
        try {
          frame.contentWindow.postMessage({ type: 'rom-slice', from, count }, '*');
        } catch (err) {
          retry();
        }
      });
      document.body.appendChild(frame);
      timer = setTimeout(retry, 45000);
    };

    window.addEventListener('message', onMessage);
    retry();
  });
}

/**
 * Fetch a file, transparently decompressing it when it is gzipped and the
 * browser supports DecompressionStream.
 */
export async function fetchMaybeGzip(url) {
  try {
    const response = await fetch(url, { cache: 'no-cache' });
    if (!response.ok) return null;
    if (typeof DecompressionStream !== 'function') return await response.arrayBuffer();
    const stream = response.body.pipeThrough(new DecompressionStream('gzip'));
    return await new Response(stream).arrayBuffer();
  } catch (err) {
    return null;
  }
}

export { readFile };
