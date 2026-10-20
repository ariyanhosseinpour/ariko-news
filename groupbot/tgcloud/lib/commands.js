// همه‌ی دستورها (فارسی و انگلیسی، با یا بدون /). هر دستور: اسم‌ها، کمترین سطح لازم، و کارش.
// کاربر هدف: ریپلای، منشن، @یوزرنیم یا آیدی عددی. هیچ‌کس روی هم‌سطح یا سطح بالاتر از خودش دستور نداره.
import { L, ROLE_FA, LOCKS, OWNERS, esc, mention, mentionId, nameOf, norm, faNum, now, dayKey, hhmm, fmtLeft, fill,
         getMember, saveMember, getDeputy, levelOf, saveCfg, chatLink } from "./core.js";
import { parseTarget, parseDuration, parseLock } from "./parse.js";
import { punish, lift, warn, del, spoiler } from "./actions.js";
import { lockLine, glockText } from "./guard.js";
import { panelView } from "./panel.js";
import { statsText } from "./stats.js";

const ON = /^(روشن|فعال|on|enable|yes|بله)$/i, OFF = /^(خاموش|غیرفعال|غیر فعال|off|disable|no|خیر)$/i;
const ACTION = { "بن": "ban", "ban": "ban", "سکوت": "mute", "mute": "mute", "اخراج": "kick", "kick": "kick" };
const splitWords = (t) => String(t || "").split(/[،,\n]+/).map((x) => x.trim()).filter(Boolean);

/** کاربر هدف رو پیدا و چک می‌کنه که فرستنده بهش دسترسی داره */
async function target(c, { allowSelf = false } = {}) {
  const r = await parseTarget(c.p, c.msg, c.args);
  if (!r.user) {
    await c.reply(r.unknown ? `❌ ${esc(r.unknown)} رو نمی‌شناسم (تا حالا توی گروه پیام نداده). روی پیامش ریپلای کن یا آیدی عددیش رو بده.`
      : "❌ روی پیام کاربر ریپلای کن، یا یوزرنیم/آیدی عددیش رو بنویس.");
    return null;
  }
  if (r.user.id === c.botId) { await c.reply("🙂 روی خودم نمی‌تونم."); return null; }
  if (/^\d+$/.test(String(r.user.first_name))) {            // با آیدی عددی: اسمش از پیام‌هایی که قبلاً داده
    const m = await getMember(c.p, c.chat.id, r.user.id);
    if (m.n) r.user = { ...r.user, first_name: m.n };
  }
  if (!allowSelf && r.user.id === c.from.id) { await c.reply("❌ روی خودت نمی‌تونی."); return null; }
  const tl = await levelOf(c.p, c.chat.id, c.cfg, r.user.id, c.deputy);
  if (!allowSelf && tl >= c.level) {
    await c.reply(`⛔️ ${mention(r.user)} ${ROLE_FA[tl]}ه؛ روی هم‌سطح یا بالاتر از خودت دستور نداری.`);
    return null;
  }
  return { ...r, level: tl };
}

async function setText(c, key, label, sub) {
  const text = c.args || (c.msg.reply_to_message && (c.msg.reply_to_message.text || c.msg.reply_to_message.caption)) || "";
  if (!text.trim()) return c.reply(`متن ${label} رو بعد از دستور بنویس یا روی یه پیام ریپلای کن.${sub ? "\n" + sub : ""}`);
  if (key.includes(".")) { const [a, b] = key.split("."); c.cfg[a][b] = text.trim(); } else c.cfg[key] = text.trim();
  await saveCfg(c.p, c.chat.id, c.cfg);
  return c.reply(`✅ ${label} ذخیره شد.`);
}

async function toggle(c, path, label) {
  const [a, b] = path.split(".");
  const v = norm(c.args);
  if (!ON.test(v) && !OFF.test(v)) return c.reply(`${label}: ${c.cfg[a][b] ? "✅ روشن" : "❌ خاموش"}\nبرای تغییر: «… روشن» یا «… خاموش»`);
  c.cfg[a][b] = ON.test(v);
  await saveCfg(c.p, c.chat.id, c.cfg);
  return c.reply(`${label} ${c.cfg[a][b] ? "✅ روشن" : "❌ خاموش"} شد.`);
}

const stats = async (c) => c.reply(await statsText(c.p, c.chat.id, c.chat.title));

