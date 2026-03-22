"""
app.py — FaceGuard Flask Application
=====================================
Entry point. Runs the web server, defines all routes and API endpoints.

Run:
    python app.py

Default: http://localhost:5000
"""

import cv2
import dlib
import numpy as np
import base64
import json
import os
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, abort
)

from database import (
    init_db, add_user, get_all_users, get_user_by_id,
    update_user_role, delete_user, user_has_face,
    save_face_encoding, get_all_face_encodings,
    delete_face_encoding, log_auth_attempt, get_auth_log
)
from fldm import (
    compute_fldm_encoding, authenticate_against_db, average_encodings
)

# ──────────────────────────────────────────────────────────────────────────────
# APP SETUP
# ──────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get("FACEGUARD_SECRET", "faceguard_dev_secret_change_in_prod")

# dlib models — must be in project root or set via env
PREDICTOR_PATH = os.environ.get(
    "DLIB_PREDICTOR",
    os.path.join(os.path.dirname(__file__), "shape_predictor_68_face_landmarks.dat")
)

detector  = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(PREDICTOR_PATH)


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def decode_base64_image(b64_string: str):
    """
    Decode a base64 data-URI image from the browser webcam capture.
    Returns an OpenCV BGR image (numpy array), or None on failure.
    """
    try:
        if "," in b64_string:
            b64_string = b64_string.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_string)
        nparr = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception:
        return None


def detect_and_encode(img_bgr):
    """
    Detect the largest face in the image and return its FLDM encoding.

    Returns
    -------
    tuple: (encoding dict or None, error_message str or None)
    """
    if img_bgr is None:
        return None, "Could not decode image."

    gray  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray  = cv2.equalizeHist(gray)                   # improve landmark detection in varied lighting
    faces = detector(gray, 1)

    if len(faces) == 0:
        return None, "No face detected. Please ensure your face is clearly visible."

    # Use the largest detected face
    face = max(faces, key=lambda f: f.width() * f.height())
    shape = predictor(gray, face)
    encoding = compute_fldm_encoding(shape)
    return encoding, None


