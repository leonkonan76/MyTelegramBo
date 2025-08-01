# bot.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    PersistenceInput,
    PicklePersistence
)
import os
import logging
import json
from datetime import datetime

# Configuration
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
PERSIST_FILE = "file_storage.pkl"

# Initialisation du logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Structure des catégories
MAIN_CATEGORIES = ["KF", "BELO", "SOULAN", "KfClone", "Filtres", "Géolocalisation"]
SUB_CATEGORIES = ["SMS", "CONTACTS", "Historiques appels", "iMessenger", "Facebook Messenger", 
                 "Audio", "Vidéo", "Documents", "Autres"]

# États de conversation
UPLOADING_FILE, EDITING_FILE = range(2)

# Helper pour créer des menus
def create_menu(buttons, back_button=False, back_data="main_menu", columns=1):
    keyboard = []
    row = []
    
    for i, btn in enumerate(buttons):
        row.append(InlineKeyboardButton(btn, callback_data=btn))
        if (i + 1) % columns == 0:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    if back_button:
        keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data=back_data)])
    
    return InlineKeyboardMarkup(keyboard)

# Sauvegarder l'état
def save_file_storage(context, file_storage):
    context.bot_data["file_storage"] = file_storage
    with open(PERSIST_FILE, 'w') as f:
        json.dump(file_storage, f)

# Charger l'état
def load_file_storage():
    try:
        with open(PERSIST_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Commandes
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_msg = f"👋 Bonjour {user.first_name} !\nChoisissez une catégorie :"
    await update.message.reply_text(welcome_msg, reply_markup=create_menu(MAIN_CATEGORIES, columns=2))

# Gestion des boutons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "main_menu":
        await show_main_menu(query)
    elif data in MAIN_CATEGORIES:
        await handle_main_category(query, context, data)
    elif data in SUB_CATEGORIES:
        await handle_subcategory(query, context, data)
    elif data.startswith("file_"):
        await send_file_to_user(query, context, data)
    elif data == "upload_file":
        await start_file_upload(query, context)
    elif data == "manage_files":
        await show_file_management(query, context)
    elif data.startswith("delete_"):
        await delete_file(query, context, data)
    elif data == "cancel_upload":
        await query.edit_message_text("❌ Upload annulé")
    elif data == "share_location":
        await handle_share_location(query)

async def show_main_menu(query):
    await query.edit_message_text(
        "📂 Menu principal :",
        reply_markup=create_menu(MAIN_CATEGORIES, columns=2)
    )

async def handle_main_category(query, context, category):
    context.user_data["current_category"] = category
    
    if category == "Géolocalisation":
        await handle_geolocation(query)
    else:
        await show_subcategories_menu(query, context, category)

async def handle_geolocation(query):
    await query.edit_message_text(
        "📍 Partagez votre position :",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Partager position", callback_data="share_location"),
            InlineKeyboardButton("🔙 Retour", callback_data="main_menu")
        ]])
    )

async def handle_share_location(query):
    await query.answer("Veuillez utiliser le bouton de partage de position dans le chat", show_alert=True)

async def show_subcategories_menu(query, context, category):
    submenu_buttons = SUB_CATEGORIES.copy()
    
    # Ajouter bouton upload pour admin
    if query.from_user.id == ADMIN_ID:
        submenu_buttons.append("⬆️ Upload Fichier")
        submenu_buttons.append("⚙️ Gérer Fichiers")
    
    await query.edit_message_text(
        f"📁 Catégorie : {category}\nSélectionnez une sous-catégorie :",
        reply_markup=create_menu(submenu_buttons, True, "main_menu", columns=2)
    )

