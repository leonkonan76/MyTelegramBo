import os
import json
import logging
import shutil
from uuid import uuid4
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration des variables d'environnement
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
STORAGE_PATH = os.getenv("STORAGE_PATH", "/opt/render/project/.render/storage/file_storage.json")

# Vérification du token
if not TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN is not set. Please set it in Render environment variables.")
    raise ValueError("Missing TELEGRAM_BOT_TOKEN environment variable.")

# Structure des catégories
CATEGORIES = {
    "KF": ["SMS", "Contacts", "Historiques appels"],
    "BELO": ["iMessenger", "Facebook Messenger"],
    "SOULAN": ["Audio", "Vidéo"],
    "KfClone": ["Documents", "Autres"],
    "Filtres": [],
    "Géolocalisation": [],
}

# Initialisation du stockage
def load_storage():
    # Créer le répertoire parent si absent
    parent_dir = os.path.dirname(STORAGE_PATH)
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir)
        logger.info(f"Répertoire créé : {parent_dir}")
    
    # Vérifier si STORAGE_PATH est un répertoire
    if os.path.isdir(STORAGE_PATH):
        shutil.rmtree(STORAGE_PATH)
        logger.warning(f"Répertoire {STORAGE_PATH} supprimé pour permettre la création du fichier.")
    
    try:
        with open(STORAGE_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"files": {}, "logs": []}

def save_storage(data):
    with open(STORAGE_PATH, 'w') as f:
        json.dump(data, f, indent=4)

STORAGE = load_storage()

# Fonctions utilitaires
def log_action(user_id, action, details):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "action": action,
        "details": details
    }
    STORAGE["logs"].append(log_entry)
    save_storage(STORAGE)
    logger.info(f"Log: {log_entry}")

def is_admin(user_id):
    return user_id == ADMIN_ID

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton(cat, callback_data=f"cat_{cat}") for cat in CATEGORIES.keys()]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_subcategory_menu(category):
    subcategories = CATEGORIES.get(category, [])
    keyboard = [
        [InlineKeyboardButton(subcat, callback_data=f"subcat_{category}_{subcat}") for subcat in subcategories]
    ]
    keyboard.append([InlineKeyboardButton("Retour", callback_data="back_main")])
    if is_admin:  # Bouton upload pour admin
        keyboard.insert(0, [InlineKeyboardButton("Uploader fichier", callback_data=f"upload_{category}")])
    return InlineKeyboardMarkup(keyboard)

