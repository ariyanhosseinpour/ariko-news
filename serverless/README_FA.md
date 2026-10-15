# بات خبری آریکو روی Telegram Serverless

- **روی تلگرام** (`tgcloud/`): چک خبرهای RSS، کپشن با Gemini، پیش‌نمایش برای ادمین، دکمه‌ی «✅ انتشار / ❌ رد».
  عکس اول با لینک فرستاده میشه؛ اگه تلگرام قبول نکرد، خود سرور دانلود و آپلودش می‌کنه (تا ۱۰ مگ، JPEG/PNG/WEBP).
- **روی کامپیوتر** (`serverless_agent.py`): فقط عکس‌هایی که سرور نتونست (بیشتر از ۱۰ مگ، AVIF/GIF، سایت دانلود رو بست).
  تا کامپیوتر روشن نشه، اون خبر منتشر نمیشه و بات پیام میده «این خبر عکس لازم داره، سیستم رو روشن کن».

## نصب (روی کامپیوتر، یه بار)
1. Node.js 18 یا بالاتر نصب باشه. این پوشه (`serverless`) رو یه جا بذار و توش ترمینال باز کن:
   ```
   npm install
   npx tgcloud login        ← توکن CLI Access رو بده (BotFather → بات → Serverless → CLI Access)
   npx tgcloud push         ← کد رو می‌فرسته
   npx tgcloud migrate      ← جدول دیتابیس (kv) ساخته میشه
   npx tgcloud webhook      ← باید بگه وبهوک با handlerها جوره
   ```
2. توی بات: `/start` ، `/setgemini کلید` ، `/setchannel @کانال` (بات ادمین کانال باشه) ، `/check`.

## برنامه‌ی کامپیوتر
`.env` کنار `serverless_agent.py`:
```
NEWS_BOT_TOKEN=توکن بات خبری
TGCLOUD_TOKEN=توکن CLI Access
TGCLOUD_PROJECT=مسیر همین پوشه‌ی serverless (اگه کنار serverless_agent.py نیست)
NEWS_PROXY=http://127.0.0.1:10809   (اگه فیلترشکن پروکسی لازم داره)
```
اجرا: `python serverless_agent.py` (نیاز: `pip install pillow`)

## چک خودکار خبرها
Serverless فعلاً زمان‌بندی (cron) نداره. هر ۵ دقیقه یکی باید «چک کن» رو صدا بزنه:
- وقتی کامپیوتر روشنه، خود `serverless_agent.py` این کار رو می‌کنه.
- برای وقتی کامپیوتر خاموشه: همین پوشه + `serverless_agent.py` + `.env` (فقط `TGCLOUD_TOKEN` لازمه) روی هاست ربات اصلی،
  و کران هر ۵ دقیقه: `python3 $HOME/botnews/serverless_agent.py --tick` (Pillow لازم نداره، خیلی سبکه).
- یا دستی توی بات: `/check`.
