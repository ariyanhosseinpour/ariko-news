// مجازات‌ها: اخطار (با بن/سکوت/اخراج خودکار سر حد اخطار)، بن، سکوت، اخراج — پیام کاربر پاک و دلیل با اسپویلر نوشته میشه.
import { esc, mention, fill, faNum, fmtLeft, getMember, saveMember, now, L } from "./core.js";

const MUTED = { can_send_messages: false, can_send_audios: false, can_send_documents: false, can_send_photos: false,
  can_send_videos: false, can_send_video_notes: false, can_send_voice_notes: false, can_send_polls: false,
  can_send_other_messages: false, can_add_web_page_previews: false };
const FREE = Object.fromEntries(Object.keys(MUTED).map((k) => [k, true]));
const ACTION_FA = { ban: "بن", mute: "سکوت", kick: "اخراج" };

export const spoiler = (t) => (t ? `<tg-spoiler>${esc(t)}</tg-spoiler>` : "<i>بدون دلیل</i>");
const send = (p, chatId, text, extra = {}) =>
  p.api("sendMessage", { chat_id: chatId, text, parse_mode: "HTML", disable_web_page_preview: true, ...extra }).catch(() => null);
export const del = (p, chatId, ids) => {
  const list = [].concat(ids).filter(Boolean);
  if (!list.length) return Promise.resolve();
  return list.length === 1 ? p.api("deleteMessage", { chat_id: chatId, message_id: list[0] }).catch(() => {})
    : p.api("deleteMessages", { chat_id: chatId, message_ids: list }).catch(() => {});
};

export async function mute(p, chatId, uid, until) {
  // تلگرام: کمتر از ۳۰ ثانیه یا بیشتر از ۳۶۶ روز = دائمی
  await p.api("restrictChatMember", { chat_id: chatId, user_id: uid, permissions: MUTED, use_independent_chat_permissions: true,
                                      until_date: until ? Math.floor(until / 1000) : 0 });
}
export const unmute = (p, chatId, uid) =>
  p.api("restrictChatMember", { chat_id: chatId, user_id: uid, permissions: FREE, use_independent_chat_permissions: true });
export const ban = (p, chatId, uid, until) =>
  p.api("banChatMember", { chat_id: chatId, user_id: uid, until_date: until ? Math.floor(until / 1000) : 0, revoke_messages: false });
export const unban = (p, chatId, uid) => p.api("unbanChatMember", { chat_id: chatId, user_id: uid, only_if_banned: true });
export async function kick(p, chatId, uid) {
  await p.api("banChatMember", { chat_id: chatId, user_id: uid });
  await p.api("unbanChatMember", { chat_id: chatId, user_id: uid, only_if_banned: true });
}

/** مجازات مستقیم (بن/سکوت/اخراج) + ثبت اینکه کی (با چه سطحی) زده؛ سطح پایین‌تر نمی‌تونه برش داره */
export async function punish(p, chat, cfg, target, kind, { until = 0, reason = "", byLevel = L.admin, byUser, deleteIds = [] } = {}) {
  const m = await getMember(p, chat.id, target.id);
  if (kind === "ban") await ban(p, chat.id, target.id, until);
  else if (kind === "mute") await mute(p, chat.id, target.id, until);
  else if (kind === "kick") await kick(p, chat.id, target.id);
  if (kind !== "kick") m[kind] = { until: until || 0, by: byLevel, at: now() };
  await saveMember(p, chat.id, target.id, m);
  await del(p, chat.id, deleteIds);
  const dur = kind === "kick" ? "" : until ? ` برای ${fmtLeft(until - now())}` : " (دائمی)";
  const icon = { ban: "⛔️", mute: "🔇", kick: "👢" }[kind];
  await send(p, chat.id, `${icon} ${mention(target)} ${ACTION_FA[kind]} شد${dur}.\nدلیل: ${spoiler(reason)}`
    + (byUser ? `\nتوسط: ${mention(byUser)}` : ""));
}

/** برداشتن مجازات؛ اگه مجازات رو سطح بالاتری زده باشه، اجازه نیست */
export async function lift(p, chat, target, kind, byLevel) {
  const m = await getMember(p, chat.id, target.id);
  const rec = m[kind];
  if (rec && rec.by > byLevel) return { ok: false, by: rec.by };
  if (kind === "ban") await unban(p, chat.id, target.id);
  else await unmute(p, chat.id, target.id);
  delete m[kind];
  await saveMember(p, chat.id, target.id, m);
  return { ok: true };
}

/** اخطار: شمارش، پیام قابل تنظیم با دلیل اسپویلر، و سر حد اخطار مجازات خودکار */
export async function warn(p, chat, cfg, target, { reason = "", byLevel = L.admin, byUser = null, deleteIds = [], auto = false } = {}) {
  const m = await getMember(p, chat.id, target.id);
  m.w = (m.w || 0) + 1;
  m.wr = [...(m.wr || []), { r: reason, by: byLevel, at: now() }].slice(-20);
  m.wby = Math.max(m.wby || 0, byLevel);
  await saveMember(p, chat.id, target.id, m);
  await del(p, chat.id, deleteIds);
  const max = cfg.warn.max || 3;
  const vals = { name: mention(target), count: faNum(m.w), max: faNum(max), reason: spoiler(reason), group: esc(chat.title || "") };
  if (m.w < max) {
    let muted = "";
    const each = cfg.warn.eachMins ?? 60;
    if (each > 0 && m.w >= 2) {                           // از اخطار دوم به بعد = سکوت موقت (مثلاً ۱ ساعت)؛ اخطار اول فقط تذکره
      const until = now() + each * 60e3;
      try {
        await mute(p, chat.id, target.id, until);
        if (!m.mute || (m.mute.until && m.mute.until < until)) m.mute = { until, by: byLevel, at: now() };
        await saveMember(p, chat.id, target.id, m);
        muted = `\n🔇 تا ${fmtLeft(each * 60e3)} سکوت شد.`;
      } catch (e) { /* ربات دسترسی محدود کردن نداره */ }
    }
    await send(p, chat.id, fill(cfg.warn.text, vals) + muted + (auto ? "\n<i>(اخطار خودکار)</i>" : byUser ? `\nتوسط: ${mention(byUser)}` : ""));
    return { count: m.w, punished: false };
  }
  const action = cfg.warn.action || "ban";
  const until = action === "mute" ? now() + (cfg.warn.muteMins || 1440) * 60e3 : 0;
  try {
    if (action === "ban") await ban(p, chat.id, target.id, 0);
    else if (action === "mute") await mute(p, chat.id, target.id, until);
    else await kick(p, chat.id, target.id);
  } catch (e) { /* ربات دسترسی نداره؛ پیامش رو می‌فرستیم */ }
  m.w = 0;                                               // دور بعد از صفر
  if (action !== "kick") m[action] = { until, by: Math.max(byLevel, m.wby || 0), at: now() };
  m.wby = 0;
  await saveMember(p, chat.id, target.id, m);
  await send(p, chat.id, fill(cfg.warn.punish, { ...vals, action: ACTION_FA[action] + (until ? ` (${fmtLeft(until - now())})` : "") }));
  return { count: max, punished: true };
}
