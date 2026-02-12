import sqlite3, os

# Main DB
conn = sqlite3.connect('camarad.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("=== camarad.db ===")
for t in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM [{t[0]}]").fetchone()[0]
    print(f"  {t[0]}: {count} rows")
conn.close()

# API docs DB
conn2 = sqlite3.connect('connectors_api_docs.db')
tables2 = conn2.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("\n=== connectors_api_docs.db ===")
for t in tables2:
    count = conn2.execute(f"SELECT COUNT(*) FROM [{t[0]}]").fetchone()[0]
    print(f"  {t[0]}: {count} rows")
conns = conn2.execute("SELECT DISTINCT connector FROM api_docs ORDER BY connector").fetchall()
print(f"  Unique connectors: {len(conns)}")
for c in conns:
    cnt = conn2.execute("SELECT COUNT(*) FROM api_docs WHERE connector=?", (c[0],)).fetchone()[0]
    print(f"    {c[0]}: {cnt} docs")
conn2.close()

# Knowledge base
if os.path.exists('knowledge_base/knowledge.db'):
    conn3 = sqlite3.connect('knowledge_base/knowledge.db')
    tables3 = conn3.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    print("\n=== knowledge_base/knowledge.db ===")
    for t in tables3:
        count = conn3.execute(f"SELECT COUNT(*) FROM [{t[0]}]").fetchone()[0]
        print(f"  {t[0]}: {count} rows")
    conn3.close()

# Count test files and total tests
import glob, re
test_files = sorted(glob.glob("test_*.py"))
total = 0
print(f"\n=== Test Suites ({len(test_files)} files) ===")
for tf in test_files:
    with open(tf, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    tests = len(re.findall(r'def test_', content))
    total += tests
    print(f"  {tf}: {tests} tests")
print(f"  TOTAL: {total} tests")

# Count routes
with open("app.py", encoding="utf-8", errors="ignore") as f:
    app_content = f.read()
routes = re.findall(r'@app\.route\(', app_content)
print(f"\n=== app.py ===")
print(f"  Routes: {len(routes)}")
print(f"  Lines: {len(app_content.splitlines())}")

# Templates
for tf in sorted(glob.glob("templates/*.html")):
    with open(tf, encoding="utf-8", errors="ignore") as f:
        lines = len(f.readlines())
    print(f"  {tf}: {lines} lines")
