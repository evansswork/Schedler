"""Telegram Bot API sendMessage (see the platform-apis skill)."""

import asyncio
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import DomainError

API = "https://api.telegram.org"
TIMEOUT_S = 20
MAX_LEN = 4096  # Telegram's message limit
sleep = asyncio.sleep  # tests replace this


class TelegramError(Exception):
    def __init__(self, human: str, raw: dict[str, Any]) -> None:
        super().__init__(human)
        self.human = human
        self.raw = raw


def configured() -> bool:
    s = get_settings()
    return bool(s.telegram_bot_token and s.telegram_chat_id)


async def send(text: str) -> None:
    """Send one HTML message; waits once on 429 (retry_after) before giving up."""
    s = get_settings()
    url = f"{API}/bot{s.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": s.telegram_chat_id,
        "text": text[:MAX_LEN],
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as http:
        for attempt in range(2):
            try:
                res = await http.post(url, json=payload)
            except httpx.TransportError as exc:
                raise TelegramError("Telegram nggak bisa dihubungi.", {"error": repr(exc)}) from exc
            try:
                body = res.json()
            except ValueError:
                body = {"raw": res.text[:300]}
            if res.is_success and body.get("ok"):
                return
            retry_after = (body.get("parameters") or {}).get("retry_after")
            if res.status_code == 429 and retry_after and attempt == 0:
                await sleep(min(int(retry_after), 30))
                continue
            raise TelegramError(_human(res.status_code, body), body)


def _human(status: int, body: dict[str, Any]) -> str:
    description = str(body.get("description", ""))
    if status == 401:
        return "Token bot Telegram salah. Cek TELEGRAM_BOT_TOKEN di .env."
    if "chat not found" in description.lower():
        return "Chat Telegram nggak ditemukan. Cek TELEGRAM_CHAT_ID dan kirim /start ke bot dulu."
    if status == 403:
        return "Bot Telegram diblokir atau belum di-/start. Buka bot-nya dan kirim /start."
    return f"Telegram menolak pesan: {description or status}"


async def send_test() -> None:
    if not configured():
        raise DomainError(
            "telegram_not_configured",
            "Isi TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID di .env, lalu restart backend.",
            status_code=409,
        )
    try:
        await send("✅ Tes dari Schedler. Notifikasi Telegram sudah jalan.")
    except TelegramError as err:
        raise DomainError("telegram_failed", err.human, status_code=502, detail=err.raw) from err
