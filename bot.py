import json
import os
from telegram import (
    Update, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    MessageHandler, filters, CallbackQueryHandler
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 123456789  # Remplace par ton ID
FILES_DB_PATH = "files.json"

main_buttons = ["KF", "BELO", "SOULAN", "KfClone", "Filtres", "Géolocalisation"]
sub_buttons = ["SMS", "CONTACTS", "Historiques appels", "iMessenger", "Facebook Messenger", "Audio", "Vidéo", "Documents", "Autres"]

# Chargement ou initialisation du fichier JSON
def load_files_db():
    if os.path.exists(FILES_DB_PATH):
        with open(FILES_DB_PATH, "r") as f:
            return json.load(f)
    return {cat: {sub: [] for sub in sub_buttons} for cat in main_buttons if cat != "Géolocalisation"}

def save_files_db():
    with open(FILES_DB_PATH, "w") as f:
        json.dump(files_db, f)

files_db = load_files_db()

def get_main_menu():
    keyboard = [[InlineKeyboardButton(text=btn, callback_data=f"cat|{btn}")] for btn in main_buttons]
    return InlineKeyboardMarkup(keyboard)

def get_sub_menu(category):
    keyboard = [[InlineKeyboardButton(text=sub, callback_data=f"subcat|{category}|{sub}")] for sub in sub_buttons]
    keyboard.append([InlineKeyboardButton("⬅️ Retour", callback_data="start")])
    return InlineKeyboardMarkup(keyboard)

def get_files_menu(category, subcat):
    files = files_db.get(category, {}).get(subcat, [])
    keyboard = [[InlineKeyboardButton(f["filename"], callback_data=f"file|{category}|{subcat}|{i}")] for i, f in enumerate(files)]
    keyboard.append([InlineKeyboardButton("⬅️ Retour", callback_data=f"cat|{category}")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or "utilisateur"
    await update.message.reply_text(f"Bienvenue {name} 👋\nChoisissez une catégorie :", reply_markup=get_main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "start":
        await query.edit_message_text("Choisissez une catégorie :", reply_markup=get_main_menu())
    elif data.startswith("cat|"):
        _, cat = data.split("|", 1)
        if cat == "Géolocalisation":
            keyboard = ReplyKeyboardMarkup(
                [[KeyboardButton("Envoyer ma position", request_location=True)]],
                resize_keyboard=True, one_time_keyboard=True
            )
            await query.message.reply_text("Merci de partager votre position :", reply_markup=keyboard)
        else:
            await query.edit_message_text(f"Sous-catégories de {cat} :", reply_markup=get_sub_menu(cat))
    elif data.startswith("subcat|"):
        _, cat, sub = data.split("|", 2)
        await query.edit_message_text(f"Fichiers dans {cat} > {sub} :", reply_markup=get_files_menu(cat, sub))
    elif data.startswith("file|"):
        _, cat, sub, idx = data.split("|", 3)
        idx = int(idx)
        try:
            file = files_db[cat][sub][idx]
            await query.message.reply_document(document=file["file_id"], filename=file["filename"])
        except:
            await query.message.reply_text("Erreur lors de l'envoi du fichier.")

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    await update.message.reply_text(f"Localisation :\nLatitude: {loc.latitude}\nLongitude: {loc.longitude}")

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return await update.message.reply_text("Seul l'administrateur peut ajouter des fichiers.")

    args = context.args
    if len(args) != 2:
        return await update.message.reply_text("/upload <catégorie> <sous-catégorie>")
    context.user_data["upload_target"] = args
    await update.message.reply_text("Envoie maintenant le fichier.")

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return await update.message.reply_text("Tu ne peux pas envoyer de fichiers.")
    if "upload_target" not in context.user_data:
        return await update.message.reply_text("Utilise /upload d'abord.")

    cat, sub = context.user_data["upload_target"]
    doc = update.message.document
    files_db[cat][sub].append({"filename": doc.file_name, "file_id": doc.file_id})
    save_files_db()
    await update.message.reply_text(f"Fichier {doc.file_name} ajouté dans {cat} > {sub}.")
    del context.user_data["upload_target"]

async def listfiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    msg = ""
    for cat, subs in files_db.items():
        for sub, files in subs.items():
            if files:
                msg += f"\n{cat} > {sub} :\n"
                for f in files:
                    msg += f"- {f['filename']}\n"
    await update.message.reply_text(msg or "Aucun fichier disponible.")

async def delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    if len(context.args) < 3:
        return await update.message.reply_text("Usage: /delete <catégorie> <sous-catégorie> <nom_fichier>")

    cat, sub, filename = context.args[0], context.args[1], " ".join(context.args[2:])
    if cat in files_db and sub in files_db[cat]:
        files = files_db[cat][sub]
        files_db[cat][sub] = [f for f in files if f["filename"] != filename]
        save_files_db()
        await update.message.reply_text(f"Fichier {filename} supprimé (si existait).")

async def edit_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return await update.message.reply_text("Seul l'administrateur peut modifier des fichiers.")

    if len(context.args) < 3:
        return await update.message.reply_text("Usage: /edit <catégorie> <sous-catégorie> <nom_fichier>")

    context.user_data["edit_target"] = context.args[0], context.args[1], " ".join(context.args[2:])
    await update.message.reply_text("Envoie maintenant le nouveau fichier pour remplacer.")

async def handle_edit_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "edit_target" not in context.user_data:
        return

    cat, sub, old_name = context.user_data["edit_target"]
    doc = update.message.document
    if not doc:
        return await update.message.reply_text("Pas de document détecté.")

    # Supprimer ancien fichier
    files = files_db.get(cat, {}).get(sub, [])
    files_db[cat][sub] = [f for f in files if f["filename"] != old_name]

    # Ajouter nouveau fichier
    files_db[cat][sub].append({"filename": doc.file_name, "file_id": doc.file_id})
    save_files_db()
    await update.message.reply_text(f"Fichier {old_name} remplacé par {doc.file_name}.")
    del context.user_data["edit_target"]

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(CommandHandler("upload", upload_command))
    app.add_handler(CommandHandler("listfiles", listfiles))
    app.add_handler(CommandHandler("delete", delete_file))
    app.add_handler(CommandHandler("edit", edit_file))
    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.COMMAND, document_handler))
    app.add_handler(MessageHandler(filters.Document.ALL & filters.COMMAND, handle_edit_document))
    print("Bot en cours...")
    app.run_polling()

if __name__ == "__main__":
    main()
