from logging.config import fileConfig
import os
import sys
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add paths to sys.path to import our modules
current_dir = Path(__file__).resolve().parent
api_dir = current_dir.parent  # services/api
services_dir = api_dir.parent  # services
repo_root = services_dir.parent  # repository root

sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(api_dir))

# Import our Base and models using the repo's canonical absolute import paths.
from services.api.core.database import Base
from services.api.modules.notebooks.models import User, Notebook
from services.api.modules.sources.models import Source

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Always use a stable absolute SQLite path unless DATABASE_URL overrides it.
default_database_url = f"sqlite:///{(repo_root / 'notebooklx.db').as_posix()}"
database_url = os.getenv("DATABASE_URL", default_database_url)
config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
