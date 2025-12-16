import sqlite3

# Connect to database
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

print("Starting database migration...\n")

# Check EVENTS table columns
cursor.execute("PRAGMA table_info(EVENTS)")
columns = [row[1] for row in cursor.fetchall()]

# Add new columns to EVENTS if they don't exist
if 'organizerName' not in columns:
    cursor.execute("ALTER TABLE EVENTS ADD COLUMN organizerName TEXT DEFAULT 'Anonymous'")
    print("✓ Added organizerName column to EVENTS")

if 'isFinalized' not in columns:
    cursor.execute("ALTER TABLE EVENTS ADD COLUMN isFinalized INTEGER DEFAULT 0")
    print("✓ Added isFinalized column to EVENTS")

if 'finalizedTime' not in columns:
    cursor.execute("ALTER TABLE EVENTS ADD COLUMN finalizedTime TEXT")
    print("✓ Added finalizedTime column to EVENTS")

# Check PARTICIPANTS table columns
cursor.execute("PRAGMA table_info(PARTICIPANTS)")
participant_columns = [row[1] for row in cursor.fetchall()]

# Add ipAddress column to PARTICIPANTS if it doesn't exist
if 'ipAddress' not in participant_columns:
    cursor.execute("ALTER TABLE PARTICIPANTS ADD COLUMN ipAddress TEXT DEFAULT '0.0.0.0'")
    print("✓ Added ipAddress column to PARTICIPANTS")

# Create BLOCKED_USERS table if it doesn't exist
cursor.execute("""CREATE TABLE IF NOT EXISTS BLOCKED_USERS (
    blockId TEXT PRIMARY KEY,
    eventId TEXT,
    ipAddress TEXT,
    participantName TEXT,
    blockedAt TEXT,
    FOREIGN KEY (eventId) REFERENCES EVENTS(eventId)
)""")
print("✓ Created/verified BLOCKED_USERS table")

conn.commit()
conn.close()

print("\n✅ Migration completed successfully!")
