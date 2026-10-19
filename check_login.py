
import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parent / "khat_seva.db"

conn = sqlite3.connect(db_path)

rows = conn.execute(
    "SELECT id, email FROM farmers"
).fetchall()

print("Registered farmers:")
for row in rows:
    print("ID:", row[0], "| Email:", row[1])

if not rows:
    print("No farmers found in this database.")

conn.close()
