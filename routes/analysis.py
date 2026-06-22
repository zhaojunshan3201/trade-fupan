"""数据分析与统计路由"""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from models import db, Order, TradeReview, User
from sqlalchemy import func, case

analysis_bp = Blueprint('analysis', __name__)


def _filter_user(query):
    """按当前用户过滤"""
    if current_user.is_authenticated:
        return query.filter(Order.user_id == current_user.id)
    return query


def _filter_account(query):
    """如果请求带有 account 参数，则按账号过滤"""
    account = request.args.get('account', '')
    if account.isdigit():
        return query.filter(Order.account_number == int(account))
    return query


def _get_accounts():
    """获取当前用户所有有数据的账号"""
    q = _filter_user(db.session.query(
        Order.account_number, func.count(Order.id)
    )).filter(Order.account_number.isnot(None), Order.account_number > 0)
    rows = q.group_by(Order.account_number).all()
    return [{'number': r[0], 'count': r[1]} for r in rows]


@analysis_bp.route('/')
@login_required
def analysis_dashboard():
    """分析页面"""
    accounts = _get_accounts()
    return render_template('analysis.html', accounts=accounts)


@analysis_bp.route('/api/overview')
@login_required
def api_overview():
    """总体统计概览"""
    query = _filter_user(_filter_account(db.session.query(
        func.count(Order.id).label('total'),
        func.sum(case((Order.close_time.isnot(None), 1), else_=0)).label('closed'),
        func.sum(case((Order.profit > 0, 1), else_=0)).label('wins'),
        func.sum(case((Order.profit < 0, 1), else_=0)).label('losses'),
        func.sum(Order.profit).label('total_pnl'),
        func.avg(Order.profit).label('avg_pnl'),
        func.sum(case((Order.profit > 0, Order.profit), else_=0)).label('total_wins'),
        func.sum(case((Order.profit < 0, Order.profit), else_=0)).label('total_losses'),
        func.max(Order.profit).label('max_win'),
        func.min(Order.profit).label('max_loss'),
    )))
    stats = query.first()

    closed = stats.closed or 0
    wins = stats.wins or 0
    losses = stats.losses or 0
    win_rate = round(wins / closed * 100, 2) if closed > 0 else 0
    total_wins = abs(stats.total_wins or 0)
    total_losses = abs(stats.total_losses or 0)

    # 盈亏比
    avg_win = round(total_wins / wins, 2) if wins > 0 else 0
    avg_loss = round(total_losses / losses, 2) if losses > 0 else 0
    profit_factor = round(total_wins / total_losses, 2) if total_losses > 0 else float('inf')

    # 最大回撤（简化版：按时间顺序计算余额回撤）
    orders = _filter_user(_filter_account(Order.query.filter(
        Order.close_time.isnot(None),
        Order.balance.isnot(None)
    ))).order_by(Order.close_time.asc()).all()

    max_dd = 0
    max_dd_pct = 0
    peak_balance = 0
    if orders:
        peak_balance = orders[0].balance or 0
        for o in orders:
            bal = o.balance or 0
            if bal > peak_balance:
                peak_balance = bal
            dd = peak_balance - bal
            dd_pct = round(dd / peak_balance * 100, 2) if peak_balance > 0 else 0
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct

    # 最近30天盈亏
    month_ago = datetime.utcnow() - timedelta(days=30)
    recent_pnl = _filter_user(_filter_account(db.session.query(func.sum(Order.profit)).filter(
        Order.close_time >= month_ago
    ))).scalar() or 0

    # 复盘率
    total_reviewed = _filter_user(_filter_account(
        db.session.query(func.count(TradeReview.id)).join(Order)
    )).scalar() or 0
    review_rate = round(total_reviewed / closed * 100, 1) if closed > 0 else 0

    return jsonify({
        'total_orders': stats.total or 0,
        'closed_trades': closed,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'total_pnl': round(stats.total_pnl or 0, 2),
        'avg_pnl': round(stats.avg_pnl or 0, 2),
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor if profit_factor != float('inf') else 0,
        'max_win': round(stats.max_win or 0, 2),
        'max_loss': round(stats.max_loss or 0, 2),
        'max_drawdown': round(max_dd, 2),
        'max_drawdown_pct': max_dd_pct,
        'recent_pnl': round(recent_pnl, 2),
        'review_count': total_reviewed,
        'review_rate': review_rate,
    })


@analysis_bp.route('/api/equity_curve')
@login_required
def api_equity_curve():
    """资金曲线数据"""
    orders = _filter_user(_filter_account(Order.query.filter(
        Order.close_time.isnot(None),
        Order.balance.isnot(None)
    ))).order_by(Order.close_time.asc()).all()

    data = []
    for o in orders:
        data.append({
            'date': o.close_time.strftime('%Y-%m-%d %H:%M'),
            'balance': o.balance or 0,
            'profit': o.profit,
            'symbol': o.symbol,
        })

    # 按月聚合
    monthly = {}
    for o in orders:
        month_key = o.close_time.strftime('%Y-%m')
        if month_key not in monthly:
            monthly[month_key] = {'month': month_key, 'pnl': 0, 'trades': 0, 'wins': 0}
        monthly[month_key]['pnl'] += o.profit or 0
        monthly[month_key]['trades'] += 1
        if o.profit > 0:
            monthly[month_key]['wins'] += 1

    monthly_data = []
    running_balance = 0
    for m in sorted(monthly.keys()):
        running_balance += monthly[m]['pnl']
        monthly_data.append({
            'month': m,
            'pnl': round(monthly[m]['pnl'], 2),
            'trades': monthly[m]['trades'],
            'win_rate': round(monthly[m]['wins'] / monthly[m]['trades'] * 100, 1),
            'cumulative': round(running_balance, 2),
        })

    return jsonify({
        'equity_curve': data,
        'monthly': monthly_data,
    })


