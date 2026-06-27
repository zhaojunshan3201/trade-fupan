"""平台账户管理路由"""
import io
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file, send_from_directory
from flask_login import login_required, current_user
from models import db, PlatformConfig, TradingAccount, Order, AccountInfo
from routes.terminal_access import allows_server_terminal_access, client_connector_required_response
from werkzeug.security import generate_password_hash, check_password_hash

accounts_bp = Blueprint('accounts', __name__, url_prefix='/accounts')
CLIENT_DIR = Path(__file__).resolve().parent.parent / 'client'
CLIENT_DOWNLOAD_FILES = {'start.bat', 'mt5_push.py', 'mt4_push.py'}


def _direct_start_bat(script_name, label, dependency_check, dependency_install):
    return (
        '@echo off\r\n'
        'chcp 65001 >nul\r\n'
        f'title 交易复盘 {label} 客户端\r\n'
        'cd /d %~dp0\r\n'
        'set "LOG=%~dp0connector.log"\r\n'
        f'echo [%date% %time%] {script_name} launched > "%LOG%"\r\n'
        f'if not exist "%~dp0{script_name}" (\r\n'
        f'    echo 未找到 {script_name}，请先解压 zip 后再运行。\r\n'
        '    pause\r\n'
        '    exit /b 1\r\n'
        ')\r\n'
        'set "PYTHON_CMD=python"\r\n'
        'python --version >nul 2>&1\r\n'
        'if %errorlevel% neq 0 (\r\n'
        '    py -3 --version >nul 2>&1\r\n'
        '    if %errorlevel% equ 0 set "PYTHON_CMD=py -3"\r\n'
        ')\r\n'
        '%PYTHON_CMD% --version >nul 2>&1\r\n'
        'if %errorlevel% neq 0 (\r\n'
        '    echo 未检测到 Python，请先安装 Python 3.7+ 并勾选 Add Python to PATH。\r\n'
        '    pause\r\n'
        '    exit /b 1\r\n'
        ')\r\n'
        f'%PYTHON_CMD% -c "{dependency_check}" >nul 2>&1\r\n'
        'if %errorlevel% neq 0 (\r\n'
        '    echo 正在安装依赖...\r\n'
        f'    %PYTHON_CMD% -m pip install --user {dependency_install}\r\n'
        '    if %errorlevel% neq 0 (\r\n'
        '        echo 依赖安装失败，请检查网络。\r\n'
        '        pause\r\n'
        '        exit /b 1\r\n'
        '    )\r\n'
        ')\r\n'
        f'%PYTHON_CMD% {script_name}\r\n'
        'echo.\r\n'
        'echo 如果上方有错误，请把 connector.log 发给管理员排查。\r\n'
        'pause\r\n'
    )


# ============================================================
# 页面
# ============================================================

@accounts_bp.route('/')
@login_required
def index():
    """账户管理主页"""
    uid = current_user.id
    platforms = PlatformConfig.query.filter_by(user_id=uid).all()
    trading_accounts = TradingAccount.query.filter_by(user_id=uid).order_by(TradingAccount.created_at.desc()).all()
    from routes.scheduler import get_sync_state
    return render_template('accounts.html',
        platforms=platforms,
        trading_accounts=trading_accounts,
        sync_state=get_sync_state(),
    )


@accounts_bp.route('/api/sync_status')
@login_required
def sync_status():
    from routes.scheduler import get_sync_state
    return jsonify(get_sync_state())


@accounts_bp.route('/api/token', methods=['GET', 'POST'])
@login_required
def manage_token():
    """生成/查看 API Token"""
    import uuid
    if request.method == 'POST':
        current_user.api_token = uuid.uuid4().hex[:32]
        db.session.commit()
        return jsonify({'status': 'ok', 'token': current_user.api_token})
    return jsonify({'token': current_user.api_token})


def _ensure_api_token():
    if not current_user.api_token:
        current_user.api_token = uuid.uuid4().hex[:32]
        db.session.commit()
    return current_user.api_token


def _server_url():
    forwarded_host = request.headers.get('X-Forwarded-Host')
    if forwarded_host:
        proto = request.headers.get('X-Forwarded-Proto', request.scheme)
        return f'{proto}://{forwarded_host}'.rstrip('/')
    return request.url_root.rstrip('/')


