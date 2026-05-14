import os
import json
import mimetypes
import uuid
from urllib import request, parse
from urllib.error import HTTPError, URLError

DATA_FILE = "data/posted.json"
VK_API_VERSION = "5.199"
IMAGE_FILE = "image.png"

def load_posted():
    if not os.path.exists(DATA_FILE):
        raise RuntimeError("Файл data/posted.json не найден")
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not data:
        raise RuntimeError("В data/posted.json нет постов для публикации")
    return data

def vk_api_call(method_name, params):
    token = os.getenv("VK_COMMUNITY_TOKEN")
    if not token:
        raise RuntimeError("VK_COMMUNITY_TOKEN не найден")

    payload = dict(params)
    payload["access_token"] = token
    payload["v"] = VK_API_VERSION

    data = parse.urlencode(payload).encode("utf-8")
    req = request.Request(
        f"https://api.vk.com/method/{method_name}",
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
        raise RuntimeError(f"Ошибка VK API ({method_name}): {json.dumps(result['error'], ensure_ascii=False)}")

    return result["response"]

def get_wall_upload_server(group_id):
    return vk_api_call("photos.getWallUploadServer", {
        "group_id": group_id
    })

def upload_file_to_vk(upload_url, file_path):
    if not os.path.exists(file_path):
        raise RuntimeError(f"Файл изображения не найден: {file_path}")

    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
    content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

    with open(file_path, "rb") as f:
        file_data = f.read()

    body = []
    body.append(f"--{boundary}".encode("utf-8"))
    body.append(
        f'Content-Disposition: form-data; name="photo"; filename="{os.path.basename(file_path)}"'.encode("utf-8")
    )
    body.append(f"Content-Type: {content_type}".encode("utf-8"))
    body.append(b"")
    body.append(file_data)
    body.append(f"--{boundary}--".encode("utf-8"))
    body.append(b"")

    data = b"\r\n".join(body)

    req = request.Request(
        upload_url,
        data=data,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        },
        method="POST"
    )

    try:
        with request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Ошибка загрузки файла в VK HTTP {e.code}: {body}")
    except URLError as e:
        raise RuntimeError(f"Ошибка сети при загрузке файла в VK: {e}")

def save_wall_photo(group_id, upload_result):
    params = {
        "group_id": group_id,
        "photo": upload_result["photo"],
        "server": upload_result["server"],
        "hash": upload_result["hash"]
    }
    response = vk_api_call("photos.saveWallPhoto", params)

    if not response or not isinstance(response, list):
        raise RuntimeError("photos.saveWallPhoto не вернул массив с фотографией")

    return response[0]

def vk_wall_post(message, attachment):
    group_id = os.getenv("VK_GROUP_ID")
    if not group_id:
        raise RuntimeError("VK_GROUP_ID не найден")

    owner_id = f"-{group_id}"

    payload = {
        "owner_id": owner_id,
        "from_group": 1,
        "message": message,
        "attachments": attachment
    }

    return vk_api_call("wall.post", payload)

def main():
    group_id = os.getenv("VK_GROUP_ID")
    if not group_id:
        raise RuntimeError("VK_GROUP_ID не найден")

    posted = load_posted()
    last_post = posted[-1]

    if last_post.get("vk_published"):
        raise RuntimeError("Последний пост уже опубликован в VK")

    post_text = last_post["post_text"].strip()
    link = last_post["post_url"].strip()
    message = f"{post_text}\n\nПодробнее: {link}"

    upload_server = get_wall_upload_server(group_id)
    upload_result = upload_file_to_vk(upload_server["upload_url"], IMAGE_FILE)
    saved_photo = save_wall_photo(group_id, upload_result)

    attachment = f"photo{saved_photo['owner_id']}_{saved_photo['id']}"
    response = vk_wall_post(message, attachment)

    last_post["vk_published"] = True
    last_post["vk_post_id"] = response.get("post_id")
    last_post["vk_photo_attachment"] = attachment
    last_post["vk_response"] = response

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(posted, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "status": "ok",
        "vk_post_id": response.get("post_id"),
        "attachment": attachment,
        "link": link
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
