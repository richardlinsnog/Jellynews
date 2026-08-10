



import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings
from models.app_settings import AppSettings  # noqa: F401
from models.base import Base
from models.channel import Channel  # noqa: F401
from models.custom_news import CustomNews  # noqa: F401
from models.delivery_log import DeliveryLog  # noqa: F401
from models.media_log import MediaLog  # noqa: F401
from models.secret import Secret  # noqa: F401
from models.subscriber import Subscriber  # noqa: F401
from models.template import Template  # noqa: F401
from models.audit_log import AuditLog  # noqa: F401
from models.user import User  # noqa: F401

target_metadata = Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option(
    "sqlalchemy.url",
    settings.DATABASE_URL.replace("+aiosqlite", ""),
)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine

    settings.db_path.parent.mkdir(parents=True, exist_ok=True)

    connectable = create_engine(
        settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "sqlite:///"),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

        connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


