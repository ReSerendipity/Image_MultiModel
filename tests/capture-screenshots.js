/**
 * Image MultiModel - Full Website Screenshot Capture
 *
 * 由 Seedvr2 的 tests/capture-screenshots.js 复制改造：
 *   - BASE_URL 改为 http://127.0.0.1:8288（Image MultiModel 默认端口）
 *   - 主题持久化键改为 imm_theme（data-theme 属性一致）
 *   - 页面结构改为单页 SPA：主页 + 高级参数/预设/历史/图库/批量 抽屉视图
 *   - 健康检查端点改为 /api/health
 *
 * Prerequisites:
 *   - Image MultiModel server running (default http://127.0.0.1:8288), start with start.bat
 *   - Playwright chromium installed: npm install && npx playwright install chromium
 *
 * Usage:
 *   node capture-screenshots.js
 *
 * Optional env overrides:
 *   IMM_BASE_URL  e.g. http://127.0.0.1:8288
 *   IMM_OUT_DIR   e.g. ./screenshots
 *
 * Output: screenshots/<viewport>/<theme>/<NN>-<name>.png
 *
 * NOTE: 只点击纯 UI 状态切换（主题、抽屉、面板）。触发真实后端工作的按钮
 *       （生成、批量等）不点击。
 */
const { chromium } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const BASE_URL = process.env.IMM_BASE_URL || 'http://127.0.0.1:8288';
const OUTPUT_DIR = process.env.IMM_OUT_DIR
  ? path.resolve(process.env.IMM_OUT_DIR)
  : path.join(__dirname, '..', 'screenshots');

const VIEWPORTS = {
  desktop: { width: 1920, height: 1080 },
  tablet: { width: 768, height: 1024, isMobile: true, hasTouch: true },
  mobile: { width: 375, height: 812, isMobile: true, hasTouch: true },
};

const THEMES = ['dark', 'light'];

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

async function screenshotPage(page, name, options = {}) {
  const {
    fullPage = true,
    waitFor = null,
    viewportName = 'desktop',
    theme = 'dark',
  } = options;

  const dir = path.join(OUTPUT_DIR, viewportName, theme);
  ensureDir(dir);

  const filePath = path.join(dir, `${name}.png`);

  if (waitFor) {
    await page.waitForTimeout(waitFor);
  }

  await page.screenshot({ path: filePath, fullPage });
  console.log(`  Captured: ${filePath}`);
}

async function setTheme(page, theme) {
  // 主题持久化键 'imm_theme' 是 index.html B1 防闪烁脚本使用的真实键。
  // 导航前设置 localStorage + data-theme 属性即可正确渲染。
  await page.evaluate((t) => {
    localStorage.setItem('imm_theme', t);
    document.documentElement.setAttribute('data-theme', t);
  }, theme);
  await page.waitForTimeout(300);
}

async function safe(label, viewportName, theme, fn) {
  try {
    await fn();
  } catch (e) {
    console.error(`  [SKIP] ${label} (${viewportName}, ${theme}): ${e.message}`);
  }
}

// 通过 JS click 打开抽屉（避免其他元素遮挡真实指针事件）
async function clickById(page, id) {
  return page.evaluate((elId) => {
    const el = document.getElementById(elId);
    if (!el) throw new Error(`element #${elId} not found`);
    el.click();
  }, id);
}

async function closeDrawers(page) {
  await page.evaluate(() => {
    ['drawer', 'histDrawer', 'galleryDrawer', 'batchDrawer'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.classList.remove('open');
    });
    const scrim = document.getElementById('scrim');
    if (scrim) scrim.classList.remove('show');
  });
  await page.waitForTimeout(200);
}

async function captureHomePage(page, viewportName, theme) {
  console.log(`Capturing Home Page (${viewportName}, ${theme})...`);
  await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(3000);

  await screenshotPage(page, '01-home-full', { viewportName, theme });
}

