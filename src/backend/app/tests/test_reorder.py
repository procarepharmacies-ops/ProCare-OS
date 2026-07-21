"""Reorder proposal generation tests (Phase 5)."""
from datetime import date, timedelta

import pytest

from app.db import models as m
from app.db.base import SessionLocal
from app.services import reorder as reorder_svc


def test_generate_reorder_suggestions_critical():
    """Generate critical reorder suggestion when stockout imminent (≤3 days)."""
    session = SessionLocal()
    try:
        # Create test data
        branch = m.Branch(
            branch_id=1001,
            code="test_critical",
            name_ar="فرع اختبار",
            name_en="Test Branch",
        )
        session.add(branch)
        session.flush()

        product = m.Product(
            code="prod_critical",
            name_ar="دواء حرج",
            name_en="Critical Drug",
            sell_price=20.0,
            buy_price=10.0,
            unit_big="علبة",
            unit_small="قرص",
            unit_factor=10.0,
        )
        session.add(product)
        session.flush()

        # Create a forecast with stockout in 2 days (critical)
        forecast = m.Forecast(
            product_id=product.product_id,
            branch_id=branch.branch_id,
            forecast_date=date.today(),
            daily_avg=5.0,
            trend_per_day=0.0,
            seasonality_factor=1.0,
            projected_demand=10.0,
            stockout_date=date.today() + timedelta(days=2),
            days_of_cover=2.0,
            method="holt",
        )
        session.add(forecast)

        # Current stock: 8 units (less than 2 days of demand)
        batch = m.StockBatch(
            product_id=product.product_id,
            branch_id=branch.branch_id,
            amount=8.0,
            exp_date=date.today() + timedelta(days=90),
        )
        session.add(batch)
        session.commit()

        suggestions = reorder_svc.generate_reorder_suggestions(session, branch.branch_id)
        assert len(suggestions) > 0

        sugg = suggestions[0]
        assert sugg["priority"] == "critical"  # 2 days = critical
        assert sugg["product_id"] == product.product_id
        assert sugg["current_stock"] == 8.0
        assert sugg["days_to_stockout"] == 2
        assert sugg["suggested_qty"] > 0
    finally:
        session.close()


def test_generate_reorder_suggestions_urgent():
    """Generate urgent reorder suggestion when stockout in 5 days."""
    session = SessionLocal()
    try:
        branch = m.Branch(
            branch_id=1002,
            code="test_urgent",
            name_ar="فرع اختبار",
            name_en="Test Branch",
        )
        session.add(branch)
        session.flush()

        product = m.Product(
            code="prod_urgent",
            name_ar="دواء عاجل",
            name_en="Urgent Drug",
            sell_price=15.0,
            buy_price=8.0,
        )
        session.add(product)
        session.flush()

        forecast = m.Forecast(
            product_id=product.product_id,
            branch_id=branch.branch_id,
            forecast_date=date.today(),
            daily_avg=3.0,
            trend_per_day=0.0,
            seasonality_factor=1.0,
            projected_demand=15.0,
            stockout_date=date.today() + timedelta(days=5),
            days_of_cover=5.0,
            method="holt",
        )
        session.add(forecast)
        session.commit()

        suggestions = reorder_svc.generate_reorder_suggestions(session, branch.branch_id)
        assert len(suggestions) > 0

        sugg = suggestions[0]
        assert sugg["priority"] == "urgent"  # 5 days = urgent
        assert sugg["days_to_stockout"] == 5
    finally:
        session.close()


def test_reorder_suggestions_sorted_by_priority():
    """Verify reorder suggestions are sorted by priority (critical → urgent → normal → low)."""
    session = SessionLocal()
    try:
        branch = m.Branch(
            branch_id=1003,
            code="test_sort",
            name_ar="فرع",
            name_en="Branch",
        )
        session.add(branch)
        session.flush()

        # Create products
        product_ids = []
        for i, days_ahead in enumerate([2, 5, 10, 20]):
            p = m.Product(
                code=f"prod_sort_{i}",
                name_ar=f"دواء {i}",
                name_en=f"Drug {i}",
                sell_price=10.0,
                buy_price=5.0,
            )
            session.add(p)
            session.flush()
            product_ids.append(p.product_id)

            forecast = m.Forecast(
                product_id=p.product_id,
                branch_id=branch.branch_id,
                forecast_date=date.today(),
                daily_avg=1.0,
                trend_per_day=0.0,
                seasonality_factor=1.0,
                projected_demand=days_ahead,
                stockout_date=date.today() + timedelta(days=days_ahead),
                days_of_cover=float(days_ahead),
                method="holt",
            )
            session.add(forecast)
        session.commit()

        suggestions = reorder_svc.generate_reorder_suggestions(session, branch.branch_id)
        assert len(suggestions) == 4

        # Verify priority order
        priorities = [s["priority"] for s in suggestions]
        assert priorities == ["critical", "urgent", "normal", "low"]
    finally:
        session.close()


