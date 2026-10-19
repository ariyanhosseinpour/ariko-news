// مسیر هر پیام گروه: فعال بودن، نقش فرستنده، دستورها، ورود اعضا، قوانین زیر پست کانال، نگهبان و آمار.
import { L, OWNERS, esc, mention, nameOf, now, dayKey, fill, getCfg, saveCfg, getMember, saveMember, getDeputy, levelOf,
         rememberUser } from "./core.js";
import { parseCommand } from "./parse.js";
import { COMMANDS, HELP } from "./commands.js";
import { guard, autoReply } from "./guard.js";
import { del, kick } from "./actions.js";

export async function botInfo(p) {
  let me = await p.kv.get("me");
  if (!me || !me.id) {
    const r = await p.api("getMe", {});
    me = { id: r.id, username: r.username };
    await p.kv.set("me", me);
  }
  return me;
}

const isGroup = (chat) => chat && (chat.type === "group" || chat.type === "supergroup");

function makeCtx(p, msg, cfg, level, deputy, me, args) {
  return {
    p, msg, cfg, level, deputy, args, chat: msg.chat, from: msg.from, botId: me.id,
    reply: (text, extra = {}) => p.api("sendMessage", { chat_id: msg.chat.id, text, parse_mode: "HTML", disable_web_page_preview: true,
      reply_parameters: { message_id: msg.message_id, allow_sending_without_reply: true }, ...extra }).catch(() => null),
  };
}

async function countStat(p, chatId, field, u) {
  const key = `d:${chatId}:${dayKey()}`;
  const d = (await p.kv.get(key)) || { t: 0, u: {}, j: 0, l: 0 };
  if (field === "msg") {
    d.t = (d.t || 0) + 1;
    const cur = (d.u || {})[u.id] || [0, ""];
    d.u = { ...(d.u || {}), [u.id]: [cur[0] + 1, nameOf(u)] };
  } else d[field] = (d[field] || 0) + 1;
  await p.kv.set(key, d);
}

async function onJoin(p, msg, cfg, me) {
  const adder = msg.from;
  const adderLevel = await levelOf(p, msg.chat.id, cfg, adder.id);
  const humans = [];
  for (const u of msg.new_chat_members) {
    if (u.id === me.id) continue;
    if (u.is_bot) {
      if (cfg.locks.bot && adderLevel < cfg.locks.bot.lvl) {                 // ربات‌هایی که غیرادمین‌ها اضافه کنن
        try { await kick(p, msg.chat.id, u.id); } catch (e) { /* */ }
      }
      continue;
    }
    humans.push(u);
    await rememberUser(p, u);
    await countStat(p, msg.chat.id, "j");
  }
  if (cfg.locks.service) await del(p, msg.chat.id, msg.message_id);
  if (humans.length && cfg.welcome.on && cfg.welcome.text) {
    if (cfg.welcome.last) await del(p, msg.chat.id, cfg.welcome.last);     // خوشامد قبلی پاک میشه که گروه شلوغ نشه
    const sent = await p.api("sendMessage", { chat_id: msg.chat.id, parse_mode: "HTML", disable_web_page_preview: true,
      text: fill(esc(cfg.welcome.text), { name: humans.map(mention).join("، "), group: esc(msg.chat.title || "") }) }).catch(() => null);
    if (sent) { cfg.welcome.last = sent.message_id; await saveCfg(p, msg.chat.id, cfg); }
  }
}

export async function groupMessage(p, msg) {
  const chat = msg.chat, u = msg.from;
  if (!isGroup(chat) || !u) return;
  const [cfg, deputy, me] = await Promise.all([getCfg(p, chat.id), getDeputy(p), botInfo(p)]);
  // ادمین ناشناس (پیام به اسم خود گروه) = ادمین
  const anon = msg.sender_chat && msg.sender_chat.id === chat.id;
  const level = anon ? L.admin : await levelOf(p, chat.id, cfg, u.id, deputy);
  const parsed = msg.text || msg.caption ? parseCommand(msg.text || msg.caption, COMMANDS, me.username) : null;

  if (!cfg.active) {
    if (parsed && parsed.cmd === "activate" && level >= L.deputy) await COMMANDS.activate.run(makeCtx(p, msg, cfg, level, deputy, me, parsed.args));
    return;
  }

  // پست کانال توی گروه بحث (صفحه‌ی نظرات): قوانین به‌عنوان اولین پیام
  if (msg.is_automatic_forward) {
    if (cfg.rulesOnPost && cfg.rules) {
      await p.api("sendMessage", { chat_id: chat.id, parse_mode: "HTML", disable_web_page_preview: true,
        text: `📜 <b>قوانین گفت‌وگو</b>\n\n${esc(cfg.rules)}`,
        reply_parameters: { message_id: msg.message_id, allow_sending_without_reply: true } }).catch(() => null);
    }
    return;
  }
  if (msg.new_chat_members) return onJoin(p, msg, cfg, me);
  if (msg.left_chat_member) {
    if (!msg.left_chat_member.is_bot) await countStat(p, chat.id, "l");
    if (cfg.locks.service) await del(p, chat.id, msg.message_id);
    return;
  }
  if (msg.sender_chat && !anon) {                          // پیام به اسم یه کانال دیگه: مثل کاربر عادی، فقط قفل‌ها
    await guard(p, msg, cfg, L.member, {});
    return;
  }

  const member = await getMember(p, chat.id, u.id);
  member.c = (member.c || 0) + 1; member.n = nameOf(u); member.u = u.username || "";
  await Promise.all([rememberUser(p, u), countStat(p, chat.id, "msg", u)]);

  if (parsed) {
    const def = COMMANDS[parsed.cmd];
    if (def && level >= def.min) {
      await saveMember(p, chat.id, u.id, member);
      await def.run(makeCtx(p, msg, cfg, level, deputy, me, parsed.args));
      return;
    }
  }
  const handled = await guard(p, msg, cfg, level, member);
  await saveMember(p, chat.id, u.id, member);
  if (!handled) await autoReply(p, msg, cfg);
}

