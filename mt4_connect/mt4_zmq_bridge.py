#!/usr/bin/env python
"""
MT4 ZeroMQ 实时数据桥接脚本 (方案 B — 低延迟)

原理:
  MT4 端运行 ZeroMQ 库的 EA，持续推送交易数据。
  本 Python 脚本订阅 ZeroMQ 消息，实时推送到 Flask 复盘系统。

MT4 端需要:
  1. 安装 MT4 ZeroMQ 库 (https://github.com/dingmaotu/mql-zmq)
  2. 编译并运行配套的 EA (见 zeroMQ_EA.mq4 示例)

使用方式:
  python mt4_zmq_bridge.py                          # 默认连接 localhost:5555
  python mt4_zmq_bridge.py --port 5556              # 指定端口
  python mt4_zmq_bridge.py --url http://localhost:5000  # Flask 地址

依赖:
  pip install pyzmq requests
"""

import sys
import json
import time
import argparse
import logging
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('mt4_zmq')

FLASK_URL = 'http://127.0.0.1:5000'
PUSH_API = '/import/api/mql4_push'
ACCOUNT_API = '/import/api/mql4_push_account'

# ZeroMQ 协议格式
MSG_TYPE_ORDER = 'ORDER'
MSG_TYPE_ACCOUNT = 'ACCOUNT'
MSG_TYPE_TICK = 'TICK'
MSG_TYPE_DEAL = 'DEAL'


def push_orders(orders):
    """批量推送订单到 Flask"""
    url = FLASK_URL + PUSH_API
    try:
        resp = requests.post(url, json=orders, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"📤 推送 {data.get('imported', 0)} 条订单 (跳过 {data.get('skipped', 0)})")
            return True
        else:
            logger.warning(f"推送失败: {resp.status_code}")
            return False
    except Exception as e:
        logger.error(f"推送异常: {e}")
        return False


def push_account(account_data):
    """推送账户信息"""
    url = FLASK_URL + ACCOUNT_API
    try:
        resp = requests.post(url, json=account_data, timeout=15)
        if resp.status_code == 200:
            logger.info(f"🏦 账户信息已更新: {account_data.get('number', 'N/A')}")
            return True
    except Exception as e:
        logger.error(f"账户推送失败: {e}")
    return False


def parse_zmq_message(topic, message):
    """解析 ZeroMQ 消息"""
    text = message.decode('utf-8', errors='replace')
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试按分隔符解析
        parts = text.split('|')
        if len(parts) >= 3:
            return {
                'type': parts[0],
                'data': parts[1],
                'timestamp': parts[2],
            }
    return {'type': 'unknown', 'raw': text}


def process_order_data(order_data):
    """处理单条订单数据并推送"""
    # 确保字段名兼容 Flask 端点
    if not isinstance(order_data, dict):
        return

    normalized = {
        'ticket': order_data.get('ticket', order_data.get('Ticket', 0)),
        'symbol': order_data.get('symbol', order_data.get('Symbol', '')),
        'type': order_data.get('type', order_data.get('Type', '')).lower(),
        'volume': order_data.get('volume', order_data.get('Volume', order_data.get('lots', 0))),
        'open_price': order_data.get('open_price', order_data.get('OpenPrice', order_data.get('openPrice', 0))),
        'close_price': order_data.get('close_price', order_data.get('ClosePrice', order_data.get('closePrice', 0))),
        'open_time': order_data.get('open_time', order_data.get('OpenTime', '')),
        'close_time': order_data.get('close_time', order_data.get('CloseTime', '')),
        'profit': order_data.get('profit', order_data.get('Profit', 0)),
        'sl': order_data.get('sl', order_data.get('Sl', order_data.get('StopLoss', 0))),
        'tp': order_data.get('tp', order_data.get('Tp', order_data.get('TakeProfit', 0))),
        'commission': order_data.get('commission', order_data.get('Commission', 0)),
        'swap': order_data.get('swap', order_data.get('Swap', 0)),
        'comment': order_data.get('comment', order_data.get('Comment', '')),
        'magic': order_data.get('magic', order_data.get('Magic', order_data.get('MagicNumber', 0))),
    }

    # 推送单条
    push_orders([normalized])


def process_account_data(acct_data):
    """处理账户信息"""
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
        'terminal': 'MetaTrader 4',
        'terminal_type': 'mt4',
    }
    push_account(normalized)


def start_bridge(port=5555, host='127.0.0.1'):
    """启动 ZeroMQ 桥接"""
    try:
        import zmq
    except ImportError:
        logger.error("请先安装 pyzmq: pip install pyzmq")
        sys.exit(1)

    context = zmq.Context()
    socket = context.socket(zmq.SUB)

    address = f'tcp://{host}:{port}'
    socket.connect(address)
    logger.info(f"🔌 正在连接 ZeroMQ: {address}")

    # 订阅所有主题 (空字符串 = 全部)
    socket.subscribe(b'')
    logger.info("📡 已订阅所有数据通道")
    logger.info(f"📤 推送目标: {FLASK_URL}")
    logger.info("⏳ 等待 MT4 数据...")

    # 连接状态
    last_heartbeat = time.time()
    order_buffer = []

    try:
        while True:
            # 检查 MT4 是否还在发送数据 (心跳)
            if time.time() - last_heartbeat > 60:
                logger.info("⏸️  等待 MT4 数据中... (60秒无消息)")
                last_heartbeat = time.time()

            # 接收消息 (超时5秒以便能响应 Ctrl+C)
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
            elif msg_type in ('ACCOUNT', 'account', 'ACCOUNT_INFO'):
                process_account_data(data)
            elif msg_type in ('TICK', 'tick'):
                # 行情数据 — 忽略
                pass
            elif msg_type in ('HEARTBEAT', 'heartbeat'):
                logger.debug(f"💓 心跳: {data.get('timestamp', '')}")
            else:
                logger.debug(f"未识别消息类型: {msg_type}")

    except KeyboardInterrupt:
        logger.info("⏹  正在关闭桥接...")
    finally:
        socket.close()
        context.term()
        logger.info("桥接已关闭")


def main():
    global FLASK_URL

    parser = argparse.ArgumentParser(description='MT4 ZeroMQ 实时数据桥接')
    parser.add_argument('--port', type=int, default=5555, help='ZeroMQ 端口 (默认 5555)')
    parser.add_argument('--host', default='127.0.0.1', help='ZeroMQ 地址 (默认 127.0.0.1)')
    parser.add_argument('--url', default=FLASK_URL, help=f'Flask 地址 (默认 {FLASK_URL})')

    args = parser.parse_args()

    if args.url:
        FLASK_URL = args.url.rstrip('/')

    start_bridge(port=args.port, host=args.host)


if __name__ == '__main__':
    main()
