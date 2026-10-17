"""ساخت کاور اینستاگرام ARIKO.

- گرادیان: نسخه‌ی ۷ که ادمین تأیید کرده (دست نزنید).
- چیدمان متن: از روی PSD خود ادمین («خبری.psd»، 1080x1440).
"""
import numpy as np
from PIL import Image, ImageFilter

COVER_SIZE = (1080, 1440)                      # 3:4 اینستاگرام (مثل PSD ادمین)
DARK = np.array([7, 7, 7], dtype=np.float32)   # مشکی خنثی (بدون ته‌رنگ آبی)
# نقاط منحنی: (ارتفاع نسبی کادر، میزان تیرگی)
GRADIENT_Y = [0.00, 0.34, 0.46, 0.56, 0.64, 0.72, 0.80, 0.88, 1.00]
GRADIENT_A = [0.00, 0.00, 0.28, 0.62, 0.83, 0.925, 0.97, 0.99, 1.00]
SMOOTH_SIGMA = 50       # پیکسل؛ صاف کردن منحنی تا هیچ لبه/پله‌ای دیده نشه
TOP_SHADE = 0.22        # سایه‌ی ملایم بالای کادر برای لوگو
TOP_SHADE_H = 0.10


def gradient_alpha(h=COVER_SIZE[1]):
    ys = np.arange(h, dtype=np.float32) / h
    alpha = np.interp(ys, GRADIENT_Y, GRADIENT_A)
    r = SMOOTH_SIGMA * 3
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / float(SMOOTH_SIGMA)) ** 2)
    k /= k.sum()
    alpha = np.convolve(np.pad(alpha, r, mode='edge'), k, mode='valid')
    return np.maximum(alpha, (np.clip((TOP_SHADE_H - ys) / TOP_SHADE_H, 0, 1) ** 2) * TOP_SHADE)


def fit_cover(img, size=COVER_SIZE, focus=(0.5, 0.0)):
    """عکس رو بدون کش آمدن، تمام‌کادر (cover) برش میده.
    focus: جای برش از ۰ تا ۱ (افقی، عمودی)؛ پیش‌فرض وسط و از بالا (صورت‌ها معمولاً بالان)."""
    w, h = size
    img = img.convert('RGB')
    s = max(w / img.width, h / img.height)
    img = img.resize((max(w, round(img.width * s)), max(h, round(img.height * s))), Image.LANCZOS)
    if s > 1.15:                                    # عکس کوچیک بزرگ شده → یه کم شارپ
        img = img.filter(ImageFilter.UnsharpMask(radius=1.6, percent=55, threshold=2))
    fx = min(1.0, max(0.0, focus[0]))
    fy = min(1.0, max(0.0, focus[1]))
    x0 = round((img.width - w) * fx)
    y0 = round((img.height - h) * fy)
    return img.crop((x0, y0, x0 + w, y0 + h))


MEDIUM_FILL = 0.74         # زوم «متوسط»: عکس تا ۷۴٪ ارتفاع کادر (لبه‌اش زیر بخش تیره‌ی گرادیان)
ZOOMS = ('original', 'cover', 'fit', 'medium')     # چرخه‌ی دکمه‌ی زوم
ZOOM_LABELS = {'original': 'اندازه‌ی اصلی', 'medium': 'متوسط',
               'fit': 'عرض کامل', 'cover': 'پر کردن کادر'}


def default_zoom(img, size=COVER_SIZE):
    """پیش‌فرض: عکس با اندازه‌ی اصلی خودش (بدون هیچ بزرگ/کوچیک کردنی)؛ ادمین خودش تنظیمش می‌کنه."""
    return 'original'


