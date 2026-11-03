# =============================================================================
# CELL 5 — Distributed Task Consumer & Worker Engine
# =============================================================================
import os
import sys
import time
import json
import math
import subprocess
import threading
import concurrent.futures
import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from cell2_config import (
        FIREBASE_DB_URL, DB_ROOT, BOT_TOKEN, PROXY_URL,
        WORKING_DIR, DOWNLOAD_DIR, MAX_RUNTIME_SECONDS,
        WORKER_SESSION_START, MAX_PARALLEL_RENDERS,
        fb_get, fb_put, fb_delete
    )
except ImportError:
    pass

try:
    from cell3_compressor import compress_pdf_lossless, get_file_size_mb
except ImportError:
    pass

def get_file_size_mb(filepath):
    try:
        if os.path.exists(filepath):
            return round(os.path.getsize(filepath) / (1024 * 1024), 2)
    except Exception:
        pass
    return 0.0

print("🚀 [CELL 5] Initializing High-Performance Kaggle Worker Loop...")

# In-memory registry of tasks currently being rendered
ACTIVE_TASKS = set()
ACTIVE_TASKS_LOCK = threading.Lock()
STOP_REQUESTED = False


def send_telegram_msg(chat_id, text, reply_to_message_id=None):
    """Sends a clean status message directly to the Telegram user."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.ok:
            return r.json().get("result", {}).get("message_id")
    except Exception as e:
        print(f"⚠️ [Telegram Error] send_message failed: {e}")
    return None


def get_progress_bar(percent):
    """Generates sleek Unicode progress bar: [████░░░░░░]."""
    total = 10
    clamped = max(0, min(100, int(percent or 0)))
    filled = int(round((clamped / 100.0) * total))
    return "█" * filled + "░" * (total - filled)


class StatusTracker:
    """Manages real-time live status updates on Telegram with rate-limiting & auto-cleanup."""
    def __init__(self, chat_id, status_msg_id, bot_token):
        self.chat_id = chat_id
        self.status_msg_id = status_msg_id
        self.bot_token = bot_token
        self.start_time = time.time()
        self.last_update_time = 0
        self.last_text = ""

    def update(self, stage, percent, text, force=False):
        if not self.status_msg_id or not self.chat_id:
            return

        now = time.time()
        # Throttling: minimum 2.5 seconds between Telegram message edits
        if not force and (now - self.last_update_time < 2.5):
            return

        elapsed = round(now - self.start_time, 1)
        bar = get_progress_bar(percent)

        if stage == "connecting":
            header = "🔍 *CONNECTING TO SCRIBD*"
        elif stage == "rendering":
            header = "⚡ *RENDERING HD PAGES*"
        elif stage == "compressing":
            header = "🗜️ *OPTIMIZING PDF*"
        elif stage == "uploading":
            header = "📤 *UPLOADING TO TELEGRAM*"
        else:
            header = "⚡ *SCRIBD HD DOWNLOADER*"

        full_message = (
            f"{header}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{text}\n"
            f"[{bar}] {int(percent)}%\n"
            f"⏳ *Time:* {elapsed}s\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 *Made by* @cryvex4"
        )

        if full_message == self.last_text:
            return

        self.last_text = full_message
        self.last_update_time = now

        url = f"https://api.telegram.org/bot{self.bot_token}/editMessageText"
        payload = {
            "chat_id": self.chat_id,
            "message_id": self.status_msg_id,
            "text": full_message,
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception:
            pass

    def delete(self):
        """Deletes the transient progress status message once document is delivered."""
        if not self.status_msg_id or not self.chat_id:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/deleteMessage"
        try:
            requests.post(url, json={"chat_id": self.chat_id, "message_id": self.status_msg_id}, timeout=5)
        except Exception:
            pass


def send_telegram_button(chat_id, text, download_url, btn_text):
    """Sends a message with an interactive download button on Telegram."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": btn_text, "url": download_url}
                ]
            ]
        }
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.ok
    except Exception as e:
        print(f"⚠️ [Telegram Button Error]: {e}")
    return False


