"""HTTP / 鉴权 / 测试数据辅助。

所有请求都走本机后端（config.BASE_URL）。注册即用 mock SMS（无需真实短信），
因为后端 SMS_PROVIDER=mock、验证码固定 1111，但注册接口本身用密码，不依赖短信。
"""
import random
import time

import httpx
from jose import jwt

from config import BASE_URL, API_PREFIX, JWT_SECRET, TEST_PASSWORD, \
    PLATFORM_ADMIN_PHONE, PLATFORM_ADMIN_PASSWORD

_state = {"n": 0}


def req(method, path, token=None, json=None, params=None, files=None, data=None, timeout=120):
    url = BASE_URL + API_PREFIX + path
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if json is not None and files is None and data is None:
        headers["Content-Type"] = "application/json"
    try:
        r = httpx.request(method, url, headers=headers, json=json,
                          params=params, files=files, data=data, timeout=timeout)
        try:
            body = r.json()
        except Exception:
            body = r.text
        return r.status_code, body
    except httpx.HTTPError as e:
        return -1, str(e)


def new_phone():
    # 11 位手机号：前缀 13 + 5位时间尾数 + 4位随机，避免重跑与历史数据冲突
    return "13" + f"{int(time.time()) % 100000:05d}{random.randint(0, 9999):04d}"


def register(tenant_name="自动化租户"):
    """注册一个新租户+用户，返回 (token, phone, error)。

    租户名（公司名）后端要求全局唯一，故追加时间+随机后缀避免重跑冲突。
    """
    p = new_phone()
    tn = f"{tenant_name}-{int(time.time() * 1000) % 100000}-{random.randint(0, 9999)}"
    code, body = req("POST", "/auth/register", json={
        "phone": p,
        "password": TEST_PASSWORD,
        "tenant_name": tn,
        "industry_code": "it",
        "display_name": "自动化测试员",
    })
    if code != 200 or not isinstance(body, dict) or not body.get("access_token"):
        return None, p, f"register {code}: {body}"
    return body["access_token"], p, None


def login(phone, password=TEST_PASSWORD):
    code, body = req("POST", "/auth/login", json={"phone": phone, "password": password})
    if code == 200 and isinstance(body, dict):
        return body.get("access_token")
    return None


def admin_login():
    """以平台管理员身份登录，返回 (token, error)。"""
    code, body = req("POST", "/auth/login", json={
        "phone": PLATFORM_ADMIN_PHONE, "password": PLATFORM_ADMIN_PASSWORD})
    if code == 200 and isinstance(body, dict) and body.get("access_token"):
        return body["access_token"], None
    return None, f"admin login code={code}: {body}"


def expired_token():
    """生成一个已经过期的 JWT（用开发密钥签名，后端能验出过期）。"""
    return jwt.encode({"sub": "x", "iat": 0, "exp": 1}, JWT_SECRET, algorithm="HS256")


def first_territory(token):
    """获取（并触发默认播种）租户的销售区域，返回第一个区域 id。

    建线索/客户等单据要求销售区域，后端会在首次 GET 时自动种入默认区域。
    """
    code, body = req("GET", "/crm/territories", token=token)
    if code == 200 and isinstance(body, list) and body:
        return body[0].get("id")
    return None


def stream_lines(method, path, token=None, json=None, timeout=120):
    """SSE 流式请求，返回 (status_code, [data 行列表])。"""
    url = BASE_URL + API_PREFIX + path
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if json is not None:
        headers["Content-Type"] = "application/json"
    lines = []
    with httpx.stream(method, url, headers=headers, json=json, timeout=timeout) as r:
        for line in r.iter_lines():
            if line.startswith("data:"):
                lines.append(line[5:].strip())
        return r.status_code, lines
