// پیام‌ها: فقط دستورهای ادمین (ورودی handler همون Message هست).
import { platform } from "../lib/platform.js";
import { isAdmin, cfg, setCfg, feeds, collect, admins } from "../lib/news.js";
import { escapeHtml } from "../lib/core.js";

export default async function (msg, ctx) {
  const p = platform();
  const uid = msg.from && msg.from.id;
  const text = (msg.text || "").trim();
  if (!uid || !text.startsWith("/") || !(await isAdmin(p, uid))) return;
  const [cmd, ...rest] = text.split(/\s+/);
  const arg = rest.join(" ").trim();
  const reply = (t) => p.api("sendMessage", { chat_id: msg.chat.id, text: t, parse_mode: "HTML", disable_web_page_preview: true });

  switch (cmd.split("@")[0]) {
    case "/start":
    case "/status": {
      const last = await cfg(p, "last_collect", null);
      const seen = await cfg(p, "agent_seen", 0);
      return reply(
        "📰 <b>بات خبری آریکو (Serverless)</b>\n\n" +
        `🔑 Gemini: ${(await cfg(p, "gemini_key", "")) ? "✅" : "❌ (/setgemini کلید)"}\n` +
        `📢 کانال: ${escapeHtml(await cfg(p, "channel", "") || "❌ (/setchannel @کانال)")}\n` +
        `🗞 منبع‌ها: ${(await feeds(p)).length} تا (/feeds)\n` +
        `🖥 کامپیوتر: ${Date.now() - seen < 120000 ? "✅ آنلاین" : "⚪️ خاموش"}\n` +
        (last ? `⏱ آخرین چک: ${Math.round((Date.now() - last.at) / 60000)} دقیقه پیش — ${last.added} خبر جدید` : "⏱ هنوز چک نشده") +
        "\n\n/check — همین الان خبرها رو چک کن\n/setgemini کلید — کلید Gemini\n/setmodel مدل\n/setchannel @کانال\n" +
        "/footer متن — امضای پایین پست\n/feeds — لیست منبع‌ها\n/addfeed لینک‌RSS اسم\n/delfeed شماره\n" +
        "/addadmin آیدی‌عددی");
    }
    case "/setgemini":
      if (!arg) return reply("کلید رو بعد از دستور بنویس: /setgemini AIza...");
      await setCfg(p, "gemini_key", arg);
      try { await p.api("deleteMessage", { chat_id: msg.chat.id, message_id: msg.message_id }); } catch (e) { /* */ }
      return reply("✅ کلید Gemini ذخیره شد (پیامت پاک شد).");
    case "/setmodel":
      await setCfg(p, "model", arg);
      return reply(`✅ مدل: ${escapeHtml(arg || "پیش‌فرض")}`);
    case "/setchannel":
      if (!arg) return reply("مثال: /setchannel @Ariko_News");
      await setCfg(p, "channel", arg);
      return reply(`✅ کانال: ${escapeHtml(arg)}\n(بات باید ادمین کانال باشه)`);
    case "/footer":
      await setCfg(p, "footer", arg);
      return reply("✅ امضای پایین پست عوض شد.");
    case "/feeds": {
      const list = await feeds(p);
      return reply("🗞 منبع‌ها:\n" + list.map((f, i) => `${i + 1}. ${escapeHtml(f.name)}\n   ${escapeHtml(f.url)}`).join("\n"));
    }
    case "/addfeed": {
      const [url, ...name] = rest;
      if (!/^https?:\/\//.test(url || "")) return reply("مثال: /addfeed https://site.com/rss.xml اسم منبع");
      const list = await feeds(p);
      list.push({ name: name.join(" ") || url, url });
      await setCfg(p, "feeds", list);
      return reply("✅ اضافه شد.");
    }
    case "/delfeed": {
      const list = await feeds(p);
      const i = parseInt(arg, 10) - 1;
      if (!(i >= 0 && i < list.length)) return reply("شماره‌ی منبع رو از /feeds بردار.");
      const [gone] = list.splice(i, 1);
      await setCfg(p, "feeds", list);
      return reply(`🗑 حذف شد: ${escapeHtml(gone.name)}`);
    }
    case "/addadmin": {
      if (Number(uid) !== (await admins(p))[0] || !/^\d+$/.test(arg)) return reply("فقط صاحب بات؛ مثال: /addadmin 123456");
      const list = (await cfg(p, "admins", [])) || [];
      await setCfg(p, "admins", [...new Set([...list, Number(arg)])]);
      return reply("✅ ادمین اضافه شد.");
    }
    case "/check": {
      await reply("⏳ دارم خبرها رو چک می‌کنم…");
      const r = await collect(p);
      return reply(`✅ ${r.checked} خبر بررسی شد، ${r.added} خبر جدید برات اومد.` +
                   (r.errors.length ? "\n⚠️ " + escapeHtml(r.errors.slice(0, 5).join("\n")) : ""));
    }
  }
}
