"""
=============================================================================
👑 SCRIBD CLOUD MINI-SERVER (MASTER COORDINATOR FOR RENDER)
=============================================================================
Features:
1. 24/7 Always-on Master on Render (Uses <60MB RAM & <30MB Bandwidth/Month).
2. Manages Telegram Bot interactions & user links.
3. Instant Telegram file_id cache checker (Delivers in 0.2s if in Firebase).
4. Submits heavy rendering tasks to Firebase Queue for Kaggle (30GB Worker).
5. 11-Hour Zero-Downtime Auto-Restart Orchestrator via Kaggle REST API.
=============================================================================
"""

import os
import sys
import time
import json
import base64
import re
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# -------------------------------------------------------------
# Configuration & Environment Variables (No hardcoded secrets)
# -------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
FIREBASE_DB_URL = os.environ.get("FIREBASE_DB_URL", "").strip().rstrip("/")
DB_ROOT = os.environ.get("DB_ROOT", "scribd_cloud").strip()

# Kaggle API Credentials for Auto-Restart
KAGGLE_USERNAME = os.environ.get("KAGGLE_USERNAME", "").strip()
KAGGLE_KEY = os.environ.get("KAGGLE_KEY", "").strip()
KAGGLE_SLUG = os.environ.get("KAGGLE_SLUG", "scribd-cloud-worker").strip()
KAGGLE_TITLE = os.environ.get("KAGGLE_TITLE", "Scribd High Speed Cloud Worker").strip()

FORCE_SUB_CHANNEL = os.environ.get("FORCE_SUB_CHANNEL", "").strip()
SERVER_START_TIME = time.time()

if not BOT_TOKEN:
    print("⚠️ WARNING: BOT_TOKEN is not set! Please configure it in your .env or environment variables.")

bot = telebot.TeleBot(BOT_TOKEN or "DUMMY_TOKEN_PLEASE_SET_ENV", parse_mode="Markdown")

# -------------------------------------------------------------
# Firebase REST Helpers (Ultra-Lightweight, Zero SDK Overhead)
# -------------------------------------------------------------
session = requests.Session()


def fb_url(path):
    return f"{FIREBASE_DB_URL}/{DB_ROOT}/{path.strip('/')}.json"


def get_cached_doc(doc_id):
    try:
        r = session.get(fb_url(f"cache/{doc_id}"), timeout=5)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return None


def push_queue_task(task_id, data):
    try:
        r = session.put(fb_url(f"queue/{task_id}"), json=data, timeout=6)
        return r.ok
    except Exception as e:
        print(f"❌ [Queue Push Error] {e}")
        return False


# -------------------------------------------------------------
# Kaggle Notebook Pusher (Spawns 30GB Cloud Worker via REST API)
# -------------------------------------------------------------
def compile_worker_notebook_json():
    """Compiles local kaggle_worker cells into a complete Jupyter Notebook JSON."""
    cells = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    worker_dir = os.path.join(os.path.dirname(base_dir), "kaggle_worker")

    cell_files = [
        "cell1_setup.py",
        "cell2_config.py",
        "cell3_compressor.py",
        "cell4_downloader.js",
        "cell5_worker.py"
    ]

    for cf in cell_files:
        cpath = os.path.join(worker_dir, cf)
        if not os.path.exists(cpath):
            continue

        with open(cpath, "r", encoding="utf-8") as f:
            code = f.read()

        # If it's the JS downloader, safely encode to base64 so no string escape issues occur
        if cf.endswith(".js"):
            js_b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
            code = (
                f'# Cell 4: Write ultra-optimized downloader.js to disk\n'
                f'import base64\n\n'
                f'b64_payload = "{js_b64}"\n'
                f'with open("downloader.js", "wb") as f:\n'
                f'    f.write(base64.b64decode(b64_payload))\n\n'
                f'print("✅ [CELL 4 Complete] downloader.js written cleanly to working directory!")'
            )

        lines = code.splitlines(keepends=True)
        cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": lines
        })

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 2
    }
    return json.dumps(notebook)


