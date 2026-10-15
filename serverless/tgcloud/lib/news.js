// منطق اصلی بات خبری روی Telegram Serverless (کارهای سبک).
// کارهای سنگین (درست کردن عکسی که تلگرام لینکش رو قبول نمی‌کنه) به صورت «job» برای برنامه‌ی کامپیوتر
// (serverless_agent.py) می‌مونه؛ تا وقتی کامپیوتر روشن نشده، خبر بدون عکس منتشر نمیشه.
import { AGENT_SYSTEM, agentUserPrompt, parseJson, validate, releasePlausible, localizeDate, renderCaption } from "./caption.js";
import { DEFAULT_FEEDS, importance, eventType, guessAnimeName, DEFAULT_MIN_IMPORTANCE, parseFeed, parseArticle, hashKey, isXFeed, xHandle, parseXSyndication, parseXBridge, SYSTEM_PROMPT, buildPrompt, extractCaption, postCaption,
         escapeHtml } from "./core.js";

export const OWNER_ID = 513902877;
const MAX_NEW_PER_RUN = 3;                                  // هر بار چک (هر ۵ دقیقه) حداکثر ۳ خبر جدید؛ سبک بمونه
const DEFAULT_MODELS = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-flash-lite-latest"];
export const DEFAULT_FOOTER = "آریکو تی وی | @Ariko_Tv";

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
  const errors = [];
  for (const model of [...new Set(models)]) {
    // مثل بات قدیمی: «فکر کردن» کم، و اگه جواب نصفه موند با سقف بیشتر دوباره
    for (const [budget, thinking] of [[2048, true], [6000, true], [6000, false]]) {
      const generationConfig = { temperature: 0.1, maxOutputTokens: budget };
      if (thinking) generationConfig.thinkingConfig = { thinkingLevel: "low" };
      let res;
      try {
        res = await p.fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "x-goog-api-key": key },
          body: JSON.stringify({ systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] },
                                 contents: [{ role: "user", parts: [{ text: buildPrompt(item) }] }], generationConfig }),
        });
      } catch (e) { errors.push(`${model}: ${e.message}`); break; }
      if (!res.ok) {
        let msg = "";
        try { msg = ((await res.json()).error || {}).message || ""; } catch (e) { /* */ }
        if (res.status === 400 && /thinking/i.test(msg) && thinking) continue;   // این مدل thinkingConfig رو نمی‌شناسه
        errors.push(`${model}: HTTP ${res.status} ${msg.slice(0, 80)}`);
        break;                                                  // 404 (مدل نیست) / 429 / 5xx → مدل بعدی
      }
      const data = await res.json();
      const cand = (data.candidates || [])[0] || {};
      const raw = ((cand.content || {}).parts || []).filter((x) => !x.thought).map((x) => x.text || "").join("");
      const cap = extractCaption(raw);
      if (cap) return { caption: cap, model };
      errors.push(`${model}: کپشن خالی (${cand.finishReason || "?"})`);
      if (cand.finishReason !== "MAX_TOKENS") break;
    }
  }
  throw new Error(errors.slice(-3).join(" | ") || "Gemini جواب نداد");
}

// ───────── کپشن مثل بات قدیمی: Gemini با دستور کانال → JSON → چک با منبع → کپشن ─────────
async function geminiRaw(p, system, user, json) {
  const key = await cfg(p, "gemini_key", "");
  if (!key) throw new Error("کلید Gemini ثبت نشده");
  const models = [await cfg(p, "model", ""), ...DEFAULT_MODELS].filter(Boolean);
  const errors = [];
  for (const model of [...new Set(models)]) {
    for (const [budget, thinking] of [[4096, true], [8000, true], [8000, false]]) {
      const generationConfig = { temperature: 0.2, maxOutputTokens: budget };
      if (json) generationConfig.responseMimeType = "application/json";
      if (thinking) generationConfig.thinkingConfig = { thinkingLevel: "low" };
      let res;
      try {
        res = await p.fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "x-goog-api-key": key },
          body: JSON.stringify({ contents: [{ role: "user", parts: [{ text: `${system}\n\n${user}` }] }], generationConfig }),
        });
      } catch (e) { errors.push(`${model}: ${e.message}`); break; }
      if (!res.ok) {
        let msg = "";
        try { msg = ((await res.json()).error || {}).message || ""; } catch (e) { /* */ }
        if (res.status === 400 && /thinking/i.test(msg) && thinking) continue;
        errors.push(`${model}: HTTP ${res.status} ${msg.slice(0, 80)}`);
        break;
      }
      const cand = ((await res.json()).candidates || [])[0] || {};
      const text = ((cand.content || {}).parts || []).filter((x) => !x.thought).map((x) => x.text || "").join("");
      if (text.trim() && cand.finishReason !== "MAX_TOKENS") return { text, model };
      errors.push(`${model}: جواب ناقص (${cand.finishReason || "?"})`);
      if (cand.finishReason !== "MAX_TOKENS") break;
    }
  }
  throw new Error(errors.slice(-3).join(" | ") || "Gemini جواب نداد");
}

