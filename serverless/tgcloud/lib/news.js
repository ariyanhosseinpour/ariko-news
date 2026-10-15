// منطق اصلی بات خبری روی Telegram Serverless (کارهای سبک).
// کارهای سنگین (درست کردن عکسی که تلگرام لینکش رو قبول نمی‌کنه) به صورت «job» برای برنامه‌ی کامپیوتر
// (serverless_agent.py) می‌مونه؛ تا وقتی کامپیوتر روشن نشده، خبر بدون عکس منتشر نمیشه.
import { DEFAULT_FEEDS, parseFeed, parseArticle, hashKey, SYSTEM_PROMPT, buildPrompt, extractCaption, postCaption,
         escapeHtml } from "./core.js";

export const OWNER_ID = 513902877;
const MAX_NEW_PER_RUN = 3;                                  // هر بار چک (هر ۵ دقیقه) حداکثر ۳ خبر جدید؛ سبک بمونه
const DEFAULT_MODELS = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-flash-lite-latest"];
const DEFAULT_FOOTER = "آریکو تی وی | @Ariko_Tv";

// ───────── تنظیمات ─────────
export async function cfg(p, key, def = null) {
  const v = await p.kv.get("cfg:" + key);
  return v === null || v === undefined ? def : v;
}
export const setCfg = (p, key, value) => p.kv.set("cfg:" + key, value);

export async function admins(p) {
  return [...new Set([OWNER_ID, ...((await cfg(p, "admins", [])) || [])])];
}
export async function isAdmin(p, uid) {
  return (await admins(p)).includes(Number(uid));
}
export async function feeds(p) {
  return (await cfg(p, "feeds", null)) || DEFAULT_FEEDS;
}
// ───────── عکس: اول با لینک، اگه تلگرام قبول نکرد خود سرور دانلود و آپلود می‌کنه ─────────
const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];

/** sendPhoto با لینک؛ اگه نشد، عکس رو خود Serverless دانلود و آپلود می‌کنه (تا ۱۰ مگ و JPEG/PNG/WEBP).
 *  فقط اگه این هم نشد (عکس خیلی بزرگ یا فرمت ناجور یا سایت دانلود رو بست) خطا میده → کار برای کامپیوتر. */
async function sendPhotoSmart(p, params, news) {
  try {
    return await p.api("sendPhoto", params);
  } catch (first) {
    if (news.file_id || !news.image || !p.InputFile) throw first;
    let res;
    try {
      res = await p.fetch(news.image, { headers: { "User-Agent": "Mozilla/5.0", "Referer": news.link } });
    } catch (e) { throw new Error(`دانلود عکس نشد (${e.message})`); }
    const type = (res.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
    if (!res.ok) throw new Error(`سایت عکس رو نداد (HTTP ${res.status})`);
    if (!PHOTO_TYPES.includes(type)) throw new Error(`فرمت عکس (${type || "نامعلوم"}) باید تبدیل بشه`);
    const bytes = await readBytes(res, 10 * 1024 * 1024);
    if (!bytes) throw new Error("عکس بزرگ‌تر از ۱۰ مگه");
    if (!bytes.length) throw first;
    const ext = type.split("/")[1].replace("jpeg", "jpg");
    return await p.api("sendPhoto", { ...params, photo: new p.InputFile(bytes, `news.${ext}`, { type }) });
  }
}

/** بدنه‌ی جواب به صورت بایت (fetch پلتفرم فقط stream داره)؛ بیشتر از max → null */
async function readBytes(res, max) {
  const parts = [];
  let size = 0;
  for await (const chunk of res.body) {
    size += chunk.length;
    if (size > max) return null;
    parts.push(chunk);
  }
  const out = new Uint8Array(size);
  let off = 0;
  for (const c of parts) { out.set(c, off); off += c.length; }
  return out;
}

function photoId(msg) {
  const sizes = (msg && msg.photo) || [];
  return sizes.length ? sizes[sizes.length - 1].file_id : "";
}

async function notifyAdmins(p, text, extra = {}) {
  for (const id of await admins(p)) {
    try { await p.api("sendMessage", { chat_id: id, text, parse_mode: "HTML", disable_web_page_preview: true, ...extra }); }
    catch (e) { /* ادمینی که بات رو بلاک کرده */ }
  }
}

// ───────── Gemini ─────────
export async function geminiCaption(p, item) {
  const key = await cfg(p, "gemini_key", "");
  if (!key) throw new Error("کلید Gemini ثبت نشده (/setgemini)");
  const models = [await cfg(p, "model", ""), ...DEFAULT_MODELS].filter(Boolean);
  let lastErr = "";
  for (const model of [...new Set(models)]) {
    const res = await p.fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] },
        contents: [{ role: "user", parts: [{ text: buildPrompt(item) }] }],
        generationConfig: { temperature: 0.1, maxOutputTokens: 900 },
      }),
    });
    if (!res.ok) { lastErr = `${model}: HTTP ${res.status}`; continue; }
    const data = await res.json();
    const raw = ((data.candidates || [])[0]?.content?.parts || []).map(x => x.text || "").join("");
    const cap = extractCaption(raw);
    if (cap) return { caption: cap, model };
    lastErr = `${model}: کپشن خالی`;
  }
  throw new Error(lastErr || "Gemini جواب نداد");
}