export const HELP = `📖 <b>راهنمای ربات مدیریت گروه</b>
همه‌ی دستورها فارسی و انگلیسی‌ان، با یا بدون «/». کاربر رو با <b>ریپلای</b>، <b>منشن</b>، <b>@یوزرنیم</b> یا <b>آیدی عددی</b> مشخص کن.

👮 <b>مجازات</b> (ادمین‌ها)
• اخطار [دلیل] — warn | حذف اخطار — unwarn | اخطارها — warns
• بن [مدت] [دلیل] — ban | رفع بن — unban
• سکوت [مدت] [دلیل] — mute | رفع سکوت — unmute
• اخراج [دلیل] — kick | حذف (ریپلای) — del | پاکسازی ۵۰ — clean
• مدت: «۳۰ دقیقه»، «۲ ساعت»، «۳ روز»، «تا صبح»، «تا ۱۴:۳۰»، «همیشه»

🔒 <b>قفل‌ها</b>
• قفل لینک / باز کردن لینک — lock link / unlock link
• «قفل لینک ادمین» = ادمین‌ها هم نتونن • «قفل لینک همه» = فقط مالک
• مجاز لینک @user / غیرمجاز لینک @user — allow / disallow
• قفل‌ها — locks • انواع: ${Object.values(LOCKS).join("، ")}
• قفل گروه [۳ ساعت | تا صبح | تا شب] — lockgroup | باز کردن گروه — unlockgroup
• قفل خودکار ۰۰:۰۰ ۰۸:۰۰ / قفل خودکار خاموش — autolock

👥 <b>نقش‌ها</b>
• ارتقا / عزل (ادمین ربات؛ جانشین و مالک) — promote / demote
• ویژه / حذف ویژه (معاف از قفل‌ها) — special / unspecial
• تنظیم جانشین / حذف جانشین (فقط مالک) — setdeputy / deldeputy
• ادمین‌ها — admins

⚙️ <b>تنظیمات</b>
• پنل — panel (همه‌ی تنظیمات با دکمه)
• قوانین — rules | تنظیم قوانین — setrules | قوانین زیر پست روشن/خاموش
• خوشامد روشن/خاموش | تنظیم خوشامد … ({name} {group})
• حد اخطار ۳ | مجازات اخطار بن/سکوت/اخراج [مدت] | سکوت اخطار ۱ ساعت/خاموش | متن اخطار … | متن مجازات …
  ({name} {count} {max} {reason} {action})
• فیلتر کلمه، کلمه — filter | حذف فیلتر — unfilter | فیلترها — filters
• کلمه ممنوع … (پاک + اخطار فوری) — badword | حذف کلمه ممنوع | کلمات ممنوع
• پاسخ خودکار سلام = سلام {name} — addreply | حذف پاسخ سلام | پاسخ‌ها
• ضد اسپم روشن/خاموش [۷ ۶] — antiflood
• عضویت اجباری @کانال | عضویت اجباری روشن/خاموش | حذف عضویت اجباری @کانال
• گزارش‌ها اینجا — reporthere | آمار — stats

🙋 <b>همه</b>
• قوانین | گزارش (ریپلای) — report | اطلاعات — info | آیدی — id | پنل من — me | راهنما — help`;