/** خروجی: { render, model, importance } یا { notNews: true } */
export async function agentCaption(p, item, meta) {
  const user = agentUserPrompt(item, meta, !!item.leak);
  let reason = "";
  for (let attempt = 0; attempt < 2; attempt++) {
    const { text, model } = await geminiRaw(p, AGENT_SYSTEM, attempt ? `${user}\n\nYOUR PREVIOUS OUTPUT WAS REJECTED: ${reason}. Fix it and follow the rules exactly.` : user, true);
    const [parts, why] = validate(parseJson(text), item, meta);
    if (why === "not_news") return { notNews: true, model };
    if (parts) {
      let dateFa = "";
      if (parts.release && releasePlausible(parts.release, item.published)) {
        try { dateFa = localizeDate(parts.release, item.published); } catch (e) { /* */ }
      }
      let studio = parts.studio;
      if (!studio && meta && meta.studio && Number(meta.year || 0) >= new Date().getUTCFullYear() - 1) studio = meta.studio;
      return { model, importance: parts.importance, animeTitle: parts.animeTitle,
               render: { emoji: parts.emoji, headline: parts.headline, details: parts.details, synopsis: parts.synopsis,
                         dateFa, studio, unofficial: !!item.leak } };
    }
    reason = why;
  }
  throw new Error(`خروجی AI رد شد: ${reason}`);
}

