import os
import json
import logging
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ---------------- НАСТРОЙКИ ----------------

TOKEN = "8312864487:AAHYo1M2f9tOCpANUAa0Bq8JDozHvapSLcE"
ADMIN_CHAT_ID = 194614510

MAX_SLOTS = 12
DATA_FILE = "registered_users.json"

RUN_DATETIME = datetime(2026, 1, 7, 20, 0)
RUN_DATE_TEXT = "07.01.26"
RUN_TITLE_TEXT = "Среда равно бег"

START_POINT = "Дринкит, ул. Вильгельма Пика, 11, Москва • этаж 1"
START_MAP_LINK_8KM = "https://yandex.ru/maps/-/CLXeaBzV"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- ДАННЫЕ ----------------

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        registered_users = json.load(f)
else:
    registered_users = []  # список участников

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(registered_users, f, ensure_ascii=False, indent=2)

# ---------------- ВСПОМОГАТЕЛЬНЫЕ ----------------

def build_participants_text():
    if not registered_users:
        return "Участников пока нет."

    text = "Участники (8 км):\n"
    for i, u in enumerate(registered_users, start=1):
        username = f"@{u['username']}" if u["username"] else "—"
        text += f"{i}. {u['name']} {username}\n"

    return text

# ---------------- /START ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"{RUN_DATE_TEXT}\n"
        f"{RUN_TITLE_TEXT}\n\n"
        "Рад, что ты присоединился к пробежке Spivak Run.\n\n"
        "Условия участия:\n"
        "— Участник самостоятельно несёт ответственность за свою жизнь и здоровье.\n"
        "— Участник несёт ответственность за сохранность личных вещей.\n"
        "— Согласие на обработку персональных данных.\n"
        "— Согласие на фото- и видеосъёмку.\n\n"
        "Если согласен — нажми кнопку ниже."
    )

    keyboard = [
        [InlineKeyboardButton("Согласен, зарегистрироваться (8 км)", callback_data="agree")],
        [InlineKeyboardButton("Информация о забеге", callback_data="info")]
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------------- РЕГИСТРАЦИЯ ----------------

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_id = str(user.id)

    if any(u["id"] == user_id for u in registered_users):
        await query.edit_message_text("Ты уже зарегистрирован.")
        return

    if len(registered_users) >= MAX_SLOTS:
        await query.edit_message_text("Все места заняты.")
        return

    user_data = {
        "id": user_id,
        "name": user.first_name,
        "username": user.username or "",
    }

    registered_users.append(user_data)
    save_data()

    await context.bot.send_message(
        ADMIN_CHAT_ID,
        f"Новый участник\n"
        f"Имя: {user.first_name}\n"
        f"Username: @{user.username}\n"
        f"ID: {user_id}"
    )

    keyboard = [
        [InlineKeyboardButton("Отменить запись", callback_data="cancel")]
    ]

    await query.edit_message_text(
        f"Ты зарегистрирован на пробежку 8 км.\n\n"
        f"{build_participants_text()}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------------- ОТМЕНА ----------------

async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)

    for u in registered_users:
        if u["id"] == user_id:
            registered_users.remove(u)
            save_data()

            await context.bot.send_message(
                ADMIN_CHAT_ID,
                f"Участник отменил регистрацию\n"
                f"Имя: {u['name']}\n"
                f"Username: @{u['username']}\n"
                f"ID: {u['id']}"
            )
            break

    await query.edit_message_text("Регистрация отменена.")

# ---------------- /INFO ----------------

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"{RUN_DATE_TEXT}\n"
        f"{RUN_TITLE_TEXT}\n\n"
        f"Старт: {START_POINT}\n"
        "Сбор: 19:30\n"
        "Старт: 20:00\n\n"
        f"Маршрут 8 км:\n{START_MAP_LINK_8KM}\n\n"
        f"{build_participants_text()}"
    )

    # если нажали кнопку
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text)

    # если вызвали командой /info
    else:
        await update.message.reply_text(text)

# ---------------- АДМИНКА ----------------

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("Доступ запрещён.")
        return

    # 1. текст
    try:
        await update.message.reply_text(build_participants_text())
    except Exception as e:
        logging.error(f"Admin text error: {e}")

    # 2. кнопки
    keyboard = []
    for i, u in enumerate(registered_users):
        keyboard.append([
            InlineKeyboardButton(
                f"Удалить {u['name']}",
                callback_data=f"del_{i}"
            )
        ])

    if not keyboard:
        keyboard = [[InlineKeyboardButton("Участников нет", callback_data="noop")]]

    # 3. отправка кнопок
    try:
        await update.message.reply_text(
            "Управление участниками:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logging.error(f"Admin keyboard error: {e}")

# ---------------- АДМИН ДЕЙСТВИЯ ----------------

async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("del_"):
        index = int(query.data.split("_")[1])

        if index < len(registered_users):
            removed = registered_users.pop(index)
            save_data()

            await query.message.reply_text(
                f"{removed['name']} удалён из списка."
            )

# ---------------- НАПОМИНАНИЕ ----------------

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"{RUN_DATE_TEXT}\n"
        f"{RUN_TITLE_TEXT}\n\n"
        "Завтра пробежка.\n\n"
        f"Старт: {START_POINT}\n"
        "Сбор: 19:30\n"
        "Старт: 20:00\n\n"
        f"Маршрут 8 км:\n{START_MAP_LINK_8KM}"
    )

    for u in registered_users:
        try:
            await context.bot.send_message(chat_id=int(u["id"]), text=text)
        except Exception:
            pass

    await context.bot.send_message(
        ADMIN_CHAT_ID,
        f"Напоминание отправлено.\n"
        f"Всего участников: {len(registered_users)}"
    )

# ---------------- ЗАПУСК ----------------

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("admin", admin))

    app.add_handler(CallbackQueryHandler(register, pattern="^agree$"))
    app.add_handler(CallbackQueryHandler(cancel_registration, pattern="^cancel$"))
    app.add_handler(CallbackQueryHandler(admin_actions, pattern="^del_"))

    reminder_time = RUN_DATETIME - timedelta(hours=24)
    app.job_queue.run_once(send_reminder, reminder_time)

    logger.info("Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
