"""
first_run.py — FaceGuard First Admin Enrollment
=================================================
Run this ONCE to enroll the first admin face before starting the main app.
This starts a temporary, localhost-only server on port 5001.
It shuts itself down automatically after enrollment is complete.

    python first_run.py

Then start the main app normally:
    python app.py
"""

import sys
import os
import cv2
import dlib
import numpy as np
import base64
import json
import threading
import time

# ── make sure we can import project modules ──────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from flask import Flask, render_template_string, request, jsonify
from database import init_db, add_user, get_all_users, save_face_encoding, user_has_face, get_user_by_id
from fldm import compute_fldm_encoding, average_encodings

# ── dlib setup ───────────────────────────────────────────────────────────────
PREDICTOR_PATH = os.environ.get(
    "DLIB_PREDICTOR",
    os.path.join(BASE_DIR, "shape_predictor_68_face_landmarks.dat")
)

if not os.path.exists(PREDICTOR_PATH):
    print("\n[!] dlib model not found. Run setup.py first:\n    python setup.py\n")
    sys.exit(1)

detector  = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(PREDICTOR_PATH)

# ── Flask app ─────────────────────────────────────────────────────────────────
setup_app = Flask(__name__)
setup_app.secret_key = "first_run_temp_secret"

# ── HTML template (self-contained, no external files needed) ─────────────────
PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>FaceGuard — First Admin Setup</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0c10; --bg2: #0f1218; --bg3: #151a22;
    --border: #1e2530; --border2: #2a3442;
    --text: #c8d4e0; --text2: #6b7f94; --text3: #3d4f62;
    --accent: #00d4ff; --accent2: #0099cc; --accent-dim: #003344;
    --green: #00e5a0; --green-dim: #003322;
    --red: #ff4466; --red-dim: #330011;
    --yellow: #ffd700;
    --mono: 'Space Mono', monospace;
    --sans: 'Syne', sans-serif;
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg); color: var(--text);
    font-family: var(--sans); min-height: 100vh;
    display: flex; align-items: center; justify-content: center;
    padding: 24px;
  }
  .card {
    width: 100%; max-width: 920px;
    background: var(--bg2); border: 1px solid var(--border);
    border-radius: 8px; overflow: hidden;
  }
  .card-header {
    background: var(--bg3); border-bottom: 1px solid var(--border);
    padding: 28px 36px;
  }
  .header-top { display: flex; align-items: center; gap: 14px; margin-bottom: 8px; }
  .logo { font-size: 28px; color: var(--accent); }
  .title { font-size: 24px; font-weight: 800; letter-spacing: 3px; }
  .subtitle { color: var(--text2); font-size: 13px; font-family: var(--mono); letter-spacing: 1px; }
  .warning-bar {
    background: rgba(255,212,0,0.08); border: 1px solid rgba(255,212,0,0.3);
    color: var(--yellow); font-family: var(--mono); font-size: 12px;
    padding: 10px 18px; letter-spacing: 1px; margin: 0 36px 0;
    border-radius: 4px; margin-top: 16px;
  }

  .card-body {
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 0;
  }
  @media (max-width: 700px) { .card-body { grid-template-columns: 1fr; } }

  /* LEFT — form */
  .left-panel { padding: 32px 36px; border-right: 1px solid var(--border); }
  .field { margin-bottom: 24px; }
  .label {
    display: block; font-family: var(--mono); font-size: 11px;
    letter-spacing: 3px; text-transform: uppercase; color: var(--text2);
    margin-bottom: 8px;
  }
  .input {
    width: 100%; background: var(--bg3); border: 1px solid var(--border2);
    color: var(--text); font-size: 16px; padding: 11px 14px;
    border-radius: 4px; outline: none; transition: border-color .2s;
    font-family: var(--sans);
  }
  .input:focus { border-color: var(--accent); }
  .input::placeholder { color: var(--text3); }

  .steps { margin-bottom: 28px; }
  .step {
    display: flex; gap: 14px; padding: 12px 0;
    border-bottom: 1px solid var(--border);
    transition: opacity .3s; opacity: .35;
  }
  .step.active, .step.done { opacity: 1; }
  .step-num {
    width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700;
    background: var(--border2); color: var(--text2);
  }
  .step.active .step-num { background: var(--accent-dim); color: var(--accent); }
  .step.done  .step-num  { background: var(--green-dim);  color: var(--green); }
  .step-title { font-weight: 700; font-size: 14px; color: var(--text); margin-bottom: 2px; }
  .step-desc  { font-size: 12px; color: var(--text2); }

  .progress-wrap { margin-bottom: 24px; display: none; }
  .progress-label { font-family: var(--mono); font-size: 12px; color: var(--text2); margin-bottom: 7px; }
  .progress-track { height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; }
  .progress-fill  { height: 100%; background: var(--accent); border-radius: 3px; transition: width .3s; }

  .btn-row { display: flex; gap: 10px; flex-wrap: wrap; }
  .btn {
    flex: 1; display: flex; align-items: center; justify-content: center; gap: 8px;
    font-family: var(--sans); font-weight: 700; font-size: 14px;
    letter-spacing: 1px; padding: 12px 18px; border: none; border-radius: 4px;
    cursor: pointer; transition: all .2s; white-space: nowrap;
  }
  .btn:disabled { cursor: not-allowed; opacity: .45; }
  .btn-capture  { background: transparent; color: var(--accent); border: 1px solid var(--accent); }
  .btn-capture:hover:not(:disabled) { background: var(--accent-dim); }
  .btn-enroll   { background: var(--accent); color: #0a0c10; }
  .btn-enroll:hover:not(:disabled)  { background: #00eeff; }

  .result {
    display: none; margin-top: 18px; padding: 13px 16px;
    border-radius: 4px; font-size: 14px; font-weight: 600; line-height: 1.5;
  }
  .result.success { background: var(--green-dim); color: var(--green); border: 1px solid var(--green); }
  .result.error   { background: var(--red-dim);   color: var(--red);   border: 1px solid var(--red); }
  .result.info    { background: var(--accent-dim); color: var(--accent); border: 1px solid var(--accent2); }

  /* RIGHT — camera */
  .right-panel { padding: 32px; display: flex; flex-direction: column; gap: 12px; }

  .viewport {
    position: relative; aspect-ratio: 4/3;
    background: #000; border-radius: 4px; overflow: hidden;
  }
  .viewport video { width: 100%; height: 100%; object-fit: cover; transform: scaleX(-1); }

  .corner { position: absolute; width: 22px; height: 22px; border-style: solid; border-color: var(--accent); border-width: 0; }
  .corner.tl { top:10px; left:10px;  border-top-width:2px;    border-left-width:2px; }
  .corner.tr { top:10px; right:10px; border-top-width:2px;    border-right-width:2px; }
  .corner.bl { bottom:10px; left:10px;  border-bottom-width:2px; border-left-width:2px; }
  .corner.br { bottom:10px; right:10px; border-bottom-width:2px; border-right-width:2px; }

  .scanline {
    position: absolute; left:0; right:0; height:2px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
    box-shadow: 0 0 8px var(--accent); display: none; top: 0;
  }
  .scanline.on { display: block; animation: sweep 2s ease-in-out infinite; }
  @keyframes sweep { 0%{top:0} 50%{top:calc(100% - 2px)} 100%{top:0} }

  .frames-strip {
    position: absolute; bottom:8px; left:8px; right:8px;
    display: flex; gap: 4px; flex-wrap: wrap; z-index: 5;
  }
  .thumb { width:34px; height:34px; object-fit:cover; border-radius:2px; border:1px solid var(--green); }

  .result-overlay {
    position: absolute; inset: 0; background: rgba(10,12,16,.88);
    display: none; flex-direction: column; align-items: center;
    justify-content: center; gap: 12px; z-index: 10;
  }
  .result-overlay.show { display: flex; }
  .ov-icon { font-size: 52px; line-height: 1; }
  .ov-text { font-size: 16px; font-weight: 700; text-align: center; padding: 0 20px; }

  .cam-hint { font-family: var(--mono); font-size: 11px; color: var(--text3); text-align: center; letter-spacing: 1px; }

  /* Existing users notice */
  .existing-notice {
    margin: 0 36px 28px;
    padding: 14px 18px;
    background: var(--green-dim); color: var(--green);
    border: 1px solid var(--green); border-radius: 4px;
    font-size: 13px; line-height: 1.6;
  }
  .existing-notice a { color: var(--green); text-decoration: underline; }
</style>
</head>
<body>
<div class="card">
  <div class="card-header">
    <div class="header-top">
      <span class="logo">⬡</span>
      <span class="title">FACEGUARD</span>
    </div>
    <div class="subtitle">FIRST ADMIN ENROLLMENT — TEMPORARY SETUP SERVER</div>
    <div class="warning-bar">
      ⚠ This setup server is running on port 5001, localhost only.
      It will shut down automatically after enrollment is complete.
    </div>
  </div>

  {% if existing_admins %}
  <div class="existing-notice">
    ✓ Existing admin accounts found:
    {% for a in existing_admins %}
      <strong>{{ a.name }}</strong> (ID #{{ a.id }}, face: {{ "enrolled" if a.has_face else "NOT enrolled" }}){% if not loop.last %}, {% endif %}
    {% endfor %}<br>
    You can re-enroll a face here, or just start the main app:
    <a href="javascript:void(0)" onclick="shutdownServer()">Shut down this setup server</a>
  </div>
  {% endif %}

  <div class="card-body">
    <!-- LEFT -->
    <div class="left-panel">
      <div class="field">
        <label class="label" for="adminName">Admin Name</label>
        <input class="input" type="text" id="adminName" placeholder="e.g. Harshit" value="{{ default_name }}" autocomplete="off"/>
      </div>

      <div class="steps">
        <div class="step active" id="s1">
          <div class="step-num">1</div>
          <div><div class="step-title">Enter your name</div><div class="step-desc">This becomes your admin account</div></div>
        </div>
        <div class="step" id="s2">
          <div class="step-num">2</div>
          <div><div class="step-title">Position face in camera</div><div class="step-desc">Look directly at the webcam</div></div>
        </div>
        <div class="step" id="s3">
          <div class="step-num">3</div>
          <div><div class="step-title">Capture frames</div><div class="step-desc">Hold still — 8 frames captured automatically</div></div>
        </div>
        <div class="step" id="s4">
          <div class="step-num">4</div>
          <div><div class="step-title">Enroll & launch</div><div class="step-desc">Save to DB, then open the main app</div></div>
        </div>
      </div>

      <div class="progress-wrap" id="progressWrap">
        <div class="progress-label">Capturing: <span id="capCount">0</span> / 8 frames</div>
        <div class="progress-track"><div class="progress-fill" id="progressFill" style="width:0%"></div></div>
      </div>

      <div class="btn-row">
        <button class="btn btn-capture" id="captureBtn" disabled>◉ Capture</button>
        <button class="btn btn-enroll"  id="enrollBtn"  disabled>✓ Enroll Admin</button>
      </div>

      <div class="result" id="result"></div>
    </div>

    <!-- RIGHT -->
    <div class="right-panel">
      <div class="viewport" id="viewport">
        <video id="video" autoplay muted playsinline></video>
        <div class="corner tl"></div><div class="corner tr"></div>
        <div class="corner bl"></div><div class="corner br"></div>
        <div class="scanline" id="scanline"></div>
        <div class="frames-strip" id="framesStrip"></div>
        <div class="result-overlay" id="overlay">
          <div class="ov-icon" id="ovIcon"></div>
          <div class="ov-text" id="ovText"></div>
        </div>
      </div>
      <p class="cam-hint">Camera activates automatically on page load</p>
    </div>
  </div>
</div>

<script>
const video      = document.getElementById("video");
const scanline   = document.getElementById("scanline");
const captureBtn = document.getElementById("captureBtn");
const enrollBtn  = document.getElementById("enrollBtn");
const nameInput  = document.getElementById("adminName");
const progressWrap = document.getElementById("progressWrap");
const progressFill = document.getElementById("progressFill");
const capCount   = document.getElementById("capCount");
const framesStrip = document.getElementById("framesStrip");
const resultEl   = document.getElementById("result");
const overlay    = document.getElementById("overlay");
const ovIcon     = document.getElementById("ovIcon");
const ovText     = document.getElementById("ovText");

const TOTAL = 8;
let frames = [];
let stream = null;

// ── Activate step UI
function step(n) {
  [1,2,3,4].forEach(i => {
    const el = document.getElementById("s" + i);
    if (i < n)  el.className = "step done";
    else if (i === n) el.className = "step active";
    else el.className = "step";
  });
}

// ── Camera
async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: {ideal:640}, height: {ideal:480}, facingMode:"user" },
      audio: false
    });
    video.srcObject = stream;
    captureBtn.disabled = false;
    step(2);
  } catch(e) {
    showResult("error", "Camera error: " + e.message + ". Make sure you allow camera access.");
  }
}

