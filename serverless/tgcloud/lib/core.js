// منطق خالص (بدون وابستگی به پلتفرم): خوندن RSS، تمیز کردن متن، پیدا کردن عکس، پرامپت و کپشن.

export const DEFAULT_FEEDS = [
  { name: "Anime News Network", url: "https://www.animenewsnetwork.com/news/rss.xml?ann-edition=us" },
  { name: "MyAnimeList News", url: "https://myanimelist.net/rss/news.xml" },
  { name: "Crunchyroll News", url: "https://cr-news-api-service.prd.crunchyrollsvc.com/v1/en-US/rss" },
];

const ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", "#39": "'" };

// منبع‌های فکت (بررسی‌شده: RSS دارن). ردیت = حرف کاربرا، قطعی حساب نمیشه
export const FACT_FEEDS = [
  { name: "ANN Interviews & Features", url: "https://www.animenewsnetwork.com/feature/rss.xml?ann-edition=us", type: "fact" },
  { name: "ANN Interest", url: "https://www.animenewsnetwork.com/interest/rss.xml?ann-edition=us", type: "fact" },
  { name: "Sakuga Blog", url: "https://blog.sakugabooru.com/feed/", type: "fact" },
  { name: "Reddit r/anime", url: "https://www.reddit.com/r/anime/top/.rss?t=day", type: "fact", unverified: true },
  { name: "Reddit r/manga", url: "https://www.reddit.com/r/manga/top/.rss?t=week", type: "fact", unverified: true },
  { name: "The Canipa Effect", url: "https://www.youtube.com/feeds/videos.xml?channel_id=UCz4ZjuO7HrynjRrRlur1yWg", type: "fact" },
  { name: "SPY_true", url: "x:SPY_true", type: "fact" },
  { name: "AIR_News_EN", url: "x:AIR_News_EN", type: "fact" },
  { name: "WSJ_manga", url: "x:WSJ_manga", type: "fact" },
];

