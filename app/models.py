from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, UniqueConstraint, event, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.schema import CreateSchema


class Base(DeclarativeBase):
    pass


event.listen(
    Base.metadata,
    "before_create",
    CreateSchema("database_connection", if_not_exists=True).execute_if(
        dialect="postgresql"
    ),
)


class URL(Base):
    __tablename__ = "urls"
    __table_args__ = (
        UniqueConstraint("short_code", name="uq_urls_short_code"),
        {"schema": "database_connection"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    short_code: Mapped[str] = mapped_column(String(16), nullable=False)
    long_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=func.now()
    )
