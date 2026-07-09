import os
import asyncio
import logging
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не задан в переменных окружения!")

CHAT_ID = None

SCHEDULE = {
    0: "Математика",
    1: "САОД",
    2: "Программирование",
    3: "Математика",
    4: "САОД",
    5: "Выходной - дела по дому",
    6: "Выходной - отдых"
}

# ========== ИНИЦИАЛИЗАЦИЯ ==========
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# ========== КОМАНДЫ БОТА ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    global CHAT_ID
    CHAT_ID = message.chat.id
    logging.info(f"✅ Chat ID сохранён: {CHAT_ID}")
    await message.answer(
        "Привет! Я буду напоминать тебе о занятиях.\n"
        "Команды: /schedule – расписание, /today – что сегодня"
    )

@dp.message(Command("schedule"))
async def cmd_schedule(message: types.Message):
    weekdays = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
    text = "📅 Расписание на неделю:\n\n"
    for i, day in enumerate(weekdays):
        text += f"{day}: {SCHEDULE.get(i, '—')}\n"
    await message.answer(text)

@dp.message(Command("today"))
async def cmd_today(message: types.Message):
    today = datetime.now().weekday()
    subject = SCHEDULE.get(today, "неизвестно")
    await message.answer(f"Сегодня учим: {subject}")

# ========== ФУНКЦИИ НАПОМИНАНИЙ ==========
async def send_reminder():
    if CHAT_ID is None:
        logging.warning("❌ CHAT_ID не установлен, напоминание не отправлено")
        return
    today = datetime.now().weekday()
    subject = SCHEDULE.get(today, "отдых")
    if today < 5:
        text = f"⏰ Напоминание: через 30 минут начало занятий по **{subject}**."
    else:
        text = f"Сегодня {subject}."
    await bot.send_message(chat_id=CHAT_ID, text=text)

async def send_start():
    if CHAT_ID is None:
        return
    today = datetime.now().weekday()
    if today < 5:
        subject = SCHEDULE.get(today)
        await bot.send_message(chat_id=CHAT_ID, text=f"🚀 Начинаем занятие по **{subject}**! Удачи!")

def schedule_jobs():
    scheduler.remove_all_jobs()
    scheduler.add_job(send_reminder, CronTrigger(hour=19, minute=0), id="reminder")
    scheduler.add_job(send_start, CronTrigger(hour=19, minute=30), id="start")
    scheduler.start()
    logging.info("⏰ Планировщик запущен")

# ========== ОБРАБОТЧИКИ ДЛЯ AioHTTP ==========
async def handle_root(request):
    return web.Response(text="Bot is running!")

async def handle_health(request):
    return web.Response(text="OK")

# ========== ЗАПУСК ВСЕГО В ОДНОМ ЦИКЛЕ ==========
async def main():
    # 1. Запускаем планировщик (теперь внутри цикла)
    schedule_jobs()

    # 2. Запускаем бота (поллинг)
    bot_task = asyncio.create_task(dp.start_polling(bot))
    logging.info("🚀 Бот начинает поллинг...")

    # 3. Запускаем aiohttp веб-сервер
    app = web.Application()
    app.router.add_get('/', handle_root)
    app.router.add_get('/health', handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
    await site.start()
    logging.info(f"🌐 Веб-сервер запущен на порту {os.environ.get('PORT', 5000)}")

    # 4. Ждём, пока бот работает (бесконечно)
    await bot_task

if __name__ == "__main__":
    asyncio.run(main())
