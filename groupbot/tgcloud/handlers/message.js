// هر پیام: توی گروه → مدیریت (دستورها، قفل‌ها، اخطار، آمار)؛ خصوصی → راهنما و لیست گروه‌ها برای مالک.
import { platform } from "../lib/platform.js";
import { groupMessage, privateMessage } from "../lib/flow.js";

export default async function (msg, ctx) {
  const p = platform();
  if (msg.chat && msg.chat.type === "private") return privateMessage(p, msg);
  return groupMessage(p, msg);
}
