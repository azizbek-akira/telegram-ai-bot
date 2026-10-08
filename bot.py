import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# Serverdagi sozlamalardan kalitlarni o'qish
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

groq_client = Groq(api_key=GROQ_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Menga matn, ovozli xabar yoki audio fayl yuboring. "
        "Groq AI va Whisper uni zudlik bilan tahlil qilib beradi!"
    )

async def analyze_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    status_msg = await update.message.reply_text("⚡ Llama 3.1 tahlil qilmoqda...")

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Siz aqlli va dostona yordamchisiz.Siz foydalanuvchining savollariga aniq va tushunarli javob berasiz.javoblaringiz qisqa boladi, agar foydalanuvchi sizdan toliq javobini so'rasa,siz unga aniq malumotlar va misollar bilan tushuntirib berasiz."},
                {"role": "user", "content": user_text}
            ],
            model="openai/gpt-oss-20b",
            temperature=0.6,
        )

        ai_response = chat_completion.choices[0].message.content
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text=ai_response
        )
    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text=f"❌xatolik turi:{e}"
        )

async def process_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("🎙 Audio qabul qilindi. Matnga o'girilmoqda...")
    file_path = "temp_voice.ogg"

    try:
        voice_or_audio = update.message.voice or update.message.audio
        telegram_file = await context.bot.get_file(voice_or_audio.file_id)
        await telegram_file.download_to_drive(file_path)

        with open(file_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(file_path, audio_file.read()),
                model="whisper-large-v3",
                prompt="O'zbek tilidagi audio",
                response_format="text"
            )

        transcribed_text = str(transcription).strip()

        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text=f"📝 Matn:\n_{transcribed_text}_\n\n⚡ Tahlil qilinmoqda..."
        )

        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Audio matnini tahlil qiling va asosiy mazmunini chiqarib bering."},
                {"role": "user", "content": transcribed_text}
            ],
            model="openai/gpt-oss-20b",
            temperature=0.6,
        )

        analysis = chat_completion.choices[0].message.content
        final_text = f"🎯 Transkripsiya:\n{transcribed_text}\n\n📊 Tahlil:\n{analysis}"

        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text=final_text
        )

    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text="❌ Audioni qayta ishlashda xatolik yuz berdi."
        )
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, process_voice))
    app.run_polling()