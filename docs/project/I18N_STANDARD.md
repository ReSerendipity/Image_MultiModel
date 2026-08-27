“本文由 2026-08-27 家族治理 E3 从 AGENTS.md §8 移出，内容逐字保留”

# i18n 多语言规范（5 种语言：简中 / 繁中 / 英 / 日 / 韩）

### 8.1 翻译机制（和 TTS_MultiModel 不同，Image_MultiModel 用 JSON 不是 gettext）
- 后端错误文案 + 前端 UI 文案共用 **5 个 JSON 文件**：`app/integrated_app/locales/{zh,zh-tw,en,ja,ko}.json`
- 后端走 `integrated_app/i18n.py` 的 `_()` 包装（三层 fallback：用户指定语言 → en 英文 → key 本身兜底）
- 前端走 `window.I18N.t(key)`，`index.html` 启动时根据浏览器语言 / localStorage 选择加载对应 JSON

### 8.2 三层 fallback 链（任何一层缺翻译不会显示空值或裸 key）
```
用户选择语言（如 ja 日语）
    ↓ 该语言 JSON 里找不到 key →
en 英文（最后兜底，key 本身就是英文语义）
    ↓ 英文也找不到（极端情况）→
key 本身直接显示（最差情况也比空白好）
```

### 8.3 新增翻译 Key 的标准步骤（6 步，1-6 一步不能落）
1. **先在 `locales/en.json` 里加英文原串**（**en.json = 基准语言，所有 key 必须先在这里出现**）：
   ```json
   { "batch_cancel_confirm": "Are you sure you want to cancel all pending batch tasks?" }
   ```
2. 代码里写：后端 `_("batch_cancel_confirm")` / 前端 `I18N.t("batch_cancel_confirm")`
3. 为其余 4 种语言 JSON 同步追加相同 key：
   ```json
   // zh.json:   "batch_cancel_confirm": "确定要取消所有待处理的批量任务吗？"
   // zh-tw.json:"batch_cancel_confirm": "確定要取消所有待處理的批量任務嗎？"
   // ja.json:   "batch_cancel_confirm": "保留中のすべてのバッチタスクをキャンセルしますか？"
   // ko.json:   "batch_cancel_confirm": "보류 중인 모든 일괄 작업을 취소하시겠습니까?"
   ```
4. **不要嵌套对象**：所有 key 扁平化为顶级 `snake_case`（和 locales/*.json 现有风格一致）。不要写 `{ "batch": { "cancel": "..." } }` 这种嵌套。
5. **命名规范**：`<模块>_<动作>_<状态>`，如 `generate_progress_started`、`preset_save_success`、`history_delete_failed`
6. **完整性校验**：跑 `tests/test_i18n.py` 和 `tests/test_i18n_coverage.py`（CI 会跑）：
   ```bash
   python -m pytest tests/test_i18n.py tests/test_i18n_coverage.py -v
   # → 必须输出：5 languages × N keys = 5N 条目全匹配，任何一种语言缺 1 个 key 就失败
   ```

---
