import os
import json
import logging
import shutil
import threading
import asyncio
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
    level=logging.DEBUG
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
MAIN_CATEGORIES = ["KF", "BELO", "SOULAN", "KfClone", "Filtres", "Géolocalisation"]
SUB_CATEGORIES = ["SMS", "Contacts", "Historiques appels", "iMessenger", "Facebook Messenger", "Audio", "Vidéo", "Documents", "Autres"]
CATEGORIES = {cat: SUB_CATEGORIES for cat in MAIN_CATEGORIES}

# Initialisation du stockage avec verrou pour accès concurrent
STORAGE_LOCK = threading.Lock()
STORAGE = None

def load_storage():
    with STORAGE_LOCK:
        parent_dir = os.path.dirname(STORAGE_PATH)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
            logger.info(f"Répertoire créé : {parent_dir}")
        
        if os.path.isdir(STORAGE_PATH):
            shutil.rmtree(STORAGE_PATH)
            logger.warning(f"Répertoire {STORAGE_PATH} supprimé pour permettre la création du fichier.")
        
        try:
            with open(STORAGE_PATH, 'r') as f:
                data = json.load(f)
                logger.debug(f"Storage chargé : {data}")
                return data
        except FileNotFoundError:
            logger.info(f"Fichier {STORAGE_PATH} non trouvé, création d'un nouveau stockage.")
            return {"files": {}, "logs": []}
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de format JSON dans {STORAGE_PATH} : {e}")
            return {"files": {}, "logs": []}

def save_storage(data):
    with STORAGE_LOCK:
        try:
            with open(STORAGE_PATH, 'w') as f:
                json.dump(data, f, indent=4)
            logger.debug(f"Storage sauvegardé : {data}")
        except Exception as e:
            logger.error(f"Erreur lors de l'écriture dans {STORAGE_PATH} : {e}")

# Vérifier les permissions du fichier de stockage
def check_storage_permissions():
    try:
        parent_dir = os.path.dirname(STORAGE_PATH)
        if not os.access(parent_dir, os.W_OK):
            logger.error(f"Pas de permission d'écriture pour {parent_dir}")
        else:
            logger.debug(f"Permissions OK pour {parent_dir}")
    except Exception as e:
        logger.error(f"Erreur lors de la vérification des permissions : {e}")

STORAGE = load_storage()
check_storage_permissions()

# Fonctions utilitaires
def log_action(user_id, action, details):
    with STORAGE_LOCK:
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "action": action,
                "details": details
            }
            STORAGE["logs"].append(log_entry)
            save_storage(STORAGE)
            logger.info(f"Log: {log_entry}")
        except Exception as e:
            logger.error(f"Erreur dans log_action : {e}")

def is_admin(user_id):
    return user_id == ADMIN_ID

def get_main_menu():
    try:
        keyboard = [
            [InlineKeyboardButton(cat, callback_data=f"cat_{cat}") for cat in MAIN_CATEGORIES]
        ]
        return InlineKeyboardMarkup(keyboard)
    except Exception as e:
        logger.error(f"Erreur dans get_main_menu : {e}")
        return InlineKeyboardMarkup([])

def get_subcategory_menu(category):
    try:
        subcategories = CATEGORIES.get(category, SUB_CATEGORIES)
        keyboard = [
            [InlineKeyboardButton(subcat, callback_data=f"subcat_{category}_{subcat}") for subcat in subcategories]
        ]
        keyboard.append([InlineKeyboardButton("Retour", callback_data="back_main")])
        if is_admin:  # Bouton upload pour admin
            keyboard.insert(0, [InlineKeyboardButton("Uploader fichier", callback_data=f"upload_{category}")])
        return InlineKeyboardMarkup(keyboard)
    except Exception as e:
        logger.error(f"Erreur dans get_subcategory_menu : {e}")
        return InlineKeyboardMarkup([])

def get_files_menu(category, subcategory):
    try:
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
    except Exception as e:
        logger.error(f"Erreur dans get_files_menu : {e}")
        return InlineKeyboardMarkup([])

def get_upload_subcategory_menu(category):
    try:
        subcategories = CATEGORIES.get(category, SUB_CATEGORIES)
        keyboard = [
            [InlineKeyboardButton(subcat, callback_data=f"upload_subcat_{category}_{subcat}")]
            for subcat in subcategories
        ]
        keyboard.append([InlineKeyboardButton("Retour", callback_data=f"back_{category}")])
        return InlineKeyboardMarkup(keyboard)
    except Exception as e:
        logger.error(f"Erreur dans get_upload_subcategory_menu : {e}")
        return InlineKeyboardMarkup([])

