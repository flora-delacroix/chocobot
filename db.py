import sqlite3, time
import bcrypt

conn = sqlite3.connect("chocobot.db", check_same_thread=False)

conn.execute("""CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    mot_de_passe_hash TEXT NOT NULL,
    allergies_encrypted TEXT,
    tranche_age TEXT,
    created_at REAL
)""")

conn.execute("""CREATE TABLE IF NOT EXISTS counters (
    category TEXT PRIMARY KEY,
    count INTEGER DEFAULT 0
)""")

conn.commit()

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hash_stored):
    return bcrypt.checkpw(password.encode(), hash_stored.encode())

def save_user(email, mot_de_passe, allergies_encrypted=None, tranche_age=None):
    mot_de_passe_hash = hash_password(mot_de_passe)
    conn.execute("""INSERT OR REPLACE INTO users (email, mot_de_passe_hash, allergies_encrypted, tranche_age, created_at)
                    VALUES (?,?,?,?,?)""",
                 (email, mot_de_passe_hash, allergies_encrypted, tranche_age, time.time()))
    conn.commit()

def get_user(email):
    row = conn.execute("SELECT mot_de_passe_hash, allergies_encrypted, tranche_age, created_at FROM users WHERE email=?",
                      (email,)).fetchone()
    return dict(zip(["mot_de_passe_hash", "allergies_encrypted", "tranche_age", "created_at"], row)) if row else None

def delete_user(email):
    conn.execute("DELETE FROM users WHERE email=?", (email,))
    conn.commit()

def increment_counter(category):
    current = conn.execute("SELECT count FROM counters WHERE category=?", (category,)).fetchone()
    if current:
        conn.execute("UPDATE counters SET count = count + 1 WHERE category=?", (category,))
    else:
        conn.execute("INSERT INTO counters (category, count) VALUES (?,?)", (category, 1))
    conn.commit()

def get_stats():
    rows = conn.execute("SELECT category, count FROM counters ORDER BY count DESC").fetchall()
    return [dict(zip(["category", "count"], r)) for r in rows]

def get_counter(category):
    row = conn.execute("SELECT count FROM counters WHERE category=?", (category,)).fetchone()
    return row[0] if row else 0