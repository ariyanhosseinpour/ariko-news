// پیام‌های ادمین: منوی دکمه‌ای (مثل بات قدیمی). دستورهای / هم هنوز کار می‌کنن.
import { platform } from "../lib/platform.js";
import { isAdmin, cfg, setCfg, feeds, collect, admins, pendingNews, resendPreview, DEFAULT_FOOTER } from "../lib/news.js";
import { escapeHtml } from "../lib/core.js";
import { B, OLD, mainKeyboard, cancelKeyboard, statusText, feedCard, aiView, adminsView, channelView, footerView,
         setWait, getWait, clearWait, WAIT_PROMPT } from "../lib/menu.js";

const COMMANDS = { "/start": B.status, "/status": B.status, "/check": B.check, "/feeds": B.feeds,
                   "/queue": B.queue, "/menu": B.status };

export default async function (msg, ctx) {
  const p = platform();
  const uid = msg.from && msg.from.id;
  if (!uid || !(await isAdmin(p, uid))) return;
  const raw = (msg.text || "").trim();
  const text = OLD[raw] || raw;
  const send = (t, extra = {}) => p.api("sendMessage", { chat_id: msg.chat.id, text: t, parse_mode: "HTML",
                                                        disable_web_page_preview: true, ...extra });
  const menu = (t) => send(t, { reply_markup: mainKeyboard() });

  if (text === B.cancel) { await clearWait(p, uid); return menu("لغو شد."); }

  const [cmd, ...rest] = text.split(/\s+/);
  const command = cmd.split("@")[0];
  const button = COMMANDS[command] || (Object.values(B).includes(text) ? text : null);
  if (button) await clearWait(p, uid);                        // زدن هر دکمه‌ی منو، انتظار قبلی رو لغو می‌کنه

  // ───── جواب به سؤال قبلی (مثلاً لینک منبع، یا پست فورواردشده از کانال) ─────
  const wait = !button && !text.startsWith("/") ? await getWait(p, uid) : null;
  if (wait) return handleWait(p, msg, uid, wait, raw, send, menu);

  switch (button) {
    case B.status: return menu(await statusText(p));
    case B.check: {
      await send("⏳ دارم خبرها رو بررسی می‌کنم…");
      const r = await collect(p);
      return menu(`✅ ${r.checked} خبر بررسی شد، ${r.added} خبر جدید برات اومد.` +
                  (r.errors.length ? "\n⚠️ " + escapeHtml(r.errors.slice(0, 5).join("\n")) : ""));
    }
    case B.queue: {
      const list = await pendingNews(p);
      if (!list.length) return menu("📥 صف بررسی خالیه؛ خبری منتظر تأیید نیست.");
      await menu(`📥 ${list.length} خبر منتظر تأییده${list.length > 5 ? " (۵ تای آخر رو می‌فرستم)" : ""}:`);
      for (const n of list.slice(0, 5)) {
        try { await resendPreview(p, msg.chat.id, n); } catch (e) { /* */ }
      }
      return;
    }
    case B.feeds: {
      const list = await feeds(p);
      if (!list.length) return menu("هیچ منبعی ثبت نشده. از «➕ افزودن منبع خبری» اضافه کن.");
      for (const [i, f] of list.entries()) await send(...view(await feedCard(p, f, i)));
      return;
    }
    case B.addFeed: return startWait("feed");
    case B.channel: return send(...view(await channelView(p)));
    case B.footer: return send(...view(await footerView(p, DEFAULT_FOOTER)));
    case B.ai: return send(...view(await aiView(p)));
    case B.admins: return send(...view(await adminsView(p)));
  }

  // ───── دستورهای قدیمی (هنوز کار می‌کنن) ─────
  const arg = rest.join(" ").trim();
  const withArg = (kind) => (arg ? handleWait(p, msg, uid, { kind }, arg, send, menu) : startWait(kind));
  switch (command) {
    case "/setgemini": return withArg("key");
    case "/setchannel": return withArg("channel");
    case "/footer": return withArg("footer");
    case "/addfeed": return withArg("feed");
    case "/addadmin": return withArg("admin");
    case "/setmodel":
      await setCfg(p, "model", arg);
      return menu(`✅ مدل: ${escapeHtml(arg || "پیش‌فرض")}`);
    case "/importfeeds": return importFeeds(p, raw, menu);
  }

  return menu("از دکمه‌های پایین صفحه استفاده کن 👇");

  async function startWait(kind) {
    await setWait(p, uid, kind);
    return send(WAIT_PROMPT[kind], { reply_markup: cancelKeyboard() });
  }
}

const view = (v) => [v.text, { reply_markup: v.reply_markup }];

