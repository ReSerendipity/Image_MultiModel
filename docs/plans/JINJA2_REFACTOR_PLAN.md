# Jinja2 模板化改造方案

## 📋 项目背景

当前 Image_MultiModel 采用单页应用 (SPA) 架构，所有 UI 代码集中在 `bin/integrated_app/static/index.html`（1884 行）。这种架构在后续维护中存在问题：
- 单一文件过大，不方便模块化调整
- CSS/JS 内联不利于团队协作和版本管理
- 无法复用通用组件

本方案参考 TTS_MultiModel 和 SeedVR2 项目的 Jinja2 模板引擎架构，将前端拆分为模块化、板块化的形式。

---

## 🎯 改造目标

### 核心目标
1. **引入 Jinja2 模板引擎**：使用服务端渲染替代纯客户端 SPA
2. **模块化拆分**：将 index.html 拆分为 base.html + partials 组件
3. **静态资源分离**：CSS/JS 从内联改为独立文件
4. **保持功能不变**：API 接口、i18n、SSE 实时通信等后端功能完全保留

### 技术对比

| 特性 | 当前 SPA 架构 | Jinja2 模板架构 |
|------|-------------|----------------|
| 模板引擎 | 无（纯静态） | Jinja2Templates |
| 页面加载 | 单 HTML + JS 动态渲染 | 服务端渲染 + HTMX 增强 |
| 组件复用 | JavaScript DOM 操作 | Jinja2 {% extends %} / {% include %} |
| i18n 实现 | JSON + t() 函数 | Jinja2 I18nExtension |
| 静态文件 | static/目录托管 | templates/ + static/分离 |
| 路由支持 | 前端 Router | 服务端 Route + HTMX |

---

## 📁 目标目录结构

```
bin/integrated_app/
├── templates/                  # ✨新增：Jinja2 模板目录
│   ├── base.html              # 基础模板（布局框架）
│   ├── index.html             # 首页模板（继承 base.html）
│   ├── partials/              # 组件片段
│   │   ├── header.html        # 顶部导航栏
│   │   ├── sidebar.html       # 侧边栏抽屉
│   │   ├── prompt_card.html   # Prompt 输入卡片
│   │   ├── generate_button.html
│   │   ├── gallery.html       # 图片展示区
│   │   └── footer.html        # 底部状态栏
│   └── components/            # 可复用组件
│       ├── drawer.html        # 抽屉容器
│       ├── button.html        # 按钮组件
│       └── input.html         # 输入框组件
├── static/                     # 保留：静态资源目录（结构调整）
│   ├── css/                   # ✨新增：样式文件
│   │   ├── main.css           # 主样式
│   │   ├── theme.css          # 主题变量
│   │   └── components.css     # 组件样式
│   ├── js/                    # ✨新增：脚本文件
│   │   ├── app.js             # 主逻辑
│   │   ├── i18n.js            # 国际化
│   │   ├── sse.js             # SSE 连接
│   │   └── components/        # 组件逻辑
│   │       ├── drawer.js
│   │       └── gallery.js
│   └── images/                # 图片资源
├── locales/                    # 保留：i18n 翻译文件
│   ├── zh.json
│   ├── en.json
│   └── ...
├── routes/                     # 保留：API 路由
├── app_server.py              # ✨修改：使用 Jinja2Templates
└── i18n.py                     # ✨修改：支持 Jinja2 扩展
```

---

## 🔧 具体实施步骤

### 第一步：安装依赖

```bash
# requirements.txt 添加
Jinja2>=3.1.2
Babel>=2.12.0  # Jinja2 国际化支持
```

### 第二步：修改 app_server.py

#### 2.1 导入 Jinja2Templates

```python
from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemLoader
from jinja2.ext import Extension  # 自定义扩展
```

#### 2.2 配置模板和静态文件

```python
# 在 create_app() 函数中替换静态文件托管逻辑
templates_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

# Jinja2 模板配置
templates = Jinja2Templates(
    directory=str(templates_dir),
    encoding="utf-8",
    autoescape=True,  # XSS 防护
)

# 注册 i18n 扩展（可选）
templates.env.add_extension('jinja2.ext.i18n')
templates.env.install_gettext_translations(i18n_manager)  # 需实现 gettext 接口
```

#### 2.3 修改路由处理

