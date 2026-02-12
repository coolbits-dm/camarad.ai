import sqlite3

# Check api_docs database
conn = sqlite3.connect('connectors_api_docs.db')
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()
print("Tables:", tables)

for t in tables:
    tname = t[0]
    c.execute(f"PRAGMA table_info({tname})")
    cols = c.fetchall()
    print(f"\n{tname} columns:", [col[1] for col in cols])
    c.execute(f"SELECT COUNT(*) FROM {tname}")
    print(f"{tname} rows:", c.fetchone()[0])
    c.execute(f"SELECT * FROM {tname} LIMIT 2")
    for row in c.fetchall():
        print(f"  Sample: {row[:4]}...")

# Also check main camarad.db
print("\n\n=== camarad.db ===")
conn2 = sqlite3.connect('camarad.db')
c2 = conn2.cursor()
c2.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables2 = c2.fetchall()
print("Tables:", [t[0] for t in tables2])

# Check if api_docs table exists in camarad.db
for t in tables2:
    if 'api_doc' in t[0].lower() or 'chunk' in t[0].lower():
        c2.execute(f"SELECT COUNT(*) FROM {t[0]}")
        print(f"{t[0]}: {c2.fetchone()[0]} rows")
        c2.execute(f"PRAGMA table_info({t[0]})")
        print(f"  Columns: {[col[1] for col in c2.fetchall()]}")
        c2.execute(f"SELECT * FROM {t[0]} LIMIT 1")
        row = c2.fetchone()
        if row:
            print(f"  Sample: {row}")

conn.close()
conn2.close()
