"""
Abstract broker interface.

All broker implementations must satisfy this contract.
The trade lifecycle service depends only on this interface,
not on any concrete broker.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class PlaceOrderRequest:
    signal_id: str
    side: OrderSide          # buy (long) or sell (short)
    units: float             # lot size (XAU: 1 lot = 100 oz; pass oz directly for OANDA)
    entry: float             # desired entry price (used for limit orders)
    stop_loss: float
    take_profit: float
    symbol: str = "XAU/USD"


@dataclass
class OrderResult:
    broker_order_id: str
    status: OrderStatus
    fill_price: Optional[float]  # None if not yet filled
    message: str = ""


@dataclass
class PositionState:
    broker_order_id: str
    status: OrderStatus
    fill_price: Optional[float]
    exit_price: Optional[float]
    unrealized_pnl: Optional[float]
    closed_reason: Optional[str]  # "tp_hit", "sl_hit", "manual", None


class BrokerClient(ABC):
    """Abstract base for all broker integrations."""

    @abstractmethod
    async def place_order(self, req: PlaceOrderRequest) -> OrderResult:
        """Submit an entry order. Returns immediately with order ID."""

    @abstractmethod
    async def get_position(self, broker_order_id: str) -> PositionState:
        """Fetch current state of an open position / order."""

    @abstractmethod
    async def close_position(self, broker_order_id: str) -> PositionState:
        """Force-close an open position at market."""

    @abstractmethod
    async def get_account_balance(self) -> float:
        """Return current NAV / account balance in USD."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable broker name, e.g. 'oanda_practice'."""
