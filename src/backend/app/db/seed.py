"""Demo-data generator for ProCare's own database.

This makes the whole stack runnable and demonstrable without the live eStock
SQL Server: it fills ProCare's clean schema with realistic, deterministic
pharmacy data shaped like the 2026-06-23 eStock audit — two branches, a drug
catalogue, batch-level stock with real expiry spread, customers (a few over
their credit limit, on purpose, to exercise the credit guard), vendors, and ~90
days of sales history with FEFO-consistent batches.

In production this module is NOT used; the data arrives via the read-only eStock
ETL (``app.services.etl``). Here it stands in for that source so the dashboard,
AI assistant, alerts and POS all have something real to work on.

Deterministic: a fixed RNG seed means the same DB every run, so reconciliation
and tests are stable.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.db.base import Base, SessionLocal, engine

RNG = random.Random(20260626)
TODAY = date(2026, 6, 26)
# Five full years of history so "pharmacy performance over time" is real: the
# owner sees year-over-year revenue, invoices, customers, purchasing and stock,
# not just a recent slice. START is the first day of the window.
YEARS_BACK = 5
START = date(TODAY.year - YEARS_BACK, TODAY.month, TODAY.day)

# A small but realistic Egyptian-pharmacy catalogue (ar / en / scientific).
DRUGS = [
    ("بانادول", "Panadol", "Paracetamol"),
    ("أوجمنتين", "Augmentin", "Amoxicillin/Clavulanate"),
    ("كونجستال", "Congestal", "Paracetamol/Chlorphenamine"),
    ("فلاجyl", "Flagyl", "Metronidazole"),
    ("كلاريتين", "Claritine", "Loratadine"),
    ("بريمولوت", "Primolut", "Norethisterone"),
    ("نوسبازم", "No-spa", "Drotaverine"),
    ("فولتارين", "Voltaren", "Diclofenac"),
    ("زيثروماكس", "Zithromax", "Azithromycin"),
    ("كونكور", "Concor", "Bisoprolol"),
    ("أملور", "Amlor", "Amlodipine"),
    ("جلوكوفاج", "Glucophage", "Metformin"),
    ("ليبيتور", "Lipitor", "Atorvastatin"),
    ("نكسيوم", "Nexium", "Esomeprazole"),
    ("أنتينال", "Antinal", "Nifuroxazide"),
    ("سيتال", "Cetal", "Paracetamol"),
    ("بروفين", "Brufen", "Ibuprofen"),
    ("كتافلام", "Cataflam", "Diclofenac Potassium"),
    ("ريفو", "Rivo", "Aspirin"),
    ("فيتامين سي", "Vitamin C", "Ascorbic Acid"),
    ("زنتاك", "Zantac", "Ranitidine"),
    ("موتيليوم", "Motilium", "Domperidone"),
    ("بروستاكلاميد", "Prostaglandin", "Misoprostol"),
    ("تامول", "Tamol", "Paracetamol"),
    ("سيبروسين", "Ciprocin", "Ciprofloxacin"),
    ("أوميبرازول", "Omez", "Omeprazole"),
    ("ديكلاك", "Declac", "Diclofenac"),
    ("هيستوب", "Histop", "Cetirizine"),
    ("فاركولين", "Farcolin", "Salbutamol"),
    ("لازكس", "Lasix", "Furosemide"),
]
# Fix a typo deliberately introduced above (kept ASCII-safe drug names clean):
DRUGS[3] = ("فلاجيل", "Flagyl", "Metronidazole")

COMPANIES = ["جلاكسو", "نوفارتس", "فايزر", "سانوفي", "إيفا فارما", "أمون", "العاشر من رمضان"]
GROUPS = ["مسكنات", "مضادات حيوية", "برد وإنفلونزا", "جهاز هضمي", "ضغط وسكر", "فيتامينات"]
UNITS = [("علبة", "box"), ("شريط", "strip"), ("قرص", "tablet")]
CUSTOMER_NAMES = [
    "أحمد محمد", "محمود علي", "فاطمة حسن", "سارة إبراهيم", "خالد يوسف", "منى سمير",
    "حسام الدين", "نورا عادل", "عمر فاروق", "هبة مصطفى", "كريم وحيد", "دعاء ناصر",
    "صيدلية النور", "مستشفى الأمل", "عيادة د. سمير", "ياسمين رضا", "طارق فؤاد", "ليلى كمال",
]
# (name_ar, name_en). PharmaOverseas and Ibn Sina are the two giant Egyptian
# distributors the pharmacy buys most of its stock from; PharmaOverseas is the
# primary supplier here, so it carries the bulk of the purchasing history below.
VENDORS = [
    ("فارما أوفرسيز", "PharmaOverseas"),
    ("ابن سينا فارما", "Ibn Sina Pharma"),
    ("شركة المهن الطبية", "Medical Professions Co"),
    ("يونايتد فارما", "United Pharma"),
    ("مصر للأدوية", "Misr Pharma"),
    ("فاركو", "Pharco"),
]
# Extra family/first names used to grow a realistic customer base over 5 years
# (staggered join dates → a real "number of customers over time" curve).
EXTRA_CUSTOMER_NAMES = [
    "إيمان صبري", "رامي عصام", "شيماء جمال", "مصطفى لطفي", "دينا حمدي", "وليد شعبان",
    "نهى فتحي", "أشرف زكي", "مروة سعيد", "هاني عبد الله", "غادة منير", "سامح رؤوف",
    "أمنية طلعت", "بلال حسني", "رانيا مجدي", "تامر صلاح", "سلمى نبيل", "يحيى عادل",
    "عبير شوقي", "كمال الدين", "نرمين وائل", "زياد أنور", "فريدة سمير", "أنس محسن",
    "ملك إيهاب", "جمانة رفعت", "سيف مراد", "لمياء عاطف", "بسنت هشام", "مازن قدري",
    "صيدلية الشفاء", "مركز طب الأسرة", "عيادة د. منى", "مستوصف الرحمة",
]
EMPLOYEES = [
    # (name_ar, username, job title, is_admin, login role)
    ("مدير النظام", "admin", "Admin", True, "ceo"),
    ("أحمد الكاشير", "ahmed", "Cashier", False, "assistant"),
    ("سارة الصيدلانية", "sara", "Pharmacist", False, "manager"),
    ("محمد فرع السنتا", "mohamed", "Cashier", False, "assistant"),
]


def _hash(pw: str) -> str:
    """Lightweight password hash for the demo (production uses a real KDF)."""
    return "sha256$" + hashlib.sha256(pw.encode()).hexdigest()


def database_is_seeded(session: Session) -> bool:
    return session.scalar(select(func.count()).select_from(m.Product)) or 0 > 0


def reset_and_seed() -> dict:
    """Drop, recreate and fill ProCare's own DB. Returns a summary dict."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        summary = _seed(s)
        s.commit()
    return summary


