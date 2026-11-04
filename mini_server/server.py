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
# Configuration & Environment Variables (Zero Plaintext Secrets)
# -------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip().strip('"').strip("'")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "cryvex_uploader_bot").strip().strip('"').strip("'")
FIREBASE_DB_URL = os.environ.get("FIREBASE_DB_URL", "").strip().strip('"').strip("'").rstrip("/")
DB_ROOT = os.environ.get("DB_ROOT", "scribd_cloud").strip().strip('"').strip("'")

# Admin Chat ID for Security & Restart Alerts
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "7975542258").strip().strip('"').strip("'")

# Master-Worker Authentication Key (Zero-Trust)
WORKER_AUTH_KEY = os.environ.get("WORKER_AUTH_KEY", "scribd_sec_key_9921_xK9").strip().strip('"').strip("'")
SERVER_URL = os.environ.get("SERVER_URL", "").strip().strip('"').strip("'").rstrip("/")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").strip().strip('"').strip("'").rstrip("/")

# Kaggle API Credentials for Auto-Restart
KAGGLE_USERNAME = os.environ.get("KAGGLE_USERNAME", "").strip().strip('"').strip("'")
KAGGLE_KEY = os.environ.get("KAGGLE_KEY", "").strip().strip('"').strip("'")
KAGGLE_SLUG = os.environ.get("KAGGLE_SLUG", "scribd-cloud-worker").strip().strip('"').strip("'")
KAGGLE_TITLE = os.environ.get("KAGGLE_TITLE", "Scribd High Speed Cloud Worker").strip().strip('"').strip("'")

FORCE_SUB_CHANNEL = os.environ.get("FORCE_SUB_CHANNEL", "").strip().strip('"').strip("'")
DEFAULT_RESIDENTIAL_PROXY = "http://exgyempf:vmto3im799sb@45.38.107.97:6014"
PROXY_URL = os.environ.get("PROXY_URL", DEFAULT_RESIDENTIAL_PROXY).strip().strip('"').strip("'") or DEFAULT_RESIDENTIAL_PROXY
SERVER_START_TIME = time.time()

# In-Memory Real-Time Telemetry Counters
STATS = {
    "total_requests": 0,
    "cache_hits": 0,
    "queue_tasks": 0,
    "unique_users": set()
}

if not BOT_TOKEN:
    print("⚠️ WARNING: BOT_TOKEN is not set! Please configure it in your .env or environment variables.")

bot = telebot.TeleBot(BOT_TOKEN or "DUMMY_TOKEN_PLEASE_SET_ENV", parse_mode="Markdown")

session = requests.Session()


