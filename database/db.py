"""
database/db.py
==============
All database operations for FaceGuard.
Uses SQLite3 — no server required, fully local/offline.
"""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "faceguard.db")


# ──────────────────────────────────────────────────────────────────────────────
# INIT
# ──────────────────────────────────────────────────────────────────────────────

def init_db():
    """Create tables if they don't exist. Call once on app startup."""
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            role        TEXT    NOT NULL DEFAULT 'employee',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS face_data (
            user_id     INTEGER PRIMARY KEY,
            encoding    TEXT    NOT NULL,
            enrolled_at TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS auth_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            score       REAL,
            success     INTEGER,
            attempted_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    conn.commit()
    conn.close()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ──────────────────────────────────────────────────────────────────────────────
# USER OPERATIONS
# ──────────────────────────────────────────────────────────────────────────────

def add_user(name: str, role: str = "employee") -> int:
    """
    Insert a new user. Returns the new user's ID.
    Role must be 'admin' or 'employee'.
    """
    if role not in ("admin", "employee"):
        raise ValueError(f"Invalid role: {role}. Must be 'admin' or 'employee'.")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (name, role) VALUES (?, ?)", (name, role))
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return user_id


def get_all_users():
    """Return all users as a list of dicts."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, role, created_at FROM users ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_by_id(user_id: int):
    """Return a single user dict, or None if not found."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id, name, role, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_role(user_id: int, new_role: str):
    """Update the role of an existing user."""
    if new_role not in ("admin", "employee"):
        raise ValueError(f"Invalid role: {new_role}")
    conn = get_conn()
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    conn.commit()
    conn.close()


def delete_user(user_id: int):
    """Delete a user and their face data (cascade)."""
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def user_has_face(user_id: int) -> bool:
    """Check if a user has an enrolled face encoding."""
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM face_data WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row is not None


# ──────────────────────────────────────────────────────────────────────────────
# FACE DATA OPERATIONS
# ──────────────────────────────────────────────────────────────────────────────

def save_face_encoding(user_id: int, encoding: dict):
    """
    Save or replace a user's FLDM face encoding.
    encoding is a dict with keys: EAR, NBR, MWR, JAR, BRR
    """
    conn = get_conn()
    conn.execute(
        """INSERT INTO face_data (user_id, encoding)
           VALUES (?, ?)
           ON CONFLICT(user_id) DO UPDATE SET encoding = excluded.encoding,
                                              enrolled_at = datetime('now')""",
        (user_id, json.dumps(encoding))
    )
    conn.commit()
    conn.close()


def get_all_face_encodings() -> dict:
    """
    Load all stored face encodings from DB.
    Returns { user_id (int): encoding (dict) }
    Used by the authentication pipeline.
    """
    conn = get_conn()
    rows = conn.execute("SELECT user_id, encoding FROM face_data").fetchall()
    conn.close()
    return {row["user_id"]: json.loads(row["encoding"]) for row in rows}


def delete_face_encoding(user_id: int):
    """Remove a user's face data without deleting the user."""
    conn = get_conn()
    conn.execute("DELETE FROM face_data WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# AUTH LOG
# ──────────────────────────────────────────────────────────────────────────────

def log_auth_attempt(user_id, score: float, success: bool):
    """Log every authentication attempt for audit trail."""
    conn = get_conn()
    conn.execute(
        "INSERT INTO auth_log (user_id, score, success) VALUES (?, ?, ?)",
        (user_id, round(score, 6), 1 if success else 0)
    )
    conn.commit()
    conn.close()


def get_auth_log(limit: int = 50):
    """Return recent auth log entries."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT al.id, u.name, al.score, al.success, al.attempted_at
           FROM auth_log al
           LEFT JOIN users u ON al.user_id = u.id
           ORDER BY al.id DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
