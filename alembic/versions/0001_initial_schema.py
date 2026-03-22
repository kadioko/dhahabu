"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2026-03-22 00:00:00

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── candles ───────────────────────────────────────────────────────────────
    op.create_table(
        "candles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("source", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_candles_symbol_tf_ts", "candles", ["symbol", "timeframe", "timestamp"])
    op.create_index("ix_candles_timestamp", "candles", ["timestamp"])

    # ── strategy_parameters ───────────────────────────────────────────────────
    op.create_table(
        "strategy_parameters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_name", sa.String(50), nullable=False),
        sa.Column("parameter_json", JSONB, nullable=False),
        sa.Column("source_window", sa.String(20), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="candidate"),
        sa.Column("is_live", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("overfit_flag", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("suppressed_flag", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discard_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sp_strategy_live", "strategy_parameters", ["strategy_name", "is_live"])

    # ── signals ───────────────────────────────────────────────────────────────
    op.create_table(
        "signals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_name", sa.String(50), nullable=False),
        sa.Column("parameter_set_id", sa.String(36),
                  sa.ForeignKey("strategy_parameters.id"), nullable=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("entry", sa.Float(), nullable=False),
        sa.Column("stop_loss", sa.Float(), nullable=False),
        sa.Column("take_profit", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rationale_json", JSONB, nullable=True),
        sa.Column("brain_score", sa.Float(), nullable=True),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("suppression_reason", sa.Text(), nullable=True),
        sa.Column("risk_metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_signals_strategy_created", "signals", ["strategy_name", "created_at"])
    op.create_index("ix_signals_approval", "signals", ["approval_status"])
    op.create_index("ix_signals_symbol_created", "signals", ["symbol", "created_at"])

    # ── trades ────────────────────────────────────────────────────────────────
    op.create_table(
        "trades",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("signal_id", sa.String(36), sa.ForeignKey("signals.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("stop_loss", sa.Float(), nullable=False),
        sa.Column("take_profit", sa.Float(), nullable=False),
        sa.Column("position_size", sa.Float(), nullable=False, server_default="0.01"),
        sa.Column("pnl", sa.Float(), nullable=True),
        sa.Column("pnl_pct", sa.Float(), nullable=True),
        sa.Column("closed_reason", sa.String(30), nullable=True),
        sa.Column("consecutive_loss_seq_snapshot", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trades_status", "trades", ["status"])
    op.create_index("ix_trades_signal_id", "trades", ["signal_id"])
    op.create_index("ix_trades_entry_time", "trades", ["entry_time"])

    # ── backtest_runs ─────────────────────────────────────────────────────────
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_name", sa.String(50), nullable=False),
        sa.Column("parameter_set_id", sa.String(36),
                  sa.ForeignKey("strategy_parameters.id"), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("profit_factor", sa.Float(), nullable=True),
        sa.Column("sharpe_score", sa.Float(), nullable=True),
        sa.Column("expectancy", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("metrics_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_br_strategy_created", "backtest_runs", ["strategy_name", "created_at"])
    op.create_index("ix_br_param_set", "backtest_runs", ["parameter_set_id"])

    # ── walk_forward_runs ─────────────────────────────────────────────────────
    op.create_table(
        "walk_forward_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_name", sa.String(50), nullable=False),
        sa.Column("parameter_set_id", sa.String(36), nullable=False),
        sa.Column("train_ratio", sa.Float(), nullable=False),
        sa.Column("test_ratio", sa.Float(), nullable=False),
        sa.Column("train_metrics_json", JSONB, nullable=True),
        sa.Column("test_metrics_json", JSONB, nullable=True),
        sa.Column("oos_degradation_score", sa.Float(), nullable=True),
        sa.Column("overfit_flag", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("oos_collapse_details", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_wfr_strategy_created", "walk_forward_runs", ["strategy_name", "created_at"])

    # ── monte_carlo_runs ──────────────────────────────────────────────────────
    op.create_table(
        "monte_carlo_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_name", sa.String(50), nullable=False),
        sa.Column("parameter_set_id", sa.String(36), nullable=False),
        sa.Column("source_backtest_run_id", sa.String(36),
                  sa.ForeignKey("backtest_runs.id"), nullable=False),
        sa.Column("simulation_count", sa.Integer(), nullable=False),
        sa.Column("robustness_score", sa.Float(), nullable=False),
        sa.Column("random_beats_original", sa.Float(), nullable=False),
        sa.Column("pass_flag", sa.Boolean(), nullable=False),
        sa.Column("distribution_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_mcr_strategy_created", "monte_carlo_runs", ["strategy_name", "created_at"])

    # ── optimization_runs ─────────────────────────────────────────────────────
    op.create_table(
        "optimization_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_name", sa.String(50), nullable=False),
        sa.Column("combos_tested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("winner_parameter_set_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("metrics_json", JSONB, nullable=True),
        sa.Column("all_results_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_or_strategy_created", "optimization_runs", ["strategy_name", "created_at"])

    # ── risk_events ───────────────────────────────────────────────────────────
    op.create_table(
        "risk_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_re_type_created", "risk_events", ["event_type", "created_at"])

    # ── daily_pnl_snapshots ───────────────────────────────────────────────────
    op.create_table(
        "daily_pnl_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("date", sa.String(10), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False, server_default="XAU/USD"),
        sa.Column("realized_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("realized_pnl_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("max_drawdown", sa.Float(), nullable=False, server_default="0"),
        sa.Column("trade_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("win_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("loss_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trading_blocked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dpnl_date_symbol", "daily_pnl_snapshots", ["date", "symbol"])

    # ── system_state ──────────────────────────────────────────────────────────
    op.create_table(
        "system_state",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("component_name", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("health_score", sa.Float(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── scheduler_job_runs ────────────────────────────────────────────────────
    op.create_table(
        "scheduler_job_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_name", sa.String(100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="started"),
        sa.Column("details_json", JSONB, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_sjr_job_started", "scheduler_job_runs", ["job_name", "started_at"])

    # ── audit_events ──────────────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("actor", sa.String(50), nullable=False, server_default="system"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ae_event_type_created", "audit_events", ["event_type", "created_at"])
    op.create_index("ix_ae_entity_type_id", "audit_events", ["entity_type", "entity_id"])

    # ── telegram_delivery_logs ────────────────────────────────────────────────
    op.create_table(
        "telegram_delivery_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("signal_id", sa.String(36), sa.ForeignKey("signals.id"), nullable=True),
        sa.Column("message_type", sa.String(50), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("delivered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("telegram_message_id", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tdl_signal_id", "telegram_delivery_logs", ["signal_id"])

    # ── shutdown_events ───────────────────────────────────────────────────────
    op.create_table(
        "shutdown_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("trigger_value", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
    )
    op.create_index("ix_se_active", "shutdown_events", ["active"])


def downgrade() -> None:
    op.drop_table("shutdown_events")
    op.drop_table("telegram_delivery_logs")
    op.drop_table("audit_events")
    op.drop_table("scheduler_job_runs")
    op.drop_table("system_state")
    op.drop_table("daily_pnl_snapshots")
    op.drop_table("risk_events")
    op.drop_table("optimization_runs")
    op.drop_table("monte_carlo_runs")
    op.drop_table("walk_forward_runs")
    op.drop_table("backtest_runs")
    op.drop_table("trades")
    op.drop_table("signals")
    op.drop_table("strategy_parameters")
    op.drop_table("candles")
