"""MT4 数据导入路由"""
import os
import csv
import uuid
from io import TextIOWrapper
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from config import Config
from models import db, Order, AccountInfo
from routes.terminal_access import allows_server_terminal_access, client_connector_required_response

import_bp = Blueprint('import_data', __name__)


# MT4 标准导出的列名映射（中文券商常见列名）
MT4_COLUMN_MAPPINGS = {
    # 标准英文
    'ticket': 'ticket',
    'order': 'ticket',
    'open time': 'open_time',
    'close time': 'close_time',
    'symbol': 'symbol',
    'type': 'order_type',
    'volume': 'volume',
    'lots': 'volume',
    'open price': 'open_price',
    'close price': 'close_price',
    'sl': 'sl',
    'stop loss': 'sl',
    'tp': 'tp',
    'take profit': 'tp',
    'commission': 'commission',
    'swap': 'swap',
    'profit': 'profit',
    'balance': 'balance',
    'comment': 'comment',
    'magic': 'magic',
    # 常见中文
    '订单号': 'ticket',
    '开仓时间': 'open_time',
    '平仓时间': 'close_time',
    '品种': 'symbol',
    '类型': 'order_type',
    '手数': 'volume',
    '开仓价': 'open_price',
    '平仓价': 'close_price',
    '止损价': 'sl',
    '止盈价': 'tp',
    '手续费': 'commission',
    '库存费': 'swap',
    '盈亏': 'profit',
    '余额': 'balance',
    '注释': 'comment',
    '魔术号': 'magic',
}


