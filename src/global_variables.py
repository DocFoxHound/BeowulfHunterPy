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
# When True, `log()` will suppress writing messages (useful during bulk ops)
suppress_logs = False

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


def set_user_id(uid):
    """Set the current user id (geid or account id) used by other modules."""
    global user_id
    user_id = uid


def get_user_id():
    """Return the currently configured user id, or None if not set."""
    return user_id


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