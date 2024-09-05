# db_helpers.py

import sqlite3
from datetime import datetime, timedelta
import os

# Database file path
DB_PATH = 'shared_podcasts.db'

def init_db():
    """Initialize the SQLite database and create the necessary table."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS shared_podcasts (
            id TEXT PRIMARY KEY,
            audio_path TEXT NOT NULL,
            transcript TEXT NOT NULL,
            expiration_date TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def save_shared_podcast(share_id, audio_path, transcript):
    """Save a shared podcast to the database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    expiration_date = (datetime.now() + timedelta(days=3)).isoformat()
    c.execute('''
        INSERT INTO shared_podcasts (id, audio_path, transcript, expiration_date)
        VALUES (?, ?, ?, ?)
    ''', (share_id, audio_path, transcript, expiration_date))
    conn.commit()
    conn.close()

def get_shared_podcast(share_id):
    """Retrieve a shared podcast from the database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM shared_podcasts WHERE id = ?', (share_id,))
    podcast = c.fetchone()
    conn.close()
    if podcast:
        return {
            'id': podcast[0],
            'audio_path': podcast[1],
            'transcript': podcast[2],
            'expiration_date': podcast[3]
        }
    return None

def cleanup_expired_podcasts():
    """Remove expired podcasts from the database and delete associated files."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute('SELECT id, audio_path FROM shared_podcasts WHERE expiration_date < ?', (now,))
    expired_podcasts = c.fetchall()
    
    for podcast in expired_podcasts:
        # Delete the audio file
        if os.path.exists(podcast[1]):
            os.remove(podcast[1])
        
        # Delete the database entry
        c.execute('DELETE FROM shared_podcasts WHERE id = ?', (podcast[0],))
    
    conn.commit()
    conn.close()