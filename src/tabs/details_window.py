import tkinter as tk
import threading
import io
from datetime import datetime, timezone, timedelta
from collections import Counter
import global_variables
import requests
from PIL import Image, ImageTk


def open_details_window(app):
    """Open the Kill Details window showing analytics and full lists (PU/AC)."""
    win = tk.Toplevel(app)
    try:
        win.title("Kill Details")
        win.configure(bg="#1a1a1a")
        win.geometry("640x420")
    except Exception:
        pass

    # header = tk.Label(
    #     win,
    #     font=("Times New Roman", 14, "bold"),
    #     fg="#ffffff",
    #     bg="#1a1a1a",
    # )
    # header.pack(side=tk.TOP, anchor='w', padx=8, pady=(8, 4))

    # Fetch combined kills
    try:
        all_items = global_variables.get_api_kills_all() or []
    except Exception:
        all_items = []

    # Analytics: Top victims, top ships killed (excluding FPS), and favorite ships used
    victim_counter = Counter()
    ship_counter = Counter()
    ship_used_counter = Counter()
    for it in all_items:
        try:
            vs = it.get('victims') if isinstance(it.get('victims'), list) else []
            for v in vs:
                if v:
                    victim_counter[v] += 1
            sk = it.get('ship_killed')
            if isinstance(sk, str) and sk.strip() and sk.strip().upper() != 'FPS':
                ship_counter[sk.strip()] += 1
            su = it.get('ship_used')
            if isinstance(su, str):
                su_s = su.strip()
                if su_s and su_s.lower() != 'null':
                    ship_used_counter[su_s] += 1
        except Exception:
            continue

    top_victims = victim_counter.most_common(3)
    top_ships = ship_counter.most_common(3)
    top_fav_ships = ship_used_counter.most_common(3)

    # Top stats row
    stats_row = tk.Frame(win, bg="#1a1a1a")
    stats_row.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 4))

    def _make_stat_box(parent, title, items):
        box = tk.Frame(parent, bg="#0f0f0f", highlightthickness=1, highlightbackground="#2a2a2a")
        tk.Label(box, text=title, font=("Times New Roman", 12, "bold"), fg="#ffffff", bg="#0f0f0f").pack(anchor='w', padx=8, pady=(6, 2))
        if not items:
            tk.Label(box, text="No data", font=("Times New Roman", 11), fg="#bcbcd8", bg="#0f0f0f").pack(anchor='w', padx=8, pady=(0, 8))
        else:
            for name, count in items:
                tk.Label(box, text=f"{name} — {count}", font=("Times New Roman", 11), fg="#bcbcd8", bg="#0f0f0f").pack(anchor='w', padx=8)
            tk.Label(box, text="", bg="#0f0f0f").pack(pady=(0, 6))
        return box

    left_box = _make_stat_box(stats_row, "Top Victims", top_victims)
    # mid_box = _make_stat_box(stats_row, "Favorite Ships", top_fav_ships)
    right_box = _make_stat_box(stats_row, "Top Ships Killed", top_ships)
    left_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4), anchor='n')
    # mid_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4), anchor='n')
    right_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0), anchor='n')

    # Below: single scrollable column with all kills (newest first)
    lists_row = tk.Frame(win, bg="#1a1a1a")
    lists_row.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def _make_scrollable_column(master, title):
        colors = {
            'bg': '#1a1a1a', 'card_bg': '#0f0f0f', 'fg': '#ffffff',
            'muted': '#bcbcd8', 'accent': '#ff5555', 'border': '#2a2a2a'
        }
        outer = tk.Frame(master, bg=colors['bg'])
        header = tk.Label(outer, text=title, font=("Times New Roman", 13, "bold"), fg=colors['fg'], bg=colors['bg'])
        header.pack(side=tk.TOP, anchor='w', pady=(0, 4))
        content = tk.Frame(outer, bg=colors['bg'])
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(content, bg=colors['bg'], highlightthickness=0, bd=0)
        vbar = tk.Scrollbar(content, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        inner = tk.Frame(canvas, bg=colors['bg'])
        window_id = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _update_scrollregion(event=None):
            try:
                canvas.configure(scrollregion=canvas.bbox('all'))
            except Exception:
                pass

        def _resize_inner(event):
            try:
                canvas.itemconfig(window_id, width=event.width)
            except Exception:
                pass

        inner.bind('<Configure>', _update_scrollregion)
        canvas.bind('<Configure>', _resize_inner)

        # Mouse wheel support — bind on canvas so it works over children
        def _on_mousewheel(event):
            try:
                steps = int(-1 * (event.delta / 120)) if event.delta != 0 else 0
                if steps:
                    canvas.yview_scroll(steps, 'units')
            except Exception:
                pass

        canvas.bind('<Enter>', lambda e: canvas.bind_all('<MouseWheel>', _on_mousewheel))
        canvas.bind('<Leave>', lambda e: canvas.unbind_all('<MouseWheel>'))

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        return {'outer': outer, 'container': inner}

    all_col = _make_scrollable_column(lists_row, "All Kills — Newest First")
    all_col['outer'].pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _parse_ts(s: str):
        try:
            if not s:
                return None
            st = s.strip()
            if st.startswith('<') and st.endswith('>'):
                st = st[1:-1].strip()
            if st.endswith('Z'):
                try:
                    return datetime.strptime(st, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
                except Exception:
                    return datetime.strptime(st, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            dt = datetime.fromisoformat(st)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    now = datetime.now(timezone.utc)
    def _is_recent(ts: str) -> bool:
        dt = _parse_ts(ts)
        return (dt is not None) and ((now - dt) <= timedelta(hours=24))

    # Tooltip helper (for org SID on org badge)
    class _ToolTip:
        def __init__(self, widget: tk.Widget, text: str = ""):
            self.widget = widget
            self.text = text
            self.tip = None
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
                try:
                    x = self.widget.winfo_rootx() + 10
                    y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
                    tip.wm_geometry(f"+{x}+{y}")
                except Exception:
                    pass
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

    # Shared cache on app for downloaded avatars (url#size -> PhotoImage)
    try:
        if not hasattr(app, 'org_avatar_cache') or not isinstance(getattr(app, 'org_avatar_cache'), dict):
            setattr(app, 'org_avatar_cache', {})
    except Exception:
        pass
    _avatar_cache = getattr(app, 'org_avatar_cache', {})

    def _make_square_thumbnail(img: Image.Image, size: int = 50) -> Image.Image:
        try:
            w, h = img.size
            if w != h:
                side = min(w, h)
                left = (w - side) // 2
                top = (h - side) // 2
                img = img.crop((left, top, left + side, top + side))
            return img.resize((size, size), Image.Resampling.LANCZOS)
        except Exception:
            try:
                return img.resize((size, size), Image.Resampling.LANCZOS)
            except Exception:
                return img

    def _load_avatar_async_sized(label: tk.Label, url: str, size: int = 50):
        if not url:
            return
        try:
            cache_key = f"{url}#s{int(size)}"
            cached = _avatar_cache.get(cache_key)
            if isinstance(cached, ImageTk.PhotoImage):
                try:
                    label.configure(image=cached)
                    label.image = cached
                except Exception:
                    pass
                return
        except Exception:
            pass

        def worker():
            content = None
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    content = resp.content
            except Exception:
                content = None

            def on_main():
                try:
                    if content:
                        try:
                            pil = Image.open(io.BytesIO(content)).convert('RGBA')
                            pil = _make_square_thumbnail(pil, size)
                            photo = ImageTk.PhotoImage(pil)
                            try:
                                _avatar_cache[cache_key] = photo
                            except Exception:
                                pass
                            try:
                                label.configure(image=photo)
                                label.image = photo
                            except Exception:
                                pass
                            return
                        except Exception:
                            pass
                except Exception:
                    pass

            try:
                app.after(0, on_main)
            except Exception:
                try:
                    on_main()
                except Exception:
                    pass

        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception:
            pass

    def _format_coords_str(coords_val):
        try:
            if not coords_val:
                return None
            s = str(coords_val).strip()
            # Accept forms like "x,y,z" or with spaces
            parts = [p.strip() for p in s.replace(" ", "").split(',') if p.strip()]
            if len(parts) != 3:
                # try space-separated
                parts = [p for p in s.split() if p]
            if len(parts) == 3:
                x, y, z = parts[0], parts[1], parts[2]
                # validate numeric
                try:
                    float(x); float(y); float(z)
                except Exception:
                    # If not numeric, still display raw string
                    return f"Coordinates: {s}"
                return f"Coordinates: x:{x} y:{y} z:{z}"
            # Fallback to raw
            return f"Coordinates: {s}"
        except Exception:
            return None

    def _add_card(container, primary_text, secondary_text=None, meta_text=None, icon=None, accent_color=None, border_color=None, org_picture_url=None, org_sid_tooltip=None, victim_image_url=None, coords_value=None):
        colors = {'bg': '#1a1a1a', 'card_bg': '#0f0f0f', 'fg': '#ffffff', 'muted': '#bcbcd8', 'accent': '#ff5555', 'border': '#2a2a2a'}
        outline = border_color if (isinstance(border_color, str) and border_color.strip()) else colors['border']
        card = tk.Frame(container, bg=colors['card_bg'], highlightthickness=1, highlightbackground=outline)
        bar = tk.Frame(card, bg=(accent_color or colors['accent']), width=4)
        bar.pack(side=tk.LEFT, fill=tk.Y)
        # Victim avatar on the left
        avatar_label = tk.Label(card, bg=colors['card_bg'])
        try:
            ph_avatar = getattr(app, 'placeholder_avatar', None)
            if ph_avatar is not None:
                avatar_label.configure(image=ph_avatar)
                avatar_label.image = ph_avatar
        except Exception:
            pass
        avatar_label.pack(side=tk.LEFT, padx=6, pady=6)
        try:
            if isinstance(victim_image_url, str) and victim_image_url.strip():
                _load_avatar_async_sized(avatar_label, victim_image_url.strip(), 50)
        except Exception:
            pass
        if icon is not None:
            try:
                lbl = tk.Label(card, image=icon, bg=colors['card_bg'])
                lbl.image = icon
                lbl.pack(side=tk.RIGHT, padx=8, pady=6)
            except Exception:
                pass
        # Org badge on the right with tooltip
        try:
            org_lbl = tk.Label(card, bg=colors['card_bg'])
            ph_small = getattr(app, 'placeholder_org', None)
            if ph_small is not None:
                try:
                    org_lbl.configure(image=ph_small)
                    org_lbl.image = ph_small
                except Exception:
                    pass
            if org_sid_tooltip:
                try:
                    _ToolTip(org_lbl, str(org_sid_tooltip))
                except Exception:
                    pass
            if isinstance(org_picture_url, str) and org_picture_url.strip():
                _load_avatar_async_sized(org_lbl, org_picture_url.strip(), 25)
            org_lbl.pack(side=tk.RIGHT, padx=(0, 0), pady=6)
        except Exception:
            pass
        body = tk.Frame(card, bg=colors['card_bg'])
        body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=6)
        # Selectable/copyable text area
        txt = tk.Text(body, wrap='word', relief='flat', bg=colors['card_bg'], fg=colors['fg'], highlightthickness=0, insertbackground=colors['fg'])
        try:
            txt.tag_configure('primary', font=("Times New Roman", 12, "bold"), foreground=colors['fg'])
            txt.tag_configure('secondary', font=("Times New Roman", 11), foreground=colors['muted'])
            txt.tag_configure('meta', font=("Times New Roman", 10), foreground=colors['muted'])
        except Exception:
            pass
        # Compose lines
        first = True
        def _append_line(s, tag):
            nonlocal first
            if s is None:
                return
            try:
                if not first:
                    txt.insert('end', '\n')
                txt.insert('end', str(s), tag)
                first = False
            except Exception:
                pass
        _append_line(primary_text, 'primary')
        _append_line(secondary_text, 'secondary')
        _append_line(meta_text, 'meta')
        coord_line = _format_coords_str(coords_value)
        _append_line(coord_line, 'meta')
        try:
            txt.configure(state=tk.DISABLED)
        except Exception:
            pass
        # Reasonable height: at least number of inserted logical lines, plus some cushion
        try:
            lines = int(str(txt.index('end-1c')).split('.')[0])
            txt.configure(height=max(3, min(8, lines + 1)))
        except Exception:
            txt.configure(height=5)
        txt.pack(fill=tk.X)
        card.pack(fill=tk.X, padx=6, pady=(0, 6))

    # Deduplicate, sort newest-first, and render with lazy chunking
    seen = set()
    unique_items = []
    for it in all_items:
        try:
            ts = str(it.get('timestamp') or '').strip()
            victims_list = it.get('victims') if isinstance(it.get('victims'), list) else []
            key = (ts, tuple(victims_list), (it.get('game_mode') or '').upper())
            if key in seen:
                continue
            seen.add(key)
            unique_items.append(it)
        except Exception:
            continue

    sorted_items = sorted(unique_items, key=lambda it: (_parse_ts(str(it.get('timestamp') or '')) or datetime.fromtimestamp(0, tz=timezone.utc)), reverse=True)

    # Log a few samples if location/coordinates appear missing to help debugging
    missing_loc_samples = 0
    # Lazy render settings
    CHUNK_SIZE = 100
    MAX_INITIAL = 300  # keep initial render fast; user can load more on demand

    # Status + control row (reuse bottom button frame; add status + load more)
    btn_frame = tk.Frame(win, bg="#1a1a1a")
    btn_frame.pack(fill=tk.X, padx=8, pady=(4, 8))
    try:
        style = getattr(app, 'BUTTON_STYLE', {})
    except Exception:
        style = {}

    status_lbl = tk.Label(btn_frame, text="", font=("Times New Roman", 10), fg="#bcbcd8", bg="#1a1a1a")
    status_lbl.pack(side=tk.LEFT)

    # Precompute safe-normalized records to avoid repeated dict lookups during chunked render
    def _normalize_record(rec):
        try:
            victims = rec.get('victims') if isinstance(rec.get('victims'), list) else []
            victims = [v for v in victims if isinstance(v, str) and v.strip()]
            title = victims[0] if victims else 'Unknown Victim'
            ship_killed = rec.get('ship_killed')
            is_fps = isinstance(ship_killed, str) and ship_killed.strip().upper() == 'FPS'
            icon = getattr(app, 'icon_rifle', None) if is_fps else getattr(app, 'icon_ship', None)
            accent = '#ff5555' if is_fps else '#3b82f6'
            game_mode = rec.get('game_mode') or 'Unknown Mode'
            ts = rec.get('timestamp') or ''
            secondary = f"{game_mode}  |  {ship_killed or 'Ship'}  |   {ts}"
            location = rec.get('location') or rec.get('zone') or 'Unknown Location'
            coords = rec.get('coordinates') or rec.get('coords') or ''
            # occasional diagnostics to understand data shape if fields are missing
            nonlocal missing_loc_samples
            try:
                if ((not rec.get('location') and not rec.get('zone')) or not (rec.get('coordinates') or rec.get('coords'))):
                    if missing_loc_samples < 3:
                        keys_preview = ', '.join(list(rec.keys())[:15])
                        global_variables.log(f"[DetailsWindow] Missing location/coords for record — ts={rec.get('timestamp')}, mode={rec.get('game_mode')}, keys=[{keys_preview}]")
                        global_variables.log(f"[DetailsWindow] Record sample: {repr(rec)}")
                        missing_loc_samples += 1
            except Exception:
                pass
            # meta shows location; coordinates formatted separately in renderer
            meta = f"Location: {location}"
            border = '#c9b037' if _is_recent(str(ts)) else None
            org_pic = rec.get('org_picture')
            victim_img = rec.get('victim_image')
            org_sid = rec.get('org_sid')
            coords_raw = rec.get('coordinates') or rec.get('coords')
            return (title, secondary, meta, icon, accent, border, org_pic, org_sid, victim_img, coords_raw)
        except Exception:
            return ('Unknown Victim', None, None, getattr(app, 'icon_ship', None), '#3b82f6', None, None, None, None, None)

    normalized_cache = [_normalize_record(rec) for rec in sorted_items]

    total = len(normalized_cache)
    shown_count = 0

    def _update_status():
        try:
            status_lbl.config(text=f"Showing {shown_count} of {total} kills")
        except Exception:
            pass

    def _render_chunk(start_idx, count):
        nonlocal shown_count
        end = min(start_idx + count, total)
        for i in range(start_idx, end):
            try:
                title, secondary, meta, icon, accent, border, org_pic, org_sid, victim_img, coords_raw = normalized_cache[i]
                _add_card(all_col['container'], title, secondary, meta, icon, accent, border, org_picture_url=org_pic, org_sid_tooltip=org_sid, victim_image_url=victim_img, coords_value=coords_raw)
            except Exception:
                continue
        shown_count = end
        # let Tk recalc geometry then tighten scrollregion
        try:
            all_col['container'].update_idletasks()
        except Exception:
            pass
        _update_status()

    # Load more button; disabled when all rendered
    def _on_load_more():
        # render next chunk and disable if complete
        next_start = shown_count
        _render_chunk(next_start, CHUNK_SIZE)
        if shown_count >= total:
            try:
                load_more_btn.config(state=tk.DISABLED)
            except Exception:
                pass

    load_more_btn = tk.Button(btn_frame, text="Load more", command=_on_load_more, **style)
    load_more_btn.pack(side=tk.RIGHT, padx=(8, 0))

    # Close button (kept on the far right)
    tk.Button(btn_frame, text="Close", command=win.destroy, **style).pack(side=tk.RIGHT)

    # Initial render (cap large lists for responsiveness)
    initial = min(MAX_INITIAL, total)
    if initial > 0:
        _render_chunk(0, initial)
    else:
        try:
            tk.Label(all_col['container'], text="No kills found", font=("Times New Roman", 11), fg="#bcbcd8", bg="#1a1a1a").pack(padx=8, pady=8)
        except Exception:
            pass

    # If everything is shown already, disable the button
    if shown_count >= total:
        try:
            load_more_btn.config(state=tk.DISABLED)
        except Exception:
            pass

