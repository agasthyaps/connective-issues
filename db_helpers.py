# db_helpers.py

import sqlite3
from datetime import datetime, timedelta
import os
from google.cloud import storage
from google.auth import default
import json
from utils import TESTING

# Database file path
DB_PATH = 'shared_podcasts.db'

if not TESTING:
    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    credentials, project = default()
    storage_client = storage.Client(credentials=credentials, project=project)


    bucket = storage_client.bucket(bucket_name)

def init_db():
    """Initialize the SQLite database and create the necessary table."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS shared_podcasts (
            id TEXT PRIMARY KEY,
            gcs_blob_name TEXT NOT NULL,
            transcript TEXT NOT NULL,
            expiration_date TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def save_shared_podcast(share_id, local_audio_path, transcript):
    """Save a shared podcast to GCS and the database."""
    # Upload audio file to GCS
    blob_name = f'podcasts/{share_id}/audio.mp3'
    audio_blob = bucket.blob(blob_name)
    audio_blob.upload_from_filename(local_audio_path)

    # Save transcript to GCS
    transcript_blob = bucket.blob(f'podcasts/{share_id}/transcript.txt')
    transcript_blob.upload_from_string(transcript)

    # Generate public URL
    public_url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"

    # Save reference to SQLite
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    expiration_date = (datetime.now() + timedelta(days=3)).isoformat()
    c.execute('''
        INSERT INTO shared_podcasts (id, gcs_blob_name, transcript, expiration_date)
        VALUES (?, ?, ?, ?)
    ''', (share_id, public_url, transcript, expiration_date))
    conn.commit()
    conn.close()

    return public_url

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
            'audio_url': podcast[1],  # This is now the public URL
            'transcript': podcast[2],
            'expiration_date': podcast[3]
        }
    return None

def cleanup_expired_podcasts():
    """Remove expired podcasts from the database and GCS."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute('SELECT id, gcs_blob_name FROM shared_podcasts WHERE expiration_date < ?', (now,))
    expired_podcasts = c.fetchall()
    
    for podcast in expired_podcasts:
        # Delete GCS objects
        bucket.blob(podcast[1]).delete()  # Delete audio file
        bucket.blob(f'podcasts/{podcast[0]}/transcript.txt').delete()
        
        # Delete the database entry
        c.execute('DELETE FROM shared_podcasts WHERE id = ?', (podcast[0],))
    
    conn.commit()
    conn.close()
