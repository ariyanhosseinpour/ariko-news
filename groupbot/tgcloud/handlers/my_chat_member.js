// ربات به یه گروه اضافه شد: اگه مالک/جانشین اضافه کرده خودکار فعال میشه، وگرنه منتظر «فعال» می‌مونه.
import { platform } from "../lib/platform.js";
import { botAdded } from "../lib/flow.js";

export default async function (upd, ctx) {
  return botAdded(platform(), upd);
}