def trigger_kaggle_worker():
    """Pushes fresh notebook to Kaggle to start or rotate the 30GB compute session."""
    try:
        print("🚀 [Kaggle Orchestrator] Compiling and pushing notebook to Kaggle REST API...")
        notebook_json = compile_worker_notebook_json()
        creds = base64.b64encode(f"{KAGGLE_USERNAME}:{KAGGLE_KEY}".encode()).decode()
        headers = {
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/json"
        }
        payload = {
            "id": None,
            "slug": f"{KAGGLE_USERNAME}/{KAGGLE_SLUG}",
            "title": KAGGLE_TITLE,
            "text": notebook_json,
            "language": "python",
            "kernelType": "notebook",
            "isPrivate": True,
            "enableGpu": False,
            "enableInternet": True,
            "datasetSources": [],
            "competitionSources": [],
            "kernelSources": []
        }
        url = "https://www.kaggle.com/api/v1/kernels/push"
        resp = session.post(url, headers=headers, json=payload, timeout=30)
        print(f"✅ [Kaggle Push Response] Status: {resp.status_code} | Body: {resp.text[:150]}")
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"❌ [Kaggle Push Failed] {e}")
        return False


# -------------------------------------------------------------
# Background Watchdog: 11-Hour Restart & Worker Heartbeat
# -------------------------------------------------------------
def start_watchdog_thread():
    """Runs in background: monitors worker health and executes zero-downtime handoff."""
    print("🛡️ [Watchdog] Heartbeat and Auto-Restart listener active...")
    while True:
        try:
            # Check restart trigger node
            r = session.get(fb_url("control/trigger_restart"), timeout=5)
            if r.ok:
                val = r.json()
                if val is True:
                    print("⚡ [Auto-Restart] Immediate restart requested by Kaggle worker!")
                    session.put(fb_url("control/trigger_restart"), json=False, timeout=5)
                    trigger_kaggle_worker()
                elif isinstance(val, (int, float)) and time.time() >= val:
                    print("⚡ [Auto-Restart] Scheduled timer reached! Launching new Kaggle worker...")
                    session.put(fb_url("control/trigger_restart"), json=False, timeout=5)
                    trigger_kaggle_worker()

            # Check if worker is dead while queue has tasks
            status_res = session.get(fb_url("worker/heartbeat"), timeout=5)
            if status_res.ok and status_res.json():
                hb = status_res.json()
                last_seen = hb.get("last_seen", 0)
                # If worker hasn't pinged in > 10 minutes (600s)
                if time.time() - last_seen > 600:
                    q_res = session.get(fb_url("queue"), timeout=5)
                    if q_res.ok and q_res.json():
                        print("⚠️ [Worker Offline] Pending tasks in queue but worker heartbeat expired! Auto-restarting Kaggle...")
                        trigger_kaggle_worker()

        except Exception as e:
            pass

        # Check every 60 seconds (Uses < 100 bytes per check = negligible bandwidth)
        time.sleep(60)


threading.Thread(target=start_watchdog_thread, daemon=True).start()


# -------------------------------------------------------------
# Telegram Bot Handlers
# -------------------------------------------------------------
def extract_scribd_info(text):
    if not text:
        return None
    m = re.search(r"scribd\.com/(?:document|doc|presentation|embeds)/(\d+)(?:/([a-zA-Z0-9_-]+))?", text, re.I)
    if m:
        return {"docId": m.group(1), "urlSlug": m.group(2) or None}
    m2 = re.search(r"[?&]doc_id=(\d+)", text, re.I)
    if m2:
        return {"docId": m2.group(1), "urlSlug": None}
    trimmed = text.strip()
    if re.match(r"^\d{6,12}$", trimmed):
        return {"docId": trimmed, "urlSlug": None}
    return None


@bot.message_handler(commands=["start"])
def handle_start(msg):
    first_name = msg.from_user.first_name or "Dost"
    text = (
        f"🌟 *WELCOME TO SCRIBD CLOUD DOWNLOADER*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Namaste *{first_name}*! Ab aap Scribd ke kisi bhi document ko bilkul *FREE*, "
        f"*100% Original Quality* aur *Compressed HD* me download kar sakte hain! 🚀\n\n"
        f"⚡ *Features:*\n"
        f"├ 🚀 *30 GB High-Speed Cloud Compute*\n"
        f"├ 🗜️ *ILovePDF-Style Lossless Compression*\n"
        f"├ 📄 *100% Crisp Font & Zero White Pages*\n"
        f"└ ⚡ *0.2s Instant Delivery for Cached Docs*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💻 *Made with ❤️ by* @cryvex4"
    )
    bot.send_message(msg.chat.id, text)


