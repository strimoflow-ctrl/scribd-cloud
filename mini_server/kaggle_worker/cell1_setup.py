# =============================================================================
# CELL 1 — System Dependencies & Ghostscript Installation
# =============================================================================
import os
import sys
import subprocess

print("⚙️ [CELL 1] Setting up 30GB Cloud Compute Environment...")

def run_cmd(cmd):
    try:
        subprocess.check_call(cmd, shell=True)
    except Exception as e:
        print(f"⚠️ Warning running '{cmd}': {e}")

# 1. Install Ghostscript & Linux Chrome GUI Libraries (libatk, libnss, libgbm, etc.)
print("🗜️ Installing Ghostscript and Chromium OS Dependencies...")
chrome_deps = (
    "ghostscript ca-certificates fonts-liberation libasound2* libatk-bridge2.0* "
    "libatk1.0* libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3* libnspr4 libnss3 "
    "libx11-xcb1 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 xdg-utils"
)
run_cmd(f"apt-get update -qq && apt-get install -y -qq {chrome_deps}")

# 2. Verify Ghostscript
try:
    res = subprocess.check_output(["gs", "--version"]).decode().strip()
    print(f"✅ Ghostscript Engine Active: Version {res}")
except Exception:
    print("⚠️ Ghostscript verification notice. Engine will proceed.")

# 3. Install Python requirements
print("🐍 Installing Python Libraries...")
run_cmd(f"{sys.executable} -m pip install -q requests pyrebase4 nest_asyncio")

# 4. Install Node.js Puppeteer & Stealth libraries for rendering
print("🌐 Installing Node.js Puppeteer Stealth & PDF-Lib...")
run_cmd("npm init -y > /dev/null 2>&1")
run_cmd("npm install --silent puppeteer puppeteer-extra puppeteer-extra-plugin-stealth pdf-lib")
run_cmd("npx puppeteer browsers install chrome --install-deps > /dev/null 2>&1")

print("✨ [CELL 1 Complete] All Compute Dependencies Initialized!")