// ── Capture frame
function captureFrame(quality = 0.88) {
  const c = document.createElement("canvas");
  c.width  = video.videoWidth  || 640;
  c.height = video.videoHeight || 480;
  const ctx = c.getContext("2d");
  ctx.translate(c.width, 0);
  ctx.scale(-1, 1);
  ctx.drawImage(video, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", quality);
}

// ── Capture button
captureBtn.addEventListener("click", async () => {
  const name = nameInput.value.trim();
  if (!name) { nameInput.focus(); showResult("error", "Enter your name first."); return; }

  frames = [];
  framesStrip.innerHTML = "";
  progressWrap.style.display = "block";
  captureBtn.disabled = true;
  enrollBtn.disabled  = true;
  step(3);
  scanline.className = "scanline on";
  resultEl.style.display = "none";

  for (let i = 0; i < TOTAL; i++) {
    const f = captureFrame();
    frames.push(f);
    progressFill.style.width = ((i+1)/TOTAL*100) + "%";
    capCount.textContent = i + 1;
    const img = document.createElement("img");
    img.src = f; img.className = "thumb"; img.alt = "";
    framesStrip.appendChild(img);
    await new Promise(r => setTimeout(r, 280));
  }

  scanline.className = "scanline";
  captureBtn.disabled = false;
  enrollBtn.disabled  = false;
  step(4);
  showResult("info", "✓ " + TOTAL + " frames captured. Click Enroll Admin to save.");
});

// ── Enroll button
enrollBtn.addEventListener("click", async () => {
  const name = nameInput.value.trim();
  if (!name) { showResult("error", "Enter your name."); return; }
  if (frames.length < 3) { showResult("error", "Capture frames first."); return; }

  captureBtn.disabled = true;
  enrollBtn.disabled  = true;
  enrollBtn.textContent = "Enrolling...";

  try {
    const res = await fetch("/setup/enroll", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, frames })
    });
    const data = await res.json();

    if (data.success) {
      overlay.className = "result-overlay show";
      ovIcon.textContent = "✓";
      ovIcon.style.color = "var(--green)";
      ovText.textContent = `Admin "${data.name}" enrolled!`;
      ovText.style.color = "var(--green)";
      showResult("success",
        `✓ Admin account created — ID #${data.user_id}, name: "${data.name}".\n` +
        `The setup server will shut down in 3 seconds.\n` +
        `Then run: python app.py  →  open http://localhost:5000`
      );
      setTimeout(() => fetch("/setup/shutdown", { method: "POST" }).catch(()=>{}), 3000);
    } else {
      showResult("error", data.error || "Enrollment failed. Try again.");
      captureBtn.disabled = false;
      enrollBtn.disabled  = false;
      enrollBtn.textContent = "✓ Enroll Admin";
    }
  } catch(e) {
    showResult("error", "Error: " + e.message);
    captureBtn.disabled = false;
    enrollBtn.disabled  = false;
    enrollBtn.textContent = "✓ Enroll Admin";
  }
});

