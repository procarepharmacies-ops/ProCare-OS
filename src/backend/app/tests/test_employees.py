"""Employee endpoints: the /summary route-shadowing regression, and
create-employee (with-login and HR-only/no-login accounts)."""
from __future__ import annotations

from app.services import auth as auth_svc


def test_employee_summary_route_is_not_shadowed_by_employee_id(client):
    """Regression: /{employee_id} was registered before /summary, so FastAPI
    tried to parse "summary" as an int and every summary request 422'd."""
    r = client.get("/api/employees/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_employees"] >= 1


def test_employee_jobs_list_route_not_shadowed(client):
    r = client.get("/api/employees/jobs/list")
    assert r.status_code == 200
    assert "jobs" in r.json()


def test_create_employee_with_login(client):
    r = client.post(
        "/api/employees",
        json={"name_ar": "يوسف أبو زيد", "name_en": "Yousef Abuzaid", "role": "manager"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "yousefabuzaid"
    assert body["role"] == "manager"
    assert body["has_login"] is True
    assert body["password"]  # returned once, at creation

    # The generated account can actually log in with the returned password.
    login = client.post("/api/auth/login", json={"username": body["username"], "password": body["password"]})
    assert login.status_code == 200
    assert login.json()["employee"]["role"] == "manager"


def test_create_employee_username_collision_gets_suffixed(client):
    a = client.post("/api/employees", json={"name_ar": "علاء أ", "name_en": "Alaa Mohamed", "role": "assistant"})
    b = client.post("/api/employees", json={"name_ar": "علاء ب", "name_en": "Alaa Magdy", "role": "assistant"})
    assert a.json()["username"] != b.json()["username"]


def test_create_employee_without_login_has_no_usable_credentials(client):
    r = client.post(
        "/api/employees",
        json={"name_ar": "أم أدهم", "name_en": None, "has_login": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["username"] is None
    assert body["password"] is None
    assert body["has_login"] is False

    # The row exists (visible in the list) but nobody can log into it — there
    # is no username to even attempt, by construction.
    listing = client.get("/api/employees/list").json()["employees"]
    assert any(e["employee_id"] == body["employee_id"] for e in listing)


def test_create_employee_rejects_invalid_role(client):
    r = client.post("/api/employees", json={"name_ar": "x", "role": "superadmin"})
    assert r.status_code == 422


def test_slugify_username_falls_back_without_latin_name(session):
    from app.services import employees as emp_svc

    username = emp_svc._slugify_username(session, None, "بدون اسم إنجليزي")
    assert username.startswith("staff")
