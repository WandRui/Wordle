"""
Entry point — choose game mode and start.

Usage examples:
  python main.py daily
  python main.py daily --size 6 --solver entropy
  python main.py random
  python main.py random --size 6 --solver minimax
  python main.py word --answer crane --solver entropy

Available solvers are defined in solver.py and loaded dynamically.
Run 'python main.py --help' to see the current list.
"""

import argparse
import random
from game import play_daily, play_random, play_word
from solver import SOLVERS

SOLVER_CHOICES = list(SOLVERS)  # single source of truth: solver.py


def _add_solver_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--solver", choices=SOLVER_CHOICES, default="random", metavar="SOLVER",
        help=f"Guessing strategy: {', '.join(SOLVER_CHOICES)} (default: random)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wordle-solver",
        description="CLI tool to automatically solve Wordle puzzles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Modes:\n"
            "  daily   Guess today's daily puzzle\n"
            "  random  Guess a random puzzle (seed is random in 0–2047 unless --seed given)\n"
            "  word    Guess a custom answer (use --answer; useful for debugging)\n"
            "\n"
            "Solvers (from solver.py):\n"
            + "".join(
                f"  {name:<10} {cls.__doc__.strip().splitlines()[0]}\n"
                for name, cls in SOLVERS.items()
            )
            + "\n"
            "Examples:\n"
            "  python main.py daily\n"
            "  python main.py daily --size 6 --solver entropy\n"
            "  python main.py random --solver minimax\n"
            "  python main.py random --seed 7 --solver minimax\n"
            "  python main.py word --answer crane --solver entropy\n"
        ),
    )

    subparsers = parser.add_subparsers(dest="mode", metavar="MODE", required=True)

    # daily
    p_daily = subparsers.add_parser("daily", help="Guess today's daily puzzle")
    p_daily.add_argument(
        "--size", type=int, default=5, metavar="N",
        help="Word length (default: 5)",
    )
    _add_solver_arg(p_daily)

    # random
    p_random = subparsers.add_parser("random", help="Guess a random puzzle")
    p_random.add_argument(
        "--size", type=int, default=5, metavar="N",
        help="Word length (default: 5)",
    )
    p_random.add_argument(
        "--seed", type=int, default=None, metavar="SEED",
        help="Random seed in 0–2047; omit to pick a random seed each run",
    )
    _add_solver_arg(p_random)

    # word
    p_word = subparsers.add_parser("word", help="Guess a custom answer word (for debugging)")
    p_word.add_argument(
        "--answer", type=str, required=True, metavar="WORD",
        help="The answer word to guess",
    )
    _add_solver_arg(p_word)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "daily":
        play_daily(size=args.size, solver_name=args.solver)

    elif args.mode == "random":
        seed = args.seed if args.seed is not None else random.randint(0, 2047)
        print(f"Seed for this game = {seed} (use --seed {seed} to reproduce)")
        play_random(size=args.size, seed=seed, solver_name=args.solver)

    elif args.mode == "word":
        play_word(answer=args.answer.lower(), solver_name=args.solver)


if __name__ == "__main__":
    main()
