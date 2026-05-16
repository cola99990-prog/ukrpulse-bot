import asyncio
from google import genai
from telegram import Bot
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
import subprocess
import os
import json
import time

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
    prompt = f"""Напиши сценарій для короткого відеовипуску новин (60 секунд) українською мовою.
Формат: привітання, потім кожна новина 1-2 реченнями, завершення.
Стиль: професійний диктор новин.
Починай з "Доброго вечора, з вами УкрПульс."
Заверши словами "Слідкуйте за нами, до зустрічі!"
Не використовуй * ** _ __ для форматування.

Новини дня:
{news_text}"""
    try:
        response = client_genai.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        result = response.text.replace("**", "").replace("__", "")
        return result
    except Exception as e:
        print(f"Помилка Gemini: {e}")
        return None

def create_audio(text, filename="digest_audio.mp3"):
    tts = gTTS(text=text, lang='uk')
    tts.save(filename)
    return filename

def create_slide(text, index, total, width=1080, height=1920):
    img = Image.new('RGB', (width, height), color=(10, 10, 40))
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()
        font_small = ImageFont.load_default()
    draw.rectangle([(0, 0), (width, 120)], fill=(200, 30, 30))
    draw.text((40, 30), "UkrPulse NEWS", fill="white", font=font_title)
    draw.text((width - 200, 35), f"{index}/{total}", fill="white", font=font_title)
    y = 200
    words = text.split()
    line = ""
    for word in words:
        test_line = line + " " + word if line else word
        if len(test_line) > 35:
            draw.text((60, y), line, fill="white", font=font_text)
            y += 50
            line = word
        else:
            line = test_line
    if line:
        draw.text((60, y), line, fill="white", font=font_text)
    draw.rectangle([(0, height - 80), (width, height)], fill=(200, 30, 30))
    draw.text((40, height - 60), "t.me/ukrpulsenew", fill="white", font=font_small)
    draw.text((width - 300, height - 60), "UkrPulse 2026", fill="white", font=font_small)
    filename = f"slide_{index}.png"
    img.save(filename)
    return filename

def create_video(slides, audio_file, output="digest_video.mp4"):
    duration_cmd = f"ffprobe -i {audio_file} -show_entries format=duration -v quiet -of csv=p=0"
    result = subprocess.run(duration_cmd.split(), capture_output=True, text=True)
    total_duration = float(result.stdout.strip())
    slide_duration = total_duration / len(slides)
    list_file = "slides_list.txt"
    with open(list_file, "w") as f:
        for slide in slides:
            f.write(f"file '{slide}'\n")
            f.write(f"duration {slide_duration}\n")
        f.write(f"file '{slides[-1]}'\n")
    cmd = f"ffmpeg -y -f concat -safe 0 -i {list_file} -i {audio_file} -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest -vf scale=1080:1920 {output}"
    subprocess.run(cmd.split())
    return output

async def create_and_publish_digest():
    print("Створюю відео-дайджест...")
    news = load_digest()
    if not news or len(news) < 3:
        print("Недостатньо новин для дайджесту")
        return
    news = news[-7:]
    print(f"Новин для дайджесту: {len(news)}")
    print("Створюю сценарій...")
    script = create_script(news)
    if not script:
        return
    print(f"Сценарій:\n{script}\n")
    print("Створюю аудіо...")
    audio = create_audio(script)
    print("Створюю слайди...")
    slides = []
    for i, item in enumerate(news):
        slide = create_slide(item, i + 1, len(news))
        slides.append(slide)
    print("Створюю відео...")
    video = create_video(slides, audio)
    print("Публікую в Telegram...")
    with open(video, "rb") as f:
        await bot.send_video(
            chat_id=TELEGRAM_CHANNEL,
            video=f,
            caption="📺 ВІДЕО-ДАЙДЖЕСТ ДНЯ\n\n🇺🇦 <b>УкрПульс</b>",
            parse_mode="HTML"
        )
    print("✅ Відео-дайджест опубліковано!")
    for s in slides:
        os.remove(s)
    os.remove(audio)
    os.remove("slides_list.txt")

if __name__ == "__main__":
    asyncio.run(create_and_publish_digest())