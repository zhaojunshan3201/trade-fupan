import os
from io import BytesIO
import zipfile
from datetime import datetime

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["AUTO_SYNC_ENABLED"] = "false"

import pytest

from app import create_app
from models import db, Order, TradeReview, TradingPlan, User


@pytest.fixture()
def app():
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        seed_data()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def seed_data():
    u1 = User(username="alice", email="alice@example.com")
    u1.set_password("password")
    u1.api_token = "alice-token"
    u2 = User(username="bob", email="bob@example.com")
    u2.set_password("password")
    db.session.add_all([u1, u2])
    db.session.flush()

    now = datetime.utcnow()
    alice_order = Order(
        ticket=1001,
        user_id=u1.id,
        symbol="EURUSD",
        order_type="buy",
        volume=0.1,
        open_time=now,
        close_time=now,
        open_price=1.1000,
        close_price=1.1100,
        profit=100,
        balance=1100,
        account_number=111,
    )
    bob_order = Order(
        ticket=2001,
        user_id=u2.id,
        symbol="GBPUSD",
        order_type="sell",
        volume=0.2,
        open_time=now,
        close_time=now,
        open_price=1.3000,
        close_price=1.2900,
        profit=900,
        balance=1900,
        account_number=222,
    )
    db.session.add_all([alice_order, bob_order])
    db.session.flush()

    db.session.add(
        TradeReview(
            order_id=bob_order.id,
            user_id=u2.id,
            tags="leak",
            trading_theory="other-system",
            rating=5,
        )
    )
    db.session.add_all([
        TradingPlan(
            user_id=u1.id,
            title="Alice plan",
            symbol="EURUSD",
            direction="buy",
        ),
        TradingPlan(
            user_id=u2.id,
            title="Bob plan",
            symbol="GBPUSD",
            direction="sell",
        ),
    ])
    db.session.commit()


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True


def test_order_detail_does_not_expose_another_users_order(client):
    login_as(client, 1)

    response = client.get("/orders/detail/2")

    assert response.status_code == 404


def test_order_delete_info_reports_review_for_owned_order(client):
    login_as(client, 2)

    response = client.get("/orders/api/2/delete_info")

    assert response.status_code == 200
    data = response.get_json()
    assert data["has_review"] is True
    assert data["ticket"] == 2001


def test_delete_order_removes_owned_order_and_review(client, app):
    login_as(client, 2)

    response = client.delete("/orders/api/2")

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["deleted_review"] is True
    with app.app_context():
        assert Order.query.get(2) is None
        assert TradeReview.query.filter_by(order_id=2).first() is None


def test_cannot_delete_another_users_order(client, app):
    login_as(client, 1)

    response = client.delete("/orders/api/2")

    assert response.status_code == 404
    with app.app_context():
        assert Order.query.get(2) is not None
        assert TradeReview.query.filter_by(order_id=2).first() is not None


def test_bulk_delete_orders_removes_owned_orders_and_reviews(client, app):
    login_as(client, 2)

    response = client.post("/orders/api/bulk_delete", json={"ids": [2]})

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["deleted_count"] == 1
    assert data["deleted_review_count"] == 1
    assert data["skipped_count"] == 0
    with app.app_context():
        assert Order.query.get(2) is None
        assert TradeReview.query.filter_by(order_id=2).first() is None


def test_bulk_delete_orders_skips_another_users_orders(client, app):
    login_as(client, 1)

    response = client.post("/orders/api/bulk_delete", json={"ids": [1, 2]})

    assert response.status_code == 200
    data = response.get_json()
    assert data["deleted_count"] == 1
    assert data["skipped_count"] == 1
    with app.app_context():
        assert Order.query.get(1) is None
        assert Order.query.get(2) is not None
        assert TradeReview.query.filter_by(order_id=2).first() is not None


def test_cannot_create_review_for_another_users_order(client, app):
    login_as(client, 1)

    response = client.post("/review/api/save/2", json={"tags": "stolen"})

    assert response.status_code == 404
    with app.app_context():
        review = TradeReview.query.filter_by(order_id=2).one()
        assert review.tags == "leak"


def test_plan_api_list_is_scoped_to_current_user(client):
    login_as(client, 1)

    response = client.get("/plans/api/list")

    assert response.status_code == 200
    assert [plan["title"] for plan in response.get_json()] == ["Alice plan"]


def test_plan_status_update_requires_owner(client, app):
    login_as(client, 1)

    response = client.post("/plans/api/update_status/2", json={"status": "completed"})

    assert response.status_code == 404
    with app.app_context():
        assert TradingPlan.query.get(2).status == "planned"


def test_analysis_overview_counts_only_current_users_recent_pnl_and_reviews(client):
    login_as(client, 1)

    response = client.get("/analysis/api/overview")

    assert response.status_code == 200
    data = response.get_json()
    assert data["total_pnl"] == 100
    assert data["recent_pnl"] == 100
    assert data["review_count"] == 0
    assert data["review_rate"] == 0


def test_review_summary_counts_only_current_users_reviews(client):
    login_as(client, 1)

    response = client.get("/analysis/api/review_summary")

    assert response.status_code == 200
    data = response.get_json()
    assert data["total_reviews"] == 0
    assert data["top_tags"] == []


def test_review_list_renders_review_tags(client):
    login_as(client, 2)

    response = client.get("/review/")

    assert response.status_code == 200
    assert b"UndefinedError" not in response.data


def test_csv_upload_accepts_api_token_for_client_push(client, app):
    csv_data = (
        b"Ticket,Open Time,Close Time,Symbol,Type,Volume,Open Price,Close Price,Profit\n"
        b"3001,2026.01.01 10:00:00,2026.01.01 11:00:00,USDJPY,buy,0.10,150.0,151.0,10\n"
    )

    response = client.post(
        "/import/upload?token=alice-token",
        data={"file": (BytesIO(csv_data), "orders.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code in (200, 302)
    with app.app_context():
        order = Order.query.filter_by(ticket=3001).one()
        assert order.user_id == 1


def test_client_script_downloads_are_available_after_login(client):
    login_as(client, 1)

    for filename in ("start.bat", "mt5_push.py", "mt4_push.py"):
        response = client.get(f"/accounts/client/{filename}")

        assert response.status_code == 200
        assert response.headers["Content-Disposition"].startswith("attachment;")
        assert response.data


def test_client_package_includes_current_server_and_token(client):
    login_as(client, 1)

    response = client.get(
        "/accounts/client/package.zip",
        headers={
            "X-Forwarded-Host": "59.110.12.91:5000",
            "X-Forwarded-Proto": "http",
        },
    )

    assert response.status_code == 200
    assert response.headers["Content-Disposition"].startswith("attachment;")

    archive = zipfile.ZipFile(BytesIO(response.data))
    names = set(archive.namelist())
    assert {
        "start.bat",
        "start_mt5.bat",
        "start_mt4.bat",
        "mt5_push.py",
        "mt4_push.py",
        "config.ini",
    } <= names

    config = archive.read("config.ini").decode("utf-8")
    assert "url = http://59.110.12.91:5000" in config
    assert "token = alice-token" in config

    start_mt4 = archive.read("start_mt4.bat").decode("utf-8")
    assert "MetaTrader5" not in start_mt4
    assert "pip install --user requests" in start_mt4
