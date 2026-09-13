"""Apply ensure_arabic_columns_unicode to the configured ProCare database.

The migration also runs automatically at backend startup; this entry point
exists so it can be applied (and its progress watched) without restarting a
backend that is currently serving the pharmacy.
"""
from __future__ import annotations

import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")

from app.db.base import DATABASE_URL, engine  # noqa: E402
from app.db.migrate import ensure_arabic_columns_unicode  # noqa: E402

print("target:", DATABASE_URL.split("://")[0])
t0 = time.time()
ensure_arabic_columns_unicode(engine)
print(f"--- ensure_arabic_columns_unicode finished in {time.time() - t0:.1f}s")
