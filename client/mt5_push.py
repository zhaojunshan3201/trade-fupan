# -*- coding: utf-8 -*-
"""
MT5 客户端连接器
运行在你的电脑上，自动读取 MT5 数据并推送到服务器。

用法:
  双击 start.bat
  或: python mt5_push.py

配置: 修改同目录下的 config.ini
  [server]
  url = http://your-server.com:5000
  token = your_api_token_here
  sync_interval_minutes = 30

依赖: pip install MetaTrader5 requests
"""

import os
import sys
import time
import json
import configparser
import logging
from datetime import datetime, timedelta

import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('mt5_client')

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')


def load_config():
    """加载配置"""
    c = configparser.ConfigParser()
    defaults = {
        'url': 'http://127.0.0.1:5000',
        'token': '',
        'sync_interval_minutes': '30',
    }
    if os.path.exists(CONFIG_FILE):
        c.read(CONFIG_FILE, encoding='utf-8')
    if 'server' not in c:
        c['server'] = {}
    for k, v in defaults.items():
        if k not in c['server'] or not c['server'][k]:
            c['server'][k] = v
    return c['server']


def save_config(config):
    """保存配置"""
    c = configparser.ConfigParser()
    c['server'] = config
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        c.write(f)


def test_connection(config):
    """测试与服务器的连接"""
    url = config['url'].rstrip('/')
    token = config['token']
    try:
        # 仅测试连接
        resp = requests.post(f'{url}/import/api/mql4_push?token={token}',
                           json=[], timeout=10)
        if resp.status_code == 200:
            return True, '服务器连接正常'
        return False, f'服务器返回 {resp.status_code}'
    except requests.exceptions.ConnectionError:
        return False, f'无法连接到 {url}'
    except Exception as e:
        return False, str(e)


def push_to_server(config, orders, account_number):
    """推送订单到服务器"""
    url = config['url'].rstrip('/')
    token = config['token']
    accounts = config.get('accounts', account_number)
    payload = {
        'token': token,
        'account_number': accounts,
        'orders': orders,
    }
    try:
        resp = requests.post(f'{url}/import/api/mql4_push', json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            return data.get('imported', 0), data.get('skipped', 0)
        return 0, 0
    except Exception as e:
        logger.error(f'推送失败: {e}')
        return 0, 0


def get_mt5_data(config):
    """从本地 MT5 读取数据"""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        logger.error('MetaTrader5 未安装。请运行: pip install MetaTrader5')
        return None, None

    # 连接
    mt5_path = config.get('mt5_path', '')
    if mt5_path:
        logger.info(f'连接 MT5: {mt5_path}')
        init = mt5.initialize(path=mt5_path)
    else:
        logger.info('连接 MT5 (自动检测)...')
        init = mt5.initialize()

    if not init:
        logger.error(f'MT5 连接失败: {mt5.last_error()}')
        return None, None

    logger.info('MT5 连接成功')

    # 账户信息
    info = mt5.account_info()
    account_number = None
    if info:
        logger.info(f'账户: {info.login} ({info.server}) 余额: ${info.balance:.2f}')
        account_number = info.login

    # 拉取最近 N 天的成交
    days = int(config.get('sync_days_back', '7'))
    from_date = datetime.utcnow() - timedelta(days=days)
    logger.info(f'拉取 {from_date.date()} ~ 今天的历史成交...')

    deals = mt5.history_deals_get(from_date, datetime.utcnow())
    if not deals or len(deals) == 0:
        logger.info('无新成交记录')
        mt5.shutdown()
        return account_number, []

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
            'magic': deal.magic,
        }
        oh = mt5.history_orders_get(ticket=deal.order)
        if oh and len(oh) > 0:
            order['open_price'] = oh[0].price_open
            order['open_time'] = datetime.fromtimestamp(oh[0].time_setup).strftime('%Y.%m.%d %H:%M:%S')
            order['sl'] = oh[0].sl
            order['tp'] = oh[0].tp
        orders.append(order)

    mt5.shutdown()
    logger.info(f'共 {len(orders)} 条平仓记录')
    return account_number, orders


def interactive_setup(config):
    """交互式配置"""
    print('\n' + '=' * 50)
    print('  MT5 客户端连接器 - 首次配置')
    print('=' * 50)
    print()

    url = input(f'服务器地址 [{config["url"]}]: ').strip()
    if url:
        config['url'] = url

    token = input(f'API Token [{config["token"][:8] + "..." if config["token"] else "无"}]: ').strip()
    if token:
        config['token'] = token

    interval = input(f'同步间隔(分钟) [{config["sync_interval_minutes"]}]: ').strip()
    if interval:
        config['sync_interval_minutes'] = interval

    mt5_path = input(f'MT5终端路径 [默认自动检测]: ').strip()
    if mt5_path:
        config['mt5_path'] = mt5_path

    save_config(config)
    print('\n配置已保存！')


def main():
    config = load_config()

    if not config['token'] or '--setup' in sys.argv:
        interactive_setup(config)
        config = load_config()

    print('\n' + '=' * 50)
    print('  MT5 客户端连接器')
    print(f'  服务器: {config["url"]}')
    print(f'  同步间隔: {config["sync_interval_minutes"]} 分钟')
    print('  按 Ctrl+C 停止')
    print('=' * 50 + '\n')

    # 测试连接
    ok, msg = test_connection(config)
    if ok:
        logger.info(f'✅ {msg}')
    else:
        logger.error(f'❌ {msg}')
        if '--test' in sys.argv:
            return
        input('按回车继续尝试...')

    interval = int(config['sync_interval_minutes']) * 60

    while True:
        try:
            logger.info('开始同步...')
            account_number, orders = get_mt5_data(config)

            if account_number and orders:
                imported, skipped = push_to_server(config, orders, account_number)
                logger.info(f'同步完成: 导入 {imported} 条, 跳过 {skipped} 条')
            elif account_number:
                logger.info('无新数据')

            logger.info(f'下次同步: {interval // 60} 分钟后')
            time.sleep(interval)

        except KeyboardInterrupt:
            logger.info('已停止')
            break
        except Exception as e:
            logger.error(f'同步异常: {e}')
            time.sleep(60)


if __name__ == '__main__':
    main()
