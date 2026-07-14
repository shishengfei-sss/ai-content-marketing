"""UTM / 落地页参数解析。"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

# UTM source → CRM 来源粗映射（可选）
UTM_SOURCE_TO_CRM = {
    "wechat": "公众号",
    "weixin": "公众号",
    "xiaohongshu": "小红书",
    "xhs": "小红书",
    "douyin": "抖音",
    "tiktok": "抖音",
    "baidu": "官网",
    "google": "官网",
    "webhook": "Webhook",
}


def parse_landing_url(url: str | None) -> dict[str, str | None]:
    if not url or not str(url).strip():
        return {}
    try:
        parsed = urlparse(str(url).strip())
        qs = parse_qs(parsed.query)
    except Exception:
        return {}

    def first(key: str) -> str | None:
        vals = qs.get(key) or []
        return vals[0] if vals else None

    utm_source = first("utm_source")
    utm_medium = first("utm_medium")
    utm_campaign = first("utm_campaign")
    detail_parts = [p for p in (utm_medium, utm_campaign) if p]
    out: dict[str, str | None] = {
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "utm_campaign": utm_campaign,
        "landing_url": str(url).strip()[:500],
    }
    if detail_parts:
        out["source_detail"] = "/".join(detail_parts)[:200]
    if utm_source:
        mapped = UTM_SOURCE_TO_CRM.get(utm_source.lower())
        if mapped:
            out["source"] = mapped
        elif not out.get("source"):
            # 未知 utm_source 写到 source_detail，不强行改 CRM 枚举
            pass
    return out


def merge_utm_into_lead_fields(
    *,
    source: str | None,
    source_detail: str | None,
    utm_source: str | None,
    utm_medium: str | None,
    utm_campaign: str | None,
    landing_url: str | None,
) -> dict:
    parsed = parse_landing_url(landing_url)
    return {
        "source": source or parsed.get("source"),
        "source_detail": source_detail or parsed.get("source_detail"),
        "utm_source": utm_source or parsed.get("utm_source"),
        "utm_medium": utm_medium or parsed.get("utm_medium"),
        "utm_campaign": utm_campaign or parsed.get("utm_campaign"),
        "landing_url": landing_url or parsed.get("landing_url"),
    }
