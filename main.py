import os
import re
import random
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
)

# ================= الإعدادات =================
BOT_TOKEN = os.environ.get("8822078543:AAHPmdZv9X_tgOUnAVvKDf67jjfG9eaE_Ug")
OWNER_ID = int(os.environ.get("8937309807"))

# ================= قواعد البيانات المؤقتة =================
# لحفظ الإعدادات: القائمة البيضاء، المشرفين الإضافيين، حالة الحماية
DB = {
    "whitelist": [],      # من يحق له إرسال روابط
    "admins": [OWNER_ID], # المشرفين على البوت
    "settings": {
        "anti_link": True,
        "anti_spam": True,
        "welcome": True
    }
}

# لتتبع الرسائل المتكررة (مكافحة السبام)
SPAM_TRACKER = {}

# ================= التراحيب العراقية =================
IRAQI_WELCOMES = [
    "هلا بالزين نورتنا 🌹، شلونك يابا؟",
    "كل الهلا بيك عيني 👑، الكروب كروبك.",
    "نورت الكروب يابا ✨، شرفت ومية هلا.",
    "حي الله من جانا 🦅، هلا بيك اخونا.",
    "يا هلا وكل الهلا بيك 🌺، نورت الديرة.",
    "شرفت الكروب والله 💙، شلون الصحة؟",
    "هلا ومية هلا بالغالي 🌸.",
    "نورتنا يا قمر الكروب 🌙.",
    "هلا بيك بكروبك الثاني 🏠، تفضل.",
    "عيوني نورتنا بوجودك 👀، الف هلا.",
    "يا هلا بالوردة 🌷، منورنا.",
    "كل الهلا بيك وبجيتك 🌟.",
    "نورت الديرة والكروب 🏘️، هلا بالزين.",
    "هلا باللي طلته تسعدنا 😌.",
    "ميت هلا بيك عيوني 💖.",
    "نورتنا يا ذهب 🥇، شلونك؟",
    "هلا بيك أخينا الغالي 🤝.",
    "شرفتنا ونورتنا يابا 🤩.",
    "هلا بالغالي ابن الغالي 💎.",
    "حي الله هالطول الحلو 🕊️، ميت هلا."
]

LINK_PATTERN = re.compile(r"(https?://|www\.|t\.me/|telegram\.me/)", re.IGNORECASE)

# ================= دوال التحقق =================
def is_bot_admin(user_id):
    return user_id in DB["admins"] or user_id == OWNER_ID

def is_whitelisted(user_id):
    return user_id in DB["whitelist"] or is_bot_admin(user_id)

# ================= الترحيب =================
async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not DB["settings"]["welcome"]:
        return
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            await update.message.reply_text("عشت يابا ع الإضافة! ارفعني مشرف حتى أحمي الكروب 🛡️")
        else:
            greeting = random.choice(IRAQI_WELCOMES)
            await update.message.reply_text(f"👋 {member.mention_html()}\n{greeting}", parse_mode="HTML")

# ================= الحماية (روابط + سبام) =================
async def group_protection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or msg.chat.type == "private":
        return

    user_id = msg.from_user.id
    
    # تجاوز الحماية للمشرفين والمسموح لهم
    if is_whitelisted(user_id):
        return

    # 1. مكافحة الروابط
    if DB["settings"]["anti_link"]:
        text = msg.text or msg.caption or ""
        if LINK_PATTERN.search(text):
            try:
                await msg.delete()
                await msg.reply_text(f"🚫 عيني {msg.from_user.mention_html()}، الروابط ممنوعة هنا!", parse_mode="HTML")
                return
            except:
                pass

    # 2. مكافحة السبام (الرسائل السريعة والمتكررة)
    if DB["settings"]["anti_spam"]:
        now = time.time()
        user_msgs = SPAM_TRACKER.get(user_id, [])
        # نحتفظ فقط بالرسائل في آخر 3 ثواني
        user_msgs = [t for t in user_msgs if now - t < 3]
        user_msgs.append(now)
        SPAM_TRACKER[user_id] = user_msgs

        if len(user_msgs) > 4: # أكثر من 4 رسائل في 3 ثواني = سبام
            try:
                await msg.delete()
                await context.bot.restrict_chat_member(
                    msg.chat_id, user_id, 
                    permissions=telegram.ChatPermissions(can_send_messages=False),
                    until_date=now + 60 # تقييد لمدة دقيقة
                )
                await msg.reply_text(f"⚠️ تم تقييد {msg.from_user.mention_html()} لمدة دقيقة بسبب السبام.", parse_mode="HTML")
            except:
                pass

# ================= غرفة التحكم (القائمة) =================
def control_panel_keyboard():
    s = DB["settings"]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"الروابط: {'🟢' if s['anti_link'] else '🔴'}", callback_data="toggle_link"),
         InlineKeyboardButton(f"السبام: {'🟢' if s['anti_spam'] else '🔴'}", callback_data="toggle_spam")],
        [InlineKeyboardButton(f"الترحيب: {'🟢' if s['welcome'] else '🔴'}", callback_data="toggle_welcome")],
        [InlineKeyboardButton("👥 القائمة البيضاء", callback_data="show_whitelist"),
         InlineKeyboardButton("👮 المشرفين", callback_data="show_admins")]
    ])

async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_bot_admin(update.message.from_user.id):
        await update.message.reply_text("❌ هذي الغرفة خاصة بمدراء البوت بس.")
        return
    await update.message.reply_text("🎛️ **غرفة التحكم المركزية:**\nاختر من الإعدادات تحت:", reply_markup=control_panel_keyboard())

async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_bot_admin(query.from_user.id):
        await query.answer("❌ مو من حقك!", show_alert=True)
        return

    data = query.data
    s = DB["settings"]

    if data == "toggle_link":
        s["anti_link"] = not s["anti_link"]
    elif data == "toggle_spam":
        s["anti_spam"] = not s["anti_spam"]
    elif data == "toggle_welcome":
        s["welcome"] = not s["welcome"]
    elif data == "show_whitelist":
        await query.answer(f"عدد المسموح لهم: {len(DB['whitelist'])}", show_alert=True)
        return
    elif data == "show_admins":
        await query.answer(f"عدد مدراء البوت: {len(DB['admins'])}", show_alert=True)
        return

    await query.edit_message_reply_markup(reply_markup=control_panel_keyboard())

# ================= إضافة أشخاص (القائمة البيضاء / مدراء) =================
async def add_allow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_bot_admin(update.message.from_user.id):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("رد على رسالة الشخص واكتب /allow")
        return
    
    target_id = update.message.reply_to_message.from_user.id
    if target_id not in DB["whitelist"]:
        DB["whitelist"].append(target_id)
        await update.message.reply_text("✅ صار يكدر يرسل روابط براحته.")

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID: # المالك الأساسي فقط يقدر يضيف مدراء
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("رد على رسالة الشخص واكتب /admin")
        return
    
    target_id = update.message.reply_to_message.from_user.id
    if target_id not in DB["admins"]:
        DB["admins"].append(target_id)
        await update.message.reply_text("✅ تم رفعه لمدير بالبوت، صار يكدر يتحكم بالإعدادات.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # الأوامر
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(CommandHandler("allow", add_allow))
    app.add_handler(CommandHandler("admin", add_admin))
    app.add_handler(CallbackQueryHandler(panel_callback))
    
    # الترحيب والحماية
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS, group_protection))
    
    print("🚀 بوت الحماية العراقي يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
