"""Background auto-sync scheduler"""
import logging
from datetime import datetime, timedelta
from models import db, TradingAccount, PlatformConfig, Order
from routes.terminal_access import allows_server_terminal_access

logger = logging.getLogger('auto_sync')

_sync_state = {
    'running': False,
    'last_sync_at': None,
    'next_sync_at': None,
    'last_result': None,
    'interval_minutes': 60,
}


def get_sync_state():
    return dict(_sync_state)


def auto_sync_all(app):
    """Auto-sync all active trading accounts"""
    if _sync_state['running']:
        logger.info('Previous sync still running, skip')
        return

    _sync_state['running'] = True
    results = {'mt5_synced': 0, 'mt5_errors': 0, 'total_imported': 0}

    try:
        with app.app_context():
            if not allows_server_terminal_access():
                logger.info('Server terminal sync skipped; client connector is required')
                return

            accounts = TradingAccount.query.filter_by(is_active=True).all()
            logger.info(f'Auto-sync start: {len(accounts)} active accounts')

            for acct in accounts:
                platform = acct.platform
                if not platform or not platform.is_active:
                    continue

                if platform.platform_type == 'mt5':
                    try:
                        import MetaTrader5 as mt5
                        path = platform.mt5_path or None
                        init = mt5.initialize(path=path) if path else mt5.initialize()

                        if not init:
                            results['mt5_errors'] += 1
                            continue

                        info = mt5.account_info()
                        if info:
                            acct.balance = info.balance
                            acct.equity = info.equity
                            acct.currency = info.currency
                            acct.leverage = info.leverage

                        from_date = datetime.utcnow() - timedelta(days=7)
                        deals = mt5.history_deals_get(from_date, datetime.utcnow())

                        if deals and len(deals) > 0:
                            orders = []
                            for deal in deals:
                                if deal.entry != 1:
                                    continue
                                order = {
                                    'ticket': deal.ticket, 'symbol': deal.symbol,
                                    'type': 'buy' if deal.type in (0, 2) else 'sell',
                                    'volume': deal.volume,
                                    'open_price': deal.price, 'close_price': deal.price,
                                    'close_time': datetime.fromtimestamp(deal.time).strftime('%Y.%m.%d %H:%M:%S'),
                                    'profit': deal.profit, 'commission': deal.commission,
                                    'swap': deal.swap, 'comment': deal.comment or '',
                                    'magic': deal.magic, 'account_number': acct.account_number,
                                }
                                oh = mt5.history_orders_get(ticket=deal.order)
                                if oh and len(oh) > 0:
                                    order['open_price'] = oh[0].price_open
                                    order['open_time'] = datetime.fromtimestamp(oh[0].time_setup).strftime('%Y.%m.%d %H:%M:%S')
                                    order['sl'] = oh[0].sl
                                    order['tp'] = oh[0].tp
                                orders.append(order)

                            if orders:
                                import requests as req
                                payload = {'account_number': acct.account_number, 'orders': orders}
                                try:
                                    resp = req.post('http://127.0.0.1:5000/import/api/mql4_push',
                                                  json=payload, timeout=60)
                                    if resp.status_code == 200:
                                        results['total_imported'] += resp.json().get('imported', 0)
                                except Exception:
                                    pass

                        mt5.shutdown()
                        acct.sync_status = 'success'
                        acct.last_sync_at = datetime.utcnow()
                        results['mt5_synced'] += 1

                    except ImportError:
                        results['mt5_errors'] += 1
                    except Exception as e:
                        acct.sync_status = 'error'
                        results['mt5_errors'] += 1

                elif platform.platform_type == 'mt4':
                    try:
                        import requests as req
                        req.get('http://127.0.0.1:5000/import/api/scan_csv', timeout=10)
                    except Exception:
                        pass

                db.session.commit()

    except Exception as e:
        logger.error(f'Auto-sync error: {e}')
    finally:
        _sync_state['running'] = False
        _sync_state['last_sync_at'] = datetime.utcnow().strftime('%H:%M:%S')
        _sync_state['last_result'] = results
        logger.info(f'Sync done: MT5={results["mt5_synced"]}ok/{results["mt5_errors"]}err, imported={results["total_imported"]}')


def init_scheduler(app):
    """Initialize background scheduler"""
    from config import Config
    from apscheduler.schedulers.background import BackgroundScheduler

    if not Config.AUTO_SYNC_ENABLED:
        logger.info('Auto-sync disabled')
        return None

    interval = Config.AUTO_SYNC_INTERVAL_MINUTES
    _sync_state['interval_minutes'] = interval

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: auto_sync_all(app),
        trigger='interval',
        minutes=interval,
        id='auto_sync_accounts',
        name='Auto-sync trading accounts',
        replace_existing=True,
    )

    scheduler.start()
    _sync_state['next_sync_at'] = (datetime.utcnow() + timedelta(minutes=interval)).strftime('%H:%M')

    logger.info(f'Auto-sync started, interval={interval}min')

    if Config.AUTO_SYNC_ON_STARTUP:
        logger.info('Running startup sync...')
        import threading
        t = threading.Thread(target=lambda: auto_sync_all(app), daemon=True)
        t.start()

    return scheduler
