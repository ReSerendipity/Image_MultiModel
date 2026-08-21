"""E1: Portable mode API verification script - safely tests and reverts config."""
import sys
import yaml
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))

config_path = PROJECT_ROOT / "config.yaml"
backup_path = PROJECT_ROOT / "config.yaml.bak"

# Backup config
shutil.copy2(config_path, backup_path)

try:
    # Read and modify config
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["models"]["model_source_mode"] = "portable"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True)

    # Now test with TestClient
    from integrated_app.config import load_config
    load_config()  # Force reload with new config
    from integrated_app.app_server import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app()) as c:
        r = c.get("/api/config/loras")
        print(f"Status: {r.status_code}")
        data = r.json()
        loras = data.get("loras", [])
        print(f"Loras count: {len(loras)}")
        print(f"No error: {'error' not in data}")
        if r.status_code == 200:
            print("Portable mode API test: PASS")
        else:
            print(f"Portable mode API test: FAIL - {data}")
finally:
    # Restore config
    shutil.copy2(backup_path, config_path)
    backup_path.unlink()
    print("Config restored to shared mode")
