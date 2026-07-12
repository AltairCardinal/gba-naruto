#!/usr/bin/env node
'use strict';

const puppeteer = require('/private/tmp/gba-puppeteer/node_modules/puppeteer-core');

async function main() {
  const browser = await puppeteer.launch({
    executablePath: process.env.PROBE_BROWSER || '/usr/bin/chromium',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--enable-features=SharedArrayBuffer'],
  });
  try {
    const page = await browser.newPage();
    await page.goto(process.env.PROBE_URL || 'https://sh.kibox.com.cn/gba-naruto/play/', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.click('#playBtn');
    await page.waitForFunction(() => typeof window.__mGBA?._readGbaByte === 'function', { timeout: 90000 });
    const report = await page.evaluate(() => {
      const gba = window.__mGBA;
      const keys = [];
      let object = gba;
      while (object && object !== Object.prototype) {
        keys.push(...Object.getOwnPropertyNames(object));
        object = Object.getPrototypeOf(object);
      }
      const unique = [...new Set(keys)].sort();
      return {
        matchingKeys: unique.filter(key => /save|sram|battery|export|data/i.test(key)),
        allCallableUnderscoreKeys: unique.filter(key => key.startsWith('_') && typeof gba[key] === 'function'),
        callableSources: Object.fromEntries(
          ['getSave', 'listSaves', 'uploadSaveOrSaveState'].filter(key => typeof gba[key] === 'function')
            .map(key => [key, String(gba[key]).slice(0, 1000)]),
        ),
      };
    });
    console.log(JSON.stringify(report, null, 2));
  } finally {
    await browser.close();
  }
}

if (require.main === module) main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
