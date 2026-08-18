import os
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY          = os.environ.get('SECRET_KEY', 'sentinel-dev-secret-2024')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER       = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH  = 10 * 1024 * 1024
    ANTHROPIC_API_KEY   = os.environ.get('ANTHROPIC_API_KEY', '')

    # Detection thresholds
    AMOUNT_THRESHOLD        = 50000
    DUPLICATE_WINDOW_HOURS  = 24
    FREQUENCY_LIMIT         = 10
    BUSINESS_HOURS_START    = 8
    BUSINESS_HOURS_END      = 18

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'sentinel.db')}"

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL',
        f"sqlite:///{os.path.join(BASE_DIR, 'sentinel.db')}")

config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
