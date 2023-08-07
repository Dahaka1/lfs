from fastapi import FastAPI, APIRouter, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from loguru import logger

import config
from config import LOGGING_PARAMS
from . import fastapi_cache_init, check_connections
from .routers import auth, users, stations, management, logs
from .static import app_description
from .static.openapi import tags_metadata, main_responses
from .static.typing import PathOperation
from .middlewares import ProcessTimeLogMiddleware

app = FastAPI(
	title="LFS company server",
	openapi_url=config.OPENAPI_URL,
	openapi_tags=tags_metadata,
	docs_url=config.API_DOCS_URL,
	redoc_url=config.API_REDOC_URL,
	description=app_description(),
	summary="LFS stations",
	version="0.0.1",
	contact={
		"name": "Yaroslav",
		"email": "ijoech@gmail.com",
		"url": "https://t.me/Dahaka1"
	}
)

api_router = APIRouter(prefix="/v1")
for r in (auth, users, stations, management, logs):
	api_router.include_router(r.router)

app.include_router(api_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_stations_process_time(request: Request, call_next: PathOperation):
	"""
	Замер времени выполнения запроса от станции.
	"""
	station_id = request.headers.get("X-Station-Uuid")
	if station_id:
		async with ProcessTimeLogMiddleware(request, call_next, "Station", station_id) as result:
			return result
	return await call_next(request)


@app.get("/", responses=main_responses)
def main():
	return {
		"message": "Server is available."
	}


@app.on_event("startup")
async def startup():
	"""
	Действия при старте сервера.
	"""
	logger.add(**LOGGING_PARAMS)
	logger.info("Starting server...")
	await check_connections()
	await fastapi_cache_init()
	logger.info("All connections are available. Server started successfully.")


@app.on_event("shutdown")
async def shutdown():
	"""
	Действия при отключении сервера.
	"""
	logger.info("Stopping server")


@app.get("/docs")
async def docs():
	return RedirectResponse(
		url=config.API_DOCS_URL,
		status_code=status.HTTP_308_PERMANENT_REDIRECT
	)


@app.get("/redoc")
async def redoc():
	return RedirectResponse(
		url=config.API_REDOC_URL,
		status_code=status.HTTP_308_PERMANENT_REDIRECT
	)
