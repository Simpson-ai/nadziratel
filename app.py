import os
import asyncio
import logging
from datetime import datetime
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")  # Токен из переменных окружения Render
CHAT_ID = None

# Ваше расписание: 0=пн, 1=вт, ...
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
app = Flask(__name__)  # <-- Это для веб-сервера

# ========== КОМАНДЫ БОТА ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    global CHAT_ID
    CHAT_ID = message.chat.id
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

# ========== ПЛАНИРОВЩИК ==========
def schedule_jobs():
    scheduler.remove_all_jobs()
    scheduler.add_job(send_reminder, CronTrigger(hour=19, minute=0), id="reminder")
    scheduler.add_job(send_start, CronTrigger(hour=19, minute=30), id="start")
    scheduler.start()

# ========== ЗАПУСК БОТА В ФОНОВОМ ПОТОКЕ ==========
async def start_bot():
    schedule_jobs()
    await dp.start_polling(bot)

# ========== ЗАПУСК ВЕБ-СЕРВЕРА (ДЛЯ RENDER) ==========
@app.route('/')
def home():
    return "Bot is running!"

@app.route('/health')
def health():
    return "OK"

# Эта функция запускает и веб-сервер, и бота
def run_bot_and_web():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(start_bot())
    # Запускаем Flask-сервер
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    run_bot_and_web()