// ───────── جمع‌آوری خبر ─────────
export async function collect(p) {
  const report = { checked: 0, added: 0, errors: [] };
  for (const f of await feeds(p)) {
    if (report.added >= MAX_NEW_PER_RUN) break;
    let items = [];
    try {
      const res = await p.fetch(f.url, { headers: { "User-Agent": "Mozilla/5.0 (ARIKO news)" } });
      items = parseFeed(await res.text());
    } catch (e) { report.errors.push(`${f.name}: ${e.message}`); continue; }
    const first = !(await p.kv.get("feedinit:" + hashKey(f.url)));
    for (const it of items.slice(0, 15)) {
      report.checked++;
      const seenKey = "seen:" + hashKey(it.link);
      if (await p.kv.get(seenKey)) continue;
      if (!first && report.added >= MAX_NEW_PER_RUN) break;  // بقیه برای چک بعدی می‌مونن (گم نمی‌شن)
      await p.kv.set(seenKey, 1);
      if (first) continue;                                    // بار اول فقط علامت‌گذاری (سیل خبرهای قدیمی نیاد)
      try {
        await addNews(p, f, it);
        report.added++;
      } catch (e) { report.errors.push(`${it.title.slice(0, 40)}: ${e.message}`); }
    }
    if (first) await p.kv.set("feedinit:" + hashKey(f.url), 1);
  }
  await setCfg(p, "last_collect", { at: Date.now(), ...report });
  return report;
}

async function addNews(p, feed, it) {
  let article = { image: "", text: "" };
  try {
    const res = await p.fetch(it.link, { headers: { "User-Agent": "Mozilla/5.0 (ARIKO news)" } });
    if (res.ok) article = parseArticle(await res.text());
  } catch (e) { /* صفحه باز نشد؛ همون خلاصه‌ی RSS */ }
  const item = { title: it.title, link: it.link, published: it.published, summary: it.summary, text: article.text };
  const { caption, model } = await geminiCaption(p, item);
  const id = hashKey(it.link + Date.now());
  const news = { id, title: it.title, link: it.link, source: feed.name, image: article.image || it.image || "",
                 caption, model, status: "pending", file_id: "", created: Date.now() };
  await p.kv.set("news:" + id, news);
  await preview(p, news);
}

function reviewKeyboard(id) {
  return { inline_keyboard: [[{ text: "✅ انتشار", callback_data: `nw:ok:${id}` },
                              { text: "❌ رد", callback_data: `nw:no:${id}` }]] };
}

function previewText(p, news) {
  return `${escapeHtml(news.caption)}\n\n— <i>${escapeHtml(news.source)}</i> · 🤖 ${escapeHtml(news.model || "")}`;
}

// ───────── پیش‌نمایش برای ادمین ─────────
export async function preview(p, news) {
  const photo = news.file_id || news.image;
  if (!photo) return needImage(p, news, "عکسی برای این خبر پیدا نشد", "preview");
  let ok = 0;
  for (const id of await admins(p)) {
    try {
      const msg = await sendPhotoSmart(p, { chat_id: id, photo: news.file_id || photo,
                                            caption: previewText(p, news).slice(0, 1024),
                                            parse_mode: "HTML", reply_markup: reviewKeyboard(news.id) }, news);
      ok++;
      if (!news.file_id && photoId(msg)) {                   // دفعه‌های بعد با file_id (بدون دانلود دوباره)
        news.file_id = photoId(msg);
        await p.kv.set("news:" + news.id, news);
      }
    } catch (e) {
      if (!ok) return needImage(p, news, `عکس فرستاده نشد: ${String(e.description || e.message || e).slice(0, 120)}`, "preview");
    }
  }
}