def compose_bg(img, size=COVER_SIZE, focus=(0.5, 0.0), zoom='cover', feather=150):
    """پس‌زمینه‌ی کاور هم‌اندازه‌ی کادر.
    cover: کل کادر پر (برش)؛ fit: کل عرض عکس دیده میشه؛ medium: عکس ~۷۴٪ ارتفاع کادر رو می‌گیره.
    اگه عکس به پایین کادر نرسه، پایینش نرم توی مشکی گرادیان حل میشه (هیچ لبه‌ای دیده نمیشه)."""
    w, h = size
    img = img.convert('RGB')
    if zoom == 'original':
        return place_original(img, size, focus)
    if zoom == 'cover' or overflow(img, size) != 'x':
        return fit_cover(img, size, focus)
    if zoom == 'fit':
        s = w / img.width
    else:
        # پایین عکس جایی تموم میشه که گرادیان تأییدشده دیگه تقریباً مشکیه (~۷۴٪ کادر)،
        # پس محو شدن لبه‌ی عکس زیر گرادیان پنهان می‌مونه و شکل گرادیان عوض نمیشه
        s = max(w / img.width, MEDIUM_FILL * h / img.height)
    nw, nh = max(w, round(img.width * s)), max(1, round(img.height * s))
    img = img.resize((nw, nh), Image.LANCZOS)
    if s > 1.15:
        img = img.filter(ImageFilter.UnsharpMask(radius=1.6, percent=55, threshold=2))
    x0 = round((nw - w) * min(1.0, max(0.0, focus[0])))
    img = img.crop((x0, 0, x0 + w, min(nh, h)))
    arr = np.asarray(img, dtype=np.float32)
    canvas = np.zeros((h, w, 3), dtype=np.float32) + DARK
    if zoom == 'fit':
        feather = max(feather, 300)                 # «کامل»: محو شدن بلندتر که لبه‌ی عکس نرم‌تر توی مشکی حل بشه
    fh = min(feather, arr.shape[0] // 2)
    m = np.ones(arr.shape[0], dtype=np.float32)
    ramp = np.linspace(1, 0, fh)
    m[-fh:] = ramp * ramp * (3 - 2 * ramp)
    canvas[:arr.shape[0]] = arr * m[:, None, None] + DARK * (1 - m[:, None, None])
    return Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))


def original_offset(img, size=COVER_SIZE, focus=(0.5, 0.0)):
    """جای عکس با اندازه‌ی اصلی: وسط افقی و از بالا؛ اگه از کادر بزرگ‌تر بود، focus تعیین می‌کنه کدوم تیکه دیده بشه."""
    w, h = size
    fx = min(1.0, max(0.0, focus[0]))
    fy = min(1.0, max(0.0, focus[1]))
    x0 = (w - img.width) // 2 if img.width <= w else -round((img.width - w) * fx)
    y0 = 0 if img.height <= h else -round((img.height - h) * fy)
    return x0, y0


def placement(img, size=COVER_SIZE, focus=(0.5, 0.0), zoom='original'):
    """(ضریب اندازه، (x, y) گوشه‌ی بالا-چپ عکس روی کادر) برای هر حالت زوم؛ برای فتوشاپ که خود عکس
    (بدون مشکی و محو شدن) جدا به‌عنوان لایه بره."""
    w, h = size
    fx = min(1.0, max(0.0, focus[0]))
    fy = min(1.0, max(0.0, focus[1]))
    if zoom == 'original':
        s0 = original_scale(img, size)
        if s0 == 1.0:
            return 1.0, original_offset(img, size, focus)
        big = img.resize((w, max(1, round(img.height * s0))))
        return s0, original_offset(big, size, focus)
    if zoom == 'fit' and overflow(img, size) == 'x':
        s = w / img.width
    elif zoom == 'medium' and overflow(img, size) == 'x':
        s = max(w / img.width, MEDIUM_FILL * h / img.height)
    else:
        s = max(w / img.width, h / img.height)
    iw, ih = round(img.width * s), round(img.height * s)
    x0 = -round((iw - w) * fx) if iw > w else (w - iw) // 2
    y0 = -round((ih - h) * fy) if ih > h else 0
    return s, (x0, y0)


def original_scale(img, size=COVER_SIZE):
    """«اندازه‌ی اصلی»: عکس بزرگ‌تر از کادر کوچیک نمیشه و بریده هم نمیشه؛ فقط عکسی که از عرض کادر باریک‌تره
    دقیقاً تا عرض کادر بزرگ میشه (وگرنه دو طرفش نوار مشکی می‌افته)."""
    return size[0] / img.width if img.width < size[0] else 1.0