async def handle_subcategory(query, context, subcategory):
    category = context.user_data.get("current_category")
    context.user_data["current_subcategory"] = subcategory
    
    file_storage = context.bot_data.get("file_storage", {})
    files = file_storage.get(category, {}).get(subcategory, [])
    
    if not files:
        message = f"📭 Aucun fichier dans '{subcategory}'"
        if query.from_user.id == ADMIN_ID:
            message += "\n\nVous pouvez ajouter des fichiers avec le bouton ⬆️ Upload Fichier"
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Retour", callback_data=category)
            ]])
        )
        return

    keyboard = []
    for idx, file_info in enumerate(files):
        keyboard.append([InlineKeyboardButton(
            f"📄 {file_info['name']}", 
            callback_data=f"file_{idx}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data=category)])
    
    await query.edit_message_text(
        f"📂 Fichiers disponibles dans '{subcategory}':",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def send_file_to_user(query, context, file_data):
    category = context.user_data.get("current_category")
    subcategory = context.user_data.get("current_subcategory")
    
    if not category or not subcategory:
        await query.answer("❌ Erreur: Catégorie non définie", show_alert=True)
        return
    
    file_idx = int(file_data.split('_')[1])
    file_storage = context.bot_data.get("file_storage", {})
    files = file_storage.get(category, {}).get(subcategory, [])
    
    if file_idx >= len(files):
        await query.answer("❌ Fichier introuvable", show_alert=True)
        return
    
    file_info = files[file_idx]
    
    try:
        if file_info['type'] == 'document':
            await context.bot.send_document(query.message.chat_id, file_info["file_id"], caption=f"📥 {file_info['name']}")
        elif file_info['type'] == 'photo':
            await context.bot.send_photo(query.message.chat_id, file_info["file_id"], caption=f"📸 {file_info['name']}")
        elif file_info['type'] == 'audio':
            await context.bot.send_audio(query.message.chat_id, file_info["file_id"], caption=f"🎵 {file_info['name']}")
        elif file_info['type'] == 'video':
            await context.bot.send_video(query.message.chat_id, file_info["file_id"], caption=f"🎬 {file_info['name']}")
        elif file_info['type'] == 'voice':
            await context.bot.send_voice(query.message.chat_id, file_info["file_id"], caption=f"🎤 {file_info['name']}")
        else:
            await context.bot.send_document(query.message.chat_id, file_info["file_id"], caption=f"📥 {file_info['name']}")
    except Exception as e:
        logger.error(f"Error sending file: {e}")
        await query.answer("❌ Erreur lors du téléchargement", show_alert=True)

# Gestion de l'upload
async def start_file_upload(query, context):
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Action réservée à l'admin", show_alert=True)
        return
    
    category = context.user_data.get("current_category")
    subcategory = context.user_data.get("current_subcategory")
    
    if not category or not subcategory:
        await query.answer("❌ Veuillez d'abord sélectionner une sous-catégorie", show_alert=True)
        return
    
    context.user_data["upload_category"] = category
    context.user_data["upload_subcategory"] = subcategory
    
    await query.message.reply_text(
        f"⬆️ Envoyez le fichier à ajouter à:\n"
        f"Catégorie: {category}\n"
        f"Sous-catégorie: {subcategory}\n\n"
        "Vous pouvez envoyer n'importe quel type de fichier.\n"
        "/cancel pour annuler"
    )
    
    return UPLOADING_FILE

async def handle_uploaded_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    category = user_data["upload_category"]
    subcategory = user_data["upload_subcategory"]
    
    file_storage = context.bot_data.get("file_storage", {})
    
    if category not in file_storage:
        file_storage[category] = {}
    if subcategory not in file_storage[category]:
        file_storage[category][subcategory] = []

    file = None
    file_name = "Fichier"
    file_type = "document"
    
    if update.message.document:
        file = update.message.document
        file_name = file.file_name or "document"
        file_type = "document"
    elif update.message.photo:
        file = update.message.photo[-1]
        file_name = "photo.jpg"
        file_type = "photo"
    elif update.message.audio:
        file = update.message.audio
        file_name = file.file_name or "audio.mp3"
        file_type = "audio"
    elif update.message.video:
        file = update.message.video
        file_name = file.file_name or "video.mp4"
        file_type = "video"
    elif update.message.voice:
        file = update.message.voice
        file_name = "audio.ogg"
        file_type = "voice"
    elif update.message.text:
        await update.message.reply_text("❌ Veuillez envoyer un fichier valide")
        return UPLOADING_FILE
    
    if file:
        file_info = {
            "file_id": file.file_id,
            "name": file_name,
            "type": file_type,
            "uploaded_at": datetime.now().isoformat(),
            "uploaded_by": update.message.from_user.id
        }
        
        file_storage[category][subcategory].append(file_info)
        context.bot_data["file_storage"] = file_storage
        save_file_storage(context, file_storage)
        
        await update.message.reply_text(
            f"✅ Fichier ajouté avec succès à:\n"
            f"Catégorie: {category}\n"
            f"Sous-catégorie: {subcategory}\n\n"
            f"Nom: {file_name}"
        )
    else:
        await update.message.reply_text("❌ Format de fichier non supporté")
    
    return ConversationHandler.END

# Gestion des fichiers (admin)
async def show_file_management(query, context):
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Action réservée à l'admin", show_alert=True)
        return
    
    category = context.user_data.get("current_category")
    subcategory = context.user_data.get("current_subcategory")
    
    if not category or not subcategory:
        await query.answer("❌ Catégorie non sélectionnée", show_alert=True)
        return
    
    file_storage = context.bot_data.get("file_storage", {})
    files = file_storage.get(category, {}).get(subcategory, [])
    
    if not files:
        await query.answer("ℹ️ Aucun fichier à gérer", show_alert=True)
        return
    
    keyboard = []
    for idx, file_info in enumerate(files):
        keyboard.append([
            InlineKeyboardButton(f"🗑️ {file_info['name']}", callback_data=f"delete_{idx}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data=category)])
    
    await query.edit_message_text(
        f"⚙️ Gestion des fichiers ({category} > {subcategory}):\n"
        "Cliquez sur un fichier pour le supprimer",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def delete_file(query, context, data):
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Action réservée à l'admin", show_alert=True)
        return
    
    file_idx = int(data.split('_')[1])
    category = context.user_data.get("current_category")
    subcategory = context.user_data.get("current_subcategory")
    
    if not category or not subcategory:
        await query.answer("❌ Catégorie non définie", show_alert=True)
        return
    
    file_storage = context.bot_data.get("file_storage", {})
    
    if category in file_storage and subcategory in file_storage[category]:
        if file_idx < len(file_storage[category][subcategory]):
            deleted_file = file_storage[category][subcategory].pop(file_idx)
            context.bot_data["file_storage"] = file_storage
            save_file_storage(context, file_storage)
            
            # Si plus de fichiers, supprimer la sous-catégorie
            if not file_storage[category][subcategory]:
                del file_storage[category][subcategory]
            
            await query.answer(f"🗑️ Fichier supprimé: {deleted_file['name']}", show_alert=True)
            await show_file_management(query, context)
            return
    
    await query.answer("❌ Fichier introuvable", show_alert=True)

async def cancel_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Upload annulé")
    return ConversationHandler.END

# Gestion de la localisation
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.location
    await update.message.reply_text(
        f"📍 Position reçue:\n"
        f"Latitude: {location.latitude}\n"
        f"Longitude: {location.longitude}"
    )

# Configuration principale
if __name__ == '__main__':
    # Vérification des variables d'environnement
    if not TOKEN or not ADMIN_ID:
        logger.error("Les variables BOT_TOKEN et ADMIN_ID doivent être définies")
        exit(1)
    
    # Initialiser la persistance
    file_storage = load_file_storage()
    persistence = PicklePersistence(
        filepath=PERSIST_FILE,
        store_data=PersistenceInput(bot_data=True)
    
    app = ApplicationBuilder() \
        .token(TOKEN) \
        .persistence(persistence) \
        .build()
    
    # Stocker les données initiales
    app.bot_data["file_storage"] = file_storage

    # Handler de conversation pour l'upload
    upload_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_file_upload, pattern="^upload_file$")],
        states={
            UPLOADING_FILE: [
                MessageHandler(
                    filters.Document.ALL | 
                    filters.PHOTO | 
                    filters.AUDIO | 
                    filters.VIDEO | 
                    filters.VOICE, 
                    handle_uploaded_file
                ),
                CommandHandler("cancel", cancel_upload)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_upload)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(upload_conv_handler)

    logger.info("🤖 Bot en cours d'exécution...")
    app.run_polling()
