# Wordle Solver

An automated Wordle solver and benchmarking suite. The program connects to a live Wordle REST API, picks guesses using one of three configurable strategies, and can benchmark all solvers head-to-head across thousands of games in parallel.

---

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Single Game](#single-game)
  - [Benchmark](#benchmark)
- [Solver Strategies](#solver-strategies)
- [Architecture](#architecture)
- [Benchmark Results](#benchmark-results)

---

## Features

- **Three game modes** — daily puzzle, random puzzle (reproducible with a seed), or a custom answer word
- **Three solver strategies** — random baseline, maximum-entropy, and minimax worst-case
- **Constraint-based candidate filtering** — automatically tracks correct / present / absent letter constraints after every guess
- **Fallback brute-force mode** — if the word list is exhausted the solver enumerates all letter strings that still satisfy the constraints, so it never gets stuck
- **Parallel benchmark runner** — compares all solvers over thousands of games concurrently using a thread pool; results include solve rate, average guesses, attempt distribution, and wall time
- **Centralised configuration** — every tunable parameter lives in `config.toml`; no magic numbers in source files
- **Retry-with-backoff HTTP client** — automatically retries on 5xx responses or connection failures with exponential back-off

---

## Project Structure

```
Wordle/
├── main.py          # CLI entry point — choose mode and solver, then run one game
├── game.py          # Core game loop — integrates solver, API, and constraints
├── solver.py        # Three guessing strategies: random, entropy, minimax
├── constraint.py    # ConstraintManager — parses feedback, filters candidates
├── api_client.py    # HTTP client for the Wordle REST API (with retry logic)
├── config.py        # Loads config.toml and exposes typed constants
├── config.toml      # All tunable parameters (API URL, retries, solver limits, …)
├── benchmark.py     # Parallel benchmark runner — compare solvers at scale
├── words.txt        # English word list (~370 k entries, all lengths)
├── benchmark.log    # Sample benchmark output (1 024 games × 3 solvers)
└── WordleAPI/       # API response screenshots (GuessDaily, GuessRandom, GuessWord)
```

---

## Requirements

- Python **3.11+** (uses the built-in `tomllib`; on Python 3.9–3.10 install `tomli`)
- [`requests`](https://pypi.org/project/requests/) ≥ 2.31.0
- Internet access to `https://wordle.votee.dev:8000`

---

## Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd Wordle

# 2. Create and activate a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

> **Python 3.9 / 3.10 only:** also run `pip install tomli` so `config.py` can parse `config.toml`.

---

## Configuration

All parameters are in `config.toml`. Edit this file to tune behaviour without touching source code.

| Section | Key | Default | Description |
|---|---|---|---|
| `[api]` | `base_url` | `https://wordle.votee.dev:8000` | Root URL of the Wordle REST API |
| `[api]` | `verify_ssl` | `false` | SSL certificate verification (server cert is expired) |
| `[api]` | `max_retries` | `3` | Retry attempts on 5xx / connection errors |
| `[api]` | `retry_backoff` | `1.0` | Base back-off in seconds (doubles each retry: 1 s → 2 s → 4 s) |
| `[game]` | `max_attempts` | `16` | Maximum guesses allowed per game |
| `[solver]` | `eval_limit` | `300` | Candidate pool size above which entropy/minimax sub-sample instead of exhaustive search |
| `[benchmark]` | `solvers` | `["random","entropy","minimax"]` | Solvers included in each benchmark run |
| `[benchmark]` | `first_guess_recompute_games` | `256` | Re-compute the first guess every N games to reduce cross-run variance |

---

## Usage

### Single Game

```
python main.py <mode> [options]
```

#### Modes

| Mode | Description |
|---|---|
| `daily` | Guess today's daily puzzle (same answer all day for a given word length) |
| `random` | Guess a random puzzle; use `--seed` to pin the answer for reproducibility |
| `word` | Guess against a known answer — useful for debugging a specific word |

#### Common Options

| Flag | Default | Description |
|---|---|---|
| `--solver` | `random` | Guessing strategy: `random`, `entropy`, or `minimax` |
| `--size` | `5` | Word length (for `daily` and `random` modes) |
| `--seed` | random 0–2047 | Fixed seed for `random` mode |
| `--answer` | — | Target word for `word` mode (required) |

#### Examples

```bash
# Today's 5-letter daily puzzle with the default (random) solver
python main.py daily

# Today's 6-letter daily puzzle with the entropy solver
python main.py daily --size 6 --solver entropy

# Random 5-letter puzzle with a fixed seed — always the same answer
python main.py random --seed 42 --solver minimax

# Custom answer word — for debugging or testing a specific case
python main.py word --answer crane --solver entropy
```
---

### Benchmark

Runs all configured solvers over N games (seeds 0 … N−1) using a thread pool for concurrency. All solvers play identical seeds for a fair, apples-to-apples comparison.

```
python benchmark.py [options]
```

| Flag | Default | Description |
|---|---|---|
| `--size` | `5` | Word length |
| `--games` | `1024` | Number of games each solver plays |
| `--batch` | `64` | Max concurrent games in the thread pool |
| `--recompute` | `256` | Re-compute first guess every N games (`0` = once for all) |

#### Examples

```bash
# Default run: 1 024 games, 5-letter words, batch size 64
python benchmark.py

# Faster smoke test: 256 games
python benchmark.py --games 256 --batch 32

# 6-letter words
python benchmark.py --size 6 --games 512
```
---
## Solver Strategies

All three solvers operate on the same candidate pool (words that still satisfy all constraints) and return a single string — the next guess.

### `random`
Picks a uniformly random word from the candidate pool. No computation beyond random selection. Fast, but the weakest strategy.

### `entropy`
For each candidate guess, computes the **expected information gain** (Shannon entropy) over the current candidate pool using the formula:

```
H = log2(N) - (1/N) × Σ c·log2(c)
```

where N is the pool size and c is the count of candidates that would produce each distinct feedback pattern. The guess with the highest H is selected — it splits the candidate space as evenly as possible in expectation.

### `minimax`
For each candidate guess, simulates every possible feedback pattern and finds the **worst-case remaining pool size**. Selects the guess that minimises this worst case — prioritising robustness over average performance.

#### Performance cap (`eval_limit`)
When the candidate pool exceeds `eval_limit` (default 300), both `entropy` and `minimax` sub-sample `eval_limit` candidates at random instead of scoring every word. This bounds the per-guess cost at O(`eval_limit`²) while keeping runtimes practical at scale.

---

## Architecture

```
main.py / benchmark.py
       │
       ▼
    game.py  ─────────────────────────────────────────────────────────┐
       │                                                               │
       ├──► solver.py          pick next guess from candidate pool     │
       │      RandomSolver                                             │
       │      EntropySolver                                            │
       │      MinimaxSolver                                            │
       │                                                               │
       ├──► api_client.py      send guess, receive feedback            │
       │      guess_daily()                                            │
       │      guess_random()                                           │
       │      guess_word()                                             │
       │                                                               │
       └──► constraint.py      update constraints, filter candidates   │
              ConstraintManager                                         │
                                                                        │
    config.py  ◄────────── config.toml  (single source of truth) ─────┘
```

**Data flow per guess:**
1. `solver.pick(candidates)` → selects the next guess word
2. `api_client.guess_*(guess)` → sends the guess to the API, receives per-letter feedback
3. `ConstraintManager.update(feedback)` → records new correct / present / absent constraints
4. `ConstraintManager.filter_candidates(candidates)` → prunes the word list to still-valid candidates
5. Repeat until solved or `max_attempts` is reached

**Fallback mode:** if `filter_candidates` returns an empty list (the word in `words.txt` was not found), the game calls `_generate_fallback_candidates`, which uses Cartesian product enumeration over per-position valid letters to guarantee the answer is always reachable.

---

## Benchmark Results

Results from a full run on a 5-letter word list (15,921 words, 1,024 games per solver, `batch=128`):

| Solver | Solve Rate | Avg Guesses | Wall Time |
|---|---|---|---|
| **entropy** | 98.6 % | **4.851** | 256.8 s |
| **minimax** | 99.0 % | 5.043 | 264.5 s |
| **random** | 98.1 % | 5.437 | 88.7 s |

- `entropy` achieves the lowest average guess count.
- `minimax` achieves the highest solve rate (fewest failures), at a small cost in average guesses.
- `random` is ~3× faster due to no per-guess computation, making it practical for quick sanity checks.

Full attempt distribution is recorded in `benchmark.log`.
