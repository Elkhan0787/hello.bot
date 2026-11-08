import logging
import json
import os
import html
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

GET_NAME, GET_CAR = range(2)

# .env и user.json находятся в той же папке, что и hello.py
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
JSON_FILE = BASE_DIR / "user.json"


def load_users_data() -> dict:
    """Загружает данные пользователей из JSON-файла."""
    if not JSON_FILE.exists():
        return {}
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as error:
        logger.error("Не удалось прочитать %s: %s", JSON_FILE, error)
        return {}


def save_user_data(user_id: int, name: str, car: str, username: str = None) -> None:
    """Сохраняет данные пользователя в JSON-файл."""
    data = load_users_data()
    data[str(user_id)] = {
        "name": name,
        "favorite_car": car,
        "username": username if username else "нет"
    }
    with open(JSON_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def get_main_keyboard() -> InlineKeyboardMarkup:
    """Создаёт главную клавиатуру бота."""
    keyboard = [[
        InlineKeyboardButton("Сохранить данные", callback_data="save_data"),
        InlineKeyboardButton("Мой профиль", callback_data="my_profile")
    ]]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /start."""
    await update.message.reply_text(
        "Привет! Я бот для сохранения данных. 💾\n\nВыберите действие ниже:",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END


async def start_save_data_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Начинает опрос после нажатия кнопки «Сохранить данные»."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "<b>Шаг 1 из 2:</b> Напишите ваше имя:",
        parse_mode="HTML"
    )
    return GET_NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает имя пользователя."""
    name = (update.message.text or "").strip()
    if not name:
        await update.message.reply_text("Пожалуйста, напишите имя.")
        return GET_NAME

    context.user_data["name"] = name
    await update.message.reply_text(
        "<b>Шаг 2 из 2:</b> Напишите вашу любимую марку машины:",
        parse_mode="HTML"
    )
    return GET_CAR


async def receive_car(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает марку машины и сохраняет профиль."""
    user = update.effective_user
    name = context.user_data.get("name")
    car = (update.message.text or "").strip()

    if not car:
        await update.message.reply_text("Пожалуйста, напишите марку машины.")
        return GET_CAR

    save_user_data(user.id, name, car, user.username)
    await update.message.reply_text(
        "✅ Ваши данные успешно сохранены!\n"
        "Теперь вы можете открыть «Мой профиль».",
        reply_markup=get_main_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END


async def show_profile_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Показывает сохранённый профиль пользователя."""
    query = update.callback_query
    await query.answer()

    user_id = str(update.effective_user.id)
    all_users = load_users_data()

    if user_id in all_users:
        user_info = all_users[user_id]
        name = html.escape(str(user_info.get("name", "Не указано")))
        car = html.escape(str(user_info.get("favorite_car", "Не указана")))
        profile_text = (
            "👤 <b>Ваш профиль:</b>\n\n"
            f"Имя: <b>{name}</b>\n"
            f"Любимая машина: <b>{car}</b>"
        )
    else:
        profile_text = (
            "У вас пока нет сохранённых данных. "
            "Нажмите «Сохранить данные», чтобы заполнить профиль!"
        )

    await query.message.reply_text(
        profile_text,
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет заполнение профиля."""
    context.user_data.clear()
    await update.message.reply_text(
        "Ввод данных отменён.",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END


def main() -> None:
    # Загружаем .env из папки hello.py, а не из текущей папки терминала
    load_dotenv(dotenv_path=ENV_FILE)
    token = os.getenv("TOKEN", "").strip()

    if not token:
        raise RuntimeError(
            "Токен не найден. Создайте файл .env рядом с hello.py "
            "и добавьте строку:\nTOKEN=ВАШ_ТОКЕН_ОТ_BOTFATHER"
        )

    application = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_save_data_callback, pattern="^save_data$")
        ],
        states={
            GET_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)
            ],
            GET_CAR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_car)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        CallbackQueryHandler(show_profile_callback, pattern="^my_profile$")
    )

    logger.info("Бот запущен.")
    application.run_polling()


if __name__ == "__main__":
    main()
