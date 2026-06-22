# Cockpit Ledger Homepage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the public homepage into the approved Cockpit Ledger trading review homepage.

**Architecture:** Keep the existing Flask route and data contract unchanged. Replace the homepage template with a self-contained Jinja/CSS homepage that renders current `latest_plans`, `latest_reviews`, `featured_reviews`, `rankings`, and total counters. Add a focused smoke test for homepage rendering and key copy.

**Tech Stack:** Flask, Jinja2, pytest, CSS Grid, vanilla CSS.

---

## File Structure

- Modify `templates/home.html`: replace the current public homepage markup and page-scoped CSS with Cockpit Ledger layout.
- Create `tests/test_homepage_render.py`: Flask test-client smoke test for the public homepage with seeded data.
- No route, database, auth, or import logic changes.

## Task 1: Homepage Render Smoke Test

**Files:**
- Create: `tests/test_homepage_render.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests\test_homepage_render.py -q`

Expected: FAIL because the current homepage does not include the Cockpit Ledger copy.

## Task 2: Replace Homepage Template

**Files:**
- Modify: `templates/home.html`

- [ ] **Step 1: Replace page-specific CSS and markup**

Implement a Jinja template with:

- `{% extends "base.html" %}`
- `{% block title %}交易复盘审计台{% endblock %}`
- A page-scoped style block using the approved palette.
- A `.ledger-home` root element.
- A `.ledger-hero` asymmetric grid.
- A `.review-ledger` for `latest_reviews`.
- A `.plan-ledger` for `latest_plans`.
- A `.ranking-ledger` for `rankings`.
- A `.featured-ledger` for `featured_reviews`.

- [ ] **Step 2: Preserve dynamic data loops**

Use the existing context variables:

```jinja2
{{ total_orders }}
{{ total_reviews }}
{{ total_users }}
{% for review, username, symbol, otype, profit in latest_reviews %}
{% for plan, username in latest_plans %}
{% for r in rankings %}
{% for review, username, symbol, otype, profit in featured_reviews %}
```

If a list is empty, show compact Chinese empty-state text.

- [ ] **Step 3: Run render test**

Run: `python -m pytest tests\test_homepage_render.py -q`

Expected: PASS.

## Task 3: Visual and Regression Verification

**Files:**
- No source changes unless verification exposes a concrete issue.

- [ ] **Step 1: Compile Python**

Run:

```powershell
$files = @('app.py','config.py','models.py') + (Get-ChildItem routes -Filter *.py | ForEach-Object { $_.FullName }) + (Get-ChildItem mt4_connect,mt5_connect,client -Filter *.py | ForEach-Object { $_.FullName }); python -m py_compile @files
```

Expected: exit code 0.

- [ ] **Step 2: Run focused tests**

Run:

```powershell
python -m pytest tests\test_homepage_render.py tests\test_user_isolation.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Browser screenshot check**

Start Flask with `AUTO_SYNC_ENABLED=false` if needed, open `/`, and capture desktop and mobile screenshots. Verify:

- The hero is asymmetric on desktop.
- Mobile has no horizontal overflow.
- Chinese homepage copy is readable.
- No purple/neon/pure-black homepage styling.

Because this project is not a git repository, do not run commit steps.

## Self-Review

- Spec coverage: hero, palette, typography, content architecture, responsive rules, and verification are covered.
- Placeholder scan: no TBD/TODO placeholder tasks remain.
- Scope: only homepage template plus smoke test.
