# db_helpers.py

import sqlite3
from datetime import datetime, timedelta
import os
from google.cloud import storage
import json
from utils import TESTING

# Database file path
DB_PATH = 'shared_podcasts.db'

if not TESTING:
    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

def init_db():
    """Initialize the SQLite database and create the necessary table."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS shared_podcasts (
            id TEXT PRIMARY KEY,
            gcs_audio_path TEXT NOT NULL,
            gcs_data_path TEXT NOT NULL,
            expiration_date TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# db_helpers.py

# ... (previous imports and setup) ...

def save_shared_podcast(share_id, audio_file_path, transcript):
    """Save a shared podcast to GCS and the database."""
    # Upload audio file to GCS
    audio_blob = bucket.blob(f'podcasts/{share_id}/audio.mp3')
    audio_blob.upload_from_filename(audio_file_path)
    gcs_audio_url = audio_blob.public_url

    # Save transcript and other data to GCS
    data_blob = bucket.blob(f'podcasts/{share_id}/data.json')
    data = {
        'transcript': transcript,
        'created_at': datetime.now().isoformat()
    }
    data_blob.upload_from_string(json.dumps(data), content_type='application/json')
    gcs_data_path = data_blob.name

    # Save reference to SQLite
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    expiration_date = (datetime.now() + timedelta(days=3)).isoformat()
    c.execute('''
        INSERT INTO shared_podcasts (id, gcs_audio_path, gcs_data_path, expiration_date)
        VALUES (?, ?, ?, ?)
    ''', (share_id, gcs_audio_url, gcs_data_path, expiration_date))
    conn.commit()
    conn.close()

    return gcs_audio_url

# ... (rest of the code) ...

def get_shared_podcast(share_id):
    """Retrieve a shared podcast from the database and GCS."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM shared_podcasts WHERE id = ?', (share_id,))
    podcast = c.fetchone()
    conn.close()

    if podcast:
        # Fetch data from GCS
        data_blob = bucket.blob(podcast[2])  # gcs_data_path
        data = json.loads(data_blob.download_as_text())
        
        return {
            'id': podcast[0],
            'audio_path': podcast[1],  # gcs_audio_path
            'transcript': data['transcript'],
            'expiration_date': podcast[3]
        }
    return None

def cleanup_expired_podcasts():
    """Remove expired podcasts from the database and GCS."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute('SELECT id, gcs_audio_path, gcs_data_path FROM shared_podcasts WHERE expiration_date < ?', (now,))
    expired_podcasts = c.fetchall()
    
    for podcast in expired_podcasts:
        # Delete GCS objects
        bucket.blob(f'podcasts/{podcast[0]}/audio.mp3').delete()
        bucket.blob(f'podcasts/{podcast[0]}/data.json').delete()
        
        # Delete the database entry
        c.execute('DELETE FROM shared_podcasts WHERE id = ?', (podcast[0],))
    
    conn.commit()
    conn.close()