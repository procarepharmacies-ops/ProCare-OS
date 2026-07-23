"""Phase 6 tests: payroll depth (Employee_salary mirror + per-employee panel)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, delete, inspect, text

from app.db import models as m
from app.db.base import SessionLocal
from app.services import etl
from app.services import payroll as svc


@pytest.fixture(autouse=True)
def clean_payroll():
    s = SessionLocal()
    try:
        s.execute(delete(m.SalaryAdvance))
        s.execute(delete(m.PayrollRecord))
        s.commit()
    finally:
        s.close()
    yield


def test_employee_payroll_panel_breaks_down_the_latest_record():
    s = SessionLocal()
    try:
        s.add_all([
            m.PayrollRecord(
                source_id=10, employee_id=2, period="2026-05", basic_salary=5000,
                commission=800, over_commission=200, deduction=150, absence_money=50,
                cash_advance=300, source_total=5500, net=5500,
            ),
            m.PayrollRecord(
                source_id=11, employee_id=2, period="2026-06", basic_salary=5000,
                commission=1000, over_commission=0, deduction=100, absence_money=0,
                cash_advance=500, source_total=5400, net=5400,
            ),
        ])
        s.commit()

        out = svc.employee_payroll(s, 2)
        assert out["has_records"] is True
        assert len(out["records"]) == 2
        # Latest = 2026-06 (highest payroll_id).
        sm = out["summary"]
        assert sm["period"] == "2026-06"
        assert sm["basic_salary"] == 5000.0
        assert sm["commission"] == 1000.0        # commission + over_commission
        assert sm["deductions"] == 100.0          # deduction + absence
        assert sm["advances"] == 500.0
        assert sm["net"] == 5400.0                # 5000 + 1000 + 0 - 100 - 0 - 500
    finally:
        s.close()


def test_employee_payroll_without_records_falls_back_to_base_on_file():
    s = SessionLocal()
    try:
        out = svc.employee_payroll(s, 3)
        assert out["has_records"] is False
        assert out["summary"] is None
        assert out["base_salary_on_file"] == pytest.approx(float(s.get(m.Employee, 3).basic_salary))
    finally:
        s.close()


def test_employee_payroll_missing_employee_returns_none():
    s = SessionLocal()
    try:
        assert svc.employee_payroll(s, 999999) is None
    finally:
        s.close()


def _payroll_source(path):
    eng = create_engine(f"sqlite:///{path}")
    with eng.begin() as c:
        # Source Employee master: emp_id -> username (matches seeded 'ahmed'=emp 2).
        c.execute(text("CREATE TABLE Employee (emp_id INT, username TEXT)"))
        c.execute(text("INSERT INTO Employee VALUES (77,'ahmed'),(88,'ghost')"))
        c.execute(text(
            "CREATE TABLE Employee_salary (salary_id INT, emp_id INT, state TEXT, basic_salary REAL, "
            "emp_commission REAL, emp_over_commission REAL, emp_deduction REAL, emp_absence_money REAL, "
            "total REAL, month_salary TEXT, cash_advance REAL)"
        ))
        c.execute(text(
            "INSERT INTO Employee_salary VALUES "
            "(1,77,'paid',5000,700,300,200,100,5400,'2026-06',400),"   # -> ahmed (emp 2)
            "(2,88,'paid',4000,0,0,0,0,4000,'2026-06',0)"              # ghost: no ProCare match -> skipped
        ))
    return eng


def test_etl_load_payroll_maps_by_username_and_upserts(tmp_path):
    src = _payroll_source(tmp_path / "pay.db")
    try:
        insp = inspect(src)
        with src.connect() as conn, SessionLocal() as dst:
            counts: dict = {}
            etl._load_payroll(insp, conn, dst, counts)
            dst.commit()
            assert counts["payroll"] == 1  # only the resolvable 'ahmed' row

            rec = dst.query(m.PayrollRecord).filter_by(source_id=1).one()
            assert rec.employee_id == 2  # ahmed
            # net = 5000 + 700 + 300 - 200 - 100 - 400
            assert float(rec.net) == pytest.approx(5300.0)

            # Re-run upserts by salary_id — no duplicate.
            etl._load_payroll(insp, conn, dst, {})
            dst.commit()
            assert dst.query(m.PayrollRecord).filter_by(source_id=1).count() == 1
    finally:
        src.dispose()
        s = SessionLocal()
        try:
            s.execute(delete(m.PayrollRecord))
            s.commit()
        finally:
            s.close()


def test_employee_payroll_includes_advances_ledger():
    s = SessionLocal()
    try:
        s.add_all([
            m.SalaryAdvance(source_id=1, employee_id=2, amount=300, advance_type="سلفة"),
            m.SalaryAdvance(source_id=2, employee_id=2, amount=200, advance_type="سلفة"),
        ])
        s.commit()
        out = svc.employee_payroll(s, 2)
        assert out["advances_total"] == 500.0
        assert len(out["advances"]) == 2
        # Newest first (highest advance_id).
        assert out["advances"][0]["advance_id"] > out["advances"][1]["advance_id"]
    finally:
        s.close()


def _advance_source(path):
    eng = create_engine(f"sqlite:///{path}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE Employee (emp_id INT, username TEXT)"))
        c.execute(text("INSERT INTO Employee VALUES (77,'ahmed'),(88,'ghost')"))
        c.execute(text(
            "CREATE TABLE Employee_cash_advance (cash_advance_id INT, emp_id INT, cash_advance REAL, type TEXT)"
        ))
        c.execute(text(
            "INSERT INTO Employee_cash_advance VALUES (1,77,300,'سلفة'),(2,88,999,'سلفة')"
        ))
    return eng


def test_etl_load_salary_advances_maps_and_upserts(tmp_path):
    src = _advance_source(tmp_path / "adv.db")
    try:
        insp = inspect(src)
        with src.connect() as conn, SessionLocal() as dst:
            counts: dict = {}
            etl._load_salary_advances(insp, conn, dst, counts)
            dst.commit()
            assert counts["salary_advances"] == 1  # only 'ahmed' resolvable
            rec = dst.query(m.SalaryAdvance).filter_by(source_id=1).one()
            assert rec.employee_id == 2 and float(rec.amount) == 300.0

            etl._load_salary_advances(insp, conn, dst, {})
            dst.commit()
            assert dst.query(m.SalaryAdvance).filter_by(source_id=1).count() == 1
    finally:
        src.dispose()
        s = SessionLocal()
        try:
            s.execute(delete(m.SalaryAdvance))
            s.commit()
        finally:
            s.close()


def test_api_employee_payroll(client):
    s = SessionLocal()
    try:
        s.add(m.PayrollRecord(source_id=20, employee_id=2, period="2026-06",
                              basic_salary=5000, commission=1000, net=6000))
        s.commit()
    finally:
        s.close()
    r = client.get("/api/employees/2/payroll")
    assert r.status_code == 200
    assert r.json()["summary"]["net"] == 6000.0
    assert client.get("/api/employees/999999/payroll").status_code == 404
