"""
benchmark.py — Parallel Wordle solver benchmark.

Runs each configured solver N times against the /random API endpoint
(seeds 0 … N-1), with up to BATCH_SIZE concurrent games.  All solvers play
the same seeds so the comparison is apples-to-apples.

First guesses are read from config.toml [solver.first_guess.<size>].
Run 'python compute_first_guess.py --size N' before benchmarking a new word size.

Usage:
    python benchmark.py                                  # all solvers, defaults
    python benchmark.py --size 6
    python benchmark.py --games 256 --batch 16
    python benchmark.py --solvers entropy,heuristic      # compare two solvers only
"""

import argparse
import concurrent.futures
import json
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import api_client
from config import EVAL_LIMIT, HEURISTIC_PRESAMPLE, MAX_ATTEMPTS, SOLVERS, get_first_guess
from constraint import ConstraintManager, WORDS_FILE, load_words
from solver import get_solver


def _is_solved(feedback: list[dict]) -> bool:
    return all(item["result"] == "correct" for item in feedback)


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
            candidates = constraints.generate_fallback_candidates(size)
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
    """Submit all games for one solver to the thread pool; return results in seed order.

    The first guess is read from config.toml [solver.first_guess.<size>] so it is
    fixed, reproducible, and computed only once offline by compute_first_guess.py.
    For the random solver, no fixed first guess is used.
    """
    first_guess = get_first_guess(size, solver_name)  # raises if not configured

    if first_guess:
        print(f"  First guess (from config): '{first_guess}'")
    else:
        print(f"  First guess: random (computed per game)")

    n = len(seeds)
    results: list[int | None] = [None] * n
    completed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as pool:
        future_map = {
            pool.submit(run_game, words, solver_name, seeds[idx], size, first_guess): idx
            for idx in range(n)
        }
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

