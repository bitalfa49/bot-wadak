# -*- coding: utf-8 -*-
"""
🛡️ بوت الحماية الاحترافي | تطوير: @zyh011

الميزات:
  • إعدادات مستقلة لكل كروب (مش عامة زي أغلب البوتات المجانية)
  • منع الروابط (قابل للتخصيص + قائمة استثناء)
  • مكافحة السبام/الفيضان (flood) — كتم تلقائي مؤقت
  • منع الرسائل المُعاد توجيهها من قنوات
  • نظام تحذيرات: عدد تحذيرات قابل للتعديل → طرد تلقائي
  • كابتشا للأعضاء الجدد (زر "أنا مش بوت") — يلي ما يضغط بوقت محدد بينطرد
  • أوامر إشراف كاملة: /ban /unban /kick /mute /unmute /warn /unwarn (بالرد)
  • لوحة تحكم تفاعلية (أزرار مدمجة) لكل كروب لحاله
  • صلاحيات تعتمد على حالة الأدمن الحقيقية بتلغرام (مش قائمة مخصصة قابلة للخطأ)
  • تخزين دائم: PostgreSQL إذا متوفر، وإلا ملف محلي

متغيرات التشغيل:
  BOT_TOKEN     (إجباري) — توكن البوت من BotFather
  DATABASE_URL  (اختياري لكن يُنصح به) — رابط PostgreSQL
  OWNER_ID      (اختياري) — ايدي المطوّر (صلاحيات كاملة بكل الكروبات)
"""

import os
import re
import json
import time
import asyncio
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import (
    Update,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    filters,
    ContextTypes,
)

# ================== الإعدادات ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "حط_توكن_البوت_هون")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DATA_FILE = os.environ.get("DATA_FILE", "guard_data.json")
OWNER_ID = int(os.environ.get("OWNER_ID", "0") or "0")
# ===============================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("guardbot")

LINK_PATTERN = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/|@\w{4,})", re.IGNORECASE
)

WELCOME_TEMPLATES = [
    "أهلاً فيك {name} 👋 نورت الكروب!",
    "هلا وغلا {name} 🌟 تشرفنا فيك.",
    "مرحباً {name} 🎉 وصلت لعنا، اقرأ القوانين واستمتع.",
]

DEFAULT_SETTINGS = {
    "anti_link": True,
    "anti_forward": False,
    "anti_spam": True,
    "welcome": True,
    "welcome_text": "",
    "captcha": False,
    "warn_limit": 3,
    "flood_limit": 5,       # عدد رسائل
    "flood_window": 4,      # خلال كم ثانية
    "mute_minutes": 15,     # مدة الكتم عند مخالفة
}


def _default_chat(chat_id):
    return {
        "chat_id": chat_id,
        "settings": dict(DEFAULT_SETTINGS),
        "whitelist": [],   # ايديات مسموح لها ترسل روابط
        "warns": {},        # {user_id(str): count}
    }


# ==================================================================
#                         طبقة التخزين
# ==================================================================
USE_DB = bool(DATABASE_URL)
_lock = threading.Lock()

