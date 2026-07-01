import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    _db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/contratos_sobral")
    # Railway fornece "postgresql://..." mas SQLAlchemy 2.x exige "postgresql+psycopg2://"
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif _db_url.startswith("postgresql://"):
        _db_url = _db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PORTAL_BASE = os.getenv("PORTAL_BASE", "https://transparencia.sobral.ce.gov.br")
    REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.5"))
    REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30"))
    USER_AGENT = os.getenv(
        "USER_AGENT",
        "AcompanhamentoContratos/1.0 (uso interno SMS Sobral)",
    )
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
