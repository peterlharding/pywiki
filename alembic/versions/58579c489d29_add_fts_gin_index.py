"""add_fts_gin_index

Revision ID: 58579c489d29
Revises: b7ed900152d9
Create Date: 2026-02-28 16:38:50.758999

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '58579c489d29'
down_revision: Union[str, Sequence[str], None] = 'b7ed900152d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add GIN index on tsvector(content) and tsvector(title) for fast FTS.

    PostgreSQL only — no-op on other databases.
    CREATE INDEX CONCURRENTLY cannot run inside a transaction, so we use
    op.get_context().autocommit_block() to step outside the transaction.
    """
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    # CONCURRENTLY requires running outside a transaction block
    with op.get_context().autocommit_block():
        conn.execute(sa.text("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_page_versions_fts
            ON page_versions
            USING GIN (to_tsvector('english', coalesce(content, '')))
        """))
        conn.execute(sa.text("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_pages_title_fts
            ON pages
            USING GIN (to_tsvector('english', coalesce(title, '')))
        """))


def downgrade() -> None:
    """Drop FTS GIN indexes."""
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    with op.get_context().autocommit_block():
        conn.execute(sa.text("DROP INDEX CONCURRENTLY IF EXISTS ix_page_versions_fts"))
        conn.execute(sa.text("DROP INDEX CONCURRENTLY IF EXISTS ix_pages_title_fts"))