def test_summarize_suggestions():
    """Test summary generation grouped by vendor + priority."""
    suggestions = [
        {
            "product_id": 1,
            "product_name_ar": "دواء أ",
            "product_name_en": "Drug A",
            "current_stock": 5.0,
            "daily_avg_demand": 2.0,
            "days_to_stockout": 2,
            "stockout_date": date.today() + timedelta(days=2),
            "suggested_qty": 20.0,
            "unit_big": "علبة",
            "unit_factor": 10.0,
            "lead_time_days": 5,
            "buy_price": 10.0,
            "priority": "critical",
            "transfer_available_qty": 0.0,
            "transfer_from_branch_id": None,
            "suggested_vendors": [
                {"vendor_id": 1, "vendor_name_ar": "بائع أ", "vendor_name_en": "Vendor A", "price": 9.0}
            ],
        },
        {
            "product_id": 2,
            "product_name_ar": "دواء ب",
            "product_name_en": "Drug B",
            "current_stock": 10.0,
            "daily_avg_demand": 1.0,
            "days_to_stockout": 10,
            "stockout_date": date.today() + timedelta(days=10),
            "suggested_qty": 5.0,
            "unit_big": "علبة",
            "unit_factor": 10.0,
            "lead_time_days": 5,
            "buy_price": 15.0,
            "priority": "normal",
            "transfer_available_qty": 0.0,
            "transfer_from_branch_id": None,
            "suggested_vendors": [
                {"vendor_id": 1, "vendor_name_ar": "بائع أ", "vendor_name_en": "Vendor A", "price": 14.0}
            ],
        },
    ]

    summary = reorder_svc.summarize_suggestions(suggestions)
    assert summary["total_suggestions"] == 2
    assert summary["by_priority"]["critical"] == 1
    assert summary["by_priority"]["normal"] == 1
    assert "بائع أ" in summary["by_vendor"]
    assert summary["by_vendor"]["بائع أ"]["qty"] == 25.0  # 20 + 5
    assert len(summary["by_vendor"]["بائع أ"]["line_items"]) == 2
    assert summary["transfer_available_total"] == 0.0


def test_reorder_with_transfer_first():
    """Test transfer-first logic: prefer moving from other branch before ordering."""
    session = SessionLocal()
    try:
        # Create two branches
        branch1 = m.Branch(branch_id=1004, code="b1", name_ar="فرع 1", name_en="Branch 1")
        branch2 = m.Branch(branch_id=1005, code="b2", name_ar="فرع 2", name_en="Branch 2")
        session.add_all([branch1, branch2])
        session.flush()

        product = m.Product(
            code="prod_transfer",
            name_ar="دواء تحويل",
            name_en="Transfer Drug",
            sell_price=20.0,
            buy_price=10.0,
        )
        session.add(product)
        session.flush()

        # Branch1: low stock
        batch1 = m.StockBatch(
            product_id=product.product_id,
            branch_id=branch1.branch_id,
            amount=2.0,
            exp_date=date.today() + timedelta(days=90),
        )
        session.add(batch1)

        # Branch2: plenty in stock
        batch2 = m.StockBatch(
            product_id=product.product_id,
            branch_id=branch2.branch_id,
            amount=100.0,
            exp_date=date.today() + timedelta(days=90),
        )
        session.add(batch2)

        # Forecast for branch1: stockout in 3 days
        forecast = m.Forecast(
            product_id=product.product_id,
            branch_id=branch1.branch_id,
            forecast_date=date.today(),
            daily_avg=5.0,
            trend_per_day=0.0,
            seasonality_factor=1.0,
            projected_demand=15.0,
            stockout_date=date.today() + timedelta(days=3),
            days_of_cover=3.0,
            method="holt",
        )
        session.add(forecast)
        session.commit()

        suggestions = reorder_svc.generate_reorder_suggestions(session, branch1.branch_id)
        assert len(suggestions) > 0

        sugg = suggestions[0]
        # Transfer available from branch2
        assert sugg["transfer_available_qty"] > 0
        assert sugg["transfer_from_branch_id"] == branch2.branch_id
        # Depending on qty needed, might need PO + transfer, or just transfer
        assert sugg["priority"] == "critical"
    finally:
        session.close()


def test_reorder_no_suggestions_when_stock_adequate():
    """No reorder suggestion when stock covers demand."""
    session = SessionLocal()
    try:
        branch = m.Branch(
            branch_id=1006,
            code="test_adequate",
            name_ar="فرع",
            name_en="Branch",
        )
        session.add(branch)
        session.flush()

        product = m.Product(
            code="prod_adequate",
            name_ar="دواء كافي",
            name_en="Adequate Drug",
            sell_price=10.0,
            buy_price=5.0,
        )
        session.add(product)
        session.flush()

        # High stock (30 days of cover)
        batch = m.StockBatch(
            product_id=product.product_id,
            branch_id=branch.branch_id,
            amount=150.0,  # 30 days of demand at 5/day
            exp_date=date.today() + timedelta(days=90),
        )
        session.add(batch)

        # Forecast with stockout in 30 days
        forecast = m.Forecast(
            product_id=product.product_id,
            branch_id=branch.branch_id,
            forecast_date=date.today(),
            daily_avg=5.0,
            trend_per_day=0.0,
            seasonality_factor=1.0,
            projected_demand=150.0,
            stockout_date=date.today() + timedelta(days=30),
            days_of_cover=30.0,
            method="holt",
        )
        session.add(forecast)
        session.commit()

        suggestions = reorder_svc.generate_reorder_suggestions(session, branch.branch_id)
        # Stock is adequate, so no urgent suggestions expected
        # (might get low priority for planning, but not urgent)
        assert len(suggestions) == 0 or all(s["priority"] == "low" for s in suggestions)
    finally:
        session.close()