def extend_down(img, target_h):
    """اگه عکس از پایین به کادر نمی‌رسه، زیرش با آینه‌ی عمودی همون عکس ادامه پیدا می‌کنه (زیر گرادیان
    تیره تقریباً دیده نمیشه ولی لبه‌ی صاف هم نمی‌مونه؛ هیچ تغییر اندازه‌ای هم نداره)."""
    if img.height >= target_h:
        return img
    out = Image.new('RGB', (img.width, target_h))
    out.paste(img, (0, 0))
    y, flip = img.height, True
    while y < target_h:
        piece = img.transpose(Image.FLIP_TOP_BOTTOM) if flip else img
        out.paste(piece, (0, y))
        y += img.height
        flip = not flip
    return out


def place_original(img, size=COVER_SIZE, focus=(0.5, 0.0), feather=90):
    """عکس با اندازه‌ی اصلی روی کادر (عکس باریک فقط تا عرض کادر بزرگ میشه)؛ اگه پایینش به کادر نرسه، نرم توی مشکی حل میشه."""
    w, h = size
    s0 = original_scale(img, size)
    if s0 != 1.0:
        img = img.resize((w, max(1, round(img.height * s0))), Image.LANCZOS)
        if s0 > 1.15:
            img = img.filter(ImageFilter.UnsharpMask(radius=1.6, percent=55, threshold=2))
    x0, y0 = original_offset(img, size, focus)
    img = extend_down(img.convert('RGB'), h - y0)     # بدون لبه‌ی پایین؛ ادامه‌ی آینه‌ای زیر گرادیان
    arr = np.asarray(img, dtype=np.float32)
    ih, iw = arr.shape[:2]
    mask = np.ones((ih, iw), dtype=np.float32)

    def ramp(n):
        r = np.linspace(0, 1, n, dtype=np.float32)
        return r * r * (3 - 2 * r)
    bottom = y0 + ih
    if bottom < h:                                   # پایین عکس به پایین کادر نمی‌رسه
        # اگه لبه‌ی عکس توی بخش تقریباً مشکی گرادیان باشه (≥۷۲٪ کادر)، فقط یه محو شدن کوتاه لازمه
        # که شکل گرادیان تأییدشده دست نخوره؛ عکس‌های کوتاه‌تر محو شدن بلندتر می‌گیرن
        dense = int(h * 0.72)
        n = 40 if bottom >= dense else feather * 2
        n = min(n, ih // 2)
        mask[-n:] *= ramp(n)[::-1][:, None]
    if x0 > 0:                                       # دو طرف (عکس باریک‌تر از کادر)
        n = min(feather, iw // 4)
        mask[:, :n] *= ramp(n)[None, :]
        mask[:, -n:] *= ramp(n)[::-1][None, :]
    canvas = np.zeros((h, w, 3), dtype=np.float32) + DARK
    sx0, sy0 = max(0, -x0), max(0, -y0)
    dx0, dy0 = max(0, x0), max(0, y0)
    cw, ch = min(w - dx0, iw - sx0), min(h - dy0, ih - sy0)
    part = arr[sy0:sy0 + ch, sx0:sx0 + cw]
    m = mask[sy0:sy0 + ch, sx0:sx0 + cw][:, :, None]
    canvas[dy0:dy0 + ch, dx0:dx0 + cw] = part * m + DARK * (1 - m)
    return Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))


def upscale_needed(img, size=COVER_SIZE, zoom='cover'):
    """چند برابر بزرگ میشه (برای هشدار/افزایش کیفیت)."""
    w, h = size
    if zoom == 'original':
        return original_scale(img, size)
    if zoom == 'fit' and overflow(img, size) == 'x':
        return w / img.width
    if zoom == 'medium' and overflow(img, size) == 'x':
        return max(w / img.width, MEDIUM_FILL * h / img.height)
    return max(w / img.width, h / img.height)


def overflow(img, size=COVER_SIZE):
    """کدوم جهت از کادر بیرون می‌زنه: 'x' (عکس افقی)، 'y' (عکس بلند) یا ''."""
    w, h = size
    r = img.width / img.height
    if r > w / h * 1.02:
        return 'x'
    if r < w / h / 1.02:
        return 'y'
    return ''


