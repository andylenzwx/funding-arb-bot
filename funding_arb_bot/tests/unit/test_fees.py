from funding_arb_bot.execution.fees import DEFAULT_TAKER_FEE_RATE, estimate_fee


def test_estimate_fee_prefers_average_fill_price() -> None:
    fee = estimate_fee(10, 100.0, None)
    assert fee == 10 * 100.0 * DEFAULT_TAKER_FEE_RATE


def test_estimate_fee_falls_back_to_limit_price_when_fill_missing() -> None:
    fee = estimate_fee(5, None, 200.0)
    assert fee == 5 * 200.0 * DEFAULT_TAKER_FEE_RATE


def test_estimate_fee_handles_negative_size_and_missing_price() -> None:
    fee = estimate_fee(-3, None, None)
    assert fee == 0.0
