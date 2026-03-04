"""
API Client — wraps HTTP requests to the Wordle API.
"""

import time
import requests
import urllib3

from config import BASE_URL, VERIFY_SSL, MAX_RETRIES, RETRY_BACKOFF as _RETRY_BACKOFF

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _get_with_retry(url: str, **kwargs) -> requests.Response:
    """Send a GET request and retry up to MAX_RETRIES times on 5xx or connection errors.

    Raises the last exception when all retries are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, verify=VERIFY_SSL, **kwargs)
            if resp.status_code < 500:
                resp.raise_for_status()
                return resp
            # 5xx — treat as transient; raise so the except block handles backoff
            resp.raise_for_status()
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                wait = _RETRY_BACKOFF * (2 ** (attempt - 1))
                time.sleep(wait)

    raise last_exc


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
    resp = _get_with_retry(
        f"{BASE_URL}/daily",
        params={"guess": guess, "size": size},
    )
    return _parse_feedback(resp.json())


def guess_random(guess: str, size: int = 5, seed: int | None = None) -> list[dict]:
    """Guess a random puzzle. Same seed yields same answer for reproducible games."""
    params = {"guess": guess, "size": size}
    if seed is not None:
        params["seed"] = seed
    resp = _get_with_retry(f"{BASE_URL}/random", params=params)
    return _parse_feedback(resp.json())


def guess_word(word: str, guess: str) -> list[dict]:
    """Guess against a given answer word (answer known; mainly for debugging)."""
    resp = _get_with_retry(f"{BASE_URL}/word/{word}", params={"guess": guess})
    return _parse_feedback(resp.json())
