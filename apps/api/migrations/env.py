from logging.config import fileConfig

from alembic import context

from slidemind_api import models  # noqa: F401
from slidemind_api.config import Settings
from slidemind_api.db import Base, create_database

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

settings = Settings()
target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine, _ = create_database(settings.database_url)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=engine.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
