import builtins
import os
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["AUTO_SYNC_ENABLED"] = "false"

import pytest

from app import create_app
from models import AccountInfo, PlatformConfig, User, db


@pytest.fixture()
def app():
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        user = User(username="alice", email="alice@example.com")
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        db.session.add(
            PlatformConfig(
                user_id=user.id,
                name="Alice MT5",
                platform_type="mt5",
                server="Broker-Demo",
            )
        )
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True


def fail_if_metatrader_imported(monkeypatch):
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "MetaTrader5":
            raise ImportError("remote requests must not import server MetaTrader5")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)


def test_remote_mt5_test_does_not_touch_server_terminal(client, monkeypatch):
    login_as(client, 1)
    fail_if_metatrader_imported(monkeypatch)

    response = client.post(
        "/import/api/mt5_test",
        environ_base={"REMOTE_ADDR": "203.0.113.10", "HTTP_HOST": "trade.example.com"},
    )

    assert response.status_code == 409
    data = response.get_json()
    assert data["status"] == "client_connector_required"
    assert data["terminal_running"] is False


def test_remote_mt4_scan_does_not_read_server_appdata(client, monkeypatch):
    login_as(client, 1)

    response = client.get(
        "/import/api/scan_csv",
        environ_base={"REMOTE_ADDR": "203.0.113.10", "HTTP_HOST": "trade.example.com"},
    )

    assert response.status_code == 409
    data = response.get_json()
    assert data["status"] == "client_connector_required"


def test_remote_platform_test_does_not_touch_server_mt5(client, monkeypatch):
    login_as(client, 1)
    fail_if_metatrader_imported(monkeypatch)

    response = client.post(
        "/accounts/api/platforms/1/test",
        environ_base={"REMOTE_ADDR": "203.0.113.10", "HTTP_HOST": "trade.example.com"},
    )

    assert response.status_code == 409
    data = response.get_json()
    assert data["status"] == "client_connector_required"


def test_account_latest_does_not_return_unrelated_global_snapshot(client, app):
    login_as(client, 1)
    with app.app_context():
        db.session.add(
            AccountInfo(
                number=999,
                name="Server Account",
                server="Server-Broker",
                balance=100000,
                terminal_type="mt5",
            )
        )
        db.session.commit()

    response = client.get("/import/api/account_latest")

    assert response.status_code == 200
    assert response.get_json() is None


def test_account_latest_can_filter_by_terminal_type(client, app):
    login_as(client, 1)
    now = datetime.utcnow()
    with app.app_context():
        db.session.add_all(
            [
                AccountInfo(
                    number=60102506,
                    name="MT5 Account",
                    server="MT5-Demo",
                    balance=7934.25,
                    terminal_type="mt5",
                    recorded_at=now + timedelta(seconds=10),
                ),
                AccountInfo(
                    number=1246398492,
                    name="MT4 Account",
                    server="Axi-US03-Demo",
                    balance=100000,
                    terminal_type="mt4",
                    recorded_at=now,
                ),
            ]
        )
        db.session.commit()

    response = client.get("/import/api/account_latest?terminal_type=mt4")

    assert response.status_code == 200
    data = response.get_json()
    assert data["terminal_type"] == "mt4"
    assert data["number"] == 1246398492
