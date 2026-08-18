// Image MultiModel 前端冒烟测试（jsdom）
// 运行：node tests/frontend/smoke.js（依赖 jsdom）
// 前置：python scripts/render_pages.py（渲染 Jinja2 模板到 _rendered/）
// 模拟后端数据，不依赖真实服务；断言失败 exit 1。
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..', '..');
const RENDERED = path.join(__dirname, '_rendered');
const HTML_FILE = path.join(RENDERED, 'index.html');
const APP_JS = path.join(ROOT, 'app', 'integrated_app', 'static', 'js', 'app.js');

/* ============ 模拟后端 ============ */
const MOCK = {
  '/api/health': {
    status: 'ok', version: '9.9.9',
    queue: { pending: 0, processing: 0 },
    gpu: { total_vram_gb: 24, free_vram_gb: 20, used_vram_gb: 4 },
    memory: { total_gb: 64, used_gb: 30, percent: 47 },
    disk: { total_gb: 1000, used_gb: 500 },
    engines: [{ name: 'z_image_turbo_native', display_name: 'Z-Image Turbo', state: 'loaded' }]
  },
  '/api/config': {
    version: '9.9.9',
    inference: { default_steps: 8, default_cfg: 1.0, default_seed: -1, default_batch_size: 1 },
    models: {
      default_engine: 'z_image_turbo_native',
      engines: { z_image_turbo_native: { display_name: 'Z-Image Turbo', default_width: 1024, default_height: 1024 } }
    }
  },
  '/api/config/loras': { loras: [{ name: 'a.safetensors' }, { name: 'b.safetensors' }] },
  '/api/outputs': {
    outputs: [{ path: 'fake_00001_.png', engine: 'z_image_turbo_native', prompt: 'a cat', output_type: 'original', width: 1024, height: 1024, created_at: '2026-08-17T12:00:00' }],
    total: 1
  },
  '/api/tasks': { tasks: [], total: 0 },
  '/api/presets': { presets: [] }
};

function mockFetch(u, o) {
  u = String(u);
  const method = (o && o.method) || 'GET';
  const pathname = u.split('?')[0];
  const j = (x) => Promise.resolve({
    json: () => Promise.resolve(x), ok: true, status: 200,
    headers: { get: () => null }
  });
  if (MOCK[pathname]) {
    if (pathname === '/api/presets' && method === 'POST') return j({ id: 'p1', name: 'x' });
    return j(MOCK[pathname]);
  }
  if (method === 'POST' && pathname === '/api/generate') return j({ task_id: 't1', status: 'pending' });
  if (method === 'PUT' || method === 'DELETE') return j({});
  return Promise.reject(new Error('unmocked ' + u));
}

/* ============ EventSource polyfill（jsdom 无原生实现） ============ */
function FakeEventSource(url) {
  this.url = url;
  this._handlers = {};
  FakeEventSource.instances.push(this);
}
FakeEventSource.instances = [];
FakeEventSource.prototype.addEventListener = function (t, cb) {
  (this._handlers[t] = this._handlers[t] || []).push(cb);
};
FakeEventSource.prototype.close = function () {};
FakeEventSource.prototype.dispatch = function (t, data) {
  (this._handlers[t] || []).forEach(function (cb) { cb({ data: JSON.stringify(data) }); });
};

/* ============ 启动 ============ */
function boot(opts) {
  opts = opts || {};
  const errors = [];
  const dom = new JSDOM(fs.readFileSync(HTML_FILE, 'utf-8'), {
    runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/',
    beforeParse(w) {
      w.fetch = mockFetch;
      w.EventSource = FakeEventSource;
      w.alert = (m) => { if (opts.logAlerts) console.log('  [alert]', m); };
      w.confirm = () => true;
      w.addEventListener('error', (e) => errors.push(String((e.error && e.error.message) || e.message)));
      if (opts.theme) w.localStorage.setItem('imm_theme', opts.theme);
      if (opts.lang) w.localStorage.setItem('imm_lang', opts.lang);
    }
  });
  // jsdom 默认不拉取外部脚本：手动注入 app.js 执行
  const s = dom.window.document.createElement('script');
  s.textContent = fs.readFileSync(APP_JS, 'utf-8');
  dom.window.document.body.appendChild(s);
  return { dom, errors };
}

