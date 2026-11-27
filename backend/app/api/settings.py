from fastapi import APIRouter
from pydantic import BaseModel

from app.notify.telegram import send_test
from app.services.maintenance import update_ytdlp

router = APIRouter(prefix="/settings")


@router.post("/telegram/test", status_code=204)
async def telegram_test() -> None:
    await send_test()


class Message(BaseModel):
    message: str


@router.post("/ytdlp/update")
async def ytdlp_update() -> Message:
    return Message(message=await update_ytdlp())
