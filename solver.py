"""
Solver — guessing strategy.

Four strategies are available:
  random    Pick a random candidate (default, fast)
  entropy   Pick the candidate that maximises expected information gain
  minimax   Pick the candidate that minimises the worst-case remaining pool size
  heuristic Like entropy, but when the pool exceeds _EVAL_LIMIT, uses
            position-weighted letter frequency to pre-rank candidates and
            evaluates only the top _EVAL_LIMIT — a smarter alternative to
            random sub-sampling.

For entropy and minimax, when the candidate pool exceeds _EVAL_LIMIT words, a random
sub-sample is evaluated to keep runtime reasonable.  heuristic replaces that random
sub-sample with a frequency-ranked shortlist.
"""

import math
import random

from config import EVAL_LIMIT as _EVAL_LIMIT, HEURISTIC_PRESAMPLE as _HEURISTIC_PRESAMPLE



def _precompute_answer_counts(candidates: list[str]) -> list[list[int]]:
    """Pre-compute per-letter frequency arrays for every candidate word.

    Called once per solver.pick() invocation so that _pattern_distribution does not
    rebuild the frequency array for the same answer on every guess in the pool.
    """
    precomp: list[list[int]] = []
    for word in candidates:
        counts = [0] * 26
        for c in word:
            counts[ord(c) - 97] += 1
        precomp.append(counts)
    return precomp


def _pattern_distribution(guess: str, candidates: list[str],
                           precomp: list[list[int]]) -> dict[int, int]:
    """Return {pattern: count} mapping for this guess against every candidate.

    Uses pre-computed answer letter counts to avoid re-building them for each
    (guess, answer) pair.  The guess letter indices are also pre-computed once
    per call, saving repeated ord() calls inside the inner loop.
    """
    dist: dict[int, int] = {}
    size = len(guess)
    gi = [ord(c) - 97 for c in guess]   # guess letter indices, computed once per guess

    for j, answer in enumerate(candidates):
        result = bytearray(size)
        counts = precomp[j][:]           # fast 26-element list copy; modified in-place below

        for i in range(size):            # first pass: correct
            if guess[i] == answer[i]:
                result[i] = 2
                counts[gi[i]] -= 1

        for i in range(size):            # second pass: present
            if result[i] == 0 and counts[gi[i]] > 0:
                result[i] = 1
                counts[gi[i]] -= 1

        pat = 0
        for v in result:
            pat = pat * 3 + v

        dist[pat] = dist.get(pat, 0) + 1

    return dist


def _rank_by_position_frequency(
    candidates: list[str], k: int, rank_pool: list[str] | None = None
) -> list[str]:
    """Return the top-k candidates ranked by position-weighted letter frequency.

    Frequency is always computed over the full `candidates` list.  If
    `rank_pool` is None, every candidate is scored and sorted; otherwise only
    words in `rank_pool` are scored and sorted (so we do O(|rank_pool|) work
    instead of O(|candidates|)), and the top-k from that subset are returned.
    Use rank_pool when you want to presample for speed (e.g. heuristic_presample).
    """
    if not candidates:
        return []

    to_rank = rank_pool if rank_pool is not None else candidates
    if not to_rank:
        return []

    size = len(candidates[0])
    freq: list[list[int]] = [[0] * 26 for _ in range(size)]
    for word in candidates:
        for i, c in enumerate(word):
            freq[i][ord(c) - 97] += 1

    def _score(word: str) -> int:
        return sum(freq[i][ord(c) - 97] for i, c in enumerate(word))

    return sorted(to_rank, key=_score, reverse=True)[:k]


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
        precomp = _precompute_answer_counts(candidates)
        best_word, best_score = pool[0], -1.0
        total = len(candidates)
        log_total = math.log2(total)    # hoisted: same for every guess in this round

        for guess in pool:
            dist = _pattern_distribution(guess, candidates, precomp)
            # Equivalent to -sum(p*log2(p)), but avoids one division per bucket:
            # H = log2(N) - (1/N) * sum(c * log2(c))
            entropy = log_total - sum(c * math.log2(c) for c in dist.values()) / total
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
        precomp = _precompute_answer_counts(candidates)
        best_word, best_score = pool[0], float("inf")

        for guess in pool:
            dist = _pattern_distribution(guess, candidates, precomp)
            worst_case = max(dist.values())
            if worst_case < best_score:
                best_score, best_word = worst_case, guess

        return best_word


class HeuristicSolver:
    """Entropy solver with a frequency-ranked pre-filter instead of random sub-sampling.

    When the candidate pool exceeds _EVAL_LIMIT, the pool is first sorted by
    position-weighted letter frequency (a cheap O(N) proxy for entropy
    potential) and only the top _EVAL_LIMIT candidates proceed to the full
    entropy calculation.  This tends to surface higher-quality guesses than
    the random sub-sample used by EntropySolver, especially early in the game
    when the pool is large and random sampling has high variance.
    """

    name = "heuristic"

    def pick(self, candidates: list[str]) -> str:
        if not candidates:
            raise ValueError("Candidate list is empty; cannot continue guessing")
        if len(candidates) == 1:
            return candidates[0]

        if len(candidates) <= _EVAL_LIMIT:
            pool = candidates
        else:
            rank_pool: list[str] | None = None
            if _HEURISTIC_PRESAMPLE > 0 and len(candidates) > _HEURISTIC_PRESAMPLE:
                rank_pool = random.sample(candidates, _HEURISTIC_PRESAMPLE)
            pool = _rank_by_position_frequency(candidates, _EVAL_LIMIT, rank_pool=rank_pool)

        precomp = _precompute_answer_counts(candidates)
        best_word, best_score = pool[0], -1.0
        total = len(candidates)
        log_total = math.log2(total)

        for guess in pool:
            dist = _pattern_distribution(guess, candidates, precomp)
            entropy = log_total - sum(c * math.log2(c) for c in dist.values()) / total
            if entropy > best_score:
                best_score, best_word = entropy, guess

        return best_word


# Backward-compatible alias
Solver = RandomSolver

SOLVERS: dict[str, type] = {
    RandomSolver.name: RandomSolver,
    EntropySolver.name: EntropySolver,
    MinimaxSolver.name: MinimaxSolver,
    HeuristicSolver.name: HeuristicSolver,
}


def get_solver(name: str):
    """Instantiate a solver by name."""
    cls = SOLVERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown solver '{name}'; choices: {list(SOLVERS)}")
    return cls()
