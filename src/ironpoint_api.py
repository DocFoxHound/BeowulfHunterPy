import requests
from packaging import version as pkg_version
from typing import List, Dict, Any, Optional, Iterable
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

USER_AGENT = "BeowulfHunter/1.0"

BASE_URL = "https://www.ironpoint.org/api/api"

# Only keep users whose `rank` contains one of these IDs
# (Provided by user requirements)
ALLOWED_RANK_IDS = {
    "1134351702431105084",
    "1134352841985773628",
    "1191071030421229689",
    "1034596054529736745",
}

# In-memory caches for user data
_FILTERED_USER_ID_TO_NAME: Dict[str, str] = {}
_ALL_USERS_FETCHED: bool = False


def _get_json(url: str, timeout: float = 8.0) -> Any:
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _extract_display_name_from_user_obj(user: Dict[str, Any]) -> str:
    """Return preferred display name from a user object.

    Preference order: nickname, rsi_display_name, rsi_handle, username, id.
    """
    for key in ("nickname", "rsi_display_name", "rsi_handle", "username"):
        val = user.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    # Fall back to id if present
    uid = user.get("id")
    if isinstance(uid, str) and uid.strip():
        return uid.strip()
    if uid is not None:
        try:
            return str(uid)
        except Exception:
            pass
    return "Unknown"


def _rank_ids_from_user_obj(user: Dict[str, Any]) -> List[str]:
    """Best-effort extraction of rank IDs from various possible shapes.

    Supports:
    - rank as a string/int (single id)
    - rank as dict with 'id' or 'rank_id'
    - rank as list/tuple/set containing strings/ints/dicts
    """
    ranks = user.get("rank")
    ids: List[str] = []
    if ranks is None:
        return ids
    try:
        # If iterable of ranks
        if isinstance(ranks, (list, tuple, set)):
            for r in ranks:
                rid = None
                if isinstance(r, dict):
                    rid = r.get("id") or r.get("rank_id")
                else:
                    rid = r
                if rid is None:
                    continue
                sid = str(rid).strip()
                if sid:
                    ids.append(sid)
        elif isinstance(ranks, dict):
            rid = ranks.get("id") or ranks.get("rank_id")
            if rid is not None:
                sid = str(rid).strip()
                if sid:
                    ids.append(sid)
        else:
            # scalar (int/str)
            sid = str(ranks).strip()
            if sid:
                ids.append(sid)
    except Exception:
        # Be resilient; return whatever we parsed so far
        pass
    return ids


def _ensure_filtered_users_loaded(timeout: float = 20.0) -> None:
    """Fetch and cache the filtered users list once.

    We hit the users endpoint once, filter by ALLOWED_RANK_IDS, and build
    a mapping of id -> preferred display name (nickname preferred).
    """
    global _ALL_USERS_FETCHED, _FILTERED_USER_ID_TO_NAME
    if _ALL_USERS_FETCHED and _FILTERED_USER_ID_TO_NAME:
        return
    try:
        url = f"{BASE_URL}/users/"
        data = _get_json(url, timeout=timeout)
        if not isinstance(data, list):
            _ALL_USERS_FETCHED = True
            return
        for user in data:
            try:
                uid = str(user.get("id") or "").strip()
                if not uid:
                    continue
                rank_ids = set(_rank_ids_from_user_obj(user))
                if not rank_ids:
                    continue
                if not any(rid in ALLOWED_RANK_IDS for rid in rank_ids):
                    # Not in the desired rank set; skip
                    continue
                _FILTERED_USER_ID_TO_NAME[uid] = _extract_display_name_from_user_obj(user)
            except Exception:
                # Skip problematic user entries but continue processing
                continue
        _ALL_USERS_FETCHED = True
    except Exception:
        # If fetching fails, mark as fetched to avoid tight retry loops in UI
        _ALL_USERS_FETCHED = True


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

    Note: Most lookups should be satisfied by the preloaded filtered users cache.
    This call is kept for backward compatibility but will be used as a fallback
    only when necessary.
    """
    if not user_id:
        return None
    # If cache already has this user, synthesize a minimal profile
    try:
        _ensure_filtered_users_loaded()
        if user_id in _FILTERED_USER_ID_TO_NAME:
            return {
                "id": user_id,
                "nickname": _FILTERED_USER_ID_TO_NAME[user_id],
            }
    except Exception:
        pass
    # Fallback: direct fetch of a single user
    url = f"{BASE_URL}/users/{user_id}"
    try:
        data = _get_json(url, timeout=timeout)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


@lru_cache(maxsize=8192)
def get_user_display_name(user_id: str) -> str:
    """Return display name using only the preloaded filtered users cache.

    If the user is not in the filtered set, return the raw user_id.
    This avoids per-user network calls as requested.
    """
    if not user_id:
        return "Unknown"
    try:
        _ensure_filtered_users_loaded()
        name = _FILTERED_USER_ID_TO_NAME.get(user_id)
        return name if isinstance(name, str) and name else user_id
    except Exception:
        return user_id


def resolve_user_display_names(user_ids: Iterable[str], max_workers: int = 8) -> Dict[str, str]:
    """Resolve many user_ids to display names using a small thread pool and cache.

    Returns mapping of user_id -> display_name.
    """
    ids = [uid for uid in set(user_ids) if uid]
    results: Dict[str, str] = {}
    if not ids:
        return results

    # Ensure the filtered cache is loaded once
    try:
        _ensure_filtered_users_loaded()
    except Exception:
        pass

    # Resolve using the filtered cache only; if missing, keep the id
    for uid in ids:
        try:
            name = _FILTERED_USER_ID_TO_NAME.get(uid)
            results[uid] = name if isinstance(name, str) and name else uid
        except Exception:
            results[uid] = uid

    return results


@lru_cache(maxsize=4096)
def get_user_display_name_fallback(user_id: str) -> str:
    """Resolve display name with a profile fetch fallback for single IDs.

    Intended for special cases like the current user so the UI can show a
    nickname even if the user is outside the filtered rank set.
    """
    if not user_id:
        return "Unknown"
    try:
        _ensure_filtered_users_loaded()
        name = _FILTERED_USER_ID_TO_NAME.get(user_id)
        if isinstance(name, str) and name:
            return name
    except Exception:
        pass
    try:
        prof = get_user_profile(user_id)
        if isinstance(prof, dict):
            return _extract_display_name_from_user_obj(prof)
    except Exception:
        pass
    return user_id
