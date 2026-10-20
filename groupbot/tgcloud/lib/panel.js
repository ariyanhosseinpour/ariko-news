// پنل دکمه‌ای مدیریت — هم توی خود گروه (مثل قبل)، هم توی خصوصی ربات (همه‌چی، حتی ویرایش متن‌ها، بدون نوشتن توی گروه).
// هر دکمه: pn:<آیدی گروه>:<کار>:<مقدار>. متن‌ها (قوانین، خوشامد، کلمه‌ها، …) توی خصوصی با «منتظر متن» گرفته میشن.
import { L, ROLE_FA, LOCKS, esc, faNum, now, saveCfg, fmtLeft, nextClock, mentionId, RULES_TEXT, WELCOME_TEXT } from "./core.js";
import { glockText } from "./guard.js";
import { statsText } from "./stats.js";

const ACTION_FA = { ban: "بن", mute: "سکوت", kick: "اخراج" };
const onoff = (v) => (v ? "✅" : "❌");
const cut = (t, n = 300) => { t = String(t || ""); return t.length > n ? t.slice(0, n) + "…" : t; };

// متن‌ها و فهرست‌هایی که با پیام بعدی ادمین (توی خصوصی) پر میشن
export const EDITS = {
  rules: { min: L.admin, prompt: "📜 متن کامل <b>قوانین</b> رو بفرست:" },
  welcome: { min: L.admin, prompt: "👋 متن <b>خوشامد</b> رو بفرست. {name} = اسم عضو جدید، {group} = اسم گروه:" },
  warntext: { min: L.admin, prompt: "⚠️ متن <b>اخطار</b> رو بفرست. {name} {count} {max} {reason}:" },
  punishtext: { min: L.admin, prompt: "⛔️ متن <b>مجازات</b> (رسیدن به حد اخطار) رو بفرست. {name} {max} {action} {reason}:" },
  filter_add: { min: L.admin, prompt: "🚫 کلمه‌هایی که باید <b>فیلتر</b> بشن (پیام فقط پاک میشه) رو بفرست؛ چندتا رو با «،» جدا کن:" },
  filter_del: { min: L.admin, prompt: "کلمه‌هایی که از <b>فیلتر</b> برداشته بشن رو بفرست:" },
  bad_add: { min: L.admin, prompt: "⛔️ <b>کلمات ممنوع</b> (پیام پاک + اخطار فوری) رو بفرست؛ چندتا رو با «،» جدا کن:" },
  bad_del: { min: L.admin, prompt: "کلمه‌هایی که از <b>ممنوع‌ها</b> برداشته بشن رو بفرست:" },
  reply_add: { min: L.admin, prompt: "💬 <b>پاسخ خودکار</b> رو این‌طوری بفرست:\n<code>سلام = سلام {name} 👋</code>\n(برای کلمه‌ی دقیق، اولش ! بذار)" },
  reply_del: { min: L.admin, prompt: "کلمه‌ی پاسخ خودکاری که باید پاک بشه رو بفرست:" },
  force_add: { min: L.admin, prompt: "📢 یوزرنیم کانال عضویت اجباری رو بفرست (مثلاً <code>@arikotv</code>). ربات باید ادمین اون کانال باشه:" },
  admin_add: { min: L.deputy, prompt: "⭐️ برای <b>ادمین کردن</b>: یه پیام از اون شخص فوروارد کن، یا یوزرنیم/آیدی عددیش رو بفرست:" },
  special_add: { min: L.admin, prompt: "💎 برای <b>کاربر ویژه</b>: یه پیام از اون شخص فوروارد کن، یا یوزرنیم/آیدی عددیش رو بفرست:" },
  deputy: { min: L.owner, prompt: "🎖 برای <b>جانشین مالک</b>: یه پیام از اون شخص فوروارد کن، یا یوزرنیم/آیدی عددیش رو بفرست:" },
  flood: { min: L.admin, prompt: "🛡 ضد اسپم: «تعداد پیام ثانیه» رو بفرست (مثلاً <code>7 6</code> یعنی بیشتر از ۷ پیام توی ۶ ثانیه):" },
};

