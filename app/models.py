from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name     = db.Column(db.String(120))
    role          = db.Column(db.String(20), default='auditor')
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    transactions  = db.relationship('Transaction', backref='uploader',  lazy='dynamic')
    reports       = db.relationship('Report',      backref='generator', lazy='dynamic')
    audit_logs    = db.relationship('AuditLog',    backref='actor',     lazy='dynamic')

    def set_password(self, pw):   self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)

    @property
    def is_admin(self): return self.role == 'admin'


class Transaction(db.Model):
    __tablename__    = 'transactions'
    id               = db.Column(db.Integer, primary_key=True)
    uploaded_by      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    batch_id         = db.Column(db.String(36))
    date             = db.Column(db.Date,    nullable=False)
    payee            = db.Column(db.String(200), nullable=False)
    description      = db.Column(db.String(300))
    amount           = db.Column(db.Float,   nullable=False)
    department       = db.Column(db.String(100))
    transaction_type = db.Column(db.String(50))
    reference_no     = db.Column(db.String(100))
    uploaded_at      = db.Column(db.DateTime, default=datetime.utcnow)

    flags = db.relationship('Flag', backref='transaction', lazy='dynamic',
                             cascade='all, delete-orphan')


class Flag(db.Model):
    __tablename__   = 'flags'
    id              = db.Column(db.Integer, primary_key=True)
    transaction_id  = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)
    rule_triggered  = db.Column(db.String(100), nullable=False)
    severity        = db.Column(db.String(20),  nullable=False)
    description     = db.Column(db.String(500))
    ai_analysis     = db.Column(db.Text)
    status          = db.Column(db.String(20), default='open')
    reviewed_by     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at     = db.Column(db.DateTime, nullable=True)
    flagged_at      = db.Column(db.DateTime, default=datetime.utcnow)


class Report(db.Model):
    __tablename__       = 'reports'
    id                  = db.Column(db.Integer, primary_key=True)
    generated_by        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title               = db.Column(db.String(200))
    report_date         = db.Column(db.DateTime, default=datetime.utcnow)
    total_transactions  = db.Column(db.Integer, default=0)
    total_flags         = db.Column(db.Integer, default=0)
    high_severity       = db.Column(db.Integer, default=0)
    medium_severity     = db.Column(db.Integer, default=0)
    low_severity        = db.Column(db.Integer, default=0)
    file_path           = db.Column(db.String(300))
    ai_summary          = db.Column(db.Text)


class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action      = db.Column(db.String(200), nullable=False)
    detail      = db.Column(db.String(500))
    ip_address  = db.Column(db.String(45))
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow)
