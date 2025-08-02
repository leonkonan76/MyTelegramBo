import os
import json
import logging
import requests
from datetime import datetime
from pathlib import Path
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InputFile
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# Configuration Render.com
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Chemin de stockage Render
RENDER_STORAGE = Path("/opt/render/project/.render/storage")
RENDER_STORAGE.mkdir(exist_ok=True, parents=True)

# Chemins des fichiers
STORAGE_PATH = RENDER_STORAGE / "file_storage.json"
FILES_DIR = RENDER_STORAGE / "files"
FILES_DIR.mkdir(exist_ok=True, parents=True)
LOG_FILE = RENDER_STORAGE / "bot_activity.log"

# Catégories
MAIN_CATEGORIES = ["KF", "BELO", "SOULAN", "KFClone", "Filtres", "Géolocalisation"]
SUB_CATEGORIES = ["SMS", "Contacts", "Historiques appels", "iMessenger", 
                 "Facebook Messenger", "Audio", "Vidéo", "Documents", "Autres"]

# Configuration du logging
logging.basicConfig(
    filename=LOG_FILE,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.info("=== BOT STARTED ===")

# Gestion de la base de données
class FileStorage:
    def __init__(self, storage_path):
        self.storage_path = storage_path
        self.data = self.load_data()
        logger.info("Storage initialized")
    
    def load_data(self):
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    return json.load(f)
            logger.info("Creating new storage file")
        except Exception as e:
            logger.error(f"Storage load error: {str(e)}")
        
        return {cat: {sub: [] for sub in SUB_CATEGORIES} for cat in MAIN_CATEGORIES}
    
    def save_data(self):
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Storage save error: {str(e)}")
    
    def add_file(self, category, subcategory, file_data):
        if category not in self.data:
            self.data[category] = {sub: [] for sub in SUB_CATEGORIES}
        if subcategory not in self.data[category]:
            self.data[category][subcategory] = []
            
        self.data[category][subcategory].append(file_data)
        self.save_data()
        logger.info(f"File added to {category}/{subcategory}")
    
    def remove_file(self, category, subcategory, file_index):
        try:
            if category in self.data and subcategory in self.data[category]:
                if 0 <= file_index < len(self.data[category][subcategory]):
                    file_data = self.data[category][subcategory][file_index]
                    file_path = FILES_DIR / file_data["file_path"]
                    
                    # Supprimer le fichier physique
                    if file_path.exists():
                        file_path.unlink()
                    
                    del self.data[category][subcategory][file_index]
                    self.save_data()
                    logger.info(f"File removed: {category}/{subcategory}/{file_path.name}")
                    return True
        except Exception as e:
            logger.error(f"Remove file error: {str(e)}")
        return False

storage = FileStorage(STORAGE_PATH)

# Helpers
def log_activity(user_id: int, action: str, details: str):
    log_entry = f"User:{user_id} | {action} | {details}"
    logger.info(log_entry)
    print(log_entry)

def create_main_menu():
    keyboard = []
    for cat in MAIN_CATEGORIES:
        keyboard.append([InlineKeyboardButton(cat, callback_data=f"cat_{cat}")])
    return InlineKeyboardMarkup(keyboard)

def create_subcategory_menu(category):
    keyboard = []
    for sub in SUB_CATEGORIES:
        keyboard.append([InlineKeyboardButton(sub, callback_data=f"sub_{category}_{sub}")])
    keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

def create_file_menu(category, subcategory):
    files = storage.data.get(category, {}).get(subcategory, [])
    keyboard = []
    
    for idx, file in enumerate(files):
        file_name = file.get('file_name', f'Fichier {idx+1}')
        keyboard.append([
            InlineKeyboardButton(f"⬇️ {file_name}", callback_data=f"file_{category}_{subcategory}_{idx}"),
        ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 Retour", callback_data=f"back_to_sub_{category}"),
        InlineKeyboardButton("➕ Upload", callback_data=f"upload_{category}_{subcategory}")
    ])
    
    return InlineKeyboardMarkup(keyboard)

# Télécharger et sauvegarder physiquement un fichier
async def download_and_save_file(file_id, file_name, context):
    try:
        # Obtenir les informations du fichier
        file = await context.bot.get_file(file_id)
        
        # Télécharger le contenu
        file_content = await file.download_as_bytearray()
        
        # Sauvegarder physiquement
        file_path = FILES_DIR / file_name
        with open(file_path, 'wb') as f:
            f.write(file_content)
            
        return str(file_path.relative_to(RENDER_STORAGE))
    except Exception as e:
        logger.error(f"File save error: {str(e)}")
        return None

# Commandes
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    welcome_msg = (
        "🌟 Bienvenue sur Konntek_Bot !\n\n"
        "📂 Accédez à la médiathèque organisée par catégories.\n"
        "📍 Envoyez /location pour partager votre position."
    )
    await update.message.reply_text(welcome_msg, reply_markup=create_main_menu())
    log_activity(user.id, "START", f"User: {user.first_name}")

async def location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Cliquez pour partager votre position :",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📍 Partager position", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    location = update.message.location
    await update.message.reply_text(
        f"📍 Position reçue :\n\n"
        f"Latitude: {location.latitude:.6f}\n"
        f"Longitude: {location.longitude:.6f}\n\n"
        f"https://maps.google.com/?q={location.latitude},{location.longitude}",
        reply_markup=ReplyKeyboardRemove()
    )
    log_activity(user.id, "LOCATION", f"Lat: {location.latitude}, Lon: {location.longitude}")

# Callbacks
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("cat_"):
        category = data[4:]
        await query.edit_message_text(
            f"📁 Catégorie: {category}\nSélectionnez une sous-catégorie:",
            reply_markup=create_subcategory_menu(category)
        )
    
    elif data.startswith("sub_"):
        _, category, subcategory = data.split("_", 2)
        files = storage.data.get(category, {}).get(subcategory, [])
        msg = f"📂 {category} / {subcategory}\n\n"
        msg += "Aucun fichier disponible." if not files else "Sélectionnez un fichier :"
        
        await query.edit_message_text(
            msg,
            reply_markup=create_file_menu(category, subcategory)
        )
    
    elif data.startswith("file_"):
        _, category, subcategory, idx = data.split("_")
        idx = int(idx)
        try:
            file_data = storage.data[category][subcategory][idx]
            file_path = RENDER_STORAGE / file_data["file_path"]
            
            # Envoyer le fichier physique
            with open(file_path, 'rb') as f:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=InputFile(f),
                    caption=f"📥 {file_data['file_name']}"
                )
            log_activity(user_id, "DOWNLOAD", f"{category}/{subcategory}/{file_data['file_name']}")
        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            await query.answer("❌ Erreur lors du téléchargement", show_alert=True)
    
    elif data.startswith("upload_"):
        if user_id != ADMIN_ID:
            await query.answer("❌ Action réservée à l'admin", show_alert=True)
            return
        
        _, category, subcategory = data.split("_", 2)
        context.user_data['upload_category'] = category
        context.user_data['upload_subcategory'] = subcategory
        await query.edit_message_text("⬆️ Envoyez le fichier à uploader (tout format accepté) :")
    
    elif data == "back_to_main":
        await query.edit_message_text("📂 Menu Principal :", reply_markup=create_main_menu())
    
    elif data.startswith("back_to_sub_"):
        category = data.split("_")[-1]
        await query.edit_message_text(
            f"📁 Catégorie: {category}\nSélectionnez une sous-catégorie:",
            reply_markup=create_subcategory_menu(category)
        )

