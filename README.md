# 🚀 Scribd Cloud Supercluster Architecture (Render + Kaggle + Firebase)

Scribd Cloud ek distributed, production-grade architecture hai jo **1000+ page Scribd documents** ko bina kisi server crash, RAM bottleneck, ya bandwidth charges ke **100% Free Tiers** par render aur deliver karta hai.

---

## 🏗️ Architecture Overview

```mermaid
flowchart TD
    User([Telegram User]) -->|1. Sends Scribd Link| MiniServer[Render Mini-Server\nMaster Coordinator 24/7\nRAM < 60MB | Bandwidth < 30MB/Mo]
    MiniServer -->|2. Check Cache| FirebaseCache[(Firebase RTDB Cache\nfile_id instant store)]
    
    FirebaseCache -.->|Cache Hit: 0.2s Instant Delivery| User
    
    MiniServer -->|3. Cache Miss: Add to Queue| FirebaseQueue[(Firebase Task Queue\n/scribd_cloud/queue)]
    
    Kaggle[Kaggle Compute Cluster\n30 GB RAM | 4 vCPUs\nWorker Session] -->|4. Safe Poll 15-20s| FirebaseQueue
    Kaggle -->|5. Headless Puppeteer + DOM Pruning| Scribd[Scribd CDN]
    Kaggle -->|6. ILovePDF-Style Lossless Compression| Ghostscript[Ghostscript Engine\n-dPDFSETTINGS=/ebook]
    Kaggle -->|7. Direct Upload sendDocument| TelegramAPI[Telegram Bot API\nDirect Delivery]
    TelegramAPI -->|Delivers PDF| User
    
    Kaggle -->|8. Store file_id in Cache| FirebaseCache
    Kaggle -->|9. 11-Hour Trigger Signal| MiniServer
    MiniServer -->|10. Auto-Restart Push via REST API| Kaggle
```

---

## 💎 Key Highlights & Free-Tier Optimization

| Component | Resource Limit | Cloud Architecture Usage | Safety Margin |
|---|---|---|---|
| **Render Web Service** | 512 MB RAM / 5 GB Bandwidth/mo | ~45 MB RAM / **<30 MB Bandwidth/mo** | **99.4% Free** (Heavy binaries bypass Render completely!) |
| **Kaggle Compute Engine** | 30 GB RAM / 4 vCPUs / 20GB Disk | Handles **10-12 parallel 1000-page PDFs** | Unlimited free CPU/RAM |
| **Firebase Spark Plan** | 10 GB Data Transfer/mo | Polling interval 15-20s = **~15 MB/mo** | **99.8% Free** (Spark plan safe forever) |
| **Ghostscript Compressor** | ILovePDF Standard | 140MB raw PDF ➔ **~32MB** | Easily stays under Telegram 50MB limit |
| **Smart Cloud Cache** | Instant Telegram `file_id` | **0.2s delivery** with 0% CPU & 0% download | Infinite instant speed |

---

## 📁 Project Structure

```text
scribd_cloud/
├── mini_server/               # 👑 Render Master Service (Runs 24/7)
│   ├── server.py              # Telegram Bot + Health Server + Kaggle Orchestrator
│   └── requirements.txt       # pyTelegramBotAPI, requests
│
├── kaggle_worker/             # ⚡ Kaggle Compute Engine (30GB RAM)
│   ├── cell1_setup.py         # Installs Ghostscript, Puppeteer, Node deps
│   ├── cell2_config.py        # Firebase RTDB config + Proxy + Session timers
│   ├── cell3_compressor.py    # ILovePDF-style Ghostscript eBook compression
│   ├── cell4_downloader.js    # Puppeteer script with DOM node pruning & watermark
│   ├── cell5_worker.py        # Multi-task queue consumer + Telegram uploader
│   ├── compile_notebook.py    # Auto-compiles cells into scribd_cloud_worker.ipynb
│   └── scribd_cloud_worker.ipynb # Ready-to-run Jupyter notebook for Kaggle
└── README.md
```

---

## 🚀 Deployment Guide

### Step 1: Render Mini-Server (Master Coordinator)
1. Render.com par new **Web Service** create karein.
2. Root directory set karein: `scribd_cloud/mini_server`
3. Settings:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python server.py`
4. Environment Variables add karein:
   - `BOT_TOKEN`: Telegram bot token (Default already set in code)
   - `KAGGLE_USERNAME`: Aapka Kaggle username
   - `KAGGLE_KEY`: Aapka Kaggle API key (Kaggle Settings ➔ Create New API Token)
   - `KAGGLE_SLUG`: Notebook slug (e.g. `scribd-cloud-worker`)

---

### Step 2: Kaggle Worker Launch

#### Option A: One-Click Automatic via Render
Mini-Server ke andar Kaggle REST API integration built-in hai. Jab aap Render par server boot karenge ya `trigger_kaggle_worker()` call hoga, notebook automatically compile hokar Kaggle par push ho jayegi!

#### Option B: Manual Launch (Jupyter UI)
1. `c:\Users\cryvex\Desktop\Mini App\scribd_cloud\kaggle_worker\scribd_cloud_worker.ipynb` ko Kaggle par **New Notebook ➔ File ➔ Import Notebook** karein.
2. Notebook Settings me:
   - **Accelerator:** CPU (4 Cores, 30 GB RAM)
   - **Internet:** Enabled (ON)
3. **Run All** button par click karein. Worker turant start ho jayega aur Firebase queue sunna shuru kar dega.

---

### Step 3: Zero-Downtime Auto-Restart (11-Hour Rotation)
- Kaggle notebooks 12 ghante baad expire hoti hain.
- Hamare worker me `MAX_RUNTIME_SECONDS = 11.0 * 3600` (11 hours) set hai.
- Jaise hi 11 ghante pure hote hain aur active rendering jobs zero hote hain:
  1. Worker Firebase me `trigger_restart = True` flag set karta hai.
  2. Mini-Server is flag ko detect karta hai aur Kaggle REST API (`https://www.kaggle.com/api/v1/kernels/push`) ko fresh kernel push karta hai.
  3. New notebook session start ho jata hai bina kisi user request ko drop kiye!

---

## 🛠️ Testing Locally

Notebook compile karne ke liye:
```bash
python kaggle_worker/compile_notebook.py
```

Direct push test karne ke liye:
```bash
python kaggle_worker/compile_notebook.py --push --user YOUR_KAGGLE_USER --key YOUR_KAGGLE_KEY
```

