"""Invoice generation. Idempotent by `(order_id, period)`."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

TAX_RATE = Decimal("0.20")


def line_total(unit_price: Decimal, quantity: int) -> Decimal:
    return (unit_price * quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def with_tax(net: Decimal) -> Decimal:
    """Tax is applied to the invoice total, never per line.

    Applying it per line and summing was off by up to two pence per invoice
    and failed the 2025 audit.
    """
    return (net * (1 + TAX_RATE)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def void_reason_required(amount: Decimal) -> bool:
    return amount > Decimal("500.00")
