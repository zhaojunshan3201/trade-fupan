# 交易复盘系统

一个基于 Flask 的个人交易复盘与交易日志系统，用于沉淀 MT4/MT5 交易记录、结构化复盘、交易计划、账户同步和统计分析。

系统目标不是预测市场，而是帮助交易者持续追踪自己的交易行为：哪些交易符合计划，哪些交易受情绪影响，哪些品种和策略真正有正期望。

## 主要功能

### 公开主页

- 展示公开交易计划、最新复盘、精选复盘和交易排名
- 首页采用交易工作台风格设计，适合快速浏览系统内容
- 未登录用户可浏览公开内容，登录后进入个人交易仪表盘

### 用户与权限

- 支持注册、登录、退出登录
- 第一个注册用户自动成为管理员
- 普通用户只能查看和操作自己的订单、复盘、计划和账户数据
- 管理员可查看用户统计、用户详情、复盘点评、重置密码、启用或禁用用户

### 交易记录

- 支持按用户隔离交易订单
- 支持订单列表、分页、品种筛选、方向筛选、是否复盘筛选
- 支持按订单查看详情 API
- 自动计算点数、持仓时长、盈亏状态和复盘状态

### 交易复盘

- 对每一笔交易记录结构化复盘
- 复盘字段包含基本面背景、大周期趋势、小周期信号、交易理论、入场质量、出场原因、情绪状态、经验教训、改进方向、标签和评分
- 支持复盘列表、复盘表单、复盘保存 API、复盘删除 API
- 支持尝试从 MT5 获取订单相关 K 线快照；该能力依赖本机 MT5 终端和历史数据

### 数据分析

- 总订单数、已平仓数、胜率、总盈亏、平均盈亏、盈亏比、最大回撤
- 近 30 天盈亏统计
- 资金曲线和月度统计
- 按品种、买卖方向统计表现
- 复盘标签、交易理论、入场质量、情绪状态和趋势分布统计
- 对比已复盘和未复盘交易表现

### 交易计划

- 创建、编辑和删除交易计划
- 记录基本面分析、技术面分析、入场理由、入场条件和出场条件
- 设置计划入场价、止损、止盈目标、风险比例、优先级和目标日期
- 记录实际执行情况，包括实际入场、出场、手数、盈亏、执行评分和关联订单
- 支持计划状态更新 API

### 数据导入与交易终端连接

- 支持 MT4 标准 CSV 上传导入
- 支持 MQL4/客户端脚本通过 API 推送交易记录
- 支持账户信息推送和最新账户快照查询
- 支持 MT4 公共目录 CSV 扫描
- 支持 MT5 官方 Python API 测试连接和导入历史成交
- 提供 MT4 导出脚本、MT4 连接辅助脚本、MT5 连接脚本和本地客户端工具

### 账户管理

- 管理 MT4/MT5 平台配置
- 管理交易账户
- 生成和查看 API Token
- 手动触发账户同步
- 查看后台自动同步状态

## 技术栈

- 后端：Python、Flask、Flask-Login、Flask-SQLAlchemy
- 数据库：默认 SQLite，也可通过 `DATABASE_URL` 使用 PostgreSQL 或 MySQL/MariaDB
- 前端：Jinja2 模板、原生 CSS、原生 JavaScript、Chart.js
- 定时任务：APScheduler
- 交易终端：MT4 CSV/MQL4 推送、MT5 官方 Python API

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/zhaojunshan3201/trade-fupan.git
cd trade-fupan
```

### 2. 创建虚拟环境

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

如果只使用网页、CSV 导入和基础复盘功能，可以不启动 MT4/MT5 终端；如果要使用 MT5 直连导入，需要 Windows 环境、已安装 MT5 终端，并确保 `MetaTrader5` Python 包可用。

### 4. 启动系统

```bash
python app.py
```

浏览器打开：

```text
http://127.0.0.1:5000
```

### 5. 创建账号

首次注册的用户会自动成为管理员。后续注册用户默认为普通用户。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SECRET_KEY` | `change-me-in-production-!!` | Flask 会话密钥，生产环境必须修改 |
| `DATABASE_URL` | `sqlite:///trade_journal.db` | 数据库连接地址 |
| `AUTO_SYNC_ENABLED` | `true` | 是否启用后台自动同步 |
| `AUTO_SYNC_INTERVAL` | `60` | 自动同步间隔，单位分钟 |
| `AUTO_SYNC_STARTUP` | `true` | 启动时是否立即执行一次同步 |

