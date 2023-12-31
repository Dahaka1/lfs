from psycopg2 import connect
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

import config

SQLALCHEMY_DATABASE_URL = config.DATABASE_URL

try:
    engine = create_async_engine(
        SQLALCHEMY_DATABASE_URL
    )
    sync_engine = create_engine(config.DATABASE_URL_SYNC)
except ValueError:
    raise RuntimeError("Apparently, virtual environment variables wasn't successfully imported.\n\n"
                       "If you use non-debug mode, check Docker-Compose configuration for environment-file reading.")

async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
SyncSession = sessionmaker(sync_engine)

Base = declarative_base()

# db connection instance (sync mode, using while starting app)
sync_db = connect(
    **config.DB_PARAMS
)