# Handlers
async def debug_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"Mise à jour reçue : {update.to_dict()}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.debug(f"Commande /start reçue de l'utilisateur {user_id}")
    try:
        # Réponse immédiate pour tester
        await update.message.reply_text("Test : Bot démarré !")
        logger.debug("Réponse 'Test : Bot démarré !' envoyée")
        # Ajouter le menu
        log_action(user_id, "start", "Commande /start exécutée")
        await update.message.reply_text(
            "Bienvenue sur @konntek_bot ! 📁\nChoisissez une catégorie :",
            reply_markup=get_main_menu()
        )
        logger.debug("Menu principal envoyé")
    except Exception as e:
        logger.error(f"Erreur dans start : {e}")
        await update.message.reply_text("Erreur lors du démarrage. Veuillez réessayer.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    try:
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
            if not is_admin(user_id):
                await query.message.reply_text("Action réservée aux administrateurs.")
                return
            category = data[7:]
            context.user_data["upload_category"] = category
            await query.edit_message_text(
                f"Choisissez une sous-catégorie pour l'upload dans {category} :",
                reply_markup=get_upload_subcategory_menu(category)
            )
            return

        if data.startswith("upload_subcat_"):
            if not is_admin(user_id):
                await query.message.reply_text("Action réservée aux administrateurs.")
                return
            _, category, subcategory = data.split("_", 2)
            context.user_data["upload_category"] = category
            context.user_data["upload_subcategory"] = subcategory
            await query.message.reply_text(
                f"Envoyez le fichier à uploader dans {category} > {subcategory} (admin uniquement)."
            )
            return

        if data.startswith("delete_"):
            if not is_admin(user_id):
                await query.message.reply_text("Action réservée aux administrateurs.")
                return
            _, category, subcategory = data.split("_", 2)
            context.user_data["delete_mode"] = {"category": category, "subcategory": subcategory}
            await query.message.reply_text(
                "Envoyez le nom du fichier à supprimer (admin uniquement)."
            )
            return
    except Exception as e:
        logger.error(f"Erreur dans button_callback : {e}")
        await query.message.reply_text("Une erreur s'est produite. Veuillez réessayer.")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Action réservée aux administrateurs.")
        return

    category = context.user_data.get("upload_category")
    subcategory = context.user_data.get("upload_subcategory")
    if not category or not subcategory:
        await update.message.reply_text("Veuillez sélectionner une catégorie et une sous-catégorie d'abord.")
        return

    try:
        file = None
        file_type = None
        file_name = None
        if update.message.document:
            file = update.message.document
            file_type = "document"
            file_name = file.file_name or "document"
        elif update.message.photo:
            file = update.message.photo[-1]
            file_type = "photo"
            file_name = "photo.jpg"
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
                "subcategory": subcategory,
                "type": file_type,
                "uploaded_at": datetime.now().isoformat(),
                "uploader_id": user_id
            }
            save_storage(STORAGE)
            log_action(user_id, "upload_file", f"Fichier : {unique_file_name} dans {category} > {subcategory}")
            await update.message.reply_text(f"Fichier {unique_file_name} uploadé avec succès !")
            context.user_data.clear()
        else:
            await update.message.reply_text("Type de fichier non supporté.")
    except Exception as e:
        logger.error(f"Erreur dans handle_file : {e}")
        await update.message.reply_text("Une erreur s'est produite. Veuillez réessayer.")

async def handle_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Action réservée aux administrateurs.")
        return

    delete_mode = context.user_data.get("delete_mode")
    if not delete_mode:
        await update.message.reply_text("Veuillez sélectionner une sous-catégorie d'abord.")
        return

    try:
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
    except Exception as e:
        logger.error(f"Erreur dans handle_delete : {e}")
        await update.message.reply_text("Une erreur s'est produite. Veuillez réessayer.")

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    location = update.message.location
    if location:
        try:
            log_action(user_id, "share_location", f"Coordonnées : {location.latitude}, {location.longitude}")
            await update.message.reply_text(
                f"Position reçue !\nLatitude : {location.latitude}\nLongitude : {location.longitude}"
            )
        except Exception as e:
            logger.error(f"Erreur dans handle_location : {e}")
            await update.message.reply_text("Une erreur s'est produite. Veuillez réessayer.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Erreur globale : {context.error}")
    if update:
        await update.message.reply_text("Une erreur s'est produite. Veuillez réessayer.")

async def main():
    try:
        # Créer une nouvelle instance de l'application
        app = Application.builder().token(TOKEN).build()
        logger.debug("Application Telegram initialisée")

        # Handlers
        app.add_handler(MessageHandler(filters.ALL, debug_update), group=1)
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_callback))
        app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO | filters.AUDIO | filters.VIDEO | filters.VOICE, handle_file))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_delete))
        app.add_handler(MessageHandler(filters.LOCATION, handle_location))
        app.add_handler(CommandHandler("upload", start))  # Ajout d'un handler pour /upload
        app.add_error_handler(error_handler)

        logger.info("Starting polling")
        # Récupérer les dernières mises à jour pour réinitialiser l'offset
        try:
            updates = await app.bot.get_updates(timeout=10)
            logger.debug(f"Mises à jour initiales reçues : {len(updates)}")
            if updates:
                last_update_id = updates[-1].update_id
                logger.debug(f"Dernier update_id : {last_update_id}")
                await app.bot.get_updates(offset=last_update_id + 1, timeout=10)
            # Lancer le polling
            await app.run_polling(allowed_updates=["message", "callback_query"], drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du polling : {e}")
            raise
    except Exception as e:
        logger.error(f"Erreur dans main : {e}")
        raise
    finally:
        # Assurer l'arrêt propre de l'application
        try:
            if 'app' in locals():
                await app.stop()
                await app.shutdown()
                logger.debug("Application Telegram arrêtée proprement")
        except Exception as e:
            logger.error(f"Erreur lors de l'arrêt de l'application : {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        logger.error(f"Erreur dans asyncio.run : {e}")
        # Si l'event loop est déjà en cours, utiliser l'event loop existant
        loop = asyncio.get_event_loop()
        if loop.is_running():
            logger.debug("Utilisation de l'event loop existant")
            loop.create_task(main())
        else:
            loop.run_until_complete(main())
    except Exception as e:
        logger.error(f"Erreur critique : {e}")
