"""Create the PostgreSQL schema and tables with python -m app.init_db."""

from app.database import engine
from app.models import Base


def main() -> None:
    Base.metadata.create_all(engine)
    print("Database schema and tables are ready.")


if __name__ == "__main__":
    main()
