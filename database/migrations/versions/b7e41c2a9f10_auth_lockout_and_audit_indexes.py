"""auth lockout columns + audit/detection indexes for the SOC console

* users.failed_logins / users.locked_until : brute-force lockout per account
* idx_audit_action_time : workflow history, collector runs, notifications
  all filter audit_logs by action + time window
* idx_detections_time : Detection Center sorts by matched_at

Revision ID: b7e41c2a9f10
Revises: dadb423768cb
Create Date: 2026-11-16 21:30:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7e41c2a9f10"
down_revision: Union[str, None] = "dadb423768cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("failed_logins", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_audit_action_time", "audit_logs", ["action", "occurred_at"])
    op.create_index("idx_detections_time", "detections", ["matched_at"])


def downgrade() -> None:
    op.drop_index("idx_detections_time", table_name="detections")
    op.drop_index("idx_audit_action_time", table_name="audit_logs")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_logins")
