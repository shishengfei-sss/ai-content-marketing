import uuid as uuid_lib

from sqlalchemy import String, cast, create_engine, or_
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def uuid_eq(column, value: uuid_lib.UUID):
    """SQLite UUID 列可能是带连字符或 32 位 hex，需两种格式都匹配。"""
    col = cast(column, String)
    return or_(col == str(value), col == value.hex)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
