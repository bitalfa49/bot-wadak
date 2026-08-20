import os
import random
import asyncio
from threading import Thread
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pymongo import MongoClient

# --- إنشاء Event Loop صريح لتفادي خطأ Python 3.10+ ---
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

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
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
MONGO_URL = os.getenv("MONGO_URL")

mongo_client = MongoClient(MONGO_URL)
db = mongo_client["telegram_bot_db"]
whitelisted_col = db["whitelisted"]
admins_col = db["admins"]

app = Client("protection_welcome_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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

@app.on_message(filters.new_chat_members)
async def welcome_new_member(client, message: Message):
    for member in message.new_chat_members:
        text = random.choice(WELCOME_MESSAGES)
        full_text = f"👤 {member.mention}\n\n{text}"
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📜 القوانين", callback_data="rules"),
             InlineKeyboardButton("💬 الدعم", callback_data="support")]
        ])
        await message.reply_text(full_text, reply_markup=buttons)

@app.on_message(filters.group & (filters.regex(r"http[s]?://") | filters.regex(r"t\.me/")))
async def link_filter(client, message: Message):
    user_id = message.from_user.id
    if is_whitelisted(user_id) or is_admin(user_id):
        return
    try:
        await message.delete()
        await message.reply_text(f"⚠️ {message.from_user.mention}، يمنع إرسال الروابط في هذه المجموعة!")
    except Exception:
        pass

@app.on_message(filters.command("control") & filters.group)
async def control_panel(client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("❌ هذه اللوحة مخصصة للمشرفين والمالك فقط.")
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ البوت يعمل بنجاح", callback_data="info")]
    ])
    await message.reply_text("🛠️ **لوحة تحكم البوت:**", reply_markup=buttons)

@app.on_message(filters.command("allow") & filters.group)
async def allow_user(client, message: Message):
    if not is_admin(message.from_user.id):
        return
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        whitelisted_col.update_one({"user_id": target_id}, {"$set": {"user_id": target_id}}, upsert=True)
        await message.reply_text("✅ تم السماح للمستخدم بنشر الروابط.")

@app.on_message(filters.command("addadmin") & filters.group)
async def add_admin_user(client, message: Message):
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        admins_col.update_one({"user_id": target_id}, {"$set": {"user_id": target_id}}, upsert=True)
        await message.reply_text("✅ تم إضافة المستخدم كـ آدمن في البوت.")

if __name__ == "__main__":
    keep_alive()
    app.run()
