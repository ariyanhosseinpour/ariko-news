// دکمه‌های «✅ انتشار / ❌ رد» زیر پیش‌نمایش خبر.
import { platform } from "../lib/platform.js";
import { isAdmin, publish, reject } from "../lib/news.js";

export default async function (q, ctx) {
  const p = platform();
  const [kind, action, id] = String(q.data || "").split(":");
  if (kind !== "nw") return;
  if (!(await isAdmin(p, q.from.id))) {
    return p.api("answerCallbackQuery", { callback_query_id: q.id, text: "دسترسی ندارید.", show_alert: true });
  }
  const result = action === "ok" ? await publish(p, id) : await reject(p, id);
  await p.api("answerCallbackQuery", { callback_query_id: q.id, text: result });
  try {                                                     // دکمه‌ها برداشته میشن که دوبار زده نشه
    await p.api("editMessageReplyMarkup", { chat_id: q.message.chat.id, message_id: q.message.message_id,
                                            reply_markup: { inline_keyboard: [[{ text: result, callback_data: "nw:x:0" }]] } });
  } catch (e) { /* */ }
}
