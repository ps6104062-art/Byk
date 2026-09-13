import asyncio
import logging
from datetime import datetime
import pytz

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS, WORK_START, WORK_STOP
from database import init_db, set_setting, get_setting, get_all_users
from handlers import user, admin

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(admin.router)
dp.include_router(user.router)

MSK = pytz.timezone("Europe/Moscow")

async def auto_work_scheduler():
    """Автоматически включает/выключает ворк по МСК"""
    last_action = None
    while True:
        now = datetime.now(MSK)
        time_str = now.strftime("%H:%M")
        
        if time_str == WORK_START and last_action != f"start_{now.date()}":
            await set_setting('work_active', '1')
            last_action = f"start_{now.date()}"
            users = await get_all_users()
            for u in users:
                if u['is_banned']:
                    continue
                try:
                    await bot.send_message(u['tg_id'], "🟢 СТАРТ ВОРК! Приём номеров открыт.\nРабочее время: 07:40 – 17:45 МСК")
                except:
                    pass
        
        elif time_str == WORK_STOP and last_action != f"stop_{now.date()}":
            await set_setting('work_active', '0')
            last_action = f"stop_{now.date()}"
            users = await get_all_users()
            for u in users:
                if u['is_banned']:
                    continue
                try:
                    await bot.send_message(u['tg_id'], "🔴 СТОП ВОРК! Приём номеров остановлен. До завтра!")
                except:
                    pass
        
        await asyncio.sleep(30)

async def main():
    await init_db()
    
    # Регистрируем главного админа
    from database import get_or_create_user, update_user
    for admin_id in ADMIN_IDS:
        await get_or_create_user(admin_id)
        await update_user(admin_id, role='admin')
    
    asyncio.create_task(auto_work_scheduler())
    
    await dp.start_polling(bot, bot=bot)

if __name__ == "__main__":
    asyncio.run(main())
