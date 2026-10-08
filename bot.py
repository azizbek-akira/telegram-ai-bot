import os
import telebot
import google.generativeai as genai
from PIL import Image
from io import BytesIO
from duckduckgo_search import DDGS

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Google Gemini API sozlamasi
genai.configure(api_key=GEMINI_API_KEY)

# Aniq va barqaror ishlaydigan Gemini modeli
model = genai.GenerativeModel('gemini-pro')
vision_model = genai.GenerativeModel('gemini-pro-vision')

user_chats = {}
unique_users = set()
total_messages = 0

def search_web(query):
    try:
        results = DDGS().text(query, max_results=3)
        if results:
            context = "\n".join([f"- {r.get('title', '')}: {r.get('body', '')}" for r in results])
            return context
    except Exception as e:
        print(f"Qidiruvda xatolik: {e}")
    return None

@bot.message_handler(commands=['start'])
def send_welcome(message):
    unique_users.add(message.from_user.id)
    welcome_text = (
        "Salom! Men Google Gemini AI asosida ishlaydigan yordamchingizman. 🤖\n\n"
        "Menga savollaringizni yuborishingiz yoki internetdan ma'lumot qidirishni so'rashingiz mumkin!"
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

    if user_id not in user_chats:
        user_chats[user_id] = model.start_chat(history=[])

    try:
        chat = user_chats[user_id]
        response = chat.send_message(user_text + web_context)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Xatolik yuz berdi: {e}")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    global total_messages
    unique_users.add(message.from_user.id)
    total_messages += 1

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        image = Image.open(BytesIO(downloaded_file))
        caption = message.caption if message.caption else "Ushbu rasmni tahlil qiling."

        response = vision_model.generate_content([caption, image])
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Rasmni tahlil qilishda xatolik: {e}")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)