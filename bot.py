import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

DATA_DIR = "./data"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton(text=cat, callback_data=f"cat|{cat}")]
        for cat in os.listdir(DATA_DIR)
        if os.path.isdir(os.path.join(DATA_DIR, cat))
    ]
    await update.message.reply_text("📂 Choisis une catégorie :", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("cat|"):
        _, category = data.split("|")
        subfolder_path = os.path.join(DATA_DIR, category)
        subfolders = [
            f for f in os.listdir(subfolder_path)
            if os.path.isdir(os.path.join(subfolder_path, f))
        ]
        buttons = [[InlineKeyboardButton(text=sub, callback_data=f"sub|{category}|{sub}")]
                   for sub in subfolders]
        await query.edit_message_text(
            text=f"📁 Sous-dossiers de {category} :", reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("sub|"):
        _, category, subfolder = data.split("|")
        folder_path = os.path.join(DATA_DIR, category, subfolder)
        files = os.listdir(folder_path)
        buttons = [[InlineKeyboardButton(text=f, callback_data=f"file|{category}|{subfolder}|{f}")]
                   for f in files]
        await query.edit_message_text(
            text=f"📂 Fichiers dans {category}/{subfolder} :",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("file|"):
        _, category, subfolder, filename = data.split("|")
        filepath = os.path.join(DATA_DIR, category, subfolder, filename)
        await query.message.reply_document(document=open(filepath, "rb"))

def main():
    from config import TOKEN
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()

if __name__ == "__main__":
    main()
