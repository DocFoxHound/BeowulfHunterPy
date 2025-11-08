import tkinter as tk
import global_variables
import time
from datetime import datetime, timezone

class OverlayManager:
    def __init__(self, root_app):
        self.root_app = root_app
        self.win = None
        self.width = 340
        self.bg = '#111111'
        self.fg = '#f5f5f5'
        self.border = '#333333'
        self.font = ('Consolas', 10)
        self.line_widgets = []
        # Store live event lines: [{'text': str, 'ts': float, 'kind': 'kill'|'fake_hit'|'actor_stall'}]
        self.lines = []
        # periodic refresh handle
        self._tick_id = None

    def show(self):
        if self.win is not None and self.win.winfo_exists():
            self._reposition()
            self.refresh()
            self._start_tick()
            return
        self.win = tk.Toplevel(self.root_app)
        try:
            self.win.title('')
            self.win.overrideredirect(True)
            self.win.attributes('-topmost', True)
            try:
                self.win.attributes('-alpha', 0.92)
            except Exception:
                pass
        except Exception:
            pass
        try:
            self.win.configure(bg=self.bg, highlightthickness=1, highlightbackground=self.border)
        except Exception:
            pass
        self.container = tk.Frame(self.win, bg=self.bg)
        self.container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._reposition()
        self.refresh()
        self._start_tick()

    def hide(self):
        if self.win is not None:
            try:
                self.win.destroy()
            except Exception:
                pass
        self.win = None
        self.line_widgets = []
        self.lines = []
        self._stop_tick()

    def _start_tick(self):
        # Schedule periodic refresh so fades progress even without new events
        if not self.win:
            return
        if self._tick_id is not None:
            return
        def _tick():
            self._tick_id = None
            try:
                self.refresh()
            except Exception:
                pass
            # Reschedule if window still exists
            if self.win and self.win.winfo_exists():
                try:
                    self._tick_id = self.win.after(800, _tick)
                except Exception:
                    self._tick_id = None
        try:
            self._tick_id = self.win.after(800, _tick)
        except Exception:
            self._tick_id = None

    def _stop_tick(self):
        try:
            if self.win and self._tick_id is not None:
                try:
                    self.win.after_cancel(self._tick_id)
                except Exception:
                    pass
        finally:
            self._tick_id = None

    def _reposition(self):
        try:
            corner = global_variables.get_overlay_corner()
        except Exception:
            corner = 'top-right'
        if self.win is None:
            return
        screen_w = self.win.winfo_screenwidth()
        screen_h = self.win.winfo_screenheight()
        # Estimate height based on number of active lines (max 12)
        active_count = len(self.lines)
        est_height = min((max(active_count, 1) * 18) + 12, 400)
        x = 5
        y = 5
        if corner == 'top-left':
            x = 5; y = 5
        elif corner == 'top-right':
            x = screen_w - self.width - 5; y = 5
        elif corner == 'bottom-left':
            x = 5; y = screen_h - est_height - 50
        elif corner == 'bottom-right':
            x = screen_w - self.width - 5; y = screen_h - est_height - 50
        try:
            self.win.geometry(f"{self.width}x{est_height}+{x}+{y}")
        except Exception:
            pass

    def add_event_line(self, text: str, kind: str):
        # Add a live line and schedule a future fade
        try:
            self.lines.append({'text': text, 'ts': time.time(), 'kind': kind})
        except Exception:
            pass
        self.refresh()
        self._schedule_prune()

    def _schedule_prune(self):
        if not self.win:
            return
        def _prune():
            cutoff = time.time() - 10.0  # fade after 10s
            try:
                self.lines = [l for l in self.lines if l.get('ts', 0) >= cutoff]
            except Exception:
                pass
            self.refresh()
            if self.lines:
                try:
                    self.win.after(1500, _prune)
                except Exception:
                    pass
            else:
                # hide when empty
                try:
                    self.win.withdraw()
                except Exception:
                    pass
        try:
            self.win.after(1500, _prune)
        except Exception:
            pass

    def refresh(self):
        if self.win is None or not self.win.winfo_exists():
            return
        # First, rebuild from globals so tests and live paths feed overlay
        self._rebuild_from_globals()
        # Filter by user selections
        try:
            filters = global_variables.get_overlay_filters()
        except Exception:
            filters = {'kills': True, 'interdictions': True, 'nearby': True}
        cutoff = time.time() - 10.0
        try:
            self.lines = [l for l in self.lines if l.get('ts', 0) >= cutoff]
        except Exception:
            pass
        filtered = []
        for l in self.lines:
            k = l.get('kind')
            if (k == 'kill' and filters.get('kills')) or (k == 'fake_hit' and filters.get('interdictions')) or (k == 'actor_stall' and filters.get('nearby')):
                filtered.append(l)
        # Clear existing widgets
        for w in self.line_widgets:
            try: w.destroy()
            except Exception: pass
        self.line_widgets = []
        if not filtered:
            try:
                self.win.withdraw()
            except Exception:
                pass
            return
        try:
            self.win.deiconify()
        except Exception:
            pass
        # Render last up to 12 with fade-out coloring over last 3 seconds
        now = time.time()
        for line in filtered[-12:]:
            txt = line.get('text')
            added = line.get('ts') or now
            age = max(0.0, now - float(added))
            # Fade between 7-10 seconds: t in [0,1]
            t = 0.0
            if age >= 7.0:
                t = min(1.0, (age - 7.0) / 3.0)
            fg = self._mix_color(self.bg, self.fg, t)
            lbl = tk.Label(self.container, text=txt, fg=fg, bg=self.bg, font=self.font, anchor='w', justify='left')
            lbl.pack(fill=tk.X, padx=2)
            self.line_widgets.append(lbl)
        self._reposition()

    def _rebuild_from_globals(self):
        """Rebuild the in-memory lines array from recent globals within 10s.
        This ensures overlay updates even if no explicit add_event_line calls were made.
        """
        cutoff = time.time() - 10.0
        now = time.time()
        lines = []
        # Fake hits (interdictions)
        try:
            fh = global_variables.get_fake_hit_events() or []
            for ev in reversed(fh):
                added = ev.get('overlay_added') or ev.get('expires_at') or 0
                # accept if we have overlay_added within 10s; fallback to expires_at approximating recency
                if (isinstance(added, (int, float)) and added >= cutoff) or (ev.get('timestamp') and (ev.get('overlay_added') is None)):
                    fp = ev.get('from_player') or ev.get('player')
                    tp = ev.get('target_player') or ev.get('player')
                    ship = ev.get('ship') or ''
                    ship_clean = ship.split('_')[0] if isinstance(ship, str) and ship else ''
                    age_sec = int(max(0, now - (ev.get('overlay_added') or now)))
                    text = f"INT {fp}->{tp} {ship_clean} -{age_sec}s"
                    lines.append({'text': text, 'ts': ev.get('overlay_added') or now, 'kind': 'fake_hit'})
        except Exception:
            pass
        # Actor stalls (nearby)
        try:
            ne = global_variables.get_actor_stall_events() or []
            for ev in reversed(ne):
                added = ev.get('overlay_added') or 0
                if isinstance(added, (int, float)) and added >= cutoff:
                    p = ev.get('player')
                    age_sec = int(max(0, now - added))
                    text = f"NEAR {p} -{age_sec}s"
                    lines.append({'text': text, 'ts': added, 'kind': 'actor_stall'})
        except Exception:
            pass
        # Kills (latest) – only locally added recent ones have _overlay_added
        try:
            kills = global_variables.get_api_kills_all() or []
            for rec in reversed(kills):
                added = rec.get('_overlay_added') or 0
                if not isinstance(added, (int, float)) or added < cutoff:
                    continue
                victims = rec.get('victims') if isinstance(rec.get('victims'), list) else []
                v = victims[0] if victims else 'Victim'
                ship_used = rec.get('ship_used') or rec.get('killers_ship') or ''
                ship_short = ship_used.split('_')[0] if isinstance(ship_used, str) and ship_used else ''
                age_sec = int(max(0, now - added))
                text = f"KILL {v} {ship_short} -{age_sec}s"
                lines.append({'text': text, 'ts': added, 'kind': 'kill'})
        except Exception:
            pass
        # Keep only last 12 most recent by ts
        try:
            lines.sort(key=lambda d: d.get('ts', 0))
            self.lines = lines[-12:]
        except Exception:
            self.lines = lines[:12]

    def _mix_color(self, bg_hex: str, fg_hex: str, t: float) -> str:
        """Mix fg toward bg by factor t in [0,1]; t=0 -> fg, t=1 -> bg."""
        def _hex_to_rgb(h):
            h = h.lstrip('#')
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        def _rgb_to_hex(rgb):
            return '#%02x%02x%02x' % rgb
        try:
            br, bgc, bb = _hex_to_rgb(bg_hex)
            fr, fgcc, fb = _hex_to_rgb(fg_hex)
            t = max(0.0, min(1.0, float(t)))
            r = int(fr * (1.0 - t) + br * t)
            g = int(fgcc * (1.0 - t) + bgc * t)
            b = int(fb * (1.0 - t) + bb * t)
            return _rgb_to_hex((r, g, b))
        except Exception:
            return fg_hex

# Convenience API

def ensure_overlay():
    if not global_variables.is_overlay_enabled():
        return None
    mgr = global_variables.get_overlay_manager()
    app = global_variables.get_app()
    if mgr is None and app is not None:
        mgr = OverlayManager(app)
        global_variables.set_overlay_manager(mgr)
        mgr.show()
    elif mgr is not None:
        mgr.show()
    return mgr


def refresh_overlay():
    try:
        if not global_variables.is_overlay_enabled():
            return
        mgr = ensure_overlay()
        if mgr:
            mgr.refresh()
    except Exception:
        pass


def disable_overlay():
    try:
        mgr = global_variables.get_overlay_manager()
        if mgr:
            mgr.hide()
        global_variables.set_overlay_enabled(False)
    except Exception:
        pass