def auto_focus(img, size=COVER_SIZE):
    """حدس جای شلوغ/مهم عکس افقی (معمولاً شخصیت‌ها) برای برش؛ خروجی focus افقی ۰ تا ۱."""
    if overflow(img, size) != 'x':
        return 0.5
    small = img.convert('RGB').resize((240, max(1, round(240 * img.height / img.width))))
    a = np.asarray(small, dtype=np.float32)
    gray = a.mean(axis=2)
    edges = np.abs(np.diff(gray, axis=1))[:-1] + np.abs(np.diff(gray, axis=0))[:, :-1]
    sat = (a.max(axis=2) - a.min(axis=2))[:-1, :-1]
    energy = (edges * (0.5 + sat / 255.0))[: int(edges.shape[0] * 0.8)].sum(axis=0)   # پایین عکس زیر گرادیان میره
    win = max(1, round(edges.shape[1] * (size[0] / size[1]) / (img.width / img.height)))
    if win >= len(energy):
        return 0.5
    sums = np.convolve(energy, np.ones(win), mode='valid')
    center = np.ones_like(sums) - 0.25 * np.abs(np.linspace(-1, 1, len(sums)))   # کمی ترجیح وسط
    best = int(np.argmax(sums * center))
    return best / max(1, len(sums) - 1)


SUBJECT_Y = 0.36        # مرکز سوژه (صورت‌ها) حدوداً این ارتفاع کادر باشه؛ بالای بلوک متن و گرادیان تیره


def shown_size(img, size=COVER_SIZE):
    """اندازه‌ی عکس روی کادر در حالت «اندازه‌ی اصلی» (فقط عکس باریک تا عرض کادر پهن میشه)."""
    s = original_scale(img, size)
    return round(img.width * s), round(img.height * s)


def focus_for_subject(img, box, size=COVER_SIZE):
    """focus (fx, fy) که سوژه‌ی اصلی وسط کادر (افقی) و بالای متن (عمودی) بیفته و بریده نشه.
    box = (x0, y0, x1, y1) نسبی ۰ تا ۱ روی خود عکس (صورت/بالاتنه‌ی شخصیت‌های اصلی)."""
    w, h = size
    W, H = shown_size(img, size)
    x0, y0, x1, y1 = box
    fx = fy = 0.5 if W > w else 0.0
    if W > w:
        cx = (x0 + x1) / 2 * W
        left = cx - w / 2
        # اگه سوژه جا میشه، مطمئن شو هیچ لبه‌اش بیرون نمی‌زنه
        if (x1 - x0) * W <= w - 40:
            left = min(max(left, x1 * W - w + 20), x0 * W - 20)
        fx = min(1.0, max(0.0, left / (W - w)))
    if H > h:
        cy = (y0 + y1) / 2 * H
        top = cy - SUBJECT_Y * h
        top = min(top, y0 * H - 30)             # سر شخصیت بریده نشه
        fy = min(1.0, max(0.0, top / (H - h)))
    else:
        fy = 0.0
    return fx, fy


def subject_fit(img, box, size=COVER_SIZE):
    """چقدر سوژه با این کادر خوب دیده میشه: (بخش دیده‌شده‌ی عرض سوژه ۰..۱، ارتفاع مرکز سوژه روی کادر ۰..۱)."""
    w, h = size
    W, H = shown_size(img, size)
    fx, fy = focus_for_subject(img, box, size)
    left = (W - w) * fx if W > w else 0
    top = (H - h) * fy if H > h else 0
    x0, y0, x1, y1 = box
    bw = max(1.0, (x1 - x0) * W)
    seen = max(0.0, min(x1 * W, left + w) - max(x0 * W, left)) / bw
    cy = ((y0 + y1) / 2 * H - top) / h
    return seen, cy


def black_white(img):
    """حالت سیاه‌وسفید آروم برای خبرهای غم‌انگیز."""
    from PIL import ImageEnhance, ImageOps
    g = ImageOps.grayscale(img).convert('RGB')
    return ImageEnhance.Contrast(g).enhance(1.06)


