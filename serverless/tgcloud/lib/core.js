// منطق خالص (بدون وابستگی به پلتفرم): خوندن RSS، تمیز کردن متن، پیدا کردن عکس، پرامپت و کپشن.

export const DEFAULT_FEEDS = [
  { name: "Anime News Network", url: "https://www.animenewsnetwork.com/news/rss.xml?ann-edition=us" },
  { name: "MyAnimeList News", url: "https://myanimelist.net/rss/news.xml" },
  { name: "Crunchyroll News", url: "https://cr-news-api-service.prd.crunchyrollsvc.com/v1/en-US/rss" },
];

const ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", "#39": "'" };

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
    const descRaw = tag(b, "description") || tag(b, "summary") || tag(b, "content:encoded") || tag(b, "content");
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
  return { image, text: paras.join("\n").slice(0, 6000) };
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
