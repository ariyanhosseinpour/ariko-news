# -*- coding: utf-8 -*-
"""
ARIKO News Bot — بات مستقل خبر انیمه
جدا شده از بات دانلود. فقط بخش خبر، رنکینگ‌ها، ایجنت AI و انتشار در کانال‌ها.
تنظیمات با متغیرهای محیطی:
  NEWS_BOT_TOKEN  (اجباری) توکن بات خبر — نباید با توکن بات دانلود یکی باشه
  NEWS_DATA_DIR   (اختیاری) پوشه دائمی دیتابیس و بکاپ‌ها؛ پیش‌فرض بیرون از پوشه بات:
                  ویندوز %APPDATA%\\ArikoNewsBot — لینوکس ~/.ariko_newsbot
                  (با عوض کردن فایل‌های بات، دیتابیس دست نمی‌خوره)
  NEWS_DB_PATH    (اختیاری) مسیر دقیق فایل دیتابیس
  OPENROUTER_API_KEY / GEMINI_API_KEY / GEMINI_MODEL / AI_BASE_URL / AI_API_KEY / AI_MODEL (اختیاری)
می‌تونی این‌ها رو توی فایل .env کنار همین فایل یا داخل پوشه دائمی بذاری (نمونه: .env.example).
"""
import os
import sys
import logging
import telebot

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path: str) -> None:
    """خواندن فایل .env ساده (KEY=VALUE). متغیرهای محیطی واقعی اولویت دارن."""
    try:
        with open(path, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass


_load_dotenv(os.path.join(BASE_DIR, ".env"))


def _default_data_dir() -> str:
    if os.name == "nt":
        return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "ArikoNewsBot")
    return os.path.join(os.path.expanduser("~"), ".ariko_newsbot")


# پوشه دائمی: بیرون از پوشه کد، تا با جایگزین کردن فایل‌های بات دیتابیس از بین نره
DATA_DIR = os.environ.get("NEWS_DATA_DIR", "").strip() or _default_data_dir()
os.makedirs(DATA_DIR, exist_ok=True)
_load_dotenv(os.path.join(DATA_DIR, ".env"))
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

TOKEN = os.environ.get("NEWS_BOT_TOKEN", "").strip()
DB_PATH = os.environ.get("NEWS_DB_PATH", "").strip() or os.path.join(DATA_DIR, "news_bot.db")
LEGACY_DB_PATH = os.path.join(BASE_DIR, "news_bot.db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler(os.path.join(BASE_DIR, "news_bot.log"), encoding="utf-8")],
)
logger = logging.getLogger("news_bot")


class _DropDeprecated(logging.Filter):
    """هشدارهای «deprecated» کتابخونه‌ی تلگرام فقط لاگ رو شلوغ می‌کنن؛ اثری روی کار ندارن."""
    def filter(self, record):
        return "is deprecated" not in record.getMessage()


logging.getLogger("TeleBot").addFilter(_DropDeprecated())
for _h in logging.getLogger().handlers:
    _h.addFilter(_DropDeprecated())
telebot.logger.setLevel(logging.WARNING)


def _migrate_legacy_db():
    """دیتابیس قدیمی کنار news.py رو یک‌بار به پوشه دائمی منتقل (کپی) می‌کنه."""
    import sqlite3 as _sq
    if os.environ.get("NEWS_DB_PATH", "").strip() or os.path.exists(DB_PATH):
        return
    if not os.path.exists(LEGACY_DB_PATH) or os.path.abspath(LEGACY_DB_PATH) == os.path.abspath(DB_PATH):
        return
    try:
        src = _sq.connect(LEGACY_DB_PATH)
        dst = _sq.connect(DB_PATH)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        logger.warning("Database migrated from %s to %s (the old file was left untouched)", LEGACY_DB_PATH, DB_PATH)
    except Exception as exc:
        logger.error("Database migration failed: %s", exc)
        try:
            os.remove(DB_PATH)
        except Exception:
            pass


_migrate_legacy_db()
logger.info("Data dir: %s | DB: %s", DATA_DIR, DB_PATH)

if not TOKEN:
    print("❌ NEWS_BOT_TOKEN تنظیم نشده. توکن بات خبر رو از BotFather بگیر و ست کن.")
    print(f"   فایل .env رو کنار news.py یا داخل پوشه دائمی بذار: {DATA_DIR}")
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path + ".txt"):
        print("⚠️ فایل .env.txt پیدا شد؛ ویندوز پسوند .txt اضافه کرده. اسمش رو دقیقاً .env بذار.")
    elif not os.path.exists(env_path) and not os.path.exists(os.path.join(DATA_DIR, ".env")):
        print(f"⚠️ فایل .env پیدا نشد: {env_path}\n"
              "   .env.example فقط نمونه‌ست و خونده نمیشه؛ یه کپی ازش بساز به اسم .env و توکن رو اونجا بنویس.")
    sys.exit(1)

# ===== پروکسی (برای اجرا روی کامپیوتر در ایران) =====
# اگه VPN ات حالت TUN / System-wide نداره، آدرس پروکسی HTTP برنامه VPN رو اینجا بذار.
# مثال v2rayN:  http://127.0.0.1:10809   — اگه لازم نیست خالی بذار: ""
NEWS_PROXY = os.environ.get("NEWS_PROXY", "").strip()
if NEWS_PROXY:
    from telebot import apihelper as _apihelper
    _apihelper.proxy = {"http": NEWS_PROXY, "https": NEWS_PROXY}
    os.environ["HTTP_PROXY"] = os.environ["HTTPS_PROXY"] = NEWS_PROXY

bot = telebot.TeleBot(TOKEN, parse_mode=None, threaded=True, num_threads=4)

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:
    Image = ImageDraw = ImageFont = ImageOps = None

import sqlite3

import base64

import threading

import os

import time

import gc

import calendar
import random
import re

import hashlib
import hmac

import ipaddress

import urllib.request

import urllib.parse

import urllib.error

import tempfile

import io

import json

import xml.etree.ElementTree as ET

from difflib import SequenceMatcher

from email.utils import parsedate_to_datetime

from html import unescape

from html.parser import HTMLParser

from datetime import date, datetime, timedelta, timezone

from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, LinkPreviewOptions
)

# جایگزین پارامتر منسوخ disable_web_page_preview
NO_LINK_PREVIEW = LinkPreviewOptions(is_disabled=True)
WITH_LINK_PREVIEW = LinkPreviewOptions(is_disabled=False)

ADMINS = [513902877, 7818030837, 1801778906, 315593077]

BACK_MAIN = "↩️ بازگشت به منوی اصلی"

NEWS_DEFAULT_CHECK_MINUTES = 10

NEWS_MIN_CHECK_MINUTES = 5

NEWS_HTTP_TIMEOUT = 20

NEWS_USER_AGENT = "ARIKO-NewsBot/1.0 (+Telegram archive collector)"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/free").strip() or "openrouter/free"

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

# gemini-2.5-flash-lite دیگه برای کاربرهای جدید در دسترس نیست (HTTP 404)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite"

# اگه مدل اصلی 404 داد (حذف/بازنشسته شد)، این‌ها به ترتیب امتحان میشن
GEMINI_FALLBACK_MODELS = [
    m.strip() for m in os.environ.get("GEMINI_FALLBACK_MODELS", "gemini-3.5-flash,gemini-flash-lite-latest,gemini-flash-latest").split(",")
    if m.strip() and m.strip() != GEMINI_MODEL
]

# کلید در هدر x-goog-api-key فرستاده میشه تا توی URL و لاگ خطاها نیاد
GEMINI_CHAT_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

def _ai_api_available() -> bool:
    return bool(GEMINI_API_KEY or OPENROUTER_API_KEY)

NEWS_AGENT_MAX_ARTICLE_CHARS = 24000

X_LEAKER_SPECIAL_PREFIX = "special://xleaker/"

X_LEAKER_REQUEST_GAP_SECONDS = 30.0

X_SYNDICATION_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)

_x_leaker_rate_lock = threading.Lock()

_x_leaker_last_fetch_monotonic = 0.0

# کوکی auth_token یک اکانت X (ترجیحاً اکانت دوم، نه اکانت اصلی). با لاگین، محدودیت 429 خیلی کمتر میشه.
def _cookie_env(name: str) -> str:
    """مقدار کوکی از .env؛ هر چیزی بعد از فاصله (مثل توضیح یا «←») و کاراکترهای غیرمجاز حذف میشه."""
    raw = (os.environ.get(name, "") or "").strip().strip('"').strip("'")
    raw = raw.split()[0] if raw.split() else ""
    return re.sub(r"[^A-Za-z0-9%_\-.:]", "", raw)


X_AUTH_TOKEN = _cookie_env("X_AUTH_TOKEN")

# کوکی sessionid یک اکانت اینستاگرام (ترجیحاً اکانت دوم). بدون لاگین اینستاگرام اکثر درخواست‌ها رو رد می‌کنه.
INSTAGRAM_SESSIONID = _cookie_env("INSTAGRAM_SESSIONID")


def _social_net_error(exc) -> str:
    """خطاهای شبکه رو به یه جمله قابل فهم تبدیل می‌کنه."""
    text = str(exc)
    if re.search(r"WRONG_VERSION_NUMBER|EOF occurred|UNEXPECTED_EOF|Connection reset|10054|Remote end closed|timed out", text, re.I):
        return "اتصال برقرار نشد (احتمالاً فیلتر شده یا VPN این سایت رو رد نمی‌کنه)"
    return text[:160]

# بعد از 429، Syndication تا این مدت دیگه صدا زده نمیشه (هر بار دو برابر، تا سقف ۳ ساعت)
X_SYNDICATION_COOLDOWN_MIN = 15 * 60
X_SYNDICATION_COOLDOWN_MAX = 3 * 3600
_x_syndication_blocked_until = 0.0
_x_syndication_cooldown = 0.0

# جایگزین وقتی Syndication محدود شده: RSS از Nitter و مشابهش. {handle} جایگزین میشه.
# با متغیر X_RSS_BRIDGES قابل تغییره (با کاما جدا کن)؛ مثلاً RSSHub شخصی خودت.
X_RSS_BRIDGES = [
    b.strip() for b in os.environ.get(
        "X_RSS_BRIDGES", "https://nitter.net/{handle}/rss"
    ).split(",") if b.strip() and "{handle}" in b
]

DEFAULT_NEWS_SOURCES = [
    ("Anime News Network", "https://www.animenewsnetwork.com/news/rss.xml?ann-edition=us", "https://www.animenewsnetwork.com/news/"),
    ("MyAnimeList News", "https://myanimelist.net/rss/news.xml", "https://myanimelist.net/news"),
    ("Crunchyroll News", "https://cr-news-api-service.prd.crunchyrollsvc.com/v1/en-US/rss", "https://www.crunchyroll.com/news/latest"),
    ("AniTrendz", "special://anitrendz", "https://www.anitrendz.com/charts/top-anime"),
    ("Anime Corner Weekly", "special://animecorner-weekly", "https://animecorner.me/category/anime-of-the-week/"),
    ("MyAnimeList Top Airing", "special://mal-top-airing", "https://myanimelist.net/topanime.php?type=airing"),
    ("MyAnimeList Top Anime Changes", "special://mal-top-alltime", "https://myanimelist.net/topanime.php"),
]

ANITRENDZ_SPECIAL_FEED = "special://anitrendz"

ANIMECORNER_SPECIAL_FEED = "special://animecorner-weekly"

MAL_TOP_AIRING_SPECIAL_FEED = "special://mal-top-airing"

MAL_TOP_AIRING_URL = "https://myanimelist.net/topanime.php?type=airing"

MAL_JIKAN_TOP_AIRING_API = "https://api.jikan.moe/v4/top/anime?filter=airing&page=1&limit=10"

MAL_TOP_ALLTIME_SPECIAL_FEED = "special://mal-top-alltime"

MAL_TOP_ALLTIME_URL = "https://myanimelist.net/topanime.php"

MAL_JIKAN_TOP_ALLTIME_API = "https://api.jikan.moe/v4/top/anime?page=1&limit=10"

MAL_TOP_ALLTIME_SNAPSHOT_KEY = "mal_top_alltime_snapshot_v55"

ANIMECORNER_POLL_BROWSE_URL = "https://animecorner.me/polls/browse/anime-of-the-week"

ANIMECORNER_WEEKLY_INDEX_URLS = [
    "https://animecorner.me/category/anime-of-the-week/",
    "https://animecorner.me/category/anime-corner/rankings/anime-of-the-week/",
    "https://animecorner.me/category/anime-corner/rankings/",
    "https://animecorner.me/",
]

ANITRENDZ_CHARTS = [
    ("anime", "https://www.anitrendz.com/charts/top-anime"),
    ("male", "https://www.anitrendz.com/charts/male-characters"),
    ("female", "https://www.anitrendz.com/charts/female-characters"),
]

_anitrendz_last_partial_error = ""

user_state = {}

state_lock = threading.Lock()

db_write_lock = threading.Lock()

news_run_lock = threading.Lock()

weekly_ranking_test_lock = threading.Lock()

def _thread_exception_hook(args):
    try:
        logger.error(
            "UNCAUGHT THREAD ERROR name=%s",
            getattr(args.thread, "name", "unknown"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
    except Exception:
        pass

threading.excepthook = _thread_exception_hook

def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn

NEWS_BACKUP_KEEP = max(1, int(os.environ.get("NEWS_BACKUP_KEEP", "14") or 14))
NEWS_BACKUP_EVERY_HOURS = 24


def news_db_backup(reason: str = "auto") -> str:
    """کپی سالم (با backup API، حتی وسط کار بات) داخل پوشه backups؛ قدیمی‌ها پاک میشن."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, f"news_bot-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{reason}.db")
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(path)
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()
    backups = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("news_bot-") and f.endswith(".db"))
    for old in backups[:-NEWS_BACKUP_KEEP]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old))
        except Exception:
            pass
    return path


def _news_backup_zip(path: str) -> str:
    """بکاپ برای فرستادن توی تلگرام زیپ میشه (دیتابیس متنیه، چند برابر کوچیک‌تر میشه و کمتر تایم‌اوت می‌خوره)."""
    import zipfile
    out = path + ".zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(path, os.path.basename(path))
    return out


def _news_last_backup_age_hours() -> float:
    try:
        files = [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith(".db")]
        return (time.time() - max(os.path.getmtime(f) for f in files)) / 3600 if files else 1e9
    except Exception:
        return 1e9


def start_db_backup_thread():
    """بکاپ خودکار روزانه. اگه NEWS_BACKUP_CHAT_ID ست باشه، فایل بکاپ به همون چت هم فرستاده میشه."""
    chat = os.environ.get("NEWS_BACKUP_CHAT_ID", "").strip()

    def loop():
        while True:
            try:
                if _news_last_backup_age_hours() >= NEWS_BACKUP_EVERY_HOURS:
                    path = news_db_backup("daily")
                    logger.info("Database backup saved: %s", path)
                    if chat:
                        zpath = _news_backup_zip(path)
                        try:
                            with open(zpath, "rb") as fh:
                                bot.send_document(int(chat) if chat.lstrip("-").isdigit() else chat, fh, timeout=900,
                                                  caption="💾 بکاپ روزانه دیتابیس بات خبر")
                        finally:
                            try:
                                os.remove(zpath)
                            except Exception:
                                pass
            except Exception:
                logger.exception("Database backup failed")
            time.sleep(3600)

    threading.Thread(target=loop, daemon=True, name="db-backup").start()


def news_db_restore_from(path: str) -> str:
    """دیتابیس فعلی رو (بعد از بکاپ گرفتن) با فایل داده‌شده جایگزین می‌کنه. خروجی: مسیر بکاپ قبلی."""
    check = sqlite3.connect(path)
    try:
        tables = {r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        ok = check.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        check.close()
    if ok != "ok" or not {"settings", "news_sources"}.issubset(tables):
        raise ValueError("این فایل دیتابیس معتبر بات خبر نیست.")
    before = news_db_backup("before-restore")
    src = sqlite3.connect(path)
    with db_write_lock:
        dst = sqlite3.connect(DB_PATH)
        try:
            with dst:
                src.backup(dst)
        finally:
            src.close()
            dst.close()
    return before


def init_db():
    with db_write_lock:
        conn = db()
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode = WAL")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS anime(
            eng_name  TEXT PRIMARY KEY,
            fa_name   TEXT NOT NULL,
            jp_name   TEXT,
            anime_code INTEGER
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS episodes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            eng_name TEXT NOT NULL,
            season  TEXT NOT NULL,
            part    TEXT NOT NULL,
            quality TEXT NOT NULL,
            file_id TEXT NOT NULL,
            UNIQUE(eng_name, season, part, quality),
            FOREIGN KEY(eng_name) REFERENCES anime(eng_name) ON DELETE CASCADE
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS sponsors(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL UNIQUE
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS anime_posts(
            eng_name TEXT PRIMARY KEY,
            media_type TEXT NOT NULL,
            file_id TEXT,
            caption TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            first_name TEXT,
            query TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            approved_by INTEGER,
            approved_by_name TEXT,
            approved_at TEXT,
            done_by INTEGER,
            done_by_name TEXT,
            done_at TEXT,
            matched_anime TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS download_links(
            code TEXT PRIMARY KEY,
            eng_name TEXT NOT NULL,
            season TEXT NOT NULL,
            part TEXT NOT NULL,
            quality TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS change_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT CURRENT_TIMESTAMP,
            action TEXT NOT NULL,
            details TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            anime_query TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, anime_query)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS seasonal_anime(
            eng_name TEXT PRIMARY KEY,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(eng_name) REFERENCES anime(eng_name) ON DELETE CASCADE
        )
        """)

        # ✅ پست‌های ساخته‌شده با دکمه شیشه‌ای (برای کانال)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS channel_posts(
            code TEXT PRIMARY KEY,
            link TEXT NOT NULL,
            button_text TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # ✅ آخرین زمانی که هر کاربر لیست «جدیدترین‌ها» رو دیده
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_latest_seen(
            user_id INTEGER PRIMARY KEY,
            last_seen_at TEXT NOT NULL
        )
        """)

        # ✅ زمان اضافه شدن هر انیمه (برای لیست جدیدترین‌ها)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS anime_added_at(
            eng_name TEXT PRIMARY KEY,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(eng_name) REFERENCES anime(eng_name) ON DELETE CASCADE
        )
        """)

        # ✅ اشتراک نوتیفیکیشن روی یک انیمه مشخص (برای قسمت جدید)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS anime_subscriptions(
            user_id INTEGER NOT NULL,
            eng_name TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, eng_name),
            FOREIGN KEY(eng_name) REFERENCES anime(eng_name) ON DELETE CASCADE ON UPDATE CASCADE
        )
        """)

        # ✅ لاگ درخواست فایل برای آمار بازخورد انیمه‌ها
        cur.execute("""
        CREATE TABLE IF NOT EXISTS anime_download_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            eng_name TEXT NOT NULL,
            season TEXT NOT NULL,
            part TEXT NOT NULL,
            quality TEXT NOT NULL,
            requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(eng_name) REFERENCES anime(eng_name) ON DELETE CASCADE ON UPDATE CASCADE
        )
        """)

        # ✅ ذخیره broadcast message ids برای امکان حذف
        cur.execute("""
        CREATE TABLE IF NOT EXISTS broadcast_messages(
            admin_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(admin_id, user_id)
        )
        """)

        # ✅ کانال‌های مجاز برای ارسال پست دکمه‌دار
        cur.execute("""
        CREATE TABLE IF NOT EXISTS post_channels(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # ✅ منابع خبری برای جمع‌آوری خودکار اخبار انیمه
        cur.execute("""
        CREATE TABLE IF NOT EXISTS news_sources(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            feed_url TEXT NOT NULL UNIQUE,
            site_url TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_checked_at TEXT,
            last_error TEXT
        )
        """)

        # ✅ آرشیو خبرهای دیده‌شده/ارسال‌شده برای جلوگیری از تکرار
        cur.execute("""
        CREATE TABLE IF NOT EXISTS news_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            guid TEXT NOT NULL,
            fingerprint TEXT,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            published_at TEXT,
            summary TEXT,
            article_text TEXT,
            image_url TEXT,
            video_url TEXT,
            trailer_url TEXT,
            news_type TEXT DEFAULT 'news',
            topic_key TEXT,
            ranking_payload TEXT,
            status TEXT DEFAULT 'queued',
            archive_chat_id TEXT,
            archive_message_id INTEGER,
            archive_secondary_message_id INTEGER,
            archive_media_type TEXT,
            archive_secondary_media_type TEXT,
            archive_text TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_id, guid),
            FOREIGN KEY(source_id) REFERENCES news_sources(id) ON DELETE CASCADE
        )
        """)

        # ✅ محل انتشار خبرها برای ساخت زنجیره ریپلای خبرهای مرتبط
        cur.execute("""
        CREATE TABLE IF NOT EXISTS news_publications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            post_channel_id INTEGER NOT NULL,
            channel_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            topic_key TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(item_id, post_channel_id),
            FOREIGN KEY(item_id) REFERENCES news_items(id) ON DELETE CASCADE
        )
        """)

        # ایندکس‌ها و migrationهای سازگار با دیتابیس قبلی
        anime_columns = {row["name"] for row in cur.execute("PRAGMA table_info(anime)").fetchall()}
        if "jp_name" not in anime_columns:
            cur.execute("ALTER TABLE anime ADD COLUMN jp_name TEXT")
        if "anime_code" not in anime_columns:
            cur.execute("ALTER TABLE anime ADD COLUMN anime_code INTEGER")

        # migration خبرها بدون پاک‌شدن منابع/آرشیو قبلی
        news_columns = {row["name"] for row in cur.execute("PRAGMA table_info(news_items)").fetchall()}
        if "topic_key" not in news_columns:
            cur.execute("ALTER TABLE news_items ADD COLUMN topic_key TEXT")
        if "archive_secondary_message_id" not in news_columns:
            cur.execute("ALTER TABLE news_items ADD COLUMN archive_secondary_message_id INTEGER")
        if "archive_secondary_media_type" not in news_columns:
            cur.execute("ALTER TABLE news_items ADD COLUMN archive_secondary_media_type TEXT")
        if "ranking_payload" not in news_columns:
            cur.execute("ALTER TABLE news_items ADD COLUMN ranking_payload TEXT")
        if "article_text" not in news_columns:
            cur.execute("ALTER TABLE news_items ADD COLUMN article_text TEXT")
        if "trailer_url" not in news_columns:
            cur.execute("ALTER TABLE news_items ADD COLUMN trailer_url TEXT")

        # هر کد فقط برای یک انیمه قابل استفاده است؛ انیمه‌های قدیمی می‌توانند فعلاً کد نداشته باشند.
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_anime_code_unique "
            "ON anime(anime_code) WHERE anime_code IS NOT NULL"
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_episodes_anime_season ON episodes(eng_name, season)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status, id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_anime_added_at_time ON anime_added_at(added_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_notifications_query ON notifications(anime_query)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_download_events_anime_time ON anime_download_events(eng_name, requested_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_download_events_user_time ON anime_download_events(user_id, requested_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_news_items_status ON news_items(status, id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_news_items_fingerprint ON news_items(fingerprint)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_news_items_created ON news_items(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_news_sources_active ON news_sources(active, id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_news_items_topic ON news_items(topic_key, id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_news_publications_topic ON news_publications(post_channel_id, topic_key, id)")

        # در اولین نصب، منابع رسمی + AniTrendz + چند لیکر شناخته‌شده X اضافه شوند؛ خبرهای موجودِ فعلی
        # در اولین Sync فقط به‌عنوان دیده‌شده ثبت می‌شوند تا کانال آرشیو پر نشود.
        for _title, _feed, _site in DEFAULT_NEWS_SOURCES:
            cur.execute(
                "INSERT OR IGNORE INTO news_sources(title, feed_url, site_url, active) VALUES(?,?,?,1)",
                (_title, _feed, _site)
            )

        # پاک‌سازی رکوردهای وابسته برای دیتابیس‌های قدیمی که FK نداشتند
        cur.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_anime_cleanup_after_delete
        AFTER DELETE ON anime
        BEGIN
            DELETE FROM anime_subscriptions WHERE eng_name=OLD.eng_name;
            DELETE FROM download_links WHERE eng_name=OLD.eng_name;
            DELETE FROM anime_posts WHERE eng_name=OLD.eng_name;
            DELETE FROM seasonal_anime WHERE eng_name=OLD.eng_name;
            DELETE FROM anime_added_at WHERE eng_name=OLD.eng_name;
            DELETE FROM anime_download_events WHERE eng_name=OLD.eng_name;
        END
        """)

        conn.commit()
        conn.close()

STATE_TTL_SECONDS = 60 * 60

_user_state_touched = {}

def _state_now():
    return time.monotonic()

def get_state(user_id):
    now = _state_now()
    with state_lock:
        touched = _user_state_touched.get(user_id)
        if touched is not None and now - touched > STATE_TTL_SECONDS:
            user_state.pop(user_id, None)
            _user_state_touched.pop(user_id, None)
            return {}
        if user_id in user_state:
            _user_state_touched[user_id] = now
        return user_state.get(user_id, {}).copy()

def set_state(user_id, state):
    with state_lock:
        user_state[user_id] = state
        _user_state_touched[user_id] = _state_now()

def update_state(user_id, **kwargs):
    with state_lock:
        if user_id not in user_state:
            user_state[user_id] = {}
        user_state[user_id].update(kwargs)
        _user_state_touched[user_id] = _state_now()

def clear_state(user_id):
    with state_lock:
        user_state.pop(user_id, None)
        _user_state_touched.pop(user_id, None)

def set_setting(key: str, value: str):
    with db_write_lock:
        conn = db()
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
        conn.commit()
        conn.close()

def get_setting(key: str, default: str = ""):
    conn = db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row and row["value"] is not None else default

def normalize_channel_id_value(channel_id: str) -> str:
    """شناسه کانال را برای ذخیره‌سازی به فرم معتبر تلگرام تبدیل می‌کند.

    نمونه‌ها:
      1002606294085  -> -1002606294085
      2606294085     -> -1002606294085
      -1002606294085 -> -1002606294085
      @channel_name  -> @channel_name
    """
    value = str(channel_id or "").strip()
    if not value:
        raise ValueError("آیدی کانال خالی است.")

    # لینک عمومی کانال
    if value.startswith(("https://t.me/", "http://t.me/", "t.me/")):
        value = value.split("t.me/", 1)[1].split("?", 1)[0].strip("/")
        if not value:
            raise ValueError("لینک کانال نامعتبر است.")
        return "@" + value.lstrip("@")

    # یوزرنیم عمومی کانال
    if value.startswith("@"):
        return value

    # آیدی عددی کانال
    if value.lstrip("-").isdigit():
        number = value.lstrip("-")
        if value.startswith("-100"):
            return value
        if number.startswith("100"):
            # کاربر - را جا انداخته است.
            return "-" + number
        # آیدی خام داخلی کانال؛ فرمت Bot API را بساز.
        return "-100" + number

    # نام کاربری بدون @
    return "@" + value.lstrip("@")

def add_post_channel(channel_id: str, title: str):
    channel_id = normalize_channel_id_value(channel_id)
    with db_write_lock:
        conn = db()
        try:
            conn.execute(
                "INSERT INTO post_channels(channel_id, title) VALUES(?,?) "
                "ON CONFLICT(channel_id) DO UPDATE SET title=excluded.title",
                (channel_id, title)
            )
            conn.commit()
        finally:
            conn.close()

def remove_post_channel(channel_id: str):
    channel_id = normalize_channel_id_value(channel_id)
    with db_write_lock:
        conn = db()
        try:
            conn.execute("DELETE FROM post_channels WHERE channel_id=?", (channel_id,))
            conn.commit()
        finally:
            conn.close()

def get_post_channels():
    """کانال‌ها را می‌خواند و آیدی‌های قدیمیِ بدون منفی را خودکار اصلاح می‌کند."""
    with db_write_lock:
        conn = db()
        try:
            rows = conn.execute(
                "SELECT id, channel_id, title FROM post_channels ORDER BY id ASC"
            ).fetchall()
            result = []
            for row in rows:
                old_id = str(row["channel_id"] or "").strip()
                try:
                    fixed_id = normalize_channel_id_value(old_id)
                except ValueError:
                    fixed_id = old_id
                if fixed_id and fixed_id != old_id:
                    try:
                        conn.execute(
                            "UPDATE post_channels SET channel_id=? WHERE id=?",
                            (fixed_id, row["id"])
                        )
                    except sqlite3.IntegrityError:
                        # اگر نسخه صحیح از قبل وجود دارد، رکورد خراب قدیمی حذف شود.
                        conn.execute("DELETE FROM post_channels WHERE id=?", (row["id"],))
                        continue
                result.append((fixed_id, row["title"]))
            conn.commit()
            return result
        finally:
            conn.close()

def normalize_eng(name: str) -> str:
    return (name or "").strip().lower()

def _normalize_anime_search_text(value: str) -> str:
    """متن جستجو را مستقل از بزرگی/کوچکی حروف و فاصله‌های اضافی نرمال می‌کند."""
    value = unescape(str(value or ""))
    value = value.translate(str.maketrans({
        "’": "'", "‘": "'", "`": "'", "´": "'",
        "–": "-", "—": "-", "−": "-",
    }))
    return re.sub(r"\s+", " ", value).strip().casefold()

def create_markup_with_back(*buttons):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    for b in buttons:
        markup.add(KeyboardButton(str(b)))
    markup.add(KeyboardButton(BACK_MAIN))
    return markup

def normalize_channel_target(channel_id: str):
    """شناسه ذخیره‌شده را به target قابل استفاده در Telegram Bot API تبدیل می‌کند."""
    value = normalize_channel_id_value(channel_id)
    if value.lstrip("-").isdigit():
        return int(value)
    return value

def validate_post_channel_access(channel_id: str):
    """وجود کانال و مجوز ارسال پست توسط بات را بررسی می‌کند."""
    target = normalize_channel_target(channel_id)
    chat = bot.get_chat(target)
    if getattr(chat, "type", None) != "channel":
        raise ValueError("این شناسه مربوط به کانال نیست.")

    me = bot.get_me()
    member = bot.get_chat_member(target, me.id)
    if member.status not in ("administrator", "creator"):
        raise PermissionError("بات در این کانال ادمین نیست.")

    can_post = getattr(member, "can_post_messages", None)
    if can_post is False:
        raise PermissionError("مجوز Post Messages برای بات فعال نیست.")
    return target, chat

def telegram_error_text(exc: Exception) -> str:
    text = str(exc)
    low = text.lower()
    if "chat not found" in low:
        return "کانال پیدا نشد؛ آیدی اشتباه است یا بات هنوز به کانال اضافه نشده."
    if "not enough rights" in low or "need administrator rights" in low:
        return "بات دسترسی کافی ندارد؛ آن را ادمین کنید و مجوز ارسال پست را بدهید."
    if "bot is not a member" in low:
        return "بات عضو کانال نیست."
    if "message caption is too long" in low:
        return "کپشن بیش از حد مجاز تلگرام است."
    if "wrong file identifier" in low or "file_id" in low:
        return "فایل قابل ارسال نیست؛ رسانه را دوباره برای بات ارسال کنید."
    return text

@bot.message_handler(func=lambda m: m.text == "📡 مدیریت کانال‌های پست")
def post_channel_panel(message):
    if message.from_user.id not in ADMINS:
        return
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("➕ افزودن کانال پست"))
    markup.add(KeyboardButton("❌ حذف کانال پست"))
    markup.add(KeyboardButton(BACK_MAIN))

    channels = get_post_channels()
    if channels:
        txt = "📡 کانال‌های ثبت‌شده:\n" + "\n".join(f"• {title} ({cid})" for cid, title in channels)
    else:
        txt = "📡 هنوز کانالی ثبت نشده."
    bot.send_message(message.chat.id, txt, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "➕ افزودن کانال پست")
def add_post_channel_start(message):
    if message.from_user.id not in ADMINS:
        return
    msg = bot.send_message(
        message.chat.id,
        "📡 آیدی کانال را بفرست؛ با یا بدون علامت منفی پذیرفته می‌شود.\n"
        "مثال: -1001234567890 یا 1001234567890 یا @channel\n\n"
        "برای پیدا کردن آیدی کانال، یه پیام توی کانال بفرست، بعد بات رو به عنوان ادمین کانال اضافه کن "
        "و آیدی که بات قبلاً با «CHANNEL ID:» نشون داد رو استفاده کن.",
        reply_markup=create_markup_with_back()
    )
    bot.register_next_step_handler(msg, add_post_channel_get_id)

def add_post_channel_get_id(message):
    if message.text == BACK_MAIN:
        show_main_menu(message.chat.id, message.from_user.id)
        return
    channel_id = (message.text or "").strip()
    try:
        target, chat = validate_post_channel_access(channel_id)
    except Exception as e:
        msg = bot.send_message(
            message.chat.id,
            f"❌ کانال قابل استفاده نیست:\n{telegram_error_text(e)}\n\n"
            "بات را در کانال ادمین کن، مجوز Post Messages را فعال کن و دوباره آیدی عددی یا @username را بفرست:"
        )
        bot.register_next_step_handler(msg, add_post_channel_get_id)
        return

    normalized_id = str(target)
    update_state(message.from_user.id, pc_id=normalized_id)
    detected_title = getattr(chat, "title", None) or normalized_id
    msg = bot.send_message(
        message.chat.id,
        f"✅ دسترسی ارسال تأیید شد.\nکانال: {detected_title}\n\n📝 یک نام برای شناسایی این کانال بفرست:"
    )
    bot.register_next_step_handler(msg, add_post_channel_get_title)

def add_post_channel_get_title(message):
    if message.text == BACK_MAIN:
        show_main_menu(message.chat.id, message.from_user.id)
        return
    title = (message.text or "").strip()
    channel_id = get_state(message.from_user.id).get("pc_id")
    if not channel_id:
        show_main_menu(message.chat.id, message.from_user.id)
        return
    add_post_channel(channel_id, title)
    bot.send_message(message.chat.id, f"✅ کانال «{title}» ({channel_id}) اضافه شد.")
    post_channel_panel(message)

@bot.message_handler(func=lambda m: m.text == "❌ حذف کانال پست")
def remove_post_channel_start(message):
    if message.from_user.id not in ADMINS:
        return
    channels = get_post_channels()
    if not channels:
        bot.send_message(message.chat.id, "❌ هیچ کانالی ثبت نشده.")
        return
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    for cid, title in channels:
        markup.add(KeyboardButton(f"{title} ({cid})"))
    markup.add(KeyboardButton(BACK_MAIN))
    set_state(message.from_user.id, {
        "mode": "remove_pc",
        "pc_map": {f"{title} ({cid})": cid for cid, title in channels}
    })
    msg = bot.send_message(message.chat.id, "کدام کانال حذف شود؟", reply_markup=markup)
    bot.register_next_step_handler(msg, remove_post_channel_do)

def remove_post_channel_do(message):
    if message.text == BACK_MAIN:
        show_main_menu(message.chat.id, message.from_user.id)
        return
    mp = get_state(message.from_user.id).get("pc_map", {})
    cid = mp.get(message.text)
    if not cid:
        show_main_menu(message.chat.id, message.from_user.id)
        return
    remove_post_channel(cid)
    bot.send_message(message.chat.id, "✅ کانال حذف شد.")
    post_channel_panel(message)

from html import escape as _html_escape

class _NewsMetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.feed_links = []
        self.video_sources = []
        self.embed_video_urls = []
        self.link_video_urls = []
        self.image_candidates = []

    @staticmethod
    def _best_srcset(value: str) -> str:
        best = ""
        best_score = -1
        for chunk in (value or "").split(","):
            bits = chunk.strip().split()
            if not bits:
                continue
            url = bits[0]
            score = 1
            if len(bits) > 1:
                token = bits[-1].lower()
                try:
                    if token.endswith("w"):
                        score = int(float(token[:-1]))
                    elif token.endswith("x"):
                        score = int(float(token[:-1]) * 1000)
                except Exception:
                    pass
            if score > best_score:
                best_score = score
                best = url
        return best

    @staticmethod
    def _dim(value) -> int:
        try:
            return int(re.sub(r"[^0-9]", "", str(value or "")) or 0)
        except Exception:
            return 0

    def handle_starttag(self, tag, attrs):
        attrs = {str(k).lower(): (v or "") for k, v in attrs}
        tag = (tag or "").lower()
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower().strip()
            value = attrs.get("content", "").strip()
            if key and value and key not in self.meta:
                self.meta[key] = value
            if key in ("og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src") and value:
                self.image_candidates.append({"url": value, "origin": "meta", "alt": "", "width": 0, "height": 0})
        elif tag == "link":
            rel = attrs.get("rel", "").lower()
            typ = attrs.get("type", "").lower()
            href = attrs.get("href", "").strip()
            if href and "alternate" in rel and ("rss" in typ or "atom" in typ or "xml" in typ):
                self.feed_links.append(href)
        elif tag in ("video", "source"):
            src = attrs.get("src", "").strip()
            typ = attrs.get("type", "").lower()
            if src and (
                tag == "video"
                or "video" in typ
                or src.lower().split("?", 1)[0].endswith((".mp4", ".webm", ".mov", ".m4v"))
            ):
                self.video_sources.append(src)
            if tag == "source" and (typ.startswith("image/") or attrs.get("srcset")):
                img = self._best_srcset(attrs.get("srcset", "")) or src
                if img:
                    self.image_candidates.append({"url": img, "origin": "article", "alt": "", "width": 0, "height": 0})
        elif tag == "img":
            src = (
                self._best_srcset(attrs.get("srcset", ""))
                or self._best_srcset(attrs.get("data-srcset", ""))
                or attrs.get("data-original", "").strip()
                or attrs.get("data-lazy-src", "").strip()
                or attrs.get("data-src", "").strip()
                or attrs.get("src", "").strip()
            )
            if src:
                self.image_candidates.append({
                    "url": src,
                    "origin": "article",
                    "alt": (attrs.get("alt", "") + " " + attrs.get("title", "")).strip(),
                    "width": self._dim(attrs.get("width")),
                    "height": self._dim(attrs.get("height")),
                })
        elif tag in ("a", "blockquote"):
            # بعضی رسانه‌ها تریلر را به‌صورت لینک/Embed شبکه اجتماعی می‌گذارند، نه iframe ساده.
            href = (attrs.get("href", "") or attrs.get("cite", "") or attrs.get("data-url", "")).strip()
            if href:
                low = href.lower()
                if any(host in low for host in (
                    "youtube.com/", "youtu.be/", "youtube-nocookie.com/",
                    "vimeo.com/", "dailymotion.com/",
                    "twitter.com/", "x.com/",
                    "bilibili.com/video/", "b23.tv/",
                    "nicovideo.jp/watch/", "nico.ms/", "streamable.com/"
                )):
                    self.link_video_urls.append(href)
        elif tag == "iframe":
            src = attrs.get("src", "").strip() or attrs.get("data-src", "").strip()
            if src:
                low = src.lower()
                if any(host in low for host in (
                    "youtube.com/embed/", "youtube-nocookie.com/embed/", "youtu.be/",
                    "player.vimeo.com/video/", "vimeo.com/", "dailymotion.com/embed/",
                    "twitter.com/", "x.com/", "bilibili.com/", "player.twitch.tv/"
                )):
                    self.embed_video_urls.append(src)

class _NewsBodyImageParser(HTMLParser):
    """عکس‌هایی که داخل بدنه‌ی خود مقاله هستن (نه سایدبار/مطالب مرتبط)، به ترتیب صفحه."""
    VOID = {"img", "br", "hr", "meta", "link", "input", "source", "wbr", "area", "base", "col", "embed", "param", "track"}
    BODY_RE = re.compile(r"(?i)article[-_]?(?:body|content|text)|entry[-_]content|post[-_](?:content|body)|"
                         r"content[-_]body|story[-_]body|news[-_](?:body|content)|richtext|rich-text|\bmeat\b|\bprose\b")
    SKIP_RE = re.compile(r"(?i)related|sidebar|recommend|share|social|author|comment|footer|\bnav|advert|\bads?\b|"
                         r"promo|newsletter|popular|trending|more-stories|read-more|breadcrumb|widget")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []          # (tag, body?, skip?)
        self.images = []
        self.stopped = False

    def _state(self):
        body = any(b for _t, b, _s in self.stack)
        skip = any(k for _t, _b, k in self.stack)
        return body, skip

    def handle_starttag(self, tag, attrs):
        tag = (tag or "").lower()
        a = {str(k).lower(): (v or "") for k, v in attrs}
        marker = f"{a.get('class', '')} {a.get('id', '')} {a.get('itemprop', '')}"
        if tag == "img":
            body, skip = self._state()
            if body and not skip and not self.stopped:
                src = (_NewsMetaParser._best_srcset(a.get("srcset", "")) or _NewsMetaParser._best_srcset(a.get("data-srcset", ""))
                       or a.get("data-original", "") or a.get("data-lazy-src", "") or a.get("data-src", "") or a.get("src", ""))
                if src.strip():
                    self.images.append({"url": src.strip(), "alt": a.get("alt", ""),
                                        "width": _NewsMetaParser._dim(a.get("width")),
                                        "height": _NewsMetaParser._dim(a.get("height"))})
            return
        if tag in self.VOID:
            return
        is_body = tag == "article" or bool(self.BODY_RE.search(marker)) or "articlebody" in marker.lower()
        is_skip = tag in ("aside", "nav", "footer", "form") or bool(self.SKIP_RE.search(marker))
        self.stack.append((tag, is_body, is_skip))

    def handle_endtag(self, tag):
        tag = (tag or "").lower()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        # بعد از تیتر «مطالب مرتبط» داخل خود مقاله دیگه عکسی برداشته نمیشه
        body, _skip = self._state()
        if body and re.fullmatch(r"(?i)\s*(?:related(?: news| posts| articles)?|read more|you may also like|more stories|recommended)\s*:?\s*",
                                 data or "-"):
            self.stopped = True


class _NewsArticleTextParser(HTMLParser):
    """متن اصلی مقاله را بدون بخش‌های حاشیه‌ای/پیشنهادهای بعدی جمع می‌کند.

    هدف این Parser این است که اطلاعاتی مثل «Upcoming Projects» یا لینک‌های مرتبط
    با فرنچایز، وارد خلاصه خبر جاری نشوند و باعث تشخیص فصل/تاریخ اشتباه نشوند.
    """
    STOP_HEADINGS = {
        "upcoming projects", "related news", "related posts", "read more", "also read",
        "more stories", "more news", "recommended", "recommendations", "source", "sources",
        "tags", "you may also like", "latest news", "previous article", "next article",
    }

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._in_block = 0
        self._buf = []
        self._block_tag = ""
        self._stop_capture = False
        self.paragraphs = []

    def handle_starttag(self, tag, attrs):
        tag = (tag or "").lower()
        if tag in ("script", "style", "noscript", "svg", "nav", "header", "footer", "form", "aside"):
            self._skip_depth += 1
            return
        if self._skip_depth or self._stop_capture:
            return
        if tag in ("p", "h1", "h2", "h3", "li", "blockquote"):
            self._in_block += 1
            if self._in_block == 1:
                self._buf = []
                self._block_tag = tag

    def handle_endtag(self, tag):
        tag = (tag or "").lower()
        if tag in ("script", "style", "noscript", "svg", "nav", "header", "footer", "form", "aside"):
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth or self._stop_capture:
            return
        if tag in ("p", "h1", "h2", "h3", "li", "blockquote") and self._in_block:
            self._in_block -= 1
            if self._in_block == 0:
                value = re.sub(r"\s+", " ", " ".join(self._buf)).strip()
                low = value.lower().strip(" :|-–—")

                # Headingهای بخش‌های حاشیه‌ای را مرز پایان متن خبر در نظر بگیر.
                if self._block_tag in ("h1", "h2", "h3"):
                    if low in self.STOP_HEADINGS or any(low.startswith(x + " ") for x in self.STOP_HEADINGS):
                        self._stop_capture = True
                    self._buf = []
                    self._block_tag = ""
                    return

                junk = (
                    "cookie", "privacy policy", "subscribe", "newsletter", "advertisement",
                    "sign up", "written by", "image:", "© ", "all rights reserved",
                )
                if 25 <= len(value) <= 1600 and not any(k in low for k in junk):
                    self.paragraphs.append(value)
                self._buf = []
                self._block_tag = ""

    def handle_data(self, data):
        if not self._skip_depth and not self._stop_capture and self._in_block and data:
            value = unescape(str(data)).strip()
            if value:
                self._buf.append(value)

def _news_strip_html(value: str) -> str:
    value = unescape(value or "")
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value

def _news_safe_url(url: str) -> bool:
    try:
        p = urllib.parse.urlparse((url or "").strip())
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        host = p.hostname.lower()
        if host in ("localhost", "localhost.localdomain"):
            return False
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            pass
        return True
    except Exception:
        return False

def _news_fetch(url: str, max_bytes: int = 3_000_000):
    if not _news_safe_url(url):
        raise ValueError("آدرس منبع معتبر نیست.")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": NEWS_USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.5",
        },
    )
    with urllib.request.urlopen(req, timeout=NEWS_HTTP_TIMEOUT) as resp:
        data = resp.read(max_bytes + 1)
        if len(data) > max_bytes:
            data = data[:max_bytes]
        content_type = resp.headers.get("Content-Type", "")
        final_url = resp.geturl()
    return data, content_type, final_url

def _news_is_feed_bytes(data: bytes) -> bool:
    head = (data or b"")[:1500].lstrip().lower()
    return b"<rss" in head or b"<feed" in head or b"<rdf:rdf" in head

def _x_leaker_handle_from_feed(feed_url: str) -> str:
    value = (feed_url or "").strip()
    if not value.lower().startswith(X_LEAKER_SPECIAL_PREFIX):
        return ""
    handle = value[len(X_LEAKER_SPECIAL_PREFIX):].strip().lstrip("@")
    return handle if re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle) else ""

def _x_leaker_special_feed(handle: str) -> str:
    handle = (handle or "").strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
        raise ValueError("هندل X معتبر نیست.")
    return f"{X_LEAKER_SPECIAL_PREFIX}{handle}"

def _x_leaker_rate_wait():
    """درخواست‌های Syndication را آرام و سریالی می‌فرستد تا 429 کمتر شود."""
    global _x_leaker_last_fetch_monotonic
    with _x_leaker_rate_lock:
        now = time.monotonic()
        wait_for = X_LEAKER_REQUEST_GAP_SECONDS - (now - _x_leaker_last_fetch_monotonic)
        if _x_leaker_last_fetch_monotonic and wait_for > 0:
            time.sleep(wait_for)
        _x_leaker_last_fetch_monotonic = time.monotonic()

def _x_clean_post_text(value: str) -> str:
    value = unescape(str(value or ""))
    value = re.sub(r"https?://t\.co/[A-Za-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def _x_is_official_confirmation_post(text: str) -> bool:
    low = (text or "").casefold()
    markers = (
        "official announcement", "official confirmation", "officially announced",
        "officially confirmed", "✅ official", "confirmed by official",
    )
    return any(m in low for m in markers)

def _x_leaker_entries_from_pageprops(page_props: dict, requested_handle: str) -> list:
    timeline = (page_props or {}).get("timeline") or {}
    raw_entries = timeline.get("entries") or []
    out = []
    requested_cf = (requested_handle or "").casefold()

    for entry in raw_entries:
        if not isinstance(entry, dict) or str(entry.get("type") or "").lower() != "tweet":
            continue
        tweet = ((entry.get("content") or {}).get("tweet") or {})
        if not isinstance(tweet, dict):
            continue
        user = tweet.get("user") or {}
        screen_name = str(user.get("screen_name") or requested_handle or "").strip()
        if requested_cf and screen_name and screen_name.casefold() != requested_cf:
            continue

        raw_text = str(tweet.get("full_text") or tweet.get("text") or "").strip()
        if not raw_text or raw_text.startswith("RT @"):
            continue
        if tweet.get("in_reply_to_name") or tweet.get("in_reply_to_status_id_str") or raw_text.lstrip().startswith("@"):
            continue
        clean_text = _x_clean_post_text(raw_text)
        if len(clean_text) < 12 or _x_is_official_confirmation_post(clean_text):
            continue

        tid = str(tweet.get("id_str") or tweet.get("id") or "").strip()
        if not tid.isdigit():
            continue
        permalink = str(tweet.get("permalink") or "").strip()
        if permalink.startswith("/"):
            post_url = "https://x.com" + permalink
        elif _news_safe_url(permalink):
            post_url = permalink.replace("https://twitter.com/", "https://x.com/")
        else:
            post_url = f"https://x.com/{screen_name or requested_handle}/status/{tid}"

        image_url = ""
        for media in (tweet.get("mediaDetails") or []):
            if isinstance(media, dict):
                candidate = str(media.get("media_url_https") or "").strip()
                if candidate and _news_safe_url(candidate):
                    image_url = candidate
                    if str(media.get("type") or "").lower() == "photo":
                        break
        if not image_url:
            for photo in (tweet.get("photos") or []):
                if isinstance(photo, dict):
                    candidate = str(photo.get("url") or photo.get("expandedUrl") or "").strip()
                    if candidate and _news_safe_url(candidate):
                        image_url = candidate
                        break

        published = _news_parse_date(str(tweet.get("created_at") or ""))
        title_piece = clean_text[:180].strip()
        if len(clean_text) > 180:
            title_piece = title_piece[:177].rstrip() + "..."
        title = f"@{screen_name or requested_handle}: {title_piece}"
        out.append({
            "guid": f"x:{(screen_name or requested_handle).casefold()}:{tid}",
            "title": title,
            "url": post_url,
            "published_at": published,
            "summary": clean_text,
            "article_text": clean_text,
            "image_url": image_url,
            "video_url": "",
            "trailer_url": "",
            "news_type": "leak",
        })
    return out[:30]

def _x_leaker_collect_syndication(handle: str) -> list:
    global _x_syndication_blocked_until, _x_syndication_cooldown
    _x_leaker_rate_wait()
    url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{urllib.parse.quote(handle)}"
    headers = {
        "User-Agent": X_SYNDICATION_UA,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    if X_AUTH_TOKEN:
        headers["Cookie"] = f"auth_token={X_AUTH_TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=NEWS_HTTP_TIMEOUT) as resp:
            raw = resp.read(5_000_000).decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        if getattr(e, "code", 0) == 429:
            _x_syndication_cooldown = min(X_SYNDICATION_COOLDOWN_MAX,
                                          max(X_SYNDICATION_COOLDOWN_MIN, _x_syndication_cooldown * 2))
            _x_syndication_blocked_until = time.time() + _x_syndication_cooldown
            logger.warning("X Syndication 429; pausing it for %d min", _x_syndication_cooldown // 60)
        hint = "" if X_AUTH_TOKEN else " (X_AUTH_TOKEN تنظیم نشده)"
        raise RuntimeError(f"X HTTP {getattr(e, 'code', '?')}{hint}") from e
    except Exception as e:
        raise RuntimeError(f"X: {_social_net_error(e)}") from e
    _x_syndication_cooldown = 0.0

    m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', raw, flags=re.I | re.S)
    if not m:
        raise RuntimeError("X Syndication داده __NEXT_DATA__ برنگرداند.")
    try:
        data = json.loads(unescape(m.group(1)).strip())
        page_props = (((data or {}).get("props") or {}).get("pageProps") or {})
    except Exception as e:
        raise RuntimeError(f"JSON تایم‌لاین X قابل خواندن نبود: {e}") from e
    entries = _x_leaker_entries_from_pageprops(page_props, handle)
    if not entries:
        raise RuntimeError("از تایم‌لاین عمومی X پست قابل استفاده‌ای دریافت نشد.")
    return entries

def _x_leaker_collect_bridge(handle: str, template: str) -> list:
    """پست‌های X از فید RSS یک bridge (Nitter/RSSHub). guid هم‌شکل Syndication میشه تا تکراری نشه."""
    feed_url = template.replace("{handle}", urllib.parse.quote(handle))
    out = []
    for item in _news_parse_feed(feed_url):
        link = str(item.get("url") or "")
        m = re.search(r"/status(?:es)?/(\d+)", link)
        if not m:
            continue
        tid = m.group(1)
        raw_title = re.sub(r"\s+", " ", str(item.get("title") or "")).strip()
        if raw_title.startswith(("RT by", "R to @", "RT @")):
            continue
        text = _x_clean_post_text(item.get("summary") or raw_title)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 12 or _x_is_official_confirmation_post(text):
            continue
        piece = text[:177].rstrip() + "..." if len(text) > 180 else text
        out.append({
            "guid": f"x:{handle.casefold()}:{tid}",
            "title": f"@{handle}: {piece}",
            "url": f"https://x.com/{handle}/status/{tid}",
            "published_at": item.get("published_at") or "",
            "summary": text,
            "article_text": text,
            "image_url": item.get("image_url") or "",
            "video_url": "",
            "trailer_url": "",
            "news_type": "leak",
        })
    if not out:
        raise RuntimeError("پستی دریافت نشد")
    return out[:30]

# =========================
# X با API داخلی خود سایت (همون که x.com توی مرورگر استفاده می‌کنه) + کوکی لاگین
# =========================
X_CT0 = _cookie_env("X_CT0")

# توکن عمومی اپ وب X (داخل جاوااسکریپت خود سایت؛ مال هیچ اکانتی نیست)
X_WEB_BEARER = ("AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
                "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA")

# اگه پیدا کردن خودکار از کد سایت ممکن نشد، این‌ها امتحان میشن
_X_GQL_FALLBACK_IDS = {
    "UserByScreenName": ["xmU6X_CKVnQ5lSrCbAmJsg", "G3KGOASz96M-Qu0nwmGXNg"],
    "UserTweets": ["E3opETHurmVJflFsUBVuUQ", "V7H0Ap3_Hh2FyS75OCDO3Q"],
}
_x_gql_ops = {}          # operationName -> {"id": ..., "features": [...]}
_x_gql_ops_at = 0.0
_x_gql_lock = threading.Lock()
_x_user_ids = {}


def _x_gql_ready() -> bool:
    return bool(X_AUTH_TOKEN and X_CT0)


def _x_gql_headers() -> dict:
    return {
        "User-Agent": X_SYNDICATION_UA,
        "Authorization": f"Bearer {X_WEB_BEARER}",
        "Cookie": f"auth_token={X_AUTH_TOKEN}; ct0={X_CT0}",
        "x-csrf-token": X_CT0,
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "en",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://x.com/",
    }


def _x_discover_ops(force: bool = False) -> dict:
    """queryId و featureهای هر عملیات رو از فایل main.js خود x.com درمیاره (هر ۱۲ ساعت یا بعد از خطا)."""
    global _x_gql_ops, _x_gql_ops_at
    with _x_gql_lock:
        if _x_gql_ops and not force and time.time() - _x_gql_ops_at < 12 * 3600:
            return _x_gql_ops
        try:
            req = urllib.request.Request("https://x.com/", headers={"User-Agent": X_SYNDICATION_UA,
                                                                  "Cookie": f"auth_token={X_AUTH_TOKEN}; ct0={X_CT0}"})
            with urllib.request.urlopen(req, timeout=NEWS_HTTP_TIMEOUT) as resp:
                html_text = resp.read(3_000_000).decode("utf-8", errors="ignore")
            scripts = re.findall(r"https://abs\.twimg\.com/responsive-web/client-web(?:-legacy)?/main\.[0-9a-zA-Z]+\.js", html_text)
            found = {}
            for js_url in dict.fromkeys(scripts):
                req = urllib.request.Request(js_url, headers={"User-Agent": X_SYNDICATION_UA})
                with urllib.request.urlopen(req, timeout=NEWS_HTTP_TIMEOUT) as resp:
                    js = resp.read(20_000_000).decode("utf-8", errors="ignore")
                for m in re.finditer(r'queryId:"([^"]+)",operationName:"(UserByScreenName|UserTweets)"'
                                     r'(.{0,4000}?)(?=queryId:|$)', js, flags=re.S):
                    feats = re.search(r"featureSwitches:\[([^\]]*)\]", m.group(3))
                    found[m.group(2)] = {
                        "id": m.group(1),
                        "features": re.findall(r'"([A-Za-z0-9_]+)"', feats.group(1)) if feats else [],
                    }
            if found:
                _x_gql_ops = found
                _x_gql_ops_at = time.time()
                logger.info("X API operations discovered: %s", {k: v["id"] for k, v in found.items()})
        except Exception as exc:
            logger.warning("X API discovery failed: %s", _social_net_error(exc))
        return _x_gql_ops


def _x_gql_call(operation: str, variables: dict) -> dict:
    ops = _x_discover_ops()
    candidates = []
    if operation in ops:
        candidates.append((ops[operation]["id"], ops[operation]["features"]))
    for qid in _X_GQL_FALLBACK_IDS.get(operation, []):
        if all(qid != c[0] for c in candidates):
            candidates.append((qid, []))
    last = ""
    for qid, feature_names in candidates:
        features = {name: True for name in feature_names}
        for _attempt in range(3):
            query = urllib.parse.urlencode({
                "variables": json.dumps(variables, separators=(",", ":")),
                "features": json.dumps(features, separators=(",", ":")),
            })
            req = urllib.request.Request(f"https://x.com/i/api/graphql/{qid}/{operation}?{query}", headers=_x_gql_headers())
            try:
                with urllib.request.urlopen(req, timeout=NEWS_HTTP_TIMEOUT) as resp:
                    return json.loads(resp.read(10_000_000).decode("utf-8", errors="ignore"))
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                missing = re.search(r"features cannot be null:\s*([A-Za-z0-9_,\s]+)", body)
                if e.code == 400 and missing:
                    # X فیچر جدیدی می‌خواد → اضافه کن و دوباره
                    for name in re.findall(r"[A-Za-z0-9_]+", missing.group(1)):
                        features[name] = True
                    continue
                if e.code in (401, 403):
                    raise RuntimeError(f"X API HTTP {e.code}: کوکی‌های X_AUTH_TOKEN / X_CT0 نامعتبر یا منقضی شدن") from e
                if e.code == 429:
                    raise RuntimeError("X API HTTP 429: محدودیت درخواست اکانت؛ چند دقیقه بعد دوباره امتحان میشه") from e
                last = f"X API HTTP {e.code}"
                break  # queryId قدیمی/نامعتبر → بعدی
            except Exception as e:
                raise RuntimeError(f"X API: {_social_net_error(e)}") from e
    _x_discover_ops(force=True)  # دفعه بعد با شناسه‌های تازه
    raise RuntimeError(last or "X API: عملیات پیدا نشد")


def _x_gql_tweet_objects(node, out: list):
    """همه‌ی آبجکت‌های توییت رو از جواب تو در توی API پیدا می‌کنه (مقاوم به تغییر ساختار)."""
    if isinstance(node, dict):
        if node.get("__typename") == "TweetWithVisibilityResults" and isinstance(node.get("tweet"), dict):
            _x_gql_tweet_objects(node["tweet"], out)
            return
        if isinstance(node.get("legacy"), dict) and "full_text" in node["legacy"] and node.get("rest_id"):
            out.append(node)
        for key, value in node.items():
            if key in ("quoted_status_result", "retweeted_status_result"):
                continue  # توییت دیگران داخل ریتوییت/کوت
            _x_gql_tweet_objects(value, out)
    elif isinstance(node, list):
        for value in node:
            _x_gql_tweet_objects(value, out)


def _x_gql_tweet_image(tw: dict) -> str:
    """عکس توییت از همه‌ی جاهایی که X می‌ذاره: extended_entities / entities / پست بلند (note) / کارت لینک."""
    legacy = tw.get("legacy") or {}
    groups = [
        (legacy.get("extended_entities") or {}).get("media"),
        (legacy.get("entities") or {}).get("media"),
    ]
    note = (((tw.get("note_tweet") or {}).get("note_tweet_results") or {}).get("result") or {})
    groups.append((note.get("media") or {}).get("inline_media"))
    groups.append((note.get("entity_set") or {}).get("media"))
    for group in groups:
        for media in group or []:
            if not isinstance(media, dict):
                continue
            candidate = str(media.get("media_url_https") or media.get("media_url") or "")
            if candidate and _news_safe_url(candidate):
                return candidate
    # کارت لینک (مثلاً لینک سایت خبر با عکس بزرگ)
    card = ((tw.get("card") or {}).get("legacy") or {})
    for bv in card.get("binding_values") or []:
        if isinstance(bv, dict) and bv.get("key") in ("photo_image_full_size_large", "thumbnail_image_large",
                                                      "summary_photo_image_large", "thumbnail_image_original"):
            url = str(((bv.get("value") or {}).get("image_value") or {}).get("url") or "")
            if url and _news_safe_url(url):
                return url
    return ""


def _x_leaker_collect_gql(handle: str) -> list:
    user_id = _x_user_ids.get(handle.casefold())
    if not user_id:
        data = _x_gql_call("UserByScreenName", {"screen_name": handle, "withSafetyModeUserFields": True})
        result = (((data.get("data") or {}).get("user") or {}).get("result") or {})
        user_id = result.get("rest_id")
        if not user_id:
            raise RuntimeError("X API: اکانت پیدا نشد (هندل درسته؟)")
        _x_user_ids[handle.casefold()] = user_id
    data = _x_gql_call("UserTweets", {
        "userId": user_id, "count": 20, "includePromotedContent": False,
        "withQuickPromoteEligibilityTweetFields": False, "withVoice": True, "withV2Timeline": True,
    })
    tweets = []
    _x_gql_tweet_objects(data, tweets)
    out, seen = [], set()
    for tw in tweets:
        legacy = tw.get("legacy") or {}
        tid = str(tw.get("rest_id") or legacy.get("id_str") or "")
        if not tid.isdigit() or tid in seen:
            continue
        seen.add(tid)
        if str(legacy.get("user_id_str") or user_id) != str(user_id):
            continue
        if legacy.get("retweeted_status_result") or legacy.get("in_reply_to_status_id_str"):
            continue
        note = ((((tw.get("note_tweet") or {}).get("note_tweet_results") or {}).get("result") or {}).get("text"))
        raw_text = str(note or legacy.get("full_text") or "")
        if raw_text.startswith("RT @") or raw_text.lstrip().startswith("@"):
            continue
        text = _x_clean_post_text(raw_text)
        if len(text) < 12 or _x_is_official_confirmation_post(text):
            continue
        image_url = _x_gql_tweet_image(tw)
        piece = text[:177].rstrip() + "..." if len(text) > 180 else text
        out.append({
            "guid": f"x:{handle.casefold()}:{tid}",
            "title": f"@{handle}: {piece}",
            "url": f"https://x.com/{handle}/status/{tid}",
            "published_at": _news_parse_date(str(legacy.get("created_at") or "")),
            "summary": text,
            "article_text": text,
            "image_url": image_url,
            "video_url": "",
            "trailer_url": "",
            "news_type": "leak",
        })
    if not out and not tweets:
        raise RuntimeError("X API: توییتی برنگشت")
    return out[:30]


def _x_leaker_collect(handle: str) -> list:
    """اول API داخلی X با کوکی لاگین (مطمئن‌ترین)، بعد Syndication، بعد bridgeهای RSS."""
    handle = (handle or "").strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
        raise ValueError("هندل X معتبر نیست.")
    errors = []
    if _x_gql_ready():
        _x_leaker_rate_wait()
        try:
            return _x_leaker_collect_gql(handle)
        except Exception as e:
            errors.append(str(e))
    elif X_AUTH_TOKEN:
        errors.append("X_CT0 تنظیم نشده (برای روش مطمئن هر دو کوکی auth_token و ct0 لازمه)")
    if time.time() >= _x_syndication_blocked_until:
        try:
            return _x_leaker_collect_syndication(handle)
        except Exception as e:
            errors.append(str(e))
    else:
        mins = int((_x_syndication_blocked_until - time.time()) // 60) + 1
        errors.append(f"X به‌خاطر محدودیت 429 تا {mins} دقیقه دیگه امتحان نمیشه"
                      + ("" if X_AUTH_TOKEN else " (با X_AUTH_TOKEN این محدودیت کمتر میشه)"))
    for template in X_RSS_BRIDGES:
        try:
            return _x_leaker_collect_bridge(handle, template)
        except Exception as e:
            host = urllib.parse.urlparse(template).hostname or template
            errors.append(f"{host}: {_social_net_error(e)}")
    raise RuntimeError(" | ".join(errors)[:500])

INSTAGRAM_SPECIAL_PREFIX = "special://instagram/"

# جایگزین وقتی اینستاگرام درخواست بدون لاگین رو رد می‌کنه: فید RSS یک bridge. {username} جایگزین میشه.
# مثال RSSHub شخصی: https://rsshub.example.com/picuki/profile/{username}
INSTAGRAM_RSS_BRIDGES = [
    b.strip() for b in os.environ.get("INSTAGRAM_RSS_BRIDGES", "").split(",")
    if b.strip() and "{username}" in b
]

INSTAGRAM_REQUEST_GAP_SECONDS = 20.0
_instagram_rate_lock = threading.Lock()
_instagram_last_fetch = 0.0
_instagram_blocked_until = 0.0

def _instagram_username_from_feed(feed_url: str) -> str:
    value = (feed_url or "").strip()
    if not value.lower().startswith(INSTAGRAM_SPECIAL_PREFIX):
        return ""
    user = value[len(INSTAGRAM_SPECIAL_PREFIX):].strip().lstrip("@")
    return user if re.fullmatch(r"[A-Za-z0-9._]{1,30}", user) else ""

def _instagram_special_feed(username: str) -> str:
    username = (username or "").strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", username):
        raise ValueError("یوزرنیم اینستاگرام معتبر نیست.")
    return f"{INSTAGRAM_SPECIAL_PREFIX}{username}"

def _instagram_post_item(username: str, shortcode: str, text: str, image_url: str, published: str) -> dict | None:
    text = re.sub(r"\s+", " ", unescape(text or "")).strip()
    # هشتگ‌های انتهای کپشن فقط نویزن
    text = re.sub(r"(?:\s*#[\w\u0600-\u06FF]+)+\s*$", "", text).strip()
    if len(text) < 12:
        return None
    piece = text[:177].rstrip() + "..." if len(text) > 180 else text
    return {
        "guid": f"ig:{username.casefold()}:{shortcode}",
        "title": f"@{username}: {piece}",
        "url": f"https://www.instagram.com/p/{shortcode}/",
        "published_at": published,
        "summary": text,
        "article_text": text,
        "image_url": image_url if _news_safe_url(image_url) else "",
        "video_url": "",
        "trailer_url": "",
        "news_type": "social",
    }

def _instagram_collect_web(username: str) -> list:
    """۱۲ پست آخر پروفایل عمومی از API وب اینستاگرام (بدون لاگین)."""
    global _instagram_last_fetch, _instagram_blocked_until
    with _instagram_rate_lock:
        wait = INSTAGRAM_REQUEST_GAP_SECONDS - (time.monotonic() - _instagram_last_fetch)
        if _instagram_last_fetch and wait > 0:
            time.sleep(wait)
        _instagram_last_fetch = time.monotonic()
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={urllib.parse.quote(username)}"
    req = urllib.request.Request(url, headers={
        "User-Agent": X_SYNDICATION_UA,
        "x-ig-app-id": "936619743392459",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://www.instagram.com/{username}/",
        **({"Cookie": f"sessionid={INSTAGRAM_SESSIONID}"} if INSTAGRAM_SESSIONID else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=NEWS_HTTP_TIMEOUT) as resp:
            payload = json.loads(resp.read(8_000_000).decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 429):
            _instagram_blocked_until = time.time() + 30 * 60
        hint = "" if INSTAGRAM_SESSIONID else " — بدون لاگین رد شد؛ INSTAGRAM_SESSIONID رو توی .env بذار"
        raise RuntimeError(f"Instagram HTTP {e.code}{hint}") from e
    except Exception as e:
        raise RuntimeError(f"Instagram: {_social_net_error(e)}") from e

    user = ((payload or {}).get("data") or {}).get("user") or {}
    if not user:
        raise RuntimeError("پروفایل پیدا نشد یا خصوصیه.")
    if user.get("is_private"):
        raise RuntimeError("این پیج خصوصیه.")
    edges = ((user.get("edge_owner_to_timeline_media") or {}).get("edges")) or []
    out = []
    for edge in edges:
        node = (edge or {}).get("node") or {}
        shortcode = str(node.get("shortcode") or "").strip()
        if not shortcode:
            continue
        cap_edges = ((node.get("edge_media_to_caption") or {}).get("edges")) or []
        text = ((cap_edges[0] or {}).get("node") or {}).get("text", "") if cap_edges else ""
        ts = int(node.get("taken_at_timestamp") or 0)
        published = datetime.utcfromtimestamp(ts).strftime("%a, %d %b %Y %H:%M:%S +0000") if ts else ""
        item = _instagram_post_item(username, shortcode, text, str(node.get("display_url") or ""), published)
        if item:
            out.append(item)
    if not out:
        raise RuntimeError("پست قابل استفاده‌ای توی پیج نبود.")
    return out

def _instagram_collect_bridge(username: str, template: str) -> list:
    out = []
    for item in _news_parse_feed(template.replace("{username}", urllib.parse.quote(username))):
        m = re.search(r"/(?:p|reel|post)/([A-Za-z0-9_-]{5,})", str(item.get("url") or ""))
        if not m:
            continue
        post = _instagram_post_item(username, m.group(1), item.get("summary") or item.get("title") or "",
                                    item.get("image_url") or "", item.get("published_at") or "")
        if post:
            out.append(post)
    if not out:
        raise RuntimeError("پستی دریافت نشد")
    return out

def _instagram_collect(username: str) -> list:
    username = (username or "").strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", username):
        raise ValueError("یوزرنیم اینستاگرام معتبر نیست.")
    errors = []
    if time.time() >= _instagram_blocked_until:
        try:
            return _instagram_collect_web(username)
        except Exception as e:
            errors.append(str(e))
    else:
        errors.append("اینستاگرام موقتاً درخواست‌ها رو رد می‌کنه"
                      + ("" if INSTAGRAM_SESSIONID else "؛ INSTAGRAM_SESSIONID رو توی .env بذار"))
    for template in INSTAGRAM_RSS_BRIDGES:
        try:
            return _instagram_collect_bridge(username, template)
        except Exception as e:
            errors.append(f"{urllib.parse.urlparse(template).hostname or template}: {_social_net_error(e)}")
    raise RuntimeError(" | ".join(errors)[:500])

def _social_handle_label(feed_url: str) -> str:
    """برچسب کوتاه برای منابع شبکه اجتماعی، یا رشته خالی."""
    x = _x_leaker_handle_from_feed(feed_url)
    if x:
        return f"X: @{x}"
    ig = _instagram_username_from_feed(feed_url)
    if ig:
        return f"Instagram: @{ig}"
    return ""

def _news_discover_feed(site_or_feed_url: str) -> tuple[str, str]:
    """URL سایت یا RSS را می‌گیرد و (feed_url, site_url) برمی‌گرداند.

    AniTrendz یک استثناست: Chartهای هفتگی آن مستقیماً از صفحات Chart خوانده می‌شوند.
    """
    raw_input = (site_or_feed_url or "").strip()
    m_ig = re.fullmatch(r"(?i)(?:ig|insta|instagram)\s*[:@]\s*@?([A-Za-z0-9._]{1,30})", raw_input)
    if m_ig:
        return _instagram_special_feed(m_ig.group(1)), f"https://www.instagram.com/{m_ig.group(1)}/"
    if raw_input.startswith("@") and re.fullmatch(r"@[A-Za-z0-9_]{1,15}", raw_input):
        handle = raw_input[1:]
        return _x_leaker_special_feed(handle), f"https://x.com/{handle}"

    url = raw_input
    if not url.startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")
    if not _news_safe_url(url):
        raise ValueError("آدرس سایت/فید معتبر نیست.")

    parsed = urllib.parse.urlparse(url)
    parsed_host = (parsed.hostname or "").lower()
    if parsed_host in ("x.com", "www.x.com", "twitter.com", "www.twitter.com"):
        path_parts = [p for p in (parsed.path or "").split("/") if p]
        if path_parts and re.fullmatch(r"[A-Za-z0-9_]{1,15}", path_parts[0]):
            handle = path_parts[0]
            return _x_leaker_special_feed(handle), f"https://x.com/{handle}"
        raise ValueError("لینک پروفایل X معتبر نیست؛ لینک اکانت یا @handle را بفرست.")

    if parsed_host in ("instagram.com", "www.instagram.com", "m.instagram.com"):
        path_parts = [p for p in (parsed.path or "").split("/") if p]
        if path_parts and path_parts[0] not in ("p", "reel", "reels", "stories", "explore") \
                and re.fullmatch(r"[A-Za-z0-9._]{1,30}", path_parts[0]):
            user = path_parts[0]
            return _instagram_special_feed(user), f"https://www.instagram.com/{user}/"
        raise ValueError("لینک پروفایل اینستاگرام معتبر نیست؛ لینک پیج رو بفرست نه لینک پست.")

    if parsed_host in ("anitrendz.com", "www.anitrendz.com", "anitrendz.net", "www.anitrendz.net"):
        return ANITRENDZ_SPECIAL_FEED, "https://www.anitrendz.com/"

    data, content_type, final_url = _news_fetch(url, max_bytes=1_500_000)
    if _news_is_feed_bytes(data) or "xml" in (content_type or "").lower():
        # مطمئن شو XML واقعاً قابل parse است.
        ET.fromstring(data)
        parsed = urllib.parse.urlparse(final_url)
        site_url = f"{parsed.scheme}://{parsed.netloc}/"
        return final_url, site_url

    html_text = data.decode("utf-8", errors="ignore")
    parser = _NewsMetaParser()
    try:
        parser.feed(html_text)
    except Exception:
        pass
    for href in parser.feed_links:
        candidate = urllib.parse.urljoin(final_url, href)
        try:
            d, _ct, feed_final = _news_fetch(candidate, max_bytes=1_500_000)
            if _news_is_feed_bytes(d):
                ET.fromstring(d)
                return feed_final, final_url
        except Exception:
            continue

    # فیدهای متداول سایت‌ها
    base = f"{urllib.parse.urlparse(final_url).scheme}://{urllib.parse.urlparse(final_url).netloc}"
    for suffix in ("/feed", "/rss", "/rss.xml", "/feed.xml"):
        candidate = base + suffix
        try:
            d, _ct, feed_final = _news_fetch(candidate, max_bytes=1_500_000)
            if _news_is_feed_bytes(d):
                ET.fromstring(d)
                return feed_final, final_url
        except Exception:
            continue
    raise ValueError("RSS/Atom این سایت پیدا نشد. لینک مستقیم فید RSS را وارد کن.")

def _news_local_name(tag: str) -> str:
    return (tag or "").split("}")[-1].split(":")[-1].lower()

def _news_child_text(node, names):
    names = {n.lower() for n in names}
    for child in list(node):
        if _news_local_name(child.tag) in names:
            txt = "".join(child.itertext()).strip()
            if txt:
                return txt
    return ""

def _news_parse_date(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        dt = parsedate_to_datetime(value)
        if dt:
            return dt.isoformat()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except Exception:
        return value[:80]

ANITRENDZ_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

ANITRENDZ_CRAWLER_UA = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)

def _anitrendz_fetch(url: str, max_bytes: int = 24_000_000, user_agent: str | None = None):
    """AniTrendz را با هدر مرورگر می‌گیرد.

    بعضی پاسخ‌های سایت برای User-Agentهای رباتی/خیلی ساده، HTML متفاوت یا ناقص دارند.
    این تابع فقط برای AniTrendz استفاده می‌شود و بقیه منابع خبری را دست نمی‌زند.
    """
    if not _news_safe_url(url):
        raise ValueError("آدرس AniTrendz معتبر نیست.")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent or ANITRENDZ_BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://www.anitrendz.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=NEWS_HTTP_TIMEOUT) as resp:
        data = resp.read(max_bytes + 1)
        if len(data) > max_bytes:
            data = data[:max_bytes]
        content_type = resp.headers.get("Content-Type", "")
        final_url = resp.geturl()
    return data, content_type, final_url

class _AniTrendzChartParser(HTMLParser):
    """Parser کلاس‌محور AniTrendz؛ مسیر سریع در صورت باقی‌ماندن ساختار کلاس‌ها."""
    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.entries = []
        self.current = None
        self.entry_depth = None
        self.capture = None
        self.capture_depth = None
        self.rank_depth = None
        self.page_text_parts = []

    @staticmethod
    def _classes(attrs):
        d = {str(k).lower(): (v or "") for k, v in attrs}
        return d, set(d.get("class", "").split())

    def _in_class(self, name):
        return any(name in classes for _tag, classes in self.stack)

    def handle_starttag(self, tag, attrs):
        tag = (tag or "").lower()
        ad, classes = self._classes(attrs)
        depth = len(self.stack) + (0 if tag in self._VOID else 1)

        # نام کلاس‌های قدیمی و چند نام عمومی‌تر را قبول کن.
        is_entry = (
            tag in ("div", "article", "li")
            and (
                "at-mcc-entry" in classes
                or "chart-entry" in classes
                or "chart-item" in classes
                or "ranking-entry" in classes
            )
        )
        if is_entry:
            self.current = {"title": "", "detail": "", "image_url": "", "rank": 0, "rank_text": ""}
            self.entry_depth = depth

        if self.current is not None:
            if tag in ("div", "span", "h3", "h4") and ("entry-title" in classes or "chart-title" in classes):
                self.capture, self.capture_depth = "title", depth
            elif tag in ("div", "span", "p") and ("entry-detail" in classes or "chart-detail" in classes):
                self.capture, self.capture_depth = "detail", depth
            elif tag in ("div", "span") and ("at-mcc-e-rank" in classes or "rank" in classes or "entry-rank" in classes):
                self.rank_depth = depth
            elif tag == "img" and (
                self._in_class("at-mcc-e-thumbnail")
                or "at-mcc-e-thumbnail" in classes
                or "entry-image" in classes
                or "chart-image" in classes
            ):
                src = (
                    _NewsMetaParser._best_srcset(ad.get("srcset", ""))
                    or _NewsMetaParser._best_srcset(ad.get("data-srcset", ""))
                    or ad.get("data-original", "").strip()
                    or ad.get("data-lazy-src", "").strip()
                    or ad.get("data-src", "").strip()
                    or ad.get("src", "").strip()
                )
                if src and not self.current.get("image_url"):
                    self.current["image_url"] = src

        if tag not in self._VOID:
            self.stack.append((tag, classes))

    def handle_data(self, data):
        txt = re.sub(r"\s+", " ", data or " ").strip()
        if not txt:
            return
        self.page_text_parts.append(txt)
        if self.current is None:
            return
        if self.capture in ("title", "detail"):
            self.current[self.capture] = (self.current.get(self.capture, "") + " " + txt).strip()
        if self.rank_depth is not None and len(self.stack) >= self.rank_depth and not self.current.get("rank_text"):
            if re.fullmatch(r"\d{1,3}", txt):
                self.current["rank_text"] = txt

    def handle_endtag(self, tag):
        tag = (tag or "").lower()
        depth = len(self.stack)

        if self.capture_depth is not None and depth == self.capture_depth:
            self.capture = None
            self.capture_depth = None
        if self.rank_depth is not None and depth == self.rank_depth:
            self.rank_depth = None

        if self.current is not None and self.entry_depth is not None and depth == self.entry_depth:
            try:
                self.current["rank"] = int(self.current.get("rank_text") or 0)
            except Exception:
                self.current["rank"] = 0
            if self.current.get("title"):
                self.entries.append(self.current)
            self.current = None
            self.entry_depth = None
            self.capture = None
            self.capture_depth = None
            self.rank_depth = None

        if self.stack:
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    break

    @property
    def page_text(self):
        return " ".join(self.page_text_parts)

class _AniTrendzLooseParser(HTMLParser):
    """Fallback بدون وابستگی به کلاس‌های CSS.

    AniTrendz در HTML رندرشده برای هر ردیف الگوی پایداری دارد:
    رتبه -> Vote -> تصویر با alt نام اثر/شخصیت -> نام -> استودیو/نام انیمه.
    با نگه‌داشتن جریان متن و تصویر می‌توانیم حتی بعد از تغییر CSS جدول را بازسازی کنیم.
    """
    def __init__(self):
        super().__init__()
        self.tokens = []
        self.page_text_parts = []

    def handle_starttag(self, tag, attrs):
        tag = (tag or "").lower()
        if tag != "img":
            return
        ad = {str(k).lower(): (v or "") for k, v in attrs}
        alt = unescape(ad.get("alt", "")).strip()
        src = (
            _NewsMetaParser._best_srcset(ad.get("srcset", ""))
            or _NewsMetaParser._best_srcset(ad.get("data-srcset", ""))
            or ad.get("data-original", "").strip()
            or ad.get("data-lazy-src", "").strip()
            or ad.get("data-src", "").strip()
            or ad.get("src", "").strip()
        )
        if alt or src:
            self.tokens.append(("img", alt, src))

    def handle_data(self, data):
        txt = unescape(re.sub(r"\s+", " ", data or " ").strip())
        if not txt:
            return
        self.page_text_parts.append(txt)
        self.tokens.append(("text", txt, ""))

    @property
    def page_text(self):
        return " ".join(self.page_text_parts)

def _anitrendz_is_generic_alt(value: str) -> bool:
    v = re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()
    if not v:
        return True
    exact = {
        "peak", "lastposition", "last position", "weeks on chart", "weeks on top 10",
        "re entry", "new", "improved", "declined", "unchanged",
        "up arrow", "down arrow", "right arrow", "left arrow",
        "voting", "chart logo", "logo", "advertisement", "ad", "menu", "close",
    }
    if v in exact:
        return True
    if v.startswith("peak ") or v.startswith("lastposition ") or v.startswith("weeks on chart "):
        return True
    return False

def _anitrendz_entries_from_tokens(tokens, final_url: str) -> list:
    entries = []
    seen = set()
    n = len(tokens)

    for i, tok in enumerate(tokens):
        if tok[0] != "text" or tok[1].strip().lower() != "vote":
            continue

        # نزدیک‌ترین عدد قبل از Vote همان رتبه است. اعداد Peak/Weeks قبل‌تر قرار دارند.
        rank = 0
        for j in range(i - 1, max(-1, i - 12), -1):
            if tokens[j][0] == "text" and re.fullmatch(r"\d{1,3}", tokens[j][1].strip()):
                try:
                    candidate = int(tokens[j][1].strip())
                    if 1 <= candidate <= 100:
                        rank = candidate
                        break
                except Exception:
                    pass
        if not rank:
            continue

        title = ""
        image_url = ""
        img_index = -1
        # تصویر اصلی ردیف معمولاً اولین img غیرآیکنی بعد از Vote است.
        for j in range(i + 1, min(n, i + 12)):
            kind, a, b = tokens[j]
            if kind == "img" and a and not _anitrendz_is_generic_alt(a):
                title = re.sub(r"\s+", " ", a).strip()
                image_url = urllib.parse.urljoin(final_url, b) if b else ""
                img_index = j
                break

        # اگر alt تصویر نبود، از متن بعد از Vote استفاده کن.
        if not title:
            for j in range(i + 1, min(n, i + 12)):
                if tokens[j][0] != "text":
                    continue
                t = re.sub(r"\s+", " ", tokens[j][1]).strip()
                if not t or t.lower() == "vote" or re.fullmatch(r"[+\-]?\d+[wW]?", t):
                    continue
                if t.lower() in ("new", "re", "advertisement"):
                    continue
                title = t
                img_index = j
                break

        if not title or _anitrendz_is_generic_alt(title):
            continue

        detail = ""
        # بعد از تصویر، معمولاً خود عنوان یک بار تکرار می‌شود و متن بعدی Detail است.
        start_j = (img_index + 1) if img_index >= 0 else (i + 1)
        title_norm = re.sub(r"\s+", " ", title).strip().casefold()
        for j in range(start_j, min(n, start_j + 18)):
            if tokens[j][0] != "text":
                continue
            t = re.sub(r"\s+", " ", tokens[j][1]).strip()
            if not t:
                continue
            tl = t.casefold()
            if tl == title_norm or tl == "vote":
                continue
            if tl in ("new", "re", "advertisement", "chart leaders", "voting links"):
                continue
            if re.fullmatch(r"[+\-]?\d+(?:w)?", t, flags=re.I):
                continue
            if re.fullmatch(r"\d{1,3}", t):
                continue
            # اگر وارد ردیف بعدی شدیم، متوقف شو.
            if t.lower() == "vote":
                break
            detail = t
            break

        key = (rank, title_norm)
        if key in seen:
            continue
        seen.add(key)
        entries.append({
            "title": title,
            "detail": detail,
            "image_url": image_url,
            "rank": rank,
            "rank_text": str(rank),
        })

    entries.sort(key=lambda x: (x.get("rank") or 999, x.get("title") or ""))
    return entries

class _AniTrendzInlineScriptParser(HTMLParser):
    """اسکریپت‌های inline صفحه AniTrendz را برای Page Data جمع می‌کند.

    AniTrendz بخش بالای جدول (از جمله Top 10) را در بعضی پاسخ‌های SSR داخل JSON
    صفحه می‌فرستد، حتی وقتی HTML قابل‌مشاهده از رتبه 20 به بعد شروع می‌شود.
    """
    def __init__(self):
        super().__init__()
        self._capture = False
        self._buf = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if (tag or '').lower() != 'script':
            return
        ad = {str(k).lower(): (v or '') for k, v in attrs}
        if ad.get('src'):
            self._capture = False
            self._buf = []
            return
        self._capture = True
        self._buf = []

    def handle_data(self, data):
        if self._capture and data:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if (tag or '').lower() == 'script' and self._capture:
            body = ''.join(self._buf).strip()
            if body:
                self.scripts.append(body)
            self._capture = False
            self._buf = []

def _anitrendz_json_walk(obj, max_depth: int = 10):
    """پیمایش محدود JSON برای تحمل تغییرات کوچک schema سایت."""
    stack = [(obj, 0)]
    seen = set()
    while stack:
        cur, depth = stack.pop()
        if depth > max_depth:
            continue
        if isinstance(cur, (dict, list)):
            oid = id(cur)
            if oid in seen:
                continue
            seen.add(oid)
        yield cur
        if isinstance(cur, dict):
            for value in cur.values():
                if isinstance(value, (dict, list)):
                    stack.append((value, depth + 1))
        elif isinstance(cur, list):
            for value in reversed(cur):
                if isinstance(value, (dict, list)):
                    stack.append((value, depth + 1))

def _anitrendz_first_scalar(obj, keys, max_depth: int = 5):
    wanted = {str(k).casefold() for k in keys}
    for cur in _anitrendz_json_walk(obj, max_depth=max_depth):
        if not isinstance(cur, dict):
            continue
        for key, value in cur.items():
            if str(key).casefold() not in wanted:
                continue
            if isinstance(value, (str, int, float)) and str(value).strip():
                return value
    return None

def _anitrendz_value_to_text(value) -> str:
    """مقادیر متنی AniTrendz را از string/list/object به متن کوتاه تبدیل می‌کند."""
    if value is None:
        return ''
    if isinstance(value, (str, int, float)):
        return re.sub(r'\s+', ' ', str(value)).strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            txt = _anitrendz_value_to_text(item)
            if txt and txt not in parts:
                parts.append(txt)
        return ', '.join(parts[:4])
    if isinstance(value, dict):
        # objectهای رایج studio/anime معمولاً name/title/english دارند.
        for key in ('name', 'title', 'english', 'romaji', 'label', 'value'):
            if key in value:
                txt = _anitrendz_value_to_text(value.get(key))
                if txt:
                    return txt
        parts = []
        for item in value.values():
            if isinstance(item, (str, int, float)):
                txt = _anitrendz_value_to_text(item)
                if txt and txt not in parts:
                    parts.append(txt)
        return ', '.join(parts[:3])
    return ''

def _anitrendz_first_value(obj, keys, max_depth: int = 6):
    wanted = [str(k).casefold() for k in keys]
    # اول کلیدهای اولویت‌دار را به همان ترتیب بررسی کن؛ نه ترتیب تصادفی JSON.
    for wanted_key in wanted:
        for cur in _anitrendz_json_walk(obj, max_depth=max_depth):
            if not isinstance(cur, dict):
                continue
            for key, value in cur.items():
                if str(key).casefold() == wanted_key and value not in (None, '', [], {}):
                    return value
    return None

def _anitrendz_normalize_image_url(value: str, final_url: str = "") -> str:
    """URL تصویر AniTrendz را از HTML/JSON به فرم قابل دانلود تبدیل می‌کند."""
    value = unescape(str(value or "")).strip().strip('"\'')
    if not value:
        return ""
    # JSON/HTML بعضی وقت‌ها slash را escape می‌کند.
    value = value.replace('\\u002F', '/').replace('\\/', '/')
    if value.startswith('//'):
        value = 'https:' + value
    if final_url:
        value = urllib.parse.urljoin(final_url, value)
    return value

def _anitrendz_looks_like_image_url(value: str) -> bool:
    """فقط URLهایی را قبول می‌کند که واقعاً شبیه asset تصویری باشند.

    نسخه قبلی هر http(s) را تصویر فرض می‌کرد و گاهی لینک صفحه/رأی را به‌عنوان
    image_url برمی‌داشت. اینجا host/pathهای شناخته‌شده AniTrendz و پسوندهای تصویر
    را ملاک قرار می‌دهیم.
    """
    v = _anitrendz_normalize_image_url(value)
    if not v:
        return False
    low = urllib.parse.unquote(v).lower()
    try:
        p = urllib.parse.urlparse(v)
    except Exception:
        return False

    if p.path.endswith('/_next/image') and urllib.parse.parse_qs(p.query).get('url'):
        return True
    if any(host in low for host in (
        'firebasestorage.googleapis.com', 'storage.googleapis.com',
        'i0.wp.com', 'i1.wp.com', 'i2.wp.com', 'i3.wp.com',
    )):
        return True
    if re.search(r'\.(?:jpe?g|png|webp|gif|avif)(?:\?|$)', low):
        return True
    if '/choices%2f' in low or '/choices/' in low:
        return True
    return False

def _anitrendz_image_from_json(obj, final_url: str) -> str:
    """بهترین URL تصویر را از Choice/Page Data استخراج می‌کند.

    AniTrendz بین نسخه‌های مختلف schema نام فیلد تصویر را عوض کرده است. به‌جای
    اولین کلید generic، همه URLهای محتمل را امتیازدهی می‌کنیم تا لینک صفحه یا Vote
    به اشتباه انتخاب نشود و URLهای عمیق Firebase/Next.js هم پیدا شوند.
    """
    candidates = []
    image_words = ('image', 'img', 'poster', 'avatar', 'thumb', 'thumbnail', 'photo', 'picture', 'art')

    for cur in _anitrendz_json_walk(obj, max_depth=12):
        if not isinstance(cur, dict):
            continue
        for k, raw in cur.items():
            key = str(k or '').casefold()
            values = []
            if isinstance(raw, str):
                values.append(raw)
            elif isinstance(raw, dict):
                for rk, rv in raw.items():
                    if isinstance(rv, str):
                        values.append(rv)
            elif isinstance(raw, list):
                values.extend(x for x in raw if isinstance(x, str))

            for raw_value in values:
                value = _anitrendz_normalize_image_url(raw_value, final_url)
                if not _anitrendz_looks_like_image_url(value):
                    continue
                low = urllib.parse.unquote(value).lower()
                score = 0
                if any(word in key for word in image_words):
                    score += 100
                if key in ('src', 'url'):
                    score += 15
                if 'firebasestorage.googleapis.com' in low or 'storage.googleapis.com' in low:
                    score += 95
                if '/_next/image' in low:
                    score += 90
                if '/choices%2f' in low or '/choices/' in low:
                    score += 80
                if re.search(r'\.(?:jpe?g|png|webp|gif|avif)(?:\?|$)', low):
                    score += 35
                if any(bad in low for bad in ('default.png', 'placeholder', 'chart-logo', 'logo-nav', '/icon', 'favicon')):
                    score -= 90
                candidates.append((score, value))

    if not candidates:
        return ''
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]

_anitrendz_poll_page_cache = {}

def _anitrendz_fetch_poll_page(url: str, ttl_seconds: int = 900):
    """صفحه رأی‌گیری را کوتاه‌مدت cache می‌کند تا ساخت سه کارت، درخواست تکراری نزند."""
    now = time.time()
    cached = _anitrendz_poll_page_cache.get(url)
    if cached and now - cached[0] < ttl_seconds:
        return cached[1], cached[2]
    data, _ct, final_url = _anitrendz_fetch(url, max_bytes=24_000_000)
    html_text = data.decode('utf-8', errors='ignore')
    _anitrendz_poll_page_cache[url] = (now, html_text, final_url)
    return html_text, final_url

def _anitrendz_inline_json_roots(html_text: str) -> list:
    parser = _AniTrendzInlineScriptParser()
    try:
        parser.feed(html_text)
    except Exception:
        pass
    bodies = list(parser.scripts)
    if not bodies:
        for attrs, body in re.findall(r'<script\b([^>]*)>(.*?)</script\s*>', html_text, flags=re.I | re.S):
            if re.search(r'\bsrc\s*=', attrs or '', flags=re.I):
                continue
            if body and body.strip():
                bodies.append(body.strip())

    roots = []
    for raw in bodies:
        body = unescape(raw or '').strip()
        if not body:
            continue
        parsed = None
        if body[:1] in ('{', '['):
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = None
        if parsed is None:
            a, b = body.find('{'), body.rfind('}')
            if 0 <= a < b:
                try:
                    parsed = json.loads(body[a:b + 1])
                except Exception:
                    parsed = None
        if parsed is not None:
            roots.append(parsed)
    return roots

def _anitrendz_title_key(value: str) -> str:
    value = unescape(str(value or '')).replace('’', "'").replace('‘', "'")
    value = re.sub(r'[^\w\']+', ' ', value, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', value).strip().casefold()

def _anitrendz_poll_image_map(html_text: str, final_url: str) -> dict:
    """img alt -> URL را از صفحه Poll استخراج می‌کند (Top Anime این مسیر را مستقیم دارد)."""
    loose = _AniTrendzLooseParser()
    try:
        loose.feed(html_text)
    except Exception:
        return {}
    out = {}
    for tok in loose.tokens:
        if tok[0] != 'img':
            continue
        alt, src = tok[1], tok[2]
        key = _anitrendz_title_key(alt)
        url = _anitrendz_normalize_image_url(src, final_url)
        if key and url and _anitrendz_looks_like_image_url(url) and not _anitrendz_is_generic_alt(alt):
            out[key] = url
    return out

def _anitrendz_poll_text_detail_map(html_text: str, target_titles: list[str]) -> dict:
    """برای Character Poll، نام انیمه را از متن کنار نام کاراکتر پیدا می‌کند."""
    loose = _AniTrendzLooseParser()
    try:
        loose.feed(html_text)
    except Exception:
        return {}
    targets = {_anitrendz_title_key(x): x for x in target_titles if _anitrendz_title_key(x)}
    out = {}
    ui_words = {
        'vote', 'back', 'next', 'international', 'romaji', 'anime trending',
        'character', 'top anime', 'current male characters', 'female characters',
    }
    texts = [tok[1].strip() for tok in loose.tokens if tok[0] == 'text' and tok[1].strip()]
    for i, text in enumerate(texts):
        key = _anitrendz_title_key(text)
        if key not in targets or key in out:
            continue
        for nxt in texts[i + 1:i + 7]:
            nk = _anitrendz_title_key(nxt)
            if not nk or nk == key or nk in ui_words:
                continue
            if re.fullmatch(r'\d+(?:\s*/\s*\d+)?', nxt):
                continue
            if nxt.upper().startswith(('LIMIT:', 'CURRENT:', 'SUMMER ', 'SPRING ', 'FALL ', 'WINTER ')):
                continue
            out[key] = nxt
            break
    return out

def _anitrendz_enrich_entries_from_poll(entries: list, chart_type: str) -> None:
    """image/detail خالی Chart را از Poll رسمی AniTrendz کامل می‌کند.

    برای کاراکترها ابتدا خود Character Poll بررسی می‌شود. اگر تصویر کاراکتر در HTML/JSON
    سایت نبود، از پوستر انیمه همان کاراکتر در Top Anime Poll به‌عنوان fallback استفاده می‌شود
    تا کارت دیگر با کادر خاکستری منتشر نشود.
    """
    if not entries:
        return
    target_by_key = {
        _anitrendz_title_key(e.get('title')): e
        for e in entries if _anitrendz_title_key(e.get('title'))
    }
    if not target_by_key:
        return

    poll_url = 'https://www.anitrendz.com/polls/top-anime' if chart_type == 'anime' else 'https://www.anitrendz.com/polls/characters'
    try:
        html_text, final_url = _anitrendz_fetch_poll_page(poll_url)
    except Exception as e:
        logger.info('AniTrendz poll enrichment fetch failed (%s): %s', chart_type, e)
        return

    # 1) مستقیم از img alt/src صفحه
    image_map = _anitrendz_poll_image_map(html_text, final_url)
    for key, entry in target_by_key.items():
        if not (entry.get('image_url') or '').strip() and image_map.get(key):
            entry['image_url'] = image_map[key]

    # 2) JSON داخلی صفحه؛ schema را generic می‌خوانیم.
    try:
        for root in _anitrendz_inline_json_roots(html_text):
            for cur in _anitrendz_json_walk(root, max_depth=11):
                if not isinstance(cur, dict):
                    continue
                if chart_type in ('male', 'female'):
                    title_raw = _anitrendz_first_value(cur, ('name', 'characterName', 'title'), max_depth=2)
                    detail_raw = _anitrendz_first_value(cur, ('anime', 'animeTitle', 'series', 'show'), max_depth=3)
                else:
                    title_raw = _anitrendz_first_value(cur, ('title', 'name', 'animeTitle'), max_depth=2)
                    detail_raw = _anitrendz_first_value(cur, ('studio', 'studios'), max_depth=3)
                title = _anitrendz_value_to_text(title_raw)
                key = _anitrendz_title_key(title)
                entry = target_by_key.get(key)
                if not entry:
                    continue
                if not (entry.get('detail') or '').strip():
                    detail = _anitrendz_value_to_text(detail_raw)
                    if detail and _anitrendz_title_key(detail) != key:
                        entry['detail'] = detail
                if not (entry.get('image_url') or '').strip():
                    img = _anitrendz_image_from_json(cur, final_url)
                    if img:
                        entry['image_url'] = img
    except Exception as e:
        logger.info('AniTrendz poll embedded enrichment failed (%s): %s', chart_type, e)

    # 3) Character Poll در بعضی نسخه‌ها تصویر را در DOM نمی‌فرستد، اما نام کاراکتر/انیمه متنی است.
    if chart_type in ('male', 'female'):
        detail_map = _anitrendz_poll_text_detail_map(html_text, [e.get('title') or '' for e in entries])
        for key, entry in target_by_key.items():
            if not (entry.get('detail') or '').strip() and detail_map.get(key):
                entry['detail'] = detail_map[key]

        # 4) اگر portrait رسمی در Character Poll نبود، پوستر همان انیمه را از Top Anime Poll بگیر.
        missing = [e for e in entries if not (e.get('image_url') or '').strip() and (e.get('detail') or '').strip()]
        if missing:
            try:
                anime_html, anime_final = _anitrendz_fetch_poll_page('https://www.anitrendz.com/polls/top-anime')
                anime_images = _anitrendz_poll_image_map(anime_html, anime_final)
                for entry in missing:
                    poster = anime_images.get(_anitrendz_title_key(entry.get('detail')))
                    if poster:
                        entry['image_url'] = poster
                        entry['_image_fallback'] = 'anime_poster'
            except Exception as e:
                logger.info('AniTrendz anime-poster fallback failed: %s', e)

def _anitrendz_unwrap_next_image(url: str) -> list[str]:
    """URL پروکسی Next.js و URL اصلی تصویر را به‌ترتیب کم‌ریسک برمی‌گرداند."""
    out = []
    value = _anitrendz_normalize_image_url(url)
    if not value:
        return out
    # ابتدا همان URL رسمی‌ای که صفحه داده است؛ معمولاً Next optimizer روی هاست پایدارتر است.
    if _news_safe_url(value):
        out.append(value)
    try:
        p = urllib.parse.urlparse(value)
        q = urllib.parse.parse_qs(p.query)
        if p.path.endswith('/_next/image') and q.get('url'):
            inner = _anitrendz_normalize_image_url(urllib.parse.unquote(q['url'][0]), value)
            if _news_safe_url(inner):
                out.append(inner)
    except Exception:
        pass
    result = []
    for item in out:
        if item not in result:
            result.append(item)
    return result

def _anitrendz_fetch_image(url: str, max_bytes: int = 5_000_000) -> bytes:
    """تصویر AniTrendz/Firebase را با fallback مناسب هاست اشتراکی می‌گیرد.

    AVIF عمداً درخواست نمی‌شود چون Pillow روی بعضی cPanelها decoder آن را ندارد و نتیجه
    قبلی برای همه ردیف‌ها کادر خاکستری می‌شد.
    """
    candidates = _anitrendz_unwrap_next_image(url)
    last_error = None

    def _download(candidate: str, with_referer: bool = True):
        headers = {
            'User-Agent': ANITRENDZ_BROWSER_UA,
            'Accept': 'image/jpeg,image/png,image/webp,image/*;q=0.8,*/*;q=0.4',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
        }
        if with_referer:
            headers['Referer'] = 'https://www.anitrendz.com/'
        req = urllib.request.Request(candidate, headers=headers)
        with urllib.request.urlopen(req, timeout=NEWS_HTTP_TIMEOUT) as resp:
            data = resp.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError('AniTrendz image too large')
            if not data:
                raise ValueError('AniTrendz image response is empty')
            ctype = (resp.headers.get('Content-Type') or '').lower()
            if 'text/html' in ctype and data.lstrip()[:1] == b'<':
                raise ValueError('AniTrendz returned HTML instead of image')
            return data

    for candidate in candidates:
        for with_referer in (True, False):
            try:
                return _download(candidate, with_referer=with_referer)
            except Exception as e:
                last_error = e

    # اگر URL مستقیم Firebase بود و مستقیم جواب نداد، از optimizer خود AniTrendz عبور بده.
    direct = ''
    for candidate in candidates:
        if '/_next/image' not in candidate:
            direct = candidate
            break
    if direct:
        try:
            wrapper = 'https://www.anitrendz.com/_next/image?' + urllib.parse.urlencode({
                'url': direct, 'w': '256', 'q': '82'
            })
            return _download(wrapper, with_referer=True)
        except Exception as e:
            last_error = e
    raise RuntimeError(f'AniTrendz image download failed: {last_error}')

def _anitrendz_choice_to_entry(choice, index: int, final_url: str, chart_type: str) -> dict | None:
    if not isinstance(choice, dict):
        return None

    rank_raw = _anitrendz_first_scalar(
        choice,
        ('rank', 'ranking', 'position', 'currentRank', 'currentPosition'),
        max_depth=4,
    )
    try:
        rank = int(str(rank_raw).strip()) if rank_raw is not None else 0
    except Exception:
        rank = 0

    # طبق schema شناخته‌شده AniTrendz: anime => title/studio، character => name/anime.
    # studio گاهی array/object است، بنابراین scalar-only کافی نیست.
    if chart_type in ('male', 'female'):
        title_raw = _anitrendz_first_value(choice, ('name', 'characterName', 'title'), max_depth=5)
        detail_raw = _anitrendz_first_value(choice, ('anime', 'animeTitle', 'series', 'show'), max_depth=5)
    else:
        title_raw = _anitrendz_first_value(choice, ('title', 'name', 'animeTitle'), max_depth=5)
        detail_raw = _anitrendz_first_value(choice, ('studio', 'studios', 'anime'), max_depth=5)

    title = _anitrendz_value_to_text(title_raw)
    detail = _anitrendz_value_to_text(detail_raw)
    if not title or _anitrendz_is_generic_alt(title):
        return None

    return {
        'title': title,
        'detail': detail,
        'image_url': _anitrendz_image_from_json(choice, final_url),
        'rank': rank,
        'rank_text': str(rank) if rank else '',
        '_embedded_index': index,
    }

def _anitrendz_chart_choices_candidates(root) -> list:
    """لیست‌های choices را از Page Data پیدا می‌کند؛ مسیر رسمی قدیمی در اولویت است."""
    candidates = []
    try:
        charts = root.get('props', {}).get('pageProps', {}).get('charts', [])
        if isinstance(charts, list):
            for chart in charts:
                if isinstance(chart, dict) and isinstance(chart.get('choices'), list):
                    candidates.append((chart, chart.get('choices')))
    except Exception:
        pass

    # fallback برای تغییر نام/عمق wrapper در Next.js.
    for cur in _anitrendz_json_walk(root, max_depth=9):
        if not isinstance(cur, dict):
            continue
        choices = cur.get('choices')
        if isinstance(choices, list) and choices:
            pair = (cur, choices)
            if not any(existing[1] is choices for existing in candidates):
                candidates.append(pair)
    return candidates

def _anitrendz_entries_from_embedded_json(html_text: str, final_url: str, chart_type: str):
    """Top 10 را از JSON داخل scriptهای AniTrendz استخراج می‌کند.

    یک scraper عمومی AniTrendz نیز از مسیر props.pageProps.charts[0].choices استفاده
    می‌کند. این مسیر مشکل SSR فعلی را حل می‌کند که HTML قابل‌مشاهده از رتبه 20 شروع می‌شود.
    خروجی: (entries, diagnostics)
    """
    parser = _AniTrendzInlineScriptParser()
    try:
        parser.feed(html_text)
    except Exception:
        pass

    # اگر HTMLParser به‌دلیل markup عجیب script را نگرفت، regex fallback.
    script_bodies = list(parser.scripts)
    if not script_bodies:
        for attrs, body in re.findall(r'<script\b([^>]*)>(.*?)</script\s*>', html_text, flags=re.I | re.S):
            if re.search(r'\bsrc\s*=', attrs or '', flags=re.I):
                continue
            if body and body.strip():
                script_bodies.append(body.strip())

    best = []
    best_score = -1
    parsed_scripts = 0
    choice_lists = 0

    for raw_body in script_bodies:
        body = unescape(raw_body or '').strip()
        if not body:
            continue
        roots = []
        # حالت رایج/شناخته‌شده: کل script یک JSON object است.
        if body[:1] in ('{', '['):
            try:
                roots.append(json.loads(body))
            except Exception:
                pass
        # __NEXT_DATA__ یا JSONی که با whitespace/BOM شروع شده.
        if not roots:
            start = body.find('{')
            end = body.rfind('}')
            if 0 <= start < end:
                candidate = body[start:end + 1].strip()
                try:
                    roots.append(json.loads(candidate))
                except Exception:
                    pass

        for root in roots:
            parsed_scripts += 1
            for chart_obj, choices in _anitrendz_chart_choices_candidates(root):
                choice_lists += 1
                entries = []
                explicit_ranks = 0
                for idx, choice in enumerate(choices, start=1):
                    entry = _anitrendz_choice_to_entry(choice, idx, final_url, chart_type)
                    if not entry:
                        continue
                    if entry.get('rank'):
                        explicit_ranks += 1
                    entries.append(entry)

                if not entries:
                    continue

                # اگر JSON خود Chart ترتیب Choices را دارد ولی rank داخل choice حذف شده،
                # فقط وقتی حداقل 10 choice واقعی داریم رتبه را از ترتیب رسمی همان لیست می‌سازیم.
                # این fallback روی HTML visible اعمال نمی‌شود و بنابراین 20..29 را 1..10 جا نمی‌زند.
                if explicit_ranks == 0 and len(entries) >= 10:
                    for idx, entry in enumerate(entries, start=1):
                        entry['rank'] = idx
                        entry['rank_text'] = str(idx)
                elif explicit_ranks and any(not e.get('rank') for e in entries):
                    # mixed schema را حدس نمی‌زنیم.
                    entries = [e for e in entries if e.get('rank')]

                entries.sort(key=lambda x: (x.get('rank') or 999, x.get('title') or ''))
                ranks = {int(e.get('rank') or 0) for e in entries if 1 <= int(e.get('rank') or 0) <= 10}
                score = len(ranks) * 100
                if ranks == set(range(1, 11)):
                    score += 5000
                elif {1, 2, 3}.issubset(ranks) and len(ranks) >= 8:
                    score += 2500

                # ترجیح ضعیف برای chart objectی که type/name آن با صفحه فعلی سازگار است.
                chart_label = ' '.join(
                    str(chart_obj.get(k) or '') for k in ('type', 'name', 'title', 'slug', 'category')
                ).lower()
                if chart_type == 'male' and 'male' in chart_label:
                    score += 20
                elif chart_type == 'female' and 'female' in chart_label:
                    score += 20
                elif chart_type == 'anime' and ('anime' in chart_label or not chart_label):
                    score += 10

                if score > best_score:
                    best_score = score
                    best = entries

    diag = {
        'scripts': len(script_bodies),
        'json_scripts': parsed_scripts,
        'choice_lists': choice_lists,
        'top10': len([e for e in best if 1 <= int(e.get('rank') or 0) <= 10]),
    }
    return best, diag

def _anitrendz_season_from_month(month: int) -> str:
    if month in (1, 2, 3):
        return "Winter"
    if month in (4, 5, 6):
        return "Spring"
    if month in (7, 8, 9):
        return "Summer"
    return "Fall"

def _anitrendz_parse_page(
    url: str,
    chart_type: str = "",
    _allow_dated_retry: bool = True,
    _allow_crawler_retry: bool = True,
    _user_agent: str | None = None,
) -> dict:
    data, _ct, final_url = _anitrendz_fetch(url, max_bytes=24_000_000, user_agent=_user_agent)
    html_text = data.decode("utf-8", errors="ignore")

    # مسیر اصلی V39: Page Data داخل inline script. Top 10 ممکن است در HTML visible نباشد.
    embedded_entries, embedded_diag = _anitrendz_entries_from_embedded_json(
        html_text, final_url, chart_type or "anime"
    )

    strict = _AniTrendzChartParser()
    loose = _AniTrendzLooseParser()
    try:
        strict.feed(html_text)
    except Exception:
        pass
    try:
        loose.feed(html_text)
    except Exception:
        pass

    # متن Loose عمداً مستقل از کلاس‌هاست و برای تاریخ/هفته مطمئن‌تر است.
    text = loose.page_text or strict.page_text

    week_m = re.search(r"\bWEEK\s*#?\s*(\d{1,2})\b", text, flags=re.I)
    week = int(week_m.group(1)) if week_m else 0

    date_m = re.search(
        r"\b(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+"
        r"(\d{1,2}),\s*(\d{4})\b",
        text,
        flags=re.I,
    )
    chart_date = None
    if date_m:
        try:
            chart_date = datetime.strptime(
                f"{date_m.group(1).title()} {date_m.group(2)}, {date_m.group(3)}", "%B %d, %Y"
            )
        except Exception:
            chart_date = None

    season_m = re.search(r"\b(SPRING|SUMMER|FALL|AUTUMN|WINTER)\s+(\d{4})\s+ANIME\s+SEASON\b", text, flags=re.I)
    season = season_m.group(1).title().replace("Autumn", "Fall") if season_m else ""
    year = int(season_m.group(2)) if season_m else (chart_date.year if chart_date else datetime.now().year)
    # صفحه current گاهی title/cache اشتباه دارد؛ تاریخ خود Chart برای تعیین فصل مرجع مطمئن‌تری است.
    if chart_date:
        season = _anitrendz_season_from_month(chart_date.month)
        year = chart_date.year

    strict_entries = strict.entries or []
    loose_entries = _anitrendz_entries_from_tokens(loose.tokens, final_url)

    # Page Data بر HTML SSR اولویت دارد، ولی فقط وقتی Top 10 واقعی/کامل داده باشد.
    # در غیر این صورت fallbackهای قدیمی همچنان فعال می‌مانند.
    embedded_ranks = {int(e.get("rank") or 0) for e in embedded_entries if 1 <= int(e.get("rank") or 0) <= 10}
    if embedded_ranks == set(range(1, 11)) or ({1, 2, 3}.issubset(embedded_ranks) and len(embedded_ranks) >= 8):
        entries = embedded_entries
    else:
        # Parser عمومی اگر داده بیشتری پیدا کرده، ترجیح دارد.
        entries = loose_entries if len(loose_entries) >= max(3, len(strict_entries)) else strict_entries

    for idx, entry in enumerate(entries, start=1):
        if not entry.get("rank"):
            entry["rank"] = idx
        img = (entry.get("image_url") or "").strip()
        if img:
            entry["image_url"] = urllib.parse.urljoin(final_url, img)
    entries.sort(key=lambda x: (x.get("rank") or 999, x.get("title") or ""))

    if not chart_type:
        path = urllib.parse.urlparse(final_url).path.lower()
        if "female-characters" in path:
            chart_type = "female"
        elif "male-characters" in path:
            chart_type = "male"
        else:
            chart_type = "anime"

    dated_url = final_url
    if chart_date:
        base = final_url.rstrip("/")
        if not re.search(r"/\d{4}-\d{2}-\d{2}$", base):
            dated_url = base + "/" + chart_date.strftime("%Y-%m-%d")

    current_chart = {
        "chart_type": chart_type,
        "week": week,
        "season": season or "",
        "year": year,
        "date": chart_date,
        "url": dated_url,
        "entries": entries,
        "embedded_diag": embedded_diag,
    }

    def _candidate_score(candidate: dict) -> int:
        # امتیاز کیفیت بر اساس وجود واقعی رتبه‌های 1..10 است، نه تعداد کل ردیف‌ها.
        # این دقیقاً باگ قبلی را رفع می‌کند که پاسخ 20..60 چون ردیف بیشتری داشت
        # از پاسخ تاریخ‌دارِ صحیح 1..10 بهتر شمرده می‌شد.
        ranks = set()
        for e in (candidate.get("entries") or []):
            try:
                r = int(e.get("rank") or 0)
            except Exception:
                r = 0
            if 1 <= r <= 10:
                ranks.add(r)
        score = len(ranks) * 20
        if {1, 2, 3}.issubset(ranks):
            score += 200
        if ranks == set(range(1, 11)):
            score += 1000
        elif len(ranks) >= 8:
            score += 500
        if candidate.get("week"):
            score += 10
        return score

    current_score = _candidate_score(current_chart)

    # fallback اول: همان URL با User-Agent خزنده. AniTrendz گاهی Top 10 را برای
    # مرورگر عادی client-side می‌فرستد اما برای crawler به‌صورت SSR کامل می‌دهد.
    if _allow_crawler_retry and current_score < 700 and _user_agent is None:
        try:
            crawler_chart = _anitrendz_parse_page(
                final_url,
                chart_type,
                _allow_dated_retry=True,
                _allow_crawler_retry=False,
                _user_agent=ANITRENDZ_CRAWLER_UA,
            )
            # اگر صفحه crawler هفته دیگری از cache قدیمی بود، قبولش نکن.
            same_week = (not week) or (not crawler_chart.get("week")) or int(crawler_chart.get("week") or 0) == int(week)
            if same_week and _candidate_score(crawler_chart) > current_score:
                return crawler_chart
        except Exception as e:
            logger.info("AniTrendz crawler SSR retry failed for %s: %s", chart_type, e)

    # fallback دوم: نسخه تاریخ‌دار همان Chart. معیار انتخاب، کیفیت Top 10 است؛
    # نه تعداد کل entries. این برای پاسخ‌هایی که فقط رتبه 20 به بعد دارند ضروری است.
    if _allow_dated_retry and chart_date and current_score < 700 and dated_url != final_url:
        try:
            retried = _anitrendz_parse_page(
                dated_url,
                chart_type,
                _allow_dated_retry=False,
                _allow_crawler_retry=_allow_crawler_retry,
                _user_agent=_user_agent,
            )
            same_week = (not week) or (not retried.get("week")) or int(retried.get("week") or 0) == int(week)
            if same_week and _candidate_score(retried) > current_score:
                return retried
        except Exception as e:
            logger.info("AniTrendz dated retry failed for %s: %s", chart_type, e)

    return current_chart

def _anitrendz_top10_entries(entries: list) -> list:
    """فقط رتبه‌های واقعی 1 تا 10 را برمی‌گرداند.

    AniTrendz گاهی در HTML عمومی فقط بخش 20 به بعد جدول را تحویل می‌دهد.
    آن داده هرگز نباید به‌عنوان Top 10 استفاده شود.
    """
    out = []
    seen = set()
    for entry in entries or []:
        try:
            rank = int(entry.get("rank") or 0)
        except Exception:
            rank = 0
        if not (1 <= rank <= 10):
            continue
        title = re.sub(r"\s+", " ", str(entry.get("title") or "")).strip()
        if not title:
            continue
        key = (rank, title.casefold())
        if key in seen:
            continue
        seen.add(key)
        clean = dict(entry)
        clean["rank"] = rank
        clean["rank_text"] = str(rank)
        out.append(clean)
    out.sort(key=lambda x: (x.get("rank") or 999, x.get("title") or ""))
    return out[:10]

def _anitrendz_top10_is_valid(entries: list) -> bool:
    top = _anitrendz_top10_entries(entries)
    ranks = {int(e.get("rank") or 0) for e in top}
    # حداقل رتبه‌های 1،2،3 و مجموعاً 8 ردیف لازم است؛ اگر سایت فقط 20-29 بدهد رد می‌شود.
    return {1, 2, 3}.issubset(ranks) and len(top) >= 8

def _anitrendz_payload_from_chart(chart: dict) -> str:
    top = _anitrendz_top10_entries(chart.get("entries") or [])
    payload = {
        "chart_type": chart.get("chart_type") or "anime",
        "week": int(chart.get("week") or 0),
        "season": chart.get("season") or "",
        "year": int(chart.get("year") or datetime.now().year),
        "url": chart.get("url") or "",
        "entries": [
            {
                "rank": int(e.get("rank") or 0),
                "title": e.get("title") or "",
                "detail": e.get("detail") or "",
                "image_url": e.get("image_url") or "",
            } for e in top
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

def _anitrendz_item_from_chart(chart: dict) -> dict:
    ctype = chart.get("chart_type", "anime")
    week = int(chart.get("week") or 0)
    season = chart.get("season") or ""
    year = int(chart.get("year") or datetime.now().year)
    entries = _anitrendz_top10_entries(chart.get("entries") or [])
    winner = (entries[0].get("title") if entries else "") or ""

    if ctype == "male":
        title = f"{winner} tops AniTrendz Male Character Rankings Week {week} {season} {year}" if winner else f"AniTrendz Male Character Rankings Week {week} {season} {year}"
    elif ctype == "female":
        title = f"{winner} tops AniTrendz Female Character Rankings Week {week} {season} {year}" if winner else f"AniTrendz Female Character Rankings Week {week} {season} {year}"
    else:
        title = f"AniTrendz Weekly Anime Ranking Week {week} {season} {year}"

    top_names = []
    for e in entries[:10]:
        if e.get("title"):
            top_names.append(f"{e.get('rank')}. {e.get('title')}")
    summary = f"AniTrendz {season} {year} Week {week} rankings. " + " | ".join(top_names)
    chart_date = chart.get("date")
    published = chart_date.isoformat() if chart_date else ""
    date_key = chart_date.strftime("%Y-%m-%d") if chart_date else f"{year}-{season.lower()}-w{week}"
    image_url = (entries[0].get("image_url") if entries else "") or ""

    return {
        # v45 namespace تازه دارد تا کارت‌های بدون تصویر نسخه قبل یک‌بار دوباره ساخته شوند.
        "guid": f"anitrendz:v45:{ctype}:{date_key}:week-{week}",
        "title": title,
        "url": chart.get("url") or "https://www.anitrendz.com/charts/top-anime",
        "published_at": published,
        "summary": summary,
        "image_url": image_url,
        "video_url": "",
        "news_type": "ranking",
        "ranking_payload": _anitrendz_payload_from_chart(chart),
    }

def _anitrendz_collect_current() -> list:
    global _anitrendz_last_partial_error
    items = []
    errors = []
    _anitrendz_last_partial_error = ""
    for chart_type, url in ANITRENDZ_CHARTS:
        try:
            chart = _anitrendz_parse_page(url, chart_type)
            entries = chart.get("entries") or []
            top10 = _anitrendz_top10_entries(entries)
            if not chart.get("week") or not _anitrendz_top10_is_valid(entries):
                ranks = [int(e.get("rank") or 0) for e in entries[:15] if e.get("rank")]
                emb = chart.get("embedded_diag") or {}
                diag = (
                    f"week={chart.get('week') or 0}, top10={len(top10)}, ranks={ranks[:10]}, "
                    f"embedded={emb}, url={chart.get('url') or url}"
                )
                raise ValueError(f"Top 10 کامل از AniTrendz دریافت نشد ({diag})؛ برای جلوگیری از انتشار رتبه اشتباه رد شد.")
            items.append(_anitrendz_item_from_chart(chart))
        except Exception as e:
            errors.append(f"{chart_type}: {e}")
    if not items and errors:
        raise ValueError(" | ".join(errors)[:500])
    # اگر یک Chart موقتاً ناقص بود، همان مورد منتشر نمی‌شود تا مثلاً رتبه 20-29 به اسم Top 10 نرود.
    if errors:
        _anitrendz_last_partial_error = " | ".join(errors)[:500]
        logger.warning("AniTrendz partial chart warning: %s", _anitrendz_last_partial_error)
    return items

FONTS_DIR = os.path.join(BASE_DIR, "fonts")

def _anitrendz_font(size: int, bold: bool = False, weight: str = ""):
    """فونت کارت‌ها. اول فونت همراه بات (fonts/)، بعد فونت‌های ویندوز و لینوکس.

    weight: "regular" / "semibold" / "extrabold" — اگه خالی باشه از bold استفاده میشه.
    """
    if ImageFont is None:
        return None
    weight = (weight or ("extrabold" if bold else "regular")).lower()
    win = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    candidates = {
        "regular": [
            os.path.join(FONTS_DIR, "Inter-Regular.ttf"),
            os.path.join(win, "segoeui.ttf"), os.path.join(win, "arial.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ],
        "semibold": [
            os.path.join(FONTS_DIR, "Inter-SemiBold.ttf"),
            os.path.join(win, "seguisb.ttf"), os.path.join(win, "arialbd.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ],
        "extrabold": [
            os.path.join(FONTS_DIR, "Inter-ExtraBold.ttf"),
            os.path.join(win, "segoeuib.ttf"), os.path.join(win, "arialbd.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ],
    }.get(weight) or []
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    try:
        # Pillow 10.1+ فونت پیش‌فرض با اندازه دلخواه داره (نه فونت ریز bitmap)
        return ImageFont.load_default(size=size)
    except Exception:
        try:
            return ImageFont.load_default()
        except Exception:
            return None

# =========================
# قالب مشترک کارت‌های رنکینگ هفتگی
# =========================
RANKING_LOGO_DIR = os.path.join(BASE_DIR, "logos")

# لوگوی داخلی Anime Corner (اگه دانلود لوگو ممکن نبود)
_ANIMECORNER_LOGO_B64 = "iVBORw0KGgoAAAANSUhEUgAAAGIAAABiCAYAAACrpQYOAAAcJElEQVR4nNWd+XdUx5XHP6UFrUhIYt9XGzA42HHsJJNkMmvy/2Z+mTMnOY7jhXjBGAEGm11iF0JCICG03PnhW1dV/fR6lQT2PeedVqv7vVq+dfdb1fAzIjMLfjX6/Y3u03rRT7ajZZMYQrDs8w7A3xe/G4ClEMJy8Vn5M35K9JMBwier1kSZWT+wDdgEDAHtaAx+tZHAeQ6MA4+Kz2ykrddNbxQIMwtlk2FmbcAAmtgONPkD8XUz0Bf/34VAAQFg8Z55YAaYAx4A0/H1JTAdQljM+5C3/abAeSNA5ABEEeOreSuwAxgERuLf++L7XgTGFqAHAeCvPg6Lfy8gjngA3EdAPAEmgLvAHeAhMJmDUta/10WvFYhcJJhZN7AX2I0megswjETOUHx/BDgE9KMJ70TiqFFaRiC8AJ4C9+J1F4HkoMwi8B4DM7F/r1V8vTYgClxwADgJHAD2AwfjtRWJngE06Z1lj2qi2eL4lpG4mkKi6yHimDEEzD2kV8ZCCLer9X8jaMOBKACwGa3wd9DEnwDeA44C3dUekf3dSn/r3b+IALkK/ADcjtf3CJhnIYSXLbTbFG0YECV64J14HYnXCeAw0gWB1St9o/pWrZ0lpEfGEBDXgYtIfD1GXPJ0g/q0MYMtgHAQOIVAOAqcBo4hPVBUsm+Kiu3PAzeBz4HLiGOeIA75PoTwar1FVcd6PSinqOwG0ar/CE3+CcQJ25CFBGkC3rQ/U1wQXcBxtFgOApeAG8hsDmZ2OYTwaj07sC5AFKyhLqQHTiNO+DVwBgFQHPCbBqBIxf7sQGDsRmLqu/idDjMbDSHMrxdnrAsQmRjqAn6FLKK3gd8C71PpdP0UAahGhvp+HJnWffF9B+KMb0IIy+sBxpqBiNywDZme+xEIJxAnHI9t/NwAcMr7ux34PeKQAeT7YGZXQggza22oZSCyVXAIeAvYhXTAceAX8W+3hn5uAJSRIcfyI2APcBZ5+yNm9mkI4flaOKMlILxBMxtCE78fgXEG6Yat2dc3GoT1sFwa6WO+qPah8IrHwmbM7GugZWtqraLpAFodp5A+OIksjo2kYuh7vYCuFlLPKTc2tgL/hkIuc8hrP/vaOCLjhgHkkB1C3vFpKvXBelI+SfmzF5HN/wpFVmfj+4X46nGp9uwZnSSl240WTn/hufXG4NwxjETVlLdhZuda8TOaAsLNVDPrRdbQMTYWhKKSfwk8Qg7WBIoTTcbrBVqZC/H7L7N7Z5HnvIzESXe8diLT9CASr/vR5DbiaDoYu4D/QmC2A91m9kWzpm2zHBGiuXYAKeQTSC9srtPpZinngEUU0n4I/AjcQh7uAxQ5HY+fzVOZk3BA2kII86WNmPUhee/hluPI7D6MJjhPNHl/KHm/B3GGAz5vZhebsaYaBiKiu2xmOxAXnAL+gFbVeoFQ5IDbyDq5izjgCZr06yisPRlCmGuk72X/DyG8AK6Y2TVknh5HXL4Pcfwv4//z/sHqsVq8548IvFmgx8y+CiHMNMIZDQGR6YVB4F/j9QekH8o61ioFJO8n0Ur/Kl7TaMU/AH4MITzL+1b6oORkVp2ELCKwCNwzs0cI7AfZ62k0yUOsdkzzfoNE24ex/wvAhJmNNjLwZkXT+8Cf47WrpEOtUP6MG8BnKCR9FYmhSSTbDUVAl/OQSj7h/sDi/6oleQrFCAGJlVFSjuIy8Ekc62EkBd5GoBT77u+PocW0HPt+uSwLWKS6QGTcsBMB8RHrD8IyGvTHwN+BT4GHVfLZoTjROSA5lRUNVOOO7P+GDIJH8Z4OJJ7OIB31AfAbpBeKDqu/nkRcPI6A+b6eeKoLRAShkxS8O8z6OFE+gGm0Cj8HvgE+DiFMQHliPx9MAZA+0kS8IFowyJDoAJ5EnVA321YA2MXWDPAMWWNTCJDjyLHLwXBj4R0E3H0zuxtCeFar3ZpAxA51ohXwAQrodbM+3BCAa8A/ETd8D3wVQpgws7YQwnIt2R4XyAhacdsRl25Csvle/Oq22N8l4KmZnQeuhRCWGuSOvL0ZMzuLrDhPt04gKTFSGJehnPvp2Jf7ZvYJ4vxSqgpENtiTCID3WLtyzqssRpH8HQUuoITLC7fOGuhXN/Jsf4niWntIXu4dtHqHkX2/gKytHcCOGMJuONvmxQQhhEUz+wYB8JhouSHDJRfXPj9vkXydGyGE29UWQFUgYuP9CNXTccCbaJ0b/L6XwJdIF4yisMBY3m6th2Qg/AGJyg/RInEF6inPeVL1xzKS+StFCWb2SQhhodHOe7/iPdfM7F5sZwYp5/+kEgxDYvEUWgRnzGyMKmK9FIgMtd1I8XyIVtNaQZhFouhj4BwCYaLR0pWsXyeQSPgNMh76sjbaqbT9nTbHzxaQWHloZpcaabdKP2bN7HO02l8hvfDfSBzm87QHcewBoK+aX1EKRFx1bUgxv4PkMKwNhFfINP0YccTXIYSpRsMAmUjaQUq/vk8lCHmbK8PJPj+IOPse0TEMIcw1GxfKRNUScMnMHiAObEOLY3/Wbmds9xBwysxKA4OrgMg65fmFI6SgWStAeJjia2QZfQ78o57CLOtTNKE/QLb8R0ghlvWr7L1/7zAqYhhDoquuZ146qEqH8YmZ/SW2MY087Lezr+8gAhHbHS+OvZpo6iDFXfa00lEqOeFL4B/AeeBcMyDAygrsQItiH1KC+5vsj4PRhzj8OhJhj5t8TlnfQghh0sz+B+mjDqSPdsc2e2K/9wDvmNnjUAgKtuUPzT4YQDLtCJKtPpBW6ALwv4gjPqlnT9eggNKTnpLtpDUuDajUczsCZc3kojyEMInE7wVkji9l/RtCQGxHnFxBbcV/mFk74oYTSD8UI5CNkE/QFFLOo8Df46ppBQR/Ziey2be0cH9OAwjQnWtJbxbIotExjhy5HxDXuWU2iDhkBDhuZludmyATTQVleIKUAoXWuGEJiaILwGdRjraV+Qj1AneROlCOeCuayFbI2+lGK3PA288npVpf6jmB8fMFM/sBgdEfPz6GuG8HilbvQLpkwp/XkT8o/rkdiaOyWEoj5N+/hkzU28irreqo1Qs3ZOKyN/Z5FSe30L+Vsv4Q8xWN+DANtjGDIrdXkNGzH/V5M+JmzxCuUIWyNtUl7Yw372yw0YpHkJy2s0gkjbtyztpZWVlm5rt/OmNnlxE3LaBVsxxjXSOkLGDdaGYD1IO4610zuxXbGqBygjxutAVN3iRwJ1RJhWbvp5BoWkAgHIpj7InP8vjXCnVAxcT0I07w2lRojhs8kvo9Wg3jyFxLI0tioBNZZUeR7NwROzmIVtRd0l4G95IXkDf7nNb1hI+nAy24D5FJ3IbAHoifufM3h4KIU7HtrWZ2jiT7Vzcg8XQ+vh1FgJ5Cc+sGx1Yz6w4hvDSzUDRfO9CkHKZ6mXw1cm64ixT0DWA0xCROFiIwU4ry17FzRxAYR5FX6hP+CK2qbxAg8yjRP4NW5t4m+5eT568PxTZHkAQYRuLPN8S8QgCMIVF7A83LsxDC5aoTEZ29qCs2oXjTEgKhHwExHMfzElb7EdtIO3egNfNwDAXdxkIIDwtiqCMO+n0USDwDvIsmNS/D6SCV6pyIk3ANrUgQ2LuprJ9qhtwLPonExBDlPlUPmry9aHHeQfWvm8xsIfapNOGURWy/Q5P9EAUJDYFZoeeKjffHTm2meXIP2sXRj/5BBsZ+UnGyh9Z9MvN8sP/dQdredRCJu0dInp8H/oXV+YBGaBqt1IPZfbUUcTtJfG4mbZa8G2NOpfoiWomzZnYdRWwfIV3TTmELWtH62IRWgDs6jQ7OOzGBrKSbHswrdLA9Pns7AmWESgBCyd+uMA+i2tNfIY6dRqvMv9+oReMbHXsL94Ual/ejndXbzPRhSsuOmNnB+N5N4hdxXsYQgIECExSBaENckW8mb4RcSd9AHDFe5Xu+bXcnyTxu5NlOfSQF3x3beURzHPEEyf5N9b5Y0g8PkbhucW52A2QQibud/r/44RISp+NI56ya2yIQ7WiimvUbQCv0NrKYKoJaWTR3e+z8QZJT1mxbzh0n471Xkciaov7iWUQg5Ku5FWd1kPJ56kectrnk+b7V+GnsQ4UJ3gYVeektNL9SnLzy7nZcAcVODqDA10G0opoRJ07+zDakzLcjAL5Hu3rq7eJ5jiZglR3fJA0gXToY3/s4FuPfvajiLx/jI8QRT1FeZjUQGXXSGsuCopgPSZOxMskxfvUuil39jtXJk2bJOWMvEhXTyMSdLbad0UPEsTNVPm+EfGIHkXg8ZWbDmR6cRGC3Afn/3bKaje3PkAAhhGBlOqJsb3M9WkSIP4mdASpiSG4CnkR+gw+qVfJ7exBXuEIsllbmRsRFtFgWWFvb3v5BxJVHYcUyXEAK+RUKKA4VYliP0eS/QL7IilPYkclyB6EZjshToJ5ML6szDchP2Mb6FysfIq2yognsRsQTtFiGkZHQrLNaRoMkTzynidiXTuA9M7uK9MMSmqcJ4p6K/KacI7zjrUzQHGLJldVWMFtDbCs3T9eLPNGzI/ZhkjSWpfg+IMDeJhUXr5V8rlbES1z5XrHei7j1PWAwfvY0XlNE03tVGDzSUryapRexA0uUy1939qZZX25wGopt34+Xhy3m0BgP0roRUo0ms/aKO2snULX8IcQNB0gxtJdoD/dU/rAiEG00d+iIk8u90vJ3NPHzaBU8Z33L+N3RGiQlY+4iIPrZGBBAdbl3ibGiAr0khWk6kd7oRovxEjCfm/ZQCUSg+dNfXAY/JZUjrkxuISx8Gcnnt1DAzzN/68Ud02hibsXnDiNR1BXfux5slXL9cwflWi4AD0oiCC9jW55K6EEgLHm0tfjwHIhhhFqzHLGEVvk8AmNVriDG7y8iP+IzxBEnab46ZJlsA0rsv4u9B0gRPozvZ5GImiGd99EK5QCAzOS/IRCulGX2gioC2xCXzqHxzlKDciB6SEVYrdASMBU7UbFCMsfmKvJqA5qw00jJwuoBF2maVL7oeqwj9tlDCG45OUATaMKWYjvdrBbH1XyKomExg8TK1/H1ElqA1TJ3nuTyuNJ87E/p9zsKN7bRmrJeig1NlX2YhcFvxM4/IcWkfotkaa3dqE+RnH1M8gUghWQ8AtuLVn8nKWY2jSbtPlqhfjiXh6JrccpSvH8S+BaVBF1DYnY8RhBWUYxSOOgBWXYuIkspByL3/Jql/JCTqhRz1g/M7EuScp9GesMPTOklgbJA2iP3Ck38PjTIfgSA539nSWX47fF1OF7L8X4XXb2kSPNmBNwCae+dT/4jJPKmEDd/iyLLz8vGl0mCIcT5XSRJ000N0HMgJpGMf1rty1XIHcGGIraxs4/M7Cla3ePI6/UCLI/7DyJZPxXb2E6auC5WRwA2k8Irnmc+iDjGAR/Pxum570UEnC/Cifg9P3bOC40vhBCmsjGUjjWK4RCfmQNRM2LRkT3wGWnLUn6QST3y7bJdaBW8qPXlvOwEuBiTJn3x3n3IOdsbX3ciW3x7lYFY9hpIx9B1IFCH4ue98RoicbznRrzC3e37x6TY1T0k1iZDrMzzMVR0IgKTieBXpF2uvaRkUO39EVmO9QqSgeOknUG1ZGg+AX3AHjO7H+qcZVQIhs0hy2LCtLvTnbDdSKzsJBkQRYVefO0g1T95ZDQn31+9qkvxnsOkTZM9wIMQworDVsYFhVSwV2n4vgznXvdp2qlSgVK0IFyJXkds3ajd3U+KxTdFmekXosXl0c09KKCWm7jVFoV/7qcOeBVGzaYLzzM0+e/GZzwlhSZKLZ2sImWQtFmmjZSG3UfaJfsDAuh+GagdhUaeoyzbrdgRT2XWs8FdaboIaPgIhExULZuZ728+jQoLGt0Y45/PUaknGrknf++m77tITF8Cvg0hlPoAse+HkOXn9bSGrC13JrtQfGsYid/7Zc8qllwuRfHglspI2U0l1JVd/VQxY8soW1UDwJ/QZo/fI65o1vN2BVxVFtchB6MHlf1fR9bSuYII8j7vRvmVj0inFwS0GPIqejebd5vZpVBS8Vi2auaQwnqUda4edVFSRtgIZWnUMyhS+RHNg+Cc52JsrWCALLczwPtm1l/mQaMVvheBcJqUoziGJIP3qwct0J3AFrPVJ/6vAJGJkQkkmu6QNnHUEzFuk3ttakOUdeYAEklnWFv2rhOJhWfUsd7qdY1U93QK+TnkfbJ0fvlmBMhQdi+F77fHz3cB+8pEdtn+iHkEwm0K5ZIl5A1tQtbCAA2GSDL27iOdeHakzm31aBMakwchobW0qI9rO1rdb5lZT9RjbXEiRxAH7Izfq5Xw6orf2Yc2quwqclg1hXafdAjtYpWHO3njW0nhhXww5SNVR9xKOYTY23VSs9zg3/djrN2LXkt018Prh9Fk/8K0dcwn8Aia3G3UrxMOyBx/G3HXR1bYH1ENiHm0qm7TuHhyX2IEVsIZ5SOszGV7zelemq+nKpKH5T1T16qeyMmTTANoErtJ5vUWBEYjutGlxhBJjK9QBRAZQvOIG+4TI4wN0FDs7GCUn42QK9buYsdapIAWjh+s5c7TWsCFZATcQz6GRxJ6SBWD1chIIRYPEi5TCK6WTljQ+RNjZKnAGuSdGEIycBdiw0Z+48edNGNtq9cnegmFKp4iq6/RRVSLlkmFaQ/j3LxAOugZCr8/p3rUeh4ZP1eQX3KHVHazQrUsnGVkxl5A8rCWSelWxjEExB6ql10W2/eEeytR3yJ5uMQT+I9o3BeqRouICxZIhQIzZnYb6cVv0GT7zy9siff5XM0hAM4jKfMIRXCn47MMSjgiy6VOIVa8iSq7a7G3g7MTmXzHzWwY6nKFV388Q6DP01oFoJP/QIcfenU1ttHsMz21CpIM0/GZy9l4bpEq390BzpNWIBB9/m4iQD4PIVwvNlgqmrLGXDSNIm+51oAMKaT3kCX0dh6RzCkLazyJnXuAYjFXqG+llbUb0MR8HZ/jP8jxDcoheKasUfJU7D0kEa6hVZyPxU/X9MSP/+6R+2FX4r3fxvc/ApdimX7NnHXqRWrQDzQcRGbc76huafnDj6BjFn40M6+FrQXGAzP7AoE4jVj3HcRdjSh9B+GvaGP9eSQCPBN3FomLEyV9LSNDi+4WmshzaJP+K5/A+Oo7nHwTyzASibfQYvD61utogZwvSyM7VdUR8YZXpv1ifWhiDiIvuJau6ETe6HFS5fO9sg5k728i1j8dB3IVxZve9a+WtOP/u41OuvkKHS9xKYI8SUqZjiDzel+VZ/jfM2hH0LdoRT9FxxdVVGpEIHbGuXibdFbJ/XjfJ6Qa2KvA1VDntIWqQGQr9pnpjKK9SETtJOVfyyKYkA6mnQBuRs6oStHnmDKzT5HMda94hPK9cu4vjKKqkC/QhvoxqMgRXDYVQLuJ6T+pM8xqEJbR3r+/ISA+Ryu8In9gZtsQNxxBC+UE8iX8h6OuIU66Gse2kpupFY2uGRfK/IqHKGF+gPQbQdXIB3YShdQvAu2hzgGD2eTdimGPYSTjfa+BT5yfx3QbJfO/Av4WQnhckikLIYRRpThWyvePock7SiqzmUNceR6JlS9CdpJmNhedcVx+DvqHSCy5hXk5XldiBrLhH4lqKEAXO3EVrYKziN2riShX6AMohnQeOBrvD9U87kLs5UdSynMKmYmb4rOfIxEwjlbeF6HKqQaZBThqZvOIu27E6wAyOdtJv093AR1fNB2dUh+fGyLvI/13BoF5IN5/BwFwEeW2F4qLoh7VBSKbIC9t900ef6L+4buHSCd4PQshlOqKYltRN51F+uIzxB2b0WS8iP9/glKZPuiaDmEI4QdTOY8H4LbF116kG6aQZfQgjtcn0bnrBALhA2S0bI/Pehzn5SJKIo01ygU5NcwR6oudJwX1NqGDeP0onBwMX0W9aOfnDLDoOqAeGNnfeZGvm4cvQ3bEdDODjuLRbfub8f5+YC7EGqWCUu4h6alfo0zcr5DDuogWxGWScr9ZHEOj1NT2pWh+nUWr0sMSf6Y8pepgHAH+gyz8EKocpxYnpRsdDZpbKH58NIX/Ncz6xXuzMT3P/h9iqLsX6ZDtCIR9SMz+jlSZOEUyl79D3PCyFW6AFk7Lj+LjMjJpvWrht8hmryamjhJPY0EFZmfJHMNscvbFa8rMHgOPCxPV0uTnVAK+T5yDMET6OYYj8e/9JOvIkFU3inyML5BemS17fqPULEe4DF80Vet1Ijm5jOz+LVSC4a8dSL7OIG4ai7K0jSiLo0UyjMTZrjjwaVPd07UQD2OvFTJpZBLK7ncdYzpH9i3E4W+hnyM4HsflZTj3ESf8E/hLiEdBtMoJTk3vrMzAWDIdb+Cc0I7k6DCr648stvUB8pzvm9n/hXjicaS27HUTKQ3ZD+yKgNyoN9h6QFW7P/oHv0QccIB0PMVw/IqXf36NzOqzwA85p9bqVz1qaYtrBsa0mf2VtG3rBVpFW4q3IDC2AH9EYmouirgn8f1i9ow+Uuq1i1Q0ts3M/LSBadIx1J6Ne1lrQqJz141WvNfXdpJC+CcQJxxH4tQPvlpC/sUnSBx9GkK40sBUNUytphGBCp0xgqwJr2Z4Bw1kuHhLbHMMmaWXSSnZCQSEkepfvVg4kIrYukiJGt+T8RRFPh8iS2YOiUtPnbofshWZ3NsQyH2kbFkvsob8M0gbNB8jIL4DvgwhXF+rKCrSmoCACjC6kILbT/p1kn+n8lzAvL2XyOT7Cnm8N5D5Nxq/N4LiOFvR5ByNz99H+k0gn6SHpLNcHyNw5klFb34CzdZ45X6EA+G5kVcoYHcThTl+INUE3wytHw5Zk1oSTTllYmoeTewVMztMyhm3IU4plu53I5PQg4nfkBys72PIYhaJikA6hm0r6USxLQiY56RD0x+TDh7pIhUfj5CObvA9FfmejDmkv+7G12soXnQD+C4oZL9mpVyN1gwEJEWVKa4bMb7TgwCYJP3MpIsV55CdpMLdr71fZvYjMT0Zn+M7Vn3F7iYdROVFC9tJ28jakTjKucLFWlv2rCUEnE/+DbT6fW/EaAyhrItSrkZrFk21yNKJme+hUMdJpEP8GKLculpCk3AOrcRxNEEuZlxPDJHEygCVCnU+XotokXlNrk++J3w6SD+dNo+4YZYk3u4Tq+LDBvxkchltGBCZ7gho9Z5CoXGP1+yi0rz1/jxBIu4aWpljpM0lc2jC3X/ZQqr+WCLtQvLNM1sQGP6557PdQnuFxKff9wpx1F0Po7wOEGCDfs8aKnSHAXdNB5lPIna/S/qBcT9Lw2kEcY4fL7oU+9lNquDzXPcYKQGzQNJL/ryt8T4vX/F9fivBvNjXVQclNhs9XSttGBBQqTtiUO0rM7uLWP8GElsnkKnaQ/Je52Pf3LxcIumCFyQP/RWKXVUrm7nbSD9L4k+vDYCVNl9nY5m42oSCaTuQiep75vL9ca5Ql0ir3Fe16w6388eROFvZbrvWUMjrptcKBKyWudHb7SEV87oyHiT+FA2psg4kgmaQZ+2O3CRyCs/9FCe5EXrtQDhVMwcjt4wgZd5HOjvPrZ+ALJxpkrUziX7vbT2K1N4IvTEgcqplo0eOGUTeeh+pIG2WtBV5oUzh/pzoJwFEkXL5nin8NvQDsDWLEH6u9JMEokglemWVlfP6e7W+9P9ISfA56iNz3QAAAABJRU5ErkJggg=="

RANKING_BRANDS = {
    "anitrendz": {
        "name": "AniTrendz", "domain": "anitrendz.com", "site": "https://www.anitrendz.com/",
        "accent": (247, 148, 29),
        "logo_urls": ["https://www.anitrendz.com/apple-touch-icon.png"],
    },
    "animecorner": {
        "name": "Anime Corner", "domain": "animecorner.me", "site": "https://animecorner.me/",
        "accent": (239, 51, 64),
        "logo_urls": ["https://animecorner.me/apple-touch-icon.png"],
        "fallback_b64": _ANIMECORNER_LOGO_B64,
    },
    "mal": {
        "name": "MyAnimeList", "domain": "myanimelist.net", "site": "https://myanimelist.net/",
        "accent": (86, 128, 232),
        "logo_urls": [
            "https://cdn.myanimelist.net/img/common/pwa/launcher-icon-4x.png",
            "https://cdn.myanimelist.net/images/apple-touch-icon-256.png",
        ],
    },
}

_ranking_logo_cache = {}
_ranking_logo_failed_at = {}
_ranking_logo_lock = threading.Lock()


def _ranking_http_bytes(url: str, max_bytes: int = 2_000_000, referer: str = "") -> bytes:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept": "*/*",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=NEWS_HTTP_TIMEOUT) as resp:
        raw = resp.read(max_bytes + 1)
    if not raw or len(raw) > max_bytes:
        raise ValueError("پاسخ خالی یا خیلی بزرگ")
    return raw


def _ranking_discover_icon_urls(site_url: str) -> list:
    """آیکن‌های صفحه اصلی سایت (apple-touch-icon / icon) رو به ترتیب اندازه برمی‌گردونه."""
    try:
        html_text = _ranking_http_bytes(site_url, max_bytes=1_500_000).decode("utf-8", errors="ignore")
    except Exception:
        return []
    found = []
    for tag in re.findall(r"<link\b[^>]*>", html_text, flags=re.I):
        rel = (re.search(r'rel=["\']([^"\']+)', tag, flags=re.I) or [None, ""])[1].lower()
        href = (re.search(r'href=["\']([^"\']+)', tag, flags=re.I) or [None, ""])[1]
        if "icon" not in rel or not href:
            continue
        sizes = (re.search(r'sizes=["\']([^"\']+)', tag, flags=re.I) or [None, ""])[1]
        m = re.search(r"(\d+)x\d+", sizes or "")
        size = int(m.group(1)) if m else (180 if "apple" in rel else 32)
        if href.lower().endswith(".svg"):
            continue
        found.append((size, urllib.parse.urljoin(site_url, unescape(href))))
    found.sort(key=lambda x: -x[0])
    return [u for _s, u in found]


def _ranking_brand_logo(key: str):
    """لوگوی سایت به‌صورت RGBA.

    اولویت: فایل logos/<key>.png (می‌تونی لوگوی دلخواهت رو همین‌جا بذاری)،
    بعد دانلود از خود سایت و ذخیره در همون پوشه، در آخر لوگوی داخلی (برای Anime Corner).
    """
    if Image is None:
        return None
    brand = RANKING_BRANDS.get(key) or {}
    with _ranking_logo_lock:
        if key in _ranking_logo_cache:
            return _ranking_logo_cache[key]
        path = os.path.join(RANKING_LOGO_DIR, f"{key}.png")
        logo = None
        if os.path.exists(path):
            try:
                logo = Image.open(path)
                logo.load()
            except Exception as e:
                logger.warning("Ranking logo file unreadable %s: %s", path, e)
                logo = None
        if logo is None and time.time() - _ranking_logo_failed_at.get(key, 0) > 3600:
            urls = list(brand.get("logo_urls") or [])
            if brand.get("site"):
                urls += _ranking_discover_icon_urls(brand["site"])
            if brand.get("domain"):
                urls.append(f"https://www.google.com/s2/favicons?domain={brand['domain']}&sz=256")
            best = None
            for url in dict.fromkeys(urls):
                try:
                    im = Image.open(io.BytesIO(_ranking_http_bytes(url, referer=brand.get("site", ""))))
                    im.load()
                except Exception:
                    continue
                if best is None or min(im.size) > min(best.size):
                    best = im
                if min(im.size) >= 128:
                    break
            if best is not None and min(best.size) >= 32:
                logo = best
                try:
                    os.makedirs(RANKING_LOGO_DIR, exist_ok=True)
                    logo.convert("RGBA").save(path, format="PNG")
                except Exception as e:
                    logger.info("Ranking logo cache save failed: %s", e)
            else:
                _ranking_logo_failed_at[key] = time.time()
                logger.info("Ranking logo download failed for %s", key)
        if logo is None and brand.get("fallback_b64"):
            try:
                logo = Image.open(io.BytesIO(base64.b64decode(brand["fallback_b64"])))
                logo.load()
            except Exception:
                logo = None
        if logo is not None:
            logo = logo.convert("RGBA")
            _ranking_logo_cache[key] = logo
        return logo


def _ranking_fit_image(im, w: int, h: int):
    """کراپ هوشمند: پوسترهای عمودی از بالا کراپ میشن تا صورت‌ها نبرن."""
    im.load()
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (40, 46, 58))
        bg.paste(im, mask=im.getchannel("A"))
        im = bg
    src_ratio = im.size[0] / float(max(1, im.size[1]))
    center_y = 0.5 if src_ratio >= (w / float(h)) * 0.9 else 0.28
    return ImageOps.fit(im, (w, h), method=getattr(Image, "Resampling", Image).LANCZOS,
                        centering=(0.5, center_y))


def _ranking_render_card(brand_key: str, heading: str, subheading: str, rows: list,
                         image_loader=None, footer_note: str = "", file_prefix: str = "ariko_rank_") -> str | None:
    """کارت تمیز Top 10 با لوگوی سایت.

    rows: [{rank, title, detail, image_url, stat_label, stat_value, note, note_color}]
    image_loader: تابعی که url می‌گیره و bytes عکس رو برمی‌گردونه.
    """
    if Image is None or ImageDraw is None or ImageOps is None:
        return None
    brand = RANKING_BRANDS.get(brand_key) or {"name": brand_key, "domain": "", "accent": (120, 140, 255)}
    accent = tuple(brand["accent"])

    S = 2  # رندر در دو برابر اندازه و کوچک کردن در آخر = لبه‌های نرم
    W = 1080
    pad = 44
    header_h = 214
    row_h, gap = 116, 12
    footer_h = 92
    H = header_h + len(rows) * (row_h + gap) - gap + footer_h

    bg = (13, 16, 22)
    surface = (22, 26, 34)
    surface_top = (27, 31, 41)
    text_c = (244, 246, 250)
    muted = (150, 160, 176)
    faint = (98, 108, 124)

    def s(v):
        return int(round(v * S))

    def mix(c1, c2, t):
        return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

    canvas = Image.new("RGB", (s(W), s(H)), bg)
    draw = ImageDraw.Draw(canvas)

    # هاله ملایم رنگ برند بالای کارت
    glow_h = s(header_h + 40)
    for yy in range(0, glow_h, 2):
        t = 1 - yy / float(glow_h)
        draw.rectangle((0, yy, s(W), yy + 2), fill=mix(bg, accent, 0.16 * t * t))

    f_name = _anitrendz_font(s(46), weight="extrabold")
    f_head = _anitrendz_font(s(22), weight="semibold")
    f_sub = _anitrendz_font(s(22), weight="regular")
    f_top = _anitrendz_font(s(20), weight="semibold")
    f_ten = _anitrendz_font(s(72), weight="extrabold")
    f_rank = _anitrendz_font(s(40), weight="extrabold")
    f_title = _anitrendz_font(s(27), weight="semibold")
    f_detail = _anitrendz_font(s(20), weight="regular")
    f_label = _anitrendz_font(s(15), weight="semibold")
    f_stat = _anitrendz_font(s(34), weight="extrabold")
    f_note = _anitrendz_font(s(17), weight="semibold")
    f_foot = _anitrendz_font(s(18), weight="regular")

    def text_w(value, font):
        try:
            bb = draw.textbbox((0, 0), value, font=font)
            return bb[2] - bb[0]
        except Exception:
            return len(value) * s(12)

    def wrap(value, font, max_w, max_lines):
        words = re.sub(r"\s+", " ", str(value or "")).strip().split(" ")
        lines, cur = [], ""
        for word in words:
            trial = (cur + " " + word).strip()
            if cur and text_w(trial, font) > max_w:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        if cur:
            lines.append(cur)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] += "…"
        for i, line in enumerate(lines):
            while text_w(line, font) > max_w and len(line) > 2:
                line = line[:-2].rstrip() + "…"
            lines[i] = line
        return [l for l in lines if l]

    # ---- هدر: لوگو + اسم سایت + عنوان ----
    tile = 112
    tx0, ty0 = pad, 50
    logo = _ranking_brand_logo(brand_key)
    tile_fill = (255, 255, 255)
    if logo is not None:
        # لوگوی سفید/روشن روی کاشی سفید دیده نمیشه → کاشی به رنگ برند
        try:
            small = logo.resize((32, 32))
            px = [p for p in (small.get_flattened_data() if hasattr(small, "get_flattened_data") else small.getdata()) if p[3] > 128]
            if px and sum(0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2] for p in px) / len(px) > 215:
                tile_fill = accent
        except Exception:
            pass
    draw.rounded_rectangle((s(tx0), s(ty0), s(tx0 + tile), s(ty0 + tile)), radius=s(28), fill=tile_fill)
    if logo is not None:
        inner = s(tile - 22)
        lg = logo.copy()
        lg.thumbnail((inner, inner), getattr(Image, "Resampling", Image).LANCZOS)
        if lg.size[0] < inner and lg.size[1] < inner:
            ratio = inner / float(max(lg.size))
            lg = lg.resize((max(1, int(lg.size[0] * ratio)), max(1, int(lg.size[1] * ratio))),
                           getattr(Image, "Resampling", Image).LANCZOS)
        cx, cy = s(tx0 + tile / 2), s(ty0 + tile / 2)
        canvas.paste(lg, (cx - lg.size[0] // 2, cy - lg.size[1] // 2), lg)
    else:
        initials = "".join(w[0] for w in brand["name"].split()[:2]).upper()
        iw = text_w(initials, f_rank)
        draw.text((s(tx0 + tile / 2) - iw / 2, s(ty0 + 30)), initials, font=f_rank, fill=accent)

    nx = tx0 + tile + 26
    draw.text((s(nx), s(ty0 + 4)), brand["name"], font=f_name, fill=text_c)
    draw.text((s(nx), s(ty0 + 66)), (heading or "").upper(), font=f_head, fill=accent)
    if subheading:
        draw.text((s(nx), s(ty0 + 94)), subheading, font=f_sub, fill=muted)

    # "TOP 10" سمت راست
    ten_w = text_w("10", f_ten)
    draw.text((s(W - pad) - ten_w, s(ty0 + 18)), "10", font=f_ten, fill=text_c)
    top_w = text_w("TOP", f_top)
    draw.text((s(W - pad) - ten_w - top_w - s(10), s(ty0 + 30)), "TOP", font=f_top, fill=accent)
    draw.rectangle((s(pad), s(header_h - 22), s(pad + 72), s(header_h - 18)), fill=accent)

    # ---- ردیف‌ها ----
    rank_w = 78
    img_w, img_h = 176, row_h - 20
    stat_w = 200 if any((r.get("stat_value") or "").strip() for r in rows) else 0
    title_x = pad + rank_w + img_w + 22
    title_max = W - pad - 24 - title_x - (stat_w + 10 if stat_w else 0)

    for i, row in enumerate(rows):
        y = header_h + i * (row_h + gap)
        rank = int(row.get("rank") or (i + 1))
        top3 = rank <= 3
        draw.rounded_rectangle((s(pad), s(y), s(W - pad), s(y + row_h)), radius=s(20),
                               fill=surface_top if top3 else surface)
        if top3:
            draw.rounded_rectangle((s(pad), s(y + 18), s(pad + 5), s(y + row_h - 18)), radius=s(3), fill=accent)

        rank_txt = str(rank)
        rw = text_w(rank_txt, f_rank)
        draw.text((s(pad + 8 + rank_w / 2) - rw / 2, s(y + row_h / 2 - 25)), rank_txt, font=f_rank,
                  fill=accent if top3 else muted)

        ix, iy = pad + rank_w + 8, y + 10
        pasted = False
        url = (row.get("image_url") or "").strip()
        if url and image_loader and _news_safe_url(url):
            try:
                im = Image.open(io.BytesIO(image_loader(url)))
                im = _ranking_fit_image(im, s(img_w), s(img_h))
                mask = Image.new("L", im.size, 0)
                ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.size[0] - 1, im.size[1] - 1), radius=s(14), fill=255)
                canvas.paste(im, (s(ix), s(iy)), mask)
                pasted = True
            except Exception as e:
                logger.info("Ranking card image failed %s rank=%s: %s", brand_key, rank, e)
        if not pasted:
            draw.rounded_rectangle((s(ix), s(iy), s(ix + img_w), s(iy + img_h)), radius=s(14), fill=(38, 44, 56))

        detail = re.sub(r"\s+", " ", str(row.get("detail") or "")).strip()
        title_lines = wrap(row.get("title") or "", f_title, s(title_max), 1 if detail else 2)
        detail_lines = wrap(detail, f_detail, s(title_max), 1) if detail else []
        block_h = len(title_lines) * 34 + (len(detail_lines) * 28 if detail_lines else 0)
        ty = y + (row_h - block_h) / 2 - 2
        for line in title_lines:
            draw.text((s(title_x), s(ty)), line, font=f_title, fill=text_c)
            ty += 34
        for line in detail_lines:
            draw.text((s(title_x), s(ty + 2)), line, font=f_detail, fill=muted)
            ty += 28

        if stat_w:
            rx = W - pad - 26
            label = (row.get("stat_label") or "").upper()
            value = (row.get("stat_value") or "").strip()
            note = (row.get("note") or "").strip()
            has_note = bool(note)
            sy = y + (16 if has_note else 26)
            if label:
                draw.text((s(rx) - text_w(label, f_label), s(sy)), label, font=f_label, fill=faint)
            if value:
                draw.text((s(rx) - text_w(value, f_stat), s(sy + 20)), value, font=f_stat, fill=text_c)
            if has_note:
                draw.text((s(rx) - text_w(note, f_note), s(sy + 64)), note, font=f_note,
                          fill=tuple(row.get("note_color") or muted))

    # ---- فوتر ----
    fy = H - footer_h + 34
    draw.line((s(pad), s(fy - 14), s(W - pad), s(fy - 14)), fill=(34, 39, 50), width=s(1))
    src = f"Source: {brand.get('domain') or ''}"
    draw.text((s(pad), s(fy)), src, font=f_foot, fill=muted)
    if footer_note:
        draw.text((s(W - pad) - text_w(footer_note, f_foot), s(fy)), footer_note, font=f_foot, fill=faint)

    out = canvas.resize((W, H), getattr(Image, "Resampling", Image).LANCZOS)
    f = tempfile.NamedTemporaryFile(prefix=file_prefix, suffix=".jpg", delete=False)
    path = f.name
    f.close()
    out.save(path, format="JPEG", quality=93, optimize=True, subsampling=0)
    return path

def _anitrendz_build_chart_card(url: str, ranking_payload: str = "") -> str | None:
    """کارت Top 10 را از snapshot ذخیره‌شده همان خبر می‌سازد.

    این کار جلوی اختلاف بین زمان جمع‌آوری و زمان ارسال را می‌گیرد. اگر payload قدیمی
    وجود نداشت، یک بار صفحه را می‌خواند؛ اما فقط رتبه‌های 1 تا 10 پذیرفته می‌شوند.
    """
    if Image is None or ImageDraw is None or ImageOps is None:
        return None

    chart = None
    if ranking_payload:
        try:
            obj = json.loads(ranking_payload)
            if isinstance(obj, dict):
                chart = obj
        except Exception:
            chart = None
    if not chart:
        chart = _anitrendz_parse_page(url)

    entries = _anitrendz_top10_entries(chart.get("entries") or [])

    # Snapshotهای نسخه‌های قبل ممکن است Top 10 را داشته باشند ولی image_url/detail خالی باشد.
    # در این حالت یک بار صفحه فعلی همان Chart را می‌خوانیم و فقط فیلدهای خالی را merge می‌کنیم.
    if entries and any(not (e.get("image_url") or "").strip() or not (e.get("detail") or "").strip() for e in entries):
        try:
            live_chart = _anitrendz_parse_page(url, chart.get("chart_type") or "")
            live_entries = _anitrendz_top10_entries(live_chart.get("entries") or [])
            by_rank = {int(e.get("rank") or 0): e for e in live_entries if e.get("rank")}
            by_title = {re.sub(r"\s+", " ", str(e.get("title") or "")).strip().casefold(): e for e in live_entries}
            for entry in entries:
                match = by_rank.get(int(entry.get("rank") or 0))
                if not match:
                    key = re.sub(r"\s+", " ", str(entry.get("title") or "")).strip().casefold()
                    match = by_title.get(key)
                if not match:
                    continue
                if not (entry.get("image_url") or "").strip() and (match.get("image_url") or "").strip():
                    entry["image_url"] = match.get("image_url")
                if not (entry.get("detail") or "").strip() and (match.get("detail") or "").strip():
                    entry["detail"] = match.get("detail")
        except Exception as e:
            logger.info("AniTrendz card enrichment failed: %s", e)

    # V45: Top 10 از Page Data می‌آید اما AniTrendz گاهی image/detail را آنجا نمی‌فرستد.
    # Poll رسمی همان فصل منبع دوم برای کامل‌کردن عکس/نام انیمه است.
    if entries and any(not (e.get("image_url") or "").strip() or not (e.get("detail") or "").strip() for e in entries):
        try:
            _anitrendz_enrich_entries_from_poll(entries, chart.get("chart_type") or "anime")
        except Exception as e:
            logger.info("AniTrendz poll card enrichment failed: %s", e)

    if not _anitrendz_top10_is_valid(entries):
        logger.warning("AniTrendz card skipped because Top 10 is incomplete: %s", [e.get("rank") for e in entries])
        return None

    ctype = chart.get("chart_type")
    label = {"anime": "Top Anime", "male": "Male Characters", "female": "Female Characters"}.get(ctype, "Anime Chart")
    season = (chart.get("season") or "").upper()
    week = chart.get("week") or "?"
    year = chart.get("year") or ""
    rows = [{
        "rank": entry.get("rank") or (i + 1),
        "title": entry.get("title"),
        "detail": entry.get("detail"),
        "image_url": entry.get("image_url"),
    } for i, entry in enumerate(entries)]
    return _ranking_render_card(
        "anitrendz", label, f"{season} {year}  ·  WEEK {week}".strip(), rows,
        image_loader=lambda u: _anitrendz_fetch_image(u, max_bytes=5_000_000),
        footer_note="Weekly fan vote", file_prefix="ariko_anitrendz_",
    )

def _poll_anitrendz_source(source_row, bootstrap: bool = False):
    """AniTrendz را بدون RSS بررسی می‌کند و Chartهای قابل‌خواندن را مستقل ثبت می‌کند."""
    source_id = source_row["id"]
    try:
        entries = _anitrendz_collect_current()
    except Exception as e:
        _news_mark_source_checked(source_id, str(e))
        logger.warning("AniTrendz direct source failed: %s", e)
        return {"new": 0, "seeded": 0, "duplicate": 0, "error": str(e)}

    new_count = 0
    for item in entries:
        conn = db()
        exists = conn.execute(
            "SELECT 1 FROM news_items WHERE source_id=? AND guid=?",
            (source_id, item["guid"])
        ).fetchone()
        conn.close()
        if exists:
            continue
        item["news_type"] = "ranking"
        item_id = _news_insert_item(source_id, item, status="queued")
        if item_id:
            new_count += 1
            _send_news_item_to_archive(item_id)

    _news_mark_source_checked(source_id, _anitrendz_last_partial_error)
    return {"new": new_count, "seeded": 0, "duplicate": 0, "error": _anitrendz_last_partial_error}

class _AnimeCornerWeeklyLinkParser(HTMLParser):
    """لینک مقاله‌های Weekly Anime Ranking را از صفحات Anime Corner پیدا می‌کند."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current_href = ""
        self.current_parts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if (tag or "").lower() != "a" or self.current_href:
            return
        ad = {str(k).lower(): (v or "") for k, v in attrs}
        href = ad.get("href", "").strip()
        if href:
            self.current_href = href
            self.current_parts = []

    def handle_data(self, data):
        if self.current_href:
            txt = re.sub(r"\s+", " ", data or " ").strip()
            if txt:
                self.current_parts.append(txt)

    def handle_endtag(self, tag):
        if (tag or "").lower() == "a" and self.current_href:
            text = re.sub(r"\s+", " ", " ".join(self.current_parts)).strip()
            self.links.append((self.current_href, text))
            self.current_href = ""
            self.current_parts = []

class _AnimeCornerRankingTableParser(HTMLParser):
    """جدول رتبه‌بندی داخل مقاله Anime Corner را به ردیف‌های متنی تبدیل می‌کند."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_row = False
        self.in_cell = False
        self.cell_parts = []
        self.row = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        tag = (tag or "").lower()
        if tag == "tr":
            self.in_row = True
            self.row = []
        elif self.in_row and tag in ("td", "th"):
            self.in_cell = True
            self.cell_parts = []

    def handle_data(self, data):
        if self.in_cell:
            txt = re.sub(r"\s+", " ", data or " ").strip()
            if txt:
                self.cell_parts.append(txt)

    def handle_endtag(self, tag):
        tag = (tag or "").lower()
        if self.in_row and tag in ("td", "th") and self.in_cell:
            self.row.append(re.sub(r"\s+", " ", " ".join(self.cell_parts)).strip())
            self.in_cell = False
            self.cell_parts = []
        elif tag == "tr" and self.in_row:
            if self.row:
                self.rows.append(self.row[:])
            self.in_row = False
            self.in_cell = False
            self.row = []
            self.cell_parts = []

class _AnimeCornerPollEntryParser(HTMLParser):
    """رتبه و تصویر هر Anime را از صفحه Results رسمی Anime Corner می‌گیرد.

    صفحه Poll برای هر ردیف Top Ranking به صفحه Performance همان انیمه لینک می‌دهد؛
    بنابراین لازم نیست برای حدس‌زدن عکس به Featured Image مقاله تکیه کنیم.
    """
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.current = None
        self.entries = []

    def handle_starttag(self, tag, attrs):
        tag = (tag or "").lower()
        ad = {str(k).lower(): (v or "") for k, v in attrs}
        if tag == "a" and self.current is None:
            href = ad.get("href", "").strip()
            low = href.lower()
            if "/polls/rankings/anime-of-the-week/" in low:
                self.current = {
                    "href": urllib.parse.urljoin(self.base_url, href),
                    "text_parts": [],
                    "image_url": "",
                    "image_alt": "",
                }
                return

        if tag == "img" and self.current is not None:
            src = (
                _NewsMetaParser._best_srcset(ad.get("srcset", ""))
                or _NewsMetaParser._best_srcset(ad.get("data-srcset", ""))
                or ad.get("data-original", "").strip()
                or ad.get("data-lazy-src", "").strip()
                or ad.get("data-src", "").strip()
                or ad.get("src", "").strip()
            )
            if src and not self.current.get("image_url"):
                self.current["image_url"] = urllib.parse.urljoin(self.base_url, unescape(src))
            alt = re.sub(r"\s+", " ", ad.get("alt", "")).strip()
            if alt and not self.current.get("image_alt"):
                self.current["image_alt"] = alt

    def handle_data(self, data):
        if self.current is not None:
            txt = re.sub(r"\s+", " ", data or " ").strip()
            if txt:
                self.current["text_parts"].append(txt)

    def handle_endtag(self, tag):
        if (tag or "").lower() != "a" or self.current is None:
            return
        text = re.sub(r"\s+", " ", " ".join(self.current.get("text_parts") or [])).strip()
        self.current["text"] = text
        self.entries.append(self.current)
        self.current = None

def _animecorner_results_media(poll_url: str) -> dict:
    """Top 10 صفحه Results را بر اساس rank به image/title/movement نگاشت می‌کند."""
    poll_url = (poll_url or "").strip()
    if not poll_url or not _news_safe_url(poll_url):
        return {}
    try:
        data, _ct, final_url = _news_fetch(poll_url, max_bytes=6_000_000)
        html_text = data.decode("utf-8", errors="ignore")
        parser = _AnimeCornerPollEntryParser(final_url)
        parser.feed(html_text)
    except Exception as e:
        logger.info("Anime Corner results media parse failed %s: %s", poll_url, e)
        return {}

    result = {}
    for item in parser.entries:
        text = item.get("text") or ""
        m = re.search(r"#\s*(\d{1,3})\b", text)
        if not m:
            continue
        rank = int(m.group(1))
        if not (1 <= rank <= 10) or rank in result:
            continue
        image_url = (item.get("image_url") or "").strip()
        if image_url and not _news_safe_url(image_url):
            image_url = ""
        # title را فقط fallback نگه می‌داریم؛ عنوان دقیق از جدول مقاله می‌آید.
        title = (item.get("image_alt") or "").strip()
        vote_m = re.search(r"(\d{1,3}(?:\.\d{1,2})?%)\s*$", text)
        result[rank] = {
            "rank": rank,
            "title": title,
            "detail": vote_m.group(1) if vote_m else "",
            "image_url": image_url,
            "performance_url": item.get("href") or "",
        }

    # بعضی نسخه‌های صفحه Results عکس را با CSS/lazy-load می‌گذارند و parser بالا src نمی‌بیند.
    # برای Top 10 فقط در ردیف‌های بدون عکس، صفحه Performance رسمی همان Anime را fallback می‌خوانیم.
    for rank in sorted(result):
        item = result[rank]
        if (item.get("image_url") or "").strip():
            continue
        perf_url = (item.get("performance_url") or "").strip()
        if not perf_url or not _news_safe_url(perf_url):
            continue
        try:
            pdata, _pct, pfinal = _news_fetch(perf_url, max_bytes=2_500_000)
            phtml = pdata.decode("utf-8", errors="ignore")
            pmeta_parser = _NewsMetaParser()
            pmeta_parser.feed(phtml)
            pmeta = pmeta_parser.meta
            img = (pmeta.get("og:image") or pmeta.get("twitter:image") or "").strip()
            if img:
                img = urllib.parse.urljoin(pfinal, img)
                if _news_safe_url(img):
                    item["image_url"] = img
        except Exception as e:
            logger.info("Anime Corner performance image fallback failed rank=%s: %s", rank, e)
    return result

def _animecorner_default_poll_results_url(season: str, year: int, week: int) -> str:
    season_slug = (season or "").strip().lower().replace("autumn", "fall")
    return f"https://animecorner.me/polls/vote/w{int(week):02d}-{season_slug}{int(year)}/results"

def _animecorner_weekly_title_parts(title: str):
    clean = re.sub(r"\s+", " ", unescape(title or "")).strip()
    m = re.search(
        r"\b(Spring|Summer|Fall|Autumn|Winter)\s+(\d{4})\s+Anime\s+Rankings?\s*[-–—:]\s*Week\s*#?\s*(\d{1,2})\b",
        clean,
        flags=re.I,
    )
    if not m:
        return None
    return m.group(1).title(), int(m.group(2)), int(m.group(3)), clean

def _animecorner_find_latest_weekly_article() -> dict:
    """جدیدترین مقاله هفتگی Anime Corner را از چند Index رسمی پیدا می‌کند."""
    candidates = []
    seen = set()
    season_order = {"winter": 1, "spring": 2, "summer": 3, "fall": 4, "autumn": 4}

    # اول Poll Browser رسمی را می‌خوانیم؛ URL نتیجه هر Week ساختاریافته است و معمولاً
    # زودتر از Category cache آپدیت می‌شود. از روی آن URL مقاله رسمی همان Week ساخته می‌شود.
    try:
        data, _ct, final_url = _news_fetch(ANIMECORNER_POLL_BROWSE_URL, max_bytes=3_000_000)
        html_text = data.decode("utf-8", errors="ignore")
        href_pat = re.compile(
            r"href=[\"']([^\"']*/polls/vote/w(\d{1,2})-(spring|summer|fall|autumn|winter)(\d{4})/results/?[^\"']*)[\"']",
            flags=re.I,
        )
        for m in href_pat.finditer(html_text):
            week = int(m.group(2))
            season = m.group(3).title()
            year = int(m.group(4))
            article_url = f"https://animecorner.me/{season.lower()}-{year}-anime-rankings-week-{week}/"
            key = article_url.rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            candidates.append({
                "season": season,
                "year": year,
                "week": week,
                "title": f"{season} {year} Anime Rankings - Week {week}",
                "url": article_url,
                "poll_url": urllib.parse.urljoin(final_url, m.group(1)),
                "sort": (year, season_order.get(season.lower(), 0), week),
            })
    except Exception as e:
        logger.info("Anime Corner poll browser failed: %s", e)

    for index_url in ANIMECORNER_WEEKLY_INDEX_URLS:
        try:
            data, _ct, final_url = _news_fetch(index_url, max_bytes=3_000_000)
            html_text = data.decode("utf-8", errors="ignore")
            parser = _AnimeCornerWeeklyLinkParser()
            parser.feed(html_text)
            for href, anchor_text in parser.links:
                parts = _animecorner_weekly_title_parts(anchor_text)
                if not parts:
                    continue
                season, year, week, clean_title = parts
                article_url = urllib.parse.urljoin(final_url, href)
                if not _news_safe_url(article_url) or "animecorner.me" not in urllib.parse.urlparse(article_url).netloc.lower():
                    continue
                key = article_url.split("#", 1)[0].rstrip("/")
                if key in seen:
                    continue
                seen.add(key)
                candidates.append({
                    "season": season,
                    "year": year,
                    "week": week,
                    "title": clean_title,
                    "url": article_url,
                    "sort": (year, season_order.get(season.lower(), 0), week),
                })
        except Exception as e:
            logger.info("Anime Corner weekly index failed %s: %s", index_url, e)

    if not candidates:
        raise ValueError("مقاله هفتگی Anime Corner پیدا نشد.")
    candidates.sort(key=lambda x: x["sort"], reverse=True)
    return candidates[0]

def _animecorner_top10_from_html(html_text: str) -> list:
    parser = _AnimeCornerRankingTableParser()
    parser.feed(html_text or "")
    found = {}
    for row in parser.rows:
        if len(row) < 2:
            continue
        rank_idx = None
        rank = 0
        for idx, cell in enumerate(row[:3]):
            m = re.match(r"^#?\s*(\d{1,3})(?:st|nd|rd|th)?\b", cell or "", flags=re.I)
            if m:
                rank = int(m.group(1))
                rank_idx = idx
                break
        if rank_idx is None or not (1 <= rank <= 10):
            continue

        title = ""
        vote = ""
        for cell in row[rank_idx + 1:]:
            clean = re.sub(r"\s+", " ", cell or "").strip()
            if not clean:
                continue
            vm = re.search(r"\b\d{1,3}(?:\.\d{1,2})?%", clean)
            if vm and not vote:
                vote = vm.group(0)
                continue
            if not title and not re.fullmatch(r"(?:NEW|—|-|\+?\d+|↓+\s*\d+|↑+\s*\d+)", clean, flags=re.I):
                title = clean
        if title and rank not in found:
            found[rank] = {"rank": rank, "title": title[:220], "detail": vote, "image_url": ""}
    return [found[r] for r in range(1, 11) if r in found]

def _animecorner_winner_from_summary(summary: str) -> str:
    text = re.sub(r"\s+", " ", summary or "").strip()
    patterns = [
        r"(?:with|and)\s+(.{2,110}?)\s+(?:taking|claiming|securing)\s+(?:first place|the top spot)",
        r"(?:with|and)\s+(.{2,110}?)\s+has\s+(?:returned|climbed|risen)\s+to\s+(?:the top|first place)",
        r"\b(.{2,110}?)\s+(?:took|takes|claimed|claims)\s+(?:first place|the top spot)\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            value = m.group(1).strip(" ,:-–—")
            if 2 <= len(value) <= 100:
                return value
    return ""

def _animecorner_photo_bytes(url: str, max_bytes: int = 8_000_000) -> bytes:
    """تصویر رسمی Ranking را خود بات دانلود می‌کند تا Hotlink/Telegram fetch مانع ارسال عکس نشود."""
    if not _news_safe_url(url):
        raise ValueError("Anime Corner image URL نامعتبر است.")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
            "Accept": "image/webp,image/png,image/jpeg,image/*;q=0.8,*/*;q=0.5",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://animecorner.me/",
        },
    )
    with urllib.request.urlopen(req, timeout=NEWS_HTTP_TIMEOUT) as resp:
        raw = resp.read(max_bytes + 1)
    if not raw or len(raw) > max_bytes:
        raise ValueError("Anime Corner ranking image خالی یا بیش از حد بزرگ است.")

    # برای اطمینان از سازگاری با Telegram، WEBP/PNG/AVIF را در صورت وجود Pillow به JPEG تبدیل کن.
    if Image is not None:
        try:
            im = Image.open(io.BytesIO(raw))
            im.load()
            if im.mode in ("RGBA", "LA"):
                bg = Image.new("RGB", im.size, (255, 255, 255))
                alpha = im.getchannel("A") if "A" in im.getbands() else None
                bg.paste(im, mask=alpha)
                im = bg
            else:
                im = im.convert("RGB")
            out = io.BytesIO()
            im.save(out, format="JPEG", quality=92, optimize=True)
            return out.getvalue()
        except Exception as e:
            logger.info("Anime Corner image JPEG conversion skipped: %s", e)
    return raw

def _animecorner_build_chart_card(url: str, ranking_payload: str = "") -> str | None:
    """کارت Top 10 Anime Corner با چیدمان نزدیک به MAL و تم قرمز."""
    if Image is None or ImageDraw is None or ImageOps is None:
        return None
    chart = None
    if ranking_payload:
        try:
            obj = json.loads(ranking_payload)
            if isinstance(obj, dict):
                chart = obj
        except Exception:
            chart = None
    if not chart:
        return None

    entries = []
    for raw_entry in chart.get("entries") or []:
        try:
            rank = int(raw_entry.get("rank") or 0)
        except Exception:
            rank = 0
        if 1 <= rank <= 10:
            entries.append({
                "rank": rank,
                "title": re.sub(r"\s+", " ", str(raw_entry.get("title") or "")).strip(),
                "detail": re.sub(r"\s+", " ", str(raw_entry.get("detail") or "")).strip(),
                "image_url": (raw_entry.get("image_url") or "").strip(),
            })
    entries.sort(key=lambda e: e.get("rank") or 999)
    ranks = {int(e.get("rank") or 0) for e in entries}
    if ranks != set(range(1, 11)):
        logger.warning("Anime Corner card skipped because Top 10 is incomplete: %s", sorted(ranks))
        return None

    if any(not (e.get("image_url") or "").strip() for e in entries):
        poll_url = (chart.get("poll_url") or "").strip()
        if not poll_url:
            try:
                poll_url = _animecorner_default_poll_results_url(chart.get("season") or "", int(chart.get("year") or 0), int(chart.get("week") or 0))
            except Exception:
                poll_url = ""
        if poll_url:
            try:
                media_by_rank = _animecorner_results_media(poll_url)
            except Exception:
                media_by_rank = {}
            for entry in entries:
                match = media_by_rank.get(int(entry.get("rank") or 0))
                if not match:
                    continue
                if not entry.get("image_url") and (match.get("image_url") or "").strip():
                    entry["image_url"] = (match.get("image_url") or "").strip()
                if not entry.get("detail") and (match.get("detail") or "").strip():
                    entry["detail"] = re.sub(r"\s+", " ", str(match.get("detail") or "")).strip()

    def extract_percent(detail: str) -> str:
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", detail or "")
        return (m.group(1) + "%") if m else (detail or "").strip()

    year = chart.get("year") or ""
    week = chart.get("week") or "?"
    season = (chart.get("season") or "").upper()
    rows = [{
        "rank": int(entry.get("rank") or (i + 1)),
        "title": entry.get("title"),
        "image_url": entry.get("image_url"),
        "stat_label": "Vote share",
        "stat_value": extract_percent(entry.get("detail") or ""),
    } for i, entry in enumerate(entries)]
    return _ranking_render_card(
        "animecorner", "Top Anime", f"{season} {year}  ·  WEEK {week}".strip(), rows,
        image_loader=lambda u: _animecorner_photo_bytes(u, max_bytes=5_000_000),
        footer_note="Weekly Anime Corner poll", file_prefix="ariko_animecorner_",
    )

def _animecorner_collect_current() -> list:
    """جدیدترین Top 10 هفتگی Anime Corner + تصویر رسمی مقاله را برمی‌گرداند."""
    latest = _animecorner_find_latest_weekly_article()
    data, _ct, final_url = _news_fetch(latest["url"], max_bytes=5_000_000)
    html_text = data.decode("utf-8", errors="ignore")

    meta_parser = _NewsMetaParser()
    meta_parser.feed(html_text)
    meta = meta_parser.meta
    published = (meta.get("article:published_time") or meta.get("date") or meta.get("datepublished") or "").strip()
    official_image = (meta.get("og:image") or meta.get("twitter:image") or "").strip()
    if official_image:
        official_image = urllib.parse.urljoin(final_url, official_image)
        if not _news_safe_url(official_image):
            official_image = ""

    base_item = {
        "guid": "",
        "title": latest["title"],
        "url": final_url,
        "published_at": published,
        "summary": "",
        "article_text": "",
        "image_url": official_image,
        "video_url": "",
        "trailer_url": "",
        "news_type": "ranking",
        "ranking_payload": "",
    }
    base_item = _news_enrich_article(base_item)
    if official_image:
        # Featured image مقاله Ranking همان گرافیک رسمی جدول است؛ آن را بر انتخاب‌های جانبی ترجیح بده.
        base_item["image_url"] = official_image

    entries = _animecorner_top10_from_html(html_text)

    season = latest["season"]
    year = latest["year"]
    week = latest["week"]
    poll_url = (latest.get("poll_url") or _animecorner_default_poll_results_url(season, year, week)).strip()

    # درست مثل AniTrendz، Snapshot خبر باید عکس همان 10 ردیف را هم نگه دارد.
    # عکس‌ها از صفحه Results رسمی Anime Corner گرفته می‌شوند؛ جدول مقاله title/vote دقیق را می‌دهد.
    if entries:
        media_by_rank = _animecorner_results_media(poll_url)
        for entry in entries:
            match = media_by_rank.get(int(entry.get("rank") or 0))
            if not match:
                continue
            if not (entry.get("image_url") or "").strip() and (match.get("image_url") or "").strip():
                entry["image_url"] = match["image_url"]
            if not (entry.get("detail") or "").strip() and (match.get("detail") or "").strip():
                entry["detail"] = match["detail"]
            if not (entry.get("title") or "").strip() and (match.get("title") or "").strip():
                entry["title"] = match["title"]
            if (match.get("performance_url") or "").strip():
                entry["performance_url"] = (match.get("performance_url") or "").strip()

    winner = entries[0]["title"] if entries and entries[0].get("rank") == 1 else _animecorner_winner_from_summary(base_item.get("summary", ""))
    winner_vote = entries[0].get("detail", "") if entries and entries[0].get("rank") == 1 else ""
    if winner:
        synthetic_title = f"{winner} tops Anime Corner Anime Rankings Week {week} {season} {year}"
    else:
        synthetic_title = f"Anime Corner Anime Rankings Week {week} {season} {year}"

    top_parts = []
    for e in entries:
        vote = f" — {e.get('detail')}" if e.get("detail") else ""
        top_parts.append(f"#{e.get('rank')} {e.get('title')}{vote}")
    ranking_summary = f"Anime Corner {season} {year} Week {week} rankings. " + " | ".join(top_parts)
    if not top_parts and base_item.get("summary"):
        ranking_summary += " " + base_item["summary"][:1800]
    elif winner_vote and winner and winner_vote not in ranking_summary:
        ranking_summary += f" #1 {winner} — {winner_vote}"

    payload = {
        "source": "animecorner",
        "chart_type": "anime",
        "week": week,
        "season": season,
        "year": year,
        "url": final_url,
        "poll_url": poll_url,
        "entries": entries,
    }

    base_item.update({
        # v50: کارت اختصاصی شبیه AniTrendz + عکس هر ردیف؛ یک‌بار دوباره ساخته شود.
        "guid": f"animecorner-weekly:v50:{year}:{season.lower()}:week-{week}",
        "title": synthetic_title,
        "summary": ranking_summary[:5000],
        "news_type": "ranking",
        "ranking_payload": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    })
    return [base_item]

def _mal_photo_bytes(url: str, max_bytes: int = 5_000_000) -> bytes:
    """عکس کاور MAL/CDN را برای کارت رتبه‌بندی دانلود می‌کند."""
    if not _news_safe_url(url):
        raise ValueError("MyAnimeList image URL نامعتبر است.")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
            "Accept": "image/webp,image/png,image/jpeg,image/*;q=0.8,*/*;q=0.5",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://myanimelist.net/",
        },
    )
    with urllib.request.urlopen(req, timeout=NEWS_HTTP_TIMEOUT) as resp:
        raw = resp.read(max_bytes + 1)
    if not raw or len(raw) > max_bytes:
        raise ValueError("MyAnimeList image خالی یا بیش از حد بزرگ است.")
    return raw

def _mal_resolve_entry_image_url(entry: dict) -> str:
    """اگر image_url خالی بود، از Jikan anime/full یا خود صفحه MAL عکس را پیدا می‌کند."""
    image_url = (entry.get("image_url") or "").strip()
    if image_url and _news_safe_url(image_url):
        return image_url
    try:
        mal_id = int(entry.get("mal_id") or 0)
    except Exception:
        mal_id = 0
    mal_url = (entry.get("mal_url") or "").strip()
    if mal_id > 0:
        api_url = f"https://api.jikan.moe/v4/anime/{mal_id}/full"
        try:
            req = urllib.request.Request(api_url, headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json,text/plain;q=0.8,*/*;q=0.5",
            })
            with urllib.request.urlopen(req, timeout=max(NEWS_HTTP_TIMEOUT, 20)) as resp:
                raw = resp.read(2_500_000)
            obj = json.loads(raw.decode("utf-8", errors="ignore"))
            data = obj.get("data") or {}
            images = data.get("images") or {}
            for fmt in ("jpg", "webp"):
                block = images.get(fmt) if isinstance(images, dict) else None
                if not isinstance(block, dict):
                    continue
                candidate = (
                    block.get("large_image_url")
                    or block.get("image_url")
                    or block.get("small_image_url")
                    or ""
                ).strip()
                if candidate and _news_safe_url(candidate):
                    return candidate
        except Exception as e:
            logger.info("MAL image fallback Jikan failed id=%s: %s", mal_id, e)
    if mal_url and _news_safe_url(mal_url):
        try:
            req = urllib.request.Request(mal_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=max(NEWS_HTTP_TIMEOUT, 20)) as resp:
                raw = resp.read(1_500_000)
                final_url = resp.geturl()
            html_text = raw.decode("utf-8", errors="ignore")
            meta_candidates = re.findall(r"<meta[^>]+(?:property|name)=[\"'](?:og:image|twitter:image)[\"'][^>]+content=[\"']([^\"']+)[\"']", html_text, flags=re.I)
            for candidate in meta_candidates:
                candidate = urllib.parse.urljoin(final_url, unescape(candidate).strip())
                if candidate and _news_safe_url(candidate):
                    return candidate
            for m in re.finditer(r"(?:data-src|data-lazy-src|src)=[\"']([^\"']+)[\"']", html_text, flags=re.I):
                candidate = urllib.parse.urljoin(final_url, unescape(m.group(1)).strip())
                low = candidate.lower()
                if ("myanimelist.net/images/anime/" in low or "cdn.myanimelist.net/images/anime/" in low) and _news_safe_url(candidate):
                    return candidate
        except Exception as e:
            logger.info("MAL image fallback HTML failed url=%s: %s", mal_url, e)
    return ""

def _mal_top_html_to_jikan_like(page_url: str, label: str) -> dict:
    """Fallback مستقیم از صفحه Top Anime خود MyAnimeList وقتی Jikan موقتاً 5xx/504 می‌دهد."""
    if not _news_safe_url(page_url):
        raise ValueError("MyAnimeList Top page URL نامعتبر است.")
    req = urllib.request.Request(
        page_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=max(NEWS_HTTP_TIMEOUT, 25)) as resp:
        raw = resp.read(4_500_000)
        final_url = resp.geturl()
    html_text = raw.decode("utf-8", errors="ignore")

    rows = re.findall(r'<tr[^>]+class=["\'][^"\']*ranking-list[^"\']*["\'][^>]*>(.*?)</tr>', html_text, flags=re.I | re.S)
    data = []
    for block in rows:
        rm = re.search(r'top-anime-rank-text[^>]*>\s*(\d+)', block, flags=re.I | re.S)
        tm = re.search(r'anime_ranking_h3[^>]*>.*?<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block, flags=re.I | re.S)
        sm = re.search(r'score-label[^>]*>\s*([0-9]+(?:\.[0-9]+)?)\s*<', block, flags=re.I | re.S)
        if not rm or not tm:
            continue
        rank = int(rm.group(1))
        title = _news_strip_html(tm.group(2))
        anime_url = urllib.parse.urljoin(final_url, unescape(tm.group(1)))
        image_url = ""
        for im in re.finditer(r'(?:data-src|data-lazy-src|src)=["\']([^"\']+)["\']', block, flags=re.I):
            candidate = unescape(im.group(1)).strip()
            if "myanimelist.net/images/anime/" in candidate.lower() or "cdn.myanimelist.net/images/anime/" in candidate.lower():
                image_url = urllib.parse.urljoin(final_url, candidate)
                break
        score = float(sm.group(1)) if sm else 0.0
        data.append({
            "mal_id": 0,
            "title": title,
            "title_english": title,
            "score": score,
            # در fallback HTML فقط رتبه همان Top page قطعی است.
            "rank": rank,
            "scored_by": 0,
            "members": 0,
            "url": anime_url,
            "images": {"jpg": {"large_image_url": image_url, "image_url": image_url}},
            "_mal_html_fallback": True,
        })
        if len(data) >= 10:
            break
    if len(data) < 10:
        raise ValueError(f"Fallback مستقیم MyAnimeList هم Top 10 کامل نداد (count={len(data)}, {label}).")
    return {"data": data, "_source": "myanimelist_html_fallback"}

def _mal_latest_cached_weekly_item() -> dict | None:
    """آخرین Snapshot هفتگی MAL در DB؛ فقط برای پیش‌نمایش وقتی سرویس زنده موقتاً قطع است."""
    try:
        conn = db()
        rows = conn.execute(
            "SELECT title,url,ranking_payload FROM news_items WHERE news_type='ranking' AND ranking_payload IS NOT NULL ORDER BY id DESC LIMIT 80"
        ).fetchall()
        conn.close()
        for row in rows:
            payload = row["ranking_payload"] or ""
            if '"ranking_kind":"top_airing_weekly_snapshot"' in payload or '"ranking_kind": "top_airing_weekly_snapshot"' in payload:
                return {"title": row["title"] or "MyAnimeList Top Airing", "url": row["url"] or MAL_TOP_AIRING_URL, "ranking_payload": payload}
    except Exception as e:
        logger.info("MAL cached weekly lookup failed: %s", e)
    return None

def _mal_fetch_top_json(api_url: str, label: str) -> dict:
    """Top 10 را با retry واقعی می‌گیرد؛ 504/5xx Jikan به MAL HTML مستقیم fallback می‌شود."""
    last_error = None
    retryable = {429, 500, 502, 503, 504, 520, 522, 524}

    # همان endpoint بدون limit یک cache-key متفاوت در Jikan دارد و هنگام 504 گاهی سالم است.
    variants = [api_url]
    alt = re.sub(r'([?&])limit=10(?:&|$)', lambda m: m.group(1) if m.group(0).endswith('&') else '', api_url).rstrip('?&')
    if alt and alt not in variants:
        variants.append(alt)

    for attempt in range(4):
        candidate = variants[attempt % len(variants)]
        try:
            req = urllib.request.Request(
                candidate,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
                    "Accept": "application/json,text/plain,*/*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=max(NEWS_HTTP_TIMEOUT, 25)) as resp:
                data = resp.read(2_500_000)
            obj = json.loads(data.decode("utf-8", errors="ignore"))
            if not isinstance(obj, dict) or not isinstance(obj.get("data"), list) or len(obj.get("data") or []) < 10:
                raise ValueError("پاسخ Jikan ساختار معتبر Top 10 ندارد.")
            return obj
        except urllib.error.HTTPError as e:
            last_error = e
            code = int(getattr(e, "code", 0) or 0)
            if code in retryable and attempt < 3:
                time.sleep((1.5, 3.0, 5.5)[min(attempt, 2)])
                continue
            break
        except (urllib.error.URLError, TimeoutError) as e:
            last_error = e
            if attempt < 3:
                time.sleep((1.5, 3.0, 5.5)[min(attempt, 2)])
                continue
            break
        except Exception as e:
            last_error = e
            if attempt < 2:
                time.sleep(1.5 + attempt * 1.5)
                continue
            break

    # Jikan هنوز down است: داده را از صفحه رسمی خود MAL بگیر.
    try:
        page_url = MAL_TOP_AIRING_URL if "airing" in (api_url or "").lower() else MAL_TOP_ALLTIME_URL
        logger.warning("Jikan %s unavailable (%s); trying MyAnimeList HTML fallback", label, last_error)
        return _mal_top_html_to_jikan_like(page_url, label)
    except Exception as fallback_error:
        raise RuntimeError(f"MyAnimeList {label} دریافت نشد؛ Jikan: {last_error} | MAL fallback: {fallback_error}")

def _mal_fetch_top_airing_json() -> dict:
    return _mal_fetch_top_json(MAL_JIKAN_TOP_AIRING_API, "Top Airing")

def _mal_fetch_top_alltime_json() -> dict:
    return _mal_fetch_top_json(MAL_JIKAN_TOP_ALLTIME_API, "Top Anime")

def _mal_collect_weekly_top_airing() -> list:
    """هفته‌ای یک Snapshot از Top 10 انیمه‌های در حال پخش MyAnimeList می‌سازد.

    توجه: MyAnimeList نظرسنجی هفتگی مستقل مثل AniTrendz/Anime Corner ندارد؛
    این خروجی Snapshot هفتگی از رنکینگ جاری Top Airing بر اساس امتیاز MAL است.
    """
    obj = _mal_fetch_top_airing_json()
    raw_items = obj.get("data") or []
    html_fallback = (obj.get("_source") == "myanimelist_html_fallback")
    if len(raw_items) < 10:
        raise ValueError(f"Top 10 کامل MyAnimeList دریافت نشد (count={len(raw_items)}).")

    entries = []
    for idx, anime in enumerate(raw_items[:10], start=1):
        if not isinstance(anime, dict):
            continue
        title = (anime.get("title_english") or anime.get("title") or "").strip()
        if not title:
            continue
        try:
            score = float(anime.get("score") or 0)
        except Exception:
            score = 0.0
        try:
            mal_rank = int(anime.get("rank") or 0)
        except Exception:
            mal_rank = 0
        try:
            scored_by = int(anime.get("scored_by") or 0)
        except Exception:
            scored_by = 0
        try:
            members = int(anime.get("members") or 0)
        except Exception:
            members = 0

        image_url = ""
        images = anime.get("images") or {}
        for fmt in ("jpg", "webp"):
            block = images.get(fmt) if isinstance(images, dict) else None
            if not isinstance(block, dict):
                continue
            image_url = (
                block.get("large_image_url")
                or block.get("image_url")
                or block.get("small_image_url")
                or ""
            ).strip()
            if image_url:
                break

        entries.append({
            "rank": idx,
            "title": title,
            "score": score,
            "mal_rank": mal_rank,
            "scored_by": scored_by,
            "members": members,
            "image_url": image_url,
            "mal_url": (anime.get("url") or "").strip(),
        })

    if len(entries) != 10 or {e["rank"] for e in entries} != set(range(1, 11)):
        raise ValueError("Top 10 کامل MyAnimeList قابل ساخت نیست.")

    now = datetime.now()
    iso = now.isocalendar()
    iso_year = int(iso[0])
    iso_week = int(iso[1])
    winner = entries[0]["title"]
    winner_score = entries[0]["score"]

    summary_parts = []
    for e in entries:
        score_txt = f"{e['score']:.2f}" if e.get("score") else "N/A"
        summary_parts.append(f"{e['rank']}. {e['title']} — SCORE {score_txt}")

    payload = {
        "source": "myanimelist",
        "chart_type": "anime",
        "ranking_kind": "top_airing_weekly_snapshot",
        "week": iso_week,
        "year": iso_year,
        "url": MAL_TOP_AIRING_URL,
        "entries": entries,
    }

    title = f"{winner} tops MyAnimeList Top Airing Anime Rankings Week {iso_week} {iso_year}"
    summary = "MyAnimeList Top Airing weekly snapshot. " + " | ".join(summary_parts)
    image_url = entries[0].get("image_url") or ""

    return [{
        "guid": f"mal-top-airing:v54:{iso_year}:week-{iso_week}",
        "title": title,
        "url": MAL_TOP_AIRING_URL,
        "published_at": now.isoformat(),
        "summary": summary[:5000],
        "article_text": "",
        "image_url": image_url,
        "video_url": "",
        "trailer_url": "",
        "news_type": "ranking",
        "ranking_payload": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    }]

def _mal_parse_top_entries(obj: dict, html_fallback: bool = False) -> list:
    """ده ردیف اول Jikan را به ساختار مشترک کارت MAL تبدیل می‌کند."""
    raw_items = obj.get("data") or []
    if len(raw_items) < 10:
        raise ValueError(f"Top 10 کامل MyAnimeList دریافت نشد (count={len(raw_items)}).")

    entries = []
    for idx, anime in enumerate(raw_items[:10], start=1):
        if not isinstance(anime, dict):
            continue
        title = (anime.get("title_english") or anime.get("title") or "").strip()
        if not title:
            continue
        try:
            mal_id = int(anime.get("mal_id") or 0)
        except Exception:
            mal_id = 0
        try:
            score = float(anime.get("score") or 0)
        except Exception:
            score = 0.0
        try:
            mal_rank = 0 if html_fallback else int(anime.get("rank") or idx)
        except Exception:
            mal_rank = 0 if html_fallback else idx
        try:
            scored_by = int(anime.get("scored_by") or 0)
        except Exception:
            scored_by = 0
        try:
            members = int(anime.get("members") or 0)
        except Exception:
            members = 0

        image_url = ""
        images = anime.get("images") or {}
        for fmt in ("jpg", "webp"):
            block = images.get(fmt) if isinstance(images, dict) else None
            if not isinstance(block, dict):
                continue
            image_url = (
                block.get("large_image_url")
                or block.get("image_url")
                or block.get("small_image_url")
                or ""
            ).strip()
            if image_url:
                break

        entries.append({
            "rank": idx,
            "mal_id": mal_id,
            "title": title,
            "score": score,
            "mal_rank": mal_rank,
            "scored_by": scored_by,
            "members": members,
            "image_url": image_url,
            "mal_url": (anime.get("url") or "").strip(),
        })

    if len(entries) != 10 or {e["rank"] for e in entries} != set(range(1, 11)):
        raise ValueError("Top 10 کامل MyAnimeList قابل ساخت نیست.")
    return entries

def _mal_alltime_entry_key(entry: dict) -> str:
    mal_id = int(entry.get("mal_id") or 0)
    if mal_id > 0:
        return f"id:{mal_id}"
    title = re.sub(r"\s+", " ", str(entry.get("title") or "")).strip().casefold()
    return f"title:{title}"

def _mal_load_alltime_snapshot() -> list:
    raw = get_setting(MAL_TOP_ALLTIME_SNAPSHOT_KEY, "")
    if not raw:
        return []
    try:
        obj = json.loads(raw)
        rows = obj.get("entries") if isinstance(obj, dict) else obj
        if not isinstance(rows, list):
            return []
        clean = []
        for row in rows[:10]:
            if not isinstance(row, dict):
                continue
            clean.append({
                "rank": int(row.get("rank") or len(clean) + 1),
                "mal_id": int(row.get("mal_id") or 0),
                "title": str(row.get("title") or "").strip(),
                "score": float(row.get("score") or 0),
            })
        return clean if len(clean) == 10 else []
    except Exception:
        return []

def _mal_save_alltime_snapshot(entries: list):
    payload = {
        "saved_at": datetime.now().isoformat(),
        "entries": [
            {
                "rank": int(e.get("rank") or i + 1),
                "mal_id": int(e.get("mal_id") or 0),
                "title": str(e.get("title") or "").strip(),
                "score": float(e.get("score") or 0),
            }
            for i, e in enumerate(entries[:10])
        ],
    }
    set_setting(MAL_TOP_ALLTIME_SNAPSHOT_KEY, json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

def _mal_build_alltime_item(entries: list, previous: list | None = None, initial: bool = False) -> dict:
    previous = previous or []
    prev_pos = {_mal_alltime_entry_key(e): int(e.get("rank") or 0) for e in previous}

    changed_count = 0
    enriched = []
    for e in entries:
        row = dict(e)
        old_rank = prev_pos.get(_mal_alltime_entry_key(e))
        row["previous_rank"] = int(old_rank or 0)
        if not initial and old_rank != int(e.get("rank") or 0):
            changed_count += 1
        enriched.append(row)

    winner = enriched[0]["title"]
    winner_score = enriched[0].get("score") or 0
    now = datetime.now()
    signature = "|".join(_mal_alltime_entry_key(e) for e in enriched)
    sig_hash = hashlib.sha1(signature.encode("utf-8", errors="ignore")).hexdigest()[:12]

    summary_parts = []
    for e in enriched:
        score_txt = f"{e['score']:.2f}" if e.get("score") else "N/A"
        old_rank = int(e.get("previous_rank") or 0)
        new_rank = int(e.get("rank") or 0)
        if initial:
            move = "CURRENT"
        elif old_rank <= 0:
            move = f"NEW->{new_rank}"
        elif old_rank == new_rank:
            move = "SAME"
        else:
            move = f"{old_rank}->{new_rank}"
        summary_parts.append(f"{new_rank}. {e['title']} — SCORE {score_txt} — MOVE {move}")

    payload = {
        "source": "myanimelist",
        "chart_type": "anime",
        "ranking_kind": "top_alltime_change",
        "change_mode": "initial" if initial else "changed",
        "changed_count": changed_count,
        "year": now.year,
        "url": MAL_TOP_ALLTIME_URL,
        "entries": enriched,
    }
    title = f"{winner} tops MyAnimeList Top Anime Rankings"
    summary_prefix = "MyAnimeList Top Anime initial snapshot." if initial else "MyAnimeList Top Anime ranking change."
    summary = summary_prefix + " " + " | ".join(summary_parts)
    guid_mode = "initial" if initial else now.strftime("%Y%m%dT%H%M%S")

    return {
        "guid": f"mal-top-alltime:v55:{guid_mode}:{sig_hash}",
        "title": title,
        "url": MAL_TOP_ALLTIME_URL,
        "published_at": now.isoformat(),
        "summary": summary[:5000],
        "article_text": "",
        "image_url": enriched[0].get("image_url") or "",
        "video_url": "",
        "trailer_url": "",
        "news_type": "ranking",
        "ranking_payload": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    }

def _mal_collect_top_alltime_change(force_preview: bool = False) -> tuple[list, list]:
    """Top 10 کل تاریخ MAL را می‌گیرد و فقط اگر ترتیب ده‌تای اول عوض شده باشد Item می‌سازد.

    خروجی دوم snapshot جاری است تا Poll فقط بعد از ثبت موفق خبر آن را در settings ذخیره کند.
    در اولین اجرا یک Snapshot اولیه فرستاده می‌شود؛ بعد از آن صرفاً تغییر ترتیب باعث پست می‌شود.
    """
    entries = _mal_parse_top_entries(_mal_fetch_top_alltime_json())
    previous = _mal_load_alltime_snapshot()

    if force_preview:
        return [_mal_build_alltime_item(entries, previous=[], initial=True)], entries

    if not previous:
        return [_mal_build_alltime_item(entries, previous=[], initial=True)], entries

    old_order = [_mal_alltime_entry_key(e) for e in previous]
    new_order = [_mal_alltime_entry_key(e) for e in entries]
    if old_order == new_order:
        return [], entries

    return [_mal_build_alltime_item(entries, previous=previous, initial=False)], entries

def _mal_build_chart_card(ranking_payload: str = "") -> str | None:
    """کارت Top 10 آبی MyAnimeList برای Snapshot هفتگی Top Airing و Top Anime کلی."""
    if Image is None or ImageDraw is None or ImageOps is None or not ranking_payload:
        return None
    try:
        chart = json.loads(ranking_payload)
    except Exception:
        return None
    if not isinstance(chart, dict):
        return None

    entries = []
    for raw_entry in chart.get("entries") or []:
        try:
            rank = int(raw_entry.get("rank") or 0)
        except Exception:
            rank = 0
        if not (1 <= rank <= 10):
            continue
        try:
            score = float(raw_entry.get("score") or 0)
        except Exception:
            score = 0.0
        try:
            mal_rank = int(raw_entry.get("mal_rank") or 0)
        except Exception:
            mal_rank = 0
        try:
            previous_rank = int(raw_entry.get("previous_rank") or 0)
        except Exception:
            previous_rank = 0
        try:
            mal_id = int(raw_entry.get("mal_id") or 0)
        except Exception:
            mal_id = 0
        entries.append({
            "rank": rank,
            "title": re.sub(r"\s+", " ", str(raw_entry.get("title") or "")).strip(),
            "score": score,
            "mal_rank": mal_rank,
            "previous_rank": previous_rank,
            "mal_id": mal_id,
            "mal_url": (raw_entry.get("mal_url") or "").strip(),
            "image_url": (raw_entry.get("image_url") or "").strip(),
        })
    entries.sort(key=lambda e: e["rank"])
    if len(entries) != 10 or {e["rank"] for e in entries} != set(range(1, 11)):
        logger.warning("MAL card skipped because Top 10 is incomplete: %s", [e.get("rank") for e in entries])
        return None

    if any(not (e.get("image_url") or "").strip() for e in entries):
        for entry in entries:
            if (entry.get("image_url") or "").strip():
                continue
            try:
                entry["image_url"] = _mal_resolve_entry_image_url(entry)
            except Exception as e:
                logger.info("MAL image enrich failed rank=%s: %s", entry.get("rank"), e)

    ranking_kind = (chart.get("ranking_kind") or "top_airing_weekly_snapshot").strip()
    is_alltime = ranking_kind == "top_alltime_change"
    change_mode = (chart.get("change_mode") or "").strip()
    year = chart.get("year") or ""
    week = chart.get("week") or "?"
    if is_alltime:
        heading = "Top Anime · All-time"
        subheading = "Current baseline" if change_mode == "initial" else "Ranking change detected"
        footer_note = "Sent only when the Top 10 changes"
    else:
        heading = "Top Airing"
        subheading = f"WEEK {week}  ·  {year}"
        footer_note = "Weekly snapshot of Top Airing"

    green, red, soft = (91, 205, 142), (244, 111, 118), (150, 160, 176)
    rows = []
    for entry in entries:
        rank = entry["rank"]
        if is_alltime:
            old_rank = int(entry.get("previous_rank") or 0)
            if change_mode == "initial" or old_rank == rank:
                note, color = "", soft
            elif old_rank <= 0:
                note, color = "NEW", green
            elif old_rank > rank:
                note, color = f"▲ from #{old_rank}", green
            else:
                note, color = f"▼ from #{old_rank}", red
        else:
            note, color = (f"Global #{entry['mal_rank']}" if entry.get("mal_rank") else ""), soft
        rows.append({
            "rank": rank,
            "title": entry.get("title"),
            "image_url": entry.get("image_url"),
            "stat_label": "Score",
            "stat_value": f"{entry['score']:.2f}" if entry.get("score") else "N/A",
            "note": note,
            "note_color": color,
        })
    return _ranking_render_card(
        "mal", heading, subheading, rows, image_loader=_mal_photo_bytes,
        footer_note=footer_note, file_prefix="ariko_mal_card_",
    )

def _poll_mal_top_airing_source(source_row, bootstrap: bool = False):
    """Snapshot هفتگی Top Airing MAL را مستقل از RSS اخبار MyAnimeList ثبت می‌کند."""
    source_id = source_row["id"]
    try:
        items = _mal_collect_weekly_top_airing()
    except Exception as e:
        _news_mark_source_checked(source_id, str(e))
        logger.warning("MyAnimeList Top Airing source failed: %s", e)
        return {"new": 0, "seeded": 0, "duplicate": 0, "error": str(e)}

    new_count = 0
    for item in items:
        conn = db()
        exists = conn.execute(
            "SELECT 1 FROM news_items WHERE source_id=? AND guid=?",
            (source_id, item["guid"]),
        ).fetchone()
        conn.close()
        if exists:
            continue
        item["news_type"] = "ranking"
        item_id = _news_insert_item(source_id, item, status="queued")
        if item_id:
            new_count += 1
            _send_news_item_to_archive(item_id)

    _news_mark_source_checked(source_id, "")
    return {"new": new_count, "seeded": 0, "duplicate": 0, "error": ""}

def _poll_mal_top_alltime_source(source_row, bootstrap: bool = False):
    """Top 10 کل تاریخ MAL را بررسی می‌کند؛ بعد از Snapshot اول فقط تغییر رتبه پست می‌شود."""
    source_id = source_row["id"]
    try:
        items, current_snapshot = _mal_collect_top_alltime_change(force_preview=False)
    except Exception as e:
        _news_mark_source_checked(source_id, str(e))
        logger.warning("MyAnimeList Top Anime change source failed: %s", e)
        return {"new": 0, "seeded": 0, "duplicate": 0, "error": str(e)}

    # هیچ تغییری در ترتیب Top 10 نیست؛ هیچ پستی نساز. Scoreهای جدید را فقط در Snapshot نگه دار.
    if not items:
        _mal_save_alltime_snapshot(current_snapshot)
        _news_mark_source_checked(source_id, "")
        return {"new": 0, "seeded": 0, "duplicate": 1, "error": ""}

    new_count = 0
    persisted = False
    for item in items:
        conn = db()
        exists = conn.execute(
            "SELECT 1 FROM news_items WHERE source_id=? AND guid=?",
            (source_id, item["guid"]),
        ).fetchone()
        conn.close()
        if exists:
            persisted = True
            continue
        item["news_type"] = "ranking"
        item_id = _news_insert_item(source_id, item, status="queued")
        if item_id:
            persisted = True
            new_count += 1
            _send_news_item_to_archive(item_id)

    # فقط وقتی Snapshot خبر واقعاً در DB ثبت شده (یا از قبل وجود داشته) مبنا را جلو ببر.
    if persisted:
        _mal_save_alltime_snapshot(current_snapshot)
    _news_mark_source_checked(source_id, "" if persisted else "Top Anime snapshot could not be persisted")
    return {"new": new_count, "seeded": 0, "duplicate": 0, "error": "" if persisted else "snapshot not persisted"}

def _poll_animecorner_source(source_row, bootstrap: bool = False):
    """Anime Corner Weekly را مستقل از خبرهای عادی می‌گیرد؛ اولین اجرا هم آخرین Week را یک بار می‌فرستد."""
    source_id = source_row["id"]
    try:
        items = _animecorner_collect_current()
    except Exception as e:
        _news_mark_source_checked(source_id, str(e))
        logger.warning("Anime Corner weekly source failed: %s", e)
        return {"new": 0, "seeded": 0, "duplicate": 0, "error": str(e)}

    new_count = 0
    for item in items:
        conn = db()
        exists = conn.execute(
            "SELECT 1 FROM news_items WHERE source_id=? AND guid=?",
            (source_id, item["guid"]),
        ).fetchone()
        conn.close()
        if exists:
            continue
        item["news_type"] = "ranking"
        item_id = _news_insert_item(source_id, item, status="queued")
        if item_id:
            new_count += 1
            _send_news_item_to_archive(item_id)

    _news_mark_source_checked(source_id, "")
    return {"new": new_count, "seeded": 0, "duplicate": 0, "error": ""}

def _news_parse_feed(feed_url: str):
    feed_value = (feed_url or "").strip()
    if feed_value == ANITRENDZ_SPECIAL_FEED:
        return _anitrendz_collect_current()
    if feed_value == ANIMECORNER_SPECIAL_FEED:
        return _animecorner_collect_current()
    if feed_value == MAL_TOP_AIRING_SPECIAL_FEED:
        return _mal_collect_weekly_top_airing()
    if feed_value == MAL_TOP_ALLTIME_SPECIAL_FEED:
        items, _snapshot = _mal_collect_top_alltime_change(force_preview=True)
        return items
    x_handle = _x_leaker_handle_from_feed(feed_value)
    if x_handle:
        return _x_leaker_collect(x_handle)
    ig_user = _instagram_username_from_feed(feed_value)
    if ig_user:
        return _instagram_collect(ig_user)
    data, _ct, final_url = _news_fetch(feed_url, max_bytes=3_000_000)
    root = ET.fromstring(data)
    entries = []

    root_name = _news_local_name(root.tag)
    if root_name == "feed":
        nodes = [n for n in list(root) if _news_local_name(n.tag) == "entry"]
    else:
        nodes = [n for n in root.iter() if _news_local_name(n.tag) == "item"]

    for item in nodes[:80]:
        title = _news_strip_html(_news_child_text(item, {"title"}))
        if not title:
            continue

        link = ""
        for ch in list(item):
            if _news_local_name(ch.tag) == "link":
                href = (ch.attrib.get("href") or "").strip()
                rel = (ch.attrib.get("rel") or "alternate").lower()
                if href and rel in ("", "alternate"):
                    link = href
                    break
                if not href and (ch.text or "").strip():
                    link = (ch.text or "").strip()
                    break
        if not link:
            link = _news_child_text(item, {"link"})
        link = urllib.parse.urljoin(final_url, link)
        if not _news_safe_url(link):
            continue

        guid = _news_child_text(item, {"guid", "id"}) or link
        summary = _news_strip_html(_news_child_text(item, {"description", "summary", "encoded", "content"}))
        published = _news_parse_date(_news_child_text(item, {"pubdate", "published", "updated", "date"}))

        image_url = ""
        video_url = ""
        for ch in item.iter():
            lname = _news_local_name(ch.tag)
            if lname not in ("enclosure", "content", "thumbnail"):
                continue
            media_url = (ch.attrib.get("url") or ch.attrib.get("href") or "").strip()
            if not media_url:
                continue
            media_url = urllib.parse.urljoin(link, media_url)
            typ = (ch.attrib.get("type") or "").lower()
            medium = (ch.attrib.get("medium") or "").lower()
            path = urllib.parse.urlparse(media_url).path.lower()
            if not video_url and ("video" in typ or medium == "video" or path.endswith((".mp4", ".webm", ".mov"))):
                video_url = media_url
            elif not image_url and ("image" in typ or medium == "image" or path.endswith((".jpg", ".jpeg", ".png", ".webp"))):
                image_url = media_url

        entries.append({
            "guid": hashlib.sha256(guid.encode("utf-8", errors="ignore")).hexdigest(),
            "title": title[:500],
            "url": link,
            "published_at": published,
            "summary": summary[:3000],
            "image_url": image_url,
            "video_url": video_url,
        })
    return entries

def _news_is_direct_video_url(url: str) -> bool:
    try:
        path = urllib.parse.urlparse((url or "").strip()).path.lower()
        return path.endswith((".mp4", ".webm", ".mov", ".m4v"))
    except Exception:
        return False

def _news_is_embedded_video_url(url: str) -> bool:
    try:
        p = urllib.parse.urlparse((url or "").strip())
        host = (p.hostname or "").lower()
        path = p.path.lower()
        return (
            host.endswith("youtube.com")
            or host.endswith("youtube-nocookie.com")
            or host == "youtu.be"
            or host.endswith("vimeo.com")
            or host.endswith("dailymotion.com")
            or host.endswith("twitter.com")
            or host == "x.com" or host.endswith(".x.com")
            or host.endswith("bilibili.com")
            or host == "b23.tv" or host.endswith(".b23.tv")
            or host.endswith("nicovideo.jp")
            or host == "nico.ms" or host.endswith(".nico.ms")
            or host.endswith("streamable.com")
        ) and bool(path)
    except Exception:
        return False

def _news_normalize_embed_video_url(url: str) -> str:
    """Embedهای متداول را به URL قابل فهم‌تر برای yt-dlp تبدیل می‌کند."""
    try:
        p = urllib.parse.urlparse((url or "").strip())
        host = (p.hostname or "").lower()
        path = p.path.strip("/")
        if (host.endswith("youtube.com") or host.endswith("youtube-nocookie.com")) and path.startswith("embed/"):
            video_id = path.split("/", 1)[1].split("/", 1)[0]
            if video_id:
                return f"https://www.youtube.com/watch?v={video_id}"
        if host == "youtu.be" and path:
            return f"https://www.youtube.com/watch?v={path.split('/', 1)[0]}"
        if host == "player.vimeo.com" and path.startswith("video/"):
            video_id = path.split("/", 1)[1].split("/", 1)[0]
            if video_id.isdigit():
                return f"https://vimeo.com/{video_id}"
    except Exception:
        pass
    return (url or "").strip()

def _news_image_words(value: str):
    value = re.sub(r"[^a-z0-9]+", " ", (value or "").lower())
    return {w for w in value.split() if len(w) >= 3}

def _news_image_score(candidate: dict, title: str, kind: str) -> int:
    url = (candidate.get("url") or "").strip()
    alt = (candidate.get("alt") or "").lower()
    low_url = url.lower()
    origin = candidate.get("origin") or "article"
    width = int(candidate.get("width") or 0)
    height = int(candidate.get("height") or 0)
    score = {"meta": 60, "feed": 54, "article": 24}.get(origin, 20)

    if any(x in low_url or x in alt for x in (
        "logo", "avatar", "author", "icon", "favicon", "emoji", "sprite",
        "placeholder", "loading", "advert", "profile", "gravatar"
    )):
        score -= 120
    if low_url.startswith("data:") or low_url.endswith(".svg"):
        return -999

    if width >= 1200: score += 28
    elif width >= 800: score += 20
    elif width >= 500: score += 10
    elif 0 < width < 250: score -= 60
    if height >= 700: score += 20
    elif height >= 400: score += 10
    elif 0 < height < 180: score -= 50

    subject_words = _news_image_words(_news_subject(title))
    candidate_words = _news_image_words(alt + " " + low_url.replace("-", " ").replace("_", " "))
    score += min(32, len(subject_words & candidate_words) * 8)

    if kind == "visual" and any(x in low_url or x in alt for x in (
        "visual", "poster", "keyvisual", "key-visual", "teaser", "mainvisual", "kv"
    )):
        score += 55
    if kind == "visual" and width and height and height > width:
        score += 12
    if kind == "ranking":
        if any(x in low_url or x in alt for x in (
            "ranking", "rankings", "rank", "chart", "weekly", "week-", "week_",
            "top10", "top-10", "poll", "character", "anime-trending", "anitrendz"
        )):
            score += 65
        # جدول‌های رتبه‌بندی معمولاً افقی/مربعی‌اند؛ عکس بزرگ امتیاز بیشتری بگیرد.
        if width >= 700 and height >= 500:
            score += 15
    return score

def _news_best_article_image(item: dict, candidates: list, final_url: str) -> str:
    kind = _news_type(item.get("title", ""), item.get("summary", ""))
    ranked = []
    seen = set()
    for cand in candidates:
        raw = (cand.get("url") or "").strip()
        if not raw:
            continue
        url = urllib.parse.urljoin(final_url, raw)
        if not _news_safe_url(url):
            continue
        p = urllib.parse.urlparse(url)
        key = (p.netloc.lower(), p.path)
        if key in seen:
            continue
        seen.add(key)
        c = dict(cand)
        c["url"] = url
        ranked.append((_news_image_score(c, item.get("title", ""), kind), url))
    ranked.sort(reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] > -40 else ""

def _news_video_candidates_from_html(html_text: str, final_url: str = "") -> list:
    """لینک ویدیوی Embed را حتی وقتی داخل JSON/اسکریپت صفحه پنهان شده باشد پیدا می‌کند.

    بعضی رسانه‌ها (به‌خصوص Crunchyroll) پلیر YouTube را به شکل iframe ساده در HTML
    نمی‌گذارند و شناسه ویدیو داخل JSON hydration / data-* نگه‌داری می‌شود.
    """
    raw = str(html_text or "")
    if not raw:
        return []

    variants = []
    for value in (raw, unescape(raw)):
        value = (
            value.replace(r"\/", "/")
                 .replace(r"\u002F", "/").replace(r"\u002f", "/")
                 .replace(r"\u003A", ":").replace(r"\u003a", ":")
                 .replace(r"\u003D", "=").replace(r"\u003d", "=")
                 .replace(r"\u0026", "&")
        )
        variants.append(value)
        try:
            variants.append(urllib.parse.unquote(value))
        except Exception:
            pass

    out = []
    seen = set()

    def add(url: str):
        url = (url or "").strip().strip('\\"\' <>')
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/") and final_url:
            url = urllib.parse.urljoin(final_url, url)
        if not url:
            return
        if url in seen:
            return
        if _news_safe_url(url) and _news_is_embedded_video_url(url):
            seen.add(url)
            out.append(url)

    # URLهای کامل YouTube/Vimeo/Dailymotion که داخل HTML/JSON آمده‌اند.
    url_patterns = [
        r'https?://(?:www\.)?youtube(?:-nocookie)?\.com/(?:watch\?[^"\'<> ]*?v=|embed/|shorts/)([A-Za-z0-9_-]{11})',
        r'https?://youtu\.be/([A-Za-z0-9_-]{11})',
        r'https?://(?:player\.)?vimeo\.com/(?:video/)?(\d{5,12})',
        r'https?://(?:www\.)?dailymotion\.com/(?:embed/video/|video/)([A-Za-z0-9]+)',
    ]
    for value in variants:
        for idx, pat in enumerate(url_patterns):
            for m in re.finditer(pat, value, flags=re.I):
                token = m.group(1)
                if idx == 0:
                    add(f"https://www.youtube.com/watch?v={token}")
                elif idx == 1:
                    add(f"https://www.youtube.com/watch?v={token}")
                elif idx == 2:
                    add(f"https://vimeo.com/{token}")
                else:
                    add(f"https://www.dailymotion.com/video/{token}")

        # Crunchyroll و چند CMS دیگر شناسه YouTube را داخل JSON نگه می‌دارند.
        id_patterns = [
            r'["\'](?:videoId|video_id|youtubeId|youtube_id|youtubeVideoId|youtubeVideoID|ytVideoId)["\']\s*:\s*["\']([A-Za-z0-9_-]{11})["\']',
            r'data-(?:youtube-)?video-id\s*=\s*["\']([A-Za-z0-9_-]{11})["\']',
            r'(?:youtube|youtu\.be)[^A-Za-z0-9_-]{0,80}([A-Za-z0-9_-]{11})',
        ]
        for pat in id_patterns:
            for m in re.finditer(pat, value, flags=re.I):
                add(f"https://www.youtube.com/watch?v={m.group(1)}")

        # ویدیوهای رسمی که داخل پست X/Twitter، Bilibili یا NicoVideo Embed شده‌اند.
        social_patterns = [
            r'https?://(?:www\.)?(?:twitter\.com|x\.com)/[A-Za-z0-9_]+/status/\d+',
            r'https?://(?:www\.)?bilibili\.com/video/(?:BV[A-Za-z0-9]+|av\d+)',
            r'https?://b23\.tv/[A-Za-z0-9]+',
            r'https?://(?:www\.)?nicovideo\.jp/watch/(?:sm|so)\d+',
            r'https?://nico\.ms/(?:sm|so)\d+',
            r'https?://streamable\.com/[A-Za-z0-9]+',
        ]
        for pat in social_patterns:
            for m in re.finditer(pat, value, flags=re.I):
                add(m.group(0))

    return out

NEWS_MAX_EXTRA_IMAGES = 9   # آلبوم تلگرام حداکثر ۱۰ تا (عکس اصلی + ۹)
_NEWS_MULTI_VISUAL_RE = re.compile(
    r"\b(?:visuals|posters|key\s+visuals?|character\s+visuals?|new\s+visuals?|poster|visual|trailer|teaser|pv"
    r"|preview(?:ed|s)?|images?|stills?|screenshots?|scenes?|photos?|gallery|episode\s+\d+|character\s+designs?)\b", re.I)
# خبرهایی که عکس‌هاشون خود خبرن (اسکرین‌شات‌های قسمت و...)؛ همه‌ی عکس‌های بدنه نگه داشته میشن
_NEWS_GALLERY_RE = re.compile(r"(?i)\b(?:preview(?:ed|s)?|stills?|screenshots?|scenes?|gallery|episode\s+\d+\s+(?:images|photos))\b")
_NEWS_BAD_IMAGE_RE = re.compile(r"(?i)logo|avatar|author|icon|favicon|emoji|sprite|placeholder|loading|advert|profile|gravatar|badge|banner-ad")

def _news_body_images(html_text: str, final_url: str, best: str) -> list:
    """عکس‌های بدنه‌ی مقاله به ترتیب صفحه (بدون عکس اصلی، لوگو و عکس‌های کوچیک)."""
    parser = _NewsBodyImageParser()
    try:
        parser.feed(html_text)
    except Exception:
        pass
    best_path = urllib.parse.urlparse(best).path if best else ""
    out, seen = [], {best_path}
    for img in parser.images:
        url = urllib.parse.urljoin(final_url, img["url"])
        path = urllib.parse.urlparse(url).path
        if not _news_safe_url(url) or path in seen or url.lower().endswith(".svg") or url.startswith("data:"):
            continue
        if _NEWS_BAD_IMAGE_RE.search(f"{url} {img['alt']}"):
            continue
        if (0 < img["width"] < 300) or (0 < img["height"] < 160):
            continue
        seen.add(path)
        out.append(url)
    return out[:NEWS_MAX_EXTRA_IMAGES]

_TWIMG_RE = re.compile(r"https?://pbs\.twimg\.com/media/[A-Za-z0-9_-]+(?:\.(?:jpe?g|png|webp)|\?format=(?:jpe?g|png|webp))[^\"'\s<>\\]*")
_image_shape_cache = {}

def _news_tweet_images(html_text: str) -> list:
    """عکس‌های توییت‌های embed شده داخل مقاله (حتی اگه فقط توی دیتای JSON صفحه باشن)."""
    raw = (html_text or "").replace("\\/", "/").replace("\\u002F", "/").replace("&amp;", "&")
    out = []
    for m in _TWIMG_RE.finditer(raw):
        url = m.group(0)
        base = url.split("?")[0]
        if "format=" in url:
            fmt = re.search(r"format=(\w+)", url).group(1)
            url = f"{base}?format={fmt}&name=large"
        if all(base not in u for u in out):
            out.append(url)
    return out[:6]

def _news_image_shape(url: str) -> tuple:
    """(عرض, ارتفاع) عکس با دانلودش (کش میشه). اگه نشد (0, 0)."""
    if url in _image_shape_cache:
        return _image_shape_cache[url]
    size = (0, 0)
    if Image is not None and _news_safe_url(url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126 Safari/537.36",
                                                       "Accept": "image/*,*/*;q=0.5"})
            with urllib.request.urlopen(req, timeout=NEWS_HTTP_TIMEOUT) as resp:
                data = resp.read(6_000_000)
            im = Image.open(io.BytesIO(data))
            size = im.size
        except Exception:
            size = (0, 0)
    _image_shape_cache[url] = size
    return size

def _news_poster_first(item: dict, html_text: str, final_url: str, best: str) -> tuple:
    """پوسترهای رسمی (عکس‌های عمودی داخل مقاله یا توییت embed شده) به ترتیب صفحه.
    خروجی: (پوستر اول, [بقیه‌ی پوسترها]) یا (best, []) اگه پوستری نبود."""
    candidates = []
    for url in _news_tweet_images(html_text) + _news_body_images(html_text, final_url, best):
        if url not in candidates and url != best:
            candidates.append(url)
    posters = []
    for url in candidates[:12]:
        w, h = _news_image_shape(url)
        if w >= 400 and h >= w * 1.2:
            posters.append(url)
    if not posters:
        return best, []
    # فقط پوسترهای رسمی کنار هم؛ عکس بالای سایت (اسکرین‌شاتی که خود سایت خبری گذاشته) نمیاد
    return posters[0], posters[1:1 + NEWS_MAX_EXTRA_IMAGES]

def _news_extra_article_images(item: dict, candidates: list, final_url: str, best: str, html_text: str = "") -> list:
    """برای خبرهای پوستر/تریلر/پیش‌نمایش قسمت، عکس‌های دیگه‌ی همون مقاله (نه عکس‌های کناری سایت)."""
    title = item.get("title", "")
    if not _NEWS_MULTI_VISUAL_RE.search(f"{title} {(item.get('summary') or '')[:300]}"):
        return []
    if html_text:
        body = _news_body_images(html_text, final_url, best)
        for url in _news_tweet_images(html_text):
            if url not in body and url != best:
                body.append(url)
        if body:
            return body[:NEWS_MAX_EXTRA_IMAGES]
    # سایت بدنه‌ی قابل تشخیص نداشت → فقط عکس‌هایی که اسم انیمه یا کلمه پوستر/ویژوال دارن
    subject_words = _news_image_words(_news_subject(title))
    best_key = urllib.parse.urlparse(best).path if best else ""
    ranked, seen = [], {best_key}
    for cand in candidates:
        if (cand.get("origin") or "article") != "article":
            continue  # og:image معمولاً همون عکس اصلیه
        url = urllib.parse.urljoin(final_url, (cand.get("url") or "").strip())
        if not url or not _news_safe_url(url):
            continue
        path = urllib.parse.urlparse(url).path
        if path in seen:
            continue
        seen.add(path)
        low = (url + " " + (cand.get("alt") or "")).lower()
        words = _news_image_words(low.replace("-", " ").replace("_", " "))
        visual_hint = any(k in low for k in ("visual", "poster", "keyvisual", "key-visual", "kv", "teaser", "character"))
        # فقط عکس‌هایی که اسم همین انیمه یا کلمه پوستر/ویژوال دارن (عکس‌های «مطالب مرتبط» حذف میشن)
        if not (subject_words & words) and not visual_hint:
            continue
        score = _news_image_score(dict(cand, url=url), title, "visual")
        if score > 20:
            ranked.append((score, url))
    ranked.sort(reverse=True)
    return [u for _s, u in ranked[:NEWS_MAX_EXTRA_IMAGES]]

def _news_enrich_article(item: dict) -> dict:
    """صفحه خبر را می‌خواند و بدنه واقعی مقاله، تصویر و لینک تریلر را استخراج می‌کند.

    متن کامل مقاله برای Agent نگه داشته می‌شود؛ بخش‌های Related/Upcoming/تبلیغات
    توسط _NewsArticleTextParser حذف می‌شوند. هیچ ویدیویی دانلود نمی‌شود.
    """
    try:
        data, _ct, final_url = _news_fetch(item["url"], max_bytes=4_500_000)
        html_text = data.decode("utf-8", errors="ignore")
        parser = _NewsMetaParser()
        parser.feed(html_text)
        meta = parser.meta

        article_paragraphs = []
        try:
            article_parser = _NewsArticleTextParser()
            article_parser.feed(html_text)
            article_paragraphs = article_parser.paragraphs or []
        except Exception:
            article_paragraphs = []

        article_uniq = []
        seen_article = set()
        for part in article_paragraphs:
            clean = re.sub(r"\s+", " ", part or "").strip()
            if not clean:
                continue
            key = re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", clean.lower())[:260]
            if key in seen_article:
                continue
            seen_article.add(key)
            article_uniq.append(clean)
        article_text = "\n\n".join(article_uniq)
        if article_text:
            item["article_text"] = article_text[:NEWS_AGENT_MAX_ARTICLE_CHARS]

        summary_parts = []
        desc = meta.get("og:description") or meta.get("description") or meta.get("twitter:description")
        if desc:
            summary_parts.append(_news_strip_html(desc))
        if article_uniq:
            # وقتی بدنه واقعی مقاله پیدا شده، RSS summary را کنار می‌گذاریم؛ بعضی فیدها
            # Related/Upcoming را هم داخل description می‌فرستند و دوباره همان آلودگی قدیمی را ایجاد می‌کنند.
            summary_parts.extend(article_uniq[:5])
        elif item.get("summary"):
            summary_parts.append(_news_strip_html(item.get("summary", "")))

        if summary_parts:
            uniq = []
            seen_summary = set()
            for part in summary_parts:
                clean = re.sub(r"\s+", " ", part or "").strip()
                key = clean.lower()[:240]
                if clean and key not in seen_summary:
                    seen_summary.add(key)
                    uniq.append(clean)
            item["summary"] = " ".join(uniq)[:5000]

        image_candidates = []
        if item.get("image_url"):
            image_candidates.append({
                "url": item["image_url"], "origin": "feed", "alt": item.get("title", ""),
                "width": 0, "height": 0
            })
        image_candidates.extend(parser.image_candidates)
        best_image = _news_best_article_image(item, image_candidates, final_url)
        if best_image:
            item["image_url"] = best_image
        item["extra_images"] = []
        headline_text = f"{item.get('title', '')} {(item.get('summary') or '')[:300]}"
        if _NEWS_GALLERY_RE.search(headline_text):
            # پیش‌نمایش قسمت / تصاویر / اسکرین‌شات: خود عکس‌های مقاله خبرن → همه‌شون
            try:
                item["extra_images"] = _news_extra_article_images(item, image_candidates, final_url, best_image, html_text)
                # اگه عکس اصلی هم یکی از عکس‌های گالریه، ترتیب خود صفحه حفظ بشه
                in_order = _news_body_images(html_text, final_url, "")
                if best_image and best_image in in_order and item["extra_images"]:
                    item["image_url"] = in_order[0]
                    item["extra_images"] = in_order[1:1 + NEWS_MAX_EXTRA_IMAGES]
            except Exception:
                item["extra_images"] = []
        else:
            # بقیه‌ی خبرها: اگه پوستر رسمی (عمودی) داخل مقاله/توییت هست، فقط پوسترها کنار هم؛
            # عکس بالای سایت (اسکرین‌شاتی که سایت خبری گذاشته) کنار گذاشته میشه
            try:
                main, extras = _news_poster_first(item, html_text, final_url, item.get("image_url") or best_image)
                if main and main != item.get("image_url"):
                    item["image_url"] = main
                item["extra_images"] = extras
            except Exception as exc:
                logger.info("Poster detection failed for %s: %s", item.get("url"), exc)
            if not item["extra_images"] and _NEWS_MULTI_VISUAL_RE.search(headline_text) and \
                    item.get("image_url") == best_image:
                # پوستر عمودی پیدا نشد ولی خبر درباره‌ی ویژواله → روش قبلی (عکس‌های هم‌اسم انیمه)
                try:
                    item["extra_images"] = _news_extra_article_images(item, image_candidates, final_url, best_image, html_text)
                except Exception:
                    item["extra_images"] = []

        trailer_url = ""
        video_relevant = _news_has_current_video_announcement(
            item.get("title", ""), item.get("summary", "")
        )
        if video_relevant:
            candidates = []
            for key in ("og:video:secure_url", "og:video", "twitter:player:stream", "twitter:player"):
                if meta.get(key):
                    candidates.append(meta[key])
            candidates.extend(parser.embed_video_urls)
            candidates.extend(parser.link_video_urls)
            candidates.extend(_news_video_candidates_from_html(html_text, final_url))
            for raw_vid in candidates:
                vid = urllib.parse.urljoin(final_url, raw_vid)
                if not _news_safe_url(vid) or not _news_is_embedded_video_url(vid):
                    continue
                trailer_url = _news_normalize_embed_video_url(vid)
                break

        item["trailer_url"] = trailer_url
        item["video_url"] = ""
    except Exception as e:
        logger.info("News article enrichment failed for %s: %s", item.get("url"), e)
    return item

def _news_ranking_variant(text: str) -> str:
    """نوع رتبه‌بندی دوره‌ای را تشخیص می‌دهد."""
    t = f" {(text or '').lower()} "

    male_markers = (
        "male character", "male characters", "best male character", "best boy",
        "boys ranking", "boy ranking", "male character ranking", "male character rankings"
    )
    female_markers = (
        "female character", "female characters", "best female character", "best girl",
        "girls ranking", "girl ranking", "female character ranking", "female character rankings"
    )
    anime_markers = (
        "anime ranking", "anime rankings", "weekly anime ranking", "weekly anime rankings",
        "top anime", "anime of the week", "best anime of the week", "weekly anime chart",
        "top 10 anime", "top 10 anime of the week"
    )

    # female character شامل زیررشته male character است؛ اول female بررسی شود.
    if any(k in t for k in female_markers):
        return "female"
    if any(k in t for k in male_markers):
        return "male"
    if any(k in t for k in anime_markers):
        return "anime"

    # بعضی منابع فقط "Week X Rankings" می‌نویسند؛ اگر کنار آن anime/character باشد بپذیر.
    if ("ranking" in t or "rankings" in t or "poll results" in t) and re.search(r"\bweek\s*#?\s*\d{1,2}\b", t):
        if "character" in t:
            return "character"
        if "anime" in t:
            return "anime"
    return ""

def _news_week_number(text: str) -> int | None:
    t = text or ""
    patterns = [
        r"\bweek\s*#?\s*(\d{1,2})\b",
        r"\b(\d{1,2})(?:st|nd|rd|th)\s+week\b",
    ]
    for pat in patterns:
        m = re.search(pat, t, flags=re.I)
        if m:
            try:
                n = int(m.group(1))
                if 1 <= n <= 30:
                    return n
            except Exception:
                pass
    return None

def _news_season_label(text: str) -> str:
    t = (text or "").lower()
    if "summer" in t:
        return "تابستان"
    if "spring" in t:
        return "بهار"
    if "winter" in t:
        return "زمستان"
    if "fall" in t or "autumn" in t:
        return "پاییز"
    return ""

def _news_ranking_winner(title: str) -> str:
    """اگر تیتر نام رتبه اول را صریح گفته باشد، همان را استخراج می‌کند."""
    t = re.sub(r"\s+", " ", (title or "").strip())
    patterns = [
        r"^(.{2,110}?)\s+(?:tops?|wins?|leads?)\s+.*?(?:anime|male|female|character).*?(?:ranking|rankings)",
        r"^(.{2,90}?)\s+(?:is|named)\s+(?:the\s+)?(?:best|top)\s+(?:male|female)\s+character",
    ]
    for pat in patterns:
        m = re.search(pat, t, flags=re.I)
        if m:
            name = m.group(1).strip(" :-–—|")
            # عنوان انیمه ممکن است چندکلمه‌ای باشد؛ فقط جمله‌های خیلی بلند رد شوند.
            if 2 <= len(name) <= 100 and len(name.split()) <= 18:
                return name
    return ""

def _news_ranking_first_vote(summary: str) -> str:
    """در payload متنی Ranking درصد رأی رتبه اول را پیدا می‌کند."""
    text = re.sub(r"\s+", " ", summary or "")
    patterns = [
        r"#?1(?:st)?[.)]?\s+.{2,180}?[—|:-]\s*(\d{1,3}(?:\.\d{1,2})?%)",
        r"(?:rank\s*1|1st)\D{0,180}?(\d{1,3}(?:\.\d{1,2})?%)",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            return m.group(1)
    return ""

def _news_type(title: str, summary: str = "") -> str:
    """نوع خبر را با اولویت تیتر تشخیص می‌دهد تا کلمات فرعی داخل متن، خبر را عوض نکنند.

    مثال مهم: "Anime's New Video ... Theme Songs" تریلر/ویدیو است، نه موزیک‌ویدیو.
    همین‌طور "chapter cover" مانگا نباید فقط به‌خاطر واژه poster در متن مقاله، visual انیمه شود.
    """
    title_low = f" {(title or '').lower()} "
    summary_low = f" {(summary or '').lower()} "
    all_text = f"{title_low} {summary_low}"

    if _news_ranking_variant(all_text):
        return "ranking"

    # موزیک‌ویدیو فقط وقتی واقعاً Music Video موضوع اصلی خبر است.
    if "music video" in title_low or re.search(r"\b(?:opening|ending|theme)\s+(?:song|theme)\b.{0,55}\b(?:music\s+video|mv)\b", title_low):
        return "music"

    # ویدیو/تریلرِ خود انیمه از اشاره فرعی به theme song مهم‌تر است.
    title_video = any(k in title_low for k in (
        "trailer", "video teaser", "teaser trailer", "teaser video",
        "promotional video", "promo video", " official pv ", " pv ",
        " new video ", " first video ", " main video "
    ))
    if title_video or (" teaser " in title_low and " visual " not in title_low):
        return "trailer"

    title_visual = any(k in title_low for k in (
        "teaser visual", "key visual", "main visual", "new visual", "new visuals",
        "poster", "posters", "illustration"
    ))
    if title_visual:
        return "visual"

    # خبرهای مانگا/کاور فصل را قبل از بررسی summary جدا کن.
    if any(k in title_low for k in (" manga ", " chapter ", " volume ", " mangaka ", " manga artist ", " chapter cover ")):
        return "manga"

    # فقط الگوهای صریح در summary حق دارند نوع رسانه را تعیین کنند؛ صرف وجود یک کلمه کافی نیست.
    if re.search(r"(?:new|first|main|official|final)\s+(?:trailer|teaser|promotional video|promo video|pv)\b.{0,90}\b(?:released|revealed|unveiled|shared|debuted|published)\b", summary_low):
        return "trailer"
    if re.search(r"(?:new|first|key|main|teaser)\s+(?:visual|poster|illustration)\b.{0,90}\b(?:released|revealed|unveiled|shared|published)\b", summary_low):
        return "visual"
    if re.search(r"\bmusic video\b.{0,90}\b(?:released|revealed|unveiled|shared|published)\b", summary_low):
        return "music"

    if any(k in title_low for k in ("premiere", "premieres", "release date", "airs on", "air date", "debut")):
        return "date"
    if any(k in all_text for k in ("days until", "countdown", "festival", " fes ", "event")):
        return "event"
    if any(k in all_text for k in (
        "season 2", "season 3", "season 4", "season 5", "season 6",
        "sequel", "announced", "announcement", "new season", "renewed", "confirmed"
    )):
        return "announcement"
    if "cast" in title_low or "voice actor" in title_low or "voice actress" in title_low:
        return "cast"
    if "studio" in title_low or "animation production" in title_low or "animated by" in title_low:
        return "studio"
    return "news"

def _news_has_visual(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in (
        "teaser visual", "key visual", "main visual", "new visual", "visuals",
        "poster", "posters", "illustration", "new image", "new images"
    ))

def _news_has_current_video_announcement(title: str, summary: str = "") -> bool:
    """فقط وقتی ویدیو را «مدیای همین خبر» بدان که واقعاً تریلر/تیزر جدید اعلام شده باشد.

    وجود یک ویدیوی قدیمی یا جمله‌هایی مثل «تریلر به‌زودی نمایش داده می‌شود» نباید
    باعث شود ربات آن ویدیو را به‌عنوان تریلر خبر جدید آپلود کند.
    """
    t_title = f" {(title or '').lower()} "
    t = f" {t_title} {(summary or '').lower()} "

    # teaser visual تصویر است، نه ویدیو.
    t_no_visual = t.replace("teaser visual", "")
    title_no_visual = t_title.replace("teaser visual", "")

    video_terms = ("trailer", "video teaser", "teaser trailer", "teaser video", "promotional video", "promo video", " official pv ", " pv ")
    if any(k in title_no_visual for k in video_terms):
        return True
    if " teaser " in title_no_visual and " visual " not in title_no_visual:
        return True

    # اشاره آینده به تریلر = هنوز تریلر این خبر منتشر نشده.
    future_patterns = (
        r"trailer.{0,45}\b(?:will|is set to|is scheduled to|coming)\b.{0,45}\b(?:soon|later|next)\b",
        r"\b(?:will|is set to|is scheduled to)\b.{0,45}\btrailer\b",
        r"trailer\s+(?:coming|arriving)\s+soon",
    )
    for pat in future_patterns:
        if re.search(pat, t_no_visual, flags=re.I):
            return False

    # در متن مقاله باید فعل انتشار/رونمایی نزدیک به واژه ویدیو باشد.
    positive_patterns = (
        r"(?:trailer|teaser trailer|video teaser|promotional video|promo video|\bpv\b).{0,80}\b(?:released|revealed|unveiled|shared|debuted|premiered|posted|published)\b",
        r"\b(?:released|revealed|unveiled|shared|debuted|premiered|posted|published)\b.{0,80}(?:trailer|teaser trailer|video teaser|promotional video|promo video|\bpv\b)",
        r"(?:first|second|new|official|main|final)\s+(?:trailer|teaser|pv)\b",
    )
    return any(re.search(pat, t_no_visual, flags=re.I) for pat in positive_patterns)

def _news_has_trailer(text: str) -> bool:
    # سازگاری با فراخوانی‌های قدیمی: متن واحد را هم با منطق قوی‌تر بررسی کن.
    return _news_has_current_video_announcement(text or "", "")

def _news_is_mixed_visual_trailer(title: str, summary: str = "") -> bool:
    all_text = f"{title} {summary}"
    return _news_has_visual(all_text) and _news_has_current_video_announcement(title, summary)

def _news_fa_digits(value: str) -> str:
    table = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return str(value or "").translate(table)

def _news_season_number(text: str) -> int | None:
    text = text or ""
    patterns = [
        r"\bseason\s+(\d{1,2})\b",
        r"\b(\d{1,2})(?:st|nd|rd|th)\s+season\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
    return None

def _news_season_phrase(number: int | None) -> str:
    if not number:
        return ""
    names = {
        1: "اول", 2: "دوم", 3: "سوم", 4: "چهارم", 5: "پنجم",
        6: "ششم", 7: "هفتم", 8: "هشتم", 9: "نهم", 10: "دهم",
        11: "یازدهم", 12: "دوازدهم",
    }
    return names.get(number, _news_fa_digits(str(number)))

def _news_subject(title: str) -> str:
    """نام اثر را تا جای ممکن از تیتر خبری جدا می‌کند، بدون اینکه خود خبر وارد نام شود."""
    t = re.sub(r"\s+", " ", (title or "").strip())
    if not t:
        return "این انیمه"

    # اول سراغ عبارت‌های موضوع خبر می‌رویم؛ برای تیترهایی مثل
    # Sakamoto Days Season 2 New Teaser Visual Revealed
    event_markers = [
        r"\s+(?:new\s+|first\s+|2nd\s+|second\s+)?teaser\s+visual\b",
        r"\s+(?:new\s+|first\s+)?key\s+visual\b",
        r"\s+(?:new\s+|first\s+)?main\s+visual\b",
        r"\s+(?:new\s+|first\s+)?visual\b",
        r"\s+(?:new\s+|first\s+)?poster\b",
        r"\s+(?:new\s+|first\s+|official\s+)?trailer\b",
        r"\s+(?:new\s+|first\s+|official\s+)?teaser\b",
        # Possessive news-title form used by ANN: "Title Anime's New Video ..."
        r"\s+(?:TV\s+)?Anime(?:'s|’s)\s+(?:new\s+|first\s+|main\s+|official\s+)?(?:video|trailer|teaser|visual|poster|pv)\b",
        r"\s+(?:new\s+|first\s+)?promotional\s+video\b",
        r"\s+(?:new\s+|first\s+)?promo\s+video\b",
        r"\s+(?:new\s+|first\s+|main\s+|official\s+)?video\b",
        r"\s+(?:new\s+)?music\s+video\b",
        r"\s+(?:new\s+)?cast\b",
        r"\s+(?:new\s+)?staff\b",
        r"\s+(?:release|air|premiere)\s+date\b",
        r"\s+(?:a\s+)?new\s+project\b",
        r"\s+project\s+(?:announcement|details?)\b",
    ]
    cut_positions = []
    for pattern in event_markers:
        m = re.search(pattern, t, flags=re.I)
        if m and m.start() >= 2:
            cut_positions.append(m.start())

    # اگر marker نبود، قبل از فعل خبری قطع کن.
    action = re.search(
        r"\s+(?:reveals?|revealed|unveils?|unveiled|announces?|announced|releases?|released|"
        r"gets?|premieres?|premiered|debuts?|debuted|streams?|streamed|returns?|returning|shares?|shared|"
        r"confirms?|confirmed|sets?|renewed)\b",
        t, flags=re.I
    )
    if action and action.start() >= 2:
        cut_positions.append(action.start())

    if cut_positions:
        t = t[:min(cut_positions)].strip(" :-–—")

    # کلمات عمومی و شماره فصل جزو نام اثر نیستند.
    t = re.sub(r"\b(?:TV\s+)?Anime\b", "", t, flags=re.I)
    t = re.sub(r"\bSeason\s+\d{1,2}\b", "", t, flags=re.I)
    t = re.sub(r"\b\d{1,2}(?:st|nd|rd|th)\s+Season\b", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" :-–—")
    return (t[:120] or (title or "این انیمه")[:120])

def _news_display_subject(title: str, summary: str = "") -> str:
    """نام پروژه جاری را ترجیح می‌دهد تا اسپین‌آف/ویژه با سری اصلی اشتباه نشود."""
    raw_subject = _news_subject(title)
    known = _news_known_anime_key(f"{title} {summary}")
    low_raw = raw_subject.lower()
    project_markers = (
        "lego ", " special", " movie", " film", " ova", " ona", " remake", " spin-off", " spinoff",
        " anthology", " live-action", " the animation", "heroines", "short anime", "web anime",
    )
    if any(k in low_raw for k in project_markers):
        return raw_subject
    return known or raw_subject

def _news_project_profile(title: str, summary: str = "") -> tuple[str, str]:
    """(نام تمیز پروژه، نوع فارسی پروژه) برای ساخت جمله طبیعی‌تر."""
    raw = _news_display_subject(title, summary)
    subject = raw
    label = "انیمه"

    patterns = [
        (r"\s+Two[- ]Part\s+(?:Animated|Animation)\s+Special\s*$", "ویژه انیمیشنی دو قسمتی"),
        (r"\s+2[- ]Part\s+(?:Animated|Animation)\s+Special\s*$", "ویژه انیمیشنی دو قسمتی"),
        (r"\s+(?:Animated|Animation)\s+Special\s*$", "ویژه انیمیشنی"),
        (r"\s+TV\s+Special\s*$", "ویژه تلویزیونی"),
        (r"\s+Special\s*$", "ویژه"),
    ]
    for pat, fa in patterns:
        if re.search(pat, subject, flags=re.I):
            subject = re.sub(pat, "", subject, flags=re.I).strip(" :-–—")
            label = fa
            break

    low = (title or "").lower()
    if label == "انیمه":
        if "live-action" in low or "live action" in low:
            label = "لایو اکشن"
        elif re.search(r"\b(?:movie|film)\b", low):
            label = "فیلم"
        elif re.search(r"\b(?:ova|ona)\b", low):
            label = "پروژه انیمیشنی"

    return subject or raw, label

def _news_project_fact_lines(text: str, subject: str = "") -> list:
    """چند نکته مهم از Lead مقاله را به فارسی و کوتاه تبدیل می‌کند."""
    raw = re.sub(r"\s+", " ", text or " ").strip()
    low = raw.lower()
    facts = []

    # پروژه‌های چندقسمتی ویژه
    if re.search(r"\b(?:2|two)[- ]part\s+(?:animated|animation)\s+special\b", raw, flags=re.I):
        facts.append("🔹 این پروژه یک ویژه انیمیشنی دو قسمتی است.")
    else:
        m = re.search(r"\b(\d{1,2})[- ]part\s+(?:animated|animation)\s+special\b", raw, flags=re.I)
        if m:
            facts.append(f"🔹 این پروژه یک ویژه انیمیشنی {_news_fa_digits(m.group(1))} قسمتی است.")

    # الگوی شناخته‌شده روایت/تمرکز داستانی برای خبرهایی که متن Lead واضح دارد.
    if "usopp" in low and ("narrat" in low or "retells" in low) and ("crew" in low or "straw hat" in low):
        if "chopper" in low:
            facts.append("🔹 در این ویژه، اوسُپ ماجراهای خدمه کلاه‌حصیری را برای چاپر روایت می‌کند.")
        else:
            facts.append("🔹 در این ویژه، اوسُپ ماجراهای خدمه کلاه‌حصیری را روایت می‌کند.")

    # اگر خبر صریحاً می‌گوید تریلر هنوز در راه است، این را به‌عنوان نکته خبری بگو؛ ویدیو آپلود نشود.
    if re.search(r"trailer.{0,50}\b(?:will be shown|will be revealed|will be released|coming soon|is coming soon)\b", raw, flags=re.I):
        facts.append("🎬 تریلر جدید این پروژه به‌زودی منتشر خواهد شد.")

    out = []
    for f in facts:
        if f not in out:
            out.append(f)
    return out[:3]

def _news_ordinal_phrase(text: str) -> str:
    low = (text or "").lower()
    for keys, fa in [
        (("final", "last"), "نهایی"),
        (("4th", "fourth"), "چهارمین"),
        (("3rd", "third"), "سومین"),
        (("2nd", "second"), "دومین"),
        (("1st", "first"), "اولین"),
    ]:
        if any(re.search(rf"\b{re.escape(k)}\b", low) for k in keys):
            return fa
    return "جدید"

def _news_topic_normalize(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def _news_known_anime_key(text: str) -> str:
    norm_text = f" {_news_topic_normalize(text)} "
    try:
        conn = db()
        rows = conn.execute("SELECT eng_name, fa_name, jp_name FROM anime").fetchall()
        conn.close()
    except Exception:
        return ""
    best_len = 0
    best_eng = ""
    for row in rows:
        for name in (row["eng_name"], row["fa_name"], row["jp_name"]):
            n = _news_topic_normalize(name or "")
            if len(n) < 3:
                continue
            if n in norm_text and len(n) > best_len:
                best_len = len(n)
                best_eng = row["eng_name"]
    return best_eng

def _news_topic_key(title: str, summary: str = "") -> str:
    all_text = f"{title} {summary}"

    # رتبه‌بندی‌های هفتگی هر هفته محتوای مستقل‌اند؛ آن‌ها را به هفته قبل ریپلای نکن.
    ranking_variant = _news_ranking_variant(all_text)
    if ranking_variant:
        week = _news_week_number(all_text)
        season_label = _news_season_label(all_text) or "general"
        year_m = re.search(r"\b(20\d{2})\b", all_text)
        year = year_m.group(1) if year_m else "year"
        week_key = f"week-{week}" if week else "week-current"
        return f"ranking|{ranking_variant}|{season_label}|{year}|{week_key}"

    canonical = _news_known_anime_key(all_text)
    subject = canonical or _news_subject(title)
    base = _news_topic_normalize(subject)[:120] or _news_fingerprint(title)[:120] or "news"
    low = all_text.lower()
    season = _news_season_number(all_text)
    if season:
        project = f"season-{season}"
    elif "special episode" in low or "special anime" in low:
        project = "special"
    elif "movie" in low or "film" in low:
        project = "movie-" + _news_topic_normalize(_news_subject(title))[:70]
    else:
        project = "general"
    return f"{base}|{project}"

def _news_release_phrase(text: str) -> str:
    """تاریخ/بازه پخش را از تیتر و متن خبر استخراج می‌کند."""
    raw = re.sub(r"\s+", " ", text or " ").strip()
    months = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    date_token = rf"{months}\s+\d{{1,2}},?\s+\d{{4}}|{months}\s+\d{{4}}|{months}\s+\d{{1,2}}|\d{{4}}"
    patterns = [
        rf"(?:premieres?|premiered|releases?|released|debuts?|debuted|airs?|aired|returns?|returned)\s+(?:on\s+|in\s+)?({date_token})\b",
        rf"(?:premiere|release|air|streaming|theatrical)\s+(?:date\s+)?(?:for\s+)?({date_token})\b",
        rf"(?:set\s+for|scheduled\s+for|starting|beginning|opens?\s+on|opens?\s+in)\s+({date_token})\b",
        rf"(?:begins?|starts?)\s+(?:streaming|airing|screening)?\s*(?:on\s+|in\s+)?({date_token})\b",
        rf"(?:returns?|comes?\s+back).{{0,80}}?\s(?:in|on|from)\s+({date_token})\b",
        rf"(?:season\s+\d{{1,2}}|part\s+\d{{1,2}}|cour\s+\d{{1,2}}).{{0,100}}?\s(?:in|on|from|starting)\s+({date_token})\b",
        rf"(?:stream(?:s|ing)?|available|launch(?:es|ing)?).{{0,90}}?\s(?:in|on|from|starting)\s+({date_token})\b",
        # تیترهایی مثل: Reveals November 6 Japan Release in 1st Trailer
        rf"(?:reveals?|revealed|announces?|announced|confirms?|confirmed|sets?)\s+({date_token})(?:\s+(?:japan|japanese|theatrical|release|premiere|debut))?\b",
        # متن‌هایی مثل: a November 6 theatrical release in Japan
        rf"\b({date_token})\s+(?:japan(?:ese)?\s+)?(?:theatrical\s+)?(?:release|premiere|debut|broadcast|airing)\b",
    ]
    for p in patterns:
        m = re.search(p, raw, flags=re.I)
        if m:
            return m.group(1).strip()

    # fallback محافظه‌کارانه: تاریخ ماه‌دار را فقط کنار واژه‌های واضح انتشار قبول کن.
    if any(k in raw.lower() for k in (
        "season", "premiere", "release", "stream", "air", "debut", "return", "broadcast",
        "theater", "theatrical", "opens", "disney+", "netflix"
    )):
        m = re.search(rf"\b({months}\s+\d{{1,2}}(?:,?\s+\d{{4}})?|{months}\s+\d{{4}})\b", raw, flags=re.I)
        if m:
            return m.group(1).strip()
    return ""

def _news_gregorian_to_jalali(gy: int, gm: int, gd: int):
    """تبدیل تاریخ میلادی به هجری شمسی، بدون وابستگی خارجی."""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        365 * gy
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
        - 80
        + gd
        + g_d_m[gm - 1]
    )
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return int(jy), int(jm), int(jd)

_EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}

def _news_parse_ref_date(published_at: str):
    try:
        ref = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
    except Exception:
        try:
            ref = parsedate_to_datetime(str(published_at))
        except Exception:
            return None
    return ref.replace(tzinfo=None) if ref.tzinfo is not None else ref

def _news_release_is_plausible(value: str, published_at: str = "") -> bool:
    """تاریخ‌های قدیمیِ داخل مقاله (پخش نسخه قبلی، سال شروع مانگا و...) رو به‌عنوان تاریخ پخش قبول نکن.

    تاریخ پخش یه خبر تازه نمی‌تونه بیشتر از ~۴۵ روز قبل از خود خبر یا توی یه سال قبل‌تر باشه.
    """
    raw = re.sub(r"\s+", " ", (value or "").strip())
    if not raw:
        return False
    ref = _news_parse_ref_date(published_at) if published_at else None
    ref = ref or datetime.now()
    years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", raw)]
    if any(y < ref.year for y in years):
        return False
    month = next((_EN_MONTHS[w] for w in re.findall(r"[A-Za-z]+", raw.lower()) if w in _EN_MONTHS), 0)
    day_m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b(?!\d)", re.sub(r"\b(19|20)\d{2}\b", "", raw))
    if years and month:
        try:
            when = datetime(years[0], month, int(day_m.group(1)) if day_m else 28)
        except Exception:
            when = datetime(years[0], month, 28)
        if when < ref - timedelta(days=45):
            return False
    return True

def _news_localize_date(value: str, reference_date: str = "") -> str:
    """تاریخ میلادی خبر را تا حد اطلاعات موجود به تاریخ شمسی ایران تبدیل می‌کند.

    اگر منبع فقط `November 6` نوشته باشد، سال از تاریخ انتشار همان خبر استنباط می‌شود.
    """
    if not value:
        return ""

    raw = re.sub(r"\s+", " ", str(value).strip())
    # فقط سال یا فصل: تبدیل به یک سال شمسی اشتباهه (۲۰۲۷ = ۱۴۰۵ و ۱۴۰۶)، همون میلادی بمونه
    m_season = re.fullmatch(r"(?i)(?:in\s+|the\s+)?(?:(spring|summer|fall|autumn|winter)\s+)?(20\d{2})", raw)
    if m_season:
        season_fa = {"spring": "بهار", "summer": "تابستان", "fall": "پاییز", "autumn": "پاییز",
                     "winter": "زمستان"}.get((m_season.group(1) or "").lower(), "")
        year_fa = _news_fa_digits(m_season.group(2))
        return f"{season_fa} {year_fa}" if season_fa else f"سال {year_fa}"
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    fa_months = {
        1: "فروردین", 2: "اردیبهشت", 3: "خرداد", 4: "تیر",
        5: "مرداد", 6: "شهریور", 7: "مهر", 8: "آبان",
        9: "آذر", 10: "دی", 11: "بهمن", 12: "اسفند",
    }

    ref_dt = None
    if reference_date:
        try:
            ref_dt = datetime.fromisoformat(str(reference_date).replace("Z", "+00:00"))
            if ref_dt.tzinfo is not None:
                ref_dt = ref_dt.replace(tzinfo=None)
        except Exception:
            try:
                ref_dt = parsedate_to_datetime(str(reference_date)).replace(tzinfo=None)
            except Exception:
                ref_dt = None

    # Month DD, YYYY
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", raw, flags=re.I)
    if m and m.group(1).lower() in months:
        gm = months[m.group(1).lower()]
        gd = int(m.group(2))
        gy = int(m.group(3))
        try:
            jy, jm, jd = _news_gregorian_to_jalali(gy, gm, gd)
            return f"{_news_fa_digits(jd)} {fa_months[jm]} {_news_fa_digits(jy)}"
        except Exception:
            pass

    # Month DD بدون سال: سال را از تاریخ انتشار خبر استنباط کن.
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2})", raw, flags=re.I)
    if m and m.group(1).lower() in months:
        gm = months[m.group(1).lower()]
        gd = int(m.group(2))
        gy = ref_dt.year if ref_dt else datetime.now().year
        try:
            candidate = datetime(gy, gm, gd)
            # اگر تاریخِ بدون سال چند ماه قبل از تاریخ انتشار باشد، معمولاً منظور سال بعد است.
            if ref_dt and candidate < (ref_dt - timedelta(days=120)):
                gy += 1
            jy, jm, jd = _news_gregorian_to_jalali(gy, gm, gd)
            return f"{_news_fa_digits(jd)} {fa_months[jm]} {_news_fa_digits(jy)}"
        except Exception:
            pass

    # Month YYYY: ماه شمسی روز اول همان ماه میلادی نمایش داده می‌شود.
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{4})", raw, flags=re.I)
    if m and m.group(1).lower() in months:
        gm = months[m.group(1).lower()]
        gy = int(m.group(2))
        try:
            jy, jm, _jd = _news_gregorian_to_jalali(gy, gm, 1)
            return f"{fa_months[jm]} {_news_fa_digits(jy)}"
        except Exception:
            pass

    # فقط سال: سال خورشیدی متناظر غالب را نمایش بده.
    m = re.fullmatch(r"(\d{4})", raw)
    if m:
        gy = int(m.group(1))
        try:
            jy, _jm, _jd = _news_gregorian_to_jalali(gy, 7, 1)
            return _news_fa_digits(jy)
        except Exception:
            return _news_fa_digits(str(max(1, gy - 621)))

    return _news_fa_digits(raw)

def _news_studio_phrases(text: str) -> list:
    """یک یا چند استودیوی سازنده را فقط از الگوهای تولید معتبر استخراج می‌کند."""
    raw = re.sub(r"\s+", " ", text or " ").strip()
    found = []

    def add_chunk(chunk: str):
        chunk = re.sub(r"\s+", " ", chunk or "").strip(" :-–—,.;")
        # اگر Regex به انتهای جمله قبل چسبیده باشد، فقط آخرین قطعه را نگه دار.
        if ". " in chunk:
            chunk = chunk.rsplit(". ", 1)[-1].strip()
        # عبارت‌های فعلی/خبری نباید اسم استودیو تلقی شوند.
        bad_starts = ("set to ", "will ", "is ", "are ", "was ", "were ", "premiere", "release", "stream", "return")
        if not chunk or chunk.lower().startswith(bad_starts):
            return
        chunk = re.split(r"\s+(?:while|with|where|which|that)\s+", chunk, maxsplit=1, flags=re.I)[0]
        parts = re.split(r"\s+(?:and|&|×|x)\s+|\s*,\s*", chunk)
        for part in parts:
            val = part.strip(" :-–—,.;")
            if not (2 <= len(val) <= 50 and len(val.split()) <= 6):
                continue
            if re.search(r"\b(?:set|premiere|release|stream|air|return|season|episode|date)\b", val, flags=re.I):
                continue
            if val not in found:
                found.append(val)

    patterns = [
        r"(?:animated\s+by|animation\s+production\s+(?:is\s+)?(?:handled\s+)?by|produced\s+by)\s*[:\-]?\s*([^.;]{2,100})",
        r"\bat\s+studios?\s+([^.;]{2,100})",
        r"\bstudios?\s+([A-Z0-9][^.;]{1,90}?)(?=\s+(?:are|is|will|with|while|and\s+[A-Z][A-Za-z'’.-]+\s+(?:serves?|directs?|writes?))\b|[.;])",
        r"\b([A-Z][A-Za-z0-9.&'’+\-]*(?:\s+[A-Z][A-Za-z0-9.&'’+\-]*){0,4})\s+is\s+(?:producing|animating|handling\s+animation\s+for)\b",
        r"\b([A-Z][A-Za-z0-9.&'’+\-]*(?:\s+[A-Z][A-Za-z0-9.&'’+\-]*){0,4})\s+(?:will\s+)?(?:produce|animate)\s+(?:the\s+)?(?:anime|series|film|movie|ona|ova|special)\b",
    ]
    for pat in patterns:
        for m in re.finditer(pat, raw, flags=re.I):
            add_chunk(m.group(1))

    # فقط شکل «Studio NAME» که NAME واقعاً اسم خاص باشد، نه «Studio set to premiere ...»
    for m in re.finditer(r"\bStudio\s+([A-Z0-9][A-Za-z0-9.&'’+\-]*(?:\s+[A-Z0-9][A-Za-z0-9.&'’+\-]*){0,2})\b", raw):
        add_chunk("Studio " + m.group(1).strip())

    bad = {"the", "animation", "production", "series", "anime", "the lego group", "shueisha"}
    out = []
    for val in found:
        clean = re.sub(r"\s+", " ", val).strip()
        if clean.lower() in bad:
            continue
        if clean not in out:
            out.append(clean)
    return out[:4]

def _news_studio_phrase(text: str) -> str:
    vals = _news_studio_phrases(text)
    return vals[0] if vals else ""

def _news_subtitle_phrase(text: str) -> str:
    """زیرعنوان/نام آرک فصل مثل Episode of Savanaclaw را استخراج می‌کند."""
    raw = re.sub(r"\s+", " ", text or " ").strip()
    patterns = [
        r"(?:subtitled|titled|entitled|called)\s+[\"“'‘]([^\"”'’]{3,80})[\"”'’]",
        r"season\s+\d{1,2}\s*,?\s+[\"“'‘]([^\"”'’]{3,80})[\"”'’]",
        r"(?:the\s+)?second\s+season\s*,?\s+[\"“'‘]([^\"”'’]{3,80})[\"”'’]",
        r"The\s+Animation\s*:\s*([^|.;]{3,80}?)(?=\s+(?:Season|Returns|Premieres|Releases|Streams)|[|.;]|$)",
    ]
    for p in patterns:
        m = re.search(p, raw, flags=re.I)
        if m:
            val = re.sub(r"\s+", " ", m.group(1)).strip(" :-–—,.;\"'“”")
            if 3 <= len(val) <= 80:
                return val
    return ""

def _news_streaming_platform(text: str) -> str:
    """پلتفرم را فقط وقتی کنار فعل/عبارت پخش آمده باشد تشخیص می‌دهد.

    این کار مانع می‌شود نام رسانه‌ای مثل Crunchyroll در متن/فوتر سایت اشتباهاً
    به‌عنوان پلتفرم پخش خود اثر ثبت شود.
    """
    raw = re.sub(r"\s+", " ", text or " ")
    platforms = ["Disney+", "Crunchyroll", "Netflix", "HIDIVE", "Prime Video", "Amazon Prime Video", "Hulu"]
    stream_words = r"stream(?:s|ing|ed)?|available|premiere(?:s|d)?|release(?:s|d)?|air(?:s|ing|ed)?|watch|launch(?:es|ed|ing)?|exclusively"
    for p in platforms:
        ep = re.escape(p)
        patterns = [
            rf"(?:{stream_words}).{{0,90}}?(?<!\w){ep}(?!\w)",
            rf"(?<!\w){ep}(?!\w).{{0,90}}?(?:{stream_words})",
        ]
        if any(re.search(pat, raw, flags=re.I) for pat in patterns):
            return p
    return ""

def _news_context_fact_lines(text: str, subject: str, season_name: str = "") -> list:
    """جزئیات کوتاه و قابل اتکای مقاله که برای پوشش خبری مفیدند."""
    raw = re.sub(r"\s+", " ", text or " ").strip()
    low = raw.lower()
    facts = []
    platform = _news_streaming_platform(raw)
    if platform and any(k in low for k in ("exclusively", "streaming", "streams", "premiere", "release", "returns", "available")):
        facts.append(f"📱 پلتفرم پخش: {platform}")

    # تأیید فصل بعدی در همان خبر
    current_no = None
    try:
        current_no = _news_season_number(raw)
    except Exception:
        pass
    word_nums = {2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh"}
    for n in range(2, 8):
        if current_no and n <= current_no:
            continue
        has_season = bool(re.search(rf"\bseason\s+{n}\b", raw, flags=re.I) or re.search(rf"\b{word_nums[n]}\s+season\b", raw, flags=re.I))
        if has_season and any(k in low for k in ("planned", "confirmed", "in production", "announced")):
            facts.append(f"🔹 ساخت فصل {_news_season_phrase(n)} این مجموعه نیز تأیید شده است.")
            break

    return facts[:2]

def _news_clean_fact_text(value: str, max_len: int = 90) -> str:
    value = unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .,:;|-–—")
    # جمله‌های خیلی بلند معمولاً پاراگراف مقاله‌اند، نه اسم رویداد/پروژه.
    if len(value) > max_len:
        value = value[:max_len].rsplit(" ", 1)[0].strip()
    return value

def _news_announcement_facts(text: str, subject: str, season_name: str = "") -> list:
    """از خبرهای announcement جزئیات قابل اتکا و قابل‌بیان فارسی استخراج می‌کند."""
    raw = re.sub(r"\s+", " ", text or " ").strip()
    low = raw.lower()
    facts = []

    # پروژه جدید + محل/رویداد معرفی
    if "new project" in low:
        event = ""
        patterns = [
            r"new project.{0,90}?(?:to be|will be|is set to be)?\s*(?:announced|revealed|unveiled|presented)\s+(?:at|during)\s+([^.;|]{3,90})",
            r"(?:announced|revealed|unveiled|presented)\s+(?:at|during)\s+([^.;|]{3,90}).{0,100}?new project",
        ]
        for pat in patterns:
            m = re.search(pat, raw, flags=re.I)
            if m:
                event = _news_clean_fact_text(m.group(1), 75)
                # انتهای عبارت‌های رایج خبری را کوتاه کن.
                event = re.split(r"\s+(?:on|with|where|which|and)\s+", event, maxsplit=1, flags=re.I)[0].strip()
                break
        if event:
            facts.append(f"🔹 پروژه جدید این مجموعه در رویداد {event} معرفی خواهد شد.")
        else:
            facts.append("🔹 یک پروژه جدید برای این مجموعه در دست معرفی است.")

    # پارت / کور دوم یا ادامه یک فصل
    part2 = any(k in low for k in ("part 2", "part two", "second part"))
    cour2 = any(k in low for k in ("cour 2", "cour two", "second cour", "2nd cour"))
    continuation = any(k in low for k in ("continuation", "continues", "continue airing", "returns", "returning"))
    if part2:
        season_text = f" فصل {season_name}" if season_name else ""
        facts.append(f"🔹 ادامه{season_text} در قالب پارت دوم منتشر خواهد شد.")
    elif cour2:
        season_text = f" فصل {season_name}" if season_name else ""
        facts.append(f"🔹 ادامه{season_text} در قالب کور دوم پخش خواهد شد.")
    elif continuation and season_name:
        facts.append(f"🔹 ادامه فصل {season_name} این انیمه تأیید شده است.")

    # تعداد قسمت
    ep = re.search(r"\b(\d{1,3})[- ]episode(?:s)?\b", raw, flags=re.I)
    if not ep:
        ep = re.search(r"\b(?:will have|will run for|set for)\s+(\d{1,3})\s+episodes?\b", raw, flags=re.I)
    if ep:
        try:
            n = int(ep.group(1))
            if 1 <= n <= 200:
                facts.append(f"🔹 تعداد قسمت‌ها: {_news_fa_digits(n)} قسمت")
        except Exception:
            pass

    # تأخیر / تعویق
    if any(k in low for k in ("delayed", "postponed", "delay announced", "postponement")):
        facts.append("🔹 پخش/انتشار این پروژه با تأخیر مواجه شده است.")

    # اپیزود ویژه
    if any(k in low for k in ("special episode", "special anime episode", "tv special")):
        facts.append("🔹 یک قسمت ویژه برای این مجموعه معرفی شده است.")

    # فیلم جدید
    if any(k in low for k in ("new anime film", "new anime movie", "new movie project", "new film project")):
        facts.append("🔹 پروژه سینمایی جدیدی از این مجموعه معرفی شده است.")

    # آرک جدید
    arc = re.search(r"(?:new|next)\s+([^.;]{2,55}?)\s+arc\b", raw, flags=re.I)
    if arc:
        arc_name = _news_clean_fact_text(arc.group(1), 45)
        if arc_name:
            facts.append(f"🔹 آرک جدید «{arc_name}» معرفی شده است.")

    # فقط موارد غیرتکراری و حداکثر سه نکته تا کپشن شلوغ نشود.
    out = []
    for fact in facts:
        if fact not in out:
            out.append(fact)
    return out[:3]

def _news_generic_fact_lines(text: str, kind: str, subject: str, season_name: str = "") -> list:
    """جزئیات کوتاه مشترک برای خبرهایی که از تیتر به تنهایی مشخص نیستند."""
    raw = re.sub(r"\s+", " ", text or " ").strip()
    low = raw.lower()
    facts = []

    # معرفی اعضای جدید تیم/صداپیشه‌ها - اگر تعداد قابل تشخیص باشد.
    if kind == "cast":
        count = re.search(r"\badds?\s+(\d{1,2})\s+(?:cast|voice cast|voice actors?)\b", raw, flags=re.I)
        if count:
            facts.append(f"🔹 {_news_fa_digits(count.group(1))} صداپیشه جدید به تیم بازیگران اضافه شده‌اند.")

    # تاریخ/استودیو در بخش اصلی جدا نمایش داده می‌شوند؛ اینجا فقط موارد مکمل.
    ep = re.search(r"\b(\d{1,3})[- ]episode(?:s)?\b", raw, flags=re.I)
    if ep and kind not in ("ranking",):
        facts.append(f"🔹 تعداد قسمت‌ها: {_news_fa_digits(ep.group(1))} قسمت")

    return facts[:2]

def _news_fingerprint(title: str) -> str:
    t = (title or "").lower()
    t = re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", t)
    stop = {"anime", "new", "first", "official", "the", "a", "an", "of", "for", "and", "reveals", "reveal", "announces", "announced"}
    words = [w for w in t.split() if w not in stop]
    return " ".join(words[:18])

def _news_is_cross_source_duplicate(title: str, url: str) -> bool:
    fp = _news_fingerprint(title)
    if not fp:
        return False
    conn = db()
    rows = conn.execute("""
        SELECT title, url, fingerprint
        FROM news_items
        WHERE created_at >= datetime('now', '-3 days')
        ORDER BY id DESC LIMIT 120
    """).fetchall()
    conn.close()
    for row in rows:
        if row["url"] == url:
            return True
        old_fp = row["fingerprint"] or _news_fingerprint(row["title"])
        if old_fp and SequenceMatcher(None, fp, old_fp).ratio() >= 0.84:
            return True
    return False

def _openrouter_http_error_message(exc: Exception) -> str:
    """پیام خطای OpenRouter را بدون نمایش API Key استخراج می‌کند."""
    code = getattr(exc, "code", None)
    raw = ""
    try:
        raw = exc.read().decode("utf-8", errors="ignore")
    except Exception:
        raw = ""
    message = ""
    if raw:
        try:
            data = json.loads(raw)
            err = data.get("error") if isinstance(data, dict) else None
            if isinstance(err, dict):
                message = str(err.get("message") or err.get("code") or "").strip()
            elif err:
                message = str(err).strip()
            if not message and isinstance(data, dict):
                message = str(data.get("message") or "").strip()
        except Exception:
            message = ""
    if not message:
        message = str(exc)
    if code:
        return f"OpenRouter HTTP {code}: {message}"
    return message

GEMINI_BUSY_RETRIES = 1
_gemini_retired = set()


_gemini_thinking_supported = True


class GeminiTruncated(RuntimeError):
    pass


class GeminiError(RuntimeError):
    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.transient = transient


def _gemini_error_message(e) -> str:
    """از بدنه JSON خطای گوگل فقط پیام کوتاهش رو درمیاره."""
    body = ""
    try:
        body = e.read().decode("utf-8", errors="ignore")
    except Exception:
        pass
    try:
        return str((json.loads(body).get("error") or {}).get("message") or "")[:160]
    except Exception:
        return re.sub(r"\s+", " ", body)[:160]

def _gemini_generate_text(prompt: str, *, max_output_tokens: int = 900,
                          timeout: int = 60, temperature: float = 0.2,
                          system_prompt: str | None = None, json_mode: bool = False) -> str:
    """درخواست به Google Gemini API می‌فرستد.

    مدل‌های جدید Gemini بخشی از سقف توکن رو صرف «فکر کردن» می‌کنن؛ برای همین سقف بالاست،
    سطح فکر کردن low درخواست میشه و اگه باز جواب ناقص موند یه بار با سقف دو برابر تکرار میشه.
    """
    budget = max(int(max_output_tokens), 8192)
    last_exc = None
    for _round in range(2):
        try:
            return _gemini_generate_once(prompt, budget=budget, timeout=timeout, temperature=temperature,
                                         system_prompt=system_prompt, json_mode=json_mode)
        except GeminiTruncated as exc:
            last_exc = exc
            logger.warning("Gemini output truncated at %d tokens; retrying with more room", budget)
            budget *= 2
    raise RuntimeError(str(last_exc))


def _gemini_generate_once(prompt: str, *, budget: int, timeout: int, temperature: float,
                          system_prompt: str | None, json_mode: bool) -> str:
    global GEMINI_MODEL, _gemini_thinking_supported
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY تنظیم نشده است.")

    contents = []
    if system_prompt:
        full_prompt = f"{system_prompt}\n\n{prompt}"
    else:
        full_prompt = prompt

    contents.append({"role": "user", "parts": [{"text": full_prompt}]})

    def build_body() -> bytes:
        config = {"temperature": float(temperature), "maxOutputTokens": int(budget)}
        if json_mode:
            config["responseMimeType"] = "application/json"
        if _gemini_thinking_supported:
            config["thinkingConfig"] = {"thinkingLevel": "low"}
        return json.dumps({"contents": contents, "generationConfig": config}, ensure_ascii=False).encode("utf-8")

    data = build_body()
    payload = None
    errors = []
    for model in [GEMINI_MODEL] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL]:
        retired = False
        for attempt in range(GEMINI_BUSY_RETRIES + 1):
            req = urllib.request.Request(
                GEMINI_CHAT_URL.format(model=model),
                data=data,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "x-goog-api-key": GEMINI_API_KEY,
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
                break
            except urllib.error.HTTPError as e:
                message = _gemini_error_message(e)
                if e.code == 400 and _gemini_thinking_supported and re.search(r"(?i)thinking", message):
                    # این مدل thinkingConfig رو نمی‌شناسه → بدونش دوباره
                    _gemini_thinking_supported = False
                    data = build_body()
                    continue
                if e.code == 404:
                    # مدل حذف/بازنشسته شده → مدل بعدی
                    logger.warning("Gemini model %s unavailable (404); trying next model", model)
                    retired = True
                    break
                if e.code in (429, 500, 502, 503, 504):
                    # شلوغی موقت سرور گوگل: چند ثانیه صبر و دوباره
                    errors.append(f"{model}: HTTP {e.code} {message}")
                    if attempt < GEMINI_BUSY_RETRIES:
                        time.sleep(4 * (attempt + 1))
                        continue
                    logger.warning("Gemini model %s busy (HTTP %s); trying next model", model, e.code)
                    break
                raise GeminiError(f"Gemini HTTP {e.code}: {message}", transient=False) from e
            except Exception as e:
                errors.append(f"{model}: {e}")
                if attempt < GEMINI_BUSY_RETRIES:
                    time.sleep(3)
                    continue
                break
        if payload is not None:
            break
        if retired:
            errors.append(f"{model}: مدل بازنشسته شده (404)")
            if model == GEMINI_MODEL:
                _gemini_retired.add(model)
    if payload is None:
        busy = any(re.search(r"HTTP (?:429|5\d\d)", x) for x in errors) or any("HTTP" not in x for x in errors)
        if busy and any(re.search(r"(?i)quota|RESOURCE_EXHAUSTED|rate limit", x) for x in errors):
            raise GeminiError("سهمیه‌ی رایگان Gemini فعلاً تموم شده (خطای 429 quota). چند دقیقه بعد (یا اگه سهمیه روزانه‌ست، فردا) "
                              "دوباره کار می‌کنه؛ برای اینکه متوقف نشی یه سرویس AI دوم هم تنظیم کن.",
                              transient=True)
        if busy:
            raise GeminiError("سرورهای Gemini الان شلوغن (خطای موقت ۵۰۳).", transient=True)
        raise GeminiError("هیچ‌کدوم از مدل‌های Gemini در دسترس نیست (HTTP 404). GEMINI_MODEL رو به یک مدل فعال تغییر بده.",
                          transient=False)
    if _gemini_retired and GEMINI_MODEL in _gemini_retired and model != GEMINI_MODEL:
        logger.warning("Gemini switched to model %s (set GEMINI_MODEL to make it permanent)", model)
        GEMINI_MODEL = model
        _gemini_retired.clear()

    try:
        candidates = payload.get("candidates") or []
        if not candidates:
            err = payload.get("error", {})
            raise RuntimeError(f"Gemini پاسخ برنگرداند: {err}")
        first = candidates[0]
        finish = str(first.get("finishReason") or "").strip().upper()
        parts = first.get("content", {}).get("parts") or []
        text = " ".join(p.get("text", "") for p in parts
                        if isinstance(p.get("text"), str) and not p.get("thought")).strip()
        if finish in {"MAX_TOKENS", "LENGTH"}:
            # اگه با وجود قطع شدن، JSON کامل برگشته بود همون قابل استفاده‌ست
            if text and (not json_mode or _news_agent_parse_json(text)):
                return text
            raise GeminiTruncated("Gemini خروجی را به‌علت محدودیت طول ناقص برگرداند.")
        if text:
            return text
    except RuntimeError:
        raise
    except Exception:
        pass

    raise RuntimeError("Gemini پاسخ متنی برنگرداند.")

def _openrouter_generate_text(prompt: str, *, max_output_tokens: int = 900,
                              timeout: int = 60, temperature: float = 0.2,
                              system_prompt: str | None = None) -> str:
    """اگه Gemini موجوده از اون استفاده کن، وگرنه OpenRouter."""
    if GEMINI_API_KEY:
        return _gemini_generate_text(
            prompt,
            max_output_tokens=max_output_tokens,
            timeout=timeout,
            temperature=temperature,
            system_prompt=system_prompt,
        )

    if not OPENROUTER_API_KEY:
        raise RuntimeError("نه GEMINI_API_KEY و نه OPENROUTER_API_KEY تنظیم نشده است.")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    body_obj = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_output_tokens),
        "reasoning": {"exclude": True},
        "include_reasoning": False,
    }
    req = urllib.request.Request(
        OPENROUTER_CHAT_URL,
        data=json.dumps(body_obj, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "HTTP-Referer": "https://t.me/ariko_tv",
            "X-Title": "ARIKO.TV Anime News Bot",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(_openrouter_http_error_message(e)) from e
    except Exception as e:
        raise RuntimeError(f"ارتباط با OpenRouter ناموفق بود: {e}") from e

    try:
        choices = payload.get("choices") or []
        first_choice = choices[0] if choices else {}
        finish_reason = str(first_choice.get("finish_reason") or "").strip().lower()
        if finish_reason in {"length", "max_tokens"}:
            raise RuntimeError("OpenRouter خروجی خبر را به‌علت محدودیت طول ناقص برگرداند.")
        message = first_choice.get("message") or {}
        content = message.get("content", "")
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    value = item.get("text") or item.get("content")
                    if isinstance(value, str) and value.strip():
                        parts.append(value.strip())
            text = "\n".join(parts).strip()
        else:
            text = ""
        if text:
            return text
    except RuntimeError:
        raise
    except Exception:
        pass

    err = payload.get("error") if isinstance(payload, dict) else None
    if err:
        raise RuntimeError(f"OpenRouter پاسخ خطا برگرداند: {err}")
    raise RuntimeError("OpenRouter پاسخ متنی برنگرداند.")

def _news_strip_cjk(text: str) -> str:
    """نویسه‌های ژاپنی/چینی/کره‌ای را از کپشن فارسی حذف می‌کند؛ نام‌های لاتین حفظ می‌شوند."""
    value = text or ""
    value = re.sub(r"[\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]+", " ", value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    value = re.sub(r"\s+([،؛:,.!?؟])", r"\1", value)
    value = re.sub(r"([،؛:])(?=\S)", r"\1 ", value)
    return value.strip()

def _news_caption_line_is_broken(line: str) -> bool:
    """چند الگوی واضح جمله ناقص/ترجمه خراب را رد می‌کند."""
    s = re.sub(r"\s+", " ", (line or "")).strip(" -–—\t")
    if not s:
        return True
    bad_patterns = (
        r"(?:این انیمه|این اثر|انیمه)\s+توسط\s+(?:است|بود|می‌شود|خواهد بود)[.!؟]*$",
        r"\bتوسط\s*[.!؟]*$",
        r"(?:کارگردان|نویسنده|استودیو|بازیگران|موسیقی|طراحی شخصیت)\s*[:：]\s*[.!؟]*$",
        r"(?:عبارت است از|شامل می‌شود|اعلام شد که)\s*[.!؟]*$",
        r"(?:و|یا|که|با|برای|از|در)\s*[،,.!؟]*$",
    )
    return any(re.search(p, s, flags=re.I) for p in bad_patterns)

def _news_remove_source_and_hashtags(text: str, source_title: str = "") -> str:
    """نام منبع، هشتگ و عبارت‌های تبلیغاتی را بدون حذف اصل خبر از کپشن پاک می‌کند."""
    value = (text or "").strip()
    if not value:
        return ""

    source_norm = re.sub(r"\s+", " ", (source_title or "")).strip().casefold()
    kept_lines = []
    for raw in value.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if line.startswith("#") or re.fullmatch(r"(?:#[^\s#]+\s*)+", line):
            continue

        # ممکن است Agent کل کپشن را در یک خط نوشته باشد؛ جمله منبع را جداگانه حذف کن، نه کل خط را.
        chunks = re.split(r"(?<=[.!؟])\s+", line)
        kept_chunks = []
        for chunk in chunks:
            c = chunk.strip()
            if not c:
                continue
            low = c.casefold()
            is_source_sentence = False
            if source_norm and source_norm in low and any(
                k in low for k in ("منبع", "از سوی", "منتشر", "گزارش", "براساس", "بر اساس")
            ):
                is_source_sentence = True
            if re.search(
                r"(?:این اطلاعات|این خبر|جزئیات)\s+(?:اولیه\s+)?از سوی\s+[^.!؟]{2,100}(?:منتشر|اعلام|گزارش)",
                c, flags=re.I,
            ):
                is_source_sentence = True
            if is_source_sentence:
                continue

            c = re.sub(r"(?<!\S)#[\w\u0600-\u06FF]+", "", c)
            c = re.sub(r"\s{2,}", " ", c).strip()
            if c:
                kept_chunks.append(c)
        if kept_chunks:
            kept_lines.append(" ".join(kept_chunks))

    value = "\n".join(kept_lines).strip()
    # شروع‌های کلیشه‌ای که فقط فضا می‌گیرند و لحن را رباتی می‌کنند.
    value = re.sub(
        r"^(?:🎬\s*)?(?:خبر\s+داغ\s+از\s+دنیای\s+انیمه[!！:：،,.\s]*|خبر\s+داغ[!！:：،,.\s]*)",
        "🎬 ", value, flags=re.I,
    )
    value = value.replace("سریال محبوب ", "").replace("انیمه محبوب ", "انیمه ")
    return re.sub(r"\n{3,}", "\n\n", value).strip()

def _news_extract_final_caption(text: str, source_title: str = "") -> str:
    """فقط کپشن نهایی، کوتاه، مستقیم و سالم فارسی را از خروجی Agent نگه می‌دارد."""
    value = (text or "").strip()
    if not value:
        return ""

    # اگر مدل تگ کامل داده بود فقط محتوا را بگیر؛ در هر حالت خود تگ‌های ناقص/اضافی را هم پاک کن.
    m = re.search(r"<CAPTION>\s*(.*?)\s*</CAPTION>", value, flags=re.I | re.S)
    if m:
        value = m.group(1).strip()
    value = re.sub(r"</?\s*CAPTION\s*>", "", value, flags=re.I)
    value = re.sub(r"</?\s*CAPTION\b[^>]*>", "", value, flags=re.I)

    # حصارهای متنی/Markdown و سربرگ‌های احتمالی مدل را حذف کن.
    value = re.sub(r"^```(?:text|markdown|persian)?\s*", "", value, flags=re.I)
    value = re.sub(r"\s*```$", "", value).strip()
    value = re.sub(r"^\s*(?:FINAL|Final answer|CAPTION|Caption)\s*[:：-]\s*", "", value, flags=re.I)

    # خروجی غیر فارسی/آسیای شرقی را قبول نکن؛ حذف کور می‌تواند جمله را خراب کند.
    if re.search(r"[\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]", value):
        return ""
    value = _news_strip_cjk(value)
    value = _news_remove_source_and_hashtags(value, source_title)
    value = re.sub(r"\n{3,}", "\n\n", value).strip()

    low = value.lower()
    reasoning_markers = (
        "we need to", "we need", "let's compute", "lets compute",
        "let's check", "need to produce", "must use only",
        "the article", "the user", "our task", "i need to",
        "reasoning:", "analysis:", "instructions:", "system prompt",
    )
    if any(marker in low for marker in reasoning_markers):
        return ""

    # این عبارت‌ها معمولاً نشانه لحن کلیشه‌ای/رباتی هستند؛ یک Retry تمیز بهتر از انتشارشان است.
    robotic_markers = (
        "خبر داغ از دنیای انیمه", "خبر داغ", "سریال محبوب", "انیمه محبوب",
        "این اطلاعات اولیه", "در دنیای انیمه", "طرفداران می‌توانند منتظر",
    )
    if any(marker in value for marker in robotic_markers):
        return ""

    # خطوط ناقص را حذف کن؛ اگر نتیجه خیلی کم شد کل خروجی رد شود.
    clean_lines = []
    for raw_line in value.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line or _news_caption_line_is_broken(line):
            continue
        clean_lines.append(line)
    value = "\n".join(clean_lines[:8]).strip()
    if not value:
        return ""

    # محافظ عبارت‌های خراب وسط جمله.
    if re.search(r"(?:این انیمه|این اثر|انیمه)\s+توسط\s+(?:است|بود|می‌شود|خواهد بود)\b", value):
        return ""

    persian_chars = len(re.findall(r"[\u0600-\u06FF]", value))
    latin_chars = len(re.findall(r"[A-Za-z]", value))
    if persian_chars < 14:
        return ""
    # اسم انیمه/استودیو/پلتفرم می‌تواند لاتین باشد، ولی متن غالب باید فارسی بماند.
    if latin_chars > persian_chars * 1.8:
        return ""

    # کپشن نهایی باید با جمله کامل تمام شود.
    if not re.search(r"[.!؟]\s*$", value):
        return ""

    # خروجی رسانه‌ای با جزئیات کنترل‌شده: تا 6 خط و حداکثر حدود 900 کاراکتر.
    if len(value) > 1000:
        return ""
    return value

def _news_caption_is_vague(caption: str, source_text: str = "", title: str = "") -> bool:
    """کپشن‌هایی که اصل اتفاق مشخص خبر را به «خبر تازه‌ای منتشر شد» تقلیل می‌دهند رد می‌کند."""
    value = re.sub(r"\s+", " ", caption or "").strip()
    if not value:
        return True
    vague_patterns = (
        r"خبر\s+(?:تازه|جدید)(?:ی|‌ای)?\s+(?:درباره|از|برای)",
        r"جزئیات\s+(?:تازه|جدید)(?:ی|‌ای)?\s+(?:درباره|از)",
        r"اطلاعات\s+(?:تازه|جدید)(?:ی|‌ای)?\s+(?:درباره|از)",
        r"خبر\s+تازه(?:‌ای|ای)?\s+منتشر\s+شد",
    )
    if not any(re.search(p, value, flags=re.I) for p in vague_patterns):
        return False

    source_low = f"{title} {source_text}".lower()
    explicit_terms = (
        "hiatus", "dies", "died", "death", "passes away", "passed away",
        "live-action", "live action", "adaptation", "starring", "stars ", "cast",
        "director", "premiere", "premieres", "release date", "prime video", "netflix",
        "ends", "ending", "final volume", "final chapter", "cancelled", "canceled",
        "delayed", "postponed", "resumes", "returns", "renewed", "confirmed",
        "season 2", "season 3", "season 4", "sequel", "anime adaptation",
    )
    # اگر منبع اتفاق صریح دارد، کپشن مبهم قابل قبول نیست.
    return any(term in source_low for term in explicit_terms) or len(source_text or "") >= 280

def _news_title_person_after(title: str, marker_pattern: str) -> str:
    m = re.search(marker_pattern, title or "", flags=re.I)
    if not m:
        return ""
    value = re.sub(r"\s+", " ", m.group(1)).strip(" .,:;|-–—")
    value = re.split(r"\s+(?:at|on|after|following|amid|due to|from)\s+", value, maxsplit=1, flags=re.I)[0].strip()
    return value if 2 <= len(value) <= 80 else ""

def _news_live_action_fact_lines(text: str) -> list:
    """چند واقعیت امن و کوتاه برای fallback خبرهای لایو اکشن."""
    raw = re.sub(r"\s+", " ", text or " ").strip()
    facts = []

    platform = _news_streaming_platform(raw)
    if platform:
        facts.append(f"📱 پلتفرم پخش: {platform}")

    # بازیگران اصلی؛ الگوهای رایج press release انگلیسی.
    cast_patterns = [
        r"(?:co-?starring|starring|stars?)\s*[:：]?\s*([^.;]{3,110})",
        r"(?:lead roles?|leads?)\s*[:：]?\s*([^.;]{3,110})",
    ]
    for pat in cast_patterns:
        m = re.search(pat, raw, flags=re.I)
        if m:
            cast = _news_clean_fact_text(m.group(1), 95)
            cast = re.split(r"\s+(?:with|directed by|director|producer|premier|release|on prime|on netflix)\b", cast, maxsplit=1, flags=re.I)[0].strip(" ,")
            if cast and len(cast.split()) <= 16:
                facts.append(f"👥 بازیگران اصلی: {cast}")
                break

    director = ""
    for pat in (r"directed\s+by\s+([^.;,|]{2,70})", r"director\s*[:：]\s*([^.;,|]{2,70})"):
        m = re.search(pat, raw, flags=re.I)
        if m:
            director = _news_clean_fact_text(m.group(1), 65)
            break
    if director:
        facts.append(f"🎬 کارگردان: {director}")

    out = []
    for f in facts:
        if f not in out:
            out.append(f)
    return out[:3]

def _news_specific_fallback_lines(title: str, summary: str, article_text: str,
                                  display_subject: str, target: str, kind: str,
                                  project_label: str, published_at: str = "") -> list:
    """وقتی Agent در دسترس نیست، اتفاق‌های صریح تیتر را به جمله عمومی تبدیل نکن."""
    raw = re.sub(r"\s+", " ", f"{title} {summary} {article_text[:5000]}" or " ").strip()
    low = raw.lower()
    title_low = (title or "").lower()
    lines = []

    # وقفه مانگا/رمان، مخصوصاً در پی درگذشت خالق اثر.
    if any(k in title_low for k in ("goes on hiatus", "go on hiatus", "enters hiatus", "on hiatus", "hiatus")):
        death_related = any(k in title_low for k in (" dies", " died", " death", "passes away", "passed away"))
        creator = _news_title_person_after(
            title,
            r"(?:after|following)\s+(?:creator|author|mangaka|artist|writer)\s+(.{2,80}?)\s+(?:dies|died|passes away|passed away|death)\b",
        )
        if project_label in ("لایو اکشن", "فیلم"):
            noun = target
        elif "manga" in title_low or kind == "manga":
            noun = f"مانگای {display_subject}"
        elif "novel" in title_low:
            noun = f"رمان {display_subject}"
        else:
            noun = target
        if death_related:
            if creator:
                lines.append(f"📚 انتشار {noun} پس از درگذشت خالق اثر، {creator}، وارد وقفه شد.")
            else:
                lines.append(f"📚 انتشار {noun} پس از درگذشت خالق اثر وارد وقفه شد.")
        else:
            lines.append(f"⏸ انتشار {noun} وارد وقفه شد.")
        return lines

    # پایان مانگا/رمان یا جلد نهایی.
    if any(k in title_low for k in ("final volume", "final chapter", "will end", "to end", "ends with volume", "ending with volume")):
        volume = re.search(r"(?:volume|vol\.?)[ -]?(\d{1,3})", title, flags=re.I)
        chapter = re.search(r"chapter[ -]?(\d{1,4})", title, flags=re.I)
        noun = f"مانگای {display_subject}" if ("manga" in title_low or kind == "manga") else target
        if volume:
            lines.append(f"📚 {noun} با جلد {_news_fa_digits(volume.group(1))} به پایان می‌رسد.")
        elif chapter:
            lines.append(f"📚 {noun} با چپتر {_news_fa_digits(chapter.group(1))} به پایان می‌رسد.")
        else:
            lines.append(f"📚 پایان {noun} رسماً اعلام شد.")
        return lines

    # اقتباس لایو اکشن.
    if "live-action" in low or "live action" in low:
        adaptation_words = any(k in low for k in ("adaptation", "drama adaptation", "series adaptation", "to adapt", "gets live-action"))
        if adaptation_words:
            if "novel" in title_low:
                base = f"رمان {display_subject}"
            elif "manga" in title_low:
                base = f"مانگای {display_subject}"
            else:
                base = display_subject
            platform = _news_streaming_platform(raw)
            platform_chunk = f" برای {platform}" if platform else ""
            lines.append(f"🎬 ساخت اقتباس لایو اکشن {base}{platform_chunk} تأیید شد.")
            lines.extend(_news_live_action_fact_lines(raw))
            return lines[:4]

    # اقتباس انیمه از مانگا/رمان.
    if "anime adaptation" in low and any(k in low for k in ("announced", "confirmed", "gets", "receives", "set for", "greenlit")):
        base = display_subject
        if "novel" in title_low:
            base = f"رمان {display_subject}"
        elif "manga" in title_low:
            base = f"مانگای {display_subject}"
        lines.append(f"📺 ساخت اقتباس انیمه‌ای {base} رسماً تأیید شد.")
        return lines

    # درگذشت خالق/نویسنده وقتی خود خبر درباره همین موضوع است.
    if any(k in title_low for k in ("creator dies", "author dies", "mangaka dies", "creator passes away", "author passes away")):
        person = _news_title_person_after(title, r"(?:creator|author|mangaka|artist|writer)\s+(.{2,80}?)\s+(?:dies|died|passes away|passed away)\b")
        if person:
            lines.append(f"🕯 {person}، خالق/نویسنده {display_subject}، درگذشت.")
            return lines

    # تعویق/لغو/ازسرگیری صریح.
    if any(k in title_low for k in ("delayed", "postponed", "delay announced")):
        lines.append(f"⏳ پخش یا انتشار {target} به تعویق افتاد.")
        return lines
    if any(k in title_low for k in ("cancelled", "canceled", "cancellation")):
        lines.append(f"⛔ پروژه {target} لغو شد.")
        return lines
    if any(k in title_low for k in ("resumes", "returns from hiatus", "serialization resumes")):
        noun = f"مانگای {display_subject}" if ("manga" in title_low or kind == "manga") else target
        lines.append(f"▶️ انتشار {noun} پس از وقفه از سر گرفته می‌شود.")
        return lines

    return []

def _news_agent_caption(row) -> str:
    """بدنه خبر/پست را به AI Agent می‌دهد و فقط کپشن رسانه‌ایِ نهایی را قبول می‌کند."""
    if not _ai_api_available():
        return ""
    kind = (row["news_type"] or "news") if "news_type" in row.keys() else "news"
    is_leak = kind == "leak"
    article = (row["article_text"] or "").strip() if "article_text" in row.keys() else ""
    if not article:
        article = (row["summary"] or "").strip()
    if not article:
        return ""

    source_title = (row["source_title"] or "").strip() if "source_title" in row.keys() else ""
    system_prompt = (
        "تو سردبیر یک رسانه فارسی انیمه هستی. فقط کپشن نهایی را بنویس؛ هیچ تحلیل، reasoning یا توضیح دستورها نده. "
        "لحن باید مستقیم، طبیعی و شبیه یک پیج خبری فارسی باشد؛ نه ترجمه لفظ‌به‌لفظ مقاله و نه متن تبلیغاتی. "
        "اصل خبر را در همان جمله اول بگو. نام رسمی انیمه، فیلم، استودیو و پلتفرم را با املای لاتین اصلی حفظ کن. "
        "هیچ نویسه ژاپنی/چینی/کره‌ای، نام منبع، URL یا هشتگ در خروجی نیاور. "
        "کپشن را دقیقاً بین <CAPTION> و </CAPTION> قرار بده و بیرون تگ‌ها هیچ متنی ننویس."
    )
    leak_rules = ""
    if is_leak:
        leak_rules = """
قوانین ویژه این مورد:
- این پست از یک منبع غیررسمی/لیکر آمده و تأیید رسمی محسوب نمی‌شود.
- خط اول حتماً با «⚠️ گزارش غیررسمی:» شروع شود.
- خبر را قطعی ننویس؛ با «طبق گزارشات غیررسمی؛» یا «طبق اطلاعات لو رفته؛» شروع کن (نه «احتمالاً» که حدس به نظر میاد).
"""

    # نام منبع و URL عمداً به Agent داده نمی‌شود تا خودش آن‌ها را داخل کپشن تکرار نکند.
    prompt = f"""برای خبر زیر یک کپشن فارسی کوتاه و رسانه‌ای بساز.

قواعد الزامی:
- فقط از اطلاعات متن زیر استفاده کن و هیچ چیز حدس نزن.
{leak_rules}
- جمله اول باید مستقیم اصل اتفاق را بگوید؛ از شروع‌هایی مثل «خبر داغ»، «در دنیای انیمه»، «سریال محبوب» و مقدمه‌چینی استفاده نکن.
- عبارت‌های کلی و بی‌اطلاعات مثل «خبر تازه‌ای درباره ... منتشر شد»، «خبر جدیدی از ... منتشر شد» و «جزئیات تازه‌ای منتشر شد» ممنوع‌اند؛ اگر تیتر یا متن اتفاق مشخصی مثل وقفه، درگذشت، اقتباس، بازیگران، تاریخ، تمدید، پایان، تأخیر یا پلتفرم را گفته، همان اتفاق را صریح در جمله اول بنویس.
- اگر متن اصلی حداقل دو واقعیت مشخص دارد، کپشن باید حداقل دو واقعیت مشخص را منتقل کند؛ نام اثر به‌تنهایی جزئیات محسوب نمی‌شود.
- کل مقاله را بازنویسی نکن، اما خبر را هم بیش‌ازحد خلاصه نکن. اصل خبر + 3 تا 5 نکته مهم و مرتبط را نگه دار.
- جزئیات فرعی و فهرست طولانی عوامل/بازیگران را حذف کن. اما 1 یا 2 نکته پس‌زمینه‌ای که مستقیماً به فهم اهمیت خبر کمک می‌کند (مثل عملکرد فیلم قبلی، آمار انتشار اثر یا وضعیت بازسازی/ادامه) قابل ذکر است.
- خروجی معمولاً 4 تا 6 خط و حدود 400 تا 800 کاراکتر باشد؛ حداکثر 900 کاراکتر.
- نام منبع، سایت، عبارت «از سوی ... منتشر شد»، URL، لینک منبع، هشتگ و Markdown ممنوع است.
- هیچ صفت تبلیغاتی مثل «محبوب»، «شاهکار»، «هیجان‌انگیز» اضافه نکن مگر عیناً جزو نام اثر باشد.
- اگر دو فیلم/فصل/پروژه هم‌زمان اعلام شده‌اند، همان جمله اول تعداد و نوعشان را واضح بگو.
- برای تریلر/تیزر/ویژوال، جمله اول دقیقاً بگو چه چیزی منتشر شده است.
- نوع خبر را از موضوع اصلی تیتر تشخیص بده، نه از کلمات فرعی متن: اگر تیتر می‌گوید "Anime's New Video ... Theme Songs" آن را موزیک‌ویدیو ننام؛ این خبر درباره ویدیوی/تریلر انیمه است که اطلاعات آهنگ‌ها را هم فاش کرده.
- اگر خبر درباره manga/chapter/volume/chapter cover یا کار مانگاکا است، آن را «پوستر جدید انیمه» ننویس.
- تاریخ‌های قدیمی که فقط در سابقه اثر آمده‌اند را هرگز «تاریخ پخش/اکران/انتشار» خبر فعلی معرفی نکن. فقط تاریخ صریحِ همین پروژه/فصل/فیلم جاری را نگه دار.
- زمان پخش/اکران، استودیو، جزئیات مهم تریلر یا ویژوال و یک یا دو نکته زمینه‌ای مرتبط را در صورت صریح بودن در متن حفظ کن.
- آخرین جمله حتماً کامل باشد و با نقطه/تعجب/سؤال تمام شود.
- اگر خود خبر چند نکته مهم دارد، آن‌ها را حذف نکن فقط برای اینکه متن کوتاه شود؛ اولویت با «اطلاعات مفید و مرتبط» است، نه کمترین تعداد خط.
- متن باید مثل بازنویسی یک ادمین رسانه فارسی باشد: روان، پیوسته و قابل‌فهم؛ نه ترجمه کلمه‌به‌کلمه و نه لیست خشک اطلاعات.

نمونه سبک مطلوب (فقط برای لحن، نه برای کپی اطلاعات):
<CAPTION>🎬 ساخت دو فیلم جدید از ONE PIECE رسماً تأیید شد.
ONE PIECE: GOD VALLEY برای تابستان ۲۰۲۷ و ONE PIECE FILM BAAD برای سال ۲۰۲۹ برنامه‌ریزی شده‌اند.
🎞 استودیو: Toei Animation.</CAPTION>

نمونه دوم:
<CAPTION>🎬 ویژوال جدید انیمه Example Title منتشر شد.
📺 پخش این اثر از اکتبر ۲۰۲۶ آغاز می‌شود و تولید آن برعهده Example Studio است.</CAPTION>

نمونه سبک با جزئیات بیشتر:
<CAPTION>🎬 دو فیلم جدید از ONE PIECE معرفی شدند؛ GOD VALLEY برای تابستان ۲۰۲۷ و FILM BAAD برای سال ۲۰۲۹ برنامه‌ریزی شده‌اند.
📺 ویدیوی معرفی GOD VALLEY روی درگیری راجر و گارپ تمرکز دارد و چند شخصیت کلیدی این آرک را نشان می‌دهد.
🎞 اگر متن منبع اطلاعات زمینه‌ای مهمی مثل عملکرد فیلم قبلی یا وضعیت تولید مجموعه دارد، فقط ۱ یا ۲ مورد مرتبط را کوتاه اضافه کن؛ نه کل تاریخچه اثر.</CAPTION>

عنوان خبر: {row['title']}
تاریخ انتشار: {row['published_at'] or ''}

متن اصلی:
{article[:NEWS_AGENT_MAX_ARTICLE_CHARS]}
"""

    def _try_generate(user_prompt: str, *, tokens: int, temp: float) -> str:
        raw = _openrouter_generate_text(
            user_prompt,
            max_output_tokens=tokens,
            timeout=45,
            temperature=temp,
            system_prompt=system_prompt,
        )
        return _news_extract_final_caption(raw, source_title)

    try:
        text = _try_generate(prompt, tokens=900, temp=0.06)
        if text and not _news_caption_is_vague(text, article, row['title']):
            if is_leak and not text.startswith("⚠️ گزارش غیررسمی"):
                text = "⚠️ گزارش غیررسمی:\n" + text
            return text[:1000]

        # فقط اگر خروجی اول خراب/رباتی بود یک Retry کوتاه انجام می‌شود؛ مصرف رایگان بی‌دلیل دوبرابر نمی‌شود.
        retry_prompt = f"""همین خبر را دوباره بنویس، اما این بار مستقیم، روان و رسانه‌ای.
4 تا 7 خط فارسی. جمله اول باید دقیقاً اتفاق مشخص تیتر را بگوید و بعد 3 تا 5 نکته مهم و مرتبط.
عبارت‌های مبهم «خبر تازه‌ای درباره...»، «خبر جدیدی از...» و «جزئیات تازه‌ای منتشر شد» ممنوع است. وقفه، درگذشت، اقتباس، بازیگر، کارگردان، پلتفرم، تاریخ، پایان یا تأخیر را اگر در متن آمده صریح بنویس.
جزئیات مفید را حذف نکن، ولی فهرست طولانی عوامل، حاشیه‌های نامرتبط، نام منبع، هشتگ، مقدمه و صفت تبلیغاتی ممنوع.
فقط <CAPTION>...</CAPTION> برگردان.
{leak_rules}
عنوان: {row['title']}
متن:
{article[:18000]}
"""
        text = _try_generate(retry_prompt, tokens=820, temp=0.02)
        if text and not _news_caption_is_vague(text, article, row['title']):
            if is_leak and not text.startswith("⚠️ گزارش غیررسمی"):
                text = "⚠️ گزارش غیررسمی:\n" + text
            return text[:1000]

        logger.warning(
            "News OpenRouter Agent output rejected twice for item %s; safe fallback caption will be used.",
            row["id"] if "id" in row.keys() else "?",
        )
    except Exception as e:
        logger.warning("News OpenRouter Agent failed for item %s: %s", row["id"] if "id" in row.keys() else "?", e)
    return ""

def _news_is_anitrendz_source(source_title: str = "", source_url: str = "") -> bool:
    """منبع اختصاصی AniTrendz را تشخیص می‌دهد."""
    st = (source_title or "").strip().casefold()
    su = (source_url or "").strip().casefold()
    return "anitrendz" in st or "anitrendz.com/charts/" in su

def _news_is_animecorner_weekly_source(source_title: str = "", source_url: str = "") -> bool:
    """فقط Poll هفتگی Anime Corner را به‌عنوان Ranking اختصاصی می‌پذیرد."""
    st = (source_title or "").strip().casefold()
    su = (source_url or "").strip().casefold()
    if "anime corner weekly" in st:
        return True
    if "animecorner.me" not in su:
        return False
    return bool(re.search(r"/(?:spring|summer|fall|autumn|winter)-\d{4}-anime-rankings?-week-\d+/?(?:[?#].*)?$", su))

def _news_is_mal_top_airing_source(source_title: str = "", source_url: str = "") -> bool:
    """فقط منبع اختصاصی Top Airing MAL را Ranking ویژه می‌داند؛ MyAnimeList News عادی نیست."""
    st = (source_title or "").strip().casefold()
    su = (source_url or "").strip().casefold()
    if "myanimelist top airing" in st:
        return True
    return "myanimelist.net/topanime.php" in su and "type=airing" in su and "news" not in st

def _news_is_mal_top_alltime_source(source_title: str = "", source_url: str = "") -> bool:
    """منبع Top 10 کل تاریخ MAL که فقط با تغییر ترتیب پست می‌شود."""
    st = (source_title or "").strip().casefold()
    su = (source_url or "").strip().casefold()
    if "myanimelist top anime changes" in st or "myanimelist top all" in st:
        return True
    if "myanimelist" in st and "top anime" in st and "airing" not in st:
        return True
    return "myanimelist.net/topanime.php" in su and "type=airing" not in su and "news" not in st

def _news_is_special_ranking_source(source_title: str = "", source_url: str = "") -> bool:
    return (
        _news_is_anitrendz_source(source_title, source_url)
        or _news_is_animecorner_weekly_source(source_title, source_url)
        or _news_is_mal_top_airing_source(source_title, source_url)
        or _news_is_mal_top_alltime_source(source_title, source_url)
    )

_RANK_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
_RANK_ORDINALS = {1: "اول", 2: "دوم", 3: "سوم"}
_SEASON_EMOJI = {"بهار": "🌸", "تابستان": "🌞", "پاییز": "🍂", "زمستان": "❄️"}

def _ranking_fa_week(week) -> str:
    try:
        n = int(week or 0)
    except Exception:
        return ""
    if n <= 0:
        return ""
    return _news_season_phrase(n) if n <= 12 else _news_fa_digits(str(n))

def _ranking_fa_num(value: str) -> str:
    return _news_fa_digits(str(value)).replace(".", "٫")

def _ranking_character_name(name: str) -> str:
    """AniTrendz اسم رو «Inoue, Orihime» میده → «Orihime Inoue»."""
    name = re.sub(r"\s+", " ", str(name or "")).strip()
    parts = [p.strip() for p in name.split(",")]
    if len(parts) == 2 and all(parts) and " " not in parts[0]:
        return f"{parts[1]} {parts[0]}"
    return name

def _ranking_caption(row) -> str | None:
    """کپشن رنکینگ از داده کامل Top 10 (ranking_payload).

    هر خط با کلمه فارسی شروع میشه تا جهت متن توی تلگرام به‌هم نریزه.
    """
    try:
        chart = json.loads(row["ranking_payload"] or "{}")
    except Exception:
        return None
    if not isinstance(chart, dict):
        return None
    entries = []
    for e in chart.get("entries") or []:
        try:
            rank = int(e.get("rank") or 0)
        except Exception:
            continue
        if 1 <= rank <= 10 and str(e.get("title") or "").strip():
            entries.append(dict(e, rank=rank))
    entries.sort(key=lambda e: e["rank"])
    if len(entries) < 3 or entries[0]["rank"] != 1:
        return None

    url = (row["url"] or "").lower() if "url" in row.keys() else ""
    source = (chart.get("source") or "").lower()
    kind = (chart.get("ranking_kind") or "").strip()
    ctype = (chart.get("chart_type") or "anime").lower()
    season = _news_season_label(chart.get("season") or "")
    year = _news_fa_digits(str(chart.get("year") or "")) if chart.get("year") else ""
    week = _ranking_fa_week(chart.get("week"))
    when = " ".join(x for x in [f"هفته‌ی {week}" if week else "", f"فصل {season}" if season else "", year] if x)

    lines = []
    top_lines = []
    if source == "myanimelist":
        alltime = kind == "top_alltime_change"
        if alltime:
            if (chart.get("change_mode") or "") == "initial":
                lines.append("🏆 ۱۰ انیمه‌ی برتر تاریخ از نگاه کاربران MyAnimeList")
            else:
                lines.append("🔄 رنکینگ ۱۰ انیمه‌ی برتر تاریخ MyAnimeList تغییر کرد!")
        else:
            lines.append(f"📊 رنکینگ هفتگی انیمه‌های در حال پخش MyAnimeList" + (f" | هفته‌ی {week}" if week else ""))
        for e in entries[:3]:
            score = ""
            if e.get("score"):
                score = " با امتیاز " + _ranking_fa_num("%.2f" % float(e.get("score") or 0))
            top_lines.append(f"{_RANK_MEDALS[e['rank']]} رتبه {_RANK_ORDINALS[e['rank']]}: «{e['title']}»{score}")
        if alltime and (chart.get("change_mode") or "") != "initial":
            moves = []
            for e in entries:
                old = int(e.get("previous_rank") or 0)
                if old <= 0:
                    moves.append(f"🆕 «{e['title']}» وارد جمع ۱۰ انیمه‌ی برتر شد.")
                elif old != e["rank"]:
                    arrow = "🔺" if old > e["rank"] else "🔻"
                    moves.append(f"{arrow} «{e['title']}» از رتبه‌ی {_news_fa_digits(str(old))} به {_news_fa_digits(str(e['rank']))} رسید.")
            if moves:
                top_lines.append("")
                top_lines.extend(moves[:4])
    elif source == "animecorner" or "animecorner" in url:
        emoji = _SEASON_EMOJI.get(season, "📊")
        lines.append(f"{emoji} برترین انیمه‌های {when} از نگاه کاربران Anime Corner".replace("  ", " "))
        for e in entries[:3]:
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", str(e.get("detail") or ""))
            vote = f" با {_ranking_fa_num(m.group(1))}٪ آرا" if m else ""
            top_lines.append(f"{_RANK_MEDALS[e['rank']]} رتبه {_RANK_ORDINALS[e['rank']]}: «{e['title']}»{vote}")
    else:  # AniTrendz
        emoji = _SEASON_EMOJI.get(season, "📊")
        if ctype in ("male", "female"):
            who = "مرد" if ctype == "male" else "زن"
            lines.append(f"👑 محبوب‌ترین شخصیت‌های {who} {when} از نگاه کاربران AniTrendz".replace("  ", " "))
            for e in entries[:3]:
                anime = str(e.get("detail") or "").strip()
                from_anime = f" از «{anime}»" if anime else ""
                top_lines.append(f"{_RANK_MEDALS[e['rank']]} رتبه {_RANK_ORDINALS[e['rank']]}: «{_ranking_character_name(e['title'])}»{from_anime}")
        else:
            lines.append(f"{emoji} برترین انیمه‌های {when} از نگاه کاربران AniTrendz".replace("  ", " "))
            for e in entries[:3]:
                top_lines.append(f"{_RANK_MEDALS[e['rank']]} رتبه {_RANK_ORDINALS[e['rank']]}: «{e['title']}»")

    parts = ["\n".join(lines), "\n".join(top_lines)]
    if len(entries) > 3:
        parts.append(f"📋 رتبه‌های ۴ تا {_news_fa_digits(str(len(entries)))} رو توی تصویر ببینید.")
    sig = _news_signature_text()
    if sig:
        parts.append(sig)
    return "\n\n".join(p for p in parts if p.strip())[:1000]

def _news_compose_archive_text(row) -> str:
    """Rankingهای اختصاصی AniTrendz و Anime Corner مستقل‌اند؛ بقیه Rankingها با Agent خلاصه می‌شوند."""
    kind = row["news_type"] or "news"
    article_text = (row["article_text"] or "").strip() if "article_text" in row.keys() else ""
    source_title = row["source_title"] if "source_title" in row.keys() else ""
    source_url = row["url"] if "url" in row.keys() else ""

    if kind == "ranking" and _news_is_special_ranking_source(source_title, source_url):
        try:
            caption = _ranking_caption(row) if "ranking_payload" in row.keys() else None
        except Exception as exc:
            logger.info("Ranking caption failed: %s", exc)
            caption = None
        if caption:
            return caption
        return _build_news_caption(
            row["title"], row["summary"] or "", source_title, source_url,
            kind, row["published_at"] or "", article_text
        )

    # رکوردهای قدیمی MyAnimeList/ANN که قبلاً اشتباه ranking ذخیره شده‌اند هم از همین لحظه
    # مثل یک خبر عادی پردازش شوند تا جمله ساختگی «از دید کاربران ...» تولید نشود.
    if kind == "ranking":
        kind = "news"

    text = _news_agent_caption(row)
    if not text:
        text = _build_news_caption(
            row["title"], row["summary"] or "", row["source_title"], row["url"],
            kind, row["published_at"] or "", article_text
        )
        if kind == "leak" and not text.startswith("⚠️ گزارش غیررسمی"):
            text = "⚠️ گزارش غیررسمی:\n" + text

    # Guard معنایی: خطاهای رایج Agent/مدل رایگان را قبل از تلگرام حذف کن.
    source_blob = f"{row['title']} {row['summary'] or ''} "
    try:
        source_blob += (row['article_text'] or '')[:2500]
    except Exception:
        pass
    source_low = source_blob.lower()
    # theme song به‌تنهایی Music Video نیست.
    if "موزیک‌ویدیو" in (text or "") and "music video" not in source_low:
        text = _build_news_caption(
            row["title"], row["summary"] or "", row["source_title"], row["url"],
            kind, row["published_at"] or "", article_text
        )
    # chapter/volume/manga را به پوستر انیمه تبدیل نکن.
    if re.search(r"\b(?:manga|chapter|volume|mangaka|manga artist)\b", source_low) and "پوستر جدید انیمه" in (text or ""):
        text = _build_news_caption(
            row["title"], row["summary"] or "", row["source_title"], row["url"],
            "manga", row["published_at"] or "", article_text
        )

    # آخرین لایه ایمنی قبل از آرشیو: تگ Agent، CJK، نام منبع و هشتگ هرگز به تلگرام نرسند.
    text = re.sub(r"</?\s*CAPTION\b[^>]*>", "", text or "", flags=re.I)
    text = _news_strip_cjk(text)
    text = _news_remove_source_and_hashtags(text, row["source_title"] if "source_title" in row.keys() else "")

    trailer_url = ""
    try:
        trailer_url = (row["trailer_url"] or "").strip()
    except Exception:
        trailer_url = ""
    if trailer_url and _news_safe_url(trailer_url):
        suffix = f"\n\n🎬 لینک تریلر رسمی:\n{trailer_url}"
        # کپشن عکس تلگرام باید زیر 1024 بماند.
        room = 1000 - len(suffix)
        text = text[:max(300, room)].rstrip()
        text += suffix
    return text[:1000]

def _build_news_caption(title: str, summary: str, source_title: str, source_url: str, kind: str, published_at: str = "", article_text: str = "") -> str:
    """کپشن کوتاه اما اطلاعاتی؛ تمرکز فقط روی خود خبر جاری، نه حاشیه‌های مقاله."""
    all_text = f"{title} {summary}"
    subject, project_label = _news_project_profile(title, summary)
    low = all_text.lower()

    # شماره فصل را ابتدا از خود تیتر بگیر؛ فقط اگر تیتر نداشت از Lead استفاده کن.
    season_num = _news_season_number(title)
    if season_num is None:
        season_num = _news_season_number(summary[:1800])
    season_name = _news_season_phrase(season_num)
    season_chunk = f" فصل {season_name}" if season_name and project_label == "انیمه" else ""

    release_raw = _news_release_phrase(f"{title} {summary[:1400]}")
    if not _news_release_is_plausible(release_raw, published_at):
        release_raw = ""
    release = _news_localize_date(release_raw, published_at)
    studios = _news_studio_phrases(summary[:2600])
    subtitle = _news_subtitle_phrase(f"{title} {summary[:1600]}")
    display_subject = subject
    if subtitle and _news_topic_normalize(subtitle) not in _news_topic_normalize(subject):
        display_subject = f"{display_subject}: {subtitle}"

    ordinal = _news_ordinal_phrase(title)
    lines = []
    mixed_visual_trailer = _news_is_mixed_visual_trailer(title, summary[:1800])

    if kind == "ranking":
        variant = _news_ranking_variant(all_text) or "anime"
        week_num = _news_week_number(all_text)
        week_name = _news_season_phrase(week_num) if week_num else ""
        week_chunk = f" هفته‌ی {week_name}" if week_name else " این هفته"
        season_label = _news_season_label(all_text)
        season_chunk_rank = f" فصل {season_label}" if season_label else ""
        winner = _news_ranking_winner(title)
        is_anitrendz = _news_is_anitrendz_source(source_title, source_url)
        is_animecorner = _news_is_animecorner_weekly_source(source_title, source_url)
        is_mal_top = _news_is_mal_top_airing_source(source_title, source_url)
        is_mal_alltime = _news_is_mal_top_alltime_source(source_title, source_url)
        is_user_poll = is_anitrendz or is_animecorner
        poll_brand = "Anime Corner" if is_animecorner else "AniTrendz"

        if is_mal_top:
            winner = _news_ranking_winner(title)
            score_m = re.search(r"\bSCORE\s+(\d+(?:\.\d+)?)\b", summary or "", flags=re.I)
            score_txt = score_m.group(1) if score_m else ""
            lines.append(f"📊 اسنپ‌شات هفتگی رنکینگ انیمه‌های در حال پخش MyAnimeList منتشر شد.")
            if winner:
                score_chunk = f" با امتیاز {score_txt}/10" if score_txt else ""
                lines.append(f"🔥 انیمه‌ی {winner}{score_chunk} در صدر رنکینگ فعلی Top Airing قرار گرفت.")
        elif is_mal_alltime:
            winner = _news_ranking_winner(title)
            score_m = re.search(r"\bSCORE\s+(\d+(?:\.\d+)?)\b", summary or "", flags=re.I)
            score_txt = score_m.group(1) if score_m else ""
            initial_snapshot = "initial snapshot" in (summary or "").lower()
            if initial_snapshot:
                lines.append("🏆 فهرست ۱۰ انیمه برتر فعلی MyAnimeList ثبت شد.")
            else:
                lines.append("🔄 رتبه‌بندی ۱۰ انیمه برتر MyAnimeList تغییر کرد.")
            if winner:
                score_chunk = f" با امتیاز {score_txt}/10" if score_txt else ""
                lines.append(f"🥇 {winner}{score_chunk} در رتبه اول قرار دارد.")
            if not initial_snapshot:
                lines.append("📈 تغییر رتبه‌ها داخل کارت با ↑ و ↓ مشخص شده است.")
        elif is_user_poll:
            if variant == "male":
                lines.append(f"🏆 بهترین شخصیت مرد{week_chunk}{season_chunk_rank} از دید کاربران {poll_brand}: {winner}" if winner else f"🏆 رتبه‌بندی شخصیت‌های مرد{week_chunk}{season_chunk_rank} از دید کاربران {poll_brand} منتشر شد.")
            elif variant == "female":
                lines.append(f"🏆 بهترین شخصیت زن{week_chunk}{season_chunk_rank} از دید کاربران {poll_brand}: {winner}" if winner else f"🏆 رتبه‌بندی شخصیت‌های زن{week_chunk}{season_chunk_rank} از دید کاربران {poll_brand} منتشر شد.")
            elif variant == "character":
                lines.append(f"🏆 رتبه‌بندی شخصیت‌های برتر{week_chunk}{season_chunk_rank} از دید کاربران {poll_brand} منتشر شد.")
            else:
                emoji = "🌞" if season_label == "تابستان" else "📊"
                lines.append(f"{emoji} لیست برترین انیمه‌های{week_chunk}{season_chunk_rank} از دید کاربران {poll_brand} منتشر شد.")
                if winner:
                    vote = _news_ranking_first_vote(summary)
                    vote_chunk = f" با {vote} از آرا" if vote else ""
                    lines.append(f"🔥 انیمه‌ی {winner}{vote_chunk} در صدر قرار گرفت.")
        else:
            # برای منابع خبری معمولی هرگز ادعا نکن که Ranking «از دید کاربران» همان سایت است.
            if variant == "male":
                lines.append(f"📊 رتبه‌بندی شخصیت‌های مرد{week_chunk}{season_chunk_rank} در {source_title} منتشر شد.")
            elif variant == "female":
                lines.append(f"📊 رتبه‌بندی شخصیت‌های زن{week_chunk}{season_chunk_rank} در {source_title} منتشر شد.")
            elif variant == "character":
                lines.append(f"📊 رتبه‌بندی شخصیت‌ها{week_chunk}{season_chunk_rank} در {source_title} منتشر شد.")
            else:
                lines.append(f"📊 یک گزارش رتبه‌بندی مرتبط با انیمه{week_chunk}{season_chunk_rank} در {source_title} منتشر شد.")
        return "\n".join(lines)[:1000]

    # جمله اصلی بسته به نوع پروژه؛ برای Special/Movie دیگر «انیمه‌ی ...» نمی‌نویسیم.
    if project_label == "انیمه":
        target = f"انیمه‌ی {display_subject}"
    else:
        target = f"{project_label} {display_subject}"

    # اگر Agent شکست خورد، خبرهایی که تیترشان اتفاق مشخصی دارد هرگز به جمله‌ی مبهم
    # «خبر تازه‌ای منتشر شد» تقلیل داده نشوند. article_text فقط برای تشخیص اصل اتفاق و
    # چند واقعیت صریح استفاده می‌شود؛ تاریخ/استودیو همچنان از Lead کنترل‌شده می‌آید.
    specific_lines = _news_specific_fallback_lines(
        title, summary, article_text, display_subject, target, kind, project_label, published_at
    )
    if specific_lines:
        for fact in specific_lines:
            if fact not in lines:
                lines.append(fact)
        if studios and not any("استودیو" in x or "سازنده" in x for x in lines):
            lines.append("")
            lines.append(f"⚙️ {'استودیوی سازنده' if len(studios) == 1 else 'استودیوهای سازنده'}: {'، '.join(studios)}")
        if release:
            lines.append("")
            if project_label == "لایو اکشن" or any(k in low for k in ("movie", "film", "theatrical", "cinema")):
                lines.append(f"📺 تاریخ پخش/انتشار: {release}")
            else:
                lines.append(f"📺 تاریخ پخش: {release}")
        return "\n".join(lines)[:1000]

    if mixed_visual_trailer:
        is_teaser_video = any(k in low for k in ("teaser trailer", "video teaser", "teaser video", "teaser pv"))
        if is_teaser_video:
            lines.append(f"📢 پوستر و تیزر جدید{season_chunk} {target} منتشر شد.")
        elif ordinal == "جدید":
            lines.append(f"📢 پوستر و تریلر جدید{season_chunk} {target} منتشر شد.")
        else:
            lines.append(f"📢 پوستر جدید و {ordinal} تریلر رسمی{season_chunk} {target} منتشر شد.")
    elif kind == "visual":
        plural = any(k in low for k in ("visuals", "posters", "images", "additional visual", "more visual"))
        if project_label != "انیمه":
            lines.append(f"📢 {'تصاویر جدید' if plural else 'تصویر جدید'} {target} منتشر {'شدند' if plural else 'شد'}.")
        elif plural:
            lines.append(f"📢 پوسترها و تصاویر جدید{season_chunk} {target} منتشر شدند.")
        elif "key visual" in low:
            lines.append(f"📢 کی‌ویژوال جدید{season_chunk} {target} منتشر شد.")
        else:
            lines.append(f"📢 پوستر جدید{season_chunk} {target} منتشر شد.")
    elif kind == "trailer":
        title_low = (title or "").lower()
        if " new video " in f" {title_low} " and "trailer" not in title_low and "promotional video" not in title_low and "promo video" not in title_low:
            lines.append(f"🎬 ویدیوی جدید{season_chunk} {target} منتشر شد.")
        elif "teaser" in low and "trailer" not in low:
            lines.append(f"🎬 تیزر جدید{season_chunk} {target} منتشر شد.")
        elif ordinal == "جدید":
            lines.append(f"🎬 تریلر جدید{season_chunk} {target} منتشر شد.")
        else:
            lines.append(f"🎬 {ordinal} تریلر رسمی{season_chunk} {target} منتشر شد.")

        extras = []
        if re.search(r"\b(?:more|new|additional)\s+cast\b|\bcast\b", title_low):
            extras.append("صداپیشه‌های جدید")
        if re.search(r"\b(?:more|new|additional)\s+staff\b|\bstaff\b", title_low):
            extras.append("عوامل تولید")
        if "theme song" in title_low or "theme songs" in title_low:
            extras.append("اطلاعات آهنگ‌های تم")
        if "visual" in title_low:
            extras.append("ویژوال جدید")
        if extras:
            if len(extras) == 1:
                extra_text = extras[0]
            else:
                extra_text = "، ".join(extras[:-1]) + " و " + extras[-1]
            lines.extend(["", f"🔹 در کنار این ویدیو، {extra_text} نیز معرفی شد."])
    elif kind == "music":
        lines.append(f"🎵 موزیک‌ویدیوی جدید {target} منتشر شد.")
    elif kind == "manga":
        manga_subject = display_subject
        # تیترهایی مثل: Artist X Used His Bodybuilder Son as Reference for New Chapter Cover
        if "chapter cover" in low and "reference" in low:
            if "bodybuilder son" in low or "bodybuilding son" in low:
                artist_m = re.search(r"(?:\bArtist\b|\bCreator\b|\bMangaka\b)\s+(.{2,60}?)\s+(?:used|uses)\s+his\s+(?:bodybuilder|bodybuilding)\s+son", title, flags=re.I)
                artist_chunk = artist_m.group(1).strip(" :-–—") if artist_m else "طراح اثر"
                # نام اثر را از ابتدای تیتر/کلید شناخته‌شده بگیر؛ بخش Artist ... جزو نام اثر نیست.
                if " artist " in f" {manga_subject.lower()} ":
                    manga_subject = re.split(r"\s+Artist\s+", manga_subject, maxsplit=1, flags=re.I)[0].strip()
                lines.append(f"📚 {artist_chunk} برای طراحی کاور چپتر جدید مانگای {manga_subject} از پسر بدنسازش به‌عنوان مدل مرجع استفاده کرده است.")
            else:
                lines.append(f"📚 جزئیات تازه‌ای درباره طراحی کاور چپتر جدید مانگای {manga_subject} منتشر شد.")
        elif "chapter cover" in low:
            lines.append(f"📚 کاور چپتر جدید مانگای {manga_subject} منتشر شد.")
        elif "volume" in low and "cover" in low:
            lines.append(f"📚 طرح جلد جدید مانگای {manga_subject} منتشر شد.")
        else:
            lines.append(f"📚 خبر تازه‌ای درباره مانگای {manga_subject} منتشر شد.")
    elif kind == "date":
        lines.append(f"📅 زمان انتشار{season_chunk} {target} مشخص شد.")
    elif kind == "event":
        m = re.search(r"\b(\d{1,3})\s+days?\s+(?:until|to)\b", low)
        lines.append(f"⏳ تنها {_news_fa_digits(m.group(1))} روز تا رویداد مرتبط با {target} باقی مانده است." if m else f"📢 جزئیات تازه‌ای از رویداد مرتبط با {target} منتشر شد.")
    elif kind == "announcement":
        if "new project" in low:
            lines.append(f"📢 پروژه جدیدی مرتبط با {target} معرفی خواهد شد.")
        elif any(k in low for k in ("part 2", "part two", "second part")):
            lines.append(f"📢 جزئیات پارت دوم{season_chunk} {target} منتشر شد.")
        elif any(k in low for k in ("cour 2", "cour two", "second cour", "2nd cour")):
            lines.append(f"📢 جزئیات کور دوم{season_chunk} {target} منتشر شد.")
        elif season_name and any(k in low for k in ("announced", "announcement", "confirmed", "renewed", "new season")):
            lines.append(f"📢 ساخت فصل {season_name} انیمه‌ی {display_subject} رسماً تأیید شد.")
        elif "sequel" in low:
            lines.append(f"📢 ساخت ادامه {target} تأیید شد.")
        else:
            lines.append(f"📢 خبر تازه‌ای درباره {target} منتشر شد.")
        for fact in _news_announcement_facts(f"{title} {summary[:2200]}", display_subject, season_name):
            lines.extend(["", fact])
    elif kind == "cast":
        lines.append(f"📢 صداپیشه‌های جدید{season_chunk} {target} معرفی شدند.")
    elif kind == "studio":
        lines.append(f"📢 اطلاعات تازه‌ای از تیم تولید{season_chunk} {target} منتشر شد.")
    else:
        lines.append(f"📢 خبر جدیدی درباره {target} منتشر شد.")

    # خبر مانگا را با سابقه انیمه/تاریخ‌های قدیمی مقاله آلوده نکن.
    if kind == "manga":
        return "\n".join(lines)[:1200]

    if kind != "announcement":
        for fact in _news_generic_fact_lines(f"{title} {summary[:2200]}", kind, display_subject, season_name):
            if fact not in lines:
                lines.extend(["", fact])

    # نکات محتوایی خود Lead (مثلاً ویژه دو قسمتی، روایت اوسپ، تریلر در راه)
    for fact in _news_project_fact_lines(summary[:2600], display_subject):
        # اگر نوع پروژه همین حالا در تیتر فارسی آمده، دوباره تکرارش نکن.
        if project_label != "انیمه" and fact.startswith("🔹 این پروژه یک ویژه"):
            continue
        if fact not in lines:
            lines.extend(["", fact])

    for fact in _news_context_fact_lines(f"{title} {summary[:2200]}", display_subject, season_name):
        if fact not in lines:
            lines.extend(["", fact])

    if studios:
        lines.append("")
        lines.append(f"⚙️ {'استودیوی سازنده' if len(studios) == 1 else 'استودیوهای سازنده'}: {'، '.join(studios)}")

    if release:
        lines.append("")
        if any(k in low for k in ("movie", "film", "theatrical", "cinema")):
            label = "🎬 تاریخ اکران"
        elif project_label in ("ویژه", "ویژه انیمیشنی", "ویژه انیمیشنی دو قسمتی", "پروژه انیمیشنی"):
            label = "📺 تاریخ انتشار"
        else:
            label = "📺 تاریخ پخش"
        lines.append(f"{label}: {release}")

    while lines and not str(lines[-1]).strip():
        lines.pop()
    return "\n".join(lines)[:1200]

def _news_trailer_reply_caption(title: str, summary: str = "") -> str:
    all_text = f"{title} {summary}"
    subject, project_label = _news_project_profile(title, summary)
    season_num = _news_season_number(title) or _news_season_number(summary[:1400])
    season_name = _news_season_phrase(season_num)
    season_chunk = f" فصل {season_name}" if season_name and project_label == "انیمه" else ""
    target = f"انیمه‌ی {subject}" if project_label == "انیمه" else f"{project_label} {subject}"
    ordinal = _news_ordinal_phrase(title)
    if any(k in all_text.lower() for k in ("teaser trailer", "video teaser", "teaser video", "teaser pv")) or ("teaser" in title.lower() and "visual" not in title.lower() and "trailer" not in title.lower()):
        return f"🎬 تیزر{season_chunk} {target}"
    if ordinal == "جدید":
        return f"🎬 تریلر جدید{season_chunk} {target}"
    return f"🎬 {ordinal} تریلر رسمی{season_chunk} {target}"

def _news_archive_channel():
    value = get_setting("news_archive_channel_id", "").strip()
    if not value:
        value = os.environ.get("NEWS_ARCHIVE_CHANNEL_ID", "").strip()
    if not value:
        return None
    try:
        return int(value) if value.lstrip("-").isdigit() else value
    except Exception:
        return value

def _ensure_anitrendz_source():
    """منابع اختصاصی Ranking (AniTrendz و Anime Corner Weekly) را روی دیتابیس‌های قدیمی تضمین می‌کند.

    چون این منبع RSS عادی نیست، feed_url آن special://anitrendz است. اگر قبلاً
    در دیتابیس وجود نداشته باشد، بدون دست‌زدن به سایر منابع اضافه می‌شود.
    """
    try:
        with db_write_lock:
            conn = db()
            conn.execute(
                "INSERT OR IGNORE INTO news_sources(title, feed_url, site_url, active) VALUES(?,?,?,1)",
                ("AniTrendz", ANITRENDZ_SPECIAL_FEED, "https://www.anitrendz.com/charts/top-anime")
            )
            # اگر رکورد special وجود دارد ولی عنوان/سایت از نسخه آزمایشی قدیمی مانده، مرتبش کن.
            conn.execute(
                "UPDATE news_sources SET title=?, site_url=? WHERE feed_url=?",
                ("AniTrendz", "https://www.anitrendz.com/charts/top-anime", ANITRENDZ_SPECIAL_FEED)
            )
            # Anime Corner Weekly هم مثل AniTrendz یک منبع اختصاصی است تا فقط Poll هفتگی واقعی
            # وارد قالب Ranking شود و اخبار معمولی Anime Corner اشتباه Ranking نشوند.
            conn.execute(
                "INSERT OR IGNORE INTO news_sources(title, feed_url, site_url, active) VALUES(?,?,?,1)",
                ("Anime Corner Weekly", ANIMECORNER_SPECIAL_FEED, "https://animecorner.me/polls/browse/anime-of-the-week")
            )
            conn.execute(
                "UPDATE news_sources SET title=?, site_url=? WHERE feed_url=?",
                ("Anime Corner Weekly", "https://animecorner.me/category/anime-of-the-week/", ANIMECORNER_SPECIAL_FEED)
            )
            # MyAnimeList: منبع اختصاصی Top Airing، جدا از RSS خبری MAL تا خبرهای عادی Ranking نشوند.
            conn.execute(
                "INSERT OR IGNORE INTO news_sources(title, feed_url, site_url, active) VALUES(?,?,?,1)",
                ("MyAnimeList Top Airing", MAL_TOP_AIRING_SPECIAL_FEED, MAL_TOP_AIRING_URL)
            )
            conn.execute(
                "UPDATE news_sources SET title=?, site_url=? WHERE feed_url=?",
                ("MyAnimeList Top Airing", MAL_TOP_AIRING_URL, MAL_TOP_AIRING_SPECIAL_FEED)
            )
            # MyAnimeList Top Anime: Top 10 کل تاریخ؛ فقط با تغییر ترتیب پست جدید می‌سازد.
            conn.execute(
                "INSERT OR IGNORE INTO news_sources(title, feed_url, site_url, active) VALUES(?,?,?,1)",
                ("MyAnimeList Top Anime Changes", MAL_TOP_ALLTIME_SPECIAL_FEED, MAL_TOP_ALLTIME_URL)
            )
            conn.execute(
                "UPDATE news_sources SET title=?, site_url=? WHERE feed_url=?",
                ("MyAnimeList Top Anime Changes", MAL_TOP_ALLTIME_URL, MAL_TOP_ALLTIME_SPECIAL_FEED)
            )
            conn.commit()
            conn.close()
    except Exception:
        logger.exception("Could not ensure AniTrendz news source")

def _news_source_rows(active_only=False):
    _ensure_anitrendz_source()
    conn = db()
    if active_only:
        rows = conn.execute("SELECT * FROM news_sources WHERE active=1 ORDER BY id ASC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM news_sources ORDER BY id ASC").fetchall()
    conn.close()
    return rows

def _news_source_by_id(source_id: int):
    conn = db()
    row = conn.execute("SELECT * FROM news_sources WHERE id=?", (source_id,)).fetchone()
    conn.close()
    return row

def _news_item_by_id(item_id: int):
    conn = db()
    row = conn.execute("""
        SELECT n.*, s.title AS source_title
        FROM news_items n JOIN news_sources s ON s.id=n.source_id
        WHERE n.id=?
    """, (item_id,)).fetchone()
    conn.close()
    return row

def _news_insert_item(source_id: int, item: dict, status="queued") -> int | None:
    topic_key = _news_topic_key(item.get("title", ""), item.get("summary", ""))
    with db_write_lock:
        conn = db()
        try:
            cur = conn.execute("""
                INSERT OR IGNORE INTO news_items(
                    source_id, guid, fingerprint, title, url, published_at, summary, article_text,
                    image_url, video_url, trailer_url, news_type, topic_key, ranking_payload, status
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                source_id, item["guid"], _news_fingerprint(item["title"]), item["title"], item["url"],
                item.get("published_at", ""), item.get("summary", ""), item.get("article_text", ""),
                item.get("image_url", ""), "", item.get("trailer_url", ""),
                item.get("news_type", "news"), topic_key, item.get("ranking_payload", ""), status
            ))
            conn.commit()
            if cur.rowcount == 0:
                return None
            return cur.lastrowid
        finally:
            conn.close()

def _news_mark_source_checked(source_id: int, error: str = ""):
    with db_write_lock:
        conn = db()
        conn.execute(
            "UPDATE news_sources SET last_checked_at=CURRENT_TIMESTAMP, last_error=? WHERE id=?",
            ((error or "")[:500], source_id)
        )
        conn.commit()
        conn.close()

def _news_archive_markup(item_id: int, source_url: str, status: str = "pending"):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("🔗 مشاهده منبع", url=source_url))
    if status == "approved":
        kb.row(
            InlineKeyboardButton("✅ تأیید شده", callback_data=f"news_approve:{item_id}"),
            InlineKeyboardButton("✏️ ویرایش متن", callback_data=f"news_edit:{item_id}")
        )
    else:
        kb.row(
            InlineKeyboardButton("✅ تأیید خبر", callback_data=f"news_approve:{item_id}"),
            InlineKeyboardButton("✏️ ویرایش متن", callback_data=f"news_edit:{item_id}")
        )

    try:
        row = _news_item_by_id(item_id)
    except Exception:
        row = None
    if row and (row["news_type"] or "") != "ranking":
        has_trailer_link = bool((row["trailer_url"] or "").strip()) if "trailer_url" in row.keys() else False
        expects_trailer = has_trailer_link or _news_has_current_video_announcement(row["title"], row["summary"] or "")
        secondary_id = row["archive_secondary_message_id"]
        if secondary_id:
            kb.row(
                InlineKeyboardButton("♻️ تعویض تریلر", callback_data=f"news_trailer_add:{item_id}"),
                InlineKeyboardButton("🗑 حذف تریلر", callback_data=f"news_trailer_del:{item_id}")
            )
        elif expects_trailer:
            kb.add(InlineKeyboardButton("🎬 افزودن تریلر", callback_data=f"news_trailer_add:{item_id}"))

    kb.row(
        InlineKeyboardButton("📤 انتشار", callback_data=f"news_publish:{item_id}"),
        InlineKeyboardButton("🗑 رد کردن", callback_data=f"news_reject:{item_id}")
    )
    return kb

def _send_news_item_to_archive(item_id: int) -> bool:
    row = _news_item_by_id(item_id)
    if not row:
        return False
    archive = _news_archive_channel()
    if not archive:
        return False

    text = row["archive_text"] or _news_compose_archive_text(row)
    kb = _news_archive_markup(item_id, row["url"], row["status"] if row["status"] in ("approved",) else "pending")
    media_type = "text"
    sent = None
    image_url = (row["image_url"] or "").strip()
    chart_card_path = None

    # رکوردهای ranking قدیمی از RSSهای عادی ممکن است فقط پوستر اولین انیمه مقاله را داشته باشند.
    # برای جلوگیری از تصویر گمراه‌کننده، فقط AniTrendz کارت اختصاصی می‌گیرد؛ رکورد قدیمیِ ranking
    # از سایر منابع در صورت نداشتن نشانه واضح chart/ranking به‌صورت متنی ارسال می‌شود.
    if (row["news_type"] or "") == "ranking" and not _news_is_special_ranking_source(
        row["source_title"] if "source_title" in row.keys() else "", row["url"] or ""
    ):
        image_low = image_url.lower()
        if not any(k in image_low for k in ("ranking", "rankings", "chart", "top10", "top-10", "weekly", "poll")):
            image_url = ""

    try:
        # AniTrendz کاملاً مستقل از Agent و سیستم خبر عادی باقی می‌ماند.
        if (row["news_type"] or "") == "ranking" and "anitrendz.com/charts/" in (row["url"] or "").lower():
            try:
                chart_card_path = _anitrendz_build_chart_card(row["url"], row["ranking_payload"] or "")
                if chart_card_path and os.path.exists(chart_card_path):
                    with open(chart_card_path, "rb") as chart_file:
                        sent = bot.send_photo(archive, chart_file, caption=text, reply_markup=kb)
                    media_type = "photo"
            except Exception as e:
                logger.info("AniTrendz chart card failed %s: %s", item_id, e)
                sent = None

        # Anime Corner Weekly هم دقیقاً مثل AniTrendz کارت Top 10 اختصاصی می‌سازد.
        # اگر ساخت کارت به هر دلیل شکست خورد، Featured Image رسمی مقاله fallback باقی می‌ماند.
        if sent is None and (row["news_type"] or "") == "ranking" and _news_is_animecorner_weekly_source(
            row["source_title"] if "source_title" in row.keys() else "", row["url"] or ""
        ):
            try:
                chart_card_path = _animecorner_build_chart_card(row["url"], row["ranking_payload"] or "")
                if chart_card_path and os.path.exists(chart_card_path):
                    with open(chart_card_path, "rb") as chart_file:
                        sent = bot.send_photo(archive, chart_file, caption=text, reply_markup=kb)
                    media_type = "photo"
            except Exception as e:
                logger.info("Anime Corner chart card failed %s: %s", item_id, e)
                sent = None

        # MyAnimeList: هم Top Airing هفتگی و هم Top Anime تغییرمحور از کارت آبی مشترک استفاده می‌کنند.
        if sent is None and (row["news_type"] or "") == "ranking" and (
            _news_is_mal_top_airing_source(
                row["source_title"] if "source_title" in row.keys() else "", row["url"] or ""
            )
            or _news_is_mal_top_alltime_source(
                row["source_title"] if "source_title" in row.keys() else "", row["url"] or ""
            )
        ):
            try:
                chart_card_path = _mal_build_chart_card(row["ranking_payload"] or "")
                if chart_card_path and os.path.exists(chart_card_path):
                    with open(chart_card_path, "rb") as chart_file:
                        sent = bot.send_photo(archive, chart_file, caption=text, reply_markup=kb)
                    media_type = "photo"
            except Exception as e:
                logger.info("MyAnimeList chart card failed %s: %s", item_id, e)
                sent = None

        if sent is None and (row["news_type"] or "") == "ranking" and _news_is_animecorner_weekly_source(
            row["source_title"] if "source_title" in row.keys() else "", row["url"] or ""
        ) and image_url and _news_safe_url(image_url):
            try:
                photo_raw = _animecorner_photo_bytes(image_url)
                photo_file = io.BytesIO(photo_raw)
                photo_file.name = "animecorner_weekly.jpg"
                sent = bot.send_photo(archive, photo_file, caption=text, reply_markup=kb)
                media_type = "photo"
            except Exception as e:
                logger.info("Anime Corner ranking fallback image send failed %s: %s", item_id, e)
                sent = None

        # خبر عادی: اولویت با پوستر/تصویر خبر است. هیچ دانلود تریلری انجام نمی‌شود.
        if sent is None and image_url and _news_safe_url(image_url):
            try:
                sent = bot.send_photo(archive, image_url, caption=text, reply_markup=kb)
                media_type = "photo"
            except Exception as e:
                logger.info("News image send failed %s: %s", item_id, e)
                sent = None

        if sent is None:
            sent = bot.send_message(archive, text, reply_markup=kb, link_preview_options=WITH_LINK_PREVIEW)
            media_type = "text"
    except Exception:
        logger.exception("ارسال خبر %s به آرشیو ناموفق بود", item_id)
        with db_write_lock:
            conn = db()
            conn.execute("UPDATE news_items SET status='queued' WHERE id=?", (item_id,))
            conn.commit()
            conn.close()
        if chart_card_path:
            try:
                os.remove(chart_card_path)
            except Exception:
                pass
        return False

    if chart_card_path:
        try:
            os.remove(chart_card_path)
        except Exception:
            pass

    with db_write_lock:
        conn = db()
        conn.execute("""
            UPDATE news_items
            SET status='pending', archive_chat_id=?, archive_message_id=?,
                archive_media_type=?, archive_text=?
            WHERE id=?
        """, (str(archive), sent.message_id, media_type, text, item_id))
        conn.commit()
        conn.close()
    return True

def _flush_queued_news(limit: int = 20) -> int:
    if not _news_archive_channel():
        return 0
    conn = db()
    rows = conn.execute(
        "SELECT id FROM news_items WHERE status='queued' AND archive_message_id IS NULL ORDER BY id ASC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    done = 0
    for row in rows:
        if _send_news_item_to_archive(row["id"]):
            done += 1
    return done

def _poll_x_leaker_source(source_row, bootstrap: bool = False):
    source_id = source_row["id"]
    handle = _x_leaker_handle_from_feed(source_row["feed_url"])
    if not handle:
        err = "هندل X از Feed قابل تشخیص نیست."
        _news_mark_source_checked(source_id, err)
        return {"new": 0, "seeded": 0, "duplicate": 0, "error": err}
    try:
        entries = _x_leaker_collect(handle)
    except Exception as e:
        _news_mark_source_checked(source_id, str(e))
        logger.warning("X leaker source failed @%s: %s", handle, e)
        return {"new": 0, "seeded": 0, "duplicate": 0, "error": str(e)}

    if not bootstrap:
        # اگه بررسی‌های قبلی همه خطا (مثلاً 429) بودن، هنوز چیزی Seed نشده؛
        # اولین دریافت موفق باید Seed باشه نه انتشار ۳۰ پست قدیمی.
        conn = db()
        has_items = conn.execute("SELECT 1 FROM news_items WHERE source_id=? LIMIT 1", (source_id,)).fetchone()
        conn.close()
        bootstrap = not has_items

    new_count = seeded = dup_count = 0
    for item in reversed(entries[:30]):
        conn = db()
        exists = conn.execute("SELECT 1 FROM news_items WHERE source_id=? AND guid=?", (source_id, item["guid"])).fetchone()
        conn.close()
        if exists:
            continue
        item["news_type"] = "leak"
        item["article_text"] = item.get("article_text") or item.get("summary") or ""
        if bootstrap:
            if _news_insert_item(source_id, item, status="seeded"):
                seeded += 1
            continue
        if _news_is_cross_source_duplicate(item["title"], item["url"]):
            if _news_insert_item(source_id, item, status="duplicate"):
                dup_count += 1
            continue
        item_id = _news_insert_item(source_id, item, status="queued")
        if item_id:
            new_count += 1
            _send_news_item_to_archive(item_id)
    _news_mark_source_checked(source_id, "")
    return {"new": new_count, "seeded": seeded, "duplicate": dup_count, "error": ""}

def _news_type_for_regular_source(source_row, item: dict) -> str:
    """نوع خبر برای RSSهای عادی.

    Ranking به‌صورت اختصاصی از special://anitrendz جمع می‌شود. بنابراین اگر MAL/ANN/Crunchyroll
    یا هر RSS معمولی فقط به‌خاطر کلمات ranking/top به‌عنوان ranking تشخیص داده شد، آن را خبر عادی
    نگه می‌داریم تا Agent متن واقعی مقاله را خلاصه کند.
    """
    detected = _news_type(item.get("title", ""), item.get("summary", ""))
    feed_value = (source_row["feed_url"] or "").strip() if source_row is not None else ""
    source_title = (source_row["title"] or "").strip() if source_row is not None else ""
    if detected == "ranking" and feed_value not in (ANITRENDZ_SPECIAL_FEED, ANIMECORNER_SPECIAL_FEED, MAL_TOP_AIRING_SPECIAL_FEED, MAL_TOP_ALLTIME_SPECIAL_FEED) and not _news_is_special_ranking_source(source_title, item.get("url", "")):
        return "news"
    return detected

def _poll_one_news_source(source_row, bootstrap: bool = False):
    source_id = source_row["id"]
    feed_value = (source_row["feed_url"] or "").strip()
    if feed_value == ANITRENDZ_SPECIAL_FEED:
        return _poll_anitrendz_source(source_row, bootstrap=bootstrap)
    if feed_value == ANIMECORNER_SPECIAL_FEED:
        return _poll_animecorner_source(source_row, bootstrap=bootstrap)
    if feed_value == MAL_TOP_AIRING_SPECIAL_FEED:
        return _poll_mal_top_airing_source(source_row, bootstrap=bootstrap)
    if feed_value == MAL_TOP_ALLTIME_SPECIAL_FEED:
        return _poll_mal_top_alltime_source(source_row, bootstrap=bootstrap)
    if _x_leaker_handle_from_feed(feed_value):
        return _poll_x_leaker_source(source_row, bootstrap=bootstrap)
    try:
        entries = _news_parse_feed(source_row["feed_url"])
    except Exception as e:
        _news_mark_source_checked(source_id, str(e))
        logger.warning("News source failed %s: %s", source_row["title"], e)
        return {"new": 0, "seeded": 0, "duplicate": 0, "error": str(e)}

    if not bootstrap:
        # بررسی‌های قبلی همه خطا بودن → هنوز چیزی Seed نشده؛ خبرهای قدیمی منتشر نشن
        conn = db()
        bootstrap = not conn.execute("SELECT 1 FROM news_items WHERE source_id=? LIMIT 1", (source_id,)).fetchone()
        conn.close()

    new_count = seeded = dup_count = 0
    # قدیمی به جدید تا ترتیب کانال طبیعی باشد.
    for item in reversed(entries[:50]):
        # آیا قبلاً همین GUID در همین منبع ثبت شده؟
        conn = db()
        exists = conn.execute(
            "SELECT 1 FROM news_items WHERE source_id=? AND guid=?",
            (source_id, item["guid"])
        ).fetchone()
        conn.close()
        if exists:
            continue

        if bootstrap:
            item["news_type"] = _news_type_for_regular_source(source_row, item)
            if _news_insert_item(source_id, item, status="seeded"):
                seeded += 1
            continue

        if _news_is_cross_source_duplicate(item["title"], item["url"]):
            item["news_type"] = _news_type_for_regular_source(source_row, item)
            if _news_insert_item(source_id, item, status="duplicate"):
                dup_count += 1
            continue

        item = _news_enrich_article(item)
        item["news_type"] = _news_type_for_regular_source(source_row, item)
        item_id = _news_insert_item(source_id, item, status="queued")
        if item_id:
            new_count += 1
            _send_news_item_to_archive(item_id)

    _news_mark_source_checked(source_id, "")
    return {"new": new_count, "seeded": seeded, "duplicate": dup_count, "error": ""}

def _news_parse_sqlite_timestamp(value: str):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(value[:26], fmt)
        except Exception:
            continue
    return None

def _news_auto_source_due(source_row) -> bool:
    """منابع Ranking سنگین را در loop اصلی هر بار scrape نکن."""
    if source_row is None:
        return True
    feed_value = (source_row["feed_url"] or "").strip()
    min_minutes = {
        ANITRENDZ_SPECIAL_FEED: 60,
        ANIMECORNER_SPECIAL_FEED: 60,
        MAL_TOP_AIRING_SPECIAL_FEED: 120,
        MAL_TOP_ALLTIME_SPECIAL_FEED: 30,
    }.get(feed_value, 0)
    if min_minutes <= 0:
        return True
    last = _news_parse_sqlite_timestamp(source_row["last_checked_at"] or "")
    if last is None:
        return True
    age = datetime.now(timezone.utc).replace(tzinfo=None) - last
    return age.total_seconds() >= min_minutes * 60

def run_news_check(manual=False):
    archive = _news_archive_channel()
    if not archive:
        return {"sources": 0, "new": 0, "seeded": 0, "duplicate": 0, "queued_sent": 0, "skipped": 0, "error": "کانال آرشیو تنظیم نشده."}

    if not news_run_lock.acquire(blocking=False):
        return {"sources": 0, "new": 0, "seeded": 0, "duplicate": 0, "queued_sent": 0, "skipped": 0, "error": "یک بررسی خبر دیگر در حال اجراست."}

    try:
        queued_sent = _flush_queued_news(limit=30)
        total = {"sources": 0, "new": 0, "seeded": 0, "duplicate": 0, "queued_sent": queued_sent, "skipped": 0, "error": ""}
        for source in _news_source_rows(active_only=True):
            total["sources"] += 1
            if not manual and not _news_auto_source_due(source):
                total["skipped"] += 1
                continue
            bootstrap = not bool(source["last_checked_at"])
            result = _poll_one_news_source(source, bootstrap=bootstrap)
            total["new"] += result["new"]
            total["seeded"] += result["seeded"]
            total["duplicate"] += result["duplicate"]
        return total
    finally:
        news_run_lock.release()

def _news_check_interval_minutes() -> int:
    try:
        val = int(get_setting("news_check_minutes", str(NEWS_DEFAULT_CHECK_MINUTES)))
    except Exception:
        val = NEWS_DEFAULT_CHECK_MINUTES
    return max(NEWS_MIN_CHECK_MINUTES, min(val, 1440))

def news_collector_loop():
    # کمی بعد از بالا آمدن ربات شروع شود تا init و polling پایدار شوند.
    time.sleep(30)
    while True:
        started = time.monotonic()
        try:
            if _news_archive_channel():
                result = run_news_check(manual=False)
                logger.info("News collector cycle: %s", result)
        except Exception:
            logger.exception("News collector loop failed")
        finally:
            gc.collect()
            logger.info("News collector cycle finished in %.1fs", time.monotonic() - started)
        time.sleep(_news_check_interval_minutes() * 60)

def start_news_collector_thread():
    _ensure_anitrendz_source()
    t = threading.Thread(target=news_collector_loop, daemon=True, name="news-collector")
    t.start()

def show_news_admin_menu(chat_id: int, user_id: int, text: str | None = None):
    if user_id not in ADMINS:
        return
    _ensure_anitrendz_source()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🔄 بررسی اخبار الان"))
    kb.add(KeyboardButton("🧪 تست رنکینگ هفتگی"))
    kb.add(KeyboardButton("➕ افزودن منبع خبری"))
    kb.add(KeyboardButton("📋 منابع خبری"))
    kb.add(KeyboardButton("📦 تنظیم کانال آرشیو خبر"))
    kb.add(KeyboardButton("⏱ فاصله بررسی اخبار"))
    kb.add(KeyboardButton("📊 آمار آرشیو اخبار"))
    kb.add(KeyboardButton(BACK_MAIN))
    archive = _news_archive_channel()
    status = f"\n📦 کانال آرشیو: {archive}" if archive else "\n⚠️ کانال آرشیو هنوز تنظیم نشده."
    trailer_status = "\n🎬 دانلود خودکار تریلر: حذف شده ✅ | افزودن فایل توسط ادمین"
    if GEMINI_API_KEY:
        agent_status = f"\n🤖 Agent اخبار: Google Gemini فعال ✅ ({GEMINI_MODEL})"
    elif OPENROUTER_API_KEY:
        agent_status = f"\n🤖 Agent اخبار: OpenRouter فعال ✅ ({OPENROUTER_MODEL})"
    else:
        agent_status = "\n🤖 Agent اخبار: کلید API تنظیم نشده ⚠️"
    anitrendz_status = "\n📊 AniTrendz مستقیم: فعال ✅"
    chart_card_status = "\n🖼 کارت تصویری AniTrendz: فعال ✅" if Image is not None else "\n🖼 کارت تصویری AniTrendz: برای Top 10 کامل، Pillow نصب شود ⚠️"
    bot.send_message(chat_id, (text or "📰 مدیریت اخبار:") + status + trailer_status + agent_status + anitrendz_status + chart_card_status, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📰 مدیریت اخبار")
def news_admin_entry(message):
    if message.from_user.id not in ADMINS:
        return
    show_news_admin_menu(message.chat.id, message.from_user.id)

@bot.message_handler(func=lambda m: m.text == "🧪 تست رنکینگ هفتگی")
def weekly_ranking_test_menu(message):
    """پیش‌نمایش دستی سه رنکینگ هفتگی بدون ثبت در DB یا دست‌زدن به زمان‌بندی اصلی."""
    if message.from_user.id not in ADMINS:
        return
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🟡 AniTrendz — Top Anime", callback_data="weekly_rank_test:anitrendz"))
    kb.add(InlineKeyboardButton("🔴 Anime Corner — Top Anime", callback_data="weekly_rank_test:animecorner"))
    kb.add(InlineKeyboardButton("🔵 MyAnimeList — Top Airing", callback_data="weekly_rank_test:mal"))
    kb.add(InlineKeyboardButton("❌ بستن", callback_data="weekly_rank_test:close"))
    bot.send_message(
        message.chat.id,
        "🧪 تست رنکینگ هفتگی\n\nیکی از ۳ منبع رو انتخاب کن.\n"
        "این فقط پیش‌نمایشه و هیچ رکوردی در آرشیو ذخیره نمی‌کنه؛ انتشار خودکار هفتگی هم مثل قبل ادامه پیدا می‌کنه.",
        reply_markup=kb,
    )

def _weekly_test_anitrendz_item() -> dict:
    items = _anitrendz_collect_current()
    # AniTrendz سه Chart دارد؛ برای تست هفتگی این منو فقط Top Anime را نشان می‌دهد.
    for item in items:
        try:
            payload = json.loads(item.get("ranking_payload") or "{}")
        except Exception:
            payload = {}
        if (payload.get("chart_type") or "").strip().lower() == "anime":
            return item
    raise ValueError("Top Anime فعلی AniTrendz پیدا نشد.")

def _weekly_test_build(source_key: str) -> tuple[str, str, str]:
    """(path, caption, source_label) را برمی‌گرداند؛ هیچ DB write انجام نمی‌دهد."""
    if source_key == "anitrendz":
        item = _weekly_test_anitrendz_item()
        path = _anitrendz_build_chart_card(item.get("url") or "", item.get("ranking_payload") or "")
        label = "AniTrendz — Top Anime"
    elif source_key == "animecorner":
        items = _animecorner_collect_current()
        if not items:
            raise ValueError("رنکینگ فعلی Anime Corner دریافت نشد.")
        item = items[0]
        path = _animecorner_build_chart_card(item.get("url") or "", item.get("ranking_payload") or "")
        label = "Anime Corner — Top Anime"
    elif source_key == "mal":
        cached_used = False
        try:
            items = _mal_collect_weekly_top_airing()
            if not items:
                raise ValueError("رنکینگ هفتگی MyAnimeList دریافت نشد.")
            item = items[0]
        except Exception as live_error:
            cached = _mal_latest_cached_weekly_item()
            if not cached:
                raise live_error
            item = cached
            cached_used = True
            logger.warning("MAL preview using cached weekly snapshot after live failure: %s", live_error)
        path = _mal_build_chart_card(item.get("ranking_payload") or "")
        label = "MyAnimeList — Top Airing" + (" (آخرین Snapshot ذخیره‌شده)" if cached_used else "")
    else:
        raise ValueError("منبع تست نامعتبر است.")

    if not path or not os.path.exists(path):
        raise ValueError(f"ساخت کارت {label} ناموفق بود.")

    caption = (
        f"🧪 پیش‌نمایش تستی — {label}\n\n"
        "این پیام فقط برای تست ادمین ساخته شده و در آرشیو خبر ثبت نمی‌شود.\n"
        "⏱ انتشار خودکار اصلی طبق روال هفتگی خودش ادامه دارد."
    )
    return path, caption, label

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("weekly_rank_test:"))
def weekly_ranking_test_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return

    source_key = (call.data or "").split(":", 1)[1]
    if source_key == "close":
        bot.answer_callback_query(call.id, "بسته شد.")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            try:
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            except Exception:
                pass
        return

    labels = {
        "anitrendz": "AniTrendz",
        "animecorner": "Anime Corner",
        "mal": "MyAnimeList",
    }
    label = labels.get(source_key, "Ranking")
    bot.answer_callback_query(call.id, f"در حال ساخت {label}…")
    chat_id = call.message.chat.id

    def worker():
        path = None
        status_msg = None
        if not weekly_ranking_test_lock.acquire(blocking=False):
            bot.send_message(chat_id, "⏳ یک تست رنکینگ دیگه هنوز در حال ساخته‌شدنه. بعد از تموم شدنش دوباره بزن.")
            return
        try:
            status_msg = bot.send_message(chat_id, f"⏳ در حال دریافت داده و ساخت پیش‌نمایش {label}…")
            path, caption, _ = _weekly_test_build(source_key)
            with open(path, "rb") as fh:
                bot.send_photo(chat_id, fh, caption=caption)
        except Exception as e:
            logger.exception("Weekly ranking preview failed source=%s", source_key)
            bot.send_message(chat_id, f"❌ ساخت پیش‌نمایش {label} ناموفق بود:\n{e}")
        finally:
            if status_msg is not None:
                try:
                    bot.delete_message(chat_id, status_msg.message_id)
                except Exception:
                    pass
            if path:
                try:
                    os.remove(path)
                except Exception:
                    pass
            weekly_ranking_test_lock.release()

    threading.Thread(target=worker, daemon=True, name=f"weekly-ranking-test-{source_key}").start()

@bot.message_handler(func=lambda m: m.text == "📦 تنظیم کانال آرشیو خبر")
def news_archive_set_start(message):
    if message.from_user.id not in ADMINS:
        return
    msg = bot.send_message(
        message.chat.id,
        "📦 یک پیام از کانال آرشیو خصوصی Forward کن، یا آیدی کانال / @username / لینک t.me را بفرست.\n"
        "ربات باید داخل کانال ادمین و اجازه ارسال پیام داشته باشد.",
        reply_markup=create_markup_with_back()
    )
    bot.register_next_step_handler(msg, news_archive_set_finish)

def news_archive_set_finish(message):
    uid = message.from_user.id
    if message.text == BACK_MAIN:
        show_news_admin_menu(message.chat.id, uid)
        return

    channel = None
    try:
        origin = getattr(message, "forward_origin", None)
        o_chat = getattr(origin, "chat", None) if origin else None
        if o_chat and getattr(o_chat, "type", None) == "channel":
            channel = o_chat.id
    except Exception:
        pass

    if channel is None:
        raw = (message.text or "").strip()
        if not raw:
            msg = bot.send_message(message.chat.id, "❌ کانال تشخیص داده نشد. دوباره بفرست:", reply_markup=create_markup_with_back())
            bot.register_next_step_handler(msg, news_archive_set_finish)
            return
        try:
            channel = normalize_channel_id_value(raw)
        except Exception as e:
            msg = bot.send_message(message.chat.id, f"❌ آیدی کانال نامعتبر است: {e}\nدوباره بفرست:", reply_markup=create_markup_with_back())
            bot.register_next_step_handler(msg, news_archive_set_finish)
            return

    try:
        test = bot.send_message(channel, "✅ کانال آرشیو اخبار ARIKO.TV با موفقیت به ربات متصل شد.")
        set_setting("news_archive_channel_id", str(channel))
        bot.send_message(message.chat.id, f"✅ کانال آرشیو ثبت شد: {channel}\nاز بررسی بعدی، خبرهای جدید وارد این کانال می‌شوند.")
        show_news_admin_menu(message.chat.id, uid)
    except Exception as e:
        msg = bot.send_message(
            message.chat.id,
            f"❌ ربات نتونست داخل این کانال پیام بفرسته:\n{e}\n\nربات رو ادمین کن و دوباره تلاش کن:",
            reply_markup=create_markup_with_back()
        )
        bot.register_next_step_handler(msg, news_archive_set_finish)

@bot.message_handler(func=lambda m: m.text == "➕ افزودن منبع خبری")
def news_source_add_start(message):
    if message.from_user.id not in ADMINS:
        return
    msg = bot.send_message(message.chat.id, "📰 اسم منبع رو بفرست؛ مثلاً Anime Corner:", reply_markup=create_markup_with_back())
    bot.register_next_step_handler(msg, news_source_add_get_title)

def news_source_add_get_title(message):
    if message.text == BACK_MAIN:
        show_news_admin_menu(message.chat.id, message.from_user.id)
        return
    title = (message.text or "").strip()
    if not title:
        msg = bot.send_message(message.chat.id, "❌ اسم خالیه. دوباره بفرست:", reply_markup=create_markup_with_back())
        bot.register_next_step_handler(msg, news_source_add_get_title)
        return
    update_state(message.from_user.id, news_source_title=title)
    msg = bot.send_message(
        message.chat.id,
        "🔗 لینک سایت، RSS/Atom یا پروفایل X / اینستاگرام رو بفرست.\nبرای لیکر X می‌تونی لینک https://x.com/username یا خود @username رو بفرستی.\nبرای اینستاگرام لینک https://instagram.com/username یا ig:username رو بفرست.\nاگر سایت RSS معرفی کرده باشه، ربات سعی می‌کنه خودکار پیداش کنه:",
        reply_markup=create_markup_with_back()
    )
    bot.register_next_step_handler(msg, news_source_add_get_url)

def news_source_add_get_url(message):
    uid = message.from_user.id
    if message.text == BACK_MAIN:
        show_news_admin_menu(message.chat.id, uid)
        return
    raw_url = (message.text or "").strip()
    title = get_state(uid).get("news_source_title", "منبع خبری")
    bot.send_message(message.chat.id, "⏳ در حال پیدا کردن و تست فید منبع...")
    try:
        feed_url, site_url = _news_discover_feed(raw_url)
        x_test_note = ""
        if _social_handle_label(feed_url):
            # X/اینستاگرام زیاد 429 میده؛ نباید جلوی ثبت منبع رو بگیره. کالکتور بعداً خودش دوباره تلاش می‌کنه.
            try:
                _news_parse_feed(feed_url)
            except Exception as e:
                x_test_note = f"\n\n⚠️ الان خوندن پست‌ها ممکن نشد ({str(e)[:200]})؛ منبع ثبت شد و در بررسی‌های بعدی دوباره امتحان میشه."
        else:
            # یک بار parse هم برای اعتبار واقعی؛ AniTrendz با Parser اختصاصی تست می‌شود.
            entries = _news_parse_feed(feed_url)
            if not entries:
                raise ValueError("منبع پیدا شد ولی خبر/Chart قابل خواندن داخلش نبود.")
        with db_write_lock:
            conn = db()
            conn.execute(
                "INSERT INTO news_sources(title, feed_url, site_url, active) VALUES(?,?,?,1)",
                (title[:120], feed_url, site_url)
            )
            conn.commit()
            conn.close()
        bot.send_message(
            message.chat.id,
            f"✅ منبع اضافه شد.\n📰 {title}\n🔗 Feed: {feed_url}\n\n"
            + ("AniTrendz مستقیم از Chartها خونده می‌شه و رتبه‌بندی جاری در اولین بررسی هم قابل ارسال است."
               if feed_url in (ANITRENDZ_SPECIAL_FEED, ANIMECORNER_SPECIAL_FEED, MAL_TOP_AIRING_SPECIAL_FEED, MAL_TOP_ALLTIME_SPECIAL_FEED)
               else ("این پیج اینستاگرام ثبت شد؛ پست‌های فعلی در اولین بررسی فقط Seed می‌شن و پست‌های بعدی بررسی میشن."
                     if _instagram_username_from_feed(feed_url)
                     else "این حساب X به‌عنوان منبع غیررسمی/لیکر ثبت شد؛ پست‌های فعلی در اولین بررسی فقط Seed می‌شن و خبرهای بعدی با برچسب «گزارش غیررسمی» می‌آیند."
                     if _x_leaker_handle_from_feed(feed_url)
                     else "در اولین بررسی، خبرهای فعلی فقط به‌عنوان «دیده‌شده» ثبت می‌شن تا آرشیو با خبرهای قدیمی پر نشه."))
            + x_test_note
        )
    except sqlite3.IntegrityError:
        bot.send_message(message.chat.id, "⚠️ این فید قبلاً ثبت شده.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ نتونستم منبع رو اضافه کنم:\n{e}")
    show_news_admin_menu(message.chat.id, uid)

@bot.message_handler(func=lambda m: m.text == "📋 منابع خبری")
def news_sources_list(message):
    if message.from_user.id not in ADMINS:
        return
    rows = _news_source_rows(active_only=False)
    if not rows:
        bot.send_message(message.chat.id, "هیچ منبع خبری ثبت نشده.")
        show_news_admin_menu(message.chat.id, message.from_user.id)
        return
    for row in rows:
        icon = "🟢" if row["active"] else "⚪️"
        last = row["last_checked_at"] or "هنوز بررسی نشده"
        err = f"\n⚠️ {row['last_error'][:120]}" if row["last_error"] else ""
        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(
            InlineKeyboardButton("⏸ غیرفعال" if row["active"] else "▶️ فعال", callback_data=f"news_src_toggle:{row['id']}"),
            InlineKeyboardButton("🗑 حذف", callback_data=f"news_src_delete:{row['id']}")
        )
        kb.add(InlineKeyboardButton("🔗 باز کردن سایت", url=row["site_url"] or row["feed_url"]))
        feed_label = _social_handle_label(row["feed_url"]) or f"Feed: {row['feed_url']}"
        bot.send_message(
            message.chat.id,
            f"{icon} #{row['id']} — {row['title']}\n"
            f"{feed_label}\nآخرین بررسی: {last}{err}",
            reply_markup=kb,
            link_preview_options=NO_LINK_PREVIEW
        )

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("news_src_toggle:"))
def news_source_toggle_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    try:
        source_id = int(call.data.split(":", 1)[1])
        found = False
        with db_write_lock:
            conn = db()
            try:
                row = conn.execute("SELECT active FROM news_sources WHERE id=?", (source_id,)).fetchone()
                if row:
                    found = True
                    new_val = 0 if row["active"] else 1
                    conn.execute("UPDATE news_sources SET active=? WHERE id=?", (new_val, source_id))
                    conn.commit()
            finally:
                conn.close()
        if not found:
            bot.answer_callback_query(call.id, "منبع پیدا نشد.")
            return
        bot.answer_callback_query(call.id, "✅ وضعیت منبع تغییر کرد.")
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
    except Exception as e:
        bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("news_src_delete:"))
def news_source_delete_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    try:
        source_id = int(call.data.split(":", 1)[1])
        with db_write_lock:
            conn = db()
            conn.execute("DELETE FROM news_sources WHERE id=?", (source_id,))
            conn.commit()
            conn.close()
        bot.answer_callback_query(call.id, "🗑 منبع حذف شد.")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
    except Exception as e:
        bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

@bot.message_handler(func=lambda m: m.text == "⏱ فاصله بررسی اخبار")
def news_interval_start(message):
    if message.from_user.id not in ADMINS:
        return
    current = _news_check_interval_minutes()
    msg = bot.send_message(
        message.chat.id,
        f"⏱ فاصله فعلی: هر {current} دقیقه\nعدد جدید رو بفرست (حداقل {NEWS_MIN_CHECK_MINUTES} دقیقه):",
        reply_markup=create_markup_with_back()
    )
    bot.register_next_step_handler(msg, news_interval_finish)

def news_interval_finish(message):
    uid = message.from_user.id
    if message.text == BACK_MAIN:
        show_news_admin_menu(message.chat.id, uid)
        return
    try:
        minutes = int((message.text or "").strip())
        if minutes < NEWS_MIN_CHECK_MINUTES or minutes > 1440:
            raise ValueError
        set_setting("news_check_minutes", str(minutes))
        bot.send_message(message.chat.id, f"✅ فاصله بررسی روی هر {minutes} دقیقه تنظیم شد.")
    except Exception:
        bot.send_message(message.chat.id, f"❌ عدد باید بین {NEWS_MIN_CHECK_MINUTES} تا 1440 دقیقه باشه.")
    show_news_admin_menu(message.chat.id, uid)

@bot.message_handler(func=lambda m: m.text == "🔄 بررسی اخبار الان")
def news_check_now(message):
    if message.from_user.id not in ADMINS:
        return
    if not _news_archive_channel():
        bot.send_message(message.chat.id, "❌ اول کانال آرشیو خبر رو تنظیم کن.")
        show_news_admin_menu(message.chat.id, message.from_user.id)
        return
    admin_chat = message.chat.id
    admin_id = message.from_user.id
    bot.send_message(admin_chat, "🔄 بررسی منابع خبری شروع شد؛ نتیجه چند لحظه دیگه میاد.")

    def worker():
        try:
            result = run_news_check(manual=True)
            bot.send_message(
                admin_chat,
                "✅ بررسی اخبار تمام شد.\n"
                f"📡 منابع فعال: {result['sources']}\n"
                f"📰 خبر جدید: {result['new']}\n"
                f"📚 ثبت اولیه/قدیمی: {result['seeded']}\n"
                f"♻️ خبر مشابه حذف‌شده: {result['duplicate']}\n"
                f"📤 صف ارسال‌شده: {result['queued_sent']}"
            )
        except Exception as e:
            bot.send_message(admin_chat, f"❌ خطا در بررسی اخبار: {e}")
        finally:
            try:
                show_news_admin_menu(admin_chat, admin_id)
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True, name="manual-news-check").start()

@bot.message_handler(func=lambda m: m.text == "📊 آمار آرشیو اخبار")
def news_stats(message):
    if message.from_user.id not in ADMINS:
        return
    conn = db()
    total = conn.execute("SELECT COUNT(*) AS c FROM news_items").fetchone()["c"]
    pending = conn.execute("SELECT COUNT(*) AS c FROM news_items WHERE status IN ('queued','pending')").fetchone()["c"]
    approved = conn.execute("SELECT COUNT(*) AS c FROM news_items WHERE status='approved'").fetchone()["c"]
    published = conn.execute("SELECT COUNT(*) AS c FROM news_items WHERE status='published'").fetchone()["c"]
    duplicate = conn.execute("SELECT COUNT(*) AS c FROM news_items WHERE status='duplicate'").fetchone()["c"]
    today = conn.execute("SELECT COUNT(*) AS c FROM news_items WHERE created_at >= datetime('now','-1 day') AND status NOT IN ('seeded','duplicate')").fetchone()["c"]
    conn.close()
    bot.send_message(
        message.chat.id,
        "📊 آمار آرشیو اخبار\n\n"
        f"📰 کل رکوردها: {total}\n"
        f"🕐 منتظر بررسی/صف: {pending}\n"
        f"✅ تأییدشده: {approved}\n"
        f"📤 منتشرشده: {published}\n"
        f"♻️ مشابه/تکراری: {duplicate}\n"
        f"🆕 خبر جدید ۲۴ ساعت اخیر: {today}"
    )
    show_news_admin_menu(message.chat.id, message.from_user.id)

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("news_approve:"))
def news_approve_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    try:
        item_id = int(call.data.split(":", 1)[1])
        row = _news_item_by_id(item_id)
        if not row:
            bot.answer_callback_query(call.id, "خبر پیدا نشد.")
            return
        with db_write_lock:
            conn = db()
            conn.execute("UPDATE news_items SET status='approved' WHERE id=?", (item_id,))
            conn.commit()
            conn.close()
        bot.answer_callback_query(call.id, "✅ خبر تأیید شد.")
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id,
                reply_markup=_news_archive_markup(item_id, row["url"], "approved")
            )
        except Exception:
            pass
    except Exception as e:
        bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("news_reject:"))
def news_reject_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    try:
        item_id = int(call.data.split(":", 1)[1])
        row = _news_item_by_id(item_id)
        with db_write_lock:
            conn = db()
            conn.execute("UPDATE news_items SET status='rejected' WHERE id=?", (item_id,))
            conn.commit()
            conn.close()
        bot.answer_callback_query(call.id, "🗑 خبر رد شد.")
        # در خبرهای ترکیبی اول تریلرِ ریپلای‌شده و بعد پوستر اصلی پاک شود.
        if row and row["archive_secondary_message_id"]:
            try:
                bot.delete_message(call.message.chat.id, int(row["archive_secondary_message_id"]))
            except Exception:
                pass
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
    except Exception as e:
        bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("news_edit:"))
def news_edit_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    item_id = int(call.data.split(":", 1)[1])
    row = _news_item_by_id(item_id)
    if not row:
        bot.answer_callback_query(call.id, "خبر پیدا نشد.")
        return
    bot.answer_callback_query(call.id, "پیام ویرایش به خصوصی ارسال شد.")
    try:
        current = row["archive_text"] or ""
        msg = bot.send_message(
            call.from_user.id,
            "✏️ متن جدید خبر رو بفرست.\n"
            "برای خبر عکس/ویدیو، متن باید حداکثر 1024 کاراکتر باشه.\n\n"
            f"متن فعلی:\n{current}",
            reply_markup=create_markup_with_back()
        )
        update_state(call.from_user.id, news_edit_item_id=item_id)
        bot.register_next_step_handler(msg, news_edit_finish)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ نتونستم پیام خصوصی بفرستم: {e}")

def news_edit_finish(message):
    uid = message.from_user.id
    if message.text == BACK_MAIN:
        show_news_admin_menu(message.chat.id, uid)
        return
    item_id = get_state(uid).get("news_edit_item_id")
    row = _news_item_by_id(item_id) if item_id else None
    if not row:
        bot.send_message(message.chat.id, "❌ خبر پیدا نشد.")
        return
    new_text = (message.text or "").strip()
    media_type = row["archive_media_type"] or "text"
    limit = 1024 if media_type in ("photo", "video") else 4096
    if not new_text or len(new_text) > limit:
        msg = bot.send_message(message.chat.id, f"❌ متن باید بین 1 تا {limit} کاراکتر باشه. دوباره بفرست:", reply_markup=create_markup_with_back())
        bot.register_next_step_handler(msg, news_edit_finish)
        return
    archive_chat = int(row["archive_chat_id"]) if str(row["archive_chat_id"] or "").lstrip("-").isdigit() else row["archive_chat_id"]
    kb = _news_archive_markup(item_id, row["url"], "approved" if row["status"] == "approved" else "pending")
    try:
        if media_type in ("photo", "video"):
            bot.edit_message_caption(new_text, chat_id=archive_chat, message_id=row["archive_message_id"], reply_markup=kb)
        else:
            bot.edit_message_text(new_text, chat_id=archive_chat, message_id=row["archive_message_id"], reply_markup=kb, link_preview_options=WITH_LINK_PREVIEW)
        with db_write_lock:
            conn = db()
            conn.execute("UPDATE news_items SET archive_text=? WHERE id=?", (new_text, item_id))
            conn.commit()
            conn.close()
        bot.send_message(message.chat.id, "✅ متن خبر در آرشیو ویرایش شد.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ ویرایش انجام نشد: {e}")
    show_news_admin_menu(message.chat.id, uid)

def _news_post_channels_with_ids():
    conn = db()
    rows = conn.execute("SELECT id, channel_id, title FROM post_channels ORDER BY id ASC").fetchall()
    conn.close()
    return rows

def _news_related_reply_message(post_channel_id: int, topic_key: str, exclude_item_id: int | None = None):
    if not topic_key:
        return None
    conn = db()
    if exclude_item_id:
        row = conn.execute("""
            SELECT message_id FROM news_publications
            WHERE post_channel_id=? AND topic_key=? AND item_id<>?
            ORDER BY id DESC LIMIT 1
        """, (post_channel_id, topic_key, exclude_item_id)).fetchone()
    else:
        row = conn.execute("""
            SELECT message_id FROM news_publications
            WHERE post_channel_id=? AND topic_key=?
            ORDER BY id DESC LIMIT 1
        """, (post_channel_id, topic_key)).fetchone()
    conn.close()
    return int(row["message_id"]) if row and row["message_id"] else None

def _news_store_publication(item_id: int, post_channel_id: int, channel_id, message_id: int, topic_key: str):
    with db_write_lock:
        conn = db()
        conn.execute("""
            INSERT INTO news_publications(item_id, post_channel_id, channel_id, message_id, topic_key)
            VALUES(?,?,?,?,?)
            ON CONFLICT(item_id, post_channel_id) DO UPDATE SET
                channel_id=excluded.channel_id,
                message_id=excluded.message_id,
                topic_key=excluded.topic_key,
                created_at=CURRENT_TIMESTAMP
        """, (item_id, post_channel_id, str(channel_id), int(message_id), topic_key))
        conn.commit()
        conn.close()

def _publish_news_item(item_id: int, post_channel_id: int, admin_id: int):
    item = _news_item_by_id(item_id)
    if not item or not item["archive_message_id"]:
        raise ValueError("پیام آرشیو خبر پیدا نشد.")
    conn = db()
    ch = conn.execute("SELECT id, channel_id, title FROM post_channels WHERE id=?", (post_channel_id,)).fetchone()
    conn.close()
    if not ch:
        raise ValueError("کانال مقصد پیدا نشد.")

    source_chat = int(item["archive_chat_id"]) if str(item["archive_chat_id"] or "").lstrip("-").isdigit() else item["archive_chat_id"]
    target = normalize_channel_id_value(ch["channel_id"])
    topic_key = item["topic_key"] or _news_topic_key(item["title"], item["summary"] or "")
    reply_to = _news_related_reply_message(post_channel_id, topic_key, exclude_item_id=item_id)

    kwargs = {"reply_markup": None}
    if reply_to:
        kwargs["reply_to_message_id"] = reply_to
        kwargs["allow_sending_without_reply"] = True

    result = bot.copy_message(target, source_chat, item["archive_message_id"], **kwargs)
    message_id = getattr(result, "message_id", None)
    if message_id is None:
        try:
            message_id = int(result)
        except Exception:
            raise ValueError("آیدی پیام منتشرشده دریافت نشد.")

    # اگر خبر در آرشیو تریلرِ دوم هم داشته باشد، بعد از پوستر کپی و به همان پوستر ریپلای شود.
    secondary_id = item["archive_secondary_message_id"]
    if secondary_id:
        try:
            bot.copy_message(
                target, source_chat, int(secondary_id),
                reply_markup=None,
                reply_to_message_id=message_id,
                allow_sending_without_reply=True,
            )
        except Exception as e:
            logger.warning("کپی تریلر ثانویه خبر %s ناموفق بود: %s", item_id, e)

    # ریشه خبر (پوستر اصلی) ذخیره می‌شود تا خبرهای بعدی همین موضوع به آن ریپلای شوند.
    _news_store_publication(item_id, post_channel_id, target, message_id, topic_key)
    with db_write_lock:
        conn = db()
        conn.execute("UPDATE news_items SET status='published', topic_key=? WHERE id=?", (topic_key, item_id))
        conn.commit()
        conn.close()
    return ch["title"]

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("news_publish:"))
def news_publish_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    item_id = int(call.data.split(":", 1)[1])
    channels = _news_post_channels_with_ids()
    if not channels:
        bot.answer_callback_query(call.id, "اول از مدیریت کانال‌های پست، کانال مقصد اضافه کن.", show_alert=True)
        return
    if len(channels) == 1:
        try:
            title = _publish_news_item(item_id, channels[0]["id"], call.from_user.id)
            bot.answer_callback_query(call.id, f"✅ در {title} منتشر شد.", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)
        return

    kb = InlineKeyboardMarkup()
    for ch in channels:
        kb.add(InlineKeyboardButton(f"📤 {ch['title']}", callback_data=f"news_pub:{item_id}:{ch['id']}"))
    try:
        bot.send_message(call.from_user.id, "📤 خبر در کدام کانال منتشر بشه؟", reply_markup=kb)
        bot.answer_callback_query(call.id, "لیست کانال‌ها به خصوصی ارسال شد.")
    except Exception:
        bot.answer_callback_query(call.id, "نتونستم به خصوصی پیام بدم.", show_alert=True)

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("news_pub:"))
def news_publish_target_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    try:
        _prefix, item_s, ch_s = call.data.split(":", 2)
        title = _publish_news_item(int(item_s), int(ch_s), call.from_user.id)
        bot.answer_callback_query(call.id, f"✅ در {title} منتشر شد.", show_alert=True)
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
    except Exception as e:
        bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("news_trailer_add:"))
def news_trailer_add_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    try:
        item_id = int(call.data.split(":", 1)[1])
        row = _news_item_by_id(item_id)
        if not row or not row["archive_message_id"]:
            bot.answer_callback_query(call.id, "خبر آرشیو پیدا نشد.", show_alert=True)
            return
        bot.answer_callback_query(call.id, "فایل تریلر را در خصوصی بفرست.")
        trailer_url = (row["trailer_url"] or "").strip() if "trailer_url" in row.keys() else ""
        hint = f"\n\n🔗 لینک تریلر برای کپی:\n{trailer_url}" if trailer_url else ""
        msg = bot.send_message(
            call.from_user.id,
            "🎬 فایل تریلر را همین‌جا ارسال یا از ربات دانلودر Forward کن.\n"
            "ربات از file_id تلگرام استفاده می‌کند و فایل روی هاست ذخیره نمی‌شود."
            + hint,
            reply_markup=create_markup_with_back()
        )
        update_state(call.from_user.id, news_trailer_item_id=item_id)
        bot.register_next_step_handler(msg, news_trailer_receive)
    except Exception as e:
        bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

def news_trailer_receive(message):
    uid = message.from_user.id
    if uid not in ADMINS:
        return
    if message.text == BACK_MAIN:
        show_news_admin_menu(message.chat.id, uid)
        return
    item_id = get_state(uid).get("news_trailer_item_id")
    row = _news_item_by_id(item_id) if item_id else None
    if not row or not row["archive_message_id"]:
        bot.send_message(message.chat.id, "❌ خبر آرشیو پیدا نشد.")
        return

    file_id = None
    media_kind = None
    if getattr(message, "video", None):
        file_id = message.video.file_id
        media_kind = "video"
    elif getattr(message, "document", None):
        file_id = message.document.file_id
        media_kind = "document"
    elif getattr(message, "animation", None):
        file_id = message.animation.file_id
        media_kind = "animation"

    if not file_id:
        msg = bot.send_message(
            message.chat.id,
            "❌ فایل ویدیویی تشخیص داده نشد. ویدیو یا فایل دانلودشده را ارسال/فوروارد کن:",
            reply_markup=create_markup_with_back()
        )
        bot.register_next_step_handler(msg, news_trailer_receive)
        return

    archive_chat = int(row["archive_chat_id"]) if str(row["archive_chat_id"] or "").lstrip("-").isdigit() else row["archive_chat_id"]
    old_secondary = row["archive_secondary_message_id"]
    caption = _news_trailer_reply_caption(row["title"], row["summary"] or "")
    kwargs = {
        "caption": caption,
        "reply_to_message_id": int(row["archive_message_id"]),
        "allow_sending_without_reply": True,
    }
    try:
        if media_kind == "video":
            sent = bot.send_video(archive_chat, file_id, supports_streaming=True, **kwargs)
        elif media_kind == "animation":
            sent = bot.send_animation(archive_chat, file_id, **kwargs)
        else:
            sent = bot.send_document(archive_chat, file_id, **kwargs)

        # اول پیام جدید با موفقیت ارسال شود، بعد قبلی حذف شود.
        if old_secondary and int(old_secondary) != sent.message_id:
            try:
                bot.delete_message(archive_chat, int(old_secondary))
            except Exception:
                pass

        with db_write_lock:
            conn = db()
            conn.execute(
                "UPDATE news_items SET archive_secondary_message_id=?, archive_secondary_media_type=? WHERE id=?",
                (sent.message_id, media_kind, item_id)
            )
            conn.commit()
            conn.close()

        try:
            fresh = _news_item_by_id(item_id)
            bot.edit_message_reply_markup(
                archive_chat, int(row["archive_message_id"]),
                reply_markup=_news_archive_markup(item_id, fresh["url"], "approved" if fresh["status"] == "approved" else "pending")
            )
        except Exception:
            pass
        bot.send_message(message.chat.id, "✅ تریلر بدون ذخیره روی هاست به همان خبر اضافه شد.")
        clear_state(uid)
        show_news_admin_menu(message.chat.id, uid)
    except Exception as e:
        msg = bot.send_message(message.chat.id, f"❌ ارسال تریلر ناموفق بود: {e}\nدوباره فایل را بفرست:")
        bot.register_next_step_handler(msg, news_trailer_receive)

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("news_trailer_del:"))
def news_trailer_delete_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    try:
        item_id = int(call.data.split(":", 1)[1])
        row = _news_item_by_id(item_id)
        if not row or not row["archive_secondary_message_id"]:
            bot.answer_callback_query(call.id, "تریلری ثبت نشده.")
            return
        archive_chat = int(row["archive_chat_id"]) if str(row["archive_chat_id"] or "").lstrip("-").isdigit() else row["archive_chat_id"]
        try:
            bot.delete_message(archive_chat, int(row["archive_secondary_message_id"]))
        except Exception:
            pass
        with db_write_lock:
            conn = db()
            conn.execute(
                "UPDATE news_items SET archive_secondary_message_id=NULL, archive_secondary_media_type=NULL WHERE id=?",
                (item_id,)
            )
            conn.commit()
            conn.close()
        fresh = _news_item_by_id(item_id)
        try:
            bot.edit_message_reply_markup(
                archive_chat, int(row["archive_message_id"]),
                reply_markup=_news_archive_markup(item_id, fresh["url"], "approved" if fresh["status"] == "approved" else "pending")
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id, "🗑 تریلر حذف شد.")
    except Exception as e:
        bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

NEWS_V2_DEFAULT_CHECK_MINUTES = 10

NEWS_V2_MIN_CHECK_MINUTES = 5

NEWS_V2_PREVIEW_LIMIT = 25

NEWS_V2_SUPPORTED_EVENTS = {
    "season_announcement", "trailer", "trailer_visual", "visual", "release_date",
    "delay", "cancellation", "new_anime", "character_pv", "movie", "other",
}

news_v2_run_lock = threading.Lock()

# =========================
# امتیاز اهمیت خبر — فقط خبرهای مهم وارد آرشیو میشن
# =========================
NEWS_IMPORTANCE_BASE = {
    "season_announcement": 85, "new_anime": 85, "cancellation": 85,
    "delay": 75, "release_date": 75, "movie": 70,
    "trailer": 65, "trailer_visual": 65,
    "character_pv": 45, "visual": 45, "other": 25,
}

_NEWS_IMPORTANCE_UP = [
    (r"\b(?:final|last)\s+episode\b|\b(?:double-length|hour-long|extended|\d{2}-minute)\s+(?:episode|finale)\b"
     r"|\bepisode\s+\d+\b.{0,60}\b(?:minutes?|runtime)\b", 30, "قسمت پایانی/طول قسمت"),
    (r"\bbox\s+office\b|\bbillion\s+yen\b|\brecord[- ]breaking\b|\bbreaks?\s+(?:the\s+)?record\b", 20, "گیشه/رکورد"),
    (r"\b(?:leak(?:ed|s)?|rumou?r(?:ed|s)?|reportedly|registered|rating\s+board|trademark(?:ed)?)\b", 15, "لیک/گزارش"),
    (r"\b(?:finale|concludes?|final\s+season|ending\s+confirmed)\b", 15, "پایان سری"),
    (r"\b(?:netflix|crunchyroll|disney\+?|amazon)\b.{0,60}\b(?:exclusive|acquires?|licens\w*)\b", 10, "پلتفرم"),
]

_NEWS_IMPORTANCE_DOWN = [
    # مقاله‌های تحلیلی/نقد/راهنما خبر نیستن
    (r"\b(?:explained|explainer|review|recap|reactions?|guide|everything\s+(?:we|you)\s+know|what\s+to\s+expect"
     r"|ranked|should\s+you\s+watch|theor(?:y|ies)|essay|opinion|editorial|listicle|\d+\s+(?:best|things|reasons))\b"
     r"|\bwhere\s+to\s+(?:watch|stream)\b|\bhow\s+to\s+watch\b|\bwatch\s+order\b|\bbest\s+anime\b",
     -60, "مقاله تحلیلی/غیرخبری"),
    (r"\bmusic\s+video\b|\b(?:new\s+)?single\b|\balbum\b|\bconcert\b|\blive\s+tour\b|\bsong\b", -35, "موسیقی"),
    (r"\b(?:figures?|merch(?:andise)?|cafe|pop-up|exhibition|stage\s+play|musical|pachinko|lottery|blu-ray|dvd|artbook|apparel)\b",
     -30, "محصول/رویداد جانبی"),
    (r"\b(?:video\s+game|mobile\s+game|gacha|visual\s+novel|game)\b", -25, "بازی"),
    (r"\b(?:manga|light\s+novel)\b", -10, "مانگا/رمان"),
    (r"\b(?:english\s+dub|dub\s+cast|english\s+cast)\b", -15, "دوبله انگلیسی"),
    (r"\b(?:film\s+fest(?:ival)?|screens|screening)\b", -15, "جشنواره/اکران محدود"),
]

def _news_min_importance() -> int:
    try:
        return max(0, min(100, int(get_setting("news_min_importance", "55") or 55)))
    except Exception:
        return 55

def _news_importance(title: str, summary: str, event_type: str, source_class: str, meta: dict) -> tuple:
    """(امتیاز ۰ تا ۱۰۰, دلیل‌ها)"""
    text = _news_v2_clean_title_text(f"{title} {(summary or '')[:600]}").casefold()
    score = NEWS_IMPORTANCE_BASE.get(event_type, 25)
    reasons = [f"نوع خبر {score}"]
    anime_about = re.search(r"\banime\b|\bseason\s+\d|\bepisode\b|\bfilm\b|\bmovie\b", text)
    for pattern, delta, label in _NEWS_IMPORTANCE_UP:
        if re.search(pattern, text):
            score += delta
            reasons.append(f"+{delta} {label}")
    for pattern, delta, label in _NEWS_IMPORTANCE_DOWN:
        if re.search(pattern, text):
            # «بازی» و «مانگا» اگه خبر واقعاً درباره انیمه‌اش باشه جریمه نداره
            if label in ("بازی", "مانگا/رمان") and anime_about:
                continue
            score += delta
            reasons.append(f"{delta} {label}")
    pop = int((meta or {}).get("popularity") or 0)
    if pop >= 300_000:
        score += 20
        reasons.append("+20 انیمه خیلی محبوب")
    elif pop >= 100_000:
        score += 12
        reasons.append("+12 انیمه محبوب")
    elif pop >= 30_000:
        score += 5
        reasons.append("+5 انیمه شناخته‌شده")
    elif 0 < pop < 5_000:
        # انیمه‌ای که هنوز پخش نشده طبیعتاً محبوبیت کمی توی AniList داره؛ جریمه فقط برای اثرهای قدیمی‌تر
        try:
            started = int((meta or {}).get("year") or 0)
        except Exception:
            started = 0
        if started and started < datetime.now().year:
            score -= 10
            reasons.append("-10 انیمه کم‌مخاطب")
    if source_class in ("official", "official_media"):
        score += 5
        reasons.append("+5 منبع رسمی")
    return max(0, min(100, score)), reasons

def _news_v2_score_item(item_id: int) -> int:
    """امتیاز اهمیت رو حساب و داخل facts ذخیره می‌کنه."""
    row = _news_v2_item_by_id(item_id)
    if not row:
        return 0
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except Exception:
        facts = {}
    meta = {}
    name = facts.get("anime_eng_name") or facts.get("anime_display") or ""
    if name and name != "این انیمه":
        try:
            meta = _news_anilist_lookup(name)
        except Exception:
            meta = {}
    score, reasons = _news_importance(row["title"] or "", row["summary"] or "", row["event_type"] or "other",
                                      row["source_class"] or "", meta)
    facts["importance"] = score
    facts["importance_reasons"] = reasons
    with db_write_lock:
        conn = db()
        conn.execute("UPDATE news_v2_items SET facts_json=? WHERE id=?", (json.dumps(facts, ensure_ascii=False), item_id))
        conn.commit()
        conn.close()
    return score

def _news_v2_mark_low(item_id: int):
    with db_write_lock:
        conn = db()
        conn.execute("UPDATE news_v2_items SET status='low' WHERE id=?", (item_id,))
        conn.commit()
        conn.close()


ranking_run_lock = threading.Lock()

def _news_v2_init_db():
    with db_write_lock:
        conn = db()
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS news_v2_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            guid TEXT NOT NULL,
            signature TEXT,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            published_at TEXT,
            summary TEXT,
            article_text TEXT,
            image_url TEXT,
            video_url TEXT,
            event_type TEXT NOT NULL DEFAULT 'other',
            source_class TEXT NOT NULL DEFAULT 'secondary',
            anime_key TEXT,
            anime_display TEXT,
            anime_eng_name TEXT,
            confidence INTEGER NOT NULL DEFAULT 0,
            facts_json TEXT,
            caption TEXT,
            status TEXT NOT NULL DEFAULT 'seeded',
            archive_chat_id TEXT,
            archive_message_id INTEGER,
            archive_secondary_message_id INTEGER,
            archive_media_type TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_id, guid)
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS news_v2_source_state(
            source_id INTEGER PRIMARY KEY,
            bootstrapped INTEGER NOT NULL DEFAULT 0,
            last_checked_at TEXT,
            last_error TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS news_v2_publications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            post_channel_id INTEGER NOT NULL,
            channel_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            anime_key TEXT NOT NULL,
            event_type TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(item_id, post_channel_id)
        )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_nv2_items_status ON news_v2_items(status, id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_nv2_items_anime ON news_v2_items(anime_key, event_type, id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_nv2_items_signature ON news_v2_items(signature)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_nv2_pub_anime ON news_v2_publications(post_channel_id, anime_key, id)")
        conn.commit()
        conn.close()

def _news_v2_is_ranking_source(source_row) -> bool:
    if source_row is None:
        return False
    feed = (source_row["feed_url"] or "").strip()
    title = (source_row["title"] or "").strip()
    return feed in (
        ANITRENDZ_SPECIAL_FEED,
        ANIMECORNER_SPECIAL_FEED,
        MAL_TOP_AIRING_SPECIAL_FEED,
        MAL_TOP_ALLTIME_SPECIAL_FEED,
    ) or _news_is_special_ranking_source(title, source_row["site_url"] or feed)

def _news_v2_source_rows(active_only: bool = True):
    conn = db()
    if active_only:
        rows = conn.execute("SELECT * FROM news_sources WHERE active=1 ORDER BY id ASC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM news_sources ORDER BY id ASC").fetchall()
    conn.close()
    return [r for r in rows if not _news_v2_is_ranking_source(r)]

def _news_v2_source_state(source_id: int):
    conn = db()
    row = conn.execute("SELECT * FROM news_v2_source_state WHERE source_id=?", (source_id,)).fetchone()
    conn.close()
    return row

def _news_v2_mark_source(source_id: int, error: str = "", bootstrapped: bool | None = None):
    old = _news_v2_source_state(source_id)
    boot = int(bool(bootstrapped)) if bootstrapped is not None else int(old["bootstrapped"] if old else 0)
    with db_write_lock:
        conn = db()
        conn.execute("""
            INSERT INTO news_v2_source_state(source_id, bootstrapped, last_checked_at, last_error)
            VALUES(?,?,CURRENT_TIMESTAMP,?)
            ON CONFLICT(source_id) DO UPDATE SET
                bootstrapped=excluded.bootstrapped,
                last_checked_at=CURRENT_TIMESTAMP,
                last_error=excluded.last_error
        """, (source_id, boot, (error or "")[:500]))
        # برای صفحه منابع هم آخرین وضعیت قابل مشاهده باشد؛ Rankingها چون در V2 نیستند دست نخورند.
        conn.execute(
            "UPDATE news_sources SET last_checked_at=CURRENT_TIMESTAMP, last_error=? WHERE id=?",
            ((error or "")[:500], source_id),
        )
        conn.commit()
        conn.close()

def _news_v2_source_class(source_row, item_url: str = "") -> str:
    feed = (source_row["feed_url"] or "").strip()
    title = (source_row["title"] or "").strip().lower()
    site = (source_row["site_url"] or item_url or "").lower()
    if _x_leaker_handle_from_feed(feed):
        return "leak"
    if "official" in title:
        return "official"
    if "crunchyroll" in title or "crunchyroll.com" in site:
        return "official_media"
    if "animenewsnetwork" in site or "anime news network" in title:
        return "secondary"
    if "myanimelist" in site or "myanimelist" in title:
        return "secondary"
    return "secondary"

def _news_v2_clean_title_text(value: str) -> str:
    value = _news_strip_cjk(value or "")
    value = _news_strip_html(value)
    return re.sub(r"\s+", " ", value).strip()

def _news_v2_event_type(title: str, summary: str = "") -> str:
    # نوع خبر عمداً بیشتر از تیتر و خلاصه کوتاه استخراج می‌شود تا سابقه تاریخی داخل مقاله
    # باعث تشخیص اشتباه «خبر جدید» نشود.
    t = _news_v2_clean_title_text(f"{title} {(summary or '')[:900]}")
    low = t.casefold()

    if re.search(r"\b(?:cancelled|canceled|cancellation)\b", low):
        return "cancellation"
    if re.search(r"\b(?:delayed|delay|postponed|postponement|rescheduled)\b", low):
        return "delay"

    character = bool(re.search(
        r"\b(?:character\s+(?:trailer|pv|video|promo)|character-focused\s+(?:trailer|pv)|introduces?\s+(?:the\s+)?character)\b",
        low,
    ))
    if character:
        return "character_pv"

    has_trailer = bool(re.search(
        r"\b(?:trailer|teaser|promotional\s+video|promo\s+video|\bpv\b|main\s+pv|teaser\s+pv)\b",
        low,
    ))
    has_visual = bool(re.search(r"\b(?:key\s+visual|teaser\s+visual|new\s+visual|visual|poster)\b", low))
    if has_trailer and has_visual:
        return "trailer_visual"
    if has_trailer:
        return "trailer"
    if has_visual:
        return "visual"

    season_announce = bool(
        re.search(r"\bseason\s+\d{1,2}\b.{0,100}\b(?:announced|confirmed|greenlit|green-lit|production|in\s+production|gets|receives)\b", low)
        or re.search(r"\b(?:announced|confirmed|greenlit|green-lit|gets|receives)\b.{0,100}\bseason\s+\d{1,2}\b", low)
        or re.search(r"\b(?:sequel|new\s+season)\b.{0,80}\b(?:announced|confirmed|greenlit|production)\b", low)
    )
    if season_announce:
        return "season_announcement"

    if re.search(r"\b(?:anime\s+adaptation|tv\s+anime|new\s+anime)\b.{0,100}\b(?:announced|revealed|greenlit|gets|receives)\b", low) \
       or re.search(r"\b(?:gets|receives|inspires)\b.{0,80}\b(?:tv\s+)?anime\b", low):
        return "new_anime"

    if re.search(r"\b(?:film|movie)\b.{0,100}\b(?:announced|revealed|greenlit|premiere|release)\b", low):
        return "movie"

    release_word = re.search(r"\b(?:premiere|premieres|air|airs|broadcast|release\s+date|debuts?|starts?\s+airing|returns?)\b", low)
    if release_word and _news_release_phrase(t):
        return "release_date"
    return "other"

def _news_v2_variant(text: str) -> str:
    low = (text or "").casefold()
    variants = [
        (r"\b(?:1st|first)\b", "first"),
        (r"\b(?:2nd|second)\b", "second"),
        (r"\b(?:3rd|third)\b", "third"),
        (r"\bfinal\b", "final"),
        (r"\bmain\b", "main"),
    ]
    for pat, name in variants:
        if re.search(pat, low):
            return name
    return ""

def _news_v2_match_anime(title: str, summary: str = ""):
    # اول Match قطعی با دیتابیس خود بات؛ سپس Subject محافظه‌کارانه برای آثار ثبت‌نشده.
    # فقط تیتر: اسم انیمه‌های دیگه داخل خلاصه (مثلاً «از سازنده X») باعث تشخیص اشتباه میشد.
    hay = _normalize_anime_search_text(_news_v2_clean_title_text(title))
    conn = db()
    rows = conn.execute("SELECT eng_name, fa_name, COALESCE(jp_name,'') AS jp_name FROM anime").fetchall()
    conn.close()
    best = None
    for row in rows:
        eng = row["eng_name"] or ""
        fa = row["fa_name"] or ""
        jp = row["jp_name"] or ""
        for field in (eng, fa, jp):
            norm = _normalize_anime_search_text(field)
            if len(norm) < 4:
                continue
            if norm in hay:
                score = 100 + min(len(norm), 80)
                if best is None or score > best[0]:
                    best = (score, eng, fa)
    if best:
        _score, eng, fa = best
        return normalize_eng(eng), eng, eng, True

    subject = _news_display_subject(title, summary)
    subject = _news_v2_clean_title_text(subject)
    if not subject or subject.casefold() in ("this anime", "the anime", "این انیمه"):
        subject = _news_v2_clean_title_text(title)
        # رویدادهای انتهای تیتر را تا حد ممکن حذف کن.
        subject = re.split(
            r"\s+(?:season\s+\d+|trailer|teaser|key\s+visual|visual|poster|premieres?|release\s+date|announced|revealed)\b",
            subject,
            maxsplit=1,
            flags=re.I,
        )[0].strip(" :-–—|\"'“”")
    # کوتیشن‌های دور اسم (مثل 'Katainaka no Ossan') توی «» زشت میشن
    subject = subject.strip(" \"'“”‘’`")
    subject = subject[:120] or "این انیمه"
    key = _news_topic_normalize(subject)[:120]
    return key or hashlib.sha1(title.encode("utf-8", errors="ignore")).hexdigest()[:20], "", subject, False

def _news_v2_extract_facts(item: dict, source_class: str, event_type: str) -> dict:
    title = _news_v2_clean_title_text(item.get("title", ""))
    summary = _news_v2_clean_title_text(item.get("summary", ""))
    headline = f"{title} {summary[:1200]}".strip()
    article = _news_v2_clean_title_text(item.get("article_text", ""))
    production_text = f"{headline} {article[:2600]}".strip()

    anime_key, anime_eng, anime_display, known = _news_v2_match_anime(title, summary)
    season_no = _news_season_number(headline)
    release_raw = _news_release_phrase(headline)
    if release_raw and not _news_release_is_plausible(release_raw, item.get("published_at", "")):
        release_raw = ""
    release_fa = _news_localize_date(release_raw, item.get("published_at", "")) if release_raw else ""
    studio = _news_studio_phrase(production_text)
    # تکه‌های ناقص مثل «and Infinite» (نیمه دوم «X and Infinite») اسم استودیو نیستن
    if studio and re.match(r"(?i)^(?:and|&|with|by|the|of)\b|^[a-z]", studio.strip()):
        studio = ""
    subtitle = _news_subtitle_phrase(headline)
    variant = _news_v2_variant(title)

    part_count = ""
    m = re.search(r"\b(?:in|into|across)?\s*(two|2)\s+(?:parts?|cours?)\b", headline, flags=re.I)
    if m:
        part_count = "2"
    episode_count = ""
    m = re.search(r"\b(\d{1,3})[- ]episode\b|\b(\d{1,3})\s+episodes\b", headline, flags=re.I)
    if m:
        episode_count = (m.group(1) or m.group(2) or "").strip()

    certainty = "unofficial" if source_class == "leak" or re.search(
        r"\b(?:rumou?r|leak(?:ed)?|reportedly|unconfirmed|insider)\b", headline, flags=re.I
    ) else "reported"

    confidence = 45
    if event_type != "other":
        confidence += 20
    if known:
        confidence += 20
    if source_class in ("official", "official_media"):
        confidence += 10
    if source_class == "leak":
        confidence -= 10
    if item.get("image_url"):
        confidence += 3
    confidence = max(20, min(confidence, 98))

    return {
        "anime_key": anime_key,
        "anime_eng_name": anime_eng,
        "anime_display": anime_display,
        "known_anime": bool(known),
        "season": season_no or "",
        "release_raw": release_raw,
        "release_fa": release_fa,
        "studio": studio,
        "subtitle": subtitle,
        "variant": variant,
        "part_count": part_count,
        "episode_count": episode_count,
        "certainty": certainty,
        "confidence": confidence,
    }

def _news_v2_fa_season(no) -> str:
    try:
        no = int(no)
    except Exception:
        return ""
    return _news_season_phrase(no) or _news_fa_digits(str(no))

def _news_v2_caption(item: dict, facts: dict, event_type: str, source_class: str) -> str:
    # Agent عمداً اینجا استفاده نمی‌شود؛ هیچ Fact جدیدی اجازه ساخته‌شدن ندارد.
    anime = (facts.get("anime_display") or "این انیمه").strip()
    season = _news_v2_fa_season(facts.get("season"))
    season_text = f"فصل {season} " if season else ""
    unofficial = facts.get("certainty") == "unofficial"

    if event_type == "season_announcement":
        if unofficial:
            lead = f"⚠️ گزارش غیررسمی: گفته می‌شود {season_text}انیمه «{anime}» در دست ساخت قرار دارد."
        else:
            lead = f"🔥 ساخت {season_text}انیمه «{anime}» اعلام شد."
    elif event_type == "trailer_visual":
        lead = f"🔥 پوستر و تریلر جدید {season_text}انیمه «{anime}» منتشر شد."
    elif event_type == "trailer":
        lead = f"🔥 تریلر جدید {season_text}انیمه «{anime}» منتشر شد."
    elif event_type == "character_pv":
        lead = f"👀 تریلر معرفی شخصیت جدیدی از {season_text}انیمه «{anime}» منتشر شد."
    elif event_type == "visual":
        lead = f"🖼 پوستر جدید {season_text}انیمه «{anime}» منتشر شد."
    elif event_type == "release_date":
        lead = f"📅 تاریخ پخش {season_text}انیمه «{anime}» اعلام شد."
    elif event_type == "delay":
        lead = f"⚠️ پخش {season_text}انیمه «{anime}» به تعویق افتاد."
    elif event_type == "cancellation":
        lead = f"⚠️ خبر جدیدی درباره لغو/توقف {season_text}انیمه «{anime}» منتشر شد."
    elif event_type == "new_anime":
        lead = f"🔥 انیمه جدید «{anime}» معرفی شد."
    elif event_type == "movie":
        lead = f"🎬 خبر جدیدی از فیلم انیمه‌ای «{anime}» منتشر شد."
    else:
        # برای موارد ناشناخته ترجمه یا نتیجه‌گیری نمی‌کنیم؛ عنوان منبع به‌عنوان Fact خام می‌ماند.
        raw_title = _news_v2_clean_title_text(item.get("title", ""))[:300]
        lead = f"📰 خبر جدید درباره «{anime}» منتشر شد.\n\n{raw_title}"

    lines = [lead]
    if facts.get("subtitle"):
        lines.append(f"🎞 عنوان/آرک: {facts['subtitle']}")
    if facts.get("part_count"):
        lines.append("🫧 این اثر در دو پارت/کور پخش خواهد شد.")
    if facts.get("episode_count"):
        lines.append(f"🎞 تعداد قسمت اعلام‌شده: {_news_fa_digits(facts['episode_count'])}")
    if facts.get("release_fa"):
        lines.append(f"📅 تاریخ پخش: {facts['release_fa']}")
    if facts.get("studio"):
        lines.append(f"⚙️ استودیو: {facts['studio']}")

    # برای Leak حتی اگر Event چیز دیگری بود، لحن قطعی نباشد.
    if unofficial and event_type != "season_announcement":
        lines.insert(0, "⚠️ گزارش غیررسمی")

    return "\n\n".join(line for line in lines if line).strip()[:1000]

def _news_v2_signature(title: str, event_type: str, facts: dict) -> str:
    normalized_title = _news_topic_normalize(title)[:180]
    payload = "|".join([
        event_type or "other",
        facts.get("anime_key", ""),
        str(facts.get("season", "")),
        facts.get("variant", ""),
        facts.get("release_raw", ""),
        normalized_title,
    ])
    return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()

def _news_v2_is_duplicate(title: str, event_type: str, facts: dict, signature: str) -> bool:
    conn = db()
    exact = conn.execute(
        "SELECT 1 FROM news_v2_items WHERE signature=? AND status NOT IN ('seeded','low') LIMIT 1",
        (signature,),
    ).fetchone()
    if exact:
        conn.close()
        return True
    rows = conn.execute("""
        SELECT title, event_type, anime_key, facts_json
        FROM news_v2_items
        WHERE created_at >= datetime('now','-7 day')
          AND status NOT IN ('seeded','duplicate','rejected','low')
        ORDER BY id DESC LIMIT 120
    """).fetchall()
    conn.close()
    anime_key = facts.get("anime_key", "")
    variant = facts.get("variant", "")
    for row in rows:
        if not anime_key or (row["anime_key"] or "") != anime_key:
            continue
        if (row["event_type"] or "") != event_type:
            continue
        try:
            old_facts = json.loads(row["facts_json"] or "{}")
        except Exception:
            old_facts = {}
        old_variant = old_facts.get("variant", "")
        if variant and old_variant and variant != old_variant:
            continue
        ratio = SequenceMatcher(
            None,
            _news_topic_normalize(title),
            _news_topic_normalize(row["title"] or ""),
        ).ratio()
        if ratio >= 0.82:
            return True
    return False

def _news_v2_item_by_id(item_id: int):
    conn = db()
    row = conn.execute("""
        SELECT n.*, s.title AS source_title, s.feed_url AS source_feed, s.site_url AS source_site
        FROM news_v2_items n LEFT JOIN news_sources s ON s.id=n.source_id
        WHERE n.id=?
    """, (item_id,)).fetchone()
    conn.close()
    return row

def _news_v2_insert(source_id: int, item: dict, status: str = "pending") -> int | None:
    source = _news_source_by_id(source_id)
    source_class = _news_v2_source_class(source, item.get("url", "")) if source else "secondary"
    event_type = _news_v2_event_type(item.get("title", ""), item.get("summary", ""))
    facts = _news_v2_extract_facts(item, source_class, event_type)
    if item.get("extra_images"):
        facts["extra_images"] = list(item["extra_images"])[:NEWS_MAX_EXTRA_IMAGES]
    if item.get("trailer_url"):
        facts["trailer_url"] = item["trailer_url"]
    caption = _news_v2_caption(item, facts, event_type, source_class)
    _news_template_render_for_insert(caption, facts)
    try:
        _syn, _src = _news_get_synopsis(facts.get("anime_key", ""))
    except Exception:
        _syn = ""
    caption = _news_render_caption(facts["render"], _syn)
    signature = _news_v2_signature(item.get("title", ""), event_type, facts)

    if status == "pending" and _news_v2_is_duplicate(item.get("title", ""), event_type, facts, signature):
        status = "duplicate"

    with db_write_lock:
        conn = db()
        try:
            cur = conn.execute("""
                INSERT OR IGNORE INTO news_v2_items(
                    source_id, guid, signature, title, url, published_at, summary, article_text,
                    image_url, video_url, event_type, source_class, anime_key, anime_display,
                    anime_eng_name, confidence, facts_json, caption, status
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                source_id, item.get("guid", ""), signature,
                _news_v2_clean_title_text(item.get("title", ""))[:500],
                item.get("url", ""), item.get("published_at", ""),
                _news_v2_clean_title_text(item.get("summary", ""))[:4000],
                _news_v2_clean_title_text(item.get("article_text", ""))[:20000],
                item.get("image_url", ""), item.get("video_url", ""),
                event_type, source_class, facts.get("anime_key", ""), facts.get("anime_display", ""),
                facts.get("anime_eng_name", ""), int(facts.get("confidence", 0)),
                json.dumps(facts, ensure_ascii=False), caption, status,
            ))
            conn.commit()
            if cur.rowcount:
                return int(cur.lastrowid)
            row = conn.execute(
                "SELECT id FROM news_v2_items WHERE source_id=? AND guid=?",
                (source_id, item.get("guid", "")),
            ).fetchone()
            return int(row["id"]) if row else None
        finally:
            conn.close()

def _news_v2_archive_markup(item_id: int, source_url: str, status: str, expects_trailer: bool = False, has_trailer: bool = False):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("🔗 منبع اصلی", url=source_url))
    kb.row(
        InlineKeyboardButton("ℹ️ جزئیات تشخیص", callback_data=f"nv2_info:{item_id}"),
        InlineKeyboardButton("✏️ ویرایش متن", callback_data=f"nv2_edit:{item_id}"),
    )
    kb.row(
        InlineKeyboardButton("🤖 بازنویسی با AI", callback_data=f"nv2_ai:{item_id}"),
        InlineKeyboardButton("📝 خلاصه داستان", callback_data=f"nv2_syn:{item_id}"),
    )
    if status == "approved":
        kb.add(InlineKeyboardButton("✅ تأیید شده", callback_data=f"nv2_approve:{item_id}"))
    else:
        kb.add(InlineKeyboardButton("✅ تأیید خبر", callback_data=f"nv2_approve:{item_id}"))
    if expects_trailer:
        label = "♻️ تعویض فایل تریلر" if has_trailer else "🎬 افزودن فایل تریلر"
        kb.add(InlineKeyboardButton(label, callback_data=f"nv2_trailer:{item_id}"))
    kb.add(InlineKeyboardButton("🎨 پست اینستاگرام", callback_data=f"nv2_insta:{item_id}"))
    kb.row(
        InlineKeyboardButton("📤 انتشار", callback_data=f"nv2_publish:{item_id}"),
        InlineKeyboardButton("🗑 رد خبر", callback_data=f"nv2_reject:{item_id}"),
    )
    return kb

NEWS_NOT_AGENT_NOTE = "⚠️ این متن قالبیه و با AI بازنویسی نشده؛ «🤖 بازنویسی با AI» رو بزن."


def _news_v2_archive_caption(row) -> str:
    """کپشن پیش‌نمایش آرشیو با یه برچسب که نشون میده متن رو کی نوشته:
    ✅ AI / ✏️ ادمین / ⚠️ متن قالبی (بازنویسی نشده).
    این برچسب‌ها فقط توی آرشیو دیده میشن؛ موقع انتشار کپشن تمیز از دیتابیس استفاده میشه."""
    caption = (row["caption"] or "").strip()
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except Exception:
        facts = {}
    render = facts.get("render") or {}
    if not render:
        return caption or "📰 خبر جدید"
    synopsis, _src = _news_get_synopsis(row["anime_key"] or "")
    if render.get("mode") == "agent":
        model = str(facts.get("agent_model") or "").split(":")[-1]
        note = f"✅ 🤖 این متن با AI بازنویسی شده" + (f" ({model})" if model else "")
        body = _news_render_caption(render, synopsis, max_len=1024 - len(note) - 4)
        return f"{body}\n\n{note}"
    if render.get("mode") == "manual":
        note = "✏️ این متن رو ادمین ویرایش کرده"
        return f"{(caption or '')[:1024 - len(note) - 4]}\n\n{note}"
    body = _news_render_caption(render, synopsis, max_len=1024 - len(NEWS_NOT_AGENT_NOTE) - 4)
    return f"{NEWS_NOT_AGENT_NOTE}\n\n{body}"


_ROMAN_SEASONS = {"ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8}
_ORDINAL_WORDS = {"second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8}


def _title_season(title: str):
    """شماره‌ی فصل از اسم انیمه (Season 4 / 4th Season / II / Second Season). بدون نشونه → None."""
    t = (title or "").strip()
    m = re.search(r"(?i)\bseason\s*(\d{1,2})\b", t) or re.search(r"(?i)\b(\d{1,2})(?:st|nd|rd|th)\s+season\b", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(?i)\b(second|third|fourth|fifth|sixth|seventh|eighth)\s+season\b", t)
    if m:
        return _ORDINAL_WORDS[m.group(1).lower()]
    m = re.search(r"\b(II|III|IV|V|VI|VII|VIII)\b", t)
    if m:
        return _ROMAN_SEASONS[m.group(1).lower()]
    return None


def _anime_base_name(name: str) -> str:
    """اسم انیمه بدون شماره‌ی فصل/پارت."""
    n = re.sub(r"(?i)[\s:\-–]*(?:season\s*\d{1,2}|\d{1,2}(?:st|nd|rd|th)\s+season|(?:second|third|fourth|fifth)\s+season"
               r"|part\s*\d{1,2}|\b(?:II|III|IV|V|VI)\b)\s*$", "", (name or "").strip())
    return n.strip(" :-–") or (name or "").strip()


def _news_v2_item_season(row, facts: dict) -> int:
    try:
        s = int(facts.get("season") or 0)
    except Exception:
        s = 0
    if not s:
        s = _news_season_number(f"{row['title'] or ''}") or _title_season(row["anime_display"] or "") or 0
    return int(s or 0)


def _anilist_franchise(base: str) -> list:
    """همه‌ی نسخه‌های یه انیمه توی AniList (فصل‌ها/فیلم‌ها) با پوستر؛ ۷ روز کش."""
    key = "franchise:" + (_news_topic_normalize(base)[:110] or base.lower()[:110])
    conn = db()
    row = conn.execute("SELECT meta_json, fetched_at FROM news_anime_meta WHERE lookup_key=?", (key,)).fetchone()
    conn.close()
    if row and time.time() - int(row["fetched_at"] or 0) < 7 * 86400:
        try:
            return json.loads(row["meta_json"] or "[]")
        except Exception:
            pass
    query = """query ($s: String) { Page(perPage: 15) { media(search: $s, type: ANIME, sort: SEARCH_MATCH) {
        title { romaji english } synonyms format seasonYear startDate { year }
        coverImage { extraLarge large } } } }"""
    entries = []
    try:
        req = urllib.request.Request(
            ANILIST_GRAPHQL_URL, method="POST",
            data=json.dumps({"query": query, "variables": {"s": base[:100]}}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": NEWS_USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            media = ((((json.loads(resp.read().decode("utf-8", errors="ignore")) or {}).get("data") or {})
                      .get("Page") or {}).get("media") or [])
        want = _news_agent_norm(base)
        for m in media:
            titles = [t for t in ((m.get("title") or {}).get("english"), (m.get("title") or {}).get("romaji")) if t]
            titles += [t for t in (m.get("synonyms") or []) if t and re.search(r"[A-Za-z]", t)]
            if not any(want and want in _news_agent_norm(t) for t in titles):
                continue  # یه انیمه‌ی دیگه‌ست
            season = next((x for x in (_title_season(t) for t in titles) if x), None)
            cover = ((m.get("coverImage") or {}).get("extraLarge") or (m.get("coverImage") or {}).get("large") or "")
            if not cover:
                continue
            entries.append({
                "season": season, "format": m.get("format") or "",
                "year": int((m.get("startDate") or {}).get("year") or m.get("seasonYear") or 0),
                "cover": cover,
            })
    except Exception as exc:
        logger.info("AniList franchise lookup failed for %s: %s", base, exc)
        return []
    with db_write_lock:
        conn = db()
        conn.execute("""
            INSERT INTO news_anime_meta(lookup_key, meta_json, fetched_at) VALUES(?,?,?)
            ON CONFLICT(lookup_key) DO UPDATE SET meta_json=excluded.meta_json, fetched_at=excluded.fetched_at
        """, (key, json.dumps(entries), int(time.time())))
        conn.commit()
        conn.close()
    return entries


def _anilist_season_cover(base: str, season: int) -> str:
    """پوستر رسمی دقیقاً همون فصل (فقط سریال‌ها). فصل ۱ = نسخه‌ی بدون شماره‌ی فصل."""
    tv = [e for e in _anilist_franchise(base) if e["format"] in ("TV", "TV_SHORT", "ONA", "")]
    if season <= 1:
        firsts = sorted((e for e in tv if not e["season"]), key=lambda e: e["year"] or 9999)
        return firsts[0]["cover"] if firsts else ""
    exact = [e for e in tv if e["season"] == season]
    return max(exact, key=lambda e: e["year"])["cover"] if exact else ""


def _news_v2_channel_poster(row, season: int | None, max_days: int = 730) -> str:
    """file_id پوستری که قبلاً برای همین انیمه (و همین فصل) توی کانال منتشر شده."""
    wanted = _news_v2_anime_names(row)
    if not wanted:
        return ""
    conn = db()
    rows = conn.execute(f"""
        SELECT i.* FROM news_v2_publications p JOIN news_v2_items i ON i.id = p.item_id
        WHERE p.item_id<>? AND p.created_at >= datetime('now', '-{int(max_days)} day')
        ORDER BY p.id DESC LIMIT 300
    """, (row["id"],)).fetchall()
    conn.close()
    for r in rows:
        try:
            f = json.loads(r["facts_json"] or "{}")
        except Exception:
            continue
        fid = f.get("archive_photo_file_id")
        if not fid or r["archive_media_type"] != "photo":
            continue
        if not _news_v2_names_match(wanted, _news_v2_anime_names(r)):
            continue
        if season is not None and _news_v2_item_season(r, f) != season:
            continue
        return fid
    return ""


def _news_v2_fallback_image(row) -> tuple:
    """عکس برای خبری که خودش عکس نداره: ("file_id", ...) یا ("url", ...) یا ("", "").

    ترتیب: پوستر همین فصل که قبلاً توی کانال رفته ← پوستر رسمی همین فصل (AniList)
    ← همین دو تا برای فقط یه فصل قبل‌تر. فصل‌های قدیمی‌تر هیچ‌وقت.
    """
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except Exception:
        facts = {}
    name = (row["anime_display"] or facts.get("anime_eng_name") or facts.get("anime_display") or "").strip()
    if len(name) < 3 or name == "این انیمه":
        return "", ""
    base = _anime_base_name(name)
    season = _news_v2_item_season(row, facts)
    if season:
        for s in ([season, season - 1] if season > 1 else [season]):
            fid = _news_v2_channel_poster(row, s)
            if fid:
                return "file_id", fid
            url = _anilist_season_cover(base, s)
            if url:
                return "url", url
        return "", ""
    # فصل مشخص نیست: آخرین پوستری که از این انیمه توی کانال رفته (۶ ماه اخیر) یا جدیدترین نسخه توی AniList
    fid = _news_v2_channel_poster(row, None, max_days=180)
    if fid:
        return "file_id", fid
    entries = [e for e in _anilist_franchise(base) if e["format"] in ("TV", "TV_SHORT", "ONA", "MOVIE", "")]
    if entries:
        return "url", max(entries, key=lambda e: e["year"])["cover"]
    return "", ""


def _news_v2_send_preview(item_id: int) -> bool:
    row = _news_v2_item_by_id(item_id)
    archive = _news_archive_channel()
    if not row or not archive or row["status"] in ("duplicate", "seeded", "rejected"):
        return False
    fallback_file_id = ""
    if not (row["image_url"] or "").strip():
        # خبر عکس نداشت (مثلاً توییت متنی لیکر) → پوستر همین فصل از کانال یا AniList
        try:
            kind, value = _news_v2_fallback_image(row)
        except Exception:
            logger.exception("Fallback image failed item=%s", item_id)
            kind, value = "", ""
        if kind == "url":
            with db_write_lock:
                conn = db()
                conn.execute("UPDATE news_v2_items SET image_url=? WHERE id=?", (value, item_id))
                conn.commit()
                conn.close()
            row = _news_v2_item_by_id(item_id)
        elif kind == "file_id":
            fallback_file_id = value
    caption = _news_v2_archive_caption(row)
    expects_trailer = row["event_type"] in ("trailer", "trailer_visual", "character_pv")
    kb = _news_v2_archive_markup(item_id, row["url"], row["status"], expects_trailer, bool(row["archive_secondary_message_id"]))
    sent = None
    media_type = "text"
    image_url = (row["image_url"] or "").strip()
    if fallback_file_id:
        try:
            sent = bot.send_photo(archive, fallback_file_id, caption=caption, reply_markup=kb, parse_mode="HTML")
            media_type = "photo"
        except Exception as exc:
            logger.info("Reusing channel poster failed item=%s: %s", item_id, exc)
    image_note = "بدون عکس" if not image_url and not fallback_file_id else ""
    if fallback_file_id and sent is not None:
        image_note = "پوستر قبلی همین انیمه از کانال"
    if sent is None and image_url and _news_safe_url(image_url):
        errors = []
        downloaded = _news_v2_image_file(image_url)
        if downloaded is None:
            errors.append("دانلود عکس توسط بات نشد")
        for photo in (downloaded, image_url):
            if photo is None:
                continue
            try:
                sent = bot.send_photo(archive, photo, caption=caption, reply_markup=kb, parse_mode="HTML")
                media_type = "photo"
                image_note = "عکس خود خبر"
                break
            except Exception as exc:
                errors.append(str(exc)[:120])
                logger.warning("News V2 image preview failed item=%s url=%s: %s", item_id, image_url, exc)
        if sent is None:
            # عکس خود خبر فرستاده نشد → پوستر همین فصل (از کانال یا AniList)
            try:
                kind, value = _news_v2_fallback_image(row)
            except Exception:
                kind, value = "", ""
            photo = value if kind == "file_id" else (_news_v2_image_file(value) if kind == "url" else None)
            if photo is not None:
                try:
                    sent = bot.send_photo(archive, photo, caption=caption, reply_markup=kb, parse_mode="HTML")
                    media_type = "photo"
                except Exception as exc:
                    errors.append(str(exc)[:120])
            image_note = ("عکس خبر نرفت، پوستر جایگزین گذاشته شد: " if sent is not None else "عکس نرفت: ") + " | ".join(errors)
    elif sent is None and image_url:
        image_note = f"آدرس عکس نامعتبر: {image_url[:80]}"
    if image_note:
        try:
            _news_v2_update_facts(item_id, image_note=image_note[:300])
        except Exception:
            pass
    if sent is None:
        try:
            sent = bot.send_message(archive, caption[:4096], reply_markup=kb, parse_mode="HTML",
                                    link_preview_options=NO_LINK_PREVIEW)
        except Exception:
            plain = unescape(re.sub(r"<[^>]+>", "", caption))
            sent = bot.send_message(archive, plain[:4096], reply_markup=kb, link_preview_options=NO_LINK_PREVIEW)
        media_type = "text"
    with db_write_lock:
        conn = db()
        conn.execute("""
            UPDATE news_v2_items SET archive_chat_id=?, archive_message_id=?, archive_media_type=?
            WHERE id=?
        """, (str(archive), int(sent.message_id), media_type, item_id))
        conn.commit()
        conn.close()
    try:
        _news_v2_send_extra_images(item_id, archive, sent)
    except Exception:
        logger.exception("News V2 extra images failed item=%s", item_id)
    try:
        _news_v2_queue_trailer(item_id)
    except Exception:
        logger.exception("Trailer auto-download queue failed item=%s", item_id)
    return True


def _news_v2_send_extra_images(item_id: int, archive, main_msg):
    """file_id عکس اصلی رو نگه می‌داره و پوسترهای اضافه رو به‌صورت آلبوم ریپلای زیر پیش‌نمایش می‌فرسته."""
    row = _news_v2_item_by_id(item_id)
    try:
        facts = json.loads((row["facts_json"] if row else "") or "{}")
    except Exception:
        facts = {}
    changes = {"archive_photo_file_id": "", "extra_file_ids": [], "archive_extra_ids": []}
    photos = getattr(main_msg, "photo", None) or []
    if photos:
        changes["archive_photo_file_id"] = photos[-1].file_id
    files = []
    for url in (facts.get("extra_images") or [])[:NEWS_MAX_EXTRA_IMAGES]:
        if not _news_safe_url(url):
            continue
        data = _news_v2_image_file(url)
        if data is not None:
            files.append(data)
    if files and photos:
        from telebot.types import InputMediaPhoto
        if len(files) == 1:
            msgs = [bot.send_photo(archive, files[0], caption="🖼 عکس دیگه‌ی این خبر (موقع انتشار کنار هم میرن)",
                                   reply_to_message_id=int(main_msg.message_id), allow_sending_without_reply=True)]
        else:
            media = [InputMediaPhoto(f, caption="🖼 عکس‌های دیگه‌ی این خبر (موقع انتشار همه با هم توی یه آلبوم میرن)" if i == 0 else None)
                     for i, f in enumerate(files)]
            msgs = bot.send_media_group(archive, media, reply_to_message_id=int(main_msg.message_id),
                                        allow_sending_without_reply=True)
        for msg in msgs or []:
            if getattr(msg, "photo", None):
                changes["extra_file_ids"].append(msg.photo[-1].file_id)
                changes["archive_extra_ids"].append(int(msg.message_id))
    _news_v2_update_facts(item_id, **changes)

NEWS_AGENT_DAILY_LIMIT = max(1, int(os.environ.get("NEWS_AGENT_DAILY_LIMIT", "45") or 45))

NEWS_AGENT_MAX_PER_CYCLE = 6

NEWS_AGENT_MAX_MODEL_TRIES = 2

ANILIST_GRAPHQL_URL = "https://graphql.anilist.co"

_NEWS_AGENT_DEFAULT_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-small-3.2-24b-instruct:free",
]

_news_agent_cycle_count = 0

_news_agent_lock = threading.Lock()

class _NewsAgentHTTPError(Exception):
    def __init__(self, code: int, detail: str = ""):
        super().__init__(f"HTTP {code}: {detail[:200]}")
        self.code = code
        self.detail = detail

def _news_agent_init_db():
    with db_write_lock:
        conn = db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS news_anime_meta(
                lookup_key TEXT PRIMARY KEY,
                meta_json TEXT,
                fetched_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS news_anime_synopsis(
                anime_key TEXT PRIMARY KEY,
                synopsis_fa TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'agent',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

def _news_agent_today() -> str:
    return time.strftime("%Y%m%d", time.gmtime())

def _news_agent_used_today() -> int:
    try:
        return int(get_setting(f"news_agent_used_{_news_agent_today()}", "0") or 0)
    except Exception:
        return 0

def _news_agent_mark_use():
    set_setting(f"news_agent_used_{_news_agent_today()}", str(_news_agent_used_today() + 1))

def _news_agent_models() -> list:
    models = [m.strip() for m in os.environ.get("NEWS_AGENT_MODELS", "").split(",") if m.strip()]
    if OPENROUTER_MODEL and OPENROUTER_MODEL != "openrouter/free" and OPENROUTER_MODEL not in models:
        models.append(OPENROUTER_MODEL)
    for m in _NEWS_AGENT_DEFAULT_MODELS:
        if m not in models:
            models.append(m)
    return models

AVALAI_BASE_URL = "https://api.avalai.ir/v1"

def _news_ai_custom_config() -> tuple:
    base = (get_setting("news_ai_base_url", "") or os.environ.get("AI_BASE_URL", "")).strip().rstrip("/")
    key = (get_setting("news_ai_api_key", "") or os.environ.get("AI_API_KEY", "")).strip()
    model = (get_setting("news_ai_model", "") or os.environ.get("AI_MODEL", "")).strip()
    return base, key, model

def _news_ai_custom_ready() -> bool:
    base, key, model = _news_ai_custom_config()
    return bool(base and key and model)

def _news_ai_custom_limit() -> int:
    try:
        return max(1, int(get_setting("news_ai_daily_limit", "150") or 150))
    except Exception:
        return 150

def _news_agent_custom_call(system_prompt: str, user_prompt: str, timeout: int = 70) -> str:
    base, key, model = _news_ai_custom_config()
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,
        "max_tokens": 1000,
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise _NewsAgentHTTPError(int(e.code), detail)
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError(f"پاسخ خالی: {str(payload.get('error') or '')[:200]}")
    content = (choices[0].get("message") or {}).get("content") or ""
    if isinstance(content, list):
        content = "\n".join(str(p.get("text") or "") for p in content if isinstance(p, dict))
    content = str(content).strip()
    if not content:
        raise RuntimeError("مدل متنی برنگرداند")
    return content

def _news_agent_can_call() -> tuple:
    if get_setting("news_agent_enabled", "1") != "1":
        return False, "ایجنت خاموشه"
    if _news_ai_custom_ready():
        used = int(get_setting(f"news_ai_used_{_news_agent_today()}", "0") or 0)
        if used < _news_ai_custom_limit():
            return True, ""
        if not (OPENROUTER_API_KEY or GEMINI_API_KEY):
            return False, f"به سقف {_news_ai_custom_limit()} درخواست امروز سرویس AI رسیدیم"
    if not (OPENROUTER_API_KEY or GEMINI_API_KEY):
        return False, "سرویس AI تنظیم نشده"
    if OPENROUTER_API_KEY and not GEMINI_API_KEY:
        if get_setting("news_agent_pause_day", "") == _news_agent_today():
            return False, "سهمیه روزانه OpenRouter تموم شده (فردا خودکار فعال میشه)"
        if _news_agent_used_today() >= NEWS_AGENT_DAILY_LIMIT:
            return False, f"به سقف {NEWS_AGENT_DAILY_LIMIT} درخواست امروز رسیدیم"
    return True, ""

def _news_agent_openrouter(system_prompt: str, user_prompt: str, model: str, timeout: int = 50) -> str:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.35,
        "max_tokens": 900,
        "reasoning": {"exclude": True},
    }
    req = urllib.request.Request(
        OPENROUTER_CHAT_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "HTTP-Referer": "https://t.me/ariko_tv",
            "X-Title": "ARIKO.TV Anime News Bot",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise _NewsAgentHTTPError(int(e.code), detail)
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError(f"پاسخ خالی: {str(payload.get('error') or '')[:200]}")
    content = (choices[0].get("message") or {}).get("content") or ""
    if isinstance(content, list):
        content = "\n".join(str(p.get("text") or "") for p in content if isinstance(p, dict))
    content = str(content).strip()
    if not content:
        raise RuntimeError("مدل متنی برنگرداند")
    return content

def _news_agent_generate(system_prompt: str, user_prompt: str) -> tuple:
    """خروجی متن و اسم مدل. اول سرویس اختصاصی (مثل AvalAI)، بعد Gemini، بعد OpenRouter."""
    last_err = None
    if _news_ai_custom_ready():
        day_key = f"news_ai_used_{_news_agent_today()}"
        used = int(get_setting(day_key, "0") or 0)
        if used < _news_ai_custom_limit():
            set_setting(day_key, str(used + 1))
            _base, _key, _model = _news_ai_custom_config()
            try:
                return _news_agent_custom_call(system_prompt, user_prompt), f"custom:{_model}"
            except Exception as exc:
                last_err = exc
                logger.warning("News Agent custom provider failed: %s", exc)
    if GEMINI_API_KEY:
        try:
            text = _gemini_generate_text(user_prompt, system_prompt=system_prompt,
                                         max_output_tokens=900, temperature=0.35, json_mode=True)
            return text, f"gemini:{GEMINI_MODEL}"
        except Exception as exc:
            last_err = exc
            logger.info("News Agent Gemini failed: %s", exc)
    if not OPENROUTER_API_KEY or get_setting("news_agent_pause_day", "") == _news_agent_today() \
            or _news_agent_used_today() >= NEWS_AGENT_DAILY_LIMIT:
        if isinstance(last_err, GeminiError):
            raise GeminiError(str(last_err), transient=last_err.transient)
        raise RuntimeError(f"هیچ سرویس AI در دسترس نیست: {last_err}")
    tries = 0
    for model in _news_agent_models():
        if tries >= NEWS_AGENT_MAX_MODEL_TRIES:
            break
        tries += 1
        _news_agent_mark_use()
        try:
            return _news_agent_openrouter(system_prompt, user_prompt, model), model
        except _NewsAgentHTTPError as exc:
            last_err = exc
            detail = (exc.detail or "").lower()
            if exc.code == 429 and ("per-day" in detail or "per day" in detail or "daily" in detail):
                set_setting("news_agent_pause_day", _news_agent_today())
                raise RuntimeError("سهمیه روزانه OpenRouter تموم شد")
            if exc.code in (401, 403):
                raise RuntimeError(f"کلید OpenRouter نامعتبر/مسدود: {exc}")
            # 402 (نیاز به اعتبار)، 404 (مدل حذف شده)، 429 لحظه‌ای، 5xx → مدل بعدی
            logger.info("News Agent model %s failed: %s", model, exc)
            time.sleep(2)
        except Exception as exc:
            last_err = exc
            logger.info("News Agent model %s failed: %s", model, exc)
    raise RuntimeError(f"هیچ مدلی پاسخ نداد: {last_err}")

def _news_agent_norm(value: str) -> str:
    try:
        return _normalize_anime_search_text(value or "")
    except Exception:
        return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()

def _news_anilist_clean_query(name: str) -> str:
    """«@MangaMoguraRE: "BLESS" Vol 9 by ...» → «BLESS»؛ «X Cour 2» / «X's 2nd» → «X»."""
    name = re.sub(r"^\s*@\w+\s*:\s*", "", name or "")
    m = re.search(r"[\"“”«]([^\"“”«»]{2,90})[\"“”»]", name)
    if m:
        name = m.group(1)
    name = re.sub(r"(?i)\s*(?:'s\s+\d+(?:st|nd|rd|th)\b.*|\s+cour\s+\d+.*|\s+(?:season|part)\s+\d+.*|\s+character\b.*)$",
                  "", name)
    return re.sub(r"\s+", " ", name).strip(" :-–—\"“”«»")


def _news_anilist_lookup(name: str) -> dict:
    name = _news_anilist_clean_query((name or "").strip())
    if len(name) < 3:
        return {}
    key = _news_topic_normalize(name)[:120] or name.lower()[:120]
    now = int(time.time())
    conn = db()
    row = conn.execute("SELECT meta_json, fetched_at FROM news_anime_meta WHERE lookup_key=?", (key,)).fetchone()
    conn.close()
    if row:
        try:
            meta = json.loads(row["meta_json"] or "{}")
        except Exception:
            meta = {}
        max_age = 7 * 86400 if meta else 86400
        # کش‌های قدیمی فیلد cover (پوستر) رو ندارن → یه بار دوباره گرفته میشن
        if now - int(row["fetched_at"] or 0) < max_age and (not meta or ("cover" in meta and "title_native" in meta and "synonyms" in meta
                                                                          and "banner" in meta)):
            return meta

    query = """
    query ($s: String) {
      Media(search: $s, type: ANIME, sort: SEARCH_MATCH) {
        title { romaji english native }
        synonyms
        format seasonYear
        startDate { year month day }
        genres
        popularity
        coverImage { extraLarge large }
        bannerImage
        description(asHtml: false)
        studios(isMain: true) { nodes { name } }
      }
    }"""
    meta = {}
    try:
        req = urllib.request.Request(
            ANILIST_GRAPHQL_URL,
            data=json.dumps({"query": query, "variables": {"s": name[:100]}}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json",
                     "User-Agent": NEWS_USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
        media = ((payload or {}).get("data") or {}).get("Media") or {}
        titles = media.get("title") or {}
        cand = [t for t in (titles.get("english"), titles.get("romaji")) if t]
        target = _news_agent_norm(name)
        good = False
        for t in cand:
            nt = _news_agent_norm(t)
            if not nt:
                continue
            if nt in target or target in nt or SequenceMatcher(None, nt, target).ratio() >= 0.6:
                good = True
                break
        if good:
            desc = _news_strip_html(media.get("description") or "")
            desc = re.sub(r"\(Source:[^)]*\)", "", desc)
            desc = re.sub(r"\s+", " ", desc).strip()[:1400]
            studios = [n.get("name") for n in ((media.get("studios") or {}).get("nodes") or []) if n.get("name")]
            sd = media.get("startDate") or {}
            meta = {
                "title_en": titles.get("english") or "",
                "title_romaji": titles.get("romaji") or "",
                "title_native": titles.get("native") or "",
                "synonyms": [x for x in (media.get("synonyms") or []) if x][:12],
                "format": media.get("format") or "",
                "year": sd.get("year") or media.get("seasonYear") or "",
                "genres": (media.get("genres") or [])[:5],
                "description": desc,
                "studio": " & ".join(studios[:2]),
                "popularity": int(media.get("popularity") or 0),
                "banner": media.get("bannerImage") or "",
                "cover": ((media.get("coverImage") or {}).get("extraLarge")
                          or (media.get("coverImage") or {}).get("large") or ""),
            }
    except urllib.error.HTTPError as exc:
        if exc.code != 404:                         # 404 یعنی AniList همچین انیمه‌ای نداره → نتیجه‌ی خالی کش میشه
            logger.info("AniList lookup failed for %s: %s", name, exc)
            return {}
    except Exception as exc:
        logger.info("AniList lookup failed for %s: %s", name, exc)
        return {}  # خطای شبکه رو کش نکن

    with db_write_lock:
        conn = db()
        conn.execute("""
            INSERT INTO news_anime_meta(lookup_key, meta_json, fetched_at) VALUES(?,?,?)
            ON CONFLICT(lookup_key) DO UPDATE SET meta_json=excluded.meta_json, fetched_at=excluded.fetched_at
        """, (key, json.dumps(meta, ensure_ascii=False), now))
        conn.commit()
        conn.close()
    return meta

def _news_get_synopsis(anime_key: str) -> tuple:
    if not anime_key:
        return "", ""
    conn = db()
    row = conn.execute("SELECT synopsis_fa, source FROM news_anime_synopsis WHERE anime_key=?", (anime_key,)).fetchone()
    conn.close()
    return (row["synopsis_fa"], row["source"]) if row else ("", "")

def _news_set_synopsis(anime_key: str, text: str, source: str):
    if not anime_key:
        return
    with db_write_lock:
        conn = db()
        if text:
            conn.execute("""
                INSERT INTO news_anime_synopsis(anime_key, synopsis_fa, source) VALUES(?,?,?)
                ON CONFLICT(anime_key) DO UPDATE SET synopsis_fa=excluded.synopsis_fa,
                    source=excluded.source, updated_at=CURRENT_TIMESTAMP
            """, (anime_key, text, source))
        else:
            conn.execute("DELETE FROM news_anime_synopsis WHERE anime_key=?", (anime_key,))
        conn.commit()
        conn.close()

_NEWS_AGENT_SYSTEM = """You write posts for a popular Iranian anime Telegram channel, in the voice of a friendly anime fan talking to other fans.
You turn ONE English anime news item into a Persian post: a catchy headline plus a short, informative second paragraph.

HARD RULES:
- Use ONLY facts present in SOURCE. Never invent names, dates, numbers, studios, platforms or plot details.
- The anime in the post MUST be the anime the SOURCE title is about. Never mention other anime (except a famous related work named in SOURCE, e.g. the author's other hit).
- Keep anime titles in their English/romaji form exactly as written in SOURCE, inside «».
- Output ONE valid JSON object and nothing else. No markdown, no explanations.

VOICE (very important):
- Spoken, warm Persian like big Persian anime channels — NOT newspaper Persian.
- Use colloquial verbs: «هست»، «داره»، «میشه»، «قراره»، «شده»، «منتشر شد»، «رسما تایید شد».
- NEVER use formal/bookish words: «است»، «می‌باشد»، «توسط»، «به مناسبت»، «گردید»، «نموده»، «برنامه‌ریزی شده است»، «میلادی»، «اعلام گردید».
- Headline = one sentence (may end with a short extra clause for a key fact, like example 7).
- details = 1 or 2 sentences whenever SOURCE has anything useful beyond the headline: episode count, parts/cours,
  where/when it streams, studio/staff/cast, source material (manga/light novel/game) and its author, a notable record,
  "currently airing". A short friendly fan reaction is welcome when it follows directly from SOURCE facts
  (e.g. «یعنی احتمالاً بعضی از چپترهای مانگا اقتباس نمیشه!»). Leave details empty ONLY if SOURCE really has nothing extra.
  Do NOT repeat the headline, and do NOT write the release date or the studio in details — the bot adds
  «تاریخ پخش» and «استودیو سازنده» lines itself, so repeating them looks bad.
- Do not write dates in the text (the bot adds a date line). Do not explain obvious things.
- If CERTAINTY is a leak/rumor, make it clear the info is UNOFFICIAL (not a guess): start the headline with
  «طبق گزارشات غیررسمی؛» or «طبق اطلاعات لو رفته؛». Do NOT use «احتمالاً» for this — it sounds like we are guessing.
- Never write «کور» / «cour» — most fans don't know it. Say «پارت» (e.g. «۲۴ قسمت در دو پارت پشت‌سرهم»،
  «پارت دوم»).

REAL EXAMPLES FROM THE CHANNEL (copy this voice, not the facts):
1) headline: ساخت انیمه‌ی مانگای درام و عاشقانه‌ی «The Failure at God School» رسما تایید شد.
   details: ["نویسنده‌ی مانگاش خانم ناتسو هیوگا، نویسنده‌ی لایت‌ناول «The Apothecary Diaries» هست."]
2) headline: یک انیمه با اقتباس از بازی «Lollipop Chainsaw» که سال ۲۰۱۲ منتشر شده در دست توسعه قرار داره.
   details: []
3) headline: پوسترهای جدید انیمه‌ی اچی و عاشقانه‌ی «Now That We Draw» از شخصیت‌های اصلی اثر منتشر شد.
   details: []
4) headline: پوستر و تریلر جدید پارت دوم انیمه‌ی اکشن و فانتزی «The Exiled Heavy Knight Knows How to Game the System» منتشر شد.
   details: ["این اثر هم‌اکنون در حال پخش هست."]
5) headline: طبق اطلاعات لو رفته؛ تاریخ اکران دومین قسمت از سه‌گانه‌ی «Demon Slayer: Kimetsu no Yaiba Infinity Castle» مشخص شده.
   details: ["یک فیلم بدون نام توسط سونی پیکچرز و کرانچی‌رول ثبت شده که احتمال می‌ره تاریخ اکران این انیمه‌ی مورد انتظار باشه."]
6) headline: طبق گزارشات؛ قسمت آخر از فصل چهارم انیمه‌ی «Re:Zero» حدود ۴۰ تا ۴۵ دقیقه‌ست.
   details: []
7) headline: تاریخ پخش انیمه‌ی به‌شدت مورد انتظار «Sekiro: No Defeat» اعلام شد! همچنین گفتن که کلاً ۸ قسمت هست.
   details: ["این انیمه اقتباسی از بازی محبوب «Sekiro: Shadows Die Twice» هست و سه صداپیشه‌ی اصلی بازی هم برای انیمه برگشتن."]
   (excitement like «!» is welcome for big news)
BAD (too formal, never write like this):
- «این انیمه‌ی تلویزیونی برای پخش در سال ۲۰۲۷ میلادی برنامه‌ریزی شده است. به مناسبت انتشار این خبر، تصویری ویژه توسط خالق اثر منتشر شد.»
- «این انیمه اقتباسی از مانگایی به همین اثر از Shoco خواهد بود که از طریق وب‌سایت رسمی این اثر معرفی شد.»
  GOOD instead: «این انیمه اقتباسی از مانگای Shoco هست.»

NOT NEWS: explainers ("Ending, Explained"), reviews, recaps, guides, "where to watch", rankings/listicles written by the
site and opinion pieces are NOT news — return {"is_anime_news": false} for them.

IMPORTANCE (1-10) for Persian anime fans:
- 8-10: new season/sequel/new anime announced, release date, delay, cancellation, major film, big leak, final-episode news of a popular show.
- 5-7: new trailer/key visual of a known anime, notable cast/staff reveal, box office record.
- 1-4: music videos, singles, concerts, merchandise, cafes/collabs, games not about an anime, English dub casts, niche festivals.

JSON FORMAT:
{
  "is_anime_news": true,
  "importance": 1-10,
  "anime_title": "exact title from SOURCE",
  "emoji": "one fitting emoji",
  "headline": "one short colloquial Persian sentence (see examples). Season/part as Persian words (فصل دوم، پارت دوم). Genre adjectives only from GENRES.",
  "voice_actors": ["ONLY for cast/voice-actor/staff announcements: up to 3 person names exactly as written in SOURCE (romaji), newly announced; otherwise empty list"],
  "headline_trailer": "ONLY if SOURCE announces BOTH a new video (trailer/teaser/PV) AND new images (posters/visuals/stills): headline for a separate video post, e.g. «تیزر جدید انیمه‌ی اچی و عاشقانه‌ی «Now That We Draw» منتشر شد.» — otherwise empty string",
  "headline_images": "same case only: headline for the separate images post, e.g. «پوسترهای جدید انیمه‌ی اچی و عاشقانه‌ی «Now That We Draw» از شخصیت‌های اصلی اثر منتشر شد.» — otherwise empty string",
  "details": ["1-2 colloquial Persian sentences with extra facts from SOURCE only (empty list only if SOURCE has nothing more)"],
  "synopsis": "2-3 sentence spoiler-free colloquial Persian synopsis translated ONLY from SYNOPSIS_EN, or empty string",
  "release_date": "premiere/release date exactly as written in SOURCE (English), or empty string",
  "studio": "studio name only if explicitly in SOURCE, else empty string"
}"""

def _news_agent_user_prompt(row, facts: dict, meta: dict) -> str:
    title = _news_v2_clean_title_text(row["title"] or "")
    summary = _news_v2_clean_title_text(row["summary"] or "")[:900]
    article = _news_v2_clean_title_text(row["article_text"] or "")[:2600]
    certainty = "UNOFFICIAL LEAK/RUMOR — start the headline with «طبق گزارشات غیررسمی؛» or «طبق اطلاعات لو رفته؛» (never «احتمالاً»)" \
        if facts.get("certainty") == "unofficial" else "reported by news outlet"
    genres = ", ".join(meta.get("genres") or []) or "(unknown — do not add genre adjectives)"
    synopsis_en = meta.get("description") or ""
    return (
        f"EVENT_TYPE_HINT: {row['event_type']}\n"
        f"CERTAINTY: {certainty}\n"
        f"GENRES: {genres}\n\n"
        f"SOURCE TITLE: {title}\n"
        f"SOURCE SUMMARY: {summary}\n"
        f"SOURCE ARTICLE: {article}\n\n"
        f"SYNOPSIS_EN: {synopsis_en or '(none — return empty synopsis)'}"
    )

_FA_TO_EN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

def _news_agent_parse_json(text: str):
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text, flags=re.I)
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return None
    raw = m.group(0)
    for candidate in (raw, re.sub(r",\s*([}\]])", r"\1", raw)):
        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else None
        except Exception:
            continue
    return None

def _news_agent_clean_fa(value) -> str:
    value = str(value or "")
    value = _news_strip_cjk(value)
    value = re.sub(r"[*_`#]+", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value

def _news_agent_persian_letters(value: str) -> int:
    return len(re.findall(r"[\u0600-\u06FF]", value or ""))

def _news_agent_check_text(value: str, source_hay: str, source_numbers: set) -> str:
    """اگه متن مشکل داشت دلیلش رو برمیگردونه، وگرنه رشته خالی."""
    if re.search(r"(?i)\b(?:i think|as an ai|note:|here is|json)\b", value):
        return "متن غیرخبری"
    for inner in re.findall(r"«([^»]{2,140})»", value):
        if re.search(r"[A-Za-z]", inner):
            if _news_agent_norm(inner) and _news_agent_norm(inner) not in source_hay:
                return f"اسم «{inner}» توی منبع نیست"
    allowed = set(source_numbers)
    for n in source_numbers:                        # سال میلادی منبع → سال شمسی معادلش هم مجازه (۲۰۲۷ → ۱۴۰۵/۱۴۰۶)
        if n.isdigit() and 1990 <= int(n) <= 2100:
            allowed.update({str(int(n) - 621), str(int(n) - 622)})
    for num in re.findall(r"\d+", value.translate(_FA_TO_EN_DIGITS)):
        if int(num) > 12 and num not in allowed:
            return f"عدد {num} توی منبع نیست"
    return ""

_NEWS_FORMAL_PATTERNS = [
    (r"\bمی‌باشد\b|\bمیباشد\b", "می‌باشد"),
    (r"\bتوسط\b", "توسط"),
    (r"\bبه مناسبت\b", "به مناسبت"),
    (r"\bگردید", "گردید"),
    (r"\bنموده", "نموده"),
    (r"\bمیلادی\b", "میلادی"),
    (r"\s(?:شده|است|بوده)\s+است[.،!]?", "... است"),
    (r"\sاست[.!]\s*$|\sاست[.!]\s", "است"),
    (r"خواهد\s+(?:بود|شد|داشت|کرد)", "خواهد بود/شد"),
    (r"\bمی‌شود\b|\bمیشود\b", "می‌شود"),
    (r"\bگردیده", "گردیده"),
    (r"\bاز طریق\b", "از طریق"),
    (r"برنامه‌ریزی\s*شده|برنامه ریزی\s*شده", "برنامه‌ریزی شده"),
    (r"\bمعرفی شد(?:ه است)?\b.*\bمعرفی شد", "تکرار"),
]

def _news_agent_formal_words(text: str) -> list:
    found = []
    for pattern, label in _NEWS_FORMAL_PATTERNS:
        if re.search(pattern, text or "") and label not in found:
            found.append(label)
    return found

def _news_agent_soften(text: str) -> str:
    """چند اصلاح مطمئن از رسمی به محاوره‌ای."""
    t = text or ""
    t = re.sub(r"\s+میلادی\b", "", t)
    t = re.sub(r"(شده|بوده)\s+است(?=[.،!\s]|$)", r"\1", t)
    t = re.sub(r"\bمی‌باشد\b|\bمیباشد\b", "هست", t)
    t = re.sub(r"\sاست(?=[.!]?\s*$)", " هست", t)
    t = re.sub(r"خواهد\s+بود", "هست", t)
    t = re.sub(r"\bمی‌شود\b|\bمیشود\b", "میشه", t)
    # «کور» (cour) رو اکثر مخاطب‌ها نمی‌شناسن → «پارت»
    t = re.sub(r"(?<![\u0600-\u06FF])کورهای(?![\u0600-\u06FF])", "پارت‌های", t)
    t = re.sub(r"(?<![\u0600-\u06FF])کور(?=\s*(?:اول|دوم|سوم|چهارم|پنجم|ششم|[۰-۹0-9]|متوالی|پشت)|(?<=\s)کور(?![\u0600-\u06FF]))", "پارت", t)
    t = re.sub(r"(?<=[۰-۹0-9یکدوسهچهارپنج]\s)کور(?![\u0600-\u06FF])|(?<=\bدو\s)کور|(?<=\bسه\s)کور", "پارت", t)
    return t

def _news_agent_validate(data, row, facts: dict, meta: dict):
    if not isinstance(data, dict):
        return None, "JSON نامعتبر"
    if data.get("is_anime_news") is False:
        return None, "مدل گفت این خبر انیمه‌ای نیست"

    source_text = " ".join([
        _news_v2_clean_title_text(row["title"] or ""),
        _news_v2_clean_title_text(row["summary"] or ""),
        _news_v2_clean_title_text(row["article_text"] or "")[:4000],
    ])
    source_hay = _news_agent_norm(source_text)
    head_hay = _news_agent_norm(f"{row['title'] or ''} {(row['summary'] or '')[:400]}")
    source_numbers = set(re.findall(r"\d+", source_text))

    anime_title = re.sub(r"\s+", " ", str(data.get("anime_title") or "")).strip()
    nt = _news_agent_norm(anime_title)
    if not nt or len(nt) < 2:
        return None, "اسم انیمه خالیه"
    if nt not in head_hay:
        known = _news_agent_norm(facts.get("anime_display") or "")
        if not known or SequenceMatcher(None, nt, known).ratio() < 0.75:
            return None, f"اسم انیمه «{anime_title}» با تیتر خبر نمیخونه"

    headline = _news_agent_clean_fa(data.get("headline"))
    if not (15 <= len(headline) <= 320):
        return None, "طول تیتر نامناسبه"
    if _news_agent_persian_letters(headline) < 10:
        return None, "تیتر فارسی نیست"
    if nt not in _news_agent_norm(headline):
        return None, "اسم انیمه توی تیتر نیست"
    problem = _news_agent_check_text(headline, source_hay, source_numbers)
    if problem:
        return None, problem

    details = []
    raw_details = data.get("details") or []
    if isinstance(raw_details, str):
        raw_details = [raw_details]
    for d in raw_details[:2]:
        d = _news_agent_clean_fa(d)
        if not d or len(d) > 320 or _news_agent_persian_letters(d) < 8:
            continue
        if _news_agent_check_text(d, source_hay, source_numbers):
            continue
        details.append(d)

    synopsis = _news_agent_clean_fa(data.get("synopsis"))
    if synopsis and (not meta.get("description") or _news_agent_persian_letters(synopsis) < 20 or len(synopsis) > 520):
        synopsis = ""

    release_raw = re.sub(r"\s+", " ", str(data.get("release_date") or "")).strip()
    if release_raw:
        yrs = re.findall(r"\b(20\d{2})\b", release_raw)
        low = source_text.lower()
        words = [w for w in re.findall(r"[a-z]{3,}", release_raw.lower())]
        if (yrs and not all(y in source_text for y in yrs)) or (words and not any(w in low for w in words)):
            release_raw = ""

    studio = re.sub(r"\s+", " ", str(data.get("studio") or "")).strip()
    if studio and _news_agent_norm(studio) not in source_hay:
        studio = ""

    emoji = str(data.get("emoji") or "").strip()
    if not emoji or len(emoji) > 4 or re.search(r"[A-Za-z0-9\u0600-\u06FF]", emoji):
        emoji = "🔥"

    try:
        importance = int(str(data.get("importance")).translate(_FA_TO_EN_DIGITS))
        importance = importance if 1 <= importance <= 10 else None
    except Exception:
        importance = None

    extra_heads = {}
    for key in ("headline_trailer", "headline_images"):
        h = _news_agent_clean_fa(data.get(key))
        if h and 15 <= len(h) <= 320 and _news_agent_persian_letters(h) >= 10 and nt in _news_agent_norm(h) \
                and not _news_agent_check_text(h, source_hay, source_numbers):
            extra_heads[key] = h

    people = []
    raw_people = data.get("voice_actors") or []
    if isinstance(raw_people, str):
        raw_people = [raw_people]
    for name in raw_people[:3]:
        name = re.sub(r"\s+", " ", str(name or "")).strip()
        if 3 <= len(name) <= 60 and re.search(r"[A-Za-z]", name) and _news_agent_norm(name) in source_hay:
            people.append(name)

    return {
        **extra_heads,
        "voice_actors": people,
        "importance": importance,
        "anime_title": anime_title,
        "emoji": emoji,
        "headline": headline,
        "details": details,
        "synopsis": synopsis,
        "release_raw": release_raw,
        "studio": studio,
    }, ""

def _news_signature_text() -> str:
    return (get_setting("news_signature", "") or "").strip()

def _news_visible_len(html_text: str) -> int:
    return len(unescape(re.sub(r"<[^>]+>", "", html_text or "")))

def _news_render_caption(render: dict, synopsis: str = "", max_len: int = 1024) -> str:
    """render یا حالت agent داره (headline/details/...) یا حالت قالب (head_html)."""
    if render.get("mode") == "manual":
        return render.get("head_html") or ""
    blocks = []
    info = []
    if render.get("mode") == "agent":
        headline = _html_escape(_news_fa_digits_outside_titles(render.get("headline", "")))
        headline = re.sub(r"«([^»]{1,140})»", r"«<b>\1</b>»", headline)
        if render.get("unofficial") and not re.search(r"غیررسمی|طبق گزارش|احتمال|لو رفت|گفته می|شایعه", headline):
            headline = "طبق گزارشات؛ " + headline
        blocks.append(f"{render.get('emoji') or '🔥'} {headline}".strip())
        details = [_html_escape(_news_fa_digits_outside_titles(d)) for d in (render.get("details") or []) if d]
        if details:
            blocks.append("\n".join(details))
        if render.get("date_fa"):
            info.append(f"🗓 تاریخ پخش: <b>{_html_escape(render['date_fa'])}</b>")
        if render.get("studio"):
            info.append(f"⚙️ استودیو سازنده: {_html_escape(render['studio'])}")
    else:
        blocks.append(render.get("head_html") or "📰 خبر جدید")

    syn_block = f"<blockquote expandable>{_html_escape(synopsis)}</blockquote>" if synopsis else ""
    sig = _news_signature_text()
    sig_block = _html_escape(sig) if sig else ""

    def build(syn):
        parts = list(blocks)
        if syn:
            parts.append(syn)
        if info:
            parts.append("\n".join(info))
        if sig_block:
            parts.append(sig_block)
        return "\n\n".join(p for p in parts if p).strip()

    text = build(syn_block)
    if _news_visible_len(text) > max_len and synopsis:
        short = synopsis
        while short and _news_visible_len(build(f"<blockquote expandable>{_html_escape(short)}…</blockquote>")) > max_len:
            short = short[: max(0, len(short) - 40)].rsplit(" ", 1)[0]
        text = build(f"<blockquote expandable>{_html_escape(short)}…</blockquote>" if short else "")
    if _news_visible_len(text) > max_len:
        text = build("")
    if _news_visible_len(text) > max_len:
        text = _html_escape(unescape(re.sub(r"<[^>]+>", "", text))[: max_len - 1]) + "…"
    return text

def _news_item_render_and_save(item_id: int, facts: dict) -> str:
    row = _news_v2_item_by_id(item_id)
    render = facts.get("render") or {"mode": "template", "head_html": _html_escape(row["caption"] or "")}
    synopsis, _src = _news_get_synopsis(row["anime_key"] or "")
    caption = _news_render_caption(render, synopsis)
    with db_write_lock:
        conn = db()
        conn.execute("UPDATE news_v2_items SET caption=?, facts_json=? WHERE id=?",
                     (caption, json.dumps(facts, ensure_ascii=False), item_id))
        conn.commit()
        conn.close()
    return caption

def _news_template_render_for_insert(template_caption: str, facts: dict):
    head = _html_escape(template_caption or "")
    head = re.sub(r"«([^»]{1,140})»", r"«<b>\1</b>»", head)
    facts["render"] = {"mode": "template", "head_html": head}

def _news_fa_digits_outside_titles(value: str) -> str:
    # عددهای متن فارسی بشن ولی اسم‌هایی مثل «Kaiju No. 8» دست نخورن
    pieces = re.split(r"(«[^»]*»)", value or "")
    return "".join(p if p.startswith("«") else _news_fa_digits(p) for p in pieces)

def _news_anilist_staff_image(name: str) -> str:
    """عکس صداپیشه/عضو عوامل از AniList (با کش). اسم باید واقعاً همون آدم باشه."""
    name = (name or "").strip()
    if len(name) < 3:
        return ""
    key = "staff:" + (_news_topic_normalize(name)[:110] or name.lower()[:110])
    conn = db()
    row = conn.execute("SELECT meta_json, fetched_at FROM news_anime_meta WHERE lookup_key=?", (key,)).fetchone()
    conn.close()
    if row and time.time() - int(row["fetched_at"] or 0) < 30 * 86400:
        try:
            return json.loads(row["meta_json"] or "{}").get("image", "")
        except Exception:
            pass
    query = "query ($s: String) { Staff(search: $s) { name { full native } image { large } } }"
    image = ""
    try:
        req = urllib.request.Request(
            ANILIST_GRAPHQL_URL,
            data=json.dumps({"query": query, "variables": {"s": name[:80]}}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": NEWS_USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            staff = ((json.loads(resp.read().decode("utf-8", errors="ignore")) or {}).get("data") or {}).get("Staff") or {}
        full = ((staff.get("name") or {}).get("full") or "")
        # ترتیب اسم (فامیل/اسم) فرق می‌کنه؛ مجموعه‌ی کلمه‌ها باید یکی باشه
        want = set(_news_agent_norm(name).split())
        got = set(_news_agent_norm(full).split())
        if want and got and (want == got or SequenceMatcher(None, " ".join(sorted(want)), " ".join(sorted(got))).ratio() >= 0.85):
            candidate = ((staff.get("image") or {}).get("large") or "")
            if candidate and "default" not in candidate.lower() and _news_safe_url(candidate):
                image = candidate
    except Exception as exc:
        logger.info("AniList staff lookup failed for %s: %s", name, exc)
        return ""
    with db_write_lock:
        conn = db()
        conn.execute("""
            INSERT INTO news_anime_meta(lookup_key, meta_json, fetched_at) VALUES(?,?,?)
            ON CONFLICT(lookup_key) DO UPDATE SET meta_json=excluded.meta_json, fetched_at=excluded.fetched_at
        """, (key, json.dumps({"image": image}), int(time.time())))
        conn.commit()
        conn.close()
    return image


def _news_cast_images(row, meta: dict, people: list) -> tuple:
    """برای خبر صداپیشه: (پوستر انیمه, [عکس صداپیشه‌ها])."""
    cover = (meta or {}).get("cover") or ""
    faces = []
    for name in people[:3]:
        img = _news_anilist_staff_image(name)
        if img and img not in faces:
            faces.append(img)
    return cover, faces


def _news_v2_apply_cast_images(item_id: int, meta: dict, people: list):
    """خبر صداپیشه: عکس اصلی = پوستر انیمه، عکس(های) کنارش = صداپیشه‌ها. پیش‌نمایش موجود بازسازی میشه."""
    row = _news_v2_item_by_id(item_id)
    cover, faces = _news_cast_images(row, meta, people)
    if not cover and not faces:
        return
    main = cover or row["image_url"] or ""
    with db_write_lock:
        conn = db()
        conn.execute("UPDATE news_v2_items SET image_url=? WHERE id=?", (main, item_id))
        conn.commit()
        conn.close()
    _news_v2_update_facts(item_id, extra_images=faces, cast_people=people,
                          images_changed=bool(row["archive_message_id"]))
    logger.info("Cast images item=%s: cover=%s faces=%d", item_id, bool(cover), len(faces))


def _news_agent_apply_ex(item_id: int) -> tuple:
    """مثل _news_agent_apply_ex_inner؛ نتیجه‌ی آخرین تلاش AI برای گزارش سلامت ثبت میشه."""
    ok, info, kind = _news_agent_apply_ex_inner(item_id)
    if ok:
        _health_set("health_ai_ok", {"at": int(time.time()), "model": str(info)[:80]})
    elif kind in ("transient", "rejected"):
        _health_set("health_ai_fail", {"at": int(time.time()), "error": str(info)[:200], "kind": kind})
    return ok, info, kind

def _news_agent_apply(item_id: int) -> tuple:
    """خروجی (موفق؟, توضیح). در صورت شکست کپشن قالبی دست نمیخوره."""
    ok, info, _kind = _news_agent_apply_ex(item_id)
    return ok, info

def _news_agent_apply_ex_inner(item_id: int) -> tuple:
    """خروجی (موفق؟, توضیح, نوع شکست). نوع شکست: "" / "transient" (بعداً دوباره) / "not_news" / "rejected"."""
    with _news_agent_lock:
        ok, why = _news_agent_can_call()
        if not ok:
            return False, why, "transient"
        row = _news_v2_item_by_id(item_id)
        if not row:
            return False, "خبر پیدا نشد", "rejected"
        try:
            facts = json.loads(row["facts_json"] or "{}")
        except Exception:
            facts = {}

        lookup_name = facts.get("anime_eng_name") or facts.get("anime_display") or ""
        meta = {}
        if lookup_name and lookup_name not in ("این انیمه",):
            meta = _news_anilist_lookup(lookup_name)

        user_prompt = _news_agent_user_prompt(row, facts, meta)
        parts, reason, model = None, "", ""
        kept = None  # جواب درست ولی رسمی؛ اگه تلاش دوم بهتر نشد همین استفاده میشه
        for attempt in range(2):
            prompt = user_prompt
            if attempt and reason:
                # یه بار دیگه با گفتن ایراد جواب قبلی
                prompt += (f"\n\nYOUR PREVIOUS ANSWER WAS REJECTED because: {reason}\n"
                           "Fix exactly that problem and output the JSON again.")
            try:
                text, model = _news_agent_generate(_NEWS_AGENT_SYSTEM, prompt)
            except Exception as exc:
                if kept:
                    parts = kept
                    break
                logger.warning("News Agent failed item=%s: %s", item_id, exc)
                transient = bool(getattr(exc, "transient", False)) or isinstance(exc, (_NewsAgentHTTPError, TimeoutError, OSError))
                return False, str(exc), "transient" if transient else "rejected"
            data = _news_agent_parse_json(text)
            if isinstance(data, dict) and data.get("is_anime_news") is False:
                return False, "به نظر AI این خبر انیمه‌ای/خبری نیست", "not_news"
            parts, reason = _news_agent_validate(data, row, facts, meta)
            if parts:
                formal = _news_agent_formal_words(" ".join([parts["headline"]] + parts["details"]))
                if formal and attempt == 0:
                    # یه بار دیگه با تذکر لحن؛ اگه باز رسمی بود همین قبول میشه
                    reason = ("too formal/bookish (" + "، ".join(formal) + "). Rewrite in spoken colloquial Persian "
                              "like the channel examples, keep it short, no dates in text")
                    kept = parts
                    parts = None
                    continue
                break
            if kept:
                parts = kept
                break
            logger.warning("News Agent output rejected item=%s model=%s attempt=%s: %s", item_id, model, attempt + 1, reason)
        if not parts:
            facts["agent_rejected"] = reason
            _news_item_render_and_save(item_id, facts)
            return False, f"خروجی رد شد: {reason}", "rejected"

        # تاریخ: اولویت با تاریخی که AI از متن فهمیده (با منبع چک شده)، بعد استخراج خود بات؛
        # هر دو باید «تازه» باشن تا تاریخ پخش نسخه قدیمی یا شروع مانگا نیاد.
        published = row["published_at"] or ""
        date_fa = ""
        if parts["release_raw"] and _news_release_is_plausible(parts["release_raw"], published):
            try:
                date_fa = _news_localize_date(parts["release_raw"], published)
            except Exception:
                date_fa = ""
        if not date_fa and facts.get("release_raw") and _news_release_is_plausible(facts["release_raw"], published):
            date_fa = facts.get("release_fa") or ""

        # استودیو: منبع خبر > خروجی مدل (که با منبع چک شده) > AniList فقط برای اثر تازه
        studio = parts["studio"] or facts.get("studio")
        if not studio and meta.get("studio"):
            try:
                if int(meta.get("year") or 0) >= int(time.strftime("%Y", time.gmtime())) - 1:
                    studio = meta["studio"]
            except Exception:
                pass

        facts["render"] = {
            "mode": "agent",
            "emoji": parts["emoji"],
            "headline": _news_agent_soften(parts["headline"]),
            "headline_trailer": _news_agent_soften(parts.get("headline_trailer") or ""),
            "headline_images": _news_agent_soften(parts.get("headline_images") or ""),
            "details": [_news_agent_soften(d) for d in parts["details"]],
            "date_fa": date_fa,
            "studio": studio,
            "unofficial": facts.get("certainty") == "unofficial",
        }
        facts["agent_model"] = model
        if parts.get("importance") is not None:
            facts["agent_importance"] = parts["importance"]
        facts.pop("agent_rejected", None)

        anime_key = row["anime_key"] or ""
        current_syn, syn_src = _news_get_synopsis(anime_key)
        if parts["synopsis"] and syn_src != "admin":
            _news_set_synopsis(anime_key, parts["synopsis"], "agent")

        with db_write_lock:
            conn = db()
            conn.execute("UPDATE news_v2_items SET anime_display=? WHERE id=?", (parts["anime_title"], item_id))
            conn.commit()
            conn.close()
        _news_item_render_and_save(item_id, facts)
        if _news_is_cast_news(row["title"] or "", row["summary"] or ""):
            try:
                _news_v2_apply_cast_images(item_id, meta, parts.get("voice_actors") or [])
            except Exception:
                logger.exception("Cast images failed item=%s", item_id)
        logger.info("News Agent OK item=%s model=%s", item_id, model)
        return True, model, ""

def _news_agent_cycle_allow() -> bool:
    global _news_agent_cycle_count
    if _news_agent_cycle_count >= NEWS_AGENT_MAX_PER_CYCLE:
        return False
    _news_agent_cycle_count += 1
    return True

def _news_agent_cycle_reset():
    global _news_agent_cycle_count
    _news_agent_cycle_count = 0

def _news_v2_image_file(url: str):
    """عکس رو خود بات دانلود میکنه چون تلگرام خیلی وقتا نمیتونه از سایت‌های خبری بگیره."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
            "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "image" not in ctype:
                return None
            data = resp.read(9_000_001)
        if len(data) < 2048 or len(data) > 9_000_000:
            return None
        bio = io.BytesIO(data)
        bio.name = "news.png" if "png" in ctype else "news.jpg"
        return bio
    except Exception as exc:
        logger.info("News image download failed %s: %s", url, exc)
        return None

def _news_v2_archive_chat(row):
    value = str(row["archive_chat_id"] or "")
    return int(value) if value.lstrip("-").isdigit() else value

def _news_v2_refresh_archive(item_id: int) -> bool:
    row = _news_v2_item_by_id(item_id)
    if not row or not row["archive_message_id"]:
        return False
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except Exception:
        facts = {}
    if facts.get("images_changed"):
        # عکس‌ها عوض شدن (مثلاً پوستر + عکس صداپیشه) → پیش‌نمایش از نو، قبلی‌ها پاک
        chat = _news_v2_archive_chat(row)
        old_ids = [int(row["archive_message_id"])] + [int(x) for x in (facts.get("archive_extra_ids") or [])]
        _news_v2_update_facts(item_id, images_changed=False)
        try:
            if not _news_v2_send_preview(item_id):
                return False
        except Exception as exc:
            logger.warning("News archive repost (new images) failed item=%s: %s", item_id, exc)
            return False
        for mid in old_ids:
            try:
                bot.delete_message(chat, mid)
            except Exception:
                pass
        return True
    expects = row["event_type"] in ("trailer", "trailer_visual", "character_pv")
    kb = _news_v2_archive_markup(item_id, row["url"], row["status"], expects, bool(row["archive_secondary_message_id"]))
    chat = _news_v2_archive_chat(row)
    caption = _news_v2_archive_caption(row)
    try:
        if row["archive_media_type"] == "photo":
            bot.edit_message_caption(caption[:4000], chat_id=chat, message_id=int(row["archive_message_id"]),
                                     reply_markup=kb, parse_mode="HTML")
        else:
            bot.edit_message_text(caption[:4096], chat_id=chat, message_id=int(row["archive_message_id"]),
                                  reply_markup=kb, parse_mode="HTML", link_preview_options=WITH_LINK_PREVIEW)
        return True
    except Exception as exc:
        if "not modified" in str(exc).lower():
            return True
        logger.warning("News archive edit failed item=%s: %s — reposting", item_id, exc)
    # ویرایش نشد (پیام پاک شده، کپشن HTML نامعتبر، ...) → پیام جدید بفرست و قبلی رو پاک کن
    old_chat, old_id = chat, int(row["archive_message_id"])
    try:
        if not _news_v2_send_preview(item_id):
            return False
    except Exception as exc:
        logger.warning("News archive repost failed item=%s: %s", item_id, exc)
        return False
    try:
        bot.delete_message(old_chat, old_id)
    except Exception:
        pass
    return True

def _news_v2_agent_importance(item_id: int):
    row = _news_v2_item_by_id(item_id)
    try:
        value = json.loads((row["facts_json"] if row else "") or "{}").get("agent_importance")
        return int(value) if value is not None else None
    except Exception:
        return None

NEWS_AI_MAX_ATTEMPTS = 6
NEWS_AI_MAX_WAIT_MINUTES = 180


def _news_v2_update_facts(item_id: int, status: str | None = None, **changes):
    row = _news_v2_item_by_id(item_id)
    if not row:
        return
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except Exception:
        facts = {}
    facts.update(changes)
    with db_write_lock:
        conn = db()
        if status:
            conn.execute("UPDATE news_v2_items SET facts_json=?, status=? WHERE id=?",
                         (json.dumps(facts, ensure_ascii=False), status, item_id))
        else:
            conn.execute("UPDATE news_v2_items SET facts_json=? WHERE id=?",
                         (json.dumps(facts, ensure_ascii=False), item_id))
        conn.commit()
        conn.close()


def _news_v2_agent_step(item_id: int, importance: int) -> str:
    """ایجنت رو روی خبر اجرا می‌کنه. خروجی: ok / wait (AI موقتاً در دسترس نیست) / low / template."""
    if not _news_agent_cycle_allow():
        _news_v2_mark_ai_wait(item_id, "سقف درخواست این دور")
        return "wait"
    try:
        ok, info, kind = _news_agent_apply_ex(item_id)
    except Exception as exc:
        logger.exception("News Agent step failed item=%s", item_id)
        ok, info, kind = False, str(exc), "transient"
    if ok:
        agent_imp = _news_v2_agent_importance(item_id)
        if agent_imp is not None and agent_imp <= 3 and importance < 80:
            _news_v2_mark_low(item_id)
            logger.info("News V2 item=%s skipped: agent rated importance %s", item_id, agent_imp)
            return "low"
        return "ok"
    if kind == "not_news":
        _news_v2_mark_low(item_id)
        logger.info("News V2 item=%s skipped: %s", item_id, info)
        return "low"
    if kind == "transient":
        _news_v2_mark_ai_wait(item_id, info)
        return "wait"
    return "template"


def _news_v2_mark_ai_wait(item_id: int, reason: str):
    row = _news_v2_item_by_id(item_id)
    try:
        facts = json.loads((row["facts_json"] if row else "") or "{}")
    except Exception:
        facts = {}
    _news_v2_update_facts(
        item_id, status="ai_wait",
        ai_attempts=int(facts.get("ai_attempts") or 0) + 1,
        ai_wait_since=facts.get("ai_wait_since") or int(time.time()),
        ai_last_error=str(reason)[:300],
    )
    logger.info("News V2 item=%s waiting for AI: %s", item_id, reason)


_NEWS_DUP_WORDS = ("spin-off", "spinoff", "movie", "film", "season", "cour", "part", "final", "sequel", "delay",
                   "trailer", "visual", "cast", "premiere", "adaptation", "episodes")


def _news_v2_identity(row) -> str:
    """اسم یکسان‌شده‌ی انیمه (با AniList): «That Time I Got Reincarnated as a Slime» و «Tensei shitara Slime» یکی میشن."""
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except Exception:
        facts = {}
    for name in (row["anime_eng_name"], facts.get("anime_title"), facts.get("anime_eng_name"), row["anime_display"]):
        name = (name or "").strip()
        if len(name) < 3 or name == "این انیمه":
            continue
        meta = _news_anilist_lookup(name) or {}
        ident = meta.get("title_romaji") or meta.get("title_en")
        if ident:
            return _news_agent_norm(ident)
        return _news_agent_norm(_anime_base_name(name))
    return ""


def _news_v2_dup_marks(row) -> set:
    """نشونه‌های محتوایی خبر (سال‌ها، شماره‌ها، کلمه‌های کلیدی) برای مقایسه‌ی دو خبر هم‌موضوع."""
    text = f"{row['title'] or ''} {(row['summary'] or '')[:600]}".lower()
    marks = {m for m in re.findall(r"\b(20\d\d)\b", text)}
    marks |= {w for w in _NEWS_DUP_WORDS if w in text}
    return marks


def _news_v2_cross_duplicate(item_id: int):
    """قبل از رفتن به آرشیو: همین خبر (همون انیمه، هر اسمی) از یه منبع دیگه توی ۳ روز اخیر به آرشیو رفته؟
    خروجی: ردیف خبر قبلی یا None."""
    row = _news_v2_item_by_id(item_id)
    if not row:
        return None
    ident = _news_v2_identity(row)
    if not ident:
        return None
    conn = db()
    rows = conn.execute("""
        SELECT n.*, s.title AS source_title FROM news_v2_items n JOIN news_sources s ON s.id=n.source_id
        WHERE n.id<>? AND n.archive_message_id IS NOT NULL AND n.archive_message_id<>''
          AND n.status IN ('pending','approved','published')
          AND n.created_at >= datetime('now','-3 day')
        ORDER BY n.id DESC LIMIT 80
    """, (item_id,)).fetchall()
    conn.close()
    mine = _news_v2_dup_marks(row)
    for old in rows:
        try:
            if _news_v2_identity(old) != ident:
                continue
        except Exception:
            continue
        same_type = bool(row["event_type"]) and row["event_type"] == old["event_type"]
        shared = mine & _news_v2_dup_marks(old)
        if same_type or len(shared) >= 2:
            return old
    return None


def _news_v2_send_preview_checked(item_id: int) -> bool:
    """مثل _news_v2_send_preview، ولی اگه همین خبر از منبع دیگه قبلاً اومده باشه، جدا فرستاده نمیشه؛
    فقط یه یادداشت زیر خبر قبلی میاد (با لینک منبع جدید و دکمه‌ی «با این حال بفرست»)."""
    try:
        old = _news_v2_cross_duplicate(item_id)
    except Exception:
        logger.exception("Cross-duplicate check failed item=%s", item_id)
        old = None
    if old is None:
        return _news_v2_send_preview(item_id)
    row = _news_v2_item_by_id(item_id)
    _news_v2_update_facts(item_id, status="duplicate", duplicate_of=int(old["id"]))
    logger.info("News V2 item=%s is the same news as #%s (other source); not sent", item_id, old["id"])
    try:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📥 با این حال بفرست به آرشیو", callback_data=f"nv2_force:{item_id}"))
        if row["url"]:
            kb.add(InlineKeyboardButton("🔗 منبع دوم", url=row["url"]))
        bot.send_message(
            _news_v2_archive_chat(old),
            f"♻️ یه منبع دیگه ({row['source_title'] or '—'}) هم همین خبر رو داد؛ جدا فرستاده نشد.\n"
            f"«{(row['title'] or '')[:200]}»\n"
            "اگه جزئیاتش با این پست فرق داره (مثلاً شماره‌ی فصل/پارت یا تاریخ)، منبع رو چک کن.",
            reply_to_message_id=int(old["archive_message_id"]), allow_sending_without_reply=True,
            reply_markup=kb, link_preview_options=NO_LINK_PREVIEW,
        )
    except Exception:
        logger.exception("Duplicate notice failed item=%s", item_id)
    return False


def _news_v2_retry_ai_waiting() -> int:
    """خبرهایی که منتظر AI موندن رو دوباره امتحان می‌کنه؛ اگه خیلی طول کشید با متن قالبی می‌فرسته."""
    conn = db()
    rows = conn.execute("SELECT id, facts_json FROM news_v2_items WHERE status='ai_wait' ORDER BY id LIMIT 20").fetchall()
    conn.close()
    released = 0
    for row in rows:
        item_id = int(row["id"])
        try:
            facts = json.loads(row["facts_json"] or "{}")
        except Exception:
            facts = {}
        waited_min = (time.time() - int(facts.get("ai_wait_since") or time.time())) / 60
        give_up = not _news_agent_can_call()[0] \
            or int(facts.get("ai_attempts") or 0) >= NEWS_AI_MAX_ATTEMPTS \
            or waited_min >= NEWS_AI_MAX_WAIT_MINUTES
        if give_up:
            outcome = "template"
            logger.warning("News V2 item=%s: AI still unavailable after %d min; sending template text", item_id, waited_min)
        else:
            outcome = _news_v2_agent_step(item_id, int(facts.get("importance") or 0))
        if outcome in ("ok", "template"):
            _news_v2_update_facts(item_id, status="pending")
            try:
                if _news_v2_send_preview_checked(item_id):
                    released += 1
            except Exception:
                logger.exception("News V2 preview failed item=%s", item_id)
    return released


def _news_v2_poll_source(source_row, bootstrap: bool):
    sid = int(source_row["id"])
    feed = (source_row["feed_url"] or "").strip()
    if _news_v2_is_ranking_source(source_row):
        return {"new": 0, "seeded": 0, "duplicate": 0, "error": ""}
    try:
        entries = _news_parse_feed(feed)
    except Exception as exc:
        _news_v2_mark_source(sid, str(exc), bootstrapped=not bootstrap)
        logger.warning("News V2 source failed %s: %s", source_row["title"], exc)
        return {"new": 0, "seeded": 0, "duplicate": 0, "error": str(exc)}

    new = seeded = dup = low = 0
    for item in reversed(entries[:NEWS_V2_PREVIEW_LIMIT]):
        conn = db()
        exists = conn.execute(
            "SELECT id FROM news_v2_items WHERE source_id=? AND guid=?",
            (sid, item.get("guid", "")),
        ).fetchone()
        conn.close()
        if exists:
            continue
        if bootstrap:
            inserted = _news_v2_insert(sid, item, status="seeded")
            if inserted:
                seeded += 1
            continue

        # فقط خبر جدید را Enrich کن؛ Seed اولیه هیچ درخواست سنگین مقاله‌ای نمی‌زند.
        if not _social_handle_label(feed):
            try:
                item = _news_enrich_article(item)
            except Exception as exc:
                logger.info("News V2 enrich failed source=%s title=%s: %s", source_row["title"], item.get("title"), exc)
        else:
            item["article_text"] = item.get("article_text") or item.get("summary") or ""

        inserted = _news_v2_insert(sid, item, status="pending")
        if not inserted:
            continue
        row = _news_v2_item_by_id(inserted)
        if row and row["status"] == "duplicate":
            dup += 1
            continue
        try:
            importance = _news_v2_score_item(inserted)
        except Exception:
            logger.exception("News importance failed item=%s", inserted)
            importance = 100
        if importance < _news_min_importance():
            _news_v2_mark_low(inserted)
            low += 1
            logger.info("News V2 item=%s skipped as low importance (%s)", inserted, importance)
            continue
        new += 1
        if _news_agent_can_call()[0]:
            outcome = _news_v2_agent_step(inserted, importance)
            if outcome == "wait":
                continue
            if outcome == "low":
                new -= 1
                low += 1
                continue
        try:
            if not _news_v2_send_preview_checked(inserted):
                new -= 1
        except Exception:
            logger.exception("News V2 preview failed item=%s", inserted)

    _news_v2_mark_source(sid, "", bootstrapped=True)
    return {"new": new, "seeded": seeded, "duplicate": dup, "low": low, "error": ""}

def run_news_v2_check(manual: bool = False):
    if not news_v2_run_lock.acquire(blocking=False):
        return {"sources": 0, "new": 0, "seeded": 0, "duplicate": 0, "busy": True, "errors": 0}
    total = {"sources": 0, "new": 0, "seeded": 0, "duplicate": 0, "busy": False, "errors": 0}
    _news_agent_cycle_reset()
    try:
        try:
            total["ai_released"] = _news_v2_retry_ai_waiting()
        except Exception:
            logger.exception("Retrying AI-waiting items failed")
        for source in _news_v2_source_rows(active_only=True):
            total["sources"] += 1
            state = _news_v2_source_state(int(source["id"]))
            bootstrap = not bool(state and state["bootstrapped"])
            result = _news_v2_poll_source(source, bootstrap=bootstrap)
            total["new"] += result["new"]
            total["seeded"] += result["seeded"]
            total["duplicate"] += result["duplicate"]
            total["low"] = total.get("low", 0) + int(result.get("low", 0))
            if result.get("error"):
                total["errors"] += 1
        return total
    finally:
        news_v2_run_lock.release()

def _news_v2_check_interval_minutes() -> int:
    try:
        value = int(get_setting("news_v2_check_minutes", str(NEWS_V2_DEFAULT_CHECK_MINUTES)))
    except Exception:
        value = NEWS_V2_DEFAULT_CHECK_MINUTES
    return max(NEWS_V2_MIN_CHECK_MINUTES, min(value, 1440))

def news_v2_collector_loop():
    time.sleep(35)
    while True:
        try:
            if _news_archive_channel():
                result = run_news_v2_check(manual=False)
                logger.info("News V2 collector cycle: %s", result)
                _health_set("health_last_cycle", {"at": int(time.time()), "result": result})
        except Exception as exc:
            logger.exception("News V2 collector loop failed")
            _health_set("health_last_crash", {"at": int(time.time()), "error": str(exc)[:300]})
        time.sleep(_news_v2_check_interval_minutes() * 60)

# =========================
# گزارش سلامت بات (/health) و هشدار خودکار
# =========================
def _health_set(key: str, value: dict):
    try:
        set_setting(key, json.dumps(value, ensure_ascii=False))
    except Exception:
        pass


def _health_get(key: str) -> dict:
    try:
        return json.loads(get_setting(key, "") or "{}")
    except Exception:
        return {}


def _ago(ts) -> str:
    """«۵ دقیقه پیش» از timestamp یا متن تاریخ SQLite (UTC)."""
    if not ts:
        return "هیچ‌وقت"
    try:
        if isinstance(ts, (int, float)):
            sec = time.time() - float(ts)
        else:
            dt = datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S")
            sec = (datetime.now(timezone.utc).replace(tzinfo=None) - dt).total_seconds()
    except Exception:
        return str(ts)
    sec = max(0, int(sec))
    if sec < 90:
        return "همین الان"
    if sec < 3600:
        return f"{_news_fa_digits(sec // 60)} دقیقه پیش"
    if sec < 86400:
        return f"{_news_fa_digits(sec // 3600)} ساعت پیش"
    return f"{_news_fa_digits(sec // 86400)} روز پیش"


def _health_report() -> tuple:
    """(متن گزارش, لیست مشکل‌ها)"""
    problems, lines = [], ["🩺 گزارش سلامت بات خبر", ""]

    def fa(n) -> str:
        return _news_fa_digits(str(int(n or 0)))
    interval = _news_v2_check_interval_minutes()

    # بررسی دوره‌ای
    cycle = _health_get("health_last_cycle")
    if not _news_archive_channel():
        problems.append("کانال آرشیو تنظیم نشده؛ بات هیچ خبری جمع نمی‌کنه")
    if cycle.get("at"):
        late = time.time() - cycle["at"] > (interval * 3 + 10) * 60
        r = cycle.get("result") or {}
        lines.append(f"{'⚠️' if late else '✅'} آخرین دور بررسی: {_ago(cycle['at'])} (هر {fa(interval)} دقیقه)")
        lines.append(f"   منبع: {fa(r.get('sources'))} | خبر جدید: {fa(r.get('new'))} | "
                     f"کم‌اهمیت: {fa(r.get('low'))} | تکراری: {fa(r.get('duplicate'))} | "
                     f"منبع با خطا: {fa(r.get('errors'))}")
        if late:
            problems.append("دور بررسی خبرها خیلی وقته اجرا نشده (بات گیر کرده؟ ری‌استارتش کن)")
    else:
        lines.append("⏳ هنوز هیچ دور بررسی‌ای از روشن شدن بات تموم نشده")
    crash = _health_get("health_last_crash")
    if crash.get("at") and time.time() - crash["at"] < 6 * 3600:
        lines.append(f"❌ خطای کلی {_ago(crash['at'])}: {crash.get('error', '')[:150]}")
        problems.append("بخش جمع‌آوری خبر خطا داده")

    # منابع
    conn = db()
    sources = conn.execute("SELECT id, title, feed_url, last_checked_at, last_error FROM news_sources WHERE active=1 ORDER BY id").fetchall()
    stats = {r["status"]: r["n"] for r in conn.execute(
        "SELECT status, COUNT(*) AS n FROM news_v2_items WHERE created_at >= datetime('now','-1 day') GROUP BY status")}
    last_item = conn.execute(
        "SELECT created_at FROM news_v2_items WHERE status IN ('pending','approved','published') ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    failing = [s for s in sources if (s["last_error"] or "").strip()]
    lines += ["", f"📰 منابع فعال: {fa(len(sources))} — {'✅ همه سالم' if not failing else f'⚠️ {fa(len(failing))} تا خطا دارن'}"]
    for src in failing[:8]:
        label = _social_handle_label(src["feed_url"]) or src["title"]
        lines.append(f"   ⚠️ #{src['id']} {label[:40]}: {(src['last_error'] or '')[:110]}")
    if sources and len(failing) == len(sources):
        problems.append("همه‌ی منابع خطا میدن (احتمالاً اینترنت/VPN قطعه)")

    # خبرهای ۲۴ ساعت اخیر
    sent = sum(stats.get(k, 0) for k in ("pending", "approved", "published"))
    lines += ["", "📊 ۲۴ ساعت اخیر:",
              f"   به آرشیو رفته: {fa(sent)} | کم‌اهمیت (فیلتر شد): {fa(stats.get('low'))} | "
              f"تکراری: {fa(stats.get('duplicate'))} | منتظر AI: {fa(stats.get('ai_wait'))}",
              f"   آخرین خبری که به آرشیو رفت: {_ago(last_item['created_at'] if last_item else None)}"]
    if stats.get("ai_wait", 0) >= 5:
        problems.append(f"{fa(stats['ai_wait'])} خبر منتظر AI موندن")

    # AI
    ai_ok, ai_fail = _health_get("health_ai_ok"), _health_get("health_ai_fail")
    lines += ["", f"🤖 AI: {'روشن' if _news_agent_can_call()[0] else '⚠️ ' + _news_agent_can_call()[1]}",
              f"   آخرین موفقیت: {_ago(ai_ok.get('at'))}" + (f" ({ai_ok.get('model')})" if ai_ok.get("model") else "")]
    if ai_fail.get("at") and ai_fail["at"] > ai_ok.get("at", 0):
        lines.append(f"   ⚠️ آخرین تلاش ناموفق بود ({_ago(ai_fail['at'])}): {ai_fail.get('error', '')[:140]}")
        if time.time() - ai_ok.get("at", 0) > 3 * 3600:
            problems.append("AI بیش از ۳ ساعته موفق نشده")

    # دیتابیس/بکاپ و تریلر
    age = _news_last_backup_age_hours()
    lines += ["", f"💾 آخرین بکاپ: {'هیچ‌وقت' if age > 1e8 else _ago(time.time() - age * 3600)}",
              f"🎬 دانلود خودکار تریلر: {'✅ آماده' if yt_dlp is not None else '⚠️ yt-dlp نصب نیست'}"]

    head = "✅ همه‌چی سالمه" if not problems else "⚠️ مشکل‌ها:\n" + "\n".join(f"• {p}" for p in problems)
    if not problems and sent == 0:
        head += "\nℹ️ بات سالمه؛ فقط توی ۲۴ ساعت اخیر خبر مهمی از منابعت نیومده (یا فیلتر اهمیت ردشون کرده)."
    lines[1:2] = [head, ""]
    return "\n".join(lines), problems


@bot.message_handler(commands=["health", "status"])
@bot.message_handler(func=lambda m: m.text == "🩺 وضعیت بات")
def news_health_command(message):
    if message.from_user.id not in ADMINS:
        return
    text, _problems = _health_report()
    bot.send_message(message.chat.id, text[:4096], link_preview_options=NO_LINK_PREVIEW)


def start_health_watchdog_thread():
    """هر ۱۵ دقیقه وضعیت رو چک می‌کنه؛ اگه مشکل جدی بود به ادمین‌ها خبر میده (هر مشکل حداکثر هر ۶ ساعت یه بار)."""
    def loop():
        time.sleep(20 * 60)  # بعد از روشن شدن فرصت بده یه دور کامل اجرا بشه
        while True:
            try:
                text, problems = _health_report()
                if problems:
                    key = "|".join(sorted(problems))
                    last = _health_get("health_last_alert")
                    if last.get("key") != key or time.time() - last.get("at", 0) > 6 * 3600:
                        _health_set("health_last_alert", {"key": key, "at": int(time.time())})
                        for admin in ADMINS:
                            try:
                                bot.send_message(admin, "🚨 هشدار خودکار بات خبر\n\n" + text[:3900],
                                                 link_preview_options=NO_LINK_PREVIEW)
                            except Exception:
                                pass
            except Exception:
                logger.exception("Health watchdog failed")
            time.sleep(15 * 60)

    threading.Thread(target=loop, daemon=True, name="health-watchdog").start()


def start_news_v2_collector_thread():
    threading.Thread(target=news_v2_collector_loop, daemon=True, name="news-v2-collector").start()

def run_ranking_check():
    if not ranking_run_lock.acquire(blocking=False):
        return {"sources": 0, "new": 0, "skipped": 0, "errors": 0}
    total = {"sources": 0, "new": 0, "skipped": 0, "errors": 0}
    try:
        for source in _news_source_rows(active_only=True):
            if not _news_v2_is_ranking_source(source):
                continue
            total["sources"] += 1
            if not _news_auto_source_due(source):
                total["skipped"] += 1
                continue
            try:
                bootstrap = not bool(source["last_checked_at"])
                result = _poll_one_news_source(source, bootstrap=bootstrap)
                total["new"] += int(result.get("new", 0))
                if result.get("error"):
                    total["errors"] += 1
            except Exception:
                total["errors"] += 1
                logger.exception("Ranking Engine source failed id=%s", source["id"])
        return total
    finally:
        ranking_run_lock.release()

def ranking_collector_loop():
    time.sleep(60)
    while True:
        try:
            if _news_archive_channel():
                logger.info("Ranking Engine cycle: %s", run_ranking_check())
        except Exception:
            logger.exception("Ranking Engine loop failed")
        time.sleep(30 * 60)

def start_ranking_collector_thread():
    threading.Thread(target=ranking_collector_loop, daemon=True, name="ranking-engine").start()

def _news_v2_source_class_fa(value: str) -> str:
    return {
        "official": "رسمی",
        "official_media": "رسانه رسمی/ناشر",
        "secondary": "رسانه خبری",
        "leak": "غیررسمی / لیک",
    }.get(value or "", value or "نامشخص")

def _news_v2_event_fa(value: str) -> str:
    return {
        "season_announcement": "اعلام فصل جدید",
        "trailer": "تریلر",
        "trailer_visual": "پوستر + تریلر",
        "visual": "پوستر / ویژوال",
        "release_date": "تاریخ پخش",
        "delay": "تأخیر",
        "cancellation": "لغو / توقف",
        "new_anime": "انیمه جدید",
        "character_pv": "تریلر شخصیت",
        "movie": "فیلم",
        "other": "نیازمند بررسی",
    }.get(value or "", value or "نامشخص")

def show_news_admin_menu(chat_id: int, user_id: int, text: str | None = None):
    # Override منوی قدیمی؛ Handlerهای قبلی نیز در زمان اجرا همین نسخه جدید را صدا می‌زنند.
    if user_id not in ADMINS:
        return
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📰 بررسی News V2 الان"))
    kb.add(KeyboardButton("📥 صف بررسی News V2"), KeyboardButton("📊 آمار News V2"))
    kb.add(KeyboardButton("📡 منابع News V2"), KeyboardButton("➕ افزودن منبع خبری"))
    kb.add(KeyboardButton("📦 تنظیم کانال آرشیو خبر"), KeyboardButton("⏱ فاصله News V2"))
    kb.add(KeyboardButton("🤖 وضعیت ایجنت خبر"), KeyboardButton("✍️ امضای کانال خبر"))
    kb.add(KeyboardButton("⭐️ فیلتر اهمیت خبر"), KeyboardButton("💾 بکاپ دیتابیس"))
    kb.add(KeyboardButton("🩺 وضعیت بات"))
    kb.add(KeyboardButton("🔑 تنظیم سرویس AI"))
    kb.add(KeyboardButton("📡 مدیریت کانال‌های پست"))
    kb.add(KeyboardButton("🧪 تست رنکینگ هفتگی"))
    kb.add(KeyboardButton(BACK_MAIN))
    archive = _news_archive_channel()
    status = f"📦 آرشیو: {archive}" if archive else "⚠️ کانال آرشیو هنوز تنظیم نشده."
    body = (
        (text or "📰 News V2 — موتور خبری جدید")
        + f"\n\n{status}"
        + ("\n🤖 ایجنت کپشن: فعال ✅" if _news_agent_can_call()[0] else "\n🤖 ایجنت کپشن: ⚠️ " + _news_agent_can_call()[1])
        + "\n✅ انتشار: فقط بعد از تأیید ادمین"
        + "\n⚠️ لیکرهای X: همیشه غیررسمی"
        + "\n📊 Ranking Engine: مستقل از News V2"
        + f"\n⏱ بررسی خودکار: هر {_news_v2_check_interval_minutes()} دقیقه"
    )
    bot.send_message(chat_id, body, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📰 بررسی News V2 الان")
def news_v2_check_now(message):
    if message.from_user.id not in ADMINS:
        return
    if not _news_archive_channel():
        bot.send_message(message.chat.id, "❌ اول کانال آرشیو خبر رو تنظیم کن.")
        show_news_admin_menu(message.chat.id, message.from_user.id)
        return
    chat_id = message.chat.id
    bot.send_message(chat_id, "🔄 News V2 در حال بررسی منابع است…")

    def worker():
        try:
            result = run_news_v2_check(manual=True)
            if result.get("busy"):
                bot.send_message(chat_id, "⏳ یک بررسی News V2 از قبل در حال اجراست.")
                return
            bot.send_message(
                chat_id,
                "✅ بررسی News V2 تمام شد.\n\n"
                f"📡 منابع: {result['sources']}\n"
                f"📰 خبر جدید: {result['new']}\n"
                f"📚 Seed اولیه: {result['seeded']}\n"
                f"♻️ تکراری: {result['duplicate']}\n"
                f"⚠️ خطای منبع: {result['errors']}",
            )
        except Exception as exc:
            logger.exception("Manual News V2 check failed")
            bot.send_message(chat_id, f"❌ بررسی News V2 ناموفق بود:\n{exc}")
    threading.Thread(target=worker, daemon=True, name="news-v2-manual").start()

@bot.message_handler(func=lambda m: m.text == "📡 منابع News V2")
def news_v2_sources_list(message):
    if message.from_user.id not in ADMINS:
        return
    rows = _news_v2_source_rows(active_only=False)
    if not rows:
        bot.send_message(message.chat.id, "هیچ منبع News V2 ثبت نشده.")
        return
    for row in rows:
        st = _news_v2_source_state(int(row["id"]))
        source_class = _news_v2_source_class(row)
        icon = "🟢" if row["active"] else "⚪️"
        last = (st["last_checked_at"] if st else None) or "هنوز توسط V2 بررسی نشده"
        err = (st["last_error"] if st else "") or ""
        feed_label = _social_handle_label(row["feed_url"]) or row["feed_url"]
        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(
            InlineKeyboardButton("⏸ غیرفعال" if row["active"] else "▶️ فعال", callback_data=f"news_src_toggle:{row['id']}"),
            InlineKeyboardButton("🗑 حذف", callback_data=f"news_src_delete:{row['id']}"),
        )
        if row["site_url"] or (not str(row["feed_url"]).startswith("special://")):
            url = row["site_url"] or row["feed_url"]
            if str(url).startswith(("http://", "https://")):
                kb.add(InlineKeyboardButton("🔗 باز کردن سایت", url=url))
        bot.send_message(
            message.chat.id,
            f"{icon} #{row['id']} — {row['title']}\n"
            f"🏷 {_news_v2_source_class_fa(source_class)}\n"
            f"{feed_label}\n"
            f"آخرین بررسی V2: {last}"
            + (f"\n⚠️ {err[:180]}" if err else ""),
            reply_markup=kb,
            link_preview_options=NO_LINK_PREVIEW,
        )

@bot.message_handler(func=lambda m: m.text == "⏱ فاصله News V2")
def news_v2_interval_start(message):
    if message.from_user.id not in ADMINS:
        return
    current = _news_v2_check_interval_minutes()
    msg = bot.send_message(
        message.chat.id,
        f"⏱ فاصله فعلی News V2: هر {current} دقیقه\nعدد جدید رو بفرست (حداقل {NEWS_V2_MIN_CHECK_MINUTES} دقیقه):",
        reply_markup=create_markup_with_back(),
    )
    bot.register_next_step_handler(msg, news_v2_interval_finish)

def news_v2_interval_finish(message):
    uid = message.from_user.id
    if message.text == BACK_MAIN:
        show_news_admin_menu(message.chat.id, uid)
        return
    try:
        minutes = int((message.text or "").strip())
        if minutes < NEWS_V2_MIN_CHECK_MINUTES or minutes > 1440:
            raise ValueError
        set_setting("news_v2_check_minutes", str(minutes))
        bot.send_message(message.chat.id, f"✅ News V2 هر {minutes} دقیقه بررسی می‌شود.")
    except Exception:
        bot.send_message(message.chat.id, f"❌ عدد باید بین {NEWS_V2_MIN_CHECK_MINUTES} تا 1440 باشه.")
    show_news_admin_menu(message.chat.id, uid)

@bot.message_handler(func=lambda m: m.text == "📊 آمار News V2")
def news_v2_stats(message):
    if message.from_user.id not in ADMINS:
        return
    conn = db()
    counts = {}
    for status in ("pending", "approved", "published", "rejected", "duplicate", "seeded"):
        counts[status] = conn.execute("SELECT COUNT(*) AS c FROM news_v2_items WHERE status=?", (status,)).fetchone()["c"]
    today = conn.execute("SELECT COUNT(*) AS c FROM news_v2_items WHERE created_at>=datetime('now','-1 day') AND status NOT IN ('seeded','duplicate','anniversary')").fetchone()["c"]
    conn.close()
    bot.send_message(
        message.chat.id,
        "📊 آمار News V2\n\n"
        f"🕐 منتظر بررسی: {counts['pending']}\n"
        f"✅ تأییدشده: {counts['approved']}\n"
        f"📤 منتشرشده: {counts['published']}\n"
        f"🗑 ردشده: {counts['rejected']}\n"
        f"♻️ تکراری: {counts['duplicate']}\n"
        f"📚 Seed اولیه: {counts['seeded']}\n"
        f"🆕 ۲۴ ساعت اخیر: {today}",
    )
    show_news_admin_menu(message.chat.id, message.from_user.id)

@bot.message_handler(func=lambda m: m.text == "📥 صف بررسی News V2")
def news_v2_queue(message):
    if message.from_user.id not in ADMINS:
        return
    conn = db()
    rows = conn.execute("""
        SELECT id, anime_display, event_type, status, confidence, title
        FROM news_v2_items
        WHERE status IN ('pending','approved')
        ORDER BY id DESC LIMIT 15
    """).fetchall()
    conn.close()
    if not rows:
        bot.send_message(message.chat.id, "✅ صف بررسی News V2 خالیه.")
        return
    lines = ["📥 آخرین خبرهای صف:"]
    for row in rows:
        icon = "✅" if row["status"] == "approved" else "🕐"
        anime = row["anime_display"] or row["title"][:55]
        lines.append(f"{icon} #{row['id']} — {anime} — {_news_v2_event_fa(row['event_type'])} — {row['confidence']}٪")
    lines.append("\nپیش‌نمایش و دکمه‌های تأیید داخل کانال آرشیو قرار دارند.")
    bot.send_message(message.chat.id, "\n".join(lines))

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("nv2_info:"))
def news_v2_info_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    item_id = int(call.data.split(":", 1)[1])
    row = _news_v2_item_by_id(item_id)
    if not row:
        bot.answer_callback_query(call.id, "خبر پیدا نشد.")
        return
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except Exception:
        facts = {}
    lines = [
        f"🧾 News V2 #{item_id}",
        f"📰 منبع: {row['source_title']}",
        f"🏷 سطح منبع: {_news_v2_source_class_fa(row['source_class'])}",
        f"🎯 نوع: {_news_v2_event_fa(row['event_type'])}",
        f"🎬 انیمه: {row['anime_display'] or 'تشخیص داده نشد'}",
        f"📈 اطمینان فنی: {row['confidence']}٪",
        f"📌 وضعیت: {row['status']}",
    ]
    if facts.get("importance") is not None:
        lines.append(f"⭐️ اهمیت: {facts['importance']}/100 (حداقل لازم: {_news_min_importance()})")
        if facts.get("importance_reasons"):
            lines.append("   " + "، ".join(facts["importance_reasons"]))
    if facts.get("agent_importance") is not None:
        lines.append(f"🤖 اهمیت از نظر AI: {facts['agent_importance']}/10")
    if facts.get("image_note"):
        lines.append(f"🖼 عکس: {facts['image_note'][:200]}")
    if facts.get("season"):
        lines.append(f"فصل: {facts['season']}")
    if facts.get("release_raw"):
        lines.append(f"تاریخ خام منبع: {facts['release_raw']}")
    if facts.get("studio"):
        lines.append(f"استودیو: {facts['studio']}")
    if facts.get("certainty") == "unofficial":
        lines.append("⚠️ این مورد به‌صورت غیررسمی نگه داشته شده و متن قطعی تولید نشده.")
    try:
        bot.send_message(call.from_user.id, "\n".join(lines), link_preview_options=NO_LINK_PREVIEW)
        bot.answer_callback_query(call.id, "جزئیات به خصوصی ارسال شد.")
    except Exception:
        bot.answer_callback_query(call.id, "ارسال جزئیات ناموفق بود.", show_alert=True)

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("nv2_approve:"))
def news_v2_approve_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    item_id = int(call.data.split(":", 1)[1])
    row = _news_v2_item_by_id(item_id)
    if not row:
        bot.answer_callback_query(call.id, "خبر پیدا نشد.")
        return
    with db_write_lock:
        conn = db()
        conn.execute("UPDATE news_v2_items SET status='approved' WHERE id=?", (item_id,))
        conn.commit(); conn.close()
    bot.answer_callback_query(call.id, "✅ خبر تأیید شد.")
    try:
        expects = row["event_type"] in ("trailer", "trailer_visual", "character_pv")
        bot.edit_message_reply_markup(
            call.message.chat.id, call.message.message_id,
            reply_markup=_news_v2_archive_markup(item_id, row["url"], "approved", expects, bool(row["archive_secondary_message_id"])),
        )
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("nv2_reject:"))
def news_v2_reject_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    item_id = int(call.data.split(":", 1)[1])
    row = _news_v2_item_by_id(item_id)
    with db_write_lock:
        conn = db(); conn.execute("UPDATE news_v2_items SET status='rejected' WHERE id=?", (item_id,)); conn.commit(); conn.close()
    bot.answer_callback_query(call.id, "🗑 خبر رد شد.")
    if row and row["archive_secondary_message_id"]:
        try: bot.delete_message(call.message.chat.id, int(row["archive_secondary_message_id"]))
        except Exception: pass
    try:
        extra_ids = json.loads((row["facts_json"] if row else "") or "{}").get("archive_extra_ids") or []
    except Exception:
        extra_ids = []
    for mid in extra_ids:
        try: bot.delete_message(call.message.chat.id, int(mid))
        except Exception: pass
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception: pass

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("nv2_edit:"))
def news_v2_edit_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    item_id = int(call.data.split(":", 1)[1])
    row = _news_v2_item_by_id(item_id)
    if not row:
        bot.answer_callback_query(call.id, "خبر پیدا نشد.")
        return
    update_state(call.from_user.id, nv2_edit_item_id=item_id)
    try:
        bot.send_message(call.from_user.id, row["caption"] or "—", parse_mode="HTML")
    except Exception:
        bot.send_message(call.from_user.id, unescape(re.sub(r"<[^>]+>", "", row["caption"] or "")) or "—")
    msg = bot.send_message(
        call.from_user.id,
        "✏️ پیام بالا متن فعلیه. کپی کن، ویرایش کن و بفرست (بولد و نقل‌قول حفظ میشه).",
        reply_markup=create_markup_with_back(),
    )
    bot.register_next_step_handler(msg, news_v2_edit_finish)
    bot.answer_callback_query(call.id, "ویرایش به خصوصی ارسال شد.")

def news_v2_edit_finish(message):
    uid = message.from_user.id
    if message.text == BACK_MAIN:
        show_news_admin_menu(message.chat.id, uid)
        return
    item_id = get_state(uid).get("nv2_edit_item_id")
    row = _news_v2_item_by_id(item_id) if item_id else None
    if not row:
        bot.send_message(message.chat.id, "❌ خبر پیدا نشد.")
        return
    new_text = (getattr(message, "html_text", None) or _html_escape(message.text or "")).strip()
    limit = 1024 if row["archive_media_type"] == "photo" else 4096
    if not new_text or _news_visible_len(new_text) > limit:
        msg = bot.send_message(message.chat.id, f"❌ متن باید بین 1 تا {limit} کاراکتر باشه. دوباره بفرست:")
        bot.register_next_step_handler(msg, news_v2_edit_finish)
        return
    expects = row["event_type"] in ("trailer", "trailer_visual", "character_pv")
    kb = _news_v2_archive_markup(item_id, row["url"], row["status"], expects, bool(row["archive_secondary_message_id"]))
    archive_chat = int(row["archive_chat_id"]) if str(row["archive_chat_id"] or "").lstrip("-").isdigit() else row["archive_chat_id"]
    try:
        if row["archive_media_type"] == "photo":
            bot.edit_message_caption(new_text, chat_id=archive_chat, message_id=row["archive_message_id"], reply_markup=kb, parse_mode="HTML")
        else:
            bot.edit_message_text(new_text, chat_id=archive_chat, message_id=row["archive_message_id"], reply_markup=kb, parse_mode="HTML", link_preview_options=NO_LINK_PREVIEW)
        with db_write_lock:
            try:
                _facts = json.loads(row["facts_json"] or "{}")
            except Exception:
                _facts = {}
            _facts["render"] = {"mode": "manual", "head_html": new_text}
            conn = db(); conn.execute("UPDATE news_v2_items SET caption=?, facts_json=? WHERE id=?", (new_text, json.dumps(_facts, ensure_ascii=False), item_id)); conn.commit(); conn.close()
        bot.send_message(message.chat.id, "✅ متن News V2 ویرایش شد.")
    except Exception as exc:
        bot.send_message(message.chat.id, f"❌ ویرایش انجام نشد: {exc}")
    show_news_admin_menu(message.chat.id, uid)

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("nv2_trailer:"))
def news_v2_trailer_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    item_id = int(call.data.split(":", 1)[1])
    row = _news_v2_item_by_id(item_id)
    if not row:
        bot.answer_callback_query(call.id, "خبر پیدا نشد.")
        return
    update_state(call.from_user.id, nv2_trailer_item_id=item_id)
    msg = bot.send_message(
        call.from_user.id,
        "🎬 فایل تریلر رو همین‌جا بفرست.\nویدیو یا فایل ویدیویی تلگرام قابل قبوله.",
        reply_markup=create_markup_with_back(),
    )
    bot.register_next_step_handler(msg, news_v2_trailer_receive)
    bot.answer_callback_query(call.id, "فایل تریلر را در خصوصی بفرست.")

def news_v2_trailer_receive(message):
    uid = message.from_user.id
    if message.text == BACK_MAIN:
        show_news_admin_menu(message.chat.id, uid)
        return
    item_id = get_state(uid).get("nv2_trailer_item_id")
    row = _news_v2_item_by_id(item_id) if item_id else None
    if not row:
        bot.send_message(message.chat.id, "❌ خبر پیدا نشد.")
        return
    file_id = None
    trailer_kind = ""
    if getattr(message, "video", None):
        file_id = message.video.file_id
        trailer_kind = "video"
    elif getattr(message, "document", None):
        mime = (getattr(message.document, "mime_type", "") or "").lower()
        if mime.startswith("video/"):
            file_id = message.document.file_id
            trailer_kind = "document"
    if not file_id:
        msg = bot.send_message(message.chat.id, "❌ فایل ویدیویی معتبر بفرست:", reply_markup=create_markup_with_back())
        bot.register_next_step_handler(msg, news_v2_trailer_receive)
        return
    _news_v2_attach_trailer(item_id, file_id, trailer_kind)
    _news_v2_update_facts(item_id, trailer_auto="manual")
    _news_v2_clear_trailer_notice(item_id)
    bot.send_message(message.chat.id, "✅ تریلر به پیش‌نمایش خبر اضافه شد؛ موقع انتشار به‌صورت یه پست جدا با کپشن خودش میره.")
    show_news_admin_menu(message.chat.id, uid)


def _news_v2_attach_trailer(item_id: int, video, trailer_kind: str = "video", note: str = "", meta: dict | None = None):
    """ویدیو (file_id یا فایل) رو زیر پیش‌نمایش خبر توی آرشیو می‌فرسته و برای آلبوم انتشار نگه می‌داره."""
    row = _news_v2_item_by_id(item_id)
    archive = _news_v2_archive_chat(row)
    if row["archive_secondary_message_id"]:
        try: bot.delete_message(archive, int(row["archive_secondary_message_id"]))
        except Exception: pass
    sent = _send_video_with_meta(
        archive, video, meta,
        caption=f"🎬 تریلر — {row['anime_display'] or 'خبر'}{note}",
        reply_to_message_id=int(row["archive_message_id"]),
        allow_sending_without_reply=True,
        supports_streaming=True,
    )
    with db_write_lock:
        conn = db(); conn.execute("UPDATE news_v2_items SET archive_secondary_message_id=? WHERE id=?", (int(sent.message_id), item_id)); conn.commit(); conn.close()
    # file_id ویدیوی ارسال‌شده به آرشیو؛ موقع انتشار کنار پوستر توی آلبوم میره
    sent_video = getattr(sent, "video", None)
    _news_v2_update_facts(item_id, trailer_file_id=sent_video.file_id if sent_video else (video if isinstance(video, str) else ""),
                          trailer_kind="video" if sent_video else trailer_kind)
    try:
        kb = _news_v2_archive_markup(item_id, row["url"], row["status"], True, True)
        bot.edit_message_reply_markup(archive, int(row["archive_message_id"]), reply_markup=kb)
    except Exception:
        pass

def _news_v2_anime_names(row) -> set:
    """اسم‌های نرمال‌شده‌ی انیمه‌ی یه خبر (کلید، اسم نمایشی، اسم انگلیسی، اسمی که AI داده)."""
    names = set()
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except Exception:
        facts = {}
    for value in (row["anime_display"], row["anime_eng_name"], facts.get("anime_display"), facts.get("anime_eng_name")):
        n = _news_agent_norm(str(value or ""))
        if len(n) >= 3 and n not in ("این انیمه", "this anime"):
            names.add(n)
    return names


def _news_v2_names_match(a: set, b: set) -> bool:
    for x in a:
        for y in b:
            if x == y:
                return True
            short, long_ = sorted((x, y), key=len)
            if len(short) >= 6 and short in long_:
                return True
            if SequenceMatcher(None, x, y).ratio() >= 0.88:
                return True
    return False


def _news_v2_related_reply(post_channel_id: int, anime_key: str, exclude_item_id: int | None = None):
    """آخرین پستی که همین انیمه توی همین کانال داشته (برای ریپلای کردن خبر جدید روی اون)."""
    conn = db()
    try:
        if anime_key:
            row = conn.execute("""
                SELECT message_id FROM news_v2_publications
                WHERE post_channel_id=? AND anime_key=? AND item_id<>?
                ORDER BY id DESC LIMIT 1
            """, (post_channel_id, anime_key, exclude_item_id or -1)).fetchone()
            if row and row["message_id"]:
                return int(row["message_id"])
        # کلیدها فرق داشتن (مثلاً یکی از تیتر ساخته شده): با اسم خود انیمه مقایسه کن
        if not exclude_item_id:
            return None
        current = conn.execute("SELECT * FROM news_v2_items WHERE id=?", (exclude_item_id,)).fetchone()
        if not current:
            return None
        wanted = _news_v2_anime_names(current)
        if not wanted:
            return None
        rows = conn.execute("""
            SELECT p.message_id, i.* FROM news_v2_publications p
            JOIN news_v2_items i ON i.id = p.item_id
            WHERE p.post_channel_id=? AND p.item_id<>? AND p.created_at >= datetime('now', '-90 day')
            ORDER BY p.id DESC LIMIT 200
        """, (post_channel_id, exclude_item_id)).fetchall()
        for r in rows:
            if _news_v2_names_match(wanted, _news_v2_anime_names(r)):
                return int(r["message_id"])
        return None
    finally:
        conn.close()

# =========================
# دانلود خودکار تریلر (yt-dlp) و آپلود زیر پیش‌نمایش خبر
# =========================
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

TRAILER_MAX_BYTES = 49 * 1024 * 1024       # سقف آپلود بات تلگرام ۵۰ مگه
TRAILER_HEIGHT = 720
TRAILER_LOWER_HEIGHTS = (480, 360, 240)
YOUTUBE_COOKIES_FILE = os.environ.get("YOUTUBE_COOKIES_FILE", "").strip()
_trailer_lock = threading.Lock()   # دانلودها یکی‌یکی


class TrailerTooBig(Exception):
    def __init__(self, size: int, height: int):
        super().__init__(f"{size / 1024 / 1024:.0f}MB")
        self.size = size
        self.height = height


def _ffmpeg_path() -> str:
    import shutil
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # pip install imageio-ffmpeg (ffmpeg آماده برای ویندوز)
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return ""


def _trailer_ydl_opts(height: int) -> dict:
    ffmpeg = _ffmpeg_path()
    # یوتیوب الان بیشتر صدا و تصویر رو جدا میده؛ با ffmpeg ترکیبشون می‌کنیم.
    # بدون ffmpeg فقط فایل‌های یکپارچه (معمولاً ۳۶۰p) قابل دانلودن.
    single = (f"best[ext=mp4][vcodec!=none][acodec!=none][height<={height}]"
              f"/best[vcodec!=none][acodec!=none][height<={height}]")
    merged = (f"bv*[ext=mp4][height<={height}]+ba[ext=m4a]/bv*[height<={height}]+ba")
    fmt = f"{single}/{merged}/b[height<={height}]/b" if ffmpeg else f"{single}/b[vcodec!=none][acodec!=none]/b"
    opts = {
        "format": fmt,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 2,
    }
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg
    if NEWS_PROXY:
        opts["proxy"] = NEWS_PROXY
    if YOUTUBE_COOKIES_FILE and os.path.exists(YOUTUBE_COOKIES_FILE):
        opts["cookiefile"] = YOUTUBE_COOKIES_FILE
    return opts


def _trailer_download(url: str, height: int) -> str:
    """ویدیو رو دانلود می‌کنه و مسیر فایل رو برمی‌گردونه؛ اگه از سقف تلگرام بزرگ‌تر باشه TrailerTooBig."""
    if yt_dlp is None:
        raise RuntimeError("کتابخونه yt-dlp نصب نیست (pip install yt-dlp)")
    opts = _trailer_ydl_opts(height)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    size = int(info.get("filesize") or info.get("filesize_approx") or 0)
    if not size and info.get("requested_formats"):
        # تصویر و صدای جدا: جمع حجم دو تکه
        size = sum(int(f.get("filesize") or f.get("filesize_approx") or 0) for f in info["requested_formats"])
    if size > TRAILER_MAX_BYTES:
        raise TrailerTooBig(size, int(info.get("height") or height))
    tmp_dir = tempfile.mkdtemp(prefix="ariko_trailer_")
    opts["outtmpl"] = os.path.join(tmp_dir, "trailer.%(ext)s")
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = [os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir)]
    if not files:
        raise RuntimeError("فایلی دانلود نشد")
    path = max(files, key=os.path.getsize)
    real = os.path.getsize(path)
    if real > TRAILER_MAX_BYTES:
        _trailer_cleanup(path)
        raise TrailerTooBig(real, int(info.get("height") or height))
    return path


def _trailer_prepare(path: str) -> tuple:
    """تریلر رو برای تلگرام آماده می‌کنه که کاور سیاه و «0:00» نشون نده:
    moov اول فایل (faststart) + مدت/ابعاد + یه فریم از وسط ویدیو به‌عنوان thumbnail و cover.
    خروجی: (مسیر ویدیو، dict برای send_video)."""
    import subprocess
    ffmpeg = _ffmpeg_path()
    meta = {}
    if not ffmpeg:
        return path, meta
    folder = os.path.dirname(path)
    fixed = os.path.join(folder, "trailer_fast.mp4")
    try:
        subprocess.run([ffmpeg, "-y", "-v", "error", "-i", path, "-c", "copy", "-movflags", "+faststart", fixed],
                       capture_output=True, timeout=180, check=True)
        if os.path.getsize(fixed) > 1000:
            path = fixed
    except Exception as exc:
        logger.info("Trailer faststart failed: %s", exc)
    try:
        probe = subprocess.run([ffmpeg, "-hide_banner", "-i", path], capture_output=True, timeout=60)
        err = probe.stderr.decode("utf-8", errors="ignore")
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
        if m:
            meta["duration"] = int(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)))
        m = re.search(r"Video:.*?\b(\d{2,5})x(\d{2,5})\b", err)
        if m:
            meta["width"], meta["height"] = int(m.group(1)), int(m.group(2))
    except Exception as exc:
        logger.info("Trailer probe failed: %s", exc)
    at = max(1, min(8, int(meta.get("duration", 6) * 0.3)))
    thumb = os.path.join(folder, "thumb.jpg")
    cover = os.path.join(folder, "cover.jpg")
    portrait = meta.get("height", 0) > meta.get("width", 1)
    try:
        subprocess.run([ffmpeg, "-y", "-v", "error", "-ss", str(at), "-i", path, "-frames:v", "1", "-q:v", "2", cover],
                       capture_output=True, timeout=60, check=True)
        subprocess.run([ffmpeg, "-y", "-v", "error", "-i", cover, "-vf",
                        "scale=-2:320" if portrait else "scale=320:-2", "-q:v", "5", thumb],
                       capture_output=True, timeout=60, check=True)
        if os.path.exists(thumb) and os.path.getsize(thumb) < 200_000:
            meta["thumb_path"] = thumb
        if os.path.exists(cover):
            meta["cover_path"] = cover
    except Exception as exc:
        logger.info("Trailer thumbnail failed: %s", exc)
    return path, meta


def _send_video_with_meta(chat, video, meta: dict | None = None, **kwargs):
    """send_video با مدت/ابعاد/کاور (پارامترهایی که نسخه‌ی کتابخونه نداره نادیده گرفته میشن)."""
    import inspect
    meta = meta or {}
    params = inspect.signature(bot.send_video).parameters
    files = []
    try:
        for key in ("duration", "width", "height"):
            if meta.get(key) and key in params:
                kwargs[key] = meta[key]
        if meta.get("thumb_path"):
            fh = open(meta["thumb_path"], "rb"); files.append(fh)
            kwargs["thumbnail" if "thumbnail" in params else "thumb"] = fh
        if meta.get("cover_path") and "cover" in params:
            fh = open(meta["cover_path"], "rb"); files.append(fh)
            kwargs["cover"] = fh
        kwargs.setdefault("timeout", 600)          # آپلود ویدیو پشت VPN کنده؛ تایم‌اوت پیش‌فرض کمه
        try:
            try:
                return bot.send_video(chat, video, **kwargs)
            except Exception as exc:
                if not re.search(r"(?i)timed out|timeout|connection aborted|reset", str(exc)):
                    raise
                logger.info("send_video timed out (%s); retrying once", exc)
                for fh in files:
                    fh.seek(0)
                if hasattr(video, "seek"):
                    video.seek(0)
                return bot.send_video(chat, video, **kwargs)
        except Exception as exc:
            if "cover" not in kwargs:
                raise
            logger.info("send_video with cover failed (%s); retrying without cover", exc)
            kwargs.pop("cover", None)
            if hasattr(video, "seek"):
                video.seek(0)
            return bot.send_video(chat, video, **kwargs)
    finally:
        for fh in files:
            try: fh.close()
            except Exception: pass


def _trailer_cleanup(path: str):
    try:
        folder = os.path.dirname(path)
        for f in os.listdir(folder):
            os.remove(os.path.join(folder, f))
        os.rmdir(folder)
    except Exception:
        pass


def _trailer_error_text(exc) -> str:
    text = re.sub(r"\x1b\[[0-9;]*m", "", str(exc))
    if "requested format is not available" in text.lower() or "javascript runtime" in text.lower():
        return ("یوتیوب فرمت قابل دانلودی نداد. معمولاً با این‌ها درست میشه: "
                "pip install -U yt-dlp imageio-ffmpeg و نصب Deno (winget install DenoLand.Deno)")
    if "confirm you" in text.lower() and "bot" in text.lower():
        return "یوتیوب جلوی دانلود خودکار رو گرفت (کوکی یوتیوب لازمه: YOUTUBE_COOKIES_FILE)"
    if re.search(r"WRONG_VERSION_NUMBER|timed out|Connection reset|Remote end closed|Unable to download webpage", text, re.I):
        return "اتصال به سایت ویدیو برقرار نشد (VPN/پروکسی رو چک کن)"
    return text[:200]


_CAST_NEWS_RE = re.compile(
    r"(?i)\b(?:cast|casts|casting|voice\s+actors?|voice\s+actress(?:es)?|voiced?\s+by|seiyuu|"
    r"joins?\s+(?:the\s+)?(?:cast|anime)|staff|director|character\s+designer|theme\s+song\s+artist)\b")

def _news_is_cast_news(title: str, summary: str = "") -> bool:
    """خبر معرفی صداپیشه/عوامل (تیتر درباره‌ی بازیگر/کست باشه، نه تریلر)."""
    t = title or ""
    if re.search(r"(?i)\b(?:trailer|teaser|pv|promo(?:tional)?\s+video)\b", t):
        return False
    return bool(_CAST_NEWS_RE.search(t))


_TRAILER_EVENTS = ("trailer", "trailer_visual", "character_pv")
# \b بین حروف ژاپنی و لاتین مرز حساب نمیشه («第1弾PV»)، برای همین با lookaround
_TRAILER_WORDS_RE = re.compile(r"(?i)(?<![A-Za-z])(?:pv\d*|trailer|teaser|promo(?:tional)? video|cm)(?![A-Za-z])|予告|ティザー")
_TRAILER_JUNK_RE = re.compile(r"(?i)(?<![A-Za-z])(?:reaction|review|explained|recap|amv|edit|fan ?made|episode\s*\d+|ep\.?\s*\d+)(?![A-Za-z])")


def _news_v2_queue_trailer(item_id: int):
    """تریلر خبر رو خودکار آماده می‌کنه: لینک مقاله → دانلود؛ بدون لینک → جستجو در یوتیوب.

    هر حالتی که ممکن نشه (مثلاً yt-dlp نصب نیست) زیر پیش‌نمایش توی آرشیو گفته میشه، نه فقط توی لاگ.
    """
    row = _news_v2_item_by_id(item_id)
    if not row or row["archive_secondary_message_id"] or not row["archive_message_id"]:
        return
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except Exception:
        facts = {}
    if facts.get("trailer_auto"):
        return
    url = (facts.get("trailer_url") or "").strip()
    expects = (row["event_type"] or "") in _TRAILER_EVENTS
    if not expects:
        # غیر از خبرهای تریلر، فقط خبرهای خیلی مهم؛ هیچ‌وقت برای معرفی صداپیشه/عوامل
        if not url or int(facts.get("importance") or 0) < 80 or _news_is_cast_news(row["title"] or "", row["summary"] or ""):
            return
    archive = _news_v2_archive_chat(row)
    if yt_dlp is None:
        _news_v2_update_facts(item_id, trailer_auto="no_ytdlp")
        _news_v2_trailer_notice(item_id, archive,
                                "⚠️ دانلود خودکار تریلر فعال نیست: کتابخونه yt-dlp نصب نیست.\n"
                                "توی CMD بزن: pip install yt-dlp و بعد بات رو ری‌استارت کن.\n"
                                "فعلاً با «🎬 افزودن فایل تریلر» دستی آپلودش کن.")
        return
    _news_v2_update_facts(item_id, trailer_auto="queued")
    if url and _news_safe_url(url):
        target = _news_v2_trailer_job
        args = (item_id, [TRAILER_HEIGHT])
    else:
        target = _news_v2_trailer_search_job
        args = (item_id,)
    threading.Thread(target=target, args=args, daemon=True, name=f"trailer-{item_id}").start()


TRAILER_MAX_AGE_DAYS = 21


def _news_published_ts(row) -> float:
    """زمان انتشار خبر (اگه نبود: الان)."""
    raw = (row["published_at"] or "").strip()
    for parse in (lambda v: parsedate_to_datetime(v).timestamp(),
                  lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()):
        try:
            return float(parse(raw))
        except Exception:
            continue
    return time.time()


def _trailer_upload_ts(url: str) -> float:
    """زمان آپلود ویدیوی یوتیوب (0 اگه معلوم نشد)."""
    try:
        opts = _trailer_ydl_opts(TRAILER_HEIGHT)
        opts.update({"skip_download": True})
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if info.get("timestamp"):
            return float(info["timestamp"])
        d = str(info.get("upload_date") or "")
        if len(d) == 8:
            return datetime.strptime(d, "%Y%m%d").timestamp()
    except Exception as exc:
        logger.info("Trailer upload date unknown %s: %s", url, exc)
    return 0.0


def _trailer_search(query: str, by_date: bool = False, count: int = 5) -> list:
    """چند نتیجه‌ی اول جستجوی یوتیوب (بدون دانلود). by_date: جدیدترین‌ها اول."""
    opts = _trailer_ydl_opts(TRAILER_HEIGHT)
    opts.update({"extract_flat": "in_playlist", "skip_download": True})
    info = None
    if by_date:
        # yt-dlp جدید «ytsearchdate» رو برداشته → صفحه‌ی جستجوی یوتیوب با مرتب‌سازی تاریخ آپلود
        for target in (f"ytsearchdate{count}:{query}",
                       "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query) + "&sp=CAI%3D"):
            try:
                o = dict(opts, playlistend=count)
                with yt_dlp.YoutubeDL(o) as ydl:
                    info = ydl.extract_info(target, download=False)
                if (info or {}).get("entries"):
                    break
            except Exception as exc:
                logger.info("Trailer search by date failed (%s): %s", target[:40], exc)
                info = None
    if not (info or {}).get("entries"):
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{count}:{query}", download=False)
    out = []
    for e in ((info or {}).get("entries") or [])[:count]:
        vid = e.get("id") or ""
        if not vid:
            continue
        out.append({
            "url": e.get("url") if str(e.get("url") or "").startswith("http") else f"https://www.youtube.com/watch?v={vid}",
            "title": str(e.get("title") or ""),
            "duration": int(e.get("duration") or 0),
            "channel": str(e.get("channel") or e.get("uploader") or ""),
        })
    return out


def _trailer_name_match(names: list, title: str) -> bool:
    tn = _news_agent_norm(title)
    for n in names:
        if not n:
            continue
        if re.search(r"[A-Za-z]", n):
            w = _news_agent_norm(n)
            if w and w in tn:
                return True
        elif len(n) >= 2 and n in title:
            return True
    return False


def _trailer_pick(anime, results: list):
    """بهترین نتیجه و اینکه «مطمئن» هست یا نه (اسم کامل انیمه + کلمه تریلر/PV + زیر ۴ دقیقه).
    anime می‌تونه یه اسم یا لیست اسم‌ها باشه (انگلیسی/رومانجی/ژاپنی)."""
    names = [anime] if isinstance(anime, str) else [n for n in anime if n]
    wants = [_news_agent_norm(n) for n in names if _news_agent_norm(n)]
    natives = [n for n in names if n and not re.search(r"[A-Za-z]", n) and len(n) >= 2]
    best, sure = None, False
    for r in results:
        if _TRAILER_JUNK_RE.search(r["title"]):
            continue
        title_norm = _news_agent_norm(r["title"])
        has_name = any(w in title_norm for w in wants) or any(n in r["title"] for n in natives)
        has_word = bool(_TRAILER_WORDS_RE.search(r["title"]))
        short = 0 < r["duration"] <= 240
        if has_name and has_word and short:
            return r, True
        if best is None and (has_name or has_word) and (r["duration"] == 0 or r["duration"] <= 600):
            best = r
    return best, sure


def _news_v2_trailer_search_job(item_id: int):
    row = _news_v2_item_by_id(item_id)
    if not row:
        return
    facts = json.loads(row["facts_json"] or "{}")
    anime = facts.get("anime_eng_name") or row["anime_display"] or facts.get("anime_display") or ""
    archive = _news_v2_archive_chat(row)
    if not anime or anime == "این انیمه":
        _news_v2_update_facts(item_id, trailer_auto="no_link")
        _news_v2_trailer_notice(item_id, archive, "ℹ️ لینک تریلر توی مقاله نبود؛ با «🎬 افزودن فایل تریلر» دستی آپلودش کن.")
        return
    meta = _news_anilist_lookup(anime) or {}
    names = [anime, meta.get("title_en"), meta.get("title_romaji"), meta.get("title_native")]
    names = [n for i, n in enumerate(names) if n and n not in names[:i]]
    queries = []
    if meta.get("title_native"):
        queries.append(f"{meta['title_native']} PV")          # کانال‌های رسمی ژاپنی با اسم ژاپنی آپلود می‌کنن
    queries.append(f"{meta.get('title_romaji') or anime} PV")
    queries.append(f"{anime} trailer")
    results, seen_urls, last_exc = [], set(), None
    for q in queries:
        try:
            for r in _trailer_search(q, by_date=True, count=8):          # جدیدترین‌ها اول
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    results.append(r)
        except Exception as exc:
            last_exc = exc
    if not results and last_exc is not None:
        _news_v2_update_facts(item_id, trailer_auto="failed")
        _news_v2_trailer_notice(item_id, archive,
                                f"ℹ️ لینک تریلر توی مقاله نبود و جستجوی یوتیوب هم نشد: {_trailer_error_text(last_exc)}\n"
                                "با «🎬 افزودن فایل تریلر» دستی آپلودش کن.")
        return
    # فقط تریلرهای تازه (نزدیک تاریخ خبر)؛ تریلر چند ماه پیش = اشتباه
    news_ts = _news_published_ts(row)
    fresh, old_seen = [], None
    for r in results:
        if _TRAILER_JUNK_RE.search(r["title"]):
            continue
        if not _trailer_name_match(names, r["title"]):
            continue                                            # اسم انیمه توی عنوان ویدیو نیست
        up = _trailer_upload_ts(r["url"])
        if up and not (news_ts - TRAILER_MAX_AGE_DAYS * 86400 <= up <= news_ts + 3 * 86400):
            old_seen = old_seen or r
            continue
        r = dict(r, date_known=bool(up))
        fresh.append(r)
        if len(fresh) >= 3:
            break
    pick, sure = _trailer_pick(names, fresh)
    if pick and not pick.get("date_known"):
        sure = False                         # تاریخ آپلودش معلوم نشد → خودکار آپلود نمیشه، از ادمین می‌پرسه
    if not pick:
        _news_v2_update_facts(item_id, trailer_auto="no_link")
        extra = (f"\n(فقط تریلرهای قدیمی‌تر پیدا شد، مثل «{old_seen['title'][:80]}»؛ فرستاده نشد)" if old_seen else "")
        _news_v2_trailer_notice(item_id, archive,
                                "ℹ️ تریلر تازه‌ای برای این خبر توی یوتیوب پیدا نشد؛ با «🎬 افزودن فایل تریلر» دستی آپلودش کن." + extra)
        return
    _news_v2_update_facts(item_id, trailer_url=pick["url"], trailer_from_search=True)
    if sure:
        logger.info("Trailer found by search item=%s: %s", item_id, pick["title"])
        _news_v2_trailer_job(item_id, [TRAILER_HEIGHT])
        return
    _news_v2_update_facts(item_id, trailer_auto="needs_confirm")
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📥 آره، همین آپلود بشه", callback_data=f"nv2_trdl:{item_id}"))
    _news_v2_trailer_notice(item_id, archive,
                            "🔎 لینک تریلر توی مقاله نبود؛ توی یوتیوب اینو پیدا کردم ولی مطمئن نیستم خودشه:\n"
                            f"«{pick['title'][:120]}» — {pick['channel'][:40]}\n{pick['url']}\n\n"
                            "اگه درسته دکمه رو بزن، وگرنه با «🎬 افزودن فایل تریلر» دستی آپلود کن.", kb)


def _news_v2_trailer_job(item_id: int, heights: list, notify_chat=None):
    """کیفیت‌ها رو به ترتیب امتحان می‌کنه؛ اولین فایلی که زیر ۵۰ مگ باشه آپلود میشه."""
    row = _news_v2_item_by_id(item_id)
    if not row or not row["archive_message_id"]:
        return
    facts = json.loads(row["facts_json"] or "{}")
    url = facts.get("trailer_url") or ""
    archive = _news_v2_archive_chat(row)
    too_big = None
    with _trailer_lock:
        for height in heights:
            path = ""
            try:
                path = _trailer_download(url, height)
                send_path, vmeta = _trailer_prepare(path)
                with open(send_path, "rb") as fh:
                    note = "" if height == TRAILER_HEIGHT else f" ({height}p)"
                    if facts.get("trailer_from_search"):
                        note += "\n🔎 از جستجوی یوتیوب پیدا شد؛ اگه اشتباهه با «♻️ تعویض فایل تریلر» عوضش کن."
                    _news_v2_attach_trailer(item_id, fh, "video", note=note, meta=vmeta)
                _news_v2_update_facts(item_id, trailer_auto="done")
                _news_v2_clear_trailer_notice(item_id)
                logger.info("Trailer uploaded item=%s at %sp", item_id, height)
                return
            except TrailerTooBig as exc:
                too_big = exc
                continue
            except Exception as exc:
                logger.warning("Trailer download failed item=%s: %s", item_id, exc)
                _news_v2_update_facts(item_id, trailer_auto="failed")
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("🔁 دوباره امتحان کن", callback_data=f"nv2_trdl:{item_id}"))
                _news_v2_trailer_notice(item_id, archive,
                                        f"⚠️ دانلود خودکار تریلر نشد: {_trailer_error_text(exc)}\n"
                                        "می‌تونی با «🎬 افزودن فایل تریلر» دستی آپلودش کنی.", kb)
                return
            finally:
                if path:
                    _trailer_cleanup(path)
    # هیچ کیفیتی زیر ۵۰ مگ نشد
    _news_v2_update_facts(item_id, trailer_auto="too_big")
    kb = InlineKeyboardMarkup()
    lower = [h for h in TRAILER_LOWER_HEIGHTS if h < min(heights)]
    if lower:
        kb.add(InlineKeyboardButton("📥 بات با کیفیت پایین‌تر آپلود کنه", callback_data=f"nv2_trlow:{item_id}"))
        msg = (f"⚠️ حجم تریلر ({too_big} در {too_big.height}p) از سقف ۵۰ مگابایت تلگرام بیشتره.\n"
               "یا با «🎬 افزودن فایل تریلر» خودت آپلودش کن، یا بذار بات کیفیت پایین‌تر رو بفرسته.")
    else:
        msg = "⚠️ تریلر حتی با کیفیت پایین هم زیر ۵۰ مگابایت نشد؛ با «🎬 افزودن فایل تریلر» خودت آپلودش کن."
    _news_v2_trailer_notice(item_id, archive, msg, kb if lower else None)


def _news_v2_trailer_notice(item_id: int, archive, text: str, kb=None):
    """پیام وضعیت تریلر زیر پیش‌نمایش (قبلی پاک میشه)."""
    _news_v2_clear_trailer_notice(item_id)
    row = _news_v2_item_by_id(item_id)
    try:
        sent = bot.send_message(archive, text, reply_markup=kb, reply_to_message_id=int(row["archive_message_id"]),
                                allow_sending_without_reply=True)
        _news_v2_update_facts(item_id, trailer_notice_id=int(sent.message_id))
    except Exception:
        logger.exception("Trailer notice failed item=%s", item_id)


def _news_v2_clear_trailer_notice(item_id: int):
    row = _news_v2_item_by_id(item_id)
    try:
        mid = json.loads(row["facts_json"] or "{}").get("trailer_notice_id")
    except Exception:
        mid = None
    if mid:
        try:
            bot.delete_message(_news_v2_archive_chat(row), int(mid))
        except Exception:
            pass
        _news_v2_update_facts(item_id, trailer_notice_id=None)


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith(("nv2_trlow:", "nv2_trdl:")))
def news_v2_trailer_download_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    action, item_s = call.data.split(":", 1)
    item_id = int(item_s)
    if yt_dlp is None:
        bot.answer_callback_query(call.id, "yt-dlp نصب نیست: pip install yt-dlp", show_alert=True)
        return
    heights = list(TRAILER_LOWER_HEIGHTS) if action == "nv2_trlow" else [TRAILER_HEIGHT]
    _news_v2_update_facts(item_id, trailer_auto="queued")
    try:
        bot.edit_message_text("⏳ در حال دانلود و آپلود تریلر…", call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    bot.answer_callback_query(call.id, "⏳ شروع شد")
    threading.Thread(target=_news_v2_trailer_job, args=(item_id, heights), daemon=True,
                     name=f"trailer-{item_id}").start()


def _news_v2_split_captions(row) -> tuple:
    """برای خبری که هم تریلر داره هم چند عکس: (کپشن پست تریلر, کپشن پست عکس‌ها).

    هر دو کپشن کامل‌ان (تیتر + خلاصه داستان + تاریخ + استودیو + امضا)؛ فقط تیترشون فرق داره.
    """
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except Exception:
        facts = {}
    render = dict(facts.get("render") or {})
    anime = (row["anime_display"] or facts.get("anime_display") or "").strip()
    blob = f"{row['title'] or ''} {(row['summary'] or '')[:400]}".lower()
    video_word = "تیزر" if re.search(r"\bteaser\b", blob) and not re.search(r"\btrailer\b", blob) else "تریلر"
    image_word = "پوسترهای" if re.search(r"\b(?:posters|visuals|key visuals)\b", blob) else \
        ("تصاویر" if re.search(r"\b(?:images|stills|screenshots|preview)\b", blob) else "پوستر")
    name = f"«{anime}»" if anime and anime != "این انیمه" else "این انیمه"
    trailer_head = render.get("headline_trailer") or f"{video_word} جدید انیمه‌ی {name} منتشر شد."
    images_head = render.get("headline_images") or f"{image_word} جدید انیمه‌ی {name} منتشر شد."
    base = {
        "mode": "agent",
        "emoji": render.get("emoji") or "🎬",
        "details": [],
        "date_fa": render.get("date_fa") or facts.get("release_fa") or "",
        "studio": render.get("studio") or facts.get("studio") or "",
        "unofficial": bool(render.get("unofficial")),
    }
    synopsis, _src = _news_get_synopsis(row["anime_key"] or "")
    trailer_caption = _news_render_caption(dict(base, headline=trailer_head, details=render.get("details") or []), synopsis)
    images_caption = _news_render_caption(dict(base, headline=images_head, details=render.get("details") or []), synopsis)
    return trailer_caption, images_caption


def _news_v2_publish_album(row, target, reply_to):
    """چیدمان انتشار خبرهای چندرسانه‌ای:
    - تریلر (با یا بدون عکس) → پست تریلر جدا با کپشن کامل؛ عکس یا آلبوم عکس‌ها (با کپشن خودش) ریپلای روی اون
    - چند عکس بدون تریلر → آلبوم عکس‌ها

    خروجی: (message_id اولین پیام یا None اگه آلبوم لازم نبود, تریلر منتشر شد؟)
    """
    from telebot.types import InputMediaPhoto
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except Exception:
        facts = {}
    main_photo = facts.get("archive_photo_file_id") if row["archive_media_type"] == "photo" else ""
    photos = ([main_photo] if main_photo else []) + list(facts.get("extra_file_ids") or [])
    video = facts.get("trailer_file_id") if facts.get("trailer_kind") == "video" and row["archive_secondary_message_id"] else ""
    caption = (row["caption"] or "")[:1024]
    kwargs = {}
    if reply_to:
        kwargs.update(reply_to_message_id=reply_to, allow_sending_without_reply=True)
    if not video and len(photos) < 2:
        return None, False

    if not video:
        media = [InputMediaPhoto(fid, caption=caption if i == 0 else None, parse_mode="HTML" if i == 0 else None)
                 for i, fid in enumerate(photos[:10])]
        msgs = bot.send_media_group(target, media, **kwargs)
        return int(msgs[0].message_id), False

    # تریلر همیشه یه پست جدای خودش با کپشن کامل (هیچ‌وقت با عکس‌ها توی یه آلبوم نمیره)؛
    # عکس‌ها (یکی یا چندتا) یه پست جدا با کپشن خودشون، ریپلای روی پست تریلر
    trailer_caption, images_caption = _news_v2_split_captions(row)
    trailer_msg = bot.send_video(target, video, caption=trailer_caption[:1024], parse_mode="HTML",
                                 supports_streaming=True, **kwargs)
    trailer_id = int(trailer_msg.message_id)
    if len(photos) == 1:
        bot.send_photo(target, photos[0], caption=images_caption[:1024], parse_mode="HTML",
                       reply_to_message_id=trailer_id, allow_sending_without_reply=True)
    elif photos:
        media = [InputMediaPhoto(fid, caption=images_caption[:1024] if i == 0 else None,
                                 parse_mode="HTML" if i == 0 else None)
                 for i, fid in enumerate(photos[:10])]
        bot.send_media_group(target, media, reply_to_message_id=trailer_id, allow_sending_without_reply=True)
    return trailer_id, True

def _news_v2_publish_item(item_id: int, post_channel_id: int):
    row = _news_v2_item_by_id(item_id)
    if not row or not row["archive_message_id"]:
        raise ValueError("پیش‌نمایش خبر پیدا نشد.")
    if row["status"] not in ("approved", "published"):
        raise ValueError("اول خبر را تأیید کن، بعد منتشرش کن.")
    conn = db(); ch = conn.execute("SELECT id, channel_id, title FROM post_channels WHERE id=?", (post_channel_id,)).fetchone(); conn.close()
    if not ch:
        raise ValueError("کانال مقصد پیدا نشد.")
    source_chat = int(row["archive_chat_id"]) if str(row["archive_chat_id"] or "").lstrip("-").isdigit() else row["archive_chat_id"]
    target = normalize_channel_id_value(ch["channel_id"])
    reply_to = _news_v2_related_reply(post_channel_id, row["anime_key"] or "", exclude_item_id=item_id)
    kwargs = {"reply_markup": None}
    if reply_to:
        kwargs.update(reply_to_message_id=reply_to, allow_sending_without_reply=True)
    message_id = None
    trailer_in_album = False
    try:
        message_id, trailer_in_album = _news_v2_publish_album(row, target, reply_to)
    except Exception as exc:
        logger.warning("Album publish failed item=%s, falling back to copy: %s", item_id, exc)
    if message_id is None:
        # کپشن از دیتابیس (نه از پیام آرشیو) تا یادداشت‌های مخصوص آرشیو منتشر نشن
        clean = (row["caption"] or "").strip()
        if row["archive_media_type"] == "photo":
            result = bot.copy_message(target, source_chat, int(row["archive_message_id"]),
                                      caption=clean[:1024], parse_mode="HTML", **kwargs)
        else:
            send_kwargs = {k: v for k, v in kwargs.items() if k != "reply_markup"}
            result = bot.send_message(target, clean[:4096], parse_mode="HTML",
                                      link_preview_options=NO_LINK_PREVIEW, **send_kwargs)
        message_id = getattr(result, "message_id", None)
        if message_id is None:
            message_id = int(result)
    if row["archive_secondary_message_id"] and not trailer_in_album:
        bot.copy_message(
            target, source_chat, int(row["archive_secondary_message_id"]), reply_markup=None,
            reply_to_message_id=int(message_id), allow_sending_without_reply=True,
        )
    with db_write_lock:
        conn = db()
        conn.execute("""
            INSERT INTO news_v2_publications(item_id, post_channel_id, channel_id, message_id, anime_key, event_type)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(item_id, post_channel_id) DO UPDATE SET
                channel_id=excluded.channel_id, message_id=excluded.message_id,
                anime_key=excluded.anime_key, event_type=excluded.event_type,
                created_at=CURRENT_TIMESTAMP
        """, (item_id, post_channel_id, str(target), int(message_id), row["anime_key"] or f"item-{item_id}", row["event_type"]))
        conn.execute("UPDATE news_v2_items SET status='published' WHERE id=?", (item_id,))
        conn.commit(); conn.close()
    return ch["title"]

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("nv2_publish:"))
def news_v2_publish_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    item_id = int(call.data.split(":", 1)[1])
    row = _news_v2_item_by_id(item_id)
    if not row:
        bot.answer_callback_query(call.id, "خبر پیدا نشد.", show_alert=True)
        return
    if row["status"] not in ("approved", "published"):
        bot.answer_callback_query(call.id, "اول ✅ تأیید خبر رو بزن.", show_alert=True)
        return
    channels = _news_post_channels_with_ids()
    if not channels:
        bot.answer_callback_query(call.id, "اول کانال مقصد اضافه کن.", show_alert=True)
        return
    if len(channels) == 1:
        try:
            title = _news_v2_publish_item(item_id, int(channels[0]["id"]))
            bot.answer_callback_query(call.id, f"✅ در {title} منتشر شد.", show_alert=True)
        except Exception as exc:
            bot.answer_callback_query(call.id, f"خطا: {exc}", show_alert=True)
        return
    kb = InlineKeyboardMarkup()
    for ch in channels:
        kb.add(InlineKeyboardButton(f"📤 {ch['title']}", callback_data=f"nv2_pub:{item_id}:{ch['id']}"))
    bot.send_message(call.from_user.id, "📤 خبر در کدام کانال منتشر بشه؟", reply_markup=kb)
    bot.answer_callback_query(call.id, "لیست کانال‌ها به خصوصی ارسال شد.")

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("nv2_pub:"))
def news_v2_publish_target_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    try:
        _p, item_s, ch_s = call.data.split(":", 2)
        title = _news_v2_publish_item(int(item_s), int(ch_s))
        bot.answer_callback_query(call.id, f"✅ در {title} منتشر شد.", show_alert=True)
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception: pass
    except Exception as exc:
        bot.answer_callback_query(call.id, f"خطا: {exc}", show_alert=True)

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("nv2_ai:"))
def news_agent_regen_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    item_id = int(call.data.split(":", 1)[1])
    ok, why = _news_agent_can_call()
    if not ok:
        bot.answer_callback_query(call.id, f"⚠️ {why}", show_alert=True)
        return
    if item_id in _news_manual_retry_items:
        bot.answer_callback_query(call.id, "⏳ این خبر همین الان توی صف تلاش دوباره‌ست؛ نتیجه رو خبر میدم.", show_alert=True)
        return
    bot.answer_callback_query(call.id, "🤖 در حال بازنویسی…")
    threading.Thread(target=_news_agent_manual_rewrite, args=(item_id, call.from_user.id),
                     daemon=True, name=f"news-agent-{item_id}").start()


# فاصله‌ی تلاش‌های دوباره برای دکمه‌ی بازنویسی وقتی AI موقتاً در دسترس نیست (ثانیه)
NEWS_MANUAL_RETRY_DELAYS = (90, 180, 300, 600)
_news_manual_retry_items = set()


def _news_agent_manual_rewrite(item_id: int, admin_id: int):
    """بازنویسی با دکمه؛ اگه Gemini شلوغ بود خودش چند بار دیگه امتحان می‌کنه و نتیجه رو خبر میده."""
    success, info, kind = _news_agent_apply_ex(item_id)
    if not success and kind == "transient":
        _news_manual_retry_items.add(item_id)
        try:
            bot.send_message(admin_id, f"⏳ بازنویسی خبر #{item_id} الان نشد: {info}\n"
                                       "تا حدود ۲۰ دقیقه‌ی دیگه خودم چند بار دوباره امتحان می‌کنم و نتیجه رو همین‌جا میگم. "
                                       "لازم نیست دوباره دکمه رو بزنی.")
        except Exception:
            pass
        try:
            for delay in NEWS_MANUAL_RETRY_DELAYS:
                time.sleep(delay)
                success, info, kind = _news_agent_apply_ex(item_id)
                if success or kind != "transient":
                    break
        finally:
            _news_manual_retry_items.discard(item_id)
    if not success:
        extra = ""
        if kind == "transient":
            extra = ("\n\n💡 اگه این زیاد پیش میاد، از «🔑 تنظیم سرویس AI» یه سرویس دوم (مثلاً AvalAI) "
                     "یا OPENROUTER_API_KEY تنظیم کن تا وقتی Gemini شلوغه از اون استفاده بشه.")
        try:
            bot.send_message(admin_id, f"❌ بازنویسی خبر #{item_id} انجام نشد:\n{info}\n\nمتن قبلی دست نخورد.{extra}")
        except Exception:
            pass
        return
    refreshed = _news_v2_refresh_archive(item_id)
    where = ("پیام کانال آرشیو آپدیت شد." if refreshed
             else "⚠️ آپدیت پیام کانال آرشیو ممکن نشد (لاگ رو ببین)؛ متن جدید ذخیره شده و موقع انتشار همین استفاده میشه.")
    row = _news_v2_item_by_id(item_id)
    caption = (row["caption"] if row else "") or ""
    # متن جدید رو خود ادمین هم ببینه
    try:
        bot.send_message(admin_id, f"✅ خبر #{item_id} با AI بازنویسی شد ({info}).\n{where}\n\n👇 متن جدید:")
        bot.send_message(admin_id, caption[:4096], parse_mode="HTML", link_preview_options=NO_LINK_PREVIEW)
    except Exception:
        try:
            bot.send_message(admin_id, unescape(re.sub(r"<[^>]+>", "", caption))[:4096])
        except Exception:
            pass

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("nv2_syn:"))
def news_agent_synopsis_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    item_id = int(call.data.split(":", 1)[1])
    row = _news_v2_item_by_id(item_id)
    if not row:
        bot.answer_callback_query(call.id, "خبر پیدا نشد.")
        return
    current, src = _news_get_synopsis(row["anime_key"] or "")
    update_state(call.from_user.id, nv2_syn_item_id=item_id)
    src_fa = {"admin": "نوشته ادمین", "agent": "ترجمه AI"}.get(src, "")
    text = (
        f"📝 خلاصه داستان «{row['anime_display'] or 'این انیمه'}» رو بفرست.\n"
        "این خلاصه برای همه خبرهای بعدی همین انیمه هم خودکار استفاده میشه.\n"
        "برای حذف خلاصه فقط یه - بفرست.\n\n"
        + (f"خلاصه فعلی ({src_fa}):\n{current}" if current else "فعلاً خلاصه‌ای ثبت نشده.")
    )
    msg = bot.send_message(call.from_user.id, text, reply_markup=create_markup_with_back())
    bot.register_next_step_handler(msg, news_agent_synopsis_finish)
    bot.answer_callback_query(call.id, "به خصوصی ارسال شد.")

def news_agent_synopsis_finish(message):
    uid = message.from_user.id
    if message.text == BACK_MAIN:
        show_news_admin_menu(message.chat.id, uid)
        return
    item_id = get_state(uid).get("nv2_syn_item_id")
    row = _news_v2_item_by_id(item_id) if item_id else None
    if not row:
        bot.send_message(message.chat.id, "❌ خبر پیدا نشد.")
        return
    text = re.sub(r"\s+", " ", (message.text or "")).strip()
    if text != "-" and (len(text) < 20 or len(text) > 600):
        msg = bot.send_message(message.chat.id, "❌ خلاصه باید بین ۲۰ تا ۶۰۰ کاراکتر باشه. دوباره بفرست:")
        bot.register_next_step_handler(msg, news_agent_synopsis_finish)
        return
    _news_set_synopsis(row["anime_key"] or "", "" if text == "-" else text, "admin")
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except Exception:
        facts = {}
    _news_item_render_and_save(int(item_id), facts)
    _news_v2_refresh_archive(int(item_id))
    bot.send_message(message.chat.id, "✅ خلاصه داستان ذخیره شد و پیش‌نمایش آپدیت شد.")
    show_news_admin_menu(message.chat.id, uid)

NEWS_IMPORTANCE_LEVELS = [
    (0, "همه خبرها"),
    (40, "معمولی به بالا"),
    (55, "فقط خبرهای مهم (پیشنهادی)"),
    (75, "فقط خبرهای خیلی مهم"),
]

def _news_importance_menu_markup():
    current = _news_min_importance()
    kb = InlineKeyboardMarkup()
    for value, label in NEWS_IMPORTANCE_LEVELS:
        mark = "✅ " if value == current else ""
        kb.add(InlineKeyboardButton(f"{mark}{label} ({value}+)", callback_data=f"news_imp:{value}"))
    return kb

@bot.message_handler(func=lambda m: m.text == "⭐️ فیلتر اهمیت خبر")
def news_importance_menu(message):
    if message.from_user.id not in ADMINS:
        return
    bot.send_message(
        message.chat.id,
        "⭐️ هر خبر یه امتیاز اهمیت از ۰ تا ۱۰۰ می‌گیره (نوع خبر، محبوبیت انیمه، کلیدواژه‌ها و نظر AI).\n"
        "خبرهای زیر این حد وارد کانال آرشیو نمیشن.\n"
        "امتیاز هر خبر رو توی «ℹ️ جزئیات تشخیص» می‌بینی.",
        reply_markup=_news_importance_menu_markup(),
    )

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("news_imp:"))
def news_importance_set_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    value = int(call.data.split(":", 1)[1])
    set_setting("news_min_importance", str(value))
    bot.answer_callback_query(call.id, "✅ ذخیره شد.")
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=_news_importance_menu_markup())
    except Exception:
        pass

@bot.message_handler(func=lambda m: m.text == "💾 بکاپ دیتابیس")
def news_db_backup_handler(message):
    if message.from_user.id not in ADMINS:
        return
    try:
        path = _news_backup_zip(news_db_backup("manual"))
        bot.send_message(message.chat.id, f"⏳ دارم بکاپ رو می‌فرستم ({os.path.getsize(path) / 1024 ** 2:.1f} مگ)…")
        with open(path, "rb") as fh:
            bot.send_document(
                message.chat.id, fh, timeout=900,
                caption=(
                    "💾 بکاپ کامل دیتابیس بات خبر\n"
                    f"📁 پوشه دائمی دیتابیس: {DATA_DIR}\n"
                    f"🗂 بکاپ خودکار روزانه: {BACKUP_DIR} (آخرین {NEWS_BACKUP_KEEP} تا)\n\n"
                    "♻️ برای بازیابی: همین فایل رو با کپشن /restore برای بات بفرست."
                ),
            )
    except Exception as exc:
        bot.send_message(message.chat.id, f"❌ بکاپ ناموفق بود: {exc}\n\n"
                                          f"فایل دیتابیس خودش اینجاست (می‌تونی دستی برداری):\n{DB_PATH}")
    finally:
        for f in os.listdir(BACKUP_DIR) if os.path.isdir(BACKUP_DIR) else []:
            if f.endswith(".db.zip"):                       # زیپ فقط برای فرستادن بود
                try:
                    os.remove(os.path.join(BACKUP_DIR, f))
                except Exception:
                    pass


@bot.message_handler(content_types=["document"],
                     func=lambda m: (m.caption or "").strip().lower().startswith(("/restore", "بازیابی")))
def news_db_restore_handler(message):
    if message.from_user.id not in ADMINS:
        return
    doc = message.document
    if not doc or not (doc.file_name or "").lower().endswith((".db", ".sqlite", ".sqlite3", ".zip")):
        bot.send_message(message.chat.id, "❌ فایل باید دیتابیس (.db) یا بکاپ زیپ‌شده (.zip) باشه.")
        return
    if (doc.file_size or 0) > 20 * 1024 ** 2:
        bot.send_message(message.chat.id, "❌ ربات‌ها فقط فایل تا ۲۰ مگ رو می‌تونن از تلگرام بگیرن. "
                                          f"فایل دیتابیس رو مستقیم بذار اینجا (با فایل منیجر هاست):\n{DB_PATH}\n"
                                          "(اول بات رو خاموش کن، بعد فایل رو جایگزین کن)")
        return
    bot.send_message(message.chat.id, "⏳ در حال بازیابی دیتابیس…")
    tmp_path = ""
    try:
        data = bot.download_file(bot.get_file(doc.file_id).file_path)
        if (doc.file_name or "").lower().endswith(".zip"):         # بکاپ زیپ‌شده: اولین فایل .db داخلش
            import zipfile
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                inner = next((n for n in zf.namelist() if n.lower().endswith(".db")), None)
                if not inner:
                    raise RuntimeError("توی زیپ فایل .db نبود")
                data = zf.read(inner)
        fd, tmp_path = tempfile.mkstemp(suffix=".db")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        before = news_db_restore_from(tmp_path)
        init_db()
        _news_v2_init_db()
        _news_agent_init_db()
        bot.send_message(message.chat.id, "✅ دیتابیس بازیابی شد.\n"
                                          f"نسخه قبلی هم برای احتیاط ذخیره شد:\n{before}")
    except Exception as exc:
        bot.send_message(message.chat.id, f"❌ بازیابی انجام نشد (دیتابیس فعلی دست نخورد): {exc}")
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

@bot.message_handler(commands=["xtest"])
def news_x_test(message):
    """/xtest SugoiLITE — تست خوندن یه اکانت X و گزارش روش و خطاها."""
    if message.from_user.id not in ADMINS:
        return
    parts = (message.text or "").split()
    handle = parts[1].lstrip("@") if len(parts) > 1 else "SugoiLITE"
    login = ("✅ X_AUTH_TOKEN و X_CT0 تنظیم شدن" if _x_gql_ready()
             else "⚠️ کوکی لاگین کامل نیست (X_AUTH_TOKEN و X_CT0 هر دو لازمن)")
    bot.send_message(message.chat.id, f"⏳ تست خوندن @{handle}…\n{login}")
    try:
        entries = _x_leaker_collect(handle)
        first = entries[0] if entries else {}
        bot.send_message(message.chat.id,
                         f"✅ {len(entries)} پست خونده شد.\n\nآخرین پست:\n{(first.get('summary') or '')[:400]}\n{first.get('url', '')}",
                         link_preview_options=NO_LINK_PREVIEW)
    except Exception as exc:
        bot.send_message(message.chat.id, f"❌ خوندن ممکن نشد:\n{str(exc)[:900]}")

_NEWS_STATUS_FA = {
    "pending": "📨 توی آرشیو فرستاده شده (منتظر تأیید)",
    "approved": "✅ تأیید شده",
    "published": "📤 منتشر شده",
    "rejected": "🗑 خودت ردش کردی",
    "low": "⛔ به‌خاطر امتیاز اهمیت پایین فرستاده نشد",
    "duplicate": "♻️ تکراری تشخیص داده شد (خبر مشابه قبلاً اومده بود)",
    "seeded": "🌱 موقع اضافه شدن منبع بود (خبرهای قدیمی فقط ثبت میشن)",
    "ai_wait": "⏳ منتظر AI (هنوز بازنویسی نشده)",
}

@bot.message_handler(commands=["why"])
def news_why_command(message):
    """/why sekiro — خبرهایی که این کلمه رو دارن و دلیل ارسال/عدم ارسالشون."""
    if message.from_user.id not in ADMINS:
        return
    keyword = (message.text or "").split(maxsplit=1)[1].strip() if len((message.text or "").split(maxsplit=1)) > 1 else ""
    if len(keyword) < 3:
        bot.send_message(message.chat.id, "یه کلمه از اسم انیمه یا خبر بنویس، مثلاً:\n/why sekiro")
        return
    conn = db()
    rows = conn.execute("""
        SELECT i.id, i.title, i.status, i.facts_json, i.created_at, s.title AS source_title
        FROM news_v2_items i LEFT JOIN news_sources s ON s.id = i.source_id
        WHERE i.title LIKE ? OR i.summary LIKE ? OR i.anime_display LIKE ?
        ORDER BY i.id DESC LIMIT 8
    """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")).fetchall()
    sources = conn.execute("SELECT COUNT(*) FROM news_sources WHERE active=1").fetchone()[0]
    conn.close()
    if not rows:
        bot.send_message(message.chat.id,
                         f"🔍 هیچ خبری با «{keyword}» توی {sources} منبع فعال پیدا نشد.\n"
                         "یعنی این خبر توی فید منابعت نبوده؛ باید منبعی که این خبر رو پوشش میده اضافه کنی "
                         "(مثلاً Crunchyroll News، Anime News Network یا اکانت X یه لیکر).")
        return
    for row in rows:
        try:
            facts = json.loads(row["facts_json"] or "{}")
        except Exception:
            facts = {}
        lines = [f"#{row['id']} — {row['title'][:150]}",
                 f"📰 منبع: {row['source_title'] or '?'} | 🕒 {row['created_at']}",
                 f"📌 {_NEWS_STATUS_FA.get(row['status'], row['status'])}"]
        if facts.get("importance") is not None:
            lines.append(f"⭐️ اهمیت: {facts['importance']}/100 (حداقل لازم: {_news_min_importance()})")
            if facts.get("importance_reasons"):
                lines.append("   " + "، ".join(facts["importance_reasons"]))
        if facts.get("agent_importance") is not None:
            lines.append(f"🤖 اهمیت از نظر AI: {facts['agent_importance']}/10")
        if facts.get("image_note"):
            lines.append(f"🖼 عکس: {facts['image_note'][:200]}")
        if facts.get("ai_last_error"):
            lines.append(f"⚠️ آخرین خطای AI: {str(facts['ai_last_error'])[:150]}")
        if facts.get("agent_rejected"):
            lines.append(f"⚠️ خروجی AI رد شد: {facts['agent_rejected']}")
        kb = None
        if row["status"] in ("low", "duplicate", "ai_wait", "seeded"):
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("📥 با این حال بفرست به آرشیو", callback_data=f"nv2_force:{row['id']}"))
        bot.send_message(message.chat.id, "\n".join(lines), reply_markup=kb, link_preview_options=NO_LINK_PREVIEW)


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("nv2_force:"))
def news_v2_force_archive_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    item_id = int(call.data.split(":", 1)[1])
    bot.answer_callback_query(call.id, "⏳ در حال آماده‌سازی…")

    def _job():
        _news_v2_update_facts(item_id, status="pending")
        if _news_agent_can_call()[0]:
            try:
                _news_agent_apply_ex(item_id)
            except Exception:
                logger.exception("Force-archive agent failed item=%s", item_id)
        try:
            _news_v2_send_preview(item_id)
            bot.send_message(call.from_user.id, f"✅ خبر #{item_id} به کانال آرشیو فرستاده شد.")
        except Exception as exc:
            bot.send_message(call.from_user.id, f"❌ ارسال خبر #{item_id} نشد: {exc}")

    threading.Thread(target=_job, daemon=True, name=f"force-{item_id}").start()

@bot.message_handler(func=lambda m: m.text == "🤖 وضعیت ایجنت خبر")
def news_agent_status(message):
    if message.from_user.id not in ADMINS:
        return
    ok, why = _news_agent_can_call()
    provider = []
    if _news_ai_custom_ready():
        _b, _k, _m = _news_ai_custom_config()
        _host = re.sub(r"^https?://", "", _b).split("/")[0]
        _used = get_setting(f"news_ai_used_{_news_agent_today()}", "0")
        provider.append(f"{_host} ({_m}) — امروز {_used} از {_news_ai_custom_limit()}")
    if GEMINI_API_KEY:
        provider.append(f"Gemini ({GEMINI_MODEL})")
    if OPENROUTER_API_KEY:
        provider.append("OpenRouter")
    enabled = get_setting("news_agent_enabled", "1") == "1"
    lines = [
        "🤖 وضعیت ایجنت خبر",
        "",
        f"سرویس: {' + '.join(provider) or 'هیچ کلیدی تنظیم نشده ⚠️'}",
        f"وضعیت: {'روشن ✅' if enabled else 'خاموش ⏸'}",
        f"آماده کار: {'بله ✅' if ok else '❌ ' + why}",
        f"درخواست‌های امروز: {_news_agent_used_today()} از {NEWS_AGENT_DAILY_LIMIT}",
        f"حداکثر خبر در هر دور بررسی: {NEWS_AGENT_MAX_PER_CYCLE}",
        "",
        "مدل‌ها به ترتیب:",
    ]
    lines += [f"• {m}" for m in _news_agent_models()[:5]]
    sig = _news_signature_text()
    lines += ["", f"✍️ امضا: {sig or 'تنظیم نشده'}"]
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⏸ خاموش کردن ایجنت" if enabled else "▶️ روشن کردن ایجنت",
                                callback_data="nagent_toggle"))
    bot.send_message(message.chat.id, "\n".join(lines), reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nagent_toggle")
def news_agent_toggle(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    new_val = "0" if get_setting("news_agent_enabled", "1") == "1" else "1"
    set_setting("news_agent_enabled", new_val)
    bot.answer_callback_query(call.id, "✅ ایجنت روشن شد." if new_val == "1" else "⏸ ایجنت خاموش شد.", show_alert=True)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

@bot.message_handler(func=lambda m: m.text == "✍️ امضای کانال خبر")
def news_signature_start(message):
    if message.from_user.id not in ADMINS:
        return
    current = _news_signature_text()
    msg = bot.send_message(
        message.chat.id,
        "✍️ امضایی که زیر همه خبرها بیاد رو بفرست.\nمثلاً: 🆔 @ariko_tv | آریکو نیوز\n"
        "برای حذف امضا فقط یه - بفرست.\n\n"
        f"امضای فعلی: {current or 'ندارد'}",
        reply_markup=create_markup_with_back(),
    )
    bot.register_next_step_handler(msg, news_signature_finish)

def news_signature_finish(message):
    uid = message.from_user.id
    if message.text == BACK_MAIN:
        show_news_admin_menu(message.chat.id, uid)
        return
    text = (message.text or "").strip()
    if text != "-" and (not text or len(text) > 120):
        msg = bot.send_message(message.chat.id, "❌ امضا باید حداکثر ۱۲۰ کاراکتر باشه. دوباره بفرست:")
        bot.register_next_step_handler(msg, news_signature_finish)
        return
    set_setting("news_signature", "" if text == "-" else text)
    bot.send_message(message.chat.id, "✅ امضا ذخیره شد. از خبرهای بعدی اعمال میشه.")
    show_news_admin_menu(message.chat.id, uid)

@bot.message_handler(func=lambda m: m.text == "🔑 تنظیم سرویس AI")
def news_ai_setup_start(message):
    if message.from_user.id not in ADMINS:
        return
    base, key, model = _news_ai_custom_config()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("AvalAI"))
    kb.add(KeyboardButton("🗑 حذف سرویس AI"))
    kb.add(KeyboardButton(BACK_MAIN))
    current = f"{base} | {model}" if _news_ai_custom_ready() else "تنظیم نشده"
    msg = bot.send_message(
        message.chat.id,
        "🔑 تنظیم سرویس AI خبر (هر API سازگار با OpenAI)\n\n"
        f"وضعیت فعلی: {current}\n\n"
        "روی AvalAI بزن یا آدرس Base URL سرویس دیگه رو بفرست (مثلاً https://example.com/v1):",
        reply_markup=kb,
    )
    bot.register_next_step_handler(msg, news_ai_setup_base)

def news_ai_setup_base(message):
    uid = message.from_user.id
    text = (message.text or "").strip()
    if text == BACK_MAIN:
        show_news_admin_menu(message.chat.id, uid)
        return
    if text == "🗑 حذف سرویس AI":
        for k in ("news_ai_base_url", "news_ai_api_key", "news_ai_model"):
            set_setting(k, "")
        bot.send_message(message.chat.id, "✅ سرویس AI حذف شد.")
        show_news_admin_menu(message.chat.id, uid)
        return
    base = AVALAI_BASE_URL if text.lower() == "avalai" else text.rstrip("/")
    if not re.match(r"^https://[^\s/]+", base):
        msg = bot.send_message(message.chat.id, "❌ آدرس باید با https:// شروع بشه. دوباره بفرست:")
        bot.register_next_step_handler(msg, news_ai_setup_base)
        return
    update_state(uid, nai_base=base)
    msg = bot.send_message(message.chat.id, "🔐 حالا API Key رو بفرست.\n(پیامت بلافاصله پاک میشه)",
                           reply_markup=create_markup_with_back())
    bot.register_next_step_handler(msg, news_ai_setup_key)

def news_ai_setup_key(message):
    uid = message.from_user.id
    text = (message.text or "").strip()
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    if text == BACK_MAIN:
        show_news_admin_menu(message.chat.id, uid)
        return
    if len(text) < 10 or " " in text:
        msg = bot.send_message(message.chat.id, "❌ کلید معتبر نیست. دوباره بفرست:")
        bot.register_next_step_handler(msg, news_ai_setup_key)
        return
    update_state(uid, nai_key=text)
    msg = bot.send_message(
        message.chat.id,
        "🧠 اسم مدل رو دقیقاً همون‌طور که توی لیست مدل‌های سرویس نوشته بفرست.\n"
        "برای خبر فارسی، یه مدل قوی ولی ارزون از خانواده Gemini Flash، GPT mini یا DeepSeek انتخاب کن.",
        reply_markup=create_markup_with_back(),
    )
    bot.register_next_step_handler(msg, news_ai_setup_model)

def news_ai_setup_model(message):
    uid = message.from_user.id
    model = (message.text or "").strip()
    if model == BACK_MAIN:
        show_news_admin_menu(message.chat.id, uid)
        return
    if not model or " " in model or len(model) > 120:
        msg = bot.send_message(message.chat.id, "❌ اسم مدل معتبر نیست. دوباره بفرست:")
        bot.register_next_step_handler(msg, news_ai_setup_model)
        return
    st = get_state(uid)
    base, key = st.get("nai_base"), st.get("nai_key")
    if not base or not key:
        bot.send_message(message.chat.id, "❌ از اول شروع کن.")
        show_news_admin_menu(message.chat.id, uid)
        return
    set_setting("news_ai_base_url", base)
    set_setting("news_ai_api_key", key)
    set_setting("news_ai_model", model)
    update_state(uid, nai_key=None)
    bot.send_message(message.chat.id, "⏳ در حال تست اتصال…")
    try:
        reply = _news_agent_custom_call("Reply briefly in Persian.", "فقط بنویس: اتصال برقرار است", timeout=40)
        bot.send_message(message.chat.id, f"✅ اتصال موفق بود.\nپاسخ مدل: {reply[:200]}")
    except Exception as exc:
        bot.send_message(message.chat.id, f"❌ تنظیمات ذخیره شد ولی تست ناموفق بود:\n{str(exc)[:400]}\n\n"
                                          "اسم مدل، کلید یا اعتبار حساب رو چک کن.")
    show_news_admin_menu(message.chat.id, uid)

# =========================
# هسته بات خبر
# =========================
def create_main_menu(user_id):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📰 مدیریت اخبار"))
    return kb


def show_main_menu(chat_id, user_id, text=None):
    if user_id in ADMINS:
        show_news_admin_menu(chat_id, user_id, text)
    else:
        bot.send_message(chat_id, "📰 این بات مخصوص مدیریت خبرهای کانال آریکوئه و فقط ادمین‌ها بهش دسترسی دارن.")


def admin_anime_panel(message):
    show_news_admin_menu(message.chat.id, message.from_user.id)


# ═════════════════════════════ پست اینستاگرام (کاور 1080x1440) ═════════════════════════════
# ادمین روی کارت آرشیو «🎨 پست اینستاگرام» رو می‌زنه → بات عکس‌های خبر رو جمع می‌کنه، تیتر کوتاه و
# کپشن اینستا رو با AI می‌نویسه، کاور رو با گرادیان و چیدمان تأییدشده می‌سازه و توی خصوصی می‌فرسته.
# عکس بعدی / جابه‌جایی برش / سیاه‌وسفید / ویرایش متن / عکس یا PSD خودت / ذخیره.
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
import insta_cover  # noqa: E402
import insta_photoshop  # noqa: E402

INSTA_FONT_DIRS = [os.path.join(DATA_DIR, "fonts"), os.path.join(BASE_DIR, "fonts")]
INSTA_LOGO_PATHS = [os.path.join(DATA_DIR, "insta_logo.png"), os.path.join(BASE_DIR, "logo.png")]
INSTA_MAX_CANDIDATES = 8
INSTA_FOCUS_STEP = 0.2
_insta_sessions = {}          # admin_id → جلسه‌ی ساخت کاور (فقط یکی در هر لحظه برای هر ادمین)
_insta_lock = threading.Lock()


def _insta_logo():
    for p in INSTA_LOGO_PATHS:
        if os.path.exists(p):
            try:
                from PIL import Image
                img = Image.open(p)
                img.load()
                return img
            except Exception as exc:
                logger.warning("Insta logo unreadable %s: %s", p, exc)
    return None


def _insta_short_name(name: str) -> str:
    """اسم‌های خیلی طولانی: قبل از «:» یا « - »، وگرنه چند کلمه‌ی اول."""
    name = re.sub(r"\s+", " ", (name or "").strip())
    if len(name) <= 24:
        return name
    for sep in (":", " - ", " – ", "~"):
        head = name.split(sep)[0].strip()
        if 3 <= len(head) <= 24:
            return head
    words = name.split()
    out = ""
    for w in words:
        if len((out + " " + w).strip()) > 24:
            break
        out = (out + " " + w).strip()
    return out or name[:24]


def _insta_plain(html_text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", html_text or "")).strip()


INSTA_AI_SYSTEM = """You write Instagram cover text for ARIKO, a Persian anime news page. Output ONLY JSON:
{"title": "...", "subtitle": "...", "tag": "...", "mood": "normal|sad", "caption": "..."}
Rules:
- title: Persian, catchy and warm (not formal/journalistic). It must carry the CORE of the news — the one thing a fan
  should get at a glance — told with its most interesting angle, NOT minor details. Minor details (studio, staff, platform,
  source manga/author, exact dates) belong in the caption, never on the cover.
  Find the angle: how long it ran / how long since, how close it is, first-ever, return, confirmation with season/year,
  delay, a surprising number that IS the news, an anniversary. Use «!» for big news.
  Keep it SHORT: apart from the anime name(s), at most 7 Persian words. Best shape: «<what happened> انیمه‌ی [Name] <verb>!»
  (on the cover the name starts its own line and «منتشر شد!» sits right after it). Put EVERY anime name, in English,
  inside [ ] — with two anime: «همکاری انیمه‌ی [A] و [B] منتشر شد!». Don't add filler like «جذاب/دیدنی/ویژه» to a
  two-name title; two names are long already.
  Examples of the right style (facts are examples only):
  «انیمه‌ی محبوب [Dr. Stone] پس از ۷ سال به پایان رسید!»
  «تنها یک هفته تا پخش فصل سوم انیمه‌ی [Frieren] باقی مانده!»
  «اولین تریلر فصل دوم انیمه‌ی [Solo Leveling] منتشر شد!»
  «فصل دوم انیمه‌ی [Draw This and Die] به صورت رسمی برای زمستان ۲۰۲۹ تایید شد!»
  «پس از گذشت ۱۰ سال، انیمه‌ی [Toradora] در آستانه‌ی بازگشت قرار داره!»
  «دو قسمت آخر انیمه‌ی [Re:Zero] به تعویق افتاد!»
  «فصل جدید انیمه‌ی [Black Clover] سرجمع ۲۶ قسمت خواهد بود!»
  «۷ سال پیش در چنین روزی، انیمه‌ی [Attack on Titan] برای اولین بار پخش شد!»
  Use only facts from the input; if the input has no such angle, keep it simple and clear.
  Do NOT copy or lightly rephrase the headline of "Our Persian channel post" — that one is written for Telegram;
  the cover needs its own short punchy headline. No «» quotes around the title or the name.
- subtitle: Persian, short (4-9 words): ONE more fact fans care about at a glance, from the input — e.g. the release
  date/season («تاریخ پخش انیمه زمستان ۲۰۲۷ اعلام شده»), when/where it airs or premieres («فیلم Dear Friend امروز در
  سینماهای ژاپن اکران شد»), or the episode count. Anime/movie names in English, no [ ]. Never repeat the title, never
  studio/staff/platform trivia. Empty string only if the input has no such fact.
- tag: 1-2 Persian words: «خبر رسمی» for official announcements (trailers, visuals, dates, confirmations), «شایعه» for leaks/rumors, «خبر تلخ» for deaths/sad news, else «خبر».
- mood: "sad" only for deaths, cancellations, tragedies; else "normal".
- caption: Instagram caption in friendly spoken Persian, 2-5 short sentences: the news, plus the details that were
  kept off the cover (studio, platform, source manga/author, exact dates, episode info) — facts from the input only,
  anime names in English, then a blank line and 6-10 hashtags (#انیمه #انیمه_جدید #anime plus the anime's English name without spaces).
Use only facts from the input."""


def _insta_norm_fa(text: str) -> str:
    return re.sub(r"[\s\u200c«»\[\]\"'!؛،.:]+", " ", text or "").strip().lower()


def _insta_short_for(name: str) -> str:
    """اسم کوتاه انیمه برای کاور: اسم خود + مترادف‌های AniList (مثل TenSura) → کوتاه‌ترین اسم لاتین معقول."""
    name = re.sub(r"\s+", " ", (name or "").strip())
    if len(name) <= 22:
        return name
    options = []
    try:
        meta = _news_anilist_lookup(name) or {}
        options = [meta.get("title_en") or "", meta.get("title_romaji") or ""] + list(meta.get("synonyms") or [])
    except Exception:
        pass
    options = [o.strip() for o in options if o and re.fullmatch(r"[A-Za-z0-9 :!'’&.\-]{4,22}", o.strip())]
    if options:
        return min(options, key=len)
    for sep in (":", " - ", " – ", "~"):              # فقط از جای طبیعی (قبل از «:» و …) کوتاه میشه
        head = name.split(sep)[0].strip()
        if 3 <= len(head) < len(name):
            return head
    return name                                      # وسط اسم بریده نمیشه (مثل «I'm Dating a Dark»)؛ فونت خودش کوچیک میشه


def _insta_clean_title(title: str, name: str) -> str:
    """«» و گیومه‌های دور تیتر/اسم حذف؛ اسم بلند داخل [] کوتاه میشه."""
    t = re.sub(r"\s+", " ", title or "").strip()
    t = re.sub(r"[«»“”\"]", "", t).strip()
    if "[" not in t and name and name in t:
        t = t.replace(name, f"[{name}]", 1)

    def shorten(m):
        inner = m.group(1).strip()
        return f"[{_insta_short_for(inner)}]" if len(inner) > 22 else f"[{inner}]"
    return re.sub(r"\[([^\]]+)\]", shorten, t)


def _insta_ai_text(row) -> dict:
    """تیتر/زیرنویس/تگ/کپشن با AI؛ اگه AI در دسترس نبود یه متن ساده از روی خبر."""
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except Exception:
        facts = {}
    name = (row["anime_eng_name"] or facts.get("anime_eng_name") or row["anime_display"] or "").strip()
    plain = _insta_plain(row["caption"])
    fallback = {
        "title": (f"خبر جدید از انیمه‌ی [{_insta_short_name(name)}]" if re.search(r"[A-Za-z]", name)
                  else (plain.split("\n")[0][:70] or "خبر جدید")),
        "subtitle": "", "tag": "خبر", "mood": "normal",
        "caption": plain + "\n\n#انیمه #انیمه_جدید #anime", "ai": False,
    }
    anniv = facts.get("anniversary") or {}
    if anniv.get("years"):                          # پست سالگرد (بدون AI هم تیترش درست باشه)
        years = _news_fa_digits(str(anniv["years"]))
        short = _insta_short_name(name)
        sfa = f"فصل {_anniv_ordinal(int(anniv['season']))}" if anniv.get("season") else "این فصل"
        fallback["title"] = {
            "first": f"{years} سال پیش در چنین روزی، انیمه‌ی [{short}] برای اولین بار پخش شد!",
            "season_start": f"{years} سال پیش در چنین روزی، پخش {sfa} انیمه‌ی [{short}] شروع شد!",
            "movie": f"{years} سال پیش در چنین روزی، فیلم [{short}] اکران شد!",
            "season_end": f"{years} سال پیش در چنین روزی، {sfa} انیمه‌ی [{short}] به پایان رسید!",
            "final_end": f"{years} سال پیش در چنین روزی، {sfa} انیمه‌ی [{short}] به پایان رسید!",
        }.get(anniv.get("kind"), fallback["title"])
        fallback["tag"] = "سالگرد"
        fallback["caption"] = plain + "\n\n#انیمه #سالگرد #anime"
    user = (f"English anime name (from database): {name or '-'}\n"
            f"Event type: {row['event_type'] or '-'}\n"
            f"Source title: {row['title'] or ''}\n"
            f"Source summary: {(row['summary'] or '')[:1500]}\n"
            f"Our Persian channel post:\n{plain[:1800]}")
    try:
        ok, _why = _news_agent_can_call()
        if not ok:
            return fallback
        text, model = _news_agent_generate(INSTA_AI_SYSTEM, user)
        data = _news_agent_parse_json(text) or {}
    except Exception as exc:
        logger.info("Insta AI text failed item=%s: %s", row["id"], exc)
        return fallback
    title = _insta_clean_title(str(data.get("title") or ""), name)
    if not title or not re.search(r"[؀-ۿ]", title):
        return fallback
    headline = _insta_plain((row["caption"] or "").split("\n")[0])
    if headline and SequenceMatcher(None, _insta_norm_fa(title), _insta_norm_fa(headline)).ratio() > 0.72:
        # تیتر تلگرام رو کپی کرده → یه بار دیگه با تأکید
        try:
            text2, _m = _news_agent_generate(INSTA_AI_SYSTEM, user + "\n\nIMPORTANT: your previous title copied the "
                                             "channel headline. Write a NEW short cover headline with the news angle.")
            data2 = _news_agent_parse_json(text2) or {}
            t2 = _insta_clean_title(str(data2.get("title") or ""), name)
            if t2 and re.search(r"[؀-ۿ]", t2):
                data, title = data2, t2
        except Exception as exc:
            logger.info("Insta AI retry failed item=%s: %s", row["id"], exc)
    # اسم انگلیسی بیرون از [] مونده؟ داخلش بذار که زرد بشه
    if "[" not in title and name and name in title:
        title = title.replace(name, f"[{_insta_short_name(name)}]", 1)
    return {
        "title": title[:200],
        "subtitle": re.sub(r"\s+", " ", str(data.get("subtitle") or "")).strip()[:80],
        "tag": "سالگرد" if anniv.get("years") else (re.sub(r"\s+", " ", str(data.get("tag") or "خبر")).strip()[:20] or "خبر"),
        "mood": "sad" if str(data.get("mood") or "").lower() == "sad" else "normal",
        "caption": str(data.get("caption") or "").strip()[:2100] or fallback["caption"],
        "ai": True,
    }


def _insta_candidates(row) -> list:
    """عکس‌های قابل استفاده برای پس‌زمینه‌ی کاور، به ترتیب اولویت."""
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except Exception:
        facts = {}
    out, seen = [], set()

    def add(kind, ref, label):
        if ref and ref not in seen and len(out) < INSTA_MAX_CANDIDATES:
            seen.add(ref)
            out.append({"kind": kind, "ref": ref, "label": label})

    # هر لینک با کپی تلگرامیِ همون عکس (پیش‌نمایش آرشیو) جفت میشه: اگه سایت اجازه‌ی دانلود نداد، کپی استفاده میشه
    main_fid = facts.get("archive_photo_file_id") or ""
    extra_urls = [u for u in (facts.get("extra_images") or []) if u and _news_safe_url(u)]
    extra_fids = list(facts.get("extra_file_ids") or [])
    pairs = []
    if row["image_url"] and _news_safe_url(row["image_url"]):
        pairs.append((row["image_url"], main_fid))
    elif main_fid:
        pairs.append(("", main_fid))
    aligned = len(extra_urls) == len(extra_fids)
    for i, u in enumerate(extra_urls):
        pairs.append((u, extra_fids[i] if aligned else ""))
    if not aligned:
        pairs += [("", f) for f in extra_fids]
    for url, fid in pairs:
        if url:
            if url not in seen and len(out) < INSTA_MAX_CANDIDATES:
                seen.add(url)
                out.append({"kind": "url", "ref": url, "alt": fid, "label": "عکس خبر"})
        else:
            add("file_id", fid, "عکس آرشیو")
    try:                                            # کتابخونه‌ی عکس خود ادمین (پوشه‌ی هم‌اسم انیمه)
        folder, files = _insta_library_images(row, facts)
        for path in files:
            if path not in seen:
                seen.add(path)
                out.append({"kind": "file", "ref": path, "label": f"📂 کتابخونه ({folder})"})
    except Exception as exc:
        logger.info("Insta library failed item=%s: %s", row["id"], exc)
    try:
        kind, ref = _news_v2_fallback_image(row)
        if kind:
            add(kind, ref, "پوستر همین فصل")
    except Exception:
        logger.info("Insta fallback poster failed item=%s", row["id"])
    try:                                            # پوستر رسمی خود انیمه از AniList
        name = (row["anime_eng_name"] or facts.get("anime_eng_name") or row["anime_display"] or "").strip()
        al = (_news_anilist_lookup(name) or {}) if len(name) >= 3 else {}
        if al.get("banner"):                        # بنر افقی رسمی: معمولاً شخصیت‌های اصلی، بدون نوشته (برای کاور عالیه)
            add("url", al["banner"], "بنر رسمی (AniList)")
        if al.get("cover"):
            add("url", al["cover"], "پوستر رسمی (AniList)")
    except Exception:
        logger.info("Insta AniList poster failed item=%s", row["id"])
    try:                                            # پوستر و صحنه‌های باکیفیت (تا 4K) از TMDB، اگه کلیدش تنظیم شده
        tname = (row["anime_eng_name"] or facts.get("anime_eng_name") or row["anime_display"] or "").strip()
        extra_imgs = _insta_tmdb_images(tname)
        try:
            extra_imgs += _insta_jikan_pictures(tname)
        except Exception as exc:
            logger.info("Insta Jikan pictures failed for %s: %s", tname, exc)
        for url, label in extra_imgs:
            if sum(1 for c in out if c["kind"] != "file") >= INSTA_MAX_CANDIDATES + 14:   # کتابخونه حساب نمیشه
                break
            if url not in seen:
                seen.add(url)
                out.append({"kind": "url", "ref": url, "label": label})
    except Exception:
        logger.info("Insta TMDB images failed item=%s", row["id"])
    for c in out:                                   # عکس‌های توییتر → نسخه‌ی اصلی با کیفیت کامل
        if c["kind"] == "url" and "pbs.twimg.com/media/" in c["ref"]:
            if "name=" in c["ref"]:
                c["ref"] = re.sub(r"([?&]name=)\w+", r"\1orig", c["ref"])
            else:
                c["ref"] += ("&" if "?" in c["ref"] else "?") + "name=orig"
    return out


INSTA_LIBRARY_MAX = 12                       # حداکثر چند عکس از پوشه‌ی هر انیمه (تصادفی، که پست‌ها تکراری نشن)
INSTA_LIBRARY_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")


def _insta_lib_words(value: str) -> list:
    """کلمه‌های اسم برای مقایسه: حروف کوچیک، بدون «Season 2/Part 2/Final Season/فصل ۲» و زیرعنوان بعد از «: »."""
    v = (value or "").lower()
    v = re.split(r":\s|\s[\-–|]\s", v)[0]
    v = re.sub(r"\b(season|part|cour)\s*\d+\b|\b\d+(st|nd|rd|th)\s+season\b|\bfinal\s+season\b|"
               r"\bs\d+\b|فصل\s*\S+", " ", v)
    return [w for w in re.split(r"[\W_]+", v) if w]


def _insta_lib_norm(value: str) -> str:
    return "".join(_insta_lib_words(value))


def _insta_library_root() -> str:
    path = get_setting("insta_library", "")
    return path if path and os.path.isdir(path) else ""


def _insta_library_folders(root: str) -> list:
    """[(اسم پوشه، مسیر، [اسم‌های قابل‌قبول])]؛ هر پوشه می‌تونه یه names.txt داشته باشه (هر خط یه اسم دیگه)."""
    out = []
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        names = [name]
        alias = os.path.join(path, "names.txt")
        if os.path.isfile(alias):
            try:
                with open(alias, encoding="utf-8-sig", errors="ignore") as fh:
                    names += [ln.strip() for ln in fh if ln.strip()]
            except OSError:
                pass
        out.append((name, path, names))
    return out


def _insta_library_match(root: str, anime_names: list):
    """پوشه‌ای که اسمش با اسم انیمه‌ی خبر می‌خونه: (اسم پوشه، مسیر) یا (None, None)."""
    targets = [w for w in (_insta_lib_words(x) for x in anime_names if x) if len("".join(w)) >= 3]
    if not targets:
        return None, None
    best, best_score = (None, None), 0.0
    for name, path, names in _insta_library_folders(root):
        for alias in names:
            aw = _insta_lib_words(alias)
            a = "".join(aw)
            if len(a) < 3:
                continue
            for tw in targets:
                t = "".join(tw)
                if a == t:
                    score = 1.0
                elif len(a) >= 4 and tw[:len(aw)] == aw:          # «Solo Leveling» ← «Solo Leveling Arise …»
                    score = 0.92
                elif (len(tw) >= 2 or len(t) >= 6) and aw[:len(tw)] == tw:
                    score = 0.88
                else:
                    score = SequenceMatcher(None, a, t).ratio()
                if score > best_score:
                    best, best_score = (name, path), score
    return best if best_score >= 0.84 else (None, None)


def _insta_library_images(row, facts: dict):
    """عکس‌های پوشه‌ی همین انیمه توی کتابخونه‌ی ادمین: (اسم پوشه، [مسیر فایل‌ها])."""
    root = _insta_library_root()
    if not root:
        return None, []
    names = [row["anime_eng_name"], facts.get("anime_eng_name"), row["anime_display"], facts.get("anime_display")]
    eng = (row["anime_eng_name"] or facts.get("anime_eng_name") or row["anime_display"] or "").strip()
    if len(eng) >= 3:
        try:
            meta = _news_anilist_lookup(eng) or {}
            names += [meta.get("title_en"), meta.get("title_romaji"), meta.get("title_native")]
            names += list(meta.get("synonyms") or [])
        except Exception:
            pass
    folder, path = _insta_library_match(root, names)
    if not path:
        return None, []
    files = []
    for base, _dirs, fnames in os.walk(path):
        files += [os.path.join(base, f) for f in fnames if f.lower().endswith(INSTA_LIBRARY_EXT)]
    if len(files) > INSTA_LIBRARY_MAX:
        files = random.sample(files, INSTA_LIBRARY_MAX)
    return folder, sorted(files)


TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "").strip()


def _insta_tmdb_images(name: str) -> list:
    """[(لینک، برچسب)]: صحنه‌های افقی (backdrop) و پوسترهای باکیفیت همین انیمه از TMDB (نیاز به TMDB_API_KEY)."""
    if not TMDB_API_KEY or len(name or "") < 3:
        return []
    base = "https://api.themoviedb.org/3"

    def get(path, **params):
        params["api_key"] = TMDB_API_KEY
        url = f"{base}{path}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": NEWS_USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8", errors="ignore"))
    hits = [h for h in (get("/search/multi", query=name).get("results") or [])
            if h.get("media_type") in ("tv", "movie")]
    anime = [h for h in hits if 16 in (h.get("genre_ids") or [])] or hits          # 16 = Animation
    if not anime:
        return []
    h = anime[0]
    imgs = get(f"/{h['media_type']}/{h['id']}/images", include_image_language="en,ja,null")
    out = []
    stills = [b for b in (imgs.get("backdrops") or []) if b.get("iso_639_1") in (None, "", "xx")]   # بدون نوشته/لوگو
    for b in sorted(stills, key=lambda x: -(x.get("vote_average") or 0))[:10]:
        out.append((f"https://image.tmdb.org/t/p/original{b['file_path']}", "صحنه (TMDB)"))
    for po in sorted(imgs.get("posters") or [], key=lambda x: -(x.get("vote_average") or 0))[:2]:
        out.append((f"https://image.tmdb.org/t/p/original{po['file_path']}", "پوستر (TMDB)"))
    try:                                            # صحنه‌ها و آرت شخصیت‌های HD از fanart.tv (کلید جدا، اختیاری)
        if h["media_type"] == "tv":
            tvdb = get(f"/tv/{h['id']}/external_ids").get("tvdb_id")
            out += _insta_fanart_images("tv", tvdb)
        else:
            out += _insta_fanart_images("movies", h["id"])
    except Exception as exc:
        logger.info("Insta fanart.tv lookup failed for %s: %s", name, exc)
    return out


FANART_API_KEY = os.environ.get("FANART_API_KEY", "").strip()


def _insta_fanart_images(kind: str, ident) -> list:
    """fanart.tv: پس‌زمینه‌های HD و آرت شخصیت‌ها (نیاز به FANART_API_KEY رایگان)."""
    if not FANART_API_KEY or not ident:
        return []
    url = f"https://webservice.fanart.tv/v3/{kind}/{ident}?api_key={urllib.parse.quote(FANART_API_KEY)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": NEWS_USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    out = []
    for key, label, limit in (("showbackground", "صحنه (fanart.tv)", 6), ("moviebackground", "صحنه (fanart.tv)", 6),
                              ("characterart", "آرت شخصیت (fanart.tv)", 3), ("tvthumb", "صحنه (fanart.tv)", 3)):
        for item in sorted(data.get(key) or [], key=lambda x: -int(x.get("likes") or 0))[:limit]:
            if item.get("url"):
                out.append((item["url"], label))
    return out


def _insta_jikan_pictures(name: str) -> list:
    """عکس‌های رسمی (کی‌ویژوال‌ها) از MyAnimeList با Jikan؛ بدون کلید."""
    if len(name or "") < 3:
        return []
    q = urllib.parse.urlencode({"q": name, "limit": 1, "sfw": "true"})
    req = urllib.request.Request(f"https://api.jikan.moe/v4/anime?{q}", headers={"User-Agent": NEWS_USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        hits = json.loads(resp.read().decode("utf-8", errors="ignore")).get("data") or []
    if not hits:
        return []
    mal_id = hits[0].get("mal_id")
    req = urllib.request.Request(f"https://api.jikan.moe/v4/anime/{mal_id}/pictures", headers={"User-Agent": NEWS_USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        pics = json.loads(resp.read().decode("utf-8", errors="ignore")).get("data") or []
    out = []
    for p in pics[-4:][::-1]:                        # جدیدترین‌ها آخر لیستن
        url = ((p.get("jpg") or {}).get("large_image_url")) or ((p.get("webp") or {}).get("large_image_url"))
        if url:
            out.append((url, "عکس رسمی (MyAnimeList)"))
    return out


def _insta_download(url: str) -> bytes:
    """دانلود عکس با کیفیت کامل (تا ۲۵ مگ، با Referer خود سایت که جلوی hotlink رو نگیره)."""
    parts = urllib.parse.urlsplit(url)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*;q=0.8",
        "Referer": f"{parts.scheme}://{parts.netloc}/",
    })
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read(25_000_001)


def _insta_load(cand):
    from PIL import Image
    errors = []
    sources = [(cand["kind"], cand["ref"])]
    if cand.get("alt"):
        sources.append(("file_id", cand["alt"]))
    for kind, ref in sources:
        try:
            if kind == "url":
                data = _insta_download(ref)
            elif kind == "file":                        # کتابخونه‌ی عکس روی همین سیستم
                with open(ref, "rb") as fh:
                    data = fh.read()
            else:
                data = bot.download_file(bot.get_file(ref).file_path)
            img = Image.open(io.BytesIO(data))
            img.load()
            if kind == "file_id" and cand["kind"] == "url":
                cand["label"] = "عکس خبر (کپی آرشیو)"
            return img.convert("RGB")
        except Exception as exc:
            errors.append(f"{kind}: {exc}")
    logger.info("Insta image load failed %s: %s", cand.get("ref"), " | ".join(errors))
    raise RuntimeError("دانلود عکس ممکن نشد: " + " | ".join(errors)[:200])


def _insta_current(sess):
    """(عکس، focus، zoom) عکس فعلی؛ بار اول دانلود میشه و اگه کوچیک بود با Gemini بزرگ میشه."""
    idx = sess["idx"]
    img = sess["images"].get(idx)
    if img is None:
        img = _insta_load(sess["cands"][idx])
        sess["images"][idx] = img
        sess.setdefault("orig", {})[idx] = img
        sess.setdefault("zoom", {})[idx] = insta_cover.default_zoom(img, insta_cover.PSD_SIZE)
    tried = sess.setdefault("up_tried", set())
    if idx not in tried:                             # هر عکس فقط یه بار (عکس‌ها از قبل دانلود شدن)
        tried.add(idx)
        zoom0 = sess.setdefault("zoom", {}).get(idx) or insta_cover.default_zoom(img, insta_cover.PSD_SIZE)
        if (get_setting("insta_upscale", "1") == "1" and sess["cands"][idx]["kind"] != "upload"
                and insta_cover.upscale_needed(img, insta_cover.PSD_SIZE, zoom0) > 1.3):
            up, why = _insta_esrgan_upscale(img)
            if up is None:
                up, why2 = _insta_gemini_upscale(img)
                why = why2 if not why else f"{why}\n{why2}"
            sess.setdefault("up_note", {})[idx] = why
            if up is not None:
                # نسخه‌ی تیزشده دقیقاً به همون اندازه‌ای که عکس قرار بود نمایش داده بشه (نه بزرگ‌تر، که زوم نشه)
                target = insta_cover.upscale_needed(img, insta_cover.PSD_SIZE, zoom0)
                tw, th = round(img.width * target), round(img.height * target)
                if up.width != tw:
                    up = up.resize((tw, th), Image.LANCZOS)
                sess["images"][idx] = img = up
    zoom = sess.setdefault("zoom", {}).get(idx) or insta_cover.default_zoom(img, insta_cover.PSD_SIZE)
    focus = sess["focus"].get(idx)
    box = (sess.get("subject") or {}).get(idx)
    if idx not in (sess.get("focus_manual") or set()) and box:
        # جای سوژه‌ی اصلی (از دید Gemini) → کادر روی شخصیت‌ها، نه وسط خالی عکس
        focus = insta_cover.focus_for_subject(img, box, insta_cover.PSD_SIZE)
        sess["focus"][idx] = focus
    elif focus is None:
        focus = (insta_cover.auto_focus(img), 0.0)
        sess["focus"][idx] = focus
    return img, focus, zoom


def _insta_render(sess):
    img, focus, zoom = _insta_current(sess)
    if sess.get("ready"):                          # کاور آماده‌ی خود ادمین: فقط اندازه‌ی کادر
        return insta_cover.fit_cover(img, insta_cover.PSD_SIZE, (0.5, 0.5))
    return insta_cover.render_cover(img, sess["title"], sess["subtitle"], sess["tag"], INSTA_FONT_DIRS,
                                    logo=_insta_logo(), focus=focus, bw=sess["bw"], zoom=zoom, adj=sess.get("adj"))


INSTA_UPSCALE_PROMPT = (
    "Upscale this anime image to a higher resolution. This is a pure restoration/upscaling task: keep EXACTLY the "
    "same composition, framing, characters, faces, expressions, line art, colors, text and every detail. Do not add, "
    "remove, redraw, restyle or crop anything. Only make it sharper and cleaner at higher resolution, like the "
    "original high-quality artwork. Return only the image."
)


REALESRGAN_PATH = os.environ.get("REALESRGAN_PATH", "").strip().strip('"')
UPSCALER_EXES = ("realesrgan-ncnn-vulkan.exe", "realcugan-ncnn-vulkan.exe", "waifu2x-ncnn-vulkan.exe")
_UPSCALER_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "upscaler_path.txt")
_upscaler_found = None


def _find_upscaler():
    """مسیر exe بزرگ‌نمایی؛ اول REALESRGAN_PATH، بعد همونی که ابزار ادیت (جعبه‌ابزار) روی سیستم داره.
    یه بار می‌گرده و نتیجه رو توی upscaler_path.txt نگه می‌داره."""
    global _upscaler_found
    if REALESRGAN_PATH and os.path.exists(REALESRGAN_PATH):
        return REALESRGAN_PATH
    if _upscaler_found is not None:
        return _upscaler_found or None
    try:
        with open(_UPSCALER_CACHE, encoding="utf-8") as f:
            cached = f.read().strip()
        if cached and os.path.exists(cached):
            _upscaler_found = cached
            return cached
    except Exception:
        pass
    home = os.path.expanduser("~")
    roots = [os.path.join(home, ".ariyan"), os.path.join(home, "Desktop"), os.path.join(home, "Downloads"),
             os.path.join(home, "Documents"), os.environ.get("LOCALAPPDATA", ""), os.environ.get("APPDATA", ""),
             os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""), "C:\\Tools", home,
             "D:\\", "E:\\"]
    skip = {"node_modules", ".git", "__pycache__", "packages", "temp", "cache", "windows", "$recycle.bin",
            "microsoft", "google", "mozilla", "steamapps"}
    deadline = time.time() + 25
    found = {}
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        base = root.rstrip("\\/").count(os.sep)
        for cur, dirs, files in os.walk(root):
            if time.time() > deadline:
                break
            low = {f.lower(): f for f in files}
            for name in UPSCALER_EXES:
                if name in low and name not in found:
                    found[name] = os.path.join(cur, low[name])
            if UPSCALER_EXES[0] in found:
                break
            if cur.count(os.sep) - base >= 5:
                dirs[:] = []
            else:
                dirs[:] = [d for d in dirs if d.lower() not in skip]
        if UPSCALER_EXES[0] in found or time.time() > deadline:
            break
    path = next((found[n] for n in UPSCALER_EXES if n in found), "")
    _upscaler_found = path
    if path:
        logger.info("Upscaler found: %s", path)
        try:
            with open(_UPSCALER_CACHE, "w", encoding="utf-8") as f:
                f.write(path)
        except Exception:
            pass
    return path or None


if os.name == "nt":                                    # گشتن دنبال exe از همون اول، که اولین کاور معطل نشه
    threading.Thread(target=_find_upscaler, daemon=True).start()

def _upscaler_cmd(exe, src, dst, need):
    """دستور اجرای exe با بهترین مدل انیمه‌ای که کنارش هست."""
    name = os.path.basename(exe).lower()
    models = os.path.join(os.path.dirname(exe), "models")
    have = set(os.listdir(models)) if os.path.isdir(models) else set()
    if name.startswith("realcugan"):
        return [exe, "-i", src, "-o", dst, "-s", "4" if need > 2.2 else "2", "-n", "-1"]
    if name.startswith("waifu2x"):
        return [exe, "-i", src, "-o", dst, "-s", "2", "-n", "1"]
    if "realesrgan-x4plus-anime.param" in have:          # بهترین مدل برای عکس ثابت انیمه (فقط ۴ برابر)
        return [exe, "-i", src, "-o", dst, "-n", "realesrgan-x4plus-anime", "-s", "4"]
    return [exe, "-i", src, "-o", dst, "-n", "realesr-animevideov3", "-s", "4" if need > 2.2 else "2"]


def _insta_esrgan_upscale(img):
    """بزرگ‌نمایی مخصوص انیمه روی خود کامپیوتر (Real-ESRGAN / Real-CUGAN ابزار ادیت)؛
    چیزی اضافه/عوض نمی‌کنه، فقط تیزتر و بزرگ‌تر. اگه پیدا نشد: (None, "")."""
    import subprocess
    import tempfile as _tf
    from PIL import Image
    exe = _find_upscaler()
    if not exe:
        return None, ""
    folder = _tf.mkdtemp(prefix="ariko_esr_")
    src, dst = os.path.join(folder, "in.png"), os.path.join(folder, "out.png")
    try:
        img.convert("RGB").save(src)
        need = max(insta_cover.PSD_SIZE[0] / img.width, insta_cover.PSD_SIZE[1] / img.height)
        cmd = _upscaler_cmd(exe, src, dst, need)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        res = subprocess.run(cmd, capture_output=True, timeout=240, cwd=os.path.dirname(exe), creationflags=flags)
        if not os.path.exists(dst):
            return None, f"بزرگ‌نمایی ابزار ادیت نشد: {(res.stderr or b'').decode('utf-8', 'ignore')[-200:]}"
        out = Image.open(dst)
        out.load()
        return out.convert("RGB"), (f"✨ کیفیت با هوش مصنوعی ابزار ادیت بیشتر شد "
                                    f"({img.width}x{img.height} → {out.width}x{out.height})")
    except Exception as exc:
        return None, f"بزرگ‌نمایی ابزار ادیت نشد: {str(exc)[:150]}"
    finally:
        for f in (src, dst):
            try:
                os.remove(f)
            except Exception:
                pass
        try:
            os.rmdir(folder)
        except Exception:
            pass


def _insta_gemini_upscale(img):
    """بزرگ‌نمایی عکس کوچیک با مدل تصویری Gemini. اگه نتیجه با اصل عکس فرق محسوس داشت
    (چیزی عوض/اضافه شده یا مصنوعی شده) رد میشه و اصل عکس می‌مونه. خروجی: (عکس یا None، توضیح)."""
    import base64
    import numpy as np
    from PIL import Image
    if not GEMINI_API_KEY:
        return None, "GEMINI_API_KEY تنظیم نشده"
    model = os.environ.get("GEMINI_IMAGE_MODEL", "").strip() or "gemini-2.5-flash-image"
    bio = io.BytesIO()
    img.save(bio, "PNG")
    body = {
        "contents": [{"parts": [{"text": INSTA_UPSCALE_PROMPT},
                                {"inline_data": {"mime_type": "image/png",
                                                 "data": base64.b64encode(bio.getvalue()).decode()}}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }
    req = urllib.request.Request(GEMINI_CHAT_URL.format(model=model), data=json.dumps(body).encode("utf-8"),
                                 method="POST", headers={"Content-Type": "application/json",
                                                         "x-goog-api-key": GEMINI_API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as exc:
        return None, f"افزایش کیفیت نشد — Gemini ({model}): {_gemini_error_message(exc)[:120]}"
    except Exception as exc:
        return None, f"افزایش کیفیت نشد — Gemini: {str(exc)[:120]}"
    data = None
    for part in (((payload.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []):
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            data = inline["data"]
    if not data:
        return None, "افزایش کیفیت نشد — Gemini عکسی برنگردوند"
    try:
        out = Image.open(io.BytesIO(base64.b64decode(data)))
        out.load()
        out = out.convert("RGB")
    except Exception as exc:
        return None, f"افزایش کیفیت نشد — خروجی Gemini خراب بود: {exc}"
    if out.width <= img.width * 1.1:
        return None, "افزایش کیفیت نشد — Gemini عکس بزرگ‌تری نداد"
    if abs(out.width / out.height - img.width / img.height) > 0.04:
        return None, "Gemini کادر عکس رو عوض کرد؛ اصل عکس نگه داشته شد"
    # شباهت ساختاری با اصل: اگه چیزی رو عوض/اضافه کرده باشه همبستگی پایین میاد
    size = (64, max(8, round(64 * img.height / img.width)))
    a = np.asarray(img.convert("L").resize(size, Image.LANCZOS), dtype=np.float32).ravel()
    b = np.asarray(out.convert("L").resize(size, Image.LANCZOS), dtype=np.float32).ravel()
    a, b = a - a.mean(), b - b.mean()
    corr = float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-6))
    if corr < 0.93:
        return None, f"نتیجه‌ی Gemini با اصل عکس فرق داشت ({corr:.2f})؛ اصل عکس نگه داشته شد"
    return out, f"✨ کیفیت با Gemini بیشتر شد ({img.width}x{img.height} → {out.width}x{out.height})"


def _insta_trailer_frames(row, count=6) -> list:
    """چند فریم خوب (صحنه‌ی انیمه) از تریلر یوتیوب این انیمه، با کیفیت تا 1080p."""
    import subprocess
    import numpy as np
    from PIL import Image
    if yt_dlp is None:
        raise RuntimeError("yt-dlp نصب نیست")
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("ffmpeg پیدا نشد (pip install imageio-ffmpeg)")
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except Exception:
        facts = {}
    url = facts.get("trailer_url") or ""
    if not url:
        name = (row["anime_eng_name"] or facts.get("anime_eng_name") or row["anime_display"] or "").strip()
        if name:
            picked, _sure = _trailer_pick(name, _trailer_search(f"{name} anime trailer PV"))
            url = (picked or {}).get("url", "")
    if not url:
        raise RuntimeError("تریلری برای این انیمه پیدا نشد")
    opts = _trailer_ydl_opts(1080)
    opts["format"] = "bv*[height<=1080][ext=mp4]/bv*[height<=1080]/b[height<=1080]/b"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    stream = info.get("url") or ((info.get("requested_formats") or [{}])[0].get("url"))
    duration = float(info.get("duration") or 90)
    if not stream:
        raise RuntimeError("لینک ویدیو پیدا نشد")
    headers = "".join(f"{k}: {v}\r\n" for k, v in (info.get("http_headers") or {}).items())
    frames = []
    last_err = ""
    n = count + 10
    for i in range(n):
        t = duration * (0.08 + 0.8 * i / max(1, n - 1))
        cmd = [ffmpeg, "-v", "error", "-ss", f"{t:.2f}"]
        if headers:
            cmd += ["-headers", headers]
        if NEWS_PROXY:
            cmd += ["-http_proxy", NEWS_PROXY]
        cmd += ["-i", stream, "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=45)
            if not res.stdout:
                last_err = (res.stderr or b"").decode("utf-8", errors="ignore").strip()[-300:] or "ffmpeg خروجی نداد"
                logger.info("Trailer frame at %.1fs empty: %s", t, last_err)
                continue
            im = Image.open(io.BytesIO(res.stdout))
            im.load()
            frames.append(im.convert("RGB"))
        except Exception as exc:
            logger.info("Trailer frame at %.1fs failed: %s", t, exc)
    # فریم‌های یکدست (سیاه/سفید/تیتراژ) کنار میرن؛ رنگی‌تر و پرجزئیات‌ترها اول
    scored = []
    for im in frames:
        a = np.asarray(im.resize((160, 90)), dtype=np.float32)
        g = a.mean(axis=2)
        if g.std() < 28 or not (30 < g.mean() < 225):
            continue
        sat = (a.max(axis=2) - a.min(axis=2)).mean()
        detail = np.abs(np.diff(g, axis=1)).mean()
        scored.append((sat * 0.6 + detail * 2.0, im))
    scored.sort(key=lambda x: -x[0])
    if not frames:
        raise RuntimeError(f"هیچ فریمی از ویدیو گرفته نشد ({url}): {last_err or 'نامعلوم'}")
    if not scored:
        raise RuntimeError(f"{len(frames)} فریم گرفته شد ولی همه تیره/یکدست (تیتراژ) بودن")
    return [im for _, im in scored[:count]]


INSTA_VISION_PROMPT = """You pick and frame the background image for an Instagram news cover (portrait 3:4) of a
Persian anime news page. News: {news}
You get {n} images numbered 0..{last} in order.
1) Score each 0-10 for how good it is as the cover background:
- great (8-10): clear, sharp, attractive shot of the main character(s) of this anime, face visible, fits the news
  mood (sad news → calm/serious shot), little or no text on it
- ok (5-7): nice scene from the anime without characters, or characters far away
- bad (0-4): blurry, dark, mostly text/logo/title card, staff credits, a thumbnail with big text like "TEASER",
  a collage/screenshot of a website, unrelated to the anime, or a vertical poster crammed with text
2) For each image give "box": the bounding box of the MAIN SUBJECT that must stay visible in the crop — the faces
  and heads (plus upper body) of the main character(s); if several characters, the box around the most important
  ones (usually the largest/most central faces); if no character, the most important object/focal point.
  Format [ymin, xmin, ymax, xmax], integers 0-1000 relative to that image. Keep the box tight (no empty background).
Output ONLY JSON: {{"scores": [{{"i": 0, "score": 7, "box": [120, 300, 560, 640]}}, ...]}}"""


def _insta_vision_scores(images: list, news: str):
    """با دید تصویری Gemini: (امتیاز ۰ تا ۱۰ هر عکس برای کاور، جای سوژه‌ی اصلی هر عکس به‌صورت (x0,y0,x1,y1)
    نسبی یا None)؛ اگه نشد: (None, None)."""
    import base64
    from PIL import Image
    if not GEMINI_API_KEY or not images:
        return None, None
    parts = [{"text": INSTA_VISION_PROMPT.format(news=news[:400], n=len(images), last=len(images) - 1)}]
    for im in images:
        t = im.convert("RGB")
        t.thumbnail((512, 512), Image.LANCZOS)
        bio = io.BytesIO()
        t.save(bio, "JPEG", quality=80)
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(bio.getvalue()).decode()}})
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8000, "responseMimeType": "application/json"}}
    for model in [GEMINI_MODEL] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL][:2]:
        try:
            req = urllib.request.Request(GEMINI_CHAT_URL.format(model=model), data=json.dumps(body).encode("utf-8"),
                                         method="POST", headers={"Content-Type": "application/json",
                                                                 "x-goog-api-key": GEMINI_API_KEY})
            with urllib.request.urlopen(req, timeout=90) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
            text = "".join(p.get("text", "") for p in
                           (((payload.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []))
            data = _news_agent_parse_json(text) or {}
            scores = [None] * len(images)
            boxes = [None] * len(images)
            for entry in data.get("scores") or []:
                i = int(entry.get("i", -1))
                if 0 <= i < len(images):
                    scores[i] = float(entry.get("score") or 0)
                    boxes[i] = _insta_parse_box(entry.get("box"))
            if any(x is not None for x in scores):
                return [x if x is not None else 3.0 for x in scores], boxes
        except Exception as exc:
            logger.info("Insta vision ranking failed (%s): %s", model, exc)
    return None, None


def _insta_parse_box(raw):
    """[ymin, xmin, ymax, xmax] از ۰ تا ۱۰۰۰ (فرمت Gemini) → (x0, y0, x1, y1) نسبی؛ اگه خراب بود None."""
    try:
        y0, x0, y1, x1 = [min(1000.0, max(0.0, float(v))) / 1000.0 for v in raw]
    except Exception:
        return None
    if x1 - x0 < 0.02 or y1 - y0 < 0.02:
        return None
    return (x0, y0, x1, y1)


def _insta_frame_penalty(img, box) -> float:
    """کسر امتیاز عکسی که سوژه‌اش توی کادر ۳:۴ جا نمیشه یا زیر متن/گرادیان تیره می‌افته."""
    if not box:
        return 0.0
    seen, cy = insta_cover.subject_fit(img, box, insta_cover.PSD_SIZE)
    pen = 0.0
    if seen < 0.85:                              # شخصیت‌ها بریده میشن
        pen += (0.85 - seen) * 4
    if cy > 0.6:                                 # صورت‌ها میرن زیر تیتر
        pen += min(2.5, (cy - 0.6) * 8)
    return pen


def _insta_reorder(sess, order: list):
    """ترتیب عکس‌های جلسه عوض میشه (همه‌ی دیکشنری‌های وابسته به شماره هم جابه‌جا میشن)."""
    newpos = {old: new for new, old in enumerate(order)}
    sess["cands"] = [sess["cands"][i] for i in order]
    for key in ("images", "focus", "orig", "zoom", "up_note", "subject"):
        sess[key] = {newpos[i]: v for i, v in (sess.get(key) or {}).items() if i in newpos}
    sess["up_tried"] = {newpos[i] for i in (sess.get("up_tried") or set()) if i in newpos}
    sess["focus_manual"] = {newpos[i] for i in (sess.get("focus_manual") or set()) if i in newpos}
    if sess.get("slide2") is not None:
        sess["slide2"] = newpos.get(sess["slide2"])
    sess["idx"] = newpos.get(sess["idx"], 0)


def _insta_add_frames(uid: int):
    sess = _insta_sessions.get(uid)
    if not sess:
        return
    row = _news_v2_item_by_id(sess["item_id"])
    bot.send_message(uid, "🎞 دارم از تریلر این انیمه چند تا صحنه درمیارم… (حدود یه دقیقه)")
    try:
        frames = _insta_trailer_frames(row)
    except Exception as exc:
        logger.info("Insta trailer frames failed item=%s: %s", sess["item_id"], exc)
        bot.send_message(uid, f"❌ صحنه‌ی تریلر گرفته نشد: {str(exc)[:300]}")
        return
    if not frames:
        bot.send_message(uid, "❌ صحنه‌ی مناسبی توی تریلر پیدا نشد.")
        return
    first = len(sess["cands"])
    for i, im in enumerate(frames):
        sess["cands"].append({"kind": "frame", "ref": f"frame:{first + i}", "label": f"صحنه‌ی تریلر {i + 1}"})
        sess["images"][first + i] = im
        sess.setdefault("orig", {})[first + i] = im
        sess.setdefault("zoom", {})[first + i] = insta_cover.default_zoom(im, insta_cover.PSD_SIZE)
    # کادربندی صحنه‌ها: Gemini جای شخصیت‌ها رو پیدا می‌کنه تا برش ۳:۴ روی اون‌ها باشه
    try:
        scores, boxes = _insta_vision_scores(frames, (row["title"] if row else "") or sess.get("title", ""))
    except Exception:
        scores, boxes = None, None
    for i in range(len(frames)):
        if boxes and boxes[i]:
            sess.setdefault("subject", {})[first + i] = boxes[i]
        if scores:
            sess["cands"][first + i]["label"] += f" ⭐{scores[i]:.0f}"
    sess["idx"] = first
    if scores:                                   # اول بهترین صحنه
        sess["idx"] = first + max(range(len(frames)),
                                  key=lambda i: scores[i] - _insta_frame_penalty(frames[i], boxes[i] if boxes else None))
    sess["ready"] = False
    _insta_show(uid)


INSTA_HI_COLORS = [("زرد", (251, 221, 27)), ("نارنجی", (255, 145, 30)), ("صورتی", (255, 95, 170)),
                   ("فیروزه‌ای", (60, 220, 210)), ("قرمز", (255, 70, 70)), ("سبز", (100, 220, 120)),
                   ("آبی", (90, 170, 255)), ("بنفش", (185, 125, 255)), ("سفید", (255, 255, 255))]
INSTA_SIZE_STEP = 0.08          # هر بار ۸٪ بزرگ‌تر/کوچیک‌تر
INSTA_MOVE_STEP = 20            # هر بار ۲۰ پیکسل (کادر ۱۴۴۰) بالا/پایین


def _insta_text_markup(sess):
    """منوی «🔤 تنظیم متن»: اندازه/جای تیتر و زیرنویس و رنگ بخش رنگی تیتر (هم پیش‌نمایش هم فتوشاپ)."""
    iid = sess["item_id"]
    a = insta_cover.adj_of(sess.get("adj"))
    hc = tuple(a["hc"]) if a["hc"] else insta_cover.YELLOW
    cname = next((n for n, c in INSTA_HI_COLORS if c == hc), "زرد")
    pct = lambda k: f"{round(k * 100)}٪"
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(InlineKeyboardButton("🔠 تیتر بزرگ‌تر", callback_data=f"ig:tsp:{iid}"),
           InlineKeyboardButton(f"🔠 تیتر کوچیک‌تر ({pct(a['ts'])})", callback_data=f"ig:tsm:{iid}"))
    kb.row(InlineKeyboardButton("⬆️ تیتر بالاتر", callback_data=f"ig:tyu:{iid}"),
           InlineKeyboardButton("⬇️ تیتر پایین‌تر", callback_data=f"ig:tyd:{iid}"))
    kb.row(InlineKeyboardButton("🔡 زیرنویس بزرگ‌تر", callback_data=f"ig:ssp:{iid}"),
           InlineKeyboardButton(f"🔡 زیرنویس کوچیک‌تر ({pct(a['ss'])})", callback_data=f"ig:ssm:{iid}"))
    kb.row(InlineKeyboardButton("⬆️ زیرنویس بالاتر", callback_data=f"ig:syu:{iid}"),
           InlineKeyboardButton("⬇️ زیرنویس پایین‌تر", callback_data=f"ig:syd:{iid}"))
    kb.row(InlineKeyboardButton(f"🎨 رنگ بخش رنگی: {cname} (بزن عوض شه)", callback_data=f"ig:hcn:{iid}"))
    kb.row(InlineKeyboardButton("↩️ متن مثل قالب", callback_data=f"ig:tres:{iid}"),
           InlineKeyboardButton("✅ تموم، برگشت", callback_data=f"ig:tmenu:{iid}"))
    return kb


def _insta_markup(sess):
    iid = sess["item_id"]
    if sess.get("txtmenu") and not sess.get("ready"):
        return _insta_text_markup(sess)
    kb = InlineKeyboardMarkup(row_width=2)
    n = len(sess["cands"])
    if n > 1:
        kb.row(InlineKeyboardButton("◀️ عکس قبلی", callback_data=f"ig:prev:{iid}"),
               InlineKeyboardButton(f"🖼 عکس بعدی ({sess['idx'] + 1}/{n})", callback_data=f"ig:next:{iid}"))
        kb.row(InlineKeyboardButton(f"🗂 دیدن همه‌ی {n} عکس و انتخاب", callback_data=f"ig:gal:{iid}"))
    img = sess["images"].get(sess["idx"])
    over = insta_cover.overflow(img, insta_cover.PSD_SIZE) if img is not None and not sess.get("ready") else ""
    zoom = (sess.get("zoom", {}).get(sess["idx"]) or insta_cover.default_zoom(img, insta_cover.PSD_SIZE)) if img is not None else ""
    if zoom == "original":                               # اندازه‌ی اصلی: جابه‌جایی فقط اگه عکس از کادر بزرگ‌تره
        W0, H0 = insta_cover.PSD_SIZE
        sw, sh = insta_cover.shown_size(img, insta_cover.PSD_SIZE)
        over = "x" if sw > W0 else ("y" if sh > H0 else "")
    if over == "x":
        kb.row(InlineKeyboardButton("⬅️ برش به چپ", callback_data=f"ig:left:{iid}"),
               InlineKeyboardButton("➡️ برش به راست", callback_data=f"ig:right:{iid}"))
    elif over == "y":
        kb.row(InlineKeyboardButton("⬆️ برش بالاتر", callback_data=f"ig:up:{iid}"),
               InlineKeyboardButton("⬇️ برش پایین‌تر", callback_data=f"ig:down:{iid}"))
    if not sess.get("ready"):
        kb.row(InlineKeyboardButton("🎨 رنگی کن" if sess["bw"] else "⚫️ سیاه‌وسفید", callback_data=f"ig:bw:{iid}"),
               InlineKeyboardButton("✏️ ویرایش متن", callback_data=f"ig:text:{iid}"))
        kb.row(InlineKeyboardButton("🔤 اندازه، جا و رنگ متن", callback_data=f"ig:tmenu:{iid}"))
    if sess["cands"][sess["idx"]]["kind"] == "upload":   # فایل آپلودی خودش کاور کامل بود؟
        kb.row(InlineKeyboardButton("🎨 متن و گرادیان بات رو بذار" if sess.get("ready")
                                    else "🧾 این فایل خودش کاور کامله (دست نزن)", callback_data=f"ig:ready:{iid}"))
    extra = [InlineKeyboardButton("🎞 صحنه از تریلر", callback_data=f"ig:frames:{iid}")]
    idx = sess["idx"]
    if sess.get("orig", {}).get(idx) is not None and sess["images"].get(idx) is not sess["orig"][idx]:
        extra.append(InlineKeyboardButton("↩️ عکس اصلی (بدون Gemini)", callback_data=f"ig:orig:{iid}"))
    kb.row(*extra)
    if not sess.get("ready"):
        s2 = sess.get("slide2")
        if s2 == sess["idx"]:
            kb.row(InlineKeyboardButton("✅ این عکس اسلاید دومه (بزن که برداشته بشه)", callback_data=f"ig:s2:{iid}"))
        else:
            kb.row(InlineKeyboardButton("➕ این عکس بشه اسلاید دوم", callback_data=f"ig:s2:{iid}"))
    kb.row(InlineKeyboardButton("📤 عکس یا PSD خودم", callback_data=f"ig:upload:{iid}"))
    save_label = ("🖌 ساخت در فتوشاپ" if _insta_ps_template()[0] and not sess.get("ready")
                  else "✅ ذخیره و دریافت فایل")
    kb.row(InlineKeyboardButton(save_label, callback_data=f"ig:save:{iid}"),
           InlineKeyboardButton("❌ بستن", callback_data=f"ig:close:{iid}"))
    return kb


def _insta_gallery(uid: int):
    """همه‌ی عکس‌های پیدا شده به‌صورت آلبوم شماره‌دار + دکمه‌ی شماره‌ها؛ ادمین مستقیم انتخاب می‌کنه (به‌جای قبلی/بعدی)."""
    from telebot.types import InputMediaPhoto
    sess = _insta_sessions.get(uid)
    n = len(sess["cands"])
    bot.send_message(uid, f"⏳ دارم {n} تا عکس رو آماده می‌کنم…")
    thumbs = []
    for i in range(n):
        img = sess["images"].get(i)
        if img is None:
            try:
                img = _insta_load(sess["cands"][i])
                sess["images"][i] = img
                sess.setdefault("orig", {})[i] = img
            except Exception as exc:
                logger.info("Insta gallery load %s failed: %s", i, exc)
                continue
        t = img.convert("RGB")
        t.thumbnail((720, 720), Image.LANCZOS)
        bio = io.BytesIO()
        t.save(bio, "JPEG", quality=82)
        bio.seek(0)
        label = re.sub(r"\s*⭐.*$", "", sess["cands"][i]["label"])
        thumbs.append((i, bio, f"{i + 1}) {label} — {img.width}×{img.height}"))
    for k in range(0, len(thumbs), 10):
        chunk = thumbs[k:k + 10]
        try:
            bot.send_media_group(uid, [InputMediaPhoto(b, caption=c) for _i, b, c in chunk])
        except Exception as exc:
            logger.info("Insta gallery album failed: %s", exc)
    kb = InlineKeyboardMarkup(row_width=5)
    kb.add(*[InlineKeyboardButton(str(i + 1), callback_data=f"ig:p{i}:{sess['item_id']}") for i, _b, _c in thumbs])
    bot.send_message(uid, "👆 شماره‌ی عکسی که می‌خوای رو بزن تا کاور با همون ساخته بشه.\n"
                          "عکس خوبی نبود؟ «🎞 صحنه از تریلر» یا «📤 عکس یا PSD خودم».", reply_markup=kb)


def _insta_status_text(sess) -> str:
    cand = sess["cands"][sess["idx"]]
    if sess.get("ready"):
        return f"🎨 کاور آماده‌ی خودت (بدون تغییر) — خبر #{sess['item_id']}\nاگه اوکیه «✅ ذخیره» رو بزن."
    who = "✅ متن با AI نوشته شد" if sess.get("ai") else "⚠️ AI در دسترس نبود؛ متن ساده گذاشتم، «✏️ ویرایش متن» رو بزن"
    img = sess["images"].get(sess["idx"])
    low = ""
    note = sess.get("up_note", {}).get(sess["idx"])
    if note:
        low += f"\n{note}"
    if img is not None:
        zoom = sess.get("zoom", {}).get(sess["idx"]) or "cover"
        need_scale = insta_cover.upscale_needed(img, insta_cover.PSD_SIZE, zoom)
        if need_scale > 1.25:
            low = (f"\n⚠️ این عکس کوچیکه ({img.width}x{img.height}) و {need_scale:.1f} برابر بزرگ میشه، پس کمی تار درمیاد؛ "
                   "اگه نسخه‌ی باکیفیت‌ترش رو داری، با «📤 عکس یا PSD خودم» بفرست.")
    s2 = sess.get("slide2")
    if s2 is not None and s2 < len(sess["cands"]):
        if s2 == sess["idx"]:
            low += "\n📑 اسلاید دوم همین عکس کاوره، پس جدا ذخیره نمیشه (یه عکس دیگه رو اسلاید دوم کن)"
        else:
            low += f"\n📑 اسلاید دوم: {sess['cands'][s2]['label']} (بعد از کاور، خود عکس کامل)"
    ps = ("\n🖌 این پیش‌نمایش سریعه؛ با دکمه‌ی «🖌 ساخت در فتوشاپ» پست از روی قالب PSD خودت توی فتوشاپ ساخته میشه و بعد از چک کردنت خروجی می‌گیره."
          if _insta_ps_template()[0] else "")
    return (f"🎨 کاور اینستاگرام — خبر #{sess['item_id']}\n{who}\n"
            f"🖼 {cand['label']}{' (سیاه‌وسفید)' if sess['bw'] else ''}{low}{ps}")


def _insta_show(uid: int, new_message: bool = False):
    """کاور رو می‌سازه و پیش‌نمایش رو می‌فرسته یا پیام قبلی رو عوض می‌کنه."""
    from telebot.types import InputMediaPhoto
    sess = _insta_sessions.get(uid)
    if not sess:
        return
    tried = 0
    while True:
        try:
            cover = _insta_render(sess)
            break
        except FileNotFoundError as exc:           # فونت نیست
            bot.send_message(uid, f"❌ {exc}\nفونت‌ها رو با /insta_setup بفرست.")
            return
        except Exception as exc:
            logger.info("Insta candidate failed item=%s idx=%s: %s", sess["item_id"], sess["idx"], exc)
            sess["cands"].pop(sess["idx"])
            sess["images"] = {}
            sess["focus"] = {}
            sess["subject"] = {}
            sess["focus_manual"] = set()
            tried += 1
            if not sess["cands"]:
                bot.send_message(uid, "❌ هیچ عکسی از این خبر قابل دانلود نبود. «📤 عکس یا PSD خودم» رو بزن و یه عکس بفرست.",
                                 reply_markup=_insta_upload_only_markup(sess["item_id"]))
                return
            sess["idx"] %= len(sess["cands"])
    bio = io.BytesIO()
    cover.save(bio, "JPEG", quality=92)
    bio.seek(0)
    bio.name = "cover.jpg"
    sess["last"] = cover
    caption = _insta_status_text(sess)
    kb = _insta_markup(sess)
    if not new_message and sess.get("msg_id"):
        try:
            bot.edit_message_media(InputMediaPhoto(bio, caption=caption), chat_id=uid,
                                   message_id=sess["msg_id"], reply_markup=kb)
            _insta_persist(uid, sess)
            return
        except Exception as exc:
            logger.info("Insta preview edit failed, sending new: %s", exc)
            bio.seek(0)
    msg = bot.send_photo(uid, bio, caption=caption, reply_markup=kb)
    sess["msg_id"] = msg.message_id
    _insta_persist(uid, sess)


_INSTA_STORE = os.path.join(DATA_DIR, "insta_sessions.json")
_INSTA_KEEP_DIR = os.path.join(DATA_DIR, "insta_keep")
_INSTA_FIELDS = ("item_id", "cands", "idx", "focus", "zoom", "title", "subtitle", "tag", "caption", "ai", "bw",
                 "msg_id", "slide2", "adj", "subject", "focus_manual", "ready", "up_note", "ps_doc")
_insta_store_lock = threading.Lock()


def _insta_persist(uid: int, sess):
    """حالت سبک جلسه روی دیسک (بدون خود عکس‌ها) تا بعد از ری‌استارت بات یا ساختن پست یه خبر دیگه،
    دکمه‌های پیش‌نمایش قبلی هم کار کنن. صحنه‌ی تریلر/عکس آپلودی یه بار به‌صورت فایل نگه داشته میشه."""
    try:
        cands = []
        for i, c in enumerate(sess.get("cands") or []):
            c = dict(c)
            if c.get("kind") in ("frame", "upload"):
                im = (sess.get("orig") or {}).get(i) or (sess.get("images") or {}).get(i)
                os.makedirs(_INSTA_KEEP_DIR, exist_ok=True)
                path = os.path.join(_INSTA_KEEP_DIR, f"{sess['item_id']}_{hashlib.md5(c['ref'].encode()).hexdigest()[:10]}.png")
                if im is None and not os.path.exists(path):
                    continue
                if not os.path.exists(path):
                    im.save(path)
                c = {"kind": "file", "ref": path, "label": c.get("label", "")}
            cands.append(c)
        if len(cands) != len(sess.get("cands") or []):
            return                                   # اندیس‌ها جابه‌جا میشدن؛ این بار ذخیره نمیشه
        data = {}
        for k in _INSTA_FIELDS:
            v = sess.get(k)
            if isinstance(v, set):
                v = sorted(v)
            elif isinstance(v, dict):
                v = {str(a): (list(b) if isinstance(b, tuple) else b) for a, b in v.items()}
            data[k] = v
        data["cands"] = cands
        data["saved"] = time.time()
        with _insta_store_lock:
            try:
                with open(_INSTA_STORE, encoding="utf-8") as fh:
                    store = json.load(fh)
            except Exception:
                store = {}
            store[f"{uid}:{sess['item_id']}"] = data
            # فقط ۱۵ تای آخر و ۳ روز اخیر
            keep = sorted(store.items(), key=lambda kv: kv[1].get("saved", 0), reverse=True)[:15]
            store = {k: v for k, v in keep if time.time() - v.get("saved", 0) < 3 * 86400}
            tmp = _INSTA_STORE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(store, fh, ensure_ascii=False, default=str)
            os.replace(tmp, _INSTA_STORE)
    except Exception as exc:
        logger.info("Insta session persist failed: %s", exc)


def _insta_restore(uid: int, item_id: int):
    """جلسه‌ی ذخیره‌شده‌ی همین خبر رو برمی‌گردونه (عکس‌ها دوباره دانلود میشن)؛ نبود → None."""
    try:
        with _insta_store_lock, open(_INSTA_STORE, encoding="utf-8") as fh:
            data = json.load(fh).get(f"{uid}:{item_id}")
    except Exception:
        return None
    if not data or not data.get("cands"):
        return None
    sess = {k: data.get(k) for k in _INSTA_FIELDS}
    for k in ("focus", "zoom", "subject", "up_note"):
        sess[k] = {int(a): (tuple(b) if k == "focus" and isinstance(b, list) else b)
                   for a, b in (data.get(k) or {}).items()}
    sess["focus_manual"] = set(data.get("focus_manual") or [])
    sess["up_tried"] = set()
    sess["images"], sess["orig"] = {}, {}
    sess["touched"] = True
    sess["idx"] = min(int(sess.get("idx") or 0), len(sess["cands"]) - 1)
    with _insta_lock:
        _insta_sessions[uid] = sess
    logger.info("Insta session restored uid=%s item=%s", uid, item_id)
    return sess


def _insta_upload_only_markup(item_id: int):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📤 عکس یا PSD خودم", callback_data=f"ig:upload:{item_id}"))
    return kb


def _insta_start(item_id: int, uid: int):
    row = _news_v2_item_by_id(item_id)
    if not row:
        bot.send_message(uid, "❌ خبر پیدا نشد.")
        return
    missing = insta_cover.missing_fonts(INSTA_FONT_DIRS)
    if missing:
        bot.send_message(uid, "❌ فونت‌های کاور پیدا نشدن: " + "، ".join(missing) +
                              "\nبا /insta_setup فایل‌های فونت رو بفرست (یا بذارشون توی پوشه‌ی fonts کنار بات).")
        return
    bot.send_message(uid, f"⏳ ساخت کاور اینستاگرام برای خبر #{item_id}… (جمع کردن عکس‌ها و نوشتن تیتر)")
    text = _insta_ai_text(row)
    # همه‌ی عکس‌ها از اول دانلود میشن تا مرتب بشن: صحنه/افقی اول (مناسب کاور)، پوسترهای عمودی آخر (اسلاید دوم)
    loaded = []
    from concurrent.futures import ThreadPoolExecutor

    def _try_load(cand):
        try:
            return cand, _insta_load(cand)
        except Exception:
            return cand, None
    with ThreadPoolExecutor(max_workers=6) as pool:     # دانلود هم‌زمان عکس‌ها
        loaded = [(c, im) for c, im in pool.map(_try_load, _insta_candidates(row)) if im is not None]
    loaded.sort(key=_insta_rank)
    sess = {
        "item_id": item_id, "cands": [c for c, _ in loaded], "idx": 0,
        "images": {i: im for i, (_, im) in enumerate(loaded)}, "focus": {},
        "orig": {i: im for i, (_, im) in enumerate(loaded)},
        "zoom": {i: insta_cover.default_zoom(im, insta_cover.PSD_SIZE) for i, (_, im) in enumerate(loaded)},
        "title": text["title"], "subtitle": text["subtitle"], "tag": text["tag"],
        "caption": text["caption"], "ai": text["ai"], "bw": text["mood"] == "sad", "msg_id": None,
        "slide2": next((i for i, (_, im) in enumerate(loaded) if i != 0 and _insta_is_poster(im)), None),
        "touched": False,
    }
    for i, (c, _) in enumerate(loaded):
        if _insta_is_poster(sess["images"][i]) and "پوستر" not in c["label"]:
            c["label"] += " (پوستر)"
    with _insta_lock:
        _insta_sessions[uid] = sess
    # صحنه‌ی تریلر فقط با دکمه‌ی «🎞 صحنه از تریلر»؛ اینجا فقط Gemini عکس‌های خود خبر رو مرتب می‌کنه
    threading.Thread(target=_insta_rank_with_vision, args=(uid, item_id), daemon=True).start()
    if not sess["cands"]:
        bot.send_message(uid, "⚠️ این خبر عکسی نداره. یه عکس (یا فایل PSD) برای پس‌زمینه بفرست:",
                         reply_markup=_insta_upload_only_markup(item_id))
        return
    _insta_show(uid, new_message=True)


def _insta_rank(cand_img):
    """ترتیب اولیه‌ی عکس‌ها برای کاور: پوستر عمودی آخر؛ بین بقیه هر چی بزرگ‌تر/باکیفیت‌تر، جلوتر.
    (بعدش Gemini با دیدن خود عکس‌ها دوباره مرتبشون می‌کنه)"""
    _cand, img = cand_img
    small = max(insta_cover.PSD_SIZE[0] / img.width, (insta_cover.PSD_SIZE[1] * 0.6) / img.height)
    return (1 if _insta_is_poster(img) else 0, round(small, 1))


def _insta_is_poster(img) -> bool:
    """عکس عمودی (مثل پوستر/کی‌ویژوال) → برای اسلاید دوم مناسب‌تره تا کاور."""
    return img is not None and img.width / img.height < 0.9


def _insta_rank_with_vision(uid: int, item_id: int, note: str = "") -> bool:
    """Gemini همه‌ی عکس‌ها رو می‌بینه و بهترین‌ها برای کاور اول میان (پوسترها برای اسلاید دوم می‌مونن).
    اگه ادمین هنوز دست نزده بود، کاور با بهترین عکس دوباره ساخته میشه. خروجی: انجام شد؟"""
    sess = _insta_sessions.get(uid)
    if not sess or sess["item_id"] != item_id or not sess["cands"]:
        return False
    row = _news_v2_item_by_id(item_id)
    news = f"{row['title'] or ''} — {sess.get('title', '')}" if row else sess.get("title", "")
    n = len(sess["cands"])
    cands0 = list(sess["cands"])
    imgs = [sess["images"].get(i) for i in range(n)]
    if any(im is None for im in imgs):
        return False
    scores, boxes = _insta_vision_scores(imgs, news)
    sess = _insta_sessions.get(uid)
    if not scores or not sess or sess["item_id"] != item_id or len(sess["cands"]) != n:
        return False
    if sess.get("touched") or n < 2:
        # ادمین خودش مشغوله (یا فقط یه عکس هست): ترتیب عوض نمیشه، فقط کادربندی (جای سوژه) اضافه میشه
        if any(sess["cands"][i] is not c for i, c in enumerate(cands0)):
            return False
        before = sess["focus"].get(sess["idx"])
        for i, b in enumerate(boxes):
            if b:
                sess.setdefault("subject", {})[i] = b
        idx = sess["idx"]
        if (boxes[idx] and sess["images"].get(idx) is not None and idx not in (sess.get("focus_manual") or set()) and not sess.get("ready")
                and insta_cover.focus_for_subject(sess["images"][idx], boxes[idx], insta_cover.PSD_SIZE) != before):
            _insta_show(uid)
        return False
    for i, b in enumerate(boxes):
        if b:
            sess.setdefault("subject", {})[i] = b
    # پوستر عمودی کمی عقب‌تر (جاش اسلاید دومه)، عکس خیلی کوچیک هم کمی عقب‌تر؛
    # عکسی که شخصیت‌هاش توی کادر ۳:۴ بریده میشن یا زیر متن می‌افتن هم عقب‌تر
    def key(i):
        im = imgs[i]
        penalty = (2.5 if _insta_is_poster(im) else 0) + (1.5 if im.width < 800 else 0)
        if not _insta_is_poster(im):
            penalty += _insta_frame_penalty(im, boxes[i])
        return -(scores[i] - penalty)
    order = sorted(range(n), key=key)
    _insta_reorder(sess, order)
    sess["idx"] = 0
    # اسلاید دوم: بهترین پوستری که خودش کاور نیست
    sess["slide2"] = next((i for i in range(1, n) if _insta_is_poster(sess["images"][i])), None)
    best = scores[order[0]]
    for new, old in enumerate(order):
        sess["cands"][new]["label"] = re.sub(r"\s*⭐.*$", "", sess["cands"][new]["label"]) + f" ⭐{scores[old]:.0f}"
    bot.send_message(uid, (note + "؛ " if note else "") +
                     f"🤖 Gemini عکس‌ها رو دید و مرتب کرد؛ کاور با بهترینش ساخته شد (امتیاز {best:.0f} از ۱۰).")
    _insta_show(uid)
    return True


def _insta_start_safe(item_id: int, uid: int):
    try:
        _insta_start(item_id, uid)
    except Exception as exc:
        logger.exception("Insta cover failed item=%s", item_id)
        try:
            bot.send_message(uid, f"❌ ساخت کاور انجام نشد: {str(exc)[:300]}")
        except Exception:
            pass


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("nv2_insta:"))
def insta_start_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    item_id = int(call.data.split(":", 1)[1])
    bot.answer_callback_query(call.id, "🎨 کاور توی خصوصی ساخته میشه…")
    threading.Thread(target=_insta_start_safe, args=(item_id, call.from_user.id),
                     daemon=True, name=f"insta-{item_id}").start()


@bot.message_handler(commands=["insta"])
def insta_command(message):
    """/insta 123 — ساخت کاور اینستاگرام برای خبر شماره‌ی ۱۲۳."""
    if message.from_user.id not in ADMINS:
        return
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].lstrip("#").isdigit():
        bot.send_message(message.chat.id, "شماره‌ی خبر رو بنویس، مثلاً:\n/insta 123\n"
                                          "(یا روی کارت خبر توی آرشیو «🎨 پست اینستاگرام» رو بزن)")
        return
    threading.Thread(target=_insta_start_safe, args=(int(parts[1].lstrip("#")), message.from_user.id),
                     daemon=True).start()


def _insta_action(uid: int, action: str):
    """کارهای دکمه‌های پیش‌نمایش (توی ترد جدا چون دانلود/رندر طول می‌کشه)."""
    sess = _insta_sessions.get(uid)
    sess["touched"] = True
    try:
        if action in ("next", "prev"):
            sess["idx"] = (sess["idx"] + (1 if action == "next" else -1)) % len(sess["cands"])
            sess["ready"] = False                   # «کاور آماده» فقط مال همون فایل آپلودی بود
        elif action in ("left", "right", "up", "down"):
            fx, fy = sess["focus"].get(sess["idx"]) or (0.5, 0.0)
            step = INSTA_FOCUS_STEP
            fx += {"left": -step, "right": step}.get(action, 0)
            fy += {"up": -step, "down": step}.get(action, 0)
            sess["focus"][sess["idx"]] = (min(1.0, max(0.0, fx)), min(1.0, max(0.0, fy)))
            sess.setdefault("focus_manual", set()).add(sess["idx"])
        elif action == "bw":
            sess["bw"] = not sess["bw"]
        elif action == "ready":
            sess["ready"] = not sess.get("ready")
        elif action == "s2":
            sess["slide2"] = None if sess.get("slide2") == sess["idx"] else sess["idx"]
        elif action == "zoom":
            idx = sess["idx"]
            img = sess["images"].get(idx)
            cur = sess.setdefault("zoom", {}).get(idx) or (insta_cover.default_zoom(img, insta_cover.PSD_SIZE)
                                                          if img is not None else "cover")
            order = list(insta_cover.ZOOMS)
            sess["zoom"][idx] = order[(order.index(cur) + 1) % len(order)] if cur in order else order[0]
        elif action == "tmenu":
            sess["txtmenu"] = not sess.get("txtmenu")
        elif action in ("tsp", "tsm", "ssp", "ssm", "tyu", "tyd", "syu", "syd", "hcn", "tres"):
            a = insta_cover.adj_of(sess.get("adj"))
            if action == "tres":
                a = dict(insta_cover.ADJ_DEFAULT)
            elif action in ("tsp", "tsm", "ssp", "ssm"):
                key = "ts" if action[0] == "t" else "ss"
                a[key] = round(min(1.6, max(0.6, a[key] + (INSTA_SIZE_STEP if action[2] == "p" else -INSTA_SIZE_STEP))), 2)
            elif action in ("tyu", "tyd", "syu", "syd"):
                key = "ty" if action[0] == "t" else "sy"
                a[key] = max(-400, min(200, a[key] + (-INSTA_MOVE_STEP if action[2] == "u" else INSTA_MOVE_STEP)))
            else:
                cur = tuple(a["hc"]) if a["hc"] else insta_cover.YELLOW
                cols = [c for _n, c in INSTA_HI_COLORS]
                a["hc"] = cols[(cols.index(cur) + 1) % len(cols)] if cur in cols else cols[0]
            sess["adj"] = a
        elif action == "gal":
            return _insta_gallery(uid)
        elif re.fullmatch(r"p\d+", action):               # از آلبوم «همه‌ی عکس‌ها»
            n = int(action[1:])
            if 0 <= n < len(sess["cands"]):
                sess["idx"] = n
                sess["ready"] = False
        elif action == "orig":
            idx = sess["idx"]
            if sess.get("orig", {}).get(idx) is not None:
                sess["images"][idx] = sess["orig"][idx]
                sess.setdefault("up_note", {})[idx] = "↩️ عکس اصلی (بدون افزایش کیفیت)"
        _insta_show(uid)
    except Exception as exc:
        logger.exception("Insta action %s failed", action)
        bot.send_message(uid, f"❌ انجام نشد: {str(exc)[:300]}")


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("ig:"))
def insta_button_callback(call):
    uid = call.from_user.id
    if uid not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    _, action, item_id = call.data.split(":", 2)
    item_id = int(item_id)
    sess = _insta_sessions.get(uid)
    if action not in ("upload", "close") and (not sess or sess["item_id"] != item_id):
        # بات ری‌استارت شده یا وسطش پست یه خبر دیگه ساخته شده → همون جلسه از روی دیسک برمی‌گرده
        sess = _insta_restore(uid, item_id)
        if sess and call.message:
            sess["msg_id"] = call.message.message_id
    if sess and sess["item_id"] == item_id:
        sess["touched"] = True                       # بعد از هر دکمه، ترتیب/عکس کاور خودکار عوض نمیشه
    if action not in ("upload", "close") and (not sess or sess["item_id"] != item_id):
        bot.answer_callback_query(call.id, "این پیش‌نمایش پیدا نشد؛ دوباره «🎨 پست اینستاگرام» رو بزن.", show_alert=True)
        return
    if action == "close":
        if sess and sess["item_id"] == item_id:
            _insta_sessions.pop(uid, None)
        bot.answer_callback_query(call.id, "بسته شد.")
        try:
            bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        return
    if action == "text":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            uid,
            "✏️ متن جدید رو این‌طوری بفرست (هر مورد یه خط):\n"
            "۱) تیتر — اسم انیمه رو داخل [ ] بنویس که زرد بشه\n"
            "۲) زیرنویس (اگه نمی‌خوای، فقط - بذار)\n"
            "۳) تگ بالای تیتر (اختیاری)\n\n👇 متن فعلی (کپی کن و عوض کن):",
        )
        bot.send_message(uid, f"{sess['title']}\n{sess['subtitle'] or '-'}\n{sess['tag']}")
        bot.register_next_step_handler(msg, insta_text_finish)
        return
    if action == "upload":
        bot.answer_callback_query(call.id)
        if not sess or sess["item_id"] != item_id:
            row = _news_v2_item_by_id(item_id)
            if not row:
                bot.send_message(uid, "❌ خبر پیدا نشد.")
                return
            text = _insta_ai_text(row)
            sess = {"item_id": item_id, "cands": [], "idx": 0, "images": {}, "focus": {},
                    "title": text["title"], "subtitle": text["subtitle"], "tag": text["tag"],
                    "caption": text["caption"], "ai": text["ai"], "bw": text["mood"] == "sad", "msg_id": None}
            _insta_sessions[uid] = sess
        msg = bot.send_message(uid, "📤 عکس یا فایل PSD رو بفرست.\n"
                                    "برای کیفیت بهتر به‌صورت «فایل» بفرست (نه عکس فشرده). PSD رو اگه آپلود نشد zip کن.")
        bot.register_next_step_handler(msg, insta_upload_finish)
        return
    if action == "frames":
        bot.answer_callback_query(call.id, "🎞")
        threading.Thread(target=_insta_add_frames, args=(uid,), daemon=True).start()
        return
    if action in ("psout", "psdrop"):
        bot.answer_callback_query(call.id, "⏳")
        threading.Thread(target=_insta_ps_finish, args=(uid, action == "psdrop"), daemon=True).start()
        return
    if action == "save":
        bot.answer_callback_query(call.id, "💾 در حال ذخیره…")
        threading.Thread(target=_insta_save, args=(uid,), daemon=True).start()
        return
    bot.answer_callback_query(call.id, "⏳")
    threading.Thread(target=_insta_action, args=(uid, action), daemon=True).start()


def insta_text_finish(message):
    uid = message.from_user.id
    sess = _insta_sessions.get(uid)
    if not sess:
        return
    if message.text == BACK_MAIN:
        show_news_admin_menu(message.chat.id, uid)
        return
    lines = [ln.strip() for ln in (message.text or "").split("\n") if ln.strip()]
    if not lines or not re.search(r"[؀-ۿA-Za-z]", lines[0]):
        msg = bot.send_message(uid, "❌ تیتر خالیه. دوباره بفرست:")
        bot.register_next_step_handler(msg, insta_text_finish)
        return
    sess["title"] = lines[0][:200]
    if len(lines) > 1:
        sess["subtitle"] = "" if lines[1] in ("-", "—", "_") else lines[1][:80]
    if len(lines) > 2:
        sess["tag"] = lines[2][:20]
    sess["ai"] = True
    threading.Thread(target=_insta_action, args=(uid, "refresh"), daemon=True).start()


def _insta_file_from_message(message):
    """(bytes, اسم فایل) از عکس یا فایل ارسالی؛ zip هم باز میشه."""
    import zipfile
    if getattr(message, "photo", None):
        info = bot.get_file(message.photo[-1].file_id)
        return bot.download_file(info.file_path), "photo.jpg"
    doc = getattr(message, "document", None)
    if not doc:
        return None, ""
    if (doc.file_size or 0) > 19_500_000:
        raise RuntimeError("فایل بزرگ‌تر از ۲۰ مگه (محدودیت دانلود بات تلگرام). یه JPG/PNG با کیفیت بالا بفرست.")
    data = bot.download_file(bot.get_file(doc.file_id).file_path)
    name = (doc.file_name or "file").lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            inner = [n for n in zf.namelist() if n.lower().endswith((".psd", ".png", ".jpg", ".jpeg", ".webp"))]
            if not inner:
                raise RuntimeError("توی zip عکس یا PSD نبود.")
            return zf.read(inner[0]), inner[0].lower()
    return data, name


def insta_upload_finish(message):
    uid = message.from_user.id
    sess = _insta_sessions.get(uid)
    if not sess:
        return
    if message.text == BACK_MAIN:
        show_news_admin_menu(message.chat.id, uid)
        return
    try:
        data, name = _insta_file_from_message(message)
        if not data:
            msg = bot.send_message(uid, "❌ عکس یا فایل نبود. دوباره بفرست (یا دکمه‌ی بازگشت):")
            bot.register_next_step_handler(msg, insta_upload_finish)
            return
        from PIL import Image
        img = Image.open(io.BytesIO(data))          # PSD هم باز میشه (نسخه‌ی یکی‌شده‌ی لایه‌ها)
        img.load()
        img = img.convert("RGB")
    except Exception as exc:
        bot.send_message(uid, f"❌ این فایل باز نشد: {str(exc)[:200]}\n"
                              "اگه PSD بود، توی فتوشاپ موقع ذخیره «Maximize Compatibility» روشن باشه، یا JPG/PNG بفرست.")
        return
    sess["cands"].insert(0, {"kind": "upload", "ref": f"upload:{time.time()}", "label": "عکس خودت"})
    for key in ("images", "focus", "orig", "zoom", "up_note", "subject"):   # بقیه‌ی عکس‌ها یه خونه جلو میرن
        sess[key] = {i + 1: v for i, v in (sess.get(key) or {}).items()}
    sess["focus_manual"] = {i + 1 for i in (sess.get("focus_manual") or set())}
    sess["up_tried"] = {i + 1 for i in (sess.get("up_tried") or set())}
    if sess.get("slide2") is not None:
        sess["slide2"] += 1
    sess["images"][0] = img
    sess["orig"][0] = img
    sess["zoom"][0] = insta_cover.default_zoom(img, insta_cover.PSD_SIZE)
    sess["touched"] = True
    sess["idx"] = 0
    sess["ready"] = False
    bot.send_message(uid, f"📥 فایل رسید ({name})؛ کاور با همین عکس ساخته میشه…")
    threading.Thread(target=lambda: _insta_show(uid, new_message=True), daemon=True).start()


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("igup:"))
def insta_upload_mode_callback(call):
    uid = call.from_user.id
    sess = _insta_sessions.get(uid)
    if uid not in ADMINS or not sess:
        bot.answer_callback_query(call.id, "این پیام قدیمیه.", show_alert=True)
        return
    sess["ready"] = call.data.split(":")[1] == "ready"
    bot.answer_callback_query(call.id, "⏳")
    try:
        bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
    except Exception:
        pass
    threading.Thread(target=lambda: _insta_show(uid, new_message=True), daemon=True).start()


def _insta_save_slide2(uid: int, sess, cover_jpg: str, size=None):
    """اسلاید دوم کاروسل: پوستر کامل (بدون برش) با پس‌زمینه‌ی مات همون پوستر؛ کنار کاور ذخیره میشه."""
    idx = sess.get("slide2")
    if idx is None or idx == sess["idx"] or sess["images"].get(idx) is None:
        return
    img = sess.get("orig", {}).get(idx) or sess["images"][idx]
    path = os.path.splitext(cover_jpg)[0] + "_2.jpg"
    try:
        insta_cover.poster_slide(img, size or insta_cover.PSD_SIZE).save(path, "JPEG", quality=95, subsampling=0)
        with open(path, "rb") as fh:
            bot.send_document(uid, fh, visible_file_name=os.path.basename(path),
                              caption=f"📑 اسلاید دوم (پوستر):\n{path}")
    except Exception as exc:
        logger.exception("Insta slide 2 failed")
        bot.send_message(uid, f"⚠️ اسلاید دوم ساخته نشد: {str(exc)[:200]}")


def _insta_ps_finish(uid: int, drop: bool):
    sess = _insta_sessions.get(uid)
    doc = (sess or {}).get("ps_doc")
    if not doc:
        bot.send_message(uid, "❌ پستی توی فتوشاپ منتظر خروجی نیست.")
        return
    where = doc["jpg"]
    try:
        if drop:
            if doc.get("remote"):
                _agent_call("drop", docname=doc["stem"])
            else:
                insta_photoshop.drop(doc["stem"])
            sess.pop("ps_doc", None)
            bot.send_message(uid, "🗑 پست توی فتوشاپ بسته شد (چیزی ذخیره نشد).")
            return
        quality = int(get_setting("insta_jpg_quality", "80") or 80)
        if doc.get("remote"):                    # خروجی روی لپ‌تاپ ذخیره میشه؛ یه نسخه هم میاد اینجا برای تلگرام
            res = _agent_call("finish", docname=doc["stem"], filename=os.path.basename(doc["jpg"]), quality=quality)
            with open(doc["jpg"], "wb") as fh:
                fh.write(base64.b64decode(res["jpg_b64"]))
            where = f"{res.get('path')} (لپ‌تاپ)"
        else:
            tmp_dir = os.path.join(DATA_DIR, "tmp")
            os.makedirs(tmp_dir, exist_ok=True)
            insta_photoshop.finish(doc["stem"], doc["jpg"], quality=quality, tmp_dir=tmp_dir)
    except Exception as exc:
        logger.exception("Insta Photoshop finish failed")
        bot.send_message(uid, f"❌ خروجی گرفته نشد: {str(exc)[:400]}")
        return
    sess.pop("ps_doc", None)
    try:
        _news_v2_update_facts(sess["item_id"], insta_cover_path=doc["jpg"])
    except Exception:
        logger.info("Insta: saving path in facts failed item=%s", sess["item_id"])
    with open(doc["jpg"], "rb") as fh:
        bot.send_document(uid, fh, visible_file_name=os.path.basename(doc["jpg"]),
                          caption=f"✅ خروجی فتوشاپ ذخیره شد:\n{where}")
    tpl, meta = _insta_ps_template()
    _insta_save_slide2(uid, sess, doc["jpg"], (int(meta["w"]), int(meta["h"])) if meta.get("w") else None)
    slide2 = os.path.splitext(doc["jpg"])[0] + "_2.jpg"
    if doc.get("remote") and os.path.exists(slide2):      # اسلاید دوم هم کنار کاور توی پوشه‌ی لپ‌تاپ
        try:
            with open(slide2, "rb") as fh:
                _agent_call("save_file", filename=os.path.basename(slide2), b64=base64.b64encode(fh.read()).decode())
        except Exception as exc:
            logger.info("Insta slide 2 copy to laptop failed: %s", exc)
    bot.send_message(uid, "📝 کپشن اینستاگرام (کپی کن):")
    bot.send_message(uid, sess.get("caption") or "—")


# ───────────────── فتوشاپ لپ‌تاپ برای ربات روی سرور (insta_agent.py) ─────────────────
# روی سرور (بدون فتوشاپ) و با PS_AGENT_TOKEN توی .env، یه API کوچیک روی پورت سرور باز میشه. برنامه‌ی insta_agent.py
# روی لپ‌تاپ مدام ازش کار می‌گیره (لپ‌تاپ وصل میشه، نه برعکس) و کارهای فتوشاپ رو با فتوشاپ خود لپ‌تاپ انجام میده.
# هر درخواست با HMAC همون رمز امضا میشه (خود رمز هیچ‌وقت فرستاده نمیشه).
PS_AGENT_TOKEN = os.environ.get("PS_AGENT_TOKEN", "").strip()
_agent_cond = threading.Condition()
_agent_queue = []
_agent_waiters = {}
_agent_state = {"last_seen": 0.0}


def _agent_configured() -> bool:
    return bool(PS_AGENT_TOKEN)


def _ps_remote() -> bool:
    """کارهای فتوشاپ با لپ‌تاپ (insta_agent) انجام بشه؟ روی خود لپ‌تاپ (pywin32 هست) همون فتوشاپ محلی."""
    return _agent_configured() and not insta_photoshop.available()[0]


def _agent_online() -> bool:
    return _agent_configured() and time.time() - _agent_state["last_seen"] < 75


def _agent_call(op: str, timeout: int = 300, **args):
    """یه کار رو به لپ‌تاپ میده و منتظر جوابش می‌مونه؛ خطای لپ‌تاپ → RuntimeError."""
    if not _agent_online():
        raise RuntimeError("لپ‌تاپ آنلاین نیست؛ روی لپ‌تاپ insta_agent.bat رو اجرا کن.")
    job_id = hashlib.sha256(f"{time.time()}{op}{random.random()}".encode()).hexdigest()[:16]
    event = threading.Event()
    with _agent_cond:
        _agent_waiters[job_id] = {"event": event, "result": None}
        _agent_queue.append({"id": job_id, "op": op, "args": args})
        _agent_cond.notify_all()
    if not event.wait(timeout):
        with _agent_cond:
            _agent_waiters.pop(job_id, None)
        raise RuntimeError("لپ‌تاپ جواب نداد (برنامه‌ی insta_agent بسته شد یا فتوشاپ گیر کرده).")
    with _agent_cond:
        res = (_agent_waiters.pop(job_id, None) or {}).get("result") or {}
    if not res.get("ok"):
        raise RuntimeError(res.get("error") or "خطای نامعلوم روی لپ‌تاپ")
    return res.get("result") or {}


def _agent_sig(method: str, path: str, ts: str, body: bytes) -> str:
    msg = f"{method}\n{path}\n{ts}\n".encode() + hashlib.sha256(body).hexdigest().encode()
    return hmac.new(PS_AGENT_TOKEN.encode(), msg, hashlib.sha256).hexdigest()


def start_agent_server():
    if not PS_AGENT_TOKEN:
        return
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    port = int(os.environ.get("PS_AGENT_PORT") or os.environ.get("SERVER_PORT") or 0)
    if not port:
        logger.warning("PS_AGENT_TOKEN set but no PS_AGENT_PORT/SERVER_PORT; laptop Photoshop bridge is off")
        return

    class Handler(BaseHTTPRequestHandler):
        server_version = "ARIKO"

        def log_message(self, *args):
            pass

        def _auth(self, body: bytes) -> bool:
            ts, sig = self.headers.get("X-Ts", ""), self.headers.get("X-Sig", "")
            try:
                fresh = abs(time.time() - float(ts)) < 300
            except ValueError:
                return False
            return fresh and hmac.compare_digest(sig, _agent_sig(self.command, self.path, ts, body))

        def _send(self, code: int, obj=None):
            data = json.dumps(obj or {}, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path != "/agent/poll":
                return self._send(404)
            if not self._auth(b""):
                return self._send(403, {"error": "bad signature"})
            _agent_state["last_seen"] = time.time()
            deadline, job = time.time() + 25, None
            with _agent_cond:
                while True:
                    while _agent_queue and _agent_queue[0]["id"] not in _agent_waiters:
                        _agent_queue.pop(0)                # کسی دیگه منتظرش نیست (وقتش تموم شده)
                    if _agent_queue:
                        job = _agent_queue.pop(0)
                        break
                    left = deadline - time.time()
                    if left <= 0:
                        break
                    _agent_cond.wait(left)
            _agent_state["last_seen"] = time.time()
            self._send(200, {"job": job})

        def do_POST(self):
            if not self.path.startswith("/agent/result/"):
                return self._send(404)
            size = int(self.headers.get("Content-Length") or 0)
            if size > 80_000_000:
                return self._send(413)
            body = self.rfile.read(size)
            if not self._auth(body):
                return self._send(403, {"error": "bad signature"})
            try:
                res = json.loads(body.decode("utf-8"))
            except Exception:
                return self._send(400)
            with _agent_cond:
                waiter = _agent_waiters.get(self.path.rsplit("/", 1)[-1])
                if waiter:
                    waiter["result"] = res
                    waiter["event"].set()
            _agent_state["last_seen"] = time.time()
            self._send(200, {"ok": True})

    try:
        # هاست اشتراکی (سی‌پنل): PS_AGENT_HOST=127.0.0.1 و از بیرون فقط از طریق psagent_proxy (Passenger) در دسترسه
        srv = ThreadingHTTPServer((os.environ.get("PS_AGENT_HOST", "0.0.0.0").strip() or "0.0.0.0", port), Handler)
    except OSError as exc:
        logger.warning("Laptop Photoshop bridge could not listen on port %s: %s", port, exc)
        return
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True, name="ps-agent-api").start()
    logger.info("Laptop Photoshop bridge listening on port %s", port)


def _ps_status_line() -> str:
    if not _ps_remote():
        return ""
    return "💻 فتوشاپ لپ‌تاپ: " + ("✅ آنلاین" if _agent_online() else "❌ آفلاین (insta_agent.bat رو روی لپ‌تاپ اجرا کن)")


def _ps_inspect(path: str):
    return _agent_call("inspect", path=path) if _ps_remote() else insta_photoshop.inspect(path)


def _ps_setup_template(path: str):
    """(مسیر فایل _ARIKO، لایه‌ها)؛ روی لپ‌تاپ یا همین سیستم."""
    if _ps_remote():
        res = _agent_call("setup_template", timeout=400, path=path)
        return res["out"], res["layer_map"]
    info = insta_photoshop.inspect(path)
    layer_map = insta_photoshop.guess_map(info)
    tmp_dir = os.path.join(DATA_DIR, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    grad = insta_photoshop.gradient_png(os.path.join(tmp_dir, "ariko_gradient.png"), (int(info["w"]), int(info["h"])))
    root, _ext = os.path.splitext(path)
    out = path if root.endswith("_ARIKO") else root + "_ARIKO.psd"
    insta_photoshop.setup(path, grad, out, layer_map)
    return out, layer_map


def _ps_prepare(template, png, title, names, tag, sub, docname, title_bottom=0, native_xy=None, logo_rgb=None, adj=None):
    if _ps_remote():
        with open(png, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        return _agent_call("prepare", timeout=300, template=template, png_b64=b64, title=title, names=names,
                           tag=tag, sub=sub, docname=docname, title_bottom=float(title_bottom or 0),
                           native_xy=list(native_xy) if native_xy else None,
                           logo_rgb=list(logo_rgb) if logo_rgb else None, adj=adj or {})
    return insta_photoshop.prepare(template, png, title, names, tag, sub, docname, title_bottom=title_bottom,
                                   native_xy=native_xy, logo_rgb=logo_rgb, adj=adj)


def _insta_out_dir() -> str:
    d = get_setting("insta_out_dir", "").strip()
    if d and os.path.isdir(d):
        return d
    if os.name != "nt":                     # روی سرور: پوشه‌ی پیش‌فرض کنار دیتابیس (فایل‌ها توی تلگرام هم میان)
        d = os.path.join(DATA_DIR, "insta")
        os.makedirs(d, exist_ok=True)
        return d
    return ""


def _insta_ps_template():
    """(مسیر قالب تأییدشده، متادیتا) یا ("", {})"""
    path = get_setting("insta_ps_template", "").strip()
    if not path or (not _ps_remote() and not os.path.exists(path)):   # قالبِ لپ‌تاپ روی سرور نیست
        return "", {}
    try:
        meta = json.loads(get_setting("insta_ps_meta", "{}") or "{}")
    except Exception:
        meta = {}
    return path, meta


def _insta_safe_name(text: str) -> str:
    name = re.sub(r"\[|\]", "", text or "")
    m = re.search(r"\[([^\]]+)\]", text or "")
    base = m.group(1) if m else name
    base = re.sub(r"[^A-Za-z0-9\u0600-\u06FF]+", "_", base).strip("_")
    return (base or "cover")[:40]


def _insta_save(uid: int):
    sess = _insta_sessions.get(uid)
    cover = sess.get("last") if sess else None
    if cover is None:
        bot.send_message(uid, "❌ اول باید پیش‌نمایش ساخته بشه.")
        return
    out_dir = _insta_out_dir()
    if not out_dir:
        bot.send_message(uid, "📁 اول پوشه‌ی خروجی رو مشخص کن (پوشه رو خودت بساز، بعد آدرسش رو بده):\n"
                              "/insta_folder C:\\Users\\ariyan\\Desktop\\Instagram\n\nبعدش دوباره «✅ ذخیره» رو بزن.")
        return
    stem = f"{_insta_safe_name(sess['title'])}_{sess['item_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    jpg = os.path.join(out_dir, stem + ".jpg")
    how = ""
    template, meta = _insta_ps_template()
    img = sess["images"].get(sess["idx"])
    if sess.get("ready"):
        img.save(jpg, "JPEG", quality=96, subsampling=0)          # کاور آماده‌ی خودت: بدون تغییر اندازه
        how = "کاور خودت، بدون تغییر"
    elif template and meta.get("w") and (not _ps_remote() or _agent_online()):
        bot.send_message(uid, ("💻 فتوشاپ لپ‌تاپ" if _ps_remote() else "🖌 فتوشاپ") +
                         " داره پست رو از روی قالبت می‌سازه… (اگه بسته باشه خودش باز میشه)")
        try:
            size = (int(meta["w"]), int(meta["h"]))
            focus = sess["focus"].get(sess["idx"]) or (0.5, 0.0)
            zoom = sess.get("zoom", {}).get(sess["idx"]) or insta_cover.default_zoom(img, size)
            bg = insta_cover.compose_bg(img, size, focus, zoom)
            if sess["bw"]:
                bg = insta_cover.black_white(bg)
            tmp_dir = os.path.join(DATA_DIR, "tmp")
            os.makedirs(tmp_dir, exist_ok=True)
            png = os.path.join(tmp_dir, "insta_image.png")
            # فقط خود عکس (بدون مشکی/محو شدن چسبیده بهش) به‌صورت Smart Object میره توی فتوشاپ، با همون جا و
            # اندازه‌ای که توی پیش‌نمایش بود؛ «اندازه‌ی اصلی» یعنی هیچ تغییر اندازه‌ای. ادمین خودش Ctrl+T می‌کنه.
            scale, offset = insta_cover.placement(img, size, focus, zoom)
            raw = insta_cover.black_white(img) if sess["bw"] else img.convert("RGB")
            if abs(scale - 1.0) > 0.001:
                raw = raw.resize((max(1, round(raw.width * scale)), max(1, round(raw.height * scale))), Image.LANCZOS)
            if offset[1] + raw.height < size[1]:           # مثل پیش‌نمایش: زیر عکس کوتاه، ادامه‌ی آینه‌ای
                raw = insta_cover.extend_down(raw, size[1] - offset[1])
            raw.save(png)
            native = list(offset)
            # خط‌ها رو خود بات (مثل پیش‌نمایش) می‌شکنه، نه فتوشاپ؛ خط‌ها متوازن و «شد!» تنها نمی‌مونه
            adj = insta_cover.adj_of(sess.get("adj"))
            title, names, tk = insta_cover.title_lines_for_photoshop(sess["title"], INSTA_FONT_DIRS, ts=adj["ts"])
            adj = dict(adj, ts=tk)                         # اندازه‌ی تیتر همونی که پیش‌نمایش داره
            title = insta_photoshop._ps_text(title)
            # رنگ لوگو: ناحیه‌ی گوشه‌ی بالا (بعد از گرادیان) روشنه → مشکی، وگرنه سفید
            shaded = insta_cover.apply_gradient(bg)
            lw = round(size[0] * 0.1)
            dark = insta_cover.logo_should_be_dark(shaded, (round(size[0] * 0.04), round(size[1] * 0.025),
                                                            round(size[0] * 0.04) + lw, round(size[1] * 0.025) + lw))
            _ps_prepare(template, png, title, names, sess["tag"], sess["subtitle"], stem,
                        title_bottom=meta.get("title_bottom", 0), native_xy=native,
                        logo_rgb=insta_cover.LOGO_DARK if dark else (255, 255, 255), adj=adj)
        except Exception as exc:
            logger.exception("Insta Photoshop prepare failed")
            bot.send_message(uid, f"⚠️ فتوشاپ نتونست پست رو بسازه: {str(exc)[:400]}\n"
                                  "اگه بخوای، /insta_template off بزن تا فعلاً خود بات بسازه.")
            return
        sess["ps_doc"] = {"stem": stem, "jpg": jpg, "remote": _ps_remote()}
        _insta_persist(uid, sess)
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("📤 اوکیه، خروجی بگیر", callback_data=f"ig:psout:{sess['item_id']}"),
               InlineKeyboardButton("🗑 بیخیال", callback_data=f"ig:psdrop:{sess['item_id']}"))
        bot.send_message(uid, f"🖌 پست توی فتوشاپ آماده‌ست (تب «{stem}»).\n"
                              "چکش کن؛ اگه چیزی رو خواستی دستی درست کن (ذخیره لازم نیست)، بعد «📤 اوکیه، خروجی بگیر» رو بزن.\n"
                              "خروجی همون چیزیه که توی فتوشاپ می‌بینی.", reply_markup=kb)
        return
    else:
        cover.save(jpg, "JPEG", quality=96, subsampling=0)
        how = ("ساخت خود بات؛ لپ‌تاپ آفلاین بود" if template and _ps_remote()
               else "ساخت خود بات (قالب فتوشاپ تنظیم نشده)")
    try:
        _news_v2_update_facts(sess["item_id"], insta_cover_path=jpg)
    except Exception:
        logger.info("Insta: saving path in facts failed item=%s", sess["item_id"])
    with open(jpg, "rb") as fh:
        bot.send_document(uid, fh, visible_file_name=os.path.basename(jpg),
                          caption=f"✅ کاور ذخیره شد ({how}):\n{jpg}")
    if not sess.get("ready"):
        _insta_save_slide2(uid, sess, jpg)
    bot.send_message(uid, "📝 کپشن اینستاگرام (کپی کن):")
    bot.send_message(uid, sess.get("caption") or "—")


@bot.message_handler(commands=["insta_library"])
def insta_library_command(message):
    """/insta_library C:\\...\\AnimeImages — کتابخونه‌ی عکس: داخلش برای هر انیمه یه پوشه با اسم انگلیسی انیمه."""
    if message.from_user.id not in ADMINS:
        return
    parts = (message.text or "").split(maxsplit=1)
    arg = parts[1].strip().strip('"') if len(parts) > 1 else ""
    if arg.lower() == "off":
        set_setting("insta_library", "")
        bot.send_message(message.chat.id, "✅ کتابخونه‌ی عکس خاموش شد.")
        return
    if arg.lower().startswith("test "):             # /insta_library test Solo Leveling Season 2
        root = _insta_library_root()
        if not root:
            bot.send_message(message.chat.id, "❌ اول کتابخونه رو تنظیم کن: /insta_library C:\\...\\AnimeImages")
            return
        name, path = _insta_library_match(root, [arg[5:].strip()])
        if not path:
            bot.send_message(message.chat.id, f"❌ برای «{arg[5:].strip()}» پوشه‌ای پیدا نشد.")
            return
        n = sum(1 for _b, _d, fs in os.walk(path) for f in fs if f.lower().endswith(INSTA_LIBRARY_EXT))
        bot.send_message(message.chat.id, f"✅ پوشه‌ی «{name}» پیدا شد ({n} عکس).")
        return
    if not arg:
        root = get_setting("insta_library", "")
        info = "— (تنظیم نشده)"
        if root:
            if os.path.isdir(root):
                folders = _insta_library_folders(root)
                info = f"{root}\n{len(folders)} پوشه‌ی انیمه: " + "، ".join(f[0] for f in folders[:40])
            else:
                info = f"{root}\n⚠️ این پوشه دیگه وجود نداره"
        bot.send_message(message.chat.id,
                         f"📂 کتابخونه‌ی عکس: {info}\n\n"
                         "یه پوشه بساز و داخلش برای هر انیمه یه پوشه با اسم انگلیسیش (مثلاً «Solo Leveling»، "
                         "«One Piece») و عکس‌های مناسب کاور رو بریز توش. بات عکس‌های پوشه‌ی همون انیمه رو کنار "
                         "بقیه‌ی عکس‌ها می‌ذاره و Gemini بهترینشون رو انتخاب می‌کنه.\n"
                         "اسم‌های دیگه‌ی انیمه (ژاپنی، مخفف…) رو میشه هر کدوم توی یه خط فایل names.txt داخل همون پوشه نوشت.\n\n"
                         "/insta_library C:\\Users\\ariyan\\Desktop\\AnimeImages — تنظیم\n"
                         "/insta_library test Solo Leveling Season 2 — ببین کدوم پوشه رو پیدا می‌کنه\n"
                         "/insta_library off — خاموش")
        return
    if not os.path.isdir(arg):
        bot.send_message(message.chat.id, f"❌ این پوشه وجود نداره:\n{arg}")
        return
    set_setting("insta_library", os.path.abspath(arg))
    folders = _insta_library_folders(os.path.abspath(arg))
    bot.send_message(message.chat.id, f"✅ کتابخونه‌ی عکس ثبت شد ({len(folders)} پوشه‌ی انیمه):\n{os.path.abspath(arg)}")


@bot.message_handler(commands=["insta_folder"])
def insta_folder_command(message):
    """/insta_folder C:\\...\\Instagram — پوشه‌ای که همه‌ی خروجی‌ها توش ذخیره میشن (خود ادمین می‌سازه)."""
    if message.from_user.id not in ADMINS:
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        cur = get_setting("insta_out_dir", "") or "— (تنظیم نشده)"
        bot.send_message(message.chat.id, f"📁 پوشه‌ی خروجی فعلی: {cur}\n\nبرای عوض کردن، اول پوشه رو بساز، بعد:\n"
                                          "/insta_folder C:\\Users\\ariyan\\Desktop\\Instagram")
        return
    path = parts[1].strip().strip('"')
    if not os.path.isdir(path):
        bot.send_message(message.chat.id, f"❌ این پوشه وجود نداره:\n{path}\nاول بسازش (یا آدرس رو از نوار آدرس File Explorer کپی کن).")
        return
    set_setting("insta_out_dir", os.path.abspath(path))
    bot.send_message(message.chat.id, f"✅ از این به بعد همه‌ی کاورها اینجا ذخیره میشن:\n{os.path.abspath(path)}")


def _insta_template_setup(uid: int, path: str):
    try:
        if _ps_remote():                          # آدرس لپ‌تاپ: همون‌جا پیدا میشه (پوشه → فایل PSD)
            path = _agent_call("resolve_psd", arg=path)["path"]
        out, layer_map = _ps_setup_template(path)
    except Exception as exc:
        logger.exception("Insta template setup failed")
        bot.send_message(uid, f"❌ آماده‌سازی قالب انجام نشد:\n{str(exc)[:500]}")
        return
    set_setting("insta_ps_pending", out)
    names = {"TITLE": "تیتر", "TAG": "تگ", "SUB": "زیرنویس", "TAG_BOX": "کادر تگ", "IMAGE": "عکس"}
    found = "\n".join(f"• {names[k]}: «{v}» → {k}" for k, v in layer_map.items() if v)
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ قالب اوکیه، از این به بعد همین", callback_data="igps:ok"))
    bot.send_message(uid,
                     f"🖌 قالب آماده شد و توی فتوشاپ باز شد:\n{out}\n\n"
                     f"لایه‌هایی که پیدا کردم (اسمشون عوض شد):\n{found}\n"
                     "• گرادیان بات → لایه‌ی ARIKO_GRADIENT (گرادیان‌های قبلی فایل فقط خاموش شدن)\n\n"
                     "حالا توی فتوشاپ هر چی لازمه درست کن (جای متن‌ها، گرادیان، لوگو…)، Ctrl+S بزن، "
                     "بعد دکمه‌ی پایین رو بزن. فایل اصلیت دست نخورده.\n"
                     "⚠️ اسم لایه‌های TITLE / TAG / SUB / IMAGE رو عوض نکن.",
                     reply_markup=kb)


@bot.message_handler(commands=["insta_template"])
def insta_template_command(message):
    """/insta_template C:\\...\\خبری.psd — آماده‌سازی قالب فتوشاپ. /insta_template off — خاموش."""
    if message.from_user.id not in ADMINS:
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        template, meta = _insta_ps_template()
        status = (f"✅ قالب فعلی: {template} ({meta.get('w')}x{meta.get('h')})" if template
                  else "— قالب فتوشاپ تنظیم نشده (کاورها رو خود بات می‌سازه)")
        if _ps_status_line():
            status += "\n" + _ps_status_line()
        bot.send_message(message.chat.id, f"🖌 {status}\n\nبرای تنظیم، آدرس فایل PSD رو بده:\n"
                                          "/insta_template C:\\Users\\ariyan\\Desktop\\خبری.psd\n"
                                          "برای خاموش کردن: /insta_template off")
        return
    arg = parts[1].strip().strip('"')
    if arg.lower() in ("upscale on", "upscale off"):
        set_setting("insta_upscale", "1" if arg.lower().endswith("on") else "0")
        bot.send_message(message.chat.id, "✅ افزایش کیفیت خودکار عکس‌های کوچیک با Gemini: "
                         + ("روشن" if arg.lower().endswith("on") else "خاموش"))
        return
    m = re.fullmatch(r"(?i)quality\s+(\d{1,3})", arg)
    if m:
        q = max(10, min(100, int(m.group(1))))
        set_setting("insta_jpg_quality", str(q))
        bot.send_message(message.chat.id, f"✅ کیفیت JPEG خروجی (Save for Web): {q}")
        return
    if arg.lower() == "off":
        set_setting("insta_ps_template", "")
        bot.send_message(message.chat.id, "✅ قالب فتوشاپ خاموش شد؛ کاورها رو خود بات می‌سازه.")
        return
    if _ps_remote():                              # ربات روی سرور: فایل روی لپ‌تاپه
        if not _agent_online():
            bot.send_message(message.chat.id, "❌ لپ‌تاپ آنلاین نیست؛ روی لپ‌تاپ insta_agent.bat رو اجرا کن و دوباره بزن.")
            return
        bot.send_message(message.chat.id, "⏳ فتوشاپ لپ‌تاپ باز میشه و قالب آماده میشه… (بار اول ممکنه یه دقیقه طول بکشه)")
        threading.Thread(target=_insta_template_setup, args=(message.from_user.id, arg), daemon=True).start()
        return
    ok, why = insta_photoshop.available()
    if not ok:
        bot.send_message(message.chat.id, f"❌ {why}\nتوی CMD بزن و ربات رو دوباره اجرا کن.")
        return
    if os.path.isdir(arg):                              # آدرس پوشه داده شده → PSD داخلش
        psds = sorted(f for f in os.listdir(arg) if f.lower().endswith(".psd"))
        mains = [f for f in psds if not os.path.splitext(f)[0].endswith("_ARIKO")] or psds
        if len(mains) == 1:
            arg = os.path.join(arg, mains[0])
        else:
            listing = "\n".join(psds) or "— هیچ فایل PSD ای نیست"
            bot.send_message(message.chat.id, f"❌ توی این پوشه {len(mains)} تا PSD هست؛ آدرس کامل فایل رو بده:\n{listing}")
            return
    if not arg.lower().endswith(".psd") or not os.path.exists(arg):
        bot.send_message(message.chat.id, f"❌ فایل PSD پیدا نشد:\n{arg}\n"
                                          "آدرس خود فایل رو بده، مثلاً: C:\\...\\PSD\\خبری.psd")
        return
    bot.send_message(message.chat.id, "⏳ فتوشاپ باز میشه و قالب آماده میشه… (بار اول ممکنه یه دقیقه طول بکشه)")
    threading.Thread(target=_insta_template_setup, args=(message.from_user.id, arg), daemon=True).start()


def _insta_template_approve(uid: int):
    path = get_setting("insta_ps_pending", "").strip() or get_setting("insta_ps_template", "").strip()
    if not path or (not _ps_remote() and not os.path.exists(path)):
        bot.send_message(uid, "❌ فایل قالب پیدا نشد؛ دوباره /insta_template رو بزن.")
        return
    try:
        info = _ps_inspect(path)
    except Exception as exc:
        bot.send_message(uid, f"❌ خوندن قالب انجام نشد: {str(exc)[:400]}")
        return
    if info.get("unsaved"):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ ذخیره کردم، دوباره چک کن", callback_data="igps:ok"))
        bot.send_message(uid, "⚠️ قالب توی فتوشاپ تغییرات ذخیره‌نشده داره. Ctrl+S بزن، بعد دکمه‌ی پایین.", reply_markup=kb)
        return
    names = {t["name"]: t for t in info.get("texts", [])}
    px_names = {p["name"] for p in info.get("pixels", [])}
    missing = [n for n in ("TITLE",) if n not in names] + [n for n in ("IMAGE",) if n not in px_names]
    if missing:
        bot.send_message(uid, "❌ این لایه‌ها توی قالب نیستن: " + "، ".join(missing) +
                              "\nاسمشون رو توی فتوشاپ درست کن، ذخیره کن و دوباره دکمه رو بزن.")
        return
    meta = {"w": info["w"], "h": info["h"], "title_bottom": names["TITLE"]["bottom"]}
    set_setting("insta_ps_template", path)
    set_setting("insta_ps_meta", json.dumps(meta))
    set_setting("insta_ps_pending", "")
    bot.send_message(uid, f"✅ قالب ثبت شد ({info['w']}x{info['h']}). از این به بعد «✅ ذخیره» توی پیش‌نمایش کاور، "
                          "کاور رو با فتوشاپ از روی همین فایل می‌سازه (فقط عکس و متن عوض میشه).\n"
                          f"📁 خروجی‌ها: {_insta_out_dir() or '⚠️ هنوز پوشه تنظیم نشده → /insta_folder'}")


@bot.callback_query_handler(func=lambda c: c.data == "igps:ok")
def insta_template_ok_callback(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return
    bot.answer_callback_query(call.id, "⏳ چک کردن قالب…")
    threading.Thread(target=_insta_template_approve, args=(call.from_user.id,), daemon=True).start()


@bot.message_handler(commands=["insta_setup"])
def insta_setup_command(message):
    """وضعیت فونت و لوگوی کاور + آپلود فایل‌هاشون."""
    if message.from_user.id not in ADMINS:
        return
    missing = insta_cover.missing_fonts(INSTA_FONT_DIRS)
    logo = next((p for p in INSTA_LOGO_PATHS if os.path.exists(p)), "")
    lines = ["🎨 تنظیمات کاور اینستاگرام",
             "✅ فونت‌ها کامله" if not missing else "❌ فونت‌های لازم: " + "، ".join(missing),
             f"✅ لوگو: {logo}" if logo else "❌ لوگو تنظیم نشده",
             f"📁 پوشه‌ی خروجی: {_insta_out_dir() or '❌ تنظیم نشده → /insta_folder'}",
             f"📂 کتابخونه‌ی عکس: {_insta_library_root() or '— ندارد (/insta_library)'}",
             f"🖌 قالب فتوشاپ: {_insta_ps_template()[0] or '— ندارد (/insta_template)'}",
             _ps_status_line() or "💻 فتوشاپ: همین سیستم",
             "",
             "حالا فایل‌های فونت (.ttf) یا لوگو (PNG با پس‌زمینه‌ی شفاف) رو به‌صورت «فایل» بفرست. "
             "تموم شد، «پایان» بنویس."]
    msg = bot.send_message(message.chat.id, "\n".join(lines))
    bot.register_next_step_handler(msg, insta_setup_upload)


def insta_setup_upload(message):
    if (message.text or "").strip() in ("پایان", "تمام", BACK_MAIN) or (message.text or "").startswith("/"):
        missing = insta_cover.missing_fonts(INSTA_FONT_DIRS)
        bot.send_message(message.chat.id, "✅ تنظیمات ذخیره شد." if not missing
                         else "⚠️ هنوز این فونت‌ها نیستن: " + "، ".join(missing))
        return
    doc = getattr(message, "document", None)
    if getattr(message, "photo", None):
        msg = bot.send_message(message.chat.id, "⚠️ لوگو رو به‌صورت «فایل» بفرست که شفافیتش از بین نره.")
        bot.register_next_step_handler(msg, insta_setup_upload)
        return
    if not doc:
        msg = bot.send_message(message.chat.id, "فایل .ttf یا .png بفرست، یا «پایان».")
        bot.register_next_step_handler(msg, insta_setup_upload)
        return
    name = os.path.basename(doc.file_name or "")
    try:
        data = bot.download_file(bot.get_file(doc.file_id).file_path)
        if name.lower().endswith((".ttf", ".otf")):
            from PIL import ImageFont
            ImageFont.truetype(io.BytesIO(data), 20)     # سالم بودن فونت
            os.makedirs(INSTA_FONT_DIRS[0], exist_ok=True)
            with open(os.path.join(INSTA_FONT_DIRS[0], name), "wb") as fh:
                fh.write(data)
            reply = f"✅ فونت {name} ذخیره شد."
        elif name.lower().endswith(".png"):
            from PIL import Image
            img = Image.open(io.BytesIO(data))
            img.load()
            if img.mode not in ("RGBA", "LA") and "transparency" not in img.info:
                reply = "⚠️ این PNG پس‌زمینه‌ی شفاف نداره؛ باز هم ذخیره شد ولی بهتره نسخه‌ی شفاف بفرستی."
            else:
                reply = "✅ لوگو ذخیره شد."
            img.save(INSTA_LOGO_PATHS[0])
            if min(img.size) < 200:
                reply += f"\n⚠️ لوگو کوچیکه ({img.width}x{img.height})؛ نسخه‌ی بزرگ‌تر (۵۰۰+ پیکسل) واضح‌تر میشه."
        else:
            reply = "⚠️ فقط .ttf / .otf (فونت) یا .png (لوگو)."
    except Exception as exc:
        reply = f"❌ ذخیره نشد: {str(exc)[:200]}"
    msg = bot.send_message(message.chat.id, reply + "\nفایل بعدی یا «پایان».")
    bot.register_next_step_handler(msg, insta_setup_upload)


@bot.message_handler(commands=["start", "menu"])
def news_bot_start(message):
    show_main_menu(message.chat.id, message.from_user.id, "📰 بات خبر آریکو")


@bot.message_handler(commands=["id"])
def news_bot_chat_id(message):
    bot.send_message(message.chat.id, f"CHAT ID: {message.chat.id}")


# ───────────────────────── سالگرد انیمه‌ها ─────────────────────────
# هر روز یه یادآوری برای ادمین: کدوم انیمه‌ها (چند روز دیگه) سالگرد اولین پخش یا پایان فصل/پایان کلی دارن،
# با دکمه‌ی «🎨 پست اینستاگرام» که همون ساخت کاور خبرها رو باز می‌کنه. داده‌ها از AniList.
ANNIV_TZ = timezone(timedelta(hours=3, minutes=30))          # تهران (بدون ساعت تابستونی)
ANNIV_FORMATS = ("TV", "MOVIE", "ONA")
ANNIV_MILESTONES = (1, 5, 10, 15, 20, 25, 30, 35, 40, 50)
ANNIV_MAX_ITEMS = 12
ANNIV_KIND_FA = {
    "first": "سالگرد اولین پخش انیمه",
    "season_start": "سالگرد شروع پخش این فصل",
    "movie": "سالگرد اکران فیلم",
    "season_end": "سالگرد پایان این فصل",
    "final_end": "سالگرد پایان انیمه (آخرین فصل پخش‌شده)",
}

_ANNIV_QUERY = """
query ($page: Int, $like: String, $pop: Int) {
  Page(page: $page, perPage: 50) {
    pageInfo { hasNextPage }
    media(type: ANIME, isAdult: false, popularity_greater: $pop, sort: POPULARITY_DESC,
          format_in: [TV, MOVIE, ONA], %s: $like) {
      id format status popularity episodes
      title { romaji english native }
      synonyms
      startDate { year month day }
      endDate { year month day }
      bannerImage
      coverImage { extraLarge large }
      studios(isMain: true) { nodes { name } }
      relations { edges { relationType(version: 2) node { type format status title { romaji english } } } }
    }
  }
}"""


def _anniv_setting_int(key: str, default: int) -> int:
    try:
        return int(get_setting(key, str(default)) or default)
    except ValueError:
        return default


def _anniv_anilist(field: str, mmdd: str, pop: int) -> list:
    """همه‌ی انیمه‌هایی که startDate یا endDate اونا (ماه و روز) برابر mmdd هست."""
    out = []
    for page in range(1, 5):
        query = _ANNIV_QUERY % field
        body = {"query": query, "variables": {"page": page, "like": f"%{mmdd}", "pop": pop}}
        req = urllib.request.Request(ANILIST_GRAPHQL_URL, data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", "Accept": "application/json",
                                              "User-Agent": NEWS_USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
        if payload.get("errors"):
            raise RuntimeError(str(payload["errors"])[:300])
        data = ((payload.get("data") or {}).get("Page") or {})
        out += data.get("media") or []
        if not (data.get("pageInfo") or {}).get("hasNextPage"):
            break
        time.sleep(1.2)
    return out


def _anniv_known_names() -> set:
    """اسم انیمه‌هایی که توی کانال خبرشون اومده (این‌ها با محبوبیت کمتر هم یادآوری میشن)."""
    conn = db()
    try:
        rows = conn.execute("""
            SELECT DISTINCT anime_eng_name, anime_display FROM news_v2_items
            WHERE status IN ('approved','published') AND created_at >= datetime('now','-730 day')
        """).fetchall()
    finally:
        conn.close()
    names = set()
    for r in rows:
        for v in (r["anime_eng_name"], r["anime_display"]):
            n = _insta_lib_norm(v or "")
            if len(n) >= 4:
                names.add(n)
    return names


def _anniv_date(d) -> date | None:
    try:
        return date(int(d["year"]), int(d["month"]), int(d["day"]))
    except Exception:
        return None


def _anniv_list(target: date) -> list:
    """سالگردهای یه روز: [{media, kind, years, when, known, milestone}] مرتب از مهم‌ترین."""
    pop_all = _anniv_setting_int("anniv_min_pop", 60000)
    pop_known = _anniv_setting_int("anniv_min_pop_known", 3000)
    known = _anniv_known_names()
    mmdds = [target.strftime("%m%d")]
    if target.month == 2 and target.day == 28 and not calendar.isleap(target.year):
        mmdds.append("0229")                               # متولدین ۲۹ فوریه، سال‌های غیرکبیسه ۲۸ام
    found, seen = [], set()
    for field in ("startDate_like", "endDate_like"):
        for mmdd in mmdds:
            try:
                medias = _anniv_anilist(field, mmdd, min(pop_all, pop_known))
            except Exception as exc:
                logger.info("Anniversary AniList query failed (%s %s): %s", field, mmdd, exc)
                continue
            for m in medias:
                is_start = field.startswith("start")
                when = _anniv_date(m.get("startDate" if is_start else "endDate") or {})
                if not when or when.strftime("%m%d") != mmdd or when.year >= target.year:
                    continue
                if not is_start and m.get("status") != "FINISHED":
                    continue
                titles = m.get("title") or {}
                names = [titles.get("english"), titles.get("romaji")] + list(m.get("synonyms") or [])
                is_known = any(_insta_lib_norm(n or "") in known for n in names if n)
                if int(m.get("popularity") or 0) < (pop_known if is_known else pop_all):
                    continue
                edges = ((m.get("relations") or {}).get("edges") or [])

                def rel(kind):
                    return [e["node"] for e in edges if e.get("relationType") == kind
                            and (e.get("node") or {}).get("type") == "ANIME"
                            and (e.get("node") or {}).get("format") in ANNIV_FORMATS]
                if m.get("format") == "MOVIE":
                    if not is_start:
                        continue                             # فیلم: فقط سالگرد اکران
                    kind = "movie"
                elif is_start:
                    kind = "season_start" if rel("PREQUEL") else "first"
                else:
                    kind = "season_end" if rel("SEQUEL") else "final_end"
                key = (m["id"], kind)
                if key in seen:
                    continue
                seen.add(key)
                years = target.year - when.year
                sequel = next(iter(rel("SEQUEL")), None) if kind == "season_end" else None
                found.append({"media": m, "kind": kind, "years": years, "when": when, "known": is_known,
                              "milestone": years in ANNIV_MILESTONES,
                              "sequel_coming": bool(sequel and sequel.get("status") in ("NOT_YET_RELEASED", "RELEASING"))})
    found.sort(key=lambda a: (not a["known"], not a["milestone"], -int(a["media"].get("popularity") or 0)))
    found = found[:ANNIV_MAX_ITEMS]
    for a in found:
        a["season"] = 1 if a["kind"] == "first" else (None if a["kind"] == "movie" else _anniv_season_number(a["media"]))
    return found


_FA_ORDINALS = ["", "اول", "دوم", "سوم", "چهارم", "پنجم", "ششم", "هفتم", "هشتم", "نهم", "دهم"]


def _anniv_ordinal(n: int) -> str:
    return _FA_ORDINALS[n] if 0 < n < len(_FA_ORDINALS) else f"{_news_fa_digits(str(n))}م"


def _anniv_season_from_title(m: dict):
    """شماره‌ی فصل از خود اسم: «Season 2»، «2nd Season»، «S3»، «II/III»؛ اگه نبود None."""
    titles = m.get("title") or {}
    for t in [titles.get("english"), titles.get("romaji")] + list(m.get("synonyms") or []):
        t = t or ""
        hit = (re.search(r"\bseason\s*(\d{1,2})\b", t, re.I) or re.search(r"\b(\d{1,2})(?:st|nd|rd|th)\s+season\b", t, re.I)
               or re.search(r"\bS(\d{1,2})\b", t) or re.search(r"第(\d{1,2})期", t))
        if hit:
            return int(hit.group(1))
        roman = re.search(r"\s(II|III|IV|V|VI)\s*$", t)
        if roman:
            return {"II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}[roman.group(1)]
    return None


_ANNIV_REL_QUERY = """query ($id: Int) { Media(id: $id) { relations { edges { relationType(version: 2)
  node { id type format } } } } }"""


def _anniv_season_number(m: dict):
    """فصل چندم: اول از اسم، وگرنه با شمردن فصل‌های قبلی (زنجیره‌ی PREQUEL سریالی توی AniList)."""
    n = _anniv_season_from_title(m)
    if n:
        return n
    count, current, seen = 1, m, {m.get("id")}
    try:
        for _ in range(12):
            edges = ((current.get("relations") or {}).get("edges") or [])
            prev = next((e["node"] for e in edges if e.get("relationType") == "PREQUEL"
                         and (e.get("node") or {}).get("type") == "ANIME"
                         and (e.get("node") or {}).get("format") in ("TV", "ONA")), None)
            if not prev or prev.get("id") in seen:
                return count
            seen.add(prev["id"])
            count += 1
            time.sleep(0.8)
            body = {"query": _ANNIV_REL_QUERY, "variables": {"id": prev["id"]}}
            req = urllib.request.Request(ANILIST_GRAPHQL_URL, data=json.dumps(body).encode("utf-8"), method="POST",
                                         headers={"Content-Type": "application/json", "Accept": "application/json",
                                                  "User-Agent": NEWS_USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as resp:
                current = ((json.loads(resp.read().decode("utf-8", errors="ignore")).get("data") or {})
                           .get("Media") or {})
    except Exception as exc:
        logger.info("Anniversary season count failed id=%s: %s", m.get("id"), exc)
        return None
    return count


def _anniv_kind_fa(a: dict) -> str:
    """«سالگرد پایان فصل دوم» و …؛ اگه شماره‌ی فصل معلوم نبود، همون متن کلی."""
    n = a.get("season")
    if not n:
        return ANNIV_KIND_FA[a["kind"]]
    ordfa = _anniv_ordinal(n)
    return {
        "first": "سالگرد اولین پخش انیمه (شروع فصل اول)",
        "season_start": f"سالگرد شروع فصل {ordfa}",
        "season_end": f"سالگرد پایان فصل {ordfa}",
        "final_end": (f"سالگرد پایان فصل {ordfa} (فعلاً تنها فصل انیمه)" if n == 1
                      else f"سالگرد پایان فصل {ordfa} (آخرین فصل پخش‌شده تا امروز)"),
    }.get(a["kind"], ANNIV_KIND_FA[a["kind"]])


def _anniv_item(a: dict, target: date) -> int | None:
    """برای هر سالگرد یه ردیف آرشیو (وضعیت anniversary، بیرون از صف خبرها) که دکمه‌ی ساخت کاور روش کار کنه."""
    m = a["media"]
    titles = m.get("title") or {}
    name = titles.get("english") or titles.get("romaji") or ""
    kind_fa = _anniv_kind_fa(a)
    season = a.get("season")
    studio = ", ".join(n.get("name") for n in ((m.get("studios") or {}).get("nodes") or []) if n.get("name"))
    what = {"first": "first aired (first episode of the whole anime)",
            "season_start": "this season first aired",
            "movie": "the movie premiered",
            "season_end": "this season aired its final episode",
            "final_end": "the anime aired its final episode (its last season so far)"}[a["kind"]]
    if season and a["kind"] != "movie":
        what += f" — this is SEASON {season}"
    title = f"{name}: {a['years']} years ago today ({a['when'].isoformat()}) {what}"
    summary = (f"ANNIVERSARY POST (not news). On {a['when'].isoformat()} — exactly {a['years']} year(s) before "
               f"{target.isoformat()} — {what}. Anime: {name} (romaji: {titles.get('romaji') or '-'}), "
               f"format {m.get('format')}, episodes {m.get('episodes') or '-'}, studio {studio or '-'}."
               + (" A new season/sequel is announced or airing." if a.get("sequel_coming") else "")
               + " Write the cover as an anniversary post, like «۷ سال پیش در چنین روزی، انیمه‌ی [X] برای اولین بار پخش شد!»"
                 " or «۱ سال پیش در چنین روزی، فصل دوم انیمه‌ی [X] به پایان رسید!». The tag must be «سالگرد».")
    caption = (f"🎂 {kind_fa}: {name}\n"
               f"تاریخ: {_news_fa_digits(a['when'].strftime('%Y/%m/%d'))} — {_news_fa_digits(str(a['years']))} سال")
    cover = (m.get("coverImage") or {}).get("extraLarge") or (m.get("coverImage") or {}).get("large") or ""
    facts = {"anime_eng_name": name, "anime_display": name, "anniversary": {
        "kind": a["kind"], "years": a["years"], "date": a["when"].isoformat(), "anilist_id": m["id"],
        "season": season}}
    if cover:
        facts["extra_images"] = [cover]
    guid = f"anniv:{m['id']}:{a['kind']}:{target.year}"
    with db_write_lock:
        conn = db()
        try:
            conn.execute("""
                INSERT INTO news_v2_items(source_id, guid, title, url, published_at, summary, image_url,
                    event_type, source_class, anime_key, anime_display, anime_eng_name, confidence, facts_json,
                    caption, status)
                VALUES (0, ?, ?, ?, ?, ?, ?, 'anniversary', 'official', ?, ?, ?, 100, ?, ?, 'anniversary')
                ON CONFLICT(source_id, guid) DO UPDATE SET title=excluded.title, summary=excluded.summary,
                    facts_json=excluded.facts_json, caption=excluded.caption
            """, (guid, title, f"https://anilist.co/anime/{m['id']}", target.isoformat(), summary,
                  m.get("bannerImage") or cover, _insta_lib_norm(name), name, name,
                  json.dumps(facts, ensure_ascii=False), caption))
            conn.commit()
            row = conn.execute("SELECT id FROM news_v2_items WHERE source_id=0 AND guid=?", (guid,)).fetchone()
            return int(row["id"]) if row else None
        finally:
            conn.close()


def _anniv_send(chat_ids, target: date, label: str = ""):
    """یه پیام عنوان، بعد هر سالگرد جدا: پوستر انیمه + توضیح + دکمه‌ی ساخت کاور."""
    items = _anniv_list(target)
    jdate = "/".join(_news_fa_digits(str(x)) for x in _news_gregorian_to_jalali(target.year, target.month, target.day))
    head = f"🎂 سالگردهای {label or ''}{jdate} ({target.isoformat()})"
    if not items:
        for chat_id in chat_ids:
            try:
                bot.send_message(chat_id, head + "\n\nسالگرد مهمی برای این روز پیدا نشد.")
            except Exception:
                logger.exception("Anniversary digest send failed chat=%s", chat_id)
        return
    cards = []
    for n, a in enumerate(items, 1):
        m = a["media"]
        titles = m.get("title") or {}
        name = titles.get("english") or titles.get("romaji") or "?"
        badge = "🎉" if a["milestone"] else "🎂"
        lines = [f"{badge} {n}. {name}"]
        if titles.get("romaji") and titles.get("romaji") != name:
            lines.append(titles["romaji"])
        lines.append(f"{_news_fa_digits(str(a['years']))} سال — {_anniv_kind_fa(a)}")
        start, end = _anniv_date(m.get("startDate") or {}), _anniv_date(m.get("endDate") or {})
        fmt = lambda d: _news_fa_digits(d.strftime("%Y/%m/%d")) if d else "—"
        if a["kind"] == "movie" or not end:
            lines.append(f"📅 {'اکران' if a['kind'] == 'movie' else 'شروع پخش'}: {fmt(a['when'])}")
        else:
            is_end = a["kind"] in ("season_end", "final_end")
            lines.append(f"📅 شروع پخش: {fmt(start)}{'' if is_end else ' ⬅️'}")
            lines.append(f"🏁 پایان پخش: {fmt(end)}{' ⬅️' if is_end else ''}")
        if a["known"]:
            lines.append("📺 خبرش توی کانال اومده")
        if a.get("sequel_coming"):
            lines.append("⏳ فصل بعدی در راهه")
        try:
            item_id = _anniv_item(a, target)
        except Exception:
            logger.exception("Anniversary item insert failed")
            item_id = None
        kb = None
        if item_id:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🎨 پست اینستاگرام", callback_data=f"nv2_insta:{item_id}"))
        cover = (m.get("coverImage") or {}).get("extraLarge") or (m.get("coverImage") or {}).get("large") or ""
        cards.append(("\n".join(lines), cover, kb))
    for chat_id in chat_ids:
        try:
            bot.send_message(chat_id, head + f"\n{_news_fa_digits(str(len(cards)))} سالگرد پیدا شد 👇\n"
                                              "🎉 = سالگرد رُند (۱، ۵، ۱۰، ۱۵… سال)")
        except Exception:
            logger.exception("Anniversary digest send failed chat=%s", chat_id)
            continue
        for caption, cover, kb in cards:
            sent = False
            if cover:
                try:                                # پوستر با لینک؛ اگه تلگرام نتونست بگیره، خودمون دانلود می‌کنیم
                    bot.send_photo(chat_id, cover, caption=caption[:1000], reply_markup=kb)
                    sent = True
                except Exception:
                    try:
                        bot.send_photo(chat_id, _insta_download(cover), caption=caption[:1000], reply_markup=kb)
                        sent = True
                    except Exception as exc:
                        logger.info("Anniversary poster failed %s: %s", cover, exc)
            if not sent:
                try:
                    bot.send_message(chat_id, caption, reply_markup=kb)
                except Exception:
                    logger.exception("Anniversary card send failed chat=%s", chat_id)
            time.sleep(0.4)


def anniversary_loop():
    while True:
        try:
            if get_setting("anniv_enabled", "1") == "1":
                now = datetime.now(ANNIV_TZ)
                today = now.date().isoformat()
                if now.hour >= _anniv_setting_int("anniv_hour", 10) and get_setting("anniv_last_sent", "") != today:
                    set_setting("anniv_last_sent", today)
                    lead = max(0, min(7, _anniv_setting_int("anniv_lead", 1)))
                    target = now.date() + timedelta(days=lead)
                    label = {0: "امروز ", 1: "فردا "}.get(lead, f"{_news_fa_digits(str(lead))} روز دیگه ")
                    _anniv_send(ADMINS, target, label)
        except Exception:
            logger.exception("Anniversary loop failed")
        time.sleep(10 * 60)


def start_anniversary_thread():
    threading.Thread(target=anniversary_loop, daemon=True, name="anniversaries").start()


@bot.message_handler(commands=["anniv"])
def anniv_command(message):
    """/anniv — سالگردهای امروز؛ /anniv 3 — سه روز دیگه؛ /anniv 2026-10-05؛ تنظیمات: on/off، hour، lead، pop."""
    if message.from_user.id not in ADMINS:
        return
    args = (message.text or "").split()[1:]
    today = datetime.now(ANNIV_TZ).date()
    if args and args[0] in ("on", "off"):
        set_setting("anniv_enabled", "1" if args[0] == "on" else "0")
        bot.send_message(message.chat.id, "✅ یادآوری روزانه‌ی سالگردها " + ("روشن شد." if args[0] == "on" else "خاموش شد."))
        return
    settings = {"hour": ("anniv_hour", 0, 23), "lead": ("anniv_lead", 0, 7),
                "pop": ("anniv_min_pop", 0, 10**7), "popknown": ("anniv_min_pop_known", 0, 10**7)}
    if args and args[0] in settings:
        key, lo, hi = settings[args[0]]
        if len(args) < 2 or not args[1].isdigit() or not lo <= int(args[1]) <= hi:
            bot.send_message(message.chat.id, f"❌ یه عدد بین {lo} و {hi} بنویس، مثلاً /anniv {args[0]} {lo + 1}")
            return
        set_setting(key, args[1])
        if key == "anniv_hour":
            set_setting("anniv_last_sent", "")             # اگه ساعت جدید امروز هنوز نرسیده، امروز هم فرستاده بشه
        bot.send_message(message.chat.id, f"✅ ذخیره شد: {args[0]} = {args[1]}")
        return
    if args and args[0] == "help" or (args and not re.fullmatch(r"\d{1,3}|\d{4}-\d{2}-\d{2}", args[0])):
        state = "روشن" if get_setting("anniv_enabled", "1") == "1" else "خاموش"
        bot.send_message(message.chat.id,
                         f"🎂 یادآوری سالگرد انیمه‌ها ({state})\n"
                         f"هر روز ساعت {_anniv_setting_int('anniv_hour', 10)} تهران، سالگردهای "
                         f"{_anniv_setting_int('anniv_lead', 1)} روز بعد فرستاده میشه.\n"
                         f"حداقل محبوبیت (تعداد عضو AniList): {_anniv_setting_int('anniv_min_pop', 60000)}؛ "
                         f"انیمه‌هایی که خبرشون توی کانال اومده: {_anniv_setting_int('anniv_min_pop_known', 3000)}\n\n"
                         "/anniv — سالگردهای امروز\n/anniv 3 — سه روز دیگه\n/anniv 2026-10-05 — یه تاریخ خاص\n"
                         "/anniv on | off — روشن/خاموش یادآوری روزانه\n/anniv hour 10 — ساعت یادآوری\n"
                         "/anniv lead 1 — چند روز زودتر خبر بده (۰ = همون روز)\n"
                         "/anniv pop 60000 — حداقل محبوبیت\n/anniv popknown 3000 — حداقل محبوبیت انیمه‌های کانال")
        return
    if args and "-" in args[0]:
        try:
            target = date.fromisoformat(args[0])
        except ValueError:
            bot.send_message(message.chat.id, "❌ تاریخ رو این‌طوری بنویس: 2026-10-05")
            return
        label = ""
    else:
        days = int(args[0]) if args else 0
        target = today + timedelta(days=days)
        label = {0: "امروز ", 1: "فردا "}.get(days, f"{_news_fa_digits(str(days))} روز دیگه ")
    bot.send_message(message.chat.id, "⏳ دارم سالگردها رو از AniList درمیارم…")
    threading.Thread(target=_anniv_send, args=([message.chat.id], target, label), daemon=True).start()


@bot.channel_post_handler(func=lambda m: (m.text or "").strip() == "/id")
def news_bot_channel_id(message):
    try:
        bot.send_message(message.chat.id, f"CHANNEL ID: {message.chat.id}")
    except Exception:
        pass


@bot.message_handler(func=lambda m: True)
def news_bot_fallback(message):
    show_main_menu(message.chat.id, message.from_user.id)


if __name__ == "__main__":
    init_db()
    _news_v2_init_db()
    _news_agent_init_db()
    start_news_v2_collector_thread()
    start_ranking_collector_thread()
    start_db_backup_thread()
    start_health_watchdog_thread()
    start_anniversary_thread()
    start_agent_server()
    try:
        bot.remove_webhook()
    except Exception:
        pass
    print("✅ News bot is running...")
    logger.info("News bot startup complete; entering polling")
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
            logger.warning("infinity_polling returned; restarting in 5s")
        except KeyboardInterrupt:
            raise
        except Exception:
            logger.exception("Polling crashed; restarting in 5s")
        time.sleep(5)
        time.sleep(5)