def apply_gradient(img):
    """گرادیان تأییدشده رو روی عکس (اندازه‌ی کاور) می‌اندازه و RGB برمی‌گردونه."""
    arr = np.array(img.convert('RGB'), dtype=np.float32)
    a = gradient_alpha(arr.shape[0])[:, None, None]
    out = arr * (1 - a) + DARK * a
    out += (np.random.random(out.shape) - np.random.random(out.shape))   # دیتر ضد باندینگ
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


# ───────────────────────── چیدمان متن (از روی PSD ادمین: «خبری.psd») ─────────────────────────
# سند فتوشاپ 1080x1440 در 300ppi → هر pt برابر 300/72 پیکسل.
import os
import re
from PIL import ImageDraw, ImageFont

PT = 300 / 72.0
PSD_SIZE = (1080, 1440)
YELLOW = (251, 221, 27)
WHITE = (255, 255, 255)
WORD_SPACE = 0.85                       # فاصله‌ی کلمه‌ها مثل فتوشاپ کمی جمع‌تر
FONT_FILES = {                          # وزن‌های IRANSansX؛ اولین فایلِ موجود استفاده میشه
    'title': ['IRANSansX-ExtraBlack.ttf', 'IRANSansX-Black.ttf', 'IRANSansX-Heavy.ttf'],
    'tag': ['IRANSansX-DemiBold.ttf', 'IRANSansX-Medium.ttf'],
    'sub': ['IRANSansX-Bold.ttf', 'IRANSansX-DemiBold.ttf'],
}
LAYOUT = {
    'title_size': 17.65 * PT, 'title_leading': 26 * PT, 'title_max_w': 980,
    'title_top': 1083 - 108,            # بالای خط اول (از روی نمونه اندازه‌گیری شده)
    'tag_size': 5.44 * PT, 'tag_box': (136, 44), 'tag_gap': 93, 'tag_stroke': 3, 'tag_radius': 9,
    'sub_size': 6 * PT, 'sub_top': 1322,
    'logo_xy': (50, 42), 'logo_h': 50,
}
_LATIN = re.compile(r'[A-Za-z]')
_ARABIC = re.compile(r'[؀-ۿ]')


def _font(role, size, fonts_dir):
    dirs = [fonts_dir] if isinstance(fonts_dir, str) else list(fonts_dir)
    for name in FONT_FILES[role]:
        for d in dirs:
            p = os.path.join(d, name)
            if os.path.exists(p):
                if RAQM:
                    return ImageFont.truetype(p, round(size))
                return ImageFont.truetype(p, round(size), layout_engine=ImageFont.Layout.BASIC)
    raise FileNotFoundError('فونت %s (%s) پیدا نشد' % (role, FONT_FILES[role][0]))


def missing_fonts(fonts_dir):
    """اسم فایل‌های فونتی که برای هر نقش هیچ‌کدوم پیدا نشده."""
    dirs = [fonts_dir] if isinstance(fonts_dir, str) else list(fonts_dir)
    return [names[0] for names in FONT_FILES.values()
            if not any(os.path.exists(os.path.join(d, n)) for n in names for d in dirs)]


def _is_latin(word):
    return bool(_LATIN.search(word)) and not _ARABIC.search(word)


def _tokens(runs, font=None, draw=None, max_w=0):
    """[('متن', رنگ), ...] → کلمه‌ها با رنگشون.
    اسم انگلیسی (تیکه‌ی زرد) اگه توی یه خط جا بشه یه تیکه‌ی نشکن میمونه (Kakunaru Ue wa نصف نمیشه)."""
    out = []
    for text, color in runs:
        text = ' '.join(text.split())
        if (color != WHITE and font is not None and _is_latin(text) and ' ' in text
                and draw.textlength(text, font=font) <= max_w):
            out.append((text, color))
        else:
            out += [(w, color) for w in text.split()]
    return out


