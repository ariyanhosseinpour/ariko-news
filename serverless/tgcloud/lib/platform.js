// پل بین منطق بات (lib/news.js) و SDK خود Telegram Serverless.
// news.js فقط با این شیء کار می‌کنه، پس بیرون از پلتفرم (تست) هم میشه یه نسخه‌ی ساختگی بهش داد.
import { api, fetch, InputFile } from 'sdk';
import db, { eq, like } from 'sdk/db';
import { kv as kvTable } from '../schema.js';
import { UPSTASH_URL, UPSTASH_TOKEN } from './secrets.js';

// پایگاه‌داده‌ی جایگزین (Upstash Redis، از طریق HTTP): اگه تنظیم شده باشه، به‌جای دیتابیس خود تلگرام استفاده میشه
// تا اگه دیتابیس Serverless خراب شد، بات از کار نیفته.
async function redis(cmd) {
  const res = await fetch(UPSTASH_URL.replace(/\/+$/, ""), {
    method: "POST",
    headers: { Authorization: `Bearer ${UPSTASH_TOKEN}`, "Content-Type": "application/json" },
    body: JSON.stringify(cmd),
  });
  const data = await res.json();
  if (data.error) throw new Error(`Upstash: ${data.error}`);
  return data.result;
}

const redisKv = {
  async get(key) {
    const v = await redis(["GET", key]);
    return v === null || v === undefined ? null : JSON.parse(v);
  },
  async set(key, value) {
    await redis(["SET", key, JSON.stringify(value === undefined ? null : value)]);
  },
  async del(key) {
    await redis(["DEL", key]);
  },
  async list(prefix) {
    const keys = [];
    let cursor = "0";
    do {
      const [next, batch] = await redis(["SCAN", cursor, "MATCH", prefix.replace(/[*?\[\]]/g, "\\$&") + "*", "COUNT", "1000"]);
      cursor = String(next);
      keys.push(...batch);
    } while (cursor !== "0" && keys.length < 20000);
    const out = [];
    for (let i = 0; i < keys.length; i += 200) {
      const chunk = keys.slice(i, i + 200);
      const vals = await redis(["MGET", ...chunk]);
      chunk.forEach((k, j) => { if (vals[j] !== null) out.push({ key: k, value: JSON.parse(vals[j]) }); });
    }
    return out;
  },
};

export const storageName = () => (UPSTASH_URL && UPSTASH_TOKEN ? "Upstash" : "Telegram");

export function platform() {
  if (UPSTASH_URL && UPSTASH_TOKEN) {
    return { api: (method, params = {}) => api[method](params), fetch, InputFile, kv: redisKv };
  }
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
