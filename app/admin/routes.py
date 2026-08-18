from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from functools import wraps
from app.admin import admin
from app.models import User, Transaction, Flag, Report, AuditLog
from app import db

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Administrator access required.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated

def _log(action, detail=''):
    db.session.add(AuditLog(user_id=current_user.id, action=action,
                            detail=detail, ip_address=request.remote_addr))
    db.session.commit()

@admin.route('/')
@login_required
@admin_required
def index():
    stats = dict(users=User.query.count(), transactions=Transaction.query.count(),
                 flags=Flag.query.count(), reports=Report.query.count(),
                 open_flags=Flag.query.filter_by(status='open').count())
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(20).all()
    return render_template('admin/index.html', stats=stats, recent_logs=logs)

@admin.route('/users')
@login_required
@admin_required
def users():
    return render_template('admin/users.html', users=User.query.order_by(User.created_at.desc()).all())

@admin.route('/users/create', methods=['GET','POST'])
@login_required
@admin_required
def create_user():
    if request.method == 'POST':
        username  = request.form.get('username','').strip()
        email     = request.form.get('email','').strip()
        full_name = request.form.get('full_name','').strip()
        password  = request.form.get('password','')
        role      = request.form.get('role','auditor')
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
        else:
            db.session.add(User(username=username, email=email, full_name=full_name,
                                password_hash=generate_password_hash(password), role=role))
            db.session.commit()
            _log('CREATE_USER', f'{username} ({role})')
            flash(f'User "{username}" created.', 'success')
            return redirect(url_for('admin.users'))
    return render_template('admin/create_user.html')

@admin.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('admin.users'))
    user.is_active = not user.is_active
    db.session.commit()
    state = 'activated' if user.is_active else 'deactivated'
    _log('TOGGLE_USER', f'{user.username} {state}')
    flash(f'User "{user.username}" {state}.', 'success')
    return redirect(url_for('admin.users'))

@admin.route('/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    pw   = request.form.get('new_password','')
    if len(pw) < 8:
        flash('Password must be at least 8 characters.', 'danger')
    else:
        user.set_password(pw); db.session.commit()
        _log('RESET_PASSWORD', f'{user.username}')
        flash(f'Password reset for "{user.username}".', 'success')
    return redirect(url_for('admin.users'))

@admin.route('/logs')
@login_required
@admin_required
def logs():
    page   = request.args.get('page', 1, type=int)
    action = request.args.get('action', '')
    query  = AuditLog.query
    if action: query = query.filter(AuditLog.action == action)
    pagination = query.order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=30, error_out=False)
    actions = [a[0] for a in db.session.query(AuditLog.action).distinct().all()]
    return render_template('admin/logs.html', pagination=pagination,
                           logs=pagination.items, actions=actions, action_filter=action)
