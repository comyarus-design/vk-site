import os
import re
import json
import html
import random
from datetime import datetime, timezone
from urllib import request
from urllib.error import HTTPError, URLError

REPO_BASE_URL = "https://comyarus-design.github.io/vk-site"
POSTS_DIR = "posts"
ASSETS_DIR = "assets"
DATA_FILE = "data/posted.json"

POST_TYPES = ["sales", "expert", "motivation", "news", "mixed"]

TYPE_PROMPTS = {
    "sales": "Сделай продающий пост для сообщества ВКонтакте про автоматизацию постинга, роботов и рост эффективности бизнеса. Нужен цепкий заголовок, основной текст и мягкий призыв к действию.",
    "expert": "Сделай экспертный пост для сообщества ВКонтакте про автоматизацию контента, автопостинг, экономию времени и системный рост. Нужен полезный и уверенный тон.",
    "motivation": "Сделай мотивационный пост для сообщества ВКонтакте про роботов, автоматизацию, будущее успеха и движение вперёд. Нужен сильный вдохновляющий тон.",
    "news": "Сделай новостной пост для сообщества ВКонтакте в стиле короткой актуальной заметки про тренд на автоматизацию, ИИ и роботов в продвижении. Без выдуманных фактов и громких неподтверждённых цифр.",
    "mixed": "Сделай смешанный пост для сообщества ВКонтакте: немного пользы, немного мотивации, немного продажи. Тема — роботы, автоматизация постинга и рост результата."
}

SVG_COLORS = {
    "sales": ("#0f172a", "#2563eb", "#38bdf8"),
    "expert": ("#111827", "#0f766e", "#2dd4bf"),
    "motivation": ("#1e1b4b", "#7c3aed", "#c084fc"),
    "news": ("#111827", "#b91c1c", "#f59e0b"),
    "mixed": ("#0b1120", "#1d4ed8", "#22c55e"),
}

def ensure_dirs():
    os.makedirs(POSTS_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)
    os.makedirs("data", exist_ok=True)

def load_posted():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

def save_posted(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def pick_post_type(posted):
    if not posted:
        return POST_TYPES[0]
    count = len(posted)
    return POST_TYPES[count % len(POST_TYPES)]

def slugify(text):
    translit = {
        "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y",
        "к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f",
        "х":"h","ц":"ts","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"
    }
    text = text.lower()
    text = "".join(translit.get(ch, ch) for ch in text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:70] if text else "post"

def call_perplexity(prompt):
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        raise RuntimeError("PERPLEXITY_API_KEY не найден в переменных окружения")

    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты создаёшь посты для сообщества ВКонтакте. "
                    "Пиши на русском языке. "
                    "Структура ответа строго такая:\n"
                    "TITLE: короткий цепкий заголовок\n"
                    "DESCRIPTION: короткое описание до 160 символов\n"
                    "POST: основной текст поста до 1200 символов\n"
                    "IMAGE_TEXT: короткая фраза для обложки до 7 слов"
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.9
    }

    req = request.Request(
        "https://api.perplexity.ai/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            return data["choices"][0]["message"]["content"]
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Ошибка Perplexity API: {e.code} {body}")
    except URLError as e:
        raise RuntimeError(f"Ошибка сети Perplexity API: {e}")

def parse_generation(text):
    title = ""
    description = ""
    post = ""
    image_text = ""

    for line in text.splitlines():
        if line.startswith("TITLE:"):
            title = line.replace("TITLE:", "", 1).strip()
        elif line.startswith("DESCRIPTION:"):
            description = line.replace("DESCRIPTION:", "", 1).strip()
        elif line.startswith("POST:"):
            post = line.replace("POST:", "", 1).strip()
        elif line.startswith("IMAGE_TEXT:"):
            image_text = line.replace("IMAGE_TEXT:", "", 1).strip()

    if not title:
        title = "Роботы — будущее успеха!"
    if not description:
        description = "Автоматизация помогает расти быстрее и делать больше без лишней рутины."
    if not post:
        post = "Роботы берут на себя рутину, а ты концентрируешься на росте, эффективности и результате."
    if not image_text:
        image_text = "Будущее успеха"

    return title, description[:160], post[:1200], image_text[:60]

def wrap_svg_text(text, max_len=18):
    words = text.split()
    lines = []
    current = []

    for w in words:
        test = " ".join(current + [w]).strip()
        if len(test) <= max_len:
            current.append(w)
        else:
            if current:
                lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))
    return lines[:3]

