// دیتابیس بات خبری: یه جدول کلید/مقدار (تنظیمات، خبرها، کارهای کامپیوتر، «قبلاً دیده شده»).
import { table, text, integer, json } from 'sdk/db';

export const kv = table('kv', {
  key: text('key').primaryKey(),
  value: json('value'),
  updated: integer('updated_at'),
});
