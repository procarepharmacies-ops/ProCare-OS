import os, sys

os.environ["SYNC_ENABLED"] = "0"
sys.path.insert(0, "C:/Users/Procare/ProCare-OS/src/backend")

import json, traceback, contextlib, io

stderr_capture = io.StringIO()

with contextlib.redirect_stderr(stderr_capture):
    try:
        from app.services import etl
        from app.config import settings
        from sqlalchemy import create_engine, inspect as sa_inspect, text

        print("=" * 60)
        print("100% ESTOCK MIRROR - VERIFICATION")
        print("=" * 60)

        # --- preflight ---
        p = etl.preflight()
        print("\n[1] preflight:", "OK" if p.get("ok") else "FAIL")
        print(json.dumps(p, indent=2, default=str))

        # --- what does the source DB have? ---
        url = settings.estock_sqlalchemy_url()
        src_engine = create_engine(url)
        src_conn = src_engine.connect()
        si = sa_inspect(src_engine)

        src_tables = si.get_table_names()
        covered = set(etl.COVERED_SOURCE_TABLES)
        uncovered = [t for t in src_tables if t not in covered]
        print(f"\n[2] eStock source tables: {len(src_tables)} total")
        print(f"    Covered (dedicated loaders): {len(covered)}")
        print(f"    Uncovered (will go to raw mirror): {len(uncovered)}")
        print(f"    Sample uncovered: {uncovered[:10]}")

        # --- what does ProCare DB have? ---
        from app.db.base import SessionLocal
        with SessionLocal() as dst:
            raw_cnt = dst.execute(text("SELECT COUNT(*) FROM estock_raw_mirror")).scalar()
            raw_tables = dst.execute(
                text("SELECT source_table, COUNT(*) as cnt FROM estock_raw_mirror GROUP BY source_table")
            ).fetchall()
            wm_cnt = dst.execute(text("SELECT COUNT(*) FROM estock_raw_watermark")).scalar()
            print(f"\n[3] ProCare DB state:")
            print(f"    estock_raw_mirror rows: {raw_cnt}")
            print(f"    estock_raw_watermark rows: {wm_cnt}")
            if raw_tables:
                print(f"    Tables in raw mirror: {len(raw_tables)}")
                for t, c in sorted(raw_tables, key=lambda x: -x[1])[:15]:
                    print(f"      {t:45s} {c:>10,}")

        # --- row counts for uncovered tables (using src_conn) ---
        print(f"\n[4] eStock row counts for uncovered tables (top 30 by size):")
        counts_list = []
        for t in uncovered:
            try:
                n = src_conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                counts_list.append((t, int(n or 0)))
            except Exception:
                counts_list.append((t, -1))
        for t, n in sorted(counts_list, key=lambda x: -x[1])[:30]:
            flag = "" if n >= 0 else " (ERR)"
            print(f"    {t:45s} {n:>12,}{flag}")

        # --- row counts for covered tables (verification) ---
        print(f"\n[5] eStock row counts for covered (dedicated) tables:")
        covered_counts = []
        for t in sorted(covered):
            try:
                n = src_conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                covered_counts.append((t, int(n or 0)))
            except Exception:
                covered_counts.append((t, -1))
        for t, n in sorted(covered_counts, key=lambda x: -x[1]):
            flag = "" if n >= 0 else " (ERR)"
            print(f"    {t:45s} {n:>12,}{flag}")

        src_conn.close()
        src_engine.dispose()

        # --- model check ---
        print(f"\n[6] Model definitions:")
        from app.db.models import EstockRawMirror, EstockRawWatermark
        print(f"    EstockRawMirror.__tablename__ = {EstockRawMirror.__tablename__!r}")
        print(f"    EstockRawMirror columns: {[c.name for c in EstockRawMirror.__table__.columns]}")
        print(f"    estock_raw_mirror indexes: {EstockRawMirror.__table_args__}")
        print(f"    EstockRawWatermark.__tablename__ = {EstockRawWatermark.__tablename__!r}")
        print(f"    EstockRawWatermark columns: {[c.name for c in EstockRawWatermark.__table__.columns]}")

        # --- guard check ---
        print(f"\n[7] Guard status:")
        print(f"    RAW_MIRROR env: {os.environ.get('RAW_MIRROR', 'UNSET')!r}")
        print(f"    _raw_mirror_enabled(): {etl._raw_mirror_enabled()}")
        print(f"    COVERED_SOURCE_TABLES: frozenset ({len(etl.COVERED_SOURCE_TABLES)} entries)")
        print(f"    _load_uncovered_tables exists: {hasattr(etl, '_load_uncovered_tables')}")
        import inspect as ins
        src_code = ins.getsource(etl.mirror)
        wired = '_load_uncovered_tables(insp, src, dst, counts' in src_code
        print(f"    mirror() wires _load_uncovered_tables: {'yes' if wired else 'NO'}")
        if not wired:
            for i, line in enumerate(src_code.split('\n'), 1):
                if '_load_uncovered_tables' in line:
                    print(f"    actual call: {line.strip()}")

        print(f"\n{'='*60}")
        print("VERIFICATION COMPLETE")
        print(f"{'='*60}")
        print(f"Summary:")
        print(f"  - eStock source: {len(src_tables)} tables, {len(uncovered)} uncovered")
        print(f"  - Raw mirror table exists in ProCare: {raw_cnt >= 0}")
        print(f"  - Current raw mirror rows: {raw_cnt}")
        print(f"  - Run POST /api/etl/run to populate the raw mirror")

    except Exception:
        print("EXCEPTION:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

err = stderr_capture.getvalue()
if err:
    print()
    print("=== STDERR ===")
    print(err)
