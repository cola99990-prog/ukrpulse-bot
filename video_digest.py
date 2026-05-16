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
GEMINI_API_KEY = "AIzaSyDM6g-euUKt7S519XXF21U-kvDAx8zGPZk"
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
    img = Image.new('RGB', (320, 240), color=(10, 10, 40))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (320, 30)], fill=(200, 30, 30))
    draw.text((5, 8), f"UKRPULSE {index}/{total}", fill="white")
    y = 40
    line = ""
    for word in text.split():
        test = line + " " + word if line else word
        if len(test) > 30:
            draw.text((10, y), line, fill="white")
            y += 18
            line = word
        else:
            line = test
    if line:
        draw.text((10, y), line, fill="white")
    draw.rectangle([(0, 220), (320, 240)], fill=(200, 30, 30))
    draw.text((5, 224), "t.me/ukrpulsenew", fill="white")
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
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", s, "-t", str(sd), "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-r", "25", part])
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
            await bot.send_video(chat_id=TELEGRAM_CHANNEL, video=f, caption="📺 VIDEO DIGEST\n\n🇺🇦 <b>UkrPulse</b>", parse_mode="HTML")
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