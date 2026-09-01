import json
import pathlib

files = [
    "workflows/Z_image_turbo.json",
    "workflows/flux1_dev_fp8.json",
    "workflows/flux2_klein_9b.json",
]
for f in files:
    p = pathlib.Path(f)
    if not p.exists():
        print("missing", f)
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    if "schema_version" not in d:
        d["schema_version"] = "1.0.0"
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        print("patched", f)
    else:
        print("already", f)
