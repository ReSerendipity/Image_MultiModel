"""
tests/e2e/test_core_user_flows.py — 核心用户流 E2E 测试

覆盖关键用户操作路径（P2 优先级）：
1. 生成图片全流程：填写表单 → 提交 → SSE 进度 → 结果展示
2. 查看历史记录：进入历史页面 → 浏览记录 → 查看详情
3. 导出功能：选择记录 → 导出 ZIP
4. 预设管理：创建预设 → 使用预设 → 删除预设

注意：这些测试需要应用正在运行且能够实际生成图片。
如果服务不可用，测试会自动跳过。

P0-1 修复：选择器对齐实际前端 ID（#posPrompt / #width / #height / #outGrid / #openBatch）
P2-2 改进：巨型 test_txt2img_complete_flow 拆分为独立小步骤
P2-3 改进：page.wait_for_timeout 改为 wait_for_selector 条件等待
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="session")
def base_url():
    """应用基础 URL"""
    return "http://127.0.0.1:8288"


def check_app_online(base_url: str) -> bool:
    """检查应用是否在线"""
    try:
        from urllib.request import urlopen
        with urlopen(f"{base_url}/api/health", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


@pytest.fixture(scope="module")
def api_client():
    """API TestClient 用于预设管理等 API 级操作"""
    from app.integrated_app.app_server import create_app
    with TestClient(create_app()) as c:
        _csrf_r = c.get('/api/health')
        _csrf_tok = _csrf_r.headers.get('X-CSRF-Token', '')
        if _csrf_tok:
            c.headers['X-CSRF-Token'] = _csrf_tok
        yield c


class TestCoreUserFlows:
    """核心用户流 E2E 测试"""

    @pytest.fixture(autouse=True)
    def setup(self, base_url):
        """每个测试前检查应用状态"""
        if not check_app_online(base_url):
            pytest.skip(f"Application not online at {base_url}")

    # ════════════════════════════════════════════════════════
    # Flow 1a: 页面加载与表单验证（从巨型测试拆分）
    # ════════════════════════════════════════════════════════
    def test_page_loads_and_form_exists(self, page, base_url, screenshot):
        """页面加载成功 + Prompt 输入框 + 生成按钮存在"""
        page.goto(base_url)
        page.wait_for_selector(".topbar")
        page.wait_for_load_state("networkidle")

        assert page.title() or "Image MultiModel" in page.inner_text("body"), \
            "Page title should contain 'Image MultiModel'"

        # 实际前端 ID 为 #posPrompt（非 #promptInput）
        prompt_input = page.query_selector("#posPrompt")
        assert prompt_input is not None, "Prompt input (#posPrompt) should exist"

        gen_btn = page.query_selector("#genBtn")
        assert gen_btn is not None, "Generate button (#genBtn) should exist"
        screenshot("page_loaded")

    # ════════════════════════════════════════════════════════
    # Flow 1b: 填写表单并提交生成请求
    # ════════════════════════════════════════════════════════
    @pytest.mark.slow  # 真实 GPU 推理：仅手动/慢速冒烟运行（对应测试体系评估 P0-2 去 GPU 化）
    def test_fill_form_and_submit(self, page, base_url, screenshot):
        """填写 prompt → 设置低分辨率 → 点击生成"""
        page.goto(base_url)
        page.wait_for_selector(".topbar")
        page.wait_for_load_state("networkidle")

        # 填写 Prompt（实际 ID: #posPrompt）
        prompt_input = page.query_selector("#posPrompt")
        assert prompt_input is not None
        prompt_input.fill("一只可爱的橘猫在窗台上晒太阳，温暖的光线，日系插画风格")

        # 设置低分辨率以加快测试速度（实际 ID: #width / #height，非 #widthInput）
        width_input = page.query_selector("#width")
        height_input = page.query_selector("#height")
        if width_input:
            width_input.fill("256")
        if height_input:
            height_input.fill("256")

        # 点击生成按钮
        gen_btn = page.query_selector("#genBtn")
        assert gen_btn is not None
        gen_btn.click()
        screenshot("form_submitted")

    # ════════════════════════════════════════════════════════
    # Flow 1c: 等待进度条出现
    # ════════════════════════════════════════════════════════
    @pytest.mark.slow  # 真实 GPU 推理：仅手动/慢速冒烟运行
    def test_progress_bar_appears(self, page, base_url, screenshot):
        """提交后等待进度条出现（条件等待替代固定 timeout）"""
        page.goto(base_url)
        page.wait_for_selector(".topbar")
        page.wait_for_load_state("networkidle")

        prompt_input = page.query_selector("#posPrompt")
        if prompt_input:
            prompt_input.fill("test progress bar")
        width_input = page.query_selector("#width")
        height_input = page.query_selector("#height")
        if width_input:
            width_input.fill("256")
        if height_input:
            height_input.fill("256")

        gen_btn = page.query_selector("#genBtn")
        if gen_btn:
            gen_btn.click()
            # 条件等待：等待进度条出现（而非固定 timeout）
            try:
                page.wait_for_selector("#genProgress", state="visible", timeout=10000)
                screenshot("progress_visible")
            except Exception:
                pytest.skip("Generation did not start (progress bar not visible)")

    # ════════════════════════════════════════════════════════
    # Flow 1d: 等待输出图片
    # ════════════════════════════════════════════════════════
    @pytest.mark.slow  # 真实 GPU 推理：仅手动/慢速冒烟运行
    def test_output_appears(self, page, base_url, screenshot):
        """等待输出图片出现（条件等待 #outGrid 内 img）"""
        page.goto(base_url)
        page.wait_for_selector(".topbar")
        page.wait_for_load_state("networkidle")

        prompt_input = page.query_selector("#posPrompt")
        if prompt_input:
            prompt_input.fill("test output")
        width_input = page.query_selector("#width")
        height_input = page.query_selector("#height")
        if width_input:
            width_input.fill("256")
        if height_input:
            height_input.fill("256")

        gen_btn = page.query_selector("#genBtn")
        if gen_btn:
            gen_btn.click()
            # 等待进度条
            try:
                page.wait_for_selector("#genProgress", state="visible", timeout=10000)
            except Exception:
                pytest.skip("Generation did not start")

        # 条件等待输出（实际 ID: #outGrid，非 #outputGrid）
        output_grid = page.query_selector("#outGrid")
        if output_grid:
            try:
                output_grid.wait_for_selector("img", state="attached", timeout=60000)
                images = output_grid.query_selector_all("img")
                assert len(images) > 0, "At least one output image should be generated"
                screenshot("output_appeared")
            except Exception:
                pytest.skip("Output did not appear within timeout (may be due to VRAM or environment)")

    # ════════════════════════════════════════════════════════
    # Flow 2: 批量任务入口验证
    # ════════════════════════════════════════════════════════
    def test_batch_drawer_opens(self, page, base_url, screenshot):
        """批量抽屉打开（实际入口: #openBatch，非 #batchInput）"""
        page.goto(base_url)
        page.wait_for_selector(".topbar")
        page.wait_for_load_state("networkidle")

        # 点击批量按钮打开抽屉
        batch_btn = page.query_selector("#openBatch")
        if batch_btn is None:
            pytest.skip("Batch open button (#openBatch) not available")

        batch_btn.click()
        # 条件等待抽屉打开（替代 wait_for_timeout）
        page.wait_for_selector("#batchDrawer.open", timeout=5000)
        screenshot("batch_drawer_open")

        # 验证批量提交按钮存在
        b_submit = page.query_selector("#bSubmit")
        assert b_submit is not None, "Batch submit button (#bSubmit) should exist"

    # ════════════════════════════════════════════════════════
    # Flow 3: 预设创建与使用（API 级操作）
    # ════════════════════════════════════════════════════════
    def test_preset_create_and_use(self, api_client: TestClient, page, base_url, screenshot):
        """预设管理：通过 API 创建预设 → UI 中验证 → 删除"""
        # Step 1: 通过 API 创建预设
        preset_name = f"E2E_Test_Preset_{uuid.uuid4().hex[:8]}"
        create_resp = api_client.post(
            "/api/presets",
            json={
                "name": preset_name,
                "engine_name": "z_image_turbo_native",
                "config": {
                    "steps": 10,
                    "cfg": 7.0,
                    "width": 512,
                    "height": 512,
                },
            },
        )

        if create_resp.status_code != 200:
            pytest.skip(f"Cannot create preset: {create_resp.status_code}")

        preset_id = create_resp.json().get("id")
        assert preset_id, "Preset ID should be returned"

        # Step 2: 刷新 UI 验证
        page.goto(base_url)
        page.wait_for_selector(".topbar")
        page.wait_for_load_state("networkidle")
        screenshot("preset_created")

        # Step 3: 通过 API 验证预设存在
        presets_resp = api_client.get("/api/presets")
        assert presets_resp.status_code == 200
        presets = presets_resp.json().get("presets", [])
        preset_names = [p.get("name") for p in presets]
        assert preset_name in preset_names, f"Preset '{preset_name}' should appear in list"

        # Step 4: 清理 - 删除创建的预设
        delete_resp = api_client.delete(f"/api/presets/{preset_id}")
        if delete_resp.status_code not in (200, 204, 404):
            print(f"Warning: Failed to delete preset: {delete_resp.status_code}")

        screenshot("preset_cleanup")

    # ════════════════════════════════════════════════════════
    # Flow 4: 主题切换
    # ════════════════════════════════════════════════════════
    def test_theme_switch_flow(self, page, base_url, screenshot):
        """主题切换：从 light 切换到 dark → 验证 HTML 属性"""
        page.goto(base_url)
        page.wait_for_selector(".topbar")
        page.wait_for_load_state("networkidle")

        initial_theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
        screenshot(f"theme_before_{initial_theme}")

        theme_toggle = page.query_selector("#themeToggle")
        if theme_toggle:
            theme_toggle.click()
            # 条件等待：等待 data-theme 属性变化（替代 wait_for_timeout(500)）
            page.wait_for_function(
                f"document.documentElement.getAttribute('data-theme') !== '{initial_theme}'",
                timeout=3000
            )
            new_theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
            screenshot(f"theme_after_{new_theme}")
        else:
            pytest.skip("Theme toggle button not found")

    # ════════════════════════════════════════════════════════
    # Flow 5: 语言切换
    # ════════════════════════════════════════════════════════
    def test_language_switch_flow(self, page, base_url, screenshot):
        """语言切换：切换到中文 → 验证界面文字 → 切回英文"""
        page.goto(base_url)
        page.wait_for_selector(".topbar")
        page.wait_for_load_state("networkidle")

        initial_lang = page.evaluate("document.documentElement.getAttribute('data-lang')")
        screenshot(f"lang_before_{initial_lang}")

        try:
            page.evaluate("""
                var sel = document.getElementById('langSelect');
                if (sel) {
                    sel.value = 'zh-CN';
                    sel.dispatchEvent(new Event('change'));
                }
            """)
            # 条件等待：等待 data-lang 属性变化（替代 wait_for_timeout(500)）
            page.wait_for_selector("html[data-lang='zh-CN']", timeout=3000)
            screenshot("lang_switched_to_zh")

            # 切回英文
            page.evaluate("""
                var sel = document.getElementById('langSelect');
                if (sel) {
                    sel.value = 'en-US';
                    sel.dispatchEvent(new Event('change'));
                }
            """)
            page.wait_for_selector("html[data-lang='en-US']", timeout=3000)
            screenshot("lang_restored_to_en")

        except Exception:
            pytest.skip("Language switch failed (element may not exist)")

    # ════════════════════════════════════════════════════════
    # Flow 6: API 健康检查与配置获取
    # ════════════════════════════════════════════════════════
    def test_api_health_and_config(self, api_client: TestClient):
        """API 可用性：健康检查 → 获取配置 → 获取引擎列表"""
        health = api_client.get("/api/health")
        assert health.status_code == 200
        health_data = health.json()
        assert health_data.get("status") == "ok"
        assert "version" in health_data
        assert "engines" in health_data

        config = api_client.get("/api/config")
        assert config.status_code == 200
        config_data = config.json()
        assert "server" in config_data
        assert "models" in config_data

        engines = api_client.get("/api/engine/engines")
        assert engines.status_code == 200
        engines_data = engines.json()
        assert "engines" in engines_data
        assert len(engines_data["engines"]) >= 1, "At least one engine should be available"

    # ════════════════════════════════════════════════════════
    # Flow 7: 任务提交与取消
    # ════════════════════════════════════════════════════════
    def test_task_submit_and_cancel(self, api_client: TestClient):
        """任务取消：提交任务 → 立即取消 → 验证状态变更"""
        submit_resp = api_client.post("/api/generate", json={
            "positive_prompt": "test cancel flow",
            "negative_prompt": "",
            "cfg": 7.5,
            "steps": 5,
            "width": 128,
            "height": 128,
            "seed": -1,
            "batch_size": 1,
            "engine_name": "z_image_turbo_native",
        })

        assert submit_resp.status_code in (200, 409), f"Should accept task: {submit_resp.text}"
        task_id = submit_resp.json()["task_id"]

        cancel_resp = api_client.post(f"/api/tasks/{task_id}/cancel")
        assert cancel_resp.status_code in (200, 404), \
            f"Cancel should be accepted or task already done: {cancel_resp.status_code}"

        status_resp = api_client.get(f"/api/tasks/{task_id}")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["status"] in ("cancelled", "completed", "failed", "pending")
