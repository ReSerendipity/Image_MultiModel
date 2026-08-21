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
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

# ── 项目根目录 ───────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent

# ── WinPython 自动检测 ───────────────────────────────────────
# 优先使用项目内的 WPy64 目录，其次查找参考项目的 WinPython，
# 再回退到系统级 CUDA Python（C:\Python312，含 cu13x PyTorch）。
def find_winpython():
    """查找带 CUDA 的 python.exe 路径"""
    # 0. 项目本地 .venv（隔离模型环境，最高优先，避免回落共享全局 Python）
    venv_py = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    # 1. 项目内的 WinPython
    for wpy_dir in PROJECT_ROOT.glob("WPy64-*"):
        py = wpy_dir / "python" / "python.exe"
        if py.exists():
            return str(py)
    # 2. 参考项目 Seedvr2 的 WinPython
    ref_wpy = Path(r"C:\Users\Doro\SeedVR2-lite\WPy64-312101\python\python.exe")
    if ref_wpy.exists():
        return str(ref_wpy)
    # 3. 参考项目 TTS_MultiModel 的 WinPython
    ref_wpy2 = Path(r"C:\Users\Doro\TTS_MultiModel\WPy64-312101\python\python.exe")
    if ref_wpy2.exists():
        return str(ref_wpy2)
    # 4. 系统级 CUDA Python（含 cu13x PyTorch，CUDA 可用）——避免回退到 CPU 版 torch
    for sys_py in (
        Path(r"C:\Python312\python.exe"),
        Path(r"C:\Users\Doro\APP\ComfyUI-aki-v3\python\python.exe"),
    ):
        if sys_py.exists():
            try:
                code = subprocess.run(
                    [str(sys_py), "-c", "import torch; assert torch.cuda.is_available()"],
                    capture_output=True, timeout=30,
                )
                if code.returncode == 0:
                    return str(sys_py)
            except Exception:
                pass
    # 5. 回退到当前 Python（如果上面都不存在）
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
    print("[OK] config.yaml found")


def check_workflows():
    """检查工作流文件存在"""
    wf_dir = PROJECT_ROOT / "workflows"
    if not wf_dir.exists():
        print("[ERROR] workflows/ directory not found")
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


def find_available_port(start_port: int, host: str = "127.0.0.1", max_attempts: int = 200) -> int:
    """从 start_port 向上查找第一个可用的端口（bind 探测）。

    对齐 TTS_MultiModel / Seedvr2 的自动换端口策略：默认端口被占用时
    向上顺延，避免启动直接报 [Errno 10048] address already in use。

    Args:
        start_port: 起始端口号（含）。
        host: 绑定主机，默认 127.0.0.1。
        max_attempts: 最大尝试次数，默认 200（最多尝试到 start_port+199）。

    Returns:
        int: 找到的第一个可用端口。

    Raises:
        OSError: 指定范围内未找到可用端口。
    """
    import socket

    for offset in range(max_attempts):
        candidate = start_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, candidate))
                return candidate
            except OSError:
                continue
    raise OSError(f"在 {start_port}~{start_port + max_attempts} 范围内未找到可用端口")


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
    print(f"[INFO] App dir: {APP_DIR}")

    # 添加 app 到 sys.path
    sys.path.insert(0, str(APP_DIR))

    # 启动
    import uvicorn

    from integrated_app.config import load_config
    cfg = load_config()

    # 端口被占用时自动向上顺延，避免启动失败（对齐 TTS_MultiModel / Seedvr2）
    host = cfg.server.host
    actual_port = find_available_port(cfg.server.port, host)
    if actual_port != cfg.server.port:
        print(f"[INFO] 端口 {cfg.server.port} 已被占用，自动切换到可用端口 {actual_port}")

    # 根据配置自动打开浏览器
    auto_open = getattr(cfg.server, "auto_open_browser", False)
    if auto_open:
        def _auto_open_browser(ip, port, timeout=300):
            url = f"http://{ip}:{port}"
            print(f"[INFO] 等待服务就绪后将自动打开浏览器: {url}")
            start_time = time.time()
            while time.time() - start_time < timeout:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1)
                    if sock.connect_ex((ip, int(port))) == 0:
                        break
                time.sleep(1)
            else:
                print(f"[WARN] 等待服务就绪超时（{timeout}s），未自动打开浏览器")
                return
            time.sleep(2)
            print(f"[INFO] 服务就绪，正在弹出网页: {url}")
            webbrowser.open(url)

        threading.Thread(
            target=_auto_open_browser,
            args=(host, actual_port),
            daemon=True,
            name="auto-open-browser",
        ).start()

    uvicorn.run(
        "integrated_app.app_server:app",
        host=host,
        port=actual_port,
        workers=cfg.server.workers,
        reload=False,
    )


if __name__ == "__main__":
    # 如果找到的 CUDA Python 与当前运行的不是同一个，则重启为它
    wpy = find_winpython()
    if os.path.abspath(wpy) != os.path.abspath(sys.executable):
        print(f"[INFO] Relaunching with CUDA Python: {wpy}")
        os.execv(wpy, [wpy, __file__])
    else:
        launch()
