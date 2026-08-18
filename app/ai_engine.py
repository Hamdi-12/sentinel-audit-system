"""
Sentinel AI Engine
Full forensic intelligence powered by Claude (Anthropic).
Handles: flag analysis, batch reports, downloadable AI reports, chat.
"""
import json, urllib.request, urllib.error, os, ssl


# ── SSL context (fixes Mac certificate issue) ─────────────────────────────
def _ssl():
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ── Core API call ─────────────────────────────────────────────────────────
def _claude(prompt, system=None, max_tokens=1500):
    key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not key:
        return None, 'ANTHROPIC_API_KEY not set in .env file.'

    body = {'model': 'claude-sonnet-4-6', 'max_tokens': max_tokens,
            'messages': [{'role': 'user', 'content': prompt}]}
    if system:
        body['system'] = system

    try:
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=json.dumps(body).encode(),
            headers={'Content-Type': 'application/json',
                     'anthropic-version': '2023-06-01',
                     'x-api-key': key},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=30, context=_ssl()) as resp:
            return json.loads(resp.read())['content'][0]['text'], None
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get('error', {}).get('message', str(e))
        except Exception:
            msg = str(e)
        return None, f'API error: {msg}'
    except Exception as e:
        return None, f'Connection error: {e}'


# ── 1. Single flag forensic analysis ─────────────────────────────────────
def analyse_flag(flag, tx):
    """Deep forensic analysis for one flagged transaction."""
    prompt = f"""You are a senior forensic auditor with 20 years of experience in financial crime investigation. 
Conduct a thorough forensic analysis of this flagged transaction.

TRANSACTION:
ID: #{tx.id} | Date: {tx.date} | Payee: {tx.payee}
Amount: KES {float(tx.amount):,.2f} | Department: {tx.department or 'Not specified'}
Type: {tx.transaction_type or 'Not specified'} | Reference: {tx.reference_no or 'Not specified'}
Description: {tx.description or 'Not specified'}

ANOMALY DETECTED:
Rule: {flag.rule_triggered} | Severity: {flag.severity.upper()}
Detection note: {flag.description}

Write a comprehensive forensic analysis using EXACTLY this structure:

RISK ASSESSMENT
Risk Level: [CRITICAL / HIGH / MEDIUM / LOW]
Risk Score: [X/10]
Summary: [2-3 sentences on the overall risk]

WHY THIS IS SUSPICIOUS
[3-4 sentences explaining specific red flags and forensic indicators. Reference established financial crime typologies.]

POSSIBLE FRAUD SCHEME
Primary Scheme: [Specific fraud type e.g. duplicate billing, ghost vendor, embezzlement]
Secondary Risk: [Any secondary concern]
Explanation: [2-3 sentences on how this fits the fraud pattern]

FORENSIC EVIDENCE POINTS
1. [Specific evidence from the data]
2. [Specific evidence from the data]
3. [Specific evidence from the data]

RECOMMENDED INVESTIGATIVE ACTIONS
Immediate (within 24 hours):
1. [Specific action]
2. [Specific action]

Short-term (within 1 week):
1. [Specific action]
2. [Specific action]

REGULATORY IMPLICATIONS
[2 sentences on compliance/legal implications under Kenyan financial regulations or IFAC audit standards]"""

    result, err = _claude(prompt, max_tokens=1000)
    return result if result else f'Analysis unavailable: {err}'


# ── 2. Batch intelligence report ──────────────────────────────────────────
def analyse_batch(transactions, flags):
    """Executive AI audit intelligence report for an uploaded batch."""
    if not transactions:
        return None

    total_amount = sum(float(t.amount) for t in transactions)
    high   = sum(1 for f in flags if f['severity'] == 'high')
    medium = sum(1 for f in flags if f['severity'] == 'medium')
    low    = sum(1 for f in flags if f['severity'] == 'low')

    dept_totals = {}
    for t in transactions:
        d = t.department or 'Unknown'
        dept_totals[d] = dept_totals.get(d, 0) + float(t.amount)

    flag_lines = []
    for f in flags:
        tx = next((t for t in transactions if t.id == f['transaction_id']), None)
        if tx:
            flag_lines.append(
                f"- {f['rule_triggered']} | {f['severity'].upper()} | "
                f"{tx.payee} | KES {float(tx.amount):,.2f} | {tx.department or 'N/A'}"
            )

    dept_lines = [f"  {d}: KES {v:,.2f}" for d, v in
                  sorted(dept_totals.items(), key=lambda x: -x[1])]

    prompt = f"""You are the Chief Forensic Auditor reviewing a batch of financial transactions processed by Sentinel AI.

BATCH STATISTICS:
Total Transactions: {len(transactions)}
Total Value: KES {total_amount:,.2f}
Anomalies Detected: {len(flags)} ({len(flags)/len(transactions)*100:.1f}% flagged)
Critical Flags: {high} | Medium: {medium} | Low: {low}

DEPARTMENT EXPENDITURE:
{chr(10).join(dept_lines)}

FLAGGED TRANSACTIONS:
{chr(10).join(flag_lines) if flag_lines else 'None'}

Produce a comprehensive executive audit intelligence report using EXACTLY this structure:

EXECUTIVE AUDIT INTELLIGENCE REPORT
Produced by Sentinel AI Forensic Engine

OVERALL RISK ASSESSMENT
Overall Risk Level: [CRITICAL / HIGH / MEDIUM / LOW]
Confidence: [X%]
Audit Opinion: [One professional sentence on the integrity of this transaction batch]

EXECUTIVE SUMMARY
[4-5 sentences summarizing findings, scale of irregularities, and urgency for senior management]

KEY FINDINGS
Finding 1 — [Title]: [2-3 sentences with specific amounts and payees]
Finding 2 — [Title]: [2-3 sentences with specific amounts and payees]
Finding 3 — [Title]: [2-3 sentences with specific amounts and payees]
Finding 4 — [Title]: [2-3 sentences with specific amounts and payees]

FRAUD RISK INDICATORS
[4-5 sentences analyzing patterns across all flagged transactions. Name specific fraud typologies. Reference actual amounts and payees.]

DEPARTMENTAL RISK ANALYSIS
[Identify which departments carry the highest risk. Be specific about amounts and flag concentration.]

COMPLIANCE CONCERNS
[3 sentences on regulatory and compliance implications under Kenyan financial law, IFAC standards, or relevant frameworks.]

PRIORITY INVESTIGATIVE ACTIONS
1. [Most urgent — reference specific transactions]
2. [Second priority]
3. [Third priority]
4. [Fourth priority]
5. [Fifth priority]

MANAGEMENT RECOMMENDATIONS
1. [Strategic recommendation]
2. [Process improvement]
3. [Control enhancement]
4. [Monitoring recommendation]

AUDITOR'S NOTE
[2 sentences on the role of AI in this analysis and the necessity of human auditor verification before formal action.]"""

    result, err = _claude(prompt, max_tokens=1800)
    return result if result else None


