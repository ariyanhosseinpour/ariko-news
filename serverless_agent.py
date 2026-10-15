# -*- coding: utf-8 -*-
"""برنامه‌ی کامپیوتر برای بات خبری Serverless (کارهای سنگین).

بات خبری روی سرورهای خود تلگرام (Serverless) اجرا میشه. اگه عکس یه خبر نه با لینک فرستاده شد و نه خود سرور
تونست دانلود و آپلودش کنه (عکس بیشتر از ۱۰ مگ، فرمت AVIF/GIF/...، سایت جلوی دانلود رو گرفته)، خبر منتشر نمیشه
و یه «کار» منتظر می‌مونه. این برنامه روی کامپیوتر هر ۲۰ ثانیه کارها رو می‌گیره، عکس رو دانلود و درست می‌کنه
(JPEG، حداکثر ۲۵۶۰ پیکسل، زیر ۱۰ مگ) و خودش با توکن بات می‌فرسته. هر ۵ دقیقه هم چک خبرها رو صدا می‌زنه.

ارتباط با سرور از همون راهی که «npx tgcloud run» استفاده می‌کنه (توکن CLI Access)؛ پورت یا آدرس جدا لازم نیست.

تنظیمات (فایل .env کنار همین فایل):
  NEWS_BOT_TOKEN=...       توکن همون بات خبری
  TGCLOUD_TOKEN=...        BotFather → بات → Serverless → CLI Access → Access token
  TGCLOUD_PROJECT=...      پوشه‌ی پروژه (همون که پوشه‌ی tgcloud توشه)؛ پیش‌فرض: serverless کنار همین فایل
  NEWS_PROXY=http://127.0.0.1:10809   (اختیاری) پروکسی فیلترشکن

اجرا:  python serverless_agent.py          نیاز: pip install pillow
فقط یه بار چک خبرها (برای کران هاست، بدون Pillow):  python serverless_agent.py --tick
"""
import io
import json
import os
import re
import sys
import time
import traceback
import urllib.parse
import urllib.request
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


_load_dotenv(os.path.join(BASE_DIR, ".env"))
TOKEN = os.environ.get("NEWS_BOT_TOKEN", "").strip()
TG_CLOUD = os.environ.get("TGCLOUD_TOKEN", "").strip()
PROJECT = os.environ.get("TGCLOUD_PROJECT", "").strip() or os.path.join(BASE_DIR, "serverless")
CLOUD_API = os.environ.get("TG_CLOUD_API_URL", "https://cloud.telegram.org").rstrip("/")
PROXY = os.environ.get("NEWS_PROXY", "").strip()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
if PROXY:
    urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})))



def log(text):
    print(time.strftime("%H:%M:%S"), text, flush=True)


# ماژول کوچیکی که فقط موقع اجرا فرستاده میشه (deploy نمیشه) و توابع lib/news.js رو صدا می‌زنه
PC_MODULE = """
import { platform } from '../lib/platform.js';
import { agentPoll, agentDone, collect, agentUpdates } from '../lib/news.js';
export default async function (input) {
  const p = platform();
  if (input.op === 'poll') return { jobs: await agentPoll(p), updates: await agentUpdates(p) };
  if (input.op === 'done') return await agentDone(p, input.result || {});
  if (input.op === 'collect') return await collect(p);
  return { error: 'unknown op' };
}
"""


def _sources():
    root = os.path.join(PROJECT, "tgcloud")
    if not os.path.isdir(root):
        sys.exit(f"پوشه‌ی پروژه پیدا نشد: {root} (TGCLOUD_PROJECT رو درست کن)")
    out = {}
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.endswith(".js"):
                full = os.path.join(dirpath, f)
                mod = os.path.relpath(full, root)[:-3].replace(os.sep, "/")
                with open(full, encoding="utf-8") as fh:
                    out[mod] = fh.read()
    out["endpoints/pc_agent"] = PC_MODULE
    return out


def cloud(op, **args):
    """یه تابع lib/news.js رو روی سرور تلگرام اجرا می‌کنه (همون API که «npx tgcloud run» داره)."""
    app_id = TG_CLOUD.split(":", 1)[0]
    body = json.dumps({"module": "endpoints/pc_agent", "sources": _sources(), "args": {"op": op, **args},
                       "ctx": {}}).encode("utf-8")
    req = urllib.request.Request(f"{CLOUD_API}/{app_id}/manage/run", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {TG_CLOUD}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        data = json.loads(exc.read().decode("utf-8") or "{}")
    if not data.get("ok"):
        raise RuntimeError(data.get("description") or f"tgcloud run: {data}")
    return (data.get("result") or {}).get("result") or {}


def _download(url, referer=""):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer or url, "Accept": "image/*,*/*"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read(30_000_000)


def _og_image(page):
    html = _download(page).decode("utf-8", "ignore")
    m = (re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)', html, re.I)
         or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)', html, re.I))
    return m.group(1).replace("&amp;", "&") if m else ""