def _wrap(tokens, font, draw, max_w):
    """شکستن متوازن خط‌ها: کمترین تعداد خط، و خط‌ها تا جای ممکن هم‌اندازه
    (نه اینکه خط اول پر بشه و «شد!» تنها بره خط بعد)."""
    if not tokens:
        return []
    space = draw.textlength(' ', font=font) * WORD_SPACE
    ws = [_word_w(t[0], font, draw) for t in tokens]
    n = len(tokens)

    def width(i, j):                                # عرض کلمه‌های i..j-1 توی یه خط
        return sum(ws[i:j]) + space * (j - i - 1)

    # کمترین تعداد خط (حریصانه)
    count, cur = 1, 0.0
    for k, w in enumerate(ws):
        add = w if cur == 0 else space + w
        if cur and cur + add > max_w:
            count, cur = count + 1, w
        else:
            cur += add
    # با همین تعداد خط، بلندترین خط رو کمینه کن (DP؛ تعداد کلمه‌ها کمه)
    INF = float("inf")
    best = {(0, 0): (0.0, [])}
    for lines_used in range(count):
        nxt = {}
        for (i, _), (worst, cuts) in best.items():
            for j in range(i + 1, n + 1):
                w = width(i, j)
                if w > max_w and j > i + 1:
                    break
                cand = max(worst, w)
                key = (j, lines_used + 1)
                if cand < nxt.get(key, (INF,))[0]:
                    nxt[key] = (cand, cuts + [j])
        best = nxt
    final = best.get((n, count))
    if not final:                                   # نشد (کلمه‌ی خیلی بلند) → حریصانه
        final = (0, [])
        out, cur_line, cur = [], [], 0.0
        for tok, w in zip(tokens, ws):
            add = w if not cur_line else space + w
            if cur_line and cur + add > max_w:
                out.append(cur_line)
                cur_line, cur = [tok], w
            else:
                cur_line.append(tok)
                cur += add
        return out + ([cur_line] if cur_line else [])
    lines, i = [], 0
    for j in final[1]:
        lines.append(tokens[i:j])
        i = j
    return lines


def _line_w(line, font, draw):
    space = draw.textlength(' ', font=font) * WORD_SPACE
    return sum(_word_w(t[0], font, draw) for t in line) + space * (len(line) - 1)


def _raqm():
    try:
        from PIL import features
        return bool(features.check('raqm'))
    except Exception:
        return False


RAQM = _raqm()      # روی ویندوز معمولاً نیست (fribidi.dll) → فارسی با arabic_reshaper + python-bidi


def _fa(text):
    """(متن آماده‌ی رسم، پارامترهای رسم) برای متن فارسی/مخلوط."""
    if _is_latin(text):
        return text, {}
    if RAQM:
        return text, dict(direction='rtl', language='fa')
    try:
        import arabic_reshaper
        try:
            from bidi import get_display
        except ImportError:
            from bidi.algorithm import get_display
    except ImportError:
        raise RuntimeError('برای متن فارسی این دو تا لازمن: pip install arabic-reshaper python-bidi')
    shaped = arabic_reshaper.reshape(text).replace('\u200c', '')
    return get_display(shaped), {}


def _word_w(word, font, draw):
    t, kw = _fa(word)
    return draw.textlength(t, font=font, **kw)


def _draw_line(draw, line, font, y, width):
    """یه خط راست‌به‌چپ با تیکه‌های انگلیسی چپ‌به‌راست، وسط‌چین."""
    space = draw.textlength(' ', font=font) * WORD_SPACE
    # گروه‌بندی به تیکه‌های هم‌جهت (bidi ساده: پاراگراف RTL)
    runs = []
    for tok in line:
        lat = _is_latin(tok[0])
        if runs and runs[-1][0] == lat:
            runs[-1][1].append(tok)
        else:
            runs.append([lat, [tok]])
    widths = [_word_w(t[0], font, draw) for t in line]
    total = sum(widths) + space * (len(line) - 1)
    x_right = (width + total) / 2
    for lat, toks in runs:                          # تیکه‌ها از راست به چپ
        ws = [_word_w(t[0], font, draw) for t in toks]
        run_w = sum(ws) + space * (len(toks) - 1)
        if lat:                                     # داخل تیکه‌ی انگلیسی: چپ به راست
            x = x_right - run_w
            for (word, color), w in zip(toks, ws):
                draw.text((x, y), word, font=font, fill=color, anchor='ls')
                x += w + space
        else:                                       # داخل تیکه‌ی فارسی: راست به چپ
            x = x_right
            for (word, color), w in zip(toks, ws):
                t, kw = _fa(word)
                draw.text((x - w, y), t, font=font, fill=color, anchor='ls', **kw)
                x -= w + space
        x_right -= run_w + space