示例：

```powershell
$env:SECRET_KEY="replace-with-a-random-secret"
$env:DATABASE_URL="sqlite:///trade_journal.db"
$env:AUTO_SYNC_ENABLED="false"
python app.py
```

## 常见使用流程

### CSV 导入交易记录

1. 登录系统
2. 进入“数据导入”
3. 上传 MT4 导出的 CSV 文件
4. 进入“交易记录”查看导入结果
5. 对未复盘订单进行结构化复盘
6. 在“统计分析”查看资金曲线、品种表现、方向表现和复盘洞察

### 使用 API Token 推送数据

1. 登录系统
2. 进入“账户管理”
3. 生成 API Token
4. 配置 `client/mt4_push.py` 或 `client/mt5_push.py`
5. 通过客户端脚本把交易记录推送到系统

注意：`client/config.ini` 是本地连接配置文件，已被 `.gitignore` 排除，不会提交到仓库。

### MT5 直连

MT5 相关功能依赖本机环境：

- Windows 系统
- 已安装并登录 MetaTrader 5 终端
- Python 环境中安装 `MetaTrader5`
- 终端中已加载对应品种的历史数据

如果 MT5 未运行或未登录，系统接口会返回连接失败或无数据提示。

## 测试

项目包含基础回归测试，覆盖首页渲染、用户数据隔离、计划隔离、复盘权限、分析统计和 CSV Token 导入。

```bash
python -m pytest tests\test_homepage_render.py tests\test_user_isolation.py -q
```

编译检查：

```bash
python -m compileall -q app.py models.py routes
```

## 项目结构

```text
trade-journal/
├── app.py                  # Flask 应用入口
├── config.py               # 配置项
├── models.py               # 数据模型
├── requirements.txt        # Python 依赖
├── routes/                 # Flask 路由模块
│   ├── main.py             # 首页和个人仪表盘
│   ├── auth.py             # 注册、登录、个人资料
│   ├── orders.py           # 交易记录
│   ├── review.py           # 交易复盘
│   ├── analysis.py         # 数据分析
│   ├── plans.py            # 交易计划
│   ├── import_data.py      # 数据导入和推送接口
│   ├── accounts.py         # 平台和账户管理
│   ├── admin.py            # 管理后台
│   └── scheduler.py        # 后台自动同步
├── templates/              # Jinja2 页面模板
├── static/                 # CSS 和 JavaScript
├── client/                 # 本地推送客户端
├── mt4_connect/            # MT4 连接辅助脚本
├── mt4_export/             # MT4 导出脚本和说明
├── mt5_connect/            # MT5 连接脚本
├── tests/                  # 自动化测试
└── docs/                   # 项目设计和实施文档
```

## 数据与安全说明

- 默认数据库文件为 `trade_journal.db`，仅保存在本地运行目录
- `trade_journal.db`、上传文件、缓存目录和本地连接配置已被 `.gitignore` 排除
- 生产环境必须设置强随机 `SECRET_KEY`
- 不建议把真实交易账号密码写入仓库或明文配置文件
- 公开主页只展示标记为公开的计划和复盘内容

## 当前状态

已验证的核心能力：

- 用户注册、登录、退出
- 首页、仪表盘、订单、复盘、计划、分析、导入、账户、后台管理页面
- 订单、复盘、计划、分析、账户和管理后台主要 API
- CSV 导入和 MQL4 推送
- 用户数据隔离和权限校验

外部依赖能力：

- MT4 自动推送依赖本机 MT4 脚本或 CSV 导出
- MT5 连接、历史成交导入和 K 线快照依赖本机 MT5 终端、登录账户和历史数据
