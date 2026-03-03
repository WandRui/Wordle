"""
Game — main game loop.

Responsibilities: call Solver to pick a word → call API to guess → parse feedback → update constraints → check termination.
"""

from constraint import ConstraintManager
from solver import Solver
import api_client

MAX_ATTEMPTS = 6


def _print_feedback(attempt: int, guess: str, feedback: list[dict]) -> None:
    """Print this round's guess result."""
    ICONS = {"correct": "🟩", "present": "🟨", "absent": "⬜"}
    icons = "".join(ICONS[item["result"]] for item in feedback)
    print(f"Attempt {attempt}  {guess.lower()}  {icons}")


def _is_solved(feedback: list[dict]) -> bool:
    """Check if all letters are correct."""
    return all(item["result"] == "correct" for item in feedback)


def play_daily(size: int = 5) -> None:
    """Play the daily puzzle."""
    print(f"=== Guess Daily (size={size}) ===\n")
    _run_game(
        guess_fn=lambda word: api_client.guess_daily(word, size=size),
        size=size,
    )


def play_random(size: int = 5, seed: int | None = None) -> None:
    """Play a random puzzle; fixed seed yields the same answer each time."""
    print(f"=== Guess Random (size={size}, seed={seed}) ===\n")
    _run_game(
        guess_fn=lambda word: api_client.guess_random(word, size=size, seed=seed),
        size=size,
    )


def play_word(answer: str) -> None:
    """Play with a given answer word (for debugging)."""
    print(f"=== Guess Word (answer={answer.lower()}) ===\n")
    _run_game(
        guess_fn=lambda word: api_client.guess_word(answer, word),
        size=len(answer),
    )


def _run_game(guess_fn, size: int) -> None:
    """Generic game loop; guess_fn encapsulates which API to call."""
    candidates = _load_words(size)
    constraints = ConstraintManager()
    solver = Solver()

    for attempt in range(1, MAX_ATTEMPTS + 1):
        guess = solver.pick(candidates)
        feedback = guess_fn(guess)

        _print_feedback(attempt, guess, feedback)

        if _is_solved(feedback):
            print(f"\nSuccess! The answer is {guess.lower()}, guessed in {attempt} attempt(s)")
            return

        constraints.update(feedback)
        candidates = constraints.filter_candidates(candidates)

        print(f"   Remaining candidates: {len(candidates)}\n")

        if not candidates:
            print("No candidates left; guess failed.")
            return

    print(f"\nFailed to guess within {MAX_ATTEMPTS} attempts.")


def _load_words(size: int) -> list[str]:
    """Load words of the given length from the word list file."""
    with open("words.txt", "r") as f:
        words = [line.strip().lower() for line in f if line.strip()]
    filtered = [w for w in words if len(w) == size]
    if not filtered:
        raise ValueError(f"No words of length {size} in word list; check words.txt")
    return filtered
