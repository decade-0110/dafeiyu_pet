# -*- coding: utf-8 -*-
"""打源码分享 zip（排除 venv/打包产物/配置）"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = HERE
OUT = os.path.join(os.path.dirname(HERE), "大肥鱼桌宠_源码.zip")

files = ["main.py", "桌宠.py", "pet_window.py", "bubble.py", "outfit.py",
         "ai_chat.py", "weather.py", "balance.py", "holiday.py", "config.py",
         "preprocess_outfits.py", "fetch_holidays.py",
         "启动桌宠.bat", "桌宠.spec",
         "requirements.txt", "requirements-dev.txt", "pytest.ini",
         "README.md", "MAINTENANCE.md", "LICENSE", "icon.ico",
         ".gitignore", ".gitattributes", "config.example.json"]
for sub in ("sprites", "assets", "tests"):
    for root, dirs, fs in os.walk(os.path.join(BASE, sub)):
        if "__pycache__" in root or ".pytest_cache" in root:
            continue
        for f in fs:
            if f.endswith(".pyc"):
                continue
            files.append(os.path.relpath(os.path.join(root, f), BASE).replace(os.sep, "/"))

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for f in files:
        z.write(os.path.join(BASE, f), f)

print("files:", len(files))
print("size:", os.path.getsize(OUT) // 1024, "KB")
for f in files:
    print(" ", f)
