from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardMarkup,
    InlineKeyboardButton, InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler, CallbackQueryHandler
)
import asyncio
import requests
import json
import os

places_data = {}


# def load_places_data():
#     with open("places.json", "r", encoding="utf-8") as f:
#         return json.load(f)

def load_places_from_github():
    url = "https://raw.githubusercontent.com/idar1504/photos_MustGoMsk_bot/main/places.json"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        print("✅ Успешно загружены данные с GitHub")
        return data
    except Exception as e:
        print("⚠️ Ошибка при загрузке данных с GitHub:", e)
        return None


TOKEN = "5847682014:AAFhiFUbNhxt-St2tzMGUqiFuEukCKElOPg"

MOSCOW_LAT = 55.7558
MOSCOW_LON = 37.6173

WEATHER_CHOICE, ENTER_CITY = range(2)
STATION_CHOICE, ACTIVITY_CHOICE, SUGGEST_PLACE, DONATE = range(4)

ADMIN_CHAT_ID = 691634637

INVITE_WAIT_PHOTO = 10

# Клавиатура
main_keyboard = ReplyKeyboardMarkup(
    [
        ["/help"],
        ["/weather", "/add"],
        ["/supportus", "/invitation"]
    ],
    resize_keyboard=True
)


# places_data =

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Привет, {update.effective_user.first_name}! Я, Даша-путешественница, помогу тебе провести незабываемое время в Москве! По команде:\n"
        "/help — выбор станции метро\n"
        "/weather — погода в Москве\n"
        "/add — добавь интересные места\n"
        "/supportus — поддержать бота\n"
        "/invitation — попасть в закрытый чат\n"
        "Выбери команду на клавиатуре ниже 👇",
        reply_markup=main_keyboard
    )


# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Какую станцию метро хочешь посетить?")
    return STATION_CHOICE


async def choose_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    station = update.message.text
    context.user_data["station"] = station

    global places_data

    new_data = load_places_from_github()
    if new_data:
        places_data = new_data  # обновление, если удалось

    station = update.message.text
    station = station.strip().lower()
    context.user_data["station"] = station

    if station in places_data:
        keyboard = [
            ["бары и рестораны", "достопримечательности"],
            ["развлечения", "парки/скверы"],
            ["музеи", "ТЦ/ТРЦ"]
        ]
        await update.message.reply_text(
            "Отлично, теперь выбери, как ты хочешь провести вечер:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        return ACTIVITY_CHOICE
    else:
        await update.message.reply_text("К сожалению, у меня нет информации по этой станции. Попробуй другую.")
        return STATION_CHOICE


async def choose_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    activity = update.message.text
    station = context.user_data.get("station")

    if not station or station not in places_data or activity not in places_data[station]:
        await update.message.reply_text(
            "Ничего не нашлось по этим параметрам.",
            reply_markup=main_keyboard  # показываем главное меню
        )
        return ConversationHandler.END

    context.user_data["places"] = places_data[station][activity]
    context.user_data["place_index"] = 0
    await show_place(update, context, edit=False)
    return ConversationHandler.END


async def show_place(update_or_query, context, edit=True):
    places = context.user_data["places"]
    index = context.user_data["place_index"]
    place = places[index]

    text = f"<b>{place['name']}</b>\n{place['desc']}"
    keyboard = [
        [InlineKeyboardButton("Хочу сюда!", url=place['yandex'])],
        [InlineKeyboardButton("⬅️", callback_data="prev"),
         InlineKeyboardButton("➡️", callback_data="next")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    image_url = place.get("image")

    if edit and isinstance(update_or_query, Update):
        query = update_or_query.callback_query
        try:
            if image_url:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=image_url, caption=text, parse_mode="HTML"),
                    reply_markup=markup
                )
            else:
                raise ValueError("Нет изображения")
        except Exception as e:
            print("❗ Ошибка при редактировании фото или отсутствует изображение:", e)
            try:
                await query.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=markup)
            except Exception as e2:
                print("❗ Ошибка при редактировании подписи:", e2)
        await query.answer()
    else:
        try:
            if image_url:
                await update_or_query.message.reply_photo(
                    photo=image_url,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            else:
                raise ValueError("Нет изображения")
        except Exception as e:
            print("❗ Ошибка при отправке фото или отсутствует изображение:", e)
            await update_or_query.message.reply_text(
                text,
                parse_mode="HTML",
                reply_markup=markup
            )

        await update_or_query.message.reply_text(
            "Выбирай следующую команду ⬇️",
            reply_markup=main_keyboard
        )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if "places" not in context.user_data or "place_index" not in context.user_data:
        await query.answer("Ошибка: список мест не найден. Попробуйте выбрать станцию заново.", show_alert=True)
        return

    if data == "next":
        context.user_data["place_index"] = (context.user_data["place_index"] + 1) % len(context.user_data["places"])
    elif data == "prev":
        context.user_data["place_index"] = (context.user_data["place_index"] - 1) % len(context.user_data["places"])

    await show_place(update, context)


# /weather
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    weather_info = get_weather_moscow()
    await update.message.reply_text(weather_info, reply_markup=main_keyboard)


def get_weather_moscow():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": MOSCOW_LAT,
        "longitude": MOSCOW_LON,
        "current_weather": True
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()["current_weather"]
        temp = data["temperature"]
        wind = data["windspeed"]
        weather_code = data["weathercode"]
        description = weather_code_to_text(weather_code)
        return f"🌆 Сейчас в Москве:\n🌡 Температура: {temp}°C\n💨 Ветер: {wind} км/ч\n☁️ Погода: {description}"
    except Exception:
        return "⚠️ Не удалось получить данные о погоде. Попробуй позже."


def weather_code_to_text(code):
    codes = {
        0: "ясно", 1: "в основном ясно", 2: "переменная облачность", 3: "пасмурно",
        45: "туман", 48: "изморозь", 51: "лёгкая морось", 53: "морось", 55: "сильная морось",
        61: "лёгкий дождь", 63: "дождь", 65: "сильный дождь",
        71: "лёгкий снег", 73: "снег", 75: "сильный снег",
        80: "кратковременные дожди", 81: "дожди", 82: "ливень",
    }
    return codes.get(code, "неизвестная погода")


# /add
async def add_place(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Хочешь посоветовать интересное место? ✨\n\n"
        "Отправь его в формате:\n"
        "<Название>\n<Описание>\n<Ссылка на Яндекс.Карты>"
    )
    return SUGGEST_PLACE


async def process_suggestion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    suggestion = update.message.text
    user = update.effective_user

    with open("suggestions.txt", "a", encoding="utf-8") as file:
        file.write(f"{user.first_name} ({user.id}):\n{suggestion}\n\n")

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"📩 Новое предложение от @{user.username or user.first_name}:\n\n{suggestion}"
        )
    except:
        pass

    await update.message.reply_text("Спасибо! Твоя рекомендация отправлена на модерацию 👍", reply_markup=main_keyboard)
    return ConversationHandler.END


