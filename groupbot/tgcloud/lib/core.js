// پایه: تنظیمات هر گروه، اعضا، نقش‌ها (مالک ← جانشین ← ادمین ← ویژه ← کاربر)، زمان، متن.
import { OWNER_IDS } from "./secrets.js";

export const OWNER_ID = 513902877;
export const OWNERS = [OWNER_ID, ...String(OWNER_IDS || "").split(/[,\s]+/).map(Number).filter(Boolean)];

// سطح هر نقش؛ هر کس فقط روی سطح‌های پایین‌تر از خودش دستور داره
export const L = { member: 0, special: 20, admin: 50, deputy: 80, owner: 100 };
export const ROLE_FA = { 0: "کاربر", 20: "کاربر ویژه", 50: "ادمین", 80: "جانشین مالک", 100: "مالک" };

export const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
export const faNum = (n) => String(n).replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[d]);
export const nameOf = (u) => (u ? [u.first_name, u.last_name].filter(Boolean).join(" ") || (u.username ? "@" + u.username : String(u.id)) : "?");
export const mention = (u) => `<a href="tg://user?id=${u.id}">${esc(nameOf(u))}</a>`;
export const mentionId = (id, name) => `<a href="tg://user?id=${id}">${esc(name || id)}</a>`;

/** متن برای مقایسه: ارقام فارسی/عربی → انگلیسی، ی/ک عربی، بدون نیم‌فاصله و اعراب، حروف کوچک */
export function norm(t) {
  return String(t || "")
    .replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d)).replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d))
    .replace(/ي/g, "ی").replace(/ك/g, "ک").replace(/[ً-ْ‌‏‎]/g, "")
    .replace(/\s+/g, " ").trim().toLowerCase();
}

// ───────── زمان (تهران، UTC+3:30) ─────────
const TZ = 3.5 * 3600 * 1000;
export const now = () => Date.now();
export const tehran = (ms = Date.now()) => new Date(ms + TZ);          // getUTC* = ساعت تهران
export const dayKey = (ms = Date.now()) => tehran(ms).toISOString().slice(0, 10);
export function hhmm(ms) {
  const d = tehran(ms);
  return faNum(`${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`);
}
/** ساعت بعدی «HH:MM» به وقت تهران (به میلی‌ثانیه) */
export function nextClock(h, m = 0, from = Date.now()) {
  const d = tehran(from);
  let t = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), h, m) - TZ;
  if (t <= from) t += 86400000;
  return t;
}
export function minutesOfDay(ms = Date.now()) {
  const d = tehran(ms);
  return d.getUTCHours() * 60 + d.getUTCMinutes();
}
export function fmtLeft(ms) {
  const m = Math.max(1, Math.round(ms / 60000));
  if (m < 60) return `${faNum(m)} دقیقه`;
  const h = Math.floor(m / 60), r = m % 60;
  if (h < 48) return `${faNum(h)} ساعت${r ? ` و ${faNum(r)} دقیقه` : ""}`;
  return `${faNum(Math.round(h / 24))} روز`;
}

// ───────── تنظیمات گروه ─────────
export const LOCKS = {
  link: "لینک", mention: "یوزرنیم", hashtag: "هشتگ", forward: "فوروارد", sticker: "استیکر", gif: "گیف",
  photo: "عکس", video: "فیلم", videonote: "فیلم سلفی", voice: "ویس", audio: "آهنگ", file: "فایل",
  contact: "مخاطب", location: "مکان", poll: "نظرسنجی", dice: "تاس", game: "بازی", inline: "اینلاین",
  button: "دکمه", text: "متن", english: "انگلیسی", emoji: "ایموجی پریمیوم", bot: "ربات", service: "پیام ورود",
};
// متن پیش‌فرض قوانین و خوشامد (ادمین‌ها با «تنظیم قوانین» / «تنظیم خوشامد» عوضش می‌کنن)
export const RULES_TEXT = `۱. 🤝 احترام به همه
توهین، فحاشی، تمسخر و تحقیر بقیه ممنوعه. بحث‌های سیاسی، مذهبی و قومیتی هم جاشون اینجا نیست.

۲. 🙈 اسپویل فقط با اسپویلر
هر چیزی از داستان که ممکنه برای بقیه لو بره (اتفاق‌های قسمت‌های جدید، پایان‌ها، فصل‌های بعد، چپترهای مانگا) فقط با اسپویلر تلگرام بفرست و اولش بنویس مال کدوم انیمه و قسمته.

۳. 🔞 محتوای +۱۸ ممنوع
فرستادن هر نوع عکس، گیف، ویدیو، استیکر یا متن پورنوگرافی و جنسی ممنوعه و بدون اخطار بن داره.

۴. 📢 تبلیغات ممنوع
تبلیغ کانال، گروه، سایت یا پیج، فرستادن لینک و آیدی، و پیام دادن به پیوی اعضا برای تبلیغ ممنوعه.

۵. 💬 اسپم نکن
پیام‌های پشت سر هم، استیکر و گیف رگباری، و تگ کردن بی‌دلیل بقیه ممنوعه.

۶. 🎌 موضوع گروه
اینجا جای گپ درباره‌ی انیمه و مانگاست؛ بحث‌های بی‌ربط و طولانی رو توی پیوی ادامه بدید.

۷. 🎬 دانلود فقط از آرشیو خودمون
لینک دانلود یا فایل از جاهای دیگه نفرستید؛ برای دانلود از @arikotv_bot استفاده کنید.

۸. 👮 حرف آخر با مدیرهاست
اگه به تصمیم مدیرها اعتراض داری، توی پیوی بگو نه وسط گروه. تخلف دیدی؟ روی پیام ریپلای کن و بنویس «گزارش».

⚠️ هر تخلف یه اخطار داره؛ از اخطار دوم سکوت موقت و با ۳ اخطار بن. محتوای +۱۸ و تبلیغات بن مستقیم دارن.`;
export const WELCOME_TEXT = `سلام {name} 👋
به {group} خوش اومدی! 🎌

اینجا جای گپ زدن درباره‌ی انیمه و مانگاست؛ با بقیه مهربون باش 😊
📜 قبل از پیام دادن، قوانین رو بخون: بنویس «قوانین»
🎬 دانلود انیمه: @arikotv_bot`;
const OLD_WELCOME = "سلام {name} 👋\nبه {group} خوش اومدی!\nقبل از هر چیز قوانین رو بخون: /rules";

