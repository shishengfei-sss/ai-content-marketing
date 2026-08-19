"""02 金标准写库主路径：打 live API（默认 8003），不用 TestClient。

隔离数据：一次性账号 / 商品 / 订单，禁止动演示单 DEMOPAID0001。
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
import urllib.error
import urllib.request
from pathlib import Path

API_BASE = os.environ.get("UI_TEST_API_BASE", "http://127.0.0.1:8003/api/v1")
MP_BASE_URL = os.environ.get("UI_TEST_MP_BASE_URL", "http://localhost:5174")
MERCHANT_PHONE = os.environ.get("UI_TEST_PHONE", "13900000099")
MERCHANT_PASSWORD = os.environ.get("UI_TEST_PASSWORD", "test123456")
PLATFORM_PHONE = os.environ.get("UI_TEST_PLATFORM_PHONE", "13800000000")
PLATFORM_PASSWORD = os.environ.get("UI_TEST_PLATFORM_PASSWORD", "admin123456")

# 1×1 PNG（真实文件头，给上传组件用）
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def tiny_png_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    Path(path).write_bytes(TINY_PNG)
    return path


def live_json(
    method: str,
    path: str,
    token: str | None = None,
    body: dict | None = None,
    timeout: int = 20,
):
    url = API_BASE + path
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"detail": raw}
        return e.code, payload
    except OSError as e:
        return 0, {"detail": str(e)}


def live_upload(
    path: str,
    token: str,
    *,
    filename: str = "c.png",
    content: bytes = TINY_PNG,
    content_type: str = "image/png",
    fields: dict | None = None,
):
    boundary = "----GoldForm" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for k, v in (fields or {}).items():
        chunks.append(
            (
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n"
            ).encode()
        )
    chunks.append(
        (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\";"
            f' filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'
        ).encode()
        + content
        + b"\r\n"
    )
    chunks.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        API_BASE + path,
        data=b"".join(chunks),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"detail": raw}
        return e.code, payload


def login(phone: str, password: str, workspace_mode: str | None = None) -> str:
    body: dict = {"phone": phone, "password": password}
    if workspace_mode:
        body["workspace_mode"] = workspace_mode
    code, data = live_json("POST", "/auth/login", body=body)
    if code != 200 or not data.get("access_token"):
        raise RuntimeError(f"login failed {code} {data}")
    return data["access_token"]


def register_workspace(tag: str | None = None) -> dict:
    tag = tag or uuid.uuid4().hex[:6]
    phone = "137" + f"{uuid.uuid4().int % 10**8:08d}"
    tenant_name = f"金标工作台{tag}"
    body = {
        "phone": phone,
        "password": "gold123456",
        "tenant_name": tenant_name,
        "display_name": f"金标用户{tag}",
    }
    code, data = live_json("POST", "/auth/register", body=body)
    if code not in (200, 201) or not data.get("access_token"):
        raise RuntimeError(f"register failed {code} {data}")
    token = data["access_token"]
    code_me, me = live_json("GET", "/auth/me", token=token)
    tid = ((me or {}).get("active_tenant") or {}).get("id") if code_me == 200 else None
    return {
        "phone": phone,
        "password": "gold123456",
        "tenant_name": tenant_name,
        "display_name": body["display_name"],
        "token": token,
        "tenant_id": tid,
        "tag": tag,
    }


def merchant_token() -> str:
    return login(MERCHANT_PHONE, MERCHANT_PASSWORD, "merchant")


def admin_token() -> str:
    return login(PLATFORM_PHONE, PLATFORM_PASSWORD, "platform")


def resolve_tenant_id(token: str) -> str:
    code, me = live_json("GET", "/auth/me", token=token)
    if code != 200:
        raise RuntimeError(f"me failed {code} {me}")
    tid = (me.get("active_tenant") or {}).get("id")
    if not tid:
        raise RuntimeError(f"no active tenant {me}")
    return str(tid)


def upload_cover(token: str) -> str:
    code, data = live_upload("/shop/content/files", token)
    if code not in (200, 201) or not data.get("file_url"):
        raise RuntimeError(f"cover upload failed {code} {data}")
    return data["file_url"]


def ensure_published_column(token: str, tag: str) -> str:
    code, col = live_json(
        "POST",
        "/shop/columns",
        token=token,
        body={"title": f"金标专栏-{tag}", "intro": "gold"},
    )
    if code not in (200, 201):
        raise RuntimeError(f"column {code} {col}")
    cid = col["id"]
    code, les = live_json(
        "POST",
        f"/shop/columns/{cid}/lessons",
        token=token,
        body={
            "title": "L1",
            "duration_sec": 60,
            "media_type": "video",
            "media_url": "https://example.com/gold.mp4",
        },
    )
    if code not in (200, 201):
        raise RuntimeError(f"lesson {code} {les}")
    live_json("POST", f"/shop/columns/{cid}/lessons/{les['id']}/publish", token=token)
    live_json("POST", f"/shop/columns/{cid}/publish", token=token)
    return cid


def create_draft_course(token: str, *, name: str | None = None) -> dict:
    tag = uuid.uuid4().hex[:6]
    cover = upload_cover(token)
    col_id = ensure_published_column(token, tag)
    body = {
        "type": "course",
        "name": name or f"金标联测课{tag}",
        "price_cents": 9900,
        "refund_policy": "always_allow",
        "cover_url": cover,
        "ref_type": "column",
        "ref_id": col_id,
    }
    code, data = live_json("POST", "/shop/products", token=token, body=body)
    if code not in (200, 201):
        raise RuntimeError(f"create product {code} {data}")
    return data


def submit_review_leave_pending(token: str, product_id: str) -> str:
    code, data = live_json(
        "POST", f"/shop/products/{product_id}/submit-review", token=token, body={}
    )
    if code != 200:
        raise RuntimeError(f"submit-review {code} {data}")
    rid = data.get("review_id") or data.get("id")
    if not rid:
        raise RuntimeError(f"no review_id {data}")
    return str(rid)


def approve_and_publish(admin: str, merchant: str, product_id: str, review_id: str) -> None:
    code, data = live_json(
        "POST", f"/admin/shop/product-reviews/{review_id}/approve", token=admin, body={}
    )
    if code != 200:
        raise RuntimeError(f"approve review {code} {data}")
    code, data = live_json("POST", f"/shop/products/{product_id}/publish", token=merchant)
    if code != 200 or data.get("status") != "on_sale":
        raise RuntimeError(f"publish {code} {data}")


def create_on_sale_course(merchant: str, admin: str | None = None) -> dict:
    admin = admin or admin_token()
    prod = create_draft_course(merchant)
    rid = submit_review_leave_pending(merchant, prod["id"])
    approve_and_publish(admin, merchant, prod["id"], rid)
    prod["review_id"] = rid
    prod["status"] = "on_sale"
    return prod


def create_isolated_paid_order() -> dict:
    """经营中商家下一笔可退已付单；独立 openid，不碰演示课。"""
    merchant = merchant_token()
    admin = admin_token()
    tenant_id = resolve_tenant_id(merchant)
    prod = create_on_sale_course(merchant, admin)
    openid = f"gold_buyer_{uuid.uuid4().hex[:8]}"
    code, auth = live_json(
        "POST",
        "/mp/shop/auth/login",
        body={"tenant_id": tenant_id, "code": f"mock:{openid}"},
    )
    if code != 200:
        raise RuntimeError(f"buyer login {code} {auth}")
    buyer = auth["access_token"]
    mobile = "136" + f"{uuid.uuid4().int % 10**8:08d}"
    live_json("POST", "/mp/shop/auth/bind", token=buyer, body={"mobile": mobile})
    code, created = live_json(
        "POST", "/mp/shop/orders", token=buyer, body={"product_id": prod["id"]}
    )
    order = (created or {}).get("order") or created
    if code not in (200, 201) or not order.get("id"):
        raise RuntimeError(f"create order {code} {created}")
    code, paid = live_json(
        "POST", f"/mp/shop/orders/{order['id']}/pay", token=buyer, body={}
    )
    paid_order = (paid or {}).get("order") or paid
    if code != 200 or paid_order.get("status") != "paid":
        raise RuntimeError(f"pay {code} {paid}")
    return {
        "tenant_id": tenant_id,
        "openid": openid,
        "buyer_token": buyer,
        "product_id": prod["id"],
        "product_name": prod.get("name"),
        "order_id": paid_order.get("id") or order["id"],
        "order_no": paid_order.get("order_no") or order.get("order_no"),
        "merchant_token": merchant,
    }
