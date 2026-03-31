"""
OANDA v20 REST API broker implementation.

Docs: https://developer.oanda.com/rest-live-v20/introduction/
Practice account: https://fxpractice.oanda.com
Live account: https://fxtrade.oanda.com

XAU_USD on OANDA is quoted in USD per troy oz.
1 unit = 1 troy oz (so position_size in lots → multiply by 100 for OANDA units,
since 1 standard lot = 100 oz in XAUUSD).

Environment variables required:
  OANDA_API_KEY      — Bearer token from your OANDA account
  OANDA_ACCOUNT_ID   — e.g. "001-001-1234567-001"
  OANDA_ENVIRONMENT  — "practice" (default) or "live"
"""

from __future__ import annotations

import asyncio
from typing import Optional

import httpx

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

_BASE_URLS = {
    "practice": "https://api-fxpractice.oanda.com/v3",
    "live": "https://api-fxtrade.oanda.com/v3",
}

_INSTRUMENT = "XAU_USD"
_LOT_TO_UNITS = 100  # 1 standard lot = 100 troy oz on OANDA


class OandaBroker(BrokerClient):
    def __init__(self, api_key: str, account_id: str, environment: str = "practice"):
        if environment not in _BASE_URLS:
            raise ValueError(f"environment must be 'practice' or 'live', got {environment!r}")
        self._api_key = api_key
        self._account_id = account_id
        self._base_url = _BASE_URLS[environment]
        self._env = environment
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @property
    def name(self) -> str:
        return f"oanda_{self._env}"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=15.0,
        )

    async def place_order(self, req: PlaceOrderRequest) -> OrderResult:
        """
        Place a market order with attached SL and TP on OANDA.

        OANDA uses 'units': positive = buy (long), negative = sell (short).
        We attach stop-loss and take-profit as on-fill orders so OANDA manages
        them server-side — no polling needed for exits.
        """
        units = req.units * _LOT_TO_UNITS
        if req.side == OrderSide.SELL:
            units = -units

        payload = {
            "order": {
                "type": "MARKET",
                "instrument": _INSTRUMENT,
                "units": str(int(units)),
                "timeInForce": "FOK",  # Fill-or-Kill
                "stopLossOnFill": {
                    "price": f"{req.stop_loss:.5f}",
                    "timeInForce": "GTC",
                },
                "takeProfitOnFill": {
                    "price": f"{req.take_profit:.5f}",
                    "timeInForce": "GTC",
                },
                "clientExtensions": {
                    "id": req.signal_id[:24],  # OANDA: max 24 chars
                    "comment": "dhahabu",
                },
            }
        }

        async with self._client() as client:
            resp = await client.post(
                f"/accounts/{self._account_id}/orders",
                json=payload,
            )

        if resp.status_code not in (200, 201):
            msg = resp.text[:300]
            logger.error("oanda.place_order.failed", status=resp.status_code, body=msg)
            return OrderResult(
                broker_order_id="",
                status=OrderStatus.REJECTED,
                fill_price=None,
                message=msg,
            )

        data = resp.json()
        fill = data.get("orderFillTransaction") or data.get("relatedTransactionIDs")
        trade_id = ""
        fill_price = None

        if "orderFillTransaction" in data:
            tx = data["orderFillTransaction"]
            trade_id = tx.get("tradeOpened", {}).get("tradeID", "")
            fill_price = float(tx.get("price", 0)) or None

        logger.info(
            "oanda.place_order.ok",
            trade_id=trade_id,
            fill_price=fill_price,
            signal_id=req.signal_id,
        )
        return OrderResult(
            broker_order_id=trade_id,
            status=OrderStatus.FILLED if trade_id else OrderStatus.PENDING,
            fill_price=fill_price,
        )

    async def get_position(self, broker_order_id: str) -> PositionState:
        """Fetch trade state from OANDA."""
        async with self._client() as client:
            resp = await client.get(
                f"/accounts/{self._account_id}/trades/{broker_order_id}"
            )

        if resp.status_code == 404:
            # Trade may be closed — check transaction history
            return await self._get_closed_trade(broker_order_id)

        if resp.status_code != 200:
            logger.warning("oanda.get_position.error", status=resp.status_code, id=broker_order_id)
            return PositionState(
                broker_order_id=broker_order_id,
                status=OrderStatus.PENDING,
                fill_price=None,
                exit_price=None,
                unrealized_pnl=None,
                closed_reason=None,
            )

        trade = resp.json().get("trade", {})
        state = trade.get("state", "OPEN")
        fill_price = float(trade.get("price", 0)) or None
        unrealized_pnl = float(trade.get("unrealizedPL", 0))

        return PositionState(
            broker_order_id=broker_order_id,
            status=OrderStatus.FILLED if state == "OPEN" else OrderStatus.CANCELLED,
            fill_price=fill_price,
            exit_price=None,
            unrealized_pnl=unrealized_pnl,
            closed_reason=None,
        )

    async def _get_closed_trade(self, broker_order_id: str) -> PositionState:
        """Look up a closed trade in OANDA's transaction history."""
        async with self._client() as client:
            resp = await client.get(
                f"/accounts/{self._account_id}/trades/{broker_order_id}",
                params={"state": "CLOSED"},
            )

        if resp.status_code != 200:
            return PositionState(
                broker_order_id=broker_order_id,
                status=OrderStatus.CANCELLED,
                fill_price=None,
                exit_price=None,
                unrealized_pnl=None,
                closed_reason="unknown",
            )

        trade = resp.json().get("trade", {})
        fill_price = float(trade.get("price", 0)) or None
        exit_price = float(trade.get("averageClosePrice", 0)) or None
        realized_pnl = float(trade.get("realizedPL", 0))

        # Determine closed_reason from close transactions
        close_txns = trade.get("closingTransactionIDs", [])
        closed_reason = _infer_close_reason(trade, realized_pnl)

        return PositionState(
            broker_order_id=broker_order_id,
            status=OrderStatus.CANCELLED,  # closed
            fill_price=fill_price,
            exit_price=exit_price,
            unrealized_pnl=realized_pnl,
            closed_reason=closed_reason,
        )

    async def close_position(self, broker_order_id: str) -> PositionState:
        """Force-close an open position at market."""
        async with self._client() as client:
            resp = await client.put(
                f"/accounts/{self._account_id}/trades/{broker_order_id}/close"
            )

        if resp.status_code not in (200, 201):
            logger.error("oanda.close_position.failed", status=resp.status_code, id=broker_order_id)
            return await self.get_position(broker_order_id)

        tx = resp.json().get("orderFillTransaction", {})
        exit_price = float(tx.get("price", 0)) or None
        pnl = float(tx.get("pl", 0))

        logger.info("oanda.close_position.ok", id=broker_order_id, exit_price=exit_price, pnl=pnl)
        return PositionState(
            broker_order_id=broker_order_id,
            status=OrderStatus.CANCELLED,
            fill_price=None,
            exit_price=exit_price,
            unrealized_pnl=pnl,
            closed_reason="manual_close",
        )

    async def get_account_balance(self) -> float:
        async with self._client() as client:
            resp = await client.get(f"/accounts/{self._account_id}/summary")

        if resp.status_code != 200:
            logger.warning("oanda.get_balance.failed", status=resp.status_code)
            return 0.0

        return float(resp.json().get("account", {}).get("NAV", 0))


def _infer_close_reason(trade: dict, realized_pnl: float) -> str:
    """Best-effort: determine if closed by TP, SL, or expiry."""
    # OANDA doesn't label the reason directly on the trade object;
    # a positive PnL close usually = TP, negative = SL.
    # For a more accurate check you'd need to fetch individual transactions.
    if realized_pnl > 0:
        return "tp_hit"
    if realized_pnl < 0:
        return "sl_hit"
    return "expired"
