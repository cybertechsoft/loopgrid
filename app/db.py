from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

is_sqlite=settings.database_url.startswith("sqlite")
if is_sqlite:
    engine=create_engine(settings.database_url,connect_args={"check_same_thread":False},future=True,pool_pre_ping=True)
else:
    engine=create_engine(
        settings.database_url,
        future=True,
        pool_pre_ping=True,
        pool_size=max(1,settings.db_pool_size),
        max_overflow=max(0,settings.db_max_overflow),
        pool_recycle=max(60,settings.db_pool_recycle_seconds),
    )
SessionLocal=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()
