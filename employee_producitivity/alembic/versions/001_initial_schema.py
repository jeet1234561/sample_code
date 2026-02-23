"""Initial schema with TimescaleDB hypertables

Revision ID: 001
Revises:
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable TimescaleDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")

    # Employees reference table
    op.create_table(
        "employees",
        sa.Column("employee_id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("team", sa.String(), nullable=True),
        sa.Column("jira_account_id", sa.String(), nullable=True),
        sa.Column("gitlab_username", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.PrimaryKeyConstraint("employee_id"),
        sa.UniqueConstraint("email"),
    )

    # Activity events — core normalized event table
    op.create_table(
        "activity_events",
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("employee_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("raw_source_id", sa.String(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("event_id", "timestamp"),
    )
    op.create_index("ix_activity_employee_id", "activity_events", ["employee_id"])
    op.create_index("ix_activity_source_ts", "activity_events", ["source", "timestamp"])
    op.create_index("ix_activity_employee_ts", "activity_events", ["employee_id", "timestamp"])

    # Convert to TimescaleDB hypertable
    op.execute("""
        SELECT create_hypertable(
            'activity_events', 'timestamp',
            chunk_time_interval => INTERVAL '7 days',
            if_not_exists => TRUE
        );
    """)

    # Partial unique index for deduplication (after hypertable creation)
    op.execute("""
        CREATE UNIQUE INDEX ix_activity_raw_source_id
        ON activity_events (raw_source_id, "timestamp")
        WHERE raw_source_id IS NOT NULL;
    """)

    # Connector state tracking
    op.create_table(
        "connector_states",
        sa.Column("connector_name", sa.String(), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_cursor", sa.String(), nullable=True),
        sa.Column("events_fetched_total", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(20), server_default="'idle'"),
        sa.Column("error_detail", sa.String(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("connector_name"),
    )

    # Metric snapshots — computed metric values
    op.create_table(
        "metric_snapshots",
        sa.Column("snapshot_id", sa.String(), nullable=False),
        sa.Column("employee_id", sa.String(), nullable=False),
        sa.Column("metric_name", sa.String(50), nullable=False),
        sa.Column("metric_category", sa.String(20), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("snapshot_id", "computed_at"),
    )
    op.create_index("ix_metric_employee_id", "metric_snapshots", ["employee_id"])
    op.create_index("ix_metric_emp_name_ts", "metric_snapshots", ["employee_id", "metric_name", "computed_at"])

    # Convert to hypertable
    op.execute("""
        SELECT create_hypertable(
            'metric_snapshots', 'computed_at',
            chunk_time_interval => INTERVAL '30 days',
            if_not_exists => TRUE
        );
    """)

    # Business value tags
    op.create_table(
        "business_value_tags",
        sa.Column("feature_id", sa.String(), nullable=False),
        sa.Column("feature_name", sa.String(), nullable=False),
        sa.Column("dollar_value", sa.Float(), nullable=False),
        sa.Column("tagged_by", sa.String(), nullable=True),
        sa.Column("tagged_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("feature_id"),
    )

    # Feature contributions
    op.create_table(
        "feature_contributions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("feature_id", sa.String(), nullable=False),
        sa.Column("employee_id", sa.String(), nullable=False),
        sa.Column("contribution_factor", sa.Float(), nullable=False),
        sa.Column("source_evidence", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fc_feature_id", "feature_contributions", ["feature_id"])
    op.create_index("ix_fc_employee_id", "feature_contributions", ["employee_id"])

    # Enable compression on activity_events for data older than 30 days
    op.execute("""
        ALTER TABLE activity_events SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'employee_id, source'
        );
    """)
    op.execute("""
        SELECT add_compression_policy('activity_events', INTERVAL '30 days');
    """)


def downgrade() -> None:
    op.execute("SELECT remove_compression_policy('activity_events', if_exists => TRUE);")
    op.drop_table("feature_contributions")
    op.drop_table("business_value_tags")
    op.drop_table("metric_snapshots")
    op.drop_table("connector_states")
    op.drop_table("activity_events")
    op.drop_table("employees")
