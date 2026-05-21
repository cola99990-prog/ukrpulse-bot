from google import genai
from telegram import Bot
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
import asyncio
import schedule
import time
import json
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', handlers=[logging.FileHandler("ukrpulse.log", encoding="utf-8"), logging.StreamHandler()])
log = logging.info

TELEGRAM_BOT_TOKEN = "8462003119:AAEjQU5Tk8Zyo2T36BnmpydAV7zSmdfJz6o"
TELEGRAM_CHANNEL = "@ukrpulsenew"
GEMINI_API_KEY = "VSTAV_SVIY_KLYUCH"
TELEGRAM_API_ID = 30993000
TELEGRAM_API_HASH = "f2cdb7e84879ea9b285158bc20002a85"
PUBLISHED_FILE = "published_ids.json"
PUBLISHED_TEXTS_FILE = "published_texts.json"
DIGEST_FILE = "daily_digest.json"
ORIGINALS_FILE = "original_news.json"

SOURCE_CHANNELS = ["@ukrainenow","@uniannet","@ukrpravda_news","@suspilne_news","@kyivindependent","@radiosvoboda","@truexanewsua","@dmytrogordon_official","@Pravda_Gerashchenko","@novini_ukrtg"]
SPAM_WORDS = ["реклама","розіграш","промокод","знижка","підписуйся","переходь за посиланням","giveaway","promo","sponsor","подписывайся","розыгрыш","скидка"]
DUPE_NAMES = ["путін","зеленськ","трамп","тайван","придністров","рязан","харків","одес","дніпр","москв","білорус","лукашенк","nato","нато","кабмін","рада","мобілізац","тривог","дрон","ракет","обстріл","шаман","свр","розвідк"]

client_genai = genai.Client(api_key=GEMINI_API_KEY)
bot = Bot(token=TELEGRAM_BOT_TOKEN)

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

published_ids = set(load_json(PUBLISHED_FILE))
published_texts = load_json(PUBLISHED_TEXTS_FILE)
original_news = load_json(ORIGINALS_FILE)
daily_news = load_json(DIGEST_FILE)

if len(published_ids) > 5000:
    published_ids = set(list(published_ids)[-2000:])
    save_json(PUBLISHED_FILE, list(published_ids))
log(f"Завантажено {len(published_ids)} ID та {len(original_news)} оригіналів")

def is_spam(text):
    text_lower = text.lower()
    for word in SPAM_WORDS:
        if word in text_lower:
            return True
    if text_lower.count("http") > 2:
        return True
    return False

def is_duplicate(text):
    global original_news
    text_lower = text.lower().strip()
    words = set(text_lower.split())
    if len(words) < 3:
        return True
    for old_text in original_news[-1000:]:
        old_lower = old_text.lower().strip()
        old_words = set(old_lower.split())
        if len(old_words) == 0:
            continue
        common = words & old_words
        similarity = len(common) / min(len(words), len(old_words))
        if similarity > 0.3:
            return True
    names = []
    for name in DUPE_NAMES:
        if name in text_lower:
            names.append(name)
    if names:
        for old_text in original_news[-1000:]:
            old_lower = old_text.lower()
            matches = sum(1 for n in names if n in old_lower)
            if matches >= 2:
                return True
    return False

def get_category(text):
    text_lower = text.lower()
    if any(w in text_lower for w in ["зсу","фронт","обстріл","ракет","дрон","удар","бойов","окупант","ппо","тривога","загинул"]):
        return "⚔️ Війна"
    if any(w in text_lower for w in ["зеленськ","рада","кабмін","закон","депутат","парламент","уряд","путін","трамп"]):
        return "🏛 Політика"
    if any(w in text_lower for w in ["долар","гривн","економік","бюджет","інфляц","ціни","тариф"]):
        return "💰 Економіка"
    if any(w in text_lower for w in ["nato","нато","єс","сша","китай","europe","biden","trump","sanctions"]):
        return "🌍 Світ"
    return "📰 Новини"

def get_priority(text):
    text_lower = text.lower()
    if any(w in text_lower for w in ["терміново","блискавка","увага","тривога","зліт","ракет","обстріл","загинул","вибух"]):
        return "urgent"
    if any(w in text_lower for w in ["зеленськ","путін","трамп","наступ","контрнаступ","обмін полонен"]):
        return "high"
    return "normal"