export const DEFAULT_CFG = {
  active: false, title: "",
  admins: {}, special: {},               // {id: {n: اسم، by: سطح کسی که داده}}
  locks: {},                             // {link: {lvl: سطحی که مجازه، by: سطح قفل‌کننده}}
  allow: {},                             // {link: [آیدی‌هایی که با وجود قفل مجازن]}
  rules: RULES_TEXT, rulesOnPost: true,
  welcome: { on: true, text: WELCOME_TEXT, last: 0 },
  warn: { max: 3, action: "ban", muteMins: 1440, eachMins: 60,   // eachMins: سکوت از اخطار دوم به بعد (۰ = خاموش)
          text: "⚠️ {name} یه اخطار گرفت ({count} از {max})\nدلیل: {reason}",
          punish: "⛔️ {name} به {max} اخطار رسید و {action} شد.\nدلیل آخر: {reason}" },
  filters: [], bad: [], replies: [],
  flood: { on: true, n: 7, sec: 6, muteMins: 15 },
  force: { on: false, chans: [] },
  glock: { until: 0, by: 0, ann: 0 }, night: { on: false, from: "00:00", to: "08:00", by: 0 },
  tgAdmins: { ids: [], ts: 0 },
  reportChat: 0,
};

export async function getCfg(p, chatId) {
  const c = (await p.kv.get("cfg:" + chatId)) || {};
  const out = JSON.parse(JSON.stringify(DEFAULT_CFG));
  for (const [k, v] of Object.entries(c)) {
    out[k] = v && typeof v === "object" && !Array.isArray(v) && DEFAULT_CFG[k] && typeof DEFAULT_CFG[k] === "object"
      && !Array.isArray(DEFAULT_CFG[k]) ? { ...DEFAULT_CFG[k], ...v } : v;
  }
  if (!out.rules) out.rules = RULES_TEXT;                      // گروه‌هایی که هنوز قانون ننوشتن
  if (out.welcome.text === OLD_WELCOME) out.welcome.text = WELCOME_TEXT;
  return out;
}
export const saveCfg = (p, chatId, cfg) => p.kv.set("cfg:" + chatId, cfg);

// ───────── اعضا ─────────
export const getMember = async (p, chatId, uid) => (await p.kv.get(`m:${chatId}:${uid}`)) || { w: 0, wr: [], c: 0 };
export const saveMember = (p, chatId, uid, m) => p.kv.set(`m:${chatId}:${uid}`, m);
export async function getDeputy(p) { return (await p.kv.get("deputy")) || null; }

/** یوزرنیم → آیدی (ربات نمی‌تونه یوزرنیم کاربر رو مستقیم بپرسه؛ از پیام‌هایی که دیده یاد می‌گیره) */
export async function rememberUser(p, u) {
  if (!u || u.is_bot || !u.username) return;
  const key = "un:" + u.username.toLowerCase();
  const old = await p.kv.get(key);
  if (!old || old.id !== u.id || old.n !== nameOf(u)) await p.kv.set(key, { id: u.id, n: nameOf(u) });
}
export const userByName = (p, username) => p.kv.get("un:" + username.replace(/^@/, "").toLowerCase());

// ───────── نقش‌ها ─────────
const TG_ADMINS_TTL = 10 * 60 * 1000;
export async function tgAdmins(p, chatId, cfg) {
  if (cfg.tgAdmins && now() - (cfg.tgAdmins.ts || 0) < TG_ADMINS_TTL) return cfg.tgAdmins.ids || [];
  try {
    const list = await p.api("getChatAdministrators", { chat_id: chatId });
    cfg.tgAdmins = { ids: list.filter((a) => !a.user.is_bot).map((a) => a.user.id), ts: now() };
    await saveCfg(p, chatId, cfg);
  } catch (e) { /* ربات ادمین نیست؛ لیست قبلی */ }
  return (cfg.tgAdmins && cfg.tgAdmins.ids) || [];
}

export async function levelOf(p, chatId, cfg, uid, deputy) {
  if (OWNERS.includes(Number(uid))) return L.owner;
  if (deputy === undefined) deputy = await getDeputy(p);
  if (deputy && Number(deputy.id) === Number(uid)) return L.deputy;
  if (cfg && cfg.admins[uid]) return L.admin;
  if (cfg && chatId && (await tgAdmins(p, chatId, cfg)).includes(Number(uid))) return L.admin;
  if (cfg && cfg.special[uid]) return L.special;
  return L.member;
}

export function chatLink(chat, msgId) {
  const id = String(chat.id).replace(/^-100/, "");
  return chat.username ? `https://t.me/${chat.username}/${msgId}` : `https://t.me/c/${id}/${msgId}`;
}

/** جایگذاری {name} {group} … توی متن‌های قابل تنظیم */
export function fill(tpl, vals) {
  return String(tpl || "").replace(/\{(\w+)\}/g, (m, k) => (k in vals ? vals[k] : m));
}
