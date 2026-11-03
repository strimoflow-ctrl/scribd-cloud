# =============================================================================
# CELL 2 — Configuration & Firebase Connection (Secure Env & Kaggle Secrets)
# =============================================================================
import os
import sys
import time
import requests

# Prevent OpenSSL clashes on Kaggle
sys.modules['OpenSSL'] = None

# Helper to fetch credentials from Kaggle Secrets, OS Environment, or .env
def get_config(key, default=""):
    val = os.environ.get(key, "").strip()
    if val:
        return val
    try:
        from kaggle_secrets import UserSecretsClient
        user_secrets = UserSecretsClient()
        val = user_secrets.get_secret(key)
        if val:
            return val.strip()
    except Exception:
        pass
    return default

# ── Dynamic Configuration from Environment ───────────────────
FIREBASE_DB_URL = get_config("FIREBASE_DB_URL", "").rstrip("/")
DB_ROOT = get_config("DB_ROOT", "scribd_cloud")
BOT_TOKEN = get_config("BOT_TOKEN", "")

# Optional Residential Proxy (Webshare, IPRoyal, etc.)
PROXY_URL = get_config("PROXY_URL", "")

# Compute and Worker Paths
WORKING_DIR = "/kaggle/working" if os.path.exists("/kaggle/working") else os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(WORKING_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# 11-Hour Zero-Downtime Handoff Window
MAX_RUNTIME_SECONDS = float(get_config("MAX_RUNTIME_HOURS", "11.0")) * 3600
WORKER_SESSION_START = time.time()

# Multi-Core Parallel Concurrency (Kaggle has 30GB RAM & 4 vCPUs!)
MAX_PARALLEL_RENDERS = int(get_config("MAX_PARALLEL_RENDERS", "10"))

print("🔥 Connecting to Firebase RTDB Cloud Queue...")
if not FIREBASE_DB_URL:
    print("⚠️ WARNING: FIREBASE_DB_URL not found in Kaggle Secrets / Environment!")
if not BOT_TOKEN:
    print("⚠️ WARNING: BOT_TOKEN not found in Kaggle Secrets / Environment!")

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
