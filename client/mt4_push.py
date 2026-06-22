# -*- coding: utf-8 -*-
r"""
MT4 客户端连接器
监控 MT4 导出目录，自动上传 CSV 到服务器。

用法:
  python mt4_push.py
  或: python mt4_push.py --setup (首次配置)

配置: config.ini
  [server]
  url = http://your-server.com:5000
  token = your_api_token_here
  watch_dir = C:\Users\...\MetaQuotes\Terminal\...\Files
"""

import os
import sys
import time
import configparser
import logging
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('mt4_client')

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')


def load_config():
    c = configparser.ConfigParser()
    defaults = {
        'url': 'http://127.0.0.1:5000',
        'token': '',
        'watch_dir': '',
    }
    if os.path.exists(CONFIG_FILE):
        c.read(CONFIG_FILE, encoding='utf-8')
    if 'server' not in c:
        c['server'] = {}
    for k, v in defaults.items():
        if k not in c['server'] or not c['server'][k]:
            c['server'][k] = v
    return c['server']


def find_mt4_dirs():
    """自动查找 MT4 数据目录"""
    appdata = os.environ.get('APPDATA', '')
    if not appdata:
        return []
    term = Path(appdata) / 'MetaQuotes' / 'Terminal'
    if not term.exists():
        return []
    dirs = []
    for child in term.iterdir():
        if child.is_dir():
            files_dir = child / 'MQL4' / 'Files'
            if files_dir.exists():
                dirs.append(str(files_dir))
            files_dir2 = child / 'Files'
            if files_dir2.exists():
                dirs.append(str(files_dir2))
    return dirs


def upload_csv(config, filepath):
    """上传 CSV 到服务器"""
    url = config['url'].rstrip('/')
    try:
        with open(filepath, 'rb') as f:
            files = {'file': (os.path.basename(filepath), f, 'text/csv')}
            resp = requests.post(f'{url}/import/upload?token={config["token"]}',
                               files=files, timeout=30)
        if resp.status_code in (200, 302):
            logger.info(f'上传成功: {os.path.basename(filepath)}')
            return True
        logger.warning(f'上传失败: {resp.status_code}')
        return False
    except Exception as e:
        logger.error(f'上传异常: {e}')
        return False


def interactive_setup(config):
    print('\n' + '=' * 50)
    print('  MT4 客户端连接器 - 首次配置')
    print('=' * 50)

    url = input(f'服务器地址 [{config["url"]}]: ').strip()
    if url: config['url'] = url

    token = input(f'API Token [{config["token"][:8] + "..." if config["token"] else "无"}]: ').strip()
    if token: config['token'] = token

    dirs = find_mt4_dirs()
    if dirs:
        print('\n找到以下 MT4 目录:')
        for i, d in enumerate(dirs):
            print(f'  [{i}] {d}')
        choice = input(f'选择目录 [0..{len(dirs)-1}] 或手动输入: ').strip()
        if choice.isdigit() and int(choice) < len(dirs):
            config['watch_dir'] = dirs[int(choice)]
        elif choice:
            config['watch_dir'] = choice
    else:
        wd = input('MT4 导出目录(手动输入): ').strip()
        if wd: config['watch_dir'] = wd

    c = configparser.ConfigParser()
    c['server'] = config
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        c.write(f)
    print('配置已保存！')


def main():
    config = load_config()

    if not config['token'] or '--setup' in sys.argv:
        interactive_setup(config)
        config = load_config()

    watch_dir = config['watch_dir']
    if not watch_dir:
        watch_dir = find_mt4_dirs()
        if watch_dir:
            watch_dir = watch_dir[0]
            config['watch_dir'] = watch_dir
        else:
            logger.error('未找到 MT4 目录，请运行 python mt4_push.py --setup 手动配置')
            return

    print('\n' + '=' * 50)
    print('  MT4 客户端连接器')
    print(f'  服务器: {config["url"]}')
    print(f'  监控目录: {watch_dir}')
    print('  按 Ctrl+C 停止')
    print('=' * 50)

    seen = set()
    while True:
        try:
            if os.path.exists(watch_dir):
                for f in sorted(Path(watch_dir).glob('*.csv'),
                              key=lambda p: p.stat().st_mtime):
                    fpath = str(f)
                    if fpath not in seen:
                        seen.add(fpath)
                        logger.info(f'新文件: {f.name}')
                        upload_csv(config, fpath)

            time.sleep(30)
        except KeyboardInterrupt:
            logger.info('已停止')
            break
        except Exception as e:
            logger.error(f'异常: {e}')
            time.sleep(60)


if __name__ == '__main__':
    main()
