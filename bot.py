from telegram import (
    Update, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    MessageHandler, filters, CallbackQueryHandler
)
import os

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 123456789  # <-- Remplace par ton ID Telegram admin

# Catégories et sous-catégories
main_buttons = ["KF", "BELO", "SOULAN", "KfClone", "Filtres", "Géolocalisation"]
sub_buttons = ["SMS", "CONTACTS", "Historiques appels", "iMessenger", "Facebook Messenger", "Audio", "Vidéo", "Documents", "Autres"]

# Structure de stockage des fichiers (en mémoire)
# Exemple : {"KF": {"SMS": [{"filename": ..., "file_id": ...}, ...]}, ...}
files_db = {cat: {sub: [] for sub in sub_buttons} for cat in main_buttons if cat != "Géolocalisation"}

def get_main_menu():
    keyboard = [[InlineKeyboardButton(text=btn, callback_data=f"cat|{btn}")] for btn in main_buttons]
    return InlineKeyboardMarkup(keyboard)

def get_sub_menu(category):
    keyboard = [[InlineKeyboardButton(text=sub, callback_data=f"subcat|{category}|{sub}")] for sub in sub_buttons]
    keyboard.append([InlineKeyboardButton("⬅️ Retour au menu principal", callback_data="start")])
    return InlineKeyboardMarkup(keyboard)

def get_files_menu(category, subcat):
    files = files_db.get(category, {}).get(subcat, [])
    keyboard = []
    for idx, f in enumerate(files):
        keyboard.append([InlineKeyboardButton(f"{f['filename']}", callback_data=f"file|{category}|{subcat}|{idx}")])
    keyboard.append([InlineKeyboardButton("⬅️ Retour aux sous-catégories", callback_data=f"cat|{category}")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bienvenue dans le bot MyTelegramBot. Choisissez une catégorie :", reply_markup=get_main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "start":
        await query.edit_message_text(text="Bienvenue dans le bot MyTelegramBot. Choisissez une catégorie :", reply_markup=get_main_menu())
        return

    if data.startswith("cat|"):
        # Afficher sous-catégories d'une catégorie
        _, category = data.split("|", 1)
        if category == "Géolocalisation":
            keyboard = ReplyKeyboardMarkup(
                [[KeyboardButton("Envoyer ma position", request_location=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await query.message.reply_text("Merci de partager votre position :", reply_markup=keyboard)
            return
        await query.edit_message_text(text=f"Catégorie : {category}. Choisissez une sous-catégorie :", reply_markup=get_sub_menu(category))
        return

    if data.startswith("subcat|"):
        # Afficher fichiers d'une sous-catégorie
        _, category, subcat = data.split("|", 2)
        await query.edit_message_text(text=f"Fichiers dans {category} > {subcat} :", reply_markup=get_files_menu(category, subcat))
        return

    if data.startswith("file|"):
        # Envoyer le fichier aux utilisateurs
        _, category, subcat, idx_str = data.split("|", 3)
        idx = int(idx_str)
        try:
            file_entry = files_db[category][subcat][idx]
            await query.message.reply_document(document=file_entry["file_id"], filename=file_entry["filename"])
        except (KeyError, IndexError):
            await query.message.reply_text("Fichier introuvable.")
        return

    # Cas autres boutons sub_buttons simples
    if data in sub_buttons:
        await query.message.reply_text(f"Vous avez sélectionné : {data}")
        return

    # Cas autres boutons main_buttons simples (hors catégories déjà gérées)
    if data in main_buttons:
        await query.message.reply_text(f"Vous avez choisi {data}. Voici les options disponibles :", reply_markup=get_sub_menu(data))
        return

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
        await update.message.reply_text(f"Localisation reçue :\nLatitude: {lat}\nLongitude: {lon}")

# Gestion upload fichiers - seulement admin
# Commande : /upload <catégorie> <sous-catégorie>
async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("Seul l'administrateur peut uploader des fichiers.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: /upload <catégorie> <sous-catégorie>")
        return
    category, subcat = args
    if category not in files_db or subcat not in files_db[category]:
        await update.message.reply_text("Catégorie ou sous-catégorie inconnue.")
        return

    await update.message.reply_text(f"Envoyez maintenant un fichier à ajouter dans {category} > {subcat}.")

    # Stocker dans context pour traitement dans handler document
    context.user_data["upload_target"] = (category, subcat)

# Traitement des documents envoyés par admin après /upload
async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("Seuls les administrateurs peuvent envoyer des fichiers.")
        return

    if "upload_target" not in context.user_data:
        await update.message.reply_text("Merci de lancer la commande /upload avant d'envoyer un fichier.")
        return

    doc = update.message.document
    if not doc:
        await update.message.reply_text("Ce message ne contient pas de fichier.")
        return

    category, subcat = context.user_data["upload_target"]

    # Sauvegarde en mémoire
    files_db[category][subcat].append({
        "filename": doc.file_name,
        "file_id": doc.file_id
    })

    await update.message.reply_text(f"Fichier {doc.file_name} ajouté dans {category} > {subcat}.")

    # Nettoyer le contexte
    del context.user_data["upload_target"]

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Commande inconnue. Utilisez /start pour commencer.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))

    app.add_handler(CommandHandler("upload", upload_command))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))

    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    print("Bot en cours d'exécution...")
    app.run_polling()

if __name__ == "__main__":
    main()
