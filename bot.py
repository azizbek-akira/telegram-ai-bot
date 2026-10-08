import os
import base64
from io import BytesIO
import telebot
from groq import Groq
from gtts import gTTS
from duckduckgo_search import DDGS

# Environment o'zgaruvchilarini olish
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# Global o'zgaruvchilar
user_history = {}
unique_users = set()
total_messages = 0

SYSTEM_PROMPT = (
    "Siz aqlli va do'stona yordamchisiz. Siz foydalanuvchining savollariga "
    "aniq va tushunarli javob berasiz. Javoblaringiz qisqa bo'ladi, agar "
    "foydalanuvchi sizdan to'liq javobini so'rasa, siz unga aniq ma'lumotlar "
    "va misollar bilan tushuntirib berasiz."
)

# Internetdan qidirish funksiyasi
def search_web(query):
    try:
        results = DDGS().text(query, max_results=3)
        if results:
            context = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
            return context
    except Exception as e:
        print(f"Qidiruvda xatolik: {e}")
    return None

# -------------------------------------------------------------
# 1. /start va /stats Buyruqlari
# -------------------------------------------------------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    unique_users.add(message.from_user.id)
    welcome_text = (
        "Salom! Men sizning aqlli yordamchingizman. 🤖\n\n"
        "Menga matn yuborishingiz, rasm jo'natishingiz, ovozli xabar berishingiz "
        "yoki internetdan ma'lumot qidirishni so'rashingiz mumkin!"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['stats'])
def show_stats(message):
    stats_text = (
        "📊 **Bot Statistikasi:**\n\n"
        f"👤 Jami foydalanuvchilar: {len(unique_users)}\n"
        f"💬 Jami qayta ishlangan xabarlar: {total_messages}"
    )
    bot.reply_to(message, stats_text, parse_mode="Markdown")

# -------------------------------------------------------------
# 2. Matnli Xabarlar va Internet Qidiruvi
# -------------------------------------------------------------
@bot.message_handler(content_types=['text'])
def handle_text(message):
    global total_messages
    user_id = message.from_user.id
    user_text = message.text

    unique_users.add(user_id)
    total_messages += 1

    # Internetdan qidirish kerakligini aniqlash
    search_keywords = ["qidir", "yangilik", "kim", "nima", "ob-havo", "kurs", "bugun", "internetdan"]
    needs_search = any(keyword in user_text.lower() for keyword in search_keywords)

    web_context = ""
    if needs_search:
        search_result = search_web(user_text)
        if search_result:
            web_context = f"\n\n[Internetdan topilgan ma'lumotlar]:\n{search_result}"

    # Foydalanuvchi xotirasini yaratish
    if user_id not in user_history:
        user_history[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    prompt_content = user_text + web_context
    user_history[user_id].append({"role": "user", "content": prompt_content})

    if len(user_history[user_id]) > 11:
        user_history[user_id] = [user_history[user_id][0]] + user_history[user_id][-10:]

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=user_history[user_id]
        )
        bot_reply = response.choices[0].message.content
        user_history[user_id].append({"role": "assistant", "content": bot_reply})

        bot.reply_to(message, bot_reply)
    except Exception as e:
        bot.reply_to(message, f"Xatolik yuz berdi: {e}")

# -------------------------------------------------------------
# 3. Rasmlarni Tahlil Qilish (Vision AI)
# -------------------------------------------------------------
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    global total_messages
    unique_users.add(message.from_user.id)
    total_messages += 1

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded_file).decode('utf-8')
        
        caption = message.caption if message.caption else "Ushbu rasmni tahlil qiling va qisqa ta'rif bering."

        response = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": caption},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ]
        )
        bot.reply_to(message, response.choices[0].message.content)
    except Exception as e:
        bot.reply_to(message, f"Rasmni tahlil qilishda xatolik: {e}")

# -------------------------------------------------------------
# 4. Ovozli Xabar Va Ovozli Javob Qaytarish (Text-to-Speech)
# -------------------------------------------------------------
@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    global total_messages
    unique_users.add(message.from_user.id)
    total_messages += 1

    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        voice_filename = "user_voice.ogg"
        with open(voice_filename, 'wb') as f:
            f.write(downloaded_file)

        with open(voice_filename, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file,
                response_format="text"
            )

        if os.path.exists(voice_filename):
            os.remove(voice_filename)

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcription}
            ]
        )
        bot_reply = response.choices[0].message.content

        tts = gTTS(text=bot_reply, lang='uz')
        reply_voice_path = "reply_voice.ogg"
        tts.save(reply_voice_path)

        with open(reply_voice_path, 'rb') as voice:
            bot.send_voice(message.chat.id, voice, caption=f"💬 **Tushunilgan matn:** {transcription}")

        if os.path.exists(reply_voice_path):
            os.remove(reply_voice_path)

    except Exception as e:
        bot.reply_to(message, f"Ovozli xabarni qayta ishlashda xatolik: {e}")

# Botni ishga tushirish
if __name__ == "__main__":
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)