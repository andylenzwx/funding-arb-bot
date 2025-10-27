from funding_arb_bot.strategy.engine import StrategyDecision
from funding_arb_bot.strategy.portfolio import PortfolioManager


def test_allocate_uses_edge_magnitude_for_notional_scaling() -> None:
    manager = PortfolioManager(max_total_notional=100_000, max_symbol_notional=25_000)
    opportunities = [
        StrategyDecision(
            symbol="ETH",
            edge_bps=-30.0,
            direction="long_lighter_short_hl",
            size=10_000,
            action="enter",
        ),
        StrategyDecision(
            symbol="BTC",
            edge_bps=40.0,
            direction="long_hl_short_lighter",
            size=10_000,
            action="enter",
        ),
    ]

    allocations = manager.allocate(opportunities, base_notional=10_000)

    assert len(allocations) == 2
    # Negative edges should still produce positive notional allocations based on magnitude
    assert allocations[0].symbol == "ETH"
    assert allocations[0].allocated_notional > 0
    assert allocations[0].allocated_notional == 15_000

    assert allocations[1].symbol == "BTC"
    assert allocations[1].allocated_notional == 20_000
