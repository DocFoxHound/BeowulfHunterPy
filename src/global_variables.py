import tkinter as tk
import functools
import traceback
import os
import time

class EventLogger:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def log(self, message):
        """Log a message to the associated Tkinter Text widget in a thread-safe way.

        If called from a non-main thread, we schedule the widget update with
        `after(0, ...)` so Tkinter operations happen on the main loop. If the
        text widget is not available or an error occurs, fall back to printing.
        """
        def _append():
            try:
                self.text_widget.config(state=tk.NORMAL)
                self.text_widget.insert(tk.END, message + "\n")
                self.text_widget.config(state=tk.DISABLED)
                self.text_widget.see(tk.END)
            except Exception:
                # If widget operations fail for any reason, fallback to stdout
                print(message)

        try:
            # Schedule the append on the Tkinter main thread if possible
            self.text_widget.after(0, _append)
        except Exception:
            # If `after` is not available or fails, attempt direct call as a last resort
            try:
                _append()
            except Exception:
                print(message)

# global_state.py
rsi_handle = None
logger = None
key = None
rsi_handle = None
log_file_location = None
user_id = None
tk_app = None
main_tab_refs = {}
# When True, `log()` will suppress writing messages (useful during bulk ops)
suppress_logs = False
org_key = None
custom_sound_interdiction = None  # absolute path to custom sound for Interdicted (Fake Hit)
custom_sound_nearby = None        # absolute path to custom sound for Nearby (Actor Stall)
custom_sound_kill = None          # absolute path to custom sound for Kill event
overlay_corner = 'top-right'      # 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'
overlay_enabled = False
overlay_manager = None
overlay_show_kills = True
overlay_show_interdictions = True
overlay_show_nearby = True

# Sound/notice toggle flags
play_kill_sound = True
play_snare_sound = True       # snare == interdiction/fake_hit
play_proximity_sound = True   # proximity == actor_stall

# Optional separate refs for Proximity tab
proximity_tab_refs = {}

# Current game patch version (e.g., "4.3") discovered from remote API
patch_version = None

# API kills storage for UI population (fetched from remote API)
api_kills_data = []        # full normalized list of kills
api_kills_pu = []          # subset classified as PU
api_kills_ac = []          # subset classified as AC
api_kills_all = []         # combined list in API-like schema (API + live)
# General-purpose combined list of all kills, referenced by graphs tab
all_kills = []
 # Last failed uploads from backup parsing (list of parsed kill dicts)
last_failed_uploads = []
kill_processing_count = 0

"""Player proximity-related event tracking.

We keep both the raw typed lists (actor stall & fake hit for legacy callers) and
an aggregated `proximity_reports` list consumed by the Proximity tab for card
rendering. The aggregated list stores newest events at the end and is trimmed
to `PROXIMITY_REPORTS_MAX` so the UI only ever displays a bounded recent history.

Schema for aggregated proximity_reports entries:
{
    'kind': 'actor_stall' | 'fake_hit' | 'kill',
    'player': str,          # primary player (victim for kill, nearby/interdicted player for others)
    'from_player': Optional[str],  # initiator for fake_hit (snare)
    'ship': Optional[str],  # ship context (fake_hit or kill ship_used)
    'timestamp': str | None, # ISO timestamp if available
    'overlay_added': float, # epoch seconds when added (used for overlay & pruning)
}
"""
actor_stall_events = []  # legacy list (trimmed separately)
fake_hit_events = []     # legacy list (trimmed separately)
proximity_reports = []   # unified list for UI

# Limits
ACTOR_STALL_MAX = 100
FAKE_HIT_MAX = 10  # legacy retention for fake hits (snare pinning behavior)
PROXIMITY_REPORTS_MAX = 100
PROXIMITY_DEDUP_SECONDS = 5.0  # ignore same kind/player repeats inside this window

def set_rsi_handle(handle):
    global rsi_handle
    rsi_handle = handle

def get_rsi_handle():
    return rsi_handle

def set_logger(text_area):
    global logger
    logger = EventLogger(text_area)

def get_logger():
    return logger

def set_key(text):
    global key
    key = text

def get_key():
    return key

def set_org_key(text):
    global org_key
    org_key = text

def get_org_key():
    return org_key

# --- Custom sound paths (user-configurable) ---
def set_custom_sound_interdiction(path: str | None):
    global custom_sound_interdiction
    try:
        custom_sound_interdiction = str(path) if path else None
    except Exception:
        custom_sound_interdiction = None

def get_custom_sound_interdiction() -> str | None:
    try:
        return custom_sound_interdiction
    except Exception:
        return None

