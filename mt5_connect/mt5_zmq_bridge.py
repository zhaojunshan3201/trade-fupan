#!/usr/bin/env python
"""MT5 ZeroMQ real-time bridge.

MT5 runs ZeroMQBridgeEA.mq5 and publishes account / closed deal messages.
This script subscribes to the local ZeroMQ socket and pushes data to Flask.
"""
import argparse
import json
import logging
import sys
import time

import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('mt5_zmq')

FLASK_URL = 'http://127.0.0.1:5000'
PUSH_API = '/import/api/mql4_push'
ACCOUNT_API = '/import/api/mql4_push_account'


def push_orders(orders):
    try:
        resp = requests.post(FLASK_URL + PUSH_API, json=orders, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            logger.info("📤 推送 %s 条订单 (跳过 %s)", data.get('imported', 0), data.get('skipped', 0))
            return True
        logger.warning("订单推送失败: HTTP %s", resp.status_code)
    except Exception as exc:
        logger.error("订单推送异常: %s", exc)
    return False


def push_account(account_data):
    try:
        resp = requests.post(FLASK_URL + ACCOUNT_API, json=account_data, timeout=15)
        if resp.status_code == 200:
            logger.info("🏦 MT5 账户信息已更新: %s", account_data.get('number', 'N/A'))
            return True
        logger.warning("账户推送失败: HTTP %s", resp.status_code)
    except Exception as exc:
        logger.error("账户推送失败: %s", exc)
    return False


def parse_zmq_message(topic, message):
    text = message.decode('utf-8', errors='replace')
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {'type': topic, 'raw': text}


def process_order_data(order_data):
    if not isinstance(order_data, dict):
        return

    trade_type = order_data.get('Type', order_data.get('order_type', order_data.get('side', '')))
    if not trade_type and str(order_data.get('type', '')).lower() not in ('deal', 'order'):
        trade_type = order_data.get('type', '')

    normalized = {
        'ticket': order_data.get('ticket', order_data.get('Ticket', 0)),
        'symbol': order_data.get('symbol', order_data.get('Symbol', '')),
        'type': str(trade_type).lower(),
        'volume': order_data.get('volume', order_data.get('Volume', 0)),
        'open_price': order_data.get('open_price', order_data.get('OpenPrice', order_data.get('price', 0))),
        'close_price': order_data.get('close_price', order_data.get('ClosePrice', order_data.get('price', 0))),
        'open_time': order_data.get('open_time', order_data.get('OpenTime', '')),
        'close_time': order_data.get('close_time', order_data.get('CloseTime', order_data.get('time', ''))),
        'profit': order_data.get('profit', order_data.get('Profit', 0)),
        'sl': order_data.get('sl', order_data.get('StopLoss', 0)),
        'tp': order_data.get('tp', order_data.get('TakeProfit', 0)),
        'commission': order_data.get('commission', order_data.get('Commission', 0)),
        'swap': order_data.get('swap', order_data.get('Swap', 0)),
        'comment': order_data.get('comment', order_data.get('Comment', '')),
        'magic': order_data.get('magic', order_data.get('Magic', 0)),
        'account_number': order_data.get('account_number', order_data.get('AccountNumber')),
    }
    push_orders([normalized])


def process_account_data(acct_data):
    normalized = {
        'number': acct_data.get('number', acct_data.get('login', acct_data.get('Login', 0))),
        'name': acct_data.get('name', acct_data.get('Name', '')),
        'company': acct_data.get('company', acct_data.get('Company', '')),
        'server': acct_data.get('server', acct_data.get('Server', '')),
        'currency': acct_data.get('currency', acct_data.get('Currency', 'USD')),
        'leverage': acct_data.get('leverage', acct_data.get('Leverage', 100)),
        'balance': acct_data.get('balance', acct_data.get('Balance', 0)),
        'equity': acct_data.get('equity', acct_data.get('Equity', 0)),
        'free_margin': acct_data.get('free_margin', acct_data.get('FreeMargin', 0)),
        'margin': acct_data.get('margin', acct_data.get('Margin', 0)),
        'profit': acct_data.get('profit', acct_data.get('Profit', 0)),
        'is_demo': acct_data.get('is_demo', acct_data.get('isDemo', True)),
        'terminal': 'MetaTrader 5',
        'terminal_type': 'mt5',
    }
    push_account(normalized)


def start_bridge(port=5556, host='127.0.0.1'):
    try:
        import zmq
    except ImportError:
        logger.error("请先安装 pyzmq: pip install pyzmq")
        sys.exit(1)

    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    address = f'tcp://{host}:{port}'
    socket.connect(address)
    socket.subscribe(b'')

    logger.info("🔌 正在连接 MT5 ZeroMQ: %s", address)
    logger.info("📤 推送目标: %s", FLASK_URL)
    logger.info("⏳ 等待 MT5 数据...")
    last_heartbeat = time.time()

    try:
        while True:
            if time.time() - last_heartbeat > 60:
                logger.info("等待 MT5 数据中... (60 秒无消息)")
                last_heartbeat = time.time()

            try:
                topic = socket.recv_string(flags=zmq.NOBLOCK)
                message = socket.recv(flags=zmq.NOBLOCK)
                last_heartbeat = time.time()
            except zmq.Again:
                time.sleep(0.1)
                continue

            data = parse_zmq_message(topic, message)
            msg_type = data.get('type', topic)
            if msg_type in ('ORDER', 'DEAL', 'order', 'deal'):
                process_order_data(data)
            elif msg_type in ('ACCOUNT', 'ACCOUNT_INFO', 'account'):
                process_account_data(data)
            elif msg_type in ('HEARTBEAT', 'heartbeat', 'TICK', 'tick'):
                logger.debug("收到 %s", msg_type)
            else:
                logger.debug("未知消息类型: %s", msg_type)
    except KeyboardInterrupt:
        logger.info("正在关闭 MT5 ZeroMQ 桥...")
    finally:
        socket.close()
        context.term()


def main():
    global FLASK_URL
    parser = argparse.ArgumentParser(description='MT5 ZeroMQ real-time bridge')
    parser.add_argument('--port', type=int, default=5556, help='ZeroMQ port (default 5556)')
    parser.add_argument('--host', default='127.0.0.1', help='ZeroMQ host (default 127.0.0.1)')
    parser.add_argument('--url', default=FLASK_URL, help=f'Flask URL (default {FLASK_URL})')
    args = parser.parse_args()

    FLASK_URL = args.url.rstrip('/')
    start_bridge(port=args.port, host=args.host)


if __name__ == '__main__':
    main()
