"""端到端：额度 → proposals（不扣）→ generate（扣 1）"""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def req(method, path, token=None, body=None, params=None):
    url = BASE + path
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = raw
        return e.code, detail


def login(phone, password):
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    if code != 200:
        raise SystemExit(f"login failed {code}: {data}")
    return data["access_token"]


def main():
    print("=== 1. 管理员登录，确认平台 AI 已配置 ===")
    admin_token = login("13800000000", "admin123456")
    code, platform = req("GET", "/admin/platform-llm", token=admin_token)
    if code != 200:
        raise SystemExit(f"get platform failed {code}: {platform}")
    print(f"platform: quota={platform.get('default_free_quota')} masked={platform.get('api_key_masked')}")

    print("\n=== 2. 注册/登录测试租户 ===")
    test_phone = "13900000099"
    test_pass = "test123456"
    code, _ = req(
        "POST",
        "/auth/register",
        body={
            "phone": test_phone,
            "password": test_pass,
            "tenant_name": "E2E测试公司",
            "industry_code": "finance",
            "display_name": "E2E测试",
        },
    )
    if code == 200:
        user_token = login(test_phone, test_pass)
        print("registered new test user")
    else:
        user_token = login(test_phone, test_pass)
        print("using existing test user")

    print("\n=== 3. 查询初始额度 ===")
    code, quota_before = req("GET", "/settings/llm/quota", token=user_token)
    print(f"quota before: {json.dumps(quota_before, ensure_ascii=False)}")
    if code != 200:
        raise SystemExit(f"quota failed: {quota_before}")

    if not quota_before.get("platform_available"):
        raise SystemExit("platform_available 仍为 false，请检查平台 Key 配置")

    print("\n=== 4. POST /content/proposals（应不扣次）===")
    proposals_body = {
        "industry_code": "finance",
        "platform": "wechat",
        "scene": "brand_intro",
        "topic": "2026年稳健理财配置思路",
        "content_format": "article",
        "llm_source": "platform",
    }
    code, proposals = req("POST", "/content/proposals", token=user_token, body=proposals_body)
    print(f"proposals status: {code}")
    if code != 200:
        print("proposals error:", json.dumps(proposals, ensure_ascii=False)[:500])
        raise SystemExit(1)
    print(f"got {len(proposals.get('proposals', []))} proposals, first title:", proposals["proposals"][0]["title"][:60])

    code, quota_after_proposals = req("GET", "/settings/llm/quota", token=user_token)
    print(f"quota after proposals: used={quota_after_proposals['used_count']} remaining={quota_after_proposals['remaining']}")
    if quota_after_proposals["used_count"] != quota_before["used_count"]:
        print("[FAIL] proposals 不应扣次!")
        sys.exit(1)
    print("[OK] proposals 未扣次")

    print("\n=== 5. POST /content/generate（成功应扣 1 次）===")
    selected = proposals["proposals"][0]
    generate_body = {
        **proposals_body,
        "topic": proposals_body["topic"],
        "selected_proposal": selected,
        "llm_source": "platform",
    }
    code, content = req("POST", "/content/generate", token=user_token, body=generate_body)
    print(f"generate status: {code}")
    if code != 200:
        print("generate error:", json.dumps(content, ensure_ascii=False)[:800])
        raise SystemExit(1)
    print(f"content id: {content['id']}, body len: {len(content.get('body', ''))}")
    print(f"body preview: {content.get('body', '')[:120]}...")

    code, quota_after_generate = req("GET", "/settings/llm/quota", token=user_token)
    print(f"quota after generate: used={quota_after_generate['used_count']} remaining={quota_after_generate['remaining']}")
    expected_used = quota_before["used_count"] + 1
    if quota_after_generate["used_count"] != expected_used:
        print(f"[FAIL] 期望 used_count={expected_used}, 实际 {quota_after_generate['used_count']}")
        sys.exit(1)
    if quota_after_generate["remaining"] != quota_before["remaining"] - 1:
        print(f"[FAIL] 期望 remaining={quota_before['remaining'] - 1}")
        sys.exit(1)
    print("[OK] generate 成功扣 1 次")

    print("\n=== E2E 通过 ===")


if __name__ == "__main__":
    main()
