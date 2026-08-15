"""微信支付集成（stub / production 骨架）。对照执行计划 M3-2。"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from typing import Any

from app.config import settings


def stub_sign(order_no: str, transaction_id: str, amount_cents: int, api_key: str) -> str:
    raw = f"{order_no}|{transaction_id}|{int(amount_cents)}|{api_key}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_stub_sign(
    order_no: str, transaction_id: str, amount_cents: int, api_key: str, sign: str | None
) -> bool:
    if not sign:
        return False
    expected = stub_sign(order_no, transaction_id, amount_cents, api_key)
    return hmac.compare_digest(expected, sign)


class WeChatPayService:
    """统一下单 / 验签 / 查单 / 退款。默认 stub。"""

    def __init__(self, mode: str | None = None):
        self.mode = (mode or settings.WECHAT_PAY_MODE or "stub").lower()
        if settings.WECHAT_PAY_MOCK == "1":
            self.mode = "stub"

    @property
    def is_stub(self) -> bool:
        return self.mode == "stub"

    def create_prepay(
        self,
        *,
        order_no: str,
        amount_cents: int,
        description: str,
        openid: str | None,
        wx_app_id: str,
        wx_mch_id: str,
        api_key: str,
        notify_url: str | None = None,
    ) -> dict[str, Any]:
        if self.is_stub:
            prepay_id = f"wx_stub_{uuid.uuid4().hex[:16]}"
            return {
                "mode": "stub",
                "prepay_id": prepay_id,
                "appId": wx_app_id or settings.WECHAT_PAY_APPID or "wx_mock_appid_001",
                "timeStamp": "1710000000",
                "nonceStr": uuid.uuid4().hex[:16],
                "package": f"prepay_id={prepay_id}",
                "signType": "RSA",
                "paySign": stub_sign(order_no, prepay_id, amount_cents, api_key or "mock"),
                "mch_id": wx_mch_id or settings.WECHAT_PAY_MCHID or "mock_mchid_001",
                "out_trade_no": order_no,
                "amount_cents": amount_cents,
                "description": description,
                "openid": openid,
                "notify_url": notify_url,
            }
        # production：骨架，未配置证书时拒绝
        raise NotImplementedError("WECHAT_PAY_MODE=production 需进件与证书（B-M3）")

    def verify_notify(
        self,
        *,
        order_no: str,
        transaction_id: str,
        paid_amount_cents: int,
        sign: str | None,
        api_key: str,
    ) -> dict[str, Any] | None:
        if self.is_stub:
            if not verify_stub_sign(order_no, transaction_id, paid_amount_cents, api_key, sign):
                return None
            return {
                "order_no": order_no,
                "transaction_id": transaction_id,
                "paid_amount_cents": paid_amount_cents,
                "trade_state": "SUCCESS",
            }
        return None

    def query_order(self, *, order_no: str, amount_cents: int) -> dict[str, Any]:
        if self.is_stub:
            tx = f"mock_txn_{hashlib.md5(order_no.encode()).hexdigest()[:20]}"
            return {
                "code": "SUCCESS",
                "trade_state": "SUCCESS",
                "transaction_id": tx,
                "out_trade_no": order_no,
                "amount": {"total": amount_cents, "currency": "CNY"},
            }
        raise NotImplementedError("production query 未配置")

    def refund(
        self, *, order_no: str, refund_no: str, refund_amount_cents: int, total_amount_cents: int
    ) -> dict[str, Any]:
        if self.is_stub:
            return {
                "code": "SUCCESS",
                "refund_id": f"mock_refund_{uuid.uuid4().hex[:16]}",
                "out_refund_no": refund_no,
                "refund_status": "SUCCESS",
                "amount": {
                    "refund": refund_amount_cents,
                    "total": total_amount_cents,
                    "currency": "CNY",
                },
            }
        raise NotImplementedError("production refund 未配置")


wechat_pay_service = WeChatPayService()
