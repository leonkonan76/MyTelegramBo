from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import os, json

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID") or "123456789"  # Remplace par ton ID admin réel

main_buttons = ["KF", "BELO", "SOULAN", "KfClone", "Filtres", "Géolocalisation"]
sub_buttons = ["SMS", "CONTACTS", "Historiques appels", "iMessenger", "Facebook Messenger", "Audio", "Vidéo", "Documents", "Autres"]

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
            # Reset subcategory selection
            context.user_data.pop("current_subcategory", None)
            await query.message.reply_text(f"📂 Vous avez choisi {data}. Voici les sous-catégories disponibles :", reply_markup=get_sub_menu())
    elif data in sub_buttons:
        context.user_data["current_subcategory"] = data
        await query.message.reply_text(f"✅ Sous-catégorie sélectionnée : {data}\nTu peux maintenant envoyer un fichier.")
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

    cat = context.user_data.get("current_category")
    sub = context.user_data.get("current_subcategory")

    if not cat or not sub:
        await update.message.reply_text("❗️ Choisis d'abord une catégorie et une sous-catégorie avec le menu.")
        return

    file = None
    file_name = "unknown"
    file_type = None

    if update.message.document:
        file = update.message.document
        file_name = file.file_name
        file_type = "document"
    elif update.message.audio:
        file = update.message.audio
        file_name = file.file_name or "audio.mp3"
        file_type = "audio"
    elif update.message.video:
        file = update.message.video
        file_name = file.file_name or "video.mp4"
        file_type = "video"
    elif update.message.photo:
        file = update.message.photo[-1]
        file_name = f"photo_{file.file_id}.jpg"
        file_type = "photo"

    if not file:
        await update.message.reply_text("⚠️ Fichier non pris en charge.")
        return

    file_id = file.file_id

    if cat not in files_db:
        files_db[cat] = {}
    if sub not in files_db[cat]:
        files_db[cat][sub] = []

    files_db[cat][sub].append({"file_id": file_id, "file_name": file_name, "file_type": file_type})
    save_files()

    await update.message.reply_text(f"✅ Fichier « {file_name} » enregistré dans {cat}/{sub}.")

async def listfiles_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("⛔ Seul l'administrateur peut voir la liste des fichiers.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage : /listfiles <catégorie> <sous-catégorie>\nExemple : /listfiles KF SMS")
        return

    cat, sub = args[0], args[1]

    if cat not in files_db or sub not in files_db[cat]:
        await update.message.reply_text(f"❌ Aucune donnée trouvée pour {cat}/{sub}.")
        return

    files = files_db[cat][sub]
    if not files:
        await update.message.reply_text(f"📂 Aucun fichier dans {cat}/{sub}.")
        return

    message = f"📁 Fichiers dans {cat}/{sub} :\n"
    for i, f in enumerate(files, 1):
        message += f"{i}. {f['file_name']} (type: {f['file_type']})\n"

    await update.message.reply_text(message)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("listfiles", listfiles_command))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.Audio.ALL | filters.Video.ALL | filters.Photo.ALL, upload_file_handler))

    print("✅ Bot en cours d'exécution...")
    app.run_polling()
