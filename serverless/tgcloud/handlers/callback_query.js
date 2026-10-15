// دکمه‌های شیشه‌ای: «✅ انتشار / ❌ رد» زیر خبر، و دکمه‌های منو (منبع‌ها، هوش مصنوعی، ادمین‌ها، …).
import { platform } from "../lib/platform.js";
import { isAdmin, publish, reject, feeds, setCfg, cfg, admins, rankJob, RANK_SOURCES } from "../lib/news.js";
import { escapeHtml, hashKey } from "../lib/core.js";
import { importanceView, feedCard, aiView, adminsView, setWait, cancelKeyboard, WAIT_PROMPT } from "../lib/menu.js";

export default async function (q, ctx) {
  const p = platform();
  const [kind, action, ...restParts] = String(q.data || "").split(":");
  const id = restParts.join(":");
  const answer = (text = "", alert = false) =>
    p.api("answerCallbackQuery", { callback_query_id: q.id, text, show_alert: alert }).catch(() => {});
  if (!(await isAdmin(p, q.from.id))) return answer("دسترسی ندارید.", true);
  const chat = q.message && q.message.chat.id;
  const mid = q.message && q.message.message_id;
  const edit = (v) => p.api("editMessageText", { chat_id: chat, message_id: mid, text: v.text, parse_mode: "HTML",
                                                 disable_web_page_preview: true, reply_markup: v.reply_markup }).catch(() => {});
  const ask = async (waitKind) => {
    await setWait(p, q.from.id, waitKind);
    await answer();
    return p.api("sendMessage", { chat_id: chat, text: WAIT_PROMPT[waitKind], parse_mode: "HTML",
                                  reply_markup: cancelKeyboard() });
  };

  switch (kind) {
    case "nw": {                                             // انتشار / رد خبر
      if (action === "x") return answer();
      const result = action === "ok" ? await publish(p, id) : await reject(p, id);
      await answer(result);
      try {                                                   // دکمه‌ها برداشته میشن که دوبار زده نشه
        await p.api("editMessageReplyMarkup", { chat_id: chat, message_id: mid,
          reply_markup: { inline_keyboard: [[{ text: result, callback_data: "nw:x:0" }]] } });
      } catch (e) { /* */ }
      return;
    }
    case "fd": {                                             // کارت منبع‌ها
      if (action === "add") return ask("feed");
      const list = await feeds(p);
      const i = list.findIndex((x) => hashKey(x.url) === id);
      if (i < 0) {
        await answer("این منبع دیگه نیست.");
        return p.api("editMessageReplyMarkup", { chat_id: chat, message_id: mid, reply_markup: { inline_keyboard: [] } }).catch(() => {});
      }
      const f = list[i];
      if (action === "ask") {
        await answer();
        return edit({ text: `🗑 منبع «<b>${escapeHtml(f.name)}</b>» حذف بشه؟\n${escapeHtml(f.url)}`,
                      reply_markup: { inline_keyboard: [[{ text: "✅ آره، حذف کن", callback_data: `fd:del:${id}` },
                                                         { text: "↩️ نه", callback_data: `fd:back:${id}` }]] } });
      }
      if (action === "del") {
        list.splice(i, 1);
        await setCfg(p, "feeds", list);
        await answer("🗑 حذف شد");
        return edit({ text: `🗑 منبع «${escapeHtml(f.name)}» حذف شد.`, reply_markup: { inline_keyboard: [] } });
      }
      if (action === "tg") {
        f.active = f.active === false;
        await setCfg(p, "feeds", list);
        await answer(f.active ? "▶️ فعال شد" : "⏸ غیرفعال شد");
      } else {
        await answer();
      }
      return edit(await feedCard(p, f, i));                   // back / toggle → کارت دوباره
    }
    case "ai": {                                             // هوش مصنوعی
      if (action === "key") return ask("key");
      if (action === "m") {
        await setCfg(p, "model", id);
        await answer(`✅ مدل: ${id || "پیش‌فرض"}`);
        return edit(await aiView(p));
      }
      return answer();
    }
    case "ad": {                                             // ادمین‌ها (فقط صاحب بات)
      if (Number(q.from.id) !== (await admins(p))[0]) return answer("فقط صاحب بات.", true);
      if (action === "add") return ask("admin");
      if (action === "del") {
        const list = ((await cfg(p, "admins", [])) || []).filter((x) => String(x) !== id);
        await setCfg(p, "admins", list);
        await answer("🗑 حذف شد");
        return edit(await adminsView(p));
      }
      return answer();
    }
    case "rk": {                                             // تست رنکینگ هفتگی
      if (action === "close") {
        await answer("بسته شد");
        return p.api("deleteMessage", { chat_id: chat, message_id: mid }).catch(() => {});
      }
      if (!RANK_SOURCES[action]) return answer();
      const online = await rankJob(p, action, chat);
      await answer(online ? "⏳ داره ساخته میشه…" : "🖥 سیستم رو روشن کن");
      return edit({ text: `🧪 ${RANK_SOURCES[action]}\n\n` + (online
        ? "⏳ کامپیوتر داره کارت رو می‌سازه؛ تا یکی دو دقیقه دیگه برات میاد."
        : "🖥 <b>سیستم رو روشن کن</b> (serverless_agent)؛ به محض روشن شدن کارت رو می‌سازه و برات می‌فرسته."),
        reply_markup: { inline_keyboard: [] } });
    }
    case "im": {                                             // فیلتر اهمیت خبر
      const v = Number(action);
      if (!(v >= 0 && v <= 100)) return answer();
      await setCfg(p, "min_importance", v);
      await answer("✅ ذخیره شد");
      return edit(await importanceView(p));
    }
    case "ch": return action === "set" ? ask("channel") : answer();
    case "ft": return action === "set" ? ask("footer") : answer();
  }
  return answer();
}
