"""Add a dozen realistic snippets to an account, to try search by hand.

    cd backend && uv run python scripts/seed_demo.py you@example.com

They start "pending"; the worker (or scripts/backfill_embeddings.py) embeds them.
Good queries to try in the UI, in semantic mode:
  "stop a function from firing too often"      → debounce / throttle
  "put an element in the middle of the page"   → centre a div
  "insert or update if the row exists"         → upsert
  "try again when a request fails"             → retry with backoff
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import get_engine, get_sessionmaker
from app.repositories import snippets, users

DEMO = [
    ("useDebounce", "Delay a value until typing pauses", "typescript", ["react", "hooks"],
     "export function useDebounce<T>(value: T, ms = 300): T {\n  const [v, setV] = useState(value);\n  useEffect(() => {\n    const t = setTimeout(() => setV(value), ms);\n    return () => clearTimeout(t);\n  }, [value, ms]);\n  return v;\n}"),
    ("Throttle", "Run at most once per interval", "javascript", ["timing"],
     "function throttle(fn, ms) {\n  let last = 0;\n  return (...args) => {\n    const now = Date.now();\n    if (now - last >= ms) { last = now; fn(...args); }\n  };\n}"),
    ("Center a div", "Flexbox centring, both axes", "css", ["layout"],
     ".parent {\n  display: flex;\n  align-items: center;\n  justify-content: center;\n}"),
    ("Upsert a user", "Postgres insert-or-update", "sql", ["postgres"],
     "INSERT INTO users (id, email) VALUES ($1, $2)\nON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email;"),
    ("Retry with backoff", "Exponential backoff with jitter", "python", ["resilience"],
     "for attempt in range(5):\n    try:\n        return call()\n    except TransientError:\n        time.sleep(2 ** attempt + random.random())\nraise"),
    ("Group by and count", "Rows per category, busiest first", "sql", ["postgres", "reporting"],
     "SELECT category, count(*) AS n\nFROM orders\nGROUP BY category\nORDER BY n DESC;"),
    ("Deep clone an object", "Structured clone keeps Dates and Maps", "javascript", ["objects"],
     "const copy = structuredClone(original);"),
    ("Read a file line by line", "Stream a big file without loading it", "python", ["files"],
     "with open(path, encoding='utf-8') as f:\n    for line in f:\n        process(line.rstrip('\\n'))"),
    ("Truncate text with ellipsis", "One line, cut with …", "css", ["typography"],
     ".title {\n  white-space: nowrap;\n  overflow: hidden;\n  text-overflow: ellipsis;\n}"),
    ("Abort a fetch", "Cancel a request after a timeout", "typescript", ["network"],
     "const res = await fetch(url, { signal: AbortSignal.timeout(5000) });"),
    ("Dedupe an array", "Unique values, order kept", "javascript", ["arrays"],
     "const unique = [...new Set(items)];"),
    ("Parse JSON safely", "Return a default instead of throwing", "typescript", ["json"],
     "function parseJson<T>(text: string, fallback: T): T {\n  try { return JSON.parse(text) as T; } catch { return fallback; }\n}"),
]  # fmt: skip


async def main(email: str) -> None:
    async with get_sessionmaker()() as session:
        user = await users.get_by_email(session, email.strip().lower())
        if user is None:
            raise SystemExit(f"No account for {email}. Sign up in the app first.")
        for title, description, language, tags, code in DEMO:
            await snippets.add(
                session, user.id, title=title, description=description, language=language,
                tags=tags, code=code,
            )  # fmt: skip
        await session.commit()
    await get_engine().dispose()
    print(f"Added {len(DEMO)} snippets for {email}. Embed them with the worker or:")
    print("  uv run python scripts/backfill_embeddings.py")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    asyncio.run(main(sys.argv[1]))
