// T7 v7: 完整 e2e
// 阶段 1: 循环 START 直到主菜单（最多 30 次 * 3s = 90s）
// 阶段 2: 按 A 一次进新游戏
// 阶段 3: 循环 A 直到 dialogue 出现（最多 40 次 * 3s = 120s）
const puppeteer = require('/tmp/gba-puppeteer/node_modules/puppeteer-core');
const fs = require('fs');

const URL = 'https://sh.kibox.com.cn/gba-naruto/play/';
const OUTDIR = '/tmp/t7-redo';
fs.mkdirSync(OUTDIR, { recursive: true });

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/chromium',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--enable-features=SharedArrayBuffer'],
    defaultViewport: { width: 960, height: 720 }
  });
  const page = await browser.newPage();
  page.on('pageerror', err => console.error(`[browser ERROR] ${err.message}`));

  console.log('=== 1. 打开 + 启动 + 4x ===');
  await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await new Promise(r => setTimeout(r, 2000));
  await page.click('#playBtn');
  await page.waitForFunction(
    () => document.querySelector('.speed-btn[data-speed="1"]')?.disabled === false,
    { timeout: 90000, polling: 2000 }
  );
  await page.evaluate(() => document.querySelector('.speed-btn[data-speed="4"]')?.click());

  // 阶段 1: 循环 START（最多 30 次 / 90s）
  console.log('=== 2. 阶段1: 循环 START（最多 30 次）===');
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 3000));
    await page.keyboard.press('Enter');
    if (i === 29) {
      await page.screenshot({ path: `${OUTDIR}/v7-stage1.png` });
      console.log(`  [${i + 1}/30] stage1 done`);
    } else if (i % 5 === 0) {
      console.log(`  [${i + 1}/30]`);
    }
  }

  // 阶段 2: 按 A 一次（确认"开始新游戏"）
  console.log('=== 3. 阶段2: 按 A 一次（开始新游戏）===');
  await new Promise(r => setTimeout(r, 1500));
  await page.keyboard.press('KeyZ');
  await new Promise(r => setTimeout(r, 1000));
  await page.screenshot({ path: `${OUTDIR}/v7-after-A.png` });

  // 阶段 3: 循环 A 直到 dialogue（最多 40 次 / 120s）
  console.log('=== 4. 阶段3: 循环 A 直到 dialogue（最多 40 次）===');
  for (let i = 0; i < 40; i++) {
    await new Promise(r => setTimeout(r, 3000));
    await page.keyboard.press('KeyZ');
    if (i === 39 || i % 5 === 0) {
      await page.screenshot({ path: `${OUTDIR}/v7-stage3-${String(i).padStart(2, '0')}.png` });
      console.log(`  [${i + 1}/40] saved v7-stage3-${String(i).padStart(2, '0')}.png`);
    }
  }

  await page.screenshot({ path: `${OUTDIR}/v7-final.png` });
  await browser.close();
  console.log(`=== 完成 ===`);
})().catch(err => {
  console.error('FATAL:', err);
  process.exit(1);
});