from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_window_str(window_str: str) -> int:
    """
    Parses human-readable window strings (e.g., '1m', '5m', '10m', '30m', '1h')
    into seconds.
    """
    cleaned = window_str.strip().lower()
    mapping = {
        "1m": 60,
        "1 min": 60,
        "1 minute": 60,
        "5m": 300,
        "5 min": 300,
        "5 minutes": 300,
        "10m": 600,
        "10 min": 600,
        "10 minutes": 600,
        "30m": 1800,
        "30 min": 1800,
        "30 minutes": 1800,
        "1h": 3600,
        "1 hour": 3600,
    }
    return mapping.get(cleaned, 300)