def ensure_seeded() -> dict:
    """Create tables and seed once if the catalogue is empty. Idempotent."""
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        count = s.scalar(select(func.count()).select_from(m.Product)) or 0
        if count > 0:
            return {"already_seeded": True, "products": count}
        summary = _seed(s)
        s.commit()
        return summary


def _seed(s: Session) -> dict:
    # --- Branches (the schema seeds these; we own them here on SQLite) --------
    # Check-before-insert: a partially-seeded DB (tables/branches already present
    # but zero products) must not crash ensure_seeded() with a duplicate-key
    # error on MAIN/ELSANTA — reuse the existing rows instead of re-inserting.
    main = s.scalars(select(m.Branch).where(m.Branch.code == "MAIN")).first()
    if main is None:
        main = m.Branch(code="MAIN", name_ar="الرئيسي", name_en="Main", is_pilot=False)
        s.add(main)
    elsanta = s.scalars(select(m.Branch).where(m.Branch.code == "ELSANTA")).first()
    if elsanta is None:
        elsanta = m.Branch(code="ELSANTA", name_ar="السنتا", name_en="Elsanta", is_pilot=True)
        s.add(elsanta)
    s.flush()
    branches = [main, elsanta]

    # --- Reference data -------------------------------------------------------
    companies = [m.Company(name_ar=n) for n in COMPANIES]
    groups = [m.ProductGroup(name_ar=n) for n in GROUPS]
    units = [m.Unit(name_ar=a, name_en=e) for a, e in UNITS]
    classes = [
        m.CustomerClass(name_ar="تجزئة", name_en="retail"),
        m.CustomerClass(name_ar="جملة", name_en="wholesale"),
    ]
    jobs = [m.Job(name_ar="مدير", name_en="Manager"), m.Job(name_ar="كاشير", name_en="Cashier")]
    s.add_all(companies + groups + units + classes + jobs)
    s.flush()

    # --- Employees (real permission flags) -----------------------------------
    employees = []
    for i, (name_ar, username, role_en, is_admin, login_role) in enumerate(EMPLOYEES):
        emp = m.Employee(
            name_ar=name_ar,
            name_en=role_en,
            username=username,
            password_hash=_hash("procare123"),
            role=login_role,
            job_id=jobs[0].job_id if is_admin else jobs[1].job_id,
            branch_id=elsanta.branch_id if "السنتا" in name_ar else main.branch_id,
            can_see_buy_price=is_admin,
            can_edit_sell_price=is_admin,
            can_sale_credit=is_admin or role_en == "Pharmacist",
            can_return=is_admin or role_en == "Pharmacist",
            can_void=is_admin,
            can_change_shift=True,
        )
        employees.append(emp)
    s.add_all(employees)
    s.flush()

    # --- Products -------------------------------------------------------------
    products: list[m.Product] = []
    for i, (ar, en, sci) in enumerate(DRUGS):
        sell = RNG.choice([12, 18, 25, 35, 48, 60, 85, 120, 7.5, 22.5])
        buy = round(sell * RNG.uniform(0.55, 0.78), 2)
        p = m.Product(
            code=f"P{1000 + i}",
            fast_code=str(100 + i),
            name_ar=ar,
            name_en=en,
            scientific_name=sci,
            company_id=RNG.choice(companies).company_id,
            group_id=RNG.choice(groups).group_id,
            unit1_id=units[0].unit_id,
            is_controlled=(i % 9 == 0),
            has_expiry=True,
            sell_price=sell,
            buy_price=buy,
            tax_price=0,
            wholesale_price=round(sell * 0.92, 2),
            min_stock=RNG.choice([10, 15, 20, 25, 30]),
        )
        products.append(p)
    s.add_all(products)
    s.flush()

    # Barcodes intentionally omitted from demo (catalogue codes are enough).

    # --- Vendors --------------------------------------------------------------
    vendors = []
    for i, (name_ar, name_en) in enumerate(VENDORS):
        # The primary distributor (PharmaOverseas) carries a larger open payable.
        balance = round(RNG.uniform(120000, 240000), 2) if i == 0 else round(RNG.uniform(0, 90000), 2)
        vendors.append(
            m.Vendor(
                name_ar=name_ar,
                name_en=name_en,
                mobile="010" + "".join(str(RNG.randint(0, 9)) for _ in range(8)),
                credit_limit=500000 if i == 0 else 200000,
                current_balance=balance,
            )
        )
    s.add_all(vendors)
    s.flush()
    # Weight purchasing toward the primary distributor, then the second-largest.
    vendor_weights = [0.5, 0.2] + [0.3 / max(1, len(vendors) - 2)] * (len(vendors) - 2)

    # --- Customers (a few deliberately over their credit limit) --------------
    # Joins are staggered across the 5-year window so "number of customers over
    # time" is a real growth curve, not a flat line. The original core names all
    # joined early (they are long-standing accounts); the extra pool trickles in.
    span_days = (TODAY - START).days
    customer_names = list(CUSTOMER_NAMES) + list(EXTRA_CUSTOMER_NAMES)
    customers = []
    for i, name in enumerate(customer_names):
        limit = RNG.choice([0, 500, 1000, 2000, 5000])
        # ~1 in 5 sits over the limit, reproducing the eStock "61 over limit" issue.
        over = i % 5 == 0 and limit > 0
        balance = round(limit * RNG.uniform(1.05, 1.4), 2) if over else round(
            RNG.uniform(0, max(limit, 1) * 0.7), 2
        )
        if i < len(CUSTOMER_NAMES):
            # Core accounts: joined near the start of the window.
            joined = START + timedelta(days=RNG.randint(0, 120))
        else:
            # New accounts acquired gradually, weighted toward more recent years.
            frac = (RNG.random() ** 0.65)  # skew later
            joined = START + timedelta(days=int(frac * span_days))
        is_org = any(k in name for k in ("صيدلية", "مستشفى", "عيادة", "مركز", "مستوصف"))
        customers.append(
            m.Customer(
                name_ar=name,
                mobile="011" + "".join(str(RNG.randint(0, 9)) for _ in range(8)),
                customer_class_id=classes[1 if is_org else 0].customer_class_id,
                credit_limit=limit,
                current_balance=balance,
                created_at=datetime(joined.year, joined.month, joined.day, 10, 0),
            )
        )
    s.add_all(customers)
    s.flush()

    # --- Stock batches (per branch, real expiry spread, some expired) --------
    batches: list[m.StockBatch] = []
    for p in products:
        for b in branches:
            n_batches = RNG.randint(1, 3)
            for _ in range(n_batches):
                roll = RNG.random()
                if roll < 0.08:  # expired-only risk (eStock had 74 expired in stock)
                    exp = TODAY - timedelta(days=RNG.randint(5, 120))
                elif roll < 0.25:  # expiring soon (drives 7/30/90-day alerts)
                    exp = TODAY + timedelta(days=RNG.randint(3, 60))
                else:
                    exp = TODAY + timedelta(days=RNG.randint(120, 720))
                # A few products are intentionally low-stock to trigger reorder.
                low = RNG.random() < 0.18
                amount = RNG.randint(1, 9) if low else RNG.randint(20, 200)
                batch = m.StockBatch(
                    product_id=p.product_id,
                    branch_id=b.branch_id,
                    vendor_id=RNG.choice(vendors).vendor_id,
                    amount=amount,
                    buy_price=p.buy_price,
                    sell_price=p.sell_price,
                    exp_date=exp,
                )
                batches.append(batch)
    s.add_all(batches)
    s.flush()

    # Opening stock movements for traceability.
    for batch in batches:
        s.add(
            m.StockMovement(
                batch_id=batch.batch_id,
                branch_id=batch.branch_id,
                delta=batch.amount,
                reason="opening",
            )
        )

    # --- Sales history (5 years), FEFO-consistent ----------------------------
    # A rising trend: both invoice volume and prices grow year over year, so the
    # performance report tells a real story. The most recent ~120 days are dense
    # (daily) so today's dashboards stay rich; older history is sampled (a few
    # days per week) to keep the demo fast while still filling every month.
    sales_count = 0
    lines_count = 0
    cashiers = [e for e in employees if e.name_en in ("Cashier", "Admin")]

    def _progress(d: date) -> float:
        """0.0 at the start of the window → 1.0 today."""
        return (d - START).days / span_days if span_days else 1.0

    day = START
    while day <= TODAY:
        prog = _progress(day)
        recent = (TODAY - day).days <= 90
        # Inflation + growth: prices ~0.75x five years ago rising to ~1.2x today.
        infl = 0.75 + 0.45 * prog
        # Sales/active-day grows from ~3 to ~10 across the window.
        target = 3 + prog * 7
        if day.weekday() == 4:  # Friday a touch quieter
            target *= 0.7

        if recent:
            active = True
            n_sales = RNG.randint(max(2, int(target) - 2), int(target) + 3)
        else:
            active = RNG.random() < 0.55  # ~4 days a week carried older history
            n_sales = RNG.randint(1, max(2, int(target * 0.8)))

        if active:
            eligible = [c for c in customers if c.created_at.date() <= day]
            for _ in range(n_sales):
                branch = RNG.choice(branches)
                hour = RNG.choices(range(9, 23), weights=[3, 4, 5, 6, 7, 6, 5, 6, 7, 8, 7, 5, 3, 2])[0]
                ts = datetime(day.year, day.month, day.day, hour, RNG.randint(0, 59))
                is_credit = RNG.random() < 0.15 and eligible
                customer = RNG.choice(eligible) if eligible and (is_credit or RNG.random() < 0.3) else None
                sale = m.Sale(
                    branch_id=branch.branch_id,
                    customer_id=customer.customer_id if customer else None,
                    cashier_id=RNG.choice(cashiers).employee_id,
                    sale_date=ts,
                    is_credit=bool(is_credit),
                )
                s.add(sale)
                s.flush()
                n_lines = RNG.randint(1, 4)
                gross = 0.0
                for _ in range(n_lines):
                    p = RNG.choice(products)
                    qty = RNG.randint(1, 3)
                    sell = round(float(p.sell_price) * infl, 2)
                    buy = round(float(p.buy_price) * infl, 2)
                    line_total = round(sell * qty, 2)
                    gross += line_total
                    s.add(
                        m.SaleLine(
                            sale_id=sale.sale_id,
                            product_id=p.product_id,
                            amount=qty,
                            sell_price=sell,
                            buy_price=buy,
                            total_sell=line_total,
                        )
                    )
                    lines_count += 1
                disc = round(gross * RNG.choice([0, 0, 0, 0.02, 0.05]), 2)
                net = round(gross - disc, 2)
                sale.total_gross = gross
                sale.total_discount = disc
                sale.total_net = net
                if is_credit:
                    sale.cash_paid = 0
                else:
                    # A slice of walk-in sales are paid by card (network) — so the
                    # cash-vs-card split in the analysis is meaningful.
                    if RNG.random() < 0.25:
                        sale.card_paid = net
                    else:
                        sale.cash_paid = net
                sales_count += 1
            s.flush()
        day += timedelta(days=1)

    # --- Purchasing history (5 years) ----------------------------------------
    # Weekly goods-received invoices per branch, mostly from the primary
    # distributor (PharmaOverseas). Recorded as historical documents (header +
    # lines) — they do NOT add to current stock, which is already seeded above,
    # so stock/expiry reports stay correct while purchasing analysis has data.
    purchases_count = 0
    purchase_lines_count = 0
    week = START
    while week <= TODAY:
        prog = _progress(week)
        infl = 0.75 + 0.45 * prog
        for branch in branches:
            if RNG.random() < 0.15:  # occasional quiet week
                continue
            vendor = RNG.choices(vendors, weights=vendor_weights)[0]
            bill_day = week + timedelta(days=RNG.randint(0, 6))
            if bill_day > TODAY:
                bill_day = TODAY
            purchase = m.Purchase(
                branch_id=branch.branch_id,
                vendor_id=vendor.vendor_id,
                bill_date=bill_day,
                bill_number=f"PO-{bill_day.year}{bill_day.month:02d}-{purchases_count + 1:04d}",
            )
            s.add(purchase)
            s.flush()
            gross = 0.0
            for _ in range(RNG.randint(2, 7)):
                p = RNG.choice(products)
                qty = RNG.randint(10, 120)
                buy = round(float(p.buy_price) * infl, 2)
                sell = round(float(p.sell_price) * infl, 2)
                gross += round(qty * buy, 2)
                s.add(
                    m.PurchaseLine(
                        purchase_id=purchase.purchase_id,
                        product_id=p.product_id,
                        amount=qty,
                        bonus=RNG.choice([0, 0, 0, qty * 0.05]),
                        buy_price=buy,
                        sell_price=sell,
                        exp_date=bill_day + timedelta(days=RNG.randint(180, 900)),
                    )
                )
                purchase_lines_count += 1
            disc = round(gross * RNG.choice([0, 0, 0.01, 0.02]), 2)
            purchase.total_gross = round(gross, 2)
            purchase.total_discount = disc
            purchase.total_tax = 0
            purchases_count += 1
        s.flush()
        week += timedelta(days=7)

    return {
        "branches": len(branches),
        "products": len(products),
        "customers": len(customers),
        "vendors": len(vendors),
        "employees": len(employees),
        "stock_batches": len(batches),
        "sales": sales_count,
        "sale_lines": lines_count,
        "purchases": purchases_count,
        "purchase_lines": purchase_lines_count,
        "history_from": START.isoformat(),
        "history_to": TODAY.isoformat(),
    }


if __name__ == "__main__":
    print(reset_and_seed())