def login_required(role=None):
    """
    Decorator to protect routes.
    role=None  → any logged-in user
    role='admin' → admin only
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login_page"))
            if role and session.get("role") != role:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ──────────────────────────────────────────────────────────────────────────────
# PAGE ROUTES
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))


@app.route("/login")
def login_page():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/dashboard")
@login_required()
def dashboard():
    user = get_user_by_id(session["user_id"])
    if not user:
        session.clear()
        return redirect(url_for("login_page"))
    if user["role"] == "admin":
        return render_template("admin_dashboard.html", user=user)
    return render_template("employee_dashboard.html", user=user)


@app.route("/admin/add-user")
@login_required(role="admin")
def add_user_page():
    return render_template("add_user.html", user=get_user_by_id(session["user_id"]))


@app.route("/admin/manage-users")
@login_required(role="admin")
def manage_users_page():
    users = get_all_users()
    for u in users:
        u["has_face"] = user_has_face(u["id"])
    return render_template(
        "manage_users.html",
        users=users,
        current_user=get_user_by_id(session["user_id"])
    )


@app.route("/admin/auth-log")
@login_required(role="admin")
def auth_log_page():
    logs = get_auth_log(limit=100)
    return render_template(
        "auth_log.html",
        logs=logs,
        user=get_user_by_id(session["user_id"])
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403


# ──────────────────────────────────────────────────────────────────────────────
# API — AUTHENTICATION
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/authenticate", methods=["POST"])
def api_authenticate():
    """
    Receive a webcam frame, run FLDM, return auth result.

    Request JSON:
        { "frame": "<base64 data-URI>" }

    Response JSON (success):
        { "authenticated": true, "name": "...", "role": "...", "score": 0.031 }

    Response JSON (failure):
        { "authenticated": false, "score": 0.19, "message": "..." }
    """
    data = request.get_json(silent=True)
    if not data or "frame" not in data:
        return jsonify({"error": "No frame provided"}), 400

    img = decode_base64_image(data["frame"])
    live_enc, err = detect_and_encode(img)

    if err:
        return jsonify({"authenticated": False, "message": err, "score": None})

    stored = get_all_face_encodings()
    if not stored:
        return jsonify({
            "authenticated": False,
            "message": "No users enrolled yet. Ask your admin to add users.",
            "score": None
        })

    user_id, score = authenticate_against_db(live_enc, stored)

    if user_id:
        user = get_user_by_id(user_id)
        log_auth_attempt(user_id, score, True)
        session["user_id"] = user_id
        session["role"]    = user["role"]
        return jsonify({
            "authenticated": True,
            "name":  user["name"],
            "role":  user["role"],
            "score": round(score, 4),
            "redirect": url_for("dashboard")
        })

    log_auth_attempt(None, score, False)
    return jsonify({
        "authenticated": False,
        "score": round(score, 4),
        "message": "Face not recognized. Please try again or contact your admin."
    })


# ──────────────────────────────────────────────────────────────────────────────
# API — USER ENROLLMENT
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/enroll", methods=["POST"])
@login_required(role="admin")
def api_enroll():
    """
    Enroll a new user with face data.

    Request JSON:
        {
            "name": "Alice",
            "frames": ["<base64>", "<base64>", ...]   // 5-10 frames recommended
        }

    Response JSON:
        { "success": true, "user_id": 3, "name": "Alice" }
    """
    data = request.get_json(silent=True)
    if not data or "name" not in data or "frames" not in data:
        return jsonify({"error": "Missing name or frames"}), 400

    name   = data["name"].strip()
    frames = data["frames"]

    if not name:
        return jsonify({"error": "Name cannot be empty"}), 400
    if not frames or len(frames) < 3:
        return jsonify({"error": "Please provide at least 3 face frames"}), 400

    encodings = []
    for b64 in frames:
        img = decode_base64_image(b64)
        enc, err = detect_and_encode(img)
        if enc:
            encodings.append(enc)

    if len(encodings) < 2:
        return jsonify({
            "error": "Could not detect a face in enough frames. "
                     "Please ensure good lighting and look directly at the camera."
        }), 400

    avg_enc = average_encodings(encodings)
    user_id = add_user(name, role="employee")   # default role; admin assigns later
    save_face_encoding(user_id, avg_enc)

    return jsonify({"success": True, "user_id": user_id, "name": name})


# ──────────────────────────────────────────────────────────────────────────────
# API — USER MANAGEMENT
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/users", methods=["GET"])
@login_required(role="admin")
def api_get_users():
    users = get_all_users()
    for u in users:
        u["has_face"] = user_has_face(u["id"])
    return jsonify(users)


@app.route("/api/users/<int:user_id>/role", methods=["PATCH"])
@login_required(role="admin")
def api_update_role(user_id):
    """
    Update a user's role.
    Request JSON: { "role": "admin" | "employee" }
    """
    data = request.get_json(silent=True)
    if not data or "role" not in data:
        return jsonify({"error": "Missing role"}), 400

    new_role = data["role"]
    if new_role not in ("admin", "employee"):
        return jsonify({"error": "Role must be 'admin' or 'employee'"}), 400

    # Prevent self-demotion
    if user_id == session.get("user_id") and new_role != "admin":
        return jsonify({"error": "You cannot demote yourself"}), 403

    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    update_user_role(user_id, new_role)
    return jsonify({"success": True, "user_id": user_id, "role": new_role})


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@login_required(role="admin")
def api_delete_user(user_id):
    """Delete a user (and their face data)."""
    if user_id == session.get("user_id"):
        return jsonify({"error": "You cannot delete yourself"}), 403

    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    delete_user(user_id)
    return jsonify({"success": True})


@app.route("/api/users/<int:user_id>/face", methods=["DELETE"])
@login_required(role="admin")
def api_delete_face(user_id):
    """Remove only the face data for a user (user record stays)."""
    delete_face_encoding(user_id)
    return jsonify({"success": True})


@app.route("/api/session", methods=["GET"])
def api_session():
    """Return current session info (for JS to check auth state)."""
    if "user_id" in session:
        user = get_user_by_id(session["user_id"])
        return jsonify({"logged_in": True, "user": user})
    return jsonify({"logged_in": False})


# ──────────────────────────────────────────────────────────────────────────────
# STARTUP
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(PREDICTOR_PATH):
        print("=" * 60)
        print("ERROR: dlib shape predictor model not found!")
        print(f"Expected at: {PREDICTOR_PATH}")
        print()
        print("Download it with:")
        print("  python setup.py")
        print("=" * 60)
        exit(1)

    init_db()
    print("FaceGuard running at http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
