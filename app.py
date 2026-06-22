"""交易复盘系统 - 主入口"""
import os
from flask import Flask
from config import Config
from models import db, login_manager

os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '请先登录'
    login_manager.login_message_category = 'warning'

    from routes.orders import orders_bp
    from routes.review import review_bp
    from routes.analysis import analysis_bp
    from routes.plans import plans_bp
    from routes.import_data import import_bp
    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.accounts import accounts_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(orders_bp, url_prefix='/orders')
    app.register_blueprint(review_bp, url_prefix='/review')
    app.register_blueprint(analysis_bp, url_prefix='/analysis')
    app.register_blueprint(plans_bp, url_prefix='/plans')
    app.register_blueprint(import_bp, url_prefix='/import')
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(accounts_bp)

    with app.app_context():
        db.create_all()

    # 启动后台自动同步
    from routes.scheduler import init_scheduler
    init_scheduler(app)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=False)