// ───────── جمع‌آوری خبر ─────────
export async function collect(p, pre = null) {
  const report = { checked: 0, added: 0, low: 0, errors: [] };
  const minImp = Number(await cfg(p, "min_importance", DEFAULT_MIN_IMPORTANCE));
  for (const f of await feeds(p)) {
    if (f.active === false) continue;                         // منبع غیرفعال
    if (report.added >= MAX_NEW_PER_RUN) break;
    let items = [];
    const stateKey = "feedstate:" + hashKey(f.url);
    const prev = await p.kv.get(stateKey);
    const preHit = pre && isXFeed(f) && pre[xUrl(xHandle(f))];
    if (isXFeed(f) && !preHit && prev && Date.now() - prev.at < (prev.wait || X_EVERY_MS)) continue;   // X رو کمتر بپرس که محدود نکنه
    try {
      items = await fetchItems(p, f, pre);
      const via = pre && (pre[f.url] || (isXFeed(f) && pre[xUrl(xHandle(f))])) ? "pre" : "";
      await p.kv.set(stateKey, { at: Date.now(), error: items.length ? "" : "هیچ خبری توی فید پیدا نشد", via });
    } catch (e) {
      report.errors.push(`${f.name}: ${e.message}`);
      const wait = isXFeed(f) ? Math.min(3 * 3600e3, Math.max(X_EVERY_MS, ((prev && prev.wait) || X_EVERY_MS) * 2)) : 0;
      await p.kv.set(stateKey, { at: Date.now(), error: String(e.message || e).slice(0, 180), wait,
                                 via: (prev && prev.via) || "" });
      continue;
    }
    const first = !(await p.kv.get("feedinit:" + hashKey(f.url)));
    for (const it of items.slice(0, 15)) {
      report.checked++;
      const seenKey = "seen:" + hashKey(it.link);
      if (await p.kv.get(seenKey)) continue;
      if (!first && report.added >= MAX_NEW_PER_RUN) break;  // بقیه برای چک بعدی می‌مونن (گم نمی‌شن)
      await p.kv.set(seenKey, 1);
      if (first) continue;                                    // بار اول فقط علامت‌گذاری (سیل خبرهای قدیمی نیاد)
      if (it.leak && !it.image) { await logDecision(p, f, it, null, "🖼 پست X بدون عکس"); continue; }
      const official = /official/i.test(f.name) || /crunchyroll/i.test(f.name + f.url);
      let imp = importance(it, official);
      if (imp.score < minImp && imp.score + 20 >= minImp) {   // فقط وقتی محبوبیت می‌تونه نتیجه رو عوض کنه، AniList رو بپرس
        imp = importance(it, official, await anilistMeta(p, guessAnimeName(it.title)));
      } else if (imp.score >= minImp) {
        const meta = await anilistMeta(p, guessAnimeName(it.title));   // برای نمایش امتیاز دقیق (کم‌مخاطب هم جریمه داره)
        if (meta) imp = importance(it, official, meta);
      }
      it.importance = imp.score;
      if (it.importance < minImp) {                           // فیلتر اهمیت خبر (قبل از Gemini؛ سهمیه هدر نمیره)
        report.low++;
        await logDecision(p, f, it, imp, `⭐️ کم‌اهمیت (${imp.score} < ${minImp})`);
        continue;
      }
      try {
        if ((await addNews(p, f, it)) === "not_news") {
          await logDecision(p, f, it, imp, "🚫 AI گفت خبر نیست (نقد/راهنما/لیست…)");
        } else {
          report.added++;
          await logDecision(p, f, it, imp, "✅ فرستاده شد");
        }
      } catch (e) {
        report.errors.push(`${it.title.slice(0, 40)}: ${e.message}`);
        await logDecision(p, f, it, imp, `⚠️ خطا: ${String(e.message || e).slice(0, 80)}`);
        const tries = Number((await p.kv.get("retry:" + hashKey(it.link))) || 0) + 1;   // مثلاً Gemini موقتاً جواب نداد
        await p.kv.set("retry:" + hashKey(it.link), tries);
        if (tries < 4) await p.kv.del(seenKey);                // تا ۳ بار دیگه توی چک‌های بعدی دوباره امتحان میشه
      }
    }
    if (first) await p.kv.set("feedinit:" + hashKey(f.url), 1);
  }
  await setCfg(p, "last_collect", { at: Date.now(), ...report });
  return report;
}

// ───────── گزارش: سرنوشت ۳۰ خبر آخر (چرا اومد/نیومد) ─────────
async function logDecision(p, f, it, imp, outcome) {
  const list = (await p.kv.get("decisions")) || [];
  list.unshift({ at: Date.now(), src: f.name, title: String(it.title || "").slice(0, 120), link: it.link,
                 score: imp ? imp.score : null, why: imp ? imp.reasons.join("، ") : "", outcome });
  await p.kv.set("decisions", list.slice(0, 30));
}
export const recentDecisions = async (p) => (await p.kv.get("decisions")) || [];

/** عیب‌یابی: خبرهای الان هر فید، دیده‌شده یا نه، و امتیازشون (بدون تغییر چیزی) */
export async function diagnose(p, pre = null) {
  const out = [];
  const minImp = Number(await cfg(p, "min_importance", DEFAULT_MIN_IMPORTANCE));
  for (const f of await feeds(p)) {
    if (f.active === false) continue;
    let items = [];
    try { items = await fetchItems(p, f, pre); } catch (e) { out.push({ src: f.name, error: e.message }); continue; }
    for (const it of items.slice(0, 8)) {
      const official = /official/i.test(f.name) || /crunchyroll/i.test(f.name + f.url);
      const imp = importance(it, official);
      out.push({ src: f.name, title: it.title.slice(0, 90), seen: !!(await p.kv.get("seen:" + hashKey(it.link))),
                 score: imp.score, pass: imp.score >= minImp, published: it.published || "" });
    }
  }
  let gemini = "";
  try {
    const sample = out.filter((x) => x.title && !x.title.startsWith("@")).sort((a, b) => b.score - a.score)[0];
    const title = sample ? sample.title : "Test anime gets season 2";
    const r = await agentCaption(p, { title, summary: "", text: "", eventType: eventType(title, "") },
                                 await anilistMeta(p, guessAnimeName(title)));
    gemini = r.notNews ? `✅ ${r.model}: (خبر نیست)` : `✅ ${r.model}:\n${renderCaption(r.render, "")}`;
  } catch (e) { gemini = `❌ ${e.message}`; }
  return { minImp, gemini, items: out };
}

