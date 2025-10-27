"""Helpers for estimating trading fees."""

from __future__ import annotations


DEFAULT_TAKER_FEE_RATE = 0.0003


def estimate_fee(
    filled_size: float,
    average_fill_price: float | None,
    fallback_price: float | None,
    fee_rate: float = DEFAULT_TAKER_FEE_RATE,
) -> float:
    """Estimate fees paid for an order execution.

    Args:
        filled_size: The quantity filled on the order. May be signed.
        average_fill_price: The exchange-reported average fill price.
        fallback_price: A backup price (e.g. limit) when the fill price is unavailable.
        fee_rate: The fee rate applied to notional (default taker fee rate).

    Returns:
        Estimated fee amount in quote currency.
    """

    size = abs(filled_size)
    if size == 0:
        return 0.0

    price = average_fill_price if average_fill_price is not None else fallback_price
    if price is None:
        return 0.0

    return size * price * fee_rate

