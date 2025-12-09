import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(EVENTS)')
print('Table structure:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]} ({row[2]})')
conn.close()
