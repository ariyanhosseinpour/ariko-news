// پل بین منطق بات (lib/news.js) و SDK خود Telegram Serverless.
// news.js فقط با این شیء کار می‌کنه، پس بیرون از پلتفرم (تست) هم میشه یه نسخه‌ی ساختگی بهش داد.
import { api, fetch, InputFile } from 'sdk';
import db, { eq, like } from 'sdk/db';
import { kv as kvTable } from '../schema.js';

export function platform() {
  return {
    api: (method, params = {}) => api[method](params),
    fetch,
    InputFile,
    kv: {
      async get(key) {
        const row = await db.select().from(kvTable).where(eq(kvTable.key, key)).get();
        return row ? row.value : null;
      },
      async set(key, value) {
        const row = { key, value, updated: Math.floor(Date.now() / 1000) };
        await db.insert(kvTable).values(row)
          .onConflictDoUpdate({ target: kvTable.key, set: { value, updated: row.updated } }).run();
      },
      async del(key) {
        await db.delete(kvTable).where(eq(kvTable.key, key)).run();
      },
      async list(prefix) {
        const rows = await db.select().from(kvTable).where(like(kvTable.key, prefix + '%')).all();
        return rows.map(r => ({ key: r.key, value: r.value }));
      },
    },
  };
}
