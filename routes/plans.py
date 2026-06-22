"""交易计划路由"""
from datetime import date, datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, TradingPlan

plans_bp = Blueprint('plans', __name__)


def _plan_for_current_user(plan_id):
    query = TradingPlan.query.filter_by(id=plan_id)
    if not current_user.is_admin:
        query = query.filter_by(user_id=current_user.id)
    return query.first_or_404()


@plans_bp.route('/')
@login_required
def plan_list():
    """交易计划列表"""
    status = request.args.get('status', '')
    symbol = request.args.get('symbol', '')

    uid = current_user.id
    query = TradingPlan.query.filter_by(user_id=uid)
    if status:
        query = query.filter(TradingPlan.status == status)
    if symbol:
        query = query.filter(TradingPlan.symbol == symbol)

    plans = query.order_by(TradingPlan.plan_date.desc(), TradingPlan.created_at.desc()).all()

    symbols = [r[0] for r in db.session.query(TradingPlan.symbol).filter_by(user_id=uid).distinct().all()]

    return render_template('plans.html', plans=plans, symbols=symbols,
                          current_status=status, current_symbol=symbol)


@plans_bp.route('/create', methods=['GET', 'POST'])
@login_required
def plan_create():
    """创建交易计划"""
    if request.method == 'POST':
        data = request.form
        plan = TradingPlan(
            user_id=current_user.id,
            title=data.get('title'),
            symbol=data.get('symbol'),
            direction=data.get('direction'),
            fundamental_analysis=data.get('fundamental_analysis', ''),
            technical_analysis=data.get('technical_analysis', ''),
            entry_reason=data.get('entry_reason', ''),
            entry_condition=data.get('entry_condition', ''),
            exit_condition=data.get('exit_condition', ''),
            planned_entry=float(data['planned_entry']) if data.get('planned_entry') else None,
            planned_sl=float(data['planned_sl']) if data.get('planned_sl') else None,
            planned_tp1=float(data['planned_tp1']) if data.get('planned_tp1') else None,
            planned_tp2=float(data['planned_tp2']) if data.get('planned_tp2') else None,
            risk_percent=float(data['risk_percent']) if data.get('risk_percent') else None,
            status='planned',
            priority=data.get('priority', 'medium'),
            plan_date=datetime.strptime(data['plan_date'], '%Y-%m-%d').date() if data.get('plan_date') else date.today(),
            target_date=datetime.strptime(data['target_date'], '%Y-%m-%d').date() if data.get('target_date') else None,
        )
        db.session.add(plan)
        db.session.commit()
        return redirect(url_for('plans.plan_list'))
    return render_template('plan_form.html', plan=None)


@plans_bp.route('/edit/<int:plan_id>', methods=['GET', 'POST'])
@login_required
def plan_edit(plan_id):
    """编辑交易计划"""
    plan = _plan_for_current_user(plan_id)
    if plan.user_id != current_user.id and not current_user.is_admin:
        flash('无权操作此计划', 'danger')
        return redirect(url_for('plans.plan_list'))
    if request.method == 'POST':
        data = request.form
        plan.title = data.get('title', plan.title)
        plan.symbol = data.get('symbol', plan.symbol)
        plan.direction = data.get('direction', plan.direction)
        plan.fundamental_analysis = data.get('fundamental_analysis', plan.fundamental_analysis)
        plan.technical_analysis = data.get('technical_analysis', plan.technical_analysis)
        plan.entry_reason = data.get('entry_reason', plan.entry_reason)
        plan.entry_condition = data.get('entry_condition', plan.entry_condition)
        plan.exit_condition = data.get('exit_condition', plan.exit_condition)
        plan.planned_entry = float(data['planned_entry']) if data.get('planned_entry') else None
        plan.planned_sl = float(data['planned_sl']) if data.get('planned_sl') else None
        plan.planned_tp1 = float(data['planned_tp1']) if data.get('planned_tp1') else None
        plan.planned_tp2 = float(data['planned_tp2']) if data.get('planned_tp2') else None
        plan.risk_percent = float(data['risk_percent']) if data.get('risk_percent') else None
        plan.status = data.get('status', plan.status)
        plan.priority = data.get('priority', plan.priority)
        plan.plan_date = datetime.strptime(data['plan_date'], '%Y-%m-%d').date() if data.get('plan_date') else plan.plan_date
        plan.target_date = datetime.strptime(data['target_date'], '%Y-%m-%d').date() if data.get('target_date') else plan.target_date
        db.session.commit()
        return redirect(url_for('plans.plan_list'))
    return render_template('plan_form.html', plan=plan)


@plans_bp.route('/execution/<int:plan_id>', methods=['GET', 'POST'])
@login_required
def plan_execution(plan_id):
    """记录执行情况"""
    plan = _plan_for_current_user(plan_id)
    if plan.user_id != current_user.id and not current_user.is_admin:
        flash('无权操作此计划', 'danger')
        return redirect(url_for('plans.plan_list'))
    if request.method == 'POST':
        data = request.form
        plan.actual_entry = float(data['actual_entry']) if data.get('actual_entry') else None
        plan.actual_exit = float(data['actual_exit']) if data.get('actual_exit') else None
        plan.actual_volume = float(data['actual_volume']) if data.get('actual_volume') else None
        plan.actual_profit = float(data['actual_profit']) if data.get('actual_profit') else None
        plan.execution_score = int(data['execution_score']) if data.get('execution_score') else None
        plan.review_notes = data.get('review_notes', plan.review_notes)
        plan.related_order_ticket = int(data['related_order_ticket']) if data.get('related_order_ticket') else None

        if data.get('actual_entry_time'):
            plan.actual_entry_time = datetime.strptime(data['actual_entry_time'], '%Y-%m-%d %H:%M')
        if data.get('actual_exit_time'):
            plan.actual_exit_time = datetime.strptime(data['actual_exit_time'], '%Y-%m-%d %H:%M')

        # 自动更新状态
        if data.get('status'):
            plan.status = data['status']

        db.session.commit()
        return redirect(url_for('plans.plan_list'))
    return render_template('plan_execution.html', plan=plan)


@plans_bp.route('/api/list')
@login_required
def api_plan_list():
    """API: 计划列表"""
    plans = TradingPlan.query.filter_by(user_id=current_user.id).order_by(TradingPlan.plan_date.desc()).all()
    return jsonify([p.to_dict() for p in plans])


@plans_bp.route('/api/update_status/<int:plan_id>', methods=['POST'])
@login_required
def api_update_status(plan_id):
    """API: 更新计划状态"""
    plan = _plan_for_current_user(plan_id)
    data = request.json
    plan.status = data.get('status', plan.status)
    db.session.commit()
    return jsonify({'status': 'ok'})


@plans_bp.route('/delete/<int:plan_id>', methods=['POST'])
@login_required
def plan_delete(plan_id):
    """删除计划"""
    plan = _plan_for_current_user(plan_id)
    db.session.delete(plan)
    db.session.commit()
    return redirect(url_for('plans.plan_list'))