export async function panelView(cfg, chatId, page = "main", ctx = {}) {
  const cb = (op, arg = "") => `pn:${chatId}:${op}:${arg}`;
  const back = (to = "main") => [{ text: "⬅️ برگشت", callback_data: cb("pg", to) }];
  const ed = (field, text) => ({ text, callback_data: cb("ed", field) });
  const priv = !!ctx.priv;
  const privHint = priv ? "" : "\n\n✏️ برای اضافه/ویرایش متن، پنل رو توی خصوصی ربات باز کن.";
  if (page === "locks") {
    const keys = Object.keys(LOCKS);
    const rows = [];
    for (let i = 0; i < keys.length; i += 3) {
      rows.push(keys.slice(i, i + 3).map((k) => ({ text: `${cfg.locks[k] ? "🔒" : "🔓"} ${LOCKS[k]}`, callback_data: cb("lk", k) })));
    }
    rows.push(back());
    return { text: "🔐 <b>قفل‌ها</b>\nبا زدن هر دکمه قفل/باز میشه (قفل‌شده‌ها: فقط ادمین‌ها و کاربران ویژه مجازن).\n"
      + "برای قفلی که ادمین‌ها رو هم شامل بشه: «قفل لینک ادمین» یا «قفل لینک همه».", kb: { inline_keyboard: rows } };
  }
  if (page === "settings") {
    return { text: `⚙️ <b>تنظیمات</b>\n🛡 ضد اسپم: بیشتر از ${faNum(cfg.flood.n)} پیام توی ${faNum(cfg.flood.sec)} ثانیه`, kb: { inline_keyboard: [
      [{ text: `${onoff(cfg.welcome.on)} پیام خوشامد`, callback_data: cb("tg", "welcome") },
       { text: `${onoff(cfg.rulesOnPost)} قوانین زیر پست`, callback_data: cb("tg", "rulesOnPost") }],
      [{ text: `${onoff(cfg.flood.on)} ضد اسپم`, callback_data: cb("tg", "flood") },
       { text: `${onoff(cfg.force.on)} عضویت اجباری`, callback_data: cb("tg", "force") }],
      [{ text: "➖", callback_data: cb("wm", "-1") }, { text: `حد اخطار: ${faNum(cfg.warn.max)}`, callback_data: cb("noop") },
       { text: "➕", callback_data: cb("wm", "1") }],
      [{ text: `مجازات اخطار: ${ACTION_FA[cfg.warn.action] || "بن"} 🔄`, callback_data: cb("wa") }],
      [{ text: `🔇 سکوت از اخطار دوم: ${cfg.warn.eachMins ? fmtLeft(cfg.warn.eachMins * 60e3) : "خاموش"} 🔄`, callback_data: cb("we") }],
      ...(priv ? [[ed("flood", "🛡 تنظیم ضد اسپم")]] : []),
      [{ text: `📮 گزارش‌ها: ${cfg.reportChat ? "توی گروه" : "خصوصی مالک"} 🔄`, callback_data: cb("rc") }],
      back(),
    ] } };
  }
  if (page === "texts") {
    return { text: `📜 <b>قوانین و متن‌ها</b>\n\n<b>قوانین:</b>\n${esc(cut(cfg.rules, 400))}\n\n<b>خوشامد:</b>\n${esc(cut(cfg.welcome.text, 200))}` + privHint,
      kb: { inline_keyboard: [
        ...(priv ? [[ed("rules", "✏️ ویرایش قوانین"), { text: "👁 کل قوانین", callback_data: cb("show", "rules") }],
                    [ed("welcome", "✏️ ویرایش خوشامد"), { text: "♻️ متن‌های پیش‌فرض", callback_data: cb("reset", "texts") }],
                    [ed("warntext", "✏️ متن اخطار"), ed("punishtext", "✏️ متن مجازات")]]
          : [[{ text: "👁 کل قوانین", callback_data: cb("show", "rules") }]]),
        back(),
      ] } };
  }
  if (page === "words") {
    return { text: `🚫 <b>کلمات و پاسخ‌ها</b>\nفیلتر (فقط پاک): ${faNum(cfg.filters.length)} • ممنوع (پاک + اخطار): ${faNum(cfg.bad.length)}`
      + ` • پاسخ خودکار: ${faNum(cfg.replies.length)}` + privHint, kb: { inline_keyboard: [
      ...(priv ? [[ed("filter_add", "➕ فیلتر"), ed("filter_del", "➖ فیلتر")],
                  [ed("bad_add", "➕ کلمه ممنوع"), ed("bad_del", "➖ کلمه ممنوع")],
                  [ed("reply_add", "➕ پاسخ خودکار"), ed("reply_del", "➖ پاسخ خودکار")]] : []),
      [{ text: "📋 نمایش همه", callback_data: cb("show", "words") }],
      back(),
    ] } };
  }
  if (page === "force") {
    return { text: `📢 <b>عضویت اجباری</b>: ${cfg.force.on ? "✅ روشن" : "❌ خاموش"}\nکانال‌ها (با زدن ❌ حذف میشن):` + privHint, kb: { inline_keyboard: [
      ...cfg.force.chans.map((c) => [{ text: `❌ ${c}`, callback_data: cb("fdel", c) }]),
      [{ text: `${cfg.force.on ? "⏸ خاموش کن" : "▶️ روشن کن"}`, callback_data: cb("tg", "force") }, ...(priv ? [ed("force_add", "➕ کانال")] : [])],
      back(),
    ] } };
  }
  if (page === "roles") {
    const dep = ctx.deputy;
    const rows = [];
    for (const [id, v] of Object.entries(cfg.admins)) rows.push([{ text: `❌ ⭐️ ${v.n || id}`, callback_data: cb("rdel", "a" + id) }]);
    for (const [id, v] of Object.entries(cfg.special)) rows.push([{ text: `❌ 💎 ${v.n || id}`, callback_data: cb("rdel", "s" + id) }]);
    if (priv) rows.push([ed("admin_add", "➕ ادمین"), ed("special_add", "➕ کاربر ویژه")]);
    if (priv && ctx.level >= L.owner) rows.push([ed("deputy", dep ? "🔄 عوض کردن جانشین" : "🎖 تعیین جانشین"),
                                                 ...(dep ? [{ text: "❌ حذف جانشین", callback_data: cb("rdel", "d") }] : [])]);
    rows.push(back());
    return { text: `👥 <b>نقش‌ها</b>\n🎖 جانشین مالک: ${dep ? mentionId(dep.id, dep.n) : "—"}\n`
      + `⭐️ ادمین‌های ربات: ${faNum(Object.keys(cfg.admins).length)} • 💎 ویژه‌ها: ${faNum(Object.keys(cfg.special).length)}\n`
      + `🛡 ادمین‌های خود تلگرام هم خودکار ادمین ربات حساب میشن.\nبرای حذف، روی ❌ کنار اسم بزن.` + privHint, kb: { inline_keyboard: rows } };
  }
  if (page === "stats") {
    return { text: await statsText(ctx.p, chatId, cfg.title), kb: { inline_keyboard: [[{ text: "🔄 تازه کردن", callback_data: cb("pg", "stats") }], back()] } };
  }
  const nLocks = Object.keys(cfg.locks).length;
  return { text: `🛠 <b>پنل مدیریت</b> — ${esc(cfg.title || "")}\n\nگروه: ${glockText(cfg)}\nقفل‌های فعال: ${faNum(nLocks)}\n`
    + `اخطار: ${faNum(cfg.warn.max)} تا ← ${ACTION_FA[cfg.warn.action] || "بن"}\nفیلتر: ${faNum(cfg.filters.length)} • ممنوع: ${faNum(cfg.bad.length)} • پاسخ خودکار: ${faNum(cfg.replies.length)}`,
    kb: { inline_keyboard: [
      [{ text: "🔐 قفل‌ها", callback_data: cb("pg", "locks") }, { text: "⚙️ تنظیمات", callback_data: cb("pg", "settings") }],
      [{ text: "📜 قوانین و متن‌ها", callback_data: cb("pg", "texts") }, { text: "🚫 کلمات و پاسخ‌ها", callback_data: cb("pg", "words") }],
      [{ text: "📢 عضویت اجباری", callback_data: cb("pg", "force") }, { text: "👥 نقش‌ها", callback_data: cb("pg", "roles") }],
      [{ text: "📊 آمار", callback_data: cb("pg", "stats") }],
      [{ text: "🔒 ۱ ساعت", callback_data: cb("gl", "60") }, { text: "🔒 ۳ ساعت", callback_data: cb("gl", "180") },
       { text: "🔒 تا صبح", callback_data: cb("gl", "morning") }],
      [{ text: "🔒 تا وقتی باز کنم", callback_data: cb("gl", "inf") }, { text: "🔓 باز کردن گروه", callback_data: cb("gl", "open") }],
      priv ? [{ text: "⬅️ لیست گروه‌ها", callback_data: "gs:list" }] : [{ text: "✖️ بستن پنل", callback_data: cb("x") }],
    ] } };
}

