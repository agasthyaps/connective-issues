import sqlite3
from datetime import datetime

DB_PATH = 'shared_podcasts.db'

def migrate_expiration_dates():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # First, add a new column for the timestamp
    c.execute('ALTER TABLE shared_podcasts ADD COLUMN expiration_timestamp REAL')
    
    # Migrate the data
    c.execute('SELECT id, expiration_date FROM shared_podcasts')
    podcasts = c.fetchall()
    for podcast in podcasts:
        try:
            old_date = datetime.fromisoformat(podcast[1])
            new_date = old_date.timestamp()
            c.execute('UPDATE shared_podcasts SET expiration_timestamp = ? WHERE id = ?', (new_date, podcast[0]))
        except ValueError:
            print(f"Error processing podcast {podcast[0]}: Invalid date format")
    
    # Update the schema to use the new column
    c.execute('ALTER TABLE shared_podcasts RENAME COLUMN expiration_date TO expiration_date_old')
    c.execute('ALTER TABLE shared_podcasts RENAME COLUMN expiration_timestamp TO expiration_date')
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate_expiration_dates()
    print("Migration completed")