# Gestion des fichiers
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    
    if 'upload_category' in context.user_data and 'upload_subcategory' in context.user_data:
        # C'est un upload admin
        if user.id != ADMIN_ID:
            await update.message.reply_text("❌ Upload réservé à l'admin")
            return
        
        category = context.user_data['upload_category']
        subcategory = context.user_data['upload_subcategory']
        file_msg = update.message
        
        # Détection de tout type de fichier
        file_id = None
        file_name = f"file_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        if file_msg.document:
            file_id = file_msg.document.file_id
            file_name = file_msg.document.file_name or file_name
            file_type = "document"
        elif file_msg.photo:
            file_id = file_msg.photo[-1].file_id
            file_name = f"photo_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            file_type = "photo"
        elif file_msg.video:
            file_id = file_msg.video.file_id
            file_name = file_msg.video.file_name or file_name
            file_type = "video"
        elif file_msg.audio:
            file_id = file_msg.audio.file_id
            file_name = file_msg.audio.file_name or file_name
            file_type = "audio"
        elif file_msg.voice:
            file_id = file_msg.voice.file_id
            file_name = f"voice_{datetime.now().strftime('%Y%m%d%H%M%S')}.ogg"
            file_type = "voice"
        else:
            file_id = file_msg.effective_attachment.file_id
            file_type = "unknown"
        
        # Sauvegarder physiquement le fichier
        file_path = await download_and_save_file(file_id, file_name, context)
        
        if file_path:
            file_data = {
                "file_path": file_path,
                "file_name": file_name,
                "file_type": file_type,
                "date": datetime.now().isoformat(),
                "uploader": user.first_name
            }
            
            storage.add_file(category, subcategory, file_data)
            await update.message.reply_text(
                f"✅ Fichier uploadé avec succès dans :\n{category} > {subcategory}"
            )
            log_activity(user.id, "UPLOAD", f"{category}/{subcategory}/{file_name}")
        else:
            await update.message.reply_text("❌ Échec de l'enregistrement du fichier")
        
        # Réinitialiser
        del context.user_data['upload_category']
        del context.user_data['upload_subcategory']

def main():
    # Vérification des variables d'environnement
    if not TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN manquant!")
        return
    if not ADMIN_ID:
        logger.critical("ADMIN_ID manquant!")
        return

    logger.info("Initialisation du bot...")
    
    # Vérifier les permissions
    try:
        test_file = RENDER_STORAGE / "test.txt"
        with open(test_file, 'w') as f:
            f.write("Test d'écriture")
        test_file.unlink()
        logger.info("Permissions d'écriture OK")
    except Exception as e:
        logger.critical(f"Erreur de permission: {str(e)}")
        return
    
    # Créer le fichier de stockage si inexistant
    if not STORAGE_PATH.exists():
        with open(STORAGE_PATH, 'w') as f:
            json.dump({}, f)
        logger.info("Fichier de stockage créé")

    app = Application.builder().token(TOKEN).build()
    
    # Commandes de base
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("location", location))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    
    # Gestion des fichiers
    app.add_handler(MessageHandler(
        filters.Document.ALL | filters.AUDIO | filters.VIDEO | 
        filters.PHOTO | filters.VOICE,
        handle_file
    ))
    
    # Callbacks généraux
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    # Lancement du bot
    logger.info("Lancement du bot...")
    app.run_polling()

if __name__ == "__main__":
    main()