async function handleWait(p, msg, uid, wait, raw, send, menu) {
  const again = (t) => send(t, { reply_markup: cancelKeyboard() });   // جواب اشتباه → دوباره بپرس
  switch (wait.kind) {
    case "feed": {
      const [url, ...name] = raw.split(/\s+/);
      if (!/^https?:\/\/\S+$/.test(url || "")) return again("❗️ این لینک نیست. لینک RSS رو بفرست (با https شروع میشه).");
      const list = await feeds(p);
      if (list.some((f) => f.url === url)) { await clearWait(p, uid); return menu("این منبع از قبل هست."); }
      let label = name.join(" ");
      if (!label) { try { label = new URL(url).hostname.replace(/^www\./, ""); } catch (e) { label = url; } }
      list.push({ name: label, url });
      await setCfg(p, "feeds", list);
      await clearWait(p, uid);
      return menu(`✅ منبع «${escapeHtml(label)}» اضافه شد. الان ${list.length} منبع داری.`);
    }
    case "channel": {
      const origin = msg.forward_origin;
      let chat = origin && origin.type === "channel" && origin.chat ? String(origin.chat.id)
               : (msg.forward_from_chat ? String(msg.forward_from_chat.id) : raw.trim());
      if (/^(https?:\/\/)?t\.me\/\+/.test(chat)) {
        return again("❗️ لینک دعوت (t.me/+…) قبول نمیشه. یه پست از کانال رو برام فوروارد کن.");
      }
      chat = chat.replace(/^(https?:\/\/)?t\.me\//, "@");
      if (!/^@[A-Za-z0-9_]{4,}$|^-100\d+$/.test(chat)) {
        return again("❗️ متوجه نشدم. یه پست از کانال رو برام فوروارد کن، یا آیدی رو مثل <code>@Ariko_News</code> بفرست.");
      }
      let title = chat;
      try {
        const info = await p.api("getChat", { chat_id: chat });
        title = info.title || chat;
      } catch (e) {
        return again("❗️ بات به این کانال دسترسی نداره. اول بات رو <b>ادمین کانال</b> کن، بعد دوباره بفرست.");
      }
      await setCfg(p, "channel", chat);
      await clearWait(p, uid);
      return menu(`✅ کانال خبر: <b>${escapeHtml(title)}</b>\n(<code>${escapeHtml(chat)}</code>)`);
    }
    case "footer": {
      const footer = raw.trim() === "-" ? "" : raw.trim();
      if (!footer && raw.trim() !== "-") return again("❗️ متن امضا رو بفرست.");
      await setCfg(p, "footer", footer);
      await clearWait(p, uid);
      return menu(footer ? `✅ امضا عوض شد:\n${escapeHtml(footer)}` : "✅ امضا برداشته شد.");
    }
    case "key": {
      try { await p.api("deleteMessage", { chat_id: msg.chat.id, message_id: msg.message_id }); } catch (e) { /* */ }
      const key = raw.trim();
      if (!/^\S{20,}$/.test(key)) return again("❗️ این کلید درست به نظر نمیاد. دوباره بفرست.");
      await setCfg(p, "gemini_key", key);
      await clearWait(p, uid);
      return menu("✅ کلید Gemini ذخیره شد (پیامت پاک شد).");
    }
    case "admin": {
      if (Number(uid) !== (await admins(p))[0]) { await clearWait(p, uid); return menu("فقط صاحب بات می‌تونه ادمین اضافه کنه."); }
      const origin = msg.forward_origin;
      const id = origin && origin.type === "user" && origin.sender_user ? origin.sender_user.id
               : (msg.forward_from ? msg.forward_from.id : (/^\d+$/.test(raw.trim()) ? Number(raw.trim()) : 0));
      if (!id) return again("❗️ آیدی پیدا نشد. آیدی عددی رو بفرست، یا پیامش رو فوروارد کن (اگه حریم خصوصی‌اش اجازه بده).");
      const list = (await cfg(p, "admins", [])) || [];
      await setCfg(p, "admins", [...new Set([...list, Number(id)])]);
      await clearWait(p, uid);
      return menu(`✅ ادمین <code>${id}</code> اضافه شد.`);
    }
  }
  await clearWait(p, uid);
  return menu("لغو شد.");
}

async function importFeeds(p, raw, menu) {
  // هر خط: لینک | اسم   (خروجی export_feeds.py از دیتابیس بات قدیمی)
  const lines = raw.split("\n").slice(1).map((l) => l.trim()).filter(Boolean);
  if (!lines.length) return menu("متن فایل feeds_import.txt رو (که export_feeds.py ساخت) همین‌جا بفرست.");
  const list = await feeds(p);
  const have = new Set(list.map((f) => f.url));
  let added = 0, skipped = 0;
  for (const l of lines) {
    const [url, ...name] = l.split("|").map((x) => x.trim());
    if (!/^https?:\/\//.test(url || "") || have.has(url)) { skipped++; continue; }
    list.push({ name: name.join(" ") || url, url });
    have.add(url);
    added++;
  }
  await setCfg(p, "feeds", list);
  return menu(`✅ ${added} منبع اضافه شد${skipped ? ` (${skipped} تا تکراری/نامعتبر بود)` : ""}. الان ${list.length} منبع داری.`);
}
