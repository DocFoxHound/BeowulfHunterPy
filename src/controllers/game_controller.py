import tkinter as tk
from typing import Optional

import global_variables
from config import set_sc_log_location, find_rsi_handle, is_game_running
import parser
from crash_detection import game_heartbeat


class GameController:
    def __init__(self, app, banner_canvas: Optional[tk.Canvas] = None):
        self.app = app
        self.banner_canvas = banner_canvas
        self._blink_job = None
        self._blink_state = False
        self._services_started = False
        # Track current running state for tooltip logic
        setattr(self.app, 'game_running_state', False)

    def setup_indicator(self):
        try:
            running_now = is_game_running()
        except Exception:
            running_now = False
        color_now = "#28a745" if running_now else "#ff4444"

        if self.banner_canvas is not None:
            try:
                oid = getattr(self.app, 'game_status_oval_id', None)
                if oid is None:
                    oid = self.banner_canvas.create_oval(8, 8, 24, 24, fill=color_now, outline="#000000", width=1)
                    setattr(self.app, 'game_status_oval_id', oid)
                    try:
                        self.banner_canvas.tag_bind(oid, "<Enter>", lambda e: self._maybe_show_status_tooltip(e))
                        self.banner_canvas.tag_bind(oid, "<Leave>", lambda e: self._hide_status_tooltip())
                    except Exception:
                        pass
                else:
                    self.banner_canvas.itemconfig(oid, fill=color_now)
            except Exception:
                pass
        else:
            # Fallback label if no banner canvas exists
            try:
                header_frame = getattr(self.app, 'header_frame', None)
                lbl = getattr(self.app, 'game_status_label', None)
                if lbl is None and header_frame is not None:
                    lbl = tk.Label(
                        header_frame,
                        text=("● Game: Running" if running_now else "● Game: Not Running"),
                        font=("Times New Roman", 12),
                        fg=color_now,
                        bg="#1a1a1a",
                    )
                    lbl.pack(side=tk.LEFT, padx=(0, 8))
                    setattr(self.app, 'game_status_label', lbl)
                    try:
                        lbl.bind("<Enter>", lambda e: self._maybe_show_status_tooltip(e))
                        lbl.bind("<Leave>", lambda e: self._hide_status_tooltip())
                    except Exception:
                        pass
                elif lbl is not None:
                    lbl.config(text=("● Game: Running" if running_now else "● Game: Not Running"), fg=color_now)
            except Exception:
                pass

        # Initialize indicator and start monitor
        self._update_indicator(running_now)
        if running_now:
            self._start_game_services_once()
        self._poll()

    def _update_indicator(self, running: bool):
        setattr(self.app, 'game_running_state', bool(running))
        color = "#28a745" if running else "#ff4444"
        try:
            if self.banner_canvas is not None:
                oid = getattr(self.app, 'game_status_oval_id', None)
                if oid is not None:
                    self.banner_canvas.itemconfig(oid, fill=color)
            lbl = getattr(self.app, 'game_status_label', None)
            if lbl is not None:
                lbl.config(text=("● Game: Running" if running else "● Game: Not Running"), fg=color)
        except Exception:
            pass

        # Manage blinking
        try:
            if running:
                self._stop_offline_blink()
            else:
                self._start_offline_blink()
        except Exception:
            pass

    def _start_game_services_once(self):
        if self._services_started:
            return
        try:
            global_variables.set_log_file_location(set_sc_log_location())
            log_file_location = global_variables.get_log_file_location()
            if log_file_location:
                try:
                    rsi_handle = find_rsi_handle(log_file_location)
                    if rsi_handle:
                        global_variables.set_rsi_handle(rsi_handle)
                        try:
                            parser.start_tail_log_thread(log_file_location, rsi_handle)
                        except Exception as e:
                            global_variables.log(f"Failed to start log tail: {e}")
                        try:
                            game_heartbeat(1, True)
                        except Exception as e:
                            global_variables.log(f"Failed to start heartbeat: {e}")
                        self._services_started = True
                    else:
                        global_variables.log("RSI handle not found; will retry once logs are available.")
                except Exception as e:
                    global_variables.log(f"Error discovering RSI handle: {e}")
            else:
                global_variables.log("Log file location not found; waiting for game to write logs.")
        except Exception as e:
            global_variables.log(f"Error starting game services: {e}")

    def _poll(self):
        try:
            running = is_game_running()
        except Exception:
            running = False
        # If state changed, update indicator and possibly start services
        try:
            prev = bool(getattr(self.app, 'game_running_state', False))
        except Exception:
            prev = False
        if running != prev:
            self._update_indicator(running)
            if running:
                self._start_game_services_once()
        try:
            self.app.after(1000, self._poll)
        except Exception:
            pass

    def _maybe_show_status_tooltip(self, event=None):
        try:
            running = bool(getattr(self.app, 'game_running_state', False))
        except Exception:
            running = False
        if running:
            return
        try:
            tip = getattr(self.app, '_status_tooltip', None)
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
            lbl = tk.Label(tip, text="Game offline", bg="#202020", fg="#ffcccc", bd=1, relief="solid", font=("Times New Roman", 10))
            lbl.pack(ipadx=6, ipady=3)
            setattr(self.app, '_status_tooltip', tip)
        except Exception:
            pass

    def _hide_status_tooltip(self):
        try:
            tip = getattr(self.app, '_status_tooltip', None)
            if tip is not None:
                tip.destroy()
                setattr(self.app, '_status_tooltip', None)
        except Exception:
            pass

    def _start_offline_blink(self):
        if self._blink_job is not None:
            return

        def _blink():
            try:
                running = bool(getattr(self.app, 'game_running_state', False))
            except Exception:
                running = False
            if running:
                self._stop_offline_blink()
                return
            try:
                self._blink_state = not self._blink_state
                color = "#ff4444" if self._blink_state else "#7a2222"
                if self.banner_canvas is not None:
                    oid = getattr(self.app, 'game_status_oval_id', None)
                    if oid is not None:
                        self.banner_canvas.itemconfig(oid, fill=color)
                else:
                    lbl = getattr(self.app, 'game_status_label', None)
                    if lbl is not None:
                        lbl.config(fg=color)
            except Exception:
                pass
            try:
                self._blink_job = self.app.after(600, _blink)
            except Exception:
                pass

        self._blink_state = False
        try:
            self._blink_job = self.app.after(600, _blink)
        except Exception:
            pass

    def _stop_offline_blink(self):
        if self._blink_job is not None:
            try:
                self.app.after_cancel(self._blink_job)
            except Exception:
                pass
            self._blink_job = None
        try:
            running = bool(getattr(self.app, 'game_running_state', False))
        except Exception:
            running = False
        color = "#28a745" if running else "#ff4444"
        try:
            if self.banner_canvas is not None:
                oid = getattr(self.app, 'game_status_oval_id', None)
                if oid is not None:
                    self.banner_canvas.itemconfig(oid, fill=color)
            else:
                lbl = getattr(self.app, 'game_status_label', None)
                if lbl is not None:
                    lbl.config(fg=color, text=("● Game: Running" if running else "● Game: Not Running"))
        except Exception:
            pass
