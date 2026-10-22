// Syntax gate for the editor's JavaScript.
//
// The headless view test cannot import app.js (it boots the app on import),
// so a syntax error there would only surface in the browser — where this
// environment's tab reloads and stalls make it easy to miss.
//
//   node tools/verify_syntax.mjs
//
// Every .js file under rom-editor/ is parsed with node --check.
import { readdirSync, statSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) out.push(...walk(path));
    else if (name.endsWith('.js') || name.endsWith('.mjs')) out.push(path);
  }
  return out;
}

const files = walk(root).sort();
let failures = 0;
for (const file of files) {
  const rel = relative(root, file).replace(/\\/g, '/');
  try {
    execFileSync(process.execPath, ['--check', file], { stdio: 'pipe' });
    console.log(`  [PASS] ${rel}`);
  } catch (err) {
    failures += 1;
    const out = `${err.stdout || ''}${err.stderr || ''}`.trim().split('\n').slice(0, 4).join(' ');
    console.log(`  [FAIL] ${rel} — ${out}`);
  }
}
console.log(`\n${failures === 0 ? '全部通过' : failures + ' 项失败'}（${files.length} 个文件）`);
process.exit(failures === 0 ? 0 : 1);
