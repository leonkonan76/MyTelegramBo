import os
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# Configuration de la journalisation
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Chemins et constantes
STORAGE_PATH = "/opt/render/project/.render/storage/file_storage.json"
ADMIN_ID = int(os.getenv("ADMIN_ID", "465520526"))  # ID de l'admin (à configurer via Render)
CATEGORY_STATE, SUBCATEGORY_STATE, FILE_STATE = range(3)

# Catégories et sous-catégories
MAIN_CATEGORIES = ["KF", "BELO", "SOULAN", "KfClone", "Filtres", "Géolocalisation"]
SUB_CATEGORIES = [
    "SMS",
    "Contacts",
    "Historiques appels",
    "iMessenger",
    "Facebook Messenger",
    "Audio",
    "Vidéo",
    "Documents",
    "Autres",
]

# Charger les données de stockage
def load_storage(file_path):
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        # Initialiser une structure vide avec toutes les catégories et sous-catégories
        storage = {'files': {}, 'logs': []}
        for category in MAIN_CATEGORIES:
            storage['files'][category] = {subcat: [] for subcat in SUB_CATEGORIES}
        return storage
    except Exception as e:
        logger.error(f"Erreur lors du chargement du stockage : {e}")
        return {'files': {cat: {subcat: [] for subcat in SUB_CATEGORIES} for cat in MAIN_CATEGORIES}, 'logs': []}

# Sauvegarder les données de stockage
def save_storage(file_path, data):
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde du stockage : {e}")

# Ajouter un journal d'action
def log_action(storage, user_id, action, details):
    storage['logs'].append({
        'user_id': user_id,
        'action': action,
        'details': details,
        'timestamp': datetime.utcnow().isoformat()
    })
    save_storage(STORAGE_PATH, storage)

# Vérifier si l'utilisateur est admin
def is_admin(user_id):
    return user_id == ADMIN_ID

# Commande /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Commande /start reçue de l'utilisateur {user.id} ({user.username})")
    
    storage = load_storage(STORAGE_PATH)
    log_action(storage, user.id, "start", f"Commande /start exécutée par {user.username or user.first_name}")
    
    # Menu principal
    buttons = [
        [InlineKeyboardButton("📂 Voir les fichiers", callback_data="view_files")],
        [InlineKeyboardButton("📍 Envoyer géolocalisation", callback_data="send_location")],
    ]
    if is_admin(user.id):
        buttons.append([InlineKeyboardButton("⬆️ Téléverser un fichier", callback_data="upload_file")])
        buttons.append([InlineKeyboardButton("🗑️ Supprimer un fichier", callback_data="delete_file")])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        f"Bienvenue sur @konntek_bot, {user.first_name} ! Choisissez une option :",
        reply_markup=reply_markup
    )

# Commande /logs (réservée à l'admin)
async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("🚫 Cette commande est réservée à l'administrateur.")
        return
    
    storage = load_storage(STORAGE_PATH)
    log_action(storage, user.id, "logs", "Consultation des journaux")
    
    if not storage['logs']:
        await update.message.reply_text("Aucun journal d'activité disponible.")
        return
    
    response = "📜 Journaux d'activité :\n"
    for log in storage['logs'][-10:]:  # Limiter aux 10 derniers pour éviter un message trop long
        response += f"[{log['timestamp']}] Utilisateur {log['user_id']}: {log['action']} - {log['details']}\n"
    
    await update.message.reply_text(response)

# Gestion des callbacks principaux
async def main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    storage = load_storage(STORAGE_PATH)
    
    if query.data == "view_files":
        log_action(storage, user.id, "view_files", "Consultation des catégories")
        buttons = [[InlineKeyboardButton(category, callback_data=f"cat_{category}")] for category in MAIN_CATEGORIES]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.reply_text("Choisissez une catégorie :", reply_markup=reply_markup)
    
    elif query.data == "send_location":
        log_action(storage, user.id, "request_location", "Demande de géolocalisation")
        await query.message.reply_text("Veuillez partager votre position via Telegram.")
    
    elif query.data == "upload_file" and is_admin(user.id):
        log_action(storage, user.id, "upload_start", "Début du processus d'upload")
        buttons = [[InlineKeyboardButton(category, callback_data=f"upload_cat_{category}")] for category in MAIN_CATEGORIES]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.reply_text("Choisissez une catégorie pour le fichier :", reply_markup=reply_markup)
        return CATEGORY_STATE
    
    elif query.data == "delete_file" and is_admin(user.id):
        log_action(storage, user.id, "delete_start", "Début du processus de suppression")
        buttons = [[InlineKeyboardButton(category, callback_data=f"delete_cat_{category}")] for category in MAIN_CATEGORIES]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.reply_text("Choisissez une catégorie pour supprimer un fichier :", reply_markup=reply_markup)

