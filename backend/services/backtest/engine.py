"""
Backtest Engine.

Runs a strategy against historical candle data over a specified window.
Produces trade-level results and aggregated metrics.

This is a pure simulation engine — no live execution occurs here.
Metrics produced:
  - total_trades, win_rate, profit_factor, sharpe_score, expectancy, max_drawdown
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from backend.core.constants import MarketRegime, StrategyName, Timeframe, VolatilityRegime
from backend.core.logging import get_logger
from backend.strategies.base import BaseStrategy, StrategyContext, StrategySignal

logger = get_logger(__name__)


@dataclass
class BacktestTrade:
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    entry_bar: int
    exit_bar: Optional[int] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    closed_reason: str = ""


@dataclass
class BacktestResult:
    strategy_name: str
    parameter_set_id: Optional[str]
    window_days: int
    start_at: datetime
    end_at: datetime
    trades: list[BacktestTrade] = field(default_factory=list)

    # Aggregated metrics
    total_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_score: float = 0.0
    expectancy: float = 0.0
    max_drawdown: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    total_pnl: float = 0.0

    def compute_metrics(self) -> None:
        """Compute all aggregate metrics from trade list."""
        if not self.trades:
            return

        closed = [t for t in self.trades if t.exit_bar is not None]
        self.total_trades = len(closed)
        if not closed:
            return

        pnls = [t.pnl for t in closed]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        self.win_count = len(wins)
        self.loss_count = len(losses)
        self.win_rate = self.win_count / self.total_trades if self.total_trades > 0 else 0.0
        self.gross_profit = sum(wins)
        self.gross_loss = abs(sum(losses))
        self.profit_factor = self.gross_profit / self.gross_loss if self.gross_loss > 0 else float("inf")
        self.total_pnl = sum(pnls)
        self.expectancy = self.total_pnl / self.total_trades

        # Sharpe-like score: mean(pnl) / std(pnl) * sqrt(N)
        if len(pnls) > 1:
            mean_pnl = np.mean(pnls)
            std_pnl = np.std(pnls, ddof=1)
            if std_pnl > 0:
                self.sharpe_score = (mean_pnl / std_pnl) * np.sqrt(len(pnls))

        # Max drawdown on cumulative PnL curve
        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        self.max_drawdown = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

    def to_metrics_dict(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 4) if self.profit_factor != float("inf") else 999.0,
            "sharpe_score": round(self.sharpe_score, 4),
            "expectancy": round(self.expectancy, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "gross_profit": round(self.gross_profit, 2),
            "gross_loss": round(self.gross_loss, 2),
            "total_pnl": round(self.total_pnl, 2),
            "win_count": self.win_count,
            "loss_count": self.loss_count,
        }


def run_backtest(
    strategy: BaseStrategy,
    candles: dict[Timeframe, pd.DataFrame],
    window_days: int,
    parameter_set_id: Optional[str] = None,
    risk_free_rate: float = 0.045,
) -> BacktestResult:
    """
    Run a walk-over-data backtest for the given strategy and candle slice.

    Uses bar-by-bar simulation:
      1. At each bar, run strategy.generate_signals()
      2. If signal, simulate execution on subsequent bars
      3. Check SL/TP on each subsequent bar
      4. Accumulate trades and metrics

    Returns BacktestResult with full trade history.
    """
    if not candles:
        return BacktestResult(
            strategy_name=strategy.name.value,
            parameter_set_id=parameter_set_id,
            window_days=window_days,
            start_at=datetime.utcnow(),
            end_at=datetime.utcnow(),
        )

    # Use H1 as primary simulation timeframe
    primary_tf = Timeframe.H1
    if primary_tf not in candles:
        primary_tf = list(candles.keys())[0]

    primary_df = candles[primary_tf]
    if len(primary_df) < 30:
        return BacktestResult(
            strategy_name=strategy.name.value,
            parameter_set_id=parameter_set_id,
            window_days=window_days,
            start_at=datetime.utcnow(),
            end_at=datetime.utcnow(),
        )

    start_at = primary_df.index[0].to_pydatetime()
    end_at = primary_df.index[-1].to_pydatetime()
    result = BacktestResult(
        strategy_name=strategy.name.value,
        parameter_set_id=parameter_set_id,
        window_days=window_days,
        start_at=start_at,
        end_at=end_at,
    )

    open_trade: Optional[BacktestTrade] = None
    min_bars = 30  # Start generating signals only after warmup

    for i in range(min_bars, len(primary_df)):
        # Build sub-candles for this bar
        bar_candles = {
            tf: df.iloc[:i] for tf, df in candles.items()
            if len(df.iloc[:i]) >= 15
        }
        if not bar_candles:
            continue

        current_bar = primary_df.iloc[i]
        current_high = float(current_bar["high"])
        current_low = float(current_bar["low"])
        current_close = float(current_bar["close"])

        # Check open trade first
        if open_trade is not None:
            direction = open_trade.direction
            tp_hit = (
                (direction == "long" and current_high >= open_trade.take_profit) or
                (direction == "short" and current_low <= open_trade.take_profit)
            )
            sl_hit = (
                (direction == "long" and current_low <= open_trade.stop_loss) or
                (direction == "short" and current_high >= open_trade.stop_loss)
            )

            if sl_hit and tp_hit:
                sl_hit = True
                tp_hit = False

            if tp_hit:
                open_trade.exit_bar = i
                open_trade.exit_price = open_trade.take_profit
                if direction == "long":
                    open_trade.pnl = (open_trade.take_profit - open_trade.entry) * 100 * 0.01
                else:
                    open_trade.pnl = (open_trade.entry - open_trade.take_profit) * 100 * 0.01
                open_trade.closed_reason = "tp_hit"
                result.trades.append(open_trade)
                open_trade = None

            elif sl_hit:
                open_trade.exit_bar = i
                open_trade.exit_price = open_trade.stop_loss
                if direction == "long":
                    open_trade.pnl = (open_trade.stop_loss - open_trade.entry) * 100 * 0.01
                else:
                    open_trade.pnl = (open_trade.entry - open_trade.stop_loss) * 100 * 0.01
                open_trade.closed_reason = "sl_hit"
                result.trades.append(open_trade)
                open_trade = None

            # Skip signal generation if trade is open
            continue

        # Generate signals for this bar
        ctx = StrategyContext(
            symbol="XAU/USD",
            candles=bar_candles,
            volatility_regime=VolatilityRegime.NORMAL,
            market_regime=MarketRegime.CHOPPY,
            atr=0.0,
            current_price=current_close,
        )

        try:
            signals = strategy.generate_signals(ctx)
        except Exception:
            continue

        if signals:
            sig = signals[0]
            open_trade = BacktestTrade(
                direction=sig.direction.value,
                entry=sig.entry,
                stop_loss=sig.stop_loss,
                take_profit=sig.take_profit,
                entry_bar=i,
            )

    # Close any open trade at end of data
    if open_trade is not None:
        last_close = float(primary_df["close"].iloc[-1])
        open_trade.exit_bar = len(primary_df) - 1
        open_trade.exit_price = last_close
        d = open_trade.direction
        open_trade.pnl = (
            (last_close - open_trade.entry) * 100 * 0.01
            if d == "long"
            else (open_trade.entry - last_close) * 100 * 0.01
        )
        open_trade.closed_reason = "end_of_data"
        result.trades.append(open_trade)

    result.compute_metrics()
    logger.debug(
        "backtest.complete",
        strategy=strategy.name.value,
        window_days=window_days,
        trades=result.total_trades,
        win_rate=round(result.win_rate, 3),
        profit_factor=round(result.profit_factor, 3) if result.profit_factor != float("inf") else 999,
    )
    return result
