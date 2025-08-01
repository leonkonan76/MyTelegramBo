from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
import os
import json
import telegram

# Afficher la version pour débogage
print(f"Version de python-telegram-bot : {telegram.__version__}")

# Variables d'environnement
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DATA_PATH = "/data/files.json"

# Catégories et sous-catégories
main_buttons = ["KF", "BELO", "SOULAN", "KfClone", "Filtres", "Géolocalisation"]
sub_buttons = ["SMS", "CONTACTS", "Historiques appels", "iMessenger", "Facebook Messenger", "Audio", "Vidéo", "Documents", "Autres"]

# États pour le ConversationHandler
SELECT_MAIN, SELECT_SUB, UPLOAD_FILE = range(3)

# Fonctions pour charger et sauvegarder les fichiers
def load_files_db():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, 'r') as f:
            return json.load(f)
    else:
        return {main: {sub: [] for sub in sub_buttons} for main in main_buttons if main != "Géolocalisation"}

def save_files_db(files_db):
    with open(DATA_PATH, 'w') as f:
        json.dump(files_db, f)

# Charger la base de données des fichiers
files_db = load_files_db()

# Menus
def get_main_menu():
    keyboard = [[InlineKeyboardButton(text=btn, callback_data=btn)] for btn in main_buttons]
    return InlineKeyboardMarkup(keyboard)

def get_sub_menu(main):
    keyboard = []
    for sub in sub_buttons:
        file_count = len(files_db.get(main, {}).get(sub, []))
        text = f"{sub} ({file_count})"
        keyboard.append([InlineKeyboardButton(text=text, callback_data=f"{main}_{sub}")])
    return InlineKeyboardMarkup(keyboard)

def get_files_menu(main, sub, is_admin=False):
    keyboard = []
    if main in files_db and sub in files_db[main]:
        for i, file_id in enumerate(files_db[main][sub]):
            keyboard.append([InlineKeyboardButton(text=f"Fichier {i+1}", callback_data=f"download_{file_id}")])
            if is_admin:
                keyboard.append([InlineKeyboardButton(text=f"Supprimer Fichier {i+1}", callback_data=f"delete_{main}_{sub}_{i}")])
    return InlineKeyboardMarkup(keyboard)

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bienvenue dans le bot MyTelegramBot. Choisissez une option :", reply_markup=get_main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    is_admin = query.from_user.id == ADMIN_ID

    if data in main_buttons:
        if data == "Géolocalisation":
            keyboard = ReplyKeyboardMarkup(
                [[KeyboardButton("Envoyer ma position", request_location=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await query.message.reply_text("Merci de partager votre position :", reply_markup=keyboard)
        else:
            reply_markup = get_sub_menu(data)
            await query.message.reply_text(f"Vous avez choisi {data}. Voici les options disponibles :", reply_markup=reply_markup)
    elif "_" in data and len(data.split("_")) == 2:
        main, sub = data.split("_")
        reply_markup = get_files_menu(main, sub, is_admin)
        await query.message.reply_text(f"Fichiers pour {main} > {sub} :", reply_markup=reply_markup)
    elif data.startswith("download_"):
        file_id = data.split("_", 1)[1]
        await query.message.reply_document(document=file_id)
    elif data.startswith("delete_") and is_admin:
        parts = data.split("_", 3)
        if len(parts) == 4 and parts[0] == "delete":
            main, sub, index_str = parts[1], parts[2], parts[3]
            try:
                index = int(index_str)
                if main in files_db and sub in files_db[main] and index < len(files_db[main][sub]):
                    del files_db[main][sub][index]
                    save_files_db(files_db)
                    await query.message.reply_text(f"Fichier supprimé de {main} > {sub}.")
                    reply_markup = get_files_menu(main, sub, is_admin)
                    await query.message.reply_text(f"Fichiers mis à jour pour {main} > {sub} :", reply_markup=reply_markup)
                else:
                    await query.message.reply_text("Fichier non trouvé.")
            except ValueError:
                await query.message.reply_text("Index invalide.")
        else:
            await query.message.reply_text("Demande invalide.")
    else:
        await query.message.reply_text(f"Vous avez sélectionné : {data}")

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
        await update.message.reply_text(f"Localisation reçue :\nLatitude: {lat}\nLongitude: {lon}")

async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Seul l'administrateur peut utiliser cette commande.")
        return ConversationHandler.END
    await update.message.reply_text("Veuillez sélectionner une catégorie principale :", reply_markup=get_main_menu())
    return SELECT_MAIN

async def select_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data in main_buttons and data != "Géolocalisation":
        context.user_data['main'] = data
        keyboard = [[InlineKeyboardButton(text=sub, callback_data=sub)] for sub in sub_buttons]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(f"Vous avez sélectionné {data}. Veuillez maintenant sélectionner une sous-catégorie :", reply_markup=reply_markup)
        return SELECT_SUB
    else:
        await query.message.reply_text("Catégorie non valide pour le téléchargement.")
        return ConversationHandler.END

async def select_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data in sub_buttons:
        context.user_data['sub'] = data
        await query.message.reply_text(f"Vous avez sélectionné {context.user_data['main']} > {data}. Veuillez maintenant envoyer le fichier.")
        return UPLOAD_FILE
    else:
        await query.message.reply_text("Sous-catégorie non valide.")
        return ConversationHandler.END

async def upload_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document:
        file_id = update.message.document.file_id
        main = context.user_data.get('main')
        sub = context.user_data.get('sub')
        if main and sub:
            if main not in files_db:
                files_db[main] = {}
            if sub not in files_db[main]:
                files_db[main][sub] = []
            files_db[main][sub].append(file_id)
            save_files_db(files_db)
            await update.message.reply_text(f"Fichier téléchargé avec succès pour {main} > {sub}.")
            return ConversationHandler.END
        else:
            await update.message.reply_text("Erreur: catégorie ou sous-catégorie non sélectionnée.")
            return ConversationHandler.END
    else:
        await update.message.reply_text("Veuillez envoyer un document.")
        return UPLOAD_FILE

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Seul l'administrateur peut envoyer des fichiers via la commande /upload.")

# Point d'entrée principal
if __name__ == '__main__':
    load_files_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("upload", upload_start)],
        states={
            SELECT_MAIN: [CallbackQueryHandler(select_main)],
            SELECT_SUB: [CallbackQueryHandler(select_sub)],
            UPLOAD_FILE: [MessageHandler(filters.Document.ALL, upload_file)],
        },
        fallbacks=[],
    )
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.COMMAND, handle_document))

    print("Bot en cours d'exécution...")
    app.run_polling()
