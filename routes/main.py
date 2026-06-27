"""主页路由"""
from pathlib import Path

from flask import Blueprint, abort, render_template, send_from_directory
from flask_login import login_required, current_user
from models import db, User, Order, TradeReview, TradingPlan
from sqlalchemy import func, desc

main_bp = Blueprint('main', __name__)

MT4_EXPORT_DIR = Path(__file__).resolve().parent.parent / 'mt4_export'
MT4_EXPORT_FILES = {'TradeExport.mq4', 'AccountInfo.mq4', 'mql4_setup.md', 'README.md'}


@main_bp.route('/mt4_export/<path:filename>')
def download_mt4_export(filename):
    """Download bundled MT4 export scripts."""
    if filename not in MT4_EXPORT_FILES:
        abort(404)
    return send_from_directory(MT4_EXPORT_DIR, filename, as_attachment=True)


@main_bp.route('/')
def home():
    """公开社区主页"""
    # 最新交易计划
    latest_plans = db.session.query(TradingPlan, User.username)\
        .join(User, TradingPlan.user_id == User.id)\
        .filter(TradingPlan.is_public == True)\
        .order_by(TradingPlan.created_at.desc()).limit(10).all()

    # 最新复盘
    latest_reviews = db.session.query(TradeReview, User.username, Order.symbol, Order.order_type, Order.profit)\
        .join(User, TradeReview.user_id == User.id)\
        .join(Order, TradeReview.order_id == Order.id)\
        .filter(TradeReview.is_public == True)\
        .order_by(TradeReview.reviewed_at.desc()).limit(10).all()

    # 复盘精华（评分≥4）
    featured_reviews = db.session.query(TradeReview, User.username, Order.symbol, Order.order_type, Order.profit)\
        .join(User, TradeReview.user_id == User.id)\
        .join(Order, TradeReview.order_id == Order.id)\
        .filter(TradeReview.is_public == True, TradeReview.rating >= 4)\
        .order_by(TradeReview.rating.desc(), TradeReview.reviewed_at.desc()).limit(6).all()

    # 交易排名（按总盈亏）
    rankings = db.session.query(
        User.username, User.id,
        func.count(Order.id).label('trades'),
        func.sum(db.case((Order.profit > 0, 1), else_=0)).label('wins'),
        func.sum(Order.profit).label('total_pnl'),
    ).join(Order, Order.user_id == User.id)\
     .filter(Order.close_time.isnot(None))\
     .group_by(User.id).having(func.count(Order.id) >= 3)\
     .order_by(desc('total_pnl')).limit(10).all()

    # 总交易统计（全局）
    total_orders = Order.query.count()
    total_reviews = TradeReview.query.filter_by(is_public=True).count()
    total_users = User.query.count()

    return render_template('home.html',
        latest_plans=latest_plans,
        latest_reviews=latest_reviews,
        featured_reviews=featured_reviews,
        rankings=rankings,
        total_orders=total_orders,
        total_reviews=total_reviews,
        total_users=total_users,
    )


@main_bp.route('/dashboard')
@login_required
def index():
    """个人仪表盘"""
    uid = current_user.id
    total_orders = Order.query.filter_by(user_id=uid).count()
    total_reviewed = TradeReview.query.filter_by(user_id=uid).count()
    total_plans = TradingPlan.query.filter_by(user_id=uid).count()

    base = db.session.query(Order).filter(Order.user_id == uid)
    stats = base.with_entities(
        func.count(Order.id).label('total'),
        func.sum(Order.profit).label('total_pnl'),
        func.avg(Order.profit).label('avg_pnl'),
        func.sum(db.case((Order.profit > 0, 1), else_=0)).label('wins'),
        func.sum(db.case((Order.profit < 0, 1), else_=0)).label('losses'),
    ).filter(Order.close_time.isnot(None)).first()

    win_count = stats.wins or 0
    loss_count = stats.losses or 0
    total_closed = win_count + loss_count
    win_rate = round(win_count / total_closed * 100, 1) if total_closed > 0 else 0
    total_pnl = round(stats.total_pnl or 0, 2)
    avg_pnl = round(stats.avg_pnl or 0, 2)

    recent_orders = Order.query.filter_by(user_id=uid).order_by(Order.close_time.desc()).limit(5).all()

    unreviewed_count = db.session.query(func.count(Order.id))\
        .outerjoin(TradeReview, Order.id == TradeReview.order_id)\
        .filter(TradeReview.id.is_(None), Order.close_time.isnot(None), Order.user_id == uid).scalar() or 0

    active_plans = TradingPlan.query.filter_by(user_id=uid).filter(
        TradingPlan.status.in_(['planned', 'active'])
    ).order_by(TradingPlan.plan_date.desc()).limit(5).all()

    return render_template('index.html',
        total_orders=total_orders,
        total_reviewed=total_reviewed,
        total_plans=total_plans,
        total_closed=total_closed,
        win_count=win_count,
        loss_count=loss_count,
        win_rate=win_rate,
        total_pnl=total_pnl,
        avg_pnl=avg_pnl,
        recent_orders=recent_orders,
        unreviewed_count=unreviewed_count,
        active_plans=active_plans,
    )
