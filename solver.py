"""
Solver — guessing strategy.

Three strategies are available:
  random   Pick a random candidate (default, fast)
  entropy  Pick the candidate that maximises expected information gain
  minimax  Pick the candidate that minimises the worst-case remaining pool size

For entropy and minimax, when the candidate pool exceeds _EVAL_LIMIT words, a random
sub-sample is evaluated to keep runtime reasonable.
"""

import math
import random
from collections import Counter

_EVAL_LIMIT = 300  # max candidates to score; randomly sample if pool is larger


def _simulate_feedback(guess: str, answer: str) -> tuple:
    """Return a feedback pattern tuple matching Wordle rules."""
    size = len(guess)
    result = ["absent"] * size
    answer_counts: dict[str, int] = {}
    for c in answer:
        answer_counts[c] = answer_counts.get(c, 0) + 1

    # First pass: mark correct positions
    for i in range(size):
        if guess[i] == answer[i]:
            result[i] = "correct"
            answer_counts[guess[i]] -= 1

    # Second pass: mark present (right letter, wrong position)
    for i in range(size):
        if result[i] == "absent" and answer_counts.get(guess[i], 0) > 0:
            result[i] = "present"
            answer_counts[guess[i]] -= 1

    return tuple(result)


def _pattern_distribution(guess: str, candidates: list[str]) -> Counter:
    counts: Counter = Counter()
    for answer in candidates:
        counts[_simulate_feedback(guess, answer)] += 1
    return counts


class RandomSolver:
    """Pick a random candidate — fast, no strategy."""

    name = "random"

    def pick(self, candidates: list[str]) -> str:
        if not candidates:
            raise ValueError("Candidate list is empty; cannot continue guessing")
        return random.choice(candidates)


class EntropySolver:
    """Pick the candidate that maximises expected information gain (entropy)."""

    name = "entropy"

    def pick(self, candidates: list[str]) -> str:
        if not candidates:
            raise ValueError("Candidate list is empty; cannot continue guessing")
        if len(candidates) == 1:
            return candidates[0]

        pool = candidates if len(candidates) <= _EVAL_LIMIT else random.sample(candidates, _EVAL_LIMIT)
        best_word, best_score = pool[0], -1.0
        total = len(candidates)

        for guess in pool:
            dist = _pattern_distribution(guess, candidates)
            entropy = -sum((c / total) * math.log2(c / total) for c in dist.values())
            if entropy > best_score:
                best_score, best_word = entropy, guess

        return best_word


class MinimaxSolver:
    """Pick the candidate that minimises the worst-case remaining pool size."""

    name = "minimax"

    def pick(self, candidates: list[str]) -> str:
        if not candidates:
            raise ValueError("Candidate list is empty; cannot continue guessing")
        if len(candidates) == 1:
            return candidates[0]

        pool = candidates if len(candidates) <= _EVAL_LIMIT else random.sample(candidates, _EVAL_LIMIT)
        best_word, best_score = pool[0], float("inf")

        for guess in pool:
            dist = _pattern_distribution(guess, candidates)
            worst_case = max(dist.values())
            if worst_case < best_score:
                best_score, best_word = worst_case, guess

        return best_word


# Backward-compatible alias
Solver = RandomSolver

SOLVERS: dict[str, type] = {
    RandomSolver.name: RandomSolver,
    EntropySolver.name: EntropySolver,
    MinimaxSolver.name: MinimaxSolver,
}


def get_solver(name: str):
    """Instantiate a solver by name."""
    cls = SOLVERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown solver '{name}'; choices: {list(SOLVERS)}")
    return cls()
