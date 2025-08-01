from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import os, json

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID") or "123456789"  # Remplace par ton vrai ID admin ou mets-le dans Render

main_buttons = ["KF", "BELO", "SOULAN", "KfClone", "Filtres", "Géolocalisation"]
sub_buttons = ["SMS", "CONTACTS", "Historiques appels", "iMessenger", "Facebook Messenger", "Audio", "Vidéo", "Documents", "Autres"]

# Chargement/Sauvegarde JSON persistante
FILES_DB_PATH = "files.json"
def load_files():
    try:
        with open(FILES_DB_PATH, "r") as f:
            return json.load(f)
    except:
        return {}

def save_files():
    with open(FILES_DB_PATH, "w") as f:
        json.dump(files_db, f, indent=2)

files_db = load_files()

def get_main_menu():
    keyboard = [[InlineKeyboardButton(text=btn, callback_data=btn)] for btn in main_buttons]
    return InlineKeyboardMarkup(keyboard)

def get_sub_menu():
    keyboard = [[InlineKeyboardButton(text=sub, callback_data=sub)] for sub in sub_buttons]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.first_name or "utilisateur"
    await update.message.reply_text(
        f"👋 Bienvenue {username} dans le bot MyTelegramBot. Choisissez une option :",
        reply_markup=get_main_menu()
    )

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
            await query.message.reply_text("📍 Merci de partager votre position :", reply_markup=keyboard)
        else:
            context.user_data["current_category"] = data
            await query.message.reply_text(f"📂 Vous avez choisi {data}. Voici les sous-catégories disponibles :", reply_markup=get_sub_menu())
    elif data in sub_buttons:
        context.user_data["current_subcategory"] = data
        await query.message.reply_text(f"✅ Sous-catégorie sélectionnée : {data}\nVous pouvez maintenant envoyer un fichier.")
    else:
        await query.message.reply_text(f"✅ Vous avez sélectionné : {data}")

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
        await update.message.reply_text(f"📍 Localisation reçue :\nLatitude: {lat}\nLongitude: {lon}")

async def upload_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("⛔ Tu ne peux pas envoyer de fichiers.")
        return

    if not context.user_data.get("current_category") or not context.user_data.get("current_subcategory"):
        await update.message.reply_text("❗ Choisis d'abord une catégorie et une sous-catégorie.")
        return

    message = update.message
    file = None
    file_name = "unknown"
    file_type = "inconnu"

    if message.document:
        file = message.document
        file_name = file.file_name
        file_type = "document"
    elif message.audio:
        file = message.audio
        file_name = file.file_name or "audio.mp3"
        file_type = "audio"
    elif message.video:
        file = message.video
        file_name = file.file_name or "video.mp4"
        file_type = "video"
    elif message.photo:
        file = message.photo[-1]
        file_name = f"photo_{file.file_id}.jpg"
        file_type = "photo"
    elif message.voice:
        file = message.voice
        file_name = f"voice_{file.file_id}.ogg"
        file_type = "voice"
    elif message.animation:
        file = message.animation
        file_name = file.file_name or "animation.gif"
        file_type = "animation"
    elif message.sticker:
        file = message.sticker
        file_name = f"sticker_{file.file_id}.webp"
        file_type = "sticker"

    if not file:
        await message.reply_text("⚠️ Fichier non pris en charge.")
        return

    file_id = file.file_id
    cat = context.user_data["current_category"]
    sub = context.user_data["current_subcategory"]

    if cat not in files_db:
        files_db[cat] = {}
    if sub not in files_db[cat]:
        files_db[cat][sub] = []

    files_db[cat][sub].append({"file_id": file_id, "file_name": file_name, "file_type": file_type})
    save_files()

    await message.reply_text(f"✅ Fichier « {file_name} » enregistré dans {cat}/{sub}.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(filters.ALL, upload_file_handler))

    print("✅ Bot en cours d'exécution...")
    app.run_polling()
