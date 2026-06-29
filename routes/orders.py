"""订单列表与详情路由"""
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from models import Order, TradeReview, db

orders_bp = Blueprint('orders', __name__)


@orders_bp.route('/')
@login_required
def order_list():
    """订单列表页面"""
    uid = current_user.id
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    symbol = request.args.get('symbol', '')
    order_type = request.args.get('type', '')
    reviewed = request.args.get('reviewed', '')
    sort_by = request.args.get('sort', 'close_time')
    sort_dir = request.args.get('dir', 'desc')

    query = Order.query.filter_by(user_id=uid)

    if symbol:
        query = query.filter(Order.symbol == symbol)
    if order_type:
        query = query.filter(Order.order_type == order_type)
    if reviewed == 'yes':
        query = query.filter(Order.review.has())
    elif reviewed == 'no':
        query = query.filter(~Order.review.has())

    # 排序
    sort_col = getattr(Order, sort_by, Order.close_time)
    if sort_dir == 'asc':
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    orders = [o.to_dict() for o in pagination.items]

    # 获取所有品种列表用于筛选
    symbols = [r[0] for r in db.session.query(Order.symbol).filter_by(user_id=uid).distinct().all()]

    return render_template('orders.html',
        orders=orders,
        pagination=pagination,
        symbols=symbols,
        current_symbol=symbol,
        current_type=order_type,
        current_reviewed=reviewed,
        current_sort=sort_by,
        current_dir=sort_dir,
    )


@orders_bp.route('/api/list')
@login_required
def order_api_list():
    """订单列表 API"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = Order.query.filter_by(user_id=current_user.id).order_by(Order.close_time.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'orders': [o.to_dict() for o in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': page,
    })


@orders_bp.route('/detail/<int:order_id>')
@login_required
def order_detail(order_id):
    """订单详情"""
    query = Order.query.filter_by(id=order_id)
    if not current_user.is_admin:
        query = query.filter_by(user_id=current_user.id)
    order = query.first_or_404()
    return jsonify(order.to_dict())


@orders_bp.route('/api/<int:order_id>/delete_info')
@login_required
def order_delete_info(order_id):
    """Return deletion warning details for the current user's order."""
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    return jsonify({
        'id': order.id,
        'ticket': order.ticket,
        'has_review': order.review is not None,
    })


@orders_bp.route('/api/<int:order_id>', methods=['DELETE'])
@login_required
def order_delete(order_id):
    """Delete one order owned by the current user."""
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    deleted_review = order.review is not None
    db.session.delete(order)
    db.session.commit()
    return jsonify({
        'status': 'ok',
        'message': '交易记录已删除',
        'deleted_review': deleted_review,
    })


@orders_bp.route('/api/bulk_delete', methods=['POST'])
@login_required
def order_bulk_delete():
    """Delete selected orders owned by the current user."""
    data = request.get_json(silent=True) or {}
    raw_ids = data.get('ids') or []
    order_ids = []
    for raw_id in raw_ids:
        try:
            order_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    if not order_ids:
        return jsonify({'status': 'error', 'message': '请选择要删除的交易记录'}), 400

    requested_ids = set(order_ids)
    orders = (
        Order.query
        .filter(Order.id.in_(requested_ids), Order.user_id == current_user.id)
        .all()
    )
    deleted_review_count = sum(1 for order in orders if order.review is not None)
    deleted_count = len(orders)

    for order in orders:
        db.session.delete(order)
    db.session.commit()

    return jsonify({
        'status': 'ok',
        'message': f'已删除 {deleted_count} 条交易记录',
        'deleted_count': deleted_count,
        'deleted_review_count': deleted_review_count,
        'skipped_count': len(requested_ids) - deleted_count,
    })
