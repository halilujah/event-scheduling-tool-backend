import sqlite3

# Connect to database
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Check if new columns exist
cursor.execute("PRAGMA table_info(EVENTS)")
columns = [row[1] for row in cursor.fetchall()]

# Add new columns if they don't exist
if 'organizerName' not in columns:
    cursor.execute("ALTER TABLE EVENTS ADD COLUMN organizerName TEXT DEFAULT 'Anonymous'")
    print("Added organizerName column")

if 'isFinalized' not in columns:
    cursor.execute("ALTER TABLE EVENTS ADD COLUMN isFinalized INTEGER DEFAULT 0")
    print("Added isFinalized column")

if 'finalizedTime' not in columns:
    cursor.execute("ALTER TABLE EVENTS ADD COLUMN finalizedTime TEXT")
    print("Added finalizedTime column")

conn.commit()
conn.close()

print("Migration completed successfully!")
