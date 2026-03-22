# ⬡ FaceGuard

**Role-Based Face Recognition Authentication System**  
*Mini Project | B.Sc. Cyber and Digital Science | SPPU | Sem-III*

---

## What is FaceGuard?

FaceGuard is a web-based biometric login system. Users scan their face to log in — no passwords. Once authenticated, they are routed to a role-appropriate dashboard (Admin or Employee) based on their account role.

The system includes a complete admin panel for enrolling new users, assigning roles, and reviewing an audit log of all authentication attempts.

---

## ⬡ The FLDM Algorithm (Our Original Contribution)

FaceGuard uses the **Facial Landmark Deviation Metric (FLDM)** — a custom face verification algorithm designed specifically for this project.

**FLDM does not use any library's built-in `face_recognition` or embedding function.** It works by:

1. Detecting **68 facial landmark points** using dlib's shape predictor
2. **Normalizing** all coordinates by inter-pupil distance (scale-invariant)
3. Computing **5 geometric zone ratios** from the landmark positions:

| Zone | Abbreviation | Weight | Description |
|------|-------------|--------|-------------|
| Eye Aspect Ratio | EAR | ×1.2 | Eye height / width (averaged both eyes) |
| Nose Bridge Ratio | NBR | ×1.0 | Bridge height relative to IPD |
| Mouth Width Ratio | MWR | ×1.1 | Outer mouth width relative to IPD |
| Jaw Angle Ratio | JAR | ×0.9 | Jaw width vs face height |
| Brow Raise Ratio | BRR | ×0.8 | Brow height above eye center |

4. Computing a **weighted normalized deviation score** between live and stored encodings:

```
D = Σ [ w_i × |enc_stored[i] − enc_live[i]| / max(enc_stored[i], enc_live[i]) ] / Σ w_i
```

5. Authenticating if **D < 0.08** (empirically calibrated threshold)

The full algorithm is in [`fldm/fldm.py`](fldm/fldm.py).

---

## Features

- **Face-only login** — no passwords required
- **Multi-frame enrollment** — 8 frames averaged for robust encoding
- **Role-based dashboards** — separate Admin and Employee views
- **Admin panel** — add users, assign roles, delete accounts
- **Auth audit log** — every login attempt logged with FLDM score
- **Offline/local** — SQLite database, no cloud dependency
- **Adaptive preprocessing** — histogram equalization for varied lighting

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, CSS3, JavaScript (Fetch API) |
| Backend | Python 3, Flask |
| Face Detection | dlib (HOG frontal face detector) |
| Landmark Prediction | dlib 68-point shape predictor |
| Face Recognition | **FLDM** (custom — this project) |
| Image Processing | OpenCV |
| Database | SQLite3 |

---

## Project Structure

```
faceguard/
│
├── app.py                  # Flask app — all routes & API endpoints
├── setup.py                # Step 1: download dlib model + init DB
├── first_run.py            # Step 2: enroll first admin face (browser UI on port 5001)
├── requirements.txt
│
├── fldm/
│   ├── __init__.py
│   └── fldm.py             # ★ FLDM algorithm (original contribution)
│
├── database/
│   ├── __init__.py
│   └── db.py               # All SQLite operations
│
├── templates/
│   ├── base.html           # Shared layout + navbar
│   ├── login.html          # Face scan login page
│   ├── admin_dashboard.html
│   ├── employee_dashboard.html
│   ├── add_user.html       # Face enrollment (admin only)
│   ├── manage_users.html   # Role management (admin only)
│   ├── auth_log.html       # Auth audit log (admin only)
│   └── 403.html
│
└── static/
    ├── css/
    │   └── main.css
    └── js/
        ├── main.js         # Shared utilities (toast, API helpers)
        ├── camera.js       # Webcam capture module
        ├── login.js        # Login page scan flow
        ├── enroll.js       # Multi-frame enrollment flow
        ├── manage_users.js # Role/delete interactions
        └── admin_dashboard.js
```

---

## Installation & Setup

### Prerequisites

- Python 3.8 or higher
- pip
- A webcam
- CMake + C++ compiler (needed to build dlib)

### Step 1 — Install dlib dependencies

**Ubuntu / Debian:**
```bash
sudo apt update
sudo apt install build-essential cmake python3-dev
```

**macOS (Homebrew):**
```bash
brew install cmake
```