@analysis_bp.route('/api/by_symbol')
@login_required
def api_by_symbol():
    """按品种统计"""
    query = _filter_user(_filter_account(db.session.query(
        Order.symbol,
        func.count(Order.id).label('total'),
        func.sum(case((Order.profit > 0, 1), else_=0)).label('wins'),
        func.sum(Order.profit).label('pnl'),
    ).filter(Order.close_time.isnot(None)).group_by(Order.symbol)))
    results = query.all()

    data = []
    for r in results:
        total = r.total or 0
        wins = r.wins or 0
        win_rate = round(wins / total * 100, 1) if total > 0 else 0
        data.append({
            'symbol': r.symbol,
            'trades': total,
            'wins': wins,
            'losses': total - wins,
            'win_rate': win_rate,
            'pnl': round(r.pnl or 0, 2),
        })

    data.sort(key=lambda x: abs(x['pnl']), reverse=True)
    return jsonify(data)


@analysis_bp.route('/api/by_type')
@login_required
def api_by_type():
    """按方向统计"""
    query = _filter_user(_filter_account(db.session.query(
        Order.order_type,
        func.count(Order.id).label('total'),
        func.sum(case((Order.profit > 0, 1), else_=0)).label('wins'),
        func.sum(Order.profit).label('pnl'),
    ).filter(Order.close_time.isnot(None)).group_by(Order.order_type)))
    results = query.all()

    data = []
    for r in results:
        total = r.total or 0
        wins = r.wins or 0
        win_rate = round(wins / total * 100, 1) if total > 0 else 0
        data.append({
            'type': r.order_type,
            'trades': total,
            'wins': wins,
            'losses': total - wins,
            'win_rate': win_rate,
            'pnl': round(r.pnl or 0, 2),
        })
    return jsonify(data)


@analysis_bp.route('/api/review_summary')
@login_required
def api_review_summary():
    """复盘结论汇总"""
    reviews = _filter_user(_filter_account(TradeReview.query.join(Order))).all()

    # 标签统计
    tag_counter = {}
    for r in reviews:
        if r.tags:
            for tag in r.tags.split(','):
                tag = tag.strip()
                if tag:
                    tag_counter[tag] = tag_counter.get(tag, 0) + 1

    # 交易理论统计
    theory_counter = {}
    for r in reviews:
        if r.trading_theory:
            theory = r.trading_theory.strip()
            if theory:
                theory_counter[theory] = theory_counter.get(theory, 0) + 1

    # 入场质量分布
    quality_dist = {}
    for r in reviews:
        if r.entry_quality:
            q = r.entry_quality.strip().upper()
            quality_dist[q] = quality_dist.get(q, 0) + 1

    # 情绪分布
    emotion_dist = {}
    for r in reviews:
        if r.emotional_state:
            e = r.emotional_state.strip()
            emotion_dist[e] = emotion_dist.get(e, 0) + 1

    # 趋势状态分布
    trend_dist = {}
    for r in reviews:
        if r.major_trend:
            t = r.major_trend.strip()
            trend_dist[t] = trend_dist.get(t, 0) + 1

    # 常见教训
    lessons = [r for r in reviews if r.lesson_learned]

    top_tags = sorted(tag_counter.items(), key=lambda x: x[1], reverse=True)[:15]
    top_theories = sorted(theory_counter.items(), key=lambda x: x[1], reverse=True)

    return jsonify({
        'total_reviews': len(reviews),
        'top_tags': [{'name': k, 'count': v} for k, v in top_tags],
        'top_theories': [{'name': k, 'count': v} for k, v in top_theories],
        'quality_distribution': [{'name': k, 'count': v} for k, v in sorted(quality_dist.items())],
        'emotion_distribution': [{'name': k, 'count': v} for k, v in sorted(emotion_dist.items())],
        'trend_distribution': [{'name': k, 'count': v} for k, v in sorted(trend_dist.items())],
        'lessons_count': len(lessons),
    })


@analysis_bp.route('/api/review_insights')
@login_required
def api_review_insights():
    """复盘洞察：复盘质量 vs 盈亏表现"""
    from sqlalchemy import outerjoin

    # 有复盘的单 vs 无复盘的单
    reviewed_orders = _filter_user(_filter_account(
        db.session.query(Order).join(TradeReview).filter(Order.close_time.isnot(None))
    )).all()
    unreviewed_orders = _filter_user(_filter_account(db.session.query(Order).outerjoin(TradeReview).filter(
        TradeReview.id.is_(None), Order.close_time.isnot(None)
    ))).all()

    reviewed_pnl = sum(o.profit or 0 for o in reviewed_orders)
    unreviewed_pnl = sum(o.profit or 0 for o in unreviewed_orders)
    reviewed_count = len(reviewed_orders)
    unreviewed_count = len(unreviewed_orders)
    reviewed_wins = sum(1 for o in reviewed_orders if o.profit > 0)
    unreviewed_wins = sum(1 for o in unreviewed_orders if o.profit > 0)

    return jsonify({
        'reviewed': {
            'count': reviewed_count,
            'pnl': round(reviewed_pnl, 2),
            'win_rate': round(reviewed_wins / reviewed_count * 100, 1) if reviewed_count else 0,
            'avg_pnl': round(reviewed_pnl / reviewed_count, 2) if reviewed_count else 0,
        },
        'unreviewed': {
            'count': unreviewed_count,
            'pnl': round(unreviewed_pnl, 2),
            'win_rate': round(unreviewed_wins / unreviewed_count * 100, 1) if unreviewed_count else 0,
            'avg_pnl': round(unreviewed_pnl / unreviewed_count, 2) if unreviewed_count else 0,
        },
    })
