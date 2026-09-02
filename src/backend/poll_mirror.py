import os, sys, time

os.environ["SYNC_ENABLED"] = "0"
sys.path.insert(0, "C:/Users/Procare/ProCare-OS/src/backend")

from sqlalchemy import create_engine, text
from app.db.base import SessionLocal

print("=" * 60)
print("POLLING estock_raw_mirror for mirror progress")
print("=" * 60)

for i in range(1, 41):
    try:
        with SessionLocal() as s:
            cnt = s.execute(text("SELECT COUNT(*) FROM estock_raw_mirror")).scalar()
            cnt = int(cnt or 0)
            tables = s.execute(
                text("SELECT source_table, COUNT(*) as cnt FROM estock_raw_mirror GROUP BY source_table ORDER BY cnt DESC")
            ).fetchall()
            print(f"\nCycle {i:2d} ({(i*15)//60}m): {cnt:>12,} rows in estock_raw_mirror")
            if tables:
                print(f"  Tables: {len(tables)}")
                for t, c in tables[:12]:
                    print(f"    {t:45s} {c:>10,}")
            if cnt >= 500000:
                print("  >> 500K+ rows — mirror well underway <<")
    except Exception as e:
        print(f"Cycle {i}: query error: {e}")
    time.sleep(15)

print(f"\n{'='*60}")
print("POLLING COMPLETE")
print(f"{'='*60}")
print(f"Final estock_raw_mirror row count will be shown above.")
