"""Run the search evaluation (see README.md in this folder).

    cd backend
    uv run python ../evals/search/run.py                     # real model, writes results/
    uv run python ../evals/search/run.py --max-distance 0.45
    uv run python ../evals/search/run.py --provider fake --no-write   # plumbing check

The logic lives in backend/app/evals/search.py (type-checked and tested with the backend).
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))

from app.evals.search import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(root=HERE))