def _fix_image(raw):
    """هر فرمتی → JPEG سالم که تلگرام قبول کنه (حداکثر ۲۵۶۰ پیکسل، زیر ۹٫۵ مگ)."""
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("Pillow روی کامپیوتر نصب نیست: pip install pillow")
    img = Image.open(io.BytesIO(raw))
    img.load()
    if img.mode not in ("RGB", "L"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
        img = bg
    img = img.convert("RGB")
    img.thumbnail((2560, 2560), Image.LANCZOS)
    for q in (92, 85, 78, 70):
        out = io.BytesIO()
        img.save(out, "JPEG", quality=q, optimize=True)
        if out.tell() < 9_500_000:
            return out.getvalue()
    raise RuntimeError("عکس حتی بعد از فشرده‌سازی خیلی بزرگه")


def _send_photo(chat_id, jpg, caption, reply_markup):
    boundary = uuid.uuid4().hex
    fields = {"chat_id": str(chat_id), "caption": caption or "", "parse_mode": "HTML"}
    if reply_markup:
        fields["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    body = io.BytesIO()
    for k, v in fields.items():
        body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n".encode())
        body.write(v.encode("utf-8") + b"\r\n")
    body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"news.jpg\"\r\n"
               "Content-Type: image/jpeg\r\n\r\n".encode() + jpg + b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendPhoto", data=body.getvalue(),
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    if not res.get("ok"):
        raise RuntimeError(res.get("description") or "sendPhoto failed")
    return res["result"]["photo"][-1]["file_id"]


def handle(job):
    raw, errors = None, []
    for src in [job.get("image")] + (["og"] if job.get("page") else []):
        if not src:
            continue
        try:
            url = _og_image(job["page"]) if src == "og" else src
            if url:
                raw = _download(url, job.get("page") or "")
                break
        except Exception as exc:
            errors.append(f"{src[:60]}: {exc}")
    if raw is None:
        raise RuntimeError("دانلود عکس نشد — " + " | ".join(errors)[:300])
    file_id = _send_photo(job["chat_id"], _fix_image(raw), job.get("caption"), job.get("reply_markup"))
    return file_id


_old_bot = None


def old_bot():
    """کد بات قدیمی (news.py کنار همین فایل) فقط به‌عنوان کتابخونه؛ خود بات قدیمی اجرا (polling) نمیشه."""
    global _old_bot
    if _old_bot is None:
        if not os.path.exists(os.path.join(BASE_DIR, "news.py")):
            raise RuntimeError("news.py (بات قدیمی) کنار serverless_agent.py نیست؛ این کار با کد اون انجام میشه.")
        sys.path.insert(0, BASE_DIR)
        import news as mod
        mod.init_db()
        mod._news_v2_init_db()
        _old_bot = mod
    return _old_bot


def handle_rank(job):
    """کارت رنکینگ هفتگی رو با همون کد بات قدیمی می‌سازه و می‌فرسته."""
    path, caption, _label = old_bot()._weekly_test_build(job["source"])
    with open(path, "rb") as fh:
        raw = fh.read()
    caption = caption.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return _send_photo(job["chat_id"], _fix_image(raw), caption, None)


def handle_insta(job):
    """خبر سرور → یه ردیف توی دیتابیس بات قدیمی، بعد همون «🎨 پست اینستاگرام» قدیمی (کاور + فتوشاپ) شروع میشه.
    بقیه‌ی کار (دکمه‌ها، آپلود عکس/PSD، تیتر) با آپدیت‌هایی که سرور می‌فرسته توسط همون کد قدیمی انجام میشه."""
    mod = old_bot()
    n = job["news"]
    guid = "srv:" + str(n["id"])
    facts = {"anime_eng_name": n.get("anime") or "", "archive_photo_file_id": n.get("file_id") or ""}
    event = mod._news_v2_event_type(n.get("title") or "", n.get("summary") or "")
    with mod.db_write_lock:
        conn = mod.db()
        row = conn.execute("SELECT id FROM news_v2_items WHERE source_id=0 AND guid=?", (guid,)).fetchone()
        if row:
            item_id = row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO news_v2_items(source_id, guid, title, url, summary, article_text, image_url, event_type,"
                " anime_eng_name, anime_display, facts_json, caption, status) VALUES(0,?,?,?,?,?,?,?,?,?,?,?,'archived')",
                (guid, n.get("title") or "", n.get("link") or "", n.get("summary") or "", n.get("summary") or "",
                 n.get("image") or "", event, facts["anime_eng_name"], facts["anime_eng_name"],
                 json.dumps(facts, ensure_ascii=False), n.get("caption") or ""))
            item_id = cur.lastrowid
            conn.commit()
        conn.close()
    import threading
    threading.Thread(target=mod._insta_start_safe, args=(item_id, int(job["uid"])), daemon=True).start()
    return ""


def relay(updates):
    """دکمه‌ها/پیام‌هایی که سرور برای منوی قدیمی فرستاده → همون handlerهای بات قدیمی."""
    mod = old_bot()
    from telebot import types
    mod.bot.process_new_updates([types.Update.de_json(u) for u in updates])


def main():
    if not TG_CLOUD or ":" not in TG_CLOUD:
        sys.exit("TGCLOUD_TOKEN رو توی .env بذار (BotFather → Serverless → CLI Access → Access token).")
    if "--tick" in sys.argv or "--loop" in sys.argv:              # گیت‌هاب: چک خبرها (یه بار، یا هر ۵ دقیقه تا --minutes)
        minutes = 0
        if "--loop" in sys.argv:
            try:
                minutes = int(sys.argv[sys.argv.index("--loop") + 1])
            except (IndexError, ValueError):
                minutes = 330
        end = time.time() + minutes * 60
        while True:
            if os.environ.get("GITHUB_ACTIONS"):                    # کد جدید push شده باشه، همین الان استفاده بشه
                os.system("git pull -q --ff-only >/dev/null 2>&1")
            try:
                r = cloud("collect")
                log(f"checked={r.get('checked')} added={r.get('added')} low={r.get('low', 0)} "
                    f"errors={len(r.get('errors') or [])}")
                for e in r.get("errors") or []:
                    log(f"   ⚠️ {e}")
            except Exception as exc:
                log(f"⚠️ {exc}")
            if time.time() + 300 > end:
                return
            time.sleep(300)
    if not TOKEN:
        sys.exit("NEWS_BOT_TOKEN رو توی .env بذار.")
    log("✅ برنامه‌ی کامپیوتر بات خبری روشنه (Ctrl+C برای بستن)")
    last_collect = 0
    busy_until = 0
    while True:
        try:
            if time.time() - last_collect > 300:                 # چک خبرها (اگه Serverless خودش زمان‌بندی نداشت)
                last_collect = time.time()
                r = cloud("collect")
                if r.get("added"):
                    log(f"📰 {r['added']} خبر جدید")
            polled = cloud("poll")
            if polled.get("updates"):
                busy_until = time.time() + 15 * 60
                try:
                    relay(polled["updates"])
                except Exception as exc:
                    log(f"⚠️ منوی اینستاگرام: {exc}")
            for job in polled.get("jobs") or []:
                kind = job.get("type")
                log({"rank": f"📊 ساخت کارت رنکینگ {job.get('source')} …",
                     "insta": f"🎨 پست اینستاگرام: {str(job.get('news', {}).get('title', ''))[:60]} …"}.get(
                    kind, f"🖼 درست کردن عکس خبر {job.get('news_id')} …"))
                if kind == "insta":
                    busy_until = time.time() + 15 * 60
                try:
                    fid = {"rank": handle_rank, "insta": handle_insta}.get(kind, handle)(job)
                    cloud("done", result={"job_id": job["id"], "ok": True, "file_id": fid})
                    log("   ✅ فرستاده شد")
                except Exception as exc:
                    cloud("done", result={"job_id": job["id"], "ok": False, "error": str(exc)[:300]})
                    log(f"   ❌ {exc}")
        except KeyboardInterrupt:
            raise
        except Exception:
            log("⚠️ " + traceback.format_exc(limit=1).strip().splitlines()[-1])
        time.sleep(2 if time.time() < busy_until else 20)       # وسط کار اینستاگرام: دکمه‌ها سریع جواب بدن


if __name__ == "__main__":
    main()
