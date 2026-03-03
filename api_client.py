"""
API Client — wraps HTTP requests to the Wordle API.
"""

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://wordle.votee.dev:8000"

# Server SSL certificate expired; disable verification for local testing
VERIFY_SSL = False


def _parse_feedback(response_json: list[dict]) -> list[dict]:
    """Normalize API response to a uniform format; each element is like:
    {"slot": 0, "letter": "a", "result": "absent" | "present" | "correct"}
    """
    return [
        {
            "slot":   item["slot"],
            "letter": item["guess"],
            "result": item["result"],
        }
        for item in response_json
    ]


def guess_daily(guess: str, size: int = 5) -> list[dict]:
    """Guess today's daily puzzle (same answer for a given size each day)."""
    resp = requests.get(
        f"{BASE_URL}/daily",
        params={"guess": guess, "size": size},
        verify=VERIFY_SSL,
    )
    resp.raise_for_status()
    return _parse_feedback(resp.json())


def guess_random(guess: str, size: int = 5, seed: int | None = None) -> list[dict]:
    """Guess a random puzzle. Same seed yields same answer for reproducible games."""
    params = {"guess": guess, "size": size}
    if seed is not None:
        params["seed"] = seed
    resp = requests.get(
        f"{BASE_URL}/random",
        params=params,
        verify=VERIFY_SSL,
    )
    resp.raise_for_status()
    return _parse_feedback(resp.json())


def guess_word(word: str, guess: str) -> list[dict]:
    """Guess against a given answer word (answer known; mainly for debugging)."""
    resp = requests.get(
        f"{BASE_URL}/word/{word}",
        params={"guess": guess},
        verify=VERIFY_SSL,
    )
    resp.raise_for_status()
    return _parse_feedback(resp.json())
