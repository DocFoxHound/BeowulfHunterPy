import os
import threading
import parser
import global_variables
from config import find_rsi_handle
import tkinter as _tk


def create_load_prev_controls(app, text_area, button_style=None, controls_parent=None):
    """Create controls to load previous logs and start parsing in a background thread.

    Adds a "Load Previous Logs" button and updates the provided text_area with
    a single-line loading progress. The button is disabled while parsing.
    """
    try:
        parent = controls_parent if controls_parent is not None else getattr(text_area, 'master', app)
        control_frame = _tk.Frame(parent, bg="#1a1a1a")

        try:
            if controls_parent is None:
                control_frame.pack(pady=(5, 0), before=text_area)
            else:
                control_frame.pack(side=_tk.LEFT, padx=(5, 0), pady=(5, 0))
        except Exception:
            control_frame.pack(pady=(5, 0))

        bstyle = button_style if button_style is not None else {
            "bg": "#0f0f0f",
            "fg": "#ff5555",
            "activebackground": "#330000",
            "activeforeground": "#ffffff",
            "relief": "ridge",
            "bd": 2,
            "font": ("Orbitron", 12)
        }

        tk = os.sys.modules['tkinter']
        load_prev_button = tk.Button(control_frame, text="Load Previous Logs", **bstyle)
        load_prev_button.pack(side=tk.LEFT, padx=(5, 0))

        try:
            text_area.tag_configure('loading', foreground='#ff5555', background='#1a1a1a', font=("Orbitron", 11))
        except Exception:
            pass

        def _load_backups_worker():
            # discover backup directory
            backup_dir = None
            log_file_location = None
            try:
                log_file_location = global_variables.get_log_file_location()
                if log_file_location:
                    game_dir = os.path.dirname(log_file_location)
                    candidate = os.path.join(game_dir, 'logbackups')
                    if os.path.isdir(candidate):
                        backup_dir = candidate
            except Exception:
                pass

            if not backup_dir:
                candidate = os.path.join(os.path.abspath('.'), 'logbackups')
                if os.path.isdir(candidate):
                    backup_dir = candidate

            rsi_handle = global_variables.get_rsi_handle()
            if not rsi_handle and log_file_location:
                try:
                    rsi_handle = find_rsi_handle(log_file_location)
                except Exception:
                    pass

            try:
                global_variables.log(f"Parsing backup logs from: {backup_dir} (RSI: {rsi_handle})")
            except Exception:
                pass

            def progress_cb(index, total, filepath):
                # schedule a concise in-text update
                def _update():
                    try:
                        pct = int((index / total) * 100) if total else 0
                        bar_len = 24
                        filled = int((pct * bar_len) / 100)
                        bar = '[' + ('#' * filled) + ('-' * (bar_len - filled)) + ']'
                        line = f"Loading logs {bar} {index}/{total} ({pct}%)"

                        ranges = text_area.tag_ranges('loading')
                        prev_state = None
                        try:
                            prev_state = text_area.cget('state')
                        except Exception:
                            prev_state = None
                        try:
                            try:
                                text_area.config(state=_tk.NORMAL)
                            except Exception:
                                pass

                            if not ranges:
                                text_area.insert(_tk.END, line + '\n', ('loading',))
                            else:
                                try:
                                    text_area.delete(ranges[0], ranges[1])
                                    text_area.insert(ranges[0], line + '\n', ('loading',))
                                except Exception:
                                    text_area.insert(_tk.END, line + '\n', ('loading',))
                        finally:
                            try:
                                if prev_state is not None:
                                    text_area.config(state=prev_state)
                            except Exception:
                                pass

                        text_area.see(_tk.END)
                    except Exception:
                        try:
                            global_variables.log(f"Parsing backups: {index}/{total} - {filepath}")
                        except Exception:
                            pass

                try:
                    text_area.after(0, _update)
                except Exception:
                    pass

            # run parser quietly
            try:
                global_variables.suppress_logs = True
            except Exception:
                pass

            # Ensure API kills cache is refreshed before parsing so duplicate
            # detection uses the latest data. Run refresh synchronously here to
            # avoid races (it's typically fast), but guard failures so parsing
            # still proceeds.
            try:
                try:
                    parser.refresh_api_kills_cache(global_variables.get_user_id())
                except Exception:
                    pass
            except Exception:
                pass

            parsed_count = 0
            duplicates_count = 0
            try:
                parsed_count, duplicates_count = parser.parse_backup_logs(backup_dir, rsi_handle, global_variables.get_user_id(), progress_callback=progress_cb, suppress_file_logs=True)
            finally:
                try:
                    global_variables.suppress_logs = False
                except Exception:
                    pass

            # final UI update on main thread
            def _done():
                try:
                    ranges = text_area.tag_ranges('loading')
                    if ranges:
                        prev_state = None
                        try:
                            prev_state = text_area.cget('state')
                        except Exception:
                            prev_state = None
                        try:
                            try:
                                text_area.config(state=_tk.NORMAL)
                            except Exception:
                                pass
                            text_area.delete(ranges[0], ranges[1])
                        finally:
                            try:
                                if prev_state is not None:
                                    text_area.config(state=prev_state)
                            except Exception:
                                pass

                    text_area.insert(_tk.END, "Parsing backup logs complete.\n")
                    try:
                        global_variables.log(f"Parsing backup logs complete. Parsed: {parsed_count}, Duplicates skipped: {duplicates_count}")
                    except Exception:
                        pass

                    try:
                        load_prev_button.config(state=_tk.NORMAL)
                    except Exception:
                        pass
                except Exception:
                    try:
                        text_area.insert(_tk.END, "Parsing backup logs complete.\n")
                        load_prev_button.config(state=_tk.NORMAL)
                    except Exception:
                        pass

            try:
                text_area.after(0, _done)
            except Exception:
                pass

        def load_previous_logs():
            # Auto-switch to the Log tab so the user can see progress
            try:
                nb = getattr(app, 'notebook', None)
                tabs = getattr(app, 'tabs', {}) if nb is not None else {}
                log_tab = tabs.get('log')
                if nb is not None and log_tab is not None:
                    nb.select(log_tab)
            except Exception:
                pass
            try:
                load_prev_button.config(state=_tk.DISABLED)
            except Exception:
                pass
            threading.Thread(target=_load_backups_worker, daemon=True).start()

        load_prev_button.config(command=load_previous_logs)

    except Exception as e:
        global_variables.log(f"Failed to create Load Previous Logs controls: {e}")
