// Loading the content pack — with progress, timeouts and fallbacks.
//
// The pack is the editor's initial data.  It is served gzipped (242 KB on the
// wire, 2.9 MB decompressed), so a page load has three visible phases:
// download → decompress → parse.  Every source has a timeout, because a
// browser that stalls on a response would otherwise leave the UI frozen on
// "正在载入内容包…" forever with no way out.

const SOURCES = [
  { url: 'content/pack.min.json.gz', gzipped: true, label: '内容包（压缩）' },
  { url: 'content/pack.json', gzipped: false, label: '内容包（明文）' },
];

/**
 * The editor's root, derived from this module's own URL.
 *
 * Paths are resolved against the root, not against the page that happens to
 * use the loader — otherwise the self-test page (which lives in tools/) would
 * look for content/ under tools/ and get a 404.
 */
export const ROOT = new URL('../', import.meta.url).href;

export function editorUrl(path) {
  return new URL(path, ROOT).href;
}

/**
 * fetch + read the body, with a timeout that covers **both**.
 *
 * Two things had to be right for a stalled response to actually time out:
 *
 * 1. the timeout is a *race* against a rejecting timer, not only an abort —
 *    some browsers never reject a stalled response body when the abort
 *    signal fires, so an abort-only timeout would never fire;
 * 2. the body read happens **inside** the raced promise — a timeout that only
 *    covers the response headers leaves a stalled *body* hanging forever,
 *    which is exactly how the UI got stuck on "正在载入内容包…".
 */
export function fetchWithTimeout(url, timeoutMs = 20000, readBody) {
  const controller = new AbortController();
  let timer = null;
  const guard = new Promise((_, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(new Error(`${url} 超过 ${Math.round(timeoutMs / 1000)} 秒没有响应`));
    }, timeoutMs);
  });
  const request = fetch(url, { cache: 'no-cache', signal: controller.signal })
    .then(async (response) => {
      if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
      const body = readBody ? await readBody(response) : await response.arrayBuffer();
      return { response, body, release: () => clearTimeout(timer) };
    })
    .catch((err) => {
      clearTimeout(timer);
      if (err && err.name === 'AbortError') {
        throw new Error(`${url} 超过 ${Math.round(timeoutMs / 1000)} 秒没有响应`);
      }
      throw err;
    });
  return Promise.race([request, guard]);
}

/** Read a response body while reporting progress. Returns an ArrayBuffer. */
async function readWithProgress(response, onChunk) {
  if (!onChunk || !response.body) {
    return await response.arrayBuffer();
  }
  const reader = response.body.getReader();
  const chunks = [];
  let received = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    received += value.length;
    onChunk(received, response.headers.get('content-length'));
  }
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const merged = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { merged.set(chunk, offset); offset += chunk.length; }
  return merged.buffer;
}

async function gunzip(buffer) {
  if (typeof DecompressionStream !== 'function') {
    throw new Error('这个浏览器不支持 DecompressionStream');
  }
  const stream = new Response(buffer).body.pipeThrough(new DecompressionStream('gzip'));
  return new Response(stream).arrayBuffer();
}

function formatBytes(n) {
  if (!Number.isFinite(n)) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/**
 * Load and parse the content pack.
 *
 * @param {(phase: object) => void} onProgress
 *        phase = { stage, label, detail, percent, bytes, total }
 * @returns {Promise<object>} the parsed pack
 */
export async function loadPackWithProgress(onProgress) {
  const errors = [];
  for (const source of SOURCES) {
    try {
      onProgress({
        stage: 'download', label: `正在下载${source.label}…`, percent: 0,
      });
      const { response, body, release } = await fetchWithTimeout(
        editorUrl(source.url), 20000,
        (res) => readWithProgress(res, (received, length) => {
          const known = Number(length) || 0;
          onProgress({
            stage: 'download',
            label: `正在下载${source.label}…`,
            detail: `${formatBytes(received)}${known ? ' / ' + formatBytes(known) : ''}`,
            bytes: received,
            total: known,
            percent: known ? Math.round((received / known) * 100) : undefined,
          });
        }));
      try {
        if (source.gzipped) {
          onProgress({ stage: 'decompress', label: '正在解压内容包…', percent: undefined });
          const plain = await gunzip(body);
          onProgress({ stage: 'parse', label: '正在解析内容包…', percent: undefined });
          return JSON.parse(new TextDecoder().decode(plain));
        }
        onProgress({ stage: 'parse', label: '正在解析内容包…', percent: undefined });
        return JSON.parse(new TextDecoder().decode(body));
      } finally {
        release();
      }
    } catch (err) {
      const reason = err && err.name === 'AbortError' ? '超时' : (err.message || String(err));
      errors.push(`${source.label}：${reason}`);
      onProgress({
        stage: 'retry', label: `${source.label}载入失败（${reason}），换下一个来源…`,
        percent: undefined,
      });
    }
  }
  const error = new Error(
    `内容包载入失败 —— ${errors.join('；')}\n` +
    '请确认是用 node rom-editor\\tools\\serve.mjs 起的服务器，' +
    '并且从 http://localhost:<端口>/rom-editor/ 打开（直接双击 index.html 会被浏览器的同源策略拦住）。');
  error.sources = errors;
  throw error;
}

/** Load the content pack through the dedicated loader document. */
export function loadPackInFrame(timeoutMs = 30000) {
  return new Promise((resolve) => {
    const frame = document.createElement('iframe');
    frame.style.display = 'none';
    frame.src = editorUrl('content/pack-loader.html');
    const done = (value) => {
      window.removeEventListener('message', onMessage);
      clearTimeout(timer);
      frame.remove();
      resolve(value);
    };
    const onMessage = (event) => {
      const data = event.data;
      if (!data || data.source !== 'pack-loader') return;
      done(data.state === 'ok' ? data.payload : null);
    };
    window.addEventListener('message', onMessage);
    frame.addEventListener('error', () => done(null));
    document.body.appendChild(frame);
    const timer = setTimeout(() => done(null), timeoutMs);
  });
}

/**
 * Fetch a JSON file, transparently using the gzipped copy when it exists.
 *
 * `url` should already be resolved against the editor root (see `editorUrl`),
 * because the self-test page lives in tools/ and a page-relative path would
 * look for content/ under tools/.
 */
export async function fetchJsonSmart(url, timeoutMs = 20000) {
  const gz = url + '.gz';
  if (typeof DecompressionStream === 'function') {
    try {
      // The body read has to happen *inside* the timeout, otherwise a stalled
      // body would hang forever.
      const { body, release } = await fetchWithTimeout(gz, timeoutMs, async (res) => {
        if (res.headers.get('content-encoding') === 'gzip') {
          return await res.text();
        }
        const stream = res.body.pipeThrough(new DecompressionStream('gzip'));
        return await new Response(stream).text();
      });
      try {
        return JSON.parse(body);
      } finally {
        release();
      }
    } catch (err) {
      /* fall through to the plain file */
    }
  }
  const { body, release } = await fetchWithTimeout(url, timeoutMs);
  try {
    return JSON.parse(body);
  } finally {
    release();
  }
}
