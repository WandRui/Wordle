"""
Game — main game loop.

Responsibilities: call Solver to pick a word → call API to guess → parse feedback → update constraints → check termination.

Fallback: when the word list has no candidates left but the puzzle isn't solved, the game
switches to brute-force mode and enumerates every letter-string that satisfies the current
constraints, then continues guessing from that set.  The answer is always guaranteed to be
in the fallback set (because it must satisfy the very constraints the API returned).
"""

import itertools
import string

from constraint import ConstraintManager
from solver import get_solver
import api_client

MAX_ATTEMPTS = 16


def _print_feedback(attempt: int, guess: str, feedback: list[dict]) -> None:
    """Print this round's guess result."""
    ICONS = {"correct": "🟩", "present": "🟨", "absent": "⬜"}
    icons = "".join(ICONS[item["result"]] for item in feedback)
    print(f"Attempt {attempt}  {guess.lower()}  {icons}")


def _is_solved(feedback: list[dict]) -> bool:
    """Check if all letters are correct."""
    return all(item["result"] == "correct" for item in feedback)


def play_daily(size: int = 5, solver_name: str = "random") -> None:
    """Play the daily puzzle."""
    print(f"=== Guess Daily (size={size}, solver={solver_name}) ===\n")
    _run_game(
        guess_fn=lambda word: api_client.guess_daily(word, size=size),
        size=size,
        solver_name=solver_name,
    )


def play_random(size: int = 5, seed: int | None = None, solver_name: str = "random") -> None:
    """Play a random puzzle; fixed seed yields the same answer each time."""
    print(f"=== Guess Random (size={size}, seed={seed}, solver={solver_name}) ===\n")
    _run_game(
        guess_fn=lambda word: api_client.guess_random(word, size=size, seed=seed),
        size=size,
        solver_name=solver_name,
    )


def play_word(answer: str, solver_name: str = "random") -> None:
    """Play with a given answer word (for debugging)."""
    print(f"=== Guess Word (answer={answer.lower()}, solver={solver_name}) ===\n")
    _run_game(
        guess_fn=lambda word: api_client.guess_word(answer, word),
        size=len(answer),
        solver_name=solver_name,
    )


def _generate_fallback_candidates(constraints: ConstraintManager, size: int) -> list[str]:
    """Enumerate every letter-string of length `size` that satisfies current constraints.

    Works by computing valid letters for each position, then taking the Cartesian product
    and keeping only combinations that contain all required "present" letters.
    The answer is always among the results, so the game can continue even when words.txt
    has no matching entry.
    """
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


def _run_game(guess_fn, size: int, solver_name: str = "random") -> None:
    """Generic game loop; guess_fn encapsulates which API to call."""
    candidates = _load_words(size)
    constraints = ConstraintManager()
    solver = get_solver(solver_name)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if not candidates:
            candidates = _generate_fallback_candidates(constraints, size)
            if not candidates:
                print("No candidates left (constraints are contradictory); guess failed.")
                return
            print(f"   [Fallback] Word list exhausted — trying {len(candidates)} constraint-satisfying combination(s)\n")

        guess = solver.pick(candidates)
        feedback = guess_fn(guess)

        _print_feedback(attempt, guess, feedback)

        if _is_solved(feedback):
            print(f"\nSuccess! The answer is {guess.lower()}, guessed in {attempt} attempt(s)")
            return

        constraints.update(feedback)
        candidates = constraints.filter_candidates(candidates)

        print(f"   Remaining candidates: {len(candidates)}\n")

    print(f"\nFailed to guess within {MAX_ATTEMPTS} attempts.")


def _load_words(size: int) -> list[str]:
    """Load words of the given length from the word list file."""
    with open("words.txt", "r") as f:
        filtered = [w for line in f if len(w := line.strip().lower()) == size]
    if not filtered:
        raise ValueError(f"No words of length {size} in word list; check words.txt")
    return filtered
