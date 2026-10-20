// کپشن خبر دقیقاً مثل بات قدیمی (news.py): همون دستور Gemini (لحن محاوره‌ای + مثال‌های واقعی کانال)،
// خروجی JSON، چک کردن با متن منبع، و ساخت کپشن: تیتر + جزئیات + خلاصه‌ی داستان + تاریخ پخش شمسی + استودیو + امضا.
import { escapeHtml } from "./core.js";

export const AGENT_SYSTEM = `You write posts for a popular Iranian anime Telegram channel, in the voice of a friendly anime fan talking to other fans.
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
- When the news IS a reveal (studio, director, cast, theme singer, episode count…), the headline MUST say WHAT was revealed,
  never just «مشخص شد» / «معرفی شد». GOOD: «استودیو سازنده‌ی دنباله‌ی «X» مشخص شد؛ استودیو Pierrot ساختش رو به عهده داره.»
  or «استودیو Pierrot دنباله‌ی «X» رو می‌سازه.» BAD: «استودیو سازنده‌ی دنباله‌ی «X» مشخص شد.» (fans' first question: which studio?)
  If the studio is revealed, also put its name in "studio". If SOURCE does not contain the revealed name at all, write
  the headline about what SOURCE does say instead of claiming something was revealed.
- If CERTAINTY is a leak/rumor, make it clear the info is UNOFFICIAL (not a guess): start the headline with
  «طبق گزارشات غیررسمی؛» or «طبق اطلاعات لو رفته؛». Do NOT use «احتمالاً» for this — it sounds like we are guessing.
- Trailer/teaser/poster order: never write «تریلر اول» or «اولین تریلر» — for the first one just say «تریلر».
  For later ones put the ordinal before the noun: «دومین تریلر» / «سومین تیزر», never «تریلر دوم».
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
  "headline_trailer": "ONLY if SOURCE announces BOTH a new video (trailer/teaser/PV) AND new images (posters/visuals/stills): headline for a separate video post, e.g. «تیزر جدید انیمه‌ی اچی و عاشقانه‌ی «Now That We Draw» منتشر شد.» — otherwise empty string",
  "headline_images": "same case only: headline for the separate images post, e.g. «پوسترهای جدید انیمه‌ی اچی و عاشقانه‌ی «Now That We Draw» از شخصیت‌های اصلی اثر منتشر شد.» — otherwise empty string",
  "details": ["1-2 colloquial Persian sentences with extra facts from SOURCE only (empty list only if SOURCE has nothing more)"],
  "synopsis": "2-3 sentence spoiler-free colloquial Persian synopsis translated ONLY from SYNOPSIS_EN, or empty string",
  "release_date": "premiere/release date exactly as written in SOURCE (English), or empty string",
  "studio": "studio name only if explicitly in SOURCE, else empty string"
}`;

const clean = (s) => String(s || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
const stripCjk = (s) => String(s || "").replace(/[぀-ヿ㐀-鿿가-힯]+/g, "");
const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
export const faDigits = (s) => String(s).replace(/[0-9]/g, (d) => FA_DIGITS[d]);
const enDigits = (s) => String(s).replace(/[۰-۹]/g, (d) => FA_DIGITS.indexOf(d)).replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d));
const norm = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const faLetters = (s) => (String(s || "").match(/[؀-ۿ]/g) || []).length;

export function agentUserPrompt(item, meta, unofficial) {
  const certainty = unofficial
    ? "UNOFFICIAL LEAK/RUMOR — start the headline with «طبق گزارشات غیررسمی؛» or «طبق اطلاعات لو رفته؛» (never «احتمالاً»)"
    : "reported by news outlet";
  const genres = (meta && meta.genres && meta.genres.length) ? meta.genres.join(", ") : "(unknown — do not add genre adjectives)";
  return `EVENT_TYPE_HINT: ${item.eventType || "other"}\nCERTAINTY: ${certainty}\nGENRES: ${genres}\n\n` +
    `SOURCE TITLE: ${clean(item.title)}\nSOURCE SUMMARY: ${clean(item.summary).slice(0, 900)}\n` +
    `SOURCE ARTICLE: ${clean(item.text).slice(0, 2600)}\n\n` +
    `SYNOPSIS_EN: ${(meta && meta.description) || "(none — return empty synopsis)"}`;
}