// ───────── خبری که عکسش مشکل داره → کار برای کامپیوتر ─────────
export async function needImage(p, news, reason, after) {
  news.status = "needs_image";
  await p.kv.set("news:" + news.id, news);
  const job = { id: "j" + news.id, type: "image", news_id: news.id, image: news.image, page: news.link, after,
                created: Date.now(), taken: 0,
                chat_id: after === "post" ? await cfg(p, "channel", "") : OWNER_ID,
                caption: after === "post" ? postCaption(news.caption, await cfg(p, "footer", DEFAULT_FOOTER))
                                          : previewText(p, news).slice(0, 1024),
                reply_markup: after === "post" ? null : reviewKeyboard(news.id) };
  await p.kv.set("job:" + job.id, job);
  await notifyAdmins(p,
    `🖥 <b>این خبر عکس لازم داره</b>\n«${escapeHtml(news.title)}»\n\n⚠️ ${escapeHtml(reason)}\n\n` +
    "خبر بدون عکس منتشر نمیشه؛ <b>سیستم رو روشن کن</b> (serverless_agent) تا عکس رو درست کنه و " +
    (after === "post" ? "خودش توی کانال منتشر کنه." : "پیش‌نمایش رو برات بفرسته."),
    { reply_markup: { inline_keyboard: [[{ text: "❌ این خبر رو رد کن", callback_data: `nw:no:${news.id}` }]] } });
}

// ───────── انتشار ─────────
export async function publish(p, id) {
  const news = await p.kv.get("news:" + id);
  if (!news) return "این خبر پیدا نشد";
  if (news.status === "posted") return "قبلاً منتشر شده";
  const channel = await cfg(p, "channel", "");
  if (!channel) return "کانال ثبت نشده (/setchannel)";
  const photo = news.file_id || news.image;
  const caption = postCaption(news.caption, await cfg(p, "footer", DEFAULT_FOOTER));
  if (!photo) { await needImage(p, news, "عکسی برای این خبر نیست", "post"); return "عکس لازم داره؛ سیستم رو روشن کن"; }
  try {
    await sendPhotoSmart(p, { chat_id: channel, photo, caption, parse_mode: "HTML" }, news);
  } catch (e) {
    await needImage(p, news, `فرستادن عکس به کانال نشد: ${String(e.description || e.message || e).slice(0, 120)}`, "post");
    return "عکس لازم داره؛ سیستم رو روشن کن";
  }
  news.status = "posted";
  await p.kv.set("news:" + id, news);
  return "✅ منتشر شد";
}

export async function reject(p, id) {
  const news = await p.kv.get("news:" + id);
  if (!news) return "این خبر پیدا نشد";
  news.status = "rejected";
  await p.kv.set("news:" + id, news);
  await p.kv.del("job:j" + id);
  return "❌ رد شد";
}

// ───────── برای برنامه‌ی کامپیوتر (از طریق «tgcloud run»؛ serverless_agent.py) ─────────
export async function agentPoll(p) {
  await setCfg(p, "agent_seen", Date.now());
  const now = Date.now();
  const jobs = [];
  for (const { value: job } of await p.kv.list("job:")) {
    if (job.taken && now - job.taken < 10 * 60 * 1000) continue;   // یکی دیگه داره روش کار می‌کنه
    job.taken = now;
    await p.kv.set("job:" + job.id, job);
    jobs.push(job);
  }
  return jobs;
}

export async function agentDone(p, { job_id, ok, file_id, error }) {
  const job = await p.kv.get("job:" + job_id);
  if (!job) return { ok: true };
  const news = await p.kv.get("news:" + job.news_id);
  if (!ok) {
    job.taken = 0;
    job.error = String(error || "").slice(0, 200);
    await p.kv.set("job:" + job_id, job);
    await notifyAdmins(p, `⚠️ کامپیوتر نتونست عکس «${escapeHtml(news ? news.title : job_id)}» رو درست کنه:\n${escapeHtml(job.error)}`);
    return { ok: true };
  }
  await p.kv.del("job:" + job_id);
  if (news) {
    news.file_id = file_id || news.file_id;
    news.status = job.after === "post" ? "posted" : "pending";
    await p.kv.set("news:" + news.id, news);
    if (job.after !== "post") {                               // کامپیوتر برای صاحب ربات فرستاد؛ بقیه‌ی ادمین‌ها با file_id
      for (const id of (await admins(p)).filter(x => x !== OWNER_ID)) {
        try { await p.api("sendPhoto", { chat_id: id, photo: news.file_id, caption: job.caption, parse_mode: "HTML",
                                         reply_markup: job.reply_markup }); } catch (e) { /* */ }
      }
    }
  }
  return { ok: true };
}
