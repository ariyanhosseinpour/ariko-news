// متن آمار یه گروه (برای دستور «آمار» و دکمه‌ی آمار پنل)
import { esc, faNum, mentionId, now, dayKey } from "./core.js";

export async function statsText(p, chatId, title) {
  const days = [];
  for (let i = 0; i < 7; i++) days.push(dayKey(now() - i * 86400e3));
  const rows = await Promise.all(days.map((d) => p.kv.get(`d:${chatId}:${d}`)));
  const today = rows[0] || { t: 0, u: {}, j: 0, l: 0 };
  const top = Object.entries(today.u || {}).sort((a, b) => b[1][0] - a[1][0]).slice(0, 10);
  let count = "";
  try { count = faNum(await p.api("getChatMemberCount", { chat_id: chatId })); } catch (e) { /* */ }
  const week = rows.reduce((s, r) => s + ((r && r.t) || 0), 0);
  return `📊 <b>آمار ${esc(title || "گروه")}</b>\n`
    + (count ? `👥 اعضا: ${count}\n` : "")
    + `💬 پیام‌های امروز: ${faNum(today.t || 0)}\n📅 پیام‌های ۷ روز اخیر: ${faNum(week)}\n`
    + `➕ ورود امروز: ${faNum(today.j || 0)} • ➖ خروج: ${faNum(today.l || 0)}\n`
    + (top.length ? `\n🏆 <b>فعال‌ترین‌های امروز</b>\n` + top.map(([id, [n, name]], i) => `${faNum(i + 1)}. ${mentionId(id, name)} — ${faNum(n)} پیام`).join("\n") : "");
}
