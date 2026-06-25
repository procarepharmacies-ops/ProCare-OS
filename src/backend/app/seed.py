"""Deterministic demo-data generator for the ProCare OS shadow database.

Produces realistic, internally-consistent synthetic data for two branches
(Main + Elsanta) so the dashboard, alerts, AI assistant and reconciliation all
have something true to compute over — without touching any live system. The
data is shaped to exercise every KPI: today/month revenue, expiring-soon
batches, low stock, over-limit debtors, vendor payables, FEFO, returns, profit.

Seeded with a fixed RNG so runs are reproducible. This stands in for the
Phase-1 ETL mirror until real eStock credentials are provided (see etl.py).
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta

from app.db import get_db

RNG_SEED = 42

# (name_en, name_ar, scientific_name, group_key, base_sell, is_controlled)
PRODUCTS = [
    ("Panadol 500mg", "بنادول ٥٠٠", "paracetamol", "analgesic", 15.0, 0),
    ("Panadol Extra", "بنادول إكسترا", "paracetamol+caffeine", "analgesic", 22.0, 0),
    ("Brufen 400mg", "بروفين ٤٠٠", "ibuprofen", "analgesic", 28.0, 0),
    ("Cataflam 50mg", "كتافلام ٥٠", "diclofenac", "analgesic", 31.0, 0),
    ("Voltaren 75mg", "فولتارين ٧٥", "diclofenac", "analgesic", 45.0, 0),
    ("Augmentin 1g", "أوجمنتين ١جم", "amoxicillin+clavulanate", "antibiotic", 95.0, 0),
    ("Augmentin 625mg", "أوجمنتين ٦٢٥", "amoxicillin+clavulanate", "antibiotic", 72.0, 0),
    ("Zithromax 500mg", "زيثروماكس ٥٠٠", "azithromycin", "antibiotic", 110.0, 0),
    ("Ciprofloxacin 500", "سيبروفلوكساسين", "ciprofloxacin", "antibiotic", 48.0, 0),
    ("Flagyl 500mg", "فلاجيل ٥٠٠", "metronidazole", "antibiotic", 26.0, 0),
    ("Concor 5mg", "كونكور ٥", "bisoprolol", "cardio", 60.0, 0),
    ("Concor 10mg", "كونكور ١٠", "bisoprolol", "cardio", 88.0, 0),
    ("Capoten 25mg", "كابوتين ٢٥", "captopril", "cardio", 18.0, 0),
    ("Norvasc 5mg", "نورفاسك ٥", "amlodipine", "cardio", 54.0, 0),
    ("Aspocid 75mg", "أسبوسيد ٧٥", "aspirin", "cardio", 9.0, 0),
    ("Plavix 75mg", "بلافيكس ٧٥", "clopidogrel", "cardio", 175.0, 0),
    ("Marevan 5mg", "ماريفان ٥", "warfarin", "cardio", 40.0, 0),
    ("Glucophage 1000", "جلوكوفاج ١٠٠٠", "metformin", "diabetes", 35.0, 0),
    ("Amaryl 2mg", "أماريل ٢", "glimepiride", "diabetes", 65.0, 0),
    ("Januvia 100mg", "جانوفيا ١٠٠", "sitagliptin", "diabetes", 240.0, 0),
    ("Lantus SoloStar", "لانتوس", "insulin glargine", "diabetes", 320.0, 0),
    ("Nexium 40mg", "نكسيوم ٤٠", "esomeprazole", "gastro", 130.0, 0),
    ("Controloc 40mg", "كونترولوك ٤٠", "pantoprazole", "gastro", 85.0, 0),
    ("Gaviscon Liquid", "جافيسكون", "alginate", "gastro", 55.0, 0),
    ("Buscopan 10mg", "بوسكوبان", "hyoscine", "gastro", 24.0, 0),
    ("Antinal", "أنتينال", "nifuroxazide", "gastro", 30.0, 0),
    ("Claritine 10mg", "كلاريتين ١٠", "loratadine", "allergy", 42.0, 0),
    ("Telfast 180mg", "تلفاست ١٨٠", "fexofenadine", "allergy", 58.0, 0),
    ("Ventolin Inhaler", "فينتولين بخاخ", "salbutamol", "respiratory", 28.0, 0),
    ("Symbicort", "سيمبيكورت", "budesonide+formoterol", "respiratory", 195.0, 0),
    ("Augmentin Syrup", "أوجمنتين شراب", "amoxicillin+clavulanate", "antibiotic", 60.0, 0),
    ("Vitamin C 1000", "فيتامين سي ١٠٠٠", "ascorbic acid", "supplement", 38.0, 0),
    ("Cal-Mag", "كال-ماج", "calcium+magnesium", "supplement", 70.0, 0),
    ("Omega 3 Plus", "أوميجا ٣", "fish oil", "supplement", 120.0, 0),
    ("Centrum", "سنتروم", "multivitamin", "supplement", 160.0, 0),
    ("Tramadol 50mg", "ترامادول ٥٠", "tramadol", "analgesic", 20.0, 1),
    ("Lyrica 75mg", "ليريكا ٧٥", "pregabalin", "neuro", 140.0, 1),
    ("Xanax 0.5mg", "زاناكس", "alprazolam", "neuro", 35.0, 1),
    ("Prozac 20mg", "بروزاك ٢٠", "fluoxetine", "neuro", 48.0, 0),
    ("Insulin Mixtard", "انسولين ميكستارد", "insulin", "diabetes", 95.0, 0),
]

GROUPS = {
    "analgesic": ("مسكنات", "Analgesics"),
    "antibiotic": ("مضادات حيوية", "Antibiotics"),
    "cardio": ("أدوية القلب", "Cardiovascular"),
    "diabetes": ("أدوية السكر", "Diabetes"),
    "gastro": ("الجهاز الهضمي", "Gastro"),
    "allergy": ("الحساسية", "Allergy"),
    "respiratory": ("الجهاز التنفسي", "Respiratory"),
    "supplement": ("مكملات غذائية", "Supplements"),
    "neuro": ("أدوية الأعصاب", "Neuro"),
}

COMPANIES = [
    ("جلاكسو سميث كلاين", "GSK"),
    ("نوفارتس", "Novartis"),
    ("فايزر", "Pfizer"),
    ("سانوفي", "Sanofi"),
    ("الحكمة فارما", "Hikma"),
    ("إيبيكو", "EIPICO"),
    ("أمون فارما", "Amoun"),
    ("فاركو", "Pharco"),
]

VENDORS = [
    ("شركة المهن الطبية", "Medical Professions Co."),
    ("ابن سينا فارما", "Ibn Sina Pharma"),
    ("يونايتد للأدوية", "United Pharma"),
    ("النيل للأدوية", "Nile Drugstore"),
    ("الإسكندرية للأدوية", "Alex Pharma"),
    ("فاركو للتوزيع", "Pharco Distribution"),
]

FIRST_NAMES = ["أحمد", "محمد", "محمود", "مصطفى", "علي", "حسن", "خالد", "عمر",
               "سارة", "منى", "هدى", "نورا", "ياسمين", "فاطمة", "مريم", "آية"]
LAST_NAMES = ["عبدالله", "السيد", "إبراهيم", "حسين", "فؤاد", "رمضان", "شعبان",
              "عبدالعزيز", "صلاح", "كمال", "زكي", "فتحي"]

UNITS = [("علبة", "box"), ("شريط", "strip"), ("قرص", "tablet")]


def _hash(pw: str) -> str:
    return "sha256$" + hashlib.sha256(pw.encode()).hexdigest()


def seed(reset: bool = True) -> dict:
    """(Re)build the demo database. Returns a small summary dict."""
    db = get_db()
    if db.mode != "demo":
        raise RuntimeError("seed() only runs against the demo SQLite database")

    if reset and db.demo_db_exists():
        db._sqlite_path.unlink()
    db.apply_schema()

    rng = random.Random(RNG_SEED)
    conn = db.connection()
    today = date.today()
    summary = {}
    try:
        cur = conn.cursor()

        # -- branches ---------------------------------------------------------
        cur.executemany(
            "INSERT INTO branches (code, name_ar, name_en, is_pilot) VALUES (?,?,?,?)",
            [("MAIN", "الرئيسي", "Main", 0), ("ELSANTA", "السنتا", "Elsanta", 1)],
        )
        branch_ids = [r[0] for r in cur.execute("SELECT branch_id FROM branches ORDER BY branch_id")]

        # -- lookups ----------------------------------------------------------
        cur.executemany("INSERT INTO units (name_ar, name_en) VALUES (?,?)", UNITS)
        cur.executemany("INSERT INTO companies (name_ar, name_en) VALUES (?,?)", COMPANIES)
        cur.executemany(
            "INSERT INTO sale_classes (name_ar, name_en) VALUES (?,?)",
            [("نقدي", "Cash"), ("آجل", "Credit")],
        )
        cur.executemany(
            "INSERT INTO customer_classes (name_ar, name_en) VALUES (?,?)",
            [("تجزئة", "Retail"), ("جملة", "Wholesale")],
        )
        group_keys = list(GROUPS.keys())
        cur.executemany(
            "INSERT INTO product_groups (name_ar, name_en) VALUES (?,?)",
            [GROUPS[k] for k in group_keys],
        )
        group_id_by_key = {
            k: i + 1 for i, k in enumerate(group_keys)
        }
        company_count = len(COMPANIES)

        # -- products ---------------------------------------------------------
        product_rows = []
        for idx, (en, ar, sci, gkey, sell, controlled) in enumerate(PRODUCTS):
            buy = round(sell * rng.uniform(0.55, 0.78), 2)
            min_stock = rng.choice([10, 15, 20, 25, 30])
            product_rows.append((
                f"P{1000 + idx}", ar, en, sci,
                rng.randint(1, company_count),
                group_id_by_key[gkey],
                1, 2, 3,                       # unit ids box/strip/tablet
                controlled, 1, 0,
                sell, buy, round(sell * 0.14, 2), min_stock,
            ))
        cur.executemany(
            """INSERT INTO products
               (code, name_ar, name_en, scientific_name, company_id, group_id,
                unit1_id, unit2_id, unit3_id, is_controlled, has_expiry,
                allow_sale_zero, sell_price, buy_price, tax_price, min_stock)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            product_rows,
        )
        products = [dict(zip(
            ["product_id", "sell_price", "buy_price", "min_stock", "scientific_name"],
            (r[0], r[1], r[2], r[3], r[4]),
        )) for r in cur.execute(
            "SELECT product_id, sell_price, buy_price, min_stock, scientific_name FROM products"
        )]

        # barcodes (one per product)
        cur.executemany(
            "INSERT INTO product_barcodes (product_id, barcode, unit_id) VALUES (?,?,?)",
            [(p["product_id"], f"622{p['product_id']:07d}", 1) for p in products],
        )

        # -- vendors ----------------------------------------------------------
        cur.executemany(
            "INSERT INTO vendors (name_ar, name_en, mobile, credit_limit, current_balance) VALUES (?,?,?,?,?)",
            [(ar, en, f"010{rng.randint(10000000, 99999999)}",
              rng.choice([50000, 80000, 120000]),
              round(rng.uniform(2000, 45000), 2)) for ar, en in VENDORS],
        )
        vendor_ids = [r[0] for r in cur.execute("SELECT vendor_id FROM vendors")]

        # -- employees (cashiers per branch) ---------------------------------
        cur.executemany("INSERT INTO jobs (name_ar, name_en) VALUES (?,?)",
                        [("صيدلي", "Pharmacist"), ("كاشير", "Cashier"), ("مدير", "Manager")])
        emp_rows = []
        emp_names = [("هبة سمير", "Heba Samir"), ("كريم فؤاد", "Karim Fouad"),
                     ("نادية حسن", "Nadia Hassan"), ("طارق منير", "Tarek Mounir"),
                     ("سلمى عادل", "Salma Adel"), ("وليد جمال", "Walid Gamal")]
        for i, (ar, en) in enumerate(emp_names):
            br = branch_ids[i % 2]
            emp_rows.append((ar, en, f"cashier{i+1}", _hash("changeme"),
                             2, br, rng.choice([4500, 5200, 6000]),
                             1, 0, 1, 1, 1, 1))
        cur.executemany(
            """INSERT INTO employees
               (name_ar, name_en, username, password_hash, job_id, branch_id,
                basic_salary, can_see_buy_price, can_void, can_return,
                can_sale_credit, is_active, can_change_shift)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            emp_rows,
        )
        cashiers = {br: [] for br in branch_ids}
        for eid, br in cur.execute("SELECT employee_id, branch_id FROM employees"):
            cashiers[br].append(eid)

        # -- customers (some over their credit limit) ------------------------
        cust_rows = []
        n_cust = 45
        for i in range(n_cust):
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            limit = rng.choice([0, 1000, 2000, 3000, 5000])
            # ~15% of credit customers pushed over their limit (mirrors eStock)
            if limit and rng.random() < 0.30:
                balance = round(limit * rng.uniform(1.05, 1.8), 2)
            elif limit:
                balance = round(limit * rng.uniform(0.0, 0.9), 2)
            else:
                balance = 0.0
            cust_rows.append((name, name, f"011{rng.randint(10000000, 99999999)}",
                              1 if rng.random() < 0.8 else 2, limit, balance))
        cur.executemany(
            """INSERT INTO customers
               (name_ar, name_en, mobile, customer_class_id, credit_limit, current_balance)
               VALUES (?,?,?,?,?,?)""",
            cust_rows,
        )
        credit_customers = [r[0] for r in cur.execute(
            "SELECT customer_id FROM customers WHERE credit_limit > 0")]

        # -- stock batches (varied expiry: fresh, near-expiry, expired-only) --
        batch_rows = []
        for p in products:
            for br in branch_ids:
                n_batches = rng.randint(1, 3)
                # decide a stock profile
                roll = rng.random()
                for b in range(n_batches):
                    if roll < 0.12:           # low stock product
                        amount = rng.randint(0, int(p["min_stock"]))
                    else:
                        amount = rng.randint(20, 220)
                    # expiry profile
                    er = rng.random()
                    if er < 0.06:             # already expired (still on hand)
                        exp = today - timedelta(days=rng.randint(5, 120))
                    elif er < 0.20:           # expiring within 30 days
                        exp = today + timedelta(days=rng.randint(3, 30))
                    elif er < 0.38:           # expiring within 90 days
                        exp = today + timedelta(days=rng.randint(31, 90))
                    else:                     # healthy
                        exp = today + timedelta(days=rng.randint(120, 720))
                    buy = round(p["buy_price"] * rng.uniform(0.95, 1.05), 2)
                    sell = round(p["sell_price"] * rng.uniform(0.98, 1.02), 2)
                    batch_rows.append((p["product_id"], br, rng.choice(vendor_ids),
                                       float(amount), buy, sell, round(sell * 0.14, 2),
                                       exp.isoformat()))
        cur.executemany(
            """INSERT INTO stock_batches
               (product_id, branch_id, vendor_id, amount, buy_price, sell_price, tax_price, exp_date)
               VALUES (?,?,?,?,?,?,?,?)""",
            batch_rows,
        )
        # index live batches per (product, branch) for FEFO sale picking
        live_batches = {}
        for bid, pid, br, amount, buy, sell, exp in cur.execute(
            "SELECT batch_id, product_id, branch_id, amount, buy_price, sell_price, exp_date FROM stock_batches"
        ):
            live_batches.setdefault((pid, br), []).append(
                {"batch_id": bid, "amount": amount, "buy": buy, "sell": sell, "exp": exp})
        for key in live_batches:
            live_batches[key].sort(key=lambda b: b["exp"])  # FEFO

        # -- sales + lines over ~95 days -------------------------------------
        sale_rows, line_rows, ledger_rows = [], [], []
        sale_id = 0
        line_id = 0
        product_by_id = {p["product_id"]: p for p in products}
        for day_offset in range(95, -1, -1):
            day = today - timedelta(days=day_offset)
            weekday = day.weekday()
            base = 22 if weekday < 5 else 30          # busier weekends
            for br in branch_ids:
                n_bills = rng.randint(base - 8, base + 8)
                if br == branch_ids[1]:
                    n_bills = int(n_bills * 0.6)       # Elsanta smaller
                for _ in range(n_bills):
                    sale_id += 1
                    hour = rng.choices(
                        [9, 10, 11, 12, 13, 16, 17, 18, 19, 20, 21],
                        weights=[3, 5, 7, 6, 5, 6, 8, 9, 8, 6, 4])[0]
                    minute = rng.randint(0, 59)
                    ts = datetime(day.year, day.month, day.day, hour, minute).isoformat(sep=" ")
                    is_return = 1 if rng.random() < 0.03 else 0
                    is_credit = 1 if (credit_customers and rng.random() < 0.12) else 0
                    customer_id = rng.choice(credit_customers) if is_credit else None
                    cashier = rng.choice(cashiers[br])

                    n_lines = rng.choices([1, 2, 3, 4], weights=[5, 4, 2, 1])[0]
                    chosen = rng.sample(products, k=min(n_lines, len(products)))
                    gross = 0.0
                    net = 0.0
                    these_lines = []
                    for p in chosen:
                        qty = rng.choices([1, 2, 3], weights=[6, 3, 1])[0]
                        batches = live_batches.get((p["product_id"], br), [])
                        batch = batches[0] if batches else None
                        sell = batch["sell"] if batch else p["sell_price"]
                        buy = batch["buy"] if batch else p["buy_price"]
                        disc = round(sell * qty * rng.choice([0, 0, 0, 0.05]), 2)
                        total = round(sell * qty - disc, 2)
                        gross += round(sell * qty, 2)
                        net += total
                        line_id += 1
                        these_lines.append((sale_id, p["product_id"],
                                            batch["batch_id"] if batch else None,
                                            float(qty), sell, buy, disc, total, is_return))
                    discount = round(gross - net, 2)
                    cash = 0.0 if is_credit else net
                    card = 0.0
                    sale_rows.append((sale_id, br, customer_id, cashier, None,
                                      2 if is_credit else 1, ts, gross, discount, net,
                                      cash, card, 0.0, is_return, is_credit))
                    line_rows.extend(these_lines)
                    # ledger: cash desk gets the cash; credit sale debits the customer
                    if is_credit and customer_id:
                        ledger_rows.append((br, ts, "customer", customer_id, "sale", sale_id, net, 0.0))
                    else:
                        ledger_rows.append((br, ts, "cash", br, "sale", sale_id, net, 0.0))

        cur.executemany(
            """INSERT INTO sales
               (sale_id, branch_id, customer_id, cashier_id, delivery_man_id,
                sale_class_id, sale_date, total_gross, total_discount, total_net,
                cash_paid, card_paid, change_given, is_return, is_credit)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            sale_rows,
        )
        cur.executemany(
            """INSERT INTO sale_lines
               (sale_id, product_id, batch_id, amount, sell_price, buy_price, disc_money, total_sell, is_return)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            line_rows,
        )
        cur.executemany(
            """INSERT INTO ledger_entries
               (branch_id, entry_date, account_type, account_ref, ref_type, ref_id, debit, credit)
               VALUES (?,?,?,?,?,?,?,?)""",
            ledger_rows,
        )

        # -- a few purchases (vendor payables provenance) --------------------
        purch_rows, purch_line_rows = [], []
        purchase_id = 0
        for _ in range(20):
            purchase_id += 1
            br = rng.choice(branch_ids)
            vendor = rng.choice(vendor_ids)
            bill_day = today - timedelta(days=rng.randint(1, 90))
            chosen = rng.sample(products, k=rng.randint(3, 8))
            gross = 0.0
            plines = []
            for p in chosen:
                qty = rng.randint(20, 100)
                buy = p["buy_price"]
                gross += round(buy * qty, 2)
                plines.append((purchase_id, p["product_id"], None, float(qty),
                               float(rng.choice([0, 0, 5, 10])), buy, p["sell_price"],
                               (today + timedelta(days=rng.randint(200, 700))).isoformat()))
            purch_rows.append((purchase_id, br, vendor, bill_day.isoformat(),
                               f"INV-{rng.randint(10000,99999)}", gross, 0.0,
                               round(gross * 0.14, 2), 0.0))
            purch_line_rows.extend(plines)
        cur.executemany(
            """INSERT INTO purchases
               (purchase_id, branch_id, vendor_id, bill_date, bill_number,
                total_gross, total_discount, total_tax, other_expenses)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            purch_rows,
        )
        cur.executemany(
            """INSERT INTO purchase_lines
               (purchase_id, product_id, batch_id, amount, bonus, buy_price, sell_price, exp_date)
               VALUES (?,?,?,?,?,?,?,?)""",
            purch_line_rows,
        )

        # -- clinical advisory pairs (Titan/Drug-Eye stand-in) ---------------
        cur.executemany(
            "INSERT INTO drug_interactions (ingredient_a, ingredient_b, severity, note_ar, note_en) VALUES (?,?,?,?,?)",
            [
                ("warfarin", "aspirin", "severe", "خطر نزيف مرتفع عند الجمع بينهما — راجع الطبيب.", "High bleeding risk together."),
                ("warfarin", "ibuprofen", "severe", "مضادات الالتهاب تزيد خطر النزيف مع الوارفارين.", "NSAIDs raise bleeding risk with warfarin."),
                ("clopidogrel", "esomeprazole", "moderate", "قد يقل تأثير بلافيكس مع مثبطات مضخة البروتون.", "PPIs may reduce clopidogrel effect."),
                ("aspirin", "ibuprofen", "moderate", "الإيبوبروفين قد يقلل تأثير الأسبرين الوقائي للقلب.", "Ibuprofen may blunt cardioprotective aspirin."),
                ("tramadol", "fluoxetine", "severe", "خطر المتلازمة السيروتونينية عند الجمع.", "Serotonin syndrome risk."),
                ("metformin", "ciprofloxacin", "minor", "قد يتغير سكر الدم — راقب القياسات.", "Monitor blood glucose."),
                ("alprazolam", "tramadol", "severe", "تثبيط تنفسي خطر — تجنب الجمع.", "Dangerous respiratory depression."),
                ("captopril", "ibuprofen", "moderate", "مضادات الالتهاب تقلل فعالية خافض الضغط.", "NSAIDs reduce ACE-inhibitor effect."),
                ("bisoprolol", "salbutamol", "moderate", "حاصرات بيتا قد تعاكس موسع الشعب.", "Beta-blocker may oppose bronchodilator."),
                ("glimepiride", "ciprofloxacin", "moderate", "خطر هبوط سكر الدم.", "Hypoglycemia risk."),
            ],
        )

        # -- ETL audit row ----------------------------------------------------
        cur.execute(
            """INSERT INTO etl_runs (source, kind, finished_at, status, rows_loaded, note)
               VALUES ('demo_seed','seed',?, 'ok', ?, 'Synthetic shadow data (no live source).')""",
            (datetime.now().isoformat(sep=" "), len(sale_rows) + len(line_rows)),
        )

        conn.commit()
        summary = {
            "products": len(products),
            "customers": n_cust,
            "vendors": len(vendor_ids),
            "stock_batches": len(batch_rows),
            "sales": len(sale_rows),
            "sale_lines": len(line_rows),
            "seeded_through": today.isoformat(),
        }
    finally:
        conn.close()
    return summary


def ensure_seeded() -> dict:
    """Seed the demo DB if missing/empty/stale. Cheap to call on startup.

    Reseeds when the newest sale predates today so the dashboard's "today"
    KPIs stay populated as the container lives across days.
    """
    db = get_db()
    if db.mode != "demo":
        return {"mode": db.mode, "seeded": False}
    if db.demo_db_exists():
        try:
            row = db.query_one("SELECT COUNT(*) AS n, MAX(date(sale_date)) AS last FROM sales")
            if row and row["n"] > 0 and row["last"] == date.today().isoformat():
                return {"mode": "demo", "seeded": True, "already": True}
        except Exception:
            pass  # schema missing/corrupt/stale -> reseed below
    return {"mode": "demo", "seeded": True, **seed(reset=True)}


if __name__ == "__main__":
    print(seed(reset=True))
