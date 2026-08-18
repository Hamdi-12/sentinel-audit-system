from flask import render_template, jsonify
from flask_login import login_required
from app.dashboard import dashboard
from app.models import Transaction, Flag, Report
from app import db
from sqlalchemy import func
from datetime import datetime, timedelta

@dashboard.route('/dashboard')
@login_required
def index():
    total_tx    = Transaction.query.count()
    total_flags = Flag.query.count()
    open_flags  = Flag.query.filter_by(status='open').count()
    high_flags  = Flag.query.filter_by(severity='high', status='open').count()
    total_amount = db.session.query(func.sum(Transaction.amount)).scalar() or 0

    sev_counts  = db.session.query(Flag.severity, func.count(Flag.id)).group_by(Flag.severity).all()
    severity    = {s: c for s, c in sev_counts}

    rule_counts = [[r, c] for r, c in
                   db.session.query(Flag.rule_triggered, func.count(Flag.id))
                   .group_by(Flag.rule_triggered).all()]

    recent_flags  = Flag.query.order_by(Flag.flagged_at.desc()).limit(8).all()

    seven_days    = datetime.utcnow() - timedelta(days=7)
    daily_tx      = db.session.query(func.date(Transaction.uploaded_at), func.count(Transaction.id))\
                      .filter(Transaction.uploaded_at >= seven_days)\
                      .group_by(func.date(Transaction.uploaded_at)).all()
    daily_labels  = [str(d) for d, _ in daily_tx]
    daily_values  = [c for _, c in daily_tx]

    recent_reports = Report.query.order_by(Report.report_date.desc()).limit(5).all()

    return render_template('dashboard/index.html',
        total_tx=total_tx, total_flags=total_flags,
        open_flags=open_flags, high_flags=high_flags,
        total_amount=total_amount, severity=severity,
        rule_counts=rule_counts, recent_flags=recent_flags,
        daily_labels=daily_labels, daily_values=daily_values,
        recent_reports=recent_reports)

@dashboard.route('/dashboard/api/stats')
@login_required
def api_stats():
    return jsonify(
        total_tx    = Transaction.query.count(),
        total_flags = Flag.query.count(),
        open_flags  = Flag.query.filter_by(status='open').count(),
        high_flags  = Flag.query.filter_by(severity='high', status='open').count(),
    )