@bot.message_handler(func=lambda m: True)
def handle_incoming_message(msg):
    text = msg.text or ""
    if text.startswith("/"):
        return

    info = extract_scribd_info(text)
    if not info:
        bot.reply_to(
            msg,
            "⚠️ *Invalid Link!*\n\n"
            "Kripya ek valid Scribd document link bhejein.\n"
            "*Example:* `https://www.scribd.com/document/362922366/...`"
        )
        return

    doc_id = info["docId"]
    chat_id = msg.chat.id
    user_id = msg.from_user.id
    username = msg.from_user.username or msg.from_user.first_name or "User"

    # 1. ⚡ SMART CACHE CHECK (0.2s Instant Delivery)
    cached = get_cached_doc(doc_id)
    if cached and cached.get("file_id"):
        title = cached.get("title", "Scribd Document")
        pages = cached.get("totalPages", "Full")
        bot.send_document(
            chat_id,
            cached["file_id"],
            caption=(
                f"📚 *{title}*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📑 *Pages:* {pages}\n"
                f"⚡ *Delivered Instantly via High-Speed Cloud Cache!* (0.2s)\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 *Downloaded via:* @ScribdPdfDownloaderBot\n"
                f"👨‍💻 *Developer:* @cryvex4"
            )
        )
        return

    # 2. PUSH TASK TO FIREBASE QUEUE FOR KAGGLE
    task_id = f"task_{doc_id}_{int(time.time())}"
    task_payload = {
        "docId": doc_id,
        "urlSlug": info["urlSlug"],
        "chatId": chat_id,
        "userId": user_id,
        "username": username,
        "status": "pending",
        "createdAt": int(time.time())
    }

    ok = push_queue_task(task_id, task_payload)
    if ok:
        bot.send_message(
            chat_id,
            f"⚡ *CLOUD TASK INITIALIZED*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📖 *Doc ID:* `{doc_id}`\n"
            f"⚙️ *Cluster:* 30 GB High-Speed Compute Node\n"
            f"🗜️ *Compressor:* Lossless Ghostscript Engine (Active)\n"
            f"⏳ *Status:* Assigned to worker. Document will be delivered shortly! 🚀\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 *Made by* @cryvex4"
        )
    else:
        bot.send_message(chat_id, "❌ *System Error:* Could not assign task. Please retry.")


# -------------------------------------------------------------
# HTTP Server for Render Health Checks, Webhooks & Uptime Monitors
# -------------------------------------------------------------
class RenderHealthServer(BaseHTTPRequestHandler):
    def do_HEAD(self):
        """Supports HTTP HEAD requests from UptimeRobot / BetterUptime monitors."""
        if self.path in ["/status", "/health", "/"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
        else:
            self.send_error(404, "Not Found")

    def do_GET(self):
        if self.path in ["/status", "/health", "/"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "status": "online",
                "service": "Scribd Cloud Mini-Server (Render Master)",
                "uptime_seconds": int(time.time() - SERVER_START_TIME),
                "timestamp": int(time.time())
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        # Endpoint to trigger Kaggle push remotely
        if self.path == "/api/kaggle/restart":
            ok = trigger_kaggle_worker()
            self.send_response(200 if ok else 500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": ok}).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        pass


def run_http_server(port=8000):
    server = HTTPServer(("0.0.0.0", port), RenderHealthServer)
    print(f"🌐 [Render Server] Health check listening on port {port}...")
    server.serve_forever()


# -------------------------------------------------------------
# Main Application Launcher
# -------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # Start HTTP Health Server in background thread
    threading.Thread(target=run_http_server, args=(port,), daemon=True).start()

    print("🤖 [Telegram Bot] Polling started on Mini-Server...")
    try:
        bot.infinity_polling(timeout=15, long_polling_timeout=10)
    except Exception as e:
        print(f"Bot Polling Exception: {e}")
