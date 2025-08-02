import os
import json
import logging
from datetime import datetime
from pathlib import Path
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
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
HIDDEN_PATH = RENDER_STORAGE / "hidden_files.json"  # Nouveau fichier pour les masquages
LOG_FILE = RENDER_STORAGE / "bot_activity.log"

# Catégories
MAIN_CATEGORIES = ["KF", "BELO", "SOULAN", "KFClone", "Filtres", "Géolocalisation"]
SUB_CATEGORIES = ["SMS", "Contacts", "Historiques appels", "iMessenger", 
                 "Facebook Messenger", "Audio", "Vidéo", "Documents", "Autres"]

# États de conversation
SELECTING_CATEGORY, SELECTING_SUBCATEGORY, UPLOADING_FILE, CONFIRMING_DELETE = range(4)

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
        
        # Structure initiale
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
                    file_name = self.data[category][subcategory][file_index]["file_name"]
                    del self.data[category][subcategory][file_index]
                    self.save_data()
                    logger.info(f"File removed: {category}/{subcategory}/{file_name}")
                    return True
        except Exception as e:
            logger.error(f"Remove file error: {str(e)}")
        return False

# Nouveau système de masquage des fichiers
class HiddenFiles:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = self.load_data()
    
    def load_data(self):
        try:
            if self.file_path.exists():
                with open(self.file_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Hidden files load error: {str(e)}")
        return {}
    
    def save_data(self):
        try:
            with open(self.file_path, 'w') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            logger.error(f"Hidden files save error: {str(e)}")
    
    def hide_file(self, user_id, category, subcategory, file_index):
        user_id = str(user_id)
        if user_id not in self.data:
            self.data[user_id] = {}
        
        if category not in self.data[user_id]:
            self.data[user_id][category] = {}
        
        if subcategory not in self.data[user_id][category]:
            self.data[user_id][category][subcategory] = []
        
        if file_index not in self.data[user_id][category][subcategory]:
            self.data[user_id][category][subcategory].append(file_index)
            self.save_data()
            return True
        return False
    
    def is_hidden(self, user_id, category, subcategory, file_index):
        user_id = str(user_id)
        return (
            user_id in self.data and
            category in self.data[user_id] and
            subcategory in self.data[user_id][category] and
            file_index in self.data[user_id][category][subcategory]
        )

# Initialisation des stockages
storage = FileStorage(STORAGE_PATH)
hidden_files = HiddenFiles(HIDDEN_PATH)

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

def create_file_menu(category, subcategory, user_id):
    files = storage.data.get(category, {}).get(subcategory, [])
    keyboard = []
    
    for idx, file in enumerate(files):
        # Vérifier si le fichier est masqué pour cet utilisateur
        if hidden_files.is_hidden(user_id, category, subcategory, idx):
            continue
            
        file_name = file.get('file_name', f'Fichier {idx+1}')
        btn_row = [
            InlineKeyboardButton(f"⬇️ {file_name}", callback_data=f"file_{category}_{subcategory}_{idx}")
        ]
        
        # Boutons d'action
        if user_id == ADMIN_ID:
            btn_row.append(InlineKeyboardButton("🗑️", callback_data=f"del_{category}_{subcategory}_{idx}"))
        else:
            btn_row.append(InlineKeyboardButton("👁️", callback_data=f"hide_{category}_{subcategory}_{idx}"))
        
        keyboard.append(btn_row)
    
    footer = [InlineKeyboardButton("🔙 Retour", callback_data=f"back_to_sub_{category}")]
    
    # Bouton upload uniquement pour admin
    if user_id == ADMIN_ID:
        footer.append(InlineKeyboardButton("➕ Upload", callback_data=f"upload_{category}_{subcategory}"))
    
    keyboard.append(footer)
    return InlineKeyboardMarkup(keyboard)

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
        
        # Compter les fichiers visibles
        visible_files = [
            f for idx, f in enumerate(files) 
            if not hidden_files.is_hidden(user_id, category, subcategory, idx)
        ]
        
        msg += "Aucun fichier disponible." if not visible_files else f"{len(visible_files)} fichier(s) disponible(s) :"
        
        await query.edit_message_text(
            msg,
            reply_markup=create_file_menu(category, subcategory, user_id)
        )
    
    elif data.startswith("file_"):
        _, category, subcategory, idx = data.split("_")
        idx = int(idx)
        try:
            file_data = storage.data[category][subcategory][idx]
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=file_data["file_id"],
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
        return UPLOADING_FILE
    
    elif data.startswith("del_"):  # Suppression admin (globale)
        if user_id != ADMIN_ID:
            await query.answer("❌ Action réservée à l'admin", show_alert=True)
            return
        
        _, category, subcategory, idx = data.split("_", 3)
        idx = int(idx)
        try:
            file_name = storage.data[category][subcategory][idx]["file_name"]
            context.user_data['del_index'] = idx
            context.user_data['del_category'] = category
            context.user_data['del_subcategory'] = subcategory
            
            keyboard = [
                [InlineKeyboardButton("✅ Confirmer", callback_data="confirm_delete")],
                [InlineKeyboardButton("❌ Annuler", callback_data=f"sub_{category}_{subcategory}")]
            ]
            
            await query.edit_message_text(
                f"⚠️ Supprimer ce fichier pour TOUS les utilisateurs ?\n\n"
                f"🗑️ {file_name}\n\n"
                f"Cette action est irréversible !",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CONFIRMING_DELETE
        except Exception as e:
            logger.error(f"Delete setup error: {str(e)}")
            await query.answer("❌ Fichier introuvable", show_alert=True)
    
    elif data.startswith("hide_"):  # Masquage utilisateur (local)
        _, category, subcategory, idx = data.split("_", 3)
        idx = int(idx)
        
        if hidden_files.hide_file(user_id, category, subcategory, idx):
            await query.answer("👁️ Fichier masqué pour vous", show_alert=True)
            
            # Mettre à jour le menu
            files = storage.data.get(category, {}).get(subcategory, [])
            visible_files = [
                f for i, f in enumerate(files) 
                if not hidden_files.is_hidden(user_id, category, subcategory, i)
            ]
            
            msg = f"📂 {category} / {subcategory}\n\n"
            msg += "Aucun fichier disponible." if not visible_files else f"{len(visible_files)} fichier(s) disponible(s) :"
            
            await query.edit_message_text(
                msg,
                reply_markup=create_file_menu(category, subcategory, user_id)
            )
        else:
            await query.answer("❌ Erreur lors du masquage", show_alert=True)
    
    elif data == "confirm_delete":
        try:
            category = context.user_data['del_category']
            subcategory = context.user_data['del_subcategory']
            idx = context.user_data['del_index']
            file_data = storage.data[category][subcategory][idx]
            
            if storage.remove_file(category, subcategory, idx):
                await query.edit_message_text(
                    "🗑️ Fichier supprimé avec succès pour tous les utilisateurs !",
                    reply_markup=create_subcategory_menu(category)
                )
                log_activity(user_id, "DELETE", f"{category}/{subcategory}/{file_data['file_name']}")
            else:
                await query.edit_message_text("❌ Erreur lors de la suppression")
        except Exception as e:
            logger.error(f"Delete execution error: {str(e)}")
            await query.edit_message_text("❌ Erreur critique lors de la suppression")
        
        return ConversationHandler.END
    
    elif data == "back_to_main":
        await query.edit_message_text("📂 Menu Principal :", reply_markup=create_main_menu())
    
    elif data.startswith("back_to_sub_"):
        category = data.split("_")[-1]
        await query.edit_message_text(
            f"📁 Catégorie: {category}\nSélectionnez une sous-catégorie:",
            reply_markup=create_subcategory_menu(category)
        )

# Gestion des fichiers
async def handle_any_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ Upload réservé à l'admin")
        return
    
    context.user_data['current_file'] = update.message
    await update.message.reply_text(
        "Sélectionnez une catégorie :",
        reply_markup=create_main_menu()
    )
    return SELECTING_CATEGORY

async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not query.data.startswith("cat_"):
        return
    
    category = query.data[4:]
    context.user_data['selected_category'] = category
    await query.edit_message_text(
        f"Catégorie sélectionnée: {category}\nChoisissez une sous-catégorie:",
        reply_markup=create_subcategory_menu(category)
    )
    return SELECTING_SUBCATEGORY

async def select_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not query.data.startswith("sub_"):
        return
    
    _, category, subcategory = query.data.split("_", 2)
    file_msg = context.user_data['current_file']
    
    # Détection de tout type de fichier
    file_id = None
    file_name = f"file_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    file_type = "document"
    
    # Vérifier tous les types possibles
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
        # Fallback pour tout autre type
        file_id = file_msg.effective_attachment.file_id
        file_type = "unknown"
    
    # Création de l'entrée
    file_data = {
        "file_id": file_id,
        "file_name": file_name,
        "file_type": file_type,
        "date": datetime.now().isoformat(),
        "uploader": query.from_user.first_name
    }
    
    storage.add_file(category, subcategory, file_data)
    await query.edit_message_text(
        f"✅ Fichier uploadé avec succès dans :\n{category} > {subcategory}",
        reply_markup=create_subcategory_menu(category)
    )
    log_activity(query.from_user.id, "UPLOAD", f"{category}/{subcategory}/{file_name}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Opération annulée.")
    return ConversationHandler.END

def main():
    # Vérification des variables d'environnement
    if not TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN manquant!")
        return
    if not ADMIN_ID:
        logger.critical("ADMIN_ID manquant!")
        return

    logger.info("Initialisation du bot...")
    
    # Créer les fichiers de stockage si inexistants
    if not STORAGE_PATH.exists():
        with open(STORAGE_PATH, 'w') as f:
            json.dump({}, f)
        logger.info("Fichier de stockage créé")
    
    if not HIDDEN_PATH.exists():
        with open(HIDDEN_PATH, 'w') as f:
            json.dump({}, f)
        logger.info("Fichier de masquage créé")

    app = Application.builder().token(TOKEN).build()
    
    # Commandes de base
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("location", location))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    
    # Gestion des fichiers (admin)
    upload_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Document.ALL | filters.AUDIO | filters.VIDEO | 
                filters.PHOTO | filters.VOICE,
                handle_any_file
            )
        ],
        states={
            SELECTING_CATEGORY: [CallbackQueryHandler(select_category)],
            SELECTING_SUBCATEGORY: [CallbackQueryHandler(select_subcategory)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        map_to_parent={ConversationHandler.END: ConversationHandler.END}
    )
    app.add_handler(upload_conv)
    
    # Callbacks généraux
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    # Lancement du bot
    logger.info("Lancement du bot...")
    app.run_polling()

if __name__ == "__main__":
    main()
