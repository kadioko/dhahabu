"""
Paper broker — wraps the existing candle-simulation logic.

When BROKER_MODE=paper (default), this is used instead of a real broker.
All order management is handled by the trade_lifecycle service's candle-
driven state machine — this class is a no-op passthrough that returns
placeholder IDs so the rest of the interface works uniformly.
"""

from __future__ import annotations

import uuid

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.services.broker.base import (
    BrokerClient,
    OrderResult,
    OrderSide,
    OrderStatus,
    PlaceOrderRequest,
    PositionState,
)

logger = get_logger(__name__)


class PaperBroker(BrokerClient):
    """
    Simulated broker. Orders are 'filled' immediately with a synthetic ID.
    The actual P&L simulation happens in trade_lifecycle/service.py via candles.
    """

    @property
    def name(self) -> str:
        return "paper"

    async def place_order(self, req: PlaceOrderRequest) -> OrderResult:
        order_id = f"paper-{uuid.uuid4().hex[:12]}"
        logger.info(
            "paper_broker.order_placed",
            order_id=order_id,
            side=req.side,
            entry=req.entry,
            sl=req.stop_loss,
            tp=req.take_profit,
        )
        return OrderResult(
            broker_order_id=order_id,
            status=OrderStatus.FILLED,
            fill_price=req.entry,
            message="paper fill",
        )

    async def get_position(self, broker_order_id: str) -> PositionState:
        # Paper broker doesn't track live positions — lifecycle service handles it
        return PositionState(
            broker_order_id=broker_order_id,
            status=OrderStatus.FILLED,
            fill_price=None,
            exit_price=None,
            unrealized_pnl=None,
            closed_reason=None,
        )

    async def close_position(self, broker_order_id: str) -> PositionState:
        return PositionState(
            broker_order_id=broker_order_id,
            status=OrderStatus.CANCELLED,
            fill_price=None,
            exit_price=None,
            unrealized_pnl=None,
            closed_reason="manual_close",
        )

    async def get_account_balance(self) -> float:
        return settings.account_balance