// ── Name input step update
nameInput.addEventListener("input", () => {
  if (nameInput.value.trim().length > 1 && stream) step(2);
});

// ── Result display
function showResult(type, msg) {
  resultEl.style.display = "block";
  resultEl.className = "result " + type;
  resultEl.textContent = msg;
}

// ── Shutdown helper (for existing-admins link)
function shutdownServer() {
  if (!confirm("Shut down the setup server?")) return;
  fetch("/setup/shutdown", { method: "POST" }).catch(()=>{});
  document.body.innerHTML = "<div style='color:#00e5a0;font-family:monospace;padding:40px;font-size:18px'>Setup server stopped.<br><br>Run: python app.py<br>Then open: http://localhost:5000</div>";
}
window.shutdownServer = shutdownServer;

startCamera();
</script>
</body>
</html>
"""

# ── Routes ────────────────────────────────────────────────────────────────────

@setup_app.route("/")
def index():
    init_db()
    users = get_all_users()
    admins = [u for u in users if u["role"] == "admin"]
    for a in admins:
        a["has_face"] = user_has_face(a["id"])

    default_name = admins[0]["name"] if admins else ""
    return render_template_string(
        PAGE_HTML,
        existing_admins=admins,
        default_name=default_name
    )


@setup_app.route("/setup/enroll", methods=["POST"])
def setup_enroll():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data received"}), 400

    name   = (data.get("name") or "").strip()
    frames = data.get("frames", [])

    if not name:
        return jsonify({"error": "Name is required"}), 400
    if len(frames) < 3:
        return jsonify({"error": "Need at least 3 frames"}), 400

    # Compute encodings from frames
    encodings = []
    for b64 in frames:
        try:
            if "," in b64:
                b64 = b64.split(",", 1)[1]
            img_bytes = base64.b64decode(b64)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            faces = detector(gray, 1)
            if not faces:
                continue
            face = max(faces, key=lambda f: f.width() * f.height())
            shape = predictor(gray, face)
            enc = compute_fldm_encoding(shape)
            encodings.append(enc)
        except Exception as e:
            continue

    if len(encodings) < 2:
        return jsonify({
            "error": (
                f"Could only detect a face in {len(encodings)} of {len(frames)} frames. "
                "Please ensure good lighting and look directly at the camera."
            )
        }), 400

    avg_enc = average_encodings(encodings)

    # Check if an admin already exists without a face — use them
    init_db()
    users = get_all_users()
    admin_no_face = next(
        (u for u in users if u["role"] == "admin" and not user_has_face(u["id"])),
        None
    )

    if admin_no_face:
        user_id = admin_no_face["id"]
        save_face_encoding(user_id, avg_enc)
    else:
        user_id = add_user(name, role="admin")
        save_face_encoding(user_id, avg_enc)

    print(f"\n[✓] Admin enrolled: '{name}' (ID #{user_id})")
    print(f"    Faces detected in {len(encodings)}/{len(frames)} frames")
    print(f"    FLDM encoding: { {k: round(v, 4) for k, v in avg_enc.items()} }")

    return jsonify({"success": True, "user_id": user_id, "name": name})


@setup_app.route("/setup/shutdown", methods=["POST"])
def setup_shutdown():
    """Graceful self-shutdown after enrollment is complete."""
    def _stop():
        time.sleep(0.5)
        os._exit(0)
    threading.Thread(target=_stop, daemon=True).start()
    return jsonify({"ok": True})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()

    print()
    print("=" * 60)
    print("  FaceGuard — First Admin Setup")
    print("=" * 60)

    users = get_all_users()
    admins = [u for u in users if u["role"] == "admin"]
    enrolled_admins = [a for a in admins if user_has_face(a["id"])]

    if enrolled_admins:
        print(f"\n[i] Already enrolled admin(s) found:")
        for a in enrolled_admins:
            print(f"    - {a['name']} (ID #{a['id']})")
        print("\n    You can re-enroll, or just start the main app:")
        print("    python app.py")
        print()
        ans = input("    Open setup page anyway? [y/N]: ").strip().lower()
        if ans != "y":
            print("\n    Skipped. Run: python app.py\n")
            sys.exit(0)

    import webbrowser

    print("\n[~] Starting setup server on http://localhost:5001 ...")
    print("    Opening browser automatically...")
    print("    (Press Ctrl+C to cancel at any time)\n")

    # Open browser after a short delay
    def open_browser():
        time.sleep(1.2)
        webbrowser.open("http://localhost:5001")

    threading.Thread(target=open_browser, daemon=True).start()

    setup_app.run(host="127.0.0.1", port=5001, debug=False, use_reloader=False)