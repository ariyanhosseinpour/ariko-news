// نگهبان پیام‌ها: قفل گروه (زمان‌دار/شبانه)، عضویت اجباری، ضد اسپم، قفل‌ها، فیلتر کلمات، کلمات ممنوع (اخطار فوری)، پاسخ خودکار.
import { L, LOCKS, esc, mention, norm, now, minutesOfDay, hhmm, fmtLeft, getMember, saveMember, saveCfg } from "./core.js";
import { warn, mute, del } from "./actions.js";

const send = (p, chatId, text, extra = {}) =>
  p.api("sendMessage", { chat_id: chatId, text, parse_mode: "HTML", disable_web_page_preview: true, ...extra }).catch(() => null);

/** نوع‌های محتوای یه پیام (برای قفل‌ها) */
export function contentKinds(msg) {
  const k = new Set();
  const ents = [...(msg.entities || []), ...(msg.caption_entities || [])];
  const text = msg.text || msg.caption || "";
  if (ents.some((e) => e.type === "url" || e.type === "text_link") || /(https?:\/\/|www\.|t\.me\/|telegram\.me\/)\S+/i.test(text)) k.add("link");
  if (ents.some((e) => e.type === "mention" || e.type === "text_mention")) k.add("mention");
  if (ents.some((e) => e.type === "hashtag")) k.add("hashtag");
  if (ents.some((e) => e.type === "custom_emoji")) k.add("emoji");
  if (msg.forward_origin || msg.forward_from || msg.forward_from_chat || msg.forward_sender_name) k.add("forward");
  if (msg.sticker) k.add("sticker");
  if (msg.animation) k.add("gif");
  else if (msg.document) k.add("file");
  if (msg.photo) k.add("photo");
  if (msg.video) k.add("video");
  if (msg.video_note) k.add("videonote");
  if (msg.voice) k.add("voice");
  if (msg.audio) k.add("audio");
  if (msg.contact) k.add("contact");
  if (msg.location || msg.venue) k.add("location");
  if (msg.poll) k.add("poll");
  if (msg.dice) k.add("dice");
  if (msg.game) k.add("game");
  if (msg.via_bot) k.add("inline");
  if (msg.reply_markup) k.add("button");
  if (msg.text) k.add("text");
  if (/[A-Za-z]{3,}/.test(text.replace(/(https?:\/\/|www\.)\S+|@\w+|#\w+/g, ""))) k.add("english");
  return k;
}

/** قفل گروه الان فعاله؟ (قفل زمان‌دار یا بازه‌ی شبانه) → {on, until, by, night} */
export function groupLockState(cfg, t = now()) {
  if (cfg.glock && (cfg.glock.until === -1 || cfg.glock.until > t)) return { on: true, until: cfg.glock.until, by: cfg.glock.by, lvl: cfg.glock.lvl };
  if (cfg.night && cfg.night.on) {
    const toMin = (s) => { const [h, m] = String(s).split(":").map(Number); return (h % 24) * 60 + (m || 0); };
    const a = toMin(cfg.night.from), b = toMin(cfg.night.to), x = minutesOfDay(t);
    const inside = a <= b ? x >= a && x < b : x >= a || x < b;
    if (inside) return { on: true, night: true, by: cfg.night.by || L.admin, lvl: L.admin };
  }
  return { on: false };
}

const wordHit = (text, words) => {
  const t = " " + norm(text).replace(/[^\p{L}\p{N}]+/gu, " ") + " ";
  return words.find((w) => {
    const n = norm(w);
    return n && (n.includes(" ") ? t.includes(" " + n + " ") || norm(text).includes(n) : t.includes(" " + n + " "));
  });
};

/**
 * پیام یه عضو رو بررسی می‌کنه. خروجی: true یعنی پیام پاک/رسیدگی شد (دیگه کاری نکن).
 * level: سطح فرستنده. state: {member} رکورد عضو (برای ضد اسپم و عضویت اجباری)
 */
export async function guard(p, msg, cfg, level, member, { edited = false } = {}) {
  const chat = msg.chat, u = msg.from, t = now();
  if (level >= L.owner) return false;                        // مالک: هیچ محدودیتی

  // قفل کل گروه
  const gl = groupLockState(cfg, t);
  if (!gl.on && cfg.glock && cfg.glock.until > 0 && cfg.glock.until <= t && !cfg.glock.ann) {
    cfg.glock = { until: 0, by: 0, ann: 1 };                 // تموم شد؛ یه بار اعلام
    await saveCfg(p, chat.id, cfg);
    await send(p, chat.id, "🔓 زمان قفل گروه تموم شد؛ گروه باز شد.");
  }
  if (gl.on && level < (gl.lvl || L.admin)) {             // معمولاً فقط ادمین‌ها؛ «قفل گروه همه» = فقط مالک/جانشین
    await del(p, chat.id, msg.message_id);
    return true;
  }

  // عضویت اجباری (ویژه‌ها و بالاتر معافن)
  if (!edited && cfg.force.on && cfg.force.chans.length && level < L.special) {
    if (!member.fj || member.fj < t) {
      const missing = [];
      for (const ch of cfg.force.chans) {
        try {
          const st = await p.api("getChatMember", { chat_id: ch, user_id: u.id });
          if (!["creator", "administrator", "member"].includes(st.status) && !(st.status === "restricted" && st.is_member)) missing.push(ch);
        } catch (e) { /* ربات ادمین اون کانال نیست؛ اون کانال رو نادیده بگیر */ }
      }
      if (missing.length) {
        await del(p, chat.id, msg.message_id);
        if (!member.fjp || t - member.fjp > 120e3) {         // هر ۲ دقیقه یه بار تذکر، نه برای هر پیام
          member.fjp = t;
          const kb = { inline_keyboard: missing.map((c, i) => [{ text: `📢 عضویت در کانال ${i + 1}`, url: `https://t.me/${String(c).replace(/^@/, "")}` }])
            .concat([[{ text: "✅ عضو شدم", callback_data: `fj:${u.id}` }]]) };
          await send(p, chat.id, `${mention(u)} برای پیام دادن توی گروه، اول باید عضو ${missing.length > 1 ? "این کانال‌ها" : "این کانال"} بشی 👇`,
                     { reply_markup: kb });
        }
        await saveMember(p, chat.id, u.id, member);
        return true;
      }
      member.fj = t + 30 * 60e3;                              // تا نیم ساعت دوباره چک نمیشه
    }
  }

  // ضد اسپم (پیام‌های پشت سر هم)
  if (!edited && cfg.flood.on && level < L.special) {
    const win = (cfg.flood.sec || 6) * 1000;
    member.fl = [...(member.fl || []).filter((x) => t - x < win), t];
    if (member.fl.length > (cfg.flood.n || 7)) {
      member.fl = [];
      try { await mute(p, chat.id, u.id, t + (cfg.flood.muteMins || 15) * 60e3); } catch (e) { /* */ }
      member.mute = { until: t + (cfg.flood.muteMins || 15) * 60e3, by: L.admin, at: t };
      await del(p, chat.id, msg.message_id);
      await send(p, chat.id, `🔇 ${mention(u)} به‌خاطر ارسال پیام‌های پشت سر هم برای ${fmtLeft((cfg.flood.muteMins || 15) * 60e3)} سکوت شد.`);
      return true;
    }
  }

  // قفل‌ها: هر قفل سطحی داره که از اون به بالا مجازن + لیست افراد مجاز
  const kinds = contentKinds(msg);
  for (const k of kinds) {
    const lock = cfg.locks[k];
    if (!lock) continue;
    if (level >= lock.lvl) continue;
    if ((cfg.allow[k] || []).includes(u.id)) continue;
    await del(p, chat.id, msg.message_id);
    return true;
  }

  // کلمات ممنوع: پاک + اخطار فوری؛ فیلتر: فقط پاک
  const text = msg.text || msg.caption || "";
  if (text && level < L.admin) {
    const bad = cfg.bad.length && wordHit(text, cfg.bad);
    if (bad) {
      await warn(p, chat, cfg, u, { reason: `استفاده از کلمه‌ی ممنوع («${bad}»)`, byLevel: L.admin, deleteIds: [msg.message_id], auto: true });
      return true;
    }
    if (cfg.filters.length && wordHit(text, cfg.filters)) {
      await del(p, chat.id, msg.message_id);
      return true;
    }
  }
  return false;
}

/** پاسخ خودکار (اگه پیام پاک نشده بود) */
export async function autoReply(p, msg, cfg) {
  const text = norm(msg.text || "");
  if (!text || !cfg.replies.length) return;
  const hit = cfg.replies.find((r) => (r.exact ? text === norm(r.t) : (" " + text + " ").includes(" " + norm(r.t) + " ")));
  if (hit) await send(p, msg.chat.id, esc(hit.r).replace(/\{name\}/g, mention(msg.from)),
                      { reply_parameters: { message_id: msg.message_id, allow_sending_without_reply: true } });
}

export function lockLine(cfg, k) {
  const l = cfg.locks[k];
  if (!l) return `🔓 ${LOCKS[k]}`;
  const who = l.lvl >= L.owner ? " (فقط مالک)" : l.lvl >= L.deputy ? " (ادمین‌ها هم نه)" : "";
  return `🔒 ${LOCKS[k]}${who}`;
}
export function glockText(cfg) {
  const s = groupLockState(cfg);
  if (!s.on) return cfg.night.on ? `🔓 باز (قفل خودکار ${esc(cfg.night.from)} تا ${esc(cfg.night.to)})` : "🔓 باز";
  if (s.night) return `🔒 قفل خودکار شبانه (تا ${esc(cfg.night.to)})`;
  return s.until === -1 ? "🔒 قفل (تا وقتی باز بشه)" : `🔒 قفل تا ${hhmm(s.until)} (${fmtLeft(s.until - now())} دیگه)`;
}