async def rewrite_news(text, source_channel=""):
    category = get_category(text)
    prompt = f"""Ти редактор новинного Telegram-каналу УкрПульс.
Перепиши цю новину українською мовою своїми словами.
Якщо новина англійською або російською — переклади на українську.
Збережи всі факти але змін формулювання.
Категорія: {category}
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
    for attempt in range(3):
        try:
            if attempt > 0:
                wait_time = 30 * (attempt + 1)
                log(f"Спроба {attempt + 1}, чекаю {wait_time} сек...")
                await asyncio.sleep(wait_time)
            else:
                await asyncio.sleep(15)
            response = client_genai.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            result = response.text
            result = result.replace("**", "").replace("__", "")
            if "надайте текст" in result.lower() or "будь ласка" in result.lower() or len(result.strip()) < 30:
                log("Gemini повернув некоректну відповідь, пропускаю")
                return None, category
            return result, category
        except Exception as e:
            log(f"Помилка Gemini (спроба {attempt + 1}): {e}")
    return None, category

def get_source_name(channel):
    sources = {"@ukrainenow":"Ukraine NOW","@uniannet":"УНІАН","@ukrpravda_news":"Українська правда","@suspilne_news":"Суспільне","@kyivindependent":"Kyiv Independent","@radiosvoboda":"Радіо Свобода","@truexanewsua":"Труха","@dmytrogordon_official":"Гордон","@Pravda_Gerashchenko":"Геращенко","@novini_ukrtg":"Новини UA"}
    return sources.get(channel, channel)

async def send_daily_digest():
    global daily_news
    if not daily_news:
        return
    log("Відправляю щоденний дайджест...")
    digest_text = "📋 ДАЙДЖЕСТ ДНЯ\n\n"
    for i, news in enumerate(daily_news[-10:], 1):
        digest_text += f"{i}. {news}\n\n"
    digest_text += "🇺🇦 <b>УкрПульс — підсумки дня</b>"
    try:
        await bot.send_message(chat_id=TELEGRAM_CHANNEL, text=digest_text, parse_mode="HTML")
        log("✅ Дайджест відправлено!")
        daily_news = []
        save_json(DIGEST_FILE, daily_news)
    except Exception as e:
        log(f"Помилка дайджесту: {e}")

async def fetch_and_publish():
    global published_ids, published_texts, daily_news, original_news
    log("Перевіряю нові новини...")
    async with TelegramClient('ukrpulse_session', TELEGRAM_API_ID, TELEGRAM_API_HASH) as client:
        for channel in SOURCE_CHANNELS:
            try:
                history = await client(GetHistoryRequest(peer=channel, limit=2, offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
                log(f"Читаю канал {channel}")
                for message in history.messages:
                    msg_key = f"{channel}_{message.id}"
                    if msg_key in published_ids:
                        continue
                    text = message.text or message.message or ""
                    if len(text) < 50:
                        published_ids.add(msg_key)
                        save_json(PUBLISHED_FILE, list(published_ids))
                        continue
                    if is_spam(text):
                        log(f"Реклама, пропускаю: {text[:50]}")
                        published_ids.add(msg_key)
                        save_json(PUBLISHED_FILE, list(published_ids))
                        continue
                    if is_duplicate(text):
                        log(f"Дублікат, пропускаю: {text[:50]}")
                        published_ids.add(msg_key)
                        save_json(PUBLISHED_FILE, list(published_ids))
                        continue
                    priority = get_priority(text)
                    if priority == "normal":
                        await asyncio.sleep(10)
                    log(f"[{priority.upper()}] Новина: {text[:80]}")
                    rewritten, category = await rewrite_news(text, channel)
                    if not rewritten or len(rewritten.strip()) < 30:
                        published_ids.add(msg_key)
                        save_json(PUBLISHED_FILE, list(published_ids))
                        continue
                    source = get_source_name(channel)
                    caption = f"{rewritten}\n\n{category} | <i>Джерело: {source}</i>\n🇺🇦 <b>УкрПульс</b>"
                    if isinstance(message.media, MessageMediaPhoto):
                        log("Завантажую фото...")
                        photo = await client.download_media(message.media, bytes)
                        await bot.send_photo(chat_id=TELEGRAM_CHANNEL, photo=photo, caption=caption, parse_mode="HTML")
                    elif isinstance(message.media, MessageMediaDocument):
                        mime = message.media.document.mime_type
                        if "video" in mime:
                            log("Завантажую відео...")
                            video = await client.download_media(message.media, bytes)
                            await bot.send_video(chat_id=TELEGRAM_CHANNEL, video=video, caption=caption, parse_mode="HTML")
                        else:
                            await bot.send_message(chat_id=TELEGRAM_CHANNEL, text=caption, parse_mode="HTML")
                    else:
                        await bot.send_message(chat_id=TELEGRAM_CHANNEL, text=caption, parse_mode="HTML")
                    original_news.append(text[:500])
                    if len(original_news) > 2000:
                        original_news = original_news[-1000:]
                    save_json(ORIGINALS_FILE, original_news)
                    headline = rewritten.split("\n")[0][:100]
                    daily_news.append(headline)
                    save_json(DIGEST_FILE, daily_news)
                    published_ids.add(msg_key)
                    published_texts.append(text[:200])
                    if len(published_texts) > 500:
                        published_texts = published_texts[-300:]
                    save_json(PUBLISHED_FILE, list(published_ids))
                    save_json(PUBLISHED_TEXTS_FILE, published_texts)
                    log(f"✅ Опубліковано з {channel}")
                    await asyncio.sleep(30)
            except Exception as e:
                log(f"Помилка при читанні {channel}: {e}")

def send_digest_sync():
    asyncio.run(send_daily_digest())

def run_scheduler():
    schedule.every(3).minutes.do(lambda: asyncio.run(fetch_and_publish()))
    schedule.every().day.at("21:00").do(send_digest_sync)
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    log("🚀 УкрПульс бот запущено!")
    log("Перевірка новин кожні 3 хвилини")
    log("Дайджест дня о 21:00")
    asyncio.run(fetch_and_publish())
    run_scheduler()