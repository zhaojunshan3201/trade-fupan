"""管理后台路由"""
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from flask_login import login_required, login_user, current_user
from models import db, User, Order, TradeReview, TradingPlan
from sqlalchemy import func
from werkzeug.security import generate_password_hash

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """管理员权限检查装饰器"""
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('需要管理员权限', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@admin_required
def dashboard():
    """管理后台首页"""
    users = User.query.order_by(User.created_at.desc()).all()

    # 汇总统计
    total_users = len(users)
    total_orders = Order.query.count()
    total_reviews = TradeReview.query.count()
    total_plans = TradingPlan.query.count()

    # 每个用户的详情
    user_stats = []
    for u in users:
        user_stats.append({
            'user': u,
            'order_count': Order.query.filter_by(user_id=u.id).count(),
            'review_count': TradeReview.query.filter_by(user_id=u.id).count(),
            'plan_count': TradingPlan.query.filter_by(user_id=u.id).count(),
            'total_pnl': db.session.query(
                func.sum(Order.profit)
            ).filter(Order.user_id == u.id, Order.close_time.isnot(None)).scalar() or 0,
        })

    return render_template('admin.html',
        users=users,
        total_users=total_users,
        total_orders=total_orders,
        total_reviews=total_reviews,
        total_plans=total_plans,
        user_stats=user_stats,
    )


@admin_bp.route('/api/user_stats')
@admin_required
def api_user_stats():
    """用户统计API"""
    users = User.query.all()
    data = []
    for u in users:
        orders = Order.query.filter_by(user_id=u.id).filter(Order.close_time.isnot(None)).all()
        wins = sum(1 for o in orders if o.profit > 0)
        total = len(orders)
        data.append({
            'id': u.id,
            'username': u.username,
            'role': u.role,
            'trades': total,
            'win_rate': round(wins / total * 100, 1) if total > 0 else 0,
            'pnl': round(sum(o.profit or 0 for o in orders), 2),
            'reviews': TradeReview.query.filter_by(user_id=u.id).count(),
            'plans': TradingPlan.query.filter_by(user_id=u.id).count(),
            'created_at': u.created_at.strftime('%Y-%m-%d') if u.created_at else None,
        })
    return jsonify(data)


# ============================================================
# 用户管理
# ============================================================

@admin_bp.route('/user/<int:user_id>')
@admin_required
def user_detail(user_id):
    """查看用户详情页——订单、复盘、计划一览"""
    user = User.query.get_or_404(user_id)

    # 统计
    orders = Order.query.filter_by(user_id=user_id)\
        .filter(Order.close_time.isnot(None))\
        .order_by(Order.close_time.desc()).limit(50).all()
    wins = sum(1 for o in orders if o.profit > 0)
    total = len(orders)

    # 复盘
    reviews = TradeReview.query.filter_by(user_id=user_id)\
        .order_by(TradeReview.reviewed_at.desc()).limit(50).all()

    # 计划
    plans = TradingPlan.query.filter_by(user_id=user_id)\
        .order_by(TradingPlan.plan_date.desc()).limit(20).all()

    return render_template('admin_user.html',
        user=user,
        orders=orders,
        total_orders=Order.query.filter_by(user_id=user_id).count(),
        wins=wins,
        total=total,
        win_rate=round(wins / total * 100, 1) if total > 0 else 0,
        total_pnl=round(sum(o.profit or 0 for o in orders), 2),
        reviews=reviews,
        plans=plans,
    )


@admin_bp.route('/impersonate/<int:user_id>')
@admin_required
def impersonate(user_id):
    """管理员模拟以其他用户身份登录"""
    user = User.query.get_or_404(user_id)
    login_user(user)
    flash(f'已切换为 {user.username} 的身份，管理员特权已保留', 'info')
    return redirect(url_for('main.index'))


@admin_bp.route('/api/toggle_user/<int:user_id>', methods=['POST'])
@admin_required
def toggle_user(user_id):
    """启用/禁用用户"""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'status': 'error', 'message': '不能禁用自己的账户'})
    user.is_active = not user.is_active
    db.session.commit()
    state = '启用' if user.is_active else '禁用'
    return jsonify({'status': 'ok', 'is_active': user.is_active, 'message': f'用户已{state}'})


