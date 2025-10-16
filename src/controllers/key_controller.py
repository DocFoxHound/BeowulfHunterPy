import tkinter as tk
from typing import Optional

import backup_loader
import global_variables
from config import get_player_name, set_sc_log_location, find_rsi_handle
from keys import validate_api_key, save_api_key, load_existing_key
from theme import BUTTON_STYLE as THEME_BUTTON_STYLE


class KeyController:
    def __init__(self, app, key_section: tk.Frame, key_entry: tk.Entry, log_text_area: Optional[tk.Text]):
        self.app = app
        self.key_section = key_section
        self.key_entry = key_entry
        self.log_text_area = log_text_area
        # Key indicator blink state
        self._key_blink_job = None
        self._key_blink_state = False
        self._key_good = False

    def _set_tabs_enabled(self, enabled: bool):
        """Enable or disable the Graphs and Functions tabs.
        If disabling and one of those tabs is selected, switch back to Main.
        """
        try:
            nb = getattr(self.app, 'notebook', None)
            tabs = getattr(self.app, 'tabs', {})
            graphs_tab = tabs.get('graphs')
            functions_tab = tabs.get('functions')
            main_tab = tabs.get('main')
            if nb is None:
                return
            state = 'normal' if enabled else 'disabled'
            try:
                if graphs_tab is not None:
                    nb.tab(graphs_tab, state=state)
            except Exception:
                pass
            try:
                if functions_tab is not None:
                    nb.tab(functions_tab, state=state)
            except Exception:
                pass
            if not enabled:
                try:
                    current = nb.select()
                    if current in (str(graphs_tab), str(functions_tab)) and main_tab is not None:
                        nb.select(main_tab)
                except Exception:
                    pass
        except Exception:
            pass

    def log(self, msg: str):
        try:
            global_variables.log(msg)
        except Exception:
            pass

    def _current_state(self):
        current_log = global_variables.get_log_file_location()
        current_handle = global_variables.get_rsi_handle()
        current_player = None
        try:
            if current_log:
                current_player = get_player_name(current_log)
        except Exception:
            current_player = None
        return current_log, current_handle, current_player

    def validate_saved_key(self):
        # Ensure a key indicator exists on the banner and default to blinking (until proven valid)
        self.setup_key_indicator()
        # Ensure section visible for feedback
        try:
            self.key_section.pack()
        except Exception:
            pass
        # While the key section is visible (awaiting a valid key), hide the kill columns
        try:
            refs = getattr(self.app, 'main_tab_refs', {})
            hide_cols = refs.get('hide_kill_columns')
            if callable(hide_cols):
                hide_cols()
        except Exception:
            pass
        # Also disable non-essential tabs until a valid key is present
        self._set_tabs_enabled(False)
        current_handle = global_variables.get_rsi_handle()
        saved_key = load_existing_key()
        if saved_key:
            self.log("Validating saved key")
            if validate_api_key(saved_key, current_handle):
                self.log("Key is Valid")
                try:
                    self.key_section.pack_forget()
                except Exception:
                    pass
                # Show the columns now that a valid key exists
                try:
                    refs = getattr(self.app, 'main_tab_refs', {})
                    show_cols = refs.get('show_kill_columns')
                    if callable(show_cols):
                        show_cols()
                except Exception:
                    pass
                # Re-enable tabs
                self._set_tabs_enabled(True)
                # Populate main tab kills columns from API
                try:
                    self._populate_kills_from_api()
                except Exception as e:
                    self.log(f"Error populating kills from API: {e}")
                # Now that key is validated, show the backup controls above the log
                try:
                    # Prefer placing the button on the Functions tab controls
                    controls_parent = getattr(self.app, 'functions_controls_container', None)
                    if controls_parent is None:
                        controls_parent = getattr(self.app, 'log_controls_container', None)
                    if self.log_text_area is not None:
                        backup_loader.create_load_prev_controls(self.app, self.log_text_area, getattr(self.app, 'BUTTON_STYLE', THEME_BUTTON_STYLE), controls_parent=controls_parent)
                except Exception as e:
                    self.log(f"Error creating backup controls: {e}")
                # Update indicator to solid green
                self._update_key_indicator(True)
            else:
                self.log("KEY IS INVALID. Please re-enter a valid key from the Discord bot using /key-create.")
                self._update_key_indicator(False)
        else:
            self.log("No key found. Please enter a key.")
            self._update_key_indicator(False)
            # Ensure tabs remain disabled when no key exists
            self._set_tabs_enabled(False)

    def activate_key(self):
        try:
            self.key_section.pack()
        except Exception:
            pass
        entered_key = self.key_entry.get().strip()
        if not entered_key:
            self.log("No key entered. Please input a valid key.")
            self._update_key_indicator(False)
            # Keep columns hidden while waiting for a valid key
            try:
                refs = getattr(self.app, 'main_tab_refs', {})
                hide_cols = refs.get('hide_kill_columns')
                if callable(hide_cols):
                    hide_cols()
            except Exception:
                pass
            # Keep tabs disabled
            self._set_tabs_enabled(False)
            return

        # Snapshot current state, and if missing, try to discover on-demand
        current_log, current_handle, current_player = self._current_state()
        if not current_log:
            try:
                potential_log = set_sc_log_location()
                if potential_log:
                    global_variables.set_log_file_location(potential_log)
                    current_log = potential_log
            except Exception:
                pass
        if current_log and not current_handle:
            try:
                rh = find_rsi_handle(current_log)
                if rh:
                    global_variables.set_rsi_handle(rh)
                    current_handle = rh
            except Exception:
                pass
        if current_log and not current_player:
            try:
                current_player = get_player_name(current_log)
            except Exception:
                current_player = None

        # Do not hard-block on missing log/handle; we can still validate the key.
        if not current_log:
            self.log("Log file location not found yet. We'll still try to validate your key; start Star Citizen for full functionality.")
        if not current_player:
            self.log("RSI Handle not detected yet. Key validation can proceed; start the game to enable kill tracking.")

        if validate_api_key(entered_key, current_handle):
            save_api_key(entered_key)
            global_variables.set_key(entered_key)
            self.log("Key activated and saved. Servitor connection established.")
            try:
                self.key_section.pack_forget()
            except Exception:
                pass
            # Show the columns once activated
            try:
                refs = getattr(self.app, 'main_tab_refs', {})
                show_cols = refs.get('show_kill_columns')
                if callable(show_cols):
                    show_cols()
            except Exception:
                pass
            # Enable tabs now that key is active
            self._set_tabs_enabled(True)
            # Populate main tab kills columns from API
            try:
                self._populate_kills_from_api()
            except Exception as e:
                self.log(f"Error populating kills from API: {e}")
            try:
                controls_parent = getattr(self.app, 'functions_controls_container', None)
                if controls_parent is None:
                    controls_parent = getattr(self.app, 'log_controls_container', None)
                if self.log_text_area is not None:
                    backup_loader.create_load_prev_controls(self.app, self.log_text_area, getattr(self.app, 'BUTTON_STYLE', THEME_BUTTON_STYLE), controls_parent=controls_parent)
            except Exception as e:
                self.log(f"Error creating backup controls: {e}")
            self._update_key_indicator(True)
        else:
            self.log("Invalid key. Please enter a valid API key.")
            self._update_key_indicator(False)
            # Keep columns hidden on invalid key
            try:
                refs = getattr(self.app, 'main_tab_refs', {})
                hide_cols = refs.get('hide_kill_columns')
                if callable(hide_cols):
                    hide_cols()
            except Exception:
                pass
            # Keep tabs disabled
            self._set_tabs_enabled(False)

    # --- Key indicator management ---
    def setup_key_indicator(self):
        """Ensure a square key status indicator exists on the banner canvas."""
        try:
            canvas = getattr(self.app, 'banner_canvas', None)
        except Exception:
            canvas = None
        if canvas is None:
            return
        rect_id = getattr(self.app, 'key_status_rect_id', None)
        if rect_id is None:
            try:
                # Position: same y as game indicator (8..24), adjusted to x=123..139
                rect_id = canvas.create_rectangle(123, 8, 139, 24, fill="#7a2222", outline="#000000", width=1)
                setattr(self.app, 'key_status_rect_id', rect_id)
                try:
                    canvas.tag_bind(rect_id, "<Enter>", lambda e: self._maybe_show_key_tooltip(e))
                    canvas.tag_bind(rect_id, "<Leave>", lambda e: self._hide_key_tooltip())
                except Exception:
                    pass
            except Exception:
                pass
        # Default to blinking until updated by validation
        self._start_key_blink()

    def _update_key_indicator(self, good: bool):
        self._key_good = bool(good)
        if good:
            self._stop_key_blink()
            try:
                canvas = getattr(self.app, 'banner_canvas', None)
                rect_id = getattr(self.app, 'key_status_rect_id', None)
                if canvas is not None and rect_id is not None:
                    canvas.itemconfig(rect_id, fill="#28a745")
            except Exception:
                pass
        else:
            self._start_key_blink()

    def _maybe_show_key_tooltip(self, event=None):
        try:
            tip = getattr(self.app, '_key_status_tooltip', None)
            if tip is not None:
                try:
                    tip.destroy()
                except Exception:
                    pass
            tip = tk.Toplevel(self.app)
            tip.wm_overrideredirect(True)
            tip.config(bg="#202020")
            x = (event.x_root + 12) if event else self.app.winfo_rootx() + 12
            y = (event.y_root + 12) if event else self.app.winfo_rooty() + 12
            tip.wm_geometry(f"+{x}+{y}")
            msg = "Valid Key" if self._key_good else "Invalid Key"
            lbl = tk.Label(tip, text=msg, bg="#202020", fg="#ffcccc", bd=1, relief="solid", font=("Times New Roman", 10))
            lbl.pack(ipadx=6, ipady=3)
            setattr(self.app, '_key_status_tooltip', tip)
        except Exception:
            pass

    def _hide_key_tooltip(self):
        try:
            tip = getattr(self.app, '_key_status_tooltip', None)
            if tip is not None:
                tip.destroy()
                setattr(self.app, '_key_status_tooltip', None)
        except Exception:
            pass

    def _start_key_blink(self):
        if self._key_blink_job is not None:
            return

        def _blink():
            try:
                canvas = getattr(self.app, 'banner_canvas', None)
                rect_id = getattr(self.app, 'key_status_rect_id', None)
                if canvas is None or rect_id is None:
                    # Nothing to do; stop scheduling
                    self._key_blink_job = None
                    return
                self._key_blink_state = not self._key_blink_state
                color = "#ff4444" if self._key_blink_state else "#7a2222"
                canvas.itemconfig(rect_id, fill=color)
            except Exception:
                pass
            try:
                self._key_blink_job = self.app.after(600, _blink)
            except Exception:
                self._key_blink_job = None

        # Initialize blink state and schedule
        self._key_blink_state = False
        try:
            self._key_blink_job = self.app.after(600, _blink)
        except Exception:
            self._key_blink_job = None

    def _stop_key_blink(self):
        if self._key_blink_job is not None:
            try:
                self.app.after_cancel(self._key_blink_job)
            except Exception:
                pass
            self._key_blink_job = None
        # Ensure final color is the 'bad' steady color only if not good; callers set good color

    # --- Kills population helpers ---
    def _populate_kills_from_api(self):
        """Fetch kills using the API and render into the two columns."""
        try:
            # Ensure we have a user_id (set during validate_api_key)
            # Fetch and classify
            from parser import fetch_and_classify_api_kills_for_ui  # local import to avoid cycles
        except Exception:
            return

        try:
            pu, ac = fetch_and_classify_api_kills_for_ui()
        except Exception:
            pu, ac = [], []

        # Get main tab references
        try:
            refs = getattr(self.app, 'main_tab_refs', {})
            clear_pu = refs.get('clear_pu_kills')
            clear_ac = refs.get('clear_ac_kills')
            add_pu = refs.get('add_pu_kill_card')
            add_ac = refs.get('add_ac_kill_card')
            set_pu_count = refs.get('set_pu_kills_count')
            set_ac_count = refs.get('set_ac_kills_count')
        except Exception:
            clear_pu = clear_ac = add_pu = add_ac = set_pu_count = set_ac_count = None

        # Clear existing
        try:
            if callable(clear_pu):
                clear_pu()
        except Exception:
            pass
        try:
            if callable(clear_ac):
                clear_ac()
        except Exception:
            pass

    # Update header counts (grand totals; display is capped separately at 10)
        try:
            if callable(set_pu_count):
                set_pu_count(len(pu))
        except Exception:
            pass
        try:
            if callable(set_ac_count):
                set_ac_count(len(ac))
        except Exception:
            pass

        # Render new cards (victim + method icon)
        # Instead of rendering directly, prefer to rebuild lists from combined all_kills
        try:
            refs = getattr(self.app, 'main_tab_refs', {})
            refresh = refs.get('refresh_kill_columns')
            if callable(refresh):
                refresh()
        except Exception:
            pass
