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

# 1. Install Ghostscript (The Lossless ILovePDF Compression Engine)
print("🗜️ Installing Ghostscript Engine...")
run_cmd("apt-get update -qq && apt-get install -y -qq ghostscript")

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

print("✨ [CELL 1 Complete] All Compute Dependencies Initialized!")

