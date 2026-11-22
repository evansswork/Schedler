from logging.config import fileConfig

from sqlmodel import SQLModel

import app.models  # noqa: F401  (registers tables on SQLModel.metadata)
from alembic import context
from app.core.config import get_settings
from app.core.db import make_engine

if context.config.config_file_name and context.config.attributes.get("configure_logger", True):
    fileConfig(context.config.config_file_name)

engine = make_engine(get_settings().database_url)

with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=SQLModel.metadata,
        render_as_batch=True,  # SQLite can't ALTER most things in place
    )
    with context.begin_transaction():
        context.run_migrations()

engine.dispose()  # closes pooled connections so SQLite checkpoints the WAL into the db file
