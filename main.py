import asyncio
import os
import socket
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from dotenv import load_dotenv
from loguru import logger
import aiohttp

from database import init_db, reset_daily_counts
from handlers import router

IST = ZoneInfo("Asia/Kolkata")

def load_env_or_die():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(dotenv_path=env_path)
    token = os.getenv("BOT_TOKEN")
    admin = os.getenv("ADMIN_ID")
    if not token:
        raise RuntimeError("BOT_TOKEN missing in .env")
    if not admin:
        raise RuntimeError("ADMIN_ID missing in .env")
    if not os.getenv("FREE_DAILY_LIMIT") and not os.getenv("DAILY_LIMIT"):
        os.environ["FREE_DAILY_LIMIT"] = "50"
    return token

async def midnight_reset_scheduler():
    while True:
        now = datetime.now(tz=IST)
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        sleep_secs = max(1, int((next_midnight - now).total_seconds()))
        logger.info(f"⏳ Daily reset scheduled at {next_midnight.isoformat()}")
        await asyncio.sleep(sleep_secs)
        try:
            await reset_daily_counts()
            logger.info("🔄 Daily counts reset (00:00 IST)")
        except Exception as e:
            logger.exception(f"Reset failed: {e}")

async def main():
    token = load_env_or_die()
    await init_db()

    # ✅ Force IPv4 (wrap custom aiohttp.ClientSession inside AiohttpSession)
    connector = aiohttp.TCPConnector(family=socket.AF_INET)
    client_session = aiohttp.ClientSession(connector=connector)
    bot = Bot(token=token, session=AiohttpSession(client_session))

    dp = Dispatcher()
    dp.include_router(router)

    logger.add("bot.log", rotation="5 MB", retention=5, enqueue=True)
    logger.info("🤖 ForwardXBot started")
    asyncio.create_task(midnight_reset_scheduler())

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Bot stopped")
