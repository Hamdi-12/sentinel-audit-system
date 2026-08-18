from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import config
import os

db           = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view         = 'auth.login'
login_manager.login_message      = 'Please sign in to continue.'
login_manager.login_message_category = 'warning'

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from app.auth         import auth         as auth_bp
    from app.dashboard    import dashboard    as dash_bp
    from app.transactions import transactions as tx_bp
    from app.reports      import reports      as rep_bp
    from app.admin        import admin        as adm_bp
    from app.chat         import chat         as chat_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dash_bp)
    app.register_blueprint(tx_bp,   url_prefix='/transactions')
    app.register_blueprint(rep_bp,  url_prefix='/reports')
    app.register_blueprint(adm_bp,  url_prefix='/admin')
    app.register_blueprint(chat_bp, url_prefix='/chat')

    with app.app_context():
        db.create_all()
        _seed_admin()

    return app

def _seed_admin():
    from app.models import User
    from werkzeug.security import generate_password_hash
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(
            username='admin', email='admin@sentinel.local',
            password_hash=generate_password_hash('Admin@1234'),
            role='admin', full_name='System Administrator'
        ))
        db.session.commit()
        print('[Sentinel] Default admin created — username: admin  password: Admin@1234')
