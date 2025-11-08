import tkinter as tk
from tkinter import filedialog
from typing import Dict, Any, Optional, Tuple
import time as _t
import threading
import re
import io

from PIL import Image, ImageTk  # type: ignore
import requests  # type: ignore

import global_variables as gv

try:
    from .. import keys  # type: ignore
except Exception:
    import keys  # type: ignore

COLORS = {
    'bg': '#1a1a1a',
    'fg': '#ffffff',
    'muted': '#bcbcd8',
    'border': '#2a2a2a',
    'card_bg': '#0f0f0f',
    'accent': '#ff5555',
}


def build(parent: tk.Misc) -> Dict[str, Any]:
    refs: Dict[str, Any] = {}

    # Header
    tk.Label(parent, text="Proximity", fg=COLORS['muted'], bg=COLORS['bg'], font=("Times New Roman", 12)).pack(anchor='nw', padx=6, pady=(6, 4))

    # Container for reports + controls
    container = tk.Frame(parent, bg=COLORS['bg'], highlightthickness=1, highlightbackground=COLORS['border'])
    container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=(0,6))
    try:
        container.grid_columnconfigure(0, weight=70)
        container.grid_columnconfigure(1, weight=30, minsize=260)
        container.grid_rowconfigure(0, weight=1)
    except Exception:
        pass

    # Reports area: scrollable list of single-line event cards
    prox_bg = "#0a0a0a"
    reports_outer = tk.Frame(container, bg=prox_bg)
    reports_outer.grid(row=0, column=0, sticky='nsew', padx=(6,3), pady=6)

    header_row = tk.Frame(reports_outer, bg=prox_bg)
    header_row.pack(side=tk.TOP, fill=tk.X)
    tk.Label(header_row, text="Proximity Reports", font=("Times New Roman", 14, "bold"), fg="#ffffff", bg=prox_bg).pack(side=tk.LEFT, padx=4)

    cards_container = tk.Frame(reports_outer, bg=prox_bg)
    cards_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(cards_container, bg="#121212", highlightthickness=1, highlightbackground="#2a2a2a")
    vscroll = tk.Scrollbar(cards_container, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=vscroll.set)
    vscroll.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    cards_frame = tk.Frame(canvas, bg="#121212")
    inner_id = canvas.create_window((0, 0), window=cards_frame, anchor='nw')

    def _on_configure(event=None):
        try:
            canvas.configure(scrollregion=canvas.bbox('all'))
            # Make inner frame width track canvas width
            canvas.itemconfig(inner_id, width=canvas.winfo_width())
        except Exception:
            pass
    cards_frame.bind('<Configure>', _on_configure)
    canvas.bind('<Configure>', _on_configure)

    # Simple caches on app (shared with other tabs)
    app = gv.get_app()
    if app is not None and (not hasattr(app, 'org_avatar_cache') or not isinstance(getattr(app, 'org_avatar_cache'), dict)):
        setattr(app, 'org_avatar_cache', {})
    _avatar_cache: Dict[str, Any] = getattr(app, 'org_avatar_cache', {}) if app is not None else {}
    # Cache for proximity profile lookups: handle_lower -> {'avatar_img': PhotoImage|None, 'org_img': PhotoImage|None, 'org_name': str|None}
    if app is not None and (not hasattr(app, 'proximity_profile_cache') or not isinstance(getattr(app, 'proximity_profile_cache'), dict)):
        setattr(app, 'proximity_profile_cache', {})
    _profile_cache: Dict[str, Any] = getattr(app, 'proximity_profile_cache', {}) if app is not None else {}

    # Placeholders (16x16)
    placeholder_avatar_small = getattr(app, 'placeholder_avatar_small', None) if app is not None else None
    placeholder_org_small = None
    try:
        placeholder_org_small = getattr(app, 'placeholder_org_small', None)
    except Exception:
        placeholder_org_small = None
    if placeholder_avatar_small is None or placeholder_org_small is None:
        try:
            # Create minimal gray squares if main tab didn't
            ph_a = Image.new('RGBA', (16, 16), (60,60,60,255))
            ph_o = Image.new('RGBA', (16, 16), (80,80,80,255))
            if placeholder_avatar_small is None:
                placeholder_avatar_small = ImageTk.PhotoImage(ph_a)
            if placeholder_org_small is None:
                placeholder_org_small = ImageTk.PhotoImage(ph_o)
        except Exception:
            pass

    def _download_photoimage(url: Optional[str], size: int = 16):
        if not isinstance(url, str) or not url.strip():
            return None
        key = f"{url}#{size}"
        if key in _avatar_cache:
            return _avatar_cache.get(key)
        try:
            r = requests.get(url, timeout=6)
            if r.status_code != 200:
                return None
            im = Image.open(io.BytesIO(r.content)).convert('RGBA')
            im = _make_square_thumbnail(im, size)
            photo = ImageTk.PhotoImage(im)
            _avatar_cache[key] = photo
            return photo
        except Exception:
            return None

    def _make_square_thumbnail(img: Image.Image, size: int = 16) -> Image.Image:  # type: ignore[name-defined]
        try:
            w, h = img.size
            if w == h:
                return img.resize((size, size), Image.Resampling.LANCZOS)
            if w > h:
                left = int((w - h) / 2)
                right = left + h
                img = img.crop((left, 0, right, h))
            else:
                top = int((h - w) / 2)
                bottom = top + w
                img = img.crop((0, top, w, bottom))
            return img.resize((size, size), Image.Resampling.LANCZOS)
        except Exception:
            return img

    def _abs(url: str) -> str:
        try:
            if not url:
                return url
            if url.startswith('http://') or url.startswith('https://'):
                return url
            base = 'https://robertsspaceindustries.com'
            if not url.startswith('/'):
                url = '/' + url
            return base + url
        except Exception:
            return url

    def _fetch_rsi_profile(handle: Optional[str]):
        if not isinstance(handle, str) or not handle:
            return (None, None, None)
        url = f"https://robertsspaceindustries.com/en/citizens/{handle}"
        try:
            headers = {"User-Agent": "BeowulfHunter/1.0 (proximity-tab)", "Accept": "text/html,application/xhtml+xml"}
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code != 200:
                return (None, None, None)
            html = r.text
            m_avatar = re.search(r'<span class="title">\s*Profile\s*</span>.*?<img\s+src="([^"]+)"', html, re.IGNORECASE | re.DOTALL)
            m_orgimg = re.search(r'<span class="title">\s*Main\s+organization\s*</span>.*?<img\s+src="([^"]+)"', html, re.IGNORECASE | re.DOTALL)
            m_orgname = re.search(r'<span class="title">\s*Main\s+organization\s*</span>.*?<a[^>]*>([^<]+)</a>', html, re.IGNORECASE | re.DOTALL)
            avatar_url = _abs(m_avatar.group(1)) if m_avatar else None
            orgimg_url = _abs(m_orgimg.group(1)) if m_orgimg else None
            org_name = m_orgname.group(1).strip() if m_orgname else None
            return (orgimg_url, avatar_url, org_name)
        except Exception:
            return (None, None, None)

    # Card management
    _cards: list[tk.Frame] = []

    # Simple tooltip helper
    class _ToolTip:
        def __init__(self, widget: tk.Widget, text: str = ""):
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
                tip = tk.Toplevel(self.widget)
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

    def _make_card_base(bg_color: str = "#0f0f0f") -> tk.Frame:
        # Create a card frame but don't pack yet; caller will insert at top
        card = tk.Frame(cards_frame, bg=bg_color, highlightthickness=1, highlightbackground="#2a2a2a")
        return card

    def _add_images_for_handle(container: tk.Frame, handle: Optional[str], known_org_url: Optional[str] = None, known_avatar_url: Optional[str] = None, known_org_name: Optional[str] = None):
        # org then avatar (16x16 each)
        og = tk.Label(container, bg=container["bg"])  # type: ignore[index]
        av = tk.Label(container, bg=container["bg"])  # type: ignore[index]
        # placeholders
        try:
            if placeholder_org_small:
                og.configure(image=placeholder_org_small); og.image = placeholder_org_small
            if placeholder_avatar_small:
                av.configure(image=placeholder_avatar_small); av.image = placeholder_avatar_small
        except Exception:
            pass
        og.pack(side=tk.LEFT, padx=(4,2), pady=2)
        av.pack(side=tk.LEFT, padx=(0,6), pady=2)
        # Prefer known URLs when provided
        if isinstance(known_org_url, str) and known_org_url.strip():
            try:
                og_img = _download_photoimage(known_org_url.strip(), 16)
                if og_img:
                    og.configure(image=og_img); og.image = og_img
                if isinstance(known_org_name, str) and known_org_name.strip():
                    _ToolTip(og, known_org_name.strip())
            except Exception:
                pass
        if isinstance(known_avatar_url, str) and known_avatar_url.strip():
            try:
                av_img = _download_photoimage(known_avatar_url.strip(), 16)
                if av_img:
                    av.configure(image=av_img); av.image = av_img
            except Exception:
                pass
        # Async fetch real images if no known URLs
        if (not known_org_url or not known_avatar_url) and isinstance(handle, str) and handle.strip():
            def _worker():
                orgimg_url, avatar_url, _org_name = _fetch_rsi_profile(handle)
                org_photo = _download_photoimage(orgimg_url, 16)
                av_photo = _download_photoimage(avatar_url, 16)
                def _apply():
                    try:
                        if isinstance(org_photo, ImageTk.PhotoImage):
                            og.configure(image=org_photo); og.image = org_photo
                            if _org_name:
                                _ToolTip(og, str(_org_name))
                        if isinstance(av_photo, ImageTk.PhotoImage):
                            av.configure(image=av_photo); av.image = av_photo
                    except Exception:
                        pass
                try:
                    if app is not None:
                        app.after(0, _apply)
                except Exception:
                    pass
            threading.Thread(target=_worker, daemon=True).start()
        return (og, av)

    def _add_card(kind: str, player: Optional[str] = None, ship: Optional[str] = None, from_player: Optional[str] = None,
                  org_picture_url: Optional[str] = None, avatar_url: Optional[str] = None, org_name: Optional[str] = None,
                  from_org_picture_url: Optional[str] = None, from_avatar_url: Optional[str] = None, from_org_name: Optional[str] = None):
        # Base colors
        colors = {
            'kill': {'fg': '#ffffff', 'bg': '#0f0f0f'},
            'near': {'fg': '#a7f3d0', 'bg': '#0f0f0f'},
            'snare': {'fg': '#facc15', 'bg': '#0f0f0f'},
        }
        gumball = {'kill': '#ef4444', 'near': '#22c55e', 'snare': '#facc15'}.get(kind, '#9ca3af')
        card = _make_card_base(colors.get(kind, {}).get('bg', '#0f0f0f'))
        # Insert newest at the top: pack before the first existing child
        try:
            children = cards_frame.winfo_children()
            if children:
                card.pack(fill=tk.X, pady=2, padx=2, before=children[0])
            else:
                card.pack(fill=tk.X, pady=2, padx=2)
        except Exception:
            card.pack(fill=tk.X, pady=2, padx=2)
        # Prefix then gumball at start for consistency with overlay
        try:
            prefix = {'kill': '[KILL]', 'near': '[PROX]', 'snare': '[SNAR]'}.get(kind, '[INFO]')
            tk.Label(card, text=prefix, fg=colors.get(kind, {}).get('fg', '#ffffff'), bg=card['bg'], font=("Consolas", 10)).pack(side=tk.LEFT, padx=(6,4))
        except Exception:
            pass
        try:
            tk.Label(card, text='●', fg=gumball, bg=card['bg'], font=("Consolas", 10)).pack(side=tk.LEFT, padx=(0,6))
        except Exception:
            pass
        # For snare, build inline segments: [from images][from name] -> [to images][to name] (ship)
        if kind == 'snare':
            # Interdictor segment
            _add_images_for_handle(card, from_player, known_org_url=from_org_picture_url, known_avatar_url=from_avatar_url, known_org_name=from_org_name)
            from_lbl = tk.Label(card, text=(from_player or 'Unknown'), fg=colors['snare']['fg'], bg=card['bg'], font=("Consolas", 11))
            from_lbl.pack(side=tk.LEFT, padx=(0,4))
            tk.Label(card, text='->', fg=colors['snare']['fg'], bg=card['bg'], font=("Consolas", 11)).pack(side=tk.LEFT, padx=(0,4))
            # Target segment
            _add_images_for_handle(card, player, known_org_url=org_picture_url, known_avatar_url=avatar_url, known_org_name=org_name)
            to_lbl = tk.Label(card, text=(player or 'Unknown'), fg=colors['snare']['fg'], bg=card['bg'], font=("Consolas", 11))
            to_lbl.pack(side=tk.LEFT, padx=(0,4))
            if ship:
                tk.Label(card, text=f" ({ship})", fg=colors['snare']['fg'], bg=card['bg'], font=("Consolas", 11)).pack(side=tk.LEFT)
            lbl = to_lbl  # for blinking below
        else:
            _add_images_for_handle(card, player, known_org_url=org_picture_url, known_avatar_url=avatar_url, known_org_name=org_name)
            # Text
            if kind == 'kill':
                ship_txt = f" ({ship})" if ship else ''
                txt = f"{player or 'Unknown'}{ship_txt}"
            elif kind == 'near':
                txt = f"{player or 'Unknown'}"
            else:
                txt = f"{player or 'Unknown'}"
            fg = colors.get(kind, {}).get('fg', '#ffffff')
            lbl = tk.Label(card, text=txt, fg=fg, bg=card['bg'], font=("Consolas", 11), anchor='w')
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Flashing behavior for snares: alternate yellow and grey for 10s, then settle yellow
        if kind == 'snare':
            start = _t.time()
            def _blink():
                age = _t.time() - start
                if age >= 10.0:
                    try:
                        lbl.configure(fg='#d4c313')  # settle yellow
                    except Exception:
                        pass
                    return
                # alternate
                phase = int((age * 2) % 2)  # 0/1 every 0.5s
                try:
                    lbl.configure(fg=('#9ca3af' if phase == 0 else '#facc15'))
                except Exception:
                    pass
                try:
                    card.after(500, _blink)
                except Exception:
                    pass
            try:
                card.after(0, _blink)
            except Exception:
                pass

        _cards.append(card)
        _on_configure()
        # Keep view pinned to top (show newest)
        try:
            canvas.yview_moveto(0)
        except Exception:
            pass

    def append_report_line(line: str):
        # Parser calls this with strings like:
        # [KILL] Victim (Ship)
        # [SNARE] From->To (Ship) or [SNARE] Player (Ship)
        # [NEAR] Player
        try:
            s = str(line).strip()
        except Exception:
            s = ''
        if not s:
            return
        try:
            if s.startswith('[KILL]'):
                m = re.match(r'^\[KILL\]\s+(.+?)\s+\(([^)]+)\)', s)
                if m:
                    victim = m.group(1).strip()
                    ship = m.group(2).strip()
                    # Try to find existing kill record to reuse scraped images
                    org_pic = None
                    avatar = None
                    org_name = None
                    try:
                        items = gv.get_api_kills_all() or []
                        # match latest record with victim and ship_used matches (strip trailing numeric)
                        ship_norm = re.sub(r'_[0-9]+$', '', ship)
                        for rec in reversed(items):
                            victims = rec.get('victims') if isinstance(rec.get('victims'), list) else []
                            su = rec.get('ship_used') or rec.get('killers_ship') or None
                            su_norm = re.sub(r'_[0-9]+$', '', su) if isinstance(su, str) else None
                            if (victim in victims) and (not ship_norm or su_norm == ship_norm):
                                org_pic = rec.get('org_picture') or None
                                avatar = rec.get('victim_image') or None
                                # org name not stored; fall back to org_sid if present
                                org_name = rec.get('org_sid') or None
                                break
                    except Exception:
                        pass
                    _add_card('kill', player=victim, ship=ship, org_picture_url=org_pic, avatar_url=avatar, org_name=org_name)
                else:
                    # Fallback: just show remaining text
                    _add_card('kill', player=s[7:].strip())
            elif s.startswith('[SNARE]'):
                body = s[8:].strip()
                # Try From->To first
                m = re.match(r'^(.+?)\s*->\s*(.+?)\s*\(([^)]+)\)', body)
                if m:
                    frm = m.group(1).strip()
                    to = m.group(2).strip()
                    ship = m.group(3).strip()
                    _add_card('snare', player=to, from_player=frm, ship=ship)
                else:
                    m2 = re.match(r'^(.+?)\s*\(([^)]+)\)', body)
                    if m2:
                        ply = m2.group(1).strip()
                        ship = m2.group(2).strip()
                        _add_card('snare', player=ply, ship=ship)
                    else:
                        _add_card('snare', player=body)
            elif s.startswith('[NEAR]'):
                name = s[7:].strip()
                _add_card('near', player=name)
            else:
                # Unrecognized, show as near
                _add_card('near', player=s)
        except Exception:
            # As a last resort, dump to console
            try:
                print(line)
            except Exception:
                pass

    def clear_reports():
        try:
            for c in list(_cards):
                try:
                    c.destroy()
                except Exception:
                    pass
            _cards.clear()
            _on_configure()
        except Exception:
            pass

    def refresh_player_events():
        # Currently, cards are appended via append_report_line from parser events
        return

    refs['refresh_player_events'] = refresh_player_events
    refs['append_report_line'] = append_report_line
    refs['clear_reports'] = clear_reports
    # Register these refs globally so parser-driven updates can refresh this tab
    try:
        gv.set_proximity_tab_refs(refs)
    except Exception:
        pass

    # Settings area
    settings = tk.Frame(container, bg=COLORS['bg'])
    settings.grid(row=0, column=1, sticky='nsew', padx=(3,6), pady=6)

    tk.Label(settings, text="Sounds", fg=COLORS['fg'], bg=COLORS['bg'], font=("Times New Roman", 12, "bold")).pack(anchor='w', pady=(0,4))

    def _pick_snare():
        path = filedialog.askopenfilename(parent=parent, title="Choose Snare Sound", filetypes=[("WAV files", "*.wav;*.wave"), ("All files", "*.*")])
        if not path:
            return
        try:
            keys.update_sound_paths(interdiction_path=path, nearby_path=keys.get_custom_sound_nearby(), kill_path=keys.get_custom_sound_kill())
            gv.set_custom_sound_interdiction(path)
            gv.log(f"Custom Snare sound set: {path}")
        except Exception:
            pass

    def _pick_proximity():
        path = filedialog.askopenfilename(parent=parent, title="Choose Proximity Sound", filetypes=[("WAV files", "*.wav;*.wave"), ("All files", "*.*")])
        if not path:
            return
        try:
            keys.update_sound_paths(interdiction_path=keys.get_custom_sound_interdiction(), nearby_path=path, kill_path=keys.get_custom_sound_kill())
            gv.set_custom_sound_nearby(path)
            gv.log(f"Custom Proximity sound set: {path}")
        except Exception:
            pass

    def _pick_kill():
        path = filedialog.askopenfilename(parent=parent, title="Choose Kill Sound", filetypes=[("WAV files", "*.wav;*.wave"), ("All files", "*.*")])
        if not path:
            return
        try:
            keys.update_sound_paths(interdiction_path=keys.get_custom_sound_interdiction(), nearby_path=keys.get_custom_sound_nearby(), kill_path=path)
            gv.set_custom_sound_kill(path)
            gv.log(f"Custom Kill sound set: {path}")
        except Exception:
            pass

    btn_style = getattr(gv.get_app(), 'BUTTON_STYLE', {}) if gv.get_app() else {"bg":"#0f0f0f","fg":"#ff5555","activebackground":"#330000","activeforeground":"#ffffff","relief":"ridge","bd":2,"font": ("Times New Roman", 12)}
    tk.Button(settings, text="Choose Kill Sound", command=_pick_kill, **btn_style).pack(fill=tk.X, pady=(0,6))
    tk.Button(settings, text="Choose Snare Sound", command=_pick_snare, **btn_style).pack(fill=tk.X, pady=(0,6))
    tk.Button(settings, text="Choose Proximity Sound", command=_pick_proximity, **btn_style).pack(fill=tk.X, pady=(0,10))

    # Toggles
    tk.Label(settings, text="Notices & Sounds", fg=COLORS['fg'], bg=COLORS['bg'], font=("Times New Roman", 12, "bold")).pack(anchor='w', pady=(0,4))
    var_play_kill = tk.BooleanVar(value=gv.get_play_kill_sound())
    var_show_kill = tk.BooleanVar(value=gv.get_show_kill_notice())
    var_play_snare = tk.BooleanVar(value=gv.get_play_snare_sound())
    var_show_snare = tk.BooleanVar(value=gv.get_show_snare_notice())
    var_play_prox = tk.BooleanVar(value=gv.get_play_proximity_sound())
    var_show_prox = tk.BooleanVar(value=gv.get_show_proximity_notice())

    def _apply_toggles():
        try:
            gv.set_play_kill_sound(var_play_kill.get())
            gv.set_play_snare_sound(var_play_snare.get())
            gv.set_play_proximity_sound(var_play_prox.get())
            # Show toggles map to overlay filters
            gv.set_show_kill_notice(var_show_kill.get())
            gv.set_show_snare_notice(var_show_snare.get())
            gv.set_show_proximity_notice(var_show_prox.get())
            # Persist to cfg
            try:
                keys.save_extended_settings({
                    'play_kill_sound': str(var_play_kill.get()),
                    'play_snare_sound': str(var_play_snare.get()),
                    'play_proximity_sound': str(var_play_prox.get()),
                    'show_kill_notice': str(var_show_kill.get()),
                    'show_snare_notice': str(var_show_snare.get()),
                    'show_proximity_notice': str(var_show_prox.get()),
                })
            except Exception:
                pass
            try:
                from overlay_window import refresh_overlay  # type: ignore
                refresh_overlay()
            except Exception:
                pass
        except Exception:
            pass

    # Place six checkboxes in a compact 3-column layout
    toggles_grid = tk.Frame(settings, bg=COLORS['bg'])
    toggles_grid.pack(fill=tk.X, pady=(0,6))

    def _mk_check(parent, text, var):
        cb = tk.Checkbutton(parent, text=text, variable=var, command=_apply_toggles,
                            bg=COLORS['bg'], fg=COLORS['fg'], selectcolor='#222222',
                            activebackground=COLORS['bg'], activeforeground=COLORS['fg'], highlightthickness=0)
        return cb

    # Column 0: Kill
    cb_kill_sound = _mk_check(toggles_grid, "Kill Sound", var_play_kill)
    cb_kill_notice = _mk_check(toggles_grid, "Kill Notice", var_show_kill)
    cb_kill_sound.grid(row=0, column=0, padx=(0,10), pady=2, sticky='w')
    cb_kill_notice.grid(row=1, column=0, padx=(0,10), pady=2, sticky='w')

    # Column 1: Snare (Interdiction)
    cb_snare_sound = _mk_check(toggles_grid, "Snare Sound", var_play_snare)
    cb_snare_notice = _mk_check(toggles_grid, "Snare Notice", var_show_snare)
    cb_snare_sound.grid(row=0, column=1, padx=(0,10), pady=2, sticky='w')
    cb_snare_notice.grid(row=1, column=1, padx=(0,10), pady=2, sticky='w')

    # Column 2: Proximity (Actor Stall)
    cb_prox_sound = _mk_check(toggles_grid, "Proximity Sound", var_play_prox)
    cb_prox_notice = _mk_check(toggles_grid, "Proximity Notice", var_show_prox)
    cb_prox_sound.grid(row=0, column=2, padx=(0,0), pady=2, sticky='w')
    cb_prox_notice.grid(row=1, column=2, padx=(0,0), pady=2, sticky='w')

    # Overlay controls (copied from Dogfighting)
    ov = tk.Frame(settings, bg=COLORS['bg'])
    ov.pack(fill=tk.X, pady=(10,6))
    tk.Label(ov, text="Overlay", fg=COLORS['fg'], bg=COLORS['bg'], font=("Times New Roman", 12, "bold")).pack(anchor='w', pady=(0,4))
    overlay_status_var = tk.StringVar(value='Enabled' if gv.is_overlay_enabled() else 'Disabled')
    corner_var = tk.StringVar(value=gv.get_overlay_corner())

    def _apply_corner():
        try:
            gv.set_overlay_corner(corner_var.get())
            from overlay_window import refresh_overlay, ensure_overlay  # type: ignore
            ensure_overlay(); refresh_overlay()
            # Persist corner
            try:
                keys.save_extended_settings({'overlay_corner': corner_var.get()})
            except Exception:
                pass
        except Exception:
            pass

    def _toggle_overlay():
        try:
            enabled = not gv.is_overlay_enabled()
            gv.set_overlay_enabled(enabled)
            overlay_status_var.set('Enabled' if enabled else 'Disabled')
            # Persist flag
            try:
                keys.save_extended_settings({'overlay_enabled': str(enabled)})
            except Exception:
                pass
            if enabled:
                from overlay_window import ensure_overlay, refresh_overlay  # type: ignore
                ensure_overlay(); refresh_overlay()
            else:
                from overlay_window import disable_overlay  # type: ignore
                disable_overlay()
        except Exception:
            pass

    tk.Button(ov, text="Enable/Disable", command=_toggle_overlay, **btn_style).pack(fill=tk.X, pady=(0,4))
    tk.Label(ov, textvariable=overlay_status_var, fg=COLORS['muted'], bg=COLORS['bg'], font=("Times New Roman", 10)).pack(anchor='w', pady=(0,6))

    # Two-column layout for overlay corner selection
    box = tk.Frame(ov, bg=COLORS['bg'])
    box.pack(fill=tk.X)
    # Left column: Top-Left, Bottom-Left; Right column: Top-Right, Bottom-Right
    left_col = tk.Frame(box, bg=COLORS['bg'])
    right_col = tk.Frame(box, bg=COLORS['bg'])
    left_col.pack(side=tk.LEFT, anchor='nw', padx=(0,20))
    right_col.pack(side=tk.LEFT, anchor='nw')

    def _mk_corner(parent, label, val):
        return tk.Radiobutton(parent, text=label, value=val, variable=corner_var,
                              command=_apply_corner, bg=COLORS['bg'], fg=COLORS['fg'], selectcolor='#222222',
                              activebackground=COLORS['bg'], activeforeground=COLORS['fg'], highlightthickness=0, padx=2, pady=2)

    _mk_corner(left_col, 'Top-Left', 'top-left').pack(anchor='w')
    _mk_corner(left_col, 'Bottom-Left', 'bottom-left').pack(anchor='w')
    _mk_corner(right_col, 'Top-Right', 'top-right').pack(anchor='w')
    _mk_corner(right_col, 'Bottom-Right', 'bottom-right').pack(anchor='w')

    # Test buttons row (compact, side-by-side) at the bottom of the settings area
    tests_row = tk.Frame(settings, bg=COLORS['bg'])
    tests_row.pack(fill=tk.X, pady=(10,6))
    tk.Label(tests_row, text="Tests", fg=COLORS['fg'], bg=COLORS['bg'], font=("Times New Roman", 12, "bold")).pack(anchor='w', pady=(0,4))
    buttons_row = tk.Frame(tests_row, bg=COLORS['bg'])
    buttons_row.pack(fill=tk.X)

    # Slightly smaller button style for inline row
    small_btn_style = dict(btn_style)
    try:
        f = small_btn_style.get('font', ("Times New Roman", 12))
        small_btn_style['font'] = (f[0], max(9, int(f[1]) - 2))
    except Exception:
        small_btn_style['font'] = ("Times New Roman", 10)

    def _refresh_everything():
        try:
            # Refresh hook (no-op for cards right now)
            refresh_player_events()
        except Exception:
            pass
        try:
            from overlay_window import refresh_overlay  # type: ignore
            refresh_overlay()
        except Exception:
            pass

    def _now_iso():
        try:
            import datetime as _dt
            return _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        except Exception:
            return "2025-01-01T00:00:00.000Z"

    def _test_kill():
        # Build a synthetic kill with scraped images so cards and overlay can reuse them
        victim = 'Galactic_Skywolf'
        ship = 'MISC_Hull_C'
        now = _t.time()
        org_pic = None
        victim_img = None
        try:
            # Try to scrape via scraper used by parser
            try:
                from ..rsi_profile_scraper import scrape_profile_images  # type: ignore
            except Exception:
                from rsi_profile_scraper import scrape_profile_images  # type: ignore
            try:
                org_pic, victim_img = scrape_profile_images(victim)
            except Exception:
                org_pic, victim_img = (None, None)
            # Insert into api_kills_all so overlay/card lookup finds it
            items = list(gv.get_api_kills_all() or [])
            items.append({
                'victims': [victim],
                'ship_used': ship,
                'killers_ship': ship,
                'org_picture': org_pic,
                'victim_image': victim_img,
                '_overlay_added': now,
                'org_sid': None,
            })
            gv.set_api_kills_all(items)
        except Exception:
            pass
        try:
            append_report_line(f"[KILL] {victim} ({ship})")
        except Exception:
            pass
        # Play kill sound for the test scenario using the same routine as live
        try:
            import parser as _parser  # type: ignore
            if hasattr(_parser, '_play_kill_sound'):
                _parser._play_kill_sound()  # type: ignore[attr-defined]
        except Exception:
            pass

    def _test_snare():
        try:
            # Build a fake-hit log line and parse via parser to keep behavior consistent
            from .. import parser as _parser  # type: ignore
        except Exception:
            try:
                import parser as _parser  # type: ignore
            except Exception:
                _parser = None
        ts = _now_iso()
        line = f"<{ts}> [Notice] <Debug Hostility Events> [OnHandleHit] Fake hit FROM Scarecrow_iso TO MISC_Hull_C_6716229536084. Being sent to child Galactic_Skywolf [Team_MissionFeatures][HitInfo]"
        try:
            if _parser is not None:
                _parser.parse_fake_hit_event(line)
            else:
                # Fallback: write directly to globals
                now = _t.time()
                gv.add_fake_hit_event({'timestamp': ts, 'player': 'Galactic_Skywolf', 'from_player': 'Scarecrow_iso', 'target_player': 'Galactic_Skywolf', 'ship': 'MISC_Hull_C', 'expires_at': now + 10.0, 'overlay_added': now})
        except Exception:
            pass
        _refresh_everything()

    def _test_proximity():
        try:
            from .. import parser as _parser  # type: ignore
        except Exception:
            try:
                import parser as _parser  # type: ignore
            except Exception:
                _parser = None
        ts = _now_iso()
        line = f"<{ts}> [Notice] <Actor stall> Actor stall detected, Player: Galactic_Skywolf, Type: downstream, Length: 6.840836. [Team_ActorTech][Actor]"
        try:
            if _parser is not None:
                _parser.parse_actor_stall_event(line)
            else:
                now = _t.time()
                gv.add_actor_stall_event({'timestamp': ts, 'player': 'Galactic_Skywolf', 'overlay_added': now})
        except Exception:
            pass
        _refresh_everything()

    # Three small inline buttons side-by-side
    tk.Button(buttons_row, text="Test Kill", command=_test_kill, **small_btn_style).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,4))
    tk.Button(buttons_row, text="Test Snare", command=_test_snare, **small_btn_style).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,4))
    tk.Button(buttons_row, text="Test Proximity", command=_test_proximity, **small_btn_style).pack(side=tk.LEFT, expand=True, fill=tk.X)

    # No initial fill needed for line-entry box

    return refs