def build_svg(post_type, title, image_text, slug):
    bg, accent1, accent2 = SVG_COLORS[post_type]
    lines = wrap_svg_text(image_text, 18)
    text_y = 250

    text_blocks = []
    for i, line in enumerate(lines):
        y = text_y + i * 70
        safe_line = html.escape(line)
        text_blocks.append(
            f'<text x="100" y="{y}" fill="#ffffff" font-family="Arial, sans-serif" '
            f'font-size="54" font-weight="700">{safe_line}</text>'
        )

    safe_title = html.escape(title[:60])

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{accent1}"/>
      <stop offset="100%" stop-color="{accent2}"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="{bg}"/>
  <circle cx="1020" cy="110" r="120" fill="{accent2}" opacity="0.18"/>
  <circle cx="210" cy="520" r="180" fill="{accent1}" opacity="0.16"/>
  <rect x="70" y="70" width="1060" height="490" rx="34" fill="url(#g)" opacity="0.18"/>
  <text x="100" y="130" fill="#cbd5e1" font-family="Arial, sans-serif" font-size="28" font-weight="700">VK ПРОРЫВ · АВТОПОСТИНГ</text>
  <text x="100" y="185" fill="#e2e8f0" font-family="Arial, sans-serif" font-size="26">{safe_title}</text>
  {''.join(text_blocks)}
  <rect x="100" y="500" width="300" height="54" rx="16" fill="#ffffff" opacity="0.12"/>
  <text x="125" y="535" fill="#ffffff" font-family="Arial, sans-serif" font-size="26" font-weight="700">роботы - будущее успеха!</text>
</svg>'''

def build_html(title, description, post, image_url):
    safe_title = html.escape(title)
    safe_description = html.escape(description)
    safe_post = html.escape(post).replace("\n", "<br>")
    safe_image_url = html.escape(image_url)

    return f'''<!doctype html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
  <meta name="description" content="{safe_description}">
  <meta property="og:title" content="{safe_title}">
  <meta property="og:description" content="{safe_description}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="">
  <meta property="og:image" content="{safe_image_url}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      background: #020617;
      color: #f8fafc;
      padding: 24px;
    }}
    .wrap {{
      max-width: 900px;
      margin: 0 auto;
      background: linear-gradient(180deg, #0f172a, #111827);
      border-radius: 24px;
      padding: 28px;
      box-shadow: 0 20px 50px rgba(0,0,0,0.35);
    }}
    .badge {{
      display: inline-block;
      padding: 8px 14px;
      border-radius: 999px;
      background: #1d4ed8;
      font-size: 13px;
      font-weight: bold;
    }}
    h1 {{
      margin: 18px 0 12px;
      font-size: 36px;
      line-height: 1.15;
    }}
    p {{
      font-size: 18px;
      line-height: 1.7;
      color: #e2e8f0;
    }}
    img {{
      display: block;
      width: 100%;
      height: auto;
      border-radius: 18px;
      margin-top: 20px;
      background: #0f172a;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="badge">VK ПРОРЫВ · Автопостинг</div>
    <h1>{safe_title}</h1>
    <p>{safe_post}</p>
    <img src="{safe_image_url}" alt="{safe_title}">
  </div>
</body>
</html>'''

def main():
    ensure_dirs()
    posted = load_posted()
    post_type = pick_post_type(posted)

    prompt = TYPE_PROMPTS[post_type]
    generation = call_perplexity(prompt)
    title, description, post, image_text = parse_generation(generation)

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d-%H%M%S")
    slug = slugify(title)[:50] + "-" + stamp

    svg_filename = f"{slug}.svg"
    html_filename = f"{slug}.html"

    svg_path = os.path.join(ASSETS_DIR, svg_filename)
    html_path = os.path.join(POSTS_DIR, html_filename)

    image_url = f"{REPO_BASE_URL}/assets/{svg_filename}"
    post_url = f"{REPO_BASE_URL}/posts/{html_filename}"

    svg_content = build_svg(post_type, title, image_text, slug)
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    html_content = build_html(title, description, post, image_url)
    html_content = html_content.replace('<meta property="og:url" content="">', f'<meta property="og:url" content="{html.escape(post_url)}">')
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    posted.append({
        "slug": slug,
        "title": title,
        "description": description,
        "post_text": post,
        "image_text": image_text,
        "post_type": post_type,
        "image_url": image_url,
        "post_url": post_url,
        "created_at_utc": now.isoformat()
    })
    save_posted(posted)

    print(json.dumps({
        "slug": slug,
        "post_type": post_type,
        "title": title,
        "post_url": post_url,
        "image_url": image_url
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()