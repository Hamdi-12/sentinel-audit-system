"""
Sentinel Rule-Based Anomaly Detection Engine
Pure Python — no pandas dependency.
"""
from datetime import timedelta
from flask import current_app


def run(transactions):
    if not transactions:
        return []
    flags = []
    flags += _threshold(transactions)
    flags += _duplicate(transactions)
    flags += _frequency(transactions)
    flags += _off_hours(transactions)
    return flags


def _threshold(txs):
    limit = current_app.config['AMOUNT_THRESHOLD']
    return [
        {'transaction_id': tx.id, 'rule_triggered': 'High-Value Transaction',
         'severity': 'high',
         'description': f'Amount KES {float(tx.amount):,.2f} exceeds the threshold of KES {limit:,.2f}. '
                        f'Large single payments are a primary indicator of unauthorized fund transfers or embezzlement.'}
        for tx in txs if float(tx.amount) > limit
    ]


def _duplicate(txs):
    window = current_app.config['DUPLICATE_WINDOW_HOURS']
    results = []
    sorted_txs = sorted(txs, key=lambda t: t.uploaded_at)
    for i, tx in enumerate(sorted_txs):
        payee  = str(tx.payee).strip().lower()
        amount = float(tx.amount)
        wstart = tx.uploaded_at - timedelta(hours=window)
        for prev in sorted_txs[:i]:
            if (str(prev.payee).strip().lower() == payee and
                    float(prev.amount) == amount and
                    prev.uploaded_at >= wstart):
                results.append({
                    'transaction_id': tx.id,
                    'rule_triggered': 'Duplicate Entry',
                    'severity': 'high',
                    'description': f'Possible duplicate of transaction #{prev.id}: '
                                   f'same payee "{tx.payee}" and amount KES {amount:,.2f} '
                                   f'within {window}h. Duplicate payments are a common embezzlement vector.'
                })
                break
    return results


def _frequency(txs):
    limit  = current_app.config['FREQUENCY_LIMIT']
    window = current_app.config['DUPLICATE_WINDOW_HOURS']
    results = []
    by_dept = {}
    for tx in txs:
        dept = str(tx.department or '').strip().lower()
        if dept:
            by_dept.setdefault(dept, []).append(tx)
    for dept, group in by_dept.items():
        group = sorted(group, key=lambda t: t.uploaded_at)
        for tx in group:
            wstart = tx.uploaded_at - timedelta(hours=window)
            count  = sum(1 for t in group if wstart <= t.uploaded_at <= tx.uploaded_at)
            if count > limit:
                results.append({
                    'transaction_id': tx.id,
                    'rule_triggered': 'High Frequency',
                    'severity': 'medium',
                    'description': f'Department "{dept}" submitted {count} transactions within {window}h '
                                   f'(limit: {limit}). High-frequency patterns are consistent with '
                                   f'structuring (smurfing) to evade detection thresholds.'
                })
    return results


def _off_hours(txs):
    start = current_app.config['BUSINESS_HOURS_START']
    end   = current_app.config['BUSINESS_HOURS_END']
    results = []
    for tx in txs:
        hour    = tx.uploaded_at.hour
        weekday = tx.uploaded_at.weekday()
        if weekday >= 5 or hour < start or hour >= end:
            when = 'weekend' if weekday >= 5 else tx.uploaded_at.strftime('%H:%M')
            results.append({
                'transaction_id': tx.id,
                'rule_triggered': 'Off-Hours Entry',
                'severity': 'low',
                'description': f'Transaction uploaded at {when}, outside business hours '
                               f'({start:02d}:00–{end:02d}:00 Mon–Fri). '
                               f'Off-hours entries may indicate unauthorized system access.'
            })
    return results
