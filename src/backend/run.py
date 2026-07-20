"""Dev launcher for the ProCare OS API.

Invoked by .claude/launch.json with an ABSOLUTE path, so it works regardless of
the caller's working directory: it puts src/backend on sys.path (and on
PYTHONPATH for uvicorn's reloader subprocess) before starting the server.
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

# Load .env files (backend dir first, then repo root) so the pharmacy PC can keep
# its API keys / DB settings in a file. Optional: if python-dotenv isn't
# installed the server still starts — a missing package must never take the
# backend down (that surfaces in the browser as a 500 on every request).
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(BASE, ".env"))
    load_dotenv(os.path.join(BASE, "..", "..", ".env"))
except ImportError:
    pass

# The reloader spawns a child process; pass the path through the environment too.
os.environ["PYTHONPATH"] = BASE + os.pathsep + os.environ.get("PYTHONPATH", "")

import uvicorn  # noqa: E402  (import after sys.path is set)

if __name__ == "__main__":
    port = int(os.environ.get("PROCARE_API_PORT", "8100"))
    # Reload is a DEV convenience and a PRODUCTION hazard: the file-watcher
    # restarts the API on any file touch and the reloader dies with its parent
    # console, so an unattended pharmacy PC loses the backend mid-day. Default
    # OFF; opt in with PROCARE_RELOAD=1 while developing.
    reload = os.environ.get("PROCARE_RELOAD", "0") == "1"
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        reload=reload,
        reload_dirs=[os.path.join(BASE, "app")] if reload else None,
    )
