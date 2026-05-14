import os
import json
from urllib import request, parse
from urllib.error import HTTPError, URLError

DATA_FILE = "data/posted.json"
VK_API_VERSION = "5.199"

def load_posted():
    if not os.path.exists(DATA_FILE):
        raise RuntimeError("Файл data/posted.json не найден")
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not data:
        raise RuntimeError("В data/posted.json нет постов для публикации")
    return data

def vk_wall_post(message):
    token = os.getenv("VK_COMMUNITY_TOKEN")
    group_id = os.getenv("VK_GROUP_ID")

    if not token:
        raise RuntimeError("VK_COMMUNITY_TOKEN не найден")
    if not group_id:
        raise RuntimeError("VK_GROUP_ID не найден")

    owner_id = f"-{group_id}"

    payload = {
        "owner_id": owner_id,
        "from_group": 1,
        "message": message,
        "access_token": token,
        "v": VK_API_VERSION
    }

    data = parse.urlencode(payload).encode("utf-8")
    req = request.Request(
        "https://api.vk.com/method/wall.post",
        data=data,
        method="POST"
    )

    try:
        with request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            result = json.loads(raw)
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Ошибка VK API HTTP {e.code}: {body}")
    except URLError as e:
        raise RuntimeError(f"Ошибка сети VK API: {e}")

    if "error" in result:
        raise RuntimeError(f"Ошибка VK API: {json.dumps(result['error'], ensure_ascii=False)}")

    return result["response"]

def main():
    posted = load_posted()
    last_post = posted[-1]

    if last_post.get("vk_published"):
        raise RuntimeError("Последний пост уже опубликован в VK")

    link = last_post["post_url"].strip()
    post_text = last_post["post_text"].strip()

    message = f"{post_text}\n\n{link}"

    response = vk_wall_post(message)

    last_post["vk_published"] = True
    last_post["vk_post_id"] = response.get("post_id")
    last_post["vk_response"] = response

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(posted, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "status": "ok",
        "vk_post_id": response.get("post_id"),
        "link": link
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
