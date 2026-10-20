// دکمه‌ها: پنل مدیریت (توی گروه یا خصوصی ربات؛ فقط ادمین‌ها و بالاتر)، لیست گروه‌ها و «✅ عضو شدم» عضویت اجباری.
import { platform } from "../lib/platform.js";
import { L, getCfg, getDeputy, levelOf } from "../lib/core.js";
import { panelView, panelAction } from "../lib/panel.js";
import { fjCheck, groupsMenu } from "../lib/flow.js";

export default async function (q, ctx) {
  const p = platform();
  const answer = (text = "", alert = false) => p.api("answerCallbackQuery", { callback_query_id: q.id, text, show_alert: alert }).catch(() => {});
  const parts = String(q.data || "").split(":");
  if (!q.message) return answer();
  const here = q.message.chat.id, priv = q.message.chat.type === "private";
  const edit = (v) => p.api("editMessageText", { chat_id: here, message_id: q.message.message_id, text: v.text, parse_mode: "HTML",
                                                 disable_web_page_preview: true, reply_markup: v.kb }).catch(() => {});

  if (parts[0] === "fj") {
    if (Number(parts[1]) !== q.from.id) return answer("این دکمه مال یه نفر دیگه‌ست.", true);
    return (await fjCheck(p, q, q.from.id)) ? answer("✅ ممنون! حالا می‌تونی پیام بدی.") : answer("هنوز عضو همه‌ی کانال‌ها نشدی.", true);
  }
  const deputy = await getDeputy(p);
  if (parts[0] === "gs" && priv) {                         // خصوصی: لیست گروه‌ها یا باز کردن پنل یه گروه
    if (parts[1] === "list") { await edit(await groupsMenu(p, q.from.id, deputy)); return answer(); }
    parts.splice(0, 2, "pn", parts[1], "pg", "main");
  }
  if (parts[0] !== "pn") return answer();
  const chatId = Number(parts[1]), op = parts[2], arg = parts.slice(3).join(":");
  if (!priv && chatId !== here) return answer();
  const cfg = await getCfg(p, chatId);
  const level = await levelOf(p, chatId, cfg, q.from.id, deputy);
  if (level < L.admin) return answer("⛔️ پنل فقط برای ادمین‌هاست.", true);
  if (op === "x") {
    await p.api("deleteMessage", { chat_id: here, message_id: q.message.message_id }).catch(() => {});
    return answer();
  }
  const r = await panelAction(p, cfg, chatId, op, arg, level);
  if (r.alert) return answer(r.alert, true);
  if (r.page) await edit(await panelView(cfg, chatId, r.page, { priv, p, level, deputy: await getDeputy(p) }));
  if (r.wait) {
    if (!priv) return answer("✏️ ویرایش متن‌ها فقط توی خصوصی رباته.", true);
    await p.kv.set("wait:" + q.from.id, { chat: chatId, field: r.wait, at: Date.now() });
  }
  if (r.send) {                                           // همیشه به خصوصی همون شخص (کلمات ممنوع توی گروه دیده نشن)
    const sent = await p.api("sendMessage", { chat_id: q.from.id, text: r.send, parse_mode: "HTML", disable_web_page_preview: true }).catch(() => null);
    if (!sent) return answer("اول ربات رو توی خصوصی استارت کن.", true);
    if (!priv) return answer("📩 توی خصوصی ربات فرستادم.");
  }
  if (r.announce) await p.api("sendMessage", { chat_id: chatId, text: r.announce }).catch(() => {});
  return answer(r.toast || "");
}
