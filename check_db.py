import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute('SELECT eventId, organizerName, isFinalized, finalizedTime FROM EVENTS')
print('Events:')
for row in cursor.fetchall():
    print(f'  ID: {row[0]}, Organizer: {row[1]}, Finalized: {row[2]}, Time: {row[3]}')
conn.close()