def set_custom_sound_nearby(path: str | None):
    global custom_sound_nearby
    try:
        custom_sound_nearby = str(path) if path else None
    except Exception:
        custom_sound_nearby = None

def get_custom_sound_nearby() -> str | None:
    try:
        return custom_sound_nearby
    except Exception:
        return None

def set_custom_sound_kill(path: str | None):
    global custom_sound_kill
    try:
        custom_sound_kill = str(path) if path else None
    except Exception:
        custom_sound_kill = None

def get_custom_sound_kill() -> str | None:
    try:
        return custom_sound_kill
    except Exception:
        return None

# --- Overlay settings and manager ---
def set_overlay_corner(pos: str):
    global overlay_corner
    try:
        if str(pos) in ('top-left', 'top-right', 'bottom-left', 'bottom-right'):
            overlay_corner = str(pos)
    except Exception:
        pass

def get_overlay_corner() -> str:
    try:
        return overlay_corner
    except Exception:
        return 'top-right'

def set_overlay_enabled(enabled: bool):
    global overlay_enabled
    try:
        overlay_enabled = bool(enabled)
    except Exception:
        overlay_enabled = False

def is_overlay_enabled() -> bool:
    try:
        return bool(overlay_enabled)
    except Exception:
        return False

def set_overlay_manager(mgr):
    global overlay_manager
    overlay_manager = mgr

def get_overlay_manager():
    return overlay_manager

def set_overlay_filters(show_kills: bool | None = None, show_interdictions: bool | None = None, show_nearby: bool | None = None):
    global overlay_show_kills, overlay_show_interdictions, overlay_show_nearby
    try:
        if show_kills is not None:
            overlay_show_kills = bool(show_kills)
        if show_interdictions is not None:
            overlay_show_interdictions = bool(show_interdictions)
        if show_nearby is not None:
            overlay_show_nearby = bool(show_nearby)
    except Exception:
        pass

def get_overlay_filters():
    try:
        return {
            'kills': bool(overlay_show_kills),
            'interdictions': bool(overlay_show_interdictions),
            'nearby': bool(overlay_show_nearby),
        }
    except Exception:
        return {'kills': True, 'interdictions': True, 'nearby': True}

# Show/Play toggles API
def set_show_kill_notice(val: bool):
    try:
        set_overlay_filters(show_kills=bool(val))
    except Exception:
        pass

def get_show_kill_notice() -> bool:
    try:
        return bool(overlay_show_kills)
    except Exception:
        return True

def set_show_snare_notice(val: bool):
    try:
        set_overlay_filters(show_interdictions=bool(val))
    except Exception:
        pass

def get_show_snare_notice() -> bool:
    try:
        return bool(overlay_show_interdictions)
    except Exception:
        return True

def set_show_proximity_notice(val: bool):
    try:
        set_overlay_filters(show_nearby=bool(val))
    except Exception:
        pass

def get_show_proximity_notice() -> bool:
    try:
        return bool(overlay_show_nearby)
    except Exception:
        return True

def set_play_kill_sound(val: bool):
    global play_kill_sound
    try:
        play_kill_sound = bool(val)
    except Exception:
        play_kill_sound = True

def get_play_kill_sound() -> bool:
    try:
        return bool(play_kill_sound)
    except Exception:
        return True

def set_play_snare_sound(val: bool):
    global play_snare_sound
    try:
        play_snare_sound = bool(val)
    except Exception:
        play_snare_sound = True

def get_play_snare_sound() -> bool:
    try:
        return bool(play_snare_sound)
    except Exception:
        return True

def set_play_proximity_sound(val: bool):
    global play_proximity_sound
    try:
        play_proximity_sound = bool(val)
    except Exception:
        play_proximity_sound = True

def get_play_proximity_sound() -> bool:
    try:
        return bool(play_proximity_sound)
    except Exception:
        return True

def set_proximity_tab_refs(refs):
    global proximity_tab_refs
    try:
        proximity_tab_refs = dict(refs) if refs is not None else {}
    except Exception:
        proximity_tab_refs = {}

def get_proximity_tab_refs():
    try:
        return proximity_tab_refs
    except Exception:
        return {}

def set_rsi_handle(handle):
    global rsi_handle
    rsi_handle = handle

def get_rsi_handle():
    return rsi_handle

def set_log_file_location(location):
    global log_file_location
    log_file_location = location
    try:
        # Log both the file path and its parent folder (if any)
        folder = os.path.dirname(location) if location else None
        # Use local module log() so it routes to GUI logger if available
        if location:
            log(f"Log file location set to: {location}")
        else:
            log("Log file location cleared or not found")
        if folder:
            log(f"Log folder: {folder}")
    except Exception:
        # Never allow logging to break state assignment
        pass