def get_files_menu(category, subcategory):
    files = [
        f for f, data in STORAGE["files"].items()
        if data["category"] == category and data["subcategory"] == subcategory
    ]
    keyboard = [
        [InlineKeyboardButton(f"File: {f[:20]}...", callback_data=f"file_{f}")]
        for f in files
    ]
    keyboard.append([InlineKeyboardButton("Retour", callback_data=f"back_{category}")])
    if is_admin:  # Bouton suppression pour admin
        keyboard.insert(0, [InlineKeyboardButton("Supprimer fichier", callback_data=f"delete_{category}_{subcategory}")])
    return InlineKeyboardMarkup(keyboard)

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    log_action(user_id, "start", "Commande /start exécutée")
    await update.message.reply_text(
        "Bienvenue sur @konntek_bot ! 📁\nChoisissez une catégorie :",
        reply_markup=get_main_menu()
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "back_main":
        await query.edit_message_text(
            "Choisissez une catégorie :",
            reply_markup=get_main_menu()
        )
        return

    if data.startswith("cat_"):
        category = data[4:]
        log_action(user_id, "view_category", f"Catégorie : {category}")
        await query.edit_message_text(
            f"Catégorie : {category}\nChoisissez une sous-catégorie :",
            reply_markup=get_subcategory_menu(category)
        )
        return

    if data.startswith("subcat_"):
        _, category, subcategory = data.split("_", 2)
        log_action(user_id, "view_subcategory", f"Sous-catégorie : {subcategory}")
        await query.edit_message_text(
            f"Sous-catégorie : {subcategory}\nFichiers disponibles :",
            reply_markup=get_files_menu(category, subcategory)
        )
        return

    if data.startswith("back_"):
        category = data[5:]
        await query.edit_message_text(
            f"Catégorie : {category}\nChoisissez une sous-catégorie :",
            reply_markup=get_subcategory_menu(category)
        )
        return

    if data.startswith("file_"):
        file_id = data[5:]
        file_data = STORAGE["files"].get(file_id)
        if file_data:
            log_action(user_id, "download_file", f"Fichier : {file_id}")
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=file_data["file_id"],
                caption=f"Fichier : {file_id}"
            )
        return

    if data.startswith("upload_"):
        category = data[7:]
        context.user_data["upload_category"] = category
        await query.message.reply_text(
            f"Envoyez le fichier à uploader dans {category} (admin uniquement)."
        )
        return

    if data.startswith("delete_"):
        _, category, subcategory = data.split("_", 2)
        context.user_data["delete_mode"] = {"category": category, "subcategory": subcategory}
        await query.message.reply_text(
            "Envoyez le nom du fichier à supprimer (admin uniquement)."
        )
        return

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Action réservée aux administrateurs.")
        return

    category = context.user_data.get("upload_category")
    if not category:
        await update.message.reply_text("Veuillez sélectionner une catégorie d'abord.")
        return

    file = None
    file_type = None
    file_name = None
    if update.message.document:
        file = update.message.document
        file_type = "document"
        file_name = file.file_name or "document"
    elif update.message.photo:
        file = update.message.photo[-1]  # Prendre la plus haute résolution
        file_type = "photo"
        file_name = "photo.jpg"  # Nom par défaut pour les photos
    elif update.message.audio:
        file = update.message.audio
        file_type = "audio"
        file_name = file.file_name or "audio"
    elif update.message.video:
        file = update.message.video
        file_type = "video"
        file_name = file.file_name or "video"
    elif update.message.voice:
        file = update.message.voice
        file_type = "voice"
        file_name = file.file_name or "voice"

    if file:
        file_id = file.file_id
        unique_file_name = f"{uuid4()}_{file_name}"
        STORAGE["files"][unique_file_name] = {
            "file_id": file_id,
            "category": category,
            "subcategory": context.user_data.get("upload_subcategory", "Autres"),
            "type": file_type,
            "uploaded_at": datetime.now().isoformat(),
            "uploader_id": user_id
        }
        save_storage(STORAGE)
        log_action(user_id, "upload_file", f"Fichier : {unique_file_name} dans {category}")
        await update.message.reply_text(f"Fichier {unique_file_name} uploadé avec succès !")
        context.user_data.clear()
    else:
        await update.message.reply_text("Type de fichier non supporté.")

async def handle_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Action réservée aux administrateurs.")
        return

    delete_mode = context.user_data.get("delete_mode")
    if not delete_mode:
        await update.message.reply_text("Veuillez sélectionner une sous-catégorie d'abord.")
        return

    file_name = update.message.text.strip()
    if file_name in STORAGE["files"]:
        file_data = STORAGE["files"][file_name]
        if (file_data["category"] == delete_mode["category"] and
                file_data["subcategory"] == delete_mode["subcategory"]):
            del STORAGE["files"][file_name]
            save_storage(STORAGE)
            log_action(user_id, "delete_file", f"Fichier : {file_name}")
            await update.message.reply_text(f"Fichier {file_name} supprimé avec succès !")
        else:
            await update.message.reply_text("Fichier non trouvé dans cette catégorie.")
    else:
        await update.message.reply_text("Fichier non trouvé.")
    context.user_data.clear()

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    location = update.message.location
    if location:
        log_action(user_id, "share_location", f"Coordonnées : {location.latitude}, {location.longitude}")
        await update.message.reply_text(
            f"Position reçue !\nLatitude : {location.latitude}\nLongitude : {location.longitude}"
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Erreur : {context.error}")
    if update:
        await update.message.reply_text("Une erreur s'est produite. Veuillez réessayer.")

def main():
    try:
        app = Application.builder().token(TOKEN).build()
    except telegram.error.InvalidToken as e:
        logger.error(f"Invalid token: {e}")
        raise

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO | filters.AUDIO | filters.VIDEO | filters.VOICE, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_delete))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_error_handler(error_handler)

    # Démarrage
    app.run_polling()

if __name__ == "__main__":
    main()