```python
# 根路径 → 服务端渲染 index.html
@app.get("/", include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "config": get_config(),
            "lang": request.cookies.get("imm_lang", "zh-CN"),
            "theme": request.cookies.get("imm_theme", "dark"),
        }
    )

# 其他路径仍回退到 index.html（支持 HTMX 局部加载）
@app.get("/{full_path:path}", include_in_schema=False)
async def catch_all(full_path: str, request: Request):
    if full_path.startswith(("css/", "js/", "images/")):
        # 静态资源走 mount
        raise HTTPException(status_code=404)
    
    # 其他路径返回 index.html（前端路由或 HTMX 加载）
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )
```

#### 2.4 移除 VersionedStaticFiles

```python
# 删除 VersionedStaticFiles 类
# 改用 FastAPI 原生 StaticFiles

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
```

### 第三步：创建 base.html 基础模板

```html
<!DOCTYPE html>
<html lang="{{ lang or 'zh-CN' }}" data-theme="{{ theme or 'dark' }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Image MultiModel{% endblock %}</title>
    
    <!-- 防闪烁：主题/语言在 head 中同步 -->
    <script>
        const savedTheme = "{{ theme }}" || localStorage.getItem('imm_theme') || 'dark';
        const savedLang = "{{ lang }}" || localStorage.getItem('imm_lang') || 'zh-CN';
        document.documentElement.setAttribute('data-theme', savedTheme);
        document.documentElement.setAttribute('lang', savedLang);
    </script>
    
    <!-- 静态资源链接 -->
    {% block stylesheets %}
    <link rel="stylesheet" href="/static/css/main.css">
    <link rel="stylesheet" href="/static/css/theme.css">
    <link rel="stylesheet" href="/static/css/components.css">
    {% endblock %}
    
    {% block head_extra %}{% endblock %}
</head>
<body>
    <!-- 头部导航栏 -->
    {% include 'partials/header.html' %}
    
    <!-- 主体内容区 -->
    <main class="main-content">
        {% block content %}
        <!-- 子类填充内容 -->
        {% endblock %}
    </main>
    
    <!-- 侧边栏抽屉 -->
    {% include 'partials/sidebar.html' %}
    
    <!-- 底部状态栏 -->
    {% include 'partials/footer.html' %}
    
    <!-- 静态资源脚本 -->
    {% block scripts %}
    <script src="/static/js/i18n.js"></script>
    <script src="/static/js/sse.js"></script>
    <script src="/static/js/components/drawer.js"></script>
    <script src="/static/js/app.js"></script>
    {% endblock %}
</body>
</html>
```

### 第四步：创建 index.html 首页模板

```html
{% extends "base.html" %}

{% block title %}Z-Image Turbo - {{ _('生成界面') }}{% endblock %}

{% block content %}
<div class="stage-container">
    <!-- Prompt 输入卡片 -->
    {% include 'partials/prompt_card.html' %}
    
    <!-- 生成按钮 -->
    {% include 'partials/generate_button.html' %}
    
    <!-- 图片展示区 -->
    {% include 'partials/gallery.html' %}
</div>
{% endblock %}
```

### 第五步：拆分静态资源

#### 5.1 CSS 文件划分

**main.css** - 主样式（来自原 index.html 第 12-200 行）
```css
/* Seed Design System 变量 */
:root {
    --seed-primary: #6366f1;
    --seed-density: 1.0;
    --seed-radius: 8px;
    /* ... 更多变量 */
}

[data-theme="dark"] {
    /* 暗色模式覆盖 */
}

/* 布局系统 */
.main-content {
    padding: var(--seed-spacing-4);
    /* ... */
}

/* 响应式断点 */
@media (max-width: 900px) {
    /* 移动端适配 */
}
```

**components.css** - 组件样式
```css
/* Drawer 抽屉系统 */
.drawer {
    position: fixed;
    transition: transform 0.3s ease;
}

.drawer-right { right: 0; width: 392px; }
.drawer-left { left: 0; width: 520px; }
.drawer-top { top: 0; max-width: 1100px; }
.drawer-bottom { bottom: 0; max-width: 880px; }

/* Card 卡片组件 */
.card {
    background: var(--seed-surface-1);
    border-radius: var(--seed-radius);
    padding: var(--seed-spacing-4);
}
```

#### 5.2 JS 文件划分

**app.js** - 主逻辑
```javascript
import { initI18n } from './i18n.js';
import { connectSSE } from './sse.js';
import { DrawerManager } from './components/drawer.js';

document.addEventListener('DOMContentLoaded', async () => {
    // 初始化 i18n
    await initI18n();
    
    // 建立 SSE 连接
    connectSSE();
    
    // 初始化抽屉管理器
    DrawerManager.init();
    
    // 加载配置
    await loadConfig();
});
```