def get_log_file_location():
    return log_file_location


def set_app(app):
    """Store a reference to the Tk root app for cross-module UI scheduling."""
    global tk_app
    tk_app = app


def get_app():
    """Return the Tk app if set, else None."""
    return tk_app


def set_main_tab_refs(refs):
    """Store refs returned by the Main tab builder for other modules (e.g., parser)."""
    global main_tab_refs
    try:
        main_tab_refs = dict(refs) if refs is not None else {}
    except Exception:
        main_tab_refs = {}


def get_main_tab_refs():
    """Return the latest stored Main tab refs dict (may be empty)."""
    return main_tab_refs


def set_user_id(uid):
    """Set the current user id (geid or account id) used by other modules."""
    global user_id
    user_id = uid


def get_user_id():
    """Return the currently configured user id, or None if not set."""
    return user_id


# --- Patch version getters/setters ---
def set_patch_version(patch: str):
    """Store the latest game patch version string (e.g., '4.3')."""
    global patch_version
    try:
        patch_version = str(patch) if patch is not None else None
    except Exception:
        patch_version = None


def get_patch_version():
    """Return the last stored game patch version string, or None if unknown."""
    return patch_version


# --- API kills getters/setters for UI ---
def set_api_kills_data(data_list):
    """Set the full, normalized list of kills fetched from the API for UI use."""
    global api_kills_data
    try:
        api_kills_data = list(data_list) if data_list is not None else []
    except Exception:
        api_kills_data = []


def get_api_kills_data():
    """Return the last fetched full normalized list of API kills for UI."""
    return api_kills_data


def set_api_kills_split(pu_list, ac_list):
    """Store the PU/AC split lists for convenient UI consumption."""
    global api_kills_pu, api_kills_ac
    try:
        api_kills_pu = list(pu_list) if pu_list is not None else []
    except Exception:
        api_kills_pu = []
    try:
        api_kills_ac = list(ac_list) if ac_list is not None else []
    except Exception:
        api_kills_ac = []


def get_api_kills_split():
    """Return a tuple (pu_list, ac_list) representing the last stored split."""
    return api_kills_pu, api_kills_ac


# --- Combined kills (API-like schema) ---
def set_api_kills_all(items):
    """Set the combined kills list (API + live) using the API-like schema.

    Each item should be a dict like:
    {
        "id": str, "user_id": str, "ship_used": Optional[str], "ship_killed": Optional[str],
        "value": int, "kill_count": int, "victims": List[str], "patch": str,
        "game_mode": str, "timestamp": str
    }
    """
    global api_kills_all, all_kills
    try:
        api_kills_all = list(items) if items is not None else []
        # Keep all_kills in sync so other modules (e.g., graphs) can reference it
        try:
            all_kills = list(api_kills_all)
        except Exception:
            pass
    except Exception:
        api_kills_all = []
        try:
            all_kills = []
        except Exception:
            pass


def get_api_kills_all():
    """Return the combined kills list (API + live) in API-like schema."""
    return api_kills_all


# --- all_kills direct access (alias for api_kills_all) ---
def set_all_kills(items):
    """Set general-purpose all_kills list and keep api_kills_all in sync."""
    global all_kills, api_kills_all
    try:
        all_kills = list(items) if items is not None else []
        api_kills_all = list(all_kills)
    except Exception:
        all_kills = []
        api_kills_all = []


def get_all_kills():
    """Return the general-purpose all_kills list (alias of api_kills_all)."""
    return all_kills


# --- failed uploads from backup parsing ---
def set_last_failed_uploads(items):
    """Store the most recent list of failed upload records from backup parsing."""
    global last_failed_uploads
    try:
        last_failed_uploads = list(items) if items is not None else []
    except Exception:
        last_failed_uploads = []


def get_last_failed_uploads():
    """Return the last failed upload records from backup parsing (list of dicts)."""
    return last_failed_uploads


# --- kill processing count ---
def set_kill_processing_count(n: int):
    global kill_processing_count
    try:
        kill_processing_count = int(n)
    except Exception:
        pass


def get_kill_processing_count() -> int:
    try:
        return int(kill_processing_count)
    except Exception:
        return 0


def inc_kill_processing_count(delta: int = 1) -> int:
    try:
        set_kill_processing_count(get_kill_processing_count() + int(delta))
        return get_kill_processing_count()
    except Exception:
        return get_kill_processing_count()


def dec_kill_processing_count(delta: int = 1) -> int:
    try:
        set_kill_processing_count(max(0, get_kill_processing_count() - int(delta)))
        return get_kill_processing_count()
    except Exception:
        return get_kill_processing_count()


