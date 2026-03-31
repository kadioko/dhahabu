"""
Broker factory.

Usage:
    from backend.services.broker import get_broker
    broker = get_broker()

Controlled by BROKER_MODE environment variable:
    paper    → PaperBroker       (default — candle simulation, no real orders)
    oanda    → OandaBroker       (OANDA v20 REST API)
    ctrader  → CTraderBroker     (cTrader Open API — Pepperstone, IC Markets, etc.)
"""

from __future__ import annotations

from functools import lru_cache

from backend.core.config import settings
from backend.services.broker.base import BrokerClient


@lru_cache(maxsize=1)
def get_broker() -> BrokerClient:
    mode = getattr(settings, "broker_mode", "paper").lower()

    if mode == "oanda":
        from backend.services.broker.oanda import OandaBroker
        return OandaBroker(
            api_key=settings.oanda_api_key,
            account_id=settings.oanda_account_id,
            environment=settings.oanda_environment,
        )

    if mode == "ctrader":
        from backend.services.broker.ctrader import CTraderBroker
        return CTraderBroker(
            client_id=settings.ctrader_client_id,
            client_secret=settings.ctrader_client_secret,
            account_id=int(settings.ctrader_account_id),
            access_token=settings.ctrader_access_token,
            environment=settings.ctrader_environment,
        )

    from backend.services.broker.paper import PaperBroker
    return PaperBroker()
