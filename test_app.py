"""Run with:  python -m pytest -q   (pip install pytest)"""
import os
import tempfile

import pytest

fd, path = tempfile.mkstemp(suffix=".db")
os.close(fd)
os.environ["DATABASE"] = path

import app as tracker  # noqa: E402


@pytest.fixture()
def client():
    tracker.app.config["TESTING"] = True
    with tracker.app.test_client() as c:
        yield c


def register_and_login(c, name="akanksha"):
    c.post("/register", data={"username": name, "password": "secret123"})
    return c.post("/login", data={"username": name, "password": "secret123"}, follow_redirects=True)


def test_category_suggestion():
    assert tracker.suggest_category("Lunch at canteen") == "Food"
    assert tracker.suggest_category("Metro ticket") == "Travel"
    assert tracker.suggest_category("random thing") == "Other"


def test_dashboard_requires_login(client):
    assert client.get("/").status_code == 302


def test_register_login_add_edit_delete(client):
    assert b"Smart Expense Tracker" in register_and_login(client).data
    client.post("/add", data={"title": "Pizza", "amount": "250", "category": "", "spent_on": "2025-01-10"})
    page = client.get("/?month=2025-01").data
    assert b"Pizza" in page and b"Food" in page
    with tracker.app.app_context():
        eid = tracker.get_db().execute("SELECT id FROM expenses WHERE title = 'Pizza'").fetchone()[0]
    client.post(f"/edit/{eid}", data={"title": "Pizza party", "amount": "300", "category": "Food", "spent_on": "2025-01-10"})
    assert b"Pizza party" in client.get("/?month=2025-01").data
    client.post(f"/delete/{eid}")
    assert b"Pizza party" not in client.get("/?month=2025-01").data


def test_invalid_amount_rejected(client):
    register_and_login(client, "second")
    r = client.post("/add", data={"title": "x", "amount": "-5", "category": "Food", "spent_on": "2025-01-10"})
    assert b"greater than zero" in r.data


def test_budget_alert_and_csv(client):
    register_and_login(client, "third")
    client.post("/budget", data={"budget": "100"})
    client.post("/add", data={"title": "Book", "amount": "500", "category": "Education", "spent_on": "2025-02-01"})
    assert b"over your budget" in client.get("/?month=2025-02").data
    assert b"Date,Title,Category,Amount" in client.get("/export").data
