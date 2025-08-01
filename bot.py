# bot.py
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

# Configuration
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # ID administrateur
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Structure des données
file_storage = {}
MAIN_CATEGORIES = ["KF", "BELO", "SOULAN", "KfClone", "Filtres", "Géolocalisation"]
SUB_CATEGORIES = ["SMS", "CONTACTS", "Historiques appels", "iMessenger", "Facebook Messenger", 
                 "Audio", "Vidéo", "Documents", "Autres"]

# États de conversation
SELECTING_CATEGORY, SELECTING_SUBCATEGORY, UPLOADING_FILE = range(3)

# Helper pour créer des menus
def create_menu(buttons, back_button=False, back_data="main_menu", columns=1):
    keyboard = []
    row = []
    
    for i, btn in enumerate(buttons):
        row.append(InlineKeyboardButton(btn, callback_data=btn))
        if (i + 1) % columns == 0:
            keyboard.append(row)
            row = []
    
    if row:  # Ajouter les boutons restants
        keyboard.append(row)
    
    if back_button:
        keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data=back_data)])
    
    return InlineKeyboardMarkup(keyboard)

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
    
    await query.edit_message_text(
        f"📁 Catégorie : {category}\nSélectionnez une sous-catégorie :",
        reply_markup=create_menu(submenu_buttons, True, "main_menu", columns=2)
    )

async def handle_subcategory(query, context, subcategory):
    category = context.user_data.get("current_category")
    
    # Stocker la sous-catégorie pour l'upload
    context.user_data["current_subcategory"] = subcategory
    
    # Vérifier si des fichiers existent
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

    # Afficher les fichiers disponibles
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
    files = file_storage.get(category, {}).get(subcategory, [])
    
    if file_idx >= len(files):
        await query.answer("❌ Fichier introuvable", show_alert=True)
        return
    
    file_info = files[file_idx]
    
    try:
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=file_info["file_id"],
            caption=f"📥 {file_info['name']}"
        )
    except Exception as e:
        logging.error(f"Error sending file: {e}")
        await query.answer("❌ Erreur lors du téléchargement", show_alert=True)

# Gestion de l'upload (admin seulement)
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
    
    # Initialiser le stockage si nécessaire
    if category not in file_storage:
        file_storage[category] = {}
    if subcategory not in file_storage[category]:
        file_storage[category][subcategory] = []

    file = None
    file_name = "Fichier"
    
    # Récupérer le fichier selon son type
    if update.message.document:
        file = update.message.document
        file_name = file.file_name
    elif update.message.photo:
        file = update.message.photo[-1]  # Meilleure qualité
        file_name = "photo.jpg"
    elif update.message.audio:
        file = update.message.audio
        file_name = file.file_name or "audio.mp3"
    elif update.message.video:
        file = update.message.video
        file_name = file.file_name or "video.mp4"
    elif update.message.voice:
        file = update.message.voice
        file_name = "audio.ogg"
    
    if file:
        # Stocker les métadonnées
        file_storage[category][subcategory].append({
            "file_id": file.file_id,
            "name": file_name
        })
        
        await update.message.reply_text(
            f"✅ Fichier ajouté avec succès à:\n"
            f"Catégorie: {category}\n"
            f"Sous-catégorie: {subcategory}\n\n"
            f"Nom: {file_name}"
        )
    else:
        await update.message.reply_text("❌ Format de fichier non supporté")
    
    return ConversationHandler.END

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
    app = ApplicationBuilder().token(TOKEN).build()

    # Handler de conversation pour l'upload
    upload_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_file_upload, pattern="^upload_file$")],
        states={
            UPLOADING_FILE: [
                MessageHandler(filters.DOCUMENT | filters.PHOTO | filters.AUDIO | 
                              filters.VIDEO | filters.VOICE, handle_uploaded_file),
                CommandHandler("cancel", cancel_upload)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_upload)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(upload_conv_handler)

    print("🤖 Bot en cours d'exécution...")
    app.run_polling()
