"""
tests/test_verify_watermark_cli.py — verify_watermark.py CLI 测试

对应 TEST_AUDIT_REPORT P2-2: scripts/verify_watermark.py 测试
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "verify_watermark.py"

from app.integrated_app import watermark


class TestVerifyWatermarkScript:
    """scripts/verify_watermark.py CLI 测试"""

    def test_script_exists(self):
        """脚本文件存在"""
        assert SCRIPT_PATH.exists(), f"Script not found: {SCRIPT_PATH}"

    def test_verify_npy_file_success(self, tmp_path):
        """验证 .npy 文件 → 成功"""
        # 嵌入水印
        rng = np.random.default_rng(42)
        img = (128 + rng.normal(0, 5, (256, 256))).clip(0, 255)
        ts = 1786200000.0
        marked = watermark.embed_watermark(img, "img_multimodel", "task_cli_001", ts)

        # 保存 .npy
        npy_path = tmp_path / "test_watermark.npy"
        np.save(npy_path, marked)

        # 运行脚本（n_bits 需足够大以覆盖完整 payload）
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(npy_path), "-p", "img_multimodel", "-n", "320"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"
        assert "img_multimodel" in result.stdout
        assert "task_cli_001" in result.stdout
        assert "✅" in result.stdout

    def test_verify_wrong_product_id(self, tmp_path):
        """验证错误 product_id → 失败"""
        rng = np.random.default_rng(42)
        img = (128 + rng.normal(0, 5, (256, 256))).clip(0, 255)
        ts = 1786200000.0
        marked = watermark.embed_watermark(img, "img_multimodel", "task_cli_002", ts)

        npy_path = tmp_path / "test_wrong_pid.npy"
        np.save(npy_path, marked)

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(npy_path), "-p", "wrong_product", "-n", "320"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )

        assert result.returncode == 1
        assert "❌" in result.stdout

    def test_verify_no_watermark(self, tmp_path):
        """验证无水印图像 → 失败"""
        rng = np.random.default_rng(42)
        img = (128 + rng.normal(0, 5, (256, 256))).clip(0, 255)

        npy_path = tmp_path / "no_watermark.npy"
        np.save(npy_path, img)

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(npy_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )

        # 无水印 → 校验失败
        assert result.returncode == 1