export const COMMANDS = {
  // ───── مجازات ─────
  warn: { names: ["اخطار", "warn"], min: L.admin, async run(c) {
    const t = await target(c); if (!t) return;
    await warn(c.p, c.chat, c.cfg, t.user, { reason: t.rest, byLevel: c.level, byUser: c.from,
                                             deleteIds: [t.replied && t.replied.message_id, c.msg.message_id] });
  } },
  unwarn: { names: ["حذف اخطار", "رفع اخطار", "unwarn"], min: L.admin, async run(c) {
    const t = await target(c); if (!t) return;
    const m = await getMember(c.p, c.chat.id, t.user.id);
    if (!m.w) return c.reply(`${mention(t.user)} اخطاری نداره.`);
    const last = (m.wr || [])[m.wr.length - 1];
    if (last && last.by > c.level) return c.reply(`⛔️ آخرین اخطار رو ${ROLE_FA[last.by]} داده؛ نمی‌تونی برش داری.`);
    m.w -= 1; m.wr = (m.wr || []).slice(0, -1);
    await saveMember(c.p, c.chat.id, t.user.id, m);
    return c.reply(`✅ یه اخطار ${mention(t.user)} برداشته شد (${faNum(m.w)} از ${faNum(c.cfg.warn.max)}).`);
  } },
  resetwarns: { names: ["حذف همه اخطارها", "پاکسازی اخطار", "resetwarns"], min: L.admin, async run(c) {
    const t = await target(c); if (!t) return;
    const m = await getMember(c.p, c.chat.id, t.user.id);
    if ((m.wr || []).some((x) => x.by > c.level)) return c.reply("⛔️ بعضی اخطارها رو سطح بالاتری داده؛ نمی‌تونی همه رو پاک کنی.");
    m.w = 0; m.wr = []; m.wby = 0;
    await saveMember(c.p, c.chat.id, t.user.id, m);
    return c.reply(`✅ همه‌ی اخطارهای ${mention(t.user)} پاک شد.`);
  } },
  warns: { names: ["اخطارها", "اخطار ها", "warns"], min: L.member, async run(c) {
    const r = await parseTarget(c.p, c.msg, c.args);
    const u = c.level >= L.admin && r.user ? r.user : c.from;
    const m = await getMember(c.p, c.chat.id, u.id);
    const list = (m.wr || []).slice(-(m.w || 0)).map((x, i) => `${faNum(i + 1)}. ${spoiler(x.r)}`).join("\n");
    return c.reply(`⚠️ اخطارهای ${mention(u)}: ${faNum(m.w || 0)} از ${faNum(c.cfg.warn.max)}${list ? "\n" + list : ""}`);
  } },
  ban: { names: ["بن", "مسدود", "ban"], min: L.admin, async run(c) {
    const t = await target(c); if (!t) return;
    const d = parseDuration(t.rest);
    await punish(c.p, c.chat, c.cfg, t.user, "ban", { until: d.until || 0, reason: d.until === null ? t.rest : d.rest,
      byLevel: c.level, byUser: c.from, deleteIds: [t.replied && t.replied.message_id, c.msg.message_id] })
      .catch((e) => c.reply("❌ نشد؛ ربات باید ادمین با دسترسی «بن کاربران» باشه."));
  } },
  unban: { names: ["رفع بن", "آنبن", "ان بن", "unban"], min: L.admin, async run(c) {
    const t = await target(c); if (!t) return;
    const r = await lift(c.p, c.chat, t.user, "ban", c.level).catch(() => ({ ok: false }));
    return c.reply(r.ok ? `✅ ${mention(t.user)} از بن دراومد.` : r.by ? `⛔️ این بن رو ${ROLE_FA[r.by]} زده؛ فقط خودش یا بالاتر می‌تونه برش داره.` : "❌ نشد.");
  } },
  mute: { names: ["سکوت", "ساکت", "mute"], min: L.admin, async run(c) {
    const t = await target(c); if (!t) return;
    const d = parseDuration(t.rest);
    await punish(c.p, c.chat, c.cfg, t.user, "mute", { until: d.until || 0, reason: d.until === null ? t.rest : d.rest,
      byLevel: c.level, byUser: c.from, deleteIds: [t.replied && t.replied.message_id, c.msg.message_id] })
      .catch(() => c.reply("❌ نشد؛ ربات باید ادمین با دسترسی «محدود کردن کاربران» باشه."));
  } },
  unmute: { names: ["رفع سکوت", "آزاد کردن", "unmute"], min: L.admin, async run(c) {
    const t = await target(c); if (!t) return;
    const r = await lift(c.p, c.chat, t.user, "mute", c.level).catch(() => ({ ok: false }));
    return c.reply(r.ok ? `✅ ${mention(t.user)} از سکوت دراومد.` : r.by ? `⛔️ این سکوت رو ${ROLE_FA[r.by]} زده؛ فقط خودش یا بالاتر می‌تونه برش داره.` : "❌ نشد.");
  } },
  kick: { names: ["اخراج", "کیک", "kick"], min: L.admin, async run(c) {
    const t = await target(c); if (!t) return;
    await punish(c.p, c.chat, c.cfg, t.user, "kick", { reason: t.rest, byLevel: c.level, byUser: c.from,
      deleteIds: [t.replied && t.replied.message_id, c.msg.message_id] }).catch(() => c.reply("❌ نشد؛ ربات باید ادمین با دسترسی «بن کاربران» باشه."));
  } },
  del: { names: ["حذف", "پاک کن", "del", "delete"], min: L.admin, async run(c) {
    const r = c.msg.reply_to_message;
    if (!r) return c.reply("روی پیامی که باید پاک بشه ریپلای کن.");
    if (r.from && r.from.id !== c.from.id && !r.sender_chat) {
      const tl = await levelOf(c.p, c.chat.id, c.cfg, r.from.id, c.deputy);
      if (tl >= c.level && r.from.id !== c.botId) return c.reply("⛔️ پیام هم‌سطح یا بالاتر از خودت رو نمی‌تونی پاک کنی.");
    }
    await del(c.p, c.chat.id, [r.message_id, c.msg.message_id]);
  } },
  clean: { names: ["پاکسازی", "پاک سازی", "clean", "purge"], min: L.admin, async run(c) {
    const r = c.msg.reply_to_message;
    let n = parseInt(norm(c.args), 10);
    if (r) n = c.msg.message_id - r.message_id;
    if (!n || n < 1) return c.reply("تعداد رو بنویس (مثلاً «پاکسازی ۵۰»)، یا روی اولین پیامی که باید پاک بشه ریپلای کن.");
    n = Math.min(n, 1000);
    const ids = [];
    for (let i = 0; i <= n; i++) ids.push(c.msg.message_id - i);
    for (let i = 0; i < ids.length; i += 100) await del(c.p, c.chat.id, ids.slice(i, i + 100));
    const m = await c.reply(`🧹 ${faNum(n)} پیام آخر پاک شد.`);
    return m;
  } },
  pin: { names: ["سنجاق", "پین", "pin"], min: L.admin, async run(c) {
    if (!c.msg.reply_to_message) return c.reply("روی پیام ریپلای کن.");
    await c.p.api("pinChatMessage", { chat_id: c.chat.id, message_id: c.msg.reply_to_message.message_id, disable_notification: /بی ?صدا|silent/.test(norm(c.args)) })
      .then(() => c.reply("📌 سنجاق شد.")).catch(() => c.reply("❌ نشد؛ ربات دسترسی «سنجاق پیام» نداره."));
  } },
  unpin: { names: ["حذف سنجاق", "برداشتن سنجاق", "unpin"], min: L.admin, async run(c) {
    const r = c.msg.reply_to_message;
    await c.p.api("unpinChatMessage", { chat_id: c.chat.id, ...(r ? { message_id: r.message_id } : {}) })
      .then(() => c.reply("✅ سنجاق برداشته شد.")).catch(() => c.reply("❌ نشد."));
  } },

  // ───── نقش‌ها ─────
  promote: { names: ["ارتقا", "ادمین کن", "promote"], min: L.deputy, async run(c) {
    const t = await target(c); if (!t) return;
    c.cfg.admins[t.user.id] = { n: nameOf(t.user), by: c.level, at: now() };
    delete c.cfg.special[t.user.id];
    await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(`⭐️ ${mention(t.user)} ادمین ربات شد.`);
  } },
  demote: { names: ["عزل", "برکنار", "demote"], min: L.deputy, async run(c) {
    const r = await parseTarget(c.p, c.msg, c.args);
    if (!r.user) return c.reply("❌ کاربر رو مشخص کن.");
    const a = c.cfg.admins[r.user.id];
    if (!a) return c.reply(`${mention(r.user)} ادمین ربات نیست${(c.cfg.tgAdmins.ids || []).includes(r.user.id) ? " (ادمین خود تلگرامه؛ از تنظیمات گروه عزلش کن)" : ""}.`);
    if (a.by > c.level) return c.reply(`⛔️ این ادمین رو ${ROLE_FA[a.by]} گذاشته؛ نمی‌تونی عزلش کنی.`);
    delete c.cfg.admins[r.user.id];
    await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(`✅ ${mention(r.user)} از ادمینی ربات عزل شد.`);
  } },
  special: { names: ["ویژه", "کاربر ویژه", "special", "vip"], min: L.admin, async run(c) {
    const t = await target(c); if (!t) return;
    c.cfg.special[t.user.id] = { n: nameOf(t.user), by: c.level, at: now() };
    await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(`💎 ${mention(t.user)} کاربر ویژه شد (از قفل‌ها و ضد اسپم معافه).`);
  } },
  unspecial: { names: ["حذف ویژه", "unspecial", "unvip"], min: L.admin, async run(c) {
    const r = await parseTarget(c.p, c.msg, c.args);
    if (!r.user || !c.cfg.special[r.user.id]) return c.reply("این کاربر ویژه نیست.");
    if (c.cfg.special[r.user.id].by > c.level) return c.reply(`⛔️ ${ROLE_FA[c.cfg.special[r.user.id].by]} ویژه‌اش کرده.`);
    delete c.cfg.special[r.user.id];
    await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(`✅ ${mention(r.user)} دیگه ویژه نیست.`);
  } },
  setdeputy: { names: ["تنظیم جانشین", "جانشین", "setdeputy"], min: L.owner, async run(c) {
    const r = await parseTarget(c.p, c.msg, c.args);
    if (!r.user) return c.reply("❌ کاربر رو مشخص کن.");
    await c.p.kv.set("deputy", { id: r.user.id, n: nameOf(r.user) });
    return c.reply(`👑 ${mention(r.user)} جانشین مالک شد (توی همه‌ی گروه‌ها؛ ادمین‌ها رو کنترل می‌کنه، ولی مالک رو نه).`);
  } },
  deldeputy: { names: ["حذف جانشین", "deldeputy"], min: L.owner, async run(c) {
    await c.p.kv.del("deputy");
    return c.reply("✅ جانشین برداشته شد.");
  } },
  admins: { names: ["ادمین ها", "ادمینها", "لیست ادمین", "admins", "staff"], min: L.member, async run(c) {
    const d = c.deputy;
    const tg = c.cfg.tgAdmins.ids || [];
    const lines = [`👑 مالک: ${OWNERS.map((id) => mentionId(id, "مالک")).join("، ")}`];
    if (d) lines.push(`🎖 جانشین: ${mentionId(d.id, d.n)}`);
    const a = Object.entries(c.cfg.admins).map(([id, v]) => `⭐️ ${mentionId(id, v.n)}`);
    if (a.length) lines.push("ادمین‌های ربات:\n" + a.join("\n"));
    if (tg.length) lines.push(`🛡 ادمین‌های تلگرام: ${faNum(tg.length)} نفر`);
    const s = Object.entries(c.cfg.special).map(([id, v]) => `💎 ${mentionId(id, v.n)}`);
    if (s.length) lines.push("کاربران ویژه:\n" + s.join("\n"));
    return c.reply(lines.join("\n\n"));
  } },

  // ───── قفل‌ها ─────
  lockgroup: { names: ["قفل گروه", "بستن گروه", "lockgroup", "lock group", "lockall"], min: L.admin, async run(c) {
    const cur = c.cfg.glock || {};
    if ((cur.until === -1 || cur.until > now()) && cur.by > c.level) return c.reply(`⛔️ گروه رو ${ROLE_FA[cur.by]} قفل کرده.`);
    const all = /(^|\s)(همه|all)(\s|$)/.test(norm(c.args));
    if (all && c.level < L.deputy) return c.reply("⛔️ «قفل گروه همه» (ادمین‌ها هم نتونن) فقط برای مالک و جانشینه.");
    const d = parseDuration(norm(c.args).replace(/(^|\s)(همه|all)(\s|$)/, " "));
    const until = d.until ? d.until : -1;
    c.cfg.glock = { until, by: c.level, lvl: all ? L.deputy : L.admin, ann: 0 };
    await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(`🔒 گروه قفل شد${until === -1 ? " (تا وقتی باز بشه)" : ` تا ساعت ${hhmm(until)} (${fmtLeft(until - now())})`}.\n`
      + `${all ? "فقط مالک و جانشین" : "فقط ادمین‌ها"} می‌تونن پیام بدن؛ پیام بقیه پاک میشه.`);
  } },
  unlockgroup: { names: ["باز کردن گروه", "بازکردن گروه", "باز شدن گروه", "unlockgroup", "unlock group", "unlockall"], min: L.admin, async run(c) {
    const cur = c.cfg.glock || {};
    if (cur.by > c.level && (cur.until === -1 || cur.until > now())) return c.reply(`⛔️ گروه رو ${ROLE_FA[cur.by]} قفل کرده؛ فقط خودش یا بالاتر بازش می‌کنه.`);
    c.cfg.glock = { until: 0, by: 0, ann: 1 };
    await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply("🔓 گروه باز شد.");
  } },
  autolock: { names: ["قفل خودکار", "قفل شبانه", "autolock", "nightlock"], min: L.admin, async run(c) {
    const a = norm(c.args);
    if (c.cfg.night.on && (c.cfg.night.by || 0) > c.level) return c.reply(`⛔️ قفل خودکار رو ${ROLE_FA[c.cfg.night.by]} تنظیم کرده.`);
    if (OFF.test(a)) { c.cfg.night.on = false; await saveCfg(c.p, c.chat.id, c.cfg); return c.reply("✅ قفل خودکار خاموش شد."); }
    const m = a.match(/(\d{1,2})(?::(\d{2}))?\s+(?:تا\s+)?(\d{1,2})(?::(\d{2}))?/);
    if (!m) return c.reply(`قفل خودکار: ${c.cfg.night.on ? `✅ هر روز ${esc(c.cfg.night.from)} تا ${esc(c.cfg.night.to)}` : "❌ خاموش"}\nتنظیم: «قفل خودکار ۰۰:۰۰ ۰۸:۰۰» • خاموش: «قفل خودکار خاموش»`);
    const f = (h, mm) => `${String(Number(h) % 24).padStart(2, "0")}:${String(Number(mm || 0)).padStart(2, "0")}`;
    c.cfg.night = { on: true, from: f(m[1], m[2]), to: f(m[3], m[4]), by: c.level };
    await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(`🌙 از این به بعد گروه هر روز از ${c.cfg.night.from} تا ${c.cfg.night.to} (وقت تهران) خودکار قفل میشه.`);
  } },
  lock: { names: ["قفل", "lock"], min: L.admin, async run(c) {
    const lk = parseLock(c.args);
    if (!lk) return c.reply(`نوع قفل رو بنویس، مثلاً «قفل لینک».\nانواع: ${Object.values(LOCKS).join("، ")}`);
    const scope = /(^|\s)(همه|all)(\s|$)/.test(lk.rest) ? L.owner : /(^|\s)(ادمین|ادمین ها|admin|admins)(\s|$)/.test(lk.rest) ? L.deputy : L.special;
    if (scope > L.special && c.level < L.deputy) return c.reply("⛔️ قفلی که شامل ادمین‌ها هم بشه، فقط برای مالک و جانشینه.");
    const cur = c.cfg.locks[lk.key];
    if (cur && cur.by > c.level) return c.reply(`⛔️ این قفل رو ${ROLE_FA[cur.by]} گذاشته.`);
    c.cfg.locks[lk.key] = { lvl: Math.min(scope, c.level === L.owner ? L.owner : scope), by: c.level };
    await saveCfg(c.p, c.chat.id, c.cfg);
    const who = scope >= L.owner ? "هیچ‌کس جز مالک" : scope >= L.deputy ? "ادمین‌ها هم نمی‌تونن؛ فقط مالک و جانشین" : "فقط ادمین‌ها و کاربران ویژه می‌تونن";
    return c.reply(`🔒 ${lk.name} قفل شد (${who}).`);
  } },
  unlock: { names: ["باز کردن", "بازکردن", "آزاد کن", "unlock"], min: L.admin, async run(c) {
    const lk = parseLock(c.args);
    if (!lk) return c.reply("نوع قفل رو بنویس، مثلاً «باز کردن لینک».");
    const cur = c.cfg.locks[lk.key];
    if (!cur) return c.reply(`${lk.name} قفل نیست.`);
    if (cur.by > c.level) return c.reply(`⛔️ این قفل رو ${ROLE_FA[cur.by]} گذاشته؛ فقط خودش یا بالاتر بازش می‌کنه.`);
    delete c.cfg.locks[lk.key];
    await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(`🔓 ${lk.name} باز شد.`);
  } },
  locks: { names: ["قفل ها", "قفلها", "locks"], min: L.member, async run(c) {
    const on = Object.keys(LOCKS).filter((k) => c.cfg.locks[k]).map((k) => lockLine(c.cfg, k));
    return c.reply(`🔐 <b>وضعیت قفل‌ها</b>\nگروه: ${glockText(c.cfg)}\n\n${on.length ? on.join("\n") : "هیچ قفلی فعال نیست."}`);
  } },
  allow: { names: ["مجاز", "allow"], min: L.admin, async run(c) {
    const lk = parseLock(c.args);
    if (!lk) return c.reply("مثلاً: «مجاز لینک @user» (با ریپلای هم میشه).");
    c.args = lk.rest;
    const r = await parseTarget(c.p, c.msg, lk.rest);
    if (!r.user) return c.reply("❌ کاربر رو مشخص کن.");
    c.cfg.allow[lk.key] = [...new Set([...(c.cfg.allow[lk.key] || []), r.user.id])];
    await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(`✅ ${mention(r.user)} با وجود قفل ${lk.name} مجازه.`);
  } },
  disallow: { names: ["غیرمجاز", "غیر مجاز", "disallow"], min: L.admin, async run(c) {
    const lk = parseLock(c.args);
    if (!lk) return c.reply("مثلاً: «غیرمجاز لینک @user».");
    const r = await parseTarget(c.p, c.msg, lk.rest);
    if (!r.user) return c.reply("❌ کاربر رو مشخص کن.");
    c.cfg.allow[lk.key] = (c.cfg.allow[lk.key] || []).filter((x) => x !== r.user.id);
    await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(`✅ ${mention(r.user)} دیگه از قفل ${lk.name} معاف نیست.`);
  } },

  // ───── قوانین / خوشامد / متن‌ها ─────
  rules: { names: ["قوانین", "قانون", "rules"], min: L.member, async run(c) {
    return c.reply(c.cfg.rules ? `📜 <b>قوانین ${esc(c.chat.title || "گروه")}</b>\n\n${esc(c.cfg.rules)}` : "هنوز قانونی ثبت نشده.");
  } },
  setrules: { names: ["تنظیم قوانین", "setrules"], min: L.admin, run: (c) => setText(c, "rules", "قوانین") },
  rulespost: { names: ["قوانین زیر پست", "rulespost"], min: L.admin, run: (c) => toggleRoot(c, "rulesOnPost", "فرستادن قوانین زیر پست‌های کانال") },
  welcome: { names: ["خوشامد", "خوش آمد", "خوشامدگویی", "welcome"], min: L.admin, run: (c) => toggle(c, "welcome.on", "پیام خوشامد") },
  setwelcome: { names: ["تنظیم خوشامد", "setwelcome"], min: L.admin, run: (c) => setText(c, "welcome.text", "متن خوشامد", "می‌تونی از {name} و {group} استفاده کنی.") },
  setwarn: { names: ["حد اخطار", "تنظیم اخطار", "setwarn"], min: L.admin, async run(c) {
    const n = parseInt(norm(c.args), 10);
    if (!n || n < 1 || n > 20) return c.reply(`حد اخطار الان ${faNum(c.cfg.warn.max)}ه. مثلاً: «حد اخطار ۳».`);
    c.cfg.warn.max = n; await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(`✅ با ${faNum(n)} اخطار، مجازات خودکار اعمال میشه.`);
  } },
  warnaction: { names: ["مجازات اخطار", "warnaction"], min: L.admin, async run(c) {
    const [w, ...rest] = norm(c.args).split(" ");
    const a = ACTION[w];
    if (!a) return c.reply("مثلاً: «مجازات اخطار بن» یا «مجازات اخطار سکوت ۱ روز» یا «مجازات اخطار اخراج».");
    c.cfg.warn.action = a;
    if (a === "mute") { const d = parseDuration(rest.join(" ")); if (d.until) c.cfg.warn.muteMins = Math.round((d.until - now()) / 60000); }
    await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(`✅ مجازات رسیدن به حد اخطار: ${w}${a === "mute" ? ` (${fmtLeft(c.cfg.warn.muteMins * 60e3)})` : ""}.`);
  } },
  warnmute: { names: ["سکوت اخطار", "warnmute"], min: L.admin, async run(c) {
    const a = norm(c.args);
    if (OFF.test(a)) c.cfg.warn.eachMins = 0;
    else {
      const d = parseDuration(a);
      if (!d.until) return c.reply(`سکوت از اخطار دوم به بعد: ${c.cfg.warn.eachMins ? fmtLeft(c.cfg.warn.eachMins * 60e3) : "❌ خاموش"}\n`
        + "تنظیم: «سکوت اخطار ۱ ساعت» / «سکوت اخطار ۳۰ دقیقه» • خاموش: «سکوت اخطار خاموش»");
      c.cfg.warn.eachMins = Math.max(1, Math.round((d.until - now()) / 60000));
    }
    await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(c.cfg.warn.eachMins ? `✅ از این به بعد از اخطار دوم به بعد، هر اخطار ${fmtLeft(c.cfg.warn.eachMins * 60e3)} سکوت داره (اخطار اول فقط تذکره).` : "✅ سکوت بعد از اخطار خاموش شد.");
  } },
  warntext: { names: ["متن اخطار", "warntext"], min: L.admin, run: (c) => setText(c, "warn.text", "متن اخطار", "{name} {count} {max} {reason}") },
  punishtext: { names: ["متن مجازات", "punishtext"], min: L.admin, run: (c) => setText(c, "warn.punish", "متن مجازات", "{name} {max} {action} {reason}") },

  // ───── فیلتر و کلمات ─────
  filter: { names: ["فیلتر", "filter"], min: L.admin, async run(c) {
    const w = splitWords(c.args); if (!w.length) return c.reply("کلمه رو بنویس: «فیلتر کلمه۱، کلمه۲».");
    c.cfg.filters = [...new Set([...c.cfg.filters, ...w])]; await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(`✅ فیلتر شد (پیامی که داشته باشه پاک میشه): ${w.map(esc).join("، ")}`);
  } },
  unfilter: { names: ["حذف فیلتر", "unfilter"], min: L.admin, async run(c) {
    const w = splitWords(c.args).map(norm);
    c.cfg.filters = c.cfg.filters.filter((x) => !w.includes(norm(x))); await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply("✅ از فیلتر برداشته شد.");
  } },
  filters: { names: ["فیلترها", "فیلتر ها", "filters"], min: L.admin, async run(c) {
    return c.reply(c.cfg.filters.length ? `🚫 کلمات فیلتر:\n${spoiler(c.cfg.filters.join("، "))}` : "هیچ کلمه‌ای فیلتر نیست.");
  } },
  badword: { names: ["کلمه ممنوع", "badword"], min: L.admin, async run(c) {
    const w = splitWords(c.args); if (!w.length) return c.reply("کلمه رو بنویس: «کلمه ممنوع کلمه۱، کلمه۲».");
    c.cfg.bad = [...new Set([...c.cfg.bad, ...w])]; await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(`✅ ممنوع شد (هر کی بگه: پیامش پاک و فوری اخطار می‌گیره): ${w.map(esc).join("، ")}`);
  } },
  unbadword: { names: ["حذف کلمه ممنوع", "حذف ممنوع", "unbadword"], min: L.admin, async run(c) {
    const w = splitWords(c.args).map(norm);
    c.cfg.bad = c.cfg.bad.filter((x) => !w.includes(norm(x))); await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply("✅ از کلمات ممنوع برداشته شد.");
  } },
  badwords: { names: ["کلمات ممنوع", "badwords"], min: L.admin, async run(c) {
    return c.reply(c.cfg.bad.length ? `⛔️ کلمات ممنوع:\n${spoiler(c.cfg.bad.join("، "))}` : "هیچ کلمه‌ی ممنوعی نیست.");
  } },
  addreply: { names: ["پاسخ خودکار", "addreply"], min: L.admin, async run(c) {
    const m = c.args.split(/\s*[=|]\s*/);
    if (m.length < 2 || !m[0] || !m[1]) return c.reply("مثلاً: «پاسخ خودکار سلام = سلام {name} 👋» (کلمه‌ی دقیق: اولش ! بذار).");
    const exact = m[0].startsWith("!");
    const t = m[0].replace(/^!/, "").trim();
    c.cfg.replies = [...c.cfg.replies.filter((r) => norm(r.t) !== norm(t)), { t, r: m.slice(1).join(" = ").trim(), exact }];
    await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(`✅ پاسخ خودکار برای «${esc(t)}» ثبت شد.`);
  } },
  delreply: { names: ["حذف پاسخ", "delreply"], min: L.admin, async run(c) {
    c.cfg.replies = c.cfg.replies.filter((r) => norm(r.t) !== norm(c.args.replace(/^!/, ""))); await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply("✅ پاسخ خودکار برداشته شد.");
  } },
  replies: { names: ["پاسخ ها", "پاسخها", "replies"], min: L.admin, async run(c) {
    return c.reply(c.cfg.replies.length ? "💬 پاسخ‌های خودکار:\n" + c.cfg.replies.map((r) => `• ${esc(r.t)}${r.exact ? " (دقیق)" : ""} ← ${esc(r.r)}`).join("\n")
      : "هیچ پاسخ خودکاری ثبت نشده.");
  } },

  // ───── ضد اسپم / عضویت اجباری ─────
  antiflood: { names: ["ضد اسپم", "ضد فلود", "antiflood", "flood"], min: L.admin, async run(c) {
    const a = norm(c.args).split(" ");
    if (ON.test(a[0]) || OFF.test(a[0])) {
      c.cfg.flood.on = ON.test(a[0]);
      if (a[1] && a[2]) { c.cfg.flood.n = Math.max(3, Number(a[1]) || 7); c.cfg.flood.sec = Math.max(2, Number(a[2]) || 6); }
      await saveCfg(c.p, c.chat.id, c.cfg);
    }
    return c.reply(`🛡 ضد اسپم: ${c.cfg.flood.on ? `✅ روشن — بیشتر از ${faNum(c.cfg.flood.n)} پیام توی ${faNum(c.cfg.flood.sec)} ثانیه = ${fmtLeft(c.cfg.flood.muteMins * 60e3)} سکوت` : "❌ خاموش"}`);
  } },
  forcejoin: { names: ["عضویت اجباری", "forcejoin"], min: L.admin, async run(c) {
    const a = c.args.trim();
    const ch = a.match(/@([A-Za-z0-9_]{4,})|(-100\d{5,})/);
    if (ch) {
      const id = ch[1] ? "@" + ch[1] : ch[2];
      try { await c.p.api("getChat", { chat_id: id }); } catch (e) { return c.reply("❌ این کانال پیدا نشد؛ ربات رو ادمین کانال کن."); }
      c.cfg.force.chans = [...new Set([...c.cfg.force.chans, id])]; c.cfg.force.on = true;
    } else if (ON.test(norm(a)) || OFF.test(norm(a))) c.cfg.force.on = ON.test(norm(a));
    else return c.reply(`📢 عضویت اجباری: ${c.cfg.force.on ? "✅ روشن" : "❌ خاموش"}\nکانال‌ها: ${c.cfg.force.chans.map(esc).join("، ") || "—"}\n`
      + "اضافه: «عضویت اجباری @کانال» (ربات باید ادمین کانال باشه) • «عضویت اجباری خاموش»");
    await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(`✅ عضویت اجباری ${c.cfg.force.on ? "روشنه" : "خاموش شد"}. کانال‌ها: ${c.cfg.force.chans.map(esc).join("، ") || "—"}`);
  } },
  delforcejoin: { names: ["حذف عضویت اجباری", "delforcejoin"], min: L.admin, async run(c) {
    const ch = c.args.match(/@([A-Za-z0-9_]{4,})|(-100\d{5,})/);
    if (!ch) return c.reply("کانال رو بنویس: «حذف عضویت اجباری @کانال».");
    const id = ch[1] ? "@" + ch[1] : ch[2];
    c.cfg.force.chans = c.cfg.force.chans.filter((x) => x.toLowerCase() !== id.toLowerCase());
    if (!c.cfg.force.chans.length) c.cfg.force.on = false;
    await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply("✅ برداشته شد.");
  } },

  // ───── گزارش / آمار / اطلاعات ─────
  report: { names: ["گزارش", "ریپورت", "report"], min: L.member, async run(c) {
    const r = c.msg.reply_to_message;
    if (!r) return c.reply("روی پیامی که می‌خوای گزارش بدی ریپلای کن.");
    const text = `🚩 <b>گزارش جدید</b> — ${esc(c.chat.title || "")}\nگزارش‌دهنده: ${mention(c.from)}\n`
      + (r.from ? `کاربر: ${mention(r.from)} (<code>${r.from.id}</code>)\n` : "")
      + (c.args ? `توضیح: ${esc(c.args)}\n` : "") + `<a href="${chatLink(c.chat, r.message_id)}">رفتن به پیام</a>`;
    const to = c.cfg.reportChat ? [c.cfg.reportChat] : [...OWNERS, ...(c.deputy ? [c.deputy.id] : [])];
    let ok = 0;
    for (const id of to) { try { await c.p.api("sendMessage", { chat_id: id, text, parse_mode: "HTML" }); ok++; } catch (e) { /* */ } }
    await del(c.p, c.chat.id, c.msg.message_id);
    return c.reply(ok ? `✅ ${mention(c.from)} گزارشت به مدیرها رسید.` : "❌ گزارش نرسید؛ مدیرها باید یه بار ربات رو استارت کرده باشن.");
  } },
  reporthere: { names: ["گزارش ها اینجا", "گزارشها اینجا", "reporthere"], min: L.admin, async run(c) {
    const off = OFF.test(norm(c.args));
    c.cfg.reportChat = off ? 0 : c.chat.id; await saveCfg(c.p, c.chat.id, c.cfg);
    return c.reply(off ? "✅ گزارش‌ها از این به بعد برای مالک و جانشین (خصوصی) میاد." : "✅ گزارش‌ها از این به بعد همین‌جا فرستاده میشه.");
  } },
  stats: { names: ["آمار", "stats", "statistics"], min: L.admin, run: stats },
  info: { names: ["اطلاعات", "info", "whois"], min: L.member, async run(c) {
    const r = await parseTarget(c.p, c.msg, c.args);
    const u = r.user || c.from;
    const lvl = await levelOf(c.p, c.chat.id, c.cfg, u.id, c.deputy);
    const m = await getMember(c.p, c.chat.id, u.id);
    let st = "";
    try { st = (await c.p.api("getChatMember", { chat_id: c.chat.id, user_id: u.id })).status; } catch (e) { /* */ }
    const ST = { creator: "سازنده‌ی گروه", administrator: "ادمین تلگرام", member: "عضو", restricted: "محدود", left: "بیرون از گروه", kicked: "بن" };
    return c.reply(`👤 ${mention(u)}\n🆔 <code>${u.id}</code>${u.username ? `\n🔗 @${esc(u.username)}` : ""}\n🎖 نقش: ${ROLE_FA[lvl]}`
      + `${st ? `\n📍 وضعیت: ${ST[st] || st}` : ""}\n⚠️ اخطار: ${faNum(m.w || 0)} از ${faNum(c.cfg.warn.max)}\n💬 پیام‌ها: ${faNum(m.c || 0)}`
      + (m.mute && (m.mute.until === 0 || m.mute.until > now()) ? `\n🔇 سکوت${m.mute.until ? ` تا ${hhmm(m.mute.until)}` : " دائمی"}` : ""));
  } },
  id: { names: ["آیدی", "ایدی", "id"], min: L.member, async run(c) {
    const r = c.msg.reply_to_message;
    const u = r && r.from ? r.from : c.from;
    return c.reply(`🆔 ${mention(u)}: <code>${u.id}</code>\n💬 گروه: <code>${c.chat.id}</code>`);
  } },
  me: { names: ["پنل من", "پنل کاربری", "me", "mypanel"], min: L.member, async run(c) {
    const m = await getMember(c.p, c.chat.id, c.from.id);
    const today = (await c.p.kv.get(`d:${c.chat.id}:${dayKey()}`)) || { u: {} };
    return c.reply(`🙋 <b>پنل کاربری ${mention(c.from)}</b>\n🎖 نقش: ${ROLE_FA[c.level]}\n⚠️ اخطار: ${faNum(m.w || 0)} از ${faNum(c.cfg.warn.max)}`
      + `\n💬 پیام‌های امروز: ${faNum(((today.u || {})[c.from.id] || [0])[0])}\n📨 کل پیام‌ها: ${faNum(m.c || 0)}`
      + `\n\nدستورهای تو: قوانین • گزارش (ریپلای) • اطلاعات • آیدی • راهنما`);
  } },
  panel: { names: ["پنل", "پنل مدیریت", "تنظیمات", "panel", "settings"], min: L.admin, async run(c) {
    const v = await panelView(c.cfg, c.chat.id, "main", { p: c.p, level: c.level, deputy: c.deputy });
    return c.reply(v.text, { reply_markup: v.kb });
  } },
  help: { names: ["راهنما", "دستورات", "help", "commands"], min: L.member, run: (c) => c.reply(HELP) },
  activate: { names: ["فعال سازی", "فعالسازی", "فعال", "activate"], min: L.deputy, async run(c) {
    c.cfg.active = true; c.cfg.title = c.chat.title || ""; await saveCfg(c.p, c.chat.id, c.cfg);
    await c.p.kv.set("grp:" + c.chat.id, { t: c.chat.title || "", at: now() });
    return c.reply("✅ ربات توی این گروه فعال شد.\n• «پنل» برای تنظیمات با دکمه\n• «راهنما» برای همه‌ی دستورها\n"
      + "• یادت نره ربات رو ادمین کنی (پاک کردن پیام، بن و محدود کردن، سنجاق).");
  } },
  deactivate: { names: ["غیرفعال", "غیر فعال", "deactivate"], min: L.deputy, async run(c) {
    c.cfg.active = false; await saveCfg(c.p, c.chat.id, c.cfg); await c.p.kv.del("grp:" + c.chat.id);
    return c.reply("⏸ ربات توی این گروه غیرفعال شد (تنظیمات می‌مونه؛ با «فعال» برمی‌گرده).");
  } },
};

async function toggleRoot(c, key, label) {
  const v = norm(c.args);
  if (!ON.test(v) && !OFF.test(v)) return c.reply(`${label}: ${c.cfg[key] ? "✅ روشن" : "❌ خاموش"}\nبرای تغییر: «… روشن» یا «… خاموش»`);
  c.cfg[key] = ON.test(v);
  await saveCfg(c.p, c.chat.id, c.cfg);
  return c.reply(`${label} ${c.cfg[key] ? "✅ روشن" : "❌ خاموش"} شد.`);
}

export { fill };
