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

def create_script_and_slides(news_list):
    news_text = "\n".join([f"{i+1}. {n}" for i, n in enumerate(news_list[:7])])
    prompt = """Створи сценарій відеовипуску новин українською.
Для КОЖНОЇ новини напиши два рядки:
СЛАЙД: короткий текст для екрану (1 речення, максимум 15 слів)
ГОЛОС: текст для диктора (2-3 речення, розгорнуто)

Почни з:
СЛАЙД: Головні новини дня
ГОЛОС: Добрий вечір! З вами УкрПульс і головні новини дня.

Заверши:
СЛАЙД: Підписуйтесь на УкрПульс
ГОЛОС: Це були головні новини. Підписуйтесь на УкрПульс. До зустрічі!

ВАЖЛИВО: текст СЛАЙД повинен бути коротким заголовком новини.
Текст ГОЛОС повинен детально розповідати цю саму новину.
Без зірочок, без символів форматування.
Новини:
""" + news_text
    try:
        response = client_genai.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text = response.text.replace("**", "").replace("__", "").replace("*", "")
        slides_text = []
        voice_text = ""
        for line in text.split("\n"):
            line = line.strip()
            if line.upper().startswith("СЛАЙД:") or line.upper().startswith("СЛАЙД :"):
                slides_text.append(line.split(":", 1)[1].strip())
            elif line.upper().startswith("ГОЛОС:") or line.upper().startswith("ГОЛОС :"):
                voice_text += line.split(":", 1)[1].strip() + " "
        return slides_text, voice_text.strip()
    except Exception as e:
        print(f"Gemini error: {e}")
        return None, None

def create_audio(text):
    tts = gTTS(text=text, lang='uk')
    tts.save("digest_audio.mp3")
    return "digest_audio.mp3"

def create_slide(text, index, total):
    w, h = 1280, 720
    img = Image.new('RGB', (w, h), color=(252, 252, 252))
    draw = ImageDraw.Draw(img)
    try:
        font_logo = ImageFont.truetype("/home/sb619725/NotoSans-Regular.ttf", 72)
        font_num = ImageFont.truetype("/home/sb619725/NotoSans-Regular.ttf", 160)
        font_text = ImageFont.truetype("/home/sb619725/NotoSans-Regular.ttf", 52)
        font_bottom = ImageFont.truetype("/home/sb619725/NotoSans-Regular.ttf", 36)
    except:
        font_logo = ImageFont.load_default()
        font_num = font_logo
        font_text = font_logo
        font_bottom = font_logo
    draw.rectangle([(0, 0), (w, 6)], fill=(0, 87, 183))
    draw.text((40, 15), "UKRPULSE", fill=(20, 20, 20), font=font_logo)
    draw.rectangle([(470, 30), (476, 78)], fill=(0, 87, 183))
    draw.text((500, 15), "NEWS", fill=(0, 87, 183), font=font_logo)
    draw.line([(40, 100), (w - 40, 100)], fill=(220, 220, 220), width=2)
    draw.text((40, 110), str(index).zfill(2), fill=(235, 235, 235), font=font_num)
    draw.rectangle([(40, 290), (200, 298)], fill=(0, 87, 183))
    y = 320
    line = ""
    for word in text.split():
        test = line + " " + word if line else word
        if len(test) > 28:
            draw.text((40, y), line, fill=(30, 30, 30), font=font_text)
            y += 65
            line = word
            if y > 560:
                break
        else:
            line = test
    if line and y <= 560:
        draw.text((40, y), line, fill=(30, 30, 30), font=font_text)
    draw.rectangle([(0, h - 80), (w, h - 74)], fill=(0, 87, 183))
    draw.rectangle([(0, h - 74), (w, h)], fill=(20, 20, 20))
    draw.text((40, h - 65), "t.me/ukrpulsenew", fill=(255, 255, 255), font=font_bottom)
    draw.text((w - 420, h - 65), f"НОВИНА {index} З {total}", fill=(0, 87, 183), font=font_bottom)
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
    slides_text, voice_text = create_script_and_slides(news)
    if not slides_text or not voice_text:
        return
    print(f"Script ready: {len(slides_text)} slides")
    audio = create_audio(voice_text)
    print("Audio ready")
    slides = [create_slide(t, i+1, len(slides_text)) for i, t in enumerate(slides_text)]
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