// پنل دکمه‌ای مدیریت (توی خود گروه، فقط ادمین‌ها و بالاتر): قفل‌ها، قفل گروه، تنظیمات.
import { L, ROLE_FA, LOCKS, esc, faNum, now, saveCfg, fmtLeft, nextClock } from "./core.js";
import { glockText } from "./guard.js";

const ACTION_FA = { ban: "بن", mute: "سکوت", kick: "اخراج" };
const onoff = (v) => (v ? "✅" : "❌");

export function panelView(cfg, chatId, page = "main") {
  const cb = (op, arg = "") => `pn:${chatId}:${op}:${arg}`;
  if (page === "locks") {
    const keys = Object.keys(LOCKS);
    const rows = [];
    for (let i = 0; i < keys.length; i += 3) {
      rows.push(keys.slice(i, i + 3).map((k) => ({ text: `${cfg.locks[k] ? "🔒" : "🔓"} ${LOCKS[k]}`, callback_data: cb("lk", k) })));
    }
    rows.push([{ text: "⬅️ برگشت", callback_data: cb("pg", "main") }]);
    return { text: "🔐 <b>قفل‌ها</b>\nبا زدن هر دکمه قفل/باز میشه (قفل‌شده‌ها: فقط ادمین‌ها و کاربران ویژه مجازن).\n"
      + "برای قفلی که ادمین‌ها رو هم شامل بشه: «قفل لینک ادمین» یا «قفل لینک همه».", kb: { inline_keyboard: rows } };
  }
  if (page === "settings") {
    return { text: "⚙️ <b>تنظیمات</b>", kb: { inline_keyboard: [
      [{ text: `${onoff(cfg.welcome.on)} پیام خوشامد`, callback_data: cb("tg", "welcome") },
       { text: `${onoff(cfg.rulesOnPost)} قوانین زیر پست`, callback_data: cb("tg", "rulesOnPost") }],
      [{ text: `${onoff(cfg.flood.on)} ضد اسپم`, callback_data: cb("tg", "flood") },
       { text: `${onoff(cfg.force.on)} عضویت اجباری`, callback_data: cb("tg", "force") }],
      [{ text: "➖", callback_data: cb("wm", "-1") }, { text: `حد اخطار: ${faNum(cfg.warn.max)}`, callback_data: cb("noop") },
       { text: "➕", callback_data: cb("wm", "1") }],
      [{ text: `مجازات اخطار: ${ACTION_FA[cfg.warn.action] || "بن"} 🔄`, callback_data: cb("wa") }],
      [{ text: "⬅️ برگشت", callback_data: cb("pg", "main") }],
    ] } };
  }
  const nLocks = Object.keys(cfg.locks).length;
  return { text: `🛠 <b>پنل مدیریت</b> — ${esc(cfg.title || "")}\n\nگروه: ${glockText(cfg)}\nقفل‌های فعال: ${faNum(nLocks)}\n`
    + `اخطار: ${faNum(cfg.warn.max)} تا ← ${ACTION_FA[cfg.warn.action] || "بن"}\nفیلتر: ${faNum(cfg.filters.length)} • ممنوع: ${faNum(cfg.bad.length)} • پاسخ خودکار: ${faNum(cfg.replies.length)}`,
    kb: { inline_keyboard: [
      [{ text: "🔐 قفل‌ها", callback_data: cb("pg", "locks") }, { text: "⚙️ تنظیمات", callback_data: cb("pg", "settings") }],
      [{ text: "🔒 ۱ ساعت", callback_data: cb("gl", "60") }, { text: "🔒 ۳ ساعت", callback_data: cb("gl", "180") },
       { text: "🔒 تا صبح", callback_data: cb("gl", "morning") }],
      [{ text: "🔒 تا وقتی باز کنم", callback_data: cb("gl", "inf") }, { text: "🔓 باز کردن گروه", callback_data: cb("gl", "open") }],
      [{ text: "✖️ بستن پنل", callback_data: cb("x") }],
    ] } };
}

/** دکمه‌های پنل؛ level سطح کسیه که زده. خروجی: {alert?, page?} */
export async function panelAction(p, cfg, chatId, op, arg, level) {
  if (op === "pg") return { page: arg };
  if (op === "noop") return {};
  if (op === "lk") {
    const cur = cfg.locks[arg];
    if (cur && cur.by > level) return { alert: `⛔️ این قفل رو ${ROLE_FA[cur.by]} گذاشته.` };
    if (cur) delete cfg.locks[arg]; else cfg.locks[arg] = { lvl: L.special, by: level };
    await saveCfg(p, chatId, cfg);
    return { page: "locks", toast: `${LOCKS[arg]} ${cur ? "باز" : "قفل"} شد` };
  }
  if (op === "gl") {
    const g = cfg.glock || {};
    if (g.by > level && (g.until === -1 || g.until > now())) return { alert: `⛔️ گروه رو ${ROLE_FA[g.by]} قفل کرده.` };
    if (arg === "open") cfg.glock = { until: 0, by: 0, ann: 1 };
    else cfg.glock = { until: arg === "inf" ? -1 : arg === "morning" ? nextClock(8) : now() + Number(arg) * 60e3, by: level, lvl: L.admin, ann: 0 };
    await saveCfg(p, chatId, cfg);
    const until = cfg.glock.until;
    return { page: "main", announce: arg === "open" ? "🔓 گروه باز شد." : `🔒 گروه قفل شد${until === -1 ? " (تا وقتی باز بشه)" : ` (${fmtLeft(until - now())})`}؛ فقط ادمین‌ها می‌تونن پیام بدن.` };
  }
  if (op === "tg") {
    if (arg === "welcome") cfg.welcome.on = !cfg.welcome.on;
    else if (arg === "rulesOnPost") cfg.rulesOnPost = !cfg.rulesOnPost;
    else if (arg === "flood") cfg.flood.on = !cfg.flood.on;
    else if (arg === "force") {
      if (!cfg.force.chans.length) return { alert: "اول کانال رو اضافه کن: «عضویت اجباری @کانال»" };
      cfg.force.on = !cfg.force.on;
    }
    await saveCfg(p, chatId, cfg);
    return { page: "settings" };
  }
  if (op === "wm") {
    cfg.warn.max = Math.min(20, Math.max(1, (cfg.warn.max || 3) + Number(arg)));
    await saveCfg(p, chatId, cfg);
    return { page: "settings" };
  }
  if (op === "wa") {
    const order = ["ban", "mute", "kick"];
    cfg.warn.action = order[(order.indexOf(cfg.warn.action) + 1) % order.length];
    await saveCfg(p, chatId, cfg);
    return { page: "settings" };
  }
  return {};
}