# --- Player event helpers ---
def add_actor_stall_event(event: dict):
    """Append an actor stall event and also register a unified proximity report."""
    try:
        global actor_stall_events
        rec = dict(event)
        now_ts = time.time()
        rec.setdefault('overlay_added', now_ts)
        actor_stall_events.append(rec)
        if len(actor_stall_events) > ACTOR_STALL_MAX:
            actor_stall_events = actor_stall_events[-ACTOR_STALL_MAX:]
        # Unified report
        add_proximity_report({
            'kind': 'actor_stall',
            'player': rec.get('player'),
            'from_player': None,
            'ship': None,
            'timestamp': rec.get('timestamp'),
            'overlay_added': rec.get('overlay_added') or now_ts,
        })
    except Exception:
        pass


def get_actor_stall_events():
    try:
        return list(actor_stall_events)
    except Exception:
        return []


def add_fake_hit_event(event: dict):
    """Add a fake hit (snare/interdiction) event & unified proximity report."""
    try:
        global fake_hit_events
        rec = dict(event)
        now_ts = time.time()
        rec.setdefault('overlay_added', now_ts)
        fake_hit_events.append(rec)
        if len(fake_hit_events) > FAKE_HIT_MAX:
            fake_hit_events = fake_hit_events[-FAKE_HIT_MAX:]
        add_proximity_report({
            'kind': 'fake_hit',
            'player': rec.get('target_player') or rec.get('player'),
            'from_player': rec.get('from_player'),
            'ship': rec.get('ship'),
            'timestamp': rec.get('timestamp'),
            'overlay_added': rec.get('overlay_added') or now_ts,
        })
    except Exception:
        pass


def get_fake_hit_events():
    try:
        return list(fake_hit_events)
    except Exception:
        return []


def prune_expired_fake_hit_events(now_ts: float):
    """Remove expired fake hit events (where expires_at < now_ts)."""
    try:
        global fake_hit_events
        fake_hit_events = [e for e in fake_hit_events if (e.get('expires_at') or 0) >= now_ts]
    except Exception:
        pass

def add_proximity_report(rec: dict):
    """Add a unified proximity report card entry.

    Dedupes same kind+player within PROXIMITY_DEDUP_SECONDS to avoid spam when
    parser already debounces but tests/users manually inject.
    """
    try:
        global proximity_reports
        now_ts = time.time()
        kind = rec.get('kind')
        player = rec.get('player')
        # Dedup check: find last matching kind+player within window
        if kind and player:
            for prev in reversed(proximity_reports[-10:]):  # search recent subset for speed
                try:
                    if prev.get('kind') == kind and prev.get('player') == player:
                        age = now_ts - float(prev.get('overlay_added') or now_ts)
                        if age < PROXIMITY_DEDUP_SECONDS:
                            return  # ignore duplicate burst
                        break
                except Exception:
                    pass
        entry = {
            'kind': kind,
            'player': player,
            'from_player': rec.get('from_player'),
            'ship': rec.get('ship'),
            'timestamp': rec.get('timestamp'),
            'overlay_added': rec.get('overlay_added') or now_ts,
        }
        proximity_reports.append(entry)
        if len(proximity_reports) > PROXIMITY_REPORTS_MAX:
            proximity_reports = proximity_reports[-PROXIMITY_REPORTS_MAX:]
    except Exception:
        pass

def get_proximity_reports():
    try:
        return list(proximity_reports)
    except Exception:
        return []


def log(message):
    """Convenience function to write a message to the GUI logger if present.

    Usage: import global_variables as gv; gv.log("message")

    This is safe to call from any thread. If no GUI logger has been set,
    the message is printed to stdout.
    """
    try:
        # quick global suppression hook used by backup loader to avoid
        # spamming the UI while parsing many files
        try:
            if suppress_logs:
                return
        except Exception:
            pass

        if logger is not None:
            logger.log(message)
        else:
            print(message)
    except Exception:
        # Ensure logging never raises for callers
        try:
            print(message)
        except Exception:
            pass


def log_exceptions(func):
    """Decorator that logs any exception raised by the wrapped function.

    The traceback is sent to `log()` so it appears in the GUI (if initialized)
    or stdout as a fallback. The exception is re-raised after logging so
    normal exception handling behavior is preserved.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            tb = traceback.format_exc()
            try:
                log(f"Exception in {func.__module__}.{func.__name__}:\n{tb}")
            except Exception:
                # As a last resort, print the traceback
                print(f"Exception in {func.__module__}.{func.__name__}:\n{tb}")
            raise
    return wrapper