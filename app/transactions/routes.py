import os, uuid, csv, io
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify, Response
from flask_login import login_required, current_user
from app.transactions import transactions
from app.models import Transaction, Flag, AuditLog
from app import db
from app.detector import run
from app.ai_engine import analyse_flag, analyse_batch

def _log(action, detail=''):
    db.session.add(AuditLog(user_id=current_user.id, action=action,
                            detail=detail, ip_address=request.remote_addr))
    db.session.commit()

def _parse_date(s):
    for fmt in ('%Y-%m-%d','%d/%m/%Y','%m/%d/%Y','%d-%m-%Y'):
        try: return datetime.strptime(str(s).strip(), fmt).date()
        except ValueError: pass
    raise ValueError(f'Cannot parse date: {s}')

@transactions.route('/')
@login_required
def list_all():
    page   = request.args.get('page', 1, type=int)
    dept   = request.args.get('dept', '')
    search = request.args.get('q', '')
    query  = Transaction.query
    if dept:   query = query.filter(Transaction.department.ilike(f'%{dept}%'))
    if search: query = query.filter(
        Transaction.payee.ilike(f'%{search}%') |
        Transaction.reference_no.ilike(f'%{search}%'))
    pagination  = query.order_by(Transaction.uploaded_at.desc()).paginate(page=page, per_page=20, error_out=False)
    departments = [d[0] for d in db.session.query(Transaction.department).distinct().all() if d[0]]
    return render_template('transactions/list.html',
        pagination=pagination, transactions=pagination.items,
        departments=departments, dept=dept, search=search)

