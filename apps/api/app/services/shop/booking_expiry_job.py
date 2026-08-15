"""过期未核销：预约时段结束 +15 分钟、次数卡领码后 48 小时仍未核销 → cancelled。

对照 PRD 02-买家端UI.html #m10-cancel-policy · 01 #a07a。
通知买家站内信本批未接通。
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.shop import ShopBooking, ShopServiceSlot
from app.services.shop.fulfillment_service import _now, mark_booking_cancelled
from app.services.shop.service_offer_service import _aware

logger = logging.getLogger(__name__)

SLOT_GRACE = timedelta(minutes=15)
TIMES_CARD_TTL = timedelta(hours=48)


def process_expired_unredeemed_bookings(db: Session) -> int:
    """扫描待服务预约并取消过期未核销；返回取消条数。"""
    now = _now()
    slot_cutoff = now - SLOT_GRACE
    card_cutoff = now - TIMES_CARD_TTL

    slot_rows = (
        db.query(ShopBooking, ShopServiceSlot)
        .join(ShopServiceSlot, ShopBooking.slot_id == ShopServiceSlot.id)
        .filter(ShopBooking.status == "booked")
        .all()
    )
    due: list[ShopBooking] = []
    for b, slot in slot_rows:
        end_at = _aware(slot.end_at)
        if end_at is not None and end_at <= slot_cutoff:
            due.append(b)

    card_rows = (
        db.query(ShopBooking)
        .filter(
            ShopBooking.status == "booked",
            ShopBooking.slot_id.is_(None),
        )
        .all()
    )
    for b in card_rows:
        created = _aware(b.created_at)
        if created is not None and created <= card_cutoff:
            due.append(b)

    if not due:
        return 0

    seen: set = set()
    n = 0
    for b in due:
        if b.id in seen:
            continue
        seen.add(b.id)
        mark_booking_cancelled(db, b, "expired_unredeemed", now=now)
        n += 1
    db.commit()
    logger.info("Expired %s unredeemed booking(s)", n)
    return n
