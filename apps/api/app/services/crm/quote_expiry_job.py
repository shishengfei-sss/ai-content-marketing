"""报价过期 Job：sent/accepted 且未转单、valid_until 已过 → expired。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.crm import Quote

logger = logging.getLogger(__name__)


def process_quote_expiry(db: Session) -> int:
    """扫描并标记过期报价；返回更新条数。"""
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Quote)
        .filter(
            Quote.deleted_at.is_(None),
            Quote.status.in_(("sent", "accepted")),
            Quote.valid_until.isnot(None),
            Quote.valid_until < now,
            Quote.converted_order_id.is_(None),
        )
        .all()
    )
    if not rows:
        return 0
    for q in rows:
        q.status = "expired"
    db.commit()
    logger.info("Marked %s quote(s) expired", len(rows))
    return len(rows)