export function decodeEntities(s) {
  return String(s || "")
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(+n))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)))
    .replace(/&([a-z0-9#]+);/gi, (m, n) => (n.toLowerCase() in ENTITIES ? ENTITIES[n.toLowerCase()] : m));
}

export function stripHtml(s) {
  return decodeEntities(String(s || "").replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/<(script|style)[\s\S]*?<\/\1>/gi, " ").replace(/<br\s*\/?>/gi, "\n").replace(/<\/p>/gi, "\n")
    .replace(/<[^>]+>/g, " ")).replace(/[ \t]+/g, " ").replace(/\n\s*\n+/g, "\n").trim();
}

function tag(block, name) {
  const m = block.match(new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)</${name}>`, "i"));
  return m ? m[1].replace(/^\s*<!\[CDATA\[([\s\S]*?)\]\]>\s*$/, "$1").trim() : "";
}

function attr(block, tagName, attrName) {
  const m = block.match(new RegExp(`<${tagName}\\b[^>]*\\b${attrName}=["']([^"']+)["']`, "i"));
  return m ? decodeEntities(m[1]) : "";
}

/** RSS/Atom → [{title, link, summary, image, published}] */
export function parseFeed(xml) {
  const out = [];
  const blocks = xml.match(/<item\b[\s\S]*?<\/item>/gi) || xml.match(/<entry\b[\s\S]*?<\/entry>/gi) || [];
  for (const b of blocks) {
    const title = stripHtml(tag(b, "title"));
    let link = stripHtml(tag(b, "link")) || attr(b, "link", "href");
    const descRaw = tag(b, "description") || tag(b, "summary") || tag(b, "content:encoded") || tag(b, "content")
      || tag(b, "media:description");
    const image = attr(b, "media:content", "url") || attr(b, "media:thumbnail", "url") || attr(b, "enclosure", "url")
      || (decodeEntities(descRaw).match(/<img[^>]+src=["']([^"']+)["']/i) || [])[1] || "";
    const published = stripHtml(tag(b, "pubDate") || tag(b, "published") || tag(b, "updated"));
    if (title && link) out.push({ title, link: link.trim(), summary: stripHtml(descRaw).slice(0, 1500), image, published });
  }
  return out;
}

/** صفحه‌ی خبر → عکس اصلی (og:image) و متن پاراگراف‌ها */
export function parseArticle(html) {
  const meta = (p) => (html.match(new RegExp(`<meta[^>]+(?:property|name)=["']${p}["'][^>]+content=["']([^"']+)["']`, "i"))
    || html.match(new RegExp(`<meta[^>]+content=["']([^"']+)["'][^>]+(?:property|name)=["']${p}["']`, "i")) || [])[1] || "";
  const image = decodeEntities(meta("og:image") || meta("twitter:image"));
  const paras = [...html.matchAll(/<p\b[^>]*>([\s\S]*?)<\/p>/gi)].map(m => stripHtml(m[1])).filter(t => t.length > 40);
  // لینک تریلر یوتیوب داخل مقاله (embed / watch / youtu.be)
  let yt = [...html.matchAll(/(?:youtube(?:-nocookie)?\.com\/(?:embed\/|watch\?(?:[^"'<>\s]*?&(?:amp;)?)?v=|shorts\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/g)]
    .map((m) => `https://www.youtube.com/watch?v=${m[1]}`);
  // سایت‌هایی که یوتیوب رو با پخش‌کننده‌ی خودشون می‌ذارن (Anime Corner: …?yt_embed=ID ، lite-youtube videoid=ID)
  for (const m of html.matchAll(/(?:[?&](?:yt_embed|yt_id|youtube_id)=|<lite-youtube[^>]*videoid=["']|data-(?:yt|youtube)(?:-id)?=["'])([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])/gi)) {
    yt.push(`https://www.youtube.com/watch?v=${m[1]}`);
  }
  return { image, text: paras.join("\n").slice(0, 6000), videos: [...new Set(yt)].slice(0, 3), images: articleImages(html) };
}

const BAD_IMG = /logo|avatar|icon|emoji|gravatar|favicon|sprite|placeholder|spinner|pixel|1x1|\/ads?\/|advert|banner-ad|badge|button|share|social|author|profile|comment|thumb-?\d{2,3}x\d{2,3}|-\d{2,3}x\d{2,3}\.(?:jpe?g|png|webp)/i;

/** عکس‌های خود متن خبر (پوستر/ویژوال)، نه لوگو و آواتار و تبلیغ */
export function articleImages(html) {
  const body = (html.match(/<article\b[\s\S]*?<\/article>/i) || html.match(/<div[^>]+class=["'][^"']*(?:entry-content|post-content|article-body|content-body|text-zone|meat)[^"']*["'][\s\S]*/i) || [html])[0];
  const out = [];
  for (const m of body.matchAll(/<img\b[^>]*>/gi)) {
    const tag = m[0];
    const pick = (a) => (tag.match(new RegExp(`\\b${a}=["']([^"']+)["']`, "i")) || [])[1] || "";
    let src = pick("data-src") || pick("data-lazy-src") || pick("src");
    const srcset = pick("srcset") || pick("data-srcset");
    if (srcset) {                                              // بزرگ‌ترین نسخه
      const best = srcset.split(",").map((x) => x.trim().split(/\s+/)).filter((x) => x[0])
        .sort((a, b) => parseInt(b[1] || "0", 10) - parseInt(a[1] || "0", 10))[0];
      if (best) src = best[0];
    }
    src = decodeEntities(src);
    const w = parseInt(pick("width"), 10), h = parseInt(pick("height"), 10);
    if (!/^https?:\/\//.test(src) || /\.(?:svg|gif)(?:\?|$)/i.test(src) || BAD_IMG.test(src)) continue;
    if ((w && w < 300) || (h && h < 300)) continue;
    if (!out.includes(src)) out.push(src);
    if (out.length >= 12) break;
  }
  // عکس‌های قدیمیِ «خبرهای مرتبط» که لای مقاله اومدن: اگه بیشترِ عکس‌ها از یه ماه هستن، بقیه حذف
  const month = (u) => (u.match(/\/(20\d\d)\/(\d\d)\//) || []).slice(1).join("-");
  const counts = {};
  for (const u of out) if (month(u)) counts[month(u)] = (counts[month(u)] || 0) + 1;
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
  const kept = top && top[1] >= 2 ? out.filter((u) => !month(u) || month(u) === top[0]) : out;
  return kept.slice(0, 10);
}

export function hashKey(s) {
  let h = 2166136261 >>> 0;                                 // FNV-1a؛ برای کلید «قبلاً دیده شده»
  for (const ch of String(s)) { h ^= ch.codePointAt(0); h = Math.imul(h, 16777619) >>> 0; }
  return h.toString(36);
}

export const SYSTEM_PROMPT =
  "تو سردبیر یک رسانه فارسی انیمه هستی. فقط کپشن نهایی را بنویس؛ هیچ تحلیل یا توضیح نده. " +
  "لحن مستقیم، طبیعی و شبیه یک پیج خبری فارسی باشد؛ نه ترجمه لفظ‌به‌لفظ و نه متن تبلیغاتی. " +
  "اصل خبر را در جمله اول بگو. نام رسمی انیمه، فیلم، استودیو و پلتفرم را با املای لاتین اصلی حفظ کن. " +
  "هیچ نویسه ژاپنی/چینی/کره‌ای، نام منبع، URL یا هشتگ در خروجی نیاور. " +
  "کپشن را دقیقاً بین <CAPTION> و </CAPTION> قرار بده.";

export function buildPrompt(item) {
  return `برای خبر زیر یک کپشن فارسی کوتاه و رسانه‌ای بساز.
قواعد:
- فقط از اطلاعات متن زیر استفاده کن و چیزی حدس نزن.
- جمله اول مستقیم اصل اتفاق را بگوید؛ مقدمه‌چینی و عبارت‌های کلی مثل «خبر تازه‌ای منتشر شد» ممنوع.
- اصل خبر + ۲ تا ۴ نکته مهم؛ معمولاً ۳ تا ۶ خط و حداکثر ۸۰۰ کاراکتر؛ هر خط با یک ایموجی مناسب شروع شود.
- تاریخ پخش/اکران و استودیو را اگر صریح در متن هست نگه دار؛ تاریخ‌های قدیمی سابقه‌ی اثر را تاریخ پخش جدید معرفی نکن.
- صفت تبلیغاتی، نام منبع، لینک، هشتگ و Markdown ممنوع. جمله آخر کامل باشد.

${item.leak ? "- این خبر از یک لیکر در X است و هنوز رسمی نیست؛ همین را در جمله اول صریح بگو (مثلاً «طبق لیک‌ها…») و آن را قطعی اعلام نکن.\n" : ""}
عنوان خبر: ${item.title}
تاریخ انتشار: ${item.published || ""}

متن اصلی:
${(item.text || item.summary || "").slice(0, 5000)}`;
}

export function extractCaption(raw) {
  const m = String(raw || "").match(/<CAPTION>([\s\S]*?)<\/CAPTION>/i);
  let t = (m ? m[1] : "").trim();
  t = t.replace(/https?:\/\/\S+/g, "").replace(/#[^\s#]+/g, "").replace(/[぀-ヿ一-鿿가-힯]+/g, "").trim();
  return t.length >= 40 ? t.slice(0, 900) : "";
}

export function escapeHtml(s) {
  return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function postCaption(caption, footer) {
  const body = escapeHtml(caption);
  return (footer ? `${body}\n\n${footer}` : body).slice(0, 1024);
}

// ───────── X (توییتر): منبع‌هایی که url شون «x:هندل» هست ─────────
export const X_PREFIX = "x:";
export const isXFeed = (f) => String((f && f.url) || "").startsWith(X_PREFIX);
export const xHandle = (f) => String(f.url).slice(X_PREFIX.length);

/** «@SugoiLITE» یا «x.com/SugoiLITE» یا «https://twitter.com/SugoiLITE/status/…» → «SugoiLITE» */
export function parseXHandle(s) {
  const t = String(s || "").trim();
  const m = t.match(/^(?:https?:\/\/)?(?:www\.|mobile\.)?(?:x|twitter)\.com\/@?([A-Za-z0-9_]{1,15})(?:[/?#].*)?$/i)
    || t.match(/^@([A-Za-z0-9_]{1,15})$/);
  if (!m) return "";
  return ["home", "i", "search", "explore", "intent", "share"].includes(m[1].toLowerCase()) ? "" : m[1];
}

const OFFICIAL_MARKERS = ["official announcement", "official confirmation", "officially announced",
                          "officially confirmed", "✅ official", "confirmed by official"];

function cleanXText(s) {
  return decodeEntities(String(s || "")).replace(/https?:\/\/t\.co\/[A-Za-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
}

function xItem(handle, id, text, image, published) {
  const piece = text.length > 180 ? text.slice(0, 177).trimEnd() + "..." : text;
  return { title: `@${handle}: ${piece}`, link: `https://x.com/${handle}/status/${id}`, summary: text,
           image: image || "", published: published || "", leak: true };
}

/** تایم‌لاین عمومی X (syndication) → پست‌ها؛ ریپلای، ریتوییت و پست «رسمی شد» حذف میشن */
export function parseXSyndication(html, handle) {
  const m = String(html).match(/<script[^>]+id=["']__NEXT_DATA__["'][^>]*>([\s\S]*?)<\/script>/i);
  if (!m) throw new Error("X جواب درستی نداد (شاید محدود کرده)");
  const data = JSON.parse(m[1]);
  const entries = (((data.props || {}).pageProps || {}).timeline || {}).entries || [];
  const out = [];
  for (const e of entries) {
    if (String(e.type || "").toLowerCase() !== "tweet") continue;
    const tw = (e.content || {}).tweet || {};
    const user = String((tw.user || {}).screen_name || handle);
    if (user.toLowerCase() !== handle.toLowerCase()) continue;
    const raw = String(tw.full_text || tw.text || "").trim();
    if (!raw || raw.startsWith("RT @") || raw.startsWith("@") || tw.in_reply_to_status_id_str) continue;
    const text = cleanXText(raw);
    if (text.length < 12 || OFFICIAL_MARKERS.some((k) => text.toLowerCase().includes(k))) continue;
    const id = String(tw.id_str || "");
    if (!/^\d+$/.test(id)) continue;
    let image = "";
    for (const md of tw.mediaDetails || []) {
      if (md && md.media_url_https) { image = md.media_url_https; if (md.type === "photo") break; }
    }
    if (!image) for (const ph of tw.photos || []) if (ph && ph.url) { image = ph.url; break; }
    out.push(xItem(handle, id, text, image, tw.created_at));
  }
  return out;
}

/** فید RSS یه bridge (مثل Nitter) → همون شکل پست‌های X */
export function parseXBridge(xml, handle) {
  const out = [];
  for (const it of parseFeed(xml)) {
    const id = (it.link.match(/\/status(?:es)?\/(\d+)/) || [])[1];
    if (!id || /^(RT by|R to @|RT @)/.test(it.title)) continue;
    const text = cleanXText(it.summary || it.title);
    if (text.length < 12 || OFFICIAL_MARKERS.some((k) => text.toLowerCase().includes(k))) continue;
    let image = it.image || "";
    if (/nitter|\/pic\//.test(image)) {                        // عکس nitter → لینک مستقیم pbs.twimg.com
      const pic = decodeURIComponent((image.match(/\/pic\/(?:orig\/)?(.+)$/) || [])[1] || "");
      image = pic ? "https://pbs.twimg.com/" + pic.replace(/^\/+/, "") : image;
    }
    out.push(xItem(handle, id, text, image, it.published));
  }
  return out;
}

// ───────── اهمیت خبر (۰ تا ۱۰۰؛ همون منطق بات قدیمی) ─────────
export const IMPORTANCE_LEVELS = [[0, "همه خبرها"], [40, "معمولی به بالا"], [55, "فقط خبرهای مهم (پیشنهادی)"],
                                  [75, "فقط خبرهای خیلی مهم"]];
export const DEFAULT_MIN_IMPORTANCE = 55;

const IMPORTANCE_BASE = { season_announcement: 85, new_anime: 85, cancellation: 85, delay: 75, release_date: 75,
                          movie: 70, trailer: 65, trailer_visual: 65, character_pv: 45, visual: 45, other: 25 };
const IMPORTANCE_UP = [
  [/\b(?:final|last)\s+episode\b|\b(?:double-length|hour-long|extended|\d{2}-minute)\s+(?:episode|finale)\b|\bepisode\s+\d+\b.{0,60}\b(?:minutes?|runtime)\b/, 30, "قسمت پایانی/طول قسمت"],
  [/\bbox\s+office\b|\bbillion\s+yen\b|\brecord[- ]breaking\b|\bbreaks?\s+(?:the\s+)?record\b/, 20, "گیشه/رکورد"],
  [/\b(?:leak(?:ed|s)?|rumou?r(?:ed|s)?|reportedly|registered|rating\s+board|trademark(?:ed)?)\b/, 15, "لیک/گزارش"],
  [/\b(?:finale|concludes?|final\s+season|ending\s+confirmed)\b/, 15, "پایان سری"],
  [/\b(?:netflix|crunchyroll|disney\+?|amazon)\b.{0,60}\b(?:exclusive|acquires?|licens\w*)\b/, 10, "پلتفرم"],
];
const IMPORTANCE_DOWN = [
  [/\b(?:explained|explainer|review|recap|reactions?|guide|everything\s+(?:we|you)\s+know|what\s+to\s+expect|ranked|should\s+you\s+watch|theor(?:y|ies)|essay|opinion|editorial|listicle|\d+\s+(?:best|things|reasons))\b|\bwhere\s+to\s+(?:watch|stream)\b|\bhow\s+to\s+watch\b|\bwatch\s+order\b|\bbest\s+anime\b/, -60, "مقاله تحلیلی/غیرخبری"],
  [/\bmusic\s+video\b|\b(?:new\s+)?single\b|\balbum\b|\bconcert\b|\blive\s+tour\b|\bsong\b/, -35, "موسیقی"],
  [/\b(?:figures?|merch(?:andise)?|cafe|pop-up|exhibition|stage\s+play|musical|pachinko|lottery|blu-ray|dvd|artbook|apparel)\b/, -30, "محصول/رویداد جانبی"],
  [/\b(?:video\s+game|mobile\s+game|gacha|visual\s+novel|game)\b/, -25, "بازی"],
  [/\b(?:manga|light\s+novel)\b/, -10, "مانگا/رمان"],
  [/\b(?:english\s+dub|dub\s+cast|english\s+cast)\b/, -15, "دوبله انگلیسی"],
  [/\b(?:film\s+fest(?:ival)?|screens|screening)\b/, -15, "جشنواره/اکران محدود"],
];

export function eventType(title, summary) {
  const low = `${title} ${String(summary || "").slice(0, 900)}`.toLowerCase();
  if (/\b(?:cancelled|canceled|cancellation)\b/.test(low)) return "cancellation";
  if (/\b(?:delayed|delay|postponed|postponement|rescheduled)\b/.test(low)) return "delay";
  if (/\b(?:character\s+(?:trailer|pv|video|promo)|character-focused\s+(?:trailer|pv)|introduces?\s+(?:the\s+)?character)\b/.test(low)) return "character_pv";
  const trailer = /\b(?:trailer|teaser|promotional\s+video|promo\s+video|pv|main\s+pv|teaser\s+pv)\b/.test(low);
  const visual = /\b(?:key\s+visual|teaser\s+visual|new\s+visual|visual|poster)\b/.test(low);
  if (trailer && visual) return "trailer_visual";
  if (trailer) return "trailer";
  if (visual) return "visual";
  if (/\bseason\s+\d{1,2}\b.{0,100}\b(?:announced|confirmed|greenlit|green-lit|production|in\s+production|gets|receives)\b/.test(low)
      || /\b(?:announced|confirmed|greenlit|green-lit|gets|receives)\b.{0,100}\bseason\s+\d{1,2}\b/.test(low)
      || /\b(?:sequel|new\s+season)\b.{0,80}\b(?:announced|confirmed|greenlit|production)\b/.test(low)) return "season_announcement";
  if (/\b(?:anime\s+adaptation|tv\s+anime|new\s+anime)\b.{0,100}\b(?:announced|revealed|greenlit|gets|receives)\b/.test(low)
      || /\b(?:gets|receives|inspires)\b.{0,80}\b(?:tv\s+)?anime\b/.test(low)) return "new_anime";
  if (/\b(?:film|movie)\b.{0,100}\b(?:announced|revealed|greenlit|premiere|release)\b/.test(low)) return "movie";
  if (/\b(?:premiere|premieres|air|airs|broadcast|release\s+date|debuts?|starts?\s+airing|returns?)\b/.test(low)
      && /\b(?:january|february|march|april|may|june|july|august|september|october|november|december|spring|summer|fall|autumn|winter|20\d\d)\b/.test(low)) return "release_date";
  return "other";
}

/** { score, reasons } — مثل بات قدیمی؛ meta = { popularity, year } از AniList (اگه پیدا شد) */
export function importance(item, isOfficial = false, meta = null) {
  const text = `${item.title} ${String(item.summary || "").slice(0, 600)}`.toLowerCase();
  const type = eventType(item.title, item.summary);
  let score = IMPORTANCE_BASE[type] ?? 25;
  const reasons = [`نوع خبر ${score}`];
  const aboutAnime = /\banime\b|\bseason\s+\d|\bepisode\b|\bfilm\b|\bmovie\b/.test(text);
  for (const [re, d, label] of IMPORTANCE_UP) if (re.test(text)) { score += d; reasons.push(`+${d} ${label}`); }
  for (const [re, d, label] of IMPORTANCE_DOWN) {
    if (!re.test(text) || ((label === "بازی" || label === "مانگا/رمان") && aboutAnime)) continue;
    score += d; reasons.push(`${d} ${label}`);
  }
  const pop = Number((meta && meta.popularity) || 0);
  if (pop >= 300000) { score += 20; reasons.push("+20 انیمه خیلی محبوب"); }
  else if (pop >= 100000) { score += 12; reasons.push("+12 انیمه محبوب"); }
  else if (pop >= 30000) { score += 5; reasons.push("+5 انیمه شناخته‌شده"); }
  else if (pop > 0 && pop < 5000) {
    // انیمه‌ای که هنوز پخش نشده طبیعتاً محبوبیت کمی داره؛ جریمه فقط برای اثرهای قدیمی‌تر
    const year = Number((meta && meta.year) || 0);
    if (year && year < new Date().getUTCFullYear()) { score -= 10; reasons.push("-10 انیمه کم‌مخاطب"); }
  }
  if (isOfficial) { score += 5; reasons.push("+5 منبع رسمی"); }
  return { score: Math.max(0, Math.min(100, score)), reasons, type };
}

/** حدس اسم انیمه از تیتر خبر: «Oshi no Ko Season 3 Announced» → «Oshi no Ko» */
export function guessAnimeName(title) {
  let t = String(title || "").replace(/^@\w+:\s*/, "").trim();
  const quoted = t.match(/["“‘']([^"”’']{3,80})["”’']/);
  if (quoted) return quoted[1].trim();
  t = t.split(/\s*(?::|\s[-–—|]\s)\s*/)[0];
  const cut = t.search(/(?:'s\b|’s\b|\s(?:TV\s+)?Anime\b|\s(?:Season|Part|Cour)\s+\d|\s(?:\d+(?:st|nd|rd|th)\s+Season|Final\s+Season|Sequel|Film|Movie|Gets|Reveals?|Announce[sd]?|Unveils?|Confirm(?:s|ed)?|Receives?|Releases?|Delayed|Postponed|Premieres?|Streams?|Casts?|Adds?|Is|Has|Will|Opens?|Debuts?|Ends?|Launches?|Teaser|Trailer|Key\s+Visual|Visual|PV|Promo|Reportedly|In\s+Production|Returns?|Shares?|Drops?|Hits?|Tops?|Wins?|Earns?|Sets?|Coming)\b)/i);
  const name = (cut > 0 ? t.slice(0, cut) : t).replace(/^(?:The\s+)?(?:New|Leak|Rumou?r|Report|Breaking)\s*:?\s*/i, "").trim();
  return name.length >= 3 && name.split(/\s+/).length <= 8 ? name : "";
}
