import os
import asyncio
import logging
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не задан в переменных окружения!")

CHAT_ID = None

# Часовой пояс Москва (для корректного времени)
MOSCOW_TZ = pytz.timezone('Asia/Novosibirsk')   # или 'Asia/Krasnoyarsk' – GMT+7

# Расписание предметов по будням (0=пн, 4=пт)
SUBJECTS = {
    0: "Математика",
    1: "САОД",
    2: "Программирование",
    3: "Математика",
    4: "САОД",
}

# ========== ФОРМИРУЕМ РАСПИСАНИЕ НА КАЖДЫЙ ДЕНЬ ==========
# Каждый элемент: (время, текст_уведомления, описание_для_today)
# В тексте можно использовать {subject} – он подставится из SUBJECTS

# Будни (пн-пт)
WEEKDAY_EVENTS = [
    ("06:30", "Просыпайся, рванина! Пора на нары!", "Подъём"),
    ("07:00", "Валим на зону! Не отставай!", "Выход из дома"),
    ("08:00", "За работу, падла! Шевели булками!", "Начало работы"),
    ("12:00", "Обед! Жри, пока дают!", "Обед"),
    ("13:00", "Хватит жрать, за работу!", "Продолжение работы"),
    ("18:00", "Свобода! Валим домой!", "Конец работы"),
    ("19:00", "Дуй в хату! Дорога – не место для размышлений!", "Дорога домой"),
    ("19:30", "Жри и отдыхай, завтра опять пахать!", "Ужин и отдых"),
    ("19:35", "А теперь – за учёбу, козёл! Садись за {subject}!", "Начало учёбы"),
    ("22:30", "Хватит мозги парить, отбой!", "Конец учёбы"),
    ("23:00", "Спать, мусор! Свет выключаю!", "Отбой"),
]

# Выходные (сб-вс)
WEEKEND_EVENTS = [
    ("08:00", "Просыпайся, выходной не значит спать до обеда!", "Подъём"),
    ("09:00", "Жри, да побыстрее!", "Завтрак"),
    ("10:00", "Садись за {subject} (1-й час)! Не прохлаждайся!", "Учёба (1-й час)"),
    ("11:00", "Отдыхай, но не расслабляйся! 5 минут на перекур!", "Перерыв"),
    ("12:00", "Второй час {subject}! Давай, шевелись!", "Учёба (2-й час)"),
    ("13:00", "Обед! Жри, кормилец!", "Обед"),
    ("14:00", "Третий час {subject}! Последний рывок!", "Учёба (3-й час)"),
    ("15:00", "Свободное время. Гуляй, но к вечеру будь готов!", "Отдых"),
    ("17:00", "Приберись в камере! Полы помой!", "Домашние дела"),
    ("19:00", "Ужин! Жри давай!", "Ужин"),
    ("22:00", "Отдыхай, завтра снова на работу!", "Отдых"),
    ("23:00", "Спать, зэк! Завтра снова на зону!", "Отбой"),
]

# Собираем полное расписание для каждого дня
def build_schedule():
    schedule = {}
    # Будни (0-4)
    for day in range(5):
        subject = SUBJECTS[day]
        events = []
        for time_str, text, desc in WEEKDAY_EVENTS:
            # Подставляем предмет в текст и описание
            text_filled = text.replace("{subject}", subject)
            desc_filled = desc.replace("{subject}", subject)
            events.append((time_str, text_filled, desc_filled))
        schedule[day] = events
    # Выходные (5-6)
    for day in range(5, 7):
        subject = "Программирование" if day == 5 else "Математика"  # можно изменить
        events = []
        for time_str, text, desc in WEEKEND_EVENTS:
            text_filled = text.replace("{subject}", subject)
            desc_filled = desc.replace("{subject}", subject)
            events.append((time_str, text_filled, desc_filled))
        schedule[day] = events
    return schedule

SCHEDULE = build_schedule()

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)  # задаём московское время

# ========== КОМАНДЫ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    global CHAT_ID
    CHAT_ID = message.chat.id
    logging.info(f"✅ Chat ID сохранён: {CHAT_ID}")
    await message.answer(
        "👋 Привет, зэк! Я твой надзиратель. Буду гонять тебя по расписанию.\n\n"
        "📌 Команды:\n"
        "/today – список дел на сегодня\n"
        "/schedule – расписание на неделю\n"
        "/help – помощь"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📋 Расписание на каждый день:\n"
        "• Будни: подъём 6:30, работа 8-18, учёба 19:30-22:30, отбой 23:00.\n"
        "• Выходные: учёба тремя блоками (10:00, 12:00, 14:00).\n\n"
        "Я буду слать уведомления на каждое действие. Не проспи!"
    )

@dp.message(Command("schedule"))
async def cmd_schedule(message: types.Message):
    days = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
    text = "📅 Расписание на неделю (события сгруппированы):\n\n"
    for day_idx, day_name in enumerate(days):
        events = SCHEDULE.get(day_idx, [])
        if not events:
            continue
        # Берём только описания с временем
        lines = [f"{time} – {desc}" for time, _, desc in events[:5]]  # покажем первые 5 для краткости
        text += f"*{day_name}*:\n" + "\n".join(lines) + "\n… (полный список по /today)\n\n"
    await message.answer(text)

@dp.message(Command("today"))
async def cmd_today(message: types.Message):
    today = datetime.now(MOSCOW_TZ).weekday()
    events = SCHEDULE.get(today, [])
    if not events:
        await message.answer("Сегодня отдыхай, дел нет.")
        return
    day_name = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"][today]
    text = f"📋 *Расписание на {day_name} (сегодня):*\n\n"
    for time_str, _, desc in events:
        text += f"⏰ {time_str} – {desc}\n"
    await message.answer(text)

# ========== ФУНКЦИЯ ОТПРАВКИ УВЕДОМЛЕНИЙ ==========
async def send_scheduled_message(text: str):
    if CHAT_ID is None:
        logging.warning("❌ CHAT_ID не установлен, уведомление не отправлено")
        return
    await bot.send_message(chat_id=CHAT_ID, text=text)

# ========== ПЛАНИРОВЩИК ==========
def schedule_jobs():
    scheduler.remove_all_jobs()
    # Проходим по каждому дню и каждому событию
    for day, events in SCHEDULE.items():
        for time_str, text, _ in events:
            hour, minute = map(int, time_str.split(':'))
            # Добавляем задание на каждый день недели
            scheduler.add_job(
                send_scheduled_message,
                CronTrigger(day_of_week=day, hour=hour, minute=minute, timezone=MOSCOW_TZ),
                args=[text],
                id=f"{day}_{time_str}"
            )
    scheduler.start()
    logging.info("⏰ Планировщик запущен, все уведомления запланированы.")

# ========== ВЕБ-СЕРВЕР (AioHTTP) ==========
async def handle_root(request):
    return web.Response(text="Bot is running!")

async def handle_health(request):
    return web.Response(text="OK")

# ========== ГЛАВНЫЙ ЗАПУСК ==========
async def main():
    # Запускаем планировщик
    schedule_jobs()

    # Запускаем бота (поллинг)
    bot_task = asyncio.create_task(dp.start_polling(bot))
    logging.info("🚀 Бот начал поллинг...")

    # Запускаем веб-сервер
    app = web.Application()
    app.router.add_get('/', handle_root)
    app.router.add_get('/health', handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
    await site.start()
    logging.info(f"🌐 Веб-сервер запущен на порту {os.environ.get('PORT', 5000)}")

    # Бесконечное ожидание
    await bot_task

if __name__ == "__main__":
    asyncio.run(main())
