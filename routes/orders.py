"""Order list, detail, and deletion routes."""
from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from models import Order, db

orders_bp = Blueprint('orders', __name__)


def _parse_account_filter(value):
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _account_options_for_user(user_id):
    rows = (
        db.session.query(Order.account_number)
        .filter_by(user_id=user_id)
        .filter(Order.account_number.isnot(None))
        .distinct()
        .order_by(Order.account_number.asc())
        .all()
    )
    return [row[0] for row in rows]


def _apply_account_filter(query, account):
    account_number = _parse_account_filter(account)
    if account_number is None:
        return query
    return query.filter(Order.account_number == account_number)


@orders_bp.route('/')
@login_required
def order_list():
    uid = current_user.id
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    account = request.args.get('account', '')
    symbol = request.args.get('symbol', '')
    order_type = request.args.get('type', '')
    reviewed = request.args.get('reviewed', '')
    sort_by = request.args.get('sort', 'close_time')
    sort_dir = request.args.get('dir', 'desc')

    query = _apply_account_filter(Order.query.filter_by(user_id=uid), account)

    if symbol:
        query = query.filter(Order.symbol == symbol)
    if order_type:
        query = query.filter(Order.order_type == order_type)
    if reviewed == 'yes':
        query = query.filter(Order.review.has())
    elif reviewed == 'no':
        query = query.filter(~Order.review.has())

    sort_col = getattr(Order, sort_by, Order.close_time)
    query = query.order_by(sort_col.asc() if sort_dir == 'asc' else sort_col.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    symbols = [
        row[0]
        for row in db.session.query(Order.symbol)
        .filter_by(user_id=uid)
        .distinct()
        .all()
    ]

    return render_template(
        'orders.html',
        orders=[order.to_dict() for order in pagination.items],
        pagination=pagination,
        symbols=symbols,
        account_options=_account_options_for_user(uid),
        current_account=account,
        current_symbol=symbol,
        current_type=order_type,
        current_reviewed=reviewed,
        current_sort=sort_by,
        current_dir=sort_dir,
    )


@orders_bp.route('/api/list')
@login_required
def order_api_list():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    account = request.args.get('account', '')

    query = _apply_account_filter(
        Order.query.filter_by(user_id=current_user.id),
        account,
    ).order_by(Order.close_time.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'orders': [order.to_dict() for order in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': page,
    })


@orders_bp.route('/detail/<int:order_id>')
@login_required
def order_detail(order_id):
    query = Order.query.filter_by(id=order_id)
    if not current_user.is_admin:
        query = query.filter_by(user_id=current_user.id)
    order = query.first_or_404()
    return jsonify(order.to_dict())


@orders_bp.route('/api/<int:order_id>/delete_info')
@login_required
def order_delete_info(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    return jsonify({
        'id': order.id,
        'ticket': order.ticket,
        'has_review': order.review is not None,
    })


@orders_bp.route('/api/<int:order_id>', methods=['DELETE'])
@login_required
def order_delete(order_id):
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