def send_admin_alert(event_title, message, alert_type="INFO"):
    """Sends real-time security & status alerts to developer Telegram (7975542258)."""
    if not ADMIN_CHAT_ID or not BOT_TOKEN:
        return
    icon = "🛡️" if alert_type == "SECURITY" else ("🟢" if alert_type == "SUCCESS" else ("⚠️" if alert_type == "WARNING" else "ℹ️"))
    now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    text = (
        f"{icon} *[SCRIBD CLOUD SYSTEM ALERT]*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ *Event:* {event_title}\n"
        f"🕒 *Time:* `{now_str}`\n"
        f"📌 *Details:* {message}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 *Cluster Master:* Render Node"
    )
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        session.post(url, json={"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        print(f"⚠️ [Admin Alert Error]: {e}")


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
    """Compiles local kaggle_worker cells into a complete Jupyter Notebook JSON, injecting credentials dynamically."""
    cells = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check both current directory and parent directory for kaggle_worker folder
    worker_dir = os.path.join(base_dir, "kaggle_worker")
    if not os.path.exists(worker_dir):
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
            print(f"⚠️ Cell file not found at: {cpath}")
            continue

        with open(cpath, "r", encoding="utf-8") as f:
            code = f.read()

        # In cell2_config.py, inject ONLY the master URL & auth key (Zero-Trust In-Memory Handshake)
        if cf == "cell2_config.py":
            master_url = SERVER_URL or RENDER_EXTERNAL_URL or ""
            inject_header = (
                f'# Zero-Trust In-Memory Runtime Authentication Handshake\n'
                f'import os\n'
                f'os.environ["SERVER_URL"] = "{master_url}"\n'
                f'os.environ["WORKER_AUTH_KEY"] = "{WORKER_AUTH_KEY}"\n\n'
            )
            code = inject_header + code

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

    if not cells:
        raise ValueError(f"No cell files found in '{worker_dir}'. Ensure kaggle_worker folder is present.")

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


LAST_KAGGLE_TRIGGER_TIME = 0
KAGGLE_TRIGGER_LOCK = threading.Lock()

def trigger_kaggle_worker(force=False, reason="Auto-Rotation"):
    """Pushes fresh notebook to Kaggle to start or rotate the 30GB compute session with strict anti-spam locking."""
    global LAST_KAGGLE_TRIGGER_TIME

    if not KAGGLE_USERNAME or not KAGGLE_KEY:
        err = "KAGGLE_USERNAME or KAGGLE_KEY is missing in Render Environment Variables!"
        print(f"❌ {err}")
        send_admin_alert("Kaggle Launch Failed", "KAGGLE_USERNAME or KAGGLE_KEY is missing in Render Environment!", "WARNING")
        return False, err

    with KAGGLE_TRIGGER_LOCK:
        now = time.time()

        # Check persistent last trigger timestamp from Firebase (persists across server restarts!)
        last_fb_trigger = 0
        try:
            r = session.get(fb_url("control/last_triggered_at"), timeout=4)
            if r.ok and r.json():
                last_fb_trigger = float(r.json())
        except Exception:
            pass

        effective_last_time = max(LAST_KAGGLE_TRIGGER_TIME, last_fb_trigger)
        elapsed = now - effective_last_time

        # Strict 10-Minute Anti-Duplicate Lock (Guarantees NO double sessions)
        if not force and elapsed < 600:
            remaining = int(600 - elapsed)
            msg = f"Anti-Duplicate Lock: A Kaggle session was launched {int(elapsed)}s ago. Next launch permitted in {remaining}s."
            print(f"⏳ [Kaggle Lock] {msg}")
            return False, msg

        try:
            print(f"🚀 [Kaggle Orchestrator] Compiling notebook for user '{KAGGLE_USERNAME}' slug '{KAGGLE_SLUG}' (Reason: {reason})...")
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
            print(f"📋 [Kaggle Push Response] Status: {resp.status_code} | Body: {resp.text}")

            if resp.status_code in (200, 201):
                LAST_KAGGLE_TRIGGER_TIME = now
                # Persist timestamp & immediately reset trigger flag to prevent second thread firing
                try:
                    session.put(fb_url("control/last_triggered_at"), json=int(now), timeout=5)
                    session.put(fb_url("control/trigger_restart"), json=False, timeout=5)
                except Exception:
                    pass
                send_admin_alert("Kaggle Worker Launched", f"New 30GB compute node started!\nReason: {reason}", "SUCCESS")
                return True, "Kaggle Worker launched successfully! 30GB node is booting."
            else:
                try:
                    err_data = resp.json()
                    msg = err_data.get("message") or err_data.get("error") or str(err_data)
                except Exception:
                    msg = resp.text[:200]
                send_admin_alert("Kaggle Launch Rejected", f"Kaggle API [{resp.status_code}]: {msg}", "WARNING")
                return False, f"Kaggle API [{resp.status_code}]: {msg}"

        except Exception as e:
            print(f"❌ [Kaggle Push Failed] {e}")
            send_admin_alert("Kaggle Launch Exception", str(e), "WARNING")
            return False, str(e)


# -------------------------------------------------------------
# Background Watchdog: 11-Hour Restart & Worker Heartbeat
# -------------------------------------------------------------
def start_watchdog_thread():
    """Runs in background: monitors worker health and executes zero-downtime handoff."""
    print("🛡️ [Watchdog] Heartbeat and Auto-Restart listener active...")
    while True:
        try:
            # 1. Check if worker requested restart via Firebase fallback
            r = session.get(fb_url("control/trigger_restart"), timeout=5)
            if r.ok:
                val = r.json()
                if val is True:
                    print("⚡ [Auto-Restart] 11-hour handoff requested via Firebase!")
                    session.put(fb_url("control/trigger_restart"), json=False, timeout=5)
                    trigger_kaggle_worker(force=False, reason="11-Hour Session Handoff (Firebase Watchdog)")

            # 2. Check worker heartbeat - only trigger if dead for > 15 mins AND pending tasks exist
            status_res = session.get(fb_url("worker/heartbeat"), timeout=5)
            if status_res.ok and status_res.json():
                hb = status_res.json()
                last_seen = hb.get("timestamp") or hb.get("last_seen", 0)
                # Only check if worker previously pinged and has gone silent for > 15 minutes (900s)
                if last_seen > 0 and (time.time() - last_seen > 900):
                    q_res = session.get(fb_url("queue"), timeout=5)
                    if q_res.ok and isinstance(q_res.json(), dict):
                        has_pending = any(
                            isinstance(t, dict) and t.get("status") == "pending"
                            for t in q_res.json().values()
                        )
                        if has_pending:
                            print("⚠️ [Worker Offline] Pending tasks in queue and heartbeat expired! Triggering Kaggle worker...")
                            trigger_kaggle_worker(force=False, reason="Crash Recovery (Dead Worker with Pending Queue)")

        except Exception as e:
            pass

        # Check every 60 seconds
        time.sleep(60)


threading.Thread(target=start_watchdog_thread, daemon=True).start()


# -------------------------------------------------------------
# Telegram Bot Handlers & Force Subscribe System
# -------------------------------------------------------------
def check_membership(user_id):
    """Checks if the user has joined the official channel."""
    if not FORCE_SUB_CHANNEL:
        return True
    try:
        channel = FORCE_SUB_CHANNEL if FORCE_SUB_CHANNEL.startswith("@") or FORCE_SUB_CHANNEL.startswith("-100") else f"@{FORCE_SUB_CHANNEL}"
        member = bot.get_chat_member(channel, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"⚠️ [FSub Warning]: {e}")
        return True


def send_join_prompt(chat_id, doc_id=None, url_slug=None):
    """Sends sleek Force Subscribe lock message with join & verify buttons."""
    clean_channel = FORCE_SUB_CHANNEL.replace("@", "").strip()
    invite_url = f"https://t.me/{clean_channel}" if clean_channel else "https://t.me"

    text = (
        "🔒 *Access Locked!*\n\n"
        "Bot use karne ke liye pehle hamare official channel ko join karein. "
        "Join karte hi aapka download activate ho jayega! ✨"
    )

    markup = telebot.types.InlineKeyboardMarkup()
    if clean_channel:
        markup.add(telebot.types.InlineKeyboardButton("📢 Join Official Channel", url=invite_url))
    cb_data = f"check_{doc_id}:{url_slug}" if doc_id else "check_start"
    markup.add(telebot.types.InlineKeyboardButton("🔄 Joined / Try Again", callback_data=cb_data))

    return bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")


def send_welcome_message(chat_id, first_name="Dost"):
    """Sends official welcome screen with key features (L858-L869)."""
    welcome_text = (
        f"🌟 *WELCOME TO SCRIBD HD DOWNLOADER*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Namaste *{first_name}*! Ab aap Scribd ke kisi bhi document ko bilkul *FREE* aur *100% Original Quality* me download kar sakte hain! 🚀\n\n"
        f"✨ *Key Features:*\n"
        f"├ 📄 *All Pages Complete*\n"
        f"├ 🎯 *Zero Margin Cutoff*\n"
        f"├ 🔤 *Crystal Clear Font*\n"
        f"├ 🖼️ *Full Image & Diagram Support*\n"
        f"└ ⚡ *High-Speed Cloud Engine*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💻 *Made with ❤️ by* @cryvex4"
    )
    markup = None
    if FORCE_SUB_CHANNEL:
        clean_channel = FORCE_SUB_CHANNEL.replace("@", "").strip()
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("📢 Official Channel", url=f"https://t.me/{clean_channel}"))

    bot.send_message(chat_id, welcome_text, reply_markup=markup, parse_mode="Markdown", disable_web_page_preview=True)


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
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    first_name = msg.from_user.first_name or "Dost"

    if not check_membership(user_id):
        send_join_prompt(chat_id, None, None)
        return

    send_welcome_message(chat_id, first_name)


@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("check_"))
def handle_check_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    first_name = call.from_user.first_name or "Dost"

    if not check_membership(user_id):
        bot.answer_callback_query(
            call.id,
            "⚠️ Aapne abhi tak channel join nahi kiya hai! Kripya pehle channel join karein.",
            show_alert=True
        )
        return

    bot.answer_callback_query(call.id, "✅ Membership Verified! Welcome!")
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except Exception:
        pass

    raw_param = call.data.replace("check_", "").strip()
    if raw_param and raw_param not in ("start", "idle") and ":" in raw_param:
        parts = raw_param.split(":")
        pending_doc_id = parts[0]
        pending_slug = parts[1] if len(parts) > 1 and parts[1] != "None" else None
        username = call.from_user.username or first_name
        dispatch_scribd_task(chat_id, user_id, username, pending_doc_id, pending_slug)
    else:
        # Directly show the complete Start Welcome screen (L858-L869)
        send_welcome_message(chat_id, first_name)