let pass = 0, fail = 0;
function assert(c, m) { if (c) { pass++; console.log('  ok - ' + m); } else { fail++; console.log('  FAIL - ' + m); } }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const click = (d, sel) => d.querySelector(sel).dispatchEvent(new d.defaultView.MouseEvent('click', { bubbles: true, cancelable: true }));

(async () => {
  /* ============ 骨架 + 后端数据加载 ============ */
  console.log('[boot + data load]');
  {
    const { dom, errors } = boot({});
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'init no errors: ' + errors.join(' | '));
    assert(d.getElementById('sbConnText').textContent === 'CONN: OK', 'health → CONN: OK');
    assert(d.getElementById('aboutVersion').textContent === '9.9.9', 'health → about version 9.9.9');
    const engItems = [...d.querySelectorAll('#engMenu .ip-item')];
    assert(engItems.length === 1 && engItems[0].textContent === 'Z-Image Turbo', 'engine menu from /api/config');
    assert(d.getElementById('snapRes').textContent === '1024 × 1024', 'snap chips: 1024 × 1024');
    assert(d.getElementById('snapSteps').textContent === '8', 'snap chips: steps 8');
    const cards = [...d.querySelectorAll('#outGrid .r-card')];
    assert(cards.length === 1 && cards[0].textContent.includes('a cat'), 'recent outputs render 1 card');
    assert(d.getElementById('statLoras').textContent.includes('2 个文件'), 'LoRA scan: 2 files');
  }

  /* ============ Prompt 输入交互 ============ */
  console.log('[prompt input]');
  {
    const { dom, errors } = boot({});
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'init no errors');
    const ta = d.getElementById('posPrompt');
    ta.value = '一只猫在窗边';
    ta.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    assert(d.getElementById('posMeta').textContent.startsWith('6 字符'), 'char/token meta updates');
    click(d, '#clearPos');
    assert(ta.value === '', 'clear button empties prompt');
    click(d, '#negToggle');
    assert(d.getElementById('negBox').classList.contains('open'), 'negative prompt box opens');
  }

  /* ============ 主题 + 语言切换持久化 ============ */
  console.log('[theme + i18n]');
  {
    const { dom, errors } = boot({ theme: 'dark', lang: 'zh-CN' });
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'init no errors');
    assert(d.documentElement.getAttribute('data-theme') === 'dark', 'stored theme pre-applied');
    click(d, '#themeToggle');
    assert(d.documentElement.getAttribute('data-theme') === 'light', 'theme toggles to light');
    assert(dom.window.localStorage.getItem('imm_theme') === 'light', 'theme persisted');
    const jaBtn = [...d.querySelectorAll('#langMenu .ip-item')].find(b => b.dataset.l === 'ja-JP');
    click(d, jaBtn);
    assert(d.documentElement.getAttribute('data-lang') === 'ja-JP', 'language switches to ja-JP');
    assert(dom.window.localStorage.getItem('imm_lang') === 'ja-JP', 'language persisted');
    assert(d.getElementById('genBtn').textContent.includes('生成'), 'btn label translated');
  }

  /* ============ 抽屉：高级参数 / 图库 / 批量 ============ */
  console.log('[drawers]');
  {
    const { dom, errors } = boot({});
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'init no errors');
    click(d, '#drawerToggle');
    assert(d.getElementById('drawer').classList.contains('open'), 'advanced drawer opens');
    assert(d.getElementById('mTitle').textContent === '高级参数', 'drawer title 高级参数');
    click(d, '#drawerClose');
    assert(!d.getElementById('drawer').classList.contains('open'), 'drawer closes');
    click(d, '#openGallery');
    await sleep(50);
    assert(d.getElementById('galleryDrawer').classList.contains('open'), 'gallery drawer opens');
    const gCards = [...d.querySelectorAll('#gMasonry .g-card')];
    assert(gCards.length === 1 && gCards[0].textContent.includes('a cat'), 'gallery renders 1 card');
    click(d, '#openBatch');
    await sleep(50);
    assert(d.getElementById('batchDrawer').classList.contains('open'), 'batch drawer opens');
    assert(d.getElementById('bFileStat').textContent === '0 个 · 0 行', 'batch summary initial');
    assert(d.getElementById('bSubmit').getAttribute('data-i18n') === 'btn_generate_batch', 'batch submit button wired');
  }

  /* ============ 悬浮查看器：点击图库卡片打开 ============ */
  console.log('[viewer]');
  {
    const { dom, errors } = boot({});
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'init no errors');
    click(d, '#openGallery');
    await sleep(50);
    click(d, '#gMasonry .g-card');
    assert(d.getElementById('viewer').classList.contains('show'), 'viewer opens on card click');
    assert(d.getElementById('vTitle').textContent === 'a cat', 'viewer title = prompt');
    assert(d.getElementById('vImg').textContent !== '' && d.getElementById('vImg').querySelector('img'), 'viewer renders image');
    click(d, '#vClose');
    assert(!d.getElementById('viewer').classList.contains('show'), 'viewer closes');
  }

  /* ============ SSE：task_status 进度 → 完成 ============ */
  console.log('[sse]');
  {
    const { dom, errors } = boot({});
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'init no errors');
    const es = FakeEventSource.instances[0];
    assert(!!es, 'EventSource created');
    es.dispatch('task_status', { task_id: 't1', status: 'processing', progress: 40, phase: 'sampling' });
    assert(d.getElementById('progFill').style.width === '40%', 'progress bar 40%');
    assert(d.getElementById('phaseText').textContent.includes('采样中'), 'phase text translated');
    es.dispatch('task_status', { task_id: 't1', status: 'completed', result: ['fake_00001_.png'] });
    assert(d.getElementById('phaseText').textContent.includes('完成'), 'completion updates phase text');
    assert(d.getElementById('progFill').style.width === '100%', 'progress bar 100%');
  }

  /* ============ 队列悬浮球 ============ */
  console.log('[queue pill]');
  {
    const { dom, errors } = boot({});
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'init no errors');
    click(d, '#queuePill');
    await sleep(50);
    assert(d.getElementById('queuePop').classList.contains('show'), 'queue popover opens');
    assert(d.getElementById('queueItems').textContent.includes('队列空闲'), 'empty queue shows 队列空闲');
    assert(d.getElementById('qCancelBtn').getAttribute('type') === 'button', 'cancel button present');
  }

  /* ============ 可访问性抽查（aria / 键盘可达） ============ */
  console.log('[a11y spot-check]');
  {
    const { dom, errors } = boot({});
    const d = dom.window.document;
    await sleep(300);
    assert(errors.length === 0, 'init no errors');
    const iconBtns = [...d.querySelectorAll('.topbar .icon-btn')];
    assert(iconBtns.length >= 4 && iconBtns.every(b => b.tagName === 'BUTTON'), 'topbar buttons are buttons');
    assert(d.getElementById('genBtn').tagName === 'BUTTON', 'generate is a button');
    assert(d.getElementById('posPrompt').tagName === 'TEXTAREA', 'prompt is textarea');
    const viewerBtns = [...d.querySelectorAll('#viewer .v-tools button')];
    assert(viewerBtns.length >= 10 && viewerBtns.every(b => b.getAttribute('aria-label')), 'viewer tools have aria-label');
  }

  console.log('\nRESULT: pass=' + pass + ' fail=' + fail);
  process.exit(fail ? 1 : 0);
})();
