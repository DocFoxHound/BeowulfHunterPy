import tkinter as tk
import tkinter.font as tkfont
import global_variables
import time
from datetime import datetime, timezone
import re
import threading
import io
from typing import Optional, Dict, Any

import requests  # type: ignore
from PIL import Image, ImageTk  # type: ignore

class OverlayManager:
    def __init__(self, root_app):
        self.root_app = root_app
        self.win = None
        self.width = 340  # base minimum; will auto-grow to fit longest line
        self.bg = '#111111'
        self.fg = '#f5f5f5'
        self.border = '#333333'
        self.font = ('Consolas', 10)
        self.line_widgets = []
        # Store live event lines: [{'text': str, 'ts': float, 'kind': 'kill'|'fake_hit'|'actor_stall'}]
        self.lines = []
        # periodic refresh handle
        self._tick_id = None
        # caches and placeholders
        self._avatar_cache: Dict[str, Any] = {}
        self._profile_cache: Dict[str, Any] = {}
        self._ph_org_small = None
        self._ph_avatar_small = None

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
        self._ensure_image_caches()
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

    # --- Image/profile helpers ---
    def _ensure_image_caches(self):
        app = global_variables.get_app()
        try:
            if app is not None:
                if not hasattr(app, 'org_avatar_cache') or not isinstance(getattr(app, 'org_avatar_cache'), dict):
                    setattr(app, 'org_avatar_cache', {})
                if not hasattr(app, 'proximity_profile_cache') or not isinstance(getattr(app, 'proximity_profile_cache'), dict):
                    setattr(app, 'proximity_profile_cache', {})
                self._avatar_cache = getattr(app, 'org_avatar_cache')
                self._profile_cache = getattr(app, 'proximity_profile_cache')
                # Placeholders
                self._ph_avatar_small = getattr(app, 'placeholder_avatar_small', None)
                self._ph_org_small = getattr(app, 'placeholder_org_small', None)
        except Exception:
            pass
        # Ensure placeholders exist
        if self._ph_avatar_small is None or self._ph_org_small is None:
            try:
                ph_a = Image.new('RGBA', (16, 16), (60,60,60,255))
                ph_o = Image.new('RGBA', (16, 16), (80,80,80,255))
                if self._ph_avatar_small is None:
                    self._ph_avatar_small = ImageTk.PhotoImage(ph_a)
                if self._ph_org_small is None:
                    self._ph_org_small = ImageTk.PhotoImage(ph_o)
            except Exception:
                pass

    def _make_square_thumbnail(self, img: Image.Image, size: int = 16) -> Image.Image:
        try:
            w, h = img.size
            if w != h:
                side = min(w, h)
                left = (w - side) // 2
                top = (h - side) // 2
                img = img.crop((left, top, left + side, top + side))
            return img.resize((size, size), Image.Resampling.LANCZOS)
        except Exception:
            return img

    def _download_photoimage(self, url: Optional[str], size: int = 16):
        if not isinstance(url, str) or not url.strip():
            return None
        key = f"{url}#{size}"
        try:
            if key in self._avatar_cache:
                return self._avatar_cache.get(key)
            r = requests.get(url, timeout=6)
            if r.status_code != 200:
                return None
            im = Image.open(io.BytesIO(r.content)).convert('RGBA')
            im = self._make_square_thumbnail(im, size)
            photo = ImageTk.PhotoImage(im)
            self._avatar_cache[key] = photo
            return photo
        except Exception:
            return None

    def _fetch_rsi_profile(self, handle: Optional[str]):
        if not isinstance(handle, str) or not handle:
            return (None, None, None)
        try:
            key = str(handle).strip().lower()
        except Exception:
            key = None
        if key and key in self._profile_cache:
            try:
                cached = self._profile_cache.get(key)
                return (cached.get('org_img_url'), cached.get('avatar_url'), cached.get('org_name'))
            except Exception:
                pass
        url = f"https://robertsspaceindustries.com/en/citizens/{handle}"
        try:
            headers = {"User-Agent": "BeowulfHunter/1.0 (overlay)", "Accept": "text/html,application/xhtml+xml"}
            r = requests.get(url, headers=headers, timeout=6)
            if r.status_code != 200:
                return (None, None, None)
            html = r.text
            m_avatar = re.search(r'<span class="title">\s*Profile\s*</span>.*?<img\s+src="([^"]+)"', html, re.IGNORECASE | re.DOTALL)
            m_orgimg = re.search(r'<span class="title">\s*Main\s+organization\s*</span>.*?<img\s+src="([^"]+)"', html, re.IGNORECASE | re.DOTALL)
            m_orgname = re.search(r'<span class="title">\s*Main\s+organization\s*</span>.*?<a[^>]*>([^<]+)</a>', html, re.IGNORECASE | re.DOTALL)
            def _abs(u):
                if not u:
                    return None
                return ("https://robertsspaceindustries.com" + u) if str(u).startswith('/') else u
            avatar_url = _abs(m_avatar.group(1)) if m_avatar else None
            orgimg_url = _abs(m_orgimg.group(1)) if m_orgimg else None
            org_name = m_orgname.group(1).strip() if m_orgname else None
            if key is not None:
                try:
                    self._profile_cache[key] = {'avatar_url': avatar_url, 'org_img_url': orgimg_url, 'org_name': org_name}
                except Exception:
                    pass
            return (orgimg_url, avatar_url, org_name)
        except Exception:
            return (None, None, None)

    class _ToolTip:
        def __init__(self, outer, widget: tk.Widget, text: str = ""):
            self.outer = outer
            self.widget = widget
            self.text = text
            self.tip: Optional[tk.Toplevel] = None
            try:
                widget.bind("<Enter>", self._enter)
                widget.bind("<Leave>", self._leave)
                widget.bind("<Motion>", self._motion)
            except Exception:
                pass
        def _enter(self, _evt=None):
            self._show()
        def _leave(self, _evt=None):
            self._hide()
        def _motion(self, evt):
            try:
                if self.tip is not None:
                    x = evt.x_root + 12
                    y = evt.y_root + 12
                    self.tip.wm_geometry(f"+{x}+{y}")
            except Exception:
                pass
        def _show(self):
            if not self.text:
                return
            try:
                if self.tip is not None:
                    return
                tip = tk.Toplevel(self.outer.win if self.outer and self.outer.win else self.widget)
                tip.wm_overrideredirect(True)
                tip.attributes('-topmost', True)
                lbl = tk.Label(tip, text=str(self.text), bg="#2a2a2a", fg="#ffffff", relief="solid", borderwidth=1, font=("Times New Roman", 10))
                lbl.pack(ipadx=6, ipady=3)
                x = self.widget.winfo_rootx() + 10
                y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
                tip.wm_geometry(f"+{x}+{y}")
                self.tip = tip
            except Exception:
                self.tip = None
        def _hide(self):
            try:
                if self.tip is not None:
                    self.tip.destroy()
                    self.tip = None
            except Exception:
                self.tip = None

    def _add_images_for_handle(self, row: tk.Frame, handle: Optional[str], known_org_url: Optional[str] = None, known_avatar_url: Optional[str] = None, known_org_name: Optional[str] = None):
        og = tk.Label(row, bg=self.bg)
        av = tk.Label(row, bg=self.bg)
        # placeholders
        try:
            if self._ph_org_small:
                og.configure(image=self._ph_org_small); og.image = self._ph_org_small
            if self._ph_avatar_small:
                av.configure(image=self._ph_avatar_small); av.image = self._ph_avatar_small
        except Exception:
            pass
        og.pack(side=tk.LEFT, padx=(4,2), pady=2)
        av.pack(side=tk.LEFT, padx=(0,6), pady=2)
        # Known URLs first
        if isinstance(known_org_url, str) and known_org_url.strip():
            try:
                og_img = self._download_photoimage(known_org_url.strip(), 16)
                if og_img:
                    og.configure(image=og_img); og.image = og_img
                if isinstance(known_org_name, str) and known_org_name.strip():
                    self._ToolTip(self, og, known_org_name.strip())
            except Exception:
                pass
        if isinstance(known_avatar_url, str) and known_avatar_url.strip():
            try:
                av_img = self._download_photoimage(known_avatar_url.strip(), 16)
                if av_img:
                    av.configure(image=av_img); av.image = av_img
            except Exception:
                pass
        # Async fetch if needed
        if (not known_org_url or not known_avatar_url) and isinstance(handle, str) and handle.strip():
            def _worker():
                orgimg_url, avatar_url, org_name = self._fetch_rsi_profile(handle)
                org_photo = self._download_photoimage(orgimg_url, 16)
                av_photo = self._download_photoimage(avatar_url, 16)
                def _apply():
                    try:
                        if isinstance(org_photo, ImageTk.PhotoImage):
                            og.configure(image=org_photo); og.image = org_photo
                            if org_name:
                                self._ToolTip(self, og, str(org_name))
                        if isinstance(av_photo, ImageTk.PhotoImage):
                            av.configure(image=av_photo); av.image = av_photo
                    except Exception:
                        pass
                try:
                    if self.win:
                        self.win.after(0, _apply)
                except Exception:
                    pass
            try:
                threading.Thread(target=_worker, daemon=True).start()
            except Exception:
                pass
        return og, av

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
            try:
                w.destroy()
            except Exception:
                pass
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
        blink_phase = int((time.time() * 2) % 2)  # toggle every 0.5s
        temp_rows = []
        for line in filtered[-12:]:
            kind = line.get('kind')
            added = line.get('ts') or now
            age = max(0.0, now - float(added))
            t = 0.0
            if age >= 7.0:
                t = min(1.0, (age - 7.0) / 3.0)
            fg_base = self._mix_color(self.bg, self.fg, t)
            row = tk.Frame(self.container, bg=self.bg)
            row.pack(fill=tk.X, padx=2)
            # Type prefix at the beginning
            try:
                pfx = {'kill': '[KILL]', 'actor_stall': '[PROX]', 'fake_hit': '[SNAR]'}.get(kind, '[INFO]')
                tk.Label(row, text=pfx, fg=fg_base, bg=self.bg, font=('Consolas', 10)).pack(side=tk.LEFT, padx=(4,4))
            except Exception:
                pass
            # Colored gumball per kind
            try:
                gb_color = {'kill': '#ef4444', 'actor_stall': '#22c55e', 'fake_hit': '#facc15'}.get(kind, '#9ca3af')
                tk.Label(row, text='●', fg=gb_color, bg=self.bg, font=('Consolas', 10)).pack(side=tk.LEFT, padx=(0,6))
            except Exception:
                pass
            # Build per-kind layout with images adjacent to names
            if kind == 'fake_hit':
                fp = line.get('from_player') or ''
                tp = line.get('player') or ''
                ship = line.get('ship') or ''
                self._add_images_for_handle(row, fp)
                tk.Label(row, text=fp, fg=( '#facc15' if blink_phase == 1 else fg_base), bg=self.bg, font=self.font).pack(side=tk.LEFT, padx=(0,4))
                tk.Label(row, text='->', fg=fg_base, bg=self.bg, font=self.font).pack(side=tk.LEFT, padx=(0,4))
                self._add_images_for_handle(row, tp)
                tk.Label(row, text=tp, fg=( '#facc15' if blink_phase == 1 else fg_base), bg=self.bg, font=self.font).pack(side=tk.LEFT, padx=(0,4))
                tail = f" {ship} -{int(age)}s" if ship else f" -{int(age)}s"
                tk.Label(row, text=tail, fg=fg_base, bg=self.bg, font=self.font).pack(side=tk.LEFT, padx=(0,4))
            elif kind == 'kill':
                self._add_images_for_handle(row, line.get('player'), known_org_url=line.get('org_picture_url'), known_avatar_url=line.get('avatar_url'), known_org_name=line.get('org_name'))
                ship = line.get('ship') or ''
                age_sec = int(max(0, now - (line.get('ts') or now)))
                txt_lbl = f"{line.get('player')} {ship} -{age_sec}s" if ship else f"{line.get('player')} -{age_sec}s"
                tk.Label(row, text=txt_lbl, fg=fg_base, bg=self.bg, font=self.font, anchor='w').pack(side=tk.LEFT, fill=tk.X, expand=True)
            else:  # actor_stall
                self._add_images_for_handle(row, line.get('player'))
                age_sec = int(max(0, now - (line.get('ts') or now)))
                txt_lbl = f"{line.get('player')} -{age_sec}s"
                tk.Label(row, text=txt_lbl, fg=fg_base, bg=self.bg, font=self.font, anchor='w').pack(side=tk.LEFT, fill=tk.X, expand=True)
            temp_rows.append(row)
        # Compute required width using requested widths of built rows (only grow, never shrink rapidly)
        try:
            self.win.update_idletasks()
            needed = max([r.winfo_reqwidth() for r in temp_rows] + [340]) + 8  # padding
            screen_w = self.win.winfo_screenwidth()
            needed = min(needed, screen_w - 10)
            # Only adjust width if difference is significant (>4px) to avoid jitter; allow shrink but not below min
            if abs(needed - self.width) > 4:
                self.width = max(340, needed)
        except Exception:
            pass
        self.line_widgets = temp_rows
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
                    # Preserve full ship name but strip trailing numeric instance id if present
                    ship_clean = ''
                    if isinstance(ship, str) and ship:
                        ship_clean = re.sub(r"_[0-9]+$", "", ship.strip())
                    age_sec = int(max(0, now - (ev.get('overlay_added') or now)))
                    text = f"INT {fp}->{tp} {ship_clean} -{age_sec}s"
                    lines.append({'text': text, 'ts': ev.get('overlay_added') or now, 'kind': 'fake_hit', 'player': tp, 'from_player': fp, 'ship': ship_clean})
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
                    lines.append({'text': text, 'ts': added, 'kind': 'actor_stall', 'player': p})
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
                ship_display = ''
                if isinstance(ship_used, str) and ship_used:
                    ship_display = re.sub(r"_[0-9]+$", "", ship_used.strip())
                age_sec = int(max(0, now - added))
                text = f"KILL {v} {ship_display} -{age_sec}s"
                lines.append({'text': text, 'ts': added, 'kind': 'kill', 'player': v,
                              'org_picture_url': rec.get('org_picture'), 'avatar_url': rec.get('victim_image'), 'org_name': rec.get('org_sid'),
                              'ship': ship_display})
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
