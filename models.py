"""数据库模型定义"""
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()
login_manager = LoginManager()


class User(UserMixin, db.Model):
    """系统用户"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(100), unique=True, nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), default='user')
    is_active = db.Column(db.Boolean, default=True)
    api_token = db.Column(db.String(64), unique=True, nullable=True, index=True)

    orders = db.relationship('Order', backref='owner', lazy='dynamic')
    reviews = db.relationship('TradeReview', backref='owner', lazy='dynamic')
    plans = db.relationship('TradingPlan', backref='owner', lazy='dynamic')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'

    def to_dict(self):
        return {
            'id': self.id, 'username': self.username, 'email': self.email,
            'role': self.role, 'order_count': self.orders.count(),
            'review_count': self.reviews.count(),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }


class PlatformConfig(db.Model):
    """MT4/MT5 平台配置"""
    __tablename__ = 'platform_configs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False, comment='平台名称')
    platform_type = db.Column(db.String(10), nullable=False, comment='mt4/mt5')
    server = db.Column(db.String(100), nullable=False, comment='服务器地址')
    broker = db.Column(db.String(100), nullable=True, comment='经纪商名称')
    api_type = db.Column(db.String(20), default='terminal', comment='连接方式: terminal/manager/zmq')
    mt5_path = db.Column(db.String(200), nullable=True, comment='MT5终端路径')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    accounts = db.relationship('TradingAccount', backref='platform', lazy='dynamic',
                               cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'platform_type': self.platform_type,
            'server': self.server, 'broker': self.broker, 'api_type': self.api_type,
            'is_active': self.is_active, 'account_count': self.accounts.count(),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
        }


class TradingAccount(db.Model):
    """交易账户"""
    __tablename__ = 'trading_accounts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    platform_id = db.Column(db.Integer, db.ForeignKey('platform_configs.id'), nullable=False)
    account_number = db.Column(db.BigInteger, nullable=False, comment='MT4/MT5账号')
    account_name = db.Column(db.String(100), nullable=True, comment='账户名称')
    password_encrypted = db.Column(db.String(200), nullable=True, comment='加密存储的交易密码')
    is_demo = db.Column(db.Boolean, default=True, comment='模拟/实盘')
    currency = db.Column(db.String(10), nullable=True)
    leverage = db.Column(db.Integer, nullable=True)
    balance = db.Column(db.Float, default=0.0)
    equity = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    last_sync_at = db.Column(db.DateTime, nullable=True, comment='最后同步时间')
    sync_status = db.Column(db.String(20), default='pending', comment='pending/syncing/success/error')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'account_number': self.account_number,
            'account_name': self.account_name, 'is_demo': self.is_demo,
            'currency': self.currency, 'leverage': self.leverage,
            'balance': self.balance, 'equity': self.equity,
            'is_active': self.is_active, 'sync_status': self.sync_status,
            'last_sync_at': self.last_sync_at.strftime('%Y-%m-%d %H:%M') if self.last_sync_at else None,
            'platform_name': self.platform.name if self.platform else None,
            'platform_type': self.platform.platform_type if self.platform else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
        }


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@login_manager.request_loader
def load_user_from_request(request):
    token = request.args.get('token')
    if not token and request.is_json:
        data = request.get_json(silent=True) or {}
        token = data.get('token')
    if not token:
        return None
    return User.query.filter_by(api_token=token, is_active=True).first()


class Order(db.Model):
    """MT4 交易订单"""
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket = db.Column(db.BigInteger, unique=True, nullable=False, index=True, comment='MT4 订单号')
    symbol = db.Column(db.String(20), nullable=False, comment='交易品种')
    order_type = db.Column(db.String(10), nullable=False, comment='方向: buy/sell')
    volume = db.Column(db.Float, nullable=False, comment='手数')
    open_time = db.Column(db.DateTime, nullable=False, comment='开仓时间')
    close_time = db.Column(db.DateTime, nullable=True, comment='平仓时间')
    open_price = db.Column(db.Float, nullable=False, comment='开仓价')
    close_price = db.Column(db.Float, nullable=True, comment='平仓价')
    sl = db.Column(db.Float, nullable=True, comment='止损')
    tp = db.Column(db.Float, nullable=True, comment='止盈')
    commission = db.Column(db.Float, default=0.0, comment='手续费')
    swap = db.Column(db.Float, default=0.0, comment='库存费')
    profit = db.Column(db.Float, default=0.0, comment='盈亏')
    balance = db.Column(db.Float, nullable=True, comment='平仓后余额')
    comment = db.Column(db.String(200), nullable=True, comment='订单备注')
    magic = db.Column(db.BigInteger, nullable=True, comment='EA Magic Number')
    import_batch = db.Column(db.String(40), nullable=True, comment='导入批次')
    account_number = db.Column(db.BigInteger, nullable=True, index=True, comment='MT4/MT5 账号')

    # 关联
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    review = db.relationship('TradeReview', backref='order', uselist=False, cascade='all, delete-orphan')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def pips(self):
        """估算盈亏点数（根据品种类型自动适配点值）"""
        if self.close_price is None or self.open_price is None:
            return 0.0
        diff = self.close_price - self.open_price
        if self.order_type == 'sell':
            diff = -diff

        sym = self.symbol.upper()

        # 黄金/白银（2位小数报价）
        if sym in ('XAUUSD', 'GOLD', 'XAGUSD', 'SILVER') or sym.startswith('XAU'):
            return diff * 100  # 0.01 = 1 pip

        # 原油/大宗商品（2-3位小数）
        if sym in ('USOIL', 'UKOIL', 'WTI', 'BRENT', 'XTIUSD', 'XBRUSD') or 'OIL' in sym:
            return diff * 100

        # 指数（通常整数报价）
        if sym in ('US30', 'SP500', 'NAS100', 'DJ30', 'DAX30', 'GER30',
                   'UK100', 'JPN225', 'AUS200', 'HKG50', 'CHINA50',
                   'STOXX50', 'ESP35', 'FRA40'):
            return diff * 10  # 1.0 = 1 点

        # 数字货币
        if sym in ('BTCUSD', 'ETHUSD', 'LTCUSD', 'XRPUSD', 'BCHUSD'):
            return diff * 100

        # 日叉盘（3位小数）
        if 'JPY' in sym:
            return diff * 100

        # 大部分外汇（5位小数报价，4位=1pip）
        return diff * 10000

    @property
    def is_win(self):
        """是否盈利单"""
        return self.profit > 0

    @property
    def is_loss(self):
        """是否亏损单"""
        return self.profit < 0

    @property
    def is_reviewed(self):
        """是否已复盘"""
        return self.review is not None

    @property
    def duration_minutes(self):
        """持仓时长（分钟）"""
        if self.open_time and self.close_time:
            delta = self.close_time - self.open_time
            return int(delta.total_seconds() / 60)
        return 0

    def to_dict(self):
        return {
            'id': self.id,
            'ticket': self.ticket,
            'symbol': self.symbol,
            'order_type': self.order_type,
            'volume': self.volume,
            'open_time': self.open_time.strftime('%Y-%m-%d %H:%M:%S') if self.open_time else None,
            'close_time': self.close_time.strftime('%Y-%m-%d %H:%M:%S') if self.close_time else None,
            'open_price': self.open_price,
            'close_price': self.close_price,
            'sl': self.sl,
            'tp': self.tp,
            'commission': self.commission,
            'swap': self.swap,
            'profit': self.profit,
            'balance': self.balance,
            'comment': self.comment,
            'pips': round(self.pips, 1),
            'is_win': self.is_win,
            'is_reviewed': self.is_reviewed,
            'duration_minutes': self.duration_minutes,
            'account_number': self.account_number,
        }

    def __repr__(self):
        return f'<Order {self.ticket} {self.symbol} {self.order_type} PnL={self.profit}>'


class AccountInfo(db.Model):
    """MT4 账户信息快照"""
    __tablename__ = 'account_info'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    number = db.Column(db.BigInteger, nullable=True, comment='MT4账号')
    name = db.Column(db.String(100), nullable=True, comment='账户名称')
    company = db.Column(db.String(100), nullable=True, comment='经纪商')
    server = db.Column(db.String(100), nullable=True, comment='服务器')
    currency = db.Column(db.String(10), nullable=True, comment='币种')
    leverage = db.Column(db.Integer, nullable=True, comment='杠杆')
    balance = db.Column(db.Float, nullable=True, comment='余额')
    equity = db.Column(db.Float, nullable=True, comment='净值')
    free_margin = db.Column(db.Float, nullable=True, comment='可用保证金')
    margin = db.Column(db.Float, nullable=True, comment='已用保证金')
    profit = db.Column(db.Float, nullable=True, comment='浮动盈亏')
    is_demo = db.Column(db.Boolean, default=True, comment='是否模拟盘')
    broker = db.Column(db.String(100), nullable=True, comment='终端公司')
    terminal = db.Column(db.String(100), nullable=True, comment='终端版本')
    terminal_type = db.Column(db.String(10), nullable=True, comment='终端类型: mt4/mt5')
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, comment='记录时间')

    def to_dict(self):
        return {
            'id': self.id,
            'number': self.number,
            'name': self.name,
            'company': self.company,
            'server': self.server,
            'currency': self.currency,
            'leverage': self.leverage,
            'balance': self.balance,
            'equity': self.equity,
            'free_margin': self.free_margin,
            'margin': self.margin,
            'profit': self.profit,
            'is_demo': self.is_demo,
            'broker': self.broker,
            'terminal': self.terminal,
            'terminal_type': self.terminal_type,
            'recorded_at': self.recorded_at.strftime('%Y-%m-%d %H:%M:%S') if self.recorded_at else None,
        }


class TradeReview(db.Model):
    """订单复盘记录"""
    __tablename__ = 'trade_reviews'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), unique=True, nullable=False, comment='关联订单')

    # 复盘核心字段
    fundamental_context = db.Column(db.Text, nullable=True, comment='基本面背景（数据发布、央行政策、地缘事件等）')
    major_trend = db.Column(db.String(50), nullable=True, comment='大周期趋势状态（上升/下降/震荡）')
    minor_signal = db.Column(db.Text, nullable=True, comment='小周期下单信号（K线形态、指标信号等）')
    trading_theory = db.Column(db.String(100), nullable=True, comment='交易理论/系统（道氏/缠论/谐波/裸K/均线等）')
    entry_quality = db.Column(db.String(20), nullable=True, comment='入场质量评分（A/B/C/D）')
    exit_reason = db.Column(db.Text, nullable=True, comment='出场原因')
    emotional_state = db.Column(db.String(50), nullable=True, comment='交易时情绪状态')

    # 复盘结果
    lesson_learned = db.Column(db.Text, nullable=True, comment='经验教训')
    improvement = db.Column(db.Text, nullable=True, comment='改进方向')
    tags = db.Column(db.String(200), nullable=True, comment='标签（逗号分隔）')
    rating = db.Column(db.Integer, nullable=True, comment='总体评分 1-5')
    is_planned_trade = db.Column(db.Boolean, default=False, comment='是否按计划执行')
    plan_deviation = db.Column(db.Text, nullable=True, comment='偏离计划的原因')
    screenshot = db.Column(db.String(200), nullable=True, comment='截图路径')
    trade_timeframe = db.Column(db.String(5), nullable=True, comment='交易周期')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    admin_note = db.Column(db.Text, nullable=True, comment='管理员点评')
    admin_note_at = db.Column(db.DateTime, nullable=True, comment='点评时间')
    is_public = db.Column(db.Boolean, default=True, comment='是否公开显示在主页')

    reviewed_at = db.Column(db.DateTime, default=datetime.utcnow, comment='复盘时间')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'fundamental_context': self.fundamental_context,
            'major_trend': self.major_trend,
            'minor_signal': self.minor_signal,
            'trading_theory': self.trading_theory,
            'entry_quality': self.entry_quality,
            'exit_reason': self.exit_reason,
            'emotional_state': self.emotional_state,
            'lesson_learned': self.lesson_learned,
            'improvement': self.improvement,
            'tags': self.tags.split(',') if self.tags else [],
            'rating': self.rating,
            'is_planned_trade': self.is_planned_trade,
            'plan_deviation': self.plan_deviation,
            'trade_timeframe': self.trade_timeframe,
            'admin_note': self.admin_note,
            'admin_note_at': self.admin_note_at.strftime('%Y-%m-%d %H:%M') if self.admin_note_at else None,
            'reviewed_at': self.reviewed_at.strftime('%Y-%m-%d %H:%M:%S') if self.reviewed_at else None,
        }


class TradingPlan(db.Model):
    """交易计划"""
    __tablename__ = 'trading_plans'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(200), nullable=False, comment='计划标题')
    symbol = db.Column(db.String(20), nullable=False, comment='交易品种')
    direction = db.Column(db.String(10), nullable=False, comment='方向: buy/sell')

    # 计划内容
    fundamental_analysis = db.Column(db.Text, nullable=True, comment='基本面分析')
    technical_analysis = db.Column(db.Text, nullable=True, comment='技术面分析')
    entry_reason = db.Column(db.Text, nullable=True, comment='入场理由')
    entry_condition = db.Column(db.Text, nullable=True, comment='入场条件')
    exit_condition = db.Column(db.Text, nullable=True, comment='出场条件')

    # 计划价位
    planned_entry = db.Column(db.Float, nullable=True, comment='计划入场价')
    planned_sl = db.Column(db.Float, nullable=True, comment='计划止损')
    planned_tp1 = db.Column(db.Float, nullable=True, comment='第一目标位')
    planned_tp2 = db.Column(db.Float, nullable=True, comment='第二目标位')
    risk_percent = db.Column(db.Float, nullable=True, comment='风险比例 %')

    # 状态
    status = db.Column(
        db.String(20), nullable=False, default='planned',
        comment='状态: planned/active/completed/cancelled'
    )
    priority = db.Column(db.String(10), default='medium', comment='优先级: high/medium/low')

    # 执行情况
    actual_entry = db.Column(db.Float, nullable=True, comment='实际入场价')
    actual_exit = db.Column(db.Float, nullable=True, comment='实际出场价')
    actual_volume = db.Column(db.Float, nullable=True, comment='实际手数')
    actual_entry_time = db.Column(db.DateTime, nullable=True, comment='实际入场时间')
    actual_exit_time = db.Column(db.DateTime, nullable=True, comment='实际出场时间')
    actual_profit = db.Column(db.Float, nullable=True, comment='实际盈亏')
    execution_score = db.Column(db.Integer, nullable=True, comment='执行评分 1-5')

    # 计划日期
    plan_date = db.Column(db.Date, nullable=False, default=date.today, comment='计划日期')
    target_date = db.Column(db.Date, nullable=True, comment='目标执行日期')
    review_notes = db.Column(db.Text, nullable=True, comment='回顾总结')
    related_order_ticket = db.Column(db.BigInteger, nullable=True, comment='关联的MT4订单号')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    is_public = db.Column(db.Boolean, default=True, comment='是否公开显示在主页')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'symbol': self.symbol,
            'direction': self.direction,
            'fundamental_analysis': self.fundamental_analysis,
            'technical_analysis': self.technical_analysis,
            'entry_reason': self.entry_reason,
            'entry_condition': self.entry_condition,
            'exit_condition': self.exit_condition,
            'planned_entry': self.planned_entry,
            'planned_sl': self.planned_sl,
            'planned_tp1': self.planned_tp1,
            'planned_tp2': self.planned_tp2,
            'risk_percent': self.risk_percent,
            'status': self.status,
            'priority': self.priority,
            'actual_entry': self.actual_entry,
            'actual_exit': self.actual_exit,
            'actual_volume': self.actual_volume,
            'actual_entry_time': self.actual_entry_time.strftime('%Y-%m-%d %H:%M') if self.actual_entry_time else None,
            'actual_exit_time': self.actual_exit_time.strftime('%Y-%m-%d %H:%M') if self.actual_exit_time else None,
            'actual_profit': self.actual_profit,
            'execution_score': self.execution_score,
            'plan_date': self.plan_date.strftime('%Y-%m-%d') if self.plan_date else None,
            'target_date': self.target_date.strftime('%Y-%m-%d') if self.target_date else None,
            'review_notes': self.review_notes,
            'related_order_ticket': self.related_order_ticket,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }
