"""
compute_first_guess.py — Pre-compute optimal first guesses for all solvers.

Uses the full word list (no eval_limit sub-sampling) to find the best opening
word for each (solver, word-size) combination, then writes the results into
first_guesses.json so subsequent benchmark/game runs can use them directly.

Results for all sizes and solvers are stored in one JSON file:
    {
      "5": {"entropy": "tares", "minimax": "steal", "heuristic": "tares"},
      "6": {"entropy": "...",   ...}
    }

Computation notes
-----------------
- heuristic : O(eval_limit × N) — fast (seconds).  Uses position-frequency
  pre-ranking then scores the top eval_limit candidates against all N words.
- entropy   : O(pool × N); default pool = all N words → O(N²).
  For N ≈ 16 k this takes several minutes.  Use --top K to limit the guess
  candidates to the top-K by position frequency for a faster near-optimal result.
- minimax   : same as entropy.
- random    : skipped — the random solver always picks its own first guess.

Usage
-----
    python compute_first_guess.py                   # all sizes already in JSON, all solvers
    python compute_first_guess.py --size 5          # only 5-letter words
    python compute_first_guess.py --size 5 6        # 5- and 6-letter words
    python compute_first_guess.py --solver heuristic
    python compute_first_guess.py --top 500         # faster, near-optimal
    python compute_first_guess.py --dry-run         # print only, don't update JSON
"""

import argparse
import json
import math
import time
from pathlib import Path

from config import EVAL_LIMIT
from constraint import load_words
from solver import (
    SOLVERS,
    _pattern_distribution,
    _precompute_answer_counts,
    _rank_by_position_frequency,
)

FIRST_GUESSES_FILE = Path(__file__).parent / "first_guesses.json"

# Solvers for which a fixed first guess is meaningful
SUPPORTED_SOLVERS = [s for s in SOLVERS if s != "random"]


# ---------------------------------------------------------------------------
# Core scoring functions (no eval_limit cap)
# ---------------------------------------------------------------------------

def _best_entropy(candidates: list[str], pool: list[str]) -> str:
    """Return the word in pool with the highest entropy against candidates."""
    precomp   = _precompute_answer_counts(candidates)
    total     = len(candidates)
    log_total = math.log2(total)
    best_word, best_score = pool[0], -1.0

    for i, guess in enumerate(pool):
        if i % 500 == 0:
            print(f"\r    {i:>6}/{len(pool)}", end="", flush=True)
        dist    = _pattern_distribution(guess, candidates, precomp)
        entropy = log_total - sum(c * math.log2(c) for c in dist.values()) / total
        if entropy > best_score:
            best_score, best_word = entropy, guess

    print(f"\r    {len(pool):>6}/{len(pool)}", flush=True)
    return best_word


def _best_minimax(candidates: list[str], pool: list[str]) -> str:
    """Return the word in pool that minimises the worst-case remaining pool."""
    precomp = _precompute_answer_counts(candidates)
    best_word, best_score = pool[0], float("inf")

    for i, guess in enumerate(pool):
        if i % 500 == 0:
            print(f"\r    {i:>6}/{len(pool)}", end="", flush=True)
        dist  = _pattern_distribution(guess, candidates, precomp)
        worst = max(dist.values())
        if worst < best_score:
            best_score, best_word = worst, guess

    print(f"\r    {len(pool):>6}/{len(pool)}", flush=True)
    return best_word


# ---------------------------------------------------------------------------
# Per-solver dispatcher
# ---------------------------------------------------------------------------

def compute_first_guess(solver_name: str, words: list[str], top: int) -> str:
    """Compute the optimal first guess for one solver.

    top : if > 0, pre-filter to top-K by position frequency before scoring.
          If 0, evaluate all N candidates (O(N²) for entropy/minimax).
    """
    n = len(words)

    if solver_name == "heuristic":
        limit = EVAL_LIMIT if top == 0 else top
        pool  = _rank_by_position_frequency(words, limit)
        print(f"    Pool : top-{len(pool)} by position frequency "
              f"→ entropy against all {n:,} candidates")
        return _best_entropy(words, pool)

    elif solver_name == "entropy":
        pool = _rank_by_position_frequency(words, top) if top > 0 else words
        print(f"    Pool : {len(pool):,} candidates "
              f"→ entropy against all {n:,} candidates")
        if top == 0:
            print(f"    Note : O(N²) with N={n:,}. Use --top 500 for a faster run.")
        return _best_entropy(words, pool)

    elif solver_name == "minimax":
        pool = _rank_by_position_frequency(words, top) if top > 0 else words
        print(f"    Pool : {len(pool):,} candidates "
              f"→ minimax against all {n:,} candidates")
        if top == 0:
            print(f"    Note : O(N²) with N={n:,}. Use --top 500 for a faster run.")
        return _best_minimax(words, pool)

    else:
        raise ValueError(
            f"Cannot compute a fixed first guess for solver '{solver_name}'. "
            f"Supported: {SUPPORTED_SOLVERS}"
        )


