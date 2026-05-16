import asyncio
from google import genai
from telegram import Bot
from gtts import gTTS
from PIL import Image, ImageDraw
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
    prompt = "Napishi stsenariy dlya korotkogo videovipusku novin (60 sekund) ukrainskoyu movoyu. Privitannya, kozhna novina 1-2 rechennyami, zavershennya. Stil: profesiyniy diktor. Pochinay: Dobrogo vechora, z vami UkrPuls. Zavershi: Slidkuyte za nami, do zustrichi! Bez * ** _ __. Novini:\n" + news_text
    try:
        response = client_genai.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return response.text.replace("**", "").replace("__", "")
    except Exception as e:
        print(f"Gemini error: {e}")
        return None

def create_audio(text):
    tts = gTTS(text=text, lang='uk')
    tts.save("digest_audio.mp3")
    return "digest_audio.mp3"

def create_slide(text, index, total):
    img = Image.new('RGB', (640, 360), color=(10, 10, 40))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (640, 50)], fill=(200, 30, 30))
    draw.text((10, 15), f"UKRPULSE NEWS  {index}/{total}", fill="white")
    y = 70
    line = ""
    for word in text.split():
        test = line + " " + word if line else word
        if len(test) > 45:
            draw.text((20, y), line, fill="white")
            y += 25
            line = word
        else:
            line = test
    if line:
        draw.text((20, y), line, fill="white")
    draw.rectangle([(0, 320), (640, 360)], fill=(200, 30, 30))
    draw.text((10, 330), "t.me/ukrpulsenew", fill="white")
    fname = f"slide_{index}.jpg"
    img.save(fname, format='JPEG', quality=95)
    return fname

def create_video(slides, audio):
    result = subprocess.run(["ffprobe", "-i", audio, "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"], capture_output=True, text=True)
    dur = float(result.stdout.strip())
    sd = dur / len(slides)
    with open("list.txt", "w") as f:
        for s in slides:
            f.write(f"file '{s}'\nduration {sd}\n")
        f.write(f"file '{slides[-1]}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-i", audio, "-vf", "format=yuv420p", "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-shortest", "digest.mp4"]
    subprocess.run(cmd)
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
            await bot.send_video(chat_id=TELEGRAM_CHANNEL, video=f, caption="📺 VIDEO DIGEST\n\n🇺🇦 <b>UkrPulse</b>", parse_mode="HTML")
        print("Published!")
    else:
        print("Error: video not created")
    for s in slides:
        if os.path.exists(s):
            os.remove(s)
    for tmp in ["digest_audio.mp3", "list.txt"]:
        if os.path.exists(tmp):
            os.remove(tmp)

if __name__ == "__main__":
    asyncio.run(run())