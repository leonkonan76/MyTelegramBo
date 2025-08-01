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
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # ID administrateur (à définir dans les variables d'environnement)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Structure des données
file_storage = {}
MAIN_CATEGORIES = ["KF", "BELO", "SOULAN", "KfClone", "Filtres", "Géolocalisation"]
SUB_CATEGORIES = ["SMS", "CONTACTS", "Historiques appels", "iMessenger", "Facebook Messenger", 
                 "Audio", "Vidéo", "Documents", "Autres"]

# États de conversation pour l'upload
SELECTING_CATEGORY, SELECTING_SUBCATEGORY, UPLOADING_FILE = range(3)

# Helper pour créer des menus
def create_menu(buttons, back_button=False, back_data="main_menu"):
    keyboard = []
    for btn in buttons:
        keyboard.append([InlineKeyboardButton(btn, callback_data=btn)])
    if back_button:
        keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data=back_data)])
    return InlineKeyboardMarkup(keyboard)

# Commandes
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_msg = f"👋 Bonjour {user.first_name} !\nChoisissez une catégorie :"
    await update.message.reply_text(welcome_msg, reply_markup=create_menu(MAIN_CATEGORIES))

# Gestion des boutons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "main_menu":
        await show_main_menu(query)
    elif data in MAIN_CATEGORIES:
        await handle_main_category(query, data)
    elif data in SUB_CATEGORIES:
        await handle_subcategory(query, data)
    elif data.startswith("file_"):
        await send_file_to_user(query, data)
    elif data == "upload_file":
        await start_file_upload(query)

async def show_main_menu(query):
    await query.edit_message_text(
        "📂 Menu principal :",
        reply_markup=create_menu(MAIN_CATEGORIES)
    )

async def handle_main_category(query, category):
    if category == "Géolocalisation":
        await handle_geolocation(query)
    else:
        context.user_data["current_category"] = category
        await show_subcategories_menu(query, category)

async def handle_geolocation(query):
    await query.message.reply_text(
        "📍 Partagez votre position :",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Partager position", callback_data="share_location")
        ]])
    )

async def show_subcategories_menu(query, category):
    submenu_buttons = SUB_CATEGORIES.copy()
    
    # Ajouter bouton upload pour admin
    if query.from_user.id == ADMIN_ID:
        submenu_buttons.append("⬆️ Upload Fichier")
    
    await query.edit_message_text(
        f"📁 Catégorie : {category}\nSélectionnez une sous-catégorie :",
        reply_markup=create_menu(submenu_buttons, True, "main_menu")
    )

async def handle_subcategory(query, subcategory):
    category = context.user_data.get("current_category")
    files = file_storage.get(category, {}).get(subcategory, [])
    
    if not files:
        await query.edit_message_text(
            f"📭 Aucun fichier dans '{subcategory}'",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Retour", callback_data=category)
            ]])
        )
        return

    keyboard = []
    for idx, file_info in enumerate(files):
        keyboard.append([InlineKeyboardButton(
            f"📄 {file_info['name']}", 
            callback_data=f"file_{category}_{subcategory}_{idx}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data=category)])
    
    await query.edit_message_text(
        f"📂 Fichiers disponibles ({subcategory}):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def send_file_to_user(query, file_data):
    _, category, subcategory, idx = file_data.split('_')
    file_info = file_storage[category][subcategory][int(idx)]
    
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
async def start_file_upload(query):
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Action réservée à l'admin", show_alert=True)
        return
    
    await query.edit_message_text(
        "📤 Processus d'upload:\nChoisissez une catégorie :",
        reply_markup=create_menu(MAIN_CATEGORIES, True, "cancel_upload")
    )
    return SELECTING_CATEGORY

async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_upload":
        await query.edit_message_text("❌ Upload annulé")
        return ConversationHandler.END
    
    context.user_data["upload_category"] = query.data
    await query.edit_message_text(
        f"📁 Catégorie: {query.data}\nChoisissez une sous-catégorie:",
        reply_markup=create_menu(SUB_CATEGORIES, True, "start_upload")
    )
    return SELECTING_SUBCATEGORY

async def subcategory_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "start_upload":
        return await start_file_upload(query)
    
    context.user_data["upload_subcategory"] = query.data
    await query.edit_message_text(
        "⬆️ Envoyez maintenant le fichier (document, audio, vidéo, photo)...\n"
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
    file_type = None
    
    # Déterminer le type de fichier
    if update.message.document:
        file = update.message.document
        file_type = "document"
    elif update.message.photo:
        file = update.message.photo[-1]  # Meilleure qualité
        file_type = "photo"
    elif update.message.audio:
        file = update.message.audio
        file_type = "audio"
    elif update.message.video:
        file = update.message.video
        file_type = "video"
    
    if file:
        # Stocker les métadonnées
        file_storage[category][subcategory].append({
            "file_id": file.file_id,
            "name": file.file_name or f"{file_type}_{file.file_id[:8]}",
            "type": file_type
        })
        
        await update.message.reply_text(
            f"✅ Fichier ajouté avec succès à:\n"
            f"Catégorie: {category}\n"
            f"Sous-catégorie: {subcategory}"
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
            SELECTING_CATEGORY: [CallbackQueryHandler(category_selected)],
            SELECTING_SUBCATEGORY: [CallbackQueryHandler(subcategory_selected)],
            UPLOADING_FILE: [MessageHandler(filters.ATTACHMENT, handle_uploaded_file)]
        },
        fallbacks=[CommandHandler("cancel", cancel_upload)],
        map_to_parent={ConversationHandler.END: -1}
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(upload_conv_handler)

    print("🤖 Bot en cours d'exécution...")
    app.run_polling()