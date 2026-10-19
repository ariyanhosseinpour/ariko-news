// دیتابیس بات مدیریت گروه: یه جدول کلید/مقدار (تنظیمات هر گروه، اعضا، آمار).
import { table, text, integer, json } from 'sdk/db';

export const kv = table('kv', {
  key: text('key').primaryKey(),
  value: json('value'),
  updated: integer('updated_at'),
});
