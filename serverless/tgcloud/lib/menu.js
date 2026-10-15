// منوی دکمه‌ای بات (مثل بات قدیمی): کیبورد پایین صفحه + دکمه‌های شیشه‌ای.
import { cfg, feeds, admins, pendingNews, OWNER_ID, RANK_SOURCES, recentDecisions } from "./news.js";
import { storageName } from "./platform.js";
import { escapeHtml, hashKey, isXFeed, xHandle, IMPORTANCE_LEVELS, DEFAULT_MIN_IMPORTANCE } from "./core.js";

export const B = {
  check: "📰 بررسی خبرها الان",
  queue: "📥 صف بررسی",
  status: "🩺 وضعیت بات",
  feeds: "📡 منابع خبری",
  addFeed: "➕ افزودن منبع خبری",
  channel: "📢 کانال خبر",
  footer: "✍️ امضای پست",
  ai: "🔑 تنظیم هوش مصنوعی",
  admins: "👤 ادمین‌ها",
  rank: "🧪 تست رنکینگ هفتگی",
  importance: "⭐️ فیلتر اهمیت خبر",
  report: "🧾 گزارش خبرها",
  cancel: "❌ لغو",
};

// دکمه‌های کیبورد بات قدیمی هم کار کنن
export const OLD = {
  "📰 بررسی News V2 الان": B.check,
  "📥 صف بررسی News V2": B.queue,
  "📊 آمار News V2": B.report,
  "🩺 وضعیت بات": B.status,
  "🤖 وضعیت ایجنت خبر": B.status,
  "📡 منابع News V2": B.feeds,
  "➕ افزودن منبع خبری": B.addFeed,
  "📦 تنظیم کانال آرشیو خبر": B.channel,
  "📡 مدیریت کانال‌های پست": B.channel,
  "✍️ امضای کانال خبر": B.footer,
  "🔑 تنظیم سرویس AI": B.ai,
  "🧪 تست رنکینگ هفتگی": B.rank,
  "⭐️ فیلتر اهمیت خبر": B.importance,
};

export function mainKeyboard() {
  return {
    keyboard: [
      [{ text: B.check }],
      [{ text: B.queue }, { text: B.report }, { text: B.status }],
      [{ text: B.feeds }, { text: B.addFeed }],
      [{ text: B.channel }, { text: B.footer }],
      [{ text: B.ai }, { text: B.admins }],
      [{ text: B.importance }, { text: B.rank }],
    ],
    resize_keyboard: true,
    is_persistent: true,
  };
}

export const cancelKeyboard = () => ({ keyboard: [[{ text: B.cancel }]], resize_keyboard: true });

export async function statusText(p) {
  const last = await cfg(p, "last_collect", null);
  const seen = await cfg(p, "agent_seen", 0);
  const queue = (await pendingNews(p)).length;
  return "📰 <b>بات خبری آریکو</b>\n\n" +
    `🔑 هوش مصنوعی (Gemini): ${(await cfg(p, "gemini_key", "")) ? "✅" : "❌ تنظیم نشده"}\n` +
    `📢 کانال: ${(await cfg(p, "channel", "")) ? "✅ " + escapeHtml(await cfg(p, "channel", "")) : "❌ تنظیم نشده"}\n` +
    `📡 منبع‌ها: ${(await feeds(p)).length} تا\n` +
    `📥 صف بررسی: ${queue} خبر\n` +
    `🖥 برنامه‌ی کامپیوتر: ${Date.now() - seen < 120000 ? "✅ روشن" : "⚪️ خاموش (فقط برای درست کردن عکس لازمه)"}\n` +
    (last ? `⏱ آخرین بررسی: ${Math.round((Date.now() - last.at) / 60000)} دقیقه پیش — ${last.added} خبر جدید`
          : "⏱ هنوز بررسی نشده") +
    `\n💾 پایگاه‌داده: ${storageName()}` +
    "\n\n✅ انتشار فقط بعد از تأیید ادمین";
}