# Gestion des catégories (lecture)
async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    category = query.data.replace("cat_", "")
    if category not in MAIN_CATEGORIES:
        await query.message.reply_text("Catégorie invalide.")
        return
    
    storage = load_storage(STORAGE_PATH)
    log_action(storage, update.effective_user.id, "category_view", f"Consultation de la catégorie {category}")
    
    buttons = [[InlineKeyboardButton(subcat, callback_data=f"subcat_{category}_{subcat}")] for subcat in SUB_CATEGORIES]
    reply_markup = InlineKeyboardMarkup(buttons + [[InlineKeyboardButton("⬅️ Retour", callback_data="view_files")]])
    await query.message.reply_text(f"Sous-catégories pour {category} :", reply_markup=reply_markup)

# Gestion des sous-catégories (lecture)
async def subcategory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, category, subcategory = query.data.split("_", 2)
    if category not in MAIN_CATEGORIES or subcategory not in SUB_CATEGORIES:
        await query.message.reply_text("Sous-catégorie invalide.")
        return
    
    storage = load_storage(STORAGE_PATH)
    log_action(storage, update.effective_user.id, "subcategory_view", f"Consultation de {category}/{subcategory}")
    
    files = storage['files'].get(category, {}).get(subcategory, [])
    if not files:
        await query.message.reply_text(f"Aucun fichier dans {category}/{subcategory}.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Retour", callback_data=f"cat_{category}")]]))
        return
    
    buttons = [[InlineKeyboardButton(f"Fichier {i+1}", callback_data=f"file_{category}_{subcategory}_{file_id}")] for i, file_id in enumerate(files)]
    buttons.append([InlineKeyboardButton("⬅️ Retour", callback_data=f"cat_{category}")])
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.message.reply_text(f"Fichiers dans {category}/{subcategory} :", reply_markup=reply_markup)

# Envoi de fichier
async def send_file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, category, subcategory, file_id = query.data.split("_", 3)
    storage = load_storage(STORAGE_PATH)
    log_action(storage, update.effective_user.id, "file_access", f"Accès au fichier {file_id} dans {category}/{subcategory}")
    
    try:
        if file_id.endswith(".jpg") or file_id.endswith(".png"):
            await query.message.reply_photo(file_id.split("_")[0])
        elif file_id.endswith(".mp3") or file_id.endswith(".ogg"):
            await query.message.reply_audio(file_id.split("_")[0])
        elif file_id.endswith(".mp4"):
            await query.message.reply_video(file_id.split("_")[0])
        elif file_id.endswith(".oga"):
            await query.message.reply_voice(file_id.split("_")[0])
        else:
            await query.message.reply_document(file_id.split("_")[0])
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du fichier {file_id} : {e}")
        await query.message.reply_text("Erreur lors de l'envoi du fichier.")

# ConversationHandler pour /upload (réservé à l'admin)
async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("🚫 Cette commande est réservée à l'administrateur.")
        return ConversationHandler.END
    
    storage = load_storage(STORAGE_PATH)
    log_action(storage, user.id, "upload_start", "Début du processus d'upload")
    
    buttons = [[InlineKeyboardButton(category, callback_data=f"upload_cat_{category}")] for category in MAIN_CATEGORIES]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("Choisissez une catégorie pour le fichier :", reply_markup=reply_markup)
    return CATEGORY_STATE