def print_solver_stats(solver_name: str, results: list[int | None], elapsed: float) -> dict:
    """Print per-solver stats and return a summary dict for the final comparison table."""
    solved = [r for r in results if r is not None]
    n_total    = len(results)
    n_solved   = len(solved)
    n_failed   = n_total - n_solved
    solve_rate = 100 * n_solved / n_total

    # Penalised average: failures count as MAX_ATTEMPTS so every game is included.
    avg_penalised = (sum(solved) + n_failed * MAX_ATTEMPTS) / n_total
    avg_solved    = sum(solved) / n_solved if n_solved else float("inf")
    effective     = [r if r is not None else MAX_ATTEMPTS for r in results]
    std_penalised = statistics.stdev(effective) if len(effective) >= 2 else 0.0

    print(f"\n  Solver : {solver_name}")
    print(f"  Played : {n_total}  |  Solved: {n_solved} ({solve_rate:.1f}%)"
          f"  |  Failed: {n_failed}")

    if not solved:
        print("  (no games solved — cannot compute average)")
        return {"name": solver_name, "solve_rate": 0.0,
                "avg_penalised": float("inf"), "avg_solved": float("inf"),
                "std": 0.0, "elapsed": elapsed, "results": results}

    dist = Counter(solved)
    dist_str = "  ".join(f"{k}×{v}" for k, v in sorted(dist.items()))
    print(f"  Avg    : {avg_penalised:.3f}  Std : {std_penalised:.3f}  "
          f"(solved-only: {avg_solved:.3f}  |  failures penalised as {MAX_ATTEMPTS})")
    print(f"  Dist   : {dist_str}"
          + (f"  +{n_failed}×DNF" if n_failed else ""))
    print(f"  Time   : {elapsed:.1f}s  ({n_total} games)")

    return {"name": solver_name, "solve_rate": solve_rate,
            "avg_penalised": avg_penalised, "avg_solved": avg_solved,
            "std": std_penalised, "elapsed": elapsed, "results": results}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _print_comparison_table_full(stats: list[dict], n_games: int, total_elapsed: float) -> None:
    """Print a side-by-side comparison table of all solver results.

    Primary sort: avg_penalised (failures count as MAX_ATTEMPTS) ascending.
    Failures are never discarded — penalising them keeps the comparison fair.
    """
    ranked = sorted(stats, key=lambda s: (s["avg_penalised"], -s["solve_rate"]))
    medals = ["1st", "2nd", "3rd"]

    col = max((len(s["name"]) for s in stats), default=6)
    col = max(col, 9)

    header = (f"  {'Rank':<5}  {'Solver':<{col}}  {'Avg(+pen)':>9}  {'Std':>6}  "
              f"{'Avg(solved)':>11}  {'Solve%':>7}  {'Wall time':>9}")
    print(header)
    print("  " + "-" * (len(header) - 2))

    for i, s in enumerate(ranked):
        rank_label  = medals[i] if i < len(medals) else f"#{i + 1}"
        pen_str     = f"{s['avg_penalised']:.3f}" if s["avg_penalised"] != float("inf") else "N/A"
        std_str     = f"{s['std']:.3f}" if s.get("std") is not None else "N/A"
        solved_str  = f"{s['avg_solved']:.3f}"    if s["avg_solved"]    != float("inf") else "N/A"
        time_str    = f"{s['elapsed']:.1f}s"
        print(f"  {rank_label:<5}  {s['name']:<{col}}  {pen_str:>9}  {std_str:>6}  "
              f"{solved_str:>11}  {s['solve_rate']:>6.1f}%  {time_str:>9}")

    print(f"\n  Avg(+pen)   = avg guesses counting failures as {MAX_ATTEMPTS} (primary rank)")
    print(f"  Std         = std dev of penalised attempts (for variance)")
    print(f"  Avg(solved) = avg guesses over solved games only (reference)")
    print(f"\n  Total wall time: {total_elapsed:.1f}s  "
          f"({n_games} games × {len(stats)} solvers)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark Wordle solvers by running them in parallel against the /random "
            "API endpoint.  All solvers play the same seeds so the comparison is "
            "apples-to-apples.  Results include solve rate, average guesses, attempt "
            "distribution, and wall time."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--size", type=int, default=5,
        help="Length of the target word (must match words in words.txt).",
    )
    parser.add_argument(
        "--games", type=int, default=1024,
        help="Number of games (seeds 0 … N-1) each solver will play.",
    )
    parser.add_argument(
        "--batch", type=int, default=128,
        help="Maximum number of games running concurrently in the thread pool.",
    )
    parser.add_argument(
        "--solvers", type=str, default=None,
        metavar="S1,S2,…",
        help=(
            "Comma-separated list of solvers to benchmark "
            f"(default: all configured — {', '.join(SOLVERS)}). "
            "Example: --solvers entropy,heuristic"
        ),
    )
    parser.add_argument(
        "--output", type=str, default=None, metavar="FILE",
        help=(
            "Write full results (per-game attempt counts, std, meta) to a JSON file "
            "for plotting or analysis.  E.g. --output results/run.json"
        ),
    )
    args = parser.parse_args()

    # Resolve solver list
    if args.solvers:
        from solver import SOLVERS as _ALL_SOLVERS
        requested = [s.strip() for s in args.solvers.split(",") if s.strip()]
        unknown = [s for s in requested if s not in _ALL_SOLVERS]
        if unknown:
            parser.error(f"Unknown solver(s): {unknown}. "
                         f"Available: {list(_ALL_SOLVERS)}")
        solver_names = requested
    else:
        solver_names = list(SOLVERS)

    print(f"Loading {args.size}-letter words from {WORDS_FILE.name} …")
    words = load_words(args.size)
    print(f"  {len(words):,} words loaded.\n")

    # All solvers play the same seeds → fair comparison
    seeds = list(range(args.games))

    print(f"Benchmark: {args.games} games × {len(solver_names)} solver(s)"
          f"  |  batch={args.batch}  |  word size={args.size}")
    print(f"Params   : eval_limit={EVAL_LIMIT}  |  max_attempts={MAX_ATTEMPTS}"
          f"  |  heuristic_presample={HEURISTIC_PRESAMPLE}  |  first-guess: first_guesses.json")
    print(f"Solvers  : {', '.join(solver_names)}")
    print("=" * 65)

    all_stats: list[dict] = []
    wall_start = time.perf_counter()

    for solver_name in solver_names:
        print(f"\n▶  {solver_name.upper()} solver")
        t0 = time.perf_counter()
        results = run_solver_benchmark(solver_name, words, seeds, args.size, args.batch)
        elapsed = time.perf_counter() - t0
        stats = print_solver_stats(solver_name, results, elapsed)
        all_stats.append(stats)

    total_elapsed = time.perf_counter() - wall_start

    print("\n" + "=" * 65)
    print("COMPARISON  (ranked by avg(+pen) ↑, then solve rate ↓)\n")
    _print_comparison_table_full(all_stats, args.games, total_elapsed)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        def _json_val(x):  # float("inf") not JSON-serialisable
            return x if x != float("inf") and x == x else None  # None for inf/NaN

        export = {
            "meta": {
                "games": args.games,
                "size": args.size,
                "batch": args.batch,
                "eval_limit": EVAL_LIMIT,
                "max_attempts": MAX_ATTEMPTS,
                "heuristic_presample": HEURISTIC_PRESAMPLE,
                "total_wall_s": round(total_elapsed, 2),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            },
            "solvers": [
                {
                    "name": s["name"],
                    "solve_rate": round(s["solve_rate"], 2),
                    "avg_penalised": _json_val(s["avg_penalised"]) if s["avg_penalised"] != float("inf") else None,
                    "avg_solved": _json_val(s["avg_solved"]) if s.get("avg_solved") != float("inf") else None,
                    "std": s.get("std"),
                    "elapsed_s": round(s["elapsed"], 2),
                    "results": s.get("results"),  # list of int or null (DNF)
                }
                for s in all_stats
            ],
        }
        with out_path.open("w") as f:
            json.dump(export, f, indent=2)
        print(f"\n  Results written to {out_path}  (use for histograms / variance analysis)")


if __name__ == "__main__":
    main()