def upload_to_temp_cloud(filepath):
    """Uploads large (>50MB) Ultra HD PDF to high-speed temporary cloud (GoFile / Filebin)."""
    filename = os.path.basename(filepath)
    size_mb = get_file_size_mb(filepath)
    print(f"☁️ Uploading large Ultra HD file '{filename}' ({size_mb} MB) to Temporary Cloud...")

    # Provider 1: GoFile.io (High speed, unlimited size, free)
    try:
        s_res = requests.get("https://api.gofile.io/servers", timeout=10).json()
        if s_res.get("status") == "ok" and s_res.get("data", {}).get("servers"):
            server = s_res["data"]["servers"][0]["name"]
            up_url = f"https://{server}.gofile.io/contents/uploadfile"
            with open(filepath, "rb") as f:
                r = requests.post(up_url, files={"file": (filename, f)}, timeout=600)
                if r.ok and r.json().get("status") == "ok":
                    dpage = r.json().get("data", {}).get("downloadPage")
                    if dpage:
                        print(f"✅ [GoFile Upload Success]: {dpage}")
                        return dpage
    except Exception as e:
        print(f"⚠️ GoFile upload notice: {e}")

    # Provider 2: Filebin.net Fallback
    try:
        bin_id = f"scribd_{int(time.time())}"
        with open(filepath, "rb") as f:
            r = requests.post(f"https://filebin.net/{bin_id}/{filename}", data=f, timeout=600)
            if r.status_code in (200, 201):
                url = f"https://filebin.net/{bin_id}/{filename}"
                print(f"✅ [Filebin Upload Success]: {url}")
                return url
    except Exception as e:
        print(f"⚠️ Filebin upload notice: {e}")

    return None


