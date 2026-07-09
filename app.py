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

# Часовой пояс – можно задать через переменную окружения TIMEZONE
# По умолчанию – Новосибирск (GMT+7)
TIMEZONE_STR = os.environ.get("TIMEZONE", "Asia/Novosibirsk")
try:
    TZ = pytz.timezone(TIMEZONE_STR)
except Exception as e:
    logging.error(f"Неверный часовой пояс: {TIMEZONE_STR}, использую UTC")
    TZ = pytz.UTC

# Функция для получения текущего времени в нужном поясе
def get_now():
    return datetime.now().astimezone(TZ)

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
# В тексте и описании можно использовать {subject}

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
    ("19:35", "А теперь – за учёбу, козёл! Садись за {subject}!", "Начало учёбы по {subject}"),
    ("22:30", "Хватит мозги парить, отбой!", "Конец учёбы"),
    ("23:00", "Спать, мусор! Свет выключаю!", "Отбой"),
]

# Выходные (сб-вс)
WEEKEND_EVENTS = [
    ("08:00", "Просыпайся, выходной не значит спать до обеда!", "Подъём"),
    ("09:00", "Жри, да побыстрее!", "Завтрак"),
    ("10:00", "Садись за {subject} (1-й час)! Не прохлаждайся!", "Учёба (1-й час) по {subject}"),
    ("11:00", "Отдыхай, но не расслабляйся! 5 минут на перекур!", "Перерыв"),
    ("12:00", "Второй час {subject}! Давай, шевелись!", "Учёба (2-й час) по {subject}"),
    ("13:00", "Обед! Жри, кормилец!", "Обед"),
    ("14:00", "Третий час {subject}! Последний рывок!", "Учёба (3-й час) по {subject}"),
    ("15:00", "Свободное время. Гуляй, но к вечеру будь готов!", "Отдых"),
    ("17:00", "Приберись в камере! Полы помой!", "Домашние дела"),
    ("19:00", "Ужин! Жри давай!", "Ужин"),
    ("22:00", "Отдыхай, завтра снова на работу!", "Отдых"),
    ("23:00", "Спать, зэк! Завтра снова на зону!", "Отбой"),
]

def build_schedule():
    schedule = {}
    for day in range(5):
        subject = SUBJECTS[day]
        events = []
        for time_str, text, desc in WEEKDAY_EVENTS:
            events.append((
                time_str,
                text.replace("{subject}", subject),
                desc.replace("{subject}", subject)
            ))
        schedule[day] = events
    for day in range(5, 7):
        subject = "Программирование" if day == 5 else "Математика"
        events = []
        for time_str, text, desc in WEEKEND_EVENTS:
            events.append((
                time_str,
                text.replace("{subject}", subject),
                desc.replace("{subject}", subject)
            ))
        schedule[day] = events
    return schedule

SCHEDULE = build_schedule()

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=TZ)

# ========== КОМАНДЫ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    global CHAT_ID
    CHAT_ID = message.chat.id
    logging.info(f"✅ CHAT_ID сохранён: {CHAT_ID}")
    await message.answer(
        "👋 Привет, зэк! Я твой надзиратель. Буду гонять тебя по расписанию.\n\n"
        "📌 Команды:\n"
        "/today – список дел на сегодня\n"
        "/now – что делать прямо сейчас\n"
        "/schedule – расписание на неделю\n"
        "/help – помощь"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📋 Расписание на каждый день:\n"
        "• Будни: подъём 6:30, работа 8-18, учёба 19:35-22:30, отбой 23:00.\n"
        "• Выходные: учёба тремя блоками (10:00, 12:00, 14:00).\n\n"
        "Я буду слать уведомления на каждое действие. Не проспи!"
    )

@dp.message(Command("schedule"))
async def cmd_schedule(message: types.Message):
    days = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
    text = "📅 Расписание на неделю (первые 5 событий):\n\n"
    for day_idx, day_name in enumerate(days):
        events = SCHEDULE.get(day_idx, [])
        if not events:
            continue
        lines = [f"{time} – {desc}" for time, _, desc in events[:5]]
        text += f"*{day_name}*:\n" + "\n".join(lines) + "\n… (полный список по /today)\n\n"
    await message.answer(text)

@dp.message(Command("today"))
async def cmd_today(message: types.Message):
    today = get_now().weekday()
    events = SCHEDULE.get(today, [])
    if not events:
        await message.answer("Сегодня отдыхай, дел нет.")
        return
    day_name = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"][today]
    text = f"📋 *Расписание на {day_name} (сегодня):*\n\n"
    for time_str, _, desc in events:
        text += f"⏰ {time_str} – {desc}\n"
    await message.answer(text)

@dp.message(Command("now"))
async def cmd_now(message: types.Message):
    now = get_now()
    today = now.weekday()
    events = SCHEDULE.get(today, [])
    if not events:
        await message.answer("Сегодня отдыхай, дел нет.")
        return

    current_time = now.strftime("%H:%M")
    next_event = None
    for time_str, _, desc in events:
        if time_str >= current_time:
            next_event = (time_str, desc)
            break

    # Логируем текущее время для отладки
    logging.info(f"Текущее время по расписанию: {current_time}")

    if next_event:
        await message.answer(f"⏰ *Прямо сейчас:* {next_event[0]} – {next_event[1]}")
    else:
        last = events[-1]
        await message.answer(f"⏰ *Все дела на сегодня сделаны!* Последнее событие: {last[0]} – {last[1]}")

# ========== ФУНКЦИЯ ОТПРАВКИ УВЕДОМЛЕНИЙ ==========
async def send_scheduled_message(text: str):
    if CHAT_ID is None:
        logging.warning("❌ CHAT_ID не установлен, уведомление не отправлено")
        return
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text)
        logging.info(f"✅ Уведомление отправлено: {text[:50]}...")
    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")

# ========== ПЛАНИРОВЩИК ==========
def schedule_jobs():
    scheduler.remove_all_jobs()
    for day, events in SCHEDULE.items():
        for time_str, text, _ in events:
            hour, minute = map(int, time_str.split(':'))
            scheduler.add_job(
                send_scheduled_message,
                CronTrigger(day_of_week=day, hour=hour, minute=minute, timezone=TZ),
                args=[text],
                id=f"{day}_{time_str}"
            )
    scheduler.start()
    logging.info(f"⏰ Планировщик запущен, временная зона: {TIMEZONE_STR}")

# ========== ВЕБ-СЕРВЕР ==========
async def handle_root(request):
    return web.Response(text="Bot is running!")

async def handle_health(request):
    return web.Response(text="OK")

# ========== ГЛАВНЫЙ ЗАПУСК ==========
async def main():
    schedule_jobs()
    bot_task = asyncio.create_task(dp.start_polling(bot))
    logging.info("🚀 Бот начал поллинг...")

    app = web.Application()
    app.router.add_get('/', handle_root)
    app.router.add_get('/health', handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
    await site.start()
    logging.info(f"🌐 Веб-сервер запущен на порту {os.environ.get('PORT', 5000)}")

    await bot_task

if __name__ == "__main__":
    asyncio.run(main())
