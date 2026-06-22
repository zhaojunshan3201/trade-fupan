#!/usr/bin/env python
"""
MT5 官方 Python 直连脚本

原理:
  使用 MetaQuotes 官方提供的 MetaTrader5 包，直接连接 MT5 终端进程，
  读取账户信息和历史成交记录，推送到 Flask 复盘系统。

  与 MT4 不同，MT5 有官方 Python API，无需 MQL 桥接。

使用方式:
  python mt5_connector.py                         # 一键导入全部历史
  python mt5_connector.py --days 30               # 只导入最近30天
  python mt5_connector.py --url http://localhost:5000  # 指定Flask地址
  python mt5_connector.py --info                  # 只获取账户信息
  python mt5_connector.py --watch                 # 持续监控模式

依赖:
  pip install MetaTrader5 requests

注意:
  - 仅 Windows 系统可用 (MT5 只支持 Windows)
  - MT5 终端必须在运行中，且已登录账户
  - 首次运行可能需要关闭 MT5 的"仅允许智能交易系统"限制
"""

import sys
import json
import time
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('mt5_connector')

FLASK_URL = 'http://127.0.0.1:5000'
PUSH_ORDERS_API = '/import/api/mql4_push'      # 复用同一订单导入端点
PUSH_ACCOUNT_API = '/import/api/mql4_push_account'


def ensure_mt5():
    """导入并验证 MetaTrader5 包"""
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError:
        logger.error("请安装 MetaTrader5: pip install MetaTrader5")
        logger.error("注意: MetaTrader5 仅支持 Windows 系统")
        sys.exit(1)


def connect(mt5, path=None):
    """连接到 MT5 终端"""
    if path:
        logger.info(f"正在连接 MT5: {path}")
        initialized = mt5.initialize(path=path)
    else:
        logger.info("正在连接 MT5 (自动检测)...")
        initialized = mt5.initialize()

    if not initialized:
        err = mt5.last_error()
        logger.error(f"❌ MT5 连接失败: {err}")
        logger.error("请确保:")
        logger.error("  1. MT5 终端正在运行")
        logger.error("  2. 已登录交易账户")
        logger.error("  3. 工具→选项→EA交易→允许DLL导入 已勾选")
        return False

    logger.info("✅ MT5 连接成功")
    return True


def get_account_info(mt5):
    """获取 MT5 账户信息"""
    info = mt5.account_info()
    if info is None:
        logger.warning("无法获取账户信息")
        return None

    info_dict = {
        'number': info.login,
        'name': info.name,
        'company': info.company,
        'server': info.server,
        'currency': info.currency,
        'leverage': info.leverage,
        'balance': info.balance,
        'equity': info.equity,
        'free_margin': info.margin_free,
        'margin': info.margin,
        'profit': info.profit,
        'is_demo': (info.trade_mode == 0),  # 0=DEMO, 1=CONTEST, 2=REAL
        'broker': info.company,
        'terminal': 'MetaTrader 5',
    }

    logger.info(f"  账号: {info.login} ({info.server})")
    logger.info(f"  公司: {info.company}")
    logger.info(f"  币种: {info.currency}  杠杆: 1:{info.leverage}")
    logger.info(f"  余额: {info.balance:.2f}  净值: {info.equity:.2f}")
    logger.info(f"  模式: {'模拟盘' if info_dict['is_demo'] else '实盘'}")

    return info_dict


def get_history_deals(mt5, days=0):
    """获取历史成交记录"""
    # 时间范围
    if days > 0:
        from_date = datetime.now() - timedelta(days=days)
    else:
        from_date = datetime(2010, 1, 1)  # 全部历史 (MT5 最早支持 2010)

    to_date = datetime.now()

    logger.info(f"正在获取历史成交 ({from_date.date()} ~ {to_date.date()})...")

    deals = mt5.history_deals_get(from_date, to_date)
    if deals is None:
        logger.warning(f"历史成交获取失败: {mt5.last_error()}")
        return []
    if len(deals) == 0:
        logger.info("  没有找到历史成交记录")
        return []

    logger.info(f"  找到 {len(deals)} 条成交记录，正在整理...")

    orders = []
    for deal in deals:
        # DEAL_ENTRY_IN=0 入场, DEAL_ENTRY_OUT=1 出场, DEAL_ENTRY_INOUT=2
        # DEAL_TYPE_BUY=0, DEAL_TYPE_SELL=1
        # 只处理出场(平仓)成交，因为入场单没有盈亏
        if deal.entry != 1:  # 只取平仓
            continue

        order = {
            'ticket': deal.ticket,
            'symbol': deal.symbol,
            'type': 'buy' if deal.type in (0, 2) else 'sell',  # 0=buy, 1=sell
            'volume': deal.volume,
            'open_price': deal.price,    # 平仓价（作为 close_price）
            'close_price': deal.price,
            'open_time': None,           # 入场时间需要从对应订单获取
            'close_time': datetime.fromtimestamp(deal.time).strftime('%Y.%m.%d %H:%M:%S'),
            'profit': deal.profit,
            'sl': 0.0,
            'tp': 0.0,
            'commission': deal.commission,
            'swap': deal.swap,
            'comment': deal.comment or '',
            'magic': deal.magic,
            # 补充字段（来自订单）
            'position_id': deal.position_id,
            'order_id': deal.order,
        }

        # 从订单历史获取入场详情
        order_history = mt5.history_orders_get(ticket=deal.order)
        if order_history and len(order_history) > 0:
            oh = order_history[0]
            order['open_price'] = oh.price_open
            order['open_time'] = datetime.fromtimestamp(oh.time_setup).strftime('%Y.%m.%d %H:%M:%S')
            order['sl'] = oh.sl
            order['tp'] = oh.tp

        orders.append(order)

    logger.info(f"  整理完成: {len(orders)} 条有效成交")
    return orders


