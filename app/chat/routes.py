from flask import render_template, request, jsonify
from flask_login import login_required
from app.chat import chat
from app.models import Transaction, Flag, Report
from app import db
from app.ai_engine import chat as ai_chat, build_context

@chat.route('/')
@login_required
def index():
    return render_template('chat/index.html')

@chat.route('/message', methods=['POST'])
@login_required
def message():
    data    = request.get_json()
    msg     = data.get('message','').strip()
    history = data.get('history', [])
    if not msg:
        return jsonify(response='Please enter a message.', success=False)
    ctx      = build_context(db, Transaction, Flag, Report)
    response, success = ai_chat(msg, history, ctx)
    return jsonify(response=response, success=success)
