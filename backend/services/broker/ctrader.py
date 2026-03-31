"""
cTrader Open API broker implementation.

Uses the official `ctrader-open-api` Python library (Spotware/OpenApiPy).
The library is Twisted-based, so we run the Twisted reactor in a dedicated
daemon thread and bridge Twisted Deferreds ↔ asyncio Futures via thread-safe
call scheduling.

Setup (one-time, per cTrader broker like Pepperstone or IC Markets):
  1. Register a developer application at https://openapi.ctrader.com
     → You receive a client_id and client_secret
  2. Authorise your trading account via the OAuth2 flow at:
     https://connect.spotware.com/apps/{client_id}/auth?redirect_uri=...&scope=trading
     → You receive an access_token for that account
  3. Find your account ID via ProtoOAGetAccountListByAccessTokenReq or the
     cTrader desktop: Menu → Account → Copy Account ID
  4. Set environment variables (see .env.example)

Environment variables:
  CTRADER_CLIENT_ID      — from developer app registration
  CTRADER_CLIENT_SECRET  — from developer app registration
  CTRADER_ACCOUNT_ID     — numeric trading account ID
  CTRADER_ACCESS_TOKEN   — OAuth access token for this account
  CTRADER_ENVIRONMENT    — "demo" (default) or "live"
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from typing import Optional

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

# cTrader volume unit: 1 lot = 100 units (centilots)
# For XAUUSD: 1 standard lot = 100 troy oz; position_size is in lots
_LOT_TO_CENTILOTS = 100


class CTraderBroker(BrokerClient):
    """
    cTrader Open API broker. Works with any cTrader-based broker
    (Pepperstone, IC Markets, FXPro, etc.).

    Thread model:
      - Twisted reactor runs in a background daemon thread (_reactor_thread)
      - FastAPI asyncio loop calls methods like `place_order` normally
      - Bridge: reactor.callFromThread() submits work to Twisted
                loop.call_soon_threadsafe() resolves asyncio Futures from Twisted
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        account_id: int,
        access_token: str,
        environment: str = "demo",
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._account_id = account_id
        self._access_token = access_token
        self._environment = environment

        self._client = None          # ctrader_open_api.Client
        self._reactor_thread = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ready_event = threading.Event()
        self._authenticated = False

        # symbol name → symbolId cache (resolved once on first use)
        self._symbol_id_cache: dict[str, int] = {}

    @property
    def name(self) -> str:
        return f"ctrader_{self._environment}"

    # ── Internal Twisted ↔ asyncio bridge ────────────────────────────────────

    def _ensure_started(self):
        """Start the Twisted reactor thread if not already running."""
        if self._reactor_thread and self._reactor_thread.is_alive():
            return
        self._loop = asyncio.get_event_loop()
        self._reactor_thread = threading.Thread(
            target=self._run_reactor, daemon=True, name="ctrader-reactor"
        )
        self._reactor_thread.start()
        # Wait up to 30s for the auth handshake to complete
        if not self._ready_event.wait(timeout=30):
            raise TimeoutError("cTrader: failed to authenticate within 30 seconds")

    def _run_reactor(self):
        """Entry point for the Twisted reactor thread."""
        from twisted.internet import reactor
        reactor.callLater(0, self._connect)
        reactor.run(installSignalHandlers=False)

    def _connect(self):
        """Called inside Twisted thread: set up cTrader client and connect."""
        from ctrader_open_api import Client, TcpProtocol, EndPoints

        if self._environment == "live":
            host = EndPoints.PROTOBUF_LIVE_HOST
        else:
            host = EndPoints.PROTOBUF_DEMO_HOST

        self._client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)

        @self._client.on("connected")
        def on_connected(client):
            self._send_app_auth()

        @self._client.on("disconnected")
        def on_disconnected(client, reason):
            logger.warning("ctrader.disconnected", reason=str(reason))
            self._authenticated = False
            # Reconnect after 5 seconds
            from twisted.internet import reactor
            reactor.callLater(5, self._client.startService)

        self._client.startService()

    def _send_app_auth(self):
        """Authenticate the application (client_id / client_secret)."""
        from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAAuthReq

        req = ProtoOAAuthReq()
        req.clientId = self._client_id
        req.clientSecret = self._client_secret

        d = self._client.send(req)
        d.addCallback(self._on_app_authed)
        d.addErrback(lambda f: logger.error("ctrader.app_auth.failed", error=str(f)))

    def _on_app_authed(self, response):
        """App is authed; now authorise the trading account."""
        from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAAccountAuthReq

        req = ProtoOAAccountAuthReq()
        req.ctidTraderAccountId = self._account_id
        req.accessToken = self._access_token

        d = self._client.send(req)
        d.addCallback(self._on_account_authed)
        d.addErrback(lambda f: logger.error("ctrader.account_auth.failed", error=str(f)))

    def _on_account_authed(self, response):
        logger.info("ctrader.authenticated", account_id=self._account_id, env=self._environment)
        self._authenticated = True
        self._ready_event.set()

    def _deferred_to_future(self, deferred) -> asyncio.Future:
        """
        Wrap a Twisted Deferred in an asyncio Future.
        Safe to call from either thread.
        """
        future: asyncio.Future = self._loop.create_future()

        def on_result(result):
            self._loop.call_soon_threadsafe(future.set_result, result)

        def on_error(failure):
            exc = Exception(str(failure.getErrorMessage()))
            self._loop.call_soon_threadsafe(future.set_exception, exc)

        deferred.addCallback(on_result)
        deferred.addErrback(on_error)
        return future

    async def _twisted_send(self, message) -> object:
        """Send a protobuf message to cTrader and await the response."""
        self._ensure_started()
        future: asyncio.Future = self._loop.create_future()

        def _send_in_reactor():
            d = self._client.send(message)
            d.addCallback(lambda r: self._loop.call_soon_threadsafe(future.set_result, r))
            d.addErrback(
                lambda f: self._loop.call_soon_threadsafe(
                    future.set_exception, Exception(str(f.getErrorMessage()))
                )
            )

        from twisted.internet import reactor
        reactor.callFromThread(_send_in_reactor)
        return await asyncio.wait_for(future, timeout=15.0)

    # ── Symbol resolution ─────────────────────────────────────────────────────

    async def _resolve_symbol_id(self, symbol: str) -> int:
        """
        Resolve a symbol name (e.g. "XAUUSD") to its cTrader symbolId.
        Result is cached after the first call.
        """
        normalised = symbol.replace("/", "").replace(" ", "").upper()  # "XAU/USD" → "XAUUSD"

        if normalised in self._symbol_id_cache:
            return self._symbol_id_cache[normalised]

        from ctrader_open_api.messages.OpenApiMessages_pb2 import (
            ProtoOASymbolsListReq,
        )

        req = ProtoOASymbolsListReq()
        req.ctidTraderAccountId = self._account_id

        resp = await self._twisted_send(req)
        for sym in resp.symbol:
            # Cache all symbols while we're here
            self._symbol_id_cache[sym.symbolName.upper()] = sym.symbolId

        if normalised not in self._symbol_id_cache:
            raise ValueError(
                f"cTrader: symbol {normalised!r} not found for account {self._account_id}. "
                "Check the symbol name matches your broker's cTrader terminal."
            )

        return self._symbol_id_cache[normalised]

    # ── BrokerClient interface ────────────────────────────────────────────────

    async def place_order(self, req: PlaceOrderRequest) -> OrderResult:
        """
        Place a market order on cTrader with attached stop-loss and take-profit.

        cTrader uses:
          volume in centilots: 1 lot = 100, 0.1 lot = 10, 0.01 lot = 1
          stopLoss / takeProfit as absolute prices
          tradeSide: BUY = 1, SELL = 2
        """
        from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOANewOrderReq
        from ctrader_open_api.messages.OpenApiModelMessages_pb2 import (
            ProtoOAOrderType,
            ProtoOATradeSide,
        )

        try:
            symbol_id = await self._resolve_symbol_id(req.symbol)
        except Exception as exc:
            logger.error("ctrader.place_order.symbol_resolve_failed", error=str(exc))
            return OrderResult(
                broker_order_id="",
                status=OrderStatus.REJECTED,
                fill_price=None,
                message=str(exc),
            )

        order = ProtoOANewOrderReq()
        order.ctidTraderAccountId = self._account_id
        order.symbolId = symbol_id
        order.orderType = ProtoOAOrderType.Value("MARKET")
        order.tradeSide = (
            ProtoOATradeSide.Value("BUY")
            if req.side == OrderSide.BUY
            else ProtoOATradeSide.Value("SELL")
        )
        order.volume = int(req.units * _LOT_TO_CENTILOTS)
        order.stopLoss = req.stop_loss
        order.takeProfit = req.take_profit
        order.comment = f"dhahabu:{req.signal_id[:16]}"

        try:
            resp = await self._twisted_send(order)
        except Exception as exc:
            logger.error("ctrader.place_order.send_failed", error=str(exc))
            return OrderResult(
                broker_order_id="",
                status=OrderStatus.REJECTED,
                fill_price=None,
                message=str(exc),
            )

        # ProtoOAExecutionEvent carries the filled order/position details
        position_id = str(getattr(getattr(resp, "position", None), "positionId", "") or "")
        fill_price = None
        if hasattr(resp, "order") and resp.order:
            fill_price = resp.order.executionPrice or None
        if fill_price is None and hasattr(resp, "position") and resp.position:
            fill_price = resp.position.price or None

        logger.info(
            "ctrader.order_placed",
            position_id=position_id,
            fill_price=fill_price,
            signal_id=req.signal_id,
        )
        return OrderResult(
            broker_order_id=position_id,
            status=OrderStatus.FILLED if position_id else OrderStatus.PENDING,
            fill_price=float(fill_price) if fill_price else None,
        )

    async def get_position(self, broker_order_id: str) -> PositionState:
        """Fetch current state of a position via ProtoOAReconcileReq."""
        from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAReconcileReq

        req = ProtoOAReconcileReq()
        req.ctidTraderAccountId = self._account_id

        try:
            resp = await self._twisted_send(req)
        except Exception as exc:
            logger.warning("ctrader.get_position.failed", error=str(exc))
            return PositionState(
                broker_order_id=broker_order_id,
                status=OrderStatus.PENDING,
                fill_price=None,
                exit_price=None,
                unrealized_pnl=None,
                closed_reason=None,
            )

        for pos in resp.position:
            if str(pos.positionId) == broker_order_id:
                return PositionState(
                    broker_order_id=broker_order_id,
                    status=OrderStatus.FILLED,
                    fill_price=float(pos.price),
                    exit_price=None,
                    unrealized_pnl=float(pos.swap + pos.commission),
                    closed_reason=None,
                )

        # Not found in open positions — it has been closed
        return PositionState(
            broker_order_id=broker_order_id,
            status=OrderStatus.CANCELLED,
            fill_price=None,
            exit_price=None,
            unrealized_pnl=None,
            closed_reason="closed_by_broker",
        )

    async def close_position(self, broker_order_id: str) -> PositionState:
        """Force-close an open position at market price."""
        from ctrader_open_api.messages.OpenApiMessages_pb2 import (
            ProtoOAClosePositionReq,
        )

        # We need to know the current volume to close it — fetch first
        current = await self.get_position(broker_order_id)
        if current.status == OrderStatus.CANCELLED:
            return current  # already closed

        req = ProtoOAClosePositionReq()
        req.ctidTraderAccountId = self._account_id
        req.positionId = int(broker_order_id)
        req.volume = 0  # 0 = close entire position

        try:
            resp = await self._twisted_send(req)
            exit_price = None
            if hasattr(resp, "order") and resp.order:
                exit_price = float(resp.order.executionPrice or 0) or None

            logger.info("ctrader.close_position.ok", position_id=broker_order_id)
            return PositionState(
                broker_order_id=broker_order_id,
                status=OrderStatus.CANCELLED,
                fill_price=current.fill_price,
                exit_price=exit_price,
                unrealized_pnl=None,
                closed_reason="manual_close",
            )
        except Exception as exc:
            logger.error("ctrader.close_position.failed", error=str(exc))
            return current

    async def get_account_balance(self) -> float:
        """Return account balance in USD via ProtoOATraderReq."""
        from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOATraderReq

        req = ProtoOATraderReq()
        req.ctidTraderAccountId = self._account_id

        try:
            resp = await self._twisted_send(req)
            # balance is in cents (e.g. $10,000 = 1000000)
            return float(resp.trader.balance) / 100.0
        except Exception as exc:
            logger.warning("ctrader.get_balance.failed", error=str(exc))
            return 0.0