/** دکمه‌های پنل؛ level سطح کسیه که زده. خروجی: {alert?, page?, toast?, announce?, wait?, send?} */
export async function panelAction(p, cfg, chatId, op, arg, level) {
  if (op === "pg") return { page: arg };
  if (op === "noop") return {};
  if (op === "ed") {
    const e = EDITS[arg];
    if (!e) return {};
    if (level < e.min) return { alert: `⛔️ این کار برای ${ROLE_FA[e.min]} به بالاست.` };
    return { wait: arg, send: e.prompt + "\n\n(برای لغو: /cancel)" };
  }
  if (op === "show") {
    if (arg === "rules") return { send: `📜 <b>قوانین فعلی</b>\n\n${esc(cfg.rules)}` };
    return { send: `🚫 <b>فیلتر:</b> <tg-spoiler>${esc(cfg.filters.join("، ")) || "—"}</tg-spoiler>\n\n⛔️ <b>ممنوع:</b> <tg-spoiler>${esc(cfg.bad.join("، ")) || "—"}</tg-spoiler>\n\n`
      + `💬 <b>پاسخ‌های خودکار:</b>\n${cfg.replies.map((r) => `• ${esc(r.t)}${r.exact ? " (دقیق)" : ""} ← ${esc(r.r)}`).join("\n") || "—"}` };
  }
  if (op === "reset") {
    cfg.rules = RULES_TEXT; cfg.welcome.text = WELCOME_TEXT;
    await saveCfg(p, chatId, cfg);
    return { page: "texts", toast: "متن‌های پیش‌فرض برگشت" };
  }
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
      if (!cfg.force.chans.length) return { alert: "اول کانال رو اضافه کن (📢 عضویت اجباری ← ➕ کانال، توی خصوصی ربات)." };
      cfg.force.on = !cfg.force.on;
    }
    await saveCfg(p, chatId, cfg);
    return { page: "settings" };
  }
  if (op === "rc") {
    cfg.reportChat = cfg.reportChat ? 0 : chatId;
    await saveCfg(p, chatId, cfg);
    return { page: "settings" };
  }
  if (op === "wm") {
    cfg.warn.max = Math.min(20, Math.max(1, (cfg.warn.max || 3) + Number(arg)));
    await saveCfg(p, chatId, cfg);
    return { page: "settings" };
  }
  if (op === "we") {
    const steps = [0, 30, 60, 180, 360, 1440];
    cfg.warn.eachMins = steps[(steps.indexOf(cfg.warn.eachMins ?? 60) + 1) % steps.length];
    await saveCfg(p, chatId, cfg);
    return { page: "settings" };
  }
  if (op === "wa") {
    const order = ["ban", "mute", "kick"];
    cfg.warn.action = order[(order.indexOf(cfg.warn.action) + 1) % order.length];
    await saveCfg(p, chatId, cfg);
    return { page: "settings" };
  }
  if (op === "fdel") {
    cfg.force.chans = cfg.force.chans.filter((c) => c !== arg);
    if (!cfg.force.chans.length) cfg.force.on = false;
    await saveCfg(p, chatId, cfg);
    return { page: "force" };
  }
  if (op === "rdel") {
    if (arg === "d") {
      if (level < L.owner) return { alert: "⛔️ فقط مالک." };
      await p.kv.del("deputy");
      return { page: "roles", toast: "جانشین برداشته شد" };
    }
    const kind = arg[0] === "a" ? "admins" : "special", id = arg.slice(1);
    const rec = cfg[kind][id];
    if (!rec) return { page: "roles" };
    if (kind === "admins" && level < L.deputy) return { alert: "⛔️ عزل ادمین برای جانشین و مالکه." };
    if (rec.by > level) return { alert: `⛔️ اینو ${ROLE_FA[rec.by]} گذاشته.` };
    delete cfg[kind][id];
    await saveCfg(p, chatId, cfg);
    return { page: "roles", toast: "برداشته شد" };
  }
  return {};
}
