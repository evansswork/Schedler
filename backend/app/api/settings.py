from fastapi import APIRouter

from app.notify.telegram import send_test

router = APIRouter(prefix="/settings")


@router.post("/telegram/test", status_code=204)
async def telegram_test() -> None:
    await send_test()
