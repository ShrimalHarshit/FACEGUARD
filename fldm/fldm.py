"""
FLDM — Facial Landmark Deviation Metric
========================================
A custom face verification algorithm designed for FaceGuard.
Developed as an original contribution for the mini-project.

This module does NOT use any library's built-in face recognition function.
It computes a geometric deviation score from the spatial relationships
of 68 detected dlib facial landmarks across 5 facial zones.

Author: FaceGuard Mini Project
"""

import numpy as np


# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

FLDM_THRESHOLD = 0.08
"""
Empirically calibrated threshold.
D < THRESHOLD  →  faces match (same person)
D >= THRESHOLD →  faces do not match (different person)
"""

ZONE_WEIGHTS = {
    "EAR": 1.2,   # Eye Aspect Ratio — good discriminator
    "NBR": 1.0,   # Nose Bridge Ratio
    "MWR": 1.1,   # Mouth Width Ratio
    "JAR": 0.9,   # Jaw Angle Ratio — can vary with expression
    "BRR": 0.8,   # Brow Raise Ratio — expression-sensitive
}


# ──────────────────────────────────────────────────────────────────────────────
# HELPER UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

def _euclidean(p1, p2):
    """Euclidean distance between two 2D points."""
    return np.linalg.norm(np.array(p1) - np.array(p2))


def _center(points):
    """Centroid of a list of (x, y) points."""
    return np.mean(points, axis=0)


def _landmarks_to_array(landmarks):
    """
    Convert dlib full_object_detection to a (68, 2) numpy array.
    Each row is (x, y) for one landmark point.
    """
    return np.array([(landmarks.part(i).x, landmarks.part(i).y) for i in range(68)], dtype=float)


# ──────────────────────────────────────────────────────────────────────────────
# ZONE RATIO COMPUTATIONS
# ──────────────────────────────────────────────────────────────────────────────

def _eye_aspect_ratio(pts, start, end):
    """
    Eye Aspect Ratio (EAR) for one eye.
    EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
    Points: p1=corner_left, p2-p3=upper, p4=corner_right, p5-p6=lower
    """
    eye = pts[start:end + 1]
    vertical = _euclidean(eye[1], eye[5]) + _euclidean(eye[2], eye[4])
    horizontal = _euclidean(eye[0], eye[3])
    return vertical / (2.0 * horizontal + 1e-6)


def _compute_ear(pts):
    """Average EAR across both eyes."""
    right_ear = _eye_aspect_ratio(pts, 36, 41)
    left_ear  = _eye_aspect_ratio(pts, 42, 47)
    return (right_ear + left_ear) / 2.0


def _compute_nbr(pts, ipd):
    """
    Nose Bridge Ratio: height of nose bridge relative to IPD.
    Nose bridge: landmarks 27 (bridge top) to 30 (tip top).
    """
    bridge_height = _euclidean(pts[27], pts[30])
    return bridge_height / (ipd + 1e-6)


def _compute_mwr(pts, ipd):
    """
    Mouth Width Ratio: outer mouth width relative to IPD.
    Landmarks 48 (left corner) and 54 (right corner).
    """
    mouth_width = _euclidean(pts[48], pts[54])
    return mouth_width / (ipd + 1e-6)


def _compute_jar(pts):
    """
    Jaw Angle Ratio: jaw width at widest point vs face height.
    Jaw width: pt[0] to pt[16]
    Face height: chin (pt[8]) to midpoint of jaw line top.
    """
    jaw_width  = _euclidean(pts[0], pts[16])
    jaw_top    = (pts[0] + pts[16]) / 2.0
    face_height = _euclidean(pts[8], jaw_top)
    return jaw_width / (face_height + 1e-6)


def _compute_brr(pts, ipd):
    """
    Brow Raise Ratio: average brow height above eye center relative to IPD.
    Brows: 17-26. Eye centers computed from 36-41, 42-47.
    """
    right_brow_center = _center(pts[17:22])
    left_brow_center  = _center(pts[22:27])
    right_eye_center  = _center(pts[36:42])
    left_eye_center   = _center(pts[42:48])

    right_raise = right_eye_center[1] - right_brow_center[1]  # positive = brow above eye
    left_raise  = left_eye_center[1]  - left_brow_center[1]
    avg_raise   = (right_raise + left_raise) / 2.0
    return avg_raise / (ipd + 1e-6)


# ──────────────────────────────────────────────────────────────────────────────
# CORE PUBLIC API
# ──────────────────────────────────────────────────────────────────────────────

def compute_fldm_encoding(landmarks):
    """
    Compute an FLDM encoding from a dlib shape prediction object.

    The encoding is a dict of 5 zone ratios derived from 68 facial landmarks.
    These ratios are scale-invariant (normalized by inter-pupil distance).

    Parameters
    ----------
    landmarks : dlib.full_object_detection
        68-point shape prediction from dlib's shape predictor.

    Returns
    -------
    dict  with keys: EAR, NBR, MWR, JAR, BRR
    """
    pts = _landmarks_to_array(landmarks)

    # Inter-pupil distance: used for normalization
    right_eye_center = _center(pts[36:42])
    left_eye_center  = _center(pts[42:48])
    ipd = _euclidean(right_eye_center, left_eye_center)

    return {
        "EAR": float(_compute_ear(pts)),
        "NBR": float(_compute_nbr(pts, ipd)),
        "MWR": float(_compute_mwr(pts, ipd)),
        "JAR": float(_compute_jar(pts)),
        "BRR": float(_compute_brr(pts, ipd)),
    }


def fldm_deviation_score(enc_stored, enc_live):
    """
    Compute FLDM deviation score D between two encodings.

    Formula (weighted normalized MAD):
        D = Σ [ w_i * |enc_stored[i] - enc_live[i]| / max(enc_stored[i], enc_live[i]) ]
            / Σ w_i

    Parameters
    ----------
    enc_stored : dict   — stored encoding from DB
    enc_live   : dict   — live encoding from current frame

    Returns
    -------
    float — deviation score (lower = more similar)
    """
    total_weight = sum(ZONE_WEIGHTS.values())
    weighted_sum = 0.0

    for zone, weight in ZONE_WEIGHTS.items():
        s = abs(enc_stored.get(zone, 0))
        l = abs(enc_live.get(zone, 0))
        denom = max(s, l, 1e-6)
        weighted_sum += weight * (abs(s - l) / denom)

    return weighted_sum / total_weight


def authenticate_against_db(live_encoding, stored_users):
    """
    Find the best-matching user from a dict of stored encodings.

    Parameters
    ----------
    live_encoding : dict
        FLDM encoding computed from the current live frame.
    stored_users : dict
        { user_id (int): encoding (dict) }

    Returns
    -------
    tuple: (user_id or None, best_score float)
        user_id is None if no match found within threshold.
    """
    best_score = float("inf")
    best_user  = None

    for user_id, enc in stored_users.items():
        score = fldm_deviation_score(enc, live_encoding)
        if score < best_score:
            best_score = score
            best_user  = user_id

    if best_score < FLDM_THRESHOLD:
        return best_user, best_score

    return None, best_score


def average_encodings(encoding_list):
    """
    Average a list of FLDM encodings (from multiple frames during enrollment).

    Parameters
    ----------
    encoding_list : list of dict

    Returns
    -------
    dict — averaged encoding
    """
    if not encoding_list:
        raise ValueError("Cannot average empty encoding list")

    keys = list(ZONE_WEIGHTS.keys())
    averaged = {}
    for key in keys:
        averaged[key] = float(np.mean([enc[key] for enc in encoding_list]))
    return averaged
