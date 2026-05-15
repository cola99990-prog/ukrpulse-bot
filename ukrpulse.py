import asyncio
from google import genai
from telegram import Bot
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
import schedule
import time
import json
import os

TELEGRAM_BOT_TOKEN = "8462003119:AAEjQU5Tk8Zyo2T36BnmpydAV7zSmdfJz6o"
TELEGRAM_CHANNEL = "@ukrpulsenew"
GEMINI_API_KEY = "AIzaSyBnXh9LpgQKbUZtWFZ-civGwxasyW1pAbg"
TELEGRAM_API_ID = 30993000
TELEGRAM_API_HASH = "f2cdb7e84879ea9b285158bc20002a85"
PUBLISHED_FILE = "published_ids.json"

SOURCE_CHANNELS = [
    "@Pravda_Gerashchenko",
    "@ukrainenow",
    "@uniannet",
    "@ukrpravda_news",
    "@suspilne_news",
    "@kyivindependent",
    "@radiosvoboda",
    "@truexanewsua",
    "@dmytrogordon_official",
    "@novini_ukrtg",
]

client_genai = genai.Client(api_key=GEMINI_API_KEY)
bot = Bot(token=TELEGRAM_BOT_TOKEN)

def load_published_ids():
    if os.path.exists(PUBLISHED_FILE):
        with open(PUBLISHED_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_published_ids(ids):
    with open(PUBLISHED_FILE, "w") as f:
        json.dump(list(ids), f)

published_ids = load_published_ids()
print(f"Завантажено {len(published_ids)} опублікованих новин")

def rewrite_news(text):
    prompt = """Ти редактор новинного Telegram-каналу УкрПульс.
Перепиши цю новину українською мовою своїми словами.
Збережи всі факти але змін формулювання.
Формат відповіді:
- Перший рядок: емодзі + заголовок БЕЗ зірочок і БЕЗ жирного (1 речення)
- Порожній рядок
- Текст новини (2-3 речення)
- Порожній рядок
- Хештеги (2-3 по темі)
ВАЖЛИВО: не використовуй символи * ** _ __ для форматування. Тільки звичайний текст.
Використовуй емодзі на початку заголовку: 🔴 для термінових, ⚡️ для важливих, 📌 для загальних.
Не пиши нічого зайвого крім самої новини.
Новина:
""" + text
    try:
        time.sleep(15)
        response = client_genai.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        result = response.text
        result = result.replace("**", "").replace("__", "")
        return result
    except Exception as e:
        print(f"Помилка Gemini: {e}")
        return None

async def fetch_and_publish():
    global published_ids
    print("Перевіряю нові новини...")
    async with TelegramClient('ukrpulse_session', TELEGRAM_API_ID, TELEGRAM_API_HASH) as client:
        for channel in SOURCE_CHANNELS:
            try:
                history = await client(GetHistoryRequest(peer=channel, limit=2, offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
                print(f"Читаю канал {channel}")
                for message in history.messages:
                    msg_key = f"{channel}_{message.id}"
                    if msg_key in published_ids:
                        print(f"Вже опубліковано, пропускаю")
                        continue

                    text = message.text or message.message or ""
                    if len(text) < 30 and not message.media:
                        continue

                    print(f"Новина: {text[:80]}")

                    rewritten = rewrite_news(text) if text else None
                    caption = f"{rewritten}\n\n🇺🇦 <b>УкрПульс</b>" if rewritten else "🇺🇦 <b>УкрПульс</b>"

                    if isinstance(message.media, MessageMediaPhoto):
                        print("Завантажую фото...")
                        photo = await client.download_media(message.media, bytes)
                        await bot.send_photo(
                            chat_id=TELEGRAM_CHANNEL,
                            photo=photo,
                            caption=caption,
                            parse_mode="HTML"
                        )
                    elif isinstance(message.media, MessageMediaDocument):
                        mime = message.media.document.mime_type
                        if "video" in mime:
                            print("Завантажую відео...")
                            video = await client.download_media(message.media, bytes)
                            await bot.send_video(
                                chat_id=TELEGRAM_CHANNEL,
                                video=video,
                                caption=caption,
                                parse_mode="HTML"
                            )
                        else:
                            if rewritten:
                                await bot.send_message(
                                    chat_id=TELEGRAM_CHANNEL,
                                    text=caption,
                                    parse_mode="HTML"
                                )
                    else:
                        if rewritten:
                            await bot.send_message(
                                chat_id=TELEGRAM_CHANNEL,
                                text=caption,
                                parse_mode="HTML"
                            )

                    published_ids.add(msg_key)
                    save_published_ids(published_ids)
                    print(f"✅ Опубліковано з {channel}")
                    await asyncio.sleep(30)

            except Exception as e:
                print(f"Помилка при читанні {channel}: {e}")

def run_scheduler():
    schedule.every(3).minutes.do(lambda: asyncio.run(fetch_and_publish()))
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    print("🚀 УкрПульс бот запущено!")
    print("Перевірка новин кожні 3 хвилини")
    asyncio.run(fetch_and_publish())
    run_scheduler()