# ── 3. Chat with live database context ───────────────────────────────────
def chat(message, history, db_context):
    """Conversational AI with full live database context."""
    system = f"""You are Sentinel AI — an expert forensic auditor and financial crime analyst embedded in the Sentinel Audit Intelligence System.

You have real-time access to this organization's financial database:
{db_context}

Your role:
- Provide deep forensic analysis of transactions and anomaly patterns
- Identify fraud schemes, money laundering, and compliance violations
- Answer questions about specific transactions, departments, or risk patterns
- Give specific investigative recommendations based on actual data
- Explain audit findings clearly for both technical and non-technical users
- Reference Kenyan financial regulations, IFAC standards, and international fraud frameworks

Rules:
- Always reference actual data from the context — use real amounts, payees, transaction IDs
- Never fabricate data not in the context
- Provide thorough, detailed, structured responses
- Format with clear sections and numbered lists where helpful
- Be direct and professional — this is a forensic investigation tool"""

    messages = [{'role': h['role'], 'content': h['content']} for h in history]
    messages.append({'role': 'user', 'content': message})

    key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not key:
        return 'Sentinel AI is not configured. Please add ANTHROPIC_API_KEY to your .env file.', False

    body = {'model': 'claude-sonnet-4-6', 'max_tokens': 1500,
            'system': system, 'messages': messages}

    try:
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=json.dumps(body).encode(),
            headers={'Content-Type': 'application/json',
                     'anthropic-version': '2023-06-01',
                     'x-api-key': key},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=30, context=_ssl()) as resp:
            return json.loads(resp.read())['content'][0]['text'], True
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get('error', {}).get('message', str(e))
        except Exception:
            msg = str(e)
        return f'API Error: {msg}', False
    except Exception as e:
        return f'Connection error: {e}', False


# ── 4. Build live database context string ────────────────────────────────
def build_context(db, Transaction, Flag, Report):
    from sqlalchemy import func

    total_tx     = Transaction.query.count()
    total_flags  = Flag.query.count()
    open_flags   = Flag.query.filter_by(status='open').count()
    total_amount = db.session.query(func.sum(Transaction.amount)).scalar() or 0

    recent_tx = Transaction.query.order_by(Transaction.uploaded_at.desc()).limit(20).all()
    tx_lines  = [
        f"  #{t.id} | {t.date} | {t.payee} | KES {float(t.amount):,.2f} | "
        f"{t.department or 'N/A'} | {t.transaction_type or 'N/A'}"
        for t in recent_tx
    ]

    open_flag_list = Flag.query.filter_by(status='open').order_by(Flag.flagged_at.desc()).limit(25).all()
    flag_lines = [
        f"  Flag#{f.id} | {f.rule_triggered} | {f.severity.upper()} | "
        f"#{f.transaction.id} {f.transaction.payee} | KES {float(f.transaction.amount):,.2f} | "
        f"{f.description[:90]}"
        for f in open_flag_list
    ]

    dept_stats = db.session.query(
        Transaction.department, func.count(Transaction.id), func.sum(Transaction.amount)
    ).group_by(Transaction.department).all()
    dept_lines = [
        f"  {d or 'Unknown'}: {c} transactions, KES {float(s or 0):,.2f}"
        for d, c, s in sorted(dept_stats, key=lambda x: -(x[2] or 0))
    ]

    sev_counts = db.session.query(Flag.severity, func.count(Flag.id)).group_by(Flag.severity).all()

    return f"""
DATABASE SNAPSHOT:
Total Transactions: {total_tx} | Total Value: KES {float(total_amount):,.2f}
Total Flags: {total_flags} | Open Flags: {open_flags}
Severity: {', '.join(f'{s.upper()}: {c}' for s, c in sev_counts)}

RECENT TRANSACTIONS (last 20):
{chr(10).join(tx_lines) or '  None'}

OPEN ANOMALY FLAGS (top 25):
{chr(10).join(flag_lines) or '  None — all clear'}

DEPARTMENT BREAKDOWN:
{chr(10).join(dept_lines) or '  No data'}
"""
