"""
benchmark.py — Parallel Wordle solver benchmark.

Runs each solver N times against the /random API endpoint (seeds 0 … N-1),
with up to BATCH_SIZE concurrent games.  All three solvers play the same seeds
so the comparison is apples-to-apples.

Usage:
    python benchmark.py                        # defaults: size=5, games=1024, batch=32
    python benchmark.py --size 6
    python benchmark.py --games 256 --batch 16
"""

import argparse
import concurrent.futures
import itertools
import string
import time
from collections import Counter
from pathlib import Path

import api_client
from constraint import ConstraintManager
from solver import get_solver

MAX_ATTEMPTS = 16
SOLVERS = ["random", "entropy", "minimax"]
WORDS_FILE = Path(__file__).parent / "words.txt"


# ---------------------------------------------------------------------------
# Helpers reused from game.py (inlined here to avoid importing private names)
# ---------------------------------------------------------------------------

def _load_words(size: int) -> list[str]:
    with WORDS_FILE.open() as f:
        words = [w for line in f if len(w := line.strip().lower()) == size]
    if not words:
        raise ValueError(f"No {size}-letter words found in {WORDS_FILE}")
    return words


def _is_solved(feedback: list[dict]) -> bool:
    return all(item["result"] == "correct" for item in feedback)


def _generate_fallback_candidates(constraints: ConstraintManager, size: int) -> list[str]:
    alphabet = set(string.ascii_lowercase)
    truly_absent = constraints.absent - constraints.present
    position_options: list[list[str]] = []
    for i in range(size):
        if i in constraints.correct:
            position_options.append([constraints.correct[i]])
        else:
            forbidden = truly_absent | constraints.not_at.get(i, set())
            position_options.append(sorted(alphabet - forbidden))
    return [
        "".join(combo)
        for combo in itertools.product(*position_options)
        if all(letter in combo for letter in constraints.present)
    ]


# ---------------------------------------------------------------------------
# Single-game runner (silent, returns attempt count or None on failure)
# ---------------------------------------------------------------------------

def run_game(
    words: list[str],
    solver_name: str,
    seed: int,
    size: int,
    first_guess: str | None = None,
) -> int | None:
    """Play one game silently. Returns number of attempts used, or None if unsolved.

    first_guess: if provided, skip solver.pick() on attempt 1 and use this word instead.
    This lets the caller pre-compute the expensive first pick once for all games,
    avoiding the GIL bottleneck when 32 threads each try to run an O(N²) entropy
    computation simultaneously.
    """
    candidates = list(words)          # per-game copy; words list is read-only shared state
    constraints = ConstraintManager()
    solver = get_solver(solver_name)  # new instance per game — solvers are stateless

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if not candidates:
            candidates = _generate_fallback_candidates(constraints, size)
            if not candidates:
                return None

        if attempt == 1 and first_guess is not None:
            guess = first_guess
        else:
            guess = solver.pick(candidates)

        try:
            feedback = api_client.guess_random(guess, size=size, seed=seed)
        except Exception:
            return None  # treat network errors as failures

        if _is_solved(feedback):
            return attempt

        constraints.update(feedback)
        candidates = constraints.filter_candidates(candidates)

    return None  # exceeded MAX_ATTEMPTS


# ---------------------------------------------------------------------------
# Batch runner for one solver
# ---------------------------------------------------------------------------

def run_solver_benchmark(
    solver_name: str,
    words: list[str],
    seeds: list[int],
    size: int,
    batch_size: int,
) -> list[int | None]:
    """Submit all games for one solver to the thread pool; return results in seed order."""
    # Pre-compute the first guess once in the main thread.
    # All 1024 games share the same initial candidate list, so the best first word
    # is identical for every game.  Without this, 32 threads would each run an
    # O(N²) entropy/minimax computation concurrently — but Python's GIL serialises
    # CPU-bound work, so they'd actually queue up and stall the progress bar.
    print("  Pre-computing first guess … ", end="", flush=True)
    first_solver = get_solver(solver_name)
    first_guess = first_solver.pick(list(words))
    print(f"'{first_guess}'")

    n = len(seeds)
    results: list[int | None] = [None] * n

    with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as pool:
        future_map = {
            pool.submit(run_game, words, solver_name, seed, size, first_guess): idx
            for idx, seed in enumerate(seeds)
        }

        completed = 0
        for future in concurrent.futures.as_completed(future_map):
            idx = future_map[future]
            results[idx] = future.result()
            completed += 1
            _print_progress(completed, n)

    print()  # newline after progress bar
    return results


def _print_progress(done: int, total: int, width: int = 40) -> None:
    filled = int(width * done / total)
    bar = "█" * filled + "░" * (width - filled)
    print(f"\r  [{bar}] {done}/{total}", end="", flush=True)


# ---------------------------------------------------------------------------
# Statistics printer
# ---------------------------------------------------------------------------

def print_solver_stats(solver_name: str, results: list[int | None], elapsed: float) -> float:
    """Print per-solver stats and return average attempts (inf if nothing solved)."""
    solved = [r for r in results if r is not None]
    n_total  = len(results)
    n_solved = len(solved)
    n_failed = n_total - n_solved

    print(f"\n  Solver : {solver_name}")
    print(f"  Played : {n_total}  |  Solved: {n_solved} ({100 * n_solved / n_total:.1f}%)"
          f"  |  Failed: {n_failed}")

    if not solved:
        print("  (no games solved — cannot compute average)")
        return float("inf")

    avg = sum(solved) / n_solved
    dist = Counter(solved)
    dist_str = "  ".join(f"{k}×{v}" for k, v in sorted(dist.items()))
    print(f"  Avg    : {avg:.3f} guesses")
    print(f"  Dist   : {dist_str}")
    print(f"  Time   : {elapsed:.1f}s  ({elapsed / n_total:.2f}s/game)")

    return avg


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark Wordle solvers with parallel /random API games",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--size",  type=int, default=5,    help="Word length")
    parser.add_argument("--games", type=int, default=1024, help="Games per solver")
    parser.add_argument("--batch", type=int, default=64,   help="Concurrent workers")
    args = parser.parse_args()

    print(f"Loading {args.size}-letter words from {WORDS_FILE.name} …")
    words = _load_words(args.size)
    print(f"  {len(words):,} words loaded.\n")

    # All solvers play the same seeds → fair comparison
    seeds = list(range(args.games))

    print(f"Benchmark: {args.games} games × {len(SOLVERS)} solvers"
          f"  |  batch={args.batch}  |  word size={args.size}")
    print("=" * 60)

    summary: dict[str, float] = {}
    wall_start = time.perf_counter()

    for solver_name in SOLVERS:
        print(f"\n▶  {solver_name.upper()} solver")
        t0 = time.perf_counter()
        results = run_solver_benchmark(solver_name, words, seeds, args.size, args.batch)
        elapsed = time.perf_counter() - t0
        avg = print_solver_stats(solver_name, results, elapsed)
        summary[solver_name] = avg

    total_elapsed = time.perf_counter() - wall_start

    print("\n" + "=" * 60)
    print("FINAL RANKING  (average guesses, lower is better)\n")
    ranking = sorted(summary.items(), key=lambda kv: kv[1])
    for rank, (name, avg) in enumerate(ranking, start=1):
        marker = "🥇" if rank == 1 else ("🥈" if rank == 2 else "🥉")
        avg_str = f"{avg:.3f}" if avg != float("inf") else "N/A"
        print(f"  {marker}  #{rank}  {name:8s}  {avg_str} avg guesses")

    print(f"\nTotal wall time: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
