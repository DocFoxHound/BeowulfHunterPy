import requests
from packaging import version as pkg_version
from typing import List, Dict, Any, Optional, Iterable
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

USER_AGENT = "BeowulfHunter/1.0"

BASE_URL = "https://www.ironpoint.org/api/api"


def _get_json(url: str, timeout: float = 8.0) -> Any:
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def get_latest_patch_version(timeout: float = 8.0) -> Optional[str]:
    """Return the highest 'version' value from the gameversion API as a string.

    Example returns: "4.1", "4.2", etc. We compare using packaging.version.
    """
    url = f"{BASE_URL}/gameversion/"
    data = _get_json(url, timeout=timeout)
    if not isinstance(data, list):
        return None

    best: Optional[str] = None
    best_v = None
    for item in data:
        try:
            ver_str = str(item.get("version", "")).strip()
            if not ver_str:
                continue
            pv = pkg_version.parse(ver_str)
            if best is None or pv > best_v:
                best = ver_str
                best_v = pv
        except Exception:
            continue
    return best


def get_piracy_summary(patch: str, timeout: float = 12.0) -> List[Dict[str, Any]]:
    """Fetch piracy summary leaderboard for a given patch.

    Returns a list of dict entries with keys like:
    player_id, patch, hits_created, air_count, ground_count, mixed_count,
    brute_force_count, extortion_count, total_value
    """
    if not patch:
        return []
    url = f"{BASE_URL}/leaderboardpiracysummary/patch/{patch}"
    data = _get_json(url, timeout=timeout)
    return data if isinstance(data, list) else []


def get_blackbox_summary(patch: str, timeout: float = 12.0) -> List[Dict[str, Any]]:
    """Fetch blackbox summary (kills/value) for a given patch.

    Returns a list of dicts with keys such as user_id, fps_kills_ac, fps_kills_pu, etc.
    """
    if not patch:
        return []
    url = f"{BASE_URL}/leaderboardblackboxsummary/patch/{patch}"
    data = _get_json(url, timeout=timeout)
    return data if isinstance(data, list) else []


# --- Users ---
@lru_cache(maxsize=4096)
def get_user_profile(user_id: str, timeout: float = 8.0) -> Optional[Dict[str, Any]]:
    """Fetch a user profile by user_id and cache the result.

    Returns a dict with fields like id, username, nickname, rsi_handle, rsi_display_name.
    If request fails or shape is unexpected, returns None.
    """
    if not user_id:
        return None
    url = f"{BASE_URL}/users/{user_id}"
    try:
        data = _get_json(url, timeout=timeout)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


@lru_cache(maxsize=8192)
def get_user_display_name(user_id: str) -> str:
    """Return the best display name for a user, preferring nickname, then RSI display name, then username, else the id."""
    prof = get_user_profile(user_id) if user_id else None
    if not prof:
        return user_id or "Unknown"
    for key in ("nickname", "rsi_display_name", "rsi_handle", "username"):
        val = prof.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return prof.get("id") or user_id or "Unknown"


def resolve_user_display_names(user_ids: Iterable[str], max_workers: int = 8) -> Dict[str, str]:
    """Resolve many user_ids to display names using a small thread pool and cache.

    Returns mapping of user_id -> display_name.
    """
    ids = [uid for uid in set(user_ids) if uid]
    results: Dict[str, str] = {}
    if not ids:
        return results

    # Use cached results immediately
    for uid in list(ids):
        try:
            if get_user_display_name.cache_info().hits:  # no-op to reference function
                pass
            name = get_user_display_name(uid)
            results[uid] = name
        except Exception:
            # We'll still include in results; get_user_display_name falls back to uid
            results[uid] = uid

    return results
