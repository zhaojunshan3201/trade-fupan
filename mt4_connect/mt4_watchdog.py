#!/usr/bin/env python
r"""
MT4 文件监控自动导入脚本 (方案 A — 最稳定推荐)

原理:
  MQL4 脚本(已提供 TradeExport.mq4)将交易历史导出为 CSV 到 MT4 公共目录。
  本 Python 脚本用 watchdog 监听该目录，新文件出现时自动 POST 到 Flask 端点。

使用方式:
  python mt4_watchdog.py                      # 默认监听 MT4 公共目录
  python mt4_watchdog.py --dir D:\MT4\Data    # 指定自定义目录
  python mt4_watchdog.py --url http://localhost:5000  # 指定 Flask 地址

依赖:
  pip install watchdog requests
"""

import os
import sys
import time
import json
import argparse
import logging
import requests
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('mt4_watchdog')

# Flask 端点
FLASK_URL = 'http://127.0.0.1:5000'
PUSH_API = '/import/api/mql4_push'
SCAN_API = '/import/api/scan_csv'
UPLOAD_API = '/import/upload'


def find_mt4_common_dirs():
    """自动发现 MT4 公共文件目录"""
    appdata = os.environ.get('APPDATA', '')
    if not appdata:
        return []

    terminal_root = Path(appdata) / 'MetaQuotes' / 'Terminal'
    if not terminal_root.exists():
        return []

    # MT4 实例目录通常为长 hash 名称，包含 MQL4 子目录
    dirs = []
    for child in terminal_root.iterdir():
        if child.is_dir() and (child / 'MQL4').exists():
            files_dir = child / 'Files'
            if files_dir.exists():
                dirs.append(str(files_dir))
            # 也添加 MQL4\Files
            mql4_files = child / 'MQL4' / 'Files'
            if mql4_files.exists():
                dirs.append(str(mql4_files))
    return dirs


def push_csv_to_flask(filepath):
    """将 CSV 文件 POST 到 Flask 导入端点"""
    url = FLASK_URL + UPLOAD_API
    try:
        with open(filepath, 'rb') as f:
            files = {'file': (os.path.basename(filepath), f, 'text/csv')}
            resp = requests.post(url, files=files, timeout=30, allow_redirects=False)

        if resp.status_code in (200, 302):
            logger.info(f"✅ 导入成功: {os.path.basename(filepath)}")
            return True
        else:
            logger.warning(f"⚠️ 导入返回 {resp.status_code}: {resp.text[:200]}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ 无法连接到 Flask ({FLASK_URL})，请确保服务已启动")
        return False
    except Exception as e:
        logger.error(f"❌ 导入失败 {filepath}: {e}")
        return False


def push_json_to_flask(orders):
    """将 JSON 数据直接 POST 到 MQL4 推送端点"""
    url = FLASK_URL + PUSH_API
    try:
        resp = requests.post(url, json=orders, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"✅ 推送成功: 导入 {data.get('imported', 0)} 条")
            return True
        else:
            logger.warning(f"⚠️ 推送返回 {resp.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ 推送失败: {e}")
        return False


def scan_mt4_directory():
    """主动扫描 MT4 目录中的 CSV 文件"""
    dirs = find_mt4_common_dirs()
    if not dirs:
        logger.warning("未找到 MT4 公共目录，请通过 --dir 参数手动指定")
        return 0

    total = 0
    for d in dirs:
        csv_files = list(Path(d).glob('trade_export*.csv'))
        if not csv_files:
            csv_files = list(Path(d).glob('*.csv'))
        for fp in sorted(csv_files, key=lambda p: p.stat().st_mtime):
            logger.info(f"发现文件: {fp.name}")
            if push_csv_to_flask(str(fp)):
                total += 1
                # 可选: 重命名已处理文件避免重复
                # fp.rename(fp.with_suffix('.imported.csv'))
    return total


class Mt4FileHandler:
    """Watchdog 文件事件处理器"""

    def __init__(self, watch_dirs):
        self.watch_dirs = watch_dirs
        self.processed_files = set()

    def process(self, filepath):
        """处理新文件"""
        if not str(filepath).lower().endswith('.csv'):
            return
        if str(filepath) in self.processed_files:
            return

        logger.info(f"📄 检测到新文件: {os.path.basename(filepath)}")
        success = push_csv_to_flask(str(filepath))
        if success:
            self.processed_files.add(str(filepath))

    def on_created(self, filepath):
        self.process(filepath)

    def on_modified(self, filepath):
        # 只处理完成写入的文件（等2秒确认写入完成）
        time.sleep(2)
        self.process(filepath)


def start_watchdog(watch_dir=None):
    """启动文件监控"""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        logger.error("请先安装 watchdog: pip install watchdog")
        sys.exit(1)

    class Handler(FileSystemEventHandler):
        def __init__(self, processor):
            self.processor = processor

        def on_created(self, event):
            if not event.is_directory:
                self.processor.on_created(event.src_path)

        def on_modified(self, event):
            if not event.is_directory:
                self.processor.on_modified(event.src_path)

    # 确定监控目录
    watch_dirs = []
    if watch_dir:
        watch_dirs = [watch_dir]
    else:
        watch_dirs = find_mt4_common_dirs()
        if not watch_dirs:
            logger.warning("未自动发现 MT4 目录，使用当前目录")
            watch_dirs = ['.']

    processor = Mt4FileHandler(watch_dirs)
    observer = Observer()

    for wd in watch_dirs:
        if not os.path.exists(wd):
            logger.warning(f"目录不存在，跳过: {wd}")
            continue
        os.makedirs(wd, exist_ok=True)
        observer.schedule(Handler(processor), wd, recursive=False)
        logger.info(f"👀 正在监控: {wd}")

    # 启动前先扫描一次已有文件
    logger.info("🔍 扫描已有文件...")
    for wd in watch_dirs:
        for fp in sorted(Path(wd).glob('*.csv'), key=lambda p: p.stat().st_mtime):
            processor.process(str(fp))

    observer.start()
    logger.info(f"✅ 监控已启动 (Flask: {FLASK_URL})")
    logger.info("按 Ctrl+C 停止")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("已停止监控")

    observer.join()


def main():
    global FLASK_URL

    parser = argparse.ArgumentParser(description='MT4 文件监控自动导入')
    parser.add_argument('--dir', help='监控目录（默认自动发现 MT4 公共目录）')
    parser.add_argument('--url', default=FLASK_URL, help=f'Flask 地址 (默认 {FLASK_URL})')
    parser.add_argument('--scan', action='store_true', help='扫描一次后退出')
    parser.add_argument('--daemon', action='store_true', help='后台运行模式')

    args = parser.parse_args()

    if args.url:
        FLASK_URL = args.url.rstrip('/')

    if args.scan:
        count = scan_mt4_directory()
        print(f"扫描完成，共处理 {count} 个文件")
        return

    # 启动监控
    start_watchdog(args.dir)


if __name__ == '__main__':
    main()
