from flask import Blueprint
transactions = Blueprint("transactions", __name__)
from app.transactions import routes
