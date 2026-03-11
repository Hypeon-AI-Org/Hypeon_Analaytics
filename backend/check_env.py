from pathlib import Path
import os
os.chdir(Path(__file__).resolve().parent)
env = Path.cwd().parent / ".env"
print("env path:", env, "exists:", env.exists())
if env.exists():
    for line in env.read_text(encoding="utf-8").splitlines():
        s = line.strip().replace("\r", "")
        if s.startswith("API_KEY=") and "=" in s:
            val = s.split("=", 1)[1].strip().strip("'\"")
            print("API_KEY length:", len(val))
            break
# Also check config
from app.config import get_api_key
k = get_api_key()
print("get_api_key() result: len=%s" % (len(k) if k else "None"))
