"""共享价税引擎（v1.5）：行级独立取整 + 头折摊入 + 平衡 + ±0.01 末行税额尾差。

报价 / 订单保存路径应共用本模块，禁止第二套取整公式。
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence


TWOPLACES = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")


def money(value: Decimal | float | int | str | None) -> Decimal:
    """四舍五入到分。"""
    if value is None:
        return ZERO
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    return d.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TaxLineIn:
    unit_price: Decimal | float | int
    quantity: Decimal | float | int = 1
    discount_rate: Decimal | float | int | None = None  # 行折扣 %
    tax_rate: Decimal | float | int | None = None  # 税率 %


@dataclass
class TaxLineOut:
    line_total: Decimal  # 行未税（头折后）
    tax_amount: Decimal
    line_incl_tax: Decimal
    tax_rate: Decimal | None
    # 调试/分摊前
    line_total_before_header: Decimal = ZERO


@dataclass
class TaxComputeResult:
    lines: list[TaxLineOut]
    total_ex_tax: Decimal
    tax_total: Decimal
    amount_incl_tax: Decimal
    exact_tax: Decimal
    tail_delta: Decimal  # 写入末行的税额调整，0 / ±0.01


def _line_ex_before_header(ln: TaxLineIn) -> Decimal:
    price = money(ln.unit_price)
    qty = ln.quantity if isinstance(ln.quantity, Decimal) else Decimal(str(ln.quantity))
    disc = Decimal(str(ln.discount_rate or 0))
    factor = HUNDRED - disc
    # round(price * qty * (1 - disc/100), 2)
    raw = price * qty * factor / HUNDRED
    return money(raw)


def _apportion_header_discount(
    line_exs: list[Decimal],
    header_discount_rate: Decimal | float | int | None,
) -> list[Decimal]:
    """头折%按行未税占比摊入；末行吃分摊尾差，保证 Σ 后 = round(Σ前 × (1-头折%), 2)。"""
    if not line_exs:
        return []
    hdr = Decimal(str(header_discount_rate or 0))
    if hdr <= 0:
        return list(line_exs)

    subtotal = money(sum(line_exs, ZERO))
    if subtotal <= 0:
        return [ZERO for _ in line_exs]

    target = money(subtotal * (HUNDRED - hdr) / HUNDRED)
    out: list[Decimal] = []
    allocated = ZERO
    for i, ex in enumerate(line_exs):
        if i < len(line_exs) - 1:
            # 按比例：round(ex / subtotal * target, 2)
            part = money(ex * target / subtotal)
            out.append(part)
            allocated += part
        else:
            out.append(money(target - allocated))
    return out


def _exact_tax(lines_ex: Sequence[Decimal], rates: Sequence[Decimal | None]) -> Decimal:
    """精确税额：中间项不按行先 round，最后一次 round 到分。

    单税率时等价 round(总未税 × rate/100, 2)。
    """
    acc = Decimal("0")
    for ex, rate in zip(lines_ex, rates):
        if rate is None:
            continue
        r = Decimal(str(rate))
        if r == 0:
            continue
        acc += ex * r / HUNDRED
    return money(acc)


def compute_tax_lines(
    lines: Sequence[TaxLineIn],
    *,
    header_discount_rate: Decimal | float | int | None = None,
) -> TaxComputeResult:
    """计算明细价税并做 ±0.01 末行税额尾差兜底。"""
    if not lines:
        return TaxComputeResult(
            lines=[],
            total_ex_tax=ZERO,
            tax_total=ZERO,
            amount_incl_tax=ZERO,
            exact_tax=ZERO,
            tail_delta=ZERO,
        )

    before = [_line_ex_before_header(ln) for ln in lines]
    after = _apportion_header_discount(before, header_discount_rate)
    rates: list[Decimal | None] = []
    outs: list[TaxLineOut] = []

    for ln, ex0, ex1 in zip(lines, before, after):
        rate: Decimal | None
        if ln.tax_rate is None:
            rate = None
            tax_amt = ZERO
        else:
            rate = Decimal(str(ln.tax_rate))
            tax_amt = money(ex1 * rate / HUNDRED) if rate else ZERO
        rates.append(rate)
        outs.append(
            TaxLineOut(
                line_total=ex1,
                tax_amount=tax_amt,
                line_incl_tax=money(ex1 + tax_amt),
                tax_rate=rate,
                line_total_before_header=ex0,
            )
        )

    exact = _exact_tax(after, rates)
    tax_sum = money(sum((o.tax_amount for o in outs), ZERO))
    delta = money(exact - tax_sum)

    # 仅 ±0.01 自动找平；写入最后一行（优先有税率的行，否则最后一行）
    if abs(delta) == TWOPLACES and outs:
        idx = len(outs) - 1
        for i in range(len(outs) - 1, -1, -1):
            if outs[i].tax_rate is not None and outs[i].tax_rate != 0:
                idx = i
                break
        last = outs[idx]
        last.tax_amount = money(last.tax_amount + delta)
        last.line_incl_tax = money(last.line_total + last.tax_amount)
        tax_sum = money(sum((o.tax_amount for o in outs), ZERO))
    else:
        delta = ZERO

    total_ex = money(sum((o.line_total for o in outs), ZERO))
    incl = money(total_ex + tax_sum)
    return TaxComputeResult(
        lines=outs,
        total_ex_tax=total_ex,
        tax_total=tax_sum,
        amount_incl_tax=incl,
        exact_tax=exact,
        tail_delta=delta,
    )


def split_untaxed_unit_price(
    list_price: Decimal | float | int,
    tax_rate: Decimal | float | int | None,
    *,
    price_includes_tax: bool,
) -> Decimal:
    """选品：含税标价拆未税单价。"""
    price = money(list_price)
    if not price_includes_tax or tax_rate is None:
        return price
    rate = Decimal(str(tax_rate))
    if rate <= 0:
        return price
    return money(price / (HUNDRED + rate) * HUNDRED)
