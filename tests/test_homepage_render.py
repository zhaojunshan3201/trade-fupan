import os
from datetime import date, datetime

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["AUTO_SYNC_ENABLED"] = "false"

from app import create_app
from models import db, Order, TradeReview, TradingPlan, User


def test_homepage_renders_cockpit_ledger_content():
    app = create_app()
    app.config.update(TESTING=True)

    with app.app_context():
        user = User(username="desk", email="desk@example.com")
        user.set_password("password")
        db.session.add(user)
        db.session.flush()

        order = Order(
            ticket=9001,
            user_id=user.id,
            symbol="EURUSD",
            order_type="buy",
            volume=0.1,
            open_time=datetime(2026, 1, 1, 9, 0),
            close_time=datetime(2026, 1, 1, 10, 0),
            open_price=1.08,
            close_price=1.09,
            profit=42.5,
            balance=1042.5,
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(TradeReview(
            order_id=order.id,
            user_id=user.id,
            lesson_learned="等待回踩后入场，执行质量更稳定。",
            major_trend="上升",
            trading_theory="趋势跟随",
            entry_quality="A",
            rating=5,
            is_public=True,
        ))
        db.session.add(TradingPlan(
            user_id=user.id,
            title="等待伦敦盘突破回踩",
            symbol="EURUSD",
            direction="buy",
            plan_date=date(2026, 1, 1),
            is_public=True,
        ))
        db.session.commit()

    response = app.test_client().get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "复盘不是回忆" in html
    assert "Cockpit Ledger" in html
    assert "EURUSD" in html
    assert "等待回踩后入场" in html
    assert "等待伦敦盘突破回踩" in html
    assert "{%" not in html
    assert "{{" not in html
    assert "total_orders" not in html


def test_mt4_export_files_are_downloadable():
    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    for filename in ("TradeExport.mq4", "AccountInfo.mq4"):
        response = client.get(f"/mt4_export/{filename}")

        assert response.status_code == 200
        assert response.headers["Content-Disposition"].startswith("attachment;")
        assert filename.encode() in response.data[:200]
