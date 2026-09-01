import json
import time
import urllib.request

base = "http://127.0.0.1:8288"
payload = {
    "positive_prompt": "一只可爱的橘猫",
    "negative_prompt": "",
    "cfg": 1.0, "steps": 8, "width": 768, "height": 768, "seed": -1, "batch_size": 1,
    "engine_name": "z_image_turbo_native",
    "lora_stack": [], "seedvr2_enable": False, "eses_enable": False, "vram_enable": False,
    "output_format": "png",
}
req = urllib.request.Request(base + "/api/generate", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
r = urllib.request.urlopen(req, timeout=15)
d = json.loads(r.read())
tid = d.get("task_id")
print("submitted:", tid, "status:", d.get("status"))

for i in range(12):
    try:
        td = json.loads(urllib.request.urlopen(f"{base}/api/tasks/{tid}", timeout=10).read())
        t = td.get("task", td)
        status = t.get("status")
        out = t.get("output_count")
        err = (t.get("error") or "")[:300]
        print(f"[{i*10}s] status={status} output={out} err={err}")
        if status in ("completed", "failed", "cancelled"):
            break
    except Exception as e:
        print(f"[{i*10}s] ERR {e}")
    time.sleep(10)
