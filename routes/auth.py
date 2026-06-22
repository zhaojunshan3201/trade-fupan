"""用户认证路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if not user.is_active:
                flash('账户已被禁用，请联系管理员', 'danger')
                return render_template('login.html')
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash(f'欢迎回来，{user.username}！', 'success')
            return redirect(next_page or url_for('main.index'))
        else:
            flash('用户名或密码错误', 'danger')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        # 验证
        errors = []
        if len(username) < 3 or len(username) > 50:
            errors.append('用户名需要 3-50 个字符')
        if User.query.filter_by(username=username).first():
            errors.append('用户名已被占用')
        if email and User.query.filter_by(email=email).first():
            errors.append('邮箱已被注册')
        if len(password) < 6:
            errors.append('密码至少 6 位')
        if password != password2:
            errors.append('两次密码不一致')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('register.html')

        user = User(username=username, email=email or None)
        user.set_password(password)
        # 第一个注册的用户为管理员
        if User.query.count() == 0:
            user.role = 'admin'
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f'注册成功！欢迎 {username}', 'success')
        return redirect(url_for('main.index'))

    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """退出登录"""
    logout_user()
    flash('已退出登录', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
@login_required
def profile():
    """个人资料"""
    return render_template('profile.html')
