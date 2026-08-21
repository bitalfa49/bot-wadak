# -*- coding: utf-8 -*-
"""
🛡️ بوت الحماية الاحترافي | تطوير: @zyh011

الميزات:
  • إعدادات مستقلة لكل كروب
  • منع الروابط (قابل للتخصيص + قائمة استثناء)
  • مكافحة السبام/الفيضان (flood) — كتم تلقائي مؤقت
  • منع الرسائل المُعاد توجيهها من قنوات
  • منع الستيكرات والـ GIF والصور والفيديوهات والصوتيات
  • نظام تحذيرات: عدد تحذيرات قابل للتعديل → طرد تلقائي
  • كابتشا للأعضاء الجدد (زر "أنا مش بوت")
  • رسالة ترحيب مخصصة قابلة للتعديل من الأدمن + صورة/فيديو
  • ردود تلقائية مخصصة (تريغرز) — تدعم ذكر اليوزر
  • أوامر إشراف كاملة: /ban /unban /kick /mute /unmute /warn /unwarn /trust /untrust
  • اختصارات عربية بالحروف (سهلة وسريعة) بدل الأزرار المعقدة
  • صلاحيات تعتمد على حالة الأدمن الحقيقية بتلغرام
  • وضع الصمت (Silent Mode) — كتم الكل
  • حماية الغزوات (Raid Protection)
  • تقييد الأعضاء الجدد (Newbie Restrict)
  • قناة تقارير (Report Channel)
  • تخزين دائم: PostgreSQL

متغيرات التشغيل:
  BOT_TOKEN     (إجباري)
  DATABASE_URL  (اختياري لكن يُنصح به)
  OWNER_ID      (اختياري)
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
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChatAdministrators,
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
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8822078543:AAHPmdZv9X_tgOUnAVvKDf67jjfG9eaE_Ug")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://guard_bot_db_user:IU2SX2bJwqQAI2kZgDffzPJSyNFbH0qD@dpg-da43c8e417fc73bum5cg-a/guard_bot_db").strip()
DATA_FILE = os.environ.get("DATA_FILE", "guard_data.json")
OWNER_ID = int(os.environ.get("OWNER_ID", "8937309807") or "8937309807")
# ===============================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("guardbot")

LINK_PATTERN = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/|@\w{4,})", re.IGNORECASE
)

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
    "يا أهلاً بالورد، نورت الكروب يا غالي 🌹💫",
]

GOODBYE_MESSAGES = [
    "ودعنا {name} 👋 نتمنالك التوفيق.",
    "{name} غادر الكروب، الله معاه 🌿",
    "سلام {name}، بالتوفيق بمشوارك 🍃",
]

DEFAULT_SETTINGS = {
    "anti_link": True,
    "anti_forward": False,
    "anti_spam": True,
    "welcome": True,
    "welcome_text": "",
    "goodbye": False,
    "captcha": False,
    "block_stickers": False,
    "block_gifs": False,
    "block_voice": False,
    "block_photos": False,
    "block_videos": False,
    "warn_limit": 3,
    "flood_limit": 5,
    "flood_window": 4,
    "mute_minutes": 15,
    "clean_mode": True,
    "raid_protection": True,
    "raid_join_limit": 5,
    "raid_window": 15,
    "locked": False,
    "newbie_restrict": False,
    "newbie_restrict_min": 60,
    "silent_mode": False,
    "report_channel": "",
}


def _default_chat(chat_id):
    return {
        "chat_id": chat_id,
        "settings": dict(DEFAULT_SETTINGS),
        "whitelist": [],
        "warns": {},
        "custom_replies": {},
        "blacklist": [],
        "trusted": [],
        "welcome_media": None,
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
    rec.setdefault("custom_replies", {})
    rec.setdefault("blacklist", [])
    rec.setdefault("trusted", [])
    rec.setdefault("welcome_media", None)
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


async def _delete_silent(bot, chat_id, message_id):
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass


async def _cleanup_command(context, msg, rec):
    if rec["settings"].get("clean_mode", True):
        await _delete_silent(context.bot, msg.chat_id, msg.message_id)


async def _reply_hideable(context, chat_id, rec, text, **kwargs):
    sent = await context.bot.send_message(chat_id, text, **kwargs)
    if rec["settings"].get("clean_mode", True):
        async def _later():
            await asyncio.sleep(8)
            await _delete_silent(context.bot, chat_id, sent.message_id)
        context.application.create_task(_later())
    return sent


# ==================================================================
#                    فحص الصلاحيات
# ==================================================================
_admin_cache = {}
ADMIN_CACHE_TTL = 60


async def is_group_admin(bot, chat_id, user_id):
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
FLOOD_TRACKER = {}


def _check_flood(chat_id, user_id, limit, window):
    key = (chat_id, user_id)
    now = time.time()
    times = [t for t in FLOOD_TRACKER.get(key, []) if now - t < window]
    times.append(now)
    FLOOD_TRACKER[key] = times
    return len(times) > limit


# ==================================================================
DEVELOPER = "zyh011"


# ==================================================================
#           نظام الاختصارات بالأحرف العربية
# ==================================================================
SHORTCUTS = {
    "ر": {"label": "منع الروابط", "type": "toggle", "key": "anti_link"},
    "ت": {"label": "منع التوجيه من قنوات", "type": "toggle", "key": "anti_forward"},
    "س": {"label": "مكافحة السبام/الفيضان", "type": "toggle", "key": "anti_spam"},
    "ص": {"label": "منع الستيكرات", "type": "toggle", "key": "block_stickers"},
    "ج": {"label": "منع الـ GIF", "type": "toggle", "key": "block_gifs"},
    "صو": {"label": "منع الصور", "type": "toggle", "key": "block_photos"},
    "ف": {"label": "منع الفيديوهات", "type": "toggle", "key": "block_videos"},
    "صت": {"label": "منع الرسائل الصوتية", "type": "toggle", "key": "block_voice"},
    "ه": {"label": "رسالة الترحيب", "type": "toggle", "key": "welcome"},
    "و": {"label": "رسالة الوداع", "type": "toggle", "key": "goodbye"},
    "تر": {"label": "تعديل رسالة الترحيب", "type": "action", "action": "welcome_edit"},
    "ك": {"label": "كابتشا الأعضاء الجدد", "type": "toggle", "key": "captcha"},
    "غ": {"label": "حماية الغزوات (Raid)", "type": "toggle", "key": "raid_protection"},
    "جديد": {"label": "تقييد الأعضاء الجدد", "type": "toggle", "key": "newbie_restrict"},
    "رد": {"label": "إدارة الردود المخصصة", "type": "action", "action": "custom"},
    "كلم": {"label": "إدارة الكلمات الممنوعة", "type": "action", "action": "blacklist"},
    "ح": {"label": "عرض حالة الحماية الكاملة", "type": "action", "action": "status"},
    "د": {"label": "تدوير حد التحذيرات (1-10)", "type": "action", "action": "warnlimit"},
    "كتم": {"label": "تعديل دقائق الكتم", "type": "action", "action": "mute_time"},
    "ق": {"label": "قفل الكروب يدوياً", "type": "action", "action": "lock"},
    "فتح": {"label": "فتح الكروب", "type": "action", "action": "unlock"},
    "صمت": {"label": "وضع الصمت (كتم الكل)", "type": "action", "action": "silent"},
    "تقرير": {"label": "تعيين قناة التقارير", "type": "action", "action": "report"},
    "موث": {"label": "إدارة الأعضاء الموثوقين", "type": "action", "action": "trusted"},
}


def status_text(rec):
    s = rec["settings"]

    def st(v):
        return "مفعّل ✅" if v else "موقوف ⛔"

    return (
        "🛡️ <b>حالة الحماية</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"🔗 منع الروابط: {st(s['anti_link'])}\n"
        f"📤 منع التوجيه: {st(s['anti_forward'])}\n"
        f"🌊 مكافحة السبام: {st(s['anti_spam'])}\n"
        f"🖼 منع الستيكرات: {st(s['block_stickers'])}\n"
        f"🎞 منع الـGIF: {st(s['block_gifs'])}\n"
        f"📷 منع الصور: {st(s['block_photos'])}\n"
        f"🎥 منع الفيديوهات: {st(s['block_videos'])}\n"
        f"🎙 منع الصوتيات: {st(s['block_voice'])}\n"
        f"👋 الترحيب: {st(s['welcome'])}\n"
        f"👋 الوداع: {st(s['goodbye'])}\n"
        f"🤖 كابتشا الجدد: {st(s['captcha'])}\n"
        f"🛡️ حماية الغزوات: {st(s['raid_protection'])}\n"
        f"🔒 تقييد الجدد: {st(s['newbie_restrict'])}\n"
        f"⚠️ حد التحذيرات: {s['warn_limit']}\n"
        f"🔇 دقائق الكتم: {s['mute_minutes']}\n"
        f"🔒 الكروب مقفول: {'إي' if s.get('locked') else 'لأ'}\n"
        f"🔇 وضع الصمت: {'مفعّل' if s.get('silent_mode') else 'موقوف'}\n"
        f"💬 ردود مخصصة: {len(rec.get('custom_replies', {}))}\n"
        f"🚫 كلمات ممنوعة: {len(rec.get('blacklist', []))}\n"
        f"⭐ أعضاء موثوقين: {len(rec.get('trusted', []))}\n"
        f"📢 قناة تقارير: {s.get('report_channel') or 'ما محددة'}"
    )


def help_text():
    lines = ["📋 <b>اختصارات الأدمن</b>", "━━━━━━━━━━━━━━━",
             "ابعت الحرف <b>لحاله</b> (بدون أي شي زيادة) جوا الكروب:\n"]

    categories = {
        "🛡️ الحماية": ["ر", "ت", "س", "ص", "ج", "صو", "ف", "صت"],
        "👋 الترحيب": ["ه", "و", "تر"],
        "🔐 الكابتشا والحماية": ["ك", "غ", "جديد"],
        "💬 الردود والكلمات": ["رد", "كلم"],
        "⚙️ الإعدادات": ["ح", "د", "كتم", "ق", "فتح", "صمت", "تقرير"],
        "⭐ الأعضاء": ["موث"],
    }

    for cat, letters in categories.items():
        lines.append(f"\n<b>{cat}</b>")
        for letter in letters:
            if letter in SHORTCUTS:
                info = SHORTCUTS[letter]
                lines.append(f"<code>{letter}</code> — {info['label']}")

    lines.append("\n<b>📝 أوامر إضافية (بالرد على رسالة):</b>")
    lines.append("/ban /kick /mute /unmute /warn /unwarn /allow /disallow /trust /untrust")
    lines.append("")
    lines.append("<b>📝 إدارة الردود المخصصة (بدون رد):</b>")
    lines.append("<code>اضف: الكلمة | الرد</code>")
    lines.append("<code>حذف: رقم</code>")
    lines.append("")
    lines.append("<b>📝 إدارة الكلمات الممنوعة:</b>")
    lines.append("<code>اضف كلمة: الكلمة</code>")
    lines.append("<code>حذف كلمة: الكلمة</code>")
    lines.append("")
    lines.append("<b>📝 أوامر خاصة:</b>")
    lines.append("<code>ترحيب: نص الترحيب</code> — تعديل رسالة الترحيب")
    lines.append("<code>تقرير: @channel</code> — ربط قناة التقارير")
    return "\n".join(lines)


def two_button_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 الأوامر", callback_data="g_help")],
        [InlineKeyboardButton("👨‍💻 المطوّر", url=f"https://t.me/{DEVELOPER}")],
    ])


# ==================================================================
#                    الترحيب + الوداع + الكابتشا
# ==================================================================
PENDING_CAPTCHA = {}
_RECENTLY_GREETED = {}
JOIN_TRACKER = {}
NEWBIE_TRACKER = {}


def _already_greeted(chat_id, user_id):
    key = (chat_id, user_id)
    now = time.time()
    exp = _RECENTLY_GREETED.get(key)
    if exp and exp > now:
        return True
    _RECENTLY_GREETED[key] = now + 30
    return False


def _welcome_text(rec, member):
    custom = rec["settings"].get("welcome_text")
    if custom:
        text = custom
        text = text.replace("{name}", esc(member.first_name or ""))
        text = text.replace("{mention}", member.mention_html())
        text = text.replace("{id}", str(member.id))
        text = text.replace("{username}", esc(member.username or ""))
        return text
    import random
    return f"{member.mention_html()} {random.choice(WELCOME_MESSAGES)}"


def _is_raid(chat_id, limit, window):
    now = time.time()
    times = [t for t in JOIN_TRACKER.get(chat_id, []) if now - t < window]
    times.append(now)
    JOIN_TRACKER[chat_id] = times
    return len(times) >= limit


async def _lock_chat(bot, chat_id):
    try:
        await bot.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
    except Exception:
        pass


async def _unlock_chat(bot, chat_id):
    try:
        await bot.set_chat_permissions(
            chat_id,
            ChatPermissions(
                can_send_messages=True, can_send_photos=True, can_send_videos=True,
                can_send_other_messages=True, can_add_web_page_previews=True,
            ),
        )
    except Exception:
        pass


async def _greet_or_captcha(context, chat_id, member):
    if _already_greeted(chat_id, member.id):
        return
    rec = get_chat_rec(chat_id)
    s = rec["settings"]

    if s.get("raid_protection", True) and not s.get("locked"):
        if _is_raid(chat_id, s.get("raid_join_limit", 5), s.get("raid_window", 15)):
            s["locked"] = True
            persist(chat_id)
            await _lock_chat(context.bot, chat_id)
            try:
                await context.bot.send_message(
                    chat_id,
                    "🚨 <b>تنبيه غزوة!</b>\nصار عدد كبير من الانضمامات بوقت قصير، "
                    "قفلت الكروب تلقائياً للحماية.\nابعت <code>فتح</code> لفتحه لما تتأكد إنو الوضع آمن.",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
            return

    if s.get("newbie_restrict"):
        mins = s.get("newbie_restrict_min", 60)
        until = int(time.time()) + mins * 60
        try:
            await context.bot.restrict_chat_member(
                chat_id, member.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_photos=False,
                    can_send_videos=False,
                    can_send_audios=False,
                    can_send_voice_notes=False,
                    can_send_video_notes=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                ),
                until_date=until,
            )
            NEWBIE_TRACKER[(chat_id, member.id)] = until
        except Exception:
            pass

    if s.get("captcha"):
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
        try:
            sent = await context.bot.send_message(
                chat_id,
                f"👋 أهلاً {member.mention_html()}!\nاضغط الزر تحت خلال دقيقتين وإلا رح تنطرد تلقائياً.",
                parse_mode=ParseMode.HTML, reply_markup=kb,
            )
            context.application.create_task(
                _captcha_timeout(context, chat_id, member.id, sent.message_id)
            )
        except Exception:
            pass
    elif s.get("welcome"):
        welcome_media = rec.get("welcome_media")
        text = _welcome_text(rec, member)
        try:
            if welcome_media:
                await context.bot.send_photo(
                    chat_id, photo=welcome_media, caption=text,
                    parse_mode=ParseMode.HTML
                )
            else:
                await context.bot.send_message(
                    chat_id, text, parse_mode=ParseMode.HTML
                )
        except Exception:
            pass


def _joined(old_status, new_status):
    was_member = old_status in (
        ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER,
    )
    is_member = new_status in (
        ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER,
    )
    return (not was_member) and is_member


def _left(old_status, new_status):
    was_member = old_status in (
        ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER,
    )
    is_member = new_status in (
        ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER,
    )
    return was_member and (not is_member)


async def on_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmu = update.chat_member
    if not cmu:
        return
    member = cmu.new_chat_member.user
    if member.id == context.bot.id:
        return
    chat_id = cmu.chat.id
    old_status, new_status = cmu.old_chat_member.status, cmu.new_chat_member.status

    if _joined(old_status, new_status):
        await _greet_or_captcha(context, chat_id, member)
        return

    if _left(old_status, new_status):
        rec = get_chat_rec(chat_id)
        if rec["settings"].get("goodbye"):
            import random
            text = random.choice(GOODBYE_MESSAGES).format(name=member.mention_html())
            try:
                await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
            except Exception:
                pass


async def on_new_member_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.new_chat_members:
        return
    chat_id = msg.chat_id
    for member in msg.new_chat_members:
        if member.id == context.bot.id:
            continue
        await _greet_or_captcha(context, chat_id, member)


async def cmd_ping(update, context):
    await update.message.reply_text("🏓 pong — البوت شغّال ووصل آخر نسخة.")


async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmu = update.my_chat_member
    if not cmu:
        return
    chat_id = cmu.chat.id
    old_status = cmu.old_chat_member.status
    new_status = cmu.new_chat_member.status

    if _joined(old_status, new_status):
        try:
            await context.bot.send_message(
                chat_id,
                "🛡️ عشت، شكراً عالإضافة!\n"
                "ارفعني <b>مشرف</b> بصلاحيات (حذف رسائل، حظر أعضاء، تقييد) عشان أقدر أحميكم فعلياً.\n\n"
                "كل التحكم صار بأحرف بسيطة تبعتها جوا الكروب. اضغط «📋 الأوامر» تحت تشوفهم كلهم.",
                parse_mode=ParseMode.HTML, reply_markup=two_button_kb(),
            )
        except Exception:
            pass

    if new_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR):
        try:
            await context.bot.set_my_commands(
                [
                    BotCommand("panel", "الأوامر والحالة"),
                    BotCommand("ban", "حظر (بالرد)"),
                    BotCommand("unban", "فك حظر <id>"),
                    BotCommand("kick", "طرد (بالرد)"),
                    BotCommand("mute", "كتم (بالرد) [دقايق]"),
                    BotCommand("unmute", "فك كتم (بالرد)"),
                    BotCommand("warn", "تحذير (بالرد)"),
                    BotCommand("unwarn", "إنقاص تحذير (بالرد)"),
                    BotCommand("allow", "استثناء روابط ووسائط (بالرد)"),
                    BotCommand("disallow", "إلغاء الاستثناء (بالرد)"),
                ],
                scope=BotCommandScopeChatAdministrators(chat_id=chat_id),
            )
        except Exception:
            pass


async def _captcha_timeout(context, chat_id, user_id, msg_id):
    await asyncio.sleep(120)
    if PENDING_CAPTCHA.pop((chat_id, user_id), None):
        try:
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.unban_chat_member(chat_id, user_id)
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

    rec = get_chat_rec(chat_id)
    try:
        await q.edit_message_text(
            f"✅ تم التحقق!\n\n{_welcome_text(rec, q.from_user)}",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass


# ==================================================================
#                    الحماية
# ==================================================================
def _custom_list_text(rec):
    replies = rec.get("custom_replies", {})
    if not replies:
        return "ما في ردود مخصصة بعد.\n\nللإضافة: <code>اضف: الكلمة | الرد</code>"
    lines = ["💬 <b>الردود المخصصة</b>", "━━━━━━━━━━━━━━━"]
    for i, (trig, resp) in enumerate(replies.items(), 1):
        preview = resp if len(resp) <= 30 else resp[:30] + "…"
        lines.append(f"{i}. <code>{esc(trig)}</code> ← {esc(preview)}")
    lines.append("\nللحذف: <code>حذف: رقم</code>")
    return "\n".join(lines)


def _blacklist_text(rec):
    words = rec.get("blacklist", [])
    if not words:
        return "ما في كلمات ممنوعة بعد.\n\nللإضافة: <code>اضف كلمة: الكلمة</code>"
    lines = ["🚫 <b>الكلمات الممنوعة</b>", "━━━━━━━━━━━━━━━"]
    for i, w in enumerate(words, 1):
        lines.append(f"{i}. {esc(w)}")
    lines.append("\nللحذف: <code>حذف كلمة: الكلمة</code>")
    return "\n".join(lines)


def _trusted_list_text(rec):
    trusted = rec.get("trusted", [])
    if not trusted:
        return "ما في أعضاء موثوقين بعد.\n\nللإضافة: رد على العضو واكتب /trust"
    lines = ["⭐ <b>الأعضاء الموثوقين</b>", "━━━━━━━━━━━━━━━"]
    for uid in trusted:
        lines.append(f"• <code>{uid}</code>")
    return "\n".join(lines)


async def _send_report(context, chat_id, text):
    rec = get_chat_rec(chat_id)
    channel = rec["settings"].get("report_channel", "")
    if channel:
        try:
            await context.bot.send_message(
                channel, f"📢 <b>تقرير من الكروب</b>\n{text}",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass


async def _handle_admin_shortcut(update, context, rec):
    msg = update.message
    text = (msg.text or "").strip()
    chat_id = msg.chat_id
    s = rec["settings"]

    if text in SHORTCUTS:
        info = SHORTCUTS[text]
        await _delete_silent(context.bot, chat_id, msg.message_id)

        if info["type"] == "toggle":
            key = info["key"]
            s[key] = not s[key]
            persist(chat_id)
            await _reply_hideable(
                context, chat_id, rec,
                f"{'✅' if s[key] else '⛔'} {info['label']}: {'مفعّل' if s[key] else 'موقوف'}",
            )
            return True

        action = info["action"]
        if action == "status":
            await context.bot.send_message(chat_id, status_text(rec), parse_mode=ParseMode.HTML)
        elif action == "warnlimit":
            s["warn_limit"] = (s["warn_limit"] % 10) + 1
            persist(chat_id)
            await _reply_hideable(context, chat_id, rec, f"⚠️ حد التحذيرات الجديد: {s['warn_limit']}")
        elif action == "mute_time":
            s["mute_minutes"] = ((s["mute_minutes"] // 15) % 4 + 1) * 15
            persist(chat_id)
            await _reply_hideable(context, chat_id, rec, f"🔇 مدة الكتم الجديدة: {s['mute_minutes']} دقيقة")
        elif action == "lock":
            await _lock_chat(context.bot, chat_id)
            s["locked"] = True
            persist(chat_id)
            await context.bot.send_message(chat_id, "🔒 تم قفل الكروب — بس المشرفين يقدروا يكتبوا.")
        elif action == "unlock":
            await _unlock_chat(context.bot, chat_id)
            s["locked"] = False
            persist(chat_id)
            await context.bot.send_message(chat_id, "🔓 تم فتح الكروب.")
        elif action == "silent":
            s["silent_mode"] = not s.get("silent_mode", False)
            persist(chat_id)
            if s["silent_mode"]:
                await _lock_chat(context.bot, chat_id)
                await context.bot.send_message(chat_id, "🔇 تم تفعيل وضع الصمت — الكل مكتوم.")
            else:
                await _unlock_chat(context.bot, chat_id)
                await context.bot.send_message(chat_id, "🔊 تم إلغاء وضع الصمت.")
        elif action == "report":
            await context.bot.send_message(
                chat_id,
                "📢 <b>تعيين قناة التقارير</b>\n"
                "اكتب: <code>تقرير: @username</code> أو <code>تقرير: -100xxxx</code>",
                parse_mode=ParseMode.HTML,
            )
        elif action == "custom":
            await context.bot.send_message(chat_id, _custom_list_text(rec), parse_mode=ParseMode.HTML)
        elif action == "blacklist":
            await context.bot.send_message(chat_id, _blacklist_text(rec), parse_mode=ParseMode.HTML)
        elif action == "trusted":
            await context.bot.send_message(chat_id, _trusted_list_text(rec), parse_mode=ParseMode.HTML)
        elif action == "welcome_edit":
            await context.bot.send_message(
                chat_id,
                "👋 <b>تعديل رسالة الترحيب</b>\n"
                "اكتب: <code>ترحيب: نص الترحيب</code>\n"
                "المتغيرات: <code>{name}</code> <code>{mention}</code> <code>{id}</code> <code>{username}</code>\n"
                "لإضافة صورة: رد على صورة واكتب <code>/setwelcome</code>",
                parse_mode=ParseMode.HTML,
            )
        return True

    if text.startswith("ترحيب:"):
        new_text = text[len("ترحيب:"):].strip()
        await _delete_silent(context.bot, chat_id, msg.message_id)
        s["welcome_text"] = new_text
        persist(chat_id)
        await _reply_hideable(context, chat_id, rec, "✅ تم تحديث رسالة الترحيب.")
        return True

    if text.startswith("تقرير:"):
        channel = text[len("تقرير:"):].strip()
        await _delete_silent(context.bot, chat_id, msg.message_id)
        s["report_channel"] = channel
        persist(chat_id)
        await _reply_hideable(context, chat_id, rec, f"✅ تم ربط قناة التقارير: {esc(channel)}")
        return True

    if text.startswith("اضف:"):
        payload = text[len("اضف:"):].strip()
        await _delete_silent(context.bot, chat_id, msg.message_id)
        if "|" not in payload:
            await _reply_hideable(context, chat_id, rec, "الصيغة: اضف: الكلمة | الرد")
            return True
        trig, resp = payload.split("|", 1)
        trig, resp = trig.strip().lower(), resp.strip()
        if not trig or not resp:
            await _reply_hideable(context, chat_id, rec, "الصيغة: اضف: الكلمة | الرد")
            return True
        rec.setdefault("custom_replies", {})[trig] = resp
        persist(chat_id)
        await _reply_hideable(context, chat_id, rec, f"✅ تم إضافة رد لـ «{esc(trig)}»")
        return True

    if text.startswith("حذف:"):
        await _delete_silent(context.bot, chat_id, msg.message_id)
        try:
            idx = int(text[len("حذف:"):].strip())
        except ValueError:
            await _reply_hideable(context, chat_id, rec, "اكتب رقم صحيح، مثال: حذف: 1")
            return True
        replies = rec.get("custom_replies", {})
        keys = list(replies.keys())
        if 1 <= idx <= len(keys):
            del replies[keys[idx - 1]]
            persist(chat_id)
            await _reply_hideable(context, chat_id, rec, "✅ تم الحذف.")
        else:
            await _reply_hideable(context, chat_id, rec, "رقم غير موجود.")
        return True

    if text.startswith("اضف كلمة:"):
        word = text[len("اضف كلمة:"):].strip().lower()
        await _delete_silent(context.bot, chat_id, msg.message_id)
        if not word:
            await _reply_hideable(context, chat_id, rec, "الصيغة: اضف كلمة: الكلمة")
            return True
        if word not in rec.get("blacklist", []):
            rec.setdefault("blacklist", []).append(word)
            persist(chat_id)
        await _reply_hideable(context, chat_id, rec, f"✅ تم منع «{esc(word)}»")
        return True

    if text.startswith("حذف كلمة:"):
        word = text[len("حذف كلمة:"):].strip().lower()
        await _delete_silent(context.bot, chat_id, msg.message_id)
        if word in rec.get("blacklist", []):
            rec["blacklist"].remove(word)
            persist(chat_id)
            await _reply_hideable(context, chat_id, rec, "✅ تم الحذف.")
        else:
            await _reply_hideable(context, chat_id, rec, "الكلمة مش موجودة بالقائمة.")
        return True

    return False


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

    if s.get("silent_mode"):
        if not await is_group_admin(context.bot, chat_id, user.id):
            try:
                await msg.delete()
            except Exception:
                pass
            return

    if msg.text and await is_group_admin(context.bot, chat_id, user.id):
        if await _handle_admin_shortcut(update, context, rec):
            return

    if user.id in rec.get("trusted", []):
        return

    if await is_group_admin(context.bot, chat_id, user.id):
        return
    if user.id in rec["whitelist"]:
        return

    if s.get("anti_forward") and msg.forward_origin:
        try:
            await msg.delete()
            await _send_report(context, chat_id, f"🚫 تم حذف توجيه من {user.mention_html()}")
        except Exception:
            pass
        return

    if s.get("block_stickers") and msg.sticker:
        try:
            await msg.delete()
            await _add_warn(context, chat_id, user, "ستيكر")
        except Exception:
            pass
        return

    is_gif = bool(msg.animation) or (
        msg.document and getattr(msg.document, "mime_type", "") == "image/gif"
    )
    if s.get("block_gifs") and is_gif:
        try:
            await msg.delete()
            await _add_warn(context, chat_id, user, "GIF")
        except Exception:
            pass
        return

    if s.get("block_photos") and msg.photo:
        try:
            await msg.delete()
            await _add_warn(context, chat_id, user, "صورة")
        except Exception:
            pass
        return

    if s.get("block_videos") and msg.video:
        try:
            await msg.delete()
            await _add_warn(context, chat_id, user, "فيديو")
        except Exception:
            pass
        return

    if s.get("block_voice") and msg.voice:
        try:
            await msg.delete()
            await _add_warn(context, chat_id, user, "رسالة صوتية")
        except Exception:
            pass
        return

    text = msg.text or msg.caption or ""

    if text:
        low = text.lower()
        for word in rec.get("blacklist", []):
            if word in low:
                try:
                    await msg.delete()
                    await _add_warn(context, chat_id, user, f"كلمة ممنوعة: {word}")
                except Exception:
                    pass
                return

    if s.get("anti_link") and LINK_PATTERN.search(text):
        try:
            await msg.delete()
            warned = await _add_warn(context, chat_id, user, "رابط")
            if not warned:
                await context.bot.send_message(
                    chat_id, f"🚫 {user.mention_html()} الروابط ممنوعة هون.",
                    parse_mode=ParseMode.HTML,
                )
        except Exception:
            pass
        return

    if text:
        low = text.lower()
        mentioned_users = re.findall(r"@(\w{3,32})", text)

        for trig, resp in rec.get("custom_replies", {}).items():
            triggered = False
            if trig in low:
                triggered = True
            elif trig.startswith("@") and trig[1:] in mentioned_users:
                triggered = True

            if triggered:
                response = resp
                response = response.replace("{name}", esc(user.first_name or ""))
                response = response.replace("{mention}", user.mention_html())
                response = response.replace("{id}", str(user.id))
                response = response.replace("{username}", esc(user.username or ""))
                try:
                    await context.bot.send_message(chat_id, response, parse_mode=ParseMode.HTML)
                except Exception:
                    pass
                return

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
                await _send_report(context, chat_id, f"⚠️ كتم تلقائي: {user.mention_html()} — فيضان رسائل")
            except Exception:
                pass


async def _add_warn(context, chat_id, user, reason=""):
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
            await _send_report(context, chat_id, f"🚷 طرد تلقائي: {user.mention_html()} — {reason}")
        except Exception:
            pass
        rec["warns"][key] = 0
        persist(chat_id)
        return True
    else:
        warn_text = f"⚠️ تحذير لـ {user.mention_html()} ({rec['warns'][key]}/{limit})"
        if reason:
            warn_text += f"\nالسبب: {esc(reason)}"
        await context.bot.send_message(chat_id, warn_text, parse_mode=ParseMode.HTML)
        return False


# ==================================================================
#                    أوامر الإشراف
# ==================================================================
def _reply_target(update):
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    return None


async def cmd_ban(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    rec = get_chat_rec(msg.chat_id)
    target = _reply_target(update)
    if not target:
        await _reply_hideable(context, msg.chat_id, rec, "رد على رسالة الشخص واكتب /ban")
        await _cleanup_command(context, msg, rec)
        return
    try:
        await context.bot.ban_chat_member(msg.chat_id, target.id)
        await _reply_hideable(context, msg.chat_id, rec, f"🚫 تم حظر {target.mention_html()}", parse_mode=ParseMode.HTML)
        await _send_report(context, msg.chat_id, f"🚫 حظر يدوي: {target.mention_html()}")
    except Exception as e:
        await _reply_hideable(context, msg.chat_id, rec, f"ما قدرت: {e}")
    await _cleanup_command(context, msg, rec)


async def cmd_unban(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    rec = get_chat_rec(msg.chat_id)
    if not context.args:
        await _reply_hideable(context, msg.chat_id, rec, "اكتب /unban <id>")
        await _cleanup_command(context, msg, rec)
        return
    try:
        await context.bot.unban_chat_member(msg.chat_id, int(context.args[0]))
        await _reply_hideable(context, msg.chat_id, rec, "✅ تم فك الحظر.")
    except Exception as e:
        await _reply_hideable(context, msg.chat_id, rec, f"ما قدرت: {e}")
    await _cleanup_command(context, msg, rec)


async def cmd_kick(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    rec = get_chat_rec(msg.chat_id)
    target = _reply_target(update)
    if not target:
        await _reply_hideable(context, msg.chat_id, rec, "رد على رسالة الشخص واكتب /kick")
        await _cleanup_command(context, msg, rec)
        return
    try:
        await context.bot.ban_chat_member(msg.chat_id, target.id)
        await context.bot.unban_chat_member(msg.chat_id, target.id)
        await _reply_hideable(context, msg.chat_id, rec, f"👢 تم طرد {target.mention_html()}", parse_mode=ParseMode.HTML)
        await _send_report(context, msg.chat_id, f"👢 طرد يدوي: {target.mention_html()}")
    except Exception as e:
        await _reply_hideable(context, msg.chat_id, rec, f"ما قدرت: {e}")
    await _cleanup_command(context, msg, rec)


async def cmd_mute(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    rec = get_chat_rec(msg.chat_id)
    target = _reply_target(update)
    if not target:
        await _reply_hideable(context, msg.chat_id, rec, "رد على رسالة الشخص واكتب /mute [دقايق]")
        await _cleanup_command(context, msg, rec)
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
        await _reply_hideable(context, msg.chat_id, rec, f"🔇 تم كتم {target.mention_html()} لمدة {minutes} دقيقة", parse_mode=ParseMode.HTML)
    except Exception as e:
        await _reply_hideable(context, msg.chat_id, rec, f"ما قدرت: {e}")
    await _cleanup_command(context, msg, rec)


async def cmd_unmute(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    rec = get_chat_rec(msg.chat_id)
    target = _reply_target(update)
    if not target:
        await _reply_hideable(context, msg.chat_id, rec, "رد على رسالة الشخص واكتب /unmute")
        await _cleanup_command(context, msg, rec)
        return
    try:
        await context.bot.restrict_chat_member(
            msg.chat_id, target.id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_photos=True,
                can_send_videos=True, can_send_other_messages=True,
            ),
        )
        await _reply_hideable(context, msg.chat_id, rec, f"🔊 تم فك الكتم عن {target.mention_html()}", parse_mode=ParseMode.HTML)
    except Exception as e:
        await _reply_hideable(context, msg.chat_id, rec, f"ما قدرت: {e}")
    await _cleanup_command(context, msg, rec)


async def cmd_warn(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    rec = get_chat_rec(msg.chat_id)
    target = _reply_target(update)
    if not target:
        await _reply_hideable(context, msg.chat_id, rec, "رد على رسالة الشخص واكتب /warn")
        await _cleanup_command(context, msg, rec)
        return
    await _add_warn(context, msg.chat_id, target)
    await _cleanup_command(context, msg, rec)


async def cmd_unwarn(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    rec = get_chat_rec(msg.chat_id)
    target = _reply_target(update)
    if not target:
        await _reply_hideable(context, msg.chat_id, rec, "رد على رسالة الشخص واكتب /unwarn")
        await _cleanup_command(context, msg, rec)
        return
    key = str(target.id)
    if rec["warns"].get(key, 0) > 0:
        rec["warns"][key] -= 1
        persist(msg.chat_id)
    await _reply_hideable(
        context, msg.chat_id, rec,
        f"↩️ تم إنقاص تحذير عن {target.mention_html()} ({rec['warns'].get(key,0)})",
        parse_mode=ParseMode.HTML,
    )
    await _cleanup_command(context, msg, rec)


async def cmd_allow(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    rec = get_chat_rec(msg.chat_id)
    target = _reply_target(update)
    if not target:
        await _reply_hideable(context, msg.chat_id, rec, "رد على رسالة الشخص واكتب /allow")
        await _cleanup_command(context, msg, rec)
        return
    if target.id not in rec["whitelist"]:
        rec["whitelist"].append(target.id)
        persist(msg.chat_id)
    await _reply_hideable(context, msg.chat_id, rec, f"✅ {target.mention_html()} صار مسموحله يبعت روابط.", parse_mode=ParseMode.HTML)
    await _cleanup_command(context, msg, rec)


async def cmd_disallow(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    rec = get_chat_rec(msg.chat_id)
    target = _reply_target(update)
    if not target:
        await _reply_hideable(context, msg.chat_id, rec, "رد على رسالة الشخص واكتب /disallow")
        await _cleanup_command(context, msg, rec)
        return
    if target.id in rec["whitelist"]:
        rec["whitelist"].remove(target.id)
        persist(msg.chat_id)
    await _reply_hideable(context, msg.chat_id, rec, "✅ تم إلغاء الاستثناء.")
    await _cleanup_command(context, msg, rec)


async def cmd_trust(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    rec = get_chat_rec(msg.chat_id)
    target = _reply_target(update)
    if not target:
        await _reply_hideable(context, msg.chat_id, rec, "رد على رسالة الشخص واكتب /trust")
        await _cleanup_command(context, msg, rec)
        return
    trusted = rec.setdefault("trusted", [])
    if target.id not in trusted:
        trusted.append(target.id)
        persist(msg.chat_id)
    await _reply_hideable(context, msg.chat_id, rec, f"⭐ {target.mention_html()} صار عضو موثوق.", parse_mode=ParseMode.HTML)
    await _cleanup_command(context, msg, rec)


async def cmd_untrust(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    rec = get_chat_rec(msg.chat_id)
    target = _reply_target(update)
    if not target:
        await _reply_hideable(context, msg.chat_id, rec, "رد على رسالة الشخص واكتب /untrust")
        await _cleanup_command(context, msg, rec)
        return
    trusted = rec.get("trusted", [])
    if target.id in trusted:
        trusted.remove(target.id)
        persist(msg.chat_id)
    await _reply_hideable(context, msg.chat_id, rec, f"⭐ تم إلغاء الثقة عن {target.mention_html()}.", parse_mode=ParseMode.HTML)
    await _cleanup_command(context, msg, rec)


async def cmd_setwelcome(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    rec = get_chat_rec(msg.chat_id)

    if msg.reply_to_message and msg.reply_to_message.photo:
        photo = msg.reply_to_message.photo[-1].file_id
        rec["welcome_media"] = photo
        persist(msg.chat_id)
        await _reply_hideable(context, msg.chat_id, rec, "✅ تم تعيين صورة الترحيب.")
    elif msg.reply_to_message and msg.reply_to_message.video:
        video = msg.reply_to_message.video.file_id
        rec["welcome_media"] = video
        persist(msg.chat_id)
        await _reply_hideable(context, msg.chat_id, rec, "✅ تم تعيين فيديو الترحيب.")
    else:
        await _reply_hideable(context, msg.chat_id, rec, "رد على صورة أو فيديو واكتب /setwelcome")
    await _cleanup_command(context, msg, rec)


async def cmd_clearwelcome(update, context):
    msg = update.message
    if not await is_group_admin(context.bot, msg.chat_id, msg.from_user.id):
        return
    rec = get_chat_rec(msg.chat_id)
    rec["welcome_media"] = None
    persist(msg.chat_id)
    await _reply_hideable(context, msg.chat_id, rec, "✅ تم إلغاء صورة/فيديو الترحيب.")
    await _cleanup_command(context, msg, rec)


# ==================================================================
#                    لوحة التحكم
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
    await _delete_silent(context.bot, msg.chat_id, msg.message_id)
    await context.bot.send_message(
        msg.chat_id, status_text(rec), parse_mode=ParseMode.HTML, reply_markup=two_button_kb()
    )


async def panel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = q.message.chat_id
    if not await is_group_admin(context.bot, chat_id, q.from_user.id):
        await q.answer("❌ بس المشرفين", show_alert=True)
        return
    if q.data == "g_help":
        await q.answer()
        await q.edit_message_text(help_text(), parse_mode=ParseMode.HTML, reply_markup=two_button_kb())
        return
    if q.data == "g_close":
        await q.answer()
        await _delete_silent(context.bot, chat_id, q.message.message_id)
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

    app.add_handler(CommandHandler("ping", cmd_ping))
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
    app.add_handler(CommandHandler("trust", cmd_trust))
    app.add_handler(CommandHandler("untrust", cmd_untrust))
    app.add_handler(CommandHandler("setwelcome", cmd_setwelcome))
    app.add_handler(CommandHandler("clearwelcome", cmd_clearwelcome))

    app.add_handler(CallbackQueryHandler(panel_cb, pattern="^g_"))
    app.add_handler(CallbackQueryHandler(captcha_cb, pattern="^cap:"))

    app.add_handler(ChatMemberHandler(on_my_chat_member, chat_member_types=ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(on_chat_member_update, chat_member_types=ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_member_message))
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
    await app.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
    try:
        await app.bot.set_my_commands([], scope=BotCommandScopeDefault())
    except Exception:
        pass
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
