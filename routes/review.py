"""复盘路由"""
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from models import db, Order, TradeReview

review_bp = Blueprint('review', __name__)


def _order_for_current_user(order_id):
    query = Order.query.filter_by(id=order_id)
    if not current_user.is_admin:
        query = query.filter_by(user_id=current_user.id)
    return query.first_or_404()


def _review_for_current_user(review_id):
    query = TradeReview.query.join(Order).filter(TradeReview.id == review_id)
    if not current_user.is_admin:
        query = query.filter(Order.user_id == current_user.id)
    return query.first_or_404()


@review_bp.route('/')
@login_required
def review_list():
    """复盘列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    uid = current_user.id
    query = db.session.query(Order).join(TradeReview).filter(Order.user_id == uid).order_by(TradeReview.reviewed_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    orders = []
    for o in pagination.items:
        d = o.to_dict()
        d['review'] = o.review.to_dict()
        orders.append(d)

    return render_template('review.html', orders=orders, pagination=pagination)


@review_bp.route('/order/<int:order_id>')
@login_required
def review_order(order_id):
    """复盘一个订单"""
    order = _order_for_current_user(order_id)
    review = order.review
    return render_template('review_form.html', order=order, review=review)


@review_bp.route('/save/<int:order_id>', methods=['POST'])
@login_required
def save_review(order_id):
    """保存复盘记录"""
    order = _order_for_current_user(order_id)
    data = request.form

    review = order.review
    if review is None:
        review = TradeReview(order_id=order_id, user_id=current_user.id)
        db.session.add(review)

    # 更新字段
    review.fundamental_context = data.get('fundamental_context', '')
    review.major_trend = data.get('major_trend', '')
    review.minor_signal = data.get('minor_signal', '')
    review.trading_theory = data.get('trading_theory', '')
    review.entry_quality = data.get('entry_quality', '')
    review.exit_reason = data.get('exit_reason', '')
    review.emotional_state = data.get('emotional_state', '')
    review.lesson_learned = data.get('lesson_learned', '')
    review.improvement = data.get('improvement', '')
    review.tags = data.get('tags', '')
    review.rating = data.get('rating', type=int)
    review.is_planned_trade = data.get('is_planned_trade') == 'on'
    review.plan_deviation = data.get('plan_deviation', '')
    review.trade_timeframe = data.get('trade_timeframe', '')
    review.reviewed_at = datetime.utcnow()

    db.session.commit()
    return redirect(url_for('review.review_list'))


@review_bp.route('/api/save/<int:order_id>', methods=['POST'])
@login_required
def api_save_review(order_id):
    """API: 保存复盘"""
    order = _order_for_current_user(order_id)
    data = request.json

    review = order.review
    if review is None:
        review = TradeReview(order_id=order_id, user_id=current_user.id)
        db.session.add(review)

    for field in ['fundamental_context', 'major_trend', 'minor_signal', 'trading_theory',
                  'entry_quality', 'exit_reason', 'emotional_state', 'lesson_learned',
                  'improvement', 'tags', 'plan_deviation']:
        if field in data:
            setattr(review, field, data[field])

    if 'rating' in data:
        review.rating = int(data['rating'])
    if 'is_planned_trade' in data:
        review.is_planned_trade = bool(data['is_planned_trade'])
    if 'trade_timeframe' in data:
        review.trade_timeframe = data['trade_timeframe']

    review.reviewed_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'status': 'ok', 'review': review.to_dict()})


@review_bp.route('/api/delete/<int:review_id>', methods=['DELETE'])
@login_required
def api_delete_review(review_id):
    """删除复盘记录"""
    review = _review_for_current_user(review_id)
    db.session.delete(review)
    db.session.commit()
    return jsonify({'status': 'ok'})


# =====================================================================
# K线数据 API — 复盘快照
# =====================================================================

MT5_TIMEFRAME_MAP = {
    'M1': 1, 'M2': 2, 'M3': 3, 'M4': 4, 'M5': 5,
    'M6': 6, 'M10': 10, 'M12': 12, 'M15': 15, 'M20': 20,
    'M30': 30, 'H1': 16385, 'H2': 16386, 'H3': 16387,
    'H4': 16388, 'H6': 16390, 'H8': 16392, 'H12': 16396,
    'D1': 16408, 'W1': 32769, 'MN1': 49153,
}

def guess_timeframe(order):
    """根据持仓时长推断可能的交易周期"""
    mins = order.duration_minutes
    if not mins or mins <= 0:
        return 'M5'  # 默认
    # 大于24小时 → 可能是D1
    if mins > 1440:
        return 'D1'
    # 4-24小时 → H4
    if mins > 240:
        return 'H4'
    # 1-4小时 → H1
    if mins > 60:
        return 'H1'
    # 30-60分钟 → M30
    if mins > 30:
        return 'M30'
    # 15-30分钟 → M15
    if mins > 15:
        return 'M15'
    # 5-15分钟 → M5
    return 'M5'


@review_bp.route('/api/candles/<int:order_id>')
@login_required
def api_candles(order_id):
    """获取订单的K线快照数据"""
    order = _order_for_current_user(order_id)

    # 周期：优先用已保存的复盘周期，未设定则自动推断
    tf_str = request.args.get('tf', '')
    if not tf_str and order.review:
        tf_str = order.review.trade_timeframe or ''
    if not tf_str:
        tf_str = guess_timeframe(order)

    tf_raw = tf_str.upper().strip()
    tf = MT5_TIMEFRAME_MAP.get(tf_raw, 5)  # 默认M5

    # 时间范围：开仓前50根K线 ~ 平仓后50根K线
    from datetime import timedelta
    # 估算每根K线时长（分钟）
    tf_minutes_map = {
        1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 10: 10,
        12: 12, 15: 15, 20: 20, 30: 30,
        16385: 60, 16386: 120, 16387: 180, 16388: 240,
        16390: 360, 16392: 480, 16396: 720,
        16408: 1440, 32769: 10080, 49153: 43200,
    }
    bar_mins = tf_minutes_map.get(tf, 5)
    margin = timedelta(minutes=bar_mins * 55)  # 前后各50根+5根缓冲

    # 确定图表时间范围 (MT5 需要 naive datetime)
    center_time = order.close_time or order.open_time or datetime.utcnow()
    # ensure naive
    if hasattr(center_time, 'tzinfo') and center_time.tzinfo is not None:
        center_time = center_time.replace(tzinfo=None)

    open_dt = order.open_time
    if open_dt and hasattr(open_dt, 'tzinfo') and open_dt.tzinfo is not None:
        open_dt = open_dt.replace(tzinfo=None)

    if not open_dt:
        open_dt = center_time
    if open_dt == center_time:
        # 入场=平仓（导入数据不完整）：以平仓为中心
        start_dt = center_time - margin
        end_dt = center_time + margin
        open_dt = None  # 不标记入场
    else:
        start_dt = open_dt - margin
        end_dt = (order.close_time or center_time) + margin
        if end_dt and hasattr(end_dt, 'tzinfo') and end_dt.tzinfo is not None:
            end_dt = end_dt.replace(tzinfo=None)

    # 尝试从 MT5 获取数据
    candles = []
    source = 'none'

    try:
        import MetaTrader5 as mt5
        initialized = mt5.initialize()
        if initialized:
            rates = mt5.copy_rates_range(order.symbol, tf, start_dt, end_dt)
            if rates is not None and len(rates) > 0:
                source = 'mt5'
                for r in rates:
                    # MT5 返回 numpy.void，用属性/下标访问
                    candles.append({
                        'time': int(r[0]),   # time
                        'open': round(float(r[1]), 5),   # open
                        'high': round(float(r[2]), 5),   # high
                        'low': round(float(r[3]), 5),    # low
                        'close': round(float(r[4]), 5),  # close
                        'volume': int(r[5]) if len(r) > 5 else 0,  # tick_volume
                    })
            mt5.shutdown()
    except ImportError:
        source = 'Error: MetaTrader5 not installed'
    except Exception as e:
        source = f'MT5 error: {e}'

    if not candles:
        return jsonify({
            'status': 'no_data',
            'message': f'未获取到 K线数据。{source}。请确保 MT5 终端已运行，且品种 {order.symbol} 的历史数据已加载。',
            'candles': [],
            'timeframe': tf_str,
            'symbol': order.symbol,
            'debug': source,
        })

    # 找入场/出场时间对应的K线索引
    entry_idx = None
    exit_idx = None
    open_ts = int(order.open_time.timestamp()) if order.open_time else 0
    close_ts = int(order.close_time.timestamp()) if order.close_time else 0

    for i, c in enumerate(candles):
        bar_end = c['time'] + bar_mins * 60
        if entry_idx is None and c['time'] <= open_ts < bar_end:
            entry_idx = i
        if close_ts and exit_idx is None and c['time'] <= close_ts < bar_end:
            exit_idx = i

    return jsonify({
        'status': 'ok',
        'symbol': order.symbol,
        'timeframe': tf_str,
        'source': source,
        'entry_time': order.open_time.strftime('%Y-%m-%d %H:%M:%S') if order.open_time else None,
        'exit_time': order.close_time.strftime('%Y-%m-%d %H:%M:%S') if order.close_time else None,
        'entry_price': order.open_price,
        'exit_price': order.close_price,
        'entry_idx': entry_idx,
        'exit_idx': exit_idx,
        'order_type': order.order_type,
        'candles': candles,
    })
