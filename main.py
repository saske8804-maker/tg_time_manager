import os
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (В ОТДЕЛЬНОМ ПОТОКЕ) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, format, *args):
        pass  # Отключаем лишние логи сервера

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    print(f"Веб-сервер запущен на порту {port}")
    server.serve_forever()

# Запускаем сервер в фоне до старта бота
threading.Thread(target=run_web_server, daemon=True).start()

# --- ОСНОВНОЙ КОД БОТА ---
TOKEN = os.getenv("BOT_TOKEN")
print(f"ОТЛАДКА: Токен выглядит так -> {TOKEN}")

from database import init_db, add_task_to_db, get_tasks_for_day, save_daily_rating

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Инициализируем базу данных при запуске
init_db()

# --- КЛАВИАТУРЫ ---
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Посмотреть задачи на сегодня"), KeyboardButton(text="➕ Добавить задачу")],
        [KeyboardButton(text="⭐ Оценить день"), KeyboardButton(text="📋 Все задачи на неделю")]
    ],
    resize_keyboard=True
)

days_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Понедельник"), KeyboardButton(text="Вторник")],
        [KeyboardButton(text="Среда"), KeyboardButton(text="Четверг")],
        [KeyboardButton(text="Пятница"), KeyboardButton(text="Суббота")],
        [KeyboardButton(text="Воскресенье"), KeyboardButton(text="🔙 Назад")]
    ],
    resize_keyboard=True
)

# --- МАШИНА СОСТОЯНИЙ (FSM) ---
class TaskState(StatesGroup):
    waiting_for_day = State()
    waiting_for_text = State()

class RatingState(StatesGroup):
    waiting_for_rating = State()

def get_rating_keyboard():
    builder = InlineKeyboardBuilder()
    for i in range(1, 11):
        builder.button(text=str(i), callback_data=f"rate_{i}")
    builder.adjust(5)
    return builder.as_markup()

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я твой личный бот для тайм-менеджмента.\n"
        "Помогу распределить задачи по дням недели и прослежу за продуктивностью!",
        reply_markup=main_menu
    )

@dp.message(F.text == "🔙 Назад")
async def back_to_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_menu)

@dp.message(F.text == "➕ Добавить задачу")
async def start_add_task(message: types.Message, state: FSMContext):
    await message.answer("На какой день недели добавить задачу?", reply_markup=days_menu)
    await state.set_state(TaskState.waiting_for_day)

@dp.message(TaskState.waiting_for_day, F.text.in_([
    "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"
]))
async def process_day(message: types.Message, state: FSMContext):
    await state.update_data(chosen_day=message.text)
    await message.answer(f"Отлично, день: **{message.text}**.\nТеперь напиши суть задачи:", reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")
    await state.set_state(TaskState.waiting_for_text)

@dp.message(TaskState.waiting_for_text)
async def process_task_text(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    day = user_data.get("chosen_day")
    task_text = message.text
    user_id = message.from_user.id

    add_task_to_db(user_id, day, task_text)
    
    await state.clear()
    await message.answer(f"✅ Задача успешно добавлена на **{day}**!", reply_markup=main_menu, parse_mode="Markdown")

@dp.message(F.text == "📅 Посмотреть задачи на сегодня")
async def show_today_tasks(message: types.Message):
    days_map = {
        0: "Понедельник", 1: "Вторник", 2: "Среда", 
        3: "Четверг", 4: "Пятница", 5: "Суббота", 6: "Воскресенье"
    }
    today_index = datetime.now().weekday()
    today_name = days_map[today_index]
    
    user_id = message.from_user.id
    tasks = get_tasks_for_day(user_id, today_name)

    if not tasks:
        await message.answer(f"📅 Сегодня **{today_name}**.\nУ тебя пока нет запланированных задач на этот день!", reply_markup=main_menu, parse_mode="Markdown")
        return

    response = f"📅 **План на сегодня ({today_name}):**\n\n"
    for idx, (task_id, text) in enumerate(tasks, 1):
        response += f"{idx}. {text}\n"

    await message.answer(response, reply_markup=main_menu, parse_mode="Markdown")

@dp.message(F.text == "📋 Все задачи на неделю")
async def show_week_tasks(message: types.Message):
    user_id = message.from_user.id
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    
    response = "📋 **Твое расписание на неделю:**\n\n"
    has_tasks = False

    for day in days:
        tasks = get_tasks_for_day(user_id, day)
        if tasks:
            has_tasks = True
            response += f"▫️ **{day}:**\n"
            for task_id, text in tasks:
                response += f"    • {text}\n"
            response += "\n"

    if not has_tasks:
        response = "У тебя пока не добавлено ни одной задачи на неделю. Нажми «➕ Добавить задачу»!"

    await message.answer(response, reply_markup=main_menu, parse_mode="Markdown")

@dp.message(F.text == "⭐ Оценить день")
async def start_rating(message: types.Message, state: FSMContext):
    await message.answer(
        "Насколько продуктивным был сегодняшний день?\n"
        "Выбери оценку от 1 до 10:",
        reply_markup=get_rating_keyboard()
    )
    await state.set_state(RatingState.waiting_for_rating)

@dp.callback_query(RatingState.waiting_for_rating, F.data.startswith("rate_"))
async def process_rating(callback: types.CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    save_daily_rating(user_id, rating)
    
    await state.clear()
    await callback.message.edit_text(f"⭐ Спасибо! Оценка сегодняшнего дня (**{rating}/10**) успешно сохранена.", parse_mode="Markdown")
    await callback.answer()

# --- ЗАПУСК БОТА ---
async def main():
    print("Бот запущен и ждет сообщения...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        import traceback 
        print("КРИТИЧЕСКАЯ ОШИБКА:")
        traceback.print_exc()
        raise e
