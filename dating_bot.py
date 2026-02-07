import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from geopy.distance import geodesic
from dotenv import load_dotenv
from aiohttp import TCPConnector, ClientConnectorError

# ----------------- Настройка -----------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("ERROR: В файле .env не найден BOT_TOKEN")
    exit()

logging.basicConfig(level=logging.INFO)

# ----------------- Кнопки -----------------
sex_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Девушка")],[KeyboardButton(text="Парень")]],
    resize_keyboard=True
)

signal_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🌙"), KeyboardButton(text="☕"), KeyboardButton(text="🎶")]],
    resize_keyboard=True
)

location_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Отправить геолокацию", request_location=True)]],
    resize_keyboard=True
)

# ----------------- Хранилище -----------------
users = {}  # user_id -> {"sex":..., "age":..., "lat":..., "lon":..., "text":..., "signal": None}
ads = []    # {"user_id":..., "sex":..., "age":..., "lat":..., "lon":..., "text":..., "signal": None}

# ----------------- Главная асинхронная функция -----------------
async def main():
    # Создаём connector и бота внутри async функции
    connector = TCPConnector(family=2)  # IPv4
    bot = Bot(token=BOT_TOKEN, connector=connector)
    dp = Dispatcher()

    # ----------------- Проверка подключения -----------------
    try:
        me = await bot.get_me()
        print(f"✅ Подключение успешно! Бот: @{me.username}")
    except ClientConnectorError:
        print("❌ Не могу связаться с api.telegram.org. Проверь интернет и DNS.")
        return
    except Exception as e:
        print(f"❌ Другая ошибка подключения: {e}")
        return

    # ----------------- Команды -----------------
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer("Привет! Для начала укажи свой пол:", reply_markup=sex_keyboard)

    @dp.message(lambda m: m.text in ["Девушка", "Парень"])
    async def choose_sex(message: types.Message):
        users[message.from_user.id] = {"sex": message.text, "signal": None}
        await message.answer("Отлично! Теперь отправь свой возраст:")

    @dp.message(lambda m: m.text.isdigit() and 10 <= int(m.text) <= 100)
    async def enter_age(message: types.Message):
        if message.from_user.id in users:
            users[message.from_user.id]["age"] = int(message.text)
            await message.answer("Отправь свою геолокацию через кнопку или координаты:", reply_markup=location_keyboard)

    @dp.message(lambda m: m.location is not None)
    async def receive_location(message: types.Message):
        user = users.get(message.from_user.id)
        if user:
            user["lat"] = message.location.latitude
            user["lon"] = message.location.longitude
            await message.answer("Отлично! Напиши короткий текст о себе (до 300 символов):")

    @dp.message(lambda m: m.text and m.from_user.id in users and "text" not in users[m.from_user.id])
    async def receive_text(message: types.Message):
        user = users[message.from_user.id]
        user["text"] = message.text[:300]
        ad = user.copy()
        ad["user_id"] = message.from_user.id
        ads.append(ad)
        await message.answer("Объявление создано! Теперь можешь отправить сигнал для сближения:", reply_markup=signal_keyboard)

    @dp.message(lambda m: m.text in ["🌙", "☕", "🎶"])
    async def send_signal(message: types.Message):
        user = users[message.from_user.id]
        user["signal"] = message.text
        matched = []

        for ad in ads:
            if ad["user_id"] == message.from_user.id:
                continue
            if ad["sex"] == user["sex"]:
                continue
            loc1 = (user["lat"], user["lon"])
            loc2 = (ad["lat"], ad["lon"])
            distance_km = geodesic(loc1, loc2).km
            if distance_km > 5:
                continue
            if ad.get("signal") == user["signal"]:
                matched.append((ad, distance_km))

        if matched:
            ad, distance = matched[0]
            await bot.send_message(message.from_user.id,
                                   f"✅ Найдено совпадение! Расстояние: {distance:.1f} км\nМожно начать анонимный чат.")
            await bot.send_message(ad["user_id"],
                                   f"✅ Найдено совпадение! Расстояние: {distance:.1f} км\nМожно начать анонимный чат.")
        else:
            await message.answer("Сигнал отправлен, совпадений пока нет. Попробуй позже!")

    # ----------------- Старт polling -----------------
    print("Бот запускается...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()  # Закрываем сессию корректно

# ----------------- Запуск -----------------
if __name__ == "__main__":
    asyncio.run(main())

