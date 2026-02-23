"""Add scores and alerts tables (Module C + D)

Revision ID: 002
Revises: 001
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Module C: Employee Scores ---
    op.create_table(
        "employee_scores",
        sa.Column("score_id", sa.String(), nullable=False),
        sa.Column("employee_id", sa.String(), nullable=False),
        sa.Column("delivery_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("team_exp_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("business_value_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("overall_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("weights", postgresql.JSONB(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("score_id", "computed_at"),
    )
    op.create_index("ix_score_employee_id", "employee_scores", ["employee_id"])
    op.create_index("ix_score_emp_ts", "employee_scores", ["employee_id", "computed_at"])

    # Convert to hypertable for time-series score history
    op.execute("""
        SELECT create_hypertable(
            'employee_scores', 'computed_at',
            chunk_time_interval => INTERVAL '30 days',
            if_not_exists => TRUE
        );
    """)

    # --- Module D1: Alert Rules ---
    op.create_table(
        "alert_rules",
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("metric_name", sa.String(50), nullable=False),
        sa.Column("operator", sa.String(5), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("threshold_unit", sa.String(20), nullable=True),
        sa.Column("time_window", sa.String(20), nullable=True),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("targets", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("rule_id"),
    )

    # --- Module D2: Alert Records ---
    op.create_table(
        "alert_records",
        sa.Column("alert_id", sa.String(), nullable=False),
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("metric_name", sa.String(50), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("operator", sa.String(5), nullable=False),
        sa.Column("employee_id", sa.String(), nullable=True),
        sa.Column("team", sa.String(), nullable=True),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("status", sa.String(15), server_default="'active'"),
        sa.Column("targets", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("fired_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("alert_id"),
    )
    op.create_index("ix_alert_rule_id", "alert_records", ["rule_id"])
    op.create_index("ix_alert_employee_id", "alert_records", ["employee_id"])
    op.create_index("ix_alert_status", "alert_records", ["status"])
    op.create_index("ix_alert_priority_status", "alert_records", ["priority", "status"])
    op.create_index("ix_alert_fired_at", "alert_records", ["fired_at"])


def downgrade() -> None:
    op.drop_table("alert_records")
    op.drop_table("alert_rules")
    op.drop_table("employee_scores")
