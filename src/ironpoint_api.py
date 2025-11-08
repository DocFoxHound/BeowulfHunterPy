import requests
from datetime import datetime, timedelta, timezone
import time
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
_SUMMARY_CACHE: Dict[tuple, tuple] = {}
_LATEST_HITS_CACHE: Dict[str, tuple] = {}
_RECENT_FLEETS_CACHE: Dict[str, tuple] = {}
_ALL_USERS_OPTIONS_CACHE: Dict[str, tuple] = {}
_COMMODITY_NAMES_CACHE: Dict[str, tuple] = {}
_COMMODITIES_FULL_CACHE: Dict[str, tuple] = {}


def _get_json(url: str, timeout: float = 8.0) -> Any:
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _post_json(url: str, payload: Dict[str, Any], timeout: float = 10.0) -> requests.Response:
    """POST JSON with a consistent User-Agent header.

    Raises requests.RequestException on errors so callers can handle/log.
    """
    headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
    return requests.post(url, json=payload, headers=headers, timeout=timeout)


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


@lru_cache(maxsize=128)
def _get_patch_id_for_version(version_str: str, timeout: float = 8.0) -> Optional[str]:
    """Return the id for a given patch version string using the gameversion API.

    If the exact version isn't found, returns None.
    """
    if not version_str:
        return None
    try:
        url = f"{BASE_URL}/gameversion/"
        data = _get_json(url, timeout=timeout)
        if not isinstance(data, list):
            return None
        for item in data:
            try:
                if str(item.get("version", "")).strip() == str(version_str).strip():
                    pid = item.get("id")
                    if pid is None:
                        return None
                    return str(pid)
            except Exception:
                continue
        return None
    except Exception:
        return None


def _tomorrow_utc_ms() -> int:
    """Compute 'tomorrow' timestamp in milliseconds (UTC)."""
    try:
        dt = datetime.now(timezone.utc) + timedelta(days=1)
        return int(dt.timestamp() * 1000)
    except Exception:
        # Fallback to current time + 1 day in ms if timezone utilities fail
        try:
            return int((datetime.utcnow() + timedelta(days=1)).timestamp() * 1000)
        except Exception:
            # Last resort: a fixed 24h ahead from epoch 0
            return 86_400_000


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
    """Fetch piracy-like summary for a patch using the Beowulf Hunter endpoint.

    This now sources data from
    /beowulfhuntersummarybypatch/patch/{patch}?start={patch_id}&end={tomorrow_ms}
    and adapts the rows to the legacy shape expected by the UI.
    """
    if not patch:
        return []
    # Use shared combined summary cache to avoid duplicate HTTP calls
    def _get_shared_data() -> List[Dict[str, Any]]:
        pid = _get_patch_id_for_version(patch, timeout=timeout)
        start_param = str(pid) if pid is not None else "0"
        cache_key = ("beowulf", patch, start_param)
        now = time.time()
        cached = _SUMMARY_CACHE.get(cache_key)
        # 30s TTL to share across tabs and functions
        if cached and (now - cached[0] < 30):
            return cached[1]  # type: ignore[index]
        end_ms = _tomorrow_utc_ms()
        url = f"{BASE_URL}/beowulfhuntersummarybypatch/patch/{patch}?start={start_param}&end={end_ms}"
        data = _get_json(url, timeout=timeout)
        rows = data if isinstance(data, list) else []
        _SUMMARY_CACHE[cache_key] = (now, rows)
        return rows

    data = _get_shared_data()

    out: List[Dict[str, Any]] = []
    for row in data:
        try:
            if not isinstance(row, dict):
                continue
            uid = row.get("user_id") or row.get("player_id") or row.get("id")
            # Map values, defaulting to 0 if missing/None
            def _ival(x):
                try:
                    return int(x)
                except Exception:
                    return 0
            # Per requirement: hits_created is the sum of brute_force_count + extortion_count
            brute = _ival(row.get("brute_force_count"))
            extort = _ival(row.get("extortion_count"))
            hits_sum = brute + extort

            item = {
                "player_id": str(uid) if uid is not None else "",
                "user_id": str(uid) if uid is not None else "",
                "patch": patch,
                "hits_created": hits_sum,
                "air_count": _ival(row.get("air_count")),
                "ground_count": _ival(row.get("ground_count")),
                "mixed_count": _ival(row.get("mixed_count")),
                "brute_force_count": brute,
                "extortion_count": extort,
                # Prefer total_value if provided; otherwise try value_pu + value_ac
                "total_value": _ival(row.get("total_value"))
                                or (_ival(row.get("value_pu")) + _ival(row.get("value_ac"))),
            }
            out.append(item)
        except Exception:
            continue
    return out