**i18n.js** - 国际化
```javascript
const I18N = {
    'zh-CN': {{ locales.zh|tojson }},
    'en-US': {{ locales.en|tojson }},
    // ...
};

let currentLang = localStorage.getItem('imm_lang') || 'zh-CN';

export function t(key, params = {}) {
    const translation = I18N[currentLang]?.[key] || key;
    // 参数替换
    return Object.entries(params).reduce(
        (str, [k, v]) => str.replace(`{${k}}`, v),
        translation
    );
}

export async function switchLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('imm_lang', lang);
    document.documentElement.lang = lang;
    location.reload();
}
```

**sse.js** - SSE 连接
```javascript
let eventSource = null;
const listeners = new Map();

export function connectSSE() {
    eventSource = new EventSource('/api/events');
    
    eventSource.addEventListener('connected', (e) => {
        console.log('SSE connected');
    });
    
    eventSource.addEventListener('task_status', (e) => {
        const data = JSON.parse(e.data);
        notifyListeners('task_status', data);
    });
    
    eventSource.addEventListener('preview', (e) => {
        const data = JSON.parse(e.data);
        notifyListeners('preview', data);
    });
    
    eventSource.addEventListener('heartbeat', (e) => {
        // 保活
    });
}

function notifyListeners(event, data) {
    listeners.get(event)?.forEach(cb => cb(data));
}
```

### 第六步：修改 i18n.py 支持 Jinja2

```python
from jinja2 import Environment, FileSystemLoader
from jinja2.ext import Extension
import json

class I18nExtension(Extension):
    """Jinja2 国际化扩展"""
    
    def __init__(self, environment: Environment):
        super().__init__(environment)
        
        # 加载翻译文件
        locales_dir = Path(__file__).parent / "locales"
        self.translations = {}
        for lang_file in locales_dir.glob("*.json"):
            lang = lang_file.stem  # zh, en, etc.
            with open(lang_file, 'r', encoding='utf-8') as f:
                self.translations[lang] = json.load(f)
    
    def _translate(self, key: str, lang: str, **kwargs) -> str:
        translation = self.translations.get(lang, {}).get(key, key)
        # 参数替换
        for k, v in kwargs.items():
            translation = translation.replace(f"{{{k}}}", str(v))
        return translation
    
    def _gettext(self, key: str, **kwargs) -> str:
        """兼容 gettext 接口"""
        lang = kwargs.pop('lang', 'zh')
        return self._translate(key, lang, **kwargs)

def setup_jinja2_environment():
    """配置 Jinja2 环境"""
    env = Environment(
        loader=FileSystemLoader('templates'),
        extensions=[I18nExtension],
        autoescape=True,
    )
    env.globals['t'] = lambda key, **kw: env.extensions[I18nExtension]._translate(key, 'zh', **kw)
    return env
```

---

## ⚠️ 注意事项

### 1. SSE 实时通信保持不变
- SSE `/api/events` 端点不受影响
- 前端仍需通过 `EventSource` 连接获取实时进度
- 只是将 JavaScript 代码从内联改为独立文件

### 2. API 接口完全兼容
- `/api/config/*`, `/api/generate/*`, `/api/task/*` 等所有 API 保持不变
- CSRF Token 机制继续工作（需通过模板注入）

### 3. 数据库持久化
- `localStorage` 中的 `imm_lang`, `imm_theme`, `imm_accent` 等继续有效
- 历史记录存储在 SQLite DB 中不受影响

### 4. 性能优化策略

#### 模板缓存
```python
# 生产环境开启模板缓存
templates = Jinja2Templates(
    directory=str(templates_dir),
    env=Environment(
        cache_size=4096,  # Jinja2 内存缓存
        auto_reload=False,  # 生产环境禁用自动重载
    )
)
```

#### 静态文件缓存
```python
# 保持差异化缓存策略
app.mount("/static", StaticFiles(
    directory=str(static_dir),
    headers={
        "Cache-Control": "public, max-age=31536000, immutable",  # JS/CSS 一年缓存
    }
), name="static")

# 或使用版本号/hash 文件名
# /static/js/app.v1.2.3.min.js
```

### 5. 开发 vs 生产环境

```yaml
# config.yaml
runtime:
  template_debug: true  # 开发环境开启模板热重载
  static_cache: false   # 开发环境禁用静态文件缓存
```

```python
# app_server.py
if config.runtime.template_debug:
    templates.env.auto_reload = True
    templates.env.cache_size = 0
else:
    templates.env.auto_reload = False
    templates.env.cache_size = 4096
```

