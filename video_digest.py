import asyncio
from google import genai
from telegram import Bot
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
import subprocess
import os
import json

TELEGRAM_BOT_TOKEN = "8462003119:AAEjQU5Tk8Zyo2T36BnmpydAV7zSmdfJz6o"
TELEGRAM_CHANNEL = "@ukrpulsenew"
GEMINI_API_KEY = "VSTAV_SVIY_KLYUCH"
DIGEST_FILE = "daily_digest.json"

client_genai = genai.Client(api_key=GEMINI_API_KEY)
bot = Bot(token=TELEGRAM_BOT_TOKEN)

def load_digest():
    if os.path.exists(DIGEST_FILE):
        with open(DIGEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def create_script(news_list):
    news_text = "\n".join([f"{i+1}. {n}" for i, n in enumerate(news_list[:7])])
    prompt = """Напиши сценарій для відеовипуску новин українською мовою.
Стиль: професійний діктор українського телебачення, впевнений голос.
Структура:
- Вступ: Добрий вечір! З вами УкрПульс і головні новини дня.
- Кожна новина 2-3 речення
- Завершення: Це були головні новини. Підписуйтесь на УкрПульс. До зустрічі!
Без зірочок, без дужок, без символів форматування. Тільки живий текст.
Новини:
""" + news_text
    try:
        response = client_genai.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return response.text.replace("**", "").replace("__", "").replace("*", "")
    except Exception as e:
        print(f"Gemini error: {e}")
        return None

def create_audio(text):
    tts = gTTS(text=text, lang='uk')
    tts.save("digest_audio.mp3")
    return "digest_audio.mp3"

def create_slide(text, index, total):
    w, h = 1280, 720
    img = Image.new('RGB', (w, h), color=(252, 252, 252))
    draw = ImageDraw.Draw(img)
    try:
        font_logo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        font_num = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
        font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except:
        try:
            font_logo = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", 36)
            font_num = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", 80)
            font_text = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans.ttf", 28)
            font_small = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans.ttf", 20)
        except:
            font_logo = ImageFont.load_default()
            font_num = font_logo
            font_text = font_logo
            font_small = font_logo
    draw.rectangle([(0, 0), (w, 3)], fill=(30, 30, 30))
    draw.text((40, 18), "UKRPULSE", fill=(30, 30, 30), font=font_logo)
    draw.rectangle([(270, 26), (273, 54)], fill=(200, 200, 200))
    draw.text((290, 18), "NEWS", fill=(160, 160, 160), font=font_logo)
    draw.line([(40, 65), (w - 40, 65)], fill=(235, 235, 235), width=1)
    draw.text((40, 85), str(index).zfill(2), fill=(230, 230, 230), font=font_num)
    draw.rectangle([(40, 178), (110, 181)], fill=(30, 30, 30))
    y = 200
    line = ""
    for word in text.split():
        test = line + " " + word if line else word
        if len(test) > 55:
            draw.text((40, y), line, fill=(40, 40, 40), font=font_text)
            y += 38
            line = word
            if y > 580:
                draw.text((40, y), "...", fill=(160, 160, 160), font=font_text)
                break
        else:
            line = test
    if line and y <= 580:
        draw.text((40, y), line, fill=(40, 40, 40), font=font_text)
    draw.line([(40, h - 65), (w - 40, h - 65)], fill=(235, 235, 235), width=1)
    draw.text((40, h - 48), "t.me/ukrpulsenew", fill=(160, 160, 160), font=font_small)
    draw.text((w - 220, h - 48), f"NOVYNA {index} Z {total}", fill=(160, 160, 160), font=font_small)
    draw.rectangle([(0, h - 3), (w, h)], fill=(30, 30, 30))
    fname = f"slide_{index}.jpg"
    img.save(fname, format='JPEG', quality=95)
    return fname

def create_video(slides, audio):
    result = subprocess.run(["ffprobe", "-i", audio, "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"], capture_output=True, text=True)
    dur = float(result.stdout.strip())
    sd = dur / len(slides)
    parts = []
    for i, s in enumerate(slides):
        part = f"part_{i}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", s, "-t", str(sd), "-vf", "format=yuv420p,scale=1280:720", "-c:v", "libx264", "-preset", "ultrafast", "-r", "25", part])
        parts.append(part)
    with open("parts.txt", "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "parts.txt", "-i", audio, "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-shortest", "digest.mp4"])
    for p in parts:
        if os.path.exists(p):
            os.remove(p)
    if os.path.exists("parts.txt"):
        os.remove("parts.txt")
    return "digest.mp4"

async def run():
    print("Creating video digest...")
    news = load_digest()
    if not news or len(news) < 3:
        print("Not enough news")
        return
    news = news[-7:]
    print(f"News count: {len(news)}")
    script = create_script(news)
    if not script:
        return
    print("Script ready")
    audio = create_audio(script)
    print("Audio ready")
    slides = [create_slide(n, i+1, len(news)) for i, n in enumerate(news)]
    print("Slides ready")
    video = create_video(slides, audio)
    print("Video ready")
    if os.path.exists(video) and os.path.getsize(video) > 0:
        with open(video, "rb") as f:
            await bot.send_video(chat_id=TELEGRAM_CHANNEL, video=f, caption="📺 ВІДЕО-ДАЙДЖЕСТ ДНЯ\n\n🇺🇦 <b>УкрПульс</b>", parse_mode="HTML")
        print("Published!")
    else:
        print("Error: video not created")
    for s in slides:
        if os.path.exists(s):
            os.remove(s)
    for tmp in ["digest_audio.mp3", "digest.mp4"]:
        if os.path.exists(tmp):
            os.remove(tmp)

if __name__ == "__main__":
    asyncio.run(run())