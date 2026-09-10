import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


load_dotenv()

engine = create_engine(
    os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://app:app@localhost:5432/system_design",
    ),
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "0")),
    pool_timeout=float(os.getenv("DB_POOL_TIMEOUT", "2")),
    connect_args={"connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "2"))},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
