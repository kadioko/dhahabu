"""
Position Sizing Service.

Implements volatility-adjusted, risk-constrained position sizing.

Formula:
  base_size = (account_balance * risk_per_trade_pct) / (sl_distance_in_price)

Then apply multipliers:
  - Volatility regime multiplier (reduce in extreme, increase in normal)
  - Strategy-specific risk multiplier (from parameter set)
  - Account exposure cap (ensure total risk does not exceed max_account_risk_pct)
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.core.config import settings
from backend.core.constants import VolatilityRegime
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Volatility regime multipliers for position sizing
_VOL_MULTIPLIERS = {
    VolatilityRegime.LOW: 1.0,
    VolatilityRegime.NORMAL: 1.0,
    VolatilityRegime.HIGH: 0.65,
    VolatilityRegime.EXTREME: 0.35,
}


@dataclass
class SizingResult:
    position_size: float        # Normalized size (e.g. lots or units)
    risk_amount: float          # Dollar risk on this trade
    risk_pct: float             # As fraction of account
    sl_distance: float          # |entry - stop_loss|
    vol_multiplier: float
    capped: bool = False        # Was size capped by exposure limits?
    details: dict | None = None


def compute_position_size(
    entry: float,
    stop_loss: float,
    account_balance: float | None = None,
    risk_per_trade_pct: float | None = None,
    volatility_regime: VolatilityRegime = VolatilityRegime.NORMAL,
    strategy_risk_multiplier: float = 1.0,
    current_exposure_pct: float = 0.0,
) -> SizingResult:
    """
    Compute a risk-controlled position size.

    Args:
        entry: Entry price
        stop_loss: Stop loss price
        account_balance: Account balance (defaults to settings)
        risk_per_trade_pct: Risk fraction per trade (defaults to settings)
        volatility_regime: Current volatility regime
        strategy_risk_multiplier: Strategy-specific multiplier (0.5–1.5 typical)
        current_exposure_pct: Already committed exposure as fraction of account

    Returns:
        SizingResult with computed lot size and risk metrics
    """
    balance = account_balance or settings.account_balance
    base_risk_pct = risk_per_trade_pct or settings.default_risk_per_trade_pct

    sl_distance = abs(entry - stop_loss)
    if sl_distance <= 0:
        logger.warning("position_sizing.zero_sl_distance", entry=entry, stop_loss=stop_loss)
        return SizingResult(
            position_size=0.01,
            risk_amount=0.0,
            risk_pct=0.0,
            sl_distance=0.0,
            vol_multiplier=1.0,
        )

    vol_mult = _VOL_MULTIPLIERS.get(volatility_regime, 1.0)
    effective_risk_pct = base_risk_pct * vol_mult * strategy_risk_multiplier

    # Cap if adding this trade would exceed max account risk
    remaining_risk_budget = settings.max_account_risk_pct - current_exposure_pct
    effective_risk_pct = min(effective_risk_pct, max(remaining_risk_budget, 0.0))
    capped = effective_risk_pct < base_risk_pct * vol_mult * strategy_risk_multiplier

    risk_amount = balance * effective_risk_pct

    # For XAUUSD: 1 standard lot = 100 oz. Price in USD/oz.
    # position_size in lots = risk_amount / (sl_distance * 100)
    # We return a normalized "lot size" — broker execution layer converts.
    position_size = risk_amount / (sl_distance * 100)
    position_size = max(round(position_size, 2), 0.01)  # minimum 0.01 lots

    return SizingResult(
        position_size=position_size,
        risk_amount=round(risk_amount, 2),
        risk_pct=round(effective_risk_pct, 6),
        sl_distance=round(sl_distance, 4),
        vol_multiplier=vol_mult,
        capped=capped,
        details={
            "base_risk_pct": base_risk_pct,
            "vol_multiplier": vol_mult,
            "strategy_multiplier": strategy_risk_multiplier,
            "effective_risk_pct": effective_risk_pct,
            "balance": balance,
        },
    )
