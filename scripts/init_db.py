"""Initialize the database with schema and seed data."""

from quiver.config import load_config
from quiver.db.connection import get_connection
from quiver.db.migrate import init_db


def main() -> None:
    config = load_config()
    conn = get_connection(config.database_path)
    try:
        init_db(conn)
        print(f"Database initialized at {config.database_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