export async function editedMessage(p, msg) {
  if (!isGroup(msg.chat) || !msg.from) return;
  const [cfg, deputy] = await Promise.all([getCfg(p, msg.chat.id), getDeputy(p)]);
  if (!cfg.active) return;
  const level = msg.sender_chat && msg.sender_chat.id === msg.chat.id ? L.admin : await levelOf(p, msg.chat.id, cfg, msg.from.id, deputy);
  if (level >= L.admin) return;
  await guard(p, msg, cfg, level, {}, { edited: true });   // لینک/کلمه‌ای که بعداً با ویرایش اضافه شده
}

export async function privateMessage(p, msg) {
  const u = msg.from;
  if (!u) return;
  await rememberUser(p, u);
  const deputy = await getDeputy(p);
  const boss = OWNERS.includes(u.id) || (deputy && deputy.id === u.id);
  const t = (msg.text || "").trim();
  const send = (text, extra = {}) => p.api("sendMessage", { chat_id: u.id, text, parse_mode: "HTML", disable_web_page_preview: true, ...extra });
  if (/^\/?(help|راهنما|دستورات)/i.test(t)) return send(HELP);
  if (boss) {
    const groups = await p.kv.list("grp:");
    return send(`👋 سلام ${mention(u)}، ${OWNERS.includes(u.id) ? "مالک" : "جانشین مالک"} عزیز.\n\n`
      + `📋 گروه‌های فعال (${groups.length}):\n${groups.map((g) => `• ${esc(g.value.t)} <code>${g.key.slice(4)}</code>`).join("\n") || "—"}\n\n`
      + "برای فعال کردن یه گروه: ربات رو به گروه اضافه و ادمین کن و توی گروه بنویس «فعال».\n"
      + "گزارش‌های کاربرها اینجا برات میاد. «راهنما» = همه‌ی دستورها.");
  }
  return send("👋 سلام! من ربات مدیریت گروه‌های آریکوام.\nتوی گروه «پنل من» رو بزن تا وضعیتت رو ببینی، یا «راهنما» برای دستورها.");
}

export async function botAdded(p, upd) {
  const chat = upd.chat, by = upd.from, st = upd.new_chat_member && upd.new_chat_member.status;
  if (!isGroup(chat) || !["member", "administrator"].includes(st)) return;
  const cfg = await getCfg(p, chat.id);
  const deputy = await getDeputy(p);
  const boss = OWNERS.includes(by.id) || (deputy && deputy.id === by.id);
  if (boss && !cfg.active) {
    cfg.active = true; cfg.title = chat.title || "";
    await saveCfg(p, chat.id, cfg);
    await p.kv.set("grp:" + chat.id, { t: chat.title || "", at: now() });
  }
  if (!(upd.old_chat_member && ["member", "administrator"].includes(upd.old_chat_member.status))) {
    await p.api("sendMessage", { chat_id: chat.id, parse_mode: "HTML", text: cfg.active
      ? "✅ ربات فعاله. منو ادمین کن (پاک کردن پیام، بن و محدود کردن، سنجاق) و «پنل» یا «راهنما» رو بزن."
      : "👋 سلام! برای فعال شدن، مالک یا جانشینش باید توی گروه بنویسه «فعال»." }).catch(() => null);
    for (const id of OWNERS) {
      await p.api("sendMessage", { chat_id: id, parse_mode: "HTML",
        text: `➕ ربات به گروه «${esc(chat.title || "")}» (<code>${chat.id}</code>) اضافه شد، توسط ${mention(by)}.\n${cfg.active ? "✅ فعال شد." : "⏸ هنوز فعال نیست (توی گروه «فعال» بزن)."}` }).catch(() => null);
    }
  }
}

export async function fjCheck(p, q, uid) {
  const chatId = q.message.chat.id;
  const cfg = await getCfg(p, chatId);
  const missing = [];
  for (const ch of cfg.force.chans) {
    try {
      const st = await p.api("getChatMember", { chat_id: ch, user_id: uid });
      if (!["creator", "administrator", "member"].includes(st.status) && !(st.status === "restricted" && st.is_member)) missing.push(ch);
    } catch (e) { /* */ }
  }
  if (missing.length) return false;
  const m = await getMember(p, chatId, uid);
  m.fj = now() + 30 * 60e3;
  await saveMember(p, chatId, uid, m);
  await del(p, chatId, q.message.message_id);
  return true;
}