def push_orders(orders):
    """推送订单到 Flask"""
    if not orders:
        logger.info("没有需要推送的数据")
        return True

    url = FLASK_URL + PUSH_ORDERS_API
    try:
        resp = requests.post(url, json=orders, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"✅ 推送完成: 导入 {data.get('imported', 0)} 条, 跳过 {data.get('skipped', 0)} 条")
            return True
        else:
            logger.error(f"❌ 推送失败 (HTTP {resp.status_code}): {resp.text[:200]}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ 无法连接到 Flask ({FLASK_URL})")
        logger.error("请先启动复盘系统: python app.py")
        return False
    except Exception as e:
        logger.error(f"❌ 推送异常: {e}")
        return False


def push_account(account_info):
    """推送账户信息到 Flask"""
    if not account_info:
        return

    url = FLASK_URL + PUSH_ACCOUNT_API
    try:
        resp = requests.post(url, json=account_info, timeout=15)
        if resp.status_code == 200:
            logger.info(f"🏦 账户信息已推送: {account_info['number']}")
    except Exception as e:
        logger.warning(f"账户信息推送失败: {e}")


def print_account_summary(account_info):
    """打印账户摘要"""
    if not account_info:
        return
    print("\n" + "=" * 50)
    print(f"  📊 MT5 账户摘要")
    print("=" * 50)
    print(f"  账号:     {account_info['number']}")
    print(f"  名称:     {account_info['name']}")
    print(f"  服务器:   {account_info['server']}")
    print(f"  公司:     {account_info['company']}")
    print(f"  币种/杠杆: {account_info['currency']} / 1:{account_info['leverage']}")
    print(f"  余额:     {account_info['balance']:.2f}")
    print(f"  净值:     {account_info['equity']:.2f}")
    print(f"  类型:     {'模拟盘' if account_info['is_demo'] else '实盘'}")
    print("=" * 50)


def run_import(mt5, days=0, push=True, show_info=True):
    """执行一次完整的导入"""
    # 1. 获取并显示账户信息
    account_info = get_account_info(mt5)
    if show_info and account_info:
        print_account_summary(account_info)

    if push and account_info:
        push_account(account_info)

    # 2. 获取历史成交
    orders = get_history_deals(mt5, days)
    if show_info:
        print(f"\n  共获取到 {len(orders)} 条平仓记录")

    # 3. 推送到 Flask
    if push and orders:
        success = push_orders(orders)
        if success and show_info:
            print("\n  ✅ 数据已全部导入复盘系统！")
            print(f"  🔗 打开 http://localhost:5000 查看")
        return success

    return True


def watch_mode(mt5, interval=300, days=1):
    """持续监控模式: 每隔 interval 秒拉取一次"""
    logger.info(f"📡 进入监控模式 (每 {interval} 秒检查一次)")
    logger.info("按 Ctrl+C 停止\n")

    while True:
        try:
            # 刷新账户信息
            account_info = get_account_info(mt5)
            if account_info:
                push_account(account_info)

            # 拉取最近 days 天的成交
            orders = get_history_deals(mt5, days)
            if orders:
                push_orders(orders)

            logger.info(f"⏳ 下次检查在 {interval} 秒后...\n")
            time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("⏹  监控已停止")
            break
        except Exception as e:
            logger.error(f"监控异常: {e}")
            time.sleep(interval)


def main():
    global FLASK_URL

    parser = argparse.ArgumentParser(description='MT5 直连导入脚本')
    parser.add_argument('--days', type=int, default=0, help='导入最近 N 天 (0=全部历史)')
    parser.add_argument('--url', default=FLASK_URL, help=f'Flask 地址 (默认 {FLASK_URL})')
    parser.add_argument('--path', help='MT5 终端路径 (默认自动检测)')
    parser.add_argument('--info', action='store_true', help='仅显示账户信息')
    parser.add_argument('--watch', action='store_true', help='持续监控模式')
    parser.add_argument('--interval', type=int, default=300, help='监控间隔秒数 (默认300)')
    parser.add_argument('--quiet', action='store_true', help='安静模式')

    args = parser.parse_args()

    if args.url:
        FLASK_URL = args.url.rstrip('/')

    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    # 导入 MetaTrader5
    mt5 = ensure_mt5()

    # 连接 MT5
    if not connect(mt5, args.path):
        sys.exit(1)

    try:
        if args.info:
            # 仅显示账户信息
            info = get_account_info(mt5)
            if info:
                print_account_summary(info)
            return

        if args.watch:
            # 监控模式
            watch_mode(mt5, args.interval, args.days or 1)
            return

        # 一次性导入
        run_import(mt5, args.days, push=True, show_info=not args.quiet)

    finally:
        mt5.shutdown()
        logger.info("MT5 连接已关闭")


if __name__ == '__main__':
    main()
