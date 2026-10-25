"""Start found. with one command:  python run.py   (then open http://localhost:8030, admin at /admin)

Serves the API, the public site and the admin console from one process. Needs PORTKEY_API_KEY in a .env in this
folder or one folder up. The database is created from data/sources/ on first start.
"""

import os
import sys
import webbrowser
from pathlib import Path
from threading import Timer

import uvicorn

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8030"))
    os.environ["FRONTEND_URL"] = f"http://localhost:{port}"  # links in emails point at this server
    if "--no-browser" not in sys.argv:
        Timer(2.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    print(f"\n  found. is starting on http://localhost:{port}   (admin console: http://localhost:{port}/admin)\n")
    uvicorn.run("main:app", host="127.0.0.1", port=port)
