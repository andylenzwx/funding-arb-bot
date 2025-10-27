from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Tuple

from funding_arb_bot.exchanges.base import ExchangeClient, OrderRequest, OrderResult
from funding_arb_bot.execution.reconciliation import apply_correction, check_fills

logger = logging.getLogger(__name__)


@dataclass
class DualLegIntent:
    leg_a: OrderRequest
    leg_b: OrderRequest


@dataclass
class ExecutionResult:
    """Enhanced result including fill reconciliation."""

    primary: OrderResult
    hedge: OrderResult
    is_balanced: bool
    imbalance: float


class ExecutionError(Exception):
    def __init__(self, leg: str, error: Exception, partial: Tuple[OrderResult | None, OrderResult | None]) -> None:
        super().__init__(str(error))
        self.leg = leg
        self.partial = partial
        self.original = error


class ExecutionRouter:
    def __init__(self, primary: ExchangeClient, hedge: ExchangeClient, auto_reconcile: bool = True) -> None:
        self._primary = primary
        self._hedge = hedge
        self._auto_reconcile = auto_reconcile

    async def execute(self, intent: DualLegIntent) -> ExecutionResult:
        primary_task = asyncio.create_task(self._primary.place_order(intent.leg_a))
        hedge_task = asyncio.create_task(self._hedge.place_order(intent.leg_b))

        results = await asyncio.gather(primary_task, hedge_task, return_exceptions=True)
        primary_result: OrderResult | None = None
        hedge_result: OrderResult | None = None
        primary_exc: Exception | None = None
        hedge_exc: Exception | None = None

        if isinstance(results[0], Exception):
            primary_exc = results[0]
        else:
            primary_result = results[0]

        if isinstance(results[1], Exception):
            hedge_exc = results[1]
        else:
            hedge_result = results[1]

        if primary_exc or hedge_exc:
            await self._handle_failure(primary_result, hedge_result, primary_exc, hedge_exc)

        # Check fill reconciliation
        reconciliation = check_fills(
            primary_result,
            hedge_result,
            intent.leg_a.size,
            intent.leg_b.size,
            tolerance=0.02,  # 2% imbalance triggers correction
        )

        logger.info(
            "execution.fills",
            extra={
                "primary_filled": reconciliation.primary_filled,
                "hedge_filled": reconciliation.hedge_filled,
                "imbalance": reconciliation.imbalance,
                "needs_correction": reconciliation.needs_correction,
            },
        )

        # Apply correction if needed and enabled
        if reconciliation.needs_correction and self._auto_reconcile:
            try:
                if reconciliation.primary_filled > reconciliation.hedge_filled:
                    await apply_correction(reconciliation, intent.leg_a.symbol, self._primary, self._hedge, "hedge")
                else:
                    await apply_correction(reconciliation, intent.leg_a.symbol, self._primary, self._hedge, "primary")
            except Exception as e:
                logger.error("reconciliation_failed", extra={"error": str(e)})

        return ExecutionResult(
            primary=primary_result,
            hedge=hedge_result,
            is_balanced=not reconciliation.needs_correction,
            imbalance=reconciliation.imbalance,
        )

    async def _handle_failure(
        self,
        primary_result: OrderResult | None,
        hedge_result: OrderResult | None,
        primary_exc: Exception | None,
        hedge_exc: Exception | None,
    ) -> None:
        if primary_exc and hedge_exc:
            combined = RuntimeError(
                f"primary_leg_failed: {primary_exc}; hedge_leg_failed: {hedge_exc}"
            )
            raise ExecutionError("parallel", combined, (primary_result, hedge_result)) from combined

        if primary_exc:
            await self._attempt_cancel(self._hedge, hedge_result)
            raise ExecutionError("primary", primary_exc, (primary_result, hedge_result)) from primary_exc

        if hedge_exc:
            await self._attempt_cancel(self._primary, primary_result)
            raise ExecutionError("hedge", hedge_exc, (primary_result, hedge_result)) from hedge_exc

    async def _attempt_cancel(self, exchange: ExchangeClient, result: OrderResult | None) -> None:
        if result is None:
            return
        try:
            await exchange.cancel_order(result.exchange_order_id)
        except Exception:
            # Cancellation best-effort; log upstream
            pass


