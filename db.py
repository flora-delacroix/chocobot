import sqlite3, time
import bcrypt

conn = sqlite3.connect("chocobot.db", check_same_thread=False)

conn.execute("""CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    mot_de_passe_hash TEXT NOT NULL,
    allergies_encrypted TEXT,
    tranche_age TEXT,
    created_at REAL,
    last_activity REAL
)""")

conn.execute("""CREATE TABLE IF NOT EXISTS counters (
    category TEXT PRIMARY KEY,
    count INTEGER DEFAULT 0
)""")

conn.commit()

# Migration: Ajouter la colonne last_activity si elle n'existe pas
try:
    conn.execute("ALTER TABLE users ADD COLUMN last_activity REAL")
    conn.commit()
except sqlite3.OperationalError:
    pass  # La colonne existe déjà

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hash_stored):
    return bcrypt.checkpw(password.encode(), hash_stored.encode())

def save_user(email, mot_de_passe, allergies_encrypted=None, tranche_age=None):
    mot_de_passe_hash = hash_password(mot_de_passe)
    now = time.time()
    conn.execute("""INSERT OR REPLACE INTO users (email, mot_de_passe_hash, allergies_encrypted, tranche_age, created_at, last_activity)
                    VALUES (?,?,?,?,?,?)""",
                 (email, mot_de_passe_hash, allergies_encrypted, tranche_age, now, now))
    conn.commit()

def get_user(email):
    row = conn.execute("SELECT mot_de_passe_hash, allergies_encrypted, tranche_age, created_at, last_activity FROM users WHERE email=?",
                      (email,)).fetchone()
    return dict(zip(["mot_de_passe_hash", "allergies_encrypted", "tranche_age", "created_at", "last_activity"], row)) if row else None

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

def update_activity(email):
    """Met à jour last_activity pour un utilisateur (au login ou chat)."""
    conn.execute("UPDATE users SET last_activity = ? WHERE email = ?", (time.time(), email))
    conn.commit()

def update_preferences(email, allergies_encrypted=None, tranche_age=None):
    """Met à jour juste les allergies et tranche_age, sans toucher au mot de passe."""
    conn.execute("UPDATE users SET allergies_encrypted = ?, tranche_age = ? WHERE email = ?",
                 (allergies_encrypted, tranche_age, email))
    conn.commit()

def clear_allergies(email):
    """Supprime juste les allergies et la tranche d'âge, garde le compte."""
    conn.execute("UPDATE users SET allergies_encrypted = NULL, tranche_age = NULL WHERE email = ?", (email,))
    conn.commit()

def delete_inactive_users(days=365):
    """Supprime les utilisateurs inactifs depuis N jours (default: 1 an)."""
    threshold = time.time() - (days * 86400)  # 86400 secondes par jour
    conn.execute("DELETE FROM users WHERE last_activity < ?", (threshold,))
    conn.commit()