"""
clean_launch.py — 启动加固（附录 E1）

安全启动 Image MultiModel 应用：
- 自动检测并使用 WinPython（不使用系统 Python）
- 检查 Python 版本
- 检查依赖
- 设置环境变量
- 启动 uvicorn
"""

import os
import subprocess
import sys
from pathlib import Path

# ── 项目根目录 ───────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = Path(__file__).resolve().parent

# ── WinPython 自动检测 ───────────────────────────────────────
# 优先使用项目内的 WPy64 目录，其次查找参考项目的 WinPython
def find_winpython():
    """查找 WinPython python.exe 路径"""
    # 1. 项目内的 WinPython
    for wpy_dir in PROJECT_ROOT.glob("WPy64-*"):
        py = wpy_dir / "python" / "python.exe"
        if py.exists():
            return str(py)
    # 2. 参考项目 Seedvr2 的 WinPython
    ref_wpy = Path(r"C:\Users\Doro\Seedvr2\WPy64-312101\python\python.exe")
    if ref_wpy.exists():
        return str(ref_wpy)
    # 3. 参考项目 TTS_MultiModel 的 WinPython
    ref_wpy2 = Path(r"C:\Users\Doro\TTS_MultiModel\WPy64-312101\python\python.exe")
    if ref_wpy2.exists():
        return str(ref_wpy2)
    # 4. 回退到当前 Python（如果 WinPython 不存在）
    return sys.executable


# ── 环境变量（附录 E1）──────────────────────────────────────
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("MODELSCOPE_OFFLINE", "1")
os.environ.setdefault("COMFYUI_DISABLE_UPDATE_CHECK", "1")
# PyTorch 内存管理
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
# 工作目录
os.chdir(str(PROJECT_ROOT))


def check_python_version():
    """检查 Python 版本 ≥ 3.10"""
    if sys.version_info < (3, 10):
        print(f"[ERROR] Python 3.10+ required, got {sys.version}")
        sys.exit(1)
    print(f"[OK] Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print(f"[OK] Python executable: {sys.executable}")


def check_dependencies():
    """检查关键依赖"""
    required = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "pydantic": "pydantic",
        "yaml": "pyyaml",
        "aiohttp": "aiohttp",
    }
    missing = []
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if missing:
        print(f"[WARN] Missing packages: {', '.join(missing)}")
        print("Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
        print("[OK] Dependencies installed")
    else:
        print("[OK] All dependencies present")


def check_config():
    """检查 config.yaml 存在"""
    cfg_path = PROJECT_ROOT / "config.yaml"
    if not cfg_path.exists():
        print(f"[ERROR] config.yaml not found at {cfg_path}")
        sys.exit(1)
    print(f"[OK] config.yaml found")


def check_workflows():
    """检查工作流文件存在"""
    wf_dir = PROJECT_ROOT / "workflows"
    if not wf_dir.exists():
        print(f"[ERROR] workflows/ directory not found")
        sys.exit(1)
    jsons = list(wf_dir.glob("*.json"))
    if not jsons:
        print("[WARN] No workflow JSON files found")
    else:
        for j in jsons:
            print(f"[OK] Workflow: {j.name}")


def check_models():
    """检查模型目录"""
    for d in ["text", "unet", "vae"]:
        p = PROJECT_ROOT / d
        if p.exists():
            files = list(p.rglob("*.safetensors"))
            print(f"[OK] {d}/ — {len(files)} model(s)")
        else:
            print(f"[WARN] {d}/ not found")


def check_winpython():
    """检查 WinPython 环境"""
    wpy_path = find_winpython()
    if "WPy64" in wpy_path:
        print(f"[OK] WinPython detected: {wpy_path}")
    else:
        print(f"[WARN] WinPython not found, using: {wpy_path}")
    return wpy_path


def launch():
    """启动应用"""
    print("\n" + "=" * 60)
    print("  Image MultiModel — Launching...")
    print("=" * 60)

    check_winpython()
    check_python_version()
    check_dependencies()
    check_config()
    check_workflows()
    check_models()

    # 确保数据目录存在
    for d in ["data", "outputs", "logs"]:
        (PROJECT_ROOT / d).mkdir(parents=True, exist_ok=True)

    print("\n[INFO] Starting uvicorn...")
    print(f"[INFO] Project root: {PROJECT_ROOT}")
    print(f"[INFO] BIN dir: {BIN_DIR}")

    # 添加 bin 到 sys.path
    sys.path.insert(0, str(BIN_DIR))

    # 启动
    import uvicorn
    from integrated_app.config import load_config
    cfg = load_config()
    uvicorn.run(
        "integrated_app.app_server:app",
        host=cfg.server.host,
        port=cfg.server.port,
        workers=cfg.server.workers,
        reload=False,
    )


if __name__ == "__main__":
    # 如果不是 WinPython 在运行，重启为 WinPython
    wpy = find_winpython()
    if "WPy64" in wpy and "WPy64" not in sys.executable:
        print(f"[INFO] Relaunching with WinPython: {wpy}")
        os.execv(wpy, [wpy, __file__])
    else:
        launch()
