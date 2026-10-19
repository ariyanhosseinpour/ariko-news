// دکمه‌ها: پنل مدیریت (فقط ادمین‌ها و بالاتر) و «✅ عضو شدم» عضویت اجباری.
import { platform } from "../lib/platform.js";
import { L, getCfg, getDeputy, levelOf } from "../lib/core.js";
import { panelView, panelAction } from "../lib/panel.js";
import { fjCheck } from "../lib/flow.js";

export default async function (q, ctx) {
  const p = platform();
  const answer = (text = "", alert = false) => p.api("answerCallbackQuery", { callback_query_id: q.id, text, show_alert: alert }).catch(() => {});
  const parts = String(q.data || "").split(":");
  if (!q.message) return answer();

  if (parts[0] === "fj") {
    if (Number(parts[1]) !== q.from.id) return answer("این دکمه مال یه نفر دیگه‌ست.", true);
    return (await fjCheck(p, q, q.from.id)) ? answer("✅ ممنون! حالا می‌تونی پیام بدی.") : answer("هنوز عضو همه‌ی کانال‌ها نشدی.", true);
  }
  if (parts[0] !== "pn") return answer();
  const chatId = Number(parts[1]), op = parts[2], arg = parts.slice(3).join(":");
  if (chatId !== q.message.chat.id) return answer();
  const cfg = await getCfg(p, chatId);
  const level = await levelOf(p, chatId, cfg, q.from.id, await getDeputy(p));
  if (level < L.admin) return answer("⛔️ پنل فقط برای ادمین‌هاست.", true);
  if (op === "x") {
    await p.api("deleteMessage", { chat_id: chatId, message_id: q.message.message_id }).catch(() => {});
    return answer();
  }
  const r = await panelAction(p, cfg, chatId, op, arg, level);
  if (r.alert) return answer(r.alert, true);
  if (r.page) {
    const v = panelView(cfg, chatId, r.page);
    await p.api("editMessageText", { chat_id: chatId, message_id: q.message.message_id, text: v.text, parse_mode: "HTML",
                                     reply_markup: v.kb }).catch(() => {});
  }
  if (r.announce) await p.api("sendMessage", { chat_id: chatId, text: r.announce }).catch(() => {});
  return answer(r.toast || "");
}
