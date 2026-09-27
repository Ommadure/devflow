"""Embed every snippet that isn't "ready", in batches of 32, without a worker.

Run after the first deploy of Phase 4 (existing snippets start "pending"), or to retry
failures:

    cd backend && uv run python scripts/backfill_embeddings.py [--include-failed]
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import get_engine, get_sessionmaker
from app.services.ai import indexing
from app.services.ai.embeddings import check_embedding_config, get_embedding_provider


async def main(include_failed: bool) -> None:
    settings = get_settings()
    configure_logging(settings.app_env, settings.log_level)
    check_embedding_config(settings)
    async with get_sessionmaker()() as session:
        counts = await indexing.embed_pending(
            session, get_embedding_provider(), include_failed=include_failed
        )
    await get_engine().dispose()
    print(f"backfill: {counts}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-failed", action="store_true", help="retry failed ones too")
    asyncio.run(main(parser.parse_args().include_failed))
