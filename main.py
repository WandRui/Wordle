"""
Entry point — choose game mode and start.

Usage examples:
  python main.py daily
  python main.py daily --size 6
  python main.py random
  python main.py random --size 6 --seed 42
  python main.py word --answer crane
"""

import argparse
import random
from game import play_daily, play_random, play_word


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wordle-solver",
        description="CLI tool to automatically solve Wordle puzzles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  daily   Guess today's daily puzzle (same answer for a given size each day)
  random  Guess a random puzzle (use --seed to fix the answer for reproducibility)
  word    Guess a custom answer (use --answer to specify; useful for debugging)

Examples:
  python main.py daily
  python main.py daily --size 6
  python main.py random --seed 42
  python main.py word --answer crane
        """,
    )

    subparsers = parser.add_subparsers(dest="mode", metavar="MODE", required=True)

    # daily
    p_daily = subparsers.add_parser("daily", help="Guess today's daily puzzle")
    p_daily.add_argument(
        "--size", type=int, default=5, metavar="N",
        help="Word length (default: 5)",
    )

    # random
    p_random = subparsers.add_parser("random", help="Guess a random puzzle")
    p_random.add_argument(
        "--size", type=int, default=5, metavar="N",
        help="Word length (default: 5)",
    )
    p_random.add_argument(
        "--seed", type=int, default=None, metavar="SEED",
        help="Random seed; fixed seed gives same puzzle (default: random)",
    )

    # word
    p_word = subparsers.add_parser("word", help="Guess a custom answer word (for debugging)")
    p_word.add_argument(
        "--answer", type=str, required=True, metavar="WORD",
        help="The answer word to guess",
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "daily":
        play_daily(size=args.size)

    elif args.mode == "random":
        seed = args.seed if args.seed is not None else random.randint(1, 99999)
        print(f"Seed for this game = {seed} (use --seed {seed} to reproduce)")
        play_random(size=args.size, seed=seed)

    elif args.mode == "word":
        play_word(answer=args.answer.lower())


if __name__ == "__main__":
    main()