# /supportus
async def supportus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💸Оплата", url="https://www.tinkoff.ru/rm/r_ppdlToypds.uMVYStqMlk/A7AVK34316")]
    ])
    await update.message.reply_text(
        "Спасибо, что хочешь поддержать проект!\n"
        "Любое пожертвование поможет нам развиваться 🙌",
        reply_markup=keyboard
    )


async def support_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = update.message.text
    await update.message.reply_text(f"Ссылка на оплату: https://example.com/pay?sum={amount}",
                                    reply_markup=main_keyboard)
    return ConversationHandler.END


# /invitation
async def process_invite_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo = update.message.photo[-1]  # самое большое качество

    caption = (
        f"📥 Заявка на доступ в чат\n"
        f"👤 Пользователь: @{user.username or user.first_name}\n"
        f"🆔 ID: {user.id}"
    )

    try:
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=photo.file_id,
            caption=caption
        )
    except Exception as e:
        print("Ошибка отправки администратору:", e)

    await update.message.reply_text(
        "✅ Спасибо! Скриншот отправлен на модерацию. Мы свяжемся с тобой после подтверждения.")
    return ConversationHandler.END


async def invitation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💸Оплата", url="https://www.tinkoff.ru/rm/r_ppdlToypds.uMVYStqMlk/A7AVK34316")]
    ])
    await update.message.reply_text(
        "В нашем закрытом чате ты сможешь:\n"
        "- Находить попутчиков по Москве\n"
        "- Обсуждать интересные места\n"
        "- Делиться впечатлениями и фото\n\n"
        "Доступ стоит 99 рублей. Для оплаты нажми кнопку ниже, а затем отправь скриншот для подтверждения перевода. Ожидание не больше 12 часов!",
        reply_markup=keyboard
    )
    return INVITE_WAIT_PHOTO


# Общий выход из диалога
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Диалог прерван. Выбери команду на клавиатуре 👇", reply_markup=main_keyboard)
    return ConversationHandler.END


# main
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CallbackQueryHandler(callback_handler))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("add", add_place)],
        states={SUGGEST_PLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_suggestion)]},
        fallbacks=[MessageHandler(filters.COMMAND, cancel)]
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("supportus", supportus)],
        states={DONATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, support_response)]},
        fallbacks=[MessageHandler(filters.COMMAND, cancel)]
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("help", help_command)],
        states={
            STATION_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_station)],
            ACTIVITY_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_activity)],
        },
        fallbacks=[MessageHandler(filters.COMMAND, cancel)]
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("invitation", invitation)],
        states={
            INVITE_WAIT_PHOTO: [MessageHandler(filters.PHOTO, process_invite_photo)]
        },
        fallbacks=[MessageHandler(filters.COMMAND, cancel)]
    ))

    await app.initialize()
    await app.start()
    bot_info = await app.bot.get_me()
    print("✅ Бот запущен!")
    print(f"🔗 https://t.me/{bot_info.username}")
    await app.updater.start_polling()
    await asyncio.Event().wait()


# запуск
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())