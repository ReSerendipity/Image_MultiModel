/* theme-init.js — 主题/语言防闪烁初始化（P2-4 CSP 收紧）。
 *
 * 自 base.html 内联 <script> 外置：CSP script-src 'self' 禁止内联脚本，
 * 外置同步脚本同样在 CSS 渲染前执行，防闪烁行为不变。
 */
(function () {
  'use strict';
  var t = localStorage.getItem('imm_theme') || 'light';
  var l = localStorage.getItem('imm_lang') || 'zh-CN';
  document.documentElement.setAttribute('data-theme', t);
  document.documentElement.setAttribute('data-lang', l);
})();