def get_blackbox_summary(patch: str, timeout: float = 12.0) -> List[Dict[str, Any]]:
    """Fetch blackbox-like summary for a patch using the Beowulf Hunter endpoint.

    This adapts rows to include fields used by the UI: fps_kills_* and ship_kills_*.
    """
    if not patch:
        return []
    # Reuse the same shared combined summary used by piracy
    def _get_shared_data() -> List[Dict[str, Any]]:
        pid = _get_patch_id_for_version(patch, timeout=timeout)
        start_param = str(pid) if pid is not None else "0"
        cache_key = ("beowulf", patch, start_param)
        now = time.time()
        cached = _SUMMARY_CACHE.get(cache_key)
        if cached and (now - cached[0] < 30):
            return cached[1]  # type: ignore[index]
        end_ms = _tomorrow_utc_ms()
        url = f"{BASE_URL}/beowulfhuntersummarybypatch/patch/{patch}?start={start_param}&end={end_ms}"
        data = _get_json(url, timeout=timeout)
        rows = data if isinstance(data, list) else []
        _SUMMARY_CACHE[cache_key] = (now, rows)
        return rows

    data = _get_shared_data()

    out: List[Dict[str, Any]] = []
    for row in data:
        try:
            if not isinstance(row, dict):
                continue
            uid = row.get("user_id") or row.get("player_id") or row.get("id")
            def _ival(x):
                try:
                    return int(x)
                except Exception:
                    return 0
            def _fval(x):
                try:
                    return float(x)
                except Exception:
                    return 0.0
            item = {
                "user_id": str(uid) if uid is not None else "",
                "player_id": str(uid) if uid is not None else "",
                # Provide both ship and fps fields; UI will pick what it needs
                "fps_kills_total": _ival(row.get("fps_kills_total")),
                "fps_kills_pu": _ival(row.get("fps_kills_pu")),
                "fps_kills_ac": _ival(row.get("fps_kills_ac")),
                "ship_kills_total": _ival(row.get("ship_kills_total")),
                "ship_kills_pu": _ival(row.get("ship_kills_pu")),
                "ship_kills_ac": _ival(row.get("ship_kills_ac")),
                # Values by mode if present
                "value_pu": _ival(row.get("value_pu")),
                "value_ac": _ival(row.get("value_ac")),
                # Ranked Arena Commander rating if present
                "rating": _fval(row.get("rating")),
            }
            out.append(item)
        except Exception:
            continue
    return out


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


# --- Latest Pirate Hits ---
def get_latest_pirate_hits(timeout: float = 8.0) -> List[Dict[str, Any]]:
    """Return the latest pirate hits (up to 10) from the hittracker endpoint.

    The endpoint returns the last 10 hits in reverse chronological order.
    We cache for a short TTL to avoid hammering the API from the UI thread.
    """
    now = time.time()
    cache_key = "hittracker/latest"
    try:
        cached = _LATEST_HITS_CACHE.get(cache_key)
        # 20s TTL is enough for a manual-refresh UI
        if cached and (now - cached[0] < 20):
            return cached[1]  # type: ignore[index]
    except Exception:
        pass

    url = f"{BASE_URL}/hittracker/latest"
    try:
        data = _get_json(url, timeout=timeout)
        rows: List[Dict[str, Any]] = []
        # Normalize to a list of dicts
        if isinstance(data, list):
            src = data
        elif isinstance(data, dict):
            src = [data]
        else:
            src = []
        for item in src:
            if not isinstance(item, dict):
                continue
            # Best-effort conversion of numeric fields to ints
            try:
                if "total_value" in item and item["total_value"] is not None:
                    item["total_value"] = int(item["total_value"])  # type: ignore[assignment]
            except Exception:
                pass
            rows.append(item)
        _LATEST_HITS_CACHE[cache_key] = (now, rows)
        return rows
    except Exception:
        # On failure, return empty list and do not raise (UI-friendly)
        return []


# --- Additional helpers for UI forms ---
def get_recent_fleets(limit: int = 50, timeout: float = 8.0) -> List[Dict[str, Any]]:
    """Return recent fleets (gangs) from the API, cached briefly.

    Uses a short TTL (30s) to avoid excessive network calls when the form opens repeatedly.
    """
    now = time.time()
    cache_key = f"recentfleets/{limit}"
    try:
        cached = _RECENT_FLEETS_CACHE.get(cache_key)
        if cached and (now - cached[0] < 30):
            return cached[1]  # type: ignore[index]
    except Exception:
        pass

    url = f"{BASE_URL}/recentfleets/"
    try:
        data = _get_json(url, timeout=timeout)
        rows: List[Dict[str, Any]] = []
        if isinstance(data, list):
            rows = data
        # Sort by timestamp desc if present
        try:
            def _ts(v):
                try:
                    s = str((v or {}).get("timestamp") or (v or {}).get("created_at") or "")
                    # Best effort: ISO8601 to epoch
                    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
                except Exception:
                    return 0.0
            rows.sort(key=_ts, reverse=True)
        except Exception:
            pass
        if isinstance(limit, int) and limit > 0:
            rows = rows[:limit]
        _RECENT_FLEETS_CACHE[cache_key] = (now, rows)
        return rows
    except Exception:
        return []


