# =============================================================================
# CELL 5 — Distributed Task Consumer & Worker Engine
# =============================================================================
import os
import sys
import time
import json
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


def send_telegram_doc(chat_id, pdf_path, caption):
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


def execute_downloader_process(doc_id, output_path, start_page=1, end_page=None):
    """Invokes Node Puppeteer downloader with DOM pruning and zero disk cache."""
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
        cwd=WORKING_DIR
    )

    stdout, stderr = proc.communicate()

    result_data = None
    for line in stdout.splitlines():
        if line.startswith("__FINAL_RESULT__"):
            try:
                result_data = json.loads(line.replace("__FINAL_RESULT__", "").strip())
            except Exception:
                pass

    if proc.returncode != 0 or not result_data:
        err_msg = stderr.strip() or stdout.strip() or "Unknown render error"
        for line in stderr.splitlines():
            if line.startswith("__FINAL_ERROR__"):
                try:
                    err_obj = json.loads(line.replace("__FINAL_ERROR__", "").strip())
                    err_msg = err_obj.get("error", err_msg)
                except Exception:
                    pass
        raise RuntimeError(err_msg)

    return result_data


def process_single_task(task_id, task_data):
    """Processes a single document render task from end-to-end."""
    doc_id = task_data.get("docId")
    chat_id = task_data.get("chatId")
    username = task_data.get("username", "User")

    print(f"\n⚡ [START TASK] ID: {task_id} | Doc: {doc_id} | User: {username}")

    # Mark as processing in Firebase
    fb_put(f"queue/{task_id}/status", "processing")
    fb_put(f"queue/{task_id}/started_at", int(time.time()))

    status_msg_id = send_telegram_msg(
        chat_id,
        f"⚡ *Rendering Started on 30GB Kaggle Cluster!*\n\n"
        f"📖 *Doc ID:* `{doc_id}`\n"
        f"🖥️ *Node:* Kaggle High-Mem Worker\n"
        f"🔄 *Status:* Downloading full-resolution pages...\n\n"
        f"⏳ _Please wait, your PDF is being generated..._"
    )

    raw_pdf_path = os.path.join(DOWNLOAD_DIR, f"scribd_{doc_id}_raw.pdf")
    compressed_pdf_path = os.path.join(DOWNLOAD_DIR, f"scribd_{doc_id}_compressed.pdf")

    try:
        # Step 1: Render via Puppeteer
        render_res = execute_downloader_process(doc_id, raw_pdf_path)
        title = render_res.get("title", f"Scribd Document {doc_id}")
        page_count = render_res.get("pageCount", "Full")
        raw_size = get_file_size_mb(raw_pdf_path)

        print(f"✅ Rendered raw PDF for {doc_id}: {page_count} pages, {raw_size} MB")

        # Step 2: Lossless Ghostscript Compression (ILovePDF ebook preset)
        comp_res = compress_pdf_lossless(raw_pdf_path, compressed_pdf_path, preset="/ebook")
        final_pdf_path = comp_res["final_path"]
        final_size = comp_res["final_size_mb"]

        print(f"🗜️ Ghostscript Finished: {raw_size} MB ➔ {final_size} MB ({comp_res['reduction_pct']}% reduction)")

        # Step 3: Check Telegram 50MB file size ceiling
        if final_size > 50.0:
            print("⚠️ Compressed size still exceeds 50MB! Applying aggressive /screen compression...")
            aggressive_pdf = os.path.join(DOWNLOAD_DIR, f"scribd_{doc_id}_screen.pdf")
            comp_res = compress_pdf_lossless(raw_pdf_path, aggressive_pdf, preset="/screen")
            final_pdf_path = comp_res["final_path"]
            final_size = comp_res["final_size_mb"]

        # Step 4: Direct Upload to Telegram User (Bypasses Render server entirely)
        caption = (
            f"📚 *{title}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📑 *Pages:* {page_count}\n"
            f"🗜️ *Original:* {raw_size} MB ➔ *Compressed:* {final_size} MB (-{comp_res['reduction_pct']}%)\n"
            f"⚡ *Engine:* Ghostscript Lossless + Kaggle 30GB Cloud\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 *Downloaded via:* @ScribdPdfDownloaderBot\n"
            f"👨‍💻 *Developer:* @cryvex4"
        )

        file_id = send_telegram_doc(chat_id, final_pdf_path, caption)

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
        fb_put(f"queue/{task_id}/status", "failed")
        fb_put(f"queue/{task_id}/error", err_str)
        send_telegram_msg(
            chat_id,
            f"❌ *Render Failed for Doc ID:* `{doc_id}`\n\n"
            f"⚠️ *Reason:* {err_str[:200]}\n"
            f"Kripya dobara link bhej kar check karein."
        )

    finally:
        # Step 6: Cleanup local temporary files immediately to keep disk clean
        for p in [raw_pdf_path, compressed_pdf_path]:
            if os.path.exists(p):
                try:
                    os.unlink(p)
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
            fb_put("worker/heartbeat", heartbeat_data)

            # ── 11-Hour Zero-Downtime Session Handoff Check ──
            if uptime >= MAX_RUNTIME_SECONDS:
                if active_count == 0:
                    print("⏰ [11-Hour Reached] No active rendering jobs! Initiating zero-downtime handoff...")
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