def send_telegram_doc(chat_id, pdf_path, caption, reply_markup=None):
    """Uploads document directly from Kaggle compute to Telegram (0% Render bandwidth)."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    filename = os.path.basename(pdf_path)
    try:
        with open(pdf_path, "rb") as f:
            files = {"document": (filename, f, "application/pdf")}
            data = {
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": "Markdown"
            }
            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup) if isinstance(reply_markup, dict) else reply_markup
            print(f"📤 Uploading '{filename}' ({get_file_size_mb(pdf_path)} MB) directly to Telegram...")
            r = requests.post(url, data=data, files=files, timeout=300)
            if r.ok:
                res_data = r.json()
                file_id = res_data.get("result", {}).get("document", {}).get("file_id")
                return file_id
            else:
                print(f"❌ Telegram API sendDocument returned: {r.text}")
    except Exception as e:
        print(f"❌ [Telegram Upload Exception]: {e}")
    return None


def execute_downloader_process(doc_id, output_path, start_page=1, end_page=None, on_progress=None):
    """Invokes Node Puppeteer downloader with real-time stdout streaming and DOM pruning."""
    downloader_script = os.path.join(WORKING_DIR, "downloader.js")
    if not os.path.exists(downloader_script):
        # Fallback to local script in same folder
        candidate = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cell4_downloader.js")
        if os.path.exists(candidate):
            downloader_script = candidate

    cmd = [
        "node",
        downloader_script,
        str(doc_id),
        output_path,
        str(start_page),
        str(end_page or ""),
        PROXY_URL or ""
    ]

    print(f"▶️ Launching: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        cwd=WORKING_DIR,
        bufsize=1
    )

    result_data = None

    # Stream stdout line by line in real time
    for line in iter(proc.stdout.readline, ""):
        line = line.strip()
        if not line:
            continue
        if line.startswith("__FINAL_RESULT__"):
            try:
                result_data = json.loads(line.replace("__FINAL_RESULT__", "").strip())
            except Exception:
                pass
        elif line.startswith("{") and line.endswith("}"):
            try:
                prog = json.loads(line)
                if on_progress and callable(on_progress):
                    on_progress(prog)
            except Exception:
                print(f"[Node Output] {line}")
        else:
            print(f"[Node Output] {line}")

    proc.stdout.close()
    stderr_out = proc.stderr.read()
    proc.stderr.close()
    proc.wait()

    if proc.returncode != 0 or not result_data:
        err_msg = stderr_out.strip() or "Unknown render error"
        for line in stderr_out.splitlines():
            if line.startswith("__FINAL_ERROR__"):
                try:
                    err_obj = json.loads(line.replace("__FINAL_ERROR__", "").strip())
                    err_msg = err_obj.get("error", err_msg)
                except Exception:
                    pass
        raise RuntimeError(err_msg)

    return result_data


def process_single_task(task_id, task_data):
    """Processes a single document render task from end-to-end with real-time UI tracking."""
    doc_id = task_data.get("docId")
    chat_id = task_data.get("chatId")
    username = task_data.get("username", "User")
    status_msg_id = task_data.get("statusMsgId")

    print(f"\n⚡ [START TASK] ID: {task_id} | Doc: {doc_id} | User: {username}")

    # Mark as processing in Firebase
    fb_put(f"queue/{task_id}/status", "processing")
    fb_put(f"queue/{task_id}/started_at", int(time.time()))

    # Initialize Live Status Tracker for Telegram UI
    if not status_msg_id:
        status_msg_id = send_telegram_msg(
            chat_id,
            f"🔍 *CONNECTING TO SCRIBD*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Allocating 30GB Cloud Node...\n"
            f"[██░░░░░░░░] 20%\n"
            f"⏳ *Time:* 0.0s\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 *Made by* @cryvex4"
        )
    tracker = StatusTracker(chat_id, status_msg_id, BOT_TOKEN)

    raw_pdf_path = os.path.join(DOWNLOAD_DIR, f"scribd_{doc_id}_raw.pdf")
    compressed_pdf_path = os.path.join(DOWNLOAD_DIR, f"scribd_{doc_id}_compressed.pdf")

    try:
        def on_render_progress(prog):
            stage = prog.get("stage", "rendering")
            pct = prog.get("percent", 0)
            text = prog.get("text", "")
            tracker.update(stage, pct, text)

        # Step 1: Render via Puppeteer with Real-time Progress
        render_res = execute_downloader_process(doc_id, raw_pdf_path, on_progress=on_render_progress)
        title = render_res.get("title", f"Scribd Document {doc_id}")
        page_count = render_res.get("pageCount", "Full")
        raw_size = get_file_size_mb(raw_pdf_path)

        print(f"✅ Rendered raw PDF for {doc_id}: {page_count} pages, {raw_size} MB")

        # Step 2: Lossless Ghostscript Compression (ILovePDF ebook preset)
        tracker.update("compressing", 88, f"Optimizing PDF ({raw_size} MB)...", force=True)
        comp_res = compress_pdf_lossless(raw_pdf_path, compressed_pdf_path, preset="/ebook")
        final_pdf_path = comp_res["final_path"]
        final_size = comp_res["final_size_mb"]

        print(f"🗜️ Ghostscript Finished: {raw_size} MB ➔ {final_size} MB ({comp_res['reduction_pct']}% reduction)")

        total_elapsed = round(time.time() - tracker.start_time, 1)

        # Step 3: Direct Telegram vs High-Speed Cloud Link (No multi-parts!)
        if final_size > 49.0:
            tracker.update("uploading", 95, f"Uploading Ultra HD PDF to Cloud ({final_size} MB)...", force=True)
            print(f"📦 Large Document ({final_size} MB) > 49MB: Uploading single Ultra HD PDF to Cloud...")
            download_url = upload_to_temp_cloud(final_pdf_path)
            if not download_url:
                raise RuntimeError("Temporary cloud upload failed.")

            # Delete progress status message
            tracker.delete()

            msg_text = (
                f"📚 *{title}*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📑 *Pages:* {page_count}\n"
                f"📦 *File Size:* {final_size} MB (Ultra HD 100% Original Quality)\n"
                f"⚡ *Speed:* {total_elapsed}s\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🚀 *Your Document is ready for High-Speed Download!*\n"
                f"⏰ _Note: Link active for 24-48 hours._\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 *Downloaded via:* @cryvex_uploader_bot\n"
                f"👨‍💻 *Developer:* @cryvex4"
            )
            btn_title = f"🚀 Download Full Ultra HD PDF ({final_size} MB)"
            ok = send_telegram_button(chat_id, msg_text, download_url, btn_title)
            if ok:
                cache_payload = {
                    "download_url": download_url,
                    "title": title,
                    "totalPages": page_count,
                    "cachedAt": int(time.time()),
                    "fileSizeMb": final_size
                }
                fb_put(f"cache/{doc_id}", cache_payload)
                fb_delete(f"queue/{task_id}")
                print(f"🎉 [TASK COMPLETED] Doc {doc_id} delivered via Cloud Link successfully!")
            else:
                raise RuntimeError("Failed to send download button on Telegram.")

        else:
            tracker.update("uploading", 95, f"Uploading PDF to Telegram ({final_size} MB)...", force=True)
            caption = (
                f"📚 *{title}*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📑 *Pages:* {page_count}\n"
                f"📦 *File Size:* {final_size} MB\n"
                f"⚡ *Speed:* {total_elapsed}s\n"
                f"🎯 *Quality:* 100% Crisp Vector HD\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 *Downloaded via:* @cryvex_uploader_bot\n"
                f"👨‍💻 *Developer:* @cryvex4"
            )

            file_id = send_telegram_doc(chat_id, final_pdf_path, caption)

            # Delete progress status message
            tracker.delete()

            if file_id:
                # Step 5: Save Telegram file_id to Firebase Cloud Cache (0.2s instant for next user!)
                cache_payload = {
                    "file_id": file_id,
                    "title": title,
                    "totalPages": page_count,
                    "cachedAt": int(time.time()),
                    "fileSizeMb": final_size
                }
                fb_put(f"cache/{doc_id}", cache_payload)
                print(f"💾 Saved doc {doc_id} to Firebase Cloud Cache! (file_id: {file_id[:15]}...)")

                # Remove task from queue
                fb_delete(f"queue/{task_id}")
                print(f"🎉 [TASK COMPLETED] Doc {doc_id} delivered successfully!")
            else:
                raise RuntimeError("Telegram rejected file upload.")

    except Exception as e:
        err_str = str(e)
        print(f"❌ [TASK FAILED] {task_id}: {err_str}")
        tracker.delete()
        fb_put(f"queue/{task_id}/status", "failed")
        fb_put(f"queue/{task_id}/error", err_str)
        send_telegram_msg(
            chat_id,
            f"❌ *Render Failed for Doc ID:* `{doc_id}`\n\n"
            f"⚠️ *Reason:* {err_str[:200]}\n"
            f"Kripya dobara link bhej kar check karein."
        )

    finally:
        # Step 6: Cleanup ALL local temporary files for this document
        try:
            for fname in os.listdir(DOWNLOAD_DIR):
                if fname.startswith(f"scribd_{doc_id}"):
                    try:
                        os.unlink(os.path.join(DOWNLOAD_DIR, fname))
                    except Exception:
                        pass
        except Exception:
            pass

        with ACTIVE_TASKS_LOCK:
            ACTIVE_TASKS.discard(task_id)


def heartbeat_loop():
    """Background thread sending 30-second heartbeats and monitoring 11-hour handoff."""
    global STOP_REQUESTED
    print("💓 Heartbeat monitoring started...")
    while not STOP_REQUESTED:
        try:
            uptime = time.time() - WORKER_SESSION_START
            with ACTIVE_TASKS_LOCK:
                active_count = len(ACTIVE_TASKS)

            heartbeat_data = {
                "status": "online",
                "timestamp": int(time.time()),
                "active_jobs": active_count,
                "uptime_hours": round(uptime / 3600.0, 2),
                "ram_mb": 30000  # Kaggle provides 30GB RAM
            }

            # 1. Direct Heartbeat to Render Master (Zero-Trust)
            if SERVER_URL:
                try:
                    payload = dict(heartbeat_data)
                    payload["auth_key"] = WORKER_AUTH_KEY
                    requests.post(f"{SERVER_URL}/api/worker/heartbeat", json=payload, timeout=5)
                except Exception:
                    pass

            # 2. Sync to Firebase RTDB
            fb_put("worker/heartbeat", heartbeat_data)

            # ── 11-Hour Zero-Downtime Session Handoff Check ──
            if uptime >= MAX_RUNTIME_SECONDS:
                if active_count == 0:
                    print("⏰ [11-Hour Reached] No active rendering jobs! Initiating zero-downtime handoff...")
                    if SERVER_URL:
                        try:
                            requests.post(
                                f"{SERVER_URL}/api/worker/restart-request",
                                json={"auth_key": WORKER_AUTH_KEY, "reason": "11-Hour Session Handoff"},
                                timeout=5
                            )
                        except Exception:
                            pass
                    fb_put("control/trigger_restart", True)
                    time.sleep(10)
                    STOP_REQUESTED = True
                    print("🛑 Clean Kaggle session termination. Next session pushed by Mini-Server!")
                    break
                else:
                    print(f"⏳ [11-Hour Warning] {active_count} jobs still active. Waiting before handoff...")

        except Exception as e:
            print(f"⚠️ Heartbeat error: {e}")

        time.sleep(30)


def main_worker_loop():
    """Main consumer loop polling Firebase RTDB at safe, Spark-friendly intervals (15-20s)."""
    global STOP_REQUESTED
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL_RENDERS)

    # Start Heartbeat Thread
    hb_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    hb_thread.start()

    print(f"🚀 Kaggle Worker is LIVE! Max parallel renders: {MAX_PARALLEL_RENDERS}")
    print("💤 Safe polling interval: 15-20s (Consumes <15MB/month bandwidth on Firebase Spark Plan)")

    while not STOP_REQUESTED:
        try:
            # Check for pending tasks
            queue = fb_get("queue")
            if queue and isinstance(queue, dict):
                for task_id, task_data in queue.items():
                    if STOP_REQUESTED:
                        break

                    if not isinstance(task_data, dict):
                        continue

                    status = task_data.get("status")
                    if status == "pending":
                        with ACTIVE_TASKS_LOCK:
                            if task_id in ACTIVE_TASKS:
                                continue
                            if len(ACTIVE_TASKS) >= MAX_PARALLEL_RENDERS:
                                print(f"⚠️ Max concurrent renders ({MAX_PARALLEL_RENDERS}) reached. Queuing next cycle...")
                                break
                            ACTIVE_TASKS.add(task_id)

                        executor.submit(process_single_task, task_id, task_data)

            # Spark Plan Safety: Sleep 15s to maintain near-zero bandwidth
            time.sleep(15)

        except KeyboardInterrupt:
            print("\n👋 Worker stopping manually...")
            STOP_REQUESTED = True
            break
        except Exception as e:
            print(f"⚠️ Worker polling exception: {e}")
            time.sleep(20)

    executor.shutdown(wait=True)
    print("🏁 Kaggle Worker Stopped Gracefully.")


if __name__ == "__main__":
    main_worker_loop()