async def upload_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("🚫 Action réservée à l'administrateur.")
        return ConversationHandler.END
    
    category = query.data.replace("upload_cat_", "")
    if category not in MAIN_CATEGORIES:
        await query.message.reply_text("Catégorie invalide.")
        return ConversationHandler.END
    
    context.user_data['category'] = category
    storage = load_storage(STORAGE_PATH)
    log_action(storage, update.effective_user.id, "upload_category", f"Catégorie choisie : {category}")
    
    buttons = [[InlineKeyboardButton(subcat, callback_data=f"upload_subcat_{subcat}")] for subcat in SUB_CATEGORIES]
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.message.reply_text(f"Choisissez une sous-catégorie pour {category} :", reply_markup=reply_markup)
    return SUBCATEGORY_STATE

async def upload_subcategory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("🚫 Action réservée à l'administrateur.")
        return ConversationHandler.END
    
    subcategory = query.data.replace("upload_subcat_", "")
    category = context.user_data.get('category')
    if category not in MAIN_CATEGORIES or subcategory not in SUB_CATEGORIES:
        await query.message.reply_text("Sous-catégorie invalide.")
        return ConversationHandler.END
    
    context.user_data['subcategory'] = subcategory
    storage = load_storage(STORAGE_PATH)
    log_action(storage, update.effective_user.id, "upload_subcategory", f"Sous-catégorie choisie : {subcategory}")
    
    await query.message.reply_text("Veuillez envoyer le fichier à uploader (photo, document, audio, vidéo, voix).")
    return FILE_STATE

async def upload_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("🚫 Action réservée à l'administrateur.")
        return ConversationHandler.END
    
    file = (
        update.message.document or
        (update.message.photo[-1] if update.message.photo else None) or
        update.message.audio or
        update.message.video or
        update.message.voice
    )
    if not file:
        await update.message.reply_text("Aucun fichier valide reçu. Veuillez envoyer un fichier, une photo, un audio, une vidéo ou un message vocal.")
        return FILE_STATE
    
    file_id = file.file_id if hasattr(file, 'file_id') else file.file_unique_id
    file_ext = (
        ".jpg" if update.message.photo else
        ".mp3" if update.message.audio else
        ".mp4" if update.message.video else
        ".oga" if update.message.voice else
        os.path.splitext(file.file_name)[1] if hasattr(file, 'file_name') else ".bin"
    )
    
    category = context.user_data.get('category')
    subcategory = context.user_data.get('subcategory')
    
    storage = load_storage(STORAGE_PATH)
    storage['files'][category][subcategory].append(f"{file_id}_{file_ext}")
    log_action(storage, user.id, "upload_file", f"Fichier {file_id} téléversé dans {category}/{subcategory}")
    save_storage(STORAGE_PATH, storage)
    
    await update.message.reply_text(f"Fichier téléversé avec succès dans {category}/{subcategory} !")
    return ConversationHandler.END

async def cancel_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    storage = load_storage(STORAGE_PATH)
    log_action(storage, user.id, "cancel_upload", "Annulation du processus d'upload")
    
    await update.message.reply_text("Téléversement annulé.")
    return ConversationHandler.END

# Gestion de la suppression (réservée à l'admin)
async def delete_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("🚫 Action réservée à l'administrateur.")
        return
    
    category = query.data.replace("delete_cat_", "")
    if category not in MAIN_CATEGORIES:
        await query.message.reply_text("Catégorie invalide.")
        return
    
    context.user_data['category'] = category
    storage = load_storage(STORAGE_PATH)
    log_action(storage, update.effective_user.id, "delete_category", f"Catégorie choisie pour suppression : {category}")
    
    buttons = [[InlineKeyboardButton(subcat, callback_data=f"delete_subcat_{category}_{subcat}")] for subcat in SUB_CATEGORIES]
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.message.reply_text(f"Choisissez une sous-catégorie pour supprimer un fichier dans {category} :", reply_markup=reply_markup)

