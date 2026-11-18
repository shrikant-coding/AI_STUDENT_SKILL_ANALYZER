"""SQLite persistence for student accounts and career assessments."""
import sqlite3
from pathlib import Path
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = Path(__file__).resolve().parent / "skill_analyzer.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            password_hash TEXT
        );
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            career TEXT NOT NULL,
            readiness REAL NOT NULL,
            similarity REAL NOT NULL,
            assessed_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(id)
        );
        CREATE TABLE IF NOT EXISTS assessment_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER NOT NULL,
            skill TEXT NOT NULL,
            student_level REAL NOT NULL,
            required_level REAL NOT NULL,
            gap REAL NOT NULL,
            FOREIGN KEY(assessment_id) REFERENCES assessments(id)
        );
        """)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(students)").fetchall()}
        if "password_hash" not in columns:
            conn.execute("ALTER TABLE students ADD COLUMN password_hash TEXT")


def create_account(name, email, password):
    clean_email = email.lower().strip()
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM students WHERE email=?", (clean_email,)).fetchone()
        if existing:
            raise ValueError("An account with this email already exists.")
        cur = conn.execute(
            "INSERT INTO students(name,email,created_at,password_hash) VALUES(?,?,?,?)",
            (name.strip(), clean_email, datetime.now().isoformat(timespec="seconds"), generate_password_hash(password))
        )
        return cur.lastrowid


def authenticate(email, password):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM students WHERE email=?", (email.lower().strip(),)).fetchone()
    if not row or not row["password_hash"] or not check_password_hash(row["password_hash"], password):
        return None
    return {"id": row["id"], "name": row["name"], "email": row["email"]}


def save_assessment(name, email, career, readiness, similarity, gap_df):
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM students WHERE email=?", (email.lower().strip(),)).fetchone()
        if row:
            student_id = row["id"]
            conn.execute("UPDATE students SET name=? WHERE id=?", (name.strip(), student_id))
        else:
            cur = conn.execute(
                "INSERT INTO students(name,email,created_at) VALUES(?,?,?)",
                (name.strip(), email.lower().strip(), now)
            )
            student_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO assessments(student_id,career,readiness,similarity,assessed_at) VALUES(?,?,?,?,?)",
            (student_id, career, float(readiness), float(similarity), now)
        )
        assessment_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO assessment_skills(assessment_id,skill,student_level,required_level,gap) VALUES(?,?,?,?,?)",
            [(assessment_id, r.skill, float(r.student_level), float(r.required_level), float(r.gap))
             for r in gap_df.itertuples()]
        )
    return assessment_id


def get_history(email):
    with get_connection() as conn:
        return conn.execute("""
            SELECT a.id, a.career, a.readiness, a.similarity, a.assessed_at
            FROM assessments a JOIN students s ON s.id=a.student_id
            WHERE s.email=? ORDER BY a.assessed_at DESC
        """, (email.lower().strip(),)).fetchall()