**Windows:**
- Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
- Install [CMake](https://cmake.org/download/)

### Step 2 — Clone and install Python packages

```bash
git clone https://github.com/YOUR_USERNAME/faceguard.git
cd faceguard
pip install -r requirements.txt
```

### Step 3 — Run setup (downloads dlib model + initializes DB)

```bash
python setup.py
```

This downloads the 68-point landmark model (~100 MB) from dlib.net and initializes the database.

### Step 4 — Enroll the first admin face

```bash
python first_run.py
```

This opens a **temporary browser-based enrollment page at http://localhost:5001**:
1. Type your admin name
2. Click **Capture** — 8 frames of your face are captured automatically
3. Click **Enroll Admin** — your FLDM face encoding is saved to the DB

The setup server **shuts itself down** when enrollment is complete. Run this only once.

### Step 5 — Start the main app

```bash
python app.py
```

Open **http://localhost:5000**, look at the camera, press **Scan Face** — you'll be logged in as Admin.

---

## Quick Start (all steps)

```bash
pip install -r requirements.txt
python setup.py        # download dlib model + init DB
python first_run.py    # enroll your admin face (opens browser on port 5001)
python app.py          # start main app on port 5000
```

After that, all user management (adding employees, assigning roles) is done through the web UI.

---

## First Run Walkthrough

### Step 1 — `python setup.py`
Downloads the dlib 68-point face landmark model and creates the SQLite database.

### Step 2 — `python first_run.py`
Opens a standalone enrollment server at **http://localhost:5001**. Scan your face to create the first admin account. The server shuts itself down when done.

### Step 3 — `python app.py`
Starts the main FaceGuard app at **http://localhost:5000**. Log in with your face — you'll land on the Admin Dashboard.

### Step 4 — Add more users
From the Admin Dashboard → **Add User** to enroll employees through the browser UI. Assign roles in **Manage Users**.

---

### Re-enrolling or adding more admins

Run `first_run.py` again at any time. It will detect existing admin accounts and let you re-enroll a face or create an additional admin.

---

## API Endpoints

| Method | Endpoint | Auth Required | Description |
|--------|---------|--------------|-------------|
| POST | `/api/authenticate` | No | Submit face frame for login |
| POST | `/api/enroll` | Admin | Enroll new user with face frames |
| GET | `/api/users` | Admin | List all users |
| PATCH | `/api/users/<id>/role` | Admin | Update a user's role |
| DELETE | `/api/users/<id>` | Admin | Delete user + face data |
| DELETE | `/api/users/<id>/face` | Admin | Remove face data only |
| GET | `/api/session` | No | Check current session |

---

## FLDM Threshold Calibration

The default threshold is `D < 0.08`. You can adjust it in `fldm/fldm.py`:

```python
FLDM_THRESHOLD = 0.08   # Lower = stricter (more false rejects)
                         # Higher = looser (more false accepts)
```

| D Score | Decision |
|---------|---------|
| 0.00 – 0.04 | High-confidence match |
| 0.04 – 0.08 | Match (authenticated) |
| 0.08 – 0.15 | Near-miss — rejected |
| 0.15+ | No match |

---

## Security Limitations (Known)

1. **No liveness detection** — a photo can spoof the system
2. **No encryption of face data at rest** — FLDM encodings are plain JSON in SQLite
3. **Flask dev server** — use gunicorn/nginx for any real deployment

---

## Future Improvements

- Liveness detection (blink challenge)
- AES-256 encryption of stored face encodings
- Department-level role granularity
- Multi-session tracking
- FLDM v2: temporal consistency across 3 frames

---

## Academic Context

This project was built for the **CDS-231-FP Mini Project** unit under the **S.Y.B.Sc Cyber and Digital Science** program, Savitribai Phule Pune University (SPPU), Academic Year 2025–26.

The FLDM algorithm is an **original contribution** developed for this project. It does not wrap any library's recognition function.

---

## References

1. Kazemi & Sullivan (2014). *One millisecond face alignment with an ensemble of regression trees.* CVPR.
2. King, D.E. (2009). *Dlib-ml: A Machine Learning Toolkit.* JMLR, 10.
3. Soukupova & Cech (2016). *Real-Time Eye Blink Detection using Facial Landmarks.* CVWW.
4. OpenCV Documentation — https://docs.opencv.org
5. Flask Documentation — https://flask.palletsprojects.com