"""
setup.py — FaceGuard First-Time Setup
======================================
Run this ONCE before starting the app for the first time.

    python setup.py

What it does:
  1. Checks Python version (3.8+ required)
  2. Verifies all required packages are installed
  3. Downloads the dlib 68-point landmark predictor model (~100 MB)
  4. Initializes the SQLite database
  5. Creates a default admin user (no face — enroll via the UI)
"""

import sys
import os
import urllib.request
import bz2
import shutil

# ── Python version check ───────────────────────────────────────────────────
if sys.version_info < (3, 8):
    print("ERROR: Python 3.8 or higher is required.")
    sys.exit(1)

print("=" * 60)
print("  FaceGuard Setup")
print("=" * 60)

# ── Package check ──────────────────────────────────────────────────────────
REQUIRED = ["flask", "dlib", "cv2", "numpy"]
missing = []

for pkg in REQUIRED:
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)

if missing:
    print("\n[!] Missing packages detected:")
    for m in missing:
        print(f"    - {m}")
    print("\n    Install them with:")
    print("    pip install flask dlib opencv-python numpy")
    print("\n    Note: dlib may require cmake and a C++ compiler.")
    print("    See README.md for platform-specific instructions.")
    sys.exit(1)

print("[✓] All Python packages found.")

# ── dlib model download ────────────────────────────────────────────────────
MODEL_URL  = "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"
MODEL_BZ2  = "shape_predictor_68_face_landmarks.dat.bz2"
MODEL_DAT  = "shape_predictor_68_face_landmarks.dat"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, MODEL_DAT)

if os.path.exists(MODEL_PATH):
    print(f"[✓] dlib model already exists: {MODEL_DAT}")
else:
    print(f"\n[~] Downloading dlib landmark model (~100 MB)...")
    print(f"    Source: {MODEL_URL}")
    print("    This may take a few minutes depending on your connection.\n")

    bz2_path = os.path.join(BASE_DIR, MODEL_BZ2)

    def report_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        pct = min(downloaded / total_size * 100, 100) if total_size > 0 else 0
        bar = int(pct / 2)
        print(f"\r    [{'█' * bar}{'░' * (50 - bar)}] {pct:.1f}%", end="", flush=True)

    try:
        urllib.request.urlretrieve(MODEL_URL, bz2_path, reporthook=report_progress)
        print("\n\n[~] Decompressing...")

        with bz2.open(bz2_path, "rb") as f_in:
            with open(MODEL_PATH, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        os.remove(bz2_path)
        print(f"[✓] Model saved: {MODEL_DAT}")

    except Exception as e:
        print(f"\n[!] Download failed: {e}")
        print("    You can download it manually from:")
        print(f"    {MODEL_URL}")
        print(f"    Then extract the .dat file to: {BASE_DIR}")
        sys.exit(1)

# ── DB init ────────────────────────────────────────────────────────────────
print("\n[~] Initializing database...")

sys.path.insert(0, BASE_DIR)
from database import init_db, add_user, get_all_users, user_has_face

init_db()
print("[✓] Database initialized: database/faceguard.db")

# ── Check if any users exist ───────────────────────────────────────────────
users = get_all_users()
if not users:
    print("\n[~] No users found. Creating default admin account...")
    uid = add_user("Admin", role="admin")
    print(f"[✓] Default admin created (ID #{uid}, name: 'Admin')")
    print("    → Go to http://localhost:5000/admin/add-user after starting")
    print("      to enroll this admin's face.")
else:
    print(f"[✓] Existing users found: {len(users)}")

# ── Done ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  Setup complete!")
print("=" * 60)
print()
print("  NEXT STEP — Enroll the first admin face:")
print()
print("    python first_run.py")
print()
print("  This opens a browser window where you scan your face")
print("  to create the admin account. It shuts itself down")
print("  automatically when done.")
print()
print("  Then start the main app:")
print("    python app.py")
print("    → http://localhost:5000")
print()