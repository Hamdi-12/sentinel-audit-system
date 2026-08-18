import os
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT

from app.reports import reports
from app.models import Transaction, Flag, Report, AuditLog
from app import db
from app.ai_engine import analyse_batch, analyse_flag


def _log(action, detail=''):
    db.session.add(AuditLog(user_id=current_user.id, action=action,
                            detail=detail, ip_address=request.remote_addr))
    db.session.commit()


@reports.route('/')
@login_required
def list_all():
    page       = request.args.get('page', 1, type=int)
    pagination = Report.query.order_by(Report.report_date.desc()).paginate(
        page=page, per_page=15, error_out=False)
    return render_template('reports/list.html',
                           pagination=pagination, reports=pagination.items)


@reports.route('/generate', methods=['GET', 'POST'])
@login_required
def generate():
    if request.method == 'POST':
        title = request.form.get('title', '').strip() or \
                f'Sentinel AI Audit Report — {datetime.utcnow().strftime("%Y-%m-%d %H:%M")}'

        date_from = request.form.get('date_from', '')
        date_to   = request.form.get('date_to', '')

        q = Transaction.query
        if date_from: q = q.filter(Transaction.date >= datetime.strptime(date_from, '%Y-%m-%d'))
        if date_to:   q = q.filter(Transaction.date <= datetime.strptime(date_to,   '%Y-%m-%d'))
        all_tx    = q.all()
        tx_ids    = [t.id for t in all_tx]
        all_flags = Flag.query.filter(Flag.transaction_id.in_(tx_ids)).all() if tx_ids else []

        high   = sum(1 for f in all_flags if f.severity == 'high')
        medium = sum(1 for f in all_flags if f.severity == 'medium')
        low    = sum(1 for f in all_flags if f.severity == 'low')

        report = Report(generated_by=current_user.id, title=title,
                        total_transactions=len(all_tx), total_flags=len(all_flags),
                        high_severity=high, medium_severity=medium, low_severity=low)
        db.session.add(report); db.session.commit()

        # AI batch analysis
        flags_dicts = [{'transaction_id': f.transaction_id, 'rule_triggered': f.rule_triggered,
                        'severity': f.severity, 'description': f.description} for f in all_flags]
        ai_batch = analyse_batch(all_tx, flags_dicts)
        report.ai_summary = ai_batch
        db.session.commit()

        # Per-flag AI analysis (top 10 by severity)
        top_flags = sorted(all_flags, key=lambda f: {'high':0,'medium':1,'low':2}.get(f.severity,3))[:10]
        flag_ai   = {}
        for f in top_flags:
            if f.ai_analysis:
                flag_ai[f.id] = f.ai_analysis
            else:
                flag_ai[f.id] = analyse_flag(f, f.transaction)

        # Generate PDF
        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
        pdf_name = f'sentinel_report_{report.id}_{datetime.utcnow().strftime("%Y%m%d%H%M%S")}.pdf'
        pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_name)
        _build_pdf(report, all_tx, all_flags, ai_batch, flag_ai, pdf_path)
        report.file_path = pdf_path
        db.session.commit()

        _log('GENERATE_REPORT', f'Report #{report.id}: {title}')
        flash(f'AI Audit Report generated successfully.', 'success')
        return redirect(url_for('reports.view', report_id=report.id))

    return render_template('reports/generate.html')


@reports.route('/<int:report_id>')
@login_required
def view(report_id):
    report = Report.query.get_or_404(report_id)
    return render_template('reports/view.html', report=report)


@reports.route('/<int:report_id>/download')
@login_required
def download(report_id):
    report = Report.query.get_or_404(report_id)
    if not report.file_path or not os.path.exists(report.file_path):
        flash('PDF not found. Please regenerate the report.', 'danger')
        return redirect(url_for('reports.list_all'))
    _log('DOWNLOAD_REPORT', f'Report #{report_id} downloaded')
    return send_file(report.file_path, as_attachment=True,
                     download_name=f'Sentinel_Audit_Report_{report_id}.pdf')


