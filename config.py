import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_URI = os.environ.get(
    'DATABASE_URL',
    'sqlite:///' + os.path.join(BASE_DIR, 'trade_journal.db')
)

# 数据库配置: 通过环境变量 DATABASE_URL 选择
# SQLite (开发/单机): 不需设置
# PostgreSQL (生产): DATABASE_URL=postgresql://user:pass@host:5432/dbname
# MySQL (生产):    DATABASE_URL=mysql+pymysql://user:pass@host:3306/dbname

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production-!!')
    SQLALCHEMY_DATABASE_URI = DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = (
        {}
        if DATABASE_URI.startswith('sqlite')
        else {
            'pool_size': 20,
            'pool_recycle': 3600,
            'pool_pre_ping': True,
        }
    )
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

    AUTO_SYNC_ENABLED = os.environ.get('AUTO_SYNC_ENABLED', 'true').lower() == 'true'
    AUTO_SYNC_INTERVAL_MINUTES = int(os.environ.get('AUTO_SYNC_INTERVAL', '60'))
    AUTO_SYNC_ON_STARTUP = os.environ.get('AUTO_SYNC_STARTUP', 'true').lower() == 'true'
