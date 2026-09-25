import os
import secrets
import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger("gateway.database")

POSTGRES_USER = os.getenv("POSTGRES_USER", "llm_admin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "PostgresSecurePassword2026!")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres-service")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "token_portal")

DATABASE_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_database_and_seed():
    """Create all tables and seed initial users, balances (100k tokens), and API keys."""
    from models import User, UserBalance, ApiKey, SystemSetting

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. Ensure system settings exist
        quota_setting = db.query(SystemSetting).filter_by(key="default_monthly_quota").first()
        if not quota_setting:
            quota_setting = SystemSetting(
                key="default_monthly_quota",
                value="100000",
                updated_at=datetime.now(timezone.utc)
            )
            db.add(quota_setting)

        # 2. Seed initial users (1 Admin + 3 Users)
        seed_users = [
            {"username": "admin", "email": "admin@example.com", "role": "admin", "default_key": "sk-admin-master-key-2026"},
            {"username": "user1", "email": "user1@example.com", "role": "user", "default_key": "sk-user1-secret-key-2026"},
            {"username": "user2", "email": "user2@example.com", "role": "user", "default_key": "sk-user2-secret-key-2026"},
            {"username": "user3", "email": "user3@example.com", "role": "user", "default_key": "sk-user3-secret-key-2026"}
        ]

        for u in seed_users:
            user = db.query(User).filter_by(username=u["username"]).first()
            if not user:
                user = User(
                    username=u["username"],
                    email=u["email"],
                    role=u["role"],
                    created_at=datetime.now(timezone.utc)
                )
                db.add(user)
                db.flush()

            # Ensure Balance (100,000 tokens)
            balance = db.query(UserBalance).filter_by(user_id=user.id).first()
            if not balance:
                balance = UserBalance(
                    user_id=user.id,
                    remaining_tokens=100000,
                    monthly_quota=100000,
                    total_consumed=0,
                    last_reset_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db.add(balance)

            # Ensure API Key
            api_key = db.query(ApiKey).filter_by(user_id=user.id, is_active=True).first()
            if not api_key:
                raw_key = u["default_key"]
                api_key = ApiKey(
                    user_id=user.id,
                    api_key=raw_key,
                    name=f"Default {u['username'].capitalize()} Key",
                    is_active=True,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(api_key)

        db.commit()
        logger.info("Database schema initialized and seed users provisioned with 100,000 tokens each.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error during database initialization: {e}")
    finally:
        db.close()
