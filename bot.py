from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler
)
import os
import logging
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

# Configuration
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
PERSIST_DIR = "/opt/render/.render"
PERSIST_FILE = os.path.join(PERSIST_DIR, "file_storage.json")

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
UPLOADING_FILE = 0

# Helper pour créer des menus
def create_menu(buttons, back_button=False, back_data="main_menu", columns=1):
    keyboard = []
    row = []
    
    for i, btn in enumerate(buttons):
        if isinstance(btn, tuple):
            text, callback = btn
            row.append(InlineKeyboardButton(text, callback_data=callback))
        else:
            row.append(InlineKeyboardButton(btn, callback_data=btn))
        
        if (i + 1) % columns == 0:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    if back_button:
        keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data=back_data)])
    
    return InlineKeyboardMarkup(keyboard)

# Charger l'état initial
def load_initial_storage():
    try:
        os.makedirs(PERSIST_DIR, exist_ok=True)
        
        if os.path.exists(PERSIST_FILE):
            try:
                with open(PERSIST_FILE, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("Fichier JSON corrompu, réinitialisation...")
                return {}
        return {}
    except Exception as e:
        logger.error(f"Erreur de chargement du stockage: {e}")
        return {}

# Sauvegarder le stockage
def save_storage(data):
    try:
        with open(PERSIST_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Erreur de sauvegarde: {e}")

# Health Check Server
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

def run_health_server():
    server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    logger.info("🩺 Serveur health check démarré sur le port 8080")
    server.serve_forever()

# Commandes
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_msg = f"👋 Bonjour {user.first_name} !\nChoisissez une catégorie :"
    await update.message.reply_text(welcome_msg, reply_markup=create_menu(MAIN_CATEGORIES, columns=2))

# Gestion des boutons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    logger.info(f"Bouton pressé: {query.data} par {query.from_user.id}")

    if query.data == "main_menu":
        await show_main_menu(query)
    elif query.data in MAIN_CATEGORIES:
        await handle_main_category(query, context, query.data)
    elif query.data in SUB_CATEGORIES:
        await handle_subcategory(query, context, query.data)
    elif query.data.startswith("file_"):
        await send_file_to_user(query, context, query.data)
    elif query.data == "upload_file":
        await start_file_upload(query, context)
    elif query.data == "manage_files":
        await show_file_management(query, context)
    elif query.data.startswith("delete_"):
        await delete_file(query, context, query.data)
    elif query.data == "cancel_upload":
        await query.edit_message_text("❌ Upload annulé")
    elif query.data == "share_location":
        await handle_share_location(query)

async def show_main_menu(query):
    await query.edit_message_text(
        "📂 Menu principal :",
        reply_markup=create_menu(MAIN_CATEGORIES, columns=2)
    )

async def handle_main_category(query, context, category):
    context.user_data["current_category"] = category
    logger.info(f"Catégorie sélectionnée: {category}")
    
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
    
    # Ajouter boutons spéciaux pour admin
    if query.from_user.id == ADMIN_ID:
        submenu_buttons.append(("⬆️ Upload Fichier", "upload_file"))
        submenu_buttons.append(("⚙️ Gérer Fichiers", "manage_files"))
    
    await query.edit_message_text(
        f"📁 Catégorie : {category}\nSélectionnez une sous-catégorie :",
        reply_markup=create_menu(submenu_buttons, True, "main_menu", columns=2)
    )

async def handle_subcategory(query, context, subcategory):
    category = context.user_data.get("current_category")
    context.user_data["current_subcategory"] = subcategory
    logger.info(f"Sous-catégorie sélectionnée: {subcategory} dans {category}")
    
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

    # Afficher les fichiers avec statistiques
    file_count = len(files)
    last_upload = max([f.get("uploaded_at", "") for f in files], default="")
    
    keyboard = []
    for idx, file_info in enumerate(files):
        keyboard.append([InlineKeyboardButton(
            f"📄 {file_info['name']}", 
            callback_data=f"file_{idx}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data=category)])
    
    await query.edit_message_text(
        f"📂 Fichiers disponibles dans '{subcategory}':\n"
        f"• Total: {file_count}\n"
        f"• Dernier ajout: {last_upload[:10] if last_upload else 'N/A'}",
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
        logger.info(f"Envoi du fichier: {file_info['name']} à {query.message.chat_id}")
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
        logger.error(f"Erreur d'envoi du fichier: {e}")
        await query.answer("❌ Erreur lors du téléchargement", show_alert=True)

# Gestion de l'upload
async def start_file_upload(query, context):
    logger.info("Début du processus d'upload")
    
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
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            f"⬆️ Envoyez le fichier à ajouter à:\n"
            f"Catégorie: {category}\n"
            f"Sous-catégorie: {subcategory}\n\n"
            "Vous pouvez envoyer n'importe quel type de fichier.\n"
            "/cancel pour annuler"
        )
    )
    
    return UPLOADING_FILE

async def handle_uploaded_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Fichier reçu pour upload")
    
    # Vérification de sécurité supplémentaire
    if update.effective_user.id != ADMIN_ID:
        logger.warning(f"Tentative d'upload non autorisée par {update.effective_user.id}")
        await update.message.reply_text("⛔ Action réservée à l'administrateur")
        return ConversationHandler.END
    
    user_data = context.user_data
    category = user_data.get("upload_category")
    subcategory = user_data.get("upload_subcategory")
    
    if not category or not subcategory:
        logger.error("Catégorie non définie pour l'upload")
        await update.message.reply_text("❌ Erreur: Catégorie non définie. Veuillez recommencer.")
        return ConversationHandler.END
    
    # Récupérer ou initialiser le stockage
    file_storage = context.bot_data.get("file_storage", {})
    if not file_storage:
        file_storage = {}
    
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
    elif update.message.text and update.message.text != "/cancel":
        await update.message.reply_text("❌ Veuillez envoyer un fichier valide")
        return UPLOADING_FILE
    else:
        return ConversationHandler.END
    
    if file:
        # Vérification des doublons
        existing_files = [f["name"] for f in file_storage[category][subcategory]]
        if file_name in existing_files:
            await update.message.reply_text(f"⚠️ Un fichier avec le nom '{file_name}' existe déjà")
            return UPLOADING_FILE
        
        file_info = {
            "file_id": file.file_id,
            "name": file_name,
            "type": file_type,
            "uploaded_at": datetime.now().isoformat(),
            "uploaded_by": update.message.from_user.id
        }
        
        file_storage[category][subcategory].append(file_info)
        context.bot_data["file_storage"] = file_storage
        save_storage(file_storage)
        
        logger.info(f"Fichier ajouté: {file_name} dans {category}/{subcategory}")
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
            
            # Si plus de fichiers, supprimer la sous-catégorie
            if not file_storage[category][subcategory]:
                del file_storage[category][subcategory]
            
            # Sauvegarder les modifications
            context.bot_data["file_storage"] = file_storage
            save_storage(file_storage)
            
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
    if not TOKEN:
        logger.error("La variable BOT_TOKEN doit être définie")
        exit(1)
    if not ADMIN_ID:
        logger.error("La variable ADMIN_ID doit être définie")
        exit(1)
    
    logger.info(f"Token: {TOKEN[:10]}...")
    logger.info(f"Admin ID: {ADMIN_ID}")
    
    # Démarrer le serveur health check dans un thread séparé
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # Charger le stockage initial
    file_storage = load_initial_storage()
    logger.info(f"Stockage initial chargé: {len(file_storage)} catégories")
    
    # Créer l'application
    app = ApplicationBuilder().token(TOKEN).build()
    
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

    logger.info("🤖 Démarrage du bot...")
    logger.info(f"Chemin de persistance: {PERSIST_FILE}")
    app.run_polling()