---

## 📝 迁移清单

### Phase 1: 基础设施搭建
- [ ] 安装 Jinja2 + Babel 依赖
- [ ] 创建 `templates/`, `static/css/`, `static/js/` 目录
- [ ] 修改 `app_server.py` 使用 `Jinja2Templates`
- [ ] 验证模板渲染基本流程

### Phase 2: 模板拆分
- [ ] 提取 `base.html` 基础布局
- [ ] 创建 `partials/` 组件片段（header, sidebar, footer）
- [ ] 重构 `index.html` 为主模板
- [ ] 测试继承和包含关系

### Phase 3: 静态资源分离
- [ ] 从 `index.html` 提取 CSS 到 `main.css` / `components.css`
- [ ] 从 `index.html` 提取 JS 到 `app.js` / `i18n.js` / `sse.js`
- [ ] 修复跨文件引用路径问题
- [ ] 测试静态文件加载和缓存

### Phase 4: i18n 集成
- [ ] 修改 `i18n.py` 支持 Jinja2 扩展
- [ ] 在模板中使用 `{% trans %}` 块
- [ ] 测试多语言切换
- [ ] 验证翻译文件加载

### Phase 5: 功能回归
- [ ] 测试生成流程（Prompt → Submit → Progress → Result）
- [ ] 测试抽屉开关（左/右/顶/底）
- [ ] 测试 SSE 实时推送
- [ ] 测试任务取消/批量模式
- [ ] 测试历史/画廊功能

### Phase 6: 性能优化
- [ ] 配置模板缓存
- [ ] 配置静态文件 CDN 缓存
- [ ] 压缩 CSS/JS（可选使用 esbuild/terser）
- [ ] 进行压力测试

### Phase 7: 文档更新
- [ ] 更新 `AGENTS.md` 说明新架构
- [ ] 更新 `DEPLOYMENT.md` 部署指南
- [ ] 编写 `FRONTEND_GUIDE.md` 前端开发手册
- [ ] 清理废弃的 `prototypes/` 目录

---

## 🔄 回滚方案

如果在改造过程中发现问题，可以立即回滚：

1. **Git 分支策略**:
```bash
git checkout -b feature/jinja2-refactor
# 所有改动在独立分支进行
git push origin feature/jinja2-refactor
```

2. **快速回滚命令**:
```bash
# 如果测试失败，直接删除分支
git branch -D feature/jinja2-refactor

# 恢复主分支
git checkout main
git pull
```

3. **渐进式上线**:
```bash
# A/B 测试：通过环境变量切换
export USE_JINJA2=true
./start.sh
```

---

## 📊 预期收益

### 开发效率提升
- **代码组织**: 从 1 个 1884 行文件 → 8-10 个小型模块
- **团队协作**: 多个开发者可同时编辑不同组件
- **调试便利**: 错误堆栈指向具体文件和行号

### 维护成本降低
- **组件复用**: 通过 `{% include %}` 避免重复代码
- **样式隔离**: CSS 模块化减少冲突
- **测试覆盖**: 独立文件便于单元测试

### 可扩展性增强
- **新功能**: 直接添加新的 partials 组件
- **多页面**: 轻松扩展 `history.html`, `settings.html`
- **主题系统**: 通过继承机制快速换肤

---

## ✅ 验收标准

1. **功能完整性**: 所有现有功能正常运行（生成、批量、历史、设置）
2. **性能达标**: 首屏加载时间 ≤ 当前 SPA 架构
3. **浏览器兼容**: Chrome/Firefox/Edge/Safari 完全兼容
4. **i18n 准确**: 5 种语言翻译完整且正确显示
5. **响应式设计**: 移动端适配无退化
6. **无障碍访问**: WCAG 2.1 AA 标准依然符合

---

## 📞 沟通计划

- **开发阶段**: 每日站会同步进展
- **测试阶段**: 邀请 QA 团队参与回归测试
- **上线前**: 产品/设计/开发三方 review
- **上线后**: 监控错误日志和用户反馈

---

## 附录 A: 参考项目链接

- TTS_MultiModel: `bin/integrated_app/templates/` (Jinja2 模板)
- SeedVR2: `bin/integrated_app/templates/` (Jinja2 + HTMX)
- FastAPI 官方文档：https://fastapi.tiangolo.com/tutorial/templates/
- Jinja2 官方文档：https://jinja.palletsprojects.com/

---

*文档版本：v1.0*  
*最后更新：2026-08-15*  
*作者：Image MultiModel 开发团队*
