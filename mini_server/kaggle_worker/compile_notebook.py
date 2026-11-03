# =============================================================================
# Kaggle Notebook Compiler & Direct REST API Deployer
# =============================================================================
import os
import sys
import json
import base64
import argparse
import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_NOTEBOOK_PATH = os.path.join(CURRENT_DIR, "scribd_cloud_worker.ipynb")

CELL_FILES = [
    ("cell1_setup.py", "python"),
    ("cell2_config.py", "python"),
    ("cell3_compressor.py", "python"),
    ("cell4_downloader.js", "javascript_wrapper"),
    ("cell5_worker.py", "python"),
]


def compile_notebook():
    """Compiles all cell modular files into a production Jupyter Notebook."""
    cells = []

    for filename, ftype in CELL_FILES:
        filepath = os.path.join(CURRENT_DIR, filename)
        if not os.path.exists(filepath):
            print(f"⚠️ Warning: {filename} not found, skipping...")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()

        if ftype == "javascript_wrapper":
            # Safely pack JS into base64 to prevent any quote/escape corruption
            b64_str = base64.b64encode(code.encode("utf-8")).decode("ascii")
            cell_code = (
                f'# Cell 4: Extract ultra-optimized downloader.js to disk\n'
                f'import base64\n\n'
                f'b64_payload = "{b64_str}"\n'
                f'with open("downloader.js", "wb") as f:\n'
                f'    f.write(base64.b64decode(b64_payload))\n\n'
                f'print("✅ [CELL 4 Complete] downloader.js written cleanly to working directory!")'
            )
        else:
            cell_code = code

        cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": cell_code.splitlines(keepends=True)
        })

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.10"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 2
    }

    with open(OUTPUT_NOTEBOOK_PATH, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=2)

    print(f"🎉 Successfully compiled notebook: {OUTPUT_NOTEBOOK_PATH}")
    return notebook


def push_to_kaggle(username, api_key, slug, title="Scribd Cloud Worker"):
    """Directly pushes and boots the notebook on Kaggle via REST API."""
    notebook = compile_notebook()
    notebook_json_str = json.dumps(notebook)

    creds = base64.b64encode(f"{username}:{api_key}".encode()).decode()
    headers = {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json"
    }
    payload = {
        "id": None,
        "slug": f"{username}/{slug}",
        "title": title,
        "text": notebook_json_str,
        "language": "python",
        "kernelType": "notebook",
        "isPrivate": True,
        "enableGpu": False,
        "enableInternet": True
    }

    url = "https://www.kaggle.com/api/v1/kernels/push"
    print(f"🚀 Pushing kernel to Kaggle: {username}/{slug} ...")
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    if r.ok:
        res = r.json()
        print(f"✅ Kaggle Push Successful! Kernel URL: {res.get('url', 'OK')}")
        return True
    else:
        print(f"❌ Kaggle Push Failed [{r.status_code}]: {r.text}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compile and Deploy Scribd Cloud Kaggle Worker")
    parser.add_argument("--push", action="store_true", help="Push directly to Kaggle after compiling")
    parser.add_argument("--user", help="Kaggle Username")
    parser.add_argument("--key", help="Kaggle API Key")
    parser.add_argument("--slug", default="scribd-cloud-worker", help="Kaggle Notebook Slug")
    parser.add_argument("--title", default="Scribd Cloud Worker", help="Kaggle Notebook Title")
    args = parser.parse_args()

    compile_notebook()

    if args.push:
        user = args.user or os.environ.get("KAGGLE_USERNAME")
        key = args.key or os.environ.get("KAGGLE_KEY")
        if not user or not key:
            print("❌ Error: Kaggle credentials required. Pass --user and --key or set KAGGLE_USERNAME & KAGGLE_KEY.")
            sys.exit(1)
        push_to_kaggle(user, key, args.slug, args.title)
