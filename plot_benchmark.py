"""
plot_benchmark.py — Plot benchmark results from JSON.

Reads benchmark JSON (from benchmark.py --output) under tmp/ or a given path,
draws one histogram per solver (2×2 subplots) and saves to tmp/.

Usage:
    python plot_benchmark.py                    # plot all tmp/*.json
    python plot_benchmark.py tmp/benchmark.json # plot one file
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use("Agg")
except ImportError:
    print("matplotlib is required: pip install matplotlib", file=sys.stderr)
    sys.exit(1)

TMP_DIR = Path(__file__).parent / "tmp"


def load_result(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def effective_results(solver: dict, max_attempts: int) -> list[int]:
    return [r if r is not None else max_attempts for r in solver["results"]]


# Distinct colors for overlay plot
SOLVER_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]


def plot_one(data: dict, out_prefix: Path) -> None:
    meta = data["meta"]
    solvers = data["solvers"]
    max_attempts = meta["max_attempts"]
    games = meta["games"]
    bins = list(range(1, max_attempts + 2))

    # Precompute hist counts to get shared y-axis limit across subplots
    all_counts = []
    try:
        import numpy as np
        for s in solvers:
            vals = effective_results(s, max_attempts)
            c, _ = np.histogram(vals, bins=bins)
            all_counts.append(c)
    except ImportError:
        for s in solvers:
            vals = effective_results(s, max_attempts)
            c = [sum(1 for v in vals if bins[i] <= v < bins[i + 1]) for i in range(len(bins) - 1)]
            all_counts.append(c)
    y_max = max(max(c) for c in all_counts) if all_counts else 400
    y_lim = (0, y_max * 1.08)

    n = len(solvers)
    ncols = 2
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows))
    if n == 1:
        axes = [axes]
    else:
        axes = axes.flatten()

    for i, s in enumerate(solvers):
        ax = axes[i]
        vals = effective_results(s, max_attempts)
        ax.hist(vals, bins=bins, color="steelblue", alpha=0.8, edgecolor="white")
        ax.axvline(s["avg_penalised"], color="red", linestyle="--", linewidth=1.5, alpha=0.9, label="avg")
        ax.set_xlabel("Attempts (DNF = max)")
        ax.set_ylabel("Count")
        ax.set_ylim(y_lim)
        ax.set_title(f"{s['name']}  (avg={s['avg_penalised']:.2f}, std={s.get('std', 0):.2f})")
        ax.legend(loc="upper right", fontsize=8)

    for j in range(len(solvers), len(axes)):
        axes[j].set_visible(False)
    fig.suptitle(f"Attempt distribution by solver (n={games} games, same Y-scale)")
    fig.tight_layout()
    fig.savefig(out_prefix.with_suffix(".hist.png"), dpi=120)
    plt.close(fig)

    # Overlay: all solvers in one plot (density) to highlight shape difference
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, s in enumerate(solvers):
        vals = effective_results(s, max_attempts)
        color = SOLVER_COLORS[i % len(SOLVER_COLORS)]
        ax.hist(vals, bins=bins, alpha=0.4, label=f"{s['name']} (avg={s['avg_penalised']:.2f})", color=color, density=True, edgecolor=color, linewidth=0.8)
        ax.axvline(s["avg_penalised"], color=color, linestyle="--", linewidth=1, alpha=0.8)
    ax.set_xlabel("Attempts (DNF = max)")
    ax.set_ylabel("Density")
    ax.legend(loc="upper right")
    ax.set_title(f"Attempt distribution overlay (n={games} games) — compare shape & mean")
    fig.tight_layout()
    fig.savefig(out_prefix.with_name(out_prefix.name + ".hist_overlay.png"), dpi=120)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot benchmark JSON results into tmp/")
    parser.add_argument(
        "paths",
        nargs="*",
        default=None,
        help="JSON file(s) to plot; default: all tmp/*.json",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=TMP_DIR,
        help=f"Directory to save figures (default: {TMP_DIR})",
    )
    args = parser.parse_args()

    if args.paths:
        files = [Path(p) for p in args.paths]
    else:
        files = sorted(TMP_DIR.glob("*.json"))
    if not files:
        print(f"No JSON files found. Put benchmark output in {TMP_DIR}/ or pass paths.", file=sys.stderr)
        sys.exit(1)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    for path in files:
        if not path.is_file():
            print(f"Skip (not a file): {path}", file=sys.stderr)
            continue
        try:
            data = load_result(path)
        except Exception as e:
            print(f"Skip {path}: {e}", file=sys.stderr)
            continue
        if "solvers" not in data or "meta" not in data:
            print(f"Skip {path}: missing meta/solvers", file=sys.stderr)
            continue
        out_prefix = args.out_dir / path.stem
        plot_one(data, out_prefix)
        print(f"  {path.name} → {out_prefix.name}.hist.png, {out_prefix.name}.hist_overlay.png")


if __name__ == "__main__":
    main()
