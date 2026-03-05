# Wordle Solver

An automated Wordle solver and benchmarking suite. The program connects to a live Wordle REST API, picks guesses using one of four configurable strategies, and can benchmark all solvers head-to-head across thousands of games in parallel.

---

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Single Game](#single-game)
  - [Pre-computing First Guesses](#pre-computing-first-guesses)
  - [Benchmark](#benchmark)
  - [Plotting Results](#plotting-results)
- [Solver Strategies](#solver-strategies)
- [Architecture](#architecture)
- [Benchmark Results](#benchmark-results)

---

## Features

- **Three game modes** — daily puzzle, random puzzle (reproducible with a seed), or a custom answer word
- **Four solver strategies** — random baseline, maximum-entropy, minimax worst-case, and heuristic (frequency-ranked entropy)
- **Pre-computed first guesses** — optimal opening words stored in `first_guesses.json` across word lengths 3–7, eliminating expensive O(N²) computation at benchmark time
- **Constraint-based candidate filtering** — automatically tracks correct / present / absent letter constraints after every guess
- **Fallback brute-force mode** — if the word list is exhausted the solver enumerates all letter strings that still satisfy the constraints, so it never gets stuck
- **Parallel benchmark runner** — compares solvers over thousands of games concurrently using a thread pool; results include solve rate, average guesses, attempt distribution, and wall time
- **JSON benchmark output + histogram plots** — export full per-game results to JSON and visualise attempt distributions with `plot_benchmark.py`
- **Centralised configuration** — every tunable parameter lives in `config.toml`; no magic numbers in source files
- **Retry-with-backoff HTTP client** — automatically retries on 5xx responses or connection failures with exponential back-off

---

## Project Structure

```
Wordle/
├── main.py                  # CLI entry point — choose mode and solver, then run one game
├── game.py                  # Core game loop — integrates solver, API, and constraints
├── solver.py                # Four guessing strategies: random, entropy, minimax, heuristic
├── constraint.py            # ConstraintManager — parses feedback, filters candidates
├── api_client.py            # HTTP client for the Wordle REST API (with retry logic)
├── config.py                # Loads config.toml and exposes typed constants
├── config.toml              # All tunable parameters (API URL, retries, solver limits, …)
├── benchmark.py             # Parallel benchmark runner — compare solvers at scale
├── compute_first_guess.py   # Pre-compute optimal first guesses → first_guesses.json
├── plot_benchmark.py        # Plot benchmark JSON output as attempt-distribution histograms
├── first_guesses.json       # Pre-computed optimal opening words (sizes 3–7, all solvers)
├── words.txt                # English word list (~370 k entries, all lengths)
├── tmp/                     # Benchmark JSON output and generated plots (git-ignored)
└── WordleAPI/               # API response screenshots (GuessDaily, GuessRandom, GuessWord)
```

---

## Requirements

- Python **3.11+** (uses the built-in `tomllib`; on Python 3.9–3.10 install `tomli`)
- [`requests`](https://pypi.org/project/requests/) ≥ 2.31.0
- [`matplotlib`](https://pypi.org/project/matplotlib/) ≥ 3.7.0 *(optional — only required for `plot_benchmark.py`)*
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
| `[solver]` | `eval_limit` | `32` | Candidate pool size above which entropy/minimax sub-sample instead of exhaustive search |
| `[solver]` | `heuristic_presample` | `0` | HeuristicSolver pre-sample size before frequency ranking (`0` = rank all candidates) |
| `[benchmark]` | `solvers` | `["random","entropy","minimax","heuristic"]` | Solvers included in each benchmark run |

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
| `--solver` | `random` | Guessing strategy: `random`, `entropy`, `minimax`, or `heuristic` |
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
python main.py word --answer crane --solver heuristic
```

---

### Pre-computing First Guesses

`compute_first_guess.py` finds the optimal opening word for each (solver, word-size) combination using the full word list (no sub-sampling) and stores the results in `first_guesses.json`. The benchmark runner reads this file automatically.

```
python compute_first_guess.py [options]
```

| Flag | Default | Description |
|---|---|---|
| `--size N [N …]` | sizes in `first_guesses.json` | Word length(s) to compute |
| `--solver NAME [NAME …]` | all non-random solvers | Solver(s) to compute for |
| `--top K` | `0` (all words) | Limit guess candidates to the top-K by position frequency; `0` = exhaustive O(N²) |
| `--dry-run` | off | Print results without writing to `first_guesses.json` |

#### Examples

```bash
# Compute for all sizes already in first_guesses.json, all solvers
python compute_first_guess.py

# Compute only 5-letter first guesses
python compute_first_guess.py --size 5

# Faster near-optimal run using top-500 candidates
python compute_first_guess.py --size 5 6 --top 500

# Inspect results without modifying the file
python compute_first_guess.py --dry-run
```

`first_guesses.json` ships with pre-computed values for word sizes 3–7:

| Size | entropy / heuristic | minimax |
|---|---|---|
| 3 | `sae` | `iao` |
| 4 | `sare` | `orae` |
| 5 | `tares` | `raise` |
| 6 | `caries` | `laiser` |
| 7 | `tarlies` | `tarlies` |

---

### Benchmark

Runs all configured solvers over N games (seeds 0 … N−1) using a thread pool for concurrency. All solvers play identical seeds for a fair, apples-to-apples comparison. First guesses are read from `first_guesses.json`.

```
python benchmark.py [options]
```

| Flag | Default | Description |
|---|---|---|
| `--size` | `5` | Word length |
| `--games` | `1024` | Number of games each solver plays |
| `--batch` | `128` | Max concurrent games in the thread pool |
| `--solvers S1,S2,…` | all configured | Comma-separated subset of solvers to run |
| `--output FILE` | — | Write full per-game results to a JSON file (for plotting/analysis) |

#### Examples

```bash
# Default run: 1 024 games, 5-letter words
python benchmark.py

# Faster smoke test: 256 games, 32 concurrent
python benchmark.py --games 256 --batch 32

# 6-letter words, compare only entropy and heuristic
python benchmark.py --size 6 --games 512 --solvers entropy,heuristic

# Save full results for plotting
python benchmark.py --output tmp/benchmark.json
```

---

### Plotting Results

`plot_benchmark.py` reads a benchmark JSON file produced by `benchmark.py --output` and generates two PNG figures in the output directory:

- `<stem>.hist.png` — one subplot per solver showing attempt-count distribution (shared Y-axis)
- `<stem>.hist_overlay.png` — all solvers overlaid as density histograms for direct shape comparison

```
python plot_benchmark.py [options] [FILE …]
```

| Argument | Default | Description |
|---|---|---|
| `FILE …` | all `tmp/*.json` | JSON file(s) to plot |
| `--out-dir DIR` | `tmp/` | Directory to save the generated PNG files |

#### Examples

```bash
# Plot all JSON files under tmp/ (default)
python plot_benchmark.py

# Plot a specific file
python plot_benchmark.py tmp/benchmark.json

# Save plots to a custom directory
python plot_benchmark.py tmp/benchmark.json --out-dir results/
```

---

## Solver Strategies

All four solvers operate on the same candidate pool (words that still satisfy all constraints) and return a single string — the next guess.

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

### `heuristic`
An entropy solver with a smarter candidate pre-filter. When the pool exceeds `eval_limit`, candidates are ranked by **position-weighted letter frequency** (a cheap O(N) proxy for entropy potential) and only the top `eval_limit` are passed to the full entropy calculation. This consistently surfaces higher-quality guesses than the random sub-sample used by `entropy`, especially early in the game when the pool is large and random sampling has high variance.

An optional `heuristic_presample` parameter (default `0` = disabled) allows the frequency ranking itself to be run over a random subset of candidates for even faster runtime at a slight quality trade-off.

#### Performance cap (`eval_limit`)
When the candidate pool exceeds `eval_limit` (default 32), `entropy` and `minimax` evaluate a random sub-sample of `eval_limit` candidates, while `heuristic` evaluates the top `eval_limit` by position frequency. This bounds the per-guess cost at O(`eval_limit`²) while keeping runtimes practical at scale.

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
       │      HeuristicSolver                                          │
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
       │
       └──► first_guesses.json  (pre-computed opening words)
              ▲
    compute_first_guess.py  (offline; run once per new word size)

    benchmark.py ──► tmp/*.json  ──► plot_benchmark.py ──► tmp/*.png
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

Results from a full run on a 5-letter word list (1,024 games per solver, `batch=128`, `eval_limit=32`):

| Rank | Solver | Solve Rate | Avg(+pen) | Std | Avg(solved) | Wall Time |
|---|---|---|---|---|---|---|
| 1st | **heuristic** | 99.0 % | **4.993** | 2.374 | 4.885 | 67.8 s |
| 2nd | **entropy** | 98.9 % | 5.015 | 2.431 | 4.895 | 73.3 s |
| 3rd | **minimax** | **99.5 %** | 5.120 | 2.402 | 5.067 | 65.8 s |
| 4th | **random** | 99.0 % | 5.642 | 2.439 | 5.539 | 66.1 s |

> `Avg(+pen)` = primary ranking metric; failures count as `max_attempts` (16) so every game is included. `Avg(solved)` = average over solved games only.

- `heuristic` achieves the lowest penalised average, outperforming `entropy` while running slightly faster — the frequency-ranked pre-filter consistently surfaces better candidates than random sub-sampling.
- `minimax` achieves the highest solve rate (fewest failures), at a small cost in average guesses.
- `entropy` and `heuristic` are comparable in quality; `entropy` has marginally higher variance due to random sub-sampling.
- `random` has zero per-guess computation overhead, making it practical for quick sanity checks.

Full attempt distributions can be exported and visualised:

```bash
python benchmark.py --output tmp/benchmark.json
python plot_benchmark.py tmp/benchmark.json
```