/** بازیابی خبرهای مهمی که دیده شدن ولی هیچ‌وقت ساخته نشدن (مثلاً خطای Gemini قبلی) → توی چک‌های بعدی میان */
export async function recoverLost(p, pre = null, maxAgeDays = 3) {
  const minImp = Number(await cfg(p, "min_importance", DEFAULT_MIN_IMPORTANCE));
  const made = new Set((await p.kv.list("news:")).map((r) => r.value && r.value.link).filter(Boolean));
  const recovered = [];
  for (const f of await feeds(p)) {
    if (f.active === false) continue;
    let items = [];
    try { items = await fetchItems(p, f, pre); } catch (e) { continue; }
    for (const it of items.slice(0, 15)) {
      const t = Date.parse(it.published || "");
      if (t && Date.now() - t > maxAgeDays * 86400e3) continue;
      if (made.has(it.link) || (it.leak && !it.image)) continue;
      const official = /official/i.test(f.name) || /crunchyroll/i.test(f.name + f.url);
      if (importance(it, official).score + 20 < minImp) continue;     // حتی با محبوبیت هم رد میشه
      if (!(await p.kv.get("seen:" + hashKey(it.link)))) continue;
      await p.kv.del("seen:" + hashKey(it.link));
      await p.kv.del("retry:" + hashKey(it.link));
      recovered.push(`${f.name}: ${it.title.slice(0, 70)}`);
    }
  }
  return { recovered };
}

/** کارهای عکسِ گیرکرده (که کامپیوتر نمی‌تونه درستشون کنه) رو پاک کن */
export async function clearImageJobs(p) {
  const gone = [];
  for (const { key, value: job } of await p.kv.list("job:")) {
    if (job && job.type !== "rank" && job.type !== "insta") { await p.kv.del(key); gone.push(job.news_id || key); }
  }
  return { gone };
}

// ───────── محبوبیت انیمه از AniList (کش ۷ روزه) ─────────
const ANILIST_QUERY = `query ($s: String) { Media(search: $s, type: ANIME, sort: SEARCH_MATCH) {
  title { romaji english } synonyms popularity startDate { year } genres description(asHtml: false)
  bannerImage coverImage { extraLarge } studios(isMain: true) { nodes { name } } } }`;

export async function anilistMeta(p, name) {
  const norm = String(name || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  if (norm.length < 3) return null;
  const key = "al2:" + hashKey(norm);
  const cached = await p.kv.get(key);
  if (cached && Date.now() - cached.at < (cached.meta ? 7 : 1) * 86400e3) return cached.meta;
  let meta = null;
  try {
    const res = await p.fetch("https://graphql.anilist.co", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ query: ANILIST_QUERY, variables: { s: name.slice(0, 100) } }),
    });
    const m = res.ok ? (((await res.json()) || {}).data || {}).Media : null;
    if (m) {
      // اطمینان از اینکه انیمه‌ی درستی پیدا شده: حداقل یه کلمه‌ی مشترک با اسم
      const words = new Set(norm.split(" ").filter((w) => w.length >= 3));
      const titles = [m.title && m.title.romaji, m.title && m.title.english, ...(m.synonyms || [])].join(" ").toLowerCase();
      if ([...words].some((w) => titles.includes(w))) {
        meta = { popularity: m.popularity || 0, year: (m.startDate || {}).year || 0,
                 title: (m.title && (m.title.english || m.title.romaji)) || "", genres: (m.genres || []).slice(0, 4),
                 description: String(m.description || "").replace(/<[^>]+>/g, " ").replace(/\(Source:[^)]*\)/gi, "")
                   .replace(/\s+/g, " ").trim().slice(0, 1200),
                 banner: m.bannerImage || "", cover: (m.coverImage || {}).extraLarge || "",
                 studio: (((m.studios || {}).nodes || [])[0] || {}).name || "" };
      }
    }
  } catch (e) { return null; }                               // خطای شبکه رو کش نکن
  await p.kv.set(key, { meta, at: Date.now() });
  return meta;
}

