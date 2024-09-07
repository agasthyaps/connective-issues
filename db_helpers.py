
import sqlite3
from datetime import datetime, timedelta
import os
from google.cloud import storage
from google.auth import default
import json
import logging

# Database file path
DB_BLOB = 'shared_podcasts.db'
DB_PATH = '/tmp/shared_podcasts.db'
DB_BUCKET = os.environ.get('DB_BUCKET_NAME')

# pod bucket
bucket = os.environ.get('GCS_BUCKET_NAME')

credentials, project = default()
storage_client = storage.Client(credentials=credentials, project=project)

def create_empty_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS shared_podcasts (
            id TEXT PRIMARY KEY,
            gcs_blob_name TEXT NOT NULL,
            transcript TEXT NOT NULL,
            expiration_date REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    upload_db()

def download_db():
    storage_client = storage.Client()
    bucket = storage_client.bucket(DB_BUCKET)
    blob = bucket.blob(DB_BLOB)
    blob.download_to_filename(DB_PATH)

def upload_db():
    storage_client = storage.Client()
    bucket = storage_client.bucket(DB_BUCKET)
    blob = bucket.blob(DB_BLOB)
    blob.upload_from_filename(DB_PATH)

def init_db():
    try:
        download_db()
    except Exception as e:
        print(f"Error downloading database: {e}. Creating a new one.")
        # If download fails, we'll create a new db file locally

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS shared_podcasts (
            id TEXT PRIMARY KEY,
            gcs_blob_name TEXT NOT NULL,
            transcript TEXT NOT NULL,
            expiration_date REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

    # Always upload after initialization to ensure GCS has the latest version
    upload_db()

def save_shared_podcast(share_id, local_audio_path, transcript):
    """Save a shared podcast to GCS and the database."""
    # Upload audio file to GCS
    blob_name = f'podcasts/{share_id}/audio.mp3'
    audio_blob = bucket.blob(blob_name)
    audio_blob.upload_from_filename(local_audio_path)

    # Save transcript to GCS
    transcript_blob = bucket.blob(f'podcasts/{share_id}/transcript.txt')
    transcript_blob.upload_from_string(transcript)

    # Save reference to SQLite
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    expiration_date = (datetime.now() + timedelta(days=3)).timestamp()
    c.execute('''
        INSERT INTO shared_podcasts (id, gcs_blob_name, transcript, expiration_date)
        VALUES (?, ?, ?, ?)
    ''', (share_id, blob_name, transcript, expiration_date))
    conn.commit()
    conn.close()
    upload_db()

    return blob_name

def get_shared_podcast(share_id):
    """Retrieve a shared podcast from the database or directly from GCS."""
    # First, try to get the podcast from the database
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM shared_podcasts WHERE id = ?', (share_id,))
    podcast = c.fetchone()
    conn.close()

    if podcast:
        logging.info(f"Retrieved podcast with ID: {share_id} from database")
        return {
            'id': podcast[0],
            'gcs_blob_name': podcast[1],
            'transcript': podcast[2],
            'expiration_date': float(podcast[3])
        }
    
    # If not found in the database, try to retrieve directly from GCS
    try:
        bucket_for_pods = storage_client.bucket(bucket)
        
        # Check if the audio file exists
        audio_blob = bucket_for_pods.blob(f'podcasts/{share_id}/audio.mp3')
        if not audio_blob.exists():
            raise FileNotFoundError

        # Retrieve the transcript
        transcript_blob = bucket_for_pods.blob(f'podcasts/{share_id}/transcript.txt')
        transcript = transcript_blob.download_as_text()

        # Set an expiration date (3 days from now) for consistency
        expiration_date = (datetime.now() + timedelta(days=3)).timestamp()

        logging.info(f"Retrieved podcast with ID: {share_id} from GCS")
        return {
            'id': share_id,
            'gcs_blob_name': f'podcasts/{share_id}/audio.mp3',
            'transcript': transcript,
            'expiration_date': expiration_date
        }

    except Exception as e:
        logging.error(f"Podcast with ID {share_id} not found in database or GCS. Error: {str(e)}")
        return None

def cleanup_expired_podcasts():
    """Remove expired podcasts from the database and GCS."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().timestamp()
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
    upload_db()
