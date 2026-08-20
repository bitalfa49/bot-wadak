import os
import random
import asyncio
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from pymongo import MongoClient

# --- سيرفر وهمي لإبقاء Render نشطاً ---
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is active and running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- إعدادات البيئة وقاعدة البيانات ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

mongo_client = MongoClient(MONGO_URL)
db = mongo_client["telegram_bot_db"]
whitelisted_col = db["whitelisted"]
admins_col = db["admins"]

# --- الترحيبات العراقية (أكثر من 20 عبارة) ---
WELCOME_MESSAGES = [
    "هلا والله نورت الجات يا الغالي 🌹✨",
    "يا هلا ويا مرحبا، نورت الجروب بوجودك يا بطل 👋🔥",
    "كل الهلا بيك، المكان نور بتواجدك ويا معود 🌟🥳",
    "أهلاً وسهلاً بيك بين إخوانك، نورتنا والله 💖✨",
    "هلا بالزين كله! نورتنا وشرفتنا يا طيب ☕️🌿",
    "يا مية هلا بيك، نورت الكروب بطلتك البهية 👑💫",
    "هلا وغلا، نورت المجموعه عيني 🌺🎈",
    "كل الهلا بيك وبأهلنا الغالين، نورت الجروب 🌸🙌",
    "هلا بالقلب، شرفتنا ونورت مكانك يا الورد 🌹❤️",
    "يا هلا باللي جانا، نورتنا واسفرت وانفرت 🎉✨",
    "كل الهلا بيكم، نورتوا المجموعه يا أطياب 🌟✨",
    "هلا والله، نورت الكروب وشرفتنا بوجودك 🤩💥",
    "يا أهلاً وسهلاً، نورتنا وعطر المنتدى بوجودك 💐🍃",
    "هلا بيك يا بعد روحي، نورت الجروب بطلتك ✨🎈",
    "كل الهلا بالزين، نورتنا وأسعدتنا بوجودك 👑🌹",
    "يا مرحبا بيك، نورت الكروب يا العالي 🌟🔥",
    "هلا وغلا بيك، نورتنا وشرفتنا يا الغالي 💫🥳",
    "يا هلا بالطيب، نورت الجروب بطلتك الحلوة 🌺✨",
    "كل الهلا بيك، نورتنا وصرت واحد منا وفينا 💖🙌",
    "هلا والله، نورت المكان بوجودك العطر 🌸🍃",
    "يا أهلاً بالورد، نورت الكروب يا غالي 🌹💫"
]

def is_whitelisted(user_id: int) -> bool:
    return whitelisted_col.find_one({"user_id": user_id}) is not None

def is_admin(user_id: int) -> bool:
    return admins_col.find_one({"user_id": user_id}) is not None

# --- الترحب بالأعضاء الجدد ---
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        text = random.choice(WELCOME_MESSAGES)
        full_text = f"👤 {member.mention_html()}\n\n{text}"
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📜 القوانين", callback_data="rules"),
             InlineKeyboardButton("💬 الدعم", callback_data="support")]
        ])
        await update.message.reply_html(full_text, reply_markup=buttons)

# --- حماية الروابط ---
async def link_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if is_whitelisted(user_id) or is_admin(user_id):
        return
    try:
        await update.message.delete()
        await update.message.reply_text(f"⚠️ {update.message.from_user.first_name}، يمنع إرسال الروابط في هذه المجموعة!")
    except Exception:
        pass

# --- إضافة استثناء روابط (بالرد) ---
async def allow_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        whitelisted_col.update_one({"user_id": target_id}, {"$set": {"user_id": target_id}}, upsert=True)
        await update.message.reply_text("✅ تم السماح للمستخدم بنشر الروابط.")

# --- إضافة أدمن للبوت (بالرد) ---
async def add_admin_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        admins_col.update_one({"user_id": target_id}, {"$set": {"user_id": target_id}}, upsert=True)
        await update.message.reply_text("✅ تم إضافة المستخدم كـ آدمن في البوت.")

# --- لوحة التحكم ---
async def control_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("❌ هذه اللوحة مخصصة للمشرفين والمالك فقط.")
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ البوت يعمل بنجاح والحماية مفعلة", callback_data="status")]
    ])
    await update.message.reply_text("🛠️ **لوحة تحكم البوت:**", reply_markup=buttons)

def main():
    keep_alive()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    application.add_handler(MessageHandler(filters.TEXT & (filters.Regex(r'http[s]?://') | filters.Regex(r't\.me/')), link_filter))
    application.add_handler(CommandHandler("allow", allow_user))
    application.add_handler(CommandHandler("addadmin", add_admin_user))
    application.add_handler(CommandHandler("control", control_panel))

    application.run_polling()

if __name__ == '__main__':
    main()