ADJ_DEFAULT = {"ts": 1.0, "ty": 0, "ss": 1.0, "sy": 0, "hc": None}   # تنظیم دستی متن از ربات (اندازه/جا/رنگ)


def _fit_title(title_runs, fonts_dir, draw, ts=1.0):
    """(فونت، اندازه، خط‌ها) تیتر؛ تیتر طولانی کمی کوچیک‌تر میشه تا ۳ خط جا بشه."""
    L = LAYOUT
    size = L['title_size'] * ts
    tf = _font('title', size, fonts_dir)
    lines = _wrap(_tokens(title_runs, tf, draw, L['title_max_w']), tf, draw, L['title_max_w'])
    while (len(lines) > 3 or any(_line_w(ln, tf, draw) > L['title_max_w'] for ln in lines)) \
            and size > L['title_size'] * ts * 0.62:
        size *= 0.94
        tf = _font('title', size, fonts_dir)
        lines = _wrap(_tokens(title_runs, tf, draw, L['title_max_w']), tf, draw, L['title_max_w'])
    return tf, size, lines


def adj_of(adj):
    out = dict(ADJ_DEFAULT)
    out.update({k: v for k, v in (adj or {}).items() if k in ADJ_DEFAULT and v is not None})
    return out


def render_text(img, title_runs, tag, subtitle, fonts_dir, logo=None, adj=None):
    """متن‌ها رو مثل PSD ادمین روی کاور (بعد از گرادیان) می‌نویسه.
    adj: ts/ss = ضریب اندازه‌ی تیتر/زیرنویس، ty/sy = جابه‌جایی عمودی (پیکسل)، hc = رنگ بخش رنگی تیتر."""
    L = LAYOUT
    A = adj_of(adj)
    W, H = img.size
    img = img.convert('RGBA')
    draw = ImageDraw.Draw(img)
    if A["hc"]:
        title_runs = [(t, tuple(A["hc"]) if c != WHITE else c) for t, c in title_runs]

    # تیتر: وسط‌چین، شکستن خودکار خط‌ها، اسم انیمه زرد و انگلیسی
    tf, size, lines = _fit_title(title_runs, fonts_dir, draw, A["ts"])
    leading = L['title_leading'] * size / L['title_size']
    cap = -tf.getbbox('A', anchor='ls')[1]
    full = _font('title', L['title_size'], fonts_dir)
    # خط پایه‌ی خط آخر همیشه همون‌جای PSD می‌مونه (فاصله تا زیرنویس ثابت)؛ تیتر کوتاه‌تر فقط از بالا کم میشه
    last_base = L['title_top'] - full.getbbox('A', anchor='ls')[1] + 2 * L['title_leading'] + A["ty"]
    base0 = last_base - (len(lines) - 1) * leading
    for i, line in enumerate(lines):
        _draw_line(draw, line, tf, base0 + i * leading, W)
    title_top = base0 - cap

    # تگ «خبر رسمی» با کادر دور خط سفید
    if tag:
        gf = _font('tag', L['tag_size'], fonts_dir)
        tag = '  '.join(tag.split())            # مثل PSD: فاصله‌ی بازتر بین کلمه‌ها (دُم «ر» به کلمه‌ی بعد نچسبه)
        bw, bh = L['tag_box']
        tag, tkw = _fa(tag)
        bw = max(bw, draw.textlength(tag, font=gf, **tkw) + 44)
        top = title_top - L['tag_gap']
        draw.rounded_rectangle(((W - bw) / 2, top, (W + bw) / 2, top + bh), radius=L['tag_radius'],
                               outline=WHITE, width=L['tag_stroke'])
        draw.text((W / 2, top + bh / 2 - 2), tag, font=gf, fill=WHITE, anchor='mm', **tkw)

    # زیرنویس با سایه‌ی نرم
    if subtitle:
        sf = _font('sub', L['sub_size'] * A["ss"], fonts_dir)
        subtitle, kw = _fa(subtitle)
        pos = (W / 2, L['sub_top'] + A["sy"])
        sh = Image.new('RGBA', img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pos[0] + 2, pos[1] + 3), subtitle, font=sf, fill=(0, 0, 0, 170), anchor='mt', **kw)
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(4)))
        ImageDraw.Draw(img).text(pos, subtitle, font=sf, fill=WHITE, anchor='mt', **kw)

    if logo is not None:
        lg = logo.convert('RGBA')
        lg = lg.crop(lg.getchannel('A').point(lambda v: 255 if v > 20 else 0).getbbox())
        h = L['logo_h']
        lg = lg.resize((round(lg.width * h / lg.height), h), Image.LANCZOS)
        x, y = L['logo_xy']
        if logo_should_be_dark(img, (x, y, x + lg.width, y + lg.height)):   # پس‌زمینه‌ی روشن → لوگوی مشکی
            dark = Image.new('RGBA', lg.size, LOGO_DARK + (255,))
            dark.putalpha(lg.getchannel('A'))
            lg = dark
        img.alpha_composite(lg, (x, y))
    return img.convert('RGB')


