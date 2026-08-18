from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from app.auth import auth
from app.models import User, AuditLog
from app import db

def _log(action, detail=''):
    db.session.add(AuditLog(
        user_id=current_user.id if not current_user.is_anonymous else None,
        action=action, detail=detail, ip_address=request.remote_addr
    ))
    db.session.commit()

@auth.route('/')
def index():
    return redirect(url_for('dashboard.index') if current_user.is_authenticated else url_for('auth.login'))

@auth.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        user = User.query.filter_by(username=username).first()
        if user and user.is_active and user.check_password(password):
            login_user(user, remember=bool(request.form.get('remember')))
            _log('LOGIN', f'{username} authenticated from {request.remote_addr}')
            return redirect(request.args.get('next') or url_for('dashboard.index'))
        flash('Invalid username or password.', 'danger')
    return render_template('auth/login.html')

@auth.route('/logout')
@login_required
def logout():
    _log('LOGOUT')
    logout_user()
    return redirect(url_for('auth.login'))

@auth.route('/register', methods=['GET','POST'])
def register():
    if current_user.is_authenticated and not current_user.is_admin:
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        username  = request.form.get('username','').strip()
        email     = request.form.get('email','').strip()
        full_name = request.form.get('full_name','').strip()
        password  = request.form.get('password','')
        password2 = request.form.get('password2','')
        errors = []
        if len(username) < 3:              errors.append('Username must be at least 3 characters.')
        if User.query.filter_by(username=username).first(): errors.append('Username already taken.')
        if User.query.filter_by(email=email).first():       errors.append('Email already registered.')
        if password != password2:          errors.append('Passwords do not match.')
        if len(password) < 8:              errors.append('Password must be at least 8 characters.')
        if errors:
            [flash(e,'danger') for e in errors]
        else:
            role = 'auditor'
            if current_user.is_authenticated and current_user.is_admin:
                role = request.form.get('role','auditor')
            db.session.add(User(username=username, email=email, full_name=full_name,
                                password_hash=generate_password_hash(password), role=role))
            db.session.commit()
            flash('Account created. You can now sign in.', 'success')
            return redirect(url_for('admin.users') if (current_user.is_authenticated and current_user.is_admin) else url_for('auth.login'))
    return render_template('auth/register.html')

@auth.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name','').strip()
        current_user.email     = request.form.get('email','').strip()
        pw = request.form.get('new_password','')
        if pw:
            if pw != request.form.get('new_password2',''):
                flash('Passwords do not match.','danger')
                return redirect(url_for('auth.profile'))
            if len(pw) < 8:
                flash('Password must be at least 8 characters.','danger')
                return redirect(url_for('auth.profile'))
            current_user.set_password(pw)
        db.session.commit()
        _log('PROFILE_UPDATE')
        flash('Profile updated.','success')
    return render_template('auth/profile.html')