export function parseJson(text) {
  const t = String(text || "").replace(/```(?:json)?/gi, "");
  const m = t.match(/\{[\s\S]*\}/);
  if (!m) return null;
  for (const c of [m[0], m[0].replace(/,\s*([}\]])/g, "$1")]) {
    try { const d = JSON.parse(c); if (d && typeof d === "object") return d; } catch (e) { /* */ }
  }
  return null;
}

const cleanFa = (v) => stripCjk(v).replace(/[*_`#]+/g, "").replace(/\s+/g, " ").trim();

function checkText(value, hay, numbers) {
  if (/\b(?:i think|as an ai|note:|here is|json)\b/i.test(value)) return "متن غیرخبری";
  for (const [, inner] of value.matchAll(/«([^»]{2,140})»/g)) {
    if (/[A-Za-z]/.test(inner) && norm(inner) && !hay.includes(norm(inner))) return `اسم «${inner}» توی منبع نیست`;
  }
  const allowed = new Set(numbers);
  for (const n of numbers) if (+n >= 1990 && +n <= 2100) { allowed.add(String(+n - 621)); allowed.add(String(+n - 622)); }
  for (const num of enDigits(value).match(/\d+/g) || []) if (+num > 12 && !allowed.has(num)) return `عدد ${num} توی منبع نیست`;
  return "";
}

/** خروجی Gemini رو با متن منبع چک می‌کنه (مثل _news_agent_validate بات قدیمی) */
export function validate(data, item, meta) {
  if (!data || typeof data !== "object") return [null, "JSON نامعتبر"];
  if (data.is_anime_news === false) return [null, "not_news"];
  const sourceText = [clean(item.title), clean(item.summary), clean(item.text).slice(0, 4000)].join(" ");
  const hay = norm(sourceText);
  const headHay = norm(`${item.title} ${String(item.summary || "").slice(0, 400)}`);
  const numbers = new Set(sourceText.match(/\d+/g) || []);
  const animeTitle = String(data.anime_title || "").replace(/\s+/g, " ").trim();
  const nt = norm(animeTitle);
  if (!nt || nt.length < 2) return [null, "اسم انیمه خالیه"];
  if (!headHay.includes(nt)) return [null, `اسم انیمه «${animeTitle}» با تیتر خبر نمیخونه`];
  const headline = cleanFa(data.headline);
  if (headline.length < 15 || headline.length > 320) return [null, "طول تیتر نامناسبه"];
  if (faLetters(headline) < 10) return [null, "تیتر فارسی نیست"];
  if (!norm(headline).includes(nt)) return [null, "اسم انیمه توی تیتر نیست"];
  const problem = checkText(headline, hay, numbers);
  if (problem) return [null, problem];
  let studio = String(data.studio || "").replace(/\s+/g, " ").trim();
  if (studio && !hay.includes(norm(studio))) studio = "";
  // «استودیو سازنده مشخص شد» بدون گفتن اسم استودیو = خبر بی‌خاصیت
  if (/استودیو/.test(headline) && /(مشخص|معرفی|اعلام|فاش|تایید|تأیید|لو)/.test(headline)) {
    const latin = (headline.replace(/«[^»]*»/g, " ").match(/[A-Za-z][A-Za-z0-9.&'\- ]{1,}/g) || []).map(norm).filter((w) => w.length > 1);
    const named = (studio && norm(headline).includes(norm(studio))) || latin.some((w) => hay.includes(w));
    if (!named) return [null, "the headline says the studio was revealed but does not name the studio — name it (from SOURCE) in the headline and in \"studio\""];
  }
  const details = [];
  for (let d of [].concat(data.details || []).slice(0, 2)) {
    d = cleanFa(d);
    if (d && d.length <= 320 && faLetters(d) >= 8 && !checkText(d, hay, numbers)) details.push(d);
  }
  let synopsis = cleanFa(data.synopsis);
  if (synopsis && (!(meta && meta.description) || faLetters(synopsis) < 20 || synopsis.length > 520)) synopsis = "";
  let release = String(data.release_date || "").replace(/\s+/g, " ").trim();
  if (release) {
    const yrs = release.match(/\b20\d{2}\b/g) || [];
    const words = release.toLowerCase().match(/[a-z]{3,}/g) || [];
    const low = sourceText.toLowerCase();
    if ((yrs.length && !yrs.every((y) => sourceText.includes(y))) || (words.length && !words.some((w) => low.includes(w)))) release = "";
  }
  let emoji = String(data.emoji || "").trim();
  if (!emoji || emoji.length > 4 || /[A-Za-z0-9؀-ۿ]/.test(emoji)) emoji = "🔥";
  const extra = {};
  for (const k of ["headline_trailer", "headline_images"]) {
    const h = cleanFa(data[k]);
    if (h && h.length >= 15 && h.length <= 320 && faLetters(h) >= 10 && norm(h).includes(nt) && !checkText(h, hay, numbers)) {
      extra[k === "headline_trailer" ? "headlineTrailer" : "headlineImages"] = soften(h);
    }
  }
  let importance = parseInt(enDigits(String(data.importance)), 10);
  if (!(importance >= 1 && importance <= 10)) importance = null;
  return [{ animeTitle, emoji, headline: soften(headline), details: details.map(soften), synopsis, release, studio, importance,
            ...extra }, ""];
}

/** چند اصلاح مطمئن از رسمی به محاوره‌ای */
export function soften(text) {
  let t = String(text || "");
  t = t.replace(/\s+میلادی(?![؀-ۿ])/g, "");
  t = t.replace(/(شده|بوده)\s+است(?=[.،!\s]|$)/g, "$1");
  t = t.replace(/می‌باشد|میباشد/g, "هست");
  t = t.replace(/\sاست(?=[.!]?\s*$)/g, " هست");
  t = t.replace(/خواهد\s+بود/g, "هست");
  t = t.replace(/می‌شود|میشود/g, "میشه");
  // «تریلر اول» → «تریلر»؛ «تریلر دوم» → «دومین تریلر»
  const MEDIA = "تریلر|تیزر|پوستر|ویژوال|پی‌وی|پیش‌نمایش";
  t = t.replace(new RegExp(`(?:اولین|نخستین)\\s+(${MEDIA})`, "g"), "$1");
  t = t.replace(new RegExp(`(${MEDIA})(‌?ها)?(\\s+(?:جدید\\s+)?)اول(?![؀-ۿ])\\s*`, "g"), (m, n, pl, sp) => `${n}${pl || ""} `);
  t = t.replace(new RegExp(`(${MEDIA})\\s+(دوم|سوم|چهارم|پنجم|ششم|هفتم)(?![؀-ۿ])`, "g"), "$2ین $1");
  t = t.replace(/\s{2,}/g, " ").replace(/\s+([.،!])/g, "$1");
  t = t.replace(/(^|[^؀-ۿ])کورهای(?![؀-ۿ])/g, "$1پارت‌های");
  t = t.replace(/(^|[^؀-ۿ])کور(?=\s*(?:اول|دوم|سوم|چهارم|پنجم|ششم|[۰-۹0-9]|متوالی|پشت))/g, "$1پارت");
  t = t.replace(/((?:[۰-۹0-9]|دو|سه)\s)کور(?![؀-ۿ])/g, "$1پارت");
  return t;
}

// ───────── تاریخ پخش: میلادی → شمسی (مثل _news_localize_date) ─────────
const EN_MONTHS = { january: 1, february: 2, march: 3, april: 4, may: 5, june: 6, july: 7, august: 8, september: 9,
                    october: 10, november: 11, december: 12 };
const FA_MONTHS = ["", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"];

export function g2j(gy, gm, gd) {
  const gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  let jy = gy <= 1600 ? 0 : 979;
  gy -= gy <= 1600 ? 621 : 1600;
  const gy2 = gm > 2 ? gy + 1 : gy;
  let days = 365 * gy + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) + Math.floor((gy2 + 399) / 400) - 80 + gd + gdm[gm - 1];
  jy += 33 * Math.floor(days / 12053); days %= 12053;
  jy += 4 * Math.floor(days / 1461); days %= 1461;
  if (days > 365) { jy += Math.floor((days - 1) / 365); days = (days - 1) % 365; }
  const jm = days < 186 ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
  const jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30);
  return [jy, jm, jd];
}

export function releasePlausible(value, published) {
  const raw = String(value || "").trim();
  if (!raw) return false;
  const ref = new Date(Date.parse(published || "") || Date.now());
  const years = (raw.match(/\b(19\d{2}|20\d{2})\b/g) || []).map(Number);
  if (years.some((y) => y < ref.getUTCFullYear())) return false;
  const month = (raw.toLowerCase().match(/[a-z]+/g) || []).map((w) => EN_MONTHS[w]).find(Boolean) || 0;
  const day = (raw.replace(/\b(19|20)\d{2}\b/g, "").match(/\b(\d{1,2})(?:st|nd|rd|th)?\b/) || [])[1];
  if (years.length && month) {
    const when = Date.UTC(years[0], month - 1, day ? +day : 28);
    if (when < ref.getTime() - 45 * 86400e3) return false;
  }
  return true;
}

export function localizeDate(value, published) {
  const raw = String(value || "").replace(/\s+/g, " ").trim().replace(/(\d)(?:st|nd|rd|th)\b/g, "$1");
  if (!raw) return "";
  const season = raw.match(/^(?:in\s+|the\s+)?(?:(spring|summer|fall|autumn|winter)\s+)?(20\d{2})$/i);
  if (season) {
    const s = { spring: "بهار", summer: "تابستان", fall: "پاییز", autumn: "پاییز", winter: "زمستان" }[(season[1] || "").toLowerCase()];
    return s ? `${s} ${faDigits(season[2])}` : `سال ${faDigits(season[2])}`;
  }
  const ref = new Date(Date.parse(published || "") || Date.now());
  let m = raw.match(/^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$/);
  if (m && EN_MONTHS[m[1].toLowerCase()]) {
    const [jy, jm, jd] = g2j(+m[3], EN_MONTHS[m[1].toLowerCase()], +m[2]);
    return `${faDigits(jd)} ${FA_MONTHS[jm]} ${faDigits(jy)}`;
  }
  m = raw.match(/^([A-Za-z]+)\s+(\d{1,2})$/);
  if (m && EN_MONTHS[m[1].toLowerCase()]) {
    const gm = EN_MONTHS[m[1].toLowerCase()];
    let gy = ref.getUTCFullYear();
    if (Date.UTC(gy, gm - 1, +m[2]) < ref.getTime() - 120 * 86400e3) gy += 1;
    const [jy, jm, jd] = g2j(gy, gm, +m[2]);
    return `${faDigits(jd)} ${FA_MONTHS[jm]} ${faDigits(jy)}`;
  }
  m = raw.match(/^([A-Za-z]+)\s+(\d{4})$/);
  if (m && EN_MONTHS[m[1].toLowerCase()]) {
    const [jy, jm] = g2j(+m[2], EN_MONTHS[m[1].toLowerCase()], 1);
    return `${FA_MONTHS[jm]} ${faDigits(jy)}`;
  }
  return faDigits(raw);
}

const faDigitsOutsideTitles = (v) => String(v || "").split(/(«[^»]*»)/).map((p) => (p.startsWith("«") ? p : faDigits(p))).join("");

/** کپشن نهایی (HTML) مثل _news_render_caption بات قدیمی */
export function renderCaption(r, footer, maxLen = 1024) {
  let headline = escapeHtml(faDigitsOutsideTitles(r.headline)).replace(/«([^»]{1,140})»/g, "«<b>$1</b>»");
  if (r.unofficial && !/غیررسمی|طبق گزارش|احتمال|لو رفت|گفته می|شایعه/.test(headline)) headline = "طبق گزارشات؛ " + headline;
  const blocks = [`${r.emoji || "🔥"} ${headline}`.trim()];
  const details = (r.details || []).filter(Boolean).map((d) => escapeHtml(faDigitsOutsideTitles(d)));
  if (details.length) blocks.push(details.join("\n"));
  const info = [];
  if (r.dateFa) info.push(`🗓 تاریخ پخش: <b>${escapeHtml(r.dateFa)}</b>`);
  if (r.studio) info.push(`⚙️ استودیو سازنده: ${escapeHtml(r.studio)}`);
  const sig = footer ? escapeHtml(footer) : "";
  const visible = (h) => h.replace(/<[^>]+>/g, "").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&").length;
  const build = (syn) => [...blocks, syn, info.join("\n"), sig].filter(Boolean).join("\n\n").trim();
  let syn = r.synopsis || "";
  let text = build(syn ? `<blockquote expandable>${escapeHtml(syn)}</blockquote>` : "");
  while (syn && visible(text) > maxLen) {
    syn = syn.slice(0, Math.max(0, syn.length - 40)).replace(/\s+\S*$/, "");
    text = build(syn ? `<blockquote expandable>${escapeHtml(syn)}…</blockquote>` : "");
  }
  if (visible(text) > maxLen) text = build("");
  return text;
}

// ───────── فکت‌ها (مثل پست‌های «فکت پشم‌ریزون» کانال‌های فارسی) ─────────
export const FACT_SYSTEM = `You find ONE surprising, funny, weird or little-known anime/manga fact in SOURCE and write it as a post for a popular Iranian anime Telegram channel, in the warm spoken voice of a fan.

GOOD FACTS: behind-the-scenes production details (how long an episode takes, budgets, crunch, studio stories like MAPPA/ufotable),
surprising words from directors/authors/voice actors, hidden details in an anime or manga, funny or weird character moments,
interesting differences between manga and anime, surprising facts about characters and their relationships, famous people
reacting to anime. NOT facts: plain release/trailer/cast announcements, reviews, rankings, sales charts, merchandise.
If SOURCE has no such fact, return {"is_fact": false}.

HARD RULES:
- Use ONLY what SOURCE says. Never invent names, numbers or quotes. Keep anime titles in English/romaji exactly as in SOURCE inside «».
- If CERTAINTY says fans/users (e.g. Reddit), the fact is NOT verified: say so («طبق گفته‌ی طرفدارا؛» / «ظاهراً») and never state it as certain.
- Spoken Persian (هست، داره، میشه، میبره، گفته). Never formal (است، می‌باشد، توسط).
- Output ONE JSON object only.

EXAMPLE (voice only, not facts):
headline: فکت پشم‌ریزون؛ طبق گفته‌ی استودیو MAPPA، تولید هر قسمت از انیمه‌ی «Jujutsu Kaisen» حدود ۲ تا ۳ ماه زمان می‌بره! 😳
reaction: ارزش جوجوتسو و کیفیت کار ماپا 🔥
details: ["این موضوع توی یه گفت‌وگو مطرح شده؛ طبق گفته‌ها خود تام کروز هم درباره‌ی روند تولید انیمه سؤال کرده."]

JSON FORMAT:
{"is_fact": true, "anime_title": "exact title from SOURCE (or the person/studio if no anime)", "emoji": "one emoji",
 "headline": "one or two spoken Persian sentences with the fact (may start with «فکت پشم‌ریزون؛» or «فکت جالب؛»)",
 "reaction": "very short fan reaction line, or empty string",
 "details": ["0-2 short Persian sentences of context from SOURCE"]}`;

export function factUserPrompt(item, unverified) {
  return `CERTAINTY: ${unverified ? "posted by fans/users — NOT verified" : "from a news outlet / interview"}\n\n` +
    `SOURCE TITLE: ${clean(item.title)}\nSOURCE SUMMARY: ${clean(item.summary).slice(0, 1200)}\n` +
    `SOURCE ARTICLE: ${clean(item.text).slice(0, 3500)}`;
}

export function validateFact(data, item) {
  if (!data || typeof data !== "object") return [null, "JSON نامعتبر"];
  if (data.is_fact === false) return [null, "not_fact"];
  const sourceText = [clean(item.title), clean(item.summary), clean(item.text).slice(0, 4000)].join(" ");
  const hay = norm(sourceText);
  const numbers = new Set(sourceText.match(/\d+/g) || []);
  const animeTitle = String(data.anime_title || "").replace(/\s+/g, " ").trim();
  const headline = cleanFa(data.headline);
  if (headline.length < 20 || headline.length > 400 || faLetters(headline) < 12) return [null, "تیتر فکت مناسب نیست"];
  const problem = checkText(headline, hay, numbers);
  if (problem) return [null, problem];
  let studio = String(data.studio || "").replace(/\s+/g, " ").trim();
  if (studio && !hay.includes(norm(studio))) studio = "";
  // «استودیو سازنده مشخص شد» بدون گفتن اسم استودیو = خبر بی‌خاصیت
  if (/استودیو/.test(headline) && /(مشخص|معرفی|اعلام|فاش|تایید|تأیید|لو)/.test(headline)) {
    const latin = (headline.replace(/«[^»]*»/g, " ").match(/[A-Za-z][A-Za-z0-9.&'\- ]{1,}/g) || []).map(norm).filter((w) => w.length > 1);
    const named = (studio && norm(headline).includes(norm(studio))) || latin.some((w) => hay.includes(w));
    if (!named) return [null, "the headline says the studio was revealed but does not name the studio — name it (from SOURCE) in the headline and in \"studio\""];
  }
  const reaction = cleanFa(data.reaction);
  const details = [];
  for (let d of [].concat(data.details || []).slice(0, 2)) {
    d = cleanFa(d);
    if (d && d.length <= 320 && faLetters(d) >= 8 && !checkText(d, hay, numbers)) details.push(soften(d));
  }
  let emoji = String(data.emoji || "").trim();
  if (!emoji || emoji.length > 4 || /[A-Za-z0-9؀-ۿ]/.test(emoji)) emoji = "🤯";
  return [{ animeTitle, emoji, headline: soften(headline), reaction: reaction.length <= 120 ? reaction : "", details }, ""];
}

/** کپشن فکت: تیتر + واکنش + توضیح + #فکت + امضا */
export function renderFactCaption(r, footer) {
  const head = escapeHtml(faDigitsOutsideTitles(r.headline)).replace(/«([^»]{1,140})»/g, "«<b>$1</b>»");
  const parts = [`${r.emoji || "🤯"} ${head}`];
  if (r.reaction) parts.push(escapeHtml(r.reaction));
  if (r.details && r.details.length) parts.push(r.details.map((d) => escapeHtml(faDigitsOutsideTitles(d))).join("\n"));
  parts.push("#فکت #اخبار_انیمه");
  if (footer) parts.push(escapeHtml(footer));
  return parts.join("\n\n").slice(0, 1024);
}
