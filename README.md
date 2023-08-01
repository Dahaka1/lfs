# **LFS backend server**

## ABOUT
LFS company backed server. 

## BUILT-IN
- Python 3.11 + asyncio;
- FastAPI + FastAPI cache;
- SQLAlchemy;
- Pydantic;
- Alembic;
- Pytest;
- PostgreSQL;
- Redis;
- Docker, Docker Compose.

## TODO
- Check that fastapi cache is really working;
- Optimize getting station info from all station relations (1-2 query instead of 5);
- Use Yandex geopy instead of Nominatim - **EXCLUDED** (need for commerce license);
- Add loguru errors email notifications if needed - **EXCLUDED**;
- Add refresh token to authenticate - **DONE**;
- Refactor DB operations with queries to ORM operations, including update ORM defining to SQLAlchemy v2 (mapped columns) - **EXCLUDED**;
- Add Celery tasks handling in case of low-speed background tasks handling by FastAPI - **EXCLUDED**;
- Add advanced path operations responses description (openapi) - **DONE**;
- nginx deploying - **DONE**;
- ssl securing - **DONE**.