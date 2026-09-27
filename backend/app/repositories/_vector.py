"""Vector search that stays correct when many users share one HNSW index.

pgvector applies WHERE filters *after* the index scan: HNSW hands back its `ef_search` (40)
nearest vectors from the whole table, and `user_id = me` then throws away everyone else's.
Once other users' vectors crowd the neighbourhood, a user's own matches never make it into
those 40 and semantic search silently returns nothing (reproduced in
tests/integration/test_vector_scan.py). Iterative scans (pgvector 0.8) keep walking the
index until the filtered query has its rows — strict_order keeps results exactly sorted.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def scan_past_other_users(session: AsyncSession) -> None:
    # SET LOCAL: this transaction only, so it also works through Neon's transaction-mode
    # PgBouncer, where a session-level SET could leak to someone else's connection.
    await session.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))
