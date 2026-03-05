"""
Constraint Manager — maintains constraints from API feedback, filters candidate
words, and provides fallback candidate generation when the word list is exhausted.
"""

import itertools
import string
from pathlib import Path

WORDS_FILE = Path(__file__).parent / "words.txt"


def load_words(size: int) -> list[str]:
    """Load all words of the given length from the shared word list."""
    with WORDS_FILE.open() as f:
        words = [w for line in f if len(w := line.strip().lower()) == size]
    if not words:
        raise ValueError(f"No {size}-letter words found in {WORDS_FILE}")
    return words


class ConstraintManager:
    def __init__(self):
        # Letter that must be at a given position, e.g. {0: 'a', 2: 'e'}
        self.correct: dict[int, str] = {}

        # Letters that must appear in the word (position unspecified)
        self.present: set[str] = set()

        # Letters that must not appear in the word
        self.absent: set[str] = set()

        # Letters that must not be at a given position, e.g. {1: {'a', 'e'}}
        self.not_at: dict[int, set[str]] = {}

        # Cached result of (absent - present); updated in update() so is_candidate()
        # doesn't recompute the set difference on every call during filter_candidates().
        self._truly_absent: set[str] = set()

    def update(self, feedback: list[dict]) -> None:
        """Update constraints from one round of API feedback."""
        for item in feedback:
            slot   = item["slot"]
            letter = item["letter"]
            result = item["result"]

            if result == "correct":
                self.correct[slot] = letter
                self.present.add(letter)

            elif result == "present":
                self.present.add(letter)
                self.not_at.setdefault(slot, set()).add(letter)

            elif result == "absent":
                # Note: if the same letter is correct/present elsewhere, we should not add to absent
                # (it means no extra of that letter at this position). For simplicity we add to absent here.
                self.absent.add(letter)

        self._truly_absent = self.absent - self.present  # refresh cache

    def is_candidate(self, word: str) -> bool:
        """Check whether a word satisfies all current constraints."""
        # 1. correct: specified positions must match
        for slot, letter in self.correct.items():
            if word[slot] != letter:
                return False

        # 2. absent: word must not contain these letters (excluding those already correct/present)
        if any(letter in word for letter in self._truly_absent):
            return False

        # 3. present: word must contain these letters
        if any(letter not in word for letter in self.present):
            return False

        # 4. not_at: letter must not appear at this position
        for slot, letters in self.not_at.items():
            if word[slot] in letters:
                return False

        return True

    def filter_candidates(self, candidates: list[str]) -> list[str]:
        """Filter the candidate list to words that satisfy the constraints."""
        return [word for word in candidates if self.is_candidate(word)]

    def generate_fallback_candidates(self, size: int) -> list[str]:
        """Enumerate every letter-string of length `size` that satisfies current constraints.

        Called when the word list has no matching candidates left.  Uses Cartesian
        product over per-position valid letters so the answer is always reachable,
        even if it is absent from words.txt.
        """
        alphabet = set(string.ascii_lowercase)
        position_options: list[list[str]] = []
        for i in range(size):
            if i in self.correct:
                position_options.append([self.correct[i]])
            else:
                forbidden = self._truly_absent | self.not_at.get(i, set())
                position_options.append(sorted(alphabet - forbidden))
        return [
            "".join(combo)
            for combo in itertools.product(*position_options)
            if all(letter in combo for letter in self.present)
        ]