def _client_config():
    return (
        '[server]\n'
        f'url = {_server_url()}\n'
        f'token = {_ensure_api_token()}\n'
        'sync_interval_minutes = 30\n'
        'sync_days_back = 7\n'
        'watch_dir = \n'
        'mt5_path = \n'
    )


@accounts_bp.route('/client/<path:filename>')
@login_required
def download_client_file(filename):
    """Download a single local connector script."""
    if filename == 'package.zip':
        return download_client_package()
    if filename not in CLIENT_DOWNLOAD_FILES:
        return jsonify({'status': 'error', 'message': '文件不存在'}), 404
    return send_from_directory(CLIENT_DIR, filename, as_attachment=True)


@accounts_bp.route('/client/package.zip')
@login_required
def download_client_package():
    """Download a ready-to-run client connector package."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename in CLIENT_DOWNLOAD_FILES:
            zf.write(CLIENT_DIR / filename, arcname=filename)
        zf.writestr(
            'start_mt5.bat',
            _direct_start_bat('mt5_push.py', 'MT5', 'import MetaTrader5, requests', 'MetaTrader5 requests'),
        )
        zf.writestr(
            'start_mt4.bat',
            _direct_start_bat('mt4_push.py', 'MT4', 'import requests', 'requests'),
        )
        zf.writestr('config.ini', _client_config())
        zf.writestr(
            'README.txt',
            '一键连接包使用方法:\r\n'
            '1. 解压本压缩包到当前电脑\r\n'
            '2. 确认本机 MT4/MT5 已打开并登录账户\r\n'
            '3. MT5 用户可双击 start_mt5.bat\r\n'
            '4. MT4 用户可双击 start_mt4.bat\r\n'
            '5. 也可以双击 start.bat 打开菜单\r\n'
            '6. 如一台电脑有多个 MT5，请编辑 config.ini 的 mt5_path\r\n'
            '7. 如窗口仍然退出，请查看 connector.log\r\n'
        )
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='trade-journal-client.zip',
    )


@accounts_bp.route('/api/sync_all', methods=['POST'])
@login_required
def trigger_sync_all():
    """手动触发全部账户同步"""
    from routes.scheduler import auto_sync_all, _sync_state
    if _sync_state['running']:
        return jsonify({'status': 'error', 'message': '同步正在进行中'})
    import threading
    from flask import current_app
    t = threading.Thread(target=lambda: auto_sync_all(current_app._get_current_object()), daemon=True)
    t.start()
    return jsonify({'status': 'ok', 'message': '同步已触发'})


# ============================================================
# 平台管理 API
# ============================================================

@accounts_bp.route('/api/platforms', methods=['GET'])
@login_required
def list_platforms():
    return jsonify([p.to_dict() for p in PlatformConfig.query.filter_by(user_id=current_user.id).all()])


@accounts_bp.route('/api/platforms', methods=['POST'])
@login_required
def create_platform():
    data = request.json
    p = PlatformConfig(
        user_id=current_user.id,
        name=data['name'],
        platform_type=data['platform_type'],
        server=data['server'],
        broker=data.get('broker', ''),
        api_type=data.get('api_type', 'terminal'),
        mt5_path=data.get('mt5_path', ''),
    )
    db.session.add(p)
    db.session.commit()
    return jsonify({'status': 'ok', 'platform': p.to_dict()})


@accounts_bp.route('/api/platforms/<int:pid>', methods=['PUT'])
@login_required
def update_platform(pid):
    p = PlatformConfig.query.get_or_404(pid)
    if p.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': '无权操作'}), 403
    data = request.json
    for f in ['name', 'server', 'broker', 'api_type', 'mt5_path']:
        if f in data:
            setattr(p, f, data[f])
    if 'is_active' in data:
        p.is_active = data['is_active']
    db.session.commit()
    return jsonify({'status': 'ok', 'platform': p.to_dict()})


@accounts_bp.route('/api/platforms/<int:pid>', methods=['DELETE'])
@login_required
def delete_platform(pid):
    p = PlatformConfig.query.get_or_404(pid)
    if p.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': '无权操作'}), 403
    # 删除关联账户
    TradingAccount.query.filter_by(platform_id=pid).delete()
    db.session.delete(p)
    db.session.commit()
    return jsonify({'status': 'ok'})


@accounts_bp.route('/api/platforms/<int:pid>/test', methods=['POST'])
@login_required
def test_platform(pid):
    """测试平台连接"""
    p = PlatformConfig.query.get_or_404(pid)
    if p.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': '无权操作'}), 403
    result = {'status': 'testing', 'message': '', 'account': None}

    if p.platform_type == 'mt5':
        if not allows_server_terminal_access():
            return client_connector_required_response('MT5')

        try:
            import MetaTrader5 as mt5
            init = mt5.initialize(path=p.mt5_path) if p.mt5_path else mt5.initialize()
            if not init:
                result['status'] = 'error'
                result['message'] = f'MT5连接失败: {mt5.last_error()}'
            else:
                info = mt5.account_info()
                if info:
                    result['status'] = 'ok'
                    result['message'] = f'MT5连接成功'
                    result['account'] = {
                        'number': info.login, 'name': info.name,
                        'server': info.server, 'balance': info.balance,
                        'equity': info.equity, 'currency': info.currency,
                        'leverage': info.leverage, 'is_demo': info.trade_mode == 0,
                    }
                else:
                    result['status'] = 'error'
                    result['message'] = 'MT5已连接但未检测到登录账户'
                mt5.shutdown()
        except ImportError:
            result['status'] = 'error'
            result['message'] = 'MetaTrader5 包未安装。pip install MetaTrader5'
        except Exception as e:
            result['status'] = 'error'
            result['message'] = str(e)

    elif p.platform_type == 'mt4':
        result['status'] = 'info'
        result['message'] = 'MT4平台已配置。请通过MQL4脚本(TradeExport.mq4)推送数据，或上传CSV导入。'
        result['note'] = 'MT4无官方Python API，需要通过MT4终端内的脚本或CSV导出获取数据。'

    return jsonify(result)


# ============================================================
# 账户管理 API
# ============================================================

@accounts_bp.route('/api/accounts', methods=['GET'])
@login_required
def list_accounts():
    accounts = TradingAccount.query.filter_by(user_id=current_user.id)\
        .order_by(TradingAccount.created_at.desc()).all()
    return jsonify([a.to_dict() for a in accounts])


@accounts_bp.route('/api/accounts', methods=['POST'])
@login_required
def create_account():
    data = request.json
    platform = PlatformConfig.query.get_or_404(int(data['platform_id']))
    if platform.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': '无权操作'}), 403

    acct = TradingAccount(
        user_id=current_user.id,
        platform_id=platform.id,
        account_number=int(data['account_number']),
        account_name=data.get('account_name', ''),
        is_demo=data.get('is_demo', True),
        currency=data.get('currency', ''),
        leverage=int(data.get('leverage', 0)) if data.get('leverage') else None,
    )
    if data.get('password'):
        acct.password_encrypted = generate_password_hash(data['password'])
    db.session.add(acct)
    db.session.commit()
    return jsonify({'status': 'ok', 'account': acct.to_dict()})


@accounts_bp.route('/api/accounts/<int:aid>', methods=['PUT'])
@login_required
def update_account(aid):
    a = TradingAccount.query.get_or_404(aid)
    if a.user_id != current_user.id:
        return jsonify({'status': 'error'}), 403
    data = request.json
    for f in ['account_name', 'is_demo', 'currency', 'is_active']:
        if f in data:
            setattr(a, f, data[f])
    if data.get('password'):
        a.password_encrypted = generate_password_hash(data['password'])
    if data.get('leverage'):
        a.leverage = int(data['leverage'])
    db.session.commit()
    return jsonify({'status': 'ok', 'account': a.to_dict()})


@accounts_bp.route('/api/accounts/<int:aid>', methods=['DELETE'])
@login_required
def delete_account(aid):
    a = TradingAccount.query.get_or_404(aid)
    if a.user_id != current_user.id:
        return jsonify({'status': 'error'}), 403
    db.session.delete(a)
    db.session.commit()
    return jsonify({'status': 'ok'})


@accounts_bp.route('/api/accounts/<int:aid>/sync', methods=['POST'])
@login_required
def sync_account(aid):
    """同步账户数据——从MT4/MT5拉取最新交易"""
    a = TradingAccount.query.get_or_404(aid)
    if a.user_id != current_user.id:
        return jsonify({'status': 'error'}), 403

    platform = a.platform
    logs = []
    imported = 0

    a.sync_status = 'syncing'
    a.last_sync_at = datetime.utcnow()
    db.session.commit()

    if platform.platform_type == 'mt5':
        if not allows_server_terminal_access():
            a.sync_status = 'error'
            db.session.commit()
            return client_connector_required_response('MT5')

        try:
            import MetaTrader5 as mt5
            path = platform.mt5_path or None
            init = mt5.initialize(path=path) if path else mt5.initialize()
            if not init:
                a.sync_status = 'error'
                db.session.commit()
                return jsonify({'status': 'error', 'message': f'MT5连接失败: {mt5.last_error()}'})

            info = mt5.account_info()
            if info and info.login != a.account_number:
                logs.append(f'⚠️ 注意: MT5当前登录账户({info.login})与配置账户({a.account_number})不一致')

            # 更新账户信息
            if info:
                a.balance = info.balance
                a.equity = info.equity
                a.currency = info.currency
                a.leverage = info.leverage

            # 拉取历史成交
            from datetime import timedelta
            from_date = datetime.utcnow() - timedelta(days=30)
            deals = mt5.history_deals_get(from_date, datetime.utcnow())
            if deals and len(deals) > 0:
                orders = []
                for deal in deals:
                    if deal.entry != 1: continue
                    order = {
                        'ticket': deal.ticket, 'symbol': deal.symbol,
                        'type': 'buy' if deal.type in (0, 2) else 'sell',
                        'volume': deal.volume,
                        'open_price': deal.price, 'close_price': deal.price,
                        'close_time': datetime.fromtimestamp(deal.time).strftime('%Y.%m.%d %H:%M:%S'),
                        'profit': deal.profit, 'commission': deal.commission,
                        'swap': deal.swap, 'comment': deal.comment or '', 'magic': deal.magic,
                    }
                    oh = mt5.history_orders_get(ticket=deal.order)
                    if oh and len(oh) > 0:
                        order['open_price'] = oh[0].price_open
                        order['open_time'] = datetime.fromtimestamp(oh[0].time_setup).strftime('%Y.%m.%d %H:%M:%S')
                        order['sl'] = oh[0].sl
                        order['tp'] = oh[0].tp
                    orders.append(order)

                # 推送到导入端点
                import requests as req
                payload = {'account_number': a.account_number, 'orders': orders}
                resp = req.post('http://127.0.0.1:5000/import/api/mql4_push',
                              json=payload, timeout=60)
                if resp.status_code == 200:
                    imported = resp.json().get('imported', 0)
                logs.append(f'✅ MT5同步完成: {len(orders)}条成交, 导入{imported}条')
            else:
                logs.append('📭 最近30天无平仓记录')

            mt5.shutdown()
            a.sync_status = 'success'

        except ImportError:
            a.sync_status = 'error'
            logs.append('❌ MetaTrader5未安装')
        except Exception as e:
            a.sync_status = 'error'
            logs.append(f'❌ {e}')

    elif platform.platform_type == 'mt4':
        # MT4: 提示用户通过MQL4脚本或CSV导入
        a.sync_status = 'success'
        logs.append('💡 MT4账户: 请使用MQL4脚本(TradeExport.mq4)推送数据，或上传CSV文件导入')

    db.session.commit()
    return jsonify({'status': 'ok', 'imported': imported, 'logs': logs, 'sync_status': a.sync_status})


@accounts_bp.route('/api/accounts/<int:aid>/test', methods=['POST'])
@login_required
def test_account(aid):
    """测试单个账户连接"""
    a = TradingAccount.query.get_or_404(aid)
    if a.user_id != current_user.id:
        return jsonify({'status': 'error'}), 403

    platform = a.platform
    if platform.platform_type == 'mt5':
        if not allows_server_terminal_access():
            return client_connector_required_response('MT5')

        try:
            import MetaTrader5 as mt5
            init = mt5.initialize(path=platform.mt5_path) if platform.mt5_path else mt5.initialize()
            if init:
                info = mt5.account_info()
                mt5.shutdown()
                if info:
                    return jsonify({'status': 'ok', 'message': f'连接成功，当前账户: {info.login}',
                                    'balance': info.balance, 'equity': info.equity})
                return jsonify({'status': 'error', 'message': 'MT5未登录'})
            return jsonify({'status': 'error', 'message': f'连接失败: {mt5.last_error()}'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
    else:
        return jsonify({'status': 'info', 'message': 'MT4账户请通过MQL4脚本或CSV导入'})
