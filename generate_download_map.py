# generate_download_map.py
# Run this to create/update download_map.json from files in ./songs
# Usage: python generate_download_map.py

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path.cwd()
SONGS_DIR = PROJECT_ROOT / "songs"
OUT_FILE = PROJECT_ROOT / "download_map.json"

if not SONGS_DIR.exists():
    print(f"Songs folder not found: {SONGS_DIR}")
    print("Create the folder and add your song files (mp3, wav, m4a, ogg, flac).")
    sys.exit(1)

valid_exts = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}

download_map = {}

for f in sorted(SONGS_DIR.iterdir()):
    if f.is_file() and f.suffix.lower() in valid_exts:
        # key = filename without extension (you can change to title normalization)
        key = f.stem.strip()
        # Ensure unique keys: if duplicate, append a number
        original_key = key
        i = 1
        while key in download_map:
            key = f"{original_key}_{i}"
            i += 1
        # store path relative to project root (use POSIX style for URLs)
        rel_path = str(Path("songs") / f.name)
        download_map[key] = rel_path

if not download_map:
    print("No song files found in songs/ with supported extensions.")
else:
    with OUT_FILE.open("w", encoding="utf-8") as fh:
        json.dump(download_map, fh, indent=2, ensure_ascii=False)
    print(f"Wrote {len(download_map)} entries to {OUT_FILE}")
    print("Example entries:")
    for k, v in list(download_map.items())[:10]:
        print(f"  {k} -> {v}")
