import os
import base64
import telebot
from groq import Groq
from gtts import gTTS
from duckduckgo_search import DDGS

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

user_history = {}
unique_users = set()
total_messages = 0

SYSTEM_PROMPT = (
    "Siz aqlli va do'stona yordamchisiz. Foydalanuvchi savollariga "
    "o'zbek tilida aniq, tushunarli va qisqa javob berishingiz kerak."
)

def search_web(query):
    try:
        results = DDGS().text(query, max_results=3)
        if results:
            return "\n".join([f"- {r.get('title', '')}: {r.get('body', '')}" for r in results])
    except Exception as e:
        print(f"Qidiruvda xatolik: {e}")
    return None

# 1. /start va /stats buyruqlari
@bot.message_handler(commands=['start'])
def send_welcome(message):
    unique_users.add(message.from_user.id)
    welcome_text = (
        "Salom! Men sizning multi-funksional AI yordamchingizman. 🤖\n\n"
        "• Matnli xabarlar va suhbat xotirasi\n"
        "• Rasmlarni tahlil qilish\n"
        "• Ovozli xabarlarga ovozli javob qaytarish\n"
        "• Internetdan ma'lumot qidirish\n"
        "• /stats buyrug'i orqali statistika"
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

# 2. Matnli xabarlar va suhbat xotirasi (Internet qidiruvi bilan)
@bot.message_handler(content_types=['text'])
def handle_text(message):
    global total_messages
    user_id = message.from_user.id
    user_text = message.text

    unique_users.add(user_id)
    total_messages += 1

    search_keywords = ["qidir", "yangilik", "ob-havo", "bugun", "kurs", "internet", "ma'lumot"]
    needs_search = any(keyword in user_text.lower() for keyword in search_keywords)

    web_context = ""
    if needs_search:
        bot.send_chat_action(message.chat.id, 'typing')
        search_result = search_web(user_text)
        if search_result:
            web_context = f"\n\n[Internetdan topilgan so'nggi ma'lumotlar]:\n{search_result}"

    if user_id not in user_history:
        user_history[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    full_prompt = user_text + web_context
    user_history[user_id].append({"role": "user", "content": full_prompt})

    if len(user_history[user_id]) > 11:
        user_history[user_id] = [user_history[user_id][0]] + user_history[user_id][-10:]

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=user_history[user_id]
        )
        bot_reply = response.choices[0].message.content
        user_history[user_id].append({"role": "assistant", "content": bot_reply})

        bot.reply_to(message, bot_reply)
    except Exception as e:
        bot.reply_to(message, f"Xatolik yuz berdi: {e}")

# 3. Rasmlarni tahlil qilish (Vision AI)
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    global total_messages
    unique_users.add(message.from_user.id)
    total_messages += 1

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded_file).decode('utf-8')
        
        caption = message.caption if message.caption else "Ushbu rasmni tahlil qiling va ta'riflab bering."

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

# 4. Ovozli xabar qabul qilish va ovozli javob qaytarish (STT va TTS)
@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    global total_messages
    unique_users.add(message.from_user.id)
    total_messages += 1

    try:
        bot.send_chat_action(message.chat.id, 'record_voice')
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        voice_filename = "user_voice.ogg"
        with open(voice_filename, 'wb') as f:
            f.write(downloaded_file)

        # Whisper audio modeli orqali ovozni matnga o'girish
        with open(voice_filename, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=audio_file,
                response_format="text"
            )

        if os.path.exists(voice_filename):
            os.remove(voice_filename)

        # AI matnli javob tayyorlaydi
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcription}
            ]
        )
        bot_reply = response.choices[0].message.content

        # Javobni gTTS orqali audio faylga o'girib yuborish
        tts = gTTS(text=bot_reply, lang='uz')
        reply_voice_path = "reply_voice.ogg"
        tts.save(reply_voice_path)

        with open(reply_voice_path, 'rb') as voice:
            bot.send_voice(message.chat.id, voice, caption=f"💬 **Tushunilgan matn:** {transcription}")

        if os.path.exists(reply_voice_path):
            os.remove(reply_voice_path)

    except Exception as e:
        bot.reply_to(message, f"Ovozli xabarni qayta ishlashda xatolik: {e}")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)