// خوندن دستورها (فارسی/انگلیسی)، کاربر هدف (ریپلای، منشن، یوزرنیم، آیدی عددی) و مدت زمان.
import { norm, nextClock, userByName, LOCKS } from "./core.js";

/** «/ban@MyBot متن» یا «بن متن» → {cmd: اسم دستور، args: بقیه‌ی متن (با شکل اصلی)} یا null */
export function parseCommand(text, commands, botName) {
  let raw = String(text || "").trim();
  if (!raw) return null;
  raw = raw.replace(/^[/!]/, "");
  const first = raw.split(/\s+/)[0];
  if (first.includes("@")) {
    const [c, b] = first.split("@");
    if (botName && b && b.toLowerCase() !== botName.toLowerCase()) return null;
    raw = c + raw.slice(first.length);
  }
  const n = norm(raw);
  let best = null;
  for (const [cmd, def] of Object.entries(commands)) {
    for (const name of def.names) {
      const k = norm(name);
      if ((n === k || n.startsWith(k + " ")) && (!best || k.length > best.len)) best = { cmd, len: k.length, words: k.split(" ").length };
    }
  }
  if (!best) return null;
  const args = raw.split(/\s+/).slice(best.words).join(" ").trim();
  return { cmd: best.cmd, args };
}

/** کاربر هدف: ریپلای → منشن متنی → @یوزرنیم → آیدی عددی. خروجی {user:{id,first_name,...}|null, rest} */
export async function parseTarget(p, msg, args) {
  let rest = String(args || "").trim();
  const r = msg.reply_to_message;
  if (r && r.from && !r.sender_chat && !r.is_automatic_forward && r.from.id !== 777000) return { user: r.from, rest, replied: r };
  const ent = (msg.entities || []).find((e) => e.type === "text_mention" && e.user);
  if (ent) {
    const t = msg.text.substr(ent.offset, ent.length);
    return { user: ent.user, rest: rest.replace(t, "").trim() };
  }
  const um = rest.match(/(^|\s)@([A-Za-z0-9_]{4,32})\b/);
  if (um) {
    const known = await userByName(p, um[2]);
    rest = rest.replace(um[0], " ").trim();
    if (known) return { user: { id: known.id, first_name: known.n, username: um[2] }, rest };
    return { user: null, rest, unknown: "@" + um[2] };
  }
  const im = norm(rest).match(/(^|\s)(\d{5,15})(?=\s|$)/);
  if (im) {
    rest = rest.replace(/[\d۰-۹٠-٩]{5,15}/, "").trim();
    return { user: { id: Number(im[2]), first_name: im[2] }, rest };
  }
  return { user: null, rest };
}

const UNITS = [
  [/^(دقیقه|دقیقه‌ای|دق|min|mins|minute|minutes|m)$/, 60e3], [/^(ساعت|h|hr|hour|hours)$/, 3600e3],
  [/^(روز|d|day|days)$/, 86400e3], [/^(هفته|w|week|weeks)$/, 7 * 86400e3],
];
const CLOCKS = { "صبح": 8, "ظهر": 12, "عصر": 17, "شب": 21, "نیمه شب": 0, "morning": 8, "noon": 12, "evening": 17, "night": 21 };

/** «3 ساعت» / «30m» / «2 روز» / «تا صبح» / «تا 14:30» / «همیشه» → {until (ms، 0=دائمی)، rest} یا {until:null} */
export function parseDuration(text, from = Date.now()) {
  const t = norm(text);
  if (!t) return { until: null, rest: "" };
  let m = t.match(/(^|\s)(همیشه|دائم|دائمی|forever|permanent)(\s|$)/);
  if (m) return { until: 0, rest: t.replace(m[0], " ").trim(), label: "دائمی" };
  m = t.match(/(^|\s)(تا|until|till)\s+(\d{1,2})(?::(\d{2}))?(\s|$)/);
  if (m) return { until: nextClock(Number(m[3]) % 24, Number(m[4] || 0), from), rest: t.replace(m[0], " ").trim() };
  for (const [w, h] of Object.entries(CLOCKS)) {
    const re = new RegExp(`(^|\\s)(تا|until|till)\\s+${w}(\\s|$)`);
    m = t.match(re);
    if (m) return { until: nextClock(h, 0, from), rest: t.replace(m[0], " ").trim() };
  }
  m = t.match(/(^|\s)(\d+(?:\.\d+)?)\s*([a-zآ-ی‌]+)(\s|$)/);
  if (m) {
    const unit = UNITS.find(([re]) => re.test(m[3]));
    if (unit) return { until: from + Number(m[2]) * unit[1], rest: t.replace(m[0], " ").trim() };
  }
  return { until: null, rest: t };
}

/** «لینک» / «link» / «فیلم سلفی» → کلید قفل */
const LOCK_ALIASES = {
  link: ["لینک", "link", "links", "url"], mention: ["یوزرنیم", "تگ", "منشن", "username", "mention"],
  hashtag: ["هشتگ", "hashtag"], forward: ["فوروارد", "forward", "fwd"], sticker: ["استیکر", "sticker", "stickers"],
  gif: ["گیف", "gif", "animation"], photo: ["عکس", "photo", "image"], video: ["فیلم", "ویدیو", "video"],
  videonote: ["فیلم سلفی", "ویدیو مسیج", "videonote", "video note"], voice: ["ویس", "صدا", "voice"],
  audio: ["آهنگ", "موزیک", "audio", "music"], file: ["فایل", "file", "document"], contact: ["مخاطب", "شماره", "contact"],
  location: ["مکان", "لوکیشن", "location"], poll: ["نظرسنجی", "poll"], dice: ["تاس", "dice"], game: ["بازی", "game"],
  inline: ["اینلاین", "inline"], button: ["دکمه", "دکمه شیشه ای", "button"], text: ["متن", "text"],
  english: ["انگلیسی", "english"], emoji: ["ایموجی پریمیوم", "ایموجی", "emoji"], bot: ["ربات", "bot", "bots"],
  service: ["پیام ورود", "ورود", "سرویس", "service", "join"],
};
export function parseLock(text) {
  const t = norm(text);
  let best = null;
  for (const [k, names] of Object.entries(LOCK_ALIASES)) {
    for (const n of names) {
      const nn = norm(n);
      if ((t === nn || t.startsWith(nn + " ")) && (!best || nn.length > best.len)) best = { key: k, len: nn.length };
    }
  }
  if (!best) return null;
  return { key: best.key, name: LOCKS[best.key], rest: t.slice(best.len).trim() };
}
