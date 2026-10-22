// Minimal static file server for the editor.
//
// The editor needs the content pack and the base ROM over HTTP (a file://
// URL cannot fetch them).  Serve the repository root so that both
// `rom-editor/content/pack.json` and `rom/base.gba` are reachable.
//
//   node rom-editor/tools/serve.mjs [port]
//   → http://localhost:8000/rom-editor/
//
// It also accepts `POST /__report`: the in-browser self-test posts its
// results there, so a run survives a browser tab that keeps reloading.
import { createServer } from 'node:http';
import { readFileSync, statSync, mkdirSync, appendFileSync } from 'node:fs';
import { extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, '..', '..');
const port = Number(process.argv[2] || 8000);
const REPORT_PATH = join(repoRoot, 'build', 'selftest-report.jsonl');

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.gz': 'application/gzip',
  '.bin': 'application/octet-stream',
  '.gba': 'application/octet-stream',
  '.png': 'image/png',
  '.md': 'text/markdown; charset=utf-8',
};

createServer((req, res) => {
  let path = decodeURIComponent(req.url.split('?')[0]);
  if (path === '/') path = '/rom-editor/';

  // --- 自检结果上报 ----------------------------------------------------
  if (path === '/__report') {
    if (req.method === 'GET') {
      let body = '';
      try { body = readFileSync(REPORT_PATH, 'utf8'); } catch { body = ''; }
      res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
      res.end(body);
      return;
    }
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => {
      const text = Buffer.concat(chunks).toString('utf8');
      try {
        mkdirSync(dirname(REPORT_PATH), { recursive: true });
        appendFileSync(REPORT_PATH, text.replace(/\n/g, ' ') + '\n', 'utf8');
      } catch (err) {
        console.log(`上报落盘失败：${err.message}`);
      }
      let summary = text;
      try {
        const parsed = JSON.parse(text);
        summary = `failures=${parsed.failures} lines=${(parsed.lines || []).length}`;
      } catch { /* keep the raw text */ }
      console.log(`SELFTEST 报告： ${summary}`);
      res.writeHead(204, { 'access-control-allow-origin': '*' });
      res.end();
    });
    return;
  }

  const target = normalize(join(repoRoot, path));
  if (!target.startsWith(repoRoot)) {
    res.writeHead(403).end('forbidden');
    return;
  }
  console.log(`${new Date().toISOString().slice(11, 23)} ${req.method} ${path}`);
  let stat;
  try {
    stat = statSync(target);
  } catch {
    res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' })
      .end('404 ' + path);
    return;
  }
  if (stat.isDirectory()) {
    const index = join(target, 'index.html');
    try {
      const body = readFileSync(index);
      res.writeHead(200, {
        'content-type': TYPES['.html'],
        'content-length': body.length,
        'cache-control': 'no-store',
      });
      res.end(body);
    } catch {
      res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' })
        .end('404 ' + path);
    }
    return;
  }
  // Read the whole file and send it in one shot: streaming a 6 MB ROM in
  // 64 KB chunks is several times slower on Windows.
  let body;
  try {
    body = readFileSync(target);
  } catch {
    res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' })
      .end('404 ' + path);
    return;
  }
  res.writeHead(200, {
    'content-type': TYPES[extname(target)] || 'application/octet-stream',
    'content-length': body.length,
    'cache-control': 'no-store',
  });
  // Let Node finish the response on its own.  Closing the socket by hand can
  // truncate a large body, and the browser then waits forever for bytes that
  // will never arrive.
  res.end(body);
}).listen(port, () => {
  console.log(`编辑器已启动： http://localhost:${port}/rom-editor/`);
  console.log(`（服务根目录： ${repoRoot}）`);
});