@admin_bp.route('/api/delete_user/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """删除用户及其所有数据"""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'status': 'error', 'message': '不能删除自己的账户'})

    # 删除关联数据
    Order.query.filter_by(user_id=user.id).delete()
    TradeReview.query.filter_by(user_id=user.id).delete()
    TradingPlan.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    return jsonify({'status': 'ok', 'message': f'用户 {user.username} 已删除'})


@admin_bp.route('/api/reset_password/<int:user_id>', methods=['POST'])
@admin_required
def reset_password(user_id):
    """重置用户密码"""
    user = User.query.get_or_404(user_id)
    new_pass = request.json.get('password', '123456')
    user.password_hash = generate_password_hash(new_pass)
    db.session.commit()
    return jsonify({'status': 'ok', 'message': f'密码已重置为 {new_pass}'})


# ============================================================
# 复盘点评
# ============================================================

@admin_bp.route('/api/review_note/<int:review_id>', methods=['POST'])
@admin_required
def save_review_note(review_id):
    """管理员对复盘添加点评"""
    review = TradeReview.query.get_or_404(review_id)
    review.admin_note = request.json.get('note', '')
    review.admin_note_at = datetime.utcnow() if review.admin_note else None
    db.session.commit()
    return jsonify({
        'status': 'ok',
        'admin_note': review.admin_note,
        'admin_note_at': review.admin_note_at.strftime('%Y-%m-%d %H:%M') if review.admin_note_at else None,
    })


# ============================================================
# 查看其它用户数据
# ============================================================

@admin_bp.route('/api/user_orders/<int:user_id>')
@admin_required
def user_orders(user_id):
    """查看指定用户的订单"""
    page = request.args.get('page', 1, type=int)
    orders = Order.query.filter_by(user_id=user_id)\
        .order_by(Order.close_time.desc())\
        .limit(50).offset((page - 1) * 50).all()
    return jsonify([o.to_dict() for o in orders])


@admin_bp.route('/api/user_reviews/<int:user_id>')
@admin_required
def user_reviews(user_id):
    """查看指定用户的复盘记录"""
    reviews = db.session.query(TradeReview)\
        .join(Order, TradeReview.order_id == Order.id)\
        .filter(TradeReview.user_id == user_id)\
        .order_by(TradeReview.reviewed_at.desc()).limit(50).all()
    return jsonify([{
        **r.to_dict(),
        'symbol': r.order.symbol,
        'order_type': r.order.order_type,
        'profit': r.order.profit,
        'open_time': r.order.open_time.strftime('%Y-%m-%d %H:%M') if r.order.open_time else None,
    } for r in reviews])


@admin_bp.route('/api/user_stats/<int:user_id>')
@admin_required
def user_stats_detail(user_id):
    """查看指定用户的详细统计"""
    user = User.query.get_or_404(user_id)
    orders = Order.query.filter_by(user_id=user_id).filter(Order.close_time.isnot(None)).all()
    wins = sum(1 for o in orders if o.profit > 0)
    total = len(orders)
    pnl = round(sum(o.profit or 0 for o in orders), 2)

    return jsonify({
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'is_active': user.is_active,
        'trades': total,
        'wins': wins,
        'losses': total - wins,
        'win_rate': round(wins / total * 100, 1) if total > 0 else 0,
        'total_pnl': pnl,
        'reviews': TradeReview.query.filter_by(user_id=user_id).count(),
        'plans': TradingPlan.query.filter_by(user_id=user_id).count(),
        'created_at': user.created_at.strftime('%Y-%m-%d') if user.created_at else None,
    })
