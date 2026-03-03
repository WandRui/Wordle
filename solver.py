"""
Solver — guessing strategy.

Current implementation: pick one word at random from candidates (simplest strategy).
Can be replaced later with better strategies: word frequency, maximum entropy, etc.
"""

import random


class Solver:
    def pick(self, candidates: list[str]) -> str:
        """Choose the next guess from the candidate list."""
        if not candidates:
            raise ValueError("Candidate list is empty; cannot continue guessing")

        return random.choice(candidates)
