"""
config.py — Load hyperparameters from config.toml and expose them as typed
module-level constants.

All other scripts import their tunable values from here rather than defining
them inline, so every parameter has a single source of truth in config.toml.
"""

from pathlib import Path

try:
    import tomllib          # built-in since Python 3.11
except ImportError:
    try:
        import tomli as tomllib   # pip install tomli  (Python 3.9 / 3.10)
    except ImportError:
        raise ImportError(
            "Python 3.11+ is required, or install 'tomli': pip install tomli"
        )

_CONFIG_PATH = Path(__file__).parent / "config.toml"

with _CONFIG_PATH.open("rb") as _f:
    _cfg = tomllib.load(_f)

# ── [api] ────────────────────────────────────────────────────────────────────
BASE_URL:       str   = _cfg["api"]["base_url"]
VERIFY_SSL:     bool  = _cfg["api"]["verify_ssl"]
MAX_RETRIES:    int   = _cfg["api"]["max_retries"]
RETRY_BACKOFF:  float = _cfg["api"]["retry_backoff"]

# ── [game] ───────────────────────────────────────────────────────────────────
MAX_ATTEMPTS:   int   = _cfg["game"]["max_attempts"]

# ── [solver] ─────────────────────────────────────────────────────────────────
EVAL_LIMIT:     int   = _cfg["solver"]["eval_limit"]

# ── [benchmark] ──────────────────────────────────────────────────────────────
SOLVERS:                   list[str] = _cfg["benchmark"]["solvers"]
FIRST_GUESS_RECOMPUTE_GAMES: int    = _cfg["benchmark"]["first_guess_recompute_games"]
