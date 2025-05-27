from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import os

TOKEN = os.getenv("BOT_TOKEN")

main_buttons = ["KF", "BELO", "SOULAN", "KfClone", "Filtres", "Géolocalisation"]
sub_buttons = ["SMS", "CONTACTS", "Historiques appels", "iMessenger", "Facebook Messenger", "Audio", "Vidéo", "Documents", "Autres"]

def get_main_menu():
    keyboard = [[InlineKeyboardButton(text=btn, callback_data=btn)] for btn in main_buttons]
    return InlineKeyboardMarkup(keyboard)

def get_sub_menu():
    keyboard = [[InlineKeyboardButton(text=sub, callback_data=sub)] for sub in sub_buttons]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bienvenue dans le bot MyTelegramBot. Choisissez une option :", reply_markup=get_main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data in main_buttons:
        if data == "Géolocalisation":
            keyboard = ReplyKeyboardMarkup(
                [[KeyboardButton("Envoyer ma position", request_location=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await query.message.reply_text("Merci de partager votre position :", reply_markup=keyboard)
        else:
            await query.message.reply_text(f"Vous avez choisi {data}. Voici les options disponibles :", reply_markup=get_sub_menu())
    else:
        await query.message.reply_text(f"Vous avez sélectionné : {data}")

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
        await update.message.reply_text(f"Localisation reçue :\nLatitude: {lat}\nLongitude: {lon}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))

    print("Bot en cours d'exécution...")
    app.run_polling()