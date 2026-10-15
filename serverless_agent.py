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
import { parseArticle } from '../lib/core.js';
import { agentPoll, agentDone, collect, agentUpdates, prefetchPlan, diagnose, recoverLost, clearImageJobs, redoNews } from '../lib/news.js';
export default async function (input) {
  const p = platform();
  if (input.op === 'poll') return { jobs: await agentPoll(p), updates: await agentUpdates(p) };
  if (input.op === 'done') return await agentDone(p, input.result || {});
  if (input.op === 'collect') return await collect(p, input.prefetched || null);
  if (input.op === 'parse') { const a = parseArticle(input.html || ''); return { images: a.images, videos: a.videos, image: a.image }; }
  if (input.op === 'redo') return await redoNews(p, input.words || []);
  if (input.op === 'clearjobs') return await clearImageJobs(p);
  if (input.op === 'recover') return await recoverLost(p, input.prefetched || null);
  if (input.op === 'diagnose') return await diagnose(p, input.prefetched || null);
  if (input.op === 'plan') return { urls: await prefetchPlan(p, !!input.force) };
  return { error: 'unknown op' };
}
"""


REPO_ZIP = "https://codeload.github.com/ariyanhosseinpour/ariko-news/zip/refs/heads/main"
AUTO_UPDATE = os.environ.get("AGENT_AUTO_UPDATE", "1") != "0" and not os.environ.get("GITHUB_ACTIONS")
_remote = {"at": 0, "files": None}


def _remote_files():
    """آخرین نسخه‌ی کد از گیت‌هاب (هر ۱۰ دقیقه)، که برنامه‌ی کامپیوتر هیچ‌وقت با کد قدیمی کار نکنه."""
    if not AUTO_UPDATE:
        return None
    if _remote["files"] is not None and time.time() - _remote["at"] < 600:
        return _remote["files"]
    _remote["at"] = time.time()
    try:
        import zipfile
        with urllib.request.urlopen(urllib.request.Request(REPO_ZIP, headers={"User-Agent": "ariko-agent"}), timeout=30) as r:
            z = zipfile.ZipFile(io.BytesIO(r.read()))
        files = {}
        for name in z.namelist():
            rel = name.split("/", 1)[1] if "/" in name else ""
            if rel == "serverless_agent.py" or (rel.startswith("serverless/tgcloud/") and rel.endswith(".js")):
                files[rel] = z.read(name).decode("utf-8")
        if any(k.startswith("serverless/tgcloud/") for k in files):
            _remote["files"] = files
            _self_update(files.get("serverless_agent.py"))
    except Exception as exc:
        log(f"⚠️ گرفتن کد جدید از گیت‌هاب نشد (با کد خود کامپیوتر ادامه میده): {exc}")
    return _remote["files"]


def _self_update(code):
    me = os.path.abspath(__file__)
    if not code:
        return
    with open(me, encoding="utf-8") as fh:
        if fh.read().replace("\r\n", "\n") == code.replace("\r\n", "\n"):
            return
    with open(me, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(code)
    log("🔄 برنامه آپدیت شد؛ اجرای دوباره…")
    os.execv(sys.executable, [sys.executable, me] + sys.argv[1:])


def _sources():
    remote = _remote_files()
    if remote:
        out = {k[len("serverless/tgcloud/"):-3]: v for k, v in remote.items() if k.startswith("serverless/tgcloud/")}
        out["endpoints/pc_agent"] = PC_MODULE
        return out
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


BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/130.0 Safari/537.36")
X_AUTH_TOKEN = os.environ.get("X_AUTH_TOKEN", "").strip()   # کوکی لاگین X (اختیاری؛ همون که بات قدیمی داشت)


def prefetch():
    """صفحه‌هایی که سرور تلگرام بهشون دسترسی نداره (X، سایت‌هایی که بلاکش کردن) اینجا گرفته میشن."""
    out = {}
    for item in cloud("plan", force="--force" in sys.argv).get("urls") or []:
        url = item["url"]
        headers = {"User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9",
                   "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
        if item.get("x") and X_AUTH_TOKEN:
            headers["Cookie"] = f"auth_token={X_AUTH_TOKEN}"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=40) as resp:
                text = resp.read(3_000_000).decode("utf-8", "ignore")
                status = resp.status
        except urllib.error.HTTPError as exc:
            out[url] = {"status": exc.code, "text": ""}
            continue
        except Exception as exc:
            out[url] = {"error": str(exc)[:150]}
            continue
        if item.get("x"):                                       # از صفحه‌ی X فقط داده‌ی پست‌ها لازمه
            m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>.*?</script>', text, re.S | re.I)
            text = m.group(0) if m else text[:2000]
        out[url] = {"status": status, "text": text[:1_500_000]}
    return out


def collect_now():
    try:
        pre = prefetch()
    except Exception as exc:
        log(f"⚠️ prefetch: {exc}")
        pre = {}
    if pre:
        log("   🌐 " + ", ".join(f"{urllib.parse.urlparse(u).netloc}{'' if v.get('status') == 200 else ' ✗' + str(v.get('status') or v.get('error'))}"
                                for u, v in pre.items()))
    return cloud("collect", prefetched=pre)


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
        orig_clean = mod._insta_clean_title

        def clean_title(title, name):                             # اسم لاتین توی [] تا توی کاور زرد بشه (حتی اگه AI کوتاهش کرده)
            t = orig_clean(title, name)
            if "[" not in t:
                runs = re.findall(r"[A-Za-z0-9][A-Za-z0-9 :!'’&.\-]*[A-Za-z0-9!']", t)
                best = max([r for r in runs if re.search(r"[A-Za-z]{2}", r)], key=len, default="")
                if len(best) >= 3:
                    t = t.replace(best, f"[{best}]", 1)
            return t
        mod._insta_clean_title = clean_title
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
            conn.execute("UPDATE news_v2_items SET anime_eng_name=?, anime_display=?, facts_json=?, caption=?, event_type=?"
                         " WHERE id=?", (facts["anime_eng_name"], facts["anime_eng_name"], json.dumps(facts, ensure_ascii=False),
                                         n.get("caption") or "", event, item_id))
            conn.commit()
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


def _find_trailer(mod, job):
    """لینک تریلر توی خبر نبود → مثل بات قدیمی توی یوتیوب (اسم ژاپنی/رومانجی + PV)؛ فقط ویدیوهای تازه."""
    from email.utils import parsedate_to_datetime
    anime = (job.get("anime") or "").strip()
    meta = (mod._news_anilist_lookup(anime) or {}) if len(anime) >= 3 else {}
    names = [anime, meta.get("title_en"), meta.get("title_romaji"), meta.get("title_native")]
    names = [n for i, n in enumerate(names) if n and n not in names[:i]]
    if not names:
        raise RuntimeError("اسم انیمه معلوم نیست که توی یوتیوب دنبال تریلرش بگردم")
    queries = ([f"{meta['title_native']} PV"] if meta.get("title_native") else []) + \
              [f"{meta.get('title_romaji') or anime} PV", f"{anime} trailer"]
    results, seen, errs = [], set(), []
    for q in queries:
        try:
            for r in mod._trailer_search(q, by_date=True, count=8):
                if r["url"] not in seen:
                    seen.add(r["url"])
                    results.append(r)
        except Exception as exc:
            errs.append(str(exc))
            log(f"   ⚠️ جستجوی یوتیوب: {exc}")
    if not results and errs:
        raise RuntimeError("جستجوی یوتیوب خطا داد (yt-dlp رو آپدیت کن: pip install -U yt-dlp): " + errs[-1][:150])
    try:
        news_ts = parsedate_to_datetime(job.get("published") or "").timestamp()
    except Exception:
        news_ts = time.time()
    fresh = []
    for r in results:
        if mod._TRAILER_JUNK_RE.search(r["title"]) or not mod._trailer_name_match(names, r["title"]):
            continue
        up = mod._trailer_upload_ts(r["url"])
        if up and not (news_ts - mod.TRAILER_MAX_AGE_DAYS * 86400 <= up <= news_ts + 3 * 86400):
            continue
        fresh.append(r)
        if len(fresh) >= 3:
            break
    pick, sure = mod._trailer_pick(names, fresh)
    if not pick:
        raise RuntimeError(f"تریلر تازه‌ای توی یوتیوب پیدا نشد ({len(results)} نتیجه بررسی شد، اسم: {names[0]})")
    return pick["url"], sure


def handle_trailer(job):
    """تریلر رو دانلود می‌کنه (بهترین کیفیت زیر ۵۰ مگ) و با کپشن خبر، یه پیام، برای صاحب بات می‌فرسته."""
    mod = old_bot()
    url, note = job.get("url") or "", ""
    if not url:
        url, sure = _find_trailer(mod, job)
        note = "از جستجوی یوتیوب پیدا شد" + ("" if sure else "؛ مطمئن نیستم خودشه، قبل از انتشار ببینش")
    too_big = None
    for height in [mod.TRAILER_HEIGHT] + list(mod.TRAILER_LOWER_HEIGHTS):
        path = ""
        try:
            path = mod._trailer_download(url, height)
            send_path, vmeta = mod._trailer_prepare(path)
            with open(send_path, "rb") as fh:                        # آپلود بی‌صدا؛ سرور پیش‌نمایش اصلی (با پوسترها) رو می‌سازه
                msg = mod._send_video_with_meta(int(job["chat_id"]), fh, vmeta, caption="🎬 در حال آماده‌سازی تریلر…",
                                                disable_notification=True, supports_streaming=True)
            log(f"   🎬 تریلر {height}p آپلود شد")
            return {"file_id": msg.video.file_id, "message_id": msg.message_id, "note": note}
        except mod.TrailerTooBig as exc:
            too_big = exc
        finally:
            if path:
                mod._trailer_cleanup(path)
    raise RuntimeError(f"حجم تریلر حتی با کیفیت پایین هم از ۵۰ مگ بیشتره ({too_big})")


def relay(updates):
    """دکمه‌ها/پیام‌هایی که سرور برای منوی قدیمی فرستاده → همون handlerهای بات قدیمی."""
    mod = old_bot()
    from telebot import types
    mod.bot.process_new_updates([types.Update.de_json(u) for u in updates])


def main():
    if not TG_CLOUD or ":" not in TG_CLOUD:
        sys.exit("TGCLOUD_TOKEN رو توی .env بذار (BotFather → Serverless → CLI Access → Access token).")
    if "--probe" in sys.argv:                                    # عیب‌یابی: یه صفحه‌ی خبر چه ویدیو/عکسی داره
        url = sys.argv[sys.argv.index("--probe") + 1]
        html = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": BROWSER_UA}), timeout=40).read().decode("utf-8", "ignore")
        log(f"len={len(html)}")
        r = cloud("parse", html=html[:1_500_000])
        log(f"og={r.get('image')}\nvideos={r.get('videos')}")
        for u in r.get("images") or []:
            log(f"   🖼 {u}")
        for pat in (r"youtube[^\s\"'<>]{0,80}", r"youtu\.be/[^\s\"'<>]{0,20}", r"lite-youtube[^>]{0,120}", r"data-(?:video-)?id=[\"'][^\"']{6,20}", r"<iframe[^>]{0,200}"):
            for m in list(dict.fromkeys(re.findall(pat, html)))[:8]:
                log(f"   {m}")
        return
    if "--redo" in sys.argv:                                     # --redo "One-Punch|Black Clover" → از نو ساخته میشن
        words = sys.argv[sys.argv.index("--redo") + 1].split("|")
        r = cloud("redo", words=words)
        log(f"♻️ {len(r.get('redone') or [])} خبر از نو ساخته میشه:")
        for t in r.get("redone") or []:
            log(f"   {t}")
        return
    if "--clear-jobs" in sys.argv:
        log(f"🧹 پاک شد: {cloud('clearjobs').get('gone')}")
        return
    if "--recover" in sys.argv:                                  # خبرهای مهمِ گم‌شده دوباره توی صف چک
        r = cloud("recover", prefetched=prefetch())
        log(f"♻️ {len(r.get('recovered') or [])} خبر برگشت:")
        for t in r.get("recovered") or []:
            log(f"   {t}")
        return
    if "--diagnose" in sys.argv:                                 # عیب‌یابی: خبرهای الان هر فید + دیده‌شده؟ + امتیاز
        r = cloud("diagnose", prefetched=prefetch())
        log(f"min_importance={r.get('minImp')}")
        log(f"Gemini: {r.get('gemini')}")
        for it in r.get("items") or []:
            if it.get("error"):
                log(f"[{it['src']}] ⚠️ {it['error']}")
            else:
                log(f"[{it['src']}] {'دیده‌شده' if it['seen'] else 'جدید':8} {it['score']:>3} {'✅' if it['pass'] else '—'} "
                    f"{it['published'][:22]:22} {it['title']}")
        return
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
                me = os.path.abspath(__file__)
                before = os.path.getmtime(me)
                os.system("git pull -q --ff-only >/dev/null 2>&1")
                if os.path.getmtime(me) != before:                    # خود این برنامه عوض شد → با بقیه‌ی وقت از نو
                    left = max(0, int((end - time.time()) / 60))
                    log("🔄 کد جدید؛ اجرای دوباره")
                    os.execv(sys.executable, [sys.executable, me, "--loop", str(left)])
            try:
                r = collect_now()
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
                r = collect_now()
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
                log({"trailer": f"🎬 تریلر: {str(job.get('title', ''))[:60]} …",
                     "rank": f"📊 ساخت کارت رنکینگ {job.get('source')} …",
                     "insta": f"🎨 پست اینستاگرام: {str(job.get('news', {}).get('title', ''))[:60]} …"}.get(
                    kind, f"🖼 درست کردن عکس خبر {job.get('news_id')} …"))
                if kind == "insta":
                    busy_until = time.time() + 15 * 60
                try:
                    fid = {"rank": handle_rank, "insta": handle_insta, "trailer": handle_trailer}.get(kind, handle)(job)
                    extra = fid if isinstance(fid, dict) else {"file_id": fid}
                    cloud("done", result={"job_id": job["id"], "ok": True, **extra})
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
