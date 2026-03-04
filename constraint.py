"""
Constraint Manager — maintains constraints from API feedback and filters candidate words.
"""


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
