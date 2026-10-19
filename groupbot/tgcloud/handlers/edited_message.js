// پیام ویرایش‌شده: لینک یا کلمه‌ای که بعداً با ویرایش اضافه بشه هم گرفته میشه.
import { platform } from "../lib/platform.js";
import { editedMessage } from "../lib/flow.js";

export default async function (msg, ctx) {
  return editedMessage(platform(), msg);
}
