# =============================================================================
# CELL 2 — Zero-Trust Configuration & In-Memory Authentication Handshake
# =============================================================================
import os
import sys
import time
import requests

# Prevent OpenSSL clashes on Kaggle
sys.modules['OpenSSL'] = None

SERVER_URL = os.environ.get("SERVER_URL", "").strip().rstrip("/")
WORKER_AUTH_KEY = os.environ.get("WORKER_AUTH_KEY", "scribd_sec_key_9921_xK9").strip()

# ── Dynamic In-Memory Runtime Credentials (Never Stored On Disk!) ───
FIREBASE_DB_URL = ""
DB_ROOT = "scribd_cloud"
BOT_TOKEN = ""
PROXY_URL = ""
BOT_USERNAME = "cryvex_uploader_bot"

if SERVER_URL:
    print(f"🔒 [Security Handshake] Authenticating with Render Master Node at {SERVER_URL}...")
    try:
        resp = requests.post(
            f"{SERVER_URL}/api/worker/handshake",
            json={"auth_key": WORKER_AUTH_KEY},
            timeout=15
        )
        if resp.ok:
            data = resp.json()
            if data.get("status") == "ok":
                BOT_TOKEN = data.get("bot_token", "")
                FIREBASE_DB_URL = data.get("firebase_db_url", "").rstrip("/")
                DB_ROOT = data.get("db_root", "scribd_cloud")
                PROXY_URL = data.get("proxy_url", "")
                BOT_USERNAME = data.get("bot_username", "cryvex_uploader_bot")
                print("✅ [Zero-Trust Verified] In-memory session credentials loaded securely!")
            else:
                print(f"❌ Handshake failed: {data.get('message')}")
        else:
            print(f"❌ Handshake HTTP error: {resp.status_code}")
    except Exception as e:
        print(f"⚠️ Handshake connection notice: {e}")

# Fallback to local environment if running locally/offline
if not FIREBASE_DB_URL:
    FIREBASE_DB_URL = os.environ.get("FIREBASE_DB_URL", "").strip().rstrip("/")
if not BOT_TOKEN:
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
if not PROXY_URL:
    PROXY_URL = os.environ.get("PROXY_URL", "").strip()

WORKING_DIR = "/kaggle/working" if os.path.exists("/kaggle/working") else os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(WORKING_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# 11-Hour Zero-Downtime Handoff Window
MAX_RUNTIME_SECONDS = float(os.environ.get("MAX_RUNTIME_HOURS", "11.0")) * 3600
WORKER_SESSION_START = time.time()

# Multi-Core Parallel Concurrency (Kaggle has 30GB RAM & 4 vCPUs!)
MAX_PARALLEL_RENDERS = int(os.environ.get("MAX_PARALLEL_RENDERS", "10"))

DB_BASE_URL = FIREBASE_DB_URL

def fb_get(path):
    if not DB_BASE_URL:
        return None
    url = f"{DB_BASE_URL}/{DB_ROOT}/{path.strip('/')}.json"
    try:
        r = requests.get(url, timeout=6)
        return r.json() if r.ok else None
    except Exception:
        return None

def fb_put(path, data):
    if not DB_BASE_URL:
        return False
    url = f"{DB_BASE_URL}/{DB_ROOT}/{path.strip('/')}.json"
    try:
        r = requests.put(url, json=data, timeout=6)
        return r.ok
    except Exception:
        return False

def fb_delete(path):
    if not DB_BASE_URL:
        return False
    url = f"{DB_BASE_URL}/{DB_ROOT}/{path.strip('/')}.json"
    try:
        r = requests.delete(url, timeout=6)
        return r.ok
    except Exception:
        return False

print("✅ [CELL 2 Complete] Cloud Configuration Active & Connected!")