# ── PDF BUILDER ───────────────────────────────────────────────────────────
def _build_pdf(report, transactions, flags, ai_batch, flag_ai, filepath):
    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    NAVY  = colors.HexColor('#1B3A6B')
    STEEL = colors.HexColor('#2E5F9E')
    LIGHT = colors.HexColor('#EEF3FA')
    RED   = colors.HexColor('#DC2626')
    ORG   = colors.HexColor('#D97706')
    GRN   = colors.HexColor('#059669')
    GRAY  = colors.HexColor('#6B7280')
    WHITE = colors.white
    BLK   = colors.HexColor('#1A1A1A')
    AIBG  = colors.HexColor('#F0F4FB')

    def ps(name, **kw):
        base = dict(fontName='Helvetica', fontSize=10, textColor=BLK,
                    spaceAfter=4, leading=14)
        base.update(kw)
        return ParagraphStyle(name, **base)

    T   = ps('T',  fontSize=20, textColor=NAVY, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=2)
    S   = ps('S',  fontSize=11, textColor=STEEL, alignment=TA_CENTER, spaceAfter=4)
    H1  = ps('H1', fontSize=13, textColor=NAVY,  fontName='Helvetica-Bold', spaceBefore=18, spaceAfter=6)
    H2  = ps('H2', fontSize=11, textColor=STEEL, fontName='Helvetica-Bold', spaceBefore=12, spaceAfter=4)
    H3  = ps('H3', fontSize=10, textColor=NAVY,  fontName='Helvetica-Bold', spaceBefore=8,  spaceAfter=3)
    BD  = ps('BD', fontSize=9.5, alignment=TA_JUSTIFY, leading=15)
    AI  = ps('AI', fontSize=9.5, alignment=TA_JUSTIFY, leading=15,
              leftIndent=8, rightIndent=8, backColor=AIBG, borderPadding=6)
    SM  = ps('SM', fontSize=8,  textColor=GRAY)
    FT  = ps('FT', fontSize=7.5, textColor=GRAY, alignment=TA_CENTER)

    def tbl(data, widths, header_bg=NAVY):
        t = Table(data, colWidths=widths)
        style = [
            ('BACKGROUND', (0,0), (-1,0), header_bg),
            ('TEXTCOLOR',  (0,0), (-1,0), WHITE),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 8.5),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LIGHT]),
            ('GRID',       (0,0), (-1,-1), 0.4, colors.HexColor('#C5D3E8')),
            ('PADDING',    (0,0), (-1,-1), 6),
        ]
        t.setStyle(TableStyle(style))
        return t

    story = []

    # ── COVER PAGE ──
    story += [
        Spacer(1, 0.5*cm),
        Paragraph('SENTINEL AUDIT INTELLIGENCE SYSTEM', T),
        Paragraph('AI-Powered Forensic Audit & Compliance Report', S),
        HRFlowable(width='100%', thickness=3, color=NAVY),
        Spacer(1, 0.3*cm),
        Paragraph(report.title, ps('TT', fontSize=14, textColor=STEEL,
                                   fontName='Helvetica-Bold', alignment=TA_CENTER)),
        Spacer(1, 0.5*cm),
    ]

    meta = [
        ['Generated By:', report.generator.full_name or report.generator.username,
         'Report Date:', report.report_date.strftime('%Y-%m-%d %H:%M UTC')],
        ['Total Transactions:', str(report.total_transactions),
         'Total Flags Detected:', str(report.total_flags)],
        ['Critical (HIGH):', str(report.high_severity),
         'Medium / Low:', f'{report.medium_severity} / {report.low_severity}'],
        ['Fraud Rate:',
         f'{(report.total_flags/report.total_transactions*100):.1f}% of transactions flagged' if report.total_transactions else 'N/A',
         'AI Engine:', 'Claude (Anthropic) — Sentinel AI'],
    ]
    mt = Table(meta, colWidths=[4*cm, 5.5*cm, 4*cm, 4.5*cm])
    mt.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [LIGHT, WHITE]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#C5D3E8')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story += [mt, Spacer(1, 0.4*cm), HRFlowable(width='100%', thickness=1, color=STEEL), Spacer(1, 0.3*cm)]

    # ── AI EXECUTIVE REPORT ──
    if ai_batch:
        story.append(Paragraph('AI FORENSIC INTELLIGENCE REPORT', H1))
        story.append(Paragraph(
            'The following analysis was generated automatically by Sentinel AI (Claude) based on '
            'forensic examination of all transactions and detected anomalies in this batch.',
            SM))
        story.append(Spacer(1, 0.2*cm))

        current_section = None
        for line in ai_batch.split('\n'):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 0.12*cm)); continue

            if line.isupper() and len(line) > 4 and not line.startswith('KES'):
                story.append(Paragraph(line, H2))
            elif line.startswith(('Overall Risk Level:', 'Confidence:', 'Audit Opinion:')):
                story.append(Paragraph(f'<b>{line}</b>', BD))
            elif line[0:2] in ('1.','2.','3.','4.','5.','6.','7.','8.','9.') and line[2] == ' ':
                story.append(Paragraph(f'<b>{line}</b>', BD))
            elif line.startswith('Finding') and '—' in line:
                story.append(Paragraph(f'<b>{line}</b>', BD))
            else:
                story.append(Paragraph(line, AI))

        story += [Spacer(1, 0.5*cm), HRFlowable(width='100%', thickness=1, color=STEEL), Spacer(1, 0.3*cm)]

    # ── SEVERITY SUMMARY ──
    story.append(Paragraph('ANOMALY SEVERITY SUMMARY', H1))
    sev_data = [
        ['Severity', 'Count', 'Risk Level', 'Required Response'],
        ['CRITICAL — HIGH',    str(report.high_severity),   'Immediate financial risk',     'Action within 24 hours'],
        ['MEDIUM',             str(report.medium_severity), 'Moderate compliance risk',     'Review within 48 hours'],
        ['LOW',                str(report.low_severity),    'Monitoring required',           'Review within 1 week'],
        ['TOTAL FLAGS',        str(report.total_flags),     '',                              ''],
    ]
    st = Table(sev_data, colWidths=[4.5*cm, 2.5*cm, 5*cm, 6*cm])
    st.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY), ('TEXTCOLOR', (0,0), (-1,0), WHITE),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#FEE2E2')),
        ('BACKGROUND', (0,2), (-1,2), colors.HexColor('#FEF3C7')),
        ('BACKGROUND', (0,3), (-1,3), colors.HexColor('#D1FAE5')),
        ('BACKGROUND', (0,4), (-1,4), LIGHT),
        ('FONTNAME', (0,4), (-1,4), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#C5D3E8')),
        ('PADDING', (0,0), (-1,-1), 7),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
    ]))
    story += [st, Spacer(1, 0.5*cm)]

    # ── ALL FLAGGED TRANSACTIONS ──
    if flags:
        story.append(Paragraph('COMPLETE FLAGGED TRANSACTIONS LOG', H1))
        fdata = [['#', 'Date', 'Payee', 'Amount (KES)', 'Department', 'Rule Triggered', 'Severity', 'Status']]
        for f in flags:
            tx = f.transaction
            fdata.append([str(f.id), str(tx.date), tx.payee[:26],
                          f'{float(tx.amount):,.2f}', tx.department or 'N/A',
                          f.rule_triggered[:20], f.severity.upper(), f.status.capitalize()])
        ft_tbl = Table(fdata, colWidths=[1*cm, 2.2*cm, 3.5*cm, 2.8*cm, 2.5*cm, 3.2*cm, 1.8*cm, 2*cm])
        ft_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), NAVY), ('TEXTCOLOR', (0,0), (-1,0), WHITE),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LIGHT]),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#C5D3E8')),
            ('PADDING', (0,0), (-1,-1), 5), ('ALIGN', (3,0), (3,-1), 'RIGHT'),
        ]))
        story += [ft_tbl, Spacer(1, 0.5*cm)]

    # ── PER-FLAG AI FORENSIC ANALYSES ──
    if flag_ai:
        story.append(PageBreak())
        story.append(Paragraph('INDIVIDUAL FLAG FORENSIC ANALYSES', H1))
        story.append(Paragraph(
            'AI-generated forensic analysis for the highest-severity flagged transactions. '
            'Each analysis references established financial crime typologies and provides '
            'specific investigative recommendations.',
            BD))
        story.append(Spacer(1, 0.3*cm))

        ordered = sorted([f for f in flags if f.id in flag_ai],
                         key=lambda f: {'high':0,'medium':1,'low':2}.get(f.severity,3))
        for flag in ordered:
            tx = flag.transaction
            story.append(HRFlowable(width='100%', thickness=0.5, color=STEEL))
            story.append(Spacer(1, 0.2*cm))

            # Flag header
            hdr_bg = {'high': colors.HexColor('#FEE2E2'),
                      'medium': colors.HexColor('#FEF3C7'),
                      'low': colors.HexColor('#D1FAE5')}.get(flag.severity, LIGHT)
            hdr = Table([[f'Flag #{flag.id}  |  {flag.rule_triggered}',
                          f'Severity: {flag.severity.upper()}',
                          f'Status: {flag.status.capitalize()}']],
                        colWidths=[8*cm, 4*cm, 6*cm])
            hdr.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), hdr_bg),
                ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#C5D3E8')),
                ('PADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(hdr)

            # Transaction details
            txd = Table([
                ['Payee:', tx.payee, 'Date:', str(tx.date)],
                ['Amount:', f'KES {float(tx.amount):,.2f}', 'Department:', tx.department or 'N/A'],
                ['Reference:', tx.reference_no or 'N/A', 'Type:', tx.transaction_type or 'N/A'],
            ], colWidths=[2.5*cm, 6*cm, 2.5*cm, 7*cm])
            txd.setStyle(TableStyle([
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8.5),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFF')),
                ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#C5D3E8')),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            story += [txd, Spacer(1, 0.15*cm)]

            # AI analysis text
            story.append(Paragraph('AI FORENSIC ANALYSIS (Sentinel AI — Claude):', H3))
            for line in flag_ai[flag.id].split('\n'):
                line = line.strip()
                if not line:
                    story.append(Spacer(1, 0.08*cm))
                elif line.isupper() and len(line) > 3:
                    story.append(Paragraph(line, ps('AH', fontSize=9, fontName='Helvetica-Bold',
                                                     textColor=NAVY, spaceBefore=6, spaceAfter=2)))
                else:
                    story.append(Paragraph(line, ps('AL', fontSize=9, leading=13,
                                                     leftIndent=6, backColor=AIBG, borderPadding=4,
                                                     spaceAfter=2)))
            story.append(Spacer(1, 0.3*cm))

    # ── FULL TRANSACTION REGISTER ──
    story.append(PageBreak())
    story.append(Paragraph('COMPLETE TRANSACTION REGISTER', H1))
    txdata = [['#', 'Date', 'Payee', 'Amount (KES)', 'Department', 'Type', 'Reference', 'Anomaly Flags']]
    for tx in transactions:
        tx_flags = Flag.query.filter_by(transaction_id=tx.id).all()
        flag_str = '; '.join(f.rule_triggered[:14] for f in tx_flags) if tx_flags else 'Clean'
        txdata.append([str(tx.id), str(tx.date), tx.payee[:24],
                       f'{float(tx.amount):,.2f}', tx.department or 'N/A',
                       tx.transaction_type or 'N/A', tx.reference_no or 'N/A', flag_str[:22]])
    tt = Table(txdata, colWidths=[1*cm, 2.2*cm, 3.2*cm, 2.8*cm, 2.5*cm, 2.2*cm, 2.3*cm, 3*cm])
    tt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY), ('TEXTCOLOR', (0,0), (-1,0), WHITE),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LIGHT]),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#C5D3E8')),
        ('PADDING', (0,0), (-1,-1), 4), ('ALIGN', (3,0), (3,-1), 'RIGHT'),
    ]))
    story += [tt, Spacer(1, 0.8*cm)]

    # ── FOOTER ──
    story += [
        HRFlowable(width='100%', thickness=1, color=STEEL),
        Spacer(1, 0.2*cm),
        Paragraph(
            f'This report was generated by the Sentinel Audit Intelligence System on '
            f'{report.report_date.strftime("%Y-%m-%d at %H:%M UTC")}. '
            f'AI forensic analysis was produced by Claude (Anthropic) through the Sentinel AI Engine. '
            f'This document is confidential and intended for authorized audit personnel only. '
            f'All AI findings must be reviewed and verified by a qualified human auditor before formal action.',
            FT),
    ]

    doc.build(story)