# ---------------------------------------------------------------------------
# first_guesses.json updater
# ---------------------------------------------------------------------------

def _update_json(size: int, results: dict[str, str]) -> None:
    """Merge new results for `size` into first_guesses.json.

    Existing entries for other sizes and other solvers within the same size
    are preserved — only the keys present in `results` are overwritten.
    """
    data: dict = {}
    if FIRST_GUESSES_FILE.exists():
        with FIRST_GUESSES_FILE.open() as f:
            data = json.load(f)

    size_key = str(size)
    if size_key not in data:
        data[size_key] = {}
    data[size_key].update(results)

    # Write back sorted by size key for readability
    ordered = {k: data[k] for k in sorted(data, key=int)}
    with FIRST_GUESSES_FILE.open("w") as f:
        json.dump(ordered, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"  first_guesses.json updated → size {size}: {results}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Default sizes: whatever is already in first_guesses.json (fallback to [5])
    existing_sizes: list[int] = []
    if FIRST_GUESSES_FILE.exists():
        with FIRST_GUESSES_FILE.open() as f:
            existing_sizes = [int(k) for k in json.load(f)]

    parser = argparse.ArgumentParser(
        description=(
            "Pre-compute optimal Wordle first guesses using the full word list "
            "(no eval_limit sub-sampling) and store results in first_guesses.json."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--size", type=int, nargs="+",
        default=existing_sizes or [5],
        metavar="N",
        help="Word length(s) to compute first guesses for.",
    )
    parser.add_argument(
        "--solver", type=str, nargs="+",
        default=SUPPORTED_SOLVERS,
        choices=SUPPORTED_SOLVERS,
        metavar="NAME",
        help=f"Solver(s) to compute for. Choices: {SUPPORTED_SOLVERS}",
    )
    parser.add_argument(
        "--top", type=int, default=0,
        metavar="K",
        help=(
            "Limit guess candidates to the top-K by position-frequency ranking. "
            "0 = evaluate all words (slowest, most accurate). "
            "Suggested: 500 for a fast near-optimal result."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print results but do not write to config.toml.",
    )
    args = parser.parse_args()

    overall: dict[int, dict[str, str]] = {}

    for size in args.size:
        print(f"\n{'=' * 55}")
        print(f"Word size : {size}")
        print(f"Loading {size}-letter words … ", end="", flush=True)
        words = load_words(size)
        print(f"{len(words):,} words loaded.")

        size_results: dict[str, str] = {}

        for solver_name in args.solver:
            print(f"\n  Solver : {solver_name}")
            if solver_name == "heuristic" and "entropy" in size_results:
                guess   = size_results["entropy"]
                elapsed = 0.0
                print(f"    → Best first guess: '{guess}'  (reused from entropy, 0.0s)")
            else:
                t0    = time.perf_counter()
                guess = compute_first_guess(solver_name, words, args.top)
                elapsed = time.perf_counter() - t0
                print(f"    → Best first guess: '{guess}'  ({elapsed:.1f}s)")
            size_results[solver_name] = guess

        overall[size] = size_results

        if args.dry_run:
            print(f"\n  [dry-run] Would write to first_guesses.json:")
            print(f'  {{"size": {size}, "results": {size_results}}}')
        else:
            _update_json(size, size_results)

    print("\n" + "=" * 55)
    if args.dry_run:
        print("Done (dry-run — first_guesses.json was NOT modified).")
    else:
        print("Done. Run 'python benchmark.py' to use the new first guesses.")


if __name__ == "__main__":
    main()
