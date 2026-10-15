// منوی دکمه‌ای بات (مثل بات قدیمی): کیبورد پایین صفحه + دکمه‌های شیشه‌ای.
import { cfg, feeds, admins, pendingNews, OWNER_ID } from "./news.js";
import { escapeHtml, hashKey } from "./core.js";

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
  cancel: "❌ لغو",
};

// دکمه‌های کیبورد بات قدیمی هم کار کنن
export const OLD = {
  "📰 بررسی News V2 الان": B.check,
  "📥 صف بررسی News V2": B.queue,
  "📊 آمار News V2": B.status,
  "🩺 وضعیت بات": B.status,
  "🤖 وضعیت ایجنت خبر": B.status,
  "📡 منابع News V2": B.feeds,
  "➕ افزودن منبع خبری": B.addFeed,
  "📦 تنظیم کانال آرشیو خبر": B.channel,
  "📡 مدیریت کانال‌های پست": B.channel,
  "✍️ امضای کانال خبر": B.footer,
  "🔑 تنظیم سرویس AI": B.ai,
};

export function mainKeyboard() {
  return {
    keyboard: [
      [{ text: B.check }],
      [{ text: B.queue }, { text: B.status }],
      [{ text: B.feeds }, { text: B.addFeed }],
      [{ text: B.channel }, { text: B.footer }],
      [{ text: B.ai }, { text: B.admins }],
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
    "\n\n✅ انتشار فقط بعد از تأیید ادمین";
}

export async function feedsView(p) {
  const list = await feeds(p);
  const rows = list.map((f) => [{ text: `🗑 ${f.name}`.slice(0, 60), callback_data: `fd:ask:${hashKey(f.url)}` }]);
  rows.push([{ text: "➕ افزودن منبع", callback_data: "fd:add" }]);
  let text = `📡 <b>منبع‌های خبری (${list.length} تا)</b>\n`;
  for (const [i, f] of list.entries()) text += `\n${i + 1}. ${escapeHtml(f.name)}`;
  text += "\n\nبرای حذف، روی دکمه‌ی منبع بزن.";
  return { text: text.slice(0, 4000), reply_markup: { inline_keyboard: rows } };
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
  feed: "🔗 لینک RSS منبع رو بفرست.\nاگه خواستی اسمش رو هم بعد از لینک بنویس:\n<code>https://site.com/feed اسم منبع</code>",
  channel: "📢 یه پست از کانال رو برام <b>فوروارد</b> کن (ساده‌ترین راه)،\nیا آیدی کانال رو بفرست: <code>@Ariko_News</code> یا <code>-100…</code>\n\n⚠️ بات باید ادمین کانال باشه.",
  footer: "✍️ متن امضای پایین پست رو بفرست.\nبرای حذف امضا بنویس: <code>-</code>",
  key: "🔑 کلید Gemini رو بفرست (با AIza شروع میشه).\nپیامت بعد از ذخیره پاک میشه.",
  admin: "👤 یه پیام از اون شخص رو برام <b>فوروارد</b> کن، یا آیدی عددی‌اش رو بفرست.",
};
