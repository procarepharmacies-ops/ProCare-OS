import os, sys

os.environ["SYNC_ENABLED"] = "0"
sys.path.insert(0, "C:/Users/Procare/ProCare-OS/src/backend")

# Write to stderr, flush
sys.stderr.write("HERMES_STDERR_TEST_OUTPUT\n")
sys.stderr.flush()

import json, urllib.request, time

def api(method, path, body=None, token=None, timeout=300):
    url = f"http://127.0.0.1:8100{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read()), e.code
        except:
            return {"error": f"HTTP {e.code}"}, e.code
    except Exception as e:
        return {"error": str(e)}, 0

print("=== AUTH ===", flush=True)
auth, code = api("POST", "/api/auth/login",
                 {"username": "ahmedibrahim", "password": "Procare@2026"},
                 timeout=15)
token = auth.get("token")
print(f"Token: {'OK' if token else 'FAIL'} (code={code})", flush=True)
if not token:
    print("FATAL", flush=True)
    sys.exit(1)

print(f"Token: {token[:40]}...", flush=True)

print("=== TRIGGER MIRROR ===", flush=True)
start = time.time()
result, code = api("POST", "/api/etl/run", {}, token, timeout=300)
elapsed = time.time() - start
print(f"Code: {code}, Elapsed: {elapsed:.1f}s", flush=True)
if code == 200:
    print(f"SUCCESS: {json.dumps(result, indent=2, default=str)[:500]}", flush=True)
elif code == 500:
    print(f"500: {json.dumps(result, indent=2, default=str)[:500]}", flush=True)
else:
    print(f"Other: {json.dumps(result, indent=2, default=str)[:500]}", flush=True)

print("=== DONE ===", flush=True)