async function captureAdvancedDrawer(page, viewportName, theme) {
  console.log(`Capturing Advanced Params Drawer (${viewportName}, ${theme})...`);
  await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(2000);

  await safe('advanced-drawer', viewportName, theme, async () => {
    await clickById(page, 'drawerToggle');
    await page.waitForSelector('#drawer.open', { timeout: 5000 });
    await page.waitForTimeout(600);
    await screenshotPage(page, '02-advanced-params-drawer', { viewportName, theme, fullPage: false });
    await closeDrawers(page);
  });
}

async function capturePresetsDrawer(page, viewportName, theme) {
  console.log(`Capturing Presets Drawer (${viewportName}, ${theme})...`);
  await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(2000);

  await safe('presets-drawer', viewportName, theme, async () => {
    await clickById(page, 'openPresets');
    await page.waitForSelector('#drawer.open', { timeout: 5000 });
    await page.waitForTimeout(600);
    await screenshotPage(page, '03-presets-drawer', { viewportName, theme, fullPage: false });
    await closeDrawers(page);
  });
}

async function captureHistoryDrawer(page, viewportName, theme) {
  console.log(`Capturing History Drawer (${viewportName}, ${theme})...`);
  await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(2000);

  await safe('history-drawer', viewportName, theme, async () => {
    await clickById(page, 'openHistory');
    await page.waitForTimeout(600);
    await screenshotPage(page, '04-history-drawer', { viewportName, theme, fullPage: false });
    await closeDrawers(page);
  });
}

async function captureGalleryDrawer(page, viewportName, theme) {
  console.log(`Capturing Gallery Drawer (${viewportName}, ${theme})...`);
  await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(2000);

  await safe('gallery-drawer', viewportName, theme, async () => {
    await clickById(page, 'openGallery');
    await page.waitForTimeout(600);
    await screenshotPage(page, '05-gallery-drawer', { viewportName, theme, fullPage: false });
    await closeDrawers(page);
  });
}

async function captureBatchDrawer(page, viewportName, theme) {
  console.log(`Capturing Batch Drawer (${viewportName}, ${theme})...`);
  await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(2000);

  await safe('batch-drawer', viewportName, theme, async () => {
    await clickById(page, 'openBatch');
    await page.waitForTimeout(600);
    await screenshotPage(page, '06-batch-drawer', { viewportName, theme, fullPage: false });
    await closeDrawers(page);
  });
}

async function captureAllViewports(page, viewports, themes) {
  for (const [vpName, vpSize] of Object.entries(viewports)) {
    console.log(`\n=== Viewport: ${vpName} (${vpSize.width}x${vpSize.height}) ===`);
    await page.setViewportSize({ width: vpSize.width, height: vpSize.height });

    for (const theme of themes) {
      console.log(`\n--- Theme: ${theme} ---`);
      await setTheme(page, theme);

      await captureHomePage(page, vpName, theme);
      await captureAdvancedDrawer(page, vpName, theme);
      await capturePresetsDrawer(page, vpName, theme);
      await captureHistoryDrawer(page, vpName, theme);
      await captureGalleryDrawer(page, vpName, theme);
      await captureBatchDrawer(page, vpName, theme);
    }
  }
}

(async () => {
  console.log('Image MultiModel - Full Website Screenshot Capture');
  console.log('==================================================');
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Output Dir: ${OUTPUT_DIR}`);
  console.log('');

  ensureDir(OUTPUT_DIR);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log('Checking if server is running...');
    try {
      await page.goto(`${BASE_URL}/api/health`, { timeout: 10000 });
      console.log('Server is running!');
    } catch (e) {
      console.error('ERROR: Server is not running at', BASE_URL);
      console.error('Please start the server first with: start.bat');
      process.exit(1);
    }

    await captureAllViewports(page, VIEWPORTS, THEMES);

    console.log('\n=========================================');
    console.log('Screenshot capture complete!');
    console.log(`All screenshots saved to: ${OUTPUT_DIR}`);

  } catch (error) {
    console.error('Error:', error);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
