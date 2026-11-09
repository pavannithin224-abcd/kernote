"""The order state machine. Nothing else may mutate `order.status`."""

from __future__ import annotations

from enum import StrEnum


class OrderStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PICKED = "picked"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.DRAFT: {OrderStatus.SUBMITTED, OrderStatus.CANCELLED},
    OrderStatus.SUBMITTED: {OrderStatus.PICKED, OrderStatus.CANCELLED},
    OrderStatus.PICKED: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


class IllegalTransition(ValueError):
    """Raised when a caller asks for a transition the machine forbids."""


def assert_can_transition(current: OrderStatus, target: OrderStatus) -> None:
    if target not in TRANSITIONS[current]:
        raise IllegalTransition(f"{current} cannot become {target}")


def is_terminal(status: OrderStatus) -> bool:
    return not TRANSITIONS[status]