def get_all_user_display_options(timeout: float = 10.0) -> List[Dict[str, str]]:
    """Return simplified user options for selection: [{id, name}].

    Name preference: nickname, rsi_display_name, rsi_handle, username; id fallback.
    Cached with a TTL of 5 minutes.
    """
    now = time.time()
    cache_key = "users/options"
    try:
        cached = _ALL_USERS_OPTIONS_CACHE.get(cache_key)
        if cached and (now - cached[0] < 300):
            return cached[1]  # type: ignore[index]
    except Exception:
        pass

    url = f"{BASE_URL}/users/"
    try:
        data = _get_json(url, timeout=timeout)
        out: List[Dict[str, str]] = []
        if isinstance(data, list):
            for user in data:
                try:
                    uid = str((user or {}).get("id") or "").strip()
                    if not uid:
                        continue
                    name = _extract_display_name_from_user_obj(user)
                    if not name or name == "Unknown":
                        name = uid
                    out.append({"id": uid, "name": name})
                except Exception:
                    continue
        # Sort case-insensitively by name
        try:
            out.sort(key=lambda x: x.get("name", "").lower())
        except Exception:
            pass
        _ALL_USERS_OPTIONS_CACHE[cache_key] = (now, out)
        return out
    except Exception:
        return []


def get_commodity_names(timeout: float = 10.0) -> List[str]:
    """Return list of commodity names from summarizedcommodities endpoint.

    Cached with a TTL of 10 minutes.
    """
    now = time.time()
    cache_key = "uex/summarizedcommodities/names"
    try:
        cached = _COMMODITY_NAMES_CACHE.get(cache_key)
        if cached and (now - cached[0] < 600):
            return cached[1]  # type: ignore[index]
    except Exception:
        pass

    url = f"{BASE_URL}/uex/summarizedcommodities/"
    try:
        data = _get_json(url, timeout=timeout)
        names: List[str] = []
        if isinstance(data, list):
            for item in data:
                try:
                    nm = str((item or {}).get("commodity_name") or "").strip()
                    if nm:
                        names.append(nm)
                except Exception:
                    continue
        # Unique and sorted
        try:
            names = sorted(sorted(set(names)), key=lambda s: s.lower())
        except Exception:
            pass
        _COMMODITY_NAMES_CACHE[cache_key] = (now, names)
        return names
    except Exception:
        return []


def get_commodities_full(timeout: float = 10.0) -> List[Dict[str, Any]]:
    """Return full commodity objects from summarizedcommodities endpoint.

    Cached with a TTL of 10 minutes. Includes price_buy_avg and price_sell_avg.
    """
    now = time.time()
    cache_key = "uex/summarizedcommodities/full"
    try:
        cached = _COMMODITIES_FULL_CACHE.get(cache_key)
        if cached and (now - cached[0] < 600):
            return cached[1]  # type: ignore[index]
    except Exception:
        pass

    url = f"{BASE_URL}/uex/summarizedcommodities/"
    try:
        data = _get_json(url, timeout=timeout)
        rows: List[Dict[str, Any]] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    rows.append(item)
        _COMMODITIES_FULL_CACHE[cache_key] = (now, rows)
        return rows
    except Exception:
        return []


# --- Submit a Pirate Hit (Add New form) ---
def post_hittracker(payload: Dict[str, Any], timeout: float = 12.0,
                    return_error: bool = False):
    """Submit a hit payload to the hittracker endpoint.

    Args:
        payload: Dict matching hit schema required by backend.
        timeout: Request timeout in seconds.
        return_error: When True, returns tuple (success: bool, info: Optional[dict]).

    Returns:
        If return_error is False (default): True on HTTP 200/201 else False.
        If return_error is True: (success, info). On failure, info contains
        status/message/response fields when available.
    """
    url = f"{BASE_URL}/hittracker/"
    try:
        resp = _post_json(url, payload, timeout=timeout)
        if resp.status_code in (200, 201):
            return (True, None) if return_error else True
        info = {
            "status": resp.status_code,
            "message": "Non-success status",
            "response": None,
        }
        try:
            txt = resp.text
            if txt and len(txt) > 2000:
                txt = txt[:2000] + "..."
            info["response"] = txt
        except Exception:
            pass
        return (False, info) if return_error else False
    except requests.RequestException as e:
        if return_error:
            return (False, {"status": None, "message": "RequestException", "exception": str(e)})
        return False
