"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        # Profile
        sa.Column("is_active", sa.Boolean(), nullable=True, default=True),
        sa.Column("is_superuser", sa.Boolean(), nullable=True, default=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        # Trading settings
        sa.Column("paper_trading", sa.Boolean(), nullable=True, default=True),
        sa.Column("initial_balance", sa.Float(), nullable=True, default=10000.0),
        sa.Column("current_balance", sa.Float(), nullable=True, default=10000.0),
        # Risk management
        sa.Column("max_daily_loss_percent", sa.Float(), nullable=True, default=5.0),
        sa.Column("daily_loss_paused", sa.Boolean(), nullable=True, default=False),
        sa.Column("daily_loss_reset_at", sa.DateTime(), nullable=True),
        # Binance Testnet (encriptados)
        sa.Column("binance_testnet_api_key", sa.String(512), nullable=True),
        sa.Column("binance_testnet_secret_key", sa.String(512), nullable=True),
        # Binance Real (encriptados)
        sa.Column("binance_real_api_key", sa.String(512), nullable=True),
        sa.Column("binance_real_secret_key", sa.String(512), nullable=True),
        # DeepSeek (encriptado)
        sa.Column("deepseek_api_key", sa.String(512), nullable=True),
        sa.Column("deepseek_enabled", sa.Boolean(), nullable=True, default=False),
        # SMTP
        sa.Column("smtp_host", sa.String(255), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=True),
        sa.Column("smtp_user", sa.String(255), nullable=True),
        sa.Column("smtp_password", sa.String(512), nullable=True),  # encriptado
        sa.Column("smtp_from_email", sa.String(255), nullable=True),
        sa.Column("smtp_enabled", sa.Boolean(), nullable=True, default=False),
        # Telegram (encriptado)
        sa.Column("telegram_bot_token", sa.String(512), nullable=True),
        sa.Column("telegram_chat_id", sa.String(100), nullable=True),
        sa.Column("telegram_enabled", sa.Boolean(), nullable=True, default=False),
        # Profile info
        sa.Column("profile_name", sa.String(100), nullable=True),
        sa.Column("summary_email", sa.String(255), nullable=True),
        sa.Column("phone_number", sa.String(50), nullable=True),
        sa.Column("platform_user_id", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "strategies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("strategy_type", sa.String(50), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("symbols", sa.Text(), nullable=True),
        sa.Column("max_trade_amount", sa.Float(), nullable=True, default=100.0),
        sa.Column("stop_loss_percent", sa.Float(), nullable=True, default=2.0),
        sa.Column("take_profit_percent", sa.Float(), nullable=True, default=3.0),
        sa.Column("max_open_trades", sa.Integer(), nullable=True, default=1),
        sa.Column("is_active", sa.Boolean(), nullable=True, default=False),
        sa.Column("config", sa.Text(), nullable=True),
        # Stats
        sa.Column("total_trades", sa.Integer(), nullable=True, default=0),
        sa.Column("winning_trades", sa.Integer(), nullable=True, default=0),
        sa.Column("losing_trades", sa.Integer(), nullable=True, default=0),
        sa.Column("win_rate", sa.Float(), nullable=True, default=0.0),
        sa.Column("total_profit_loss", sa.Float(), nullable=True, default=0.0),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("last_trade_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_strategies_id", "strategies", ["id"])

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("trade_type", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="PENDING"),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("take_profit", sa.Float(), nullable=True),
        sa.Column("profit_loss", sa.Float(), nullable=True),
        sa.Column("profit_loss_percent", sa.Float(), nullable=True),
        sa.Column("strategy_name", sa.String(100), nullable=True),
        sa.Column("strategy_signals", sa.Text(), nullable=True),
        sa.Column("is_paper_trade", sa.Integer(), nullable=True, default=1),
        sa.Column("binance_order_id", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trades_id", "trades", ["id"])

    op.create_table(
        "deepseek_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("strategy_id", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("current_price", sa.Float(), nullable=False),
        sa.Column("recommendation", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("risk_assessment", sa.String(20), nullable=True),
        sa.Column("suggested_entry", sa.Float(), nullable=True),
        sa.Column("suggested_stop_loss", sa.Float(), nullable=True),
        sa.Column("suggested_take_profit", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("indicators_snapshot", sa.Text(), nullable=True),
        sa.Column("was_executed", sa.Boolean(), nullable=True, default=False),
        sa.Column("execution_reason", sa.Text(), nullable=True),
        sa.Column("trade_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deepseek_decisions_id", "deepseek_decisions", ["id"])


def downgrade() -> None:
    op.drop_table("deepseek_decisions")
    op.drop_table("trades")
    op.drop_table("strategies")
    op.drop_table("users")