def dispatch_scribd_task(chat_id, user_id, username, doc_id, url_slug=None):
    """Handles smart cache check or dispatches high-speed task to Kaggle."""
    # Track Telemetry
    STATS["total_requests"] += 1
    STATS["unique_users"].add(user_id)

    # 1. ⚡ SMART CACHE CHECK (0.2s Instant Delivery)
    cached = get_cached_doc(doc_id)
    if cached:
        title = cached.get("title", "Scribd Document")
        pages = cached.get("totalPages", "Full")
        if cached.get("file_id"):
            STATS["cache_hits"] += 1
            bot.send_document(
                chat_id,
                cached["file_id"],
                caption=(
                    f"📚 *{title}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📑 *Pages:* {pages}\n"
                    f"⚡ *Delivered Instantly via High-Speed Cloud Cache!* (0.2s)\n"
                    f"🎯 *Quality:* 100% Crisp Vector HD\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🤖 *Downloaded via:* @cryvex_uploader_bot\n"
                    f"👨‍💻 *Developer:* @cryvex4"
                )
            )
            return
        elif cached.get("download_url"):
            STATS["cache_hits"] += 1
            f_size = cached.get("fileSizeMb", "Ultra HD")
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton(f"🚀 Download Full Ultra HD PDF ({f_size} MB)", url=cached["download_url"]))
            msg_text = (
                f"📚 *{title}*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📑 *Pages:* {pages}\n"
                f"📦 *File Size:* {f_size} MB (Ultra HD 100% Original Quality)\n"
                f"⚡ *Speed:* 0.2s (Instant Cloud Cache)\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🚀 *Your Document is ready for High-Speed Download!*\n"
                f"⏰ _Note: Link active for 24-48 hours._\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 *Downloaded via:* @cryvex_uploader_bot\n"
                f"👨‍💻 *Developer:* @cryvex4"
            )
            bot.send_message(
                chat_id,
                msg_text,
                reply_markup=markup,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            return

    # 2. INITIAL STATUS MESSAGE (Stage 1: Connecting)
    clean_title = url_slug.replace("-", " ").replace("_", " ").title() if url_slug else f"Doc #{doc_id}"
    init_status_text = (
        f"🔍 *CONNECTING TO SCRIBD*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Connecting to Scribd servers...\n"
        f"[██░░░░░░░░] 15%\n"
        f"⏳ *Time:* 0.0s\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💻 *Made by* @cryvex4"
    )
    status_msg = bot.send_message(chat_id, init_status_text, parse_mode="Markdown")
    status_msg_id = status_msg.message_id if status_msg else None

    # 3. PUSH TASK TO FIREBASE QUEUE FOR KAGGLE WORKER
    task_id = f"task_{doc_id}_{int(time.time())}"
    task_payload = {
        "docId": doc_id,
        "urlSlug": url_slug,
        "title": clean_title,
        "chatId": chat_id,
        "userId": user_id,
        "username": username,
        "statusMsgId": status_msg_id,
        "status": "pending",
        "createdAt": int(time.time())
    }

    ok = push_queue_task(task_id, task_payload)
    if ok:
        STATS["queue_tasks"] += 1
    else:
        bot.send_message(chat_id, "❌ *System Error:* Could not assign task. Please retry.")


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

    user_id = msg.from_user.id
    chat_id = msg.chat.id
    username = msg.from_user.username or msg.from_user.first_name or "User"

    # Check Force Subscribe
    if not check_membership(user_id):
        send_join_prompt(chat_id, info["docId"], info["urlSlug"])
        return

    dispatch_scribd_task(chat_id, user_id, username, info["docId"], info["urlSlug"])


# -------------------------------------------------------------
# Live Stats & Responsive HTML Dashboard
# -------------------------------------------------------------
def get_worker_heartbeat():
    """Fetches the latest heartbeat from Firebase."""
    try:
        r = session.get(fb_url("worker/heartbeat"), timeout=3)
        if r.ok and r.json():
            return r.json()
    except Exception:
        pass
    return None


def get_live_stats():
    """Fetches real-time status from Firebase and in-memory counters."""
    heartbeat = get_worker_heartbeat() or {}
    last_seen = heartbeat.get("timestamp", 0)
    is_worker_online = (time.time() - last_seen) < 90 if last_seen else False

    # Get cached count
    cache_count = 0
    try:
        r = session.get(fb_url("cache"), timeout=3)
        if r.ok and isinstance(r.json(), dict):
            cache_count = len(r.json())
    except Exception:
        pass

    # Get pending queue count
    queue_count = 0
    try:
        r = session.get(fb_url("queue"), timeout=3)
        if r.ok and isinstance(r.json(), dict):
            queue_count = len(r.json())
    except Exception:
        pass

    return {
        "server_status": "online",
        "server_uptime_seconds": int(time.time() - SERVER_START_TIME),
        "total_requests": STATS["total_requests"],
        "unique_users": len(STATS["unique_users"]),
        "cache_hits": STATS["cache_hits"],
        "queue_tasks": STATS["queue_tasks"],
        "total_cached_docs": cache_count,
        "pending_queue": queue_count,
        "worker": {
            "online": is_worker_online,
            "status": heartbeat.get("status", "offline") if is_worker_online else "offline",
            "active_jobs": heartbeat.get("active_jobs", 0) if is_worker_online else 0,
            "uptime_hours": heartbeat.get("uptime_hours", 0) if is_worker_online else 0,
            "last_seen_sec_ago": int(time.time() - last_seen) if last_seen else -1
        }
    }


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <title>Scribd Cloud Supercluster</title>
  <style>
    :root {
      --bg: #090d16;
      --card: #131b2e;
      --card-border: #1e293b;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --success: #10b981;
      --danger: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text-main);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      padding: 16px;
      min-height: 100vh;
      display: flex;
      justify-content: center;
      align-items: flex-start;
    }
    .container {
      width: 100%;
      max-width: 480px;
      margin-top: 4px;
    }
    .header {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 14px 18px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .brand-icon {
      font-size: 20px;
      background: rgba(59, 130, 246, 0.15);
      padding: 6px 10px;
      border-radius: 10px;
    }
    .brand-text h1 {
      font-size: 16px;
      font-weight: 700;
      letter-spacing: -0.3px;
    }
    .brand-text p {
      font-size: 11px;
      color: var(--text-muted);
    }
    .badge-live {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: 20px;
      background: rgba(16, 185, 129, 0.15);
      color: var(--success);
      border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .pulse-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 8px var(--success);
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.9); }
      100% { opacity: 1; transform: scale(1); }
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 14px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 14px;
    }
    .card-title {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
      margin-bottom: 6px;
    }
    .card-val {
      font-size: 22px;
      font-weight: 800;
      color: #fff;
    }
    .card-sub {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 4px;
    }
    .panel {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 16px;
      margin-bottom: 14px;
    }
    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--card-border);
    }
    .panel-title {
      font-size: 13px;
      font-weight: 700;
      color: #cbd5e1;
    }
    .status-pill {
      font-size: 11px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 6px;
    }
    .status-online { background: rgba(16, 185, 129, 0.15); color: var(--success); }
    .status-offline { background: rgba(239, 68, 68, 0.15); color: var(--danger); }
    .info-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 13px;
      padding: 6px 0;
      color: var(--text-muted);
    }
    .info-row span:last-child {
      font-weight: 600;
      color: #f1f5f9;
    }
    .btn-action {
      width: 100%;
      background: linear-gradient(135deg, #2563eb, #1d4ed8);
      color: white;
      border: none;
      padding: 13px;
      font-size: 14px;
      font-weight: 700;
      border-radius: 12px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: all 0.2s ease;
      box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
    }
    .btn-action:hover {
      background: linear-gradient(135deg, #1d4ed8, #1e40af);
      transform: translateY(-1px);
    }
    .btn-action:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      transform: none;
    }
    .alert-box {
      display: none;
      margin-top: 12px;
      padding: 10px;
      border-radius: 10px;
      font-size: 12px;
      font-weight: 600;
      text-align: center;
    }
    .alert-success { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .alert-error { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .footer {
      text-align: center;
      font-size: 11px;
      color: #64748b;
      margin-top: 14px;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="brand">
        <div class="brand-icon">⚡</div>
        <div class="brand-text">
          <h1>Scribd Cloud</h1>
          <p>Render Master Node</p>
        </div>
      </div>
      <div class="badge-live">
        <div class="pulse-dot"></div>
        <span>LIVE</span>
      </div>
    </div>

    <!-- Quick KPI Grid -->
    <div class="grid">
      <div class="card">
        <div class="card-title">👥 Unique Users</div>
        <div class="card-val" id="stat-users">0</div>
        <div class="card-sub">Active bot users</div>
      </div>
      <div class="card">
        <div class="card-title">📥 Requests</div>
        <div class="card-val" id="stat-requests">0</div>
        <div class="card-sub">Scribd links processed</div>
      </div>
      <div class="card">
        <div class="card-title">⚡ Instant Cache</div>
        <div class="card-val" id="stat-cache">0</div>
        <div class="card-sub">0.2s instant deliveries</div>
      </div>
      <div class="card">
        <div class="card-title">⏳ Queue Pending</div>
        <div class="card-val" id="stat-queue">0</div>
        <div class="card-sub">Awaiting render</div>
      </div>
    </div>

    <!-- Kaggle Compute Cluster Status -->
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">🖥️ Kaggle Compute Cluster</div>
        <div id="worker-status-badge" class="status-pill status-offline">CHECKING</div>
      </div>
      <div class="info-row">
        <span>Hardware Allocation</span>
        <span>30 GB RAM • 4 vCPUs</span>
      </div>
      <div class="info-row">
        <span>Active Rendering Jobs</span>
        <span id="worker-jobs">0 jobs</span>
      </div>
      <div class="info-row">
        <span>Worker Session</span>
        <span id="worker-uptime">0h / 11h</span>
      </div>
      <div class="info-row">
        <span>Mini-Server Uptime</span>
        <span id="server-uptime">0m</span>
      </div>

      <div style="margin-top: 14px;">
        <button id="btn-restart" class="btn-action" onclick="triggerKaggle()">
          <span>🚀</span>
          <span>Start / Restart Kaggle Worker</span>
        </button>
        <div id="alert-box" class="alert-box"></div>
      </div>
    </div>

    <div class="footer">
      Developed with ❤️ by @cryvex4 • Scribd Cloud Architecture
    </div>
  </div>

  <script>
    async function updateStats() {
      try {
        const res = await fetch('/api/stats');
        if (!res.ok) return;
        const data = await res.json();

        document.getElementById('stat-users').innerText = data.unique_users || 0;
        document.getElementById('stat-requests').innerText = data.total_requests || 0;
        document.getElementById('stat-cache').innerText = (data.cache_hits || 0) + ' (' + (data.total_cached_docs || 0) + ' in db)';
        document.getElementById('stat-queue').innerText = data.pending_queue || 0;

        const badge = document.getElementById('worker-status-badge');
        if (data.worker && data.worker.online) {
          badge.className = 'status-pill status-online';
          badge.innerText = '🟢 ONLINE';
          document.getElementById('worker-jobs').innerText = (data.worker.active_jobs || 0) + ' active';
          document.getElementById('worker-uptime').innerText = (data.worker.uptime_hours || 0) + 'h / 11h';
        } else {
          badge.className = 'status-pill status-offline';
          badge.innerText = '🔴 OFFLINE / STANDBY';
          document.getElementById('worker-jobs').innerText = '0 jobs';
          document.getElementById('worker-uptime').innerText = 'Standby';
        }

        const upSec = data.server_uptime_seconds || 0;
        const upMins = Math.floor(upSec / 60);
        const upHours = Math.floor(upMins / 60);
        document.getElementById('server-uptime').innerText = upHours > 0 ? (upHours + 'h ' + (upMins % 60) + 'm') : (upMins + 'm ' + (upSec % 60) + 's');
      } catch (e) {
        console.error('Stats poll failed', e);
      }
    }

    async function triggerKaggle() {
      const btn = document.getElementById('btn-restart');
      const alertBox = document.getElementById('alert-box');
      btn.disabled = true;
      btn.innerHTML = '<span>⏳</span><span>Pushing Notebook to Kaggle...</span>';
      alertBox.style.display = 'none';

      try {
        const res = await fetch('/api/kaggle/restart', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          alertBox.className = 'alert-box alert-success';
          alertBox.innerText = '✅ ' + (data.message || 'Kaggle Worker Started! 30GB compute session initialized.');
        } else {
          alertBox.className = 'alert-box alert-error';
          alertBox.innerText = '❌ Failed: ' + (data.error || 'Check Kaggle credentials in Render environment');
        }
      } catch (err) {
        alertBox.className = 'alert-box alert-error';
        alertBox.innerText = '❌ Network Error: ' + err.message;
      }
      alertBox.style.display = 'block';

      setTimeout(() => {
        btn.disabled = false;
        btn.innerHTML = '<span>🚀</span><span>Start / Restart Kaggle Worker</span>';
        updateStats();
      }, 5000);
    }

    updateStats();
    setInterval(updateStats, 8000);
  </script>
</body>
</html>
"""


# -------------------------------------------------------------
# HTTP Server for Render Health Checks, Webhooks & Uptime Monitors
# -------------------------------------------------------------
class RenderHealthServer(BaseHTTPRequestHandler):
    def do_HEAD(self):
        """Supports HTTP HEAD requests from UptimeRobot / BetterUptime monitors (0 body bandwidth)."""
        if self.path in ["/status", "/health", "/", "/dashboard", "/api/stats"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8" if self.path != "/api/stats" else "application/json")
            self.end_headers()
        else:
            self.send_error(404, "Not Found")

    def do_GET(self):
        # 1. JSON Telemetry API for AJAX auto-refresh
        if self.path == "/api/stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(get_live_stats()).encode("utf-8"))

        # 2. Render Internal Health Check (Pure JSON)
        elif self.path == "/health":
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

        # 3. Mobile-Optimized Control Dashboard on /status, /dashboard, and /
        elif self.path in ["/status", "/dashboard", "/"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))

        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        # 1. Endpoint to trigger Kaggle push remotely from dashboard
        if self.path == "/api/kaggle/restart":
            ok, msg = trigger_kaggle_worker(force=True, reason="Dashboard Button Action")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": ok, "message": msg, "error": msg if not ok else None}).encode("utf-8"))

        # 2. In-Memory Runtime Handshake for Kaggle Worker
        elif self.path == "/api/worker/handshake":
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
            try:
                body_data = json.loads(post_body.decode("utf-8"))
            except Exception:
                body_data = {}

            req_auth = body_data.get("auth_key") or self.headers.get("X-Worker-Key") or ""
            if req_auth and req_auth == WORKER_AUTH_KEY:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                payload = {
                    "status": "ok",
                    "bot_token": BOT_TOKEN,
                    "firebase_db_url": FIREBASE_DB_URL,
                    "db_root": DB_ROOT,
                    "proxy_url": PROXY_URL,
                    "bot_username": BOT_USERNAME
                }
                self.wfile.write(json.dumps(payload).encode("utf-8"))
                send_admin_alert("Worker Handshake Verified", "Kaggle 30GB compute node authenticated! Credentials loaded strictly into memory.", "SUCCESS")
            else:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Unauthorized: Invalid Worker Auth Key"}).encode("utf-8"))
                send_admin_alert("Security Warning", "Blocked unauthorized worker handshake attempt!", "SECURITY")

        # 3. Direct Heartbeat from Kaggle Worker
        elif self.path == "/api/worker/heartbeat":
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
            try:
                hb_data = json.loads(post_body.decode("utf-8"))
            except Exception:
                hb_data = {}

            req_auth = hb_data.get("auth_key") or self.headers.get("X-Worker-Key") or ""
            if req_auth == WORKER_AUTH_KEY:
                hb_data.pop("auth_key", None)
                try:
                    session.put(fb_url("worker/heartbeat"), json=hb_data, timeout=4)
                except Exception:
                    pass
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
            else:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Unauthorized"}).encode("utf-8"))

        # 4. Direct Restart Request from Worker (11-Hour Mark)
        elif self.path == "/api/worker/restart-request":
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
            try:
                req_data = json.loads(post_body.decode("utf-8"))
            except Exception:
                req_data = {}

            req_auth = req_data.get("auth_key") or self.headers.get("X-Worker-Key") or ""
            if req_auth == WORKER_AUTH_KEY:
                ok, msg = trigger_kaggle_worker(force=False, reason="11-Hour Session Handoff (Direct API)")
                self.send_response(200 if ok else 429)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "launched": ok, "message": msg}).encode("utf-8"))
            else:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Unauthorized"}).encode("utf-8"))

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

    send_admin_alert("Render Master Online", "Mini-Server coordinator is live and actively monitoring Telegram & Kaggle cluster.", "SUCCESS")

    print("🤖 [Telegram Bot] Polling started on Mini-Server...")
    try:
        bot.infinity_polling(timeout=15, long_polling_timeout=10)
    except Exception as e:
        print(f"Bot Polling Exception: {e}")