const X_EVERY_MS = 15 * 60 * 1000;                           // هر اکانت X حداکثر هر ۱۵ دقیقه یه بار
const BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36";

const xUrl = (handle) => `https://syndication.twitter.com/srv/timeline-profile/screen-name/${encodeURIComponent(handle)}`;

// صفحه‌هایی که سرور تلگرام بهشون دسترسی نداره رو گیت‌هاب/کامپیوتر قبلش می‌گیره و متنشون رو می‌فرسته (prefetched)
async function pget(p, url, headers, pre) {
  const hit = pre && pre[url];
  if (hit) {
    if (hit.error) throw new Error(`(گیت‌هاب) ${hit.error}`);
    return { ok: hit.status >= 200 && hit.status < 300, status: hit.status, text: async () => hit.text || "" };
  }
  return p.fetch(url, { headers });
}

async function fetchItems(p, f, pre) {
  if (!isXFeed(f)) {
    const res = await pget(p, f.url, { "User-Agent": "Mozilla/5.0 (ARIKO news)" }, pre);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return parseFeed(await res.text());
  }
  // X: تایم‌لاین عمومی خود X (اگه گیت‌هاب/کامپیوتر گرفته بود، همون)، بعد bridgeهایی که ادمین گذاشته
  const handle = xHandle(f);
  const errors = [];
  try {
    const res = await pget(p, xUrl(handle), { "User-Agent": BROWSER_UA, "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9" }, pre);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const items = parseXSyndication(await res.text(), handle);
    if (items.length) return items;
    errors.push("X: پستی برنگردوند");
  } catch (e) { errors.push(`X: ${e.message}`); }
  for (const tpl of (await cfg(p, "x_bridges", null)) || []) {
    try {
      const res = await p.fetch(tpl.replace("{handle}", encodeURIComponent(handle)), { headers: { "User-Agent": BROWSER_UA } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const items = parseXBridge(await res.text(), handle);
      if (items.length) return items;
      errors.push(`${new URL(tpl.replace("{handle}", "x")).hostname}: پستی برنگردوند`);
    } catch (e) { errors.push(`bridge: ${e.message}`); }
  }
  throw new Error(errors.join(" | "));
}

/** لیست آدرس‌هایی که گیت‌هاب/کامپیوتر باید قبل از collect بگیره: اکانت‌های X + فیدهایی که سرور بهشون دسترسی نداره */
export async function prefetchPlan(p, force = false) {
  const out = [];
  for (const f of await feeds(p)) {
    if (f.active === false) continue;
    const st = await p.kv.get("feedstate:" + hashKey(f.url));
    if (isXFeed(f)) {
      if (!force && st && Date.now() - st.at < (st.wait || X_EVERY_MS)) continue;
      out.push({ url: xUrl(xHandle(f)), x: true });
    } else if (st && ((st.error && /request failed|fetch|HTTP (?:403|429|5\d\d)/i.test(st.error)) || st.via === "pre")) {
      out.push({ url: f.url });
    }
  }
  return out;
}

async function addNews(p, feed, it) {
  let article = { image: "", text: "", videos: [] };
  if (!it.leak) {                                             // پست X صفحه‌ی خبر نداره؛ خود متن پست کافیه
    try {
      const res = await p.fetch(it.link, { headers: { "User-Agent": "Mozilla/5.0 (ARIKO news)" } });
      if (res.ok) article = parseArticle(await res.text());
    } catch (e) { /* صفحه باز نشد؛ همون خلاصه‌ی RSS */ }
  }
  const item = { title: it.title, link: it.link, published: it.published, summary: it.summary, text: article.text,
                 leak: !!it.leak, eventType: eventType(it.title, it.summary) };
  const meta = await anilistMeta(p, guessAnimeName(it.title));
  const out = await agentCaption(p, item, meta);
  if (out.notNews) return "not_news";
  let image = article.image || it.image || "";
  if (!image || GENERIC_IMAGE.test(image)) image = (meta && (meta.banner || meta.cover)) || image;   // لوگوی سایت به‌جای عکس خبر
  const id = hashKey(it.link + Date.now());
  const news = { id, title: it.title, link: it.link, source: feed.name, image,
                 render: out.render, caption: out.render.headline, model: out.model, status: "pending", file_id: "",
                 anime: out.animeTitle || guessAnimeName(it.title),
                 created: Date.now(), importance: it.importance, summary: String(it.summary || "").slice(0, 1500),
                 published: it.published || "" };
  const trailerNews = TRAILER_TYPES.includes(item.eventType) || /\b(?:trailer|teaser|pv)\b/i.test(it.title);
  if (trailerNews) {                                           // خبر تریلر: ویدیو + کپشن توی یه پیام، با کامپیوتر
    news.trailer = { url: (article.videos || [])[0] || (it.leak ? it.link : ""), anime: news.anime || "" };
    await p.kv.set("news:" + id, news);
    await trailerJob(p, news);
    return "ok";
  }
  await p.kv.set("news:" + id, news);
  await preview(p, news);
  return "ok";
}

const TRAILER_TYPES = ["trailer", "trailer_visual", "character_pv"];

/** کار دانلود تریلر برای کامپیوتر؛ اگه خاموشه به ادمین‌ها خبر میده و منتظر می‌مونه */
async function trailerJob(p, news) {
  news.status = "needs_trailer";
  await p.kv.set("news:" + news.id, news);
  const job = { id: "t" + news.id, type: "trailer", news_id: news.id, url: news.trailer.url, anime: news.trailer.anime,
                title: news.title, published: news.published || "", created: Date.now(), taken: 0, chat_id: OWNER_ID,
                caption: previewText(p, news).slice(0, 1024), reply_markup: reviewKeyboard(news.id, news.link) };
  await p.kv.set("job:" + job.id, job);
  if (!(await agentOnline(p))) {
    await notifyAdmins(p, `🎬 یه خبر <b>تریلر</b> درباره‌ی انیمه‌ی «${escapeHtml(news.anime || news.title)}» اومده.\n\n` +
      "🖥 منتظرم <b>سیستم رو روشن کنی</b> (serverless_agent) تا تریلر رو دانلود کنم و با کپشنش برات بفرستم.",
      { reply_markup: { inline_keyboard: [[{ text: "❌ این خبر رو رد کن", callback_data: `nw:no:${news.id}` }]] } });
  }
}

// عکس‌های عمومی سایت (لوگو/عکس پیش‌فرض اشتراک‌گذاری) عکس خبر نیستن
const GENERIC_IMAGE = /logo|default|placeholder|og[-_]?image|share[-_]?image|social[-_]?(?:card|share)|favicon|site[-_]?image/i;

function reviewKeyboard(id, link = "") {
  const rows = [[{ text: "✅ انتشار", callback_data: `nw:ok:${id}` }, { text: "❌ رد", callback_data: `nw:no:${id}` }],
                [{ text: "🎨 پست اینستاگرام", callback_data: `ig0:${id}` }]];
  if (/^https?:\/\//.test(link)) rows.push([{ text: "🔗 منبع اصلی", url: link }]);
  return { inline_keyboard: rows };
}

// ───────── پست اینستاگرام (کاور + فتوشاپ): کل کار با کد بات قدیمی روی کامپیوتر انجام میشه ─────────
// سرور فقط کار رو به کامپیوتر میده و تا ۳ ساعت دکمه‌ها/پیام‌های مربوط به اون (ig:… ، عکس/PSD ، تیتر) رو
// دست‌نخورده برای کامپیوتر می‌فرسته تا همون منوی قدیمی کار کنه.
export const RELAY_PREFIXES = ["ig", "igup", "igps", "nv2_insta"];
const RELAY_MS = 3 * 3600 * 1000;

export async function agentOnline(p) {
  return Date.now() - ((await cfg(p, "agent_seen", 0)) || 0) < 90000;
}

export async function instaJob(p, newsId, uid) {
  const news = await p.kv.get("news:" + newsId);
  if (!news) return { ok: false, text: "این خبر پیدا نشد" };
  const job = { id: "i" + newsId + uid, type: "insta", uid, created: Date.now(), taken: 0,
                news: { id: news.id, title: news.title, link: news.link, image: news.image,
                        caption: news.render ? renderCaption(news.render, "") : news.caption,
                        file_id: news.file_id, source: news.source, summary: news.summary || "", anime: "" } };
  // اسم انیمه همون‌طور که توی خبر اومده (مثل بات قدیمی)، تا توی کاور [زرد] بشه
  let anime = news.anime || guessAnimeName(news.title);
  if (!anime) { const meta = await anilistMeta(p, news.title); anime = (meta && meta.title) || ""; }
  job.news.anime = anime;
  await p.kv.set("job:" + job.id, job);
  await startRelay(p, uid);
  return { ok: true, online: await agentOnline(p) };
}

export const startRelay = (p, uid) => p.kv.set("relay:" + uid, Date.now() + RELAY_MS);
export async function relayActive(p, uid) {
  return Number((await p.kv.get("relay:" + uid)) || 0) > Date.now();
}

export async function relayUpdate(p, update) {
  const key = `upd:${String(Date.now()).padStart(14, "0")}:${Math.random().toString(36).slice(2, 8)}`;
  await p.kv.set(key, update);
}

export async function agentUpdates(p) {
  const rows = (await p.kv.list("upd:")).sort((a, b) => (a.key < b.key ? -1 : 1));
  for (const r of rows) await p.kv.del(r.key);
  return rows.map((r) => r.value).filter(Boolean);
}

function previewText(p, news) {
  // مثل آرشیو بات قدیمی: کپشن تمیز + برچسب «با AI بازنویسی شده» (این برچسب‌ها توی کانال نمیان)
  const note = (news.trailer_note ? `⚠️ تریلر: ${escapeHtml(news.trailer_note)}\n` : "") +
    `✅ 🤖 این متن با AI بازنویسی شده (${escapeHtml(news.model || "")})\n` +
    `— <i>${escapeHtml(news.source)}</i>` + (news.importance !== undefined ? ` · ⭐️ ${news.importance}/100` : "");
  const body = news.render ? renderCaption(news.render, "", 1024 - note.length - 4) : escapeHtml(news.caption);
  return `${body}\n\n${note}`;
}

/** کپشن نهایی کانال: همون کپشن + امضا (بدون برچسب‌های ادمین) */
function channelCaption(news, footer) {
  return news.render ? renderCaption(news.render, footer) : postCaption(news.caption, footer);
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
                                            parse_mode: "HTML", reply_markup: reviewKeyboard(news.id, news.link) }, news);
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
                caption: after === "post" ? channelCaption(news, await cfg(p, "footer", DEFAULT_FOOTER))
                                          : previewText(p, news).slice(0, 1024),
                reply_markup: after === "post" ? null : reviewKeyboard(news.id, news.link) };
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
  const caption = channelCaption(news, await cfg(p, "footer", DEFAULT_FOOTER));
  if (news.video_file_id) {                                   // خبر تریلر: ویدیو با کپشن، یه پیام
    await p.api("sendVideo", { chat_id: channel, video: news.video_file_id, caption, parse_mode: "HTML",
                               supports_streaming: true });
    news.status = "posted";
    await p.kv.set("news:" + id, news);
    return "✅ منتشر شد";
  }
  if (news.status === "needs_trailer") return "منتظر تریلره؛ سیستم رو روشن کن";
  const photo = news.file_id || news.image;
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
  await p.kv.del("job:t" + id);
  return "❌ رد شد";
}

