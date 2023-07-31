from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter(
	prefix="/",
	tags=["main_page"],
	default_response_class=HTMLResponse
)


@router.get("")
async def main():
	pass
