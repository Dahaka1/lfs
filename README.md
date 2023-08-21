# **LFS backend server**

## ABOUT
LFS company backed server. The project realizes administrative processes for company technologies (mechanic stations).
See the docs of the project for advanced functionality information.

## RUN IT
Fill .env-docker file (its "null"-values).
Start server by cmds:
```
docker-compose build
docker-compose up
```
... and open docs you need then: 
- [Localhost project docs](http://localhost:8080/docs)
- [redoc](http://localhost:8080/redoc)

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
- [x] Check that fastapi cache is really working;
- [ ] Optimize getting station info from all station relations (1-2 query instead of 5);
- [ ] Use Yandex geopy instead of Nominatim - **EXCLUDED** (need for commerce license);
- [ ] Add loguru errors email notifications if needed - **EXCLUDED**;
- [x] Add refresh token to authenticate;
- [ ] Refactor DB operations with queries to ORM operations, including update ORM defining to SQLAlchemy v2 (mapped columns) - **EXCLUDED**;
- [ ] Add Celery tasks handling in case of low-speed background tasks handling by FastAPI - **EXCLUDED**;
- [x] Add advanced path operations responses description (openapi);
- [x] Nginx deploying;
- [x] SSL securing;
- [ ] Think, refactor all stations methods to OOP-reasonable;
- [ ] Optimize DB-queries amount in station methods.