// ───────── تست رنکینگ هفتگی: ساخت کارت (عکس) کار سنگینه → برای کامپیوتر ─────────
export const RANK_SOURCES = { anitrendz: "🟡 AniTrendz — Top Anime", animecorner: "🔴 Anime Corner — Top Anime",
                              mal: "🔵 MyAnimeList — Top Airing" };

export async function rankJob(p, source, chatId) {
  const job = { id: "r" + source + chatId, type: "rank", source, chat_id: chatId, created: Date.now(), taken: 0 };
  await p.kv.set("job:" + job.id, job);
  return Date.now() - ((await cfg(p, "agent_seen", 0)) || 0) < 120000;   // کامپیوتر روشنه؟
}

// ───────── صف بررسی: خبرهایی که هنوز تأیید/رد نشدن ─────────
export async function pendingNews(p) {
  const rows = (await p.kv.list("news:")).map((r) => r.value)
    .filter((n) => n && ["pending", "needs_image", "needs_trailer"].includes(n.status));
  return rows.sort((a, b) => (b.created || 0) - (a.created || 0));
}

export async function resendPreview(p, chatId, news) {
  if (news.video_file_id) {
    return p.api("sendVideo", { chat_id: chatId, video: news.video_file_id, caption: previewText(p, news).slice(0, 1024),
                                parse_mode: "HTML", supports_streaming: true, reply_markup: reviewKeyboard(news.id, news.link) });
  }
  if (news.status === "needs_trailer") {
    return p.api("sendMessage", { chat_id: chatId, parse_mode: "HTML",
      text: `🎬 «${escapeHtml(news.anime || news.title)}»\nمنتظر تریلره؛ سیستم رو روشن کن.`,
      reply_markup: { inline_keyboard: [[{ text: "❌ رد", callback_data: `nw:no:${news.id}` }]] } });
  }
  const photo = news.file_id || news.image;
  if (!photo || news.status === "needs_image") {
    return p.api("sendMessage", { chat_id: chatId, parse_mode: "HTML",
      text: `🖥 «${escapeHtml(news.title)}»\nعکس لازم داره؛ سیستم رو روشن کن.`,
      reply_markup: { inline_keyboard: [[{ text: "❌ رد", callback_data: `nw:no:${news.id}` }]] } });
  }
  return sendPhotoSmart(p, { chat_id: chatId, photo, caption: previewText(p, news).slice(0, 1024),
                             parse_mode: "HTML", reply_markup: reviewKeyboard(news.id, news.link) }, news);
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
  if (job.type === "trailer") {                              // کامپیوتر تریلر رو با کپشن برای صاحب بات فرستاد
    await p.kv.del("job:" + job_id);
    const news = await p.kv.get("news:" + job.news_id);
    if (!news || news.status === "rejected") return { ok: true };
    if (ok && file_id) {
      news.video_file_id = file_id;
      news.status = "pending";
      await p.kv.set("news:" + news.id, news);
      for (const id of (await admins(p)).filter((x) => x !== OWNER_ID)) {
        try { await p.api("sendVideo", { chat_id: id, video: file_id, caption: previewText(p, news).slice(0, 1024),
                                         parse_mode: "HTML", supports_streaming: true,
                                         reply_markup: reviewKeyboard(news.id, news.link) }); } catch (e) { /* */ }
      }
    } else {                                                    // تریلر پیدا/دانلود نشد → پیش‌نمایش عادی با عکس
      news.status = "pending";
      news.trailer_note = String(error || "تریلر پیدا نشد").slice(0, 200);
      await p.kv.set("news:" + news.id, news);
      await preview(p, news);
    }
    return { ok: true };
  }
  if (job.type === "insta") {                                // کاور اینستاگرام: بقیه‌ی کار با منوی بات قدیمی روی کامپیوتره
    await p.kv.del("job:" + job_id);
    if (!ok) {
      try { await p.api("sendMessage", { chat_id: job.uid, parse_mode: "HTML",
        text: `⚠️ شروع ساخت پست اینستاگرام نشد:\n${escapeHtml(String(error || "").slice(0, 300))}` }); } catch (e) { /* */ }
    }
    return { ok: true };
  }
  if (job.type === "rank") {                                  // کارت رنکینگ: کامپیوتر خودش عکس رو فرستاده
    await p.kv.del("job:" + job_id);
    if (!ok) {
      try { await p.api("sendMessage", { chat_id: job.chat_id, parse_mode: "HTML",
        text: `⚠️ ساخت کارت رنکینگ نشد:\n${escapeHtml(String(error || "").slice(0, 300))}` }); } catch (e) { /* */ }
    }
    return { ok: true };
  }
  const news = await p.kv.get("news:" + job.news_id);
  if (!ok) {
    job.error = String(error || "").slice(0, 200);
    job.tries = (job.tries || 0) + 1;
    if (job.tries < 3) {                                      // بی‌صدا دوباره امتحان (۱۰ دقیقه بعد)
      await p.kv.set("job:" + job_id, job);
      return { ok: true };
    }
    await p.kv.del("job:" + job_id);
    await notifyAdmins(p, `⚠️ کامپیوتر ۳ بار نتونست عکس «${escapeHtml(news ? news.title : job_id)}» رو درست کنه و بیخیالش شد:\n${escapeHtml(job.error)}`);
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
