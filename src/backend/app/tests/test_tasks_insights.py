"""Daily tasks, footfall ingestion/conversion, insights, roster, password change."""
from __future__ import annotations

from sqlalchemy import select

from app.db import models as m
from app.db.migrate import ROSTER, ensure_roster


def test_task_lifecycle_via_api(client):
    r = client.post("/api/tasks", json={"title": "جرد رف الأنسولين", "details": "قبل الظهر"})
    assert r.status_code == 200
    task_id = r.json()["task_id"]

    listing = client.get("/api/tasks").json()
    assert any(t["task_id"] == task_id and t["status"] == "pending" for t in listing["tasks"])
    assert listing["summary"]["pending"] >= 1

    done = client.post(f"/api/tasks/{task_id}/status", json={"status": "done"})
    assert done.status_code == 200 and done.json()["status"] == "done"
    assert client.get("/api/tasks").json()["summary"]["done_today"] >= 1

    # Unknown task -> 404; bad status -> 422.
    assert client.post("/api/tasks/999999/status", json={"status": "done"}).status_code == 404
    assert client.post(f"/api/tasks/{task_id}/status", json={"status": "maybe"}).status_code == 422


def test_task_assignees_listing(client):
    names = {a["name_en"] for a in client.get("/api/tasks/assignees").json()["assignees"]}
    assert "Ahmed Ibrahim" in names  # real roster is provisioned at startup


def test_footfall_event_and_conversion(client, session):
    branch_id = session.scalars(select(m.Branch.branch_id)).first()
    r = client.post("/api/footfall/event", json={"branch_id": branch_id, "direction": "in", "count": 25, "source": "nvr-ch1"})
    assert r.status_code == 200 and r.json()["recorded"] == 25

    s = client.get("/api/footfall/summary", params={"branch_id": branch_id, "days": 3}).json()
    assert s["counter_connected"] is True
    assert s["total_visitors"] >= 25
    # Seeded demo sales exist today or not — either way conversion math holds.
    today = s["series"][-1]
    assert today["visitors"] >= 25
    if today["visitors"]:
        assert today["conversion_pct"] == round(100 * today["bills"] / today["visitors"], 1)

    assert client.post("/api/footfall/event", json={"branch_id": branch_id, "direction": "sideways"}).status_code == 422


def test_insights_daily_and_productivity(client):
    daily = client.get("/api/insights/daily").json()
    assert {"date", "sales", "visitors", "conversion_pct", "tasks", "alerts"} <= set(daily)
    assert daily["sales"]["bills"] >= 0

    prod = client.get("/api/insights/productivity", params={"days": 30}).json()
    assert prod["days"] == 30
    assert isinstance(prod["employees"], list) and len(prod["employees"]) >= 1
    top = prod["employees"][0]
    assert {"name", "bills", "revenue", "peak_hour", "hourly"} <= set(top)
    assert len(top["hourly"]) == 24
    assert prod["busiest_hour"] is None or 0 <= prod["busiest_hour"] <= 23


def test_roster_provisioned_and_idempotent(client, session):  # client boots the app lifespan that provisions the roster
    for username, _, _, role, _ in ROSTER:
        emp = session.scalar(select(m.Employee).where(m.Employee.username == username))
        assert emp is not None, f"missing roster account {username}"
        assert emp.role == role

    before = session.scalar(select(m.Employee.employee_id).order_by(m.Employee.employee_id.desc()))
    ensure_roster(session)  # second run must not duplicate
    after = session.scalar(select(m.Employee.employee_id).order_by(m.Employee.employee_id.desc()))
    assert before == after


def test_roster_login_and_change_password(client):
    r = client.post("/api/auth/login", json={"username": "ahmedibrahim", "password": "Procare@2026"})
    assert r.status_code == 200
    body = r.json()
    assert body["employee"]["role"] == "ceo"
    headers = {"Authorization": f"Bearer {body['token']}"}

    # Wrong old password rejected; too-short new password rejected.
    assert client.post("/api/auth/change-password", json={"old_password": "nope", "new_password": "longenough1"}, headers=headers).status_code == 401
    assert client.post("/api/auth/change-password", json={"old_password": "Procare@2026", "new_password": "short"}, headers=headers).status_code == 422

    ok = client.post("/api/auth/change-password", json={"old_password": "Procare@2026", "new_password": "NewSecret#99"}, headers=headers)
    assert ok.status_code == 200

    assert client.post("/api/auth/login", json={"username": "ahmedibrahim", "password": "Procare@2026"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "ahmedibrahim", "password": "NewSecret#99"}).status_code == 200

    # Restore so other tests (and reruns) see the initial password.
    tok = client.post("/api/auth/login", json={"username": "ahmedibrahim", "password": "NewSecret#99"}).json()["token"]
    client.post(
        "/api/auth/change-password",
        json={"old_password": "NewSecret#99", "new_password": "Procare@2026"},
        headers={"Authorization": f"Bearer {tok}"},
    )
