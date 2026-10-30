"""内网演示入口基址与仓库 IP 一致性。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.shop_demo_urls import demo_origins, h5_link, web_link

_REPO_ROOT = Path(__file__).resolve().parents[3]
_INTRANET_HOST = "192.168.10.201"
_LEGACY_HOST = "192.168.20.201"

_CONFIG_PATHS_NO_LEGACY = (
    _REPO_ROOT / "apps/mp/.env.production",
    _REPO_ROOT / "apps/api/.env.example",
    _REPO_ROOT / "apps/api/tests/shop_demo_urls.py",
)


def test_demo201_preset_points_to_intranet_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHOP_DEMO_ENV", "demo201")
    monkeypatch.delenv("SHOP_DEMO_H5_ORIGIN", raising=False)
    monkeypatch.delenv("SHOP_DEMO_WEB_ORIGIN", raising=False)
    h5, web = demo_origins()
    assert h5 == f"http://{_INTRANET_HOST}:8089"
    assert web == f"http://{_INTRANET_HOST}:8088"
    assert _LEGACY_HOST not in h5_link("/shop")
    assert _LEGACY_HOST not in web_link("/login")


def test_key_configs_use_intranet_host() -> None:
    hits: list[str] = []
    for path in _CONFIG_PATHS_NO_LEGACY:
        assert path.is_file(), f"missing {path}"
        text = path.read_text(encoding="utf-8")
        if _LEGACY_HOST in text:
            hits.append(str(path.relative_to(_REPO_ROOT)))
    assert not hits, hits

    rule = (_REPO_ROOT / ".cursor/rules/git-push-production.mdc").read_text(encoding="utf-8")
    assert f"shengfei@{_INTRANET_HOST}:/opt/git/" in rule


def test_demo_origins_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SHOP_DEMO_ENV", raising=False)
    monkeypatch.setenv("SHOP_DEMO_H5_ORIGIN", "http://example:1")
    monkeypatch.setenv("SHOP_DEMO_WEB_ORIGIN", "http://example:2")
    assert demo_origins() == ("http://example:1", "http://example:2")