LOGO_DARK = (12, 12, 12)


def logo_should_be_dark(img, box):
    """پشت لوگو روشنه؟ (میانگین روشنایی ناحیه‌ی لوگو و کمی اطرافش)"""
    x0, y0, x1, y1 = box
    pad = 12
    region = img.convert('L').crop((max(0, x0 - pad), max(0, y0 - pad), x1 + pad, y1 + pad))
    arr = np.asarray(region, dtype=np.float32)
    return float(arr.mean()) > 185 and float(np.percentile(arr, 25)) > 160


def parse_title(text):
    """«تریلر جدید انیمه‌ی [Roshidere] منتشر شد!» → تیکه‌های رنگی (داخل [] زرد)."""
    runs = []
    for i, part in enumerate(re.split(r'\[([^\]]+)\]', text or '')):
        if part.strip():
            runs.append((part.strip(), YELLOW if i % 2 else WHITE))
    return runs


def render_cover(bg, title, subtitle, tag, fonts_dir, logo=None, focus=None, bw=False, size=PSD_SIZE, zoom=None, adj=None):
    """کاور کامل: جاگذاری عکس (زوم) → (سیاه‌وسفید) → گرادیان → متن و لوگو."""
    if focus is None:
        focus = (auto_focus(bg, size), 0.0)
    img = compose_bg(bg, size, focus, zoom or default_zoom(bg, size))
    if bw:
        img = black_white(img)
    img = apply_gradient(img)
    return render_text(img, parse_title(title), tag, subtitle, fonts_dir, logo=logo, adj=adj)


def title_lines_for_photoshop(title, fonts_dir, ts=1.0):
    """شکستن خط‌های تیتر دقیقاً مثل پیش‌نمایش (همون خط‌ها و همون کوچیک شدن تیتر بلند)، برای فتوشاپ.
    خروجی: (متن با \r بین خط‌ها، تیکه‌های زرد هر خط، ضریب اندازه نسبت به اندازه‌ی قالب)."""
    draw = ImageDraw.Draw(Image.new('RGB', (10, 10)))
    tf, size, lines = _fit_title(parse_title(title), fonts_dir, draw, ts)
    text_lines, names = [], []
    for line in lines:
        text_lines.append(' '.join(t[0] for t in line))
        piece = []
        for word, color in line + [('', WHITE)]:
            if color != WHITE and word:
                piece.append(word)
            elif piece:
                names.append(' '.join(piece))
                piece = []
    return '\r'.join(text_lines), names, size / LAYOUT['title_size']


def poster_slide(img, size=PSD_SIZE):
    """اسلاید دوم: کل پوستر بدون برش وسط کادر؛ دو طرف/بالا-پایین با نسخه‌ی مات و تیره‌ی همون پوستر پر میشه."""
    from PIL import ImageEnhance
    w, h = size
    img = img.convert('RGB')
    bg = fit_cover(img, size, (0.5, 0.5)).filter(ImageFilter.GaussianBlur(40))
    bg = ImageEnhance.Brightness(bg).enhance(0.45)
    s = min(w / img.width, h / img.height)
    fg = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    if s > 1.15:
        fg = fg.filter(ImageFilter.UnsharpMask(radius=1.6, percent=55, threshold=2))
    bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
    return bg