@transactions.route('/upload', methods=['GET','POST'])
@login_required
def upload():
    if request.method == 'POST':
        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
        if 'file' not in request.files or request.files['file'].filename == '':
            flash('No file selected.', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if not file.filename.lower().endswith('.csv'):
            flash('Only CSV files are supported.', 'danger')
            return redirect(request.url)
        try:
            raw    = file.read().decode('utf-8-sig', errors='replace')
            reader = csv.DictReader(io.StringIO(raw))
            rows   = [{k.strip().lower().replace(' ','_'): v for k,v in row.items()} for row in reader]
            if not rows:
                flash('File is empty.', 'danger')
                return redirect(request.url)
            missing = {'date','payee','amount'} - set(rows[0].keys())
            if missing:
                flash(f'Missing required columns: {", ".join(missing)}', 'danger')
                return redirect(request.url)

            batch_id       = str(uuid.uuid4())
            saved, skipped = 0, 0
            new_txs        = []
            for row in rows:
                try:
                    tx = Transaction(
                        uploaded_by=current_user.id, batch_id=batch_id,
                        date=_parse_date(row['date']),
                        payee=str(row['payee']).strip(),
                        amount=float(str(row['amount']).replace(',','')),
                        description=str(row.get('description') or '').strip(),
                        department=str(row.get('department') or '').strip(),
                        transaction_type=str(row.get('transaction_type') or '').strip(),
                        reference_no=str(row.get('reference_no') or '').strip(),
                    )
                    db.session.add(tx); new_txs.append(tx); saved += 1
                except Exception: skipped += 1
            db.session.commit()

            # Rule-based detection
            flags_data = run(new_txs)
            new_flags  = []
            for f in flags_data:
                flag = Flag(transaction_id=f['transaction_id'],
                            rule_triggered=f['rule_triggered'],
                            severity=f['severity'], description=f['description'])
                db.session.add(flag); new_flags.append(flag)
            db.session.commit()

            # AI batch analysis (runs automatically)
            ai_report = analyse_batch(new_txs, flags_data)

            # AI per-flag analysis (stored in DB)
            for flag in new_flags:
                tx = next((t for t in new_txs if t.id == flag.transaction_id), None)
                if tx:
                    flag.ai_analysis = analyse_flag(flag, tx)
            db.session.commit()

            _log('UPLOAD', f'{saved} transactions, {len(flags_data)} flags')
            return render_template('transactions/upload_result.html',
                saved=saved, skipped=skipped,
                high=sum(1 for f in flags_data if f['severity']=='high'),
                medium=sum(1 for f in flags_data if f['severity']=='medium'),
                low=sum(1 for f in flags_data if f['severity']=='low'),
                ai_report=ai_report, new_flags=new_flags)
        except Exception as e:
            db.session.rollback()
            flash(f'Upload failed: {e}', 'danger')
            return redirect(request.url)
    return render_template('transactions/upload.html')

@transactions.route('/manual', methods=['GET','POST'])
@login_required
def manual_entry():
    if request.method == 'POST':
        try:
            tx = Transaction(
                uploaded_by=current_user.id, batch_id=str(uuid.uuid4()),
                date=_parse_date(request.form['date']),
                payee=request.form['payee'].strip(),
                amount=float(request.form['amount']),
                description=request.form.get('description','').strip(),
                department=request.form.get('department','').strip(),
                transaction_type=request.form.get('transaction_type','').strip(),
                reference_no=request.form.get('reference_no','').strip(),
            )
            db.session.add(tx); db.session.commit()
            flags_data = run([tx])
            for f in flags_data:
                flag = Flag(transaction_id=f['transaction_id'],
                            rule_triggered=f['rule_triggered'],
                            severity=f['severity'], description=f['description'],
                            ai_analysis=analyse_flag(type('F',(),f)(), tx))
                db.session.add(flag)
            db.session.commit()
            _log('MANUAL_ENTRY', f'{tx.payee} KES {tx.amount}')
            if flags_data:
                flash(f'Transaction saved. {len(flags_data)} anomaly flag(s) detected.', 'warning')
                return redirect(url_for('transactions.flags'))
            flash('Transaction saved. No anomalies detected.', 'success')
            return redirect(url_for('transactions.list_all'))
        except Exception as e:
            db.session.rollback(); flash(f'Error: {e}', 'danger')
    return render_template('transactions/manual.html')

@transactions.route('/flags')
@login_required
def flags():
    page     = request.args.get('page', 1, type=int)
    severity = request.args.get('severity', '')
    status   = request.args.get('status', '')
    rule     = request.args.get('rule', '')
    query    = Flag.query
    if severity: query = query.filter(Flag.severity == severity)
    if status:   query = query.filter(Flag.status == status)
    if rule:     query = query.filter(Flag.rule_triggered == rule)
    pagination = query.order_by(Flag.flagged_at.desc()).paginate(page=page, per_page=20, error_out=False)
    rules = [r[0] for r in db.session.query(Flag.rule_triggered).distinct().all()]
    return render_template('transactions/flags.html',
        pagination=pagination, flags=pagination.items,
        rules=rules, severity=severity, status=status, rule=rule)

@transactions.route('/flags/<int:flag_id>/analyse')
@login_required
def analyse_flag_route(flag_id):
    flag = Flag.query.get_or_404(flag_id)
    if not flag.ai_analysis:
        flag.ai_analysis = analyse_flag(flag, flag.transaction)
        db.session.commit()
    return jsonify(analysis=flag.ai_analysis)

@transactions.route('/flags/<int:flag_id>/review', methods=['POST'])
@login_required
def review_flag(flag_id):
    flag = Flag.query.get_or_404(flag_id)
    flag.status = request.form.get('action','reviewed')
    flag.reviewed_by = current_user.id
    flag.reviewed_at = datetime.utcnow()
    db.session.commit()
    _log('FLAG_REVIEW', f'Flag {flag_id} -> {flag.status}')
    flash(f'Flag marked as {flag.status}.', 'success')
    return redirect(request.referrer or url_for('transactions.flags'))

@transactions.route('/delete/<int:tx_id>', methods=['POST'])
@login_required
def delete(tx_id):
    if not current_user.is_admin:
        flash('Administrator access required.', 'danger')
        return redirect(url_for('transactions.list_all'))
    tx = Transaction.query.get_or_404(tx_id)
    db.session.delete(tx); db.session.commit()
    _log('DELETE_TX', f'Transaction {tx_id} deleted')
    flash('Transaction deleted.', 'success')
    return redirect(url_for('transactions.list_all'))

@transactions.route('/sample-csv')
@login_required
def sample_csv():
    content = (
        "date,payee,amount,department,description,transaction_type,reference_no\n"
        "2024-01-15,Acme Supplies Ltd,12500.00,Procurement,Office supplies Q1,Payment,REF-001\n"
        "2024-01-15,City Power Kenya,3200.00,Facilities,January electricity,Utility,REF-002\n"
        "2024-01-15,Safaricom Business,8750.00,IT,Monthly internet,Utility,REF-003\n"
        "2024-01-16,Tech Solutions Ltd,85000.00,IT,Server upgrade,Service,REF-004\n"
        "2024-01-16,Acme Supplies Ltd,12500.00,Procurement,Office supplies Q1,Payment,REF-005\n"
        "2024-01-16,Ghost Vendor Ltd,95000.00,Procurement,Consultancy,Service,REF-006\n"
        "2024-01-16,Ghost Vendor Ltd,95000.00,Procurement,Consultancy,Service,REF-007\n"
        "2024-01-16,Petty Cash,500.00,Administration,Tea and coffee,Expense,REF-008\n"
        "2024-01-16,Petty Cash,500.00,Administration,Tea and coffee,Expense,REF-009\n"
        "2024-01-16,Petty Cash,500.00,Administration,Tea and coffee,Expense,REF-010\n"
        "2024-01-16,Petty Cash,500.00,Administration,Tea and coffee,Expense,REF-011\n"
        "2024-01-16,Petty Cash,500.00,Administration,Tea and coffee,Expense,REF-012\n"
        "2024-01-16,Petty Cash,500.00,Administration,Tea and coffee,Expense,REF-013\n"
        "2024-01-16,Petty Cash,500.00,Administration,Tea and coffee,Expense,REF-014\n"
        "2024-01-16,Petty Cash,500.00,Administration,Tea and coffee,Expense,REF-015\n"
        "2024-01-17,Unknown Payee,120000.00,Finance,Urgent transfer,Transfer,REF-016\n"
        "2024-01-17,Unknown Payee,120000.00,Finance,Urgent transfer,Transfer,REF-017\n"
        "2024-01-17,Kenya Revenue Authority,15000.00,Finance,PAYE remittance,Tax,REF-018\n"
        "2024-01-18,Office Rent,75000.00,Facilities,February rent advance,Rent,REF-019\n"
        "2024-01-18,Catering Services Ltd,22000.00,Administration,Board meeting,Expense,REF-020\n"
        "2024-01-18,Catering Services Ltd,22000.00,Administration,Board meeting,Expense,REF-021\n"
        "2024-01-19,Staff Salary - John Kamau,45000.00,HR,January salary,Salary,REF-022\n"
        "2024-01-19,Staff Salary - Jane Wanjiku,38000.00,HR,January salary,Salary,REF-023\n"
        "2024-01-19,Staff Salary - Peter Otieno,42000.00,HR,January salary,Salary,REF-024\n"
        "2024-01-20,Security Plus,18000.00,Facilities,Security services,Service,REF-025\n"
    )
    return Response(content, mimetype='text/csv',
                    headers={'Content-Disposition':'attachment;filename=sample_transactions.csv'})