if USE_DB:
    import psycopg

    def _db():
        return psycopg.connect(DATABASE_URL, autocommit=True)

    def db_init():
        with _db() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id TEXT PRIMARY KEY,
                    data    TEXT NOT NULL
                )
                """
            )
        log.info("✅ قاعدة البيانات جاهزة")

    def db_all_chats():
        out = {}
        with _db() as conn:
            for row in conn.execute("SELECT chat_id, data FROM chats"):
                try:
                    out[row[0]] = json.loads(row[1])
                except Exception:
                    pass
        return out

    def db_upsert(chat_id, rec):
        with _db() as conn:
            conn.execute(
                """
                INSERT INTO chats (chat_id, data) VALUES (%s,%s)
                ON CONFLICT (chat_id) DO UPDATE SET data=EXCLUDED.data
                """,
                (str(chat_id), json.dumps(rec, ensure_ascii=False)),
            )


DATA = {"chats": {}}


def load_all():
    global DATA
    if USE_DB:
        DATA["chats"] = db_all_chats()
    else:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    DATA = json.load(f)
            except Exception:
                DATA = {"chats": {}}
        DATA.setdefault("chats", {})
    for rec in DATA["chats"].values():
        _normalize(rec)
    return DATA


def _normalize(rec):
    base = _default_chat(rec.get("chat_id"))
    rec.setdefault("settings", {})
    for k, v in base["settings"].items():
        rec["settings"].setdefault(k, v)
    rec.setdefault("whitelist", [])
    rec.setdefault("warns", {})
    return rec


def persist(chat_id):
    with _lock:
        if USE_DB:
            rec = DATA["chats"].get(str(chat_id))
            if rec:
                db_upsert(chat_id, rec)
        else:
            tmp = DATA_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(DATA, f, ensure_ascii=False, indent=2)
            os.replace(tmp, DATA_FILE)


def get_chat_rec(chat_id):
    key = str(chat_id)
    if key not in DATA["chats"]:
        DATA["chats"][key] = _default_chat(key)
        persist(chat_id)
    return DATA["chats"][key]


def esc(text):
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ==================================================================
#                    فحص الصلاحيات
# ==================================================================
_admin_cache = {}   # (chat_id, user_id) -> (is_admin, expiry_ts)
ADMIN_CACHE_TTL = 60


async def is_group_admin(bot, chat_id, user_id):
    """يتحقق من كون الشخص أدمن حقيقي بالكروب (بحالة تلغرام نفسها)"""
    if user_id == OWNER_ID:
        return True
    key = (chat_id, user_id)
    cached = _admin_cache.get(key)
    now = time.time()
    if cached and cached[1] > now:
        return cached[0]
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        result = member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        result = False
    _admin_cache[key] = (result, now + ADMIN_CACHE_TTL)
    return result


# ==================================================================
#                    مكافحة الفيضان (Flood)
# ==================================================================
FLOOD_TRACKER = {}   # (chat_id, user_id) -> [timestamps]


def _check_flood(chat_id, user_id, limit, window):
    key = (chat_id, user_id)
    now = time.time()
    times = [t for t in FLOOD_TRACKER.get(key, []) if now - t < window]
    times.append(now)
    FLOOD_TRACKER[key] = times
    return len(times) > limit


# ==================================================================
#                    لوحة التحكم (Inline)
# ==================================================================
def panel_kb(rec):
    s = rec["settings"]

    def dot(v):
        return "🟢" if v else "🔴"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🔗 الروابط {dot(s['anti_link'])}", callback_data="g_link"),
            InlineKeyboardButton(f"📤 التوجيه {dot(s['anti_forward'])}", callback_data="g_fwd"),
        ],
        [
            InlineKeyboardButton(f"🌊 السبام {dot(s['anti_spam'])}", callback_data="g_spam"),
            InlineKeyboardButton(f"👋 الترحيب {dot(s['welcome'])}", callback_data="g_welcome"),
        ],
        [
            InlineKeyboardButton(f"🤖 كابتشا الجدد {dot(s['captcha'])}", callback_data="g_captcha"),
        ],
        [
            InlineKeyboardButton(f"⚠️ حد التحذيرات: {s['warn_limit']}", callback_data="g_warnlimit"),
        ],
        [InlineKeyboardButton("🔄 تحديث", callback_data="g_refresh")],
    ])


def panel_text(rec):
    s = rec["settings"]
    return (
        "🛡️ <b>لوحة تحكم الحماية</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"🔗 منع الروابط: {'مفعّل' if s['anti_link'] else 'موقوف'}\n"
        f"📤 منع التوجيه: {'مفعّل' if s['anti_forward'] else 'موقوف'}\n"
        f"🌊 مكافحة السبام: {'مفعّل' if s['anti_spam'] else 'موقوف'}\n"
        f"👋 الترحيب: {'مفعّل' if s['welcome'] else 'موقوف'}\n"
        f"🤖 كابتشا الأعضاء الجدد: {'مفعّل' if s['captcha'] else 'موقوف'}\n"
        f"⚠️ حد التحذيرات قبل الطرد: {s['warn_limit']}\n\n"
        "بس مشرفين الكروب فيهم يعدّلوا هالإعدادات."
    )


# ==================================================================
#                    الترحيب + الكابتشا
# ==================================================================
PENDING_CAPTCHA = {}   # (chat_id, user_id) -> True


async def on_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.new_chat_members:
        return
    chat_id = msg.chat_id
    rec = get_chat_rec(chat_id)
    s = rec["settings"]

    for member in msg.new_chat_members:
        if member.id == context.bot.id:
            await msg.reply_text(
                "🛡️ عشت، شكراً عالإضافة!\n"
                "ارفعني <b>مشرف</b> بصلاحيات (حذف رسائل، حظر أعضاء) عشان أقدر أحميكم فعلياً.\n\n"
                "اكتب /panel عشان تفتح لوحة الإعدادات.",
                parse_mode=ParseMode.HTML,
            )
            continue

        if s.get("captcha"):
            # نقيّد العضو مؤقتاً لحد ما يضغط الزر
            try:
                await context.bot.restrict_chat_member(
                    chat_id, member.id,
                    permissions=ChatPermissions(can_send_messages=False),
                )
            except Exception:
                pass
            PENDING_CAPTCHA[(chat_id, member.id)] = True
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ أنا مش بوت", callback_data=f"cap:{member.id}")
            ]])
            sent = await msg.reply_text(
                f"👋 أهلاً {member.mention_html()}!\nاضغط الزر تحت خلال دقيقتين وإلا رح تنطرد تلقائياً.",
                parse_mode=ParseMode.HTML, reply_markup=kb,
            )
            context.application.create_task(
                _captcha_timeout(context, chat_id, member.id, sent.message_id)
            )
        elif s.get("welcome"):
            text = s.get("welcome_text") or None
            if not text:
                import random
                text = random.choice(WELCOME_TEMPLATES)
            await msg.reply_text(
                text.format(name=member.mention_html()), parse_mode=ParseMode.HTML
            )


async def _captcha_timeout(context, chat_id, user_id, msg_id):
    await asyncio.sleep(120)
    if PENDING_CAPTCHA.pop((chat_id, user_id), None):
        try:
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.unban_chat_member(chat_id, user_id)  # طرد بدون حظر دائم
            await context.bot.delete_message(chat_id, msg_id)
        except Exception:
            pass


async def captcha_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = q.message.chat_id
    target_id = int(q.data.split(":")[1])
    if q.from_user.id != target_id:
        await q.answer("هاد الزر مو الك 🙅", show_alert=True)
        return
    if PENDING_CAPTCHA.pop((chat_id, target_id), None) is None:
        await q.answer("انتهت الصلاحية.", show_alert=True)
        return
    try:
        await context.bot.restrict_chat_member(
            chat_id, target_id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_photos=True,
                can_send_videos=True, can_send_other_messages=True,
            ),
        )
    except Exception:
        pass
    await q.answer("تم التحقق ✅")
    try:
        await q.edit_message_text(f"✅ تم التحقق، أهلاً فيك!")
    except Exception:
        pass


# ==================================================================
#                    الحماية (روابط، فيضان، توجيه)
# ==================================================================
async def group_protection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or msg.chat.type not in ("group", "supergroup"):
        return
    user = msg.from_user
    if not user:
        return
    chat_id = msg.chat_id
    rec = get_chat_rec(chat_id)
    s = rec["settings"]

    # المشرفين ومن بالقائمة البيضاء معفيين
    if await is_group_admin(context.bot, chat_id, user.id):
        return
    if user.id in rec["whitelist"]:
        return

    # منع التوجيه من قنوات
    if s.get("anti_forward") and msg.forward_origin:
        try:
            await msg.delete()
        except Exception:
            pass
        return

    text = msg.text or msg.caption or ""

    # منع الروابط
    if s.get("anti_link") and LINK_PATTERN.search(text):
        try:
            await msg.delete()
            warned = await _add_warn(context, chat_id, user)
            if not warned:
                await context.bot.send_message(
                    chat_id, f"🚫 {user.mention_html()} الروابط ممنوعة هون.",
                    parse_mode=ParseMode.HTML,
                )
        except Exception:
            pass
        return

    # مكافحة السبام
    if s.get("anti_spam"):
        limit = s.get("flood_limit", 5)
        window = s.get("flood_window", 4)
        if _check_flood(chat_id, user.id, limit, window):
            try:
                minutes = s.get("mute_minutes", 15)
                await context.bot.restrict_chat_member(
                    chat_id, user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=int(time.time()) + minutes * 60,
                )
                await context.bot.send_message(
                    chat_id,
                    f"⚠️ تم كتم {user.mention_html()} لمدة {minutes} دقيقة بسبب إرسال رسائل متكررة.",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass


async def _add_warn(context, chat_id, user):
    """يضيف تحذير، وإذا وصل الحد يطرد. يرجع True لو صار طرد."""
    rec = get_chat_rec(chat_id)
    key = str(user.id)
    rec["warns"][key] = rec["warns"].get(key, 0) + 1
    limit = rec["settings"].get("warn_limit", 3)
    persist(chat_id)
    if rec["warns"][key] >= limit:
        try:
            await context.bot.ban_chat_member(chat_id, user.id)
            await context.bot.unban_chat_member(chat_id, user.id)
            await context.bot.send_message(
                chat_id,
                f"🚷 تم طرد {user.mention_html()} بعد {limit} تحذيرات.",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass
        rec["warns"][key] = 0
        persist(chat_id)
        return True
    else:
        await context.bot.send_message(
            chat_id,
            f"⚠️ تحذير لـ {user.mention_html()} ({rec['warns'][key]}/{limit})",
            parse_mode=ParseMode.HTML,
        )
        return False


# ==================================================================
#                    أوامر الإشراف (بالرد على رسالة)
# ==================================================================
def _reply_target(update):
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    return None


async def cmd_ban(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    target = _reply_target(update)
    if not target:
        await msg.reply_text("رد على رسالة الشخص واكتب /ban")
        return
    try:
        await context.bot.ban_chat_member(msg.chat_id, target.id)
        await msg.reply_text(f"🚫 تم حظر {target.mention_html()}", parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.reply_text(f"ما قدرت: {e}")


async def cmd_unban(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    if not context.args:
        await msg.reply_text("اكتب /unban <id>")
        return
    try:
        await context.bot.unban_chat_member(msg.chat_id, int(context.args[0]))
        await msg.reply_text("✅ تم فك الحظر.")
    except Exception as e:
        await msg.reply_text(f"ما قدرت: {e}")


async def cmd_kick(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    target = _reply_target(update)
    if not target:
        await msg.reply_text("رد على رسالة الشخص واكتب /kick")
        return
    try:
        await context.bot.ban_chat_member(msg.chat_id, target.id)
        await context.bot.unban_chat_member(msg.chat_id, target.id)
        await msg.reply_text(f"👢 تم طرد {target.mention_html()}", parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.reply_text(f"ما قدرت: {e}")


async def cmd_mute(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    target = _reply_target(update)
    if not target:
        await msg.reply_text("رد على رسالة الشخص واكتب /mute [دقايق]")
        return
    minutes = 15
    if context.args:
        try:
            minutes = int(context.args[0])
        except ValueError:
            pass
    try:
        await context.bot.restrict_chat_member(
            msg.chat_id, target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=int(time.time()) + minutes * 60,
        )
        await msg.reply_text(f"🔇 تم كتم {target.mention_html()} لمدة {minutes} دقيقة", parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.reply_text(f"ما قدرت: {e}")


async def cmd_unmute(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    target = _reply_target(update)
    if not target:
        await msg.reply_text("رد على رسالة الشخص واكتب /unmute")
        return
    try:
        await context.bot.restrict_chat_member(
            msg.chat_id, target.id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_photos=True,
                can_send_videos=True, can_send_other_messages=True,
            ),
        )
        await msg.reply_text(f"🔊 تم فك الكتم عن {target.mention_html()}", parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.reply_text(f"ما قدرت: {e}")


async def cmd_warn(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    target = _reply_target(update)
    if not target:
        await msg.reply_text("رد على رسالة الشخص واكتب /warn")
        return
    await _add_warn(context, msg.chat_id, target)


async def cmd_unwarn(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    target = _reply_target(update)
    if not target:
        await msg.reply_text("رد على رسالة الشخص واكتب /unwarn")
        return
    rec = get_chat_rec(msg.chat_id)
    key = str(target.id)
    if rec["warns"].get(key, 0) > 0:
        rec["warns"][key] -= 1
        persist(msg.chat_id)
    await msg.reply_text(f"↩️ تم إنقاص تحذير عن {target.mention_html()} ({rec['warns'].get(key,0)})", parse_mode=ParseMode.HTML)


async def cmd_allow(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    target = _reply_target(update)
    if not target:
        await msg.reply_text("رد على رسالة الشخص واكتب /allow")
        return
    rec = get_chat_rec(msg.chat_id)
    if target.id not in rec["whitelist"]:
        rec["whitelist"].append(target.id)
        persist(msg.chat_id)
    await msg.reply_text(f"✅ {target.mention_html()} صار مسموحله يبعت روابط.", parse_mode=ParseMode.HTML)


async def cmd_disallow(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    target = _reply_target(update)
    if not target:
        await msg.reply_text("رد على رسالة الشخص واكتب /disallow")
        return
    rec = get_chat_rec(msg.chat_id)
    if target.id in rec["whitelist"]:
        rec["whitelist"].remove(target.id)
        persist(msg.chat_id)
    await msg.reply_text("✅ تم إلغاء الاستثناء.")


# ==================================================================
#                    لوحة التحكم — أوامر وردود
# ==================================================================
async def cmd_panel(update, context):
    msg = update.message
    if msg.chat.type not in ("group", "supergroup"):
        await msg.reply_text("هاد الأمر يشتغل جوا الكروبات بس.")
        return
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        await msg.reply_text("❌ بس مشرفين الكروب يقدروا يفتحوا اللوحة.")
        return
    rec = get_chat_rec(msg.chat_id)
    await msg.reply_text(panel_text(rec), parse_mode=ParseMode.HTML, reply_markup=panel_kb(rec))


async def panel_cb(update, context):
    q = update.callback_query
    chat_id = q.message.chat_id
    if not await is_group_admin(context.bot, chat_id, q.from_user.id):
        await q.answer("❌ بس المشرفين", show_alert=True)
        return
    rec = get_chat_rec(chat_id)
    s = rec["settings"]
    data = q.data

    toggles = {
        "g_link": "anti_link",
        "g_fwd": "anti_forward",
        "g_spam": "anti_spam",
        "g_welcome": "welcome",
        "g_captcha": "captcha",
    }
    if data in toggles:
        key = toggles[data]
        s[key] = not s[key]
        persist(chat_id)
        await q.answer("تم ✅")
        await q.edit_message_text(panel_text(rec), parse_mode=ParseMode.HTML, reply_markup=panel_kb(rec))
        return

    if data == "g_warnlimit":
        s["warn_limit"] = (s["warn_limit"] % 10) + 1  # يدور 1..10
        persist(chat_id)
        await q.answer(f"حد التحذيرات: {s['warn_limit']}")
        await q.edit_message_text(panel_text(rec), parse_mode=ParseMode.HTML, reply_markup=panel_kb(rec))
        return

    if data == "g_refresh":
        await q.answer()
        await q.edit_message_text(panel_text(rec), parse_mode=ParseMode.HTML, reply_markup=panel_kb(rec))
        return


# ==================================================================
#            سيرفر ويب صغير (Render)
# ==================================================================
class _PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"GuardBot is running")

    def log_message(self, *args):
        pass


def start_web_server():
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), _PingHandler).serve_forever()


# ==================================================================
#                            التشغيل
# ==================================================================
def build_app():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("panel", cmd_panel))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("kick", cmd_kick))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("unmute", cmd_unmute))
    app.add_handler(CommandHandler("warn", cmd_warn))
    app.add_handler(CommandHandler("unwarn", cmd_unwarn))
    app.add_handler(CommandHandler("allow", cmd_allow))
    app.add_handler(CommandHandler("disallow", cmd_disallow))

    app.add_handler(CallbackQueryHandler(panel_cb, pattern="^g_"))
    app.add_handler(CallbackQueryHandler(captcha_cb, pattern="^cap:"))

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_member))
    app.add_handler(
        MessageHandler(filters.ALL & filters.ChatType.GROUPS & ~filters.StatusUpdate.ALL, group_protection)
    )
    return app


async def _run_async():
    if USE_DB:
        db_init()
    load_all()
    log.info(f"📦 التخزين: {'PostgreSQL' if USE_DB else 'ملف محلي'} | كروبات محفوظة: {len(DATA['chats'])}")

    threading.Thread(target=start_web_server, daemon=True).start()

    app = build_app()
    await app.initialize()
    await app.start()
    # stop_signals=None يمنع مشاكل معالجة إشارات النظام جوا حاويات مثل Render
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("🛡️ بوت الحماية شغّال...")

    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


def main():
    if not BOT_TOKEN or "حط_توكن" in BOT_TOKEN:
        raise SystemExit("⚠️ لازم تحط توكن البوت بمتغير BOT_TOKEN")

    # نتأكد إنو في event loop بالخيط الرئيسي (يحل مشكلة نسخ بايثون الجديدة مثل 3.14)
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    try:
        asyncio.run(_run_async())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
