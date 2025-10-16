import tkinter as tk
import functools
import traceback

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

# API kills storage for UI population (fetched from remote API)
api_kills_data = []        # full normalized list of kills
api_kills_pu = []          # subset classified as PU
api_kills_ac = []          # subset classified as AC
api_kills_all = []         # combined list in API-like schema (API + live)
# General-purpose combined list of all kills, referenced by graphs tab
all_kills = []

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

def set_rsi_handle(handle):
    global rsi_handle
    rsi_handle = handle

def get_rsi_handle():
    return rsi_handle

def set_log_file_location(location):
    global log_file_location
    log_file_location = location

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