def parse_mt4_datetime(value):
    """解析 MT4 日期时间格式"""
    if not value or value.strip() == '':
        return None
    value = value.strip()
    # 尝试常见格式
    formats = [
        '%Y.%m.%d %H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y/%m/%d %H:%M:%S',
        '%Y.%m.%d %H:%M',
        '%Y-%m-%d %H:%M',
        '%Y/%m/%d %H:%M',
        '%Y-%m-%d',
        '%Y.%m.%d',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_mt4_type(value):
    """解析 MT4 订单类型"""
    v = value.strip().lower()
    if v in ('buy', 'buy limit', 'buy stop'):
        return 'buy'
    if v in ('sell', 'sell limit', 'sell stop'):
        return 'sell'
    if 'buy' in v:
        return 'buy'
    if 'sell' in v:
        return 'sell'
    # 中文
    if '买' in v:
        return 'buy'
    if '卖' in v or '沽' in v:
        return 'sell'
    return v


@import_bp.route('/')
@login_required
def import_page():
    """导入页面"""
    return render_template('import.html')


@import_bp.route('/mt4_connect')
@login_required
def mt4_connect():
    """MT4 自动连接页面"""
    from models import Order
    order_count = Order.query.count()
    return render_template('mt4_connect.html', order_count=order_count)


@import_bp.route('/mt5_connect')
@login_required
def mt5_connect():
    """MT5 官方直连页面"""
    from models import Order
    order_count = Order.query.count()
    return render_template('mt5_connect.html', order_count=order_count)


@import_bp.route('/api/mt5_test', methods=['POST'])
def api_mt5_test():
    """测试 MT5 连接是否可用"""
    if not allows_server_terminal_access():
        return client_connector_required_response('MT5')

    try:
        return _do_mt5_test()
    except Exception as e:
        import traceback
        return jsonify({
            'package_installed': False,
            'terminal_running': False,
            'account_connected': False,
            'account': None,
            'error': f'服务器内部错误: {e}',
            'traceback': str(traceback.format_exc()),
        })


def _do_mt5_test():
    result = {
        'package_installed': False,
        'terminal_running': False,
        'account_connected': False,
        'account': None,
        'error': None,
    }

    # 1. 检查 MetaTrader5 包
    try:
        import MetaTrader5 as mt5
        result['package_installed'] = True
    except ImportError:
        result['error'] = 'MetaTrader5 包未安装。请运行: pip install MetaTrader5'
        return jsonify(result)

    # 2. 连接 MT5 终端
    try:
        initialized = mt5.initialize()
        if not initialized:
            err = mt5.last_error()
            result['error'] = f'连接失败: {err}。请确保 MT5 正在运行且已登录。'
            mt5.shutdown()
            return jsonify(result)
        result['terminal_running'] = True
    except Exception as e:
        result['error'] = f'连接异常: {e}'
        return jsonify(result)

    # 3. 获取账户信息
    try:
        info = mt5.account_info()
        if info is not None:
            result['account_connected'] = True
            result['account'] = {
                'number': info.login,
                'name': info.name,
                'server': info.server,
                'company': info.company,
                'currency': info.currency,
                'leverage': info.leverage,
                'balance': info.balance,
                'equity': info.equity,
                'is_demo': info.trade_mode == 0,
                'terminal_type': 'mt5',
            }
        else:
            result['error'] = '已连接 MT5，但未获取到账户信息。请确认已登录。'
    except Exception as e:
        result['error'] = f'获取账户信息失败: {e}'
    finally:
        mt5.shutdown()

    return jsonify(result)


@import_bp.route('/api/mt5_import', methods=['POST'])
def api_mt5_import():
    """在服务端直接执行 MT5 导入"""
    if not allows_server_terminal_access():
        return client_connector_required_response('MT5')

    try:
        days = request.json.get('days', 0) if request.is_json else 0
    except Exception:
        days = 0

    def run_import():
        """在后台线程执行导入，通过队列传递日志"""
        logs = []
        def log(msg, level='info'):
            logs.append({'msg': msg, 'level': level})

        try:
            import MetaTrader5 as mt5
        except ImportError:
            log('❌ MetaTrader5 包未安装', 'error')
            log('请运行: pip install MetaTrader5', 'info')
            return {'status': 'error', 'logs': logs}

        # 连接
        log('🔄 正在连接 MT5 终端...', 'info')
        try:
            initialized = mt5.initialize()
            if not initialized:
                err = mt5.last_error()
                log(f'❌ 连接失败: {err}', 'error')
                log('请确保: MT5正在运行、已登录、允许DLL导入已勾选', 'warn')
                return {'status': 'error', 'logs': logs}
        except Exception as e:
            log(f'❌ 连接异常: {e}', 'error')
            return {'status': 'error', 'logs': logs}

        log('✅ MT5 连接成功', 'success')

        # 账户信息
        info = mt5.account_info()
        if info:
            log(f'🏦 账户: {info.login} ({info.server})  余额: ${info.balance:.2f}', 'success')
            # 推送到Flask
            account_data = {
                'number': info.login, 'name': info.name, 'company': info.company,
                'server': info.server, 'currency': info.currency, 'leverage': info.leverage,
                'balance': info.balance, 'equity': info.equity, 'profit': info.profit,
                'free_margin': info.margin_free, 'margin': info.margin,
                'is_demo': info.trade_mode == 0, 'terminal': 'MetaTrader 5',
                'terminal_type': 'mt5',
            }
            try:
                import requests as req
                req.post('http://127.0.0.1:5000/import/api/mql4_push_account',
                        json=account_data, timeout=10)
            except Exception:
                pass

        # 获取历史
        from datetime import datetime, timedelta
        if days > 0:
            from_date = datetime.now() - timedelta(days=days)
        else:
            from_date = datetime(2010, 1, 1)  # MT5 最早支持 2010-01-01

        log(f'📊 正在获取历史成交 ({from_date.date()} ~ 今天)...', 'info')
        try:
            deals = mt5.history_deals_get(from_date, datetime.now())
        except Exception as e:
            log(f'❌ 获取历史成交失败: {e}', 'error')
            log('💡 可能原因: MT5终端正忙、连接超时、或参数错误', 'warn')
            mt5.shutdown()
            return {'status': 'error', 'imported': 0, 'logs': logs}

        if deals is None or len(deals) == 0:
            log('📭 没有找到历史成交记录', 'warn')
            mt5.shutdown()
            return {'status': 'ok', 'imported': 0, 'logs': logs}

        log(f'📄 找到 {len(deals)} 条成交记录，正在整理...', 'info')

        # 整理订单
        orders = []
        for deal in deals:
            if deal.entry != 1:  # 只取平仓
                continue
            order = {
                'ticket': deal.ticket,
                'symbol': deal.symbol,
                'type': 'buy' if deal.type in (0, 2) else 'sell',
                'volume': deal.volume,
                'open_price': deal.price,
                'close_price': deal.price,
                'close_time': datetime.fromtimestamp(deal.time).strftime('%Y.%m.%d %H:%M:%S'),
                'profit': deal.profit, 'commission': deal.commission, 'swap': deal.swap,
                'comment': deal.comment or '', 'magic': deal.magic,
            }
            # 从订单获取入场价
            order_history = mt5.history_orders_get(ticket=deal.order)
            if order_history and len(order_history) > 0:
                oh = order_history[0]
                order['open_price'] = oh.price_open
                order['open_time'] = datetime.fromtimestamp(oh.time_setup).strftime('%Y.%m.%d %H:%M:%S')
                order['sl'] = oh.sl
                order['tp'] = oh.tp
            orders.append(order)

        log(f'📦 整理完成: {len(orders)} 条有效平仓记录，正在推送...', 'info')

        # 推送到 Flask
        try:
            import requests as req
            mt5_account = info.login if info else None
            payload = {'account_number': mt5_account, 'orders': orders} if mt5_account else orders
            resp = req.post('http://127.0.0.1:5000/import/api/mql4_push',
                          json=payload, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                log(f'✅ 导入成功: {data.get("imported", 0)} 条新记录 (跳过 {data.get("skipped", 0)} 条)', 'success')
            else:
                log(f'❌ 推送失败: HTTP {resp.status_code}', 'error')
        except Exception as e:
            log(f'❌ 推送异常: {e}', 'error')

        mt5.shutdown()
        log(f'🔌 MT5 连接已关闭', 'info')
        return {'status': 'ok', 'imported': len(orders), 'logs': logs}

    # 执行导入
    try:
        result = run_import()
        return jsonify(result)
    except Exception as e:
        import traceback
        logs = [{'msg': f'❌ 服务器内部错误: {e}', 'level': 'error'}]
        logs.append({'msg': str(traceback.format_exc()), 'level': 'error'})
        return jsonify({'status': 'error', 'imported': 0, 'logs': logs})


@import_bp.route('/upload', methods=['POST'])
@login_required
def upload_csv():
    """上传并解析 CSV 文件"""
    if 'file' not in request.files:
        flash('请选择文件', 'danger')
        return redirect(url_for('import_data.import_page'))

    file = request.files['file']
    if file.filename == '':
        flash('请选择文件', 'danger')
        return redirect(url_for('import_data.import_page'))

    if not file.filename.endswith('.csv'):
        flash('请上传 CSV 格式文件', 'danger')
        return redirect(url_for('import_data.import_page'))

    batch_id = str(uuid.uuid4())[:8]
    imported = 0
    skipped = 0
    errors = []

    try:
        stream = TextIOWrapper(file.stream, encoding='utf-8-sig')
        reader = csv.DictReader(stream)

        if reader.fieldnames is None:
            flash('无法解析 CSV 文件头部', 'danger')
            return redirect(url_for('import_data.import_page'))

        # 映射列名
        header_map = {}
        for col in reader.fieldnames:
            col_lower = col.strip().lower()
            if col_lower in MT4_COLUMN_MAPPINGS:
                header_map[col] = MT4_COLUMN_MAPPINGS[col_lower]
            elif col_lower.replace(' ', '') in MT4_COLUMN_MAPPINGS:
                header_map[col] = MT4_COLUMN_MAPPINGS[col_lower.replace(' ', '')]

        if 'ticket' not in header_map.values():
            flash(f'无法识别CSV列名: {", ".join(reader.fieldnames)}。<br>请确保包含 订单号(Ticket) 和 品种(Symbol) 等列。', 'danger')
            return redirect(url_for('import_data.import_page'))

        for row_idx, row in enumerate(reader, 1):
            try:
                mapped = {}
                for orig_col, mapped_col in header_map.items():
                    mapped[mapped_col] = row.get(orig_col, '').strip()

                ticket = int(float(mapped.get('ticket', 0)))
                if not ticket:
                    skipped += 1
                    continue

                # 检查是否已存在
                existing = Order.query.filter_by(ticket=ticket).first()
                if existing:
                    skipped += 1
                    continue

                symbol = mapped.get('symbol', '').upper()
                if not symbol:
                    skipped += 1
                    continue

                order_type = parse_mt4_type(mapped.get('order_type', ''))

                volume = float(mapped.get('volume', 0))
                if volume <= 0:
                    skipped += 1
                    continue

                open_price = float(mapped.get('open_price', 0))
                close_price_str = mapped.get('close_price', '')
                close_price = float(close_price_str) if close_price_str else None

                open_time = parse_mt4_datetime(mapped.get('open_time', ''))
                close_time = parse_mt4_datetime(mapped.get('close_time', ''))

                profit = float(mapped.get('profit', 0))
                balance = float(mapped.get('balance')) if mapped.get('balance') else None

                # 创建订单
                order = Order(
                    ticket=ticket,
                    symbol=symbol,
                    order_type=order_type,
                    volume=volume,
                    open_time=open_time or datetime.utcnow(),
                    close_time=close_time,
                    open_price=open_price,
                    close_price=close_price,
                    sl=float(mapped['sl']) if mapped.get('sl') else None,
                    tp=float(mapped['tp']) if mapped.get('tp') else None,
                    commission=float(mapped.get('commission', 0)),
                    swap=float(mapped.get('swap', 0)),
                    profit=profit,
                    balance=balance,
                    comment=mapped.get('comment', ''),
                    magic=int(float(mapped['magic'])) if mapped.get('magic') else None,
                    import_batch=batch_id,
                    user_id=current_user.id,
                )
                db.session.add(order)
                imported += 1

            except (ValueError, KeyError) as e:
                errors.append(f'第{row_idx}行: {str(e)}')

        db.session.commit()
        flash(f'导入完成！成功 {imported} 条，跳过 {skipped} 条（已存在或不完整）'
              + (f'，{len(errors)} 条错误' if errors else ''), 'success' if imported else 'warning')

    except Exception as e:
        db.session.rollback()
        flash(f'导入失败: {str(e)}', 'danger')

    return redirect(url_for('import_data.import_page'))


@import_bp.route('/sample')
def download_sample():
    """下载样例 CSV"""
    import io
    sample = (
        "Ticket,Open Time,Close Time,Symbol,Type,Volume,Open Price,Close Price,SL,TP,Commission,Swap,Profit,Balance,Comment\n"
        "1001,2024.01.15 08:00:00,2024.01.15 16:30:00,EURUSD,buy,0.10,1.09500,1.09800,1.09200,1.10000,-0.50,-1.20,25.30,10025.30,\"趋势跟随\"\n"
        "1002,2024.01.16 09:15:00,2024.01.16 21:45:00,GBPUSD,sell,0.20,1.26800,1.26500,1.27300,1.26000,-0.80,-0.50,55.00,10080.30,\"突破交易\"\n"
        "1003,2024.01.17 10:30:00,2024.01.17 15:00:00,XAUUSD,buy,0.05,2035.00,2032.00,2028.00,2045.00,-0.30,-0.10,-15.00,10065.30,\"止损\"\n"
    )
    return io.BytesIO(sample.encode('utf-8-sig')), 200, {
        'Content-Type': 'text/csv; charset=utf-8-sig',
        'Content-Disposition': 'attachment; filename=mt4_sample.csv',
    }


# =====================================================================
# MQL4 脚本自动推送端点
# =====================================================================

def _get_push_user_id():
    """获取推送数据时的用户ID，支持三种认证方式"""
    from models import TradingAccount, User

    # 1. Session 登录
    try:
        from flask_login import current_user
        if current_user and hasattr(current_user, 'id') and current_user.is_authenticated:
            return current_user.id
    except Exception:
        pass

    # 2. API Token 认证（客户端推送用）
    payload = request.get_json(silent=True)
    token = request.args.get('token') or (payload.get('token') if isinstance(payload, dict) else None)
    if token:
        user = User.query.filter_by(api_token=token, is_active=True).first()
        if user:
            return user.id

    # 3. 通过 account_number 反查
    acct_num = None
    if isinstance(payload, dict):
        acct_num = payload.get('account_number')
    elif isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            acct_num = first.get('account_number')
    if acct_num:
        ta = TradingAccount.query.filter_by(account_number=int(acct_num)).first()
        if ta:
            return ta.user_id

    admin = User.query.filter_by(role='admin').first()
    return admin.id if admin else 1


@import_bp.route('/api/mql4_push', methods=['POST'])
def mql4_push():
    """MQL4 脚本推送交易历史 (JSON 数组)"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({'status': 'error', 'message': '无效的 JSON 数据'}), 400

    account = None

    if isinstance(data, dict):
        account = data.get('account', data.get('account_number'))
        # 兼容包裹对象
        if 'orders' in data:
            data = data['orders']
        elif not isinstance(data, dict):
            return jsonify({'status': 'error', 'message': '需要 JSON 数组或 {orders: [...]}'}), 400
        # 如果是包裹对象的 dict 无 orders 字段，可能是单个order，转为列表
        else:
            data = [data]

    if not isinstance(data, list):
        return jsonify({'status': 'error', 'message': '需要 JSON 数组'}), 400

    batch_id = f'mql4-{uuid.uuid4().hex[:8]}'
    imported = 0
    skipped = 0

    for item in data:
        try:
            ticket = int(item.get('ticket', 0))
            if not ticket:
                skipped += 1
                continue

            # 去重
            if Order.query.filter_by(ticket=ticket).first():
                skipped += 1
                continue

            symbol = item.get('symbol', '').upper()
            if not symbol:
                skipped += 1
                continue

            order_type = item.get('type', item.get('Type', '')).lower()
            if order_type in ('buy', 'sell'):
                pass
            elif 'buy' in order_type:
                order_type = 'buy'
            elif 'sell' in order_type:
                order_type = 'sell'
            else:
                skipped += 1
                continue

            volume = float(item.get('volume', 0))
            if volume <= 0:
                skipped += 1
                continue

            open_price = float(item.get('open_price', 0))
            close_price = item.get('close_price')
            if close_price is not None:
                close_price = float(close_price)

            def parse_dt(val):
                if not val:
                    return None
                if isinstance(val, (int, float)):
                    # MQL4 datetime = seconds since 1970
                    return datetime.fromtimestamp(int(val))
                # 字符串
                return parse_mt4_datetime(str(val))

            open_time = parse_dt(item.get('open_time'))
            close_time = parse_dt(item.get('close_time'))

            profit = float(item.get('profit', 0))
            balance = item.get('balance')
            if balance is not None:
                balance = float(balance)

            sl = item.get('sl')
            if sl is not None:
                sl = float(sl)
            tp = item.get('tp')
            if tp is not None:
                tp = float(tp)

            order = Order(
                ticket=ticket,
                symbol=symbol,
                order_type=order_type,
                volume=volume,
                open_time=open_time or datetime.utcnow(),
                close_time=close_time,
                open_price=open_price,
                close_price=close_price,
                sl=sl,
                tp=tp,
                commission=float(item.get('commission', 0)),
                swap=float(item.get('swap', 0)),
                profit=profit,
                balance=balance,
                comment=str(item.get('comment', '')),
                magic=int(item.get('magic', 0)) if item.get('magic') else None,
                import_batch=batch_id,
                account_number=account or (int(item.get('account_number')) if item.get('account_number') else None),
                user_id=_get_push_user_id(),
            )
            db.session.add(order)
            imported += 1

        except (ValueError, TypeError, KeyError) as e:
            skipped += 1
            continue

    db.session.commit()
    return jsonify({
        'status': 'ok',
        'imported': imported,
        'skipped': skipped,
        'batch': batch_id,
    })


@import_bp.route('/api/mql4_push_account', methods=['POST'])
def mql4_push_account():
    """MQL4 脚本推送账户信息"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({'status': 'error', 'message': '无效的 JSON 数据'}), 400

    info = AccountInfo(
        number=int(data['number']) if data.get('number') else None,
        name=str(data.get('name', '')),
        company=str(data.get('company', '')),
        server=str(data.get('server', '')),
        currency=str(data.get('currency', '')),
        leverage=int(data['leverage']) if data.get('leverage') else None,
        balance=float(data['balance']) if data.get('balance') else None,
        equity=float(data['equity']) if data.get('equity') else None,
        free_margin=float(data.get('free_margin', 0)),
        margin=float(data.get('margin', 0)),
        profit=float(data.get('profit', 0)),
        is_demo=data.get('is_demo', True),
        broker=str(data.get('broker', '')),
        terminal=str(data.get('terminal', '')),
        terminal_type=str(data.get('terminal_type', '')),
    )
    db.session.add(info)
    db.session.commit()

    return jsonify({
        'status': 'ok',
        'message': f'账户信息已记录: {info.number} ({info.server})',
    })


@import_bp.route('/api/account_latest')
@login_required
def api_account_latest():
    """获取最新账户信息"""
    from models import TradingAccount

    terminal_type = request.args.get('terminal_type')
    if terminal_type in ('mt4', 'mt5'):
        info = (
            AccountInfo.query
            .filter_by(terminal_type=terminal_type)
            .order_by(AccountInfo.recorded_at.desc())
            .first()
        )
        if info:
            return jsonify(info.to_dict())
        return jsonify(None)

    account_numbers = {
        row[0]
        for row in db.session.query(TradingAccount.account_number)
        .filter_by(user_id=current_user.id)
        .all()
        if row[0] is not None
    }
    account_numbers.update(
        row[0]
        for row in db.session.query(Order.account_number)
        .filter_by(user_id=current_user.id)
        .filter(Order.account_number.isnot(None))
        .all()
        if row[0] is not None
    )

    if not account_numbers:
        return jsonify(None)

    info = (
        AccountInfo.query
        .filter(AccountInfo.number.in_(account_numbers))
        .order_by(AccountInfo.recorded_at.desc())
        .first()
    )
    if info:
        return jsonify(info.to_dict())
    return jsonify(None)


@import_bp.route('/api/scan_csv')
def api_scan_csv():
    """扫描 MT4 公共目录下的 CSV 文件并导入"""
    if not allows_server_terminal_access():
        return client_connector_required_response('MT4')

    import glob as glob_mod

    # MT4 公共数据目录路径
    mt4_common = os.path.expandvars(r'%APPDATA%\MetaQuotes\Terminal')
    found_files = []
    imported_total = 0

    if not os.path.exists(mt4_common):
        return jsonify({
            'status': 'error',
            'message': f'MT4 目录不存在: {mt4_common}。请手动导入 CSV。',
        })

    # 递归查找所有 trade_export*.csv
    pattern = os.path.join(mt4_common, '**', 'trade_export*.csv')
    for fpath in glob_mod.iglob(pattern, recursive=True):
        if not os.path.isfile(fpath):
            continue
        found_files.append(fpath)

        try:
            with open(fpath, encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                imported = parse_csv_rows(reader)
                imported_total += imported
        except Exception as e:
            pass

    return jsonify({
        'status': 'ok',
        'files_found': len(found_files),
        'imported': imported_total,
        'files': found_files,
    })


def parse_csv_rows(reader):
    """解析 CSV 行并入库（复用列映射逻辑）"""
    if reader.fieldnames is None:
        return 0

    # 映射列名
    header_map = {}
    for col in reader.fieldnames:
        col_lower = col.strip().lower()
        if col_lower in MT4_COLUMN_MAPPINGS:
            header_map[col] = MT4_COLUMN_MAPPINGS[col_lower]

    if 'ticket' not in header_map.values():
        return 0

    batch_id = f'auto-{uuid.uuid4().hex[:8]}'
    user_id = _get_push_user_id()
    imported = 0

    for row in reader:
        try:
            mapped = {}
            for orig_col, mapped_col in header_map.items():
                mapped[mapped_col] = row.get(orig_col, '').strip()

            ticket = int(float(mapped.get('ticket', 0)))
            if not ticket:
                continue
            if Order.query.filter_by(ticket=ticket).first():
                continue

            symbol = mapped.get('symbol', '').upper()
            if not symbol:
                continue

            order = Order(
                ticket=ticket,
                symbol=symbol,
                order_type=parse_mt4_type(mapped.get('order_type', '')),
                volume=float(mapped.get('volume', 0)),
                open_time=parse_mt4_datetime(mapped.get('open_time', '')) or datetime.utcnow(),
                close_time=parse_mt4_datetime(mapped.get('close_time', '')),
                open_price=float(mapped.get('open_price', 0)),
                close_price=float(mapped['close_price']) if mapped.get('close_price') else None,
                sl=float(mapped['sl']) if mapped.get('sl') else None,
                tp=float(mapped['tp']) if mapped.get('tp') else None,
                commission=float(mapped.get('commission', 0)),
                swap=float(mapped.get('swap', 0)),
                profit=float(mapped.get('profit', 0)),
                balance=float(mapped['balance']) if mapped.get('balance') else None,
                comment=mapped.get('comment', ''),
                magic=int(float(mapped['magic'])) if mapped.get('magic') else None,
                import_batch=batch_id,
                user_id=user_id,
            )
            db.session.add(order)
            imported += 1
        except (ValueError, KeyError):
            continue

    db.session.commit()
    return imported
