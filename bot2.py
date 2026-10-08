import os
import telebot
from groq import Groq

# Render Environment Variables bo'limidan olinadi
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# Foydalanuvchilar suhbat xotirasini saqlash lug'ati
user_history = {}

SYSTEM_PROMPT = (
    "Siz aqlli va do'stona AI yordamchisiz. Foydalanuvchi savollariga "
    "o'zbek tilida aniq, tushunarli va ravon javob berasiz."
)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    # Start bosilganda ushbu foydalanuvchi xotirasini yangilaymiz
    user_history[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    welcome_text = (
        "Salom! Men suhbat xotirasiga ega AI yordamchingizman. 🤖\n\n"
        "Siz bilan avvalgi gaplashgan xabarlarimizni eslab qolaman.\n"
        "Suhbatni noldan boshlash uchun xohlagan vaqtingizda /clear buyrug'ini yuboring."
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['clear'])
def clear_history(message):
    user_id = message.from_user.id
    # Suhbat xotirasini tozalash
    user_history[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    bot.reply_to(message, "🧹 Suhbat xotirasi tozalandi! Yangi suhbat boshlashimiz mumkin.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    user_text = message.text

    # Agar foydalanuvchi lug'atda bo'lmasa, unga yangi xotira ro'yxatini ochamiz
    if user_id not in user_history:
        user_history[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Foydalanuvchi xabarini xotiraga qo'shamiz
    user_history[user_id].append({"role": "user", "content": user_text})

    # Xotira hajmi juda kattalashib ketmasligi uchun oxirgi 10 ta xabarni saqlaymiz
    if len(user_history[user_id]) > 11:
        user_history[user_id] = [user_history[user_id][0]] + user_history[user_id][-10:]

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Siz so'ragan model bo'yicha Groq API so'rovi
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=user_history[user_id]
        )
        
        bot_reply = response.choices[0].message.content
        
        # AI javobini ham xotiraga qo'shamiz
        user_history[user_id].append({"role": "assistant", "content": bot_reply})

        bot.reply_to(message, bot_reply)
    except Exception as e:
        bot.reply_to(message, f"Xatolik yuz berdi: {e}")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)