async def delete_subcategory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("🚫 Action réservée à l'administrateur.")
        return
    
    _, category, subcategory = query.data.split("_", 2)
    if category not in MAIN_CATEGORIES or subcategory not in SUB_CATEGORIES:
        await query.message.reply_text("Sous-catégorie invalide.")
        return
    
    storage = load_storage(STORAGE_PATH)
    files = storage['files'].get(category, {}).get(subcategory, [])
    if not files:
        await query.message.reply_text(f"Aucun fichier dans {category}/{subcategory}.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Retour", callback_data=f"delete_cat_{category}")]]))
        return
    
    context.user_data['category'] = category
    context.user_data['subcategory'] = subcategory
    buttons = [[InlineKeyboardButton(f"Fichier {i+1}", callback_data=f"delete_file_{category}_{subcategory}_{file_id}")] for i, file_id in enumerate(files)]
    buttons.append([InlineKeyboardButton("⬅️ Retour", callback_data=f"delete_cat_{category}")])
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.message.reply_text(f"Choisissez un fichier à supprimer dans {category}/{subcategory} :", reply_markup=reply_markup)

async def delete_file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("🚫 Action réservée à l'administrateur.")
        return
    
    _, category, subcategory, file_id = query.data.split("_", 3)
    storage = load_storage(STORAGE_PATH)
    
    if file_id in storage['files'][category][subcategory]:
        storage['files'][category][subcategory].remove(file_id)
        log_action(storage, update.effective_user.id, "delete_file", f"Fichier {file_id} supprimé de {category}/{subcategory}")
        save_storage(STORAGE_PATH, storage)
        await query.message.reply_text(f"Fichier supprimé de {category}/{subcategory}.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Retour", callback_data=f"delete_cat_{category}")]]))
    else:
        await query.message.reply_text("Fichier introuvable.")

# Gestion de la géolocalisation
async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    location = update.message.location
    if not location:
        await update.message.reply_text("Aucune position reçue. Veuillez partager votre position via Telegram.")
        return
    
    storage = load_storage(STORAGE_PATH)
    log_action(storage, user.id, "location_shared", f"Position reçue : lat={location.latitude}, lon={location.longitude}")
    
    await update.message.reply_text(f"Position reçue : Latitude {location.latitude}, Longitude {location.longitude}")

# Gestion principale
async def main():
    # Charger le jeton d'API depuis une variable d'environnement
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("Le jeton TELEGRAM_TOKEN n'est pas défini dans les variables d'environnement.")
        return

    # Initialiser l'application avec python-telegram-bot v20.8
    application = Application.builder().token(token).build()

    # Charger le stockage
    storage = load_storage(STORAGE_PATH)
    logger.info(f"Stockage chargé : {len(storage['logs'])} journaux, structure des fichiers initialisée")

    # Supprimer tout webhook existant pour utiliser le polling
    await application.bot.delete_webhook()

    # Ajouter les gestionnaires de commandes
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("logs", logs))
    
    # Gestionnaires de callbacks
    application.add_handler(CallbackQueryHandler(main_callback, pattern="^(view_files|send_location|upload_file|delete_file)$"))
    application.add_handler(CallbackQueryHandler(category_callback, pattern="^cat_"))
    application.add_handler(CallbackQueryHandler(subcategory_callback, pattern="^subcat_"))
    application.add_handler(CallbackQueryHandler(send_file_callback, pattern="^file_"))
    application.add_handler(CallbackQueryHandler(delete_category_callback, pattern="^delete_cat_"))
    application.add_handler(CallbackQueryHandler(delete_subcategory_callback, pattern="^delete_subcat_"))
    application.add_handler(CallbackQueryHandler(delete_file_callback, pattern="^delete_file_"))

    # ConversationHandler pour /upload
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("upload", upload)],
        states={
            CATEGORY_STATE: [CallbackQueryHandler(upload_category_callback, pattern="^upload_cat_")],
            SUBCATEGORY_STATE: [CallbackQueryHandler(upload_subcategory_callback, pattern="^upload_subcat_")],
            FILE_STATE: [MessageHandler(filters.Document.ALL | filters.PHOTO | filters.AUDIO | filters.VIDEO | filters.VOICE, upload_file)],
        },
        fallbacks=[CommandHandler("cancel", cancel_upload)],
    )
    application.add_handler(conv_handler)

    # Gestionnaire pour la géolocalisation
    application.add_handler(MessageHandler(filters.LOCATION, location_handler))

    # Démarrer le polling
    await application.run_polling(timeout=15)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