// کارت هر منبع (مثل بات قدیمی): وضعیت، نوع، لینک، آخرین بررسی + دکمه‌های حذف/غیرفعال/سایت
function sourceClass(f) {
  if (f.type === "fact") return f.unverified ? "🧠 فکت (حرف کاربرا؛ تأییدنشده)" : "🧠 فکت / مصاحبه";
  if (isXFeed(f)) return "غیررسمی / لیک (X)";
  const t = (f.name || "").toLowerCase(), u = (f.url || "").toLowerCase();
  if (t.includes("official")) return "رسمی";
  if (t.includes("crunchyroll") || u.includes("crunchyroll")) return "رسانه رسمی/ناشر";
  return "رسانه خبری";
}

function tehranTime(ms) {                                     // ایران از ۱۴۰۱ ساعت تابستونی نداره: UTC+3:30
  return new Date(ms + 3.5 * 3600 * 1000).toISOString().replace("T", " ").slice(0, 19);
}

export async function feedCard(p, f, i) {
  const h = hashKey(f.url);
  const st = await p.kv.get("feedstate:" + h);
  const on = f.active !== false;
  let site = isXFeed(f) ? `https://x.com/${xHandle(f)}` : f.url;
  if (!isXFeed(f)) try { site = new URL(f.url).origin; } catch (e) { /* */ }
  if (/crunchyrollsvc\.com/.test(site)) site = "https://www.crunchyroll.com/news";
  const rows = [[{ text: "🗑 حذف", callback_data: `fd:ask:${h}` },
                 { text: on ? "⏸ غیرفعال" : "▶️ فعال", callback_data: `fd:tg:${h}` }]];
  if (/^https?:\/\//.test(site)) rows.push([{ text: "🔗 باز کردن سایت", url: site }]);
  return {
    text: `${on ? "🟢" : "⚪️"} #${i + 1} — ${escapeHtml(f.name)}\n` +
      `🏷 ${sourceClass(f)}\n${escapeHtml(isXFeed(f) ? "@" + xHandle(f) : f.url)}\n` +
      `آخرین بررسی: ${st ? tehranTime(st.at) : "هنوز بررسی نشده"}` +
      (st && st.error ? `\n⚠️ ${escapeHtml(st.error)}` : ""),
    reply_markup: { inline_keyboard: rows },
  };
}

export async function aiView(p) {
  const model = await cfg(p, "model", "");
  const has = !!(await cfg(p, "gemini_key", ""));
  return {
    text: "🔑 <b>هوش مصنوعی</b>\n\n" +
      `کلید Gemini: ${has ? "✅ ثبت شده" : "❌ ثبت نشده"}\n` +
      `مدل: ${escapeHtml(model || "پیش‌فرض (خودکار)")}`,
    reply_markup: { inline_keyboard: [
      [{ text: has ? "🔁 عوض کردن کلید" : "➕ ثبت کلید", callback_data: "ai:key" }],
      [{ text: "⚡️ flash-lite", callback_data: "ai:m:gemini-3.5-flash-lite" },
       { text: "🧠 flash", callback_data: "ai:m:gemini-3.5-flash" }],
      [{ text: "♻️ مدل پیش‌فرض (خودکار)", callback_data: "ai:m:" }],
    ] },
  };
}

export async function adminsView(p) {
  const list = await admins(p);
  const rows = list.filter((id) => id !== OWNER_ID)
    .map((id) => [{ text: `🗑 ${id}`, callback_data: `ad:del:${id}` }]);
  rows.push([{ text: "➕ افزودن ادمین", callback_data: "ad:add" }]);
  return {
    text: "👤 <b>ادمین‌ها</b>\n\n" + list.map((id) => `• <code>${id}</code>${id === OWNER_ID ? " (صاحب بات)" : ""}`).join("\n") +
      "\n\nفقط صاحب بات می‌تونه ادمین اضافه/حذف کنه.",
    reply_markup: { inline_keyboard: rows },
  };
}

export const channelView = async (p) => ({
  text: "📢 <b>کانال خبر</b>\n\n" +
    `الان: ${escapeHtml((await cfg(p, "channel", "")) || "❌ تنظیم نشده")}\n\n` +
    "برای عوض کردن، دکمه‌ی زیر رو بزن.",
  reply_markup: { inline_keyboard: [[{ text: "🔁 تنظیم کانال", callback_data: "ch:set" }]] },
});

export const footerView = async (p, def) => ({
  text: "✍️ <b>امضای پایین پست</b>\n\n" + escapeHtml((await cfg(p, "footer", null)) ?? def),
  reply_markup: { inline_keyboard: [[{ text: "✏️ عوض کردن", callback_data: "ft:set" }]] },
});

// منتظر جواب متنی ادمین (مثلاً لینک منبع)
export const setWait = (p, uid, kind) => p.kv.set("wait:" + uid, { kind, at: Date.now() });
export async function getWait(p, uid) {
  const w = await p.kv.get("wait:" + uid);
  return w && Date.now() - w.at < 15 * 60 * 1000 ? w : null;
}
export const clearWait = (p, uid) => p.kv.del("wait:" + uid);

export const WAIT_PROMPT = {
  feed: "🔗 یکی از این‌ها رو بفرست:\n\n" +
    "🐦 <b>اکانت X (توییتر):</b> آیدی با @ یا لینک پروفایل؛ چندتا رو هم می‌تونی با فاصله یا خط جدید با هم بفرستی:\n" +
    "<code>@SugoiLITE @d0nut2x</code>\n\n" +
    "📰 <b>سایت خبری:</b> لینک RSS (اسمش رو هم اگه خواستی بعد از لینک بنویس):\n<code>https://site.com/feed اسم منبع</code>",
  channel: "📢 یه پست از کانال رو برام <b>فوروارد</b> کن (ساده‌ترین راه)،\nیا آیدی کانال رو بفرست: <code>@Ariko_News</code> یا <code>-100…</code>\n\n⚠️ بات باید ادمین کانال باشه.",
  footer: "✍️ متن امضای پایین پست رو بفرست.\nبرای حذف امضا بنویس: <code>-</code>",
  key: "🔑 کلید Gemini رو بفرست (با AIza شروع میشه).\nپیامت بعد از ذخیره پاک میشه.",
  admin: "👤 یه پیام از اون شخص رو برام <b>فوروارد</b> کن، یا آیدی عددی‌اش رو بفرست.",
};

export const rankView = () => ({
  text: "🧪 <b>تست رنکینگ هفتگی</b>\n\nیکی از ۳ منبع رو انتخاب کن.\n" +
    "این فقط پیش‌نمایشه و توی کانال منتشر نمیشه.\n\n🖥 کارت روی کامپیوتر ساخته میشه (برنامه‌ی serverless_agent باید روشن باشه).",
  reply_markup: { inline_keyboard: [...Object.entries(RANK_SOURCES).map(([k, label]) => [{ text: label, callback_data: `rk:${k}` }]),
                                    [{ text: "❌ بستن", callback_data: "rk:close" }]] },
});

export async function importanceView(p) {
  const cur = Number(await cfg(p, "min_importance", DEFAULT_MIN_IMPORTANCE));
  return {
    text: "⭐️ <b>فیلتر اهمیت خبر</b>\n\nهر خبر یه امتیاز اهمیت از ۰ تا ۱۰۰ می‌گیره (نوع خبر و کلیدواژه‌ها).\n" +
      "خبرهای زیر این حد اصلاً برات فرستاده نمیشن.\nامتیاز هر خبر پایین پیش‌نمایشش نوشته میشه (⭐️).",
    reply_markup: { inline_keyboard: IMPORTANCE_LEVELS.map(([v, label]) =>
      [{ text: `${v === cur ? "✅ " : ""}${label} (${v}+)`, callback_data: `im:${v}` }]) },
  };
}

function ago(ms) {
  const m = Math.round((Date.now() - ms) / 60000);
  return m < 60 ? `${m} دقیقه پیش` : m < 1440 ? `${Math.round(m / 60)} ساعت پیش` : `${Math.round(m / 1440)} روز پیش`;
}

export async function reportText(p) {
  const list = await recentDecisions(p);
  if (!list.length) return "🧾 هنوز خبر تازه‌ای بررسی نشده (از این به بعد سرنوشت هر خبر اینجا نوشته میشه).";
  let out = "🧾 <b>سرنوشت خبرهای تازه</b> (جدیدترین بالا)\n";
  for (const d of list.slice(0, 20)) {
    const line = `\n${d.outcome} · ${escapeHtml(d.src)} · ${ago(d.at)}\n<a href="${escapeHtml(d.link)}">${escapeHtml(d.title)}</a>\n`;
    if (out.length + line.length > 3900) break;
    out += line;
  }
